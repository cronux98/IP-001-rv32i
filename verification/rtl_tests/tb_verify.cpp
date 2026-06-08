// IP-001 RV32I — Verification Testbench (Verilator C++)
// Runs RTL with test binary, compares against Spike GRM
#include "Vrv32i_core.h"
#include "verilated.h"
#include "verilated_vcd_c.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <vector>
#include <string>
#include <fstream>
#include <sstream>
#include <map>

Vrv32i_core *top;
vluint64_t sim_time = 0;
const int MAX_CYCLES = 50000;

// Memory models (Harvard)
uint8_t i_mem[4096];  // 4KB instruction memory
uint8_t d_mem[4096];  // 4KB data memory

// Trace: register writes
struct RegWrite {
    int reg_num;
    uint32_t value;
    uint32_t pc;
};
std::vector<RegWrite> rtl_trace;

// Load binary into instruction memory
bool load_i_mem(const char *filename) {
    FILE *f = fopen(filename, "rb");
    if (!f) { fprintf(stderr, "ERROR: Cannot open %s\n", filename); return false; }
    fseek(f, 0, SEEK_END);
    size_t size = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (size > 4096) { fprintf(stderr, "ERROR: Binary too large (%zu > 4KB)\n", size); fclose(f); return false; }
    memset(i_mem, 0, 4096);
    fread(i_mem, 1, size, f);
    fclose(f);
    printf("Loaded %zu bytes into I-mem\n", size);
    return true;
}

// Fetch instruction from i_mem
uint32_t fetch_instr(uint32_t addr) {
    if (addr >= 4096) return 0x00000013; // NOP for OOB
    uint32_t aligned = addr & 0xFFC;
    return (i_mem[aligned] | (i_mem[aligned+1] << 8) |
            (i_mem[aligned+2] << 16) | (i_mem[aligned+3] << 24));
}

// Data memory access
uint32_t dm_read(uint32_t addr) {
    if (addr >= 4096) return 0;
    uint32_t aligned = addr & 0xFFC;
    return (d_mem[aligned] | (d_mem[aligned+1] << 8) |
            (d_mem[aligned+2] << 16) | (d_mem[aligned+3] << 24));
}

void dm_write(uint32_t addr, uint32_t data, uint8_t be) {
    if (addr >= 4096) return;
    uint32_t aligned = addr & 0xFFC;
    if (be & 1) d_mem[aligned]   = data & 0xFF;
    if (be & 2) d_mem[aligned+1] = (data >> 8) & 0xFF;
    if (be & 4) d_mem[aligned+2] = (data >> 16) & 0xFF;
    if (be & 8) d_mem[aligned+3] = (data >> 24) & 0xFF;
}

// Run Spike to get reference trace
std::vector<RegWrite> spike_trace;
void run_spike(const char *elf_file) {
    char cmd[1024];
    snprintf(cmd, sizeof(cmd),
        "spike --isa=rv32i -l --log-commits --pc=0x00000000 %s 2>&1",
        elf_file);
    
    FILE *p = popen(cmd, "r");
    if (!p) return;
    
    char line[256];
    while (fgets(line, sizeof(line), p)) {
        // Parse Spike commit log: core 0: 0x00000004 (0x00a00093) x1 0x0000000a
        uint32_t pc, instr, reg_val;
        int rd;
        if (sscanf(line, "core   0: 0x%08x (0x%08x) x%u 0x%08x", &pc, &instr, &rd, &reg_val) == 4) {
            spike_trace.push_back({rd, reg_val, pc});
        }
    }
    pclose(p);
}

void tick() {
    top->clk = 0; top->eval(); sim_time++;
    top->clk = 1; top->eval(); sim_time++;
}

void reset() {
    top->rst_n = 0;
    top->irq_timer = 0; top->irq_external = 0;
    top->i_rdata = 0x00000013;
    top->d_rdata = 0;
    for (int i = 0; i < 10; i++) tick();
    top->rst_n = 1;
    printf("Reset released at cycle %lu\n", sim_time / 2);
}

// Probe register file writes via debug ports
void capture_wb() {
    static uint8_t last_we = 0;
    uint8_t we = top->debug_rf_we;
    if (we && !last_we) {
        uint8_t rd = top->debug_rf_waddr;
        uint32_t data = top->debug_rf_wdata;
        uint32_t pc = top->debug_pc;
        if (rd != 0) {
            rtl_trace.push_back({(int)rd, data, pc});
        }
    }
    last_we = we;
}

// Check for magic completion value in data memory
bool check_magic(uint32_t expected_addr, uint32_t expected_val) {
    return dm_read(expected_addr) == expected_val;
}

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    Verilated::traceEverOn(true);
    
    top = new Vrv32i_core;
    
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <test_elf>\n", argv[0]);
        return 1;
    }
    
    const char *elf_file = argv[1];
    
    // Extract binary from ELF
    char bin_file[512];
    snprintf(bin_file, sizeof(bin_file), "%s.bin", elf_file);
    // Remove .elf extension if present
    char tmp[512];
    strncpy(tmp, elf_file, sizeof(tmp)-1);
    char *dot = strrchr(tmp, '.');
    if (dot) *dot = '\0';
    snprintf(bin_file, sizeof(bin_file), "%s.bin", tmp);
    
    // Convert ELF to binary using objcopy
    char cmd[1024];
    snprintf(cmd, sizeof(cmd), "riscv64-unknown-elf-objcopy -O binary %s %s 2>/dev/null", elf_file, bin_file);
    system(cmd);
    
    if (!load_i_mem(bin_file)) return 1;
    
    // Run Spike for reference trace
    printf("Running Spike...\n");
    run_spike(elf_file);
    printf("Spike trace: %zu instructions committed\n", spike_trace.size());
    
    // Reset RTL
    reset();
    memset(d_mem, 0, 4096);
    
    // Run simulation
    printf("Running RTL simulation...\n");
    uint32_t last_pc = 0;
    int stall_count = 0;
    
    for (int cycle = 0; cycle < MAX_CYCLES; cycle++) {
        // Provide instruction from i_mem
        uint32_t pc = top->debug_pc;
        top->i_rdata = fetch_instr(pc);
        
        // Handle data memory reads
        if (top->d_we) {
            dm_write(top->d_addr, top->d_wdata, top->d_be);
        }
        top->d_rdata = dm_read(top->d_addr);
        
        tick();
        capture_wb();
        
        // Check for completion (magic value at 0x1004)
        if (dm_read(0x1004) == 0xCAFEBABE) {
            printf("✅ MAGIC VALUE DETECTED at cycle %d — test reached completion\n", cycle);
            break;
        }
        
        // Stall detection
        if (pc == last_pc) {
            stall_count++;
            if (stall_count > 100) {
                printf("⚠️  CPU stalled at PC=0x%08x for >100 cycles — aborting\n", pc);
                break;
            }
        } else {
            stall_count = 0;
            last_pc = pc;
        }
    }
    
    printf("RTL trace: %zu register writes\n", rtl_trace.size());
    
    // Compare traces
    int matches = 0, mismatches = 0;
    int max_cmp = std::min((int)rtl_trace.size(), (int)spike_trace.size());
    
    // Build RTL trace map: for each register, the last value written
    std::map<int, uint32_t> rtl_final, spike_final;
    for (auto &w : rtl_trace) rtl_final[w.reg_num] = w.value;
    for (auto &w : spike_trace) spike_final[w.reg_num] = w.value;
    
    printf("\n═══ REGISTER COMPARISON (final written values) ═══\n");
    for (int r = 1; r <= 31; r++) {
        auto rit = rtl_final.find(r);
        auto sit = spike_final.find(r);
        uint32_t rv = (rit != rtl_final.end()) ? rit->second : 0;
        uint32_t sv = (sit != spike_final.end()) ? sit->second : 0;
        
        if (rit != rtl_final.end() || sit != spike_final.end()) {
            if (rv == sv) {
                if (rv != 0) printf("  x%-2d  RTL=0x%08x  SPIKE=0x%08x  ✅ MATCH\n", r, rv, sv);
                matches++;
            } else {
                printf("  x%-2d  RTL=0x%08x  SPIKE=0x%08x  ❌ MISMATCH\n", r, rv, sv);
                mismatches++;
            }
        }
    }
    
    printf("\n═══ MEMORY COMPARISON (data memory) ═══\n");
    // Check data memory for any writes
    bool mem_match = true;
    for (int a = 0x1000; a < 0x1020; a += 4) {
        uint32_t dv = dm_read(a);
        if (dv != 0) {
            printf("  DM[0x%04x] = 0x%08x\n", a, dv);
        }
    }
    
    printf("\n═══ VERDICT ═══\n");
    printf("Register matches:   %d\n", matches);
    printf("Register mismatches: %d\n", mismatches);
    if (mismatches == 0 && check_magic(0x1004, 0xCAFEBABE)) {
        printf("✅ TEST PASSED — All registers match, magic value detected\n");
    } else {
        printf("❌ TEST FAILED\n");
    }
    
    top->final();
    delete top;
    return mismatches > 0 ? 1 : 0;
}
