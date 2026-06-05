# IP-001 — RV32I 5-Stage Pipeline Core: Golden Reference Model Specification

**Document:** grm_specification.md  
**Phase:** 4 — GRM Engineer  
**Date:** 2026-06-05  
**Author:** Sage (GRM Engineer)  
**Dependencies:** spec.md v0.1, microarchitecture.md, all module specs, synthesis.md  
**Tier:** Medium  

---

## 1. GRM Architecture Overview

### 1.1 Strategy

The Golden Reference Model (GRM) for IP-001 uses **Spike RISC-V ISA Simulator** as the architectural golden reference for all RV32I instruction execution, wrapped in a Python orchestration layer that provides:

1. **Programmatic invocation** of Spike with correct ISA and memory configuration
2. **Register file state capture** (x0–x31) at instruction granularity
3. **CSR state capture** for all 7 machine-mode CSRs
4. **Memory state capture** for verification of load/store behavior
5. **Execution trace generation** in a format comparable to DUT simulation output
6. **Trace comparison engine** for Phase 5 cocotb scoreboard integration

### 1.2 Why Spike?

| Criterion | Spike | Custom C++ Model | Pure Python |
|-----------|-------|------------------|-------------|
| ISA accuracy | **Gold standard** — maintained by RISC-V Foundation | Error-prone — must re-implement all 40 instructions | Slow — Python isn't cycle-accurate |
| CSR behavior | Full privileged spec compliance | Must hand-code 7 CSRs with field interactions | Same |
| Trap handling | Correct trap entry/exit sequences | Complex FSM to get right | Same |
| Maintenance | Upstream updates for free | Burden on project team | Same |
| riscv-tests | Direct execution | Must port test framework | Same |

**Decision:** Spike as GRM core, Python as wrapper/orchestrator. Spike provides correctness; Python provides programmability.

### 1.3 Architecture Diagram

```
+------------------------------------------------------------------+
|                    GRM SYSTEM ARCHITECTURE                        |
|                                                                  |
|  +------------------+     +------------------+                   |
|  |  riscv-tests     |     |  Custom Tests    |                   |
|  |  (rv32ui-p-*)    |     |  (hand-written)  |                   |
|  +--------+---------+     +--------+---------+                   |
|           |                        |                             |
|           v                        v                             |
|  +------------------+     +------------------+                   |
|  | riscv64-gcc      |     | Assembly (.S)    |                   |
|  | compile + link   |     | → ELF binary     |                   |
|  +--------+---------+     +--------+---------+                   |
|           |                        |                             |
|           +----------+-------------+                             |
|                      v                                           |
|             +-------------------+                                |
|             |   ELF Binary      |                                |
|             +--------+----------+                                |
|                      |                                           |
|                      v                                           |
|  +------------------------------------------+                    |
|  |          spike_grm.py                     |                    |
|  |                                          |                    |
|  |  +-------------+    +-----------------+  |                    |
|  |  | SpikeRunner  |    | TraceParser     |  |                    |
|  |  | (subprocess) |--->| (parse -l log)  |  |                    |
|  |  +------+------+    +--------+--------+  |                    |
|  |         |                    |           |                    |
|  |         v                    v           |                    |
|  |  +-----------------------------+        |                    |
|  |  |       GRMState              |        |                    |
|  |  |  - regfile[32] (x0-x31)     |        |                    |
|  |  |  - csr[7] (named CSRs)      |        |                    |
|  |  |  - memory dict              |        |                    |
|  |  |  - pc, cycle count          |        |                    |
|  |  |  - execution trace          |        |                    |
|  |  +-----------------------------+        |                    |
|  +------------------------------------------+                    |
|                      |                                           |
|                      v                                           |
|  +------------------------------------------+                    |
|  |          compare_trace.py                 |                    |
|  |  - Compare DUT trace vs GRM trace         |                    |
|  |  - Per-instruction register diff          |                    |
|  |  - CSR state diff                         |                    |
|  |  - Memory state diff                      |                    |
|  +------------------------------------------+                    |
|                      |                                           |
|                      v                                           |
|             +-------------------+                                |
|             |  Pass/Fail Report |                                |
|             +-------------------+                                |
+------------------------------------------------------------------+
```

---

## 2. Spike Configuration

### 2.1 Command-Line Invocation

```bash
spike \
  --isa=rv32i \          # RV32I base integer ISA only
  --priv=m \              # Machine-mode only
  -m0x80000000:0x1000 \   # Memory region at reset vector (4KB I-mem)
  -m0x80001000:0x1000 \   # Data memory region (4KB D-mem)  
  -l \                    # Generate execution trace log
  --log=<logfile> \       # Trace output file
  <elf_binary>
```

**Note on memory addresses:** Spike's `-m` option specifies core physical memory. The memory map from Phase 3 has I-mem at `0x0000_0000` and D-mem at `0x0000_1000`. Spike maps memory contiguously. We use a single 8KB region covering both:

```bash
spike --isa=rv32i --priv=m -m0x0:0x2000 -l --log=spike_trace.log <elf>
```

This provides 4KB at `0x0000_0000`–`0x0000_0FFF` (I-mem) and 4KB at `0x0000_1000`–`0x0000_1FFF` (D-mem), matching the microarchitecture memory map exactly.

### 2.2 ISA String

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `--isa` | `rv32i` | RV32I base integer ISA only — no M, C, F, D, A extensions |
| `--priv` | `m` | Machine-mode only — no user or supervisor modes |

### 2.3 Spike Limitations vs Our Microarchitecture

| Feature | Spike Behavior | Our Microarchitecture | Impact |
|---------|---------------|----------------------|--------|
| Pipeline | Single-cycle-per-instruction model (functional) | 5-stage pipeline with stalls/flushes | GRM trace must be reordered by retirement order for cycle-accurate comparison |
| Memory latency | Zero-cycle memory access | Single-cycle synchronous memory | Compatible — our memory responds in one cycle |
| Instruction timing | All instructions complete in 1 "cycle" | Forwarding, load-use stalls extend timing | Compare by instruction count, not cycle count |
| Register file | x0–x31, all read/write internally | x0 hardwired to zero | GRM must mask x0 writes from comparison |
| CSR reset values | Full privileged spec defaults | Our subset with specific resets | GRM config overrides to match our reset values |
| MRET behavior | Full spec compliance | Simplified (MIE←MPIE, MPIE←1) | Match our simplified behavior in GRM CSR model |
| Trap vector mode | Supports vectored mode | Direct mode only | Configure Spike for direct mode; GRM validates direct-only |
| Memory access | Byte-addressable, unaligned OK | Misaligned access traps | GRM must handle misaligned gracefully (Spike does) |

### 2.4 Instruction Retirement Trace (Spike `-l` Format)

Spike's `-l` log produces commit-log format:

```
core   0: 0x00000000 (0x00000093) x1 0x00000000
core   0: 0x00000004 (0x00000113) x2 0x00000020
```

Format: `core <hart>: <pc> (<instruction_hex>) <rd> <rd_value>`

For stores: `core <hart>: <pc> (<instruction_hex>) mem <addr> <value>`

Our parser extracts: PC, instruction word, destination register, written value, memory accesses.

---

## 3. Python Wrapper Design

### 3.1 Class Hierarchy

```
grm_config.py
  └── GRMConfig — Memory map, CSR map, reset values, platform constants

spike_grm.py
  ├── SpikeRunner — Subprocess management for spike binary
  ├── TraceParser  — Parse spike -l commit log into structured trace
  ├── TraceEntry   — Single instruction trace entry (namedtuple)
  ├── GRMState     — Snapshot of architectural state (regs, CSRs, memory)
  └── SpikeGRM     — Top-level GRM (orchestrates SpikeRunner + TraceParser)

run_grm.py
  └── CLI entry point for running tests through the GRM

compare_trace.py
  └── Compare two traces (GRM vs DUT) and report diffs
```

### 3.2 SpikeGRM Public API

```python
class SpikeGRM:
    """Golden Reference Model wrapping Spike RISC-V simulator."""

    def __init__(self, config: GRMConfig):
        """Initialize GRM with platform configuration."""

    def run_elf(self, elf_path: str, timeout: int = 30) -> GRMTrace:
        """Run an ELF binary through Spike and capture complete trace.
        Returns GRMTrace with all retired instructions."""

    def run_step(self, elf_path: str) -> Iterator[GRMState]:
        """Run a binary step-by-step, yielding GRMState after each instruction.
        For interactive/debug verification."""

    def get_final_state(self) -> GRMState:
        """Get final architectural state after simulation."""

    def check_available(self) -> bool:
        """Verify Spike is installed and accessible."""

    def get_version(self) -> str:
        """Return Spike version string."""

class GRMState:
    regfile: Dict[int, int]     # x0-x31 (x0 always 0)
    csr: Dict[str, int]         # Named CSRs (mstatus, misa, etc.)
    pc: int                     # Current program counter
    instret: int                # Instructions retired
    memory: Dict[int, int]      # Byte-addressable memory snapshot

    def to_dict(self) -> dict: ...
    def compare_regs(self, other: 'GRMState') -> List[str]: ...
    def compare_csrs(self, other: 'GRMState') -> List[str]: ...
    def compare_memory(self, other: 'GRMState') -> List[str]: ...
```

### 3.3 TraceEntry Structure

```python
TraceEntry = namedtuple('TraceEntry', [
    'index',        # int: 0-based instruction index
    'pc',           # int: program counter
    'instr_word',   # int: 32-bit instruction encoding
    'rd',           # int or None: destination register number
    'rd_value',     # int or None: value written to rd
    'is_store',     # bool: this is a store instruction
    'store_addr',   # int or None: store address
    'store_value',  # int or None: store value
    'is_load',      # bool: this is a load instruction (inferred)
    'load_addr',    # int or None: load address (inferred from prior trace)
    'branch_taken', # bool or None: conditional branch was taken
    'branch_target',# int or None: branch/jump target PC
])
```

### 3.4 GRMConfig Constants

```python
@dataclass
class GRMConfig:
    # Memory map (matches Phase 3 microarchitecture)
    IMEM_BASE: int = 0x0000_0000
    IMEM_SIZE: int = 0x1000      # 4 KB
    DMEM_BASE: int = 0x0000_1000
    DMEM_SIZE: int = 0x1000      # 4 KB
    TOTAL_MEM: int = 0x2000      # 8 KB total

    # Reset configuration
    RESET_VECTOR: int = 0x0000_0000
    RESET_PC: int = 0x0000_0000

    # CSR addresses (RISC-V privileged spec)
    CSR_MSTATUS: int = 0x300
    CSR_MISA: int = 0x301
    CSR_MIE: int = 0x304
    CSR_MTVEC: int = 0x305
    CSR_MEPC: int = 0x341
    CSR_MCAUSE: int = 0x342
    CSR_MIP: int = 0x344

    # CSR reset values (must match microarchitecture §4.3)
    CSR_RESET: Dict[int, int] = field(default_factory=lambda: {
        0x300: 0x0000_0000,   # mstatus: MIE=0, MPIE=0
        0x301: 0x4000_0100,   # misa: RV32, no extensions
        0x304: 0x0000_0000,   # mie: all disabled
        0x305: 0x0000_0000,   # mtvec: direct mode, base=0
        0x341: 0x0000_0000,   # mepc: undefined
        0x342: 0x0000_0000,   # mcause: undefined
        0x344: 0x0000_0000,   # mip: no pending interrupts
    })

    # Spike configuration
    SPIKE_BINARY: str = "spike"
    SPIKE_ISA: str = "rv32i"
    SPIKE_PRIV: str = "m"

    # RISC-V toolchain
    RISCV_GCC: str = "riscv64-unknown-elf-gcc"
    RISCV_OBJCOPY: str = "riscv64-unknown-elf-objcopy"
    RISCV_OBJDUMP: str = "riscv64-unknown-elf-objdump"

    # Linker script (simplified: text at 0x0, data at 0x1000)
    LINKER_SCRIPT: str = "link.ld"
```

---

## 4. Memory Map Configuration (Spike)

### 4.1 Memory Region Definition

```
+=====================================================================+
|                     SPIKE MEMORY MAP                                  |
+=====================================================================+
| START ADDR    | END ADDR      | SIZE  | REGION          | ACCESS     |
+---------------+---------------+-------+-----------------+------------+
| 0x0000_0000   | 0x0000_0FFF   | 4 KB  | Instruction Mem | R/X        |
| 0x0000_1000   | 0x0000_1FFF   | 4 KB  | Data Memory     | R/W        |
+=====================================================================+

Spike invocation:
  spike --isa=rv32i --priv=m -m0x0:0x2000 -l --log=trace.log <elf>
```

Spike provides a flat 8KB memory space at physical address `0x0000_0000`. The Harvard split is conceptual — in Spike, there is a single physical memory space, and the SRAM model is unified. Our microarchitecture has separate I/D paths, but Spike's unified model is functionally equivalent since:
1. Instruction fetches only occur from executable regions
2. Data accesses only from load/store
3. No self-modifying code (Harvard constraint) — verified by testbench

### 4.2 Memory Content Extraction

After simulation completes, the Python wrapper extracts memory contents:

```python
def _extract_memory_state(self, spike_output: str) -> Dict[int, int]:
    """Parse spike memory state from its dump.
    
    Strategy: Run spike with a small post-simulation script that
    dumps memory regions, OR use objdump to extract .data section
    and compare against expected.
    
    Alternative: Run a second spike invocation with GDB-mode memory peek,
    OR extract from the trace log (stores capture memory state).
    
    Recommended: Reconstruct from store trace entries.
    """
```

---

## 5. CSR Initialization and Validation

### 5.1 CSR State Tracking

Spike's `-l` log does NOT dump CSR values. To capture CSR state, we use one of two strategies:

**Strategy A — GDB Interface (preferred):**
```bash
# Start spike in debug mode, connect via GDB/socket
spike --isa=rv32i --priv=m -d -s <elf> &
# Use Python pexpect to interact with spike debugger
```

**Strategy B — Post-execution CSR dump (alternative):**
Insert a custom exit routine in the test binary that reads all CSRs and writes them to a known memory location, then parse from memory dump.

**Strategy C — Trace-based inference (fallback):**
Infer CSR state from the trace: CSR instructions appear as writes to `xN` with the old CSR value. The new CSR value is known from the instruction encoding.

### 5.2 Implemented Strategy

**We implement Strategy A (GDB interface via pexpect)** as primary, with **Strategy C (trace inference)** as fallback.

For self-tests (where Spike is installed and we just need basic validation), we use Strategy B — each test program explicitly reads and stores CSR values to memory before exiting.

### 5.3 CSR Validation Checklist

| CSR | Check | Method |
|-----|-------|--------|
| misa | Read-only, reset = 0x4000_0100 | Test program reads misa, stores to memory |
| mstatus | MIE[3], MPIE[7] field read/write | Test program writes MIE, reads back |
| mtvec | BASE[31:2] writable, MODE[1:0] = 00 | Test program writes mtvec, reads back |
| mepc | Trap entry: saves PC; MRET: restores PC | Trap test program |
| mcause | Trap entry: saves cause code | Trap test program |
| mie | MTIE[7], MEIE[11] writable | Test program writes mie, reads back |
| mip | RO from hardware; MTIP[7], MEIP[11] reflect pins | Cannot fully test without interrupts wired |

---

## 6. Test Plan

### 6.1 Self-Test Suite (Phase 4)

| Test | File | What It Tests | Spike Dependency |
|------|------|--------------|------------------|
| T4.1 Spike availability | `test_spike_basic.py` | Spike binary found, launches, produces trace | Yes |
| T4.2 Instruction class test | `test_grm_instructions.py` | Each RV32I instruction class produces correct result | Yes |
| T4.3 CSR test | `test_grm_csr.py` | CSR read/write/set/clear behavior | Yes |
| T4.4 Trap test | `test_grm_traps.py` | ECALL, EBREAK, illegal instruction trap handling | Yes |
| T4.5 Trace parsing | (in test_spike_basic) | Spike log parsing into TraceEntry objects | Yes |
| T4.6 riscv-tests integration | (documentation) | Official riscv-tests RV32I suite | Yes |

### 6.2 riscv-tests Integration (Phase 5 Prep)

```
riscv-tests repo: https://github.com/riscv-software-src/riscv-tests
Build: git clone && cd riscv-tests && autoconf && ./configure --prefix=/tmp/riscv-tests
       make ISA=rv32i
Run:   spike --isa=rv32i riscv-tests/isa/rv32ui-p-add
       spike --isa=rv32i riscv-tests/isa/rv32ui-p-simple
       ... (all rv32ui-p-* tests)
```

### 6.3 Performance Metrics (Phase 4 Baseline)

| Metric | Target | Method |
|--------|--------|--------|
| Instructions per test run | Varies by test | Count trace entries |
| Spike simulation time | < 0.1s per test | `time` wrapper |
| Trace parse time | < 0.01s per test | Python `time.perf_counter()` |
| Memory footprint (GRM) | < 50 MB | Python `tracemalloc` |

---

## 7. Known Limitations

1. **Cycle-approximate only.** Spike is a functional simulator, not a cycle-accurate model. The GRM cannot replicate pipeline stalls, forwarding delays, or branch flush penalties. Phase 5 verification must compare instruction-level results, not cycle-level timing.

2. **CSR state inference.** Spike's `-l` log does not directly export CSR state. The CSR tracking relies on GDB interface or explicit test program self-reporting.

3. **Memory ordering.** Spike executes instructions atomically; the Harvard architecture's implicit separation of I/D memory is not modeled. Self-modifying code detection must be handled by the verilog testbench, not the GRM.

4. **Interrupt modeling.** Spike does not model external interrupt inputs in the same way as our hardware. Interrupt tests rely on explicit trap injection via CSR manipulation or pre-set mip bits. A full interrupt latency test requires the DUT simulation.

5. **Reset behavior.** Spike's internal state initialization differs from our microarchitecture reset values. The GRM wrapper explicitly validates CSR reset values through test programs rather than assuming Spike defaults.

6. **x0 write suppression.** Spike internally allows x0 to be read as zero but may show non-zero "write" values in traces (e.g., `x0 0xDEADBEEF`). The GRM comparison engine must mask x0 writes — treat x0 as always 0 regardless of Spike trace data.

7. **Misaligned access.** Spike handles misaligned loads/stores by default. Our microarchitecture traps on misaligned access. The GRM must be configured to validate the trap path, not the hardware-unaligned path. For misaligned access tests: configure Spike to trap (if possible) or verify that our DUT traps while Spike silently handles.

---

## 8. File Inventory

| File | Path | Purpose |
|------|------|---------|
| GRM Specification | `docs/04_grm/grm_specification.md` | This document |
| GRM Configuration | `grm/src/grm_config.py` | Memory map, CSR addresses, platform constants |
| Main GRM Module | `grm/src/spike_grm.py` | SpikeGRM class, SpikeRunner, TraceParser, GRMState |
| CLI Runner | `grm/src/run_grm.py` | Command-line interface to run tests through GRM |
| Trace Comparison | `grm/src/compare_trace.py` | Compare GRM trace vs DUT trace |
| Makefile | `grm/Makefile` | Build and test targets |
| Requirements | `grm/requirements.txt` | Python dependencies |
| Spike Basic Test | `grm/tests/test_spike_basic.py` | Spike availability + trace parsing |
| Instruction Test | `grm/tests/test_grm_instructions.py` | Each instruction class through Spike |
| CSR Test | `grm/tests/test_grm_csr.py` | CSR read/write/set/clear behavior |
| Trap Test | `grm/tests/test_grm_traps.py` | Trap entry/exit validation |
| Linker Script | `grm/binaries/link.ld` | Linker script for test binaries |
| Test Assembly | `grm/binaries/*.S` | Hand-written assembly test programs |
| riscv-tests Script | `grm/binaries/build_riscv_tests.sh` | Build and run riscv-tests suite |

---

## 9. Phase 4 Gate Checklist

See `subagent-checklists.md` Phase 4 section. Self-assessment to be completed after deliverables created.

---

*GRM specification complete. Proceed to source implementation.*
