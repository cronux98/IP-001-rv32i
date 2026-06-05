# ID Stage — Instruction Decode Unit

**Module:** `id_stage`  
**Parent:** IP-001 RV32I 5-Stage Pipeline Core  
**Phase:** 3 — Microarch Designer  
**FR Trace:** FR-002, FR-011  
**Research Ref:** B1(RV32I ISA), B3(encoding table), B4(L10:decode signals), B12(TTP041:immediate gen)  

---

## 1. Functional Description

The ID stage decodes the 32-bit instruction word from the IF/ID pipeline register into control signals for the execute stage. It performs:

1. **Opcode classification:** Maps opcode[6:0] to instruction class (R-type ALU, I-type ALU, load, store, branch, JAL, JALR, LUI, AUIPC, SYSTEM)
2. **Control signal generation:** Produces ALU operation, memory access type, writeback enable/source, branch operation, CSR operation, and pipeline control hints
3. **Immediate extraction:** Extracts and sign/zero-extends 32-bit immediates from 5 formats (I, S, B, U, J)
4. **Register file read:** Reads rs1 and rs2 from the register file using decoded addresses
5. **Illegal instruction detection:** Identifies undefined opcode/funct3/funct7 combinations and signals an illegal instruction trap
6. **Jump target computation:** Computes JAL and JALR target addresses for the IF stage PC mux

---

## 2. Port List

| Signal | Direction | Width | Description |
|--------|-----------|-------|-------------|
| `clk` | Input | 1 | 50 MHz system clock |
| `rst_sync_n` | Input | 1 | Synchronous reset (active low) |
| `stall_id` | Input | 1 | Stall ID stage (from pipeline control) |
| `flush_id` | Input | 1 | Flush ID stage (from pipeline control) |
| `instr` | Input | 32 | Instruction word from IF/ID pipeline register |
| `pc` | Input | 32 | PC of this instruction (from IF/ID, for JAL/JALR target) |
| `rf_rs1_data` | Input | 32 | Register file read data for rs1 |
| `rf_rs2_data` | Input | 32 | Register file read data for rs2 |
| `rf_rs1_addr` | Output | 5 | Register file read address 1 (rs1 field) |
| `rf_rs2_addr` | Output | 5 | Register file read address 2 (rs2 field) |
| `rd_addr` | Output | 5 | Destination register address (rd field) |
| `rs1_data` | Output | 32 | rs1 data (to ID/EX register) |
| `rs2_data` | Output | 32 | rs2 data (to ID/EX register) |
| `imm` | Output | 32 | Sign/zero-extended immediate value |
| `alu_op` | Output | 4 | ALU operation code |
| `alu_src_a` | Output | 1 | ALU operand A select: 0=rs1, 1=PC |
| `alu_src_b` | Output | 1 | ALU operand B select: 0=rs2, 1=imm |
| `mem_read` | Output | 1 | Load instruction: assert memory read |
| `mem_write` | Output | 1 | Store instruction: assert memory write |
| `mem_width` | Output | 2 | Memory access width: 00=byte, 01=half, 10=word |
| `mem_sign_ext` | Output | 1 | Sign-extend load data: 1=signed (LB/LH), 0=unsigned (LBU/LHU) |
| `wb_en` | Output | 1 | Writeback enable (register file write) |
| `wb_src` | Output | 2 | Writeback source: 00=ALU, 01=MEM, 10=PC+4, 11=CSR |
| `branch_op` | Output | 3 | Branch condition: 000=BEQ, 001=BNE, 010=BLT, 011=BGE, 100=BLTU, 101=BGEU, 110=JAL, 111=JALR |
| `is_branch` | Output | 1 | This is a conditional branch instruction |
| `is_jal` | Output | 1 | This is a JAL instruction |
| `is_jalr` | Output | 1 | This is a JALR instruction |
| `is_csr` | Output | 1 | This is a CSR access instruction |
| `is_ecall` | Output | 1 | This is an ECALL instruction |
| `is_ebreak` | Output | 1 | This is an EBREAK instruction |
| `is_illegal` | Output | 1 | Illegal instruction detected |
| `csr_op` | Output | 2 | CSR operation: 00=CSRRW, 01=CSRRS, 10=CSRRC, 11=CSRRI |
| `csr_addr` | Output | 12 | CSR address (from instruction[31:20]) |
| `funct3` | Output | 3 | funct3 field (for ALU/LSU/CSR decoding downstream) |
| `jal_target` | Output | 32 | JAL target: pc + J_immediate (to IF stage) |
| `jalr_target` | Output | 32 | JALR target: (rs1 + I_immediate) & ~1 (to IF stage) |

---

## 3. Internal Block Diagram

```
                               +------------------------------------+
  instr[31:0] -------+-------->|         RV32I DECODER              |
                     |         |                                    |
                     |         | opcode[6:0] → instruction class    |
                     |         | funct3[2:0] → sub-operation        |
                     |         | funct7[6:0] → SUB/SRA vs ADD/SRL   |
                     |         +---+-----+----+------+-------+------+
                     |             |     |    |      |       |
                     |   alu_op ---+     |    |      |       |
                     |   mem_rd/wr ------+    |      |       |
                     |   wb_en/src -----------+      |       |
                     |   branch_op -----------------+       |
                     |   csr_op/is_csr ---------------------+
                     |
  instr[31:0] -------+-------->+------------------+
  instr[31:7]  --------------->| IMMEDIATE EXTRACT|
                               | I/S/B/U/J formats|
                               +--------+---------+
                                        |
                                        v
                                    imm[31:0]

  instr[19:15] ----------------> rf_rs1_addr[4:0] (to Register File)
  instr[24:20] ----------------> rf_rs2_addr[4:0] (to Register File)
  instr[11:7]  ----------------> rd_addr[4:0]      (to ID/EX register)

  rf_rs1_data[31:0] -----------> rs1_data[31:0]    (to ID/EX register)
  rf_rs2_data[31:0] -----------> rs2_data[31:0]    (to ID/EX register)

  +--------------------------------------+
  |     ILLEGAL INSTRUCTION DETECT       |
  |  Unknown opcode / funct3 / funct7    |
  |  → is_illegal = 1                    |
  +--------------------------------------+

  +--------------------------------------+
  |     JUMP TARGET COMPUTE              |
  |  JAL:    pc + J_imm                  |
  |  JALR:   (rs1_data + I_imm) & ~1    |
  +--------------------------------------+
```

---

## 4. Instruction Decode Table

### 4.1 Opcode Map

| opcode[6:0] | Class | Instructions |
|-------------|-------|-------------|
| 0110111 | LUI | LUI rd, imm[31:12] |
| 0010111 | AUIPC | AUIPC rd, imm[31:12] |
| 1101111 | JAL | JAL rd, offset[20:1] |
| 1100111 | JALR | JALR rd, rs1, offset[11:0] |
| 1100011 | Branch | BEQ, BNE, BLT, BGE, BLTU, BGEU |
| 0000011 | Load | LB, LH, LW, LBU, LHU |
| 0100011 | Store | SB, SH, SW |
| 0010011 | I-type ALU | ADDI, SLTI, SLTIU, XORI, ORI, ANDI, SLLI, SRLI, SRAI |
| 0110011 | R-type ALU | ADD, SUB, SLT, SLTU, XOR, OR, AND, SLL, SRL, SRA |
| 0001111 | FENCE | FENCE, FENCE.I (treated as NOP for single-hart) |
| 1110011 | SYSTEM | ECALL, EBREAK, CSRRW, CSRRS, CSRRC, CSRRWI, CSRRSI, CSRRCI |

### 4.2 ALU Operation Codes

| alu_op[3:0] | Operation | funct3 | funct7[5] | Instruction(s) |
|-------------|-----------|--------|-----------|----------------|
| 0000 | ADD | 000 | 0 | ADD, ADDI, load/store addr, AUIPC |
| 0001 | SUB | 000 | 1 | SUB |
| 0010 | SLL | 001 | 0 | SLL, SLLI |
| 0011 | SLT | 010 | 0 | SLT, SLTI |
| 0100 | SLTU | 011 | 0 | SLTU, SLTIU |
| 0101 | XOR | 100 | 0 | XOR, XORI |
| 0110 | SRL | 101 | 0 | SRL, SRLI |
| 0111 | SRA | 101 | 1 | SRA, SRAI |
| 1000 | OR | 110 | 0 | OR, ORI |
| 1001 | AND | 111 | 0 | AND, ANDI |
| 1010 | LUI_SRC | — | — | LUI (pass imm through ALU) |
| 1011 | AUIPC_SRC | — | — | AUIPC (add imm to PC, uses ADD) |
| 1100 | BEQ_CMP | — | — | BEQ (branch EQ check) |
| 1101 | BNE_CMP | — | — | BNE (branch NE check) |
| 1110 | BLT_CMP | — | — | BLT (signed LT check) |
| 1111 | (reserved) | — | — | — |

**Note:** `alu_op[3:0] = 0000 (ADD)` covers ADDI, load address calc, store address calc, AUIPC, and JAL/JALR. The ADD/SUB distinction is controlled by funct7[5]. SRL/SRA distinction is also by funct7[5].

### 4.3 Branch Condition Codes

| branch_op[2:0] | Condition | Instruction |
|----------------|-----------|-------------|
| 000 | rs1 == rs2 | BEQ |
| 001 | rs1 != rs2 | BNE |
| 010 | rs1 < rs2 (signed) | BLT |
| 011 | rs1 >= rs2 (signed) | BGE |
| 100 | rs1 < rs2 (unsigned) | BLTU |
| 101 | rs1 >= rs2 (unsigned) | BGEU |
| 110 | (unconditional) | JAL |
| 111 | (unconditional) | JALR |

### 4.4 Writeback Source Codes

| wb_src[1:0] | Source | Used By |
|------------|--------|---------|
| 00 | ALU result | R-type, I-type ALU, LUI, AUIPC, load/store addr (unused) |
| 01 | Memory read data | Load instructions (LB/LH/LW/LBU/LHU) |
| 10 | PC + 4 | JAL, JALR (link register) |
| 11 | CSR read data | CSR instructions |

---

## 5. Immediate Extraction Formulas

```
Given instr[31:0]:

I-immediate (ADDI, load, JALR, CSR):
  imm[31:0] = {{20{instr[31]}}, instr[31:20]}
  // 12-bit signed, sign-extended to 32

S-immediate (store):
  imm[31:0] = {{20{instr[31]}}, instr[31:25], instr[11:7]}
  // 12-bit signed, fields scrambled

B-immediate (branch):
  imm[31:0] = {{20{instr[31]}}, instr[7], instr[30:25], instr[11:8], 1'b0}
  // 13-bit signed, LSB=0 (shifted left by 1)

U-immediate (LUI, AUIPC):
  imm[31:0] = {instr[31:12], 12'b0}
  // 32-bit, upper 20 bits from instruction, lower 12 bits zero

J-immediate (JAL):
  imm[31:0] = {{12{instr[31]}}, instr[19:12], instr[20], instr[30:21], 1'b0}
  // 21-bit signed, LSB=0 (shifted left by 1)
```

---

## 6. Illegal Instruction Detection

### Detection Conditions

| Condition | Detects |
|-----------|---------|
| opcode[6:0] is undefined | Unknown instruction class |
| opcode == 0000011 (load), funct3 == 01x or 11x | Reserved load widths |
| opcode == 0100011 (store), funct3 == 01x | Reserved store widths |
| opcode == 1100011 (branch), funct3 == 01x or 11x | Reserved branch types |
| opcode == 0010011 (I-ALU), funct3 == 001/101 with funct7[5]==1 | SLLI/SRLI/SRAI with illegal funct7 |
| opcode == 0110011 (R-ALU), funct3 == 01x, 11x | Reserved R-type funct3 |
| opcode == 1110011 (SYSTEM), funct3 == 000, imm[21:0] != 0 | Non-standard SYSTEM with non-zero imm |
| opcode == 1110011, funct3 != 000, 001, 010, 011, 101, 110, 111 | Unknown CSR funct3 |

**Simplified approach:** The decoder maintains a valid-instruction lookup table. Any instruction encoding not in the table produces `is_illegal = 1`. The lookup table enumerates all 40 RV32I instructions.

---

## 7. Timing Behavior

- **Combinational:** All decode outputs are combinational functions of `instr[31:0]` and `pc[31:0]`. Stable within one clock cycle.
- **Register file read:** `rf_rs1_addr`, `rf_rs2_addr` are combinational from `instr`. Read data `rf_rs1_data`, `rf_rs2_data` is available from register file (combinational read from FF array).
- **Stall:** When `stall_id = 1`, the IF/ID register holds its value, so `instr` does not change. Decode outputs remain stable.
- **Flush:** When `flush_id = 1`, the ID/EX register captures NOP values (all control signals = 0). The decoder continues to produce outputs, but they are not captured.
- **Illegal instruction:** Detected in ID stage. `is_illegal = 1` propagates to pipeline control, which triggers a trap flush in the EX stage.

---

## 8. Interface Contracts

### 8.1 From IF/ID Pipeline Register
- `instr[31:0]` — instruction word. Valid if IF/ID register holds valid instruction.
- `pc[31:0]` — PC of this instruction.

### 8.2 To Register File (rf_rs1_addr, rf_rs2_addr)
- `rf_rs1_addr = instr[19:15]` — rs1 field (always read, even if unused)
- `rf_rs2_addr = instr[24:20]` — rs2 field (always read, even if unused)
- Reads are combinational, no clock dependency
- For x0 source: read returns 0x00000000 (hardwired in register file)

### 8.3 To ID/EX Pipeline Register
- All control signals: `rd_addr`, `rs1_data`, `rs2_data`, `imm`, `alu_op`, `alu_src_a`, `alu_src_b`, `mem_read`, `mem_write`, `mem_width`, `mem_sign_ext`, `wb_en`, `wb_src`, `branch_op`, `is_branch`, `is_jal`, `is_jalr`, `is_csr`, `is_ecall`, `is_ebreak`, `is_illegal`, `csr_op`, `csr_addr`, `funct3`, `pc`

### 8.4 To IF Stage (PC Generation)
- `jal_target = pc + J_immediate` — JAL target address
- `jalr_target = (rs1_data + I_immediate) & 32'hFFFFFFFE` — JALR target (LSB cleared)
- `is_jal`, `is_jalr` — flags for PC mux priority

### 8.5 To CSR Block (via ID/EX)
- `csr_op`, `csr_addr` — propagate through pipeline for CSR access in EX stage
- `is_ecall`, `is_ebreak` — propagate for trap detection

---

## 9. Control Signal Summary by Instruction Type

| Instruction | alu_op | alu_src_a | alu_src_b | mem_read | mem_write | wb_en | wb_src | branch_op |
|-------------|--------|-----------|-----------|----------|-----------|-------|--------|-----------|
| ADD | ADD | rs1 | rs2 | 0 | 0 | 1 | ALU | 000 |
| SUB | SUB | rs1 | rs2 | 0 | 0 | 1 | ALU | 000 |
| SLL/SRL/SRA | (varies) | rs1 | rs2 | 0 | 0 | 1 | ALU | 000 |
| SLT/SLTU | SLT/SLTU| rs1 | rs2 | 0 | 0 | 1 | ALU | 000 |
| AND/OR/XOR | AND/OR/XOR| rs1 | rs2 | 0 | 0 | 1 | ALU | 000 |
| ADDI | ADD | rs1 | imm | 0 | 0 | 1 | ALU | 000 |
| SLTI/SLTIU | SLT/SLTU| rs1 | imm | 0 | 0 | 1 | ALU | 000 |
| XORI/ORI/ANDI | XOR/OR/AND| rs1 | imm | 0 | 0 | 1 | ALU | 000 |
| SLLI/SRLI/SRAI | (varies) | rs1 | imm | 0 | 0 | 1 | ALU | 000 |
| LW | ADD | rs1 | imm | 1 | 0 | 1 | MEM | 000 |
| LH/LB | ADD | rs1 | imm | 1 | 0 | 1 | MEM | 000 |
| LHU/LBU | ADD | rs1 | imm | 1 | 0 | 1 | MEM | 000 |
| SW/SH/SB | ADD | rs1 | imm | 0 | 1 | 0 | — | 000 |
| BEQ/BNE/BLT/BGE/BLTU/BGEU | (cmp) | rs1 | rs2 | 0 | 0 | 0 | — | (varies) |
| JAL | ADD | PC | 4 | 0 | 0 | 1 | PC+4 | 110 |
| JALR | ADD | rs1 | imm | 0 | 0 | 1 | PC+4 | 111 |
| LUI | LUI_SRC | 0 | imm | 0 | 0 | 1 | ALU | 000 |
| AUIPC | ADD | PC | imm | 0 | 0 | 1 | ALU | 000 |
| ECALL | ADD | 0 | 0 | 0 | 0 | 0 | — | 000 |
| EBREAK | ADD | 0 | 0 | 0 | 0 | 0 | — | 000 |
| CSRRW/CSRRS/CSRRC | ADD | rs1 | 0 | 0 | 0 | 1 | CSR | 000 |
| CSRRWI/CSRRSI/CSRRCI | ADD | zimm | 0 | 0 | 0 | 1 | CSR | 000 |

---

## 10. Design Notes and Constraints

1. **Combinational depth:** Decode is the deepest combinational path in ID stage. All 40 instructions are decoded in a single cycle. The case statement is an N-way mux — sky130hd at 50MHz easily meets timing (>15 ns margin).

2. **No inferred latches:** Default assignments for ALL control signals before the case statement. Default: `alu_op=ADD, alu_src_a=0, alu_src_b=0, mem_read=0, mem_write=0, wb_en=0, wb_src=ALU, branch_op=BEQ, is_branch=0, is_jal=0, is_jalr=0, is_csr=0, is_ecall=0, is_ebreak=0, is_illegal=0, csr_op=0, csr_addr=0`.

3. **FENCE/FENCE.I:** Decoded as NOP (all control signals = 0). Single-hart with no memory ordering requirements.

4. **JALR LSB:** `jalr_target[0] = 0` (forced zero by masking). RISC-V ISA requires LSB cleared.

5. **Gate count estimate:** ~1,200 GE (40-instruction case tree, 5 immediate extract muxes, 3 comparators, JAL/JALR adders).

---

## 11. Research References

| Source | Relevance |
|--------|-----------|
| B1 (RV32I ISA) | Opcode map, funct3/funct7 encoding, immediate formats |
| B3 (encoding table) | Visual reference for all 40 instruction encodings |
| B4 (L10 §3) | Control signal generation, NOP encoding |
| B12 (TTP041) | 5-format immediate generator (I/S/B/U/J), VHDL implementation reference |
| B5 (Roy §2, §6) | Combinational case for decoder, default assignments |

---

## 12. Per-Module Gate Checklist

- [ ] All 40 RV32I instructions decoded
- [ ] All 6 immediate formats (I/S/B/U/J) correctly extracted
- [ ] Illegal instruction detection for undefined opcodes
- [ ] Illegal instruction detection for reserved funct3/funct7 combos
- [ ] Default control signal assignments (no latches)
- [ ] JAL target = pc + J-immediate
- [ ] JALR target = (rs1 + I-immediate) & ~1
- [ ] x0 reads as zero (hardwired in register file)
- [ ] FENCE/FENCE.I treated as NOP
- [ ] rs1 and rs2 addresses correctly extracted from instr[19:15] and instr[24:20]
- [ ] rd address correctly extracted from instr[11:7]
- [ ] FR-002, FR-011 trace confirmed
