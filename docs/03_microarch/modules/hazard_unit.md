# Hazard Detection Unit — Load-Use Stall Logic

**Module:** `hazard_unit`  
**Parent:** IP-001 RV32I 5-Stage Pipeline Core  
**Phase:** 3 — Microarch Designer  
**FR Trace:** FR-008  
**Research Ref:** B21(P&H §4.7:load-use stall), B4(L10:load-use hazard), B9(TTP010:valid_load_a5), B8(Ibex:load stall)  

---

## 1. Functional Description

The hazard detection unit detects load-use data hazards — situations where an instruction in the ID stage depends on the result of a load instruction currently in the EX stage. When such a hazard is detected, the unit asserts stall signals that freeze the IF and ID pipeline stages and insert a NOP (bubble) into the EX stage for one cycle. This single-cycle stall bridges the gap until the load data becomes available for forwarding from the MEM/WB stage.

This is the ONLY source of pipeline stalls in IP-001. All other data hazards (ALU→ALU, load→store) are resolved by forwarding without stalling.

---

## 2. Port List

| Signal | Direction | Width | Description |
|--------|-----------|-------|-------------|
| `id_ex_mem_read` | Input | 1 | Load instruction flag from ID/EX register |
| `id_ex_rd_addr` | Input | 5 | Destination register of instruction in EX stage |
| `if_id_rs1_addr` | Input | 5 | rs1 address of instruction in ID stage |
| `if_id_rs2_addr` | Input | 5 | rs2 address of instruction in ID stage |
| `stall_if` | Output | 1 | Stall IF stage (freeze PC and IF/ID register) |
| `stall_id` | Output | 1 | Stall ID stage (freeze ID/EX register, inject NOP into EX) |

---

## 3. Internal Block Diagram

```
  id_ex_mem_read ----+
                     |
  id_ex_rd_addr[4:0] +--->+---------------------------+
                      |    | LOAD-USE DETECT LOGIC     |
  if_id_rs1_addr[4:0]+--->|                           |
                      |    | match1 = (id_ex_rd != 0)  |
  if_id_rs2_addr[4:0]+--->|   && (id_ex_rd == rs1)    |
                      |    |                           |
                      |    | match2 = (id_ex_rd != 0)  |
                      |    |   && (id_ex_rd == rs2)    |
                      |    |                           |
                      |    | stall = id_ex_mem_read    |
                      |    |   && (match1 || match2)   |
                      |    +------------+--------------+
                      |                 |
                      |                 v
                      |            stall_if (= stall)
                      |            stall_id (= stall)
                      +-----------------+
                                        |
                                        v
                                  (to pipeline control)
```

## 4. Hazard Detection Logic

```
Hazard condition:
  stall = id_ex_mem_read                            // Load is in EX stage
          && (id_ex_rd_addr != 5'd0)                // Destination is not x0
          && (   (id_ex_rd_addr == if_id_rs1_addr)  // rs1 depends on load
              || (id_ex_rd_addr == if_id_rs2_addr)  // rs2 depends on load
             );
```

### Why These Conditions?

1. **`id_ex_mem_read = 1`:** Only loads create the load-use hazard. ALU instructions produce results in EX — they forward without stalling.

2. **`id_ex_rd_addr != 0`:** If the load writes to x0 (e.g., via a dummy load from address 0), there's no real dependency. x0 always reads as zero. Stalling for a write to x0 wastes a cycle.

3. **`id_ex_rd_addr == rs1/rs2`:** The dependent instruction in ID must actually USE the loaded register. If the load writes to x5 but the next instruction uses x6 and x7, no stall.

### What Happens During Stall

| Signal | Stall Cycle | Next Cycle (stall released) |
|--------|-------------|---------------------------|
| `stall_if` | 1 | 0 |
| `stall_id` | 1 | 0 |
| IF stage | PC frozen | PC increments (or target) |
| IF/ID register | Holds value | Captures new instruction |
| ID stage | Holds decoded signals | Decodes next instruction |
| ID/EX register | Receives NOP (bubble) | Receives stalled instruction |
| EX stage | Load continues | Receives stalled dependent instruction |

---

## 5. Store-After-Load — NO STALL

A special case: the instruction in ID is a store that uses the load destination as store data source (rs2).

```
LW  x5, 0(x10)     // EX stage: load to x5
SW  x5, 0(x11)     // ID stage: store x5 to memory
```

**Decision: NO STALL.** Store-after-load is handled by forwarding. The store instruction reaches EX in the cycle after the load reaches MEM. At that point, the load data is available in MEM/WB, and forwarding sends it directly to the store's rs2 (store data). The store doesn't need the data until MEM stage, giving an extra cycle.

This is a key optimization: the hazard unit does NOT stall for store-after-load. Only loads where the load destination feeds the ALU operand (rs1/rs2) of the next instruction trigger a stall.

---

## 6. Timing Behavior

- **Combinational:** Hazard detection is purely combinational. `stall_if` and `stall_id` are asserted in the same cycle the hazard is detected.
- **Stall duration:** Exactly ONE cycle. After one stall, the load reaches MEM/WB, and forwarding supplies the data to EX.
- **No consecutive stalls:** The hazard cannot persist across multiple cycles because (a) after one stall, the load moves to MEM and is no longer in EX, so the detection condition clears, and (b) even if the next instruction also depends on the same load, forwarding from MEM/WB resolves it.

---

## 7. Interface Contracts

### 7.1 From ID/EX Pipeline Register
- `id_ex_mem_read` — asserted when the instruction in EX is a load
- `id_ex_rd_addr` — destination register of the EX stage instruction

### 7.2 From IF/ID Pipeline Register
- `if_id_rs1_addr = IF/ID.instr[19:15]` — rs1 of instruction in ID
- `if_id_rs2_addr = IF/ID.instr[24:20]` — rs2 of instruction in ID

### 7.3 To Pipeline Control
- `stall_if`, `stall_id` — pipeline control uses these to generate:
  - PC write enable (stall_if → freeze PC)
  - IF/ID register write enable (stall_if → freeze IF/ID)
  - ID/EX register NOP insertion (stall_id → NOP into EX)

---

## 8. Design Notes and Constraints

1. **Comparator count:** 2 × 5-bit comparators + 2 × AND gates. ~100 GE. Minimal hardware.

2. **Timing:** Comparator + AND chain: ~5 gate delays ≈ 375 ps. Well within 20 ns cycle.

3. **Interaction with forwarding:** After the stall cycle, the load data is in MEM/WB. The forwarding unit detects the RAW from MEM/WB→EX and forwards correctly. The hazard unit ONLY detects load-use for stalling; forwarding handles the actual data routing.

4. **No false positives:** The detection conditions are exact. `rd_addr != 0` prevents stalls on trivial dependencies. The comparator is exact (not approximate).

5. **Gate count estimate:** ~200 GE (2 comparators + gates). Negligible.

---

## 9. Research References

| Source | Relevance |
|--------|-----------|
| B21 (P&H §4.7) | Load-use hazard detection conditions |
| B4 (L10 §2) | Load-use stall — identical conditions for 3-stage adapted to 5-stage |
| B9 (TTP010) | valid_load_a5 signal — stall generation pattern |
| B8 (Ibex) | Load stall implementation in production RISC-V core |

---

## 10. Per-Module Gate Checklist

- [ ] Load-use detection: mem_read(EX) && rd(EX) != 0 && (rd(EX) == rs1(ID) || rs2(ID))
- [ ] Stall signals: stall_if, stall_id both asserted on hazard
- [ ] Stall duration: exactly 1 cycle
- [ ] NO stall for load→store (rs2 only)
- [ ] NO stall when rd = x0
- [ ] NO stall for non-load instructions in EX
- [ ] Combinational detection (no state)
- [ ] FR-008 trace confirmed
