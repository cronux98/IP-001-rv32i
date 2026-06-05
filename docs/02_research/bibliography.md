# IP-001 — Phase 2 Annotated Bibliography

**Project:** IP-001 — RV32I 5-Stage Pipeline Core  
**Date:** 2026-06-05  
**Sources:** 22 (14 vault + 8 external)  

---

## 1. ISA Specifications & Standards

### [B1] RISC-V User-Level ISA Specification v2.2 (2019)
- **Type:** Standard / Specification
- **Source:** RISC-V Foundation, ratified 2019-12-13
- **URL:** https://github.com/riscv/riscv-isa-manual/releases/tag/Ratified-IMAFDQC
- **Key Findings:** Definitive encoding of all 40 RV32I instructions across 6 formats (R/I/S/B/U/J). Opcode map, funct3/funct7 discrimination, immediate encoding formulas. Branch offset LSB always 0 (16-bit aligned instruction boundary). x0 hardwired to zero. All memory accesses are little-endian.
- **Relevance to IP-001:** Primary ISA compliance reference. Every instruction decode, ALU operation, and memory access in our design must match this spec. ARC-001 mandates compliance.
- **Confidence:** HIGH

### [B2] RISC-V Privileged Architecture Specification v1.12 (2021)
- **Type:** Standard / Specification
- **Source:** RISC-V Foundation  
- **URL:** https://github.com/riscv/riscv-isa-manual (Volume II: Privileged Architecture)
- **Key Findings:** Machine-mode CSR address map (misa=0x301, mstatus=0x300, mtvec=0x305, mepc=0x341, mcause=0x342, mie=0x304, mip=0x344). CSR instruction semantics (CSRRW/CSRRS/CSRRC + immediate variants). Trap entry/exit sequence: save PC→mepc, cause→mcause, MIE←0, PC→mtvec. MRET restores PC←mepc, MIE←MPIE. Exception codes: 2=illegal instruction, 3=breakpoint, 11=ECALL from M-mode.
- **Relevance to IP-001:** FR-010, FR-011, and IFR-004 are directly derived from this spec. CSR implementation must be byte-exact to the privileged spec to avoid software incompatibility (RSK-002).
- **Confidence:** HIGH

### [B3] RISC-V Instruction Encoding Table (rv32i_encoding_table.md)
- **Type:** Vault Research Note
- **Source:** Vault: ~/vlsi-team/architecture-notes/02-research/rv32i_encoding_table.md
- **Key Findings:** Complete visual encoding map of all RV32I instructions showing opcode, funct3, funct7, and format. Covers all 40 instructions with immediate field mappings. Opcode=0110011 for R-type, 0010011 for I-type ALU, 0000011 for loads, 0100011 for stores, 1100011 for branches, 1101111 for JAL, 1100111 for JALR, 0110111 for LUI, 0010111 for AUIPC, 1110011 for SYSTEM (ECALL/EBREAK/CSR).
- **Relevance to IP-001:** Reference table for decoder design (FR-002). Confirms all instruction encodings match the RV32I spec.
- **Confidence:** HIGH

---

## 2. Pipeline Architecture & Design Patterns

### [B4] L10 RISC-V RV32I Research Synthesis
- **Type:** Vault Research Note
- **Source:** Vault: ~/vlsi-team/architecture-notes/02-research/L10_RISCV_RESEARCH_SYNTHESIS.md
- **Key Findings:** 3-stage pipeline design (FETCH→DECODE→EXECUTE) with complete hazard analysis: EX→EX forwarding, load-use stall (1 cycle), branch resolution in decode (1-cycle flush). Data hazard detection: EX/MEM.rd == ID/EX.rs1/rs2 → forward. Load-use: ID/EX.mem_read && rd matches source → stall. Design decisions: predict-not-taken, no delay slot, single clock domain.
- **Relevance to IP-001:** This note was our prior work on a simpler RV32I pipeline. Key hazard handling patterns transfer directly to the 5-stage design for IP-001, with one additional forwarding stage (MEM/WB→EX) and branch resolution moved from ID to EX.
- **Confidence:** HIGH

### [B5] Roy — Advanced Digital System Design: A Practical Guide (2024)
- **Type:** Textbook
- **Source:** Shirshendu Roy, Springer 2024, ISBN 978-3-031-41085-7
- **Key Findings:** Comprehensive reference for: FSM design (Mealy/Moore, 2 always-block pattern, state minimization), adder architectures (CLA, Brent-Kung, Kogge-Stone, Ladner-Fischer), shift register design, counter architectures (LFSR, ring, Johnson), memory design (SPRAM, DPRAM, initialization methods), static timing analysis (setup/hold/recovery/removal equations, max frequency calculation, skew budget), pipeline design principles, and Verilog coding for synthesis. Critical: non-blocking (<=) for sequential, blocking (=) for combinational; always cover else/default.
- **Relevance to IP-001:** Foundational textbook for all digital design decisions. FSM patterns apply to pipeline control (FR-013), ALU design (FR-003), register file (FR-006), and STA verification (NFR-001). The STA chapter directly informs our 50MHz timing closure strategy.
- **Confidence:** HIGH

### [B6] Taraate — ASIC Design and Synthesis: RTL Design Using Verilog (2021)
- **Type:** Textbook
- **Source:** Vaibbhav Taraate, Springer 2021, ISBN 978-981-33-4641-3
- **Key Findings:** 25 essential ASIC design patterns including: non-blocking for sequential, blocking for combinational, registered outputs, no inferred latches, synchronous reset preferred, 2-FF CDC synchronizer, async FIFO for multi-bit CDC, register balancing, resource sharing, pipelining. Synthesis methodology: RTL → gate-level netlist with constraints and technology library. Physical design flow: floorplan → PDN → placement → CTS → routing → DRC/LVS → GDSII. Clock gating awareness.
- **Relevance to IP-001:** 15 of the 25 patterns apply directly to IP-001 RTL quality: no inferred latches (decoder), synchronous reset (FR-012), single clock domain (NFR-002), registered outputs (pipeline registers), partition at sequential boundaries. Synthesis flow reference for sky130hd mapping.
- **Confidence:** HIGH

### [B7] NEORV32 Pipeline Architecture Study
- **Type:** Vault Research Note (dual files)
- **Source:** Vault: neorv32_pipeline_summary.md + neorv32_pipeline_study.md
- **Key Findings:** NEORV32 uses a 2-stage pipeline (front-end fetch/issue + multi-cycle execute engine FSM). NO forwarding required — write/read timing separation eliminates need through register file mux scheduling. Load-use hazards naturally avoided by multi-cycle state machine sequencing. Branch resolution in execute BRANCH state, 4-cycle penalty. 12-state execute engine FSM. Critical insight: RF uses single muxed port for rd(write)/rs1(read) — write in DISPATCH state, read in EXECUTE state, always 1 cycle apart.
- **Relevance to IP-001:** NEORV32 represents the "no forwarding needed" design approach. Valuable contrast for IP-001: our 5-stage pipeline MUST have forwarding because result-to-use distance is 1-2 cycles (vs NEORV32's forced 1-cycle gap). Validates that our forwarding requirements are architecturally necessary, not optional.
- **Confidence:** HIGH

### [B8] Ibex (lowRISC) CPU Pipeline Documentation
- **Type:** Open-Source Implementation Documentation
- **Source:** lowRISC, GitHub: lowRISC/ibex, Docs: https://ibex-core.readthedocs.io/
- **Key Findings:** Ibex is a production-quality 32-bit RISC-V core supporting RV32IMCB. 2-stage pipeline (IF → ID/EX), optionally 3-stage with writeback. Performance configs: "micro" (RV32EC, 16.85kGE Yosys, 0.904 CoreMark/MHz), "small" (RV32IMC, 26.60kGE, 2.47 CoreMark/MHz), "maxperf" (RV32IMC, 32.48kGE, 3.13 CoreMark/MHz). Verified with industrial-grade UVM. Multiple tapeouts. All instructions take ≥2 cycles; multi-cycle instructions stall ID/EX. Forwarding from EX result to next ID/EX.
- **Relevance to IP-001:** Ibex "maxperf" config (32.48kGE) is our closest comparable. Our 5-stage RV32I (no M/C) should be ~12-15kGE — about half of Ibex maxperf. Ibex verification methodology is a gold standard to aspire toward (though we use cocotb, not UVM).
- **Confidence:** HIGH

---

## 3. Open-Source RISC-V Core Implementations

### [B9] TTP-010: RISCV32I CPU with SPI Bootloader (TT07)
- **Type:** Vault TTP Note (Silicon Tapeout)
- **Source:** Vault: ~/vlsi-team/architecture-notes/03-tt-projects/TTP010_RISCV32I_SPI_Wrapper.md
- **Key Findings:** Silicon-taped 5-stage RV32I pipeline at 50MHz on SkyWater 130nm. 8×2 tiles, ~20-35k gates. TL-Verilog → SandPiper → SystemVerilog flow. Pipeline stages: a0(PC) → a1(IF/Decode) → a2(ID/RegRd) → a3(EX/ALU) → a4(MEM) → a5(WB). Forwarding from a3 to a2. Load-use handled by valid_load_a5. Predict-not-taken with 2-cycle flush penalty. DMEM write-protect bug found (CSR protection logic uses OR of ≠ checks = always true). 16 instruction words, SPI bootloader.
- **Relevance to IP-001:** Closest existing silicon reference — same 5-stage pipeline, same frequency, same PDK, similar RV32I target. The DMEM write-protect bug is a cautionary tale. Pipeline stage mapping (a0-a5) provides naming convention reference.
- **Confidence:** HIGH (silicon-verified on SkyWater 130nm)

### [B10] TTP-021: UART-Programmable RV32I Core (TT06)
- **Type:** Vault TTP Note (Silicon Tapeout)  
- **Source:** Vault: ~/vlsi-team/architecture-notes/03-tt-projects/TTP021_UART_RV32I_CPU.md
- **Key Findings:** Simplified RV32I with 16 GPRs (not 32), Harvard architecture, UART auto-baud bootloader. Verilog + TL-Verilog hybrid. 4×2 tiles, ~8-15k gates. UART is a clean, reusable IP block (auto-baud, half-bit sampling, 4-state FSM). CPU pipeline: @1(fetch), @2(decode+regread), @3(execute+writeback). Only 16 instructions of IMEM and 4 words of DMEM. x16-x31 not implemented. No ECALL/EBREAK.
- **Relevance to IP-001:** Demonstrates minimal viable RV32I in a small tile footprint. The register file byte-write-enable pattern and Harvard architecture are directly applicable. The 16-GPR simplification is NOT sufficient for IP-001 (we need full 32-entry RF). Clean module decomposition pattern.
- **Confidence:** HIGH (silicon-verified on SkyWater 130nm)

### [B11] TTP-029: TinyQV RISC-V SoC (TT06)
- **Type:** Vault TTP Note (Silicon Tapeout)
- **Source:** Vault: ~/vlsi-team/architecture-notes/03-tt-projects/TTP029_TinyQV_RISC_V_SoC.md
- **Key Findings:** RV32EC SoC with novel 4-bit serial ALU architecture in 2×2 tiles at 64MHz sky130. ALU processes 4 bits/cycle, register file barrel-rotates nibble. 8 cycles per 32-bit ALU operation. Complete machine-mode trap handling (mstatus, mie, mip, mepc, mcause). QSPI Flash + dual PSRAM external memory. 16-entry register file (E extension). GDS Built ✅. Formal verification on QSPI controller. Custom GCC toolchain and web programmer.
- **Relevance to IP-001:** Demonstrates that full machine-mode CSR handling (FR-010, FR-011) fits even in 2×2 tiles. The serial ALU is the opposite of our design (maximum area optimization vs our IPC optimization), but CSR+trap implementation patterns are reusable. Shows SkyWater 130nm supports 64MHz (our 50MHz target is conservative).
- **Confidence:** HIGH (silicon-tested on SkyWater 130nm)

### [B12] TTP-041: TinyRV1 CPU (TT06)
- **Type:** Vault TTP Note (Silicon Tapeout)
- **Source:** Vault: ~/vlsi-team/architecture-notes/03-tt-projects/TTP041_TinyRV1_CPU.md
- **Key Findings:** VHDL-based RISC-V CPU implementing TinyRV1 ISA subset. Memory-less architecture — zero on-die instruction memory; all instructions fetched from external SPI Flash. 6-state multi-cycle FSM. 12MHz. ~10-20k gates in 3×2 tiles. Comprehensive verification: cocotb Python + per-module VHDL testbenches + gate-level simulation. 13-instruction test program. 5-format immediate generator (I/S/B/U/J). x1 exposed on 13 debug pins.
- **Relevance to IP-001:** Exemplary verification methodology (cocotb + VHDL + GLS). The immediate generator pattern (combinational, 5-format) is directly reusable. Shows a clean multi-cycle FSM architecture. The memory-less approach is NOT relevant for IP-001 (we have internal Harvard interfaces). Proves that cocotb + standard RISC-V test methodology works in the open-source flow.
- **Confidence:** HIGH (silicon on SkyWater 130nm)

### [B13] SERV — The SErial RISC-V CPU
- **Type:** Open-Source Implementation
- **Source:** olofk/serv, GitHub. ISC License.
- **Key Findings:** Award-winning bit-serial RISC-V core. World's smallest RISC-V CPU: 2.1kGE in CMOS, 125 LUTs on Artix-7. RV32I with bit-serial ALU. ~32 cycles per instruction. 200+ MHz capable on sky130. Used by multiple TT submissions as co-processor.
- **Relevance to IP-001:** SERV defines the lower bound on RV32I implementation size — our 5-stage design will be ~7× larger but >30× faster. Validates our gate budget target (15kGE for our core is between SERV at 2.1kGE and Ibex "micro" at 16.85kGE). Reference for worst-case correctness verification.
- **Confidence:** HIGH

---

## 4. Verification & Testing Methodology

### [B14] riscv-tests — RISC-V Unit Tests
- **Type:** Verification Suite / Software
- **Source:** riscv-software-src/riscv-tests, GitHub. BSD License.
- **Key Findings:** Official RISC-V compliance test suite. TVMs (Test Virtual Machines) for rv32ui (user-level integer), rv32si (supervisor-level integer). Tests use standardized macros (RVTEST_CODE_BEGIN/END, RVTEST_PASS/FAIL). Self-checking: each test writes pass/fail signature to memory. Designed to run on bare-metal with minimal infrastructure.
- **Relevance to IP-001:** Primary verification reference for FR-001 through FR-005 compliance. The rv32ui-p-* tests (p=physical memory, no VM) are directly runnable in our cocotb testbench. Provides coverage for all 40 RV32I instructions.
- **Confidence:** HIGH

### [B15] RISC-V Formal Verification Framework (riscv-formal)
- **Type:** Formal Verification Tool
- **Source:** YosysHQ/riscv-formal, GitHub
- **Key Findings:** Formal verification specifications for RISC-V ISA compliance. Uses SymbiYosys to prove instruction behaviors against a formal ISA model. Covers RV32I base instruction set. Provides bounded model check (BMC) and k-induction proofs for each instruction type.
- **Relevance to IP-001:** Recommended for Phase 5 verification (beyond cocotb directed+random tests). Especially valuable for hazard detection logic (FR-007, FR-008) and branch resolution (FR-009) where corner cases are subtle. Mentioned in RSK-001 and RSK-006 mitigations.
- **Confidence:** MEDIUM (requires SymbiYosys setup; not yet tested in our flow)

---

## 5. Core Comparison & Selection Reference

### [B16] GAP006 — RV32IMC Core Options for SkyWater 130nm
- **Type:** Vault Research (Comprehensive Comparison)
- **Source:** Vault: ~/vlsi-team/architecture-notes/02-research/GAP006_RV32IMC_CORE_OPTIONS.md
- **Key Findings:** Quantitative comparison of 5 RISC-V cores for sky130: NEORV32 (10-15k gates, 2-stage), SERV (2.1kGE bit-serial), PicoRV32 (3-5k gates, multi-cycle), VexRiscv (3-8k gates, configurable), Ibex (10-15k gates, 2/3-stage). NEORV32 recommended for IP-001 bed alarm (rich peripherals). Gate count scaling: Core size doubles from 2-stage→5-stage due to pipeline registers, forwarding muxes, and hazard control.
- **Relevance to IP-001:** Provides gate count calibration for our custom core. NEORV32 at 10-15k gates (2-stage, no forwarding) → our 5-stage with forwarding should be 12-15k gates if no M extension. The comparison validates that a custom RV32I core is architecturally justified when we need specific pipeline characteristics.
- **Confidence:** HIGH

### [B17] PicoRV32 — A Size-Optimized RISC-V Core
- **Type:** Open-Source Implementation
- **Source:** YosysHQ/picorv32, GitHub. ISC License.
- **Key Findings:** Configurable RV32I/E + M + C core. Multi-cycle FSM (no pipeline). Core size: ~1,000-2,000 LUTs (FPGA) → ~3-5k gates ASIC. CPI ~4. f_max ~80 MHz on sky130. 8 execution states (FETCH→LD_RS1→LD_RS2→EXEC→SHIFT→STMEM→LDMEM→TRAP). Barrel shifter takes extra cycle.
- **Relevance to IP-001:** PicoRV32's instruction execution model (8-state FSM) is the opposite of our pipelined approach. Useful as a correctness reference for instruction semantics. Its minimal decode logic is a good starting point for our decoder design. Gate count (~3-5kGE) confirms our 12-15kGE estimate for the pipelined version is reasonable.
- **Confidence:** HIGH

---

## 6. PDK, Toolchain & Implementation

### [B18] SkyWater 130nm HD Standard Cell Library
- **Type:** PDK / Technology Library
- **Source:** SkyWater Technology Foundry / Google, via OpenROAD-flow-scripts: `platforms/sky130hd/`
- **Key Findings:** HD library (1.8V core, 3.3V I/O). ~400 standard cells. Typical NAND2 delay ~47ps, DFF setup ~200ps. 50MHz (20ns period) is deeply conservative — sky130hd supports 100+ MHz with proper pipelining. Multiple TT tapeouts at 50-64MHz confirm. SRAM access time ~2-3ns at sky130 (OpenRAM).
- **Relevance to IP-001:** Primary target library (ARC-002, NFR-003). All gate count estimates use sky130hd NAND2-equivalent metric. The conservative 50MHz target ensures ample timing margin even at slow corner (SS/125C/1.62V).
- **Confidence:** HIGH

### [B19] OpenROAD-flow-scripts (ORFS)
- **Type:** Open-Source Physical Design Flow
- **Source:** The-OpenROAD-Project/OpenROAD-flow-scripts, GitHub
- **Key Findings:** Complete open-source RTL-to-GDSII flow for sky130hd. Stages: synthesis (Yosys) → floorplan → PDN → placement (RePlAce) → CTS (TritonCTS) → routing (TritonRoute) → DRC/LVS (Magic/KLayout). sky130hd platform fully supported. Multiple tapeout successes via Tiny Tapeout + Google/Efabless shuttles.
- **Relevance to IP-001:** Backend implementation flow after architect stage. Confirms that the open-source toolchain requirement (ARC-003, NFR-007) is production-ready for sky130hd at our target complexity.
- **Confidence:** HIGH

### [B20] Verilator — Fast Verilog/SystemVerilog Simulator
- **Type:** Open-Source EDA Tool
- **Source:** verilator/verilator, GitHub. LGPL-3.0.
- **Key Findings:** Industry-standard open-source Verilog lint and simulation tool. `--Wall --lint-only` catches inferred latches, width mismatches, unused signals. Co-simulation with C++/SystemC. Fast enough for constrained-random testbenches.
- **Relevance to IP-001:** Primary lint tool (NFR-007). The "never ship RTL that hasn't seen verilator --lint-only --Wall" rule from SOUL.md applies. Lint-zero is a Phase 5 gate requirement.
- **Confidence:** HIGH

---

## 7. External Research — Pipeline Design & Verification

### [B21] Patterson & Hennessy — Computer Organization and Design (RISC-V Edition)
- **Type:** Textbook (referenced indirectly via vault notes)
- **Source:** D.A. Patterson and J.L. Hennessy, "Computer Organization and Design: The Hardware/Software Interface, RISC-V Edition", Morgan Kaufmann, 2017
- **Key Findings:** Classic 5-stage pipeline architecture (IF→ID→EX→MEM→WB). Complete forwarding path analysis: EX/MEM→EX (both operands), MEM/WB→EX (both operands). Load-use hazard detection: stall 1 cycle when load result feeds next instruction. Branch hazard: predict-not-taken, flush 2 instructions if taken. Pipeline control: stall signals (freeze PC + insert bubble), flush signals (clear to NOP). Hazard detection unit + forwarding unit block diagrams. CPI analysis: ideal 1.0, actual 1.1-1.3 with forwarding + load stalls + branch flushes.
- **Relevance to IP-001:** This is THE canonical reference for 5-stage pipeline design. Every forwarding path, stall condition, and flush mechanism in FR-007 through FR-009 derives from this textbook. The predict-not-taken strategy and 2-cycle branch penalty were directly adopted.
- **Confidence:** HIGH (standard textbook, universally cited)

### [B22] OpenCores / FPGA RISC-V 5-Stage Implementations (Survey)
- **Type:** Open-Source Implementations (multiple)
- **Source:** Various GitHub repositories (survey of ~12 small RV32I cores)
- **Key Findings:** Common patterns in small 5-stage RV32I cores: ALU implemented as case/mux tree (25+ conditions), forwarding with 2-level mux (no-fwd/EX-fwd/MEM-fwd), branch resolved in EX stage, stall+flush handled by pipeline control FSM. Typical gate count: 8-15k LUTs on FPGA → 5-12k GE on ASIC. Common bug: x0 write suppression missing in one pipeline path. Common optimization: forwarding of ALU result from EX stage resolves most hazards without stall.
- **Relevance to IP-001:** Validates our architecture choices (5-stage, predict-not-taken, forwarding from EX+MEM). Confirms gate count estimates. The x0 write suppression bug appears in multiple implementations → our FR-005 acceptance criteria must be strictly tested.
- **Confidence:** MEDIUM (aggregated from multiple sources, not individually verified)

---

## Source Summary

| Category | Count | Sources |
|----------|-------|---------|
| ISA Specifications & Standards | 3 | B1-B3 |
| Pipeline Architecture & Patterns | 5 | B4-B8 |
| Open-Source Core Implementations | 5 | B9-B13 |
| Verification & Testing | 2 | B14-B15 |
| Core Comparison & Selection | 2 | B16-B17 |
| PDK, Toolchain & Implementation | 3 | B18-B20 |
| External Pipeline Design | 2 | B21-B22 |
| **TOTAL** | **22** | |

### Source Quality

| Quality | Count | Description |
|---------|-------|-------------|
| Silicon-Verified (TTP) | 4 | TTP-010, TTP-021, TTP-029, TTP-041 — fabricated on SkyWater 130nm |
| RISC-V Standard/Foundation | 2 | RISC-V ISA spec, Privileged spec |
| Academic Textbook | 3 | Roy 2024, Taraate 2021, Patterson & Hennessy 2017 |
| Open-Source Production | 4 | Ibex, SERV, PicoRV32, riscv-tests |
| Vault Research (Curated) | 6 | L10 Synthesis, NEORV32 study, GAP006, encoding table, rv32i research |
| Tool/Flow Documentation | 2 | Sky130 PDK, ORFS |
| Community Survey | 1 | FPGA RV32I implementations |

---

*22 sources, 7 categories, all annotated with findings and relevance to IP-001.*
