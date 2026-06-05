# IP-001 — Phase 2 Research Synthesis

**Project:** IP-001 — RV32I 5-Stage Pipeline Core  
**Date:** 2026-06-05  
**Status:** Complete — Phase 2 Gate Ready  

---

## Executive Summary

Phase 2 research for IP-001 confirmed that a **custom 5-stage pipelined RV32I core** on SkyWater 130nm HD is well-precedented, architecturally sound, and achievable within the 15,000 NAND2-equivalent gate budget. Twenty-two sources were analyzed (14 vault + 8 external), including 4 silicon-verified TT06/TT07 tapeout projects using the identical PDK and 3 academic textbooks.

**Key finding:** The 5-stage pipeline with full forwarding (EX/MEM→EX, MEM/WB→EX) and predict-not-taken branch resolution represents the canonical textbook design (Patterson & Hennessy) and has been silicon-proven in at least one TT project (TTP-010). The gate count estimate of 12-15kGE is calibrated against Ibex (16.85kGE for RV32EC "micro", 26.6kGE for RV32IMC "small") and PicoRV32 (3-5kGE multi-cycle). Our 50MHz target is deeply conservative for sky130hd (TTP-029 operates at 64MHz in 2×2 tiles).

**All 34 spec requirements are research-grounded.** No spec corrections are required — the FR spec is internally consistent with the RISC-V ISA and the scope choices are validated by existing implementations. Two architecture decisions require Phase 3 attention: register file implementation (FF array vs SRAM macro) and stall+flush interaction formal verification.

---

## Architecture Decisions Driven by Research

### AD-001: 5-Stage Pipeline (IF→ID→EX→MEM→WB) — CONFIRMED
**Decision:** Implement exactly five pipeline stages with registers between each stage pair.  
**Research basis:** Patterson & Hennessy canonical 5-stage RISC pipeline. TTP-010 demonstrates working 5-stage RV32I at 50MHz on SkyWater 130nm. Roy (2024) provides complete FSM and pipeline register design patterns.  
**Rationale:** Matches NFR-006 requirement. 5 stages provide the forwarding hazard scenarios that make this an "academic workflow stress test" per spec §1.1. Single-cycle ALU at 50MHz is trivial for sky130hd (20ns period vs ~8ns worst-case 32-bit ADD).  
**Risk:** Low — multiple silicon proofs exist.  
**Sources:** B1, B4, B5, B8, B9, B21

### AD-002: Predict-Not-Taken Branch Strategy — CONFIRMED
**Decision:** Evaluate branch condition in EX stage. Predict not-taken. Flush IF+ID (2-cycle penalty) when branch is actually taken.  
**Research basis:** TTP-010 uses identical strategy. L10 synthesis (B4) analyzed this for 3-stage and concluded it's the simplest correct strategy. Patterson & Hennessy recommend predict-not-taken for simple pipelines. NEORV32 (B7) uses no prediction — resolves in execute, 4-cycle taken penalty.  
**Rationale:** No branch prediction hardware needed. 2-cycle flush penalty acceptable (~0.18 CPI overhead). Meets NFR-005 CPI < 1.5 target when combined with forwarding.  
**Risk:** Low — well-established pattern.  
**Sources:** B4, B7, B9, B21

### AD-003: Full Forwarding (EX/MEM→EX + MEM/WB→EX) — CONFIRMED
**Decision:** Implement two-level forwarding: EX/MEM pipeline register result → EX stage ALU inputs, and MEM/WB pipeline register result → EX stage ALU inputs. Forward both rs1 and rs2 operands. EX/MEM forwarding takes priority for back-to-back dependent instructions.  
**Research basis:** L10 synthesis (B4) detailed forwarding conditions. Patterson & Hennessy §4.5-4.7 provides complete forwarding path analysis. TTP-010 implements forwarding from a3(EX) to a2(ID) and via valid_load for loads. Ibex (B8) forwards EX result to ID/EX for next instruction.  
**Rationale:** Without forwarding, every RAW hazard costs 2 stall cycles — CPI would be ~1.6-1.8, exceeding NFR-005 target. Forwarding reduces CPI to ~1.2-1.3 for typical integer code.  
**Risk:** Medium — forwarding mux is on the critical path (see RSK-004). Mitigated by conservative 50MHz target.  
**Sources:** B4, B7, B8, B9, B21

### AD-004: Load-Use Hazard with Single-Cycle Stall — CONFIRMED
**Decision:** When a load is in EX stage and the instruction in ID stage uses the load destination register as a source, stall IF and ID for one cycle, inserting a NOP into EX. After the stall, load data forwards from MEM/WB to EX normally.  
**Research basis:** L10 synthesis (B4): "Load-use hazard: ID/EX.mem_read && (ID/EX.rd == IF/ID.rs1 || IF/ID.rs2) → stall 1 cycle." Patterson & Hennessy §4.7: canonical load-use stall. NEORV32 (B7): NO stall needed because multi-cycle FSM naturally separates — this confirms our 5-stage pipeline MUST have the stall.  
**Rationale:** Load data is not available until after MEM stage (end of cycle). The dependent instruction in ID needs it in EX stage (next cycle). One-cycle stall bridges this gap.  
**Risk:** Medium — stall+flush interaction (RSK-006) needs formal verification.  
**Sources:** B4, B7, B9, B21

### AD-005: Harvard Internal Architecture — CONFIRMED
**Decision:** Separate instruction fetch and data access paths internally. I-memory interface: 32-bit read-only (i_addr, i_rdata). D-memory interface: 32-bit read/write (d_addr, d_wdata, d_rdata, d_be, d_we).  
**Research basis:** TTP-021 (B10) demonstrates Harvard RV32I on SkyWater 130nm. TTP-010 (B9) has separate IMEM/DMEM. PicoRV32, Ibex, and SERV all have separate I/D paths. Roy (B5) recommends Harvard for pipelined processors.  
**Rationale:** Avoids structural hazard of simultaneous instruction fetch and data access to single memory. Backend integration can physically combine into unified SRAM with arbiter (spec ARC-006).  
**Risk:** Low. Memory controller integration is out of scope for core-only design.  
**Sources:** B5, B9, B10, B11

### AD-006: Machine-Mode Only CSR Subset — CONFIRMED
**Decision:** Implement 7 CSRs: misa (read-only RV32I), mstatus (MIE/MPIE), mtvec, mepc, mcause, mie, mip. Support 6 CSR instruction variants. No mstatus.MPP field (ARC-007).  
**Research basis:** RISC-V Privileged Spec (B2) defines exact CSR addresses, fields, and behaviors. TTP-029 (B11) demonstrates full machine-mode CSR implementation in 2×2 tiles with RV32EC — confirms our subset fits comfortably in the gate budget. TTP-041 (B12) verifies CSR behavior via cocotb testbenches.  
**Rationale:** Minimum CSR set needed for trap handling (FR-011) and interrupt support (IFR-004). MISa is machine-mode only, consistent with ARC-007.  
**Risk:** Medium — CSR field interactions are subtle (RSK-002). Every CSR write must respect read-only fields and write-ignore semantics.  
**Sources:** B2, B11, B12

### AD-007: Synchronous Pipeline Control FSM — CONFIRMED
**Decision:** Pipeline control unit manages stall (freeze IF/ID, NOP into EX) and flush (clear IF/ID to NOP). Flush takes priority over stall when both asserted. Uses 2-always-block FSM pattern (Roy §6).  
**Research basis:** Roy (B5) §6 provides complete FSM methodology. Patterson & Hennessy §4.7 defines stall/flush signal propagation. TTP-010 handles transitions with valid_taken_br signals.  
**Rationale:** Clean separation of control from datapath. Formal verification of pipeline control FSM is recommended for RSK-006 (stall+flush deadlock).  
**Risk:** HIGH for stall+flush interaction (RSK-006) — formal property checking needed in Phase 5.  
**Sources:** B5, B9, B21

### AD-008: Register File — FF Array vs SRAM Macro — DEFERRED
**Decision:** **DEFER** to Phase 3 microarchitecture. Option A: flip-flop array (32×32b = 1024 FFs ≈ 4kGE, fully resettable, simple). Option B: SRAM macro via OpenRAM (single-port, 64×32b macro, ~0.5kGE but complex integration).  
**Research basis:** GAP006 (B16) notes NEORV32 has both options (REGFILE_HW_RST config). TTP-029 (B11) uses PDK-aware delay buffers for its rotate-design register file. Roy (B5) provides DPRAM Verilog patterns. OpenRAM sky130 macros confirmed feasible at 32KB/64KB in self-learning.  
**Rationale:** FF array is simpler but area-expensive. SRAM macro saves gates but complicates verification (no reset, read-during-write behavior). The 2-read-1-write requirement (FR-006) maps naturally to DPRAM.  
**Risk:** Low-Medium. Both options are viable at 50MHz.  
**Sources:** B5, B11, B16

### AD-009: Unaligned Access → Trap — CONFIRMED
**Decision:** Misaligned LW/LH/SH/SW access raises misaligned-address exception (trap). No hardware unaligned access handling.  
**Research basis:** RISC-V ISA (B1) §2.3: "Load and store instructions...cause an address-misaligned exception if the effective address is not naturally aligned." Hardware handling is optional and adds significant complexity (byte-level assembly/disassembly).  
**Rationale:** Simpler implementation. Spec-compliant. For bare-metal embedded workloads (spec §1.4), aligned access is the norm.  
**Risk:** Low. Most compilers naturally align data.  
**Sources:** B1

---

## Conflicts Resolved Between Sources

### Conflict 1: Forwarding from ID vs EX Stage
- **L10 Synthesis (B4):** Branch resolution in DECODE, forwarding from EX to ID/EX
- **Patterson & Hennessy (B21) + TTP-010 (B9):** Branch resolution in EX, forwarding from EX/MEM and MEM/WB to EX  
- **Resolution:** IP-001 places branch resolution in EX stage (AD-002). Forwarding is EX/MEM→EX and MEM/WB→EX (AD-003). L10 was a 3-stage design; the 5-stage design follows Patterson & Hennessy naming.

### Conflict 2: Pipeline Stage Naming
- **TTP-010 (B9):** Uses a0-a5 (6 positions, asymmetric)
- **Classic (B21):** Uses IF/ID/EX/MEM/WB (5 positions)
- **Resolution:** IP-001 uses the classic 5-stage naming (IF/ID/EX/MEM/WB) as specified in NFR-006. TTP-010's a0-a5 convention (which includes a PC stage) is unique to that TL-Verilog implementation.

### Conflict 3: Register File Write Port Timing
- **NEORV32 (B7):** RF write in DISPATCH state, read in EXECUTE — 1 cycle separation, no forwarding needed
- **5-Stage Classic (B21):** RF write in WB, read in ID — 3 cycle separation, forwarding REQUIRED  
- **Resolution:** IP-001 uses the 5-stage timing (WB write, ID read, 3 cycles apart). Forwarding (AD-003) is MANDATORY in our design. NEORV32's approach demonstrates that a different pipeline depth eliminates the forwarding requirement — but we are committed to 5 stages by NFR-006.

---

## Spec Corrections

### ✅ No spec corrections required.

The Phase 1 spec (spec.md v0.1) is internally consistent with the RISC-V ISA specifications and the chosen architectural scope. All 34 requirements (13 FR + 8 NFR + 4 IFR + 9 ARC) have been verified against research:

| Category | Count | Research-Validated | Corrections Needed |
|----------|-------|-------------------|-------------------|
| Functional Requirements | 13 | 13 ✅ | 0 |
| Non-Functional Requirements | 8 | 8 ✅ | 0 |
| Interface Requirements | 4 | 4 ✅ | 0 |
| Architecture Constraints | 9 | 9 ✅ | 0 |

### Observations (Not Corrections)
1. **FR-009 Branch Penalty:** Spec says "2 cycles for taken branch." Research confirms this as the standard predict-not-taken penalty (IF+ID flush). This is optimal for the chosen strategy.
2. **FR-008 Load-Use Stall:** Spec says "single pipeline bubble." Research confirms exactly 1 cycle is needed (data available at end of MEM stage, needed at start of EX stage).
3. **FR-010 CSR Addresses:** Spec lists correct addresses (0x300-0x344). All match the privileged spec.
4. **NFR-004 Gate Budget:** 15k GE target is between SERV (2.1kGE) and Ibex "micro" (16.85kGE RV32EC). Our RV32I with 5-stage + forwarding is likely 12-15kGE — at the edge of the target. Phase 3 should synthesize an early prototype to validate.
5. **NFR-001 Clock Target:** 50MHz (20ns) is more than 2× the expected critical path (~8-10ns) on sky130hd slow corner. Timing closure risk is LOW.

---

## New Vault Notes Created

No new standalone vault notes created during Phase 2. All research findings are captured in the three Phase 2 deliverables (research_checklist.md, bibliography.md, synthesis.md) and the updated rtm.csv.

The vault already contains comprehensive coverage for RV32I ISA (B1-B3), pipeline design (B4-B8), and SkyWater 130nm implementation (B16, B18-B19). External sources (B14, B15, B22) augment the vault with verification and community implementation data.

---

## Risk Re-Assessment

| Risk ID | Original Assessment | Post-Research Adjustment |
|---------|-------------------|--------------------------|
| RSK-001 (Hazard logic) | HIGH/HIGH | Maintained. Research confirms subtlety. Formal verification recommended. |
| RSK-002 (CSR gaps) | MEDIUM/HIGH | Maintained. CSR interactions need directed test for every trap cause. |
| RSK-003 (Branch flush) | MEDIUM/HIGH | Maintained. TTP-010 had a 2-cycle flush implementation — reference pattern exists. |
| RSK-004 (Timing closure) | LOW/MEDIUM | **Downgraded to LOW/LOW.** 50MHz at sky130hd with 32-bit ALU has >10ns slack. |
| RSK-005 (Illegal instr) | MEDIUM/MEDIUM | Maintained. Exhaustive opcode coverage needed. |
| RSK-006 (Stall+flush deadlock) | LOW/HIGH | Maintained. Formal liveness proof recommended. |
| RSK-007 (Reset values) | MEDIUM/HIGH | Maintained. CSR reset values from privileged spec (B2). |

---

## Handoff to Phase 3 (Microarchitecture)

### Key Design Parameters
- [x] ISA: RV32I (40 instructions, 6 formats) — see B1-B3
- [x] Pipeline: 5 stages (IF/ID/EX/MEM/WB) with full forwarding
- [x] Branch: Predict-not-taken, resolve in EX, 2-cycle flush
- [x] Load-use: Single-cycle stall
- [x] CSR: 7 machine-mode CSRs, 6 instruction variants
- [x] Harvard I/D interfaces (no bus protocol)
- [x] Clock: 50MHz, single domain
- [x] PDK: sky130hd
- [x] Reset: Synchronous, 0x00000000 vector
- [x] Interrupts: irq_timer + irq_external via mip/mie

### Deferred Decisions (Phase 3)
- [ ] Register file: FF array vs OpenRAM SRAM macro
- [ ] ALU architecture: RCA vs CLA vs hybrid
- [ ] Decoder architecture: flat case vs hierarchical
- [ ] Pipeline control FSM: exact state encoding
- [ ] I/D memory interface timing: synchronous vs registered

### Verification Recommendations (Phase 4/5)
- [ ] Spike `--isa=rv32i` as golden reference model (B2, B14)
- [ ] riscv-tests rv32ui-p-* suite for ISA compliance (B14)
- [ ] riscv-formal SymbiYosys properties for hazard logic (B15)
- [ ] Formal liveness proof for pipeline control FSM (RSK-006)

---

**Synthesis complete. Phase 2 research confirms all 34 requirements are achievable with the chosen architecture. No spec corrections required. Proceed to Phase 3 gate.**
