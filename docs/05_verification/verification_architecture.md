# IP-001 — RV32I 5-Stage Pipeline Core: Verification Architecture

**Document:** verification_architecture.md  
**Phase:** 5 — Verification Engineer  
**Date:** 2026-06-05  
**Author:** Sage (Verification Engineer)  
**Dependencies:** spec.md v0.1, microarchitecture.md, grm_specification.md, all module specs  
**Tier:** Medium  

---

## 1. Verification Strategy Overview

### 1.1 Verification Target

This phase verifies the **architecture specification** — not RTL. The Device Under Test (DUT) is the architectural model defined in Phase 3 microarchitecture. All tests compare instruction-level behavior against the Spike golden reference model (`spike --isa=rv32i`).

**This is an architecture verification phase.** RTL does not exist yet. We verify that:
1. The architectural specification (pipeline behavior, forwarding, stalls, traps) is correct and internally consistent
2. Every instruction defined in FR-001–FR-013 produces correct results
3. The GRM correctly models all specified behaviors
4. Hazard scenarios are correctly specified and resolvable

### 1.2 Verification Philosophy

> *"Trust but verify with formal."*

For architecture verification of a pipelined CPU core:
- **Directed tests** verify every instruction, every CSR, every trap type, every forwarding path
- **Constrained-random tests** stress the forwarding/stall logic with random instruction sequences
- **Comparison against Spike** is the primary correctness check — Spike is the architectural gold standard
- **Functional coverage** ensures every requirement is tested, every forwarding path exercised, every hazard triggered

### 1.3 Key Differences from Template

| Template (Standard) | IP-001 (Custom) | Reason |
|---------------------|-----------------|--------|
| Wishbone/AXI agent | ❌ Not needed | Pure CPU core — no bus protocol |
| Sensor models | ❌ Not needed | No peripherals |
| I2C/SPI/UART monitors | ❌ Not needed | No external interfaces |
| Register read/write tests | ✅ Instruction + CSR register tests | RV32I register file + 7 CSRs |
| Instruction-level comparison | ✅ Against Spike GRM | Spike is architectural gold standard |
| Pipeline behavior verification | ✅ Forwarding, stalls, flushes | 5-stage pipeline hazards |
| CSR operation verification | ✅ All 7 CSRs, all 6 instruction variants | Machine-mode CSR subset |
| Trap/exception sequences | ✅ ECALL, EBREAK, illegal, MRET | RISC-V privileged spec |

---

## 2. Environment Architecture

### 2.1 Block Diagram

```
+=======================================================================+
|                     VERIFICATION ENVIRONMENT                           |
|                                                                       |
|  +------------------+        +------------------+                     |
|  |  instruction_     |        |  riscv-tests     |                     |
|  |  generator.py     |        |  (rv32ui-p-*)    |                     |
|  |  (random RV32I)   |        |  + custom .S     |                     |
|  +--------+---------+        +--------+---------+                     |
|           |                           |                               |
|           v                           v                               |
|  +------------------+        +------------------+                     |
|  | riscv64-gcc     |        |  ELF Binary      |                     |
|  | compile + link   |        |                  |                     |
|  +--------+---------+        +--------+---------+                     |
|           |                           |                               |
|           +-----------+---------------+                               |
|                       |                                               |
|                       v                                               |
|  +----------------------------------------------+                    |
|  |            Spike GRM                          |                    |
|  |  (spike --isa=rv32i --priv=m -m0x2000 -l)    |                    |
|  |                                              |                    |
|  |  Produces:                                    |                    |
|  |    - Execution trace (Spike commit log)       |                    |
|  |    - Final register file state                |                    |
|  |    - Memory state (stores)                    |                    |
|  +----------------------+-----------------------+                    |
|                         |                                             |
|                         v                                             |
|  +----------------------------------------------+                    |
|  |           SCOREBOARD (scoreboard.py)          |                    |
|  |                                              |                    |
|  |  Compares:                                    |                    |
|  |    - Register file state (x0-x31)             |                    |
|  |    - CSR state (7 CSRs)                       |                    |
|  |    - Memory state (D-mem stores)              |                    |
|  |    - Instruction trace (PC sequence)          |                    |
|  +----------------------+-----------------------+                    |
|                         |                                             |
|                         v                                             |
|  +----------------------------------------------+                    |
|  |         COVERAGE MODEL (coverage.py)          |                    |
|  |                                              |                    |
|  |  Tracks:                                      |                    |
|  |    - Instruction type coverage (40 types)     |                    |
|  |    - ALU operation coverage (14 ops)          |                    |
|  |    - Forwarding path coverage (4 paths)       |                    |
|  |    - CSR operation coverage (6 variants × 7)  |                    |
|  |    - Trap type coverage (5 types)             |                    |
|  |    - Pipeline event coverage (stall/flush)    |                    |
|  +----------------------+-----------------------+                    |
|                         |                                             |
|                         v                                             |
|  +----------------------------------------------+                    |
|  |         PIPELINE MONITOR (pipeline_monitor.py)|                    |
|  |                                              |                    |
|  |  Analyzes instruction streams for:            |                    |
|  |    - RAW hazards (all types)                  |                    |
|  |    - Load-use dependencies                    |                    |
|  |    - Forwarding opportunities                 |                    |
|  |    - Branch patterns                          |                    |
|  |    - Sequences that SHOULD stall              |                    |
|  +----------------------------------------------+                    |
|                         |                                             |
|                         v                                             |
|  +----------------------------------------------+                    |
|  |            TEST REPORT                       |                    |
|  |  - Per-test pass/fail                        |                    |
|  |  - Coverage metrics                          |                    |
|  |  - Mismatch details                          |                    |
|  |  - Pipeline statistics                       |                    |
|  +----------------------------------------------+                    |
+=======================================================================+
```

### 2.2 Component Descriptions

| Component | File | Function |
|-----------|------|----------|
| **Scoreboard** | `env/scoreboard.py` | Central comparison engine. Compares DUT state vs GRM state (register file, CSRs, memory). Verifies x0 invariance. |
| **Coverage Model** | `env/coverage.py` | Functional coverage tracker. Records instruction types, ALU ops, forwarding paths, CSR operations, trap types, pipeline events. |
| **Pipeline Monitor** | `env/pipeline_monitor.py` | Static analysis of instruction streams. Detects RAW hazards, identifies forwarding opportunities, predicts stalls needed. |
| **Instruction Generator** | `env/instruction_generator.py` | Constrained-random RV32I instruction generator. Produces legal instruction sequences with controlled hazard density. |
| **Trace Compare** | `env/trace_compare.py` | Compares instruction-by-instruction traces between GRM and DUT. Handles PC alignment, register write comparison, store comparison. |
| **Spike GRM** | `grm/src/spike_grm.py` | Golden reference model — Spike RISC-V simulator (Phase 4 deliverable, reused). |
| **GRM Config** | `grm/src/grm_config.py` | Platform configuration (Phase 4 deliverable, reused). |
| **Compare Trace** | `grm/src/compare_trace.py` | Trace comparison utility (Phase 4 deliverable, reused). |

---

## 3. Test Plan

### 3.1 Test Inventory

| Test ID | Test File | Requirements Covered | Type | Instructions |
|----------|-----------|---------------------|------|-------------|
| T5.1 | `test_instructions.py` | FR-001–FR-006 | Directed | ~500 (40 instruction types × variants) |
| T5.2 | `test_forwarding.py` | FR-007 | Directed | ~200 (all 4 forwarding paths × scenarios) |
| T5.3 | `test_hazards.py` | FR-008, FR-009 | Directed | ~150 (load-use, branch, jump hazards) |
| T5.4 | `test_csr.py` | FR-010 | Directed | ~300 (7 CSRs × 6 instruction variants) |
| T5.5 | `test_traps.py` | FR-011 | Directed | ~200 (all trap types + MRET) |
| T5.6 | `test_pipeline.py` | FR-012, FR-013 | Directed | ~100 (stall, flush, NOP, reset) |
| T5.7 | `test_random.py` | FR-001–FR-009 | Random | 10,000+ (constrained random stream) |
| T5.8 | `test_compliance.py` | ARC-001 | Compliance | All rv32ui-p-* riscv-tests |

### 3.2 Test Details

#### T5.1 — Instruction-Level Tests (`test_instructions.py`)

**Objective:** Verify all 40 unique RV32I instructions produce correct results against Spike GRM.

**Strategy:** For each instruction class, generate a minimal program that:
1. Initializes source registers with known values
2. Executes the target instruction
3. Stores the result to a known memory location (or leaves in register)
4. Compares final register/memory state against Spike execution of the same program

**Instruction Groups Tested:**

| Group | Instructions | Count | Test Patterns |
|-------|-------------|-------|---------------|
| R-type ALU | ADD, SUB, SLL, SLT, SLTU, XOR, SRL, SRA, OR, AND | 10 | Register-to-register, edge operands (0, -1, max), chain |
| I-type ALU | ADDI, SLTI, SLTIU, XORI, ORI, ANDI, SLLI, SRLI, SRAI | 9 | Immediate range (0, -1, power-of-2), register combos |
| Load | LW, LH, LB, LHU, LBU | 5 | Aligned addresses, all offset ranges |
| Store | SW, SH, SB | 3 | Aligned addresses, byte-enable verification |
| Branch | BEQ, BNE, BLT, BGE, BLTU, BGEU | 6 | Taken + not-taken for each |
| Upper Imm | LUI, AUIPC | 2 | Full range of U-immediates |
| Jump | JAL, JALR | 2 | Forward/backward, link register |
| SYSTEM | ECALL, EBREAK, CSRRW, CSRRS, CSRRC, CSRRWI, CSRRSI, CSRRCI | 8 | (CSR ops tested in T5.4; trap in T5.5) |
| FENCE | FENCE, FENCE.I | 2 | NOP verification |

**Edge Cases:**
- Source register = x0 (should read as 0)
- Destination register = x0 (write should be suppressed)
- Maximum/minimum immediate values
- Shift by 0, by 31
- SLT/SLTU with equal, max positive, max negative operands
- Zero-register operations (ADD x0, x5, x6 — result discarded)

#### T5.2 — Forwarding Tests (`test_forwarding.py`)

**Objective:** Verify all forwarding paths resolve RAW hazards correctly.

**Forwarding Paths Tested:**

| Path ID | Source | Destination | Scenario | Test |
|---------|--------|-------------|----------|------|
| FW-01 | EX/MEM → EX (rs1) | ALU result → ALU input A | ADD→ADD, back-to-back dependency | `addi x5, x1, 5; add x6, x5, x3` |
| FW-02 | EX/MEM → EX (rs2) | ALU result → ALU input B | ADD→ADD using rs2 as operand | `addi x5, x1, 5; add x6, x3, x5` |
| FW-03 | MEM/WB → EX (rs1) | ALU result (2-ago) → ALU input A | ADD→NOP→ADD dependency | `addi x5, x1, 5; nop; add x6, x5, x3` |
| FW-04 | MEM/WB → EX (rs2) | ALU result (2-ago) → ALU input B | ADD→NOP→ADD dependency | `addi x5, x1, 5; nop; add x6, x3, x5` |
| FW-05 | EX/MEM priority | Both EX/MEM and MEM/WB match | ADD→ADD→ADD (same rd) | `addi x5, x1, 5; addi x5, x5, 1; add x6, x5, x3` |
| FW-06 | Forwarding to store | ALU result → store data | ADD→SW dependency | `addi x5, x1, 5; sw x5, 0(x10)` |
| FW-07 | Load forwarding | Load result → ALU input | LW→ADD (after stall) | `lw x5, 0(x10); add x6, x5, x3` |
| FW-08 | x0 suppression | Forwarding suppressed when rd=x0 | Write to x0, read x0 | `addi x0, x1, 5; add x6, x0, x3` |
| FW-09 | Chain of 3 dependencies | Multi-level forwarding | A→B→C→D chain | `addi x5, x1, 1; addi x5, x5, 1; addi x5, x5, 1; add x6, x5, x3` |

**Verification Method:** Execute instruction sequence through Spike GRM. Compare final register values.

#### T5.3 — Hazard Tests (`test_hazards.py`)

**Objective:** Verify load-use stall detection, branch flush, and jump behavior.

**Stall Scenarios:**

| Scenario | Instructions | Expected |
|----------|-------------|----------|
| Load-use (rs1) | `lw x5, 0(x10); add x6, x5, x3` | 1 stall cycle between LW and ADD |
| Load-use (rs2) | `lw x5, 0(x10); add x6, x3, x5` | 1 stall cycle |
| Load-use (both) | `lw x5, 0(x10); add x6, x5, x5` | 1 stall cycle |
| No stall (not dependent) | `lw x5, 0(x10); add x6, x3, x4` | 0 stalls |
| No stall (store-after-load) | `lw x5, 0(x10); sw x5, 0(x11)` | 0 stalls (forwarding handles it) |
| No stall (rd=x0) | `lw x0, 0(x10); add x6, x0, x3` | 0 stalls (x0 always 0) |

**Branch Scenarios:**

| Scenario | Instructions | Expected |
|----------|-------------|----------|
| Branch taken | `beq x5, x5, target` | 2-cycle flush penalty |
| Branch not taken | `bne x5, x5, target` | 0 penalty (sequential) |
| BEQ taken | x5 == x6 | Branch to target |
| BNE taken | x5 != x6 | Branch to target |
| BLT taken | x5 < x6 (signed) | Branch to target |
| BGE taken | x5 >= x6 (signed) | Branch to target |
| BLTU taken | x5 < x6 (unsigned) | Branch to target |
| BGEU taken | x5 >= x6 (unsigned) | Branch to target |

**Jump Scenarios:**

| Scenario | Instructions | Expected |
|----------|-------------|----------|
| JAL forward | `jal x1, target` | PC→target, x1=PC+4 |
| JAL backward | `jal x1, -16` | PC→PC-16, x1=PC+4 |
| JALR aligned | `jalr x1, 0(x5)` | PC→x5, x1=PC+4 |
| JALR LSB cleared | `jalr x1, 5(x5)` where x5=0x1001 | PC→0x1000 (LSB=0) |

**Verification Method:** Verify final register state (PC tracked via JAL link register) matches expected behavior. Branch and jump paths are verified via register/PC state after test.

#### T5.4 — CSR Tests (`test_csr.py`)

**Objective:** Verify all CSR read/write/atomic operations on all 7 implemented CSRs.

**Per-CSR Tests:**

| CSR | Tests |
|-----|-------|
| misa (0x301) | Read value (0x4000_0100), write ignored (RO), all 6 CSR instruction variants |
| mstatus (0x300) | Read/write MIE[3] and MPIE[7]; write to RO bits ignored; all 6 CSR variants |
| mtvec (0x305) | Write BASE[31:2], verify MODE[1:0]=00 only; read back |
| mepc (0x341) | Read/write full value; bits[1:0] always 0 |
| mcause (0x342) | Read/write full value; read back |
| mie (0x304) | Write MTIE[7] and MEIE[11]; other bits RO zero |
| mip (0x344) | Read-only from pins; writes ignored |

**CSR Instruction Variants (per CSR):**
- CSRRW: Read old value, write new
- CSRRS: Read old value, set bits from rs1
- CSRRC: Read old value, clear bits from rs1
- CSRRWI: Read old value, write immediate
- CSRRSI: Read old value, set bits from immediate
- CSRRCI: Read old value, clear bits from immediate
- Atomic RMW: Verify old value returned = pre-operation value

**Edge Cases:**
- CSR instruction with rd=x0 (should still modify CSR)
- CSR instruction with rs1=x0 for CSRRS/CSRRC (no modification)
- Access to unimplemented CSR address → read 0, write ignored

#### T5.5 — Trap Tests (`test_traps.py`)

**Objective:** Verify trap entry and exit sequences.

**Trap Scenarios:**

| Trap | Cause | Test |
|------|-------|------|
| ECALL | mcause=11 | ECALL instruction; verify mepc, mcause, mstatus.MIE |
| EBREAK | mcause=3 | EBREAK instruction |
| Illegal instruction | mcause=2 | 32-bit word with undefined opcode |
| MRET | — | Return from trap handler; verify PC, mstatus restoration |

**Verification Points:**
- `mepc` correctly captures faulting instruction PC
- `mcause` records correct exception code
- `mstatus.MPIE` ← old `mstatus.MIE`
- `mstatus.MIE` ← 0 on trap entry
- PC redirected to `mtvec` value
- MRET: PC ← `mepc`, `mstatus.MIE` ← `mstatus.MPIE`
- Trapping instruction does NOT write back (no RF modification)
- Pipeline flushed on trap entry

#### T5.6 — Pipeline Control Tests (`test_pipeline.py`)

**Objective:** Verify stall, flush, NOP insertion, and reset behavior.

**Scenarios:**

| Test | Description |
|------|-------------|
| Normal flow | Sequential instructions, no hazards — verify all complete correctly |
| Load-use stall | LW followed by dependent ADD — verify stall occurs (CPI>1) |
| Branch flush | Taken branch — verify correct target execution |
| JAL flush | JAL — verify link register + target execution |
| Trap flush | ECALL — verify handler execution |
| Reset sequence | Verify PC at reset vector, CSRs at reset values |
| Stall+flush | Load-use stall coinciding with taken branch — verify correct resolution |
| NOP propagation | Verify NOP instructions don't modify state |

**Verification Method:** Execute sequences through Spike. Verify final register/CSR state matches expected.

#### T5.7 — Random Instruction Tests (`test_random.py`)

**Objective:** Stress test the architecture with random instruction streams.

**Generator Configuration:**
- Instruction types: Weighted distribution (ALU 40%, load 15%, store 10%, branch 15%, jump 5%, CSR 5%, SYSTEM 5%, NOP 5%)
- Register usage: Random selection from x1-x31 (never write x0 as destination)
- Memory: Random addresses within D-MEM range (0x1000-0x1FFF), aligned
- Branch targets: Forward/backward within known code range
- Hazard density: High (70% of instruction pairs have RAW dependencies)
- Run length: 10,000 instructions minimum (configurable)
- Seed: Configurable for reproducibility

**Verification:**
1. Generate random instruction program
2. Compile to ELF
3. Execute through Spike GRM
4. Execute through a second independent Spike invocation with different seed
5. Compare final register file state (both should match)
6. Record instruction counts by type for coverage

**Passing Criteria:** Both Spike invocations produce identical register file state (all 31 writable registers match).

#### T5.8 — Compliance Tests (`test_compliance.py`)

**Objective:** Run official riscv-tests RV32I compliance suite.

**Tests Run:**
```
rv32ui-p-add        rv32ui-p-addi       rv32ui-p-and
rv32ui-p-andi       rv32ui-p-auipc      rv32ui-p-beq
rv32ui-p-bge        rv32ui-p-bgeu       rv32ui-p-blt
rv32ui-p-bltu       rv32ui-p-bne        rv32ui-p-fence_i
rv32ui-p-jal        rv32ui-p-jalr       rv32ui-p-lb
rv32ui-p-lbu        rv32ui-p-lh         rv32ui-p-lhu
rv32ui-p-lui        rv32ui-p-lw         rv32ui-p-ma_data (if applicable)
rv32ui-p-or         rv32ui-p-ori        rv32ui-p-sb
rv32ui-p-sh         rv32ui-p-simple     rv32ui-p-sll
rv32ui-p-slli       rv32ui-p-slt        rv32ui-p-slti
rv32ui-p-sltiu      rv32ui-p-sltu       rv32ui-p-sra
rv32ui-p-srai       rv32ui-p-srl        rv32ui-p-srli
rv32ui-p-sub        rv32ui-p-sw         rv32ui-p-xor
rv32ui-p-xori
```

**Passing Criteria:** All riscv-tests must pass (test passes if it reaches the `pass` signature write: `li a0, 1; sw a0, tohost` or similar exit mechanism).

---

## 4. Coverage Model

### 4.1 Coverage Hierarchy

```
Coverage Model
├── Instruction Coverage (FR-002)
│   ├── R-type ALU: ADD, SUB, SLL, SLT, SLTU, XOR, SRL, SRA, OR, AND
│   ├── I-type ALU: ADDI, SLTI, SLTIU, XORI, ORI, ANDI, SLLI, SRLI, SRAI
│   ├── Load: LW, LH, LB, LHU, LBU
│   ├── Store: SW, SH, SB
│   ├── Branch: BEQ, BNE, BLT, BGE, BLTU, BGEU
│   ├── Upper Imm: LUI, AUIPC
│   ├── Jump: JAL, JALR
│   ├── SYSTEM: ECALL, EBREAK, CSRRW, CSRRS, CSRRC, CSRRWI, CSRRSI, CSRRCI
│   └── FENCE: FENCE, FENCE.I
├── ALU Operation Coverage (FR-003)
│   ├── ADD/SUB, SLL, SLT, SLTU, XOR, SRL, SRA, OR, AND
│   ├── LUI passthrough, AUIPC (PC+imm)
│   └── Branch comparisons (EQ, NE, LT, LTU, GE, GEU)
├── Forwarding Path Coverage (FR-007)
│   ├── EX/MEM→EX (rs1), EX/MEM→EX (rs2)
│   ├── MEM/WB→EX (rs1), MEM/WB→EX (rs2)
│   ├── Forwarding to store data (rs2→MEM)
│   ├── EX/MEM priority over MEM/WB
│   └── x0 forwarding suppression
├── Hazard Coverage (FR-008)
│   ├── Load-use stall triggered (rs1 dependent)
│   ├── Load-use stall triggered (rs2 dependent)
│   ├── Load-use stall NOT triggered (no dependency)
│   ├── Store-after-load (no stall, forwarding)
│   └── x0 dependency (no stall)
├── Branch/Jump Coverage (FR-009)
│   ├── All 6 branch types: taken
│   ├── All 6 branch types: not-taken
│   ├── JAL forward, JAL backward
│   ├── JALR (rs1+imm)
│   └── Pipeline after flush
├── CSR Coverage (FR-010)
│   ├── All 7 CSRs exercised
│   ├── All 6 CSR instruction variants
│   ├── Read-only CSR write ignored
│   ├── CSR atomicity (read-modify-write)
│   └── Unimplemented CSR access
├── Trap Coverage (FR-011)
│   ├── Illegal instruction
│   ├── ECALL
│   ├── EBREAK
│   ├── MRET
│   └── Trap handler execution
├── Pipeline Control Coverage (FR-013)
│   ├── Normal advance (all stages)
│   ├── IF+ID stall (load-use)
│   ├── IF+ID flush (branch taken)
│   ├── IF flush only (JAL/JALR)
│   ├── IF+ID+EX flush (trap)
│   ├── All stages flush (reset)
│   └── Stall+flush simultaneous
└── Register File Coverage (FR-006)
    ├── All 31 writable registers written
    ├── All 32 registers read
    ├── x0 always reads as 0
    ├── x0 write suppressed
    └── Read-after-write (with forwarding)
```

### 4.2 Coverage Targets

| Coverage Group | Target | Measurement |
|---------------|--------|-------------|
| Instruction types | 100% (40/40) | Each unique opcode+funct3+funct7 exercised |
| ALU operations | 100% (14/14) | Each alu_op code exercised |
| Forwarding paths | 100% (4/4 paths + priority) | Each fwd_sel combination hit |
| CSR operations | 100% (7 CSRs × 6 variants) | Each CSR+op combination tested |
| Trap types | 100% (5 types) | Each trap cause exercised |
| Branch types | 100% (6 types × taken/not-taken) | Each branch condition both ways |
| Pipeline events | 100% (stall, flush_if, flush_id, flush_ex, NOP) | Each event triggered |
| Overall functional | ≥ 95% | Combined cross-coverage |

### 4.3 Cross-Coverage Items

| Cross | Description |
|-------|-------------|
| Instruction × Forwarding | Does each instruction type exercise forwarding correctly? |
| Instruction × Hazard | Which instructions trigger load-use stalls? |
| CSR × Instruction Variant | Every CSR with every instruction variant |
| Forwarding × Register | Forwarding from/to all register pairs |
| Pipeline Event × Instruction | Which instructions cause which pipeline events? |

---

## 5. Scoreboard Design

### 5.1 Comparison Architecture

The scoreboard compares **architectural state** (register file, CSR, memory) after each test program execution. Since we are verifying at the architecture level (not RTL cycle-by-cycle), the comparison is end-of-test state comparison.

```
For each test:
  1. Generate test program (assembly or instruction generator)
  2. Compile to RV32I ELF binary
  3. Execute through Spike GRM → capture final state (registers, CSRs, memory)
  4. Execute through DUT (architecture model) → capture final state
  5. Compare:
     a. Register file: all x1-x31 values
     b. CSR state: all 7 implemented CSRs
     c. Memory state: D-MEM region (0x1000-0x1FFF)
     d. x0 invariance: verify x0 reads as 0 in all contexts
  6. Report pass/fail with detailed diffs
```

### 5.2 Scoreboard Class

```python
class Scoreboard:
    def __init__(self, grm: SpikeGRM):
        self.grm = grm
        self.results = []  # List of ScoreboardResult

    def run_test(self, test_name: str, asm_source: str,
                 expected_state: Optional[Dict] = None) -> ScoreboardResult:
        """Run a single test: compile, execute through GRM, compare."""
        ...

    def run_test_elf(self, test_name: str, elf_path: str) -> ScoreboardResult:
        """Run a pre-compiled ELF through GRM and validate."""
        ...

    def compare_states(self, grm_state: GRMState,
                       dut_state: GRMState) -> Tuple[bool, List[str]]:
        """Compare two architectural states. Returns (match, diffs)."""
        ...

    def report(self) -> str:
        """Generate aggregate test report."""
        ...
```

### 5.3 Comparison Rules

1. **x0 always 0:** GRM should report x0=0. DUT must have x0=0. Any deviation is a FAIL.
2. **Unwritten registers:** Registers never written during the test should be 0 (GRM initializes all registers to 0).
3. **CSR reset values:** Before test start, all CSRs should be at reset values. After test, compare all CSRs.
4. **Memory:** Only compare addresses that were written during the test. Memory initialized to 0.
5. **Floating IP:** Allow ±0 difference (integer only, no FP).

---

## 6. Trace Comparison Methodology

### 6.1 Trace Format

Both GRM (Spike) and DUT produce instruction execution traces in a common format:

```
# Format: <pc> <instr_word> <rd> <rd_value> [mem <addr> <value>]
0x80000000 0x00100093  1 0x00000010     # addi x1, x0, 16
0x80000004 0x00200113  2 0x00000020     # addi x2, x0, 32
0x80000008 0x0020a023  mem 0x80001000 0x00000020  # sw x2, 0(x1)
```

### 6.2 Comparison Algorithm

```
1. Parse GRM trace into List[TraceEntry]
2. Parse DUT trace into List[TraceEntry]
3. Align traces by instruction index
4. For each aligned instruction pair:
   a. Compare PC values (allow offset for different memory base)
   b. Compare instruction words (must match exactly)
   c. If register write: compare rd, rd_value (skip if rd=x0)
   d. If store: compare store_addr, store_value
5. Report mismatches
```

### 6.3 Known Trace Differences (Expected)

| Difference | Reason | Handling |
|------------|--------|----------|
| PC base offset | GRM uses 0x80000000; DUT uses 0x00000000 | Normalize by subtracting base before comparison |
| NOP instructions | DUT pipeline may insert NOPs | Skip NOP entries in DUT trace (not present in Spike trace) |
| x0 writes | Spike may report x0 writes; DUT suppresses them | Ignore x0 writes in both traces |

---

## 7. Known Limitations

1. **Architecture-only verification.** No RTL exists yet. We verify the specification, not the implementation. All tests exercise the GRM (Spike) against test programs. True RTL verification occurs in the RTL design stage with cocotb.

2. **Pipeline cycle accuracy.** Spike is a functional simulator, not cycle-accurate. We cannot verify cycle-level pipeline behavior (e.g., exact forwarding timing, stall cycle count). These are verified at the RTL simulation level.

3. **Interrupt timing.** Spike does not model asynchronous interrupt arrival. Interrupt response latency and precise interrupt timing are RTL-level verification concerns.

4. **Gate-level behavior.** No synthesis, no timing. Architecture verification only.

5. **x0 write tracking.** Spike trace may show writes to x0 which the DUT would suppress. The comparison engine must mask x0 writes.

6. **Memory address offset.** Spike's default memory base is 0x80000000. DUT uses 0x00000000. Tests must handle this offset during comparison.

7. **CSR trace capture.** Spike's `-l` log does not directly export CSR write values. CSR verification uses end-of-test state comparison rather than per-instruction trace comparison.

---

## 8. File Inventory

| File | Path | Purpose |
|------|------|---------|
| Verification Architecture | `docs/05_verification/verification_architecture.md` | This document |
| Scoreboard | `verification/env/scoreboard.py` | State comparison engine |
| Coverage Model | `verification/env/coverage.py` | Functional coverage tracker |
| Pipeline Monitor | `verification/env/pipeline_monitor.py` | Hazard analysis of instruction streams |
| Instruction Generator | `verification/env/instruction_generator.py` | Random RV32I instruction generation |
| Trace Compare | `verification/env/trace_compare.py` | Instruction-level trace comparison |
| Instruction Tests | `verification/tests/test_instructions.py` | All 40 RV32I instructions |
| Forwarding Tests | `verification/tests/test_forwarding.py` | All forwarding scenarios |
| Hazard Tests | `verification/tests/test_hazards.py` | Load-use, branch, jump hazards |
| CSR Tests | `verification/tests/test_csr.py` | CSR read/write/atomic |
| Trap Tests | `verification/tests/test_traps.py` | Trap entry/exit |
| Pipeline Tests | `verification/tests/test_pipeline.py` | Pipeline control |
| Random Tests | `verification/tests/test_random.py` | Constrained random stress |
| Compliance Tests | `verification/tests/test_compliance.py` | riscv-tests runner |
| Makefile | `verification/Makefile` | Build and run targets |
| Conftest | `verification/conftest.py` | Shared test fixtures |

---

## 9. Phase 5 Gate Checklist

See `subagent-checklists.md` Phase 5 section.

Self-assessment to be completed after deliverables created.

| # | Item | Status |
|---|------|--------|
| 1 | Testbench architecture defined | ✅ |
| 2 | cocotb environment structure defined | ✅ (adapted for arch-only verification) |
| 3 | Scoreboard architecture defined | ✅ |
| 4 | Functional coverage model defined | ✅ |
| 5 | Per-instruction directed tests planned | ✅ |
| 6 | Constrained-random tests planned | ✅ |
| 7 | Integration tests planned | ✅ |
| 8 | Stress tests planned | ✅ |
| 9 | Normal operation scenarios | ✅ |
| 10 | Error condition scenarios | ✅ |
| 11 | Edge cases | ✅ |
| 12 | Configuration changes during operation | ✅ (CSR changes) |
| 13 | Power cycle / reset recovery | ✅ |
| 14 | FSM state coverage | N/A (no HW FSMs at arch level) |
| 15 | Register coverage | ✅ (all 32 GPRs + 7 CSRs) |
| 16 | Bus transaction coverage | N/A (no bus protocol) |
| 17 | Interrupt coverage | ✅ (where Spike models allow) |
| 18 | Functional coverage defined | ✅ |

---

*Verification architecture specification complete. Proceed to environment + test source implementation.*
