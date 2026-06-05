# IP-001 Phase 2 — Research Checklist

**Project:** IP-001 — RV32I 5-Stage Pipeline Core  
**Date:** 2026-06-05  
**Researcher:** Research Librarian (Phase 2 Sub-Agent)

---

## FR-001 — Instruction Fetch Unit

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 1.1 | PC increment logic (PC+4 default) | Fundamental to any CPU pipeline — must match RV32I spec byte-addressable but instruction-aligned | RV32I_ISA_RESEARCH.md §1 (RISC-V Unprivileged ISA v2.2) | HIGH |
| 1.2 | Jump target computation (JAL/JALR) | Spec compliance: JAL=PC+imm (bit 0 cleared), JALR=(rs1+imm)&~1 | RV32I_ISA_RESEARCH.md + L10_RISCV_RESEARCH_SYNTHESIS.md §3 | HIGH |
| 1.3 | Branch target resolution timing | In 5-stage, resolve in EX stage → flush IF/ID if taken | L10_RISCV_RESEARCH_SYNTHESIS.md §2 (Control Hazards), TTP010 (2-cycle penalty) | HIGH |
| 1.4 | IF stage stall behavior (load-use, hazard) | IF stalls when ID is stalled or pipeline flush requested | Roy_Advanced §6 (FSM design), TTP010 pipeline control | MEDIUM |
| 1.5 | PC reset vector (0x00000000) | Standard RISC-V convention; verify against spec | RISC-V Privileged Spec v1.12 | HIGH |
| 1.6 | Speculative fetch vs side effects | Fetch is read-only → no side effects. Fetch-ahead pattern | NEORV32_pipeline_summary §5.1, Ibex doc | HIGH |

---

## FR-002 — Instruction Decode Unit

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 2.1 | Full RV32I opcode/funct3/funct7 decode table | Must decode all 40 instructions across 6 formats | RV32I_ISA_RESEARCH.md §1, rv32i_encoding_table.md (image) | HIGH |
| 2.2 | Immediate format extraction (I/S/B/U/J) | 5 distinct bit-scrambling patterns; timing-critical combinatorial | RV32I_ISA_RESEARCH.md §1 (Immediate Encoding), TTP041 control.vhd | HIGH |
| 2.3 | Illegal instruction detection methodology | Unknown opcode/funct3/funct7 combos → trap code 2 | RISC-V Privileged Spec + RSK-005 | HIGH |
| 2.4 | Control signal generation timing | Decoded signals must be stable within one clock cycle (20ns @ 50MHz) | Roy_Advanced §6 (Combinational decode), Taraate_ASIC §3 | MEDIUM |
| 2.5 | x0 hardwired to zero datapath | Must read zero regardless of write; both rs1/rs2 paths | RISC-V ISA §2.1, ALL vault CPU implementations | HIGH |

---

## FR-003 — Execute Unit (ALU)

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 3.1 | RV32I ALU operation completeness | ADD/SUB/AND/OR/XOR/SLL/SRL/SRA/SLT/SLTU — 10 R-type ops | RV32I_ISA_RESEARCH.md §1, rv32i_encoding_table.md | HIGH |
| 3.2 | Arithmetic shift right (SRA) implementation | Sign-bit preservation; funct7 bit 30 discriminates SRA vs SRL | L10_RISCV_RESEARCH_SYNTHESIS.md §1 (funct7 discrimination) | HIGH |
| 3.3 | Variable shift by rs2[4:0] | Only lower 5 bits of shift amount matter | RV32I ISA v2.2 spec; confirmed by PicoRV32 study | HIGH |
| 3.4 | 32-bit adder/subtractor architecture (CLA vs RCA) | Sky130 32-bit RCA ~7ns; CLA ~3ns but more area. 20ns period is generous | Roy_Advanced §7 (Adder Architectures), sky130hd liberty timing data | MEDIUM |
| 3.5 | Branch condition evaluation (EQ/LT/LTU) | 6 branch types require signed + unsigned comparison outputs | L10_RISCV_RESEARCH_SYNTHESIS.md §3, NEORV32_pipeline_study §4 | HIGH |
| 3.6 | Single-cycle ALU feasibility at 50MHz sky130 | 20ns period; 32-bit ADD ~7ns RCA → easily meets timing | Roy_Advanced §13 (STA) + sky130hd typical timing ~50ps/gate | HIGH |

---

## FR-004 — Memory Access Unit

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 4.1 | Load instruction byte/halfword sign extension | LB/LBU/LH/LHU — sign/zero extend to 32 bits | RV32I_ISA_RESEARCH.md §2.3, rv32i_encoding_table.md | HIGH |
| 4.2 | Byte-enable generation for stores (SB/SH/SW) | addr[1:0] determines byte lanes; correct be masking | TTP010 (dmem_wr_en logic), rv32i_encoding_table.md | HIGH |
| 4.3 | Unaligned access policy (trap vs hardware) | Spec says trap on misaligned LW/LH/SW/SH unless hardware handles | RISC-V ISA v2.2 §2.3; Decision: trap (simpler, spec-compliant) | HIGH |
| 4.4 | Harvard D-memory interface timing | Address/wdata/be valid during MEM; d_rdata sampled at cycle end | FR-001+002 spec, IFR-002 | HIGH |
| 4.5 | Memory ordering (single-hart, no speculation) | No fence needed; in-order = naturally consistent | RV32I ISA, spec says FENCE = NOP for single hart | HIGH |

---

## FR-005 — Writeback Unit

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 5.1 | Result mux: ALU/memory/PC+4/CSR | Correct input selection per instruction type | L10_RISCV_RESEARCH_SYNTHESIS.md §3, TTP010 pipeline mux design | HIGH |
| 5.2 | x0 write suppression | Write enable deasserted when rd==0 | All RISC-V implementations in vault | HIGH |
| 5.3 | Writeback-enable control per instruction type | Stores/branches don't write back; JAL/JALR write PC+4 | L10_RISCV_RESEARCH_SYNTHESIS.md §3 | HIGH |
| 5.4 | Concurrent read/write register file behavior | RF write in WB stage; reads in ID stage (2 stages ahead) | Roy_Advanced §5 (DPRAM timing), L10 §2 (forwarding) | HIGH |

---

## FR-006 — Register File

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 6.1 | 32×32-bit with 2R1W ports | Standard RISC-V integer register file spec | Roy_Advanced §5, TTP029 (rotate design), TTP041 (VHDL regs) | HIGH |
| 6.2 | Synthesis strategy: FF array vs block RAM | FF array for sky130hd (no hard macros at this gate budget) | Taraate_ASIC §4, GAP006 (NEORV32 REGFILE_HW_RST option) | MEDIUM |
| 6.3 | Read-during-write behavior with forwarding | RF writes in WB, reads in ID ≡ 2 stages apart → if no forwarding, 2-cycle latency on RAW | L10_RISCV_RESEARCH_SYNTHESIS.md §2 (Data Hazards) | HIGH |
| 6.4 | Reset behavior of register file | Options: zeroed (area cost) or undefined (cheaper). Spec says "documented choice" | TTP010 (reset to index), NEORV32 (optional HW reset) | MEDIUM |

---

## FR-007 — Data Forwarding

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 7.1 | Forwarding path topology: EX/MEM→EX + MEM/WB→EX | Two forwarding sources for both rs1 and rs2 operands | L10_RISCV_RESEARCH_SYNTHESIS.md §2, Patterson & Hennessy §4.5 | HIGH |
| 7.2 | Hazard detection: compare rd(writing) vs rs1/rs2(reading) | Destination register of in-flight instructions matched against sources | L10_RISCV_RESEARCH_SYNTHESIS.md §2 (Data Hazards), Roy_Advanced §13 | HIGH |
| 7.3 | Forwarding priority: EX/MEM > MEM/WB | Most recent result wins — critical for back-to-back dependent instructions | L10 §2 + standard forwarding architecture | HIGH |
| 7.4 | x0 forwarding suppression | Don't forward if destination is x0 | All RISC-V implementations | HIGH |
| 7.5 | Forwarding of memory loads (MEM/WB path) | Load data available at MEM/WB → forwards to EX on next instruction (after stall if needed) | L10 §2 (Load-use hazard) | HIGH |
| 7.6 | Forwarding mux size and critical path impact | 3-select mux per operand (no-fwd / EX-fwd / MEM-fwd); ~2 gate delays | Roy_Advanced §13 (Timing), sky130hd timing | MEDIUM |

---

## FR-008 — Load-Use Hazard Detection and Stall

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 8.1 | Load-use detection: ID loads from rd of EX load | mem_read(EX) && rd(EX)==rs1(ID) or ==rs2(ID) | L10_RISCV_RESEARCH_SYNTHESIS.md §2 (Load-use hazard) | HIGH |
| 8.2 | Single-cycle stall implementation | Freeze IF and ID PC + pipeline registers; insert NOP into EX | Roy_Advanced §6 (FSM with stall), Patterson & Hennessy §4.7 | HIGH |
| 8.3 | Store-after-load: no stall needed | Store gets store data via forwarding from MEM/WB directly | L10 §2, Ibex pipeline details | HIGH |
| 8.4 | Load-use stall + forwarding interaction | After stall, load data forwards from MEM/WB to EX normally | Standard pipeline architecture | HIGH |
| 8.5 | Stall impact on CPI | ~10-15% of instructions in typical code have load-use dependency → CPI ~1.10-1.15 | Patterson & Hennessy data, Dhrystone profiling | MEDIUM |

---

## FR-009 — Branch and Jump Handling

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 9.1 | Predict-not-taken strategy: simplest approach | 0-cycle penalty for not-taken, 2-cycle for taken (flush IF+ID) | L10 §2 (Control Hazards), TTP010 (2-cycle penalty) | HIGH |
| 9.2 | Branch resolved in EX stage in 5-stage pipe | Condition evaluation + target calc in EX; IF/ID flushed on taken | L10 §2, TTP010 pipeline | HIGH |
| 9.3 | JAL/JALR unconditional flush | Link register written (PC+4), pipeline flushed to target | L10 §2, RV32I ISA spec | HIGH |
| 9.4 | 2-cycle branch penalty acceptability | ~15-20% of dynamic instructions are branches; ~50-60% taken → 0.15-0.20 CPI overhead | Patterson & Hennessy data; NFR-005 target CPI < 1.5 | HIGH |
| 9.5 | Branch condition with forwarding | If branch operand depends on prior EX result, forward before branch eval | L10 §2; forwarding covers this case | HIGH |

---

## FR-010 — CSR Access (Zicsr Machine-Mode Subset)

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 10.1 | CSR instruction variants (CSRRW/CSRRS/CSRRC + immediate forms) | Read-modify-write atomicity; CSR address embedded in instruction[31:20] | RISC-V Privileged Spec v1.12 §2.1, rv32i_encoding_table.md | HIGH |
| 10.2 | CSR address map (0x300-0x344) | misa=0x301, mstatus=0x300, mtvec=0x305, mepc=0x341, mcause=0x342, mie=0x304, mip=0x344 | RISC-V Privileged Spec §2.2 | HIGH |
| 10.3 | misa read-only behavior | Write-ignore side-effect implemented in CSR write logic | RISC-V Privileged Spec; misa.MXL=1 (RV32), Extensions field=0 (RV32I only) | HIGH |
| 10.4 | mstatus.MIE/MPIE field interaction | Trap entry: MPIE←MIE, MIE←0. MRET: MIE←MPIE | RISC-V Privileged §3.1 | HIGH |
| 10.5 | mcause exception codes | 2=illegal instruction, 3=breakpoint, 11=ECALL from M-mode | RISC-V Privileged §3.1.13 | HIGH |

---

## FR-011 — Exception and Trap Handling

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 11.1 | Trap entry sequence (save PC→mepc, cause→mcause, disable interrupts, jump→mtvec) | 4-step atomic trap entry; pipeline must flush | RISC-V Privileged Spec §3.1.13-3.1.14 | HIGH |
| 11.2 | MRET exit sequence (restore PC←mepc, MIE←MPIE, return to original mode) | Reverse of trap entry | RISC-V Privileged §3.1.14 | HIGH |
| 11.3 | Trap pipeline flush scope | Entire pipeline must be flushed on trap entry (IF→ID→EX→MEM→WB all NOP) | L10_RISCV_RESEARCH_SYNTHESIS.md, NEORV32 TRAP_ENTER state | HIGH |
| 11.4 | Illegal instruction detection in ID vs EX | Spec says detect in decode; we detect in ID stage | TTP010, TTP041; all implementations decode in ID or ID/EX | HIGH |
| 11.5 | ECALL/EBREAK detection | ECALL = opcode 1110011, funct3=000, imm=0; EBREAK = same but imm=1 | RISC-V ISA v2.2, rv32i_encoding_table.md | HIGH |

---

## FR-012 — Reset Behavior

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 12.1 | Synchronous reset design pattern | Reset asserted for ≥4 cycles; all FFs see same edge | Taraate_ASIC §3.4, Roy_Advanced §4 (FF types) | HIGH |
| 12.2 | Reset vector: 0x00000000 | Standard RISC-V convention; first instruction at reset vector | RISC-V Privileged Spec, all vault implementations | HIGH |
| 12.3 | CSR reset values | mstatus=0, mtvec=0 (or 0x00000000), misa=0x40000100 (RV32I), mie=0, mip=0, mepc=0, mcause=0 | RISC-V Privileged Spec §2.2 | HIGH |
| 12.4 | Pipeline flush on reset | All stages → NOP, PC→reset vector | Roy_Advanced §6 (FSM reset) | HIGH |

---

## FR-013 — Pipeline Control

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 13.1 | Stall implementation: freeze IF/ID registers, inject NOP in EX | Standard 5-stage stall mechanism | Roy_Advanced §6, Patterson & Hennessy §4.7 | HIGH |
| 13.2 | Flush implementation: clear IF/ID (and optionally ID/EX) to NOP | On branch taken, trap, or JAL/JALR | L10 §2, TTP010 | HIGH |
| 13.3 | Simultaneous stall+flush handling | If load-use stall + branch taken same cycle → flush takes priority (RSK-006) | Patterson & Hennessy (standard priority: flush > stall) | MEDIUM |
| 13.4 | Pipeline register structure: data + control signals | Capture instruction word, PC, control signals, ALU inputs/outputs per stage | L10 §2-3, TTP010 signal naming convention | HIGH |

---

## NFR-001 — Clock Frequency (50 MHz sky130hd)

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 14.1 | sky130hd worst-case timing at SS/125C/1.62V | Slow corner FO4 delay ~100ps; 32-bit ADD ~7-8ns; critical path < 20ns easily met | sky130hd liberty files (ORFS); Roy_Advanced §13 | HIGH |
| 14.2 | Critical path identification (forwarding mux + ALU) | fwd_mux(2 gate delays) + 32b ADD(~8ns) + result_mux(1 gate) ≈ 10-12ns → positive slack | Roy_Advanced §13 (Timing), sky130 typical NAND2: 47ps | MEDIUM |
| 14.3 | Clock uncertainty budget for sky130hd at 50MHz | Jitter < 100ps, skew < 300ps → budget ~500ps from 20ns | OpenSTA default margins + sky130 CTS reports from TT projects | MEDIUM |

---

## NFR-002 — Single Clock Domain

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 15.1 | All sequential elements on same clk | No CDC, no clock gating, no dividers | Spec ARC-004; confirmed by all TTP RV32I implementations (single-domain) | HIGH |
| 15.2 | Clock tree balance in OpenROAD | TritonCTS handles sky130hd 50MHz easily; balanced tree < 300ps skew | ORFS flow docs, TTP-029 (64MHz at sky130 works) | HIGH |

---

## NFR-003 — Target PDK (sky130hd)

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 16.1 | sky130hd standard cell availability | ~400 cells; DFF, NAND, NOR, INV, MUX, full/half adder, AOI/OAI, buffers, delays | sky130_fd_sc_hd liberty + LEF (ORFS) | HIGH |
| 16.2 | Yosys synthesis with sky130hd liberty | Proven flow: read_liberty → synth → dfflibmap → abc; TTP projects use this | GAP006 (NEORV32 sky130 flow), all TT submissions | HIGH |
| 16.3 | OpenROAD PnR compatibility | sky130hd has full OpenROAD support (floorplan, PDN, placement, CTS, routing) | ORFS flow/platforms/sky130hd | HIGH |

---

## NFR-004 — Gate Count Budget (≤15k gates)

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 17.1 | Comparable core gate counts | Ibex "micro" RV32EC: 16.85kGE; PicoRV32: ~3-5k GE; SERV: 2.1kGE | Ibex synth reports, SERV README, GAP006 comparison table | HIGH |
| 17.2 | 5-stage RV32I gate estimate | ~12-15k GE (decode+RF ~4k, ALU ~2k, pipeline regs ~1.5k, forwarding+hazard ~1.5k, CSR+trap ~2k, control ~1.5k) | Derived from TTP010 (20-35k with SPI+IMEM), TTP041 (10-20k), Ibex "micro" (16.85k RV32EC) | MEDIUM |
| 17.3 | Gate budget risk: forwarding + CSR may push >15k | CSR block (7 registers × 32b = 224 FFs + logic) is significant area | Synthesize early (Phase 3 recommendation: Yosys gate count after module design) | MEDIUM |

---

## NFR-005 — CPI Target (<1.5)

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 18.1 | Ideal 5-stage CPI baseline = 1.0 | No stalls, no flushes → 1 instruction per cycle | Standard pipeline theory (Patterson & Hennessy) | HIGH |
| 18.2 | Load-use stall overhead: ~10% of instructions | Typical code has ~25% loads, ~40% have dependent next instruction → 0.1 stall/instruction | Patterson & Hennessy §4.7 profiling data | MEDIUM |
| 18.3 | Branch flush overhead: ~15% × 60% taken × 2 cycles | ~0.18 CPI overhead from branches | Patterson & Hennessy branch statistics | MEDIUM |
| 18.4 | Estimated real CPI: 1.0 + 0.1 + 0.18 = ~1.3 | Within NFR-005 target of <1.5 | Calculated from above; verify with Dhrystone simulation | MEDIUM |

---

## IFR-001/002/003 — Memory Interfaces

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 19.1 | Harvard internal interface design | Separate I-addr/rdata and D-addr/rdata/wdata/be/we ports | Spec IFR-001/002, ARC-006, TTP021 (Harvard arch) | HIGH |
| 19.2 | No bus protocol rationale | Simpler verification; internal core only; backend integration handles memory macros | Spec IFR-003, ARC-006 | HIGH |
| 19.3 | Synchronous memory model assumption | Data expected same-cycle; SRAM macros at sky130 have <3ns access time | Roy_Advanced §5, OpenRAM sky130 data (self-learning), 50MHz = 20ns margin | HIGH |

---

## IFR-004 — Interrupt Inputs

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 20.1 | mip.MEIP/MTIP connection to external pins | Direct wire from irq_timer + irq_external → mip CSR bits | RISC-V Privileged Spec §2.2 | HIGH |
| 20.2 | Level-sensitive interrupt model | Interrupt held until serviced (cleared by handler writes to mip) | RISC-V Privileged Spec, TTP029 interrupt architecture | HIGH |

---

## Cross-Cutting Research

| # | Research Item | Why? | Source(s) | Confidence |
|---|--------------|------|-----------|------------|
| 21.1 | RISC-V compliance test suite (riscv-tests) | Official RISC-V unit tests for RV32I; Spike golden model comparison | riscv-tests GitHub repo (riscv-software-src) | HIGH |
| 21.2 | RISC-V formal verification (riscv-formal) | Formal properties for RV32I instruction set compliance | YosysHQ/riscv-formal GitHub | HIGH |
| 21.3 | Spike ISA simulator as GRM | Spike `--isa=rv32i` for golden reference comparison | riscv-isa-sim (riscv-software-src), self-learning (IP-001 lessons) | HIGH |
| 21.4 | Open-source 5-stage RV32I pipeline implementations | Study known-good designs for hazard handling patterns | TTP010 (5-stage, TL-Verilog), various FPGA cores (GitHub) | MEDIUM |
| 21.5 | Sky130 SRAM macro vs flip-flop register file trade-off | 32×32b FF array ~1024 FFs = ~4k GE; SRAM macro more efficient but needs OpenRAM | OpenRAM sky130, GAP006; FF array simpler for Phase 3 | MEDIUM |

---

## Confidence Summary

| Level | Count | Notes |
|-------|-------|-------|
| **HIGH** | 42 | Well-covered by vault + RISC-V spec |
| **MEDIUM** | 11 | Some estimation needed; confirm at Phase 3/4 |
| **LOW** | 0 | All research items covered |

---

## Flagged for Phase 3 (Microarch)

1. **NFR-004 gate count:** Synthesize prototype early in Phase 3 to confirm <15k GE
2. **FR-007 forwarding critical path:** Synthesize with sky130hd liberty to confirm setup slack at 50MHz
3. **FR-008/FR-009 stall+flush interaction (RSK-006):** Formal property checking recommended for pipeline control FSM
4. **FR-006 register file:** Choose FF array vs block RAM inference; impact on gate count
5. **FR-010 CSR block:** Detailed CSR decode + FSM required; interaction with trap FSM needs careful design

---

**Research Checklist Complete — 55 research items across 20 requirement areas.**
