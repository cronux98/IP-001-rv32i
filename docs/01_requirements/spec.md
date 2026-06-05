# IP-001 — RV32I 5-Stage Pipeline Core: Requirements Specification

**Document:** spec.md  
**Phase:** 1 — Requirements Engineering  
**Tier:** Medium | **Distinction:** IP (Real Project)  
**PDK:** SkyWater 130nm HD (sky130hd)  
**Date:** 2026-06-05  
**Status:** Draft  

---

## 1. Project Overview

### 1.1 Elevator Pitch
A compact, single-clock, 5-stage pipelined RV32I integer processor core targeting the SkyWater 130nm open-source PDK. This is a **pure CPU core** — no external bus protocols, no peripherals, no MMU. Machine-mode only. Built as an academic workflow stress test for the open-source architect→RTL→backend toolchain.

### 1.2 Stakeholders
| Role | Entity |
|------|--------|
| Architect / Designer | Silicon Sage (Sage) |
| Client / Reviewer | Luqman (Rinri) |
| Target Audience | Academic / Open-Source Silicon Community |

### 1.3 Scope
**IN SCOPE:**
- RV32I base integer ISA (all 40 unique RV32I instructions across 6 formats)
- 5-stage classic pipeline: IF → ID → EX → MEM → WB
- 32-entry × 32-bit general-purpose register file (x0 hardwired to zero)
- Hazard detection with full forwarding (EX/MEM, MEM/WB → EX)
- Load-use hazard stall (single-cycle bubble insertion)
- Branch resolution with flush of IF/ID on taken branch
- Machine-mode CSR subset: misa, mstatus, mtvec, mepc, mcause, mie, mip
- Exception handling: illegal instruction trap, ECALL, EBREAK
- Harvard-style internal I/D memory interfaces
- Synchronous reset with clean pipeline flush

**OUT OF SCOPE:**
- M-extension (multiply/divide) — no hardware multiplier
- C-extension (compressed instructions) — 32-bit instructions only
- Supervisor/User privilege modes — machine-mode only
- MMU, virtual memory, address translation
- External bus protocols (Wishbone, AXI, TileLink)
- Interrupt controller (PLIC/CLIC) — IRQ wires only (mip/mie CSR)
- Debug module / JTAG
- Performance counters (mcycle/minstret optional in P2)
- Clock gating, power management
- Multi-core / multi-hart

### 1.4 Operational Context
- **Environment:** Simulation-first; FPGA validation optional; ASIC tapeout as stretch goal
- **Volume:** Prototype / single-digit tapeout
- **Execution model:** Bare-metal — no operating system
- **Memory model:** Harvard (separate instruction fetch and data access paths internally); physically may share a single-port SRAM with arbitration in backend

---

## 2. Functional Requirements

### FR-001 — Instruction Fetch Unit
**Priority:** P0  
**Description:** The processor SHALL fetch 32-bit instructions from the instruction memory interface on every clock cycle (unless stalled or flushed). The program counter (PC) SHALL increment by 4 bytes sequentially, with overrides for branch targets, jump targets (JAL/JALR), and exception trap vectors.

**Acceptance Criteria:**
- PC resets to the reset vector address (defined in memory map)
- Sequential PC = PC + 4 when no control-flow change occurs
- JAL target = PC + signed immediate, lower bit cleared
- JALR target = (rs1 + signed immediate) & ~1
- Branch target = PC + signed immediate (when condition met)
- Trap entry target = mtvec CSR value
- IF stage stalls when ID stage is stalled or pipeline is flushed

### FR-002 — Instruction Decode Unit
**Priority:** P0  
**Description:** The processor SHALL decode all RV32I instructions into control signals for the execute stage, including: register source/destination indices, ALU operation selection, immediate value extraction (I/S/B/U/J formats), memory access type (load/store, width, sign-extension), branch condition selection, and CSR access control. The decoder SHALL detect illegal instructions and raise an illegal-instruction exception.

**Acceptance Criteria:**
- All 40 unique RV32I instructions correctly decoded
- All 6 immediate formats (I, S, B, U, J) correctly sign/zero-extended
- Unknown opcode/funct3/funct7 combinations raise illegal-instruction trap
- Register x0 reads as zero regardless of write-back value
- Decoded control signals stable within one clock cycle

### FR-003 — Execute Unit (ALU)
**Priority:** P0  
**Description:** The processor SHALL perform all RV32I ALU operations: addition/subtraction, logical (AND/OR/XOR), shift (SLL/SRL/SRA — logical and arithmetic), set-less-than (signed and unsigned), and branch condition evaluation. The ALU SHALL also compute effective addresses for load/store operations and branch/jump targets.

**Acceptance Criteria:**
- ADD/SUB produce correct 32-bit results with no overflow trap (RV32I wraps)
- SLT/SLTU produce 0 or 1 based on signed/unsigned comparison
- SLL/SRL/SRA shift by rs2[4:0] only (lower 5 bits of shift amount)
- SRA preserves sign bit for arithmetic right shift
- All operations complete within one clock cycle (no multi-cycle ALU ops)
- Branch condition evaluation produces single-bit taken/not-taken signal

### FR-004 — Memory Access Unit
**Priority:** P0  
**Description:** The processor SHALL perform load and store operations to the data memory interface. Loads SHALL support LB, LH, LW, LBU, LHU with correct sign/zero extension. Stores SHALL support SB, SH, SW with correct byte/half-word/word alignment. Unaligned memory accesses SHALL trap with a misaligned-address exception (or be handled by hardware, designer's choice with documentation).

**Acceptance Criteria:**
- LW loads 32-bit word from aligned address (addr[1:0] == 00)
- LH/LHU loads 16-bit half-word from aligned address (addr[0] == 0)
- LB/LBU loads 8-bit byte from any address
- SB/SH/SW store correct byte lanes with byte-enable signaling
- Naturally aligned accesses complete without exception
- Misaligned LW/LH/SH/SW raise exception or are handled atomically (documented decision)

### FR-005 — Writeback Unit
**Priority:** P0  
**Description:** The processor SHALL write results back to the register file in the WB stage. Results may originate from: ALU output (R-type, I-type arithmetic), memory load data, JAL/JALR link address (PC+4), or CSR read data. The destination register index SHALL be passed through the pipeline from ID stage.

**Acceptance Criteria:**
- Register file write occurs on rising clock edge in WB stage
- x0 writes are suppressed (x0 hardwired to zero)
- Write enable is deasserted for: store instructions, branch instructions (if link not set), illegal instructions
- Correct result selected from ALU/memory/PC+4/CSR multiplexer

### FR-006 — Register File
**Priority:** P0  
**Description:** The processor SHALL implement a 32-entry × 32-bit general-purpose register file conforming to the RV32I integer register specification. Register x0 SHALL be hardwired to zero. The register file SHALL support two read ports (for rs1, rs2 in ID stage) and one write port (from WB stage).

**Acceptance Criteria:**
- 32 registers, each 32 bits wide
- x0 always reads as 0x00000000 regardless of write data
- Two simultaneous reads (rs1, rs2) produce correct values
- Write occurs on rising clock edge when write-enable is asserted
- Read-after-write within same cycle: read returns newly written value (bypass implemented or documented as read-old-value with forwarding compensation)
- Register file implemented with block RAM inference or flip-flop array

### FR-007 — Data Forwarding (Hazard Resolution)
**Priority:** P0  
**Description:** The processor SHALL implement full forwarding paths to resolve data hazards without stalling (except load-use). Forwarding paths SHALL include: EX/MEM result → EX stage (rs1, rs2), MEM/WB result → EX stage (rs1, rs2). The forwarding unit SHALL detect RAW (read-after-write) hazards by comparing destination register indices of in-flight instructions against source register indices of the current instruction.

**Acceptance Criteria:**
- ALU result from EX/MEM forwarded to EX stage inputs when destination matches rs1/rs2
- ALU/memory result from MEM/WB forwarded to EX stage when destination matches rs1/rs2
- Forwarding priority: EX/MEM takes precedence over MEM/WB (most recent result)
- Forwarding suppressed when destination is x0
- Verification: every RAW hazard in random instruction stream resolved correctly

### FR-008 — Load-Use Hazard Detection and Stall
**Priority:** P0  
**Description:** The processor SHALL detect load-use hazards (instruction in ID stage depends on load in EX stage) and SHALL insert a single pipeline bubble (stall IF and ID, insert NOP into EX) to allow the load data to become available for forwarding. This is the ONLY pipeline stall required for the base RV32I implementation.

**Acceptance Criteria:**
- Load in EX stage + dependent instruction in ID stage → one cycle stall
- IF stage: PC frozen, instruction re-fetched after stall
- ID stage: control signals held
- EX stage: NOP (bubble) inserted for one cycle
- After stall, load data forwards from MEM/WB to EX stage normally
- No stall when load result is not used by next instruction
- No stall for store-after-load (store data forwarded directly)

### FR-009 — Branch and Jump Handling
**Priority:** P0  
**Description:** The processor SHALL decode branches in ID or EX stage, evaluate the branch condition, and flush incorrectly fetched instructions when a branch is taken. Unconditional jumps (JAL, JALR) SHALL also flush the pipeline. Branch prediction is NOT required — the simplest "predict not-taken, flush on taken" strategy is acceptable.

**Acceptance Criteria:**
- Branch condition evaluated using register values (with forwarding if available)
- Taken branch: IF and ID stage instructions flushed (converted to NOPs)
- PC updated to branch target in next cycle
- Not-taken branch: pipeline continues without flush
- JAL: unconditional flush of IF stage, PC updated to JAL target, link register written
- JALR: similar to JAL but target from rs1+immediate
- Branch penalty: 2 cycles for taken branch (IF+ID flush), 0 for not-taken

### FR-010 — CSR Access (Zicsr Machine-Mode Subset)
**Priority:** P0  
**Description:** The processor SHALL implement the Zicsr machine-mode CSR subset required for basic trap handling and system control. CSRs SHALL be accessible via the CSRRC, CSRRS, CSRRW, CSRRCI, CSRRSI, CSRRWI instruction variants. The minimum CSRs implemented SHALL be:

| CSR | Address | Description |
|-----|---------|-------------|
| misa | 0x301 | ISA and extensions (read-only: RV32I) |
| mstatus | 0x300 | Machine status (MIE, MPIE fields) |
| mtvec | 0x305 | Machine trap vector base address |
| mepc | 0x341 | Machine exception program counter |
| mcause | 0x342 | Machine trap cause |
| mie | 0x304 | Machine interrupt enable |
| mip | 0x344 | Machine interrupt pending |

**Acceptance Criteria:**
- CSRRW: atomic read/write of CSR
- CSRRS: atomic read and set bits in CSR
- CSRRC: atomic read and clear bits in CSR
- CSRRWI/CSRRSI/CSRRCI: immediate variants operate correctly
- Read-only CSRs (misa) ignore writes
- mcause records exception code on trap entry
- mepc captures faulting instruction PC on trap
- mstatus.MIE cleared on trap entry, restored on MRET

### FR-011 — Exception and Trap Handling
**Priority:** P0  
**Description:** The processor SHALL detect and handle the following exception conditions in machine mode: illegal instruction (detected in ID stage), ECALL instruction (environment call), EBREAK instruction (breakpoint), and misaligned memory access (if not hardware-handled). On any trap, the processor SHALL: save PC to mepc, save cause to mcause, set mstatus.MPIE = mstatus.MIE, clear mstatus.MIE, and redirect PC to mtvec. MRET instruction SHALL restore PC from mepc and restore mstatus.MIE from mstatus.MPIE.

**Acceptance Criteria:**
- Illegal instruction (unknown opcode/funct3/funct7): trap with mcause = 2
- ECALL: trap with mcause = 11 (machine-mode ECALL)
- EBREAK: trap with mcause = 3
- Trap entry: mepc = PC of faulting instruction, PC → mtvec
- MRET: PC restored from mepc, mstatus restored
- Pipeline flushed on trap entry
- No nested trap handling required (simplified: MIE=0 prevents interrupts during handler)

### FR-012 — Reset Behavior
**Priority:** P0  
**Description:** The processor SHALL support a synchronous reset input that, when asserted, SHALL: flush all pipeline stages, reset PC to the reset vector (0x00000000 or designer-defined), initialize all CSRs to their architecturally-defined reset values, and clear the register file (or leave undefined — documented choice).

**Acceptance Criteria:**
- Reset asserted for minimum 4 clock cycles
- PC = reset vector after reset deassertion (first instruction fetch)
- Pipeline stages contain NOP-equivalent values after reset
- CSRs at documented reset values (mstatus = 0, mtvec = 0, etc.)
- First instruction fetch occurs on cycle after reset deassertion
- Register file contents documented (zeroed or undefined)

### FR-013 — Pipeline Register and Control Logic
**Priority:** P0  
**Description:** The processor SHALL implement pipeline registers between each stage (IF/ID, ID/EX, EX/MEM, MEM/WB) to hold instruction data and control signals. Pipeline control logic SHALL support: normal advance (all stages advance), stall (IF and ID frozen, EX gets bubble), and flush (selected stages cleared to NOP). Stall and flush signals SHALL be generated by the hazard detection and branch resolution logic respectively.

**Acceptance Criteria:**
- Pipeline registers correctly capture and propagate data each cycle
- Stall: IF/ID register holds value, ID/EX register receives NOP
- Flush: IF/ID register cleared to NOP (after taken branch/jump/trap)
- No data corruption during mixed stall+flush conditions
- Control signals propagate correctly through all pipeline stages

---

## 3. Non-Functional Requirements

### NFR-001 — Clock Frequency
**Priority:** P0  
**Description:** The processor SHALL operate at a minimum clock frequency of 50 MHz under SkyWater 130nm HD (sky130hd) worst-case PVT conditions (SS, 125°C, 1.62V).

**Acceptance Criteria:**
- Static timing analysis (OpenSTA) shows zero setup violations at 50 MHz
- Critical path identified and documented
- Positive slack on all timing paths post-synthesis

### NFR-002 — Clock Domain Architecture
**Priority:** P0  
**Description:** The processor SHALL use a single, global synchronous clock domain. No clock domain crossings (CDC) SHALL exist. No clock gating SHALL be used.

**Acceptance Criteria:**
- Single clock source drives all sequential elements
- No derived or divided clocks
- No gated clocks in implementation
- Clock tree insertion by OpenROAD CTS produces balanced skew

### NFR-003 — Target Process Design Kit
**Priority:** P0  
**Description:** The design SHALL target the SkyWater 130nm High-Density (sky130hd) standard cell library.

**Acceptance Criteria:**
- Synthesis with Yosys using sky130hd liberty file
- Place-and-route compatible with sky130hd LEF
- DRC/LVS clean against sky130hd design rules

### NFR-004 — Gate Count Budget
**Priority:** P1  
**Description:** The synthesized gate count (NAND2-equivalent) SHOULD not exceed 15,000 gates. Compact implementation is prioritized over performance.

**Acceptance Criteria:**
- Post-synthesis gate count reported by Yosys
- Target < 15k gates; alert if > 20k gates

### NFR-005 — Cycles Per Instruction (CPI)
**Priority:** P1  
**Description:** The average CPI for typical RV32I workloads (Dhrystone, CoreMark subset) SHOULD be less than 1.5 cycles per instruction, accounting for load-use stalls and branch flush penalties.

**Acceptance Criteria:**
- CPI measured in RTL simulation with instruction trace
- CPI < 1.5 for Dhrystone-like integer workload
- Stall and flush counts reported

### NFR-006 — Pipeline Depth
**Priority:** P0  
**Description:** The processor SHALL implement exactly five (5) pipeline stages: IF, ID, EX, MEM, WB.

**Acceptance Criteria:**
- Five distinct pipeline register boundaries
- Each instruction traverses all five stages (some as NOP in MEM/WB for non-memory instructions)
- Structural hazard: single write port on register file in WB stage

### NFR-007 — Open-Source Toolchain
**Priority:** P0  
**Description:** All design, verification, and implementation SHALL use only open-source tools: Yosys for synthesis, Verilator for lint and simulation, cocotb for verification, OpenROAD for place-and-route, OpenSTA for timing analysis, KLayout/Magic for physical verification.

**Acceptance Criteria:**
- Verilator lint passes with --Wall --lint-only (zero warnings)
- Yosys synthesis completes without errors
- cocotb verification environment runs with Icarus Verilog or Verilator
- OpenROAD flow completes through routing

### NFR-008 — Reset Synchronization
**Priority:** P1  
**Description:** The external reset signal SHOULD be synchronized to the processor clock domain with a 2-stage flip-flop synchronizer. Reset deassertion SHALL be synchronous to eliminate recovery timing issues.

**Acceptance Criteria:**
- Reset synchronizer implemented (2 FF chain)
- Synchronous deassertion: all flops see reset removal on same clock edge
- No metastability path from async reset input

---

## 4. Interface Requirements

### IFR-001 — Instruction Memory Interface
**Priority:** P0  
**Description:** The processor SHALL provide a 32-bit address output and accept a 32-bit instruction input from an internal instruction memory interface. This is an INTERNAL interface only — no external bus protocol is required. The interface SHALL be read-only from the processor perspective.

**Signal Definition:**
| Signal | Direction | Width | Description |
|--------|-----------|-------|-------------|
| i_addr | Output | 32 | Instruction fetch address (word-aligned: addr[1:0]=00) |
| i_rdata | Input | 32 | Instruction data read from memory |

**Acceptance Criteria:**
- Read request every cycle (unless stalled)
- Address is always word-aligned
- i_rdata sampled at end of cycle (synchronous memory model)
- No external protocol handshake required (internal combinational or single-cycle SRAM)

### IFR-002 — Data Memory Interface
**Priority:** P0  
**Description:** The processor SHALL provide a 32-bit address output, 32-bit write data output, 32-bit read data input, 4-bit byte-enable output, and write-enable control for an internal data memory interface. This is an INTERNAL interface only — no external bus protocol is required.

**Signal Definition:**
| Signal | Direction | Width | Description |
|--------|-----------|-------|-------------|
| d_addr | Output | 32 | Data access address |
| d_wdata | Output | 32 | Write data |
| d_rdata | Input | 32 | Read data |
| d_be | Output | 4 | Byte enable (one-hot per byte lane) |
| d_we | Output | 1 | Write enable (1 = store, 0 = load) |

**Acceptance Criteria:**
- Address, wdata, be, we valid during MEM stage
- d_rdata sampled at end of MEM stage (synchronous memory model)
- Byte enables correct for SB/SH/SW (e.g., SW: 4'b1111, SH at addr[1]=0: 4'b0011, SB at addr[1:0]=10: 4'b0100)
- No external protocol handshake required

### IFR-003 — No External Bus Protocols
**Priority:** P0  
**Description:** The processor SHALL NOT implement any external bus protocol interface (Wishbone, AXI, TileLink, etc.). The I-memory and D-memory interfaces described in IFR-001 and IFR-002 are internal point-to-point connections to be connected to SRAM macros or memory arbiters within the top-level integration (which is out of scope for this core).

**Acceptance Criteria:**
- Core top-level ports are as defined in IFR-001 and IFR-002
- No bus protocol signals (stb, cyc, ack, err, etc.)
- Backend integration handles memory macro connection separately

### IFR-004 — External Interrupt Inputs
**Priority:** P1  
**Description:** The processor SHOULD provide machine-mode external interrupt inputs (connected to mip.MEIP and mip.MTIP bits) for timer and external interrupts, gated by mie.MEIE and mie.MTIE respectively. At minimum, a single external interrupt input signal SHALL be present.

**Signal Definition:**
| Signal | Direction | Width | Description |
|--------|-----------|-------|-------------|
| irq_timer | Input | 1 | Machine timer interrupt (connected to mip.MTIP) |
| irq_external | Input | 1 | Machine external interrupt (connected to mip.MEIP) |

**Acceptance Criteria:**
- Interrupts sampled and reflected in mip CSR
- Interrupts only taken when mstatus.MIE = 1 and corresponding mie bit set
- Interrupt causes trap with appropriate mcause code
- Level-sensitive interrupts (held until serviced)

---

## 5. Architecture Constraints

### ARC-001 — ISA Compliance
The processor SHALL implement the RV32I base integer instruction set as defined in The RISC-V Instruction Set Manual, Volume I: User-Level ISA, version 2.1 (or later ratified version). No extensions beyond RV32I and the Zicsr machine-mode CSR subset are included.

### ARC-002 — PDK and Standard Cell Library
The design SHALL target the SkyWater 130nm High-Density (sky130hd) standard cell library. No commercial PDKs or standard cell libraries SHALL be used.

### ARC-003 — Open-Source Toolchain
All tools used in the design flow SHALL be open-source: Yosys, Verilator, Icarus Verilog, cocotb, OpenROAD, OpenSTA, KLayout/Magic. No commercial EDA licenses SHALL be required.

### ARC-004 — Clock Architecture
The design SHALL use exactly one clock domain. No clock dividers, clock muxes, or derived clocks SHALL exist. All sequential elements receive the same clock signal.

### ARC-005 — Pipeline Architecture
The processor SHALL implement a 5-stage pipeline (IF, ID, EX, MEM, WB). Pipeline registers SHALL exist between each stage pair. No stage SHALL be combined or split.

### ARC-006 — Harvard Memory Architecture
The processor SHALL have separate instruction fetch and data access paths internally (Harvard architecture). This separation is structural at the core level; the physical memory organization (unified vs split SRAM) is a backend integration decision.

### ARC-007 — Privilege Mode
The processor SHALL implement machine-mode (M-mode) only. No user-mode (U-mode) or supervisor-mode (S-mode) SHALL be implemented. The mstatus.MPP field is not required.

### ARC-008 — No Virtual Memory
The processor SHALL NOT implement any form of address translation, MMU, or memory protection unit. All addresses are physical.

### ARC-009 — RTL Language
All RTL SHALL be written in synthesizable SystemVerilog (IEEE 1800-2017) or Verilog-2001, targeting Yosys synthesis compatibility. No VHDL, Chisel, SpinalHDL, or Amaranth for RTL deliverables.

---

## 6. System Block Diagram

```
+-----------------------------------------------------------------------------+
|                        RV32I 5-STAGE PIPELINE CORE                          |
|                                                                             |
|  +----------+   +----------+   +----------+   +----------+   +----------+  |
|  |          |   |          |   |          |   |          |   |          |  |
|  |    IF    |-->|    ID    |-->|    EX    |-->|   MEM    |-->|    WB    |  |
|  |          |   |          |   |          |   |          |   |          |  |
|  +----+-----+   +----+-----+   +----+-----+   +----+-----+   +-----+----+  |
|       |              |              |              |               |        |
|       |   +----------+--------------+              |               |        |
|       |   |                                       |               |        |
|  +----v---v--+                              +-----v----+    +-----v----+   |
|  |  HAZARD   |                              |   DATA   |    | REGISTER |   |
|  | DETECTION |                              |  MEMORY  |    |   FILE   |   |
|  |   UNIT    |                              | INTERFACE|    | (32x32)  |   |
|  +----+------+                              +----------+    +----------+   |
|       |                                                                     |
|       |   +---------------------------+                                    |
|       |   |       FORWARDING UNIT     |                                    |
|       |   |  (EX/MEM, MEM/WB -> EX)   |                                    |
|       |   +---------------------------+                                    |
|       |                                                                     |
|  +----v------+   +------------------------------------------------------+  |
|  | PIPELINE  |   |                   CSR BLOCK                          |  |
|  |  CONTROL  |   |  misa | mstatus | mtvec | mepc | mcause | mie | mip |  |
|  | (stall/   |   +------------------------------------------------------+  |
|  |  flush)   |                                                             |
|  +-----------+                                                             |
|                                                                            |
|  +-----------------------------+      +----------------------------+       |
|  |  INSTRUCTION MEMORY I/F     |      |    DATA MEMORY I/F         |       |
|  |  i_addr[31:0] ->            |      |    d_addr[31:0] ->         |       |
|  |  i_rdata[31:0] <-           |      |    d_rdata[31:0] <-        |       |
|  |  (read-only, internal)      |      |    d_wdata[31:0] ->        |       |
|  +-----------------------------+      |    d_be[3:0] ->            |       |
|                                       |    d_we ->                 |       |
|                                       |    (read/write, internal)  |       |
|                                       +----------------------------+       |
|                                                                            |
|  EXTERNAL SIGNALS:                                                         |
|  clk, rst_n, irq_timer, irq_external                                       |
+-----------------------------------------------------------------------------+

PIPELINE FLOW (single instruction traversal):

  clk edge N:   [IF ] -> [ID ] -> [EX ] -> [MEM] -> [WB ]
  clk edge N+1:        [IF ] -> [ID ] -> [EX ] -> [MEM] -> [WB ]

STALL SCENARIO (load-use):
  Cycle N:   [LD  ] -> [IF]  -> [ID]  -> [EX]  -> [MEM] -> [WB]
  Cycle N+1: [USE ] -> [LD ] -> [IF]  -> [NOP] -> [EX ] -> [MEM] -> [WB]
  Cycle N+2: [NEXT] -> [USE] -> [LD ] -> [ID ] -> [EX ] -> [MEM] -> [WB]
                  ^-- stalled one cycle, bubble inserted

TAKEN BRANCH (flush):
  Cycle N:   [BR  ] -> [IF]  -> [ID]  -> [EX]  -> [MEM] -> [WB]
  Cycle N+1: [TRG ] -> [NOP] -> [NOP] -> [BR]  -> [EX]  -> [MEM] -> [WB]
                     ^-- IF/ID flushed, PC redirected to target
```

---

## 7. Risk Register

| ID | Risk Description | Probability | Impact | Mitigation |
|----|------------------|-------------|--------|------------|
| RSK-001 | **Hazard logic correctness.** Data forwarding and stall logic contains subtle bugs that produce incorrect results under specific instruction sequences. | HIGH | HIGH | Exhaustive constrained-random verification with forwarding-aware scoreboard. Formal property checking on hazard detection FSM. Compare all results against Spike GRM. |
| RSK-002 | **CSR implementation gaps.** Incorrect or incomplete CSR behavior (e.g., mstatus field interactions, trap entry/exit sequence) causes software incompatibility. | MEDIUM | HIGH | Implement full Zicsr machine-mode compliance checklist. Verify CSR behavior against RISC-V privileged spec with directed tests for every CSR instruction variant and every trap cause. |
| RSK-003 | **Branch flush timing.** Incorrectly timed flush corrupts pipeline state, causing wrong instruction execution after branch. | MEDIUM | HIGH | Directed tests for all branch conditions (taken/not-taken) with known instruction sequences. Verify PC sequence against expected trace. Formal check on flush signal propagation. |
| RSK-004 | **Timing closure at 50 MHz.** Forwarding mux and ALU critical path exceeds 20ns period under sky130hd worst-case PVT. | LOW | MEDIUM | 50 MHz (20ns) is conservative for sky130hd. Synthesize early, identify critical path, pipeline if needed. ALU already single-cycle by architecture — if timing fails, add EX-stage pipeline register (becomes 6-stage, requires spec change). |
| RSK-005 | **Illegal instruction detection gaps.** Some bit patterns that should trap are not detected, leading to undefined behavior. | MEDIUM | MEDIUM | Exhaustive opcode/funct3/funct7 coverage in decoder verification. Fuzz test with random 32-bit patterns; confirm all non-RV32I patterns trap. |
| RSK-006 | **Pipeline interlock deadlock.** Stall logic interacts with flush logic to create a livelock or deadlock condition (e.g., stall+flush simultaneously). | LOW | HIGH | Formal verification of pipeline control FSM — prove liveness (no deadlock) and that all stalls eventually resolve. Directed test for simultaneous stall+flush conditions. |
| RSK-007 | **Reset vector and CSR initialization.** Incorrect reset values cause boot failure or unexpected trap behavior on first instruction. | MEDIUM | HIGH | Hard-code reset values in RTL (not dependent on initialization sequence). Verify CSR reset values in first cycle of simulation. Verify first instruction fetch address matches reset vector. |

---

## 8. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-06-05 | Sage (Requirements Engineer) | Initial draft for Phase 1 gate review |

---

**End of spec.md**
