# IF Stage — Instruction Fetch Unit

**Module:** `if_stage`  
**Parent:** IP-001 RV32I 5-Stage Pipeline Core  
**Phase:** 3 — Microarch Designer  
**FR Trace:** FR-001, FR-009, FR-012  
**Research Ref:** B1(RV32I ISA §2.3), B4(L10:PC logic), B9(TTP010:5-stage IF), B21(P&H §4.5)  

---

## 1. Functional Description

The IF stage generates the program counter (PC) for instruction fetch. On each clock cycle (unless stalled), it outputs the instruction memory address (`i_addr`) and computes the next PC value. The next PC is normally PC+4 for sequential instruction fetch, but can be overridden by:

1. **Branch target** (from EX stage, when branch is taken)  
2. **JAL target** (PC + J-immediate, from ID stage)  
3. **JALR target** ((rs1 + I-immediate) & ~1, from ID stage)  
4. **Trap vector** (mtvec CSR value, on trap entry from CSR block)  
5. **MRET target** (mepc CSR value, on MRET from CSR block)  
6. **Reset vector** (0x0000_0000, on reset)

PC is held constant when the IF stage is stalled (load-use stall). On flush, PC is updated immediately to the new target.

---

## 2. Port List

| Signal | Direction | Width | Description |
|--------|-----------|-------|-------------|
| `clk` | Input | 1 | 50 MHz system clock |
| `rst_sync_n` | Input | 1 | Synchronous reset (active low) |
| `stall_if` | Input | 1 | Stall IF stage (from hazard unit) |
| `flush_if` | Input | 1 | Flush IF stage (from pipeline control) |
| `branch_taken` | Input | 1 | Branch was taken in EX (from EX stage via pipeline ctrl) |
| `branch_target` | Input | 32 | Branch target address (PC + B-immediate, from EX stage) |
| `jal_target` | Input | 32 | JAL target address (PC + J-immediate, from ID stage) |
| `jalr_target` | Input | 32 | JALR target address ((rs1 + I-immediate) & ~1, from ID stage) |
| `trap_target` | Input | 32 | Trap entry target (mtvec value, from CSR block) |
| `trap_taken` | Input | 1 | Trap entry active (from CSR block) |
| `mret_taken` | Input | 1 | MRET active (from CSR block) |
| `mret_target` | Input | 32 | MRET return address (mepc value, from CSR block) |
| `pc` | Output | 32 | Current program counter (to I-memory + IF/ID register) |
| `pc_plus4` | Output | 32 | PC + 4 (to IF/ID register for JAL link) |
| `i_addr` | Output | 32 | Instruction memory address (word-aligned: bits [1:0] = 00) |

---

## 3. Internal Block Diagram

```
                                +-------------------------+
  branch_target[31:0] --------->|                         |
  branch_taken -------+         |      PC NEXT MUX        |
  jal_target[31:0] ---+-------->|                         |
  jalr_target[31:0] --+-------->|   Priority:             |
  trap_target[31:0] --+-------->|   1. Reset  → 0x00000000|
  mret_target[31:0] -+--------->|   2. Trap   → mtvec     |
  pc_plus4[31:0] ----+--------->|   3. MRET   → mepc      |
                      |         |   4. Branch → br_target  |
  +--------+          |         |   5. JALR   → jalr_tgt   |
  | PC REG |<---------+         |   6. JAL    → jal_tgt    |
  |  32b   |                    |   7. Stall  → hold PC    |
  +----+---+                    |   8. Normal → PC+4       |
       |                        +------------+------------+
       |                                     |
       +-------> i_addr[31:0] (to I-Memory)   +------> pc+4 out
       |
       +-------> IF/ID_reg.pc (to next stage)
```

---

## 4. PC Next Mux Priority

| Priority | Condition | Next PC | Description |
|----------|-----------|---------|-------------|
| 1 (highest) | `rst_sync_n == 0` | 0x0000_0000 | Reset: PC to reset vector |
| 2 | `trap_taken == 1` | `trap_target` (mtvec) | Trap entry |
| 3 | `mret_taken == 1` | `mret_target` (mepc) | Return from trap |
| 4 | `branch_taken == 1` | `branch_target` | Taken branch target |
| 5 | `is_jalr == 1` | `jalr_target` | JALR target |
| 6 | `is_jal == 1` | `jal_target` | JAL target |
| 7 | `stall_if == 1` | `pc` (hold) | Load-use stall |
| 8 | `flush_if == 1` | `pc` (hold) | Flush without target change |
| 9 (lowest) | (default) | `pc + 4` | Sequential fetch |

**Note:** `flush_if` without any target change (e.g., external flush) holds PC. Taken branch, trap, JAL, JALR, and MRET all drive PC update AND assert flush. The `stall_if` signal freezes PC regardless of other conditions (except reset/trap which take priority).

---

## 5. Timing Behavior

- **Normal operation:** PC increments by 4 each clock cycle. `i_addr = pc[31:0]`. `pc_plus4 = pc + 4`.
- **Stall:** PC holds current value. `i_addr` holds. Instruction re-fetched next cycle.
- **Flush (taken branch/JAL/JALR/trap/MRET):** PC updated to target in current cycle. Next cycle fetches from target.
- **Reset:** PC forced to 0x0000_0000. Held while `rst_sync_n == 0`.

| Cycle | Condition | PC Value | i_addr | Next PC |
|-------|-----------|----------|--------|---------|
| T0 | Reset active | 0x0000_0000 | 0x0000_0000 | 0x0000_0000 |
| T1 | Normal (post-reset) | 0x0000_0000 | 0x0000_0000 | 0x0000_0004 |
| T2 | Normal | 0x0000_0004 | 0x0000_0004 | 0x0000_0008 |
| T3 | JAL to 0x100 | — | 0x0000_0008 | 0x0000_0100 |
| T4 | Normal (at target) | 0x0000_0100 | 0x0000_0100 | 0x0000_0104 |
| T5 | Stall (load-use) | 0x0000_0104 | 0x0000_0104 | 0x0000_0104 (held) |
| T6 | Normal (stall released) | 0x0000_0104 | 0x0000_0104 | 0x0000_0108 |

---

## 6. Interface Contracts

### 6.1 To/From Pipeline Control
- **Input:** `stall_if`, `flush_if` — asserted by pipeline control based on hazard/control conditions
- **Response:** PC holds on stall; PC holds on flush unless target override also asserted

### 6.2 To I-Memory Interface (IFR-001)
- `i_addr = pc` — always word-aligned (bits [1:0] = 00)
- Instruction data sampled from `i_rdata` in IF/ID pipeline register at cycle end
- No handshake — synchronous memory assumed

### 6.3 To IF/ID Pipeline Register
- `pc` — current PC of fetched instruction (for branch target calc, trap mepc save)
- `pc_plus4` — PC+4 (for JAL link writeback)

### 6.4 From EX Stage (via pipeline control)
- `branch_taken`, `branch_target` — from EX stage branch evaluation. `branch_target = pc + B_immediate` (computed in EX, not IF).

### 6.5 From ID Stage
- `jal_target = pc + J_immediate` (computed in ID for JAL)
- `jalr_target = (rs1_data + I_immediate) & ~1` (computed in ID for JALR)
- `is_jal`, `is_jalr` — decoded in ID stage

### 6.6 From CSR Block
- `trap_target` = mtvec CSR value
- `trap_taken` — asserted on trap entry
- `mret_target` = mepc CSR value
- `mret_taken` — asserted on MRET execution

---

## 7. Design Notes and Constraints

1. **Word-aligned addresses:** `i_addr[1:0]` is always 00. PC increments by 4 bytes. JAL/JALR targets have bit 0 cleared (see JALR: `target & ~1`). Branch targets have bit 0 implicitly zero (offset is multiple of 2 bytes, signed immediate shifted left by 1). This is enforced by the RISC-V ISA: all instructions are 16-bit aligned, and RV32I instructions are 32-bit aligned (bit 0 always 0).

2. **Speculative fetch:** Instructions are fetched speculatively (predict-not-taken). If branch is actually taken, the speculatively fetched instruction is flushed (NOP'd) in ID stage. No side effects from speculative fetch (read-only I-memory).

3. **PC register:** Single 32-bit D-type flip-flop register. Reset to 0x00000000. Updated on rising clock edge with next_pc value from priority mux.

4. **PC+4 adder:** Dedicated 32-bit adder (ripple-carry acceptable — 20 ns period, adder ~7 ns). Output is `pc + 32'd4`. This is a separate path from the branch target adder in EX stage (which uses `pc + B_immediate`).

5. **Stall vs flush interaction:** When both `stall_if` and a target change (branch/JAL/trap/MRET) occur simultaneously, the target change wins. `flush_if` from pipeline control is asserted alongside target signals. Stall only holds PC when no target change is pending.

6. **Gate count estimate:** ~400 GE (32-bit register + 32-bit adder + 9:1 mux tree). Part of IF stage.

7. **Critical path:** PC mux → PC register setup. Less than 1 ns — not a bottleneck.

---

## 8. Research References

| Source | Relevance |
|--------|-----------|
| B1 (RV32I ISA §2.3) | PC increment by 4, target alignment rules |
| B4 (L10 §3) | PC next logic, priority mux |
| B9 (TTP010) | 5-stage PC generation, stall/flush interaction |
| B21 (P&H §4.5) | IF stage design, pipeline register capture |

---

## 9. Per-Module Gate Checklist

- [ ] Module spec complete with port list
- [ ] PC next mux priority documented
- [ ] Reset vector = 0x00000000
- [ ] Stall behavior: PC holds
- [ ] Flush behavior: PC updates to target or holds
- [ ] JAL/JALR target LSB cleared
- [ ] i_addr is word-aligned
- [ ] No inferred latches in control logic
- [ ] All signals have defined widths
- [ ] FR-001, FR-009, FR-012 trace confirmed
