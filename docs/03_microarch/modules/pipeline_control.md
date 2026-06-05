# Pipeline Control — Stall, Flush, and NOP Insertion

**Module:** `pipeline_control`  
**Parent:** IP-001 RV32I 5-Stage Pipeline Core  
**Phase:** 3 — Microarch Designer  
**FR Trace:** FR-013  
**Research Ref:** B5(Roy §6:FSM design), B21(P&H §4.7:pipeline control), B9(TTP010:pipeline ctrl), B15(riscv-formal:properties)  

---

## 1. Functional Description

The pipeline control module manages the flow of instructions through the 5-stage pipeline by controlling stall and flush signals. It generates:

1. **Stall signals:** Freeze IF and ID stages (PC, IF/ID register, ID/EX register) during load-use hazard
2. **Flush signals:** Clear selected pipeline registers to NOP on control hazards (branch, jump, trap, MRET)
3. **Pipeline register write enables:** Enable/disable capture into IF/ID, ID/EX, EX/MEM, MEM/WB registers
4. **NOP insertion:** Route NOP (all control signals = 0) into ID/EX register during stall

The module is purely combinational — it does not maintain internal state. It takes stall requests from the hazard unit and flush requests from branch resolution, trap logic, and MRET, and generates the appropriate pipeline control signals.

---

## 2. Port List

| Signal | Direction | Width | Description |
|--------|-----------|-------|-------------|
| `stall_from_hazard` | Input | 1 | Load-use stall request (from hazard unit) |
| `branch_taken` | Input | 1 | Branch taken (from EX stage) |
| `is_jal` | Input | 1 | JAL instruction in ID stage |
| `is_jalr` | Input | 1 | JALR instruction in ID stage |
| `trap_taken` | Input | 1 | Trap entry (from CSR block) |
| `mret_taken` | Input | 1 | MRET (from CSR block / decoder) |
| `rst_sync_n` | Input | 1 | Synchronous reset |
| `if_id_reg_en` | Output | 1 | IF/ID register write enable (0 = freeze) |
| `id_ex_reg_en` | Output | 1 | ID/EX register write enable (0 = freeze) |
| `ex_mem_reg_en` | Output | 1 | EX/MEM register write enable |
| `mem_wb_reg_en` | Output | 1 | MEM/WB register write enable |
| `stall_if` | Output | 1 | Stall IF stage (freeze PC) |
| `stall_id` | Output | 1 | Stall ID stage |
| `flush_if` | Output | 1 | Flush IF stage → NOP (clear IF/ID register) |
| `flush_id` | Output | 1 | Flush ID stage → NOP (clear ID/EX register) |
| `flush_ex` | Output | 1 | Flush EX stage → NOP (clear EX/MEM register) |
| `flush_mem` | Output | 1 | Flush MEM stage → NOP (clear MEM/WB register) |
| `nop_into_ex` | Output | 1 | Insert NOP into ID/EX register (load-use bubble) |
| `pc_write_en` | Output | 1 | PC register write enable (0 = freeze) |

---

## 3. Internal Block Diagram

```
  stall_from_hazard  ──+
  branch_taken ────────+
  is_jal ──────────────+
  is_jalr ─────────────+────> +----------------------------+
  trap_taken ──────────+      |  FLUSH / STALL PRIORITY   |
  mret_taken ──────────+      |                            |
  rst_sync_n ──────────+      |  Priority:                 |
                              |  1. Reset → flush ALL     |
                              |  2. Trap  → flush IF,ID,EX|
                              |  3. MRET  → flush IF,ID,EX|
                              |  4. Branch→ flush IF,ID   |
                              |  5. JAL/JALR → flush IF   |
                              |  6. Stall → freeze IF,ID  |
                              +-------------+--------------+
                                            |
          +-----------+-----------+---------+---------+
          |           |           |         |         |
          v           v           v         v         v
    flush_if    flush_id    flush_ex    flush_mem  stall_if
    flush_id                                         stall_id
                                                     nop_into_ex
                                                     pc_write_en
```

---

## 4. Signal Generation Logic

### 4.1 Flush Signal Priority

```
  if (rst_sync_n == 0) begin
      // RESET: flush EVERYTHING
      flush_if  = 1;  flush_id  = 1;  flush_ex = 1;  flush_mem = 1;
      stall_if  = 0;  stall_id  = 0;  nop_into_ex = 0;
  end
  else if (trap_taken) begin
      // TRAP ENTRY: flush IF, ID, EX (trap inst is in EX, don't write back)
      flush_if  = 1;  flush_id  = 1;  flush_ex = 1;  flush_mem = 0;
      stall_if  = 0;  stall_id  = 0;  nop_into_ex = 0;
  end
  else if (mret_taken) begin
      // MRET: flush IF, ID, EX
      flush_if  = 1;  flush_id  = 1;  flush_ex = 1;  flush_mem = 0;
      stall_if  = 0;  stall_id  = 0;  nop_into_ex = 0;
  end
  else if (branch_taken) begin
      // TAKEN BRANCH: flush IF, ID (branch inst in EX, correctly fetched IF+ID)
      flush_if  = 1;  flush_id  = 1;  flush_ex = 0;  flush_mem = 0;
      stall_if  = 0;  stall_id  = 0;  nop_into_ex = 0;
  end
  else if (is_jal || is_jalr) begin
      // JAL/JALR: flush IF only (JAL decoded in ID, IF has next sequential)
      flush_if  = 1;  flush_id  = 0;  flush_ex = 0;  flush_mem = 0;
      stall_if  = 0;  stall_id  = 0;  nop_into_ex = 0;
  end
  else if (stall_from_hazard) begin
      // LOAD-USE STALL: freeze IF + ID, NOP into EX
      flush_if  = 0;  flush_id  = 0;  flush_ex = 0;  flush_mem = 0;
      stall_if  = 1;  stall_id  = 1;  nop_into_ex = 1;
  end
  else begin
      // NORMAL OPERATION
      flush_if  = 0;  flush_id  = 0;  flush_ex = 0;  flush_mem = 0;
      stall_if  = 0;  stall_id  = 0;  nop_into_ex = 0;
  end
```

### 4.2 Pipeline Register Write Enables

```
  pc_write_en    = !stall_if && !flush_if;  // Freeze PC on stall or flush
  if_id_reg_en   = !stall_if;               // Freeze IF/ID on stall
  id_ex_reg_en   = !stall_id;               // Freeze ID/EX on stall; on nop_into_ex, NOP mux selects

  ex_mem_reg_en  = 1;  // Always enabled (flush clears it via reset signal)
  mem_wb_reg_en  = 1;  // Always enabled
```

**Note on EX/MEM and MEM/WB:** These stages are never stalled. They either advance normally (capturing valid data) or are flushed to NOP by the flush signals. Flush is implemented by controlling the data input to the register (NOP mux), not by disabling the register enable. This is safer — it prevents stale data from persisting in downstream stages.

### 4.3 NOP Definition

A NOP instruction has all control signals = 0:
- `alu_op = 0000`, `alu_src_a = 0`, `alu_src_b = 0`
- `mem_read = 0`, `mem_write = 0`
- `wb_en = 0` (no writeback → RF write suppressed)
- `is_branch = 0`, `is_jal = 0`, `is_jalr = 0`, `is_csr = 0`
- `is_ecall = 0`, `is_ebreak = 0`, `is_illegal = 0`
- All other control signals = 0

This is equivalent to `ADDI x0, x0, 0` in RISC-V encoding, but specifically with all pipeline control signals zeroed.

---

## 5. Pipeline Register Control Detail

### 5.1 IF/ID Register
- **Normal:** Captures `{pc+4, instr}` on each cycle.
- **Stall (`if_id_reg_en = 0`):** Holds current value. Same instruction re-decoded next cycle.
- **Flush (`flush_if = 1`):** Captures NOP instruction (all zeroes or explicit NOP encoding).

### 5.2 ID/EX Register
- **Normal:** Captures decoded control signals + data.
- **Stall (`id_ex_reg_en = 0`):** Holds current value.
- **NOP insertion (`nop_into_ex = 1`):** Captures NOP values (all control signals = 0). This is the "bubble" during load-use stall.
- **Flush (`flush_id = 1`):** Captures NOP values.

### 5.3 EX/MEM Register
- **Normal:** Captures ALU result + control signals.
- **Flush (`flush_ex = 1`):** Captures NOP values. Used during trap entry to prevent trapping instruction's WB and CSR writes.

### 5.4 MEM/WB Register
- **Normal:** Captures memory data + ALU result + control signals.
- **Flush (`flush_mem = 1`):** Captures NOP values. Used during reset only.

---

## 6. Flush Propagation Timing

### Branch Flush (2-cycle penalty)
```
  Cycle N:   Branch in EX. branch_taken=1 (combinational from EX stage).
             flush_if=1, flush_id=1 generated.
             IF/ID and ID/EX capture NOP at end of cycle N.
  
  Cycle N+1: IF fetches from branch_target. PC updated.
             ID decodes NOP (what would have been fall-through).
             EX processes NOP (what would have been branch+1).

  Cycle N+2: IF fetches target+4. ID decodes target instruction.
             EX processes NOP. Pipeline resumes normal flow.
```

### Trap Flush
```
  Cycle N:   Trap detected. trap_taken=1. flush_if=1, flush_id=1, flush_ex=1.
             IF/ID, ID/EX, EX/MEM all capture NOP at end of cycle N.
             PC → mtvec. mepc ← pc_current.

  Cycle N+1: IF fetches from mtvec. ID/EX/EX stages contain NOPs.
  
  Cycle N+2: First handler instruction reaches ID.
```

### Load-Use Stall
```
  Cycle N:   Load in EX, dependent in ID. stall_from_hazard=1.
             stall_if=1, stall_id=1, nop_into_ex=1.
             IF/ID holds value. ID/EX captures NOP.
             PC frozen.

  Cycle N+1: Load in MEM, dependent in ID (re-decoded). Stall released.
             EX processes NOP (bubble).
             ID/EX captures dependent instruction.

  Cycle N+2: Load in WB, dependent in EX.
             Forwarding from MEM/WB → EX supplies load data.
             Dependent instruction executes correctly.
```

---

## 7. Simultaneous Events (Conflict Resolution)

### 7.1 Stall + Branch in Same Cycle
```
  Scenario: Load-use stall requested at the same time a branch is taken.
  
  Resolution: flush takes priority over stall (per priority chain).
  flush_if=1, flush_id=1. stall is overridden.
  
  Rationale: A taken branch redirects the instruction stream.
  The load whose dependency caused the stall was speculatively
  fetched and is being flushed anyway. The dependent instruction
  is also being flushed. The stall is moot.
```

### 7.2 Stall + Trap in Same Cycle
```
  Resolution: trap takes priority. All stages flushed.
  Stall request ignored.
```

### 7.3 JAL in ID + Load-Use Stall
```
  JAL is detected in ID (combinational from IF/ID register).
  If stall is also requested: flush takes priority.
  JAL flushes IF (flush_if=1). No stall needed — the instruction
  that would have been stalled is being flushed.
```

---

## 8. Timing Behavior

- **Combinational:** All pipeline control signals are generated combinationally from input conditions. No state machine.
- **Critical path:** Flush priority chain ≈ 6 gate delays ≈ 450 ps. Not critical.
- **Setup to pipeline registers:** Flush and enable signals must be stable before the clock edge that captures the pipeline register. With ~450 ps generation delay and ~200 ps setup, ~650 ps overhead — well within 20 ns cycle.

---

## 9. Interface Contracts

### 9.1 From Hazard Unit
- `stall_from_hazard` — load-use hazard detected. The only stall source.

### 9.2 From EX Stage
- `branch_taken` — branch condition evaluated to TRUE. Also asserted for JAL/JALR.

### 9.3 From ID Stage
- `is_jal`, `is_jalr` — JAL/JALR decoded. Flush IF stage.

### 9.4 From CSR Block
- `trap_taken` — trap entry active. Highest non-reset priority.
- `mret_taken` — MRET active.

### 9.5 To Pipeline Registers
- `if_id_reg_en`, `id_ex_reg_en`, `ex_mem_reg_en`, `mem_wb_reg_en` — write enables
- `flush_if`, `flush_id`, `flush_ex`, `flush_mem` — flush control (selects NOP mux)
- `nop_into_ex` — NOP insertion mux select for ID/EX register

### 9.6 To IF Stage
- `stall_if` — freeze PC
- `pc_write_en` — PC register write enable

---

## 10. Formal Verification Properties (Pre-Planning for Phase 5)

1. **Liveness:** If `stall_from_hazard` is asserted, it MUST be deasserted within 1 cycle (no infinite stalls).
2. **Deadlock freedom:** The combination `flush && stall` MUST NOT cause both signals to persist indefinitely. Flush overrides stall — proven by priority logic.
3. **NOP propagation:** After any flush or stall+flush sequence, all flushed registers MUST contain NOP values within 2 cycles.
4. **Reset completeness:** After `rst_sync_n` assertion, all pipeline registers MUST contain NOP within 1 cycle.
5. **No lost writes:** When `flush_ex = 1`, the instruction in EX MUST NOT write to the register file or CSRs (wb_en suppressed).

---

## 11. Design Notes and Constraints

1. **Combinational only:** No FSM state. All outputs are functions of current inputs. This avoids state-machine bugs (dead states, unreachable transitions) and simplifies formal verification.

2. **Flush > Stall priority:** Hardwired in the conditional chain. No arbitration circuit needed.

3. **NOP encoding:** All control signals zeroed for NOP. This naturally produces: no register write, no memory access, no ALU side effects, no CSR update. It's architecturally equivalent to `ADDI x0, x0, 0`.

4. **JAL/JALR flush scope:** Only IF is flushed for JAL/JALR (decoded in ID). The instruction after JAL/JALR in ID is the JAL/JALR itself — it proceeds normally through the pipeline (computes link address in EX, writes back in WB). Only IF is flushed because that's where the wrong next instruction was fetched.

5. **Gate count estimate:** ~300 GE (priority chain logic + per-stage enable/flush logic). Minimal — this is glue logic.

---

## 12. Research References

| Source | Relevance |
|--------|-----------|
| B5 (Roy §6) | FSM design methodology, 2-always-block pattern |
| B21 (P&H §4.7) | Pipeline control signals, stall/flush generation |
| B9 (TTP010) | Pipeline control in 5-stage RV32I, stall and flush timing |
| B15 (riscv-formal) | Formal properties for pipeline control (liveness, safety) |

---

## 13. Per-Module Gate Checklist

- [ ] Stall: freeze IF (PC + IF/ID) and ID (ID/EX) on load-use hazard
- [ ] NOP insertion: bubble into EX during stall
- [ ] Flush: taken branch flushes IF+ID
- [ ] Flush: JAL/JALR flushes IF only
- [ ] Flush: trap/MRET flushes IF+ID+EX
- [ ] Flush: reset flushes all stages (IF+ID+EX+MEM)
- [ ] Priority: reset > trap/MRET > branch > JAL/JALR > stall
- [ ] Stall+flush simultaneous: flush wins
- [ ] Pipeline register write enables correctly generated
- [ ] PC write enable: 0 during stall or flush
- [ ] NOP encoding: all control signals = 0, no side effects
- [ ] Combinational (no state, no latches)
- [ ] FR-013 trace confirmed
