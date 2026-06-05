# EX Stage — Execute Unit (ALU + Branch Resolution)

**Module:** `ex_stage`  
**Parent:** IP-001 RV32I 5-Stage Pipeline Core  
**Phase:** 3 — Microarch Designer  
**FR Trace:** FR-003, FR-007, FR-009  
**Research Ref:** B1(RV32I ALU ops), B5(Roy §7:adder), B4(L10:funct7 discrimination), B21(P&H §4.5:ALU design)  

---

## 1. Functional Description

The EX stage performs all arithmetic, logical, and shift operations, evaluates branch conditions, and computes branch/jump effective addresses. It integrates the forwarding muxes on the ALU input operands, allowing results from later pipeline stages (EX/MEM and MEM/WB) to bypass the register file and feed directly into the ALU.

Key functions:
1. **Forwarding muxes:** Select ALU operands from register file data (ID/EX), EX/MEM result, or MEM/WB result based on forwarding unit signals
2. **ALU:** Execute ADD, SUB, SLL, SLT, SLTU, XOR, SRL, SRA, OR, AND, LUI pass-through
3. **Branch condition evaluation:** Compare forwarded operand values for branch decisions
4. **Branch target computation:** `pc + B_immediate` (B-immediate computed in ID stage is passed via ID/EX.imm)
5. **CSR passthrough:** CSR instructions pass through to MEM stage for CSR block access

---

## 2. Port List

| Signal | Direction | Width | Description |
|--------|-----------|-------|-------------|
| `clk` | Input | 1 | 50 MHz system clock |
| `rst_sync_n` | Input | 1 | Synchronous reset (active low) |
| `flush_ex` | Input | 1 | Flush EX stage (from pipeline control) |
| `pc` | Input | 32 | PC of this instruction (from ID/EX) |
| `rs1_data` | Input | 32 | rs1 data from ID/EX register |
| `rs2_data` | Input | 32 | rs2 data from ID/EX register |
| `imm` | Input | 32 | Immediate value from ID/EX register |
| `rd_addr` | Input | 5 | Destination register from ID/EX |
| `alu_op` | Input | 4 | ALU operation code from ID/EX |
| `alu_src_a` | Input | 1 | ALU A source select: 0=rs1, 1=PC |
| `alu_src_b` | Input | 1 | ALU B source select: 0=rs2(forwarded), 1=imm |
| `fwd_a_sel` | Input | 2 | Forwarding mux A select: 00=ID/EX, 01=EX/MEM_fwd, 10=MEM/WB_fwd |
| `fwd_b_sel` | Input | 2 | Forwarding mux B select: 00=ID/EX, 01=EX/MEM_fwd, 10=MEM/WB_fwd |
| `exmem_fwd_data` | Input | 32 | Forwarded data from EX/MEM pipeline register |
| `memwb_fwd_data` | Input | 32 | Forwarded data from MEM/WB pipeline register |
| `branch_op` | Input | 3 | Branch condition select |
| `is_branch` | Input | 1 | This is a conditional branch |
| `is_jal` | Input | 1 | This is JAL |
| `is_jalr` | Input | 1 | This is JALR |
| `is_csr` | Input | 1 | This is a CSR instruction |
| `is_ecall` | Input | 1 | ECALL instruction |
| `is_ebreak` | Input | 1 | EBREAK instruction |
| `is_illegal` | Input | 1 | Illegal instruction flag |
| `csr_op` | Input | 2 | CSR operation |
| `csr_addr` | Input | 12 | CSR address |
| `alu_result` | Output | 32 | ALU result (to EX/MEM register) |
| `branch_taken` | Output | 1 | Branch condition evaluated to TRUE |
| `branch_target` | Output | 32 | Branch target PC (pc + B_imm) |
| `rs2_data_out` | Output | 32 | rs2 data (to EX/MEM, for store data) |
| `rd_addr_out` | Output | 5 | Destination register (to EX/MEM) |
| `pc_out` | Output | 32 | PC pass-through (to EX/MEM) |
| `is_csr_out` | Output | 1 | CSR flag pass-through |
| `is_ecall_out` | Output | 1 | ECALL flag pass-through |
| `is_ebreak_out` | Output | 1 | EBREAK flag pass-through |
| `is_illegal_out` | Output | 1 | Illegal flag pass-through |
| `csr_op_out` | Output | 2 | CSR op pass-through |
| `csr_addr_out` | Output | 12 | CSR addr pass-through |
| `is_jal_out` | Output | 1 | JAL flag pass-through |
| `is_jalr_out` | Output | 1 | JALR flag pass-through |

---

## 3. Internal Block Diagram

```
                              FORWARDING MUX A
  rs1_data[31:0] -------------+
  exmem_fwd_data[31:0] -------+ 3:1 MUX
  memwb_fwd_data[31:0] -------+   |
  fwd_a_sel[1:0] -------------+   |
                                  v
                              operand_a[31:0]

                              FORWARDING MUX B
  rs2_data[31:0] -------------+
  exmem_fwd_data[31:0] -------+ 3:1 MUX
  memwb_fwd_data[31:0] -------+   |
  fwd_b_sel[1:0] -------------+   |
                                  v
                              operand_b[31:0]

                              ALU SRC MUX A
  operand_a[31:0] ------------+
  pc[31:0] -------------------+ 2:1 MUX
  alu_src_a ------------------+   |
                                  v
                              alu_in_a[31:0]

                              ALU SRC MUX B
  operand_b[31:0] ------------+
  imm[31:0] ------------------+ 2:1 MUX
  alu_src_b ------------------+   |
                                  v
                              alu_in_b[31:0]

  +---------------------------------------------------------------+
  |                           ALU                                 |
  |  alu_op[3:0]                                                  |
  |  0000: ADD  = a + b                           +----> alu_result|
  |  0001: SUB  = a - b                                          |
  |  0010: SLL  = a << b[4:0]                                    |
  |  0011: SLT  = ($signed(a) < $signed(b)) ? 1 : 0              |
  |  0100: SLTU = (a < b) ? 1 : 0                                |
  |  0101: XOR  = a ^ b                                          |
  |  0110: SRL  = a >> b[4:0]                                    |
  |  0111: SRA  = $signed(a) >>> b[4:0]                          |
  |  1000: OR   = a | b        +----> branch_taken (to IF ctrl)  |
  |  1001: AND  = a & b                                          |
  |  1010: LUI  = b             +----> branch_target (to IF)     |
  |  1100: BEQ  = (a == b)                                        |
  |  1101: BNE  = (a != b)                                        |
  |  1110: BLT  = ($signed(a) < $signed(b))                      |
  +---------------------------------------------------------------+
```

---

## 4. ALU Operation Details

### 4.1 32-bit Adder/Subtractor
- **ADD (alu_op=0000):** `result = a + b` (unsigned 32-bit, wraps on overflow — RV32I spec)
- **SUB (alu_op=0001):** `result = a - b` (two's complement: a + ~b + 1)
- **Architecture:** Ripple-carry adder (RCA) — 32 stages. Estimated delay: ~7 ns at sky130hd SS/125C. Well within 20 ns.
- **Alternative considered:** Carry-lookahead adder. Rejected — unnecessary at 50 MHz. RCA saves area (~500 GE for 32b RCA vs ~900 GE for CLA).

### 4.2 Logical Operations
- **XOR (0101):** Bitwise XOR. `result = a ^ b`.
- **OR (1000):** Bitwise OR. `result = a | b`.
- **AND (1001):** Bitwise AND. `result = a & b`.
- Single gate delay per bit — negligible timing.

### 4.3 Shift Operations
- **SLL (0010):** Logical left shift. `result = a << b[4:0]`.
- **SRL (0110):** Logical right shift. `result = a >> b[4:0]` (zero-fill).
- **SRA (0111):** Arithmetic right shift. `result = $signed(a) >>> b[4:0]` (sign-fill).
- **Shift amount:** Only lower 5 bits of `b` (operand_b[4:0]) used. RISC-V ISA §2.4.
- **Implementation:** Barrel shifter or cascade of MUX stages recommended. 5 MUX levels = ~5 × 75 ps = 375 ps. Not on critical path.

### 4.4 Set-Less-Than Operations
- **SLT (0011):** `result = ($signed(a) < $signed(b)) ? 1 : 0`. Signed comparison.
- **SLTU (0100):** `result = (a < b) ? 1 : 0`. Unsigned comparison.
- Uses the adder's borrow/carry outputs.

### 4.5 Special Operations
- **LUI (1010):** `result = b` (passthrough — passes the U-immediate through). Used for LUI.
- **AUIPC (uses ADD):** `alu_in_a = pc`, `alu_in_b = imm`. `result = pc + U_immediate`.

---

## 5. Branch Condition Evaluation

### 5.1 Evaluation Logic

| branch_op[2:0] | Condition | Formula | Output |
|----------------|-----------|---------|--------|
| 000 (BEQ) | Equal | `operand_a == operand_b` | `branch_taken = 1` if equal |
| 001 (BNE) | Not equal | `operand_a != operand_b` | `branch_taken = 1` if not equal |
| 010 (BLT) | Less than (signed) | `$signed(operand_a) < $signed(operand_b)` | `branch_taken = 1` if less |
| 011 (BGE) | Greater/equal (signed) | `$signed(operand_a) >= $signed(operand_b)` | `branch_taken = 1` if >= |
| 100 (BLTU) | Less than (unsigned) | `operand_a < operand_b` | `branch_taken = 1` if less |
| 101 (BGEU) | Greater/equal (unsigned) | `operand_a >= operand_b` | `branch_taken = 1` if >= |
| 110 | JAL (unconditional) | Always true | `branch_taken = 1` (always) |
| 111 | JALR (unconditional) | Always true | `branch_taken = 1` (always) |

### 5.2 Branch Target
- `branch_target = pc + imm` (B-immediate or J-immediate already computed in ID, stored in ID/EX.imm)
- For JALR: target = `(rs1_data + I_imm) & ~1`, computed in ID. EX stage just asserts `branch_taken=1`.

### 5.3 Timing Note
- Branch evaluation uses forwarded operand values from EX/MEM or MEM/WB if the operands depend on prior instructions. This is handled by the forwarding muxes automatically — the same forwarded values used for ALU computation are used for branch comparison.

---

## 6. Forwarding Mux Integration

The EX stage receives `fwd_a_sel[1:0]` and `fwd_b_sel[1:0]` from the forwarding unit. These signals select:

| fwd_sel[1:0] | Source | Data |
|-------------|--------|------|
| 00 | ID/EX register | `rs1_data` or `rs2_data` (no forwarding) |
| 01 | EX/MEM pipeline register | `exmem_fwd_data` (ALU result from previous instruction) |
| 10 | MEM/WB pipeline register | `memwb_fwd_data` (ALU or load result from 2 instructions ago) |
| 11 | (reserved) | — |

Forwarding data arrives from:
- `exmem_fwd_data`: The ALU result currently in the EX/MEM pipeline register
- `memwb_fwd_data`: The writeback data currently in the MEM/WB pipeline register (could be ALU or load result)

**Forwarding with x0:** The forwarding unit suppresses forwarding when the destination register is x0 (`rd_addr != 0`). This means `fwd_sel` will be 00 when the producing instruction writes to x0.

---

## 7. Timing Behavior

- **Normal:** ALU computes result based on forwarding mux output operands. Branch condition evaluated. Results captured in EX/MEM register at clock edge.
- **Flush:** When `flush_ex = 1`, the EX/MEM register captures NOP values. ALU and branch evaluation still occur but results are discarded.
- **Single-cycle:** All operations complete in one cycle. No multi-cycle ALU operations.

---

## 8. Interface Contracts

### 8.1 From ID/EX Pipeline Register
- All input signals come from ID/EX. These are held during ID stage stalls.

### 8.2 From Forwarding Unit
- `fwd_a_sel`, `fwd_b_sel` — determined by comparing ID/EX.rs1/rs2 with EX/MEM.rd and MEM/WB.rd.
- `exmem_fwd_data` — wired from EX/MEM.alu_result.
- `memwb_fwd_data` — wired from MEM/WB writeback data (muxed: ALU or mem result).

### 8.3 To EX/MEM Pipeline Register
- `alu_result[31:0]` — ALU computation result
- `rs2_data_out[31:0]` — store data (forwarded rs2 value passed through ALU B forwarding mux)
- `branch_taken`, `branch_target` — to pipeline control (for flush generation)
- Pass-through signals: `pc`, `rd_addr`, control flags, CSR signals

### 8.4 To Pipeline Control (Combinational)
- `branch_taken` — asserted for: taken conditional branch, JAL, JALR
- `branch_target` — next PC address when branch/jump is taken
- `is_ecall`, `is_ebreak`, `is_illegal` — for trap generation

---

## 9. Design Notes and Constraints

1. **Critical path:** Forwarding mux (~150 ps) + ALU 32b adder (~7 ns) + result mux (~75 ps) = ~7.2 ns. Setup time ~200 ps. Total ~7.4 ns. With 20 ns period, slack >12 ns. **Very comfortable.**

2. **Store data forwarding:** `rs2_data_out` is the forwarded `operand_b` (after forwarding mux B). This ensures that store-after-ALU instructions get the correct data without stalling. Store-after-load is handled by the load-use stall mechanism.

3. **No inferred latches:** Default case in ALU mux covers all `alu_op` values. Unused opcodes (1111) produce `alu_result = 0`.

4. **Shift amount masking:** Shift operations mask the shift amount: `b[4:0]`. RV32I spec requirement.

5. **SLT/SLTU implementation:** Uses the 32-bit subtractor's overflow and sign outputs to determine signed/unsigned comparison results. Or: use explicit comparator logic. Either approach is fine at 50 MHz.

6. **ALU writeback data:** `alu_result` is the default writeback source. For loads, the MEM stage overrides writeback data with memory read data. For CSR, the CSR block provides data.

7. **Gate count estimate:** ~2,000 GE (RCA adder ~500 GE + logical ops ~200 GE + barrel shifter ~400 GE + comparators ~300 GE + forwarding muxes ~400 GE + miscellaneous muxes ~200 GE).

---

## 10. Research References

| Source | Relevance |
|--------|-----------|
| B1 (RV32I ISA) | ALU operation semantics, shift amount masking |
| B5 (Roy §7) | Adder architectures (RCA, CLA), shifter design |
| B4 (L10 §1) | funct7 discrimination for ADD/SUB and SRL/SRA |
| B21 (P&H §4.5) | ALU design for 5-stage pipeline, forwarding integration |
| B9 (TTP010) | ALU + forwarding in 5-stage RV32I pipeline |

---

## 11. Per-Module Gate Checklist

- [ ] All 14 ALU operations implemented
- [ ] ADD/SUB discriminated by funct7[5]
- [ ] SRL/SRA discriminated by funct7[5]
- [ ] Shift by b[4:0] only (lower 5 bits)
- [ ] SRA preserves sign bit
- [ ] SLT/SLTU produce 0 or 1
- [ ] LUI passthrough (alu_in_a=0, alu_in_b=imm)
- [ ] AUIPC (alu_in_a=pc, alu_in_b=imm, result=pc+imm)
- [ ] Branch condition evaluation for all 6 branch types
- [ ] Branch target = pc + imm
- [ ] Forwarding muxes on both ALU inputs (A and B)
- [ ] Store data (rs2) passed through forwarding mux B
- [ ] Default case for unused alu_op values
- [ ] FR-003, FR-007, FR-009 trace confirmed
