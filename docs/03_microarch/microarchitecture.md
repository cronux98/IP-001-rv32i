# IP-001 — RV32I 5-Stage Pipeline Core: Microarchitecture Specification

**Document:** microarchitecture.md  
**Phase:** 3 — Microarch Designer  
**Date:** 2026-06-05  
**Author:** Sage (Microarch Designer)  
**Dependencies:** spec.md v0.1, synthesis.md, bibliography.md (22 sources), research_checklist.md  

---

## 1. Top-Level Block Diagram

```
+===========================================================================================+
|                         RV32I 5-STAGE PIPELINE CORE — TOP LEVEL                           |
|                                                                                           |
|                              +----------------------+                                     |
|                              |    PIPELINE CONTROL   |                                     |
|                              |  stall_if, stall_id,  |                                     |
|                              |  flush_if, flush_id,  |                                     |
|                              |  flush_ex, nop_ctrl   |                                     |
|                              +--^---^---^---^---^----+                                     |
|                                 |   |   |   |   |                                          |
|  +--------+   IF_ID_REG  +--------+   |   |   |   +--------+   WB_MUX   +-----------+     |
|  |   IF   |---[IR,PC]--->|   ID   |   |   |   |   |   WB   |<---[rd_data]| REGISTER  |     |
|  | STAGE  |              | STAGE  |   |   |   |   | STAGE  |---[we,wd]-->|   FILE    |     |
|  +--+--+--+              +--+--+--+   |   |   |   +---^----+            | 32x32 2R1W|     |
|     |  |                    |  |  |    |   |   |       |                 +-----+-----+     |
|     |  |   +----------+     |  |  |    |   |   |       |                       |           |
|     |  +-->| FORWARD  |<----+  |  |    |   |   |  +----+----+        +--------+--------+  |
|     |  |   |  UNIT    |<-------+  |    |   |   |  |   CSR   |<------>|    HAZARD      |  |
|     |  |   | (raw haz)|<----------+    |   |   |  |  BLOCK  |        |   DETECTION    |  |
|     |  |   +---^---^--+               |   |   |  +----+----+        | (load-use chk) |  |
|     |  |       |   |                  |   |   |       |             +----------------+  |
|     |  |   [fwd_a/fwd_b]              |   |   |       |                                   |
|  +--v--v-+ ID_EX_REG +--v--v-+ EX_MEM_REG +--v--v-+ MEM_WB_REG                           |
|  |  (to) |--[ctl]--->|  EX   |--[res]--->|  MEM  |--[mem_dat]-->                         |
|  |  (EX) |           | STAGE |           | STAGE |                                        |
|  +-------+           +-------+           +-------+                                        |
|      ^                   ^                   ^                                            |
|      |                   |                   |                                            |
|  +---+---------------+---+----+    +---------+---------+                                  |
|  |   INSTRUCTION MEMORY I/F  |    |  DATA MEMORY I/F  |                                  |
|  |  i_addr[31:0]  (out)      |    |  d_addr[31:0] (out)|                                  |
|  |  i_rdata[31:0] (in)       |    |  d_rdata[31:0] (in)|                                  |
|  +---------------------------+    |  d_wdata[31:0](out)|                                  |
|                                   |  d_be[3:0]   (out) |                                  |
|                                   |  d_we        (out) |                                  |
|                                   +---------------------+                                  |
|                                                                                           |
|  EXTERNAL PORTS:  clk, rst_n, irq_timer, irq_external                                     |
+===========================================================================================+

PIPELINE REGISTERS (between each stage pair):
  IF/ID_reg:  pc[31:0], instr[31:0]
  ID/EX_reg:  pc[31:0], rs1_data[31:0], rs2_data[31:0], imm[31:0],
              rd_addr[4:0], alu_op[3:0], alu_src_a, alu_src_b,
              mem_read, mem_write, mem_width[1:0], mem_sign_ext,
              wb_en, wb_src[1:0], csr_op[1:0], csr_addr[11:0],
              branch_op[2:0], is_branch, is_jal, is_jalr, is_csr,
              is_ecall, is_ebreak, is_illegal, funct3[2:0]
  EX/MEM_reg: pc[31:0], alu_result[31:0], rs2_data[31:0],
              rd_addr[4:0], mem_read, mem_write, mem_width[1:0],
              mem_sign_ext, wb_en, wb_src[1:0], csr_rdata[31:0],
              is_csr, is_ecall, is_ebreak, is_illegal, branch_taken,
              branch_target[31:0], is_jal, is_jalr
  MEM/WB_reg: pc[31:0], alu_result[31:0], mem_rdata[31:0],
              rd_addr[4:0], wb_en, wb_src[1:0], csr_rdata[31:0]
```

---

## 2. Module Inventory

| # | Module | File | Function | FR Trace |
|---|--------|------|----------|----------|
| 1 | `if_stage` | modules/if_stage.md | PC generation, I-mem address, PC+4, target mux | FR-001, FR-009, FR-012 |
| 2 | `id_stage` | modules/id_stage.md | RV32I decoder, immediate extract, RF read, illegal instr detect | FR-002, FR-011 |
| 3 | `ex_stage` | modules/ex_stage.md | ALU, branch eval, forwarding muxes on ALU inputs | FR-003, FR-007, FR-009 |
| 4 | `mem_stage` | modules/mem_stage.md | D-mem address/data/be, load/store width control, sign/zero ext | FR-004, FR-009 |
| 5 | `wb_stage` | modules/wb_stage.md | Writeback mux (ALU/mem/PC+4/CSR), RF we, x0 suppression | FR-005 |
| 6 | `register_file` | modules/register_file.md | 32×32-bit, 2-read 1-write, x0 hardwired zero | FR-006 |
| 7 | `hazard_unit` | modules/hazard_unit.md | Load-use detection, IF/ID stall, EX bubble insertion | FR-008 |
| 8 | `forwarding_unit` | modules/forwarding_unit.md | RAW hazard detect on rs1/rs2 vs EX/MEM.dst, MEM/WB.dst, priority | FR-007 |
| 9 | `csr_block` | modules/csr_block.md | 6 machine-mode CSRs, CSR ops, trap entry/mret | FR-010, FR-011 |
| 10 | `pipeline_control` | modules/pipeline_control.md | Pipeline register enables, stall/flush ctrl, NOP insertion | FR-013 |

---

## 3. Memory Map

```
+=====================================================================+
|                     IP-001 RV32I MEMORY MAP                          |
+=====================================================================+
| START ADDR    | END ADDR      | REGION          | ACCESS     | SIZE  |
+---------------+---------------+-----------------+------------+-------+
| 0x0000_0000   | 0x0000_0FFF   | I-Memory (ROM)  | R (fetch)  | 4 KB  |
| 0x0000_1000   | 0x0000_1FFF   | D-Memory (SRAM) | R/W        | 4 KB  |
| 0x0000_2000   | 0x7FFF_FFFF   | Reserved        | —          | ~2 GB  |
| 0x8000_0000   | 0xFFFF_FFFF   | Reserved (ext)  | —          | ~2 GB  |
+=====================================================================+

NOTES:
- I-Memory (0x0000_0000): Instruction fetch only. Read-only. Reset vector = 0x0000_0000.
  Backend provides 4KB minimum; expandable by address decode at top level.
- D-Memory (0x0000_1000): Load/store data. Read/write. Backend provides 4KB minimum.
- No peripherals mapped — this is a bare CPU core. Peripherals and external buses
  are out of scope per ARC-006/IFR-003.
- Physical addresses only (no MMU, ARC-008).
- The Harvard split is internal to the core. Backend may physically unify
  I+D memory with an arbiter; core's I/D paths remain separate per ARC-006.
```

---

## 4. Clock and Reset Strategy

### 4.1 Clock Architecture (ARC-004, NFR-002)

```
                    clk (50 MHz, sky130hd)
                         |
        +----------------+----------------+
        |                |                |
   [IF_STAGE]      [ID_STAGE]       [EX_STAGE]
        |                |                |
   [MEM_STAGE]     [WB_STAGE]       [CSR_BLOCK]
        |                |                |
   [REG_FILE]     [HAZARD_UNIT]    [FWD_UNIT]
        |                |                |
   [PIPELINE_CTRL]       |                |
        |                |                |
        +-------+--------+--------+-------+
                |
        ALL sequential elements receive the SAME clk signal.
        NO clock dividers, NO clock muxes, NO derived clocks, NO clock gating.
```

- **Frequency:** 50 MHz (20 ns period)
- **Source:** Single external clock input (`clk`)
- **Domains:** Exactly ONE (all flops on same `clk`)
- **Skew budget:** < 300 ps (TritonCTS delivers ~200 ps on sky130hd)
- **Rationale:** Single-domain eliminates all CDC concerns. 50 MHz is >2× conservative for sky130hd critical path (~8-10 ns). Confirmed by TTP-010 (50 MHz), TTP-029 (64 MHz) on same PDK.

### 4.2 Reset Strategy (FR-012, NFR-008)

```
                    rst_n (external, async)
                         |
                         v
              +---------------------+
              |  2-FF SYNCHRONIZER  |
              |  FF0: rst_n_sync0   |
              |  FF1: rst_n_sync1   |
              +----------+----------+
                         |
                         v
                   rst_sync_n (synchronous deassertion)
                         |
        +----------------+----------------+
        |                                 |
   ALL sequential elements         Pipeline flush
   use rst_sync_n as reset         (all stages → NOP)
```

- **Type:** Synchronous reset (async assert, sync deassert via 2-FF chain)
- **Synchronizer:** 2 flip-flop chain on `clk` — standard pattern (Taraate §3.4, Roy §4)
- **Minimum pulse:** 4 clock cycles (80 ns)
- **Deassertion:** All flops see reset removal on same clock edge
- **Behavior on reset:**
  - PC ← 0x0000_0000 (reset vector)
  - All pipeline stages ← NOP
  - CSRs ← architecturally-defined reset values (see §5.8)
  - Register file ← undefined (no explicit clear — saves ~1024 FFs of reset logic)
  - `rst_sync_n` = 0 holds all state in reset
- **First fetch:** First `clk` edge after `rst_sync_n` deassertion → fetch from 0x0000_0000

### 4.3 Reset Values Summary

| State Element | Reset Value | Rationale |
|---------------|-------------|-----------|
| PC | 0x0000_0000 | Standard RISC-V convention (Privileged Spec) |
| Pipeline registers (IF/ID, ID/EX, EX/MEM, MEM/WB) | NOP-equivalent | All control signals = 0 |
| Register file (x1-x31) | undefined | No reset to save area; software initializes |
| Register file (x0) | 0x0000_0000 | Hardwired to zero |
| misa | 0x4000_0100 | MXL=1 (RV32), Extensions=0 (RV32I only) |
| mstatus | 0x0000_1800 | MIE=0, MPIE=0, MPP=0 (M-mode only) |
| mtvec | 0x0000_0000 | Direct mode, base=0 |
| mepc | 0x0000_0000 | Undefined until first trap |
| mcause | 0x0000_0000 | Undefined until first trap |
| mie | 0x0000_0000 | All interrupts disabled |
| mip | 0x0000_0000 | No interrupts pending |

---

## 5. Architecture Decisions

### AD-001: 5-Stage Pipeline (IF→ID→EX→MEM→WB)
**Decision:** Implement exactly five pipeline stages with pipeline registers between each stage pair.
**Rationale:** Matches NFR-006 requirement. Patterson & Hennessy canonical RISC design. Single-cycle ALU at 50 MHz (20 ns) gives >10 ns of slack on sky130hd. TTP-010 demonstrates working 5-stage RV32I at same frequency/PDK.
**Trade-off:** Area cost from 4 pipeline register banks (~1500 FFs total) vs. higher throughput. With forwarding, CPI ~1.2-1.3 vs ~4-5 for multi-cycle (PicoRV32).
**Alternatives:** 2-stage (NEORV32 — no forwarding needed but CPI > 1), 3-stage (Ibex "micro" at 16.85kGE, CPI ~1.5+)
**Research:** B1, B4, B5, B8, B9, B21

### AD-002: Predict-Not-Taken Branch Strategy
**Decision:** Evaluate branch condition in EX stage. Predict not-taken. Flush IF+ID (2-cycle penalty) when branch is actually taken. Unconditional jumps (JAL/JALR) always flush.
**Rationale:** Simplest correct strategy. No branch predictor hardware needed. 2-cycle penalty for ~60% of ~20% of instructions = ~0.18 CPI overhead. Within NFR-005 target of CPI < 1.5.
**Trade-off:** Higher taken-branch penalty than branch predictor designs, but simpler design with fewer verification corner cases.
**Alternatives:** Static predict-taken (not standard, worse CPI), dynamic prediction (too complex for 15kGE budget), branch delay slot (not RV32I convention)
**Research:** B4, B7, B9, B21

### AD-003: Full Forwarding (EX/MEM→EX + MEM/WB→EX)
**Decision:** Two-level forwarding on ALU inputs. EX/MEM pipeline register result and MEM/WB pipeline register result both forward to EX stage ALU operand inputs (a and b). Forwarding priority: EX/MEM > MEM/WB (most recent result wins).
**Rationale:** Without forwarding, every RAW hazard costs 2 stall cycles → CPI ~2.0. With forwarding, ALU→ALU dependencies cost 0 stall cycles. Most RAW hazards are ALU→ALU, resolved by forwarding. Forwarding reduces CPI from ~2.0 to ~1.1-1.2 (plus load-use stall overhead). Pattern matches Patterson & Hennessy §4.5-4.7 and TTP-010 (a3→a2 forwarding).
**Trade-off:** Forwarding mux adds ~2 gate delays on ALU critical path (RSK-004). Mitigated by conservative 50 MHz target. 3-input mux per operand (no-fwd / EX-fwd / MEM-fwd).
**Alternatives:** No forwarding (CPI > 2, fails NFR-005), ID→EX forwarding only (insufficient for 5-stage)
**Research:** B4, B7, B8, B9, B21

### AD-004: Load-Use Hazard with Single-Cycle Stall
**Decision:** When a load is in EX stage and the instruction in ID stage reads the load destination register as rs1 or rs2, stall IF and ID for one cycle, inserting a NOP (bubble) into EX. After the stall, load data forwards from MEM/WB→EX normally.
**Rationale:** Load data is not available until the end of MEM stage. Dependent instruction needs it at the start of EX stage (next cycle). One cycle stall bridges the gap. Patterson & Hennessy canonical approach.
**Trade-off:** ~10-15% of loads have dependent next instruction → ~0.1-0.15 CPI overhead. Compiler instruction scheduling can reduce this but not eliminate it.
**Alternatives:** Stall until WB (2 cycles, worse CPI), no stall (incorrect results), out-of-order execution (far too complex)
**Research:** B4, B7, B9, B21

### AD-005: Harvard Internal Architecture
**Decision:** Separate instruction fetch path (i_addr, i_rdata) and data access path (d_addr, d_wdata, d_rdata, d_be, d_we) inside the core. No shared bus between I and D.
**Rationale:** Eliminates structural hazard of simultaneous fetch + data access. Matches ARC-006. Backend may physically unify with arbiter — core remains Harvard. TTP-010, TTP-021, PicoRV32, Ibex all use separate I/D paths.
**Trade-off:** Requires separate memory interfaces or a backend arbiter (out of scope). 4KB each for I-Mem and D-Mem is sufficient for prototype workloads.
**Alternatives:** Unified Von Neumann (structural hazard on every load/store, reduces IPC), shared bus Wishbone (adds protocol complexity out of scope)
**Research:** B5, B9, B10, B11, B17

### AD-006: Machine-Mode Only CSR Subset
**Decision:** Implement 7 CSRs: misa (0x301, RO), mstatus (0x300, MIE/MPIE), mtvec (0x305), mepc (0x341), mcause (0x342), mie (0x304), mip (0x344). Support 6 CSR instruction variants: CSRRW, CSRRS, CSRRC, CSRRWI, CSRRSI, CSRRCI. No mstatus.MPP field (M-mode only, ARC-007).
**Rationale:** Minimum set needed for trap handling and interrupt gating. All CSR addresses and fields match RISC-V Privileged Spec v1.12. TTP-029 demonstrates full machine-mode CSR in 2×2 tiles — confirms our subset fits <2000 GE.
**Trade-off:** 7 CSRs = 224 FFs + decode logic. Smaller than full machine-mode (adds mcycle, minstret, mtval, mscratch, etc.) but sufficient for our use case.
**Alternatives:** Full machine-mode CSR (more area, unnecessary for bare-metal core), no CSRs (no trap handling, violates ISA requirement), user-mode CSRs (out of scope per ARC-007)
**Research:** B2, B11, B12

### AD-007: Synchronous Pipeline Control FSM
**Decision:** Pipeline control unit manages stall (freeze IF/ID, NOP→EX) and flush (clear IF/ID or IF/ID/EX to NOP). Flush takes priority over stall when both asserted. Uses separate combinational logic for each control signal.
**Rationale:** Clean separation of control from datapath. Roy §6 FSM methodology. Flush>Stall priority is standard (Patterson & Hennessy §4.7) and prevents deadlock when a load-use stall coincides with a taken branch.
**Trade-off:** Pipeline control logic is combinational (not a stateful FSM) — simpler but requires careful verification of simultaneous stall+flush (RSK-006).
**Alternatives:** Stateful pipeline FSM (more verification effort, same functionality)
**Research:** B5, B9, B21

### AD-008: Register File — Flip-Flop Array
**Decision:** Implement 32×32-bit register file as a flip-flop array (inferred by synthesis). x0 hardwired to zero (read mux bypass). 2 read ports (combinational), 1 write port (clocked). No explicit reset on x1-x31 (undefined at startup).
**Rationale:** 32×32b = 1024 FFs ≈ 4 kGE. Simple implementation — no OpenRAM dependency, no SRAM macro integration complexity, clean reset behavior. At our 15 kGE budget target, 4 kGE for RF is acceptable. Read-during-write (same register written in WB, read in ID 2 stages later) handled by forwarding — no RF bypass needed.
**Trade-off:** ~4× area compared to SRAM macro (~1 kGE for 64×32 OpenRAM). But avoids: OpenRAM characterization, macro placement constraints, read-during-write behavior analysis, and macro-ASIC integration complexity.
**Alternatives:** OpenRAM SRAM macro (smaller area but complex integration, no reset, read-during-write corner cases), latch-based RF (infer latches — violates no-latch rule)
**Research:** B5, B11, B16

### AD-009: Unaligned Access → Trap
**Decision:** Misaligned LW (addr[1:0] ≠ 00), LH/LHU (addr[0] ≠ 0), SH (addr[0] ≠ 0), SW (addr[1:0] ≠ 00) raise misaligned-address exception. No hardware unaligned access handling. LB/LBU, SB are always aligned (byte granularity).
**Rationale:** RISC-V ISA §2.3 permits either trap or hardware handling. Trap is simpler — no byte-level assembly/disassembly state machine. Bare-metal embedded code with standard compiler flags produces aligned accesses. Spec-compliant.
**Trade-off:** Software must ensure aligned data. GCC `-mstrict-align` flag generates safe code at minor performance cost. Most embedded workloads are alignment-safe by convention.
**Alternatives:** Hardware unaligned handling (adds 10-20% LSU area, multi-cycle memory access FSMs, additional hazard scenarios)
**Research:** B1 (RISC-V ISA §2.3)

---

## 6. Pipeline Timing Diagrams

### 6.1 Normal Pipeline Flow

```
Cycle:     T0      T1      T2      T3      T4      T5      T6
         +------++------++------++------++------++------++------+
IF:      | I0   || I1   || I2   || I3   || I4   || I5   || I6   |
         +------++------++------++------++------++------++------+
ID:      |      || I0   || I1   || I2   || I3   || I4   || I5   |
         +------++------++------++------++------++------++------+
EX:      |      ||      || I0   || I1   || I2   || I3   || I4   |
         +------++------++------++------++------++------++------+
MEM:     |      ||      ||      || I0   || I1   || I2   || I3   |
         +------++------++------++------++------++------++------+
WB:      |      ||      ||      ||      || I0   || I1   || I2   |
         +------++------++------++------++------++------++------+
```

First instruction I0 completes WB in T4. Steady state: 1 IPC.

### 6.2 Load-Use Hazard (Single-Cycle Stall)

```
Cycle:     T0      T1      T2      T3      T4      T5
         +------++------++------++------++------++------+
IF:      | LD   || USE  || USE  || NEXT || N+1  || N+2  |
         |      ||(stall)||(re-fetch)||     ||      |
         +------++------++------++------++------++------+
ID:      |      || LD   || LD   || USE  || NEXT || N+1  |
         |      ||      ||(stall)||      ||      ||      |
         +------++------++------++------++------++------+
EX:      |      ||      || LD   || NOP  || USE  || NEXT |
         |      ||      ||      ||(bubble)||      ||      |
         +------++------++------++------++------++------+
MEM:     |      ||      ||      || LD   || NOP  || USE  |
         +------++------++------++------++------++------+
WB:      |      ||      ||      ||      || LD   || NOP  |
         +------++------++------++------++------++------+
         T0: LD fetched
         T1: USE fetched (hazard detected in ID)
         T2: IF/ID stalled, EX gets NOP (bubble)
         T3: LD data available in MEM/WB; USE in EX forwards from MEM/WB
```

### 6.3 Taken Branch (Predict-Not-Taken)

```
Cycle:     T0      T1      T2      T3      T4
         +------++------++------++------++------+
IF:      | BR   || TGT0 || TGT1 || TGT2 || TGT3 |
         +------++------++------++------++------+
ID:      |      || BR   || NOP  || TGT0 || TGT1 |
         |      ||      ||(flush)||      ||      |
         +------++------++------++------++------+
EX:      |      ||      || BR   || NOP  || TGT0 |
         |      ||      || (eval, taken)||      |
         +------++------++------++------++------+
MEM:     |      ||      ||      || BR   || NOP  |
         +------++------++------++------++------+
WB:      |      ||      ||      ||      || BR   |
         +------++------++------++------++------+
         T0: Branch (BR) fetched
         T1: BR+1 (fall-through) speculatively fetched; BR decoded
         T2: BR evaluated in EX → TAKEN. IF/ID flushed. PC → target.
         T3: Target instruction TGT0 in IF
         T4: TGT0 in ID
         Branch penalty: 2 cycles (T1, T2 instructions flushed)
```

### 6.4 Trap Entry Sequence

```
Cycle:     T0      T1      T2      T3      T4
         +------++------++------++------++------+
IF:      | TRAP || TR+1 || HAND0|| HAND1|| HAND2|
         |      ||(flush)||      ||      ||      |
         +------++------++------++------++------+
ID:      |      || TRAP || NOP  || HAND0|| HAND1|
         |      ||(trap det)||(flush)||     ||      |
         +------++------++------++------++------+
EX:      |      ||      || TRAP || NOP  || HAND0|
         |      ||      ||(trap->flush)||      |
         +------++------++------++------++------+
MEM:     |      ||      ||      || TRAP || NOP  |
         +------++------++------++------++------+
WB:      |      ||      ||      ||      || TRAP |
         +------++------++------++------++------+
         T0: Trapping instruction fetched (e.g., illegal instr)
         T1: Trap detected in ID. IF (TR+1) will be flushed.
         T2: Entire pipeline flushed. PC → mtvec.
             CSRs updated: mepc←PC(TRAP), mcause←cause, mstatus.MPIE←MIE, MIE←0
         T3: First handler instruction fetched from mtvec
         Note: Trapping instruction does NOT write back (WB suppressed)
```

### 6.5 MRET (Trap Return)

```
Cycle:     T0      T1      T2      T3      T4
         +------++------++------++------++------+
IF:      | MRET  || RET+1 || REST0|| REST1|| REST2|
         |      ||(flush)||      ||      ||      |
         +------++------++------++------++------+
ID:      |      || MRET  || NOP  || REST0|| REST1|
         |      ||      ||(flush)||      ||      |
         +------++------++------++------++------+
EX:      |      ||      || MRET  || NOP  || REST0|
         |      ||      ||(mret->flush)||      |
         +------++------++------++------++------+
MEM:     |      ||      ||      || MRET  || NOP  |
         +------++------++------++------++------+
WB:      |      ||      ||      ||      || MRET  |
         +------++------++------++------++------+
         T0: MRET fetched
         T2: MRET in EX → PC ← mepc, MIE ← MPIE. IF/ID/EX flushed.
         T3: Restored context instruction fetched from mepc
```

---

## 7. Interconnect and Signal Flow

### 7.1 Forwarding Paths

```
                       +-----------------------------+
                       |       FORWARDING UNIT        |
                       |                             |
  ID/EX.rs1_addr[4:0] -+--> compare with EX/MEM.rd   |
  ID/EX.rs2_addr[4:0] -+--> compare with MEM/WB.rd   |
                       |                             |
                       |  fwd_a_sel[1:0]:            |
                       |    00 = ID/EX.rs1_data      |
                       |    01 = EX/MEM.alu_result   |
                       |    10 = MEM/WB.wb_data      |
                       |    11 = (unused)            |
                       |                             |
                       |  fwd_b_sel[1:0]:            |
                       |    00 = ID/EX.rs2_data      |
                       |    01 = EX/MEM.alu_result   |
                       |    10 = MEM/WB.wb_data      |
                       |    11 = (unused)            |
                       +-----------------------------+

  Conditions:
  - fwd_a = EX if: EX/MEM.wb_en && EX/MEM.rd != 0 && EX/MEM.rd == ID/EX.rs1_addr
  - fwd_a = MEM if: MEM/WB.wb_en && MEM/WB.rd != 0 && MEM/WB.rd == ID/EX.rs1_addr
                    && NOT (EX/MEM fwd already matches rs1)
  - Same for fwd_b with ID/EX.rs2_addr
  - Priority: EX/MEM overrides MEM/WB (most recent value)
```

### 7.2 Hazard Detection (Load-Use)

```
                       +-----------------------------+
                       |       HAZARD UNIT            |
                       |                             |
  ID/EX.mem_read ------+--> load-use check:          |
  ID/EX.rd_addr[4:0] --+     IF/ID.rs1_addr == ID/EX.rd_addr |
  IF/ID.rs1_addr[4:0] -+     OR                       |
  IF/ID.rs2_addr[4:0] -+     IF/ID.rs2_addr == ID/EX.rd_addr |
                       |                             |
                       |  Output: stall_if, stall_id  |
                       |          nop_into_ex         |
                       +-----------------------------+

  Condition:
  - stall = ID/EX.mem_read && (ID/EX.rd != 0) &&
            ((ID/EX.rd == IF/ID.rs1_addr) || (ID/EX.rd == IF/ID.rs2_addr))
```

### 7.3 Pipeline Control Priority

```
  flush > stall (always)

  flush sources (in priority order):
    1. Reset (rst_sync_n = 0) — flush all stages
    2. Trap entry (in ID stage) — flush IF, ID (trap inst proceeds to EX but WB suppressed)
    3. Taken branch (in EX stage) — flush IF, ID
    4. JAL/JALR (in ID stage) — flush IF
    5. MRET (in EX stage) — flush IF, ID, EX

  stall sources:
    1. Load-use hazard (detected in ID) — stall IF, ID; NOP→EX
    2. Data memory busy (not in scope — synchronous memory always ready)

  Flush rules:
    - flush_if: assert on taken branch, JAL/JALR, trap, MRET, reset
    - flush_id: assert on taken branch, trap, MRET, reset
    - flush_ex: assert on trap (prevents WB of trapping instruction), MRET, reset
    - flush_mem: assert on reset only (trap instruction MEM stage completes normally)
```

---

## 8. CSR Block Architecture

### 8.1 CSR Register Map

| CSR | Address | Bits Implemented | Reset Value | Access |
|-----|---------|-----------------|-------------|--------|
| mstatus | 0x300 | [7] MPIE, [3] MIE | 0x0000_1800 | RW (fields) |
| misa | 0x301 | [31:30] MXL=1, [25:0] Ext=0 | 0x4000_0100 | RO |
| mie | 0x304 | [7] MTIE, [11] MEIE | 0x0000_0000 | RW |
| mtvec | 0x305 | [31:2] BASE, [1:0] MODE | 0x0000_0000 | RW |
| mcause | 0x342 | [31] Interrupt, [30:0] Exception Code | 0x0000_0000 | RW |
| mepc | 0x341 | [31:0] Exception PC | 0x0000_0000 | RW |
| mip | 0x344 | [7] MTIP, [11] MEIP | 0x0000_0000 | RO (bits from wires) |

### 8.2 Trap Cause Codes

| Cause | Code | Description |
|-------|------|-------------|
| Illegal instruction | 2 | Unknown opcode/funct3/funct7 combination |
| Breakpoint | 3 | EBREAK instruction |
| ECALL (M-mode) | 11 | ECALL from machine mode |
| Misaligned load | 4 | LW/LH/LHU to unaligned address |
| Misaligned store | 6 | SW/SH to unaligned address |
| Timer interrupt | 0x8000_0007 | mcause[31]=1, code=7 |
| External interrupt | 0x8000_000B | mcause[31]=1, code=11 |

### 8.3 CSR Instruction Operations

| Instruction | Operation | Formula |
|-------------|-----------|---------|
| CSRRW | Atomic read/write | tmp = CSR; CSR = rs1; rd = tmp |
| CSRRS | Atomic read/set | tmp = CSR; CSR = CSR \| rs1; rd = tmp |
| CSRRC | Atomic read/clear | tmp = CSR; CSR = CSR & ~rs1; rd = tmp |
| CSRRWI | Immediate read/write | tmp = CSR; CSR = zimm; rd = tmp |
| CSRRSI | Immediate read/set | tmp = CSR; CSR = CSR \| zimm; rd = tmp |
| CSRRCI | Immediate read/clear | tmp = CSR; CSR = CSR & ~zimm; rd = tmp |

Where zimm = {27'b0, rs1_addr[4:0]} for immediate variants.

---

## 9. Gate Count Estimate

| Component | Estimated Gates (NAND2-equiv) | Notes |
|-----------|-------------------------------|-------|
| Register file (32×32 FF) | 4,000 | 1024 FFs = ~4 kGE at ~4 GE/FF |
| Pipeline registers (4 × ~40 flops) | 650 | IF/ID + ID/EX + EX/MEM + MEM/WB |
| ALU (adder + logic + shifter + comparator) | 2,000 | 32-bit RCA adder ≈ 500 GE + mux + logic |
| Decoder (combinational + immediate extract) | 1,200 | 40-instruction case tree |
| Forwarding unit (comparators + muxes) | 800 | 2 × 3:1 32-bit muxes + 4 × 5-bit comparators |
| Hazard unit (load-use detection) | 200 | Comparators + AND/OR |
| Pipeline control | 300 | Combinational stall/flush logic |
| CSR block (7 registers + decode) | 1,200 | 224 FFs + case logic + trap FSM |
| LSU (sign/zero ext + byte-enable + alignment chk) | 500 | Combinational + comparators |
| PC generation (mux + adder) | 400 | PC+4 adder + 5-way PC mux |
| Branch evaluation | 300 | Comparators (EQ, LT, LTU, GE, GEU) |
| Trap logic (mux + priority encoder) | 300 | Trap handler + mepc/mcause write logic |
| Miscellaneous (top-level glue, wires) | 650 | Buffers, fanout |
| **TOTAL (estimated)** | **~12,500** | Within 15k GE budget (NFR-004) |

**Note:** This is an architectural estimate. Yosys synthesis with sky130hd liberty needed for precise gate count. Comparable designs: Ibex "micro" = 16.85 kGE (RV32EC), PicoRV32 = 3-5 kGE (multi-cycle, no forwarding), TTP-010 = 20-35 kGE (with SPI + IMEM + DMEM).

---

## 10. Critical Path Analysis

### Predicted Critical Path

```
  IF/ID_reg → ID/EX_reg → Forwarding MUX → ALU (32b ADD) → EX/MEM_reg

  Components on path:
  - ID/EX_reg clk→Q:           ~200 ps
  - Forwarding mux (3:1 32b):  ~150 ps (2 gate delays × 75 ps)
  - ALU 32-bit ADD:            ~7,000 ps (RCA, ~7 ns at sky130hd SS/125C)
  - EX/MEM_reg setup:          ~200 ps
  - Clock uncertainty:         ~500 ps (skew + jitter)
  TOTAL:                       ~8,050 ps << 20,000 ps (50 MHz)

  Slack: ~12 ns — very comfortable margin.
```

**Conclusion:** 50 MHz is deeply conservative for this design on sky130hd. Even at slow corner (SS/125C/1.62V), the critical path has >10 ns of positive slack. No pipeline stage splitting or ALU deeper pipelining is needed.

---

## 11. Verification Strategy (Phase 4-5 Pre-Planning)

### 11.1 Golden Reference Model
- **Spike RISC-V ISA simulator** (`spike --isa=rv32i`) as GRM
- Compare register file state after each instruction retirement
- Compare CSR state after each trap

### 11.2 Special Verification Targets

| Target | Method | Why |
|--------|--------|-----|
| Forwarding correctness | Random instruction stream with forwarding-aware scoreboard | RSK-001 — most subtle bugs are in forwarding |
| x0 immutability | Directed test: write x0, verify reads as zero | Common bug across implementations |
| Stall+flush interaction | Directed + formal on pipeline control | RSK-006 — deadlock/livelock potential |
| ALL RV32I instructions | riscv-tests rv32ui-p-* suite | ISA compliance (ARC-001) |
| ALL CSR operations | Directed per-CSR test with all 6 instruction variants | RSK-002 — CSR field interactions are subtle |
| Illegal instruction detection | Fuzz: random 32-bit patterns, verify trap or valid instruction | RSK-005 — decoder gaps |
| Trap entry/exit | Directed: ECALL, EBREAK, illegal, MRET | RSK-002 — save/restore sequence |
| Branch flush | Directed: all branch types × taken/not-taken | RSK-003 — PC sequence verification |
| Reset sequence | Verify CSR values at cycle 0; verify first fetch address | RSK-007 — initialization |
| Load-store | All LSU variants with all address offsets | FR-004 — byte-enable, sign-ext |
| Pipeline hazard stress | Sequence: ALU→ALU, ALU→branch, load→ALU, load→store | RSK-001 — forwarding + stall + flush |

---

## 12. Design Constraints for SDC

```tcl
# IP-001 SDC Constraints (preliminary)
set clk_period 20.0  ;# 50 MHz
create_clock -name clk -period $clk_period [get_ports clk]

# Single clock domain — all paths in same clock group
# No derived clocks, no clock gating

# Input delays (external interrupt signals)
set_input_delay -clock clk 15.0 [get_ports {irq_timer irq_external}]

# Output delays (memory interface)
# I-Memory: address is registered in IF stage; output before next edge
set_output_delay -clock clk 5.0 [get_ports i_addr*]
# D-Memory: address/data/be/we registered in MEM stage
set_output_delay -clock clk 5.0 [get_ports {d_addr* d_wdata* d_be* d_we}]

# Input delay on memory read data (sampled at end of IF/MEM cycle)
set_input_delay -clock clk 5.0 [get_ports {i_rdata* d_rdata*}]

# False paths: reset synchronizer first stage
set_false_path -from [get_cells rst_sync0_reg] -to [get_cells rst_sync1_reg/D]

# Clock uncertainty budget
set_clock_uncertainty -setup 0.3 [get_clocks clk]
set_clock_uncertainty -hold  0.1 [get_clocks clk]
```

---

## 13. Risk Register (Post-Microarchitecture)

| ID | Risk | Original (Phase 1) | Post-Microarch | Mitigation Status |
|----|------|-------------------|----------------|-------------------|
| RSK-001 | Hazard logic correctness | HIGH/HIGH | HIGH/HIGH | Forwarding unit design includes explicit priority and x0 suppression. Formal verification recommended. |
| RSK-002 | CSR implementation gaps | MEDIUM/HIGH | MEDIUM/HIGH | CSR spec enumerates all fields and interactions. Directed test for every CSR × instruction variant. |
| RSK-003 | Branch flush timing | MEDIUM/HIGH | MEDIUM/HIGH | PC mux priority documented. Flush vs stall priority: flush wins. Directed test for all branch types. |
| RSK-004 | Timing closure at 50 MHz | LOW/MEDIUM | LOW/LOW | Critical path estimate: ~8 ns vs 20 ns period. >10 ns slack. Conservative. |
| RSK-005 | Illegal instruction detection | MEDIUM/MEDIUM | MEDIUM/MEDIUM | Decoder spec enumerates all opcode/funct3/funct7 combos. Fuzz test strategy defined. |
| RSK-006 | Stall+flush deadlock | LOW/HIGH | LOW/HIGH | Pipeline control priority: flush > stall. Formal liveness proof recommended in Phase 5. |
| RSK-007 | Reset values | MEDIUM/HIGH | MEDIUM/HIGH | All CSR reset values documented per Privileged Spec. First-fetch test defined. |

---

## 14. Traceability Summary

All 34 requirements trace to microarchitecture elements:

| Requirement | Module | Architecture Decision |
|-------------|--------|----------------------|
| FR-001 | if_stage | AD-001, AD-002 |
| FR-002 | id_stage | AD-001 |
| FR-003 | ex_stage | AD-001, AD-003 |
| FR-004 | mem_stage | AD-001, AD-009 |
| FR-005 | wb_stage, register_file | AD-001 |
| FR-006 | register_file | AD-008 |
| FR-007 | forwarding_unit | AD-003 |
| FR-008 | hazard_unit | AD-004 |
| FR-009 | ex_stage (branch), if_stage (target), id_stage (jump) | AD-002 |
| FR-010 | csr_block | AD-006 |
| FR-011 | csr_block, pipeline_control | AD-006 |
| FR-012 | pipeline_control (reset) | §4.2 |
| FR-013 | pipeline_control | AD-007 |
| NFR-001 | (STA constraint) | §10, §12 |
| NFR-002 | (all modules — single clk) | §4.1 |
| NFR-003 | (sky130hd) | §9 (gate est) |
| NFR-004 | (all modules) | §9 (gate est) |
| NFR-005 | (CPI) | AD-002, AD-003, AD-004 |
| NFR-006 | pipeline_control | AD-001 |
| NFR-007 | (Phase 5 verification) | — |
| NFR-008 | (reset synchronizer) | §4.2 |
| IFR-001 | if_stage | AD-005 |
| IFR-002 | mem_stage | AD-005, AD-009 |
| IFR-003 | (top-level ports) | AD-005 (§5 confirms) |
| IFR-004 | csr_block | AD-006 |
| ARC-001-009 | (all decisions) | AD-001 through AD-009 |

---

## 15. Handoff to Phase 4 (GRM Engineer)

- [x] Processor core: Custom RV32I 5-stage, 50 MHz, sky130hd
- [x] Pipeline: IF→ID→EX→MEM/WB with full forwarding
- [x] Branch: Predict-not-taken, resolve EX, 2-cycle flush
- [x] Load-use: Single-cycle stall
- [x] CSR: 7 machine-mode CSRs, 6 instruction variants
- [x] Harvard I/D interfaces (no bus protocol)
- [x] Register file: FF array, 2R1W, x0 hardwired
- [x] Memory map: I@0x00000000(4KB), D@0x00001000(4KB)
- [x] Reset vector: 0x00000000
- [x] Spike `--isa=rv32i` as GRM

---

*Microarchitecture specification complete. Proceed to Phase 4 (GRM Engineer).*
