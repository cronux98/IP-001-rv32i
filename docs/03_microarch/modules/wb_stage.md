# WB Stage — Writeback Unit

**Module:** `wb_stage`  
**Parent:** IP-001 RV32I 5-Stage Pipeline Core  
**Phase:** 3 — Microarch Designer  
**FR Trace:** FR-005  
**Research Ref:** B4(L10:WB mux), B9(TTP010:WB stage), B21(P&H §4.7:writeback), B1(RV32I:x0=zero)  

---

## 1. Functional Description

The WB stage selects the result to write back to the register file and controls the write enable. Results may come from four sources:

1. **ALU result** (R-type, I-type ALU, LUI, AUIPC)
2. **Memory read data** (load instructions: LB/LH/LW/LBU/LHU)
3. **PC + 4** (JAL, JALR link register)
4. **CSR read data** (CSR instructions: CSRRW/CSRRS/CSRRC)

The writeback stage also suppresses writes to x0 (registers x0 always reads as zero regardless of write data).

---

## 2. Port List

| Signal | Direction | Width | Description |
|--------|-----------|-------|-------------|
| `clk` | Input | 1 | 50 MHz system clock |
| `rst_sync_n` | Input | 1 | Synchronous reset (active low) |
| `alu_result` | Input | 32 | ALU result from MEM/WB register |
| `mem_rdata` | Input | 32 | Load data from MEM/WB register |
| `pc` | Input | 32 | PC from MEM/WB register |
| `csr_rdata` | Input | 32 | CSR read data from MEM/WB register |
| `rd_addr` | Input | 5 | Destination register address |
| `wb_en` | Input | 1 | Writeback enable |
| `wb_src` | Input | 2 | Writeback source select |
| `rf_wdata` | Output | 32 | Writeback data to register file |
| `rf_waddr` | Output | 5 | Writeback register address (rd) |
| `rf_we` | Output | 1 | Register file write enable |

---

## 3. Internal Block Diagram

```
  alu_result[31:0] ----+
  mem_rdata[31:0] -----+
  pc_plus4 (pc+4) -----+ 4:1 MUX
  csr_rdata[31:0] -----+   |
  wb_src[1:0] ---------+   |
                           v
                       wb_data_raw[31:0]
                            |
                            v
  rd_addr[5:0] ---------> x0 CHECK
  wb_en ---------------->   |
                            v
                       rf_wdata[31:0]
                       rf_waddr[4:0]
                       rf_we
```

### Writeback Source Mux

| wb_src[1:0] | Source | Used By |
|------------|--------|---------|
| 00 | `alu_result` | R-type, I-type ALU, LUI, AUIPC |
| 01 | `mem_rdata` | Load instructions |
| 10 | `pc` | JAL, JALR (link register = PC+4) |
| 11 | `csr_rdata` | CSR instructions |

---

## 4. x0 Write Suppression

```
rf_we   = wb_en  &&  (rd_addr != 5'd0)
rf_waddr = rd_addr
rf_wdata = wb_data_raw
```

When `rd_addr == 0` (x0), write enable is deasserted regardless of `wb_en`. This ensures x0 is never overwritten — it is hardwired to zero in the register file.

The RF still receives `rf_wdata` and `rf_waddr`, but `rf_we = 0` means no write occurs.

---

## 5. Writeback Enable by Instruction Type

| Instruction Type | wb_en | wb_src | Notes |
|-----------------|-------|--------|-------|
| R-type ALU (ADD, SUB, etc.) | 1 | 00 (ALU) | Standard writeback |
| I-type ALU (ADDI, SLTI, etc.) | 1 | 00 (ALU) | |
| LUI | 1 | 00 (ALU) | ALU passed imm through |
| AUIPC | 1 | 00 (ALU) | ALU computed PC+imm |
| Load (LB/LH/LW/LBU/LHU) | 1 | 01 (MEM) | Load data from memory |
| JAL | 1 | 10 (PC) | PC+4 as link address |
| JALR | 1 | 10 (PC) | PC+4 as link address |
| CSR (CSRRW/CSRRS/CSRRC) | 1 | 11 (CSR) | Old CSR value |
| CSR immediate variants | 1 | 11 (CSR) | Old CSR value |
| Store (SB/SH/SW) | 0 | — | No writeback |
| Branch (BEQ/BNE/etc.) | 0 | — | No writeback (unless link, N/A for RV32I) |
| ECALL | 0 | — | No writeback |
| EBREAK | 0 | — | No writeback |
| FENCE/FENCE.I | 0 | — | NOP |
| Illegal instruction | 0 | — | Trap — WB suppressed |

---

## 6. Timing Behavior

- **Write occurs on rising clock edge** of WB stage. Data from MEM/WB register is written to register file.
- **Read-during-write:** If an instruction in ID reads a register being written in WB (same cycle), the register file may return old or new data. This is NOT a hazard — the forwarding unit has already forwarded the data from MEM/WB to EX stage before the write even occurs. By the time the data is in WB, the consumer has already used the forwarded value.

---

## 7. Interface Contracts

### 7.1 From MEM/WB Pipeline Register
- All inputs come from MEM/WB. `pc` is PC+4 for JAL/JALR link (PC+4 is stored in MEM/WB.pc from the original IF stage PC+4).

### 7.2 To Register File
- `rf_wdata` — selected writeback data
- `rf_waddr` — destination register (rd)
- `rf_we` — write enable (0 for x0, stores, branches, NOPs)

### 7.3 To Forwarding Unit
- The forwarding unit monitors `rf_waddr` (rd) and `rf_we` from the MEM/WB register to determine if forwarding is needed.

---

## 8. Design Notes and Constraints

1. **Static mux:** The writeback mux is a simple 4:1 multiplexer. ~75 ps delay. Not on critical path.

2. **PC+4 storage:** The PC stored in the pipeline registers is the PC of the instruction (from IF stage). For JAL/JALR, the link value is PC+4, which is stored as `pc_plus4` in the IF/ID register and propagated through the pipeline as `pc`. The writeback stage selects `pc` for wb_src=10, which is already PC+4.

3. **Gate count estimate:** ~150 GE (4:1 32-bit mux + x0 comparator + AND gate). Minimal.

4. **WB stage inactivity:** Many instructions don't write back (stores, branches). The WB stage still operates — it produces `rf_we = 0` and the register file ignores the write. This simplifies pipeline control (no need to "skip" WB stage).

---

## 9. Research References

| Source | Relevance |
|--------|-----------|
| B4 (L10 §3) | WB mux design, x0 write suppression |
| B9 (TTP010) | WB stage in 5-stage pipeline |
| B21 (P&H §4.7) | Writeback stage operation |
| B1 (RV32I) | x0 hardwired to zero |

---

## 10. Per-Module Gate Checklist

- [ ] 4:1 writeback mux: ALU/MEM/PC/CSR
- [ ] WB source codes match instruction types
- [ ] x0 write suppression: rf_we = 0 when rd_addr = 0
- [ ] Stores, branches: rf_we = 0
- [ ] JAL/JALR: wb_src = PC (PC+4)
- [ ] Register file write on rising clock edge
- [ ] rf_waddr, rf_wdata valid when rf_we = 1
- [ ] FR-005 trace confirmed
