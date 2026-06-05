# Forwarding Unit — RAW Hazard Resolution

**Module:** `forwarding_unit`  
**Parent:** IP-001 RV32I 5-Stage Pipeline Core  
**Phase:** 3 — Microarch Designer  
**FR Trace:** FR-007  
**Research Ref:** B21(P&H §4.5-4.7:forwarding), B4(L10:EX→EX forwarding), B9(TTP010:a3→a2 forwarding), B8(Ibex:forwarding)  

---

## 1. Functional Description

The forwarding unit detects Read-After-Write (RAW) data hazards and controls the forwarding multiplexers in the EX stage. It compares the destination register of instructions in the EX/MEM and MEM/WB pipeline registers against the source registers (rs1, rs2) of the instruction currently in the EX stage. When a match is found, forwarding is enabled to bypass the register file and feed the latest result directly to the ALU inputs.

Two levels of forwarding are provided:
1. **EX/MEM forwarding:** The result from the previous instruction (currently in MEM stage) forwards to the EX stage ALU inputs.
2. **MEM/WB forwarding:** The result from two instructions ago (currently in WB stage) forwards to the EX stage ALU inputs.

**Priority rule:** EX/MEM forwarding takes precedence over MEM/WB forwarding when both match (back-to-back dependent instructions — the EX/MEM result is newer).

---

## 2. Port List

| Signal | Direction | Width | Description |
|--------|-----------|-------|-------------|
| `id_ex_rs1_addr` | Input | 5 | rs1 address of instruction in EX stage |
| `id_ex_rs2_addr` | Input | 5 | rs2 address of instruction in EX stage |
| `ex_mem_wb_en` | Input | 1 | WB enable of instruction in MEM stage |
| `ex_mem_rd_addr` | Input | 5 | Destination register of instruction in MEM stage |
| `ex_mem_alu_result` | Input | 32 | ALU result from EX/MEM register (forw. data) |
| `mem_wb_wb_en` | Input | 1 | WB enable of instruction in WB stage |
| `mem_wb_rd_addr` | Input | 5 | Destination register of instruction in WB stage |
| `mem_wb_wb_data` | Input | 32 | WB data from MEM/WB register (forwarding data) |
| `fwd_a_sel` | Output | 2 | Forwarding mux A select (to EX stage) |
| `fwd_b_sel` | Output | 2 | Forwarding mux B select (to EX stage) |
| `exmem_fwd_data` | Output | 32 | Forwarded data from EX/MEM (wired to EX stage) |
| `memwb_fwd_data` | Output | 32 | Forwarded data from MEM/WB (wired to EX stage) |

---

## 3. Internal Block Diagram

```
  +-------------------------------------------------------------+
  |                     FORWARDING UNIT                          |
  |                                                             |
  |  MATCH DETECTION (per operand):                             |
  |                                                             |
  |  FORWARD A (rs1):                                           |
  |    ex_fwd_a = ex_mem_wb_en && ex_mem_rd != 0                |
  |               && (ex_mem_rd == id_ex_rs1)                   |
  |    mem_fwd_a = mem_wb_wb_en && mem_wb_rd != 0               |
  |                && (mem_wb_rd == id_ex_rs1)                  |
  |                && !ex_fwd_a  // EX/MEM priority            |
  |                                                             |
  |  FORWARD B (rs2):                                           |
  |    ex_fwd_b = ex_mem_wb_en && ex_mem_rd != 0                |
  |               && (ex_mem_rd == id_ex_rs2)                   |
  |    mem_fwd_b = mem_wb_wb_en && mem_wb_rd != 0               |
  |                && (mem_wb_rd == id_ex_rs2)                  |
  |                && !ex_fwd_b  // EX/MEM priority            |
  |                                                             |
  |  OUTPUT ENCODING:                                           |
  |    fwd_a_sel = ex_fwd_a ? 2'b01 : (mem_fwd_a ? 2'b10 : 2'b00) |
  |    fwd_b_sel = ex_fwd_b ? 2'b01 : (mem_fwd_b ? 2'b10 : 2'b00) |
  +-------------------------------------------------------------+
                         |               |
                         v               v
              fwd_a_sel[1:0]     fwd_b_sel[1:0]
              (to EX stage)      (to EX stage)

  exmem_fwd_data = ex_mem_alu_result  (wired pass-through)
  memwb_fwd_data = mem_wb_wb_data     (wired pass-through)
```

---

## 4. Forwarding Selection Encoding

| fwd_sel[1:0] | Source | Data | When |
|-------------|--------|------|------|
| 00 | ID/EX register | `rs1_data` or `rs2_data` | No hazard (default) |
| 01 | EX/MEM forwarding | `ex_mem_alu_result` | Previous instruction writes rd that matches rs1/rs2 |
| 10 | MEM/WB forwarding | `mem_wb_wb_data` | Two-ago instruction writes rd that matches, AND no EX/MEM match |

---

## 5. Forwarding Scenarios

### Scenario 1: ALU → ALU (EX/MEM forwarding)
```
ADD x5, x1, x2    // EX stage: writing x5
SUB x6, x5, x3    // ID stage: reading x5 as rs1
```
- `ex_mem_wb_en = 1`, `ex_mem_rd = 5`, `id_ex_rs1 = 5`
- Match: `ex_fwd_a = 1`. `fwd_a_sel = 01` (forward from EX/MEM).
- SUB receives forwarded ALU result of ADD for rs1. **No stall.**

### Scenario 2: Two-Instruction Gap (MEM/WB forwarding)
```
ADD x5, x1, x2    // MEM stage
OR  x7, x4, x3    // EX stage
SUB x6, x5, x8    // ID stage: reading x5
```
- SUB is in EX, ADD is in MEM. `ex_mem_rd` is OR's destination (x7), not x5.
- `mem_wb_wb_en = 1`, `mem_wb_rd = 5` (ADD's destination). `id_ex_rs1 = 5`.
- `ex_fwd_a = 0` (EX/MEM doesn't match), `mem_fwd_a = 1`.
- `fwd_a_sel = 10` (forward from MEM/WB). **No stall.**

### Scenario 3: Back-to-Back Dependencies (EX/MEM priority)
```
ADD x5, x1, x2    // MEM stage: writing x5
ADD x5, x5, x3    // EX stage: reading x5 (rs1), writing x5
SUB x6, x5, x4    // ID stage: reading x5 (rs1)
```
- For SUB's rs1: both EX/MEM and MEM/WB match x5.
- EX/MEM priority: `ex_fwd_a = 1` → `fwd_a_sel = 01`.
- MEM/WB match is ignored (`mem_fwd_a = 0` because `ex_fwd_a = 1`).
- SUB gets the most recent value of x5 (from the second ADD). **Correct!**

### Scenario 4: Load → ALU (Load-Use — stall + MEM/WB forwarding)
```
LW  x5, 0(x10)    // EX stage: load x5
ADD x6, x5, x3    // ID stage: uses x5 as rs1 → STALL
```
- The hazard unit detects this and stalls IF/ID for 1 cycle.
- After stall: LW in MEM, ADD in EX. ADD's rs1 = 5.
- `ex_mem_rd` = LW destination (5). But LW result isn't in `ex_mem_alu_result` — it's in `mem_wb_wb_data`.
- After stall cycle: LW in MEM/WB, ADD in EX. `mem_wb_rd = 5`. Forward from MEM/WB.
- `fwd_a_sel = 10`. ADD receives load data forwarded from MEM/WB.

### Scenario 5: x0 Destination — No forwarding
```
ADDI x0, x1, 5    // Write to x0 — but x0 is hardwired to zero
ADD  x5, x0, x2   // Read x0 — should get 0, NOT 5
```
- `ex_mem_rd = 0`. The condition `ex_mem_rd != 0` fails.
- `fwd_a_sel = 00` (no forwarding). ADD reads x0 as 0 from register file.
- **Correct!** Forwarding is suppressed for x0.

---

## 6. Store Instruction Forwarding

When the instruction in EX is a store, the store data (rs2) may need forwarding:

```
ADD x5, x1, x2    // EX: writing x5
SW  x5, 0(x10)    // ID: store x5 to memory
```
- In the next cycle, SW is in EX. SW's rs2 = 5.
- `ex_mem_rd = 5`, `id_ex_rs2 = 5`. `ex_fwd_b = 1`.
- `fwd_b_sel = 01`. Store data gets forwarded from EX/MEM. **No stall needed.**
- The forwarded value goes to `rs2_data_out` in EX stage (which is the forwarded operand_b), feeding directly into the store data path in the MEM stage.

---

## 7. Timing Behavior

- **Combinational:** Forwarding detection and selection signals are purely combinational. Produced in the same cycle.
- **Timing criticality:** Forwarding mux is on the ALU critical path. The detection logic runs in parallel with the pipeline register read and doesn't add to the path directly (the mux select arrives before the data).
- **Comparator depth:** 5-bit comparator ≈ 5 gate delays ≈ 375 ps. Select encoding ≈ 150 ps. Total detection ≈ 525 ps. Parallel to register read path.

---

## 8. Interface Contracts

### 8.1 From ID/EX Pipeline Register
- `id_ex_rs1_addr`, `id_ex_rs2_addr` — source registers needing forwarding check

### 8.2 From EX/MEM Pipeline Register
- `ex_mem_wb_en`, `ex_mem_rd_addr` — previous instruction's write target
- `ex_mem_alu_result` — ALU result (forwarding data source for EX/MEM path)

### 8.3 From MEM/WB Pipeline Register
- `mem_wb_wb_en`, `mem_wb_rd_addr` — two-ago instruction's write target
- `mem_wb_wb_data` — writeback data (forwarding data source for MEM/WB path)

### 8.4 To EX Stage
- `fwd_a_sel[1:0]`, `fwd_b_sel[1:0]` — mux select signals
- `exmem_fwd_data`, `memwb_fwd_data` — actual forwarding data (bypassed from pipeline registers)

---

## 9. Design Notes and Constraints

1. **EX/MEM priority:** Always forward the most recent value. If both EX/MEM and MEM/WB match the same register, EX/MEM wins. This is critical for correctness with back-to-back writes to the same register.

2. **x0 suppression:** Forwarding is suppressed when `rd_addr == 0`. This is checked on both EX/MEM and MEM/WB. Even though WB stage suppresses x0 writes, we check here defensively.

3. **No forwarding for non-writing instructions:** `wb_en = 0` for stores, branches, NOPs → no forwarding from those stages.

4. **Forwarding data passthrough:** `exmem_fwd_data` and `memwb_fwd_data` are direct wire connections from the pipeline registers. The forwarding unit doesn't modify or delay them — it only provides select signals.

5. **Gate count estimate:** ~800 GE (4 × 5-bit comparators ~200 GE + priority + encoding logic ~200 GE + data passthrough muxes in EX stage ~400 GE). The bulk of forwarding area is in the EX stage muxes, not the detection logic.

---

## 10. Research References

| Source | Relevance |
|--------|-----------|
| B21 (P&H §4.5-4.7) | Forwarding paths, RAW detection, priority rules |
| B4 (L10 §2) | Forwarding conditions for RV32I, x0 suppression |
| B9 (TTP010) | a3→a2 forwarding in 5-stage pipeline |
| B8 (Ibex) | Forwarding from EX to ID/EX in production core |
| B16 (GAP006) | Forwarding vs no-forwarding trade-off analysis |

---

## 11. Per-Module Gate Checklist

- [ ] EX/MEM forwarding: ex_mem_wb_en && ex_mem_rd != 0 && ex_mem_rd == rs1/rs2
- [ ] MEM/WB forwarding: mem_wb_wb_en && mem_wb_rd != 0 && mem_wb_rd == rs1/rs2
- [ ] EX/MEM priority overrides MEM/WB when both match
- [ ] x0 forwarding suppressed (rd != 0 check)
- [ ] Separate fwd_a and fwd_b path (independent for rs1/rs2)
- [ ] Store operand forwarding (rs2 forward to store data)
- [ ] Combinational (no state, no latches)
- [ ] Forwarding data passthrough from pipeline registers
- [ ] FR-007 trace confirmed
