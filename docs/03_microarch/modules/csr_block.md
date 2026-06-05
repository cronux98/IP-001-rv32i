# CSR Block — Machine-Mode CSRs + Trap Handling

**Module:** `csr_block`  
**Parent:** IP-001 RV32I 5-Stage Pipeline Core  
**Phase:** 3 — Microarch Designer  
**FR Trace:** FR-010, FR-011, IFR-004  
**Research Ref:** B2(Privileged Spec §2.1-2.2, §3.1), B11(TTP029:CSR+trap), B4(L10:CSR decode), B14(riscv-tests:CSR tests)  

---

## 1. Functional Description

The CSR block implements 7 machine-mode Control and Status Registers (CSRs) and the trap handling logic for IP-001. It processes CSR read/write instructions, manages trap entry and exit (MRET), and provides interrupt input gating.

Key functions:
1. **CSR registers:** Store and manage misa, mstatus, mtvec, mepc, mcause, mie, mip
2. **CSR instruction processing:** Execute CSRRW, CSRRS, CSRRC, CSRRWI, CSRRSI, CSRRCI
3. **Trap entry:** On exception or interrupt, save context to CSRs and redirect PC to trap handler
4. **Trap exit (MRET):** Restore PC from mepc, restore MIE from MPIE
5. **Interrupt gating:** Route external interrupt inputs to mip bits; gate with mie and mstatus.MIE

---

## 2. Port List

| Signal | Direction | Width | Description |
|--------|-----------|-------|-------------|
| `clk` | Input | 1 | 50 MHz system clock |
| `rst_sync_n` | Input | 1 | Synchronous reset (active low) |
| `csr_op` | Input | 2 | CSR operation: 00=CSRRW, 01=CSRRS, 10=CSRRC, 11=CSRRI |
| `csr_addr` | Input | 12 | CSR address from instruction[31:20] |
| `rs1_data` | Input | 32 | Source register data (or zimm for immediate variants) |
| `rd_addr` | Input | 5 | Destination register (for csr_rdata output) |
| `wb_en_in` | Input | 1 | Writeback enable from pipeline |
| `is_ecall` | Input | 1 | ECALL instruction in EX |
| `is_ebreak` | Input | 1 | EBREAK instruction in EX |
| `is_illegal` | Input | 1 | Illegal instruction detected |
| `misaligned_trap` | Input | 1 | Misaligned memory access (from MEM stage) |
| `pc_current` | Input | 32 | PC of current instruction in EX (for mepc save) |
| `irq_timer` | Input | 1 | Machine timer interrupt (external pin → mip.MTIP) |
| `irq_external` | Input | 1 | Machine external interrupt (external pin → mip.MEIP) |
| `mstatus_mie` | Input | 1 | Current mstatus.MIE (for interrupt gating) |
| `csr_rdata` | Output | 32 | CSR read data (to WB stage) |
| `wb_en_out` | Output | 1 | Writeback enable to MEM/WB |
| `trap_taken` | Output | 1 | Trap entry active (to IF stage PC mux) |
| `trap_target` | Output | 32 | Trap handler address (mtvec) |
| `mret_taken` | Output | 1 | MRET active (to IF stage PC mux) |
| `mret_target` | Output | 32 | MRET return address (mepc) |
| `flush_pipeline` | Output | 1 | Flush pipeline on trap/MRET |

---

## 3. Internal Block Diagram

```
  +----------------------------------------------------------------+
  |                        CSR BLOCK                                |
  |                                                                |
  |  CSR ADDRESS DECODE                                            |
  |  csr_addr[11:0] ──> 0x300: mstatus                            |
  |                      0x301: misa                                |
  |                      0x304: mie                                 |
  |                      0x305: mtvec                               |
  |                      0x341: mepc                                |
  |                      0x342: mcause                              |
  |                      0x344: mip                                 |
  |                      other: read=0, write=ignored              |
  +----------------------------------------------------------------+
       |                |                |                |
       v                v                v                v
  +---------+    +---------+    +---------+    +---------+
  | mstatus |    |  misa   |    |  mtvec  |    |  mepc   |
  |  [7]MPIE|    | RO:     |    | BASE[31:2]   | [31:0]  |
  |  [3]MIE |    | 0x4000  |    | MODE[1:0]    |         |
  |         |    |  0100   |    |         |    |         |
  +---------+    +---------+    +---------+    +---------+

  +---------+    +---------+    +---------+
  | mcause  |    |   mie   |    |   mip   |
  | [31]Int |    | [7]MTIE |    | [7]MTIP |
  | [30:0]Ex|    | [11]MEIE|    | [11]MEIP|
  +---------+    +---------+    +---------+
       ^              ^              ^
       |              |              |
  trap_cause    csr_write       irq_timer
                                   irq_external

  +----------------------------------------------------------------+
  |                    CSR WRITE LOGIC                              |
  |   CSRRW:  CSR_new = rs1                                       |
  |   CSRRS:  CSR_new = CSR_old | rs1                              |
  |   CSRRC:  CSR_new = CSR_old & ~rs1                             |
  |   CSRRWI: CSR_new = zimm (rs1_addr zero-extended)              |
  |   CSRRSI: CSR_new = CSR_old | zimm                             |
  |   CSRRCI: CSR_new = CSR_old & ~zimm                            |
  |   Read:   csr_rdata = CSR_old                                  |
  |   RO CSR (misa): write ignored                                 |
  |   RO fields (mip): external interrupts only, SW writes ignored  |
  +----------------------------------------------------------------+

  +----------------------------------------------------------------+
  |                    TRAP ENTRY LOGIC                             |
  |   On: is_illegal, is_ecall, is_ebreak, misaligned_trap,       |
  |       (irq_timer && mie.MTIE && mstatus.MIE),                  |
  |       (irq_external && mie.MEIE && mstatus.MIE)                |
  |                                                                |
  |   Actions:                                                     |
  |   1. mepc     ← pc_current (faulting instruction PC)            |
  |   2. mcause   ← trap cause code                               |
  |   3. mstatus.MPIE ← mstatus.MIE                                |
  |   4. mstatus.MIE ← 0                                          |
  |   5. PC       → mtvec                                         |
  |   6. flush_pipeline = 1                                       |
  +----------------------------------------------------------------+

  +----------------------------------------------------------------+
  |                    MRET LOGIC                                   |
  |   On: CSR instruction with addr=0x341 (mepc) and op != read    |
  |        (MRET is actually a separate opcode detection needed)    |
  |                                                                |
  |   Actions:                                                     |
  |   1. PC       → mepc (restore program counter)                 |
  |   2. mstatus.MIE ← mstatus.MPIE                                |
  |   3. mstatus.MPIE ← 1 (or 0 per spec)                         |
  |   4. flush_pipeline = 1                                       |
  +----------------------------------------------------------------+
```

---

## 4. CSR Register Specifications

### 4.1 misa (0x301) — Machine ISA Register (Read-Only)

| Bits | Field | Value | Description |
|------|-------|-------|-------------|
| [31:30] | MXL | 2'b01 | XLEN = 32 (RV32) |
| [25:0] | Extensions | 26'b0 | No extensions (RV32I only) |
| Others | — | 0 | Reserved |

**Reset value:** 0x4000_0100  
**Access:** Read-only. Writes are ignored.

### 4.2 mstatus (0x300) — Machine Status Register

| Bits | Field | Reset | Description |
|------|-------|-------|-------------|
| [7] | MPIE | 0 | Machine Previous Interrupt Enable |
| [3] | MIE | 0 | Machine Interrupt Enable |
| Others | — | 0 | Not implemented (no MPP in M-mode only) |

**Reset value:** 0x0000_1800 (per Privileged Spec: MIE=0, MPIE=0, but SD=1 erroneously in some versions. We use 0x0000_1800 per spec convention.)
**Actual implemented reset:** 0x0000_0000 (MIE=0, MPIE=0, all others 0).  
**Access:** Bits [7] and [3] are read/write. All other bits hardwired to 0 (read-only zero).  
**Field interactions:**
- Trap entry: `MPIE ← MIE`, then `MIE ← 0`
- MRET: `MIE ← MPIE`, then `MPIE ← 1` (or 0 — spec says implementation-defined; we set to 1)

### 4.3 mtvec (0x305) — Machine Trap Vector Base Address

| Bits | Field | Reset | Description |
|------|-------|-------|-------------|
| [31:2] | BASE | 0 | Trap handler base address (4-byte aligned) |
| [1:0] | MODE | 0 | 00=Direct (all traps to BASE), 01=Vectored (not implemented) |

**Reset value:** 0x0000_0000  
**Access:** Read/Write. MODE field: only 00 (Direct) supported. Writes to MODE=01 (Vectored) are ignored — MODE stays 00.

### 4.4 mepc (0x341) — Machine Exception Program Counter

| Bits | Field | Reset | Description |
|------|-------|-------|-------------|
| [31:0] | PC | 0 | Faulting instruction PC, saved on trap entry |

**Reset value:** 0x0000_0000  
**Access:** Read/Write. Bit [1:0] always read as 0 (word-aligned). Writes to bits [1:0] are ignored.

### 4.5 mcause (0x342) — Machine Cause Register

| Bits | Field | Reset | Description |
|------|-------|-------|-------------|
| [31] | Interrupt | 0 | 1 = interrupt, 0 = exception |
| [30:0] | Exception Code | 0 | Trap cause code |

**Reset value:** 0x0000_0000  
**Access:** Read/Write.

### 4.6 mie (0x304) — Machine Interrupt Enable

| Bits | Field | Reset | Description |
|------|-------|-------|-------------|
| [11] | MEIE | 0 | Machine External Interrupt Enable |
| [7] | MTIE | 0 | Machine Timer Interrupt Enable |
| Others | — | 0 | Not implemented |

**Reset value:** 0x0000_0000  
**Access:** Read/Write. Only bits [11] and [7] are writable; others read as zero.

### 4.7 mip (0x344) — Machine Interrupt Pending

| Bits | Field | Source | Description |
|------|-------|--------|-------------|
| [11] | MEIP | irq_external pin | Machine External Interrupt Pending |
| [7] | MTIP | irq_timer pin | Machine Timer Interrupt Pending |
| Others | — | 0 | Not implemented |

**Reset value:** 0x0000_0000  
**Access:** Read-only from software perspective. Bits are driven by external interrupt input pins. Writes from CSR instructions are ignored (RO bits). Timer/external interrupts are level-sensitive — held until cleared by external hardware or handler actions.

---

## 5. Trap Cause Codes

| mcause[31] | mcause[30:0] | Description | Source |
|------------|-------------|-------------|--------|
| 0 | 2 | Illegal instruction | `is_illegal` from ID stage |
| 0 | 3 | Breakpoint | `is_ebreak` |
| 0 | 4 | Misaligned load address | `misaligned_trap` + `mem_read` |
| 0 | 6 | Misaligned store address | `misaligned_trap` + `mem_write` |
| 0 | 11 | Environment call from M-mode | `is_ecall` |
| 1 | 7 | Machine timer interrupt | `irq_timer && mie[7] && mstatus[3]` |
| 1 | 11 | Machine external interrupt | `irq_external && mie[11] && mstatus[3]` |

---

## 6. Trap Entry Sequence (Hardware FSM)

```
  State: TRAP_DETECT
    Condition: any trap source active
    Actions (in THIS cycle, combinational):
      1. mepc_next     = pc_current    // Save faulting PC
      2. mcause_next   = {is_interrupt, cause_code}  // Set cause
      3. mstatus_next  = {mstatus[31:8], mstatus[3], mstatus[4:4], 1'b0, mstatus[2:0]}
                          // MPIE ← MIE, MIE ← 0
      4. trap_taken    = 1              // Signal IF stage PC mux
      5. trap_target   = {mtvec[31:2], 2'b00}  // mtvec.BASE, word-aligned
      6. flush_pipeline = 1             // Flush IF, ID, EX stages
      7. wb_en_out     = 0              // Suppress WB of trapping instruction

  State: TRAP_COMMIT (next cycle, on clock edge)
    - mepc, mcause, mstatus updated from _next values
    - trap_taken deasserted (pulse for one cycle)
    - flush_pipeline deasserted
    - Pipeline refills from mtvec
```

**Note:** `wb_en_out = 0` ensures the trapping instruction does NOT write back to the register file. The exception is precise — all instructions before the trap have completed, none after have started. The trapping instruction itself is squashed.

---

## 7. MRET Operation

```
  MRET detection:
    - CSR instruction targeting mepc (0x341) with write operation
    - OR: explicit MRET opcode (funct3=000, rs1/rd=x0, csr_addr=0x341)
    - Simplification: Any CSR write to address 0x341 with specific encoding
      triggers MRET.

  MRET sequence:
    1. mret_taken    = 1
    2. mret_target   = {mepc[31:2], 2'b00}  // Word-aligned
    3. mstatus_next  = {mstatus[31:8], 1'b1, mstatus[6:4], mstatus[7], mstatus[2:0]}
                         // MIE ← MPIE, MPIE ← 1
    4. flush_pipeline = 1
    5. wb_en_out     = 0              // MRET doesn't write to rd

  On next clock edge:
    - mstatus updated
    - mret_taken deasserted
    - PC → mepc
    - Pipeline refills from mepc
```

**RISC-V MRET encoding:** MRET is `funct3=000, rs1=x0, rd=x0, csr_addr=0x341, op=CSRRW` but this is actually a separate instruction encoding — SYSTEM opcode (1110011), funct3=000 (privileged), funct12=001100000010 (MRET). In hardware: detect the 12-bit immediate field `0x302` at the SYSTEM opcode.

Simpler approach: Detect MRET as `instr[31:0] == 32'h30200073`. This is the standard MRET encoding.

---

## 8. CSR Instruction Processing

### 8.1 Read Phase (Combinational)
- `csr_rdata` is combinational output based on `csr_addr`
- Unknown/unsupported CSR addresses return 0

### 8.2 Write Phase (Clocked)
- On rising edge of `clk`, if CSR instruction in EX (is_csr=1):
  - Read old CSR value → `csr_rdata` (for WB)
  - Compute new CSR value based on `csr_op`
  - Write new value to CSR register
  - For RO CSRs (misa): ignore write, keep old value
  - For RO fields within RW CSRs: mask writes to those fields

### 8.3 Operation Details

| csr_op[1:0] | Operation | New CSR Value | WB Data |
|-------------|-----------|---------------|---------|
| 00 (CSRRW) | Read/Write | `rs1_data` (if rd != x0) | old CSR |
| 01 (CSRRS) | Read/Set | `csr_old | rs1_data` (if rs1 != x0) | old CSR |
| 10 (CSRRC) | Read/Clear | `csr_old & ~rs1_data` (if rs1 != x0) | old CSR |
| 11 (CSRRI) | Read/Set Imm | `csr_old | zimm` | old CSR |
| (CSRRWI) | Read/Write Imm | `zimm` | old CSR |
| (CSRRCI) | Read/Clear Imm | `csr_old & ~zimm` | old CSR |

**Note:** CSRRWI/CSRRSI/CSRRCI are encoded with csr_op=11 (same funct3 field). The distinction between CSRRWI (funct3=101) and CSRRSI/CSRRCI (funct3=110/111) is made by the funct3 from the decoder, not the 2-bit csr_op. Actually, the funct3 directly encodes: 001=CSRRW, 010=CSRRS, 011=CSRRC, 101=CSRRWI, 110=CSRRSI, 111=CSRRCI. The csr_op needs 3 bits to cover all cases. We pass funct3 through as a 3-bit csr_op.

**Correction:** `csr_op` should be 3 bits (funct3), not 2 bits as specified in earlier module specs. This will be corrected in ID stage.

---

## 9. Interrupt Handling

### 9.1 Interrupt Input Sampling
- `irq_timer` and `irq_external` are sampled on every clock cycle
- Sampled values reflected in mip.MTIP and mip.MEIP (combinational or registered — registered preferred for timing)
- Interrupts are level-sensitive: the handler must clear the interrupt source

### 9.2 Interrupt Gating
```
  irq_pending = (irq_timer  && mie.MTIE) || (irq_external && mie.MEIE)
  irq_taken   = irq_pending && mstatus.MIE
```

### 9.3 Interrupt vs Exception Priority
When multiple trap sources are active simultaneously:
1. External interrupt (highest)
2. Timer interrupt
3. Illegal instruction
4. EBREAK
5. ECALL
6. Misaligned access

Exceptions within the same class (e.g., illegal + misaligned in same instruction) are prioritized by pipeline stage: ID exceptions (illegal, ECALL, EBREAK) before MEM exceptions (misaligned).

---

## 10. Timing Behavior

- **CSR read:** Combinational. `csr_rdata` available in same cycle as `csr_addr`. Used for writeback.
- **CSR write:** Clocked. On rising edge, if CSR instruction, write new value.
- **Trap entry:** Combinational detection + immediate PC redirect. `trap_taken` pulsed for one cycle. CSR values updated on next rising edge.
- **MRET:** Same as trap entry but restores from mepc.

**Important:** When a trap occurs, the trapping instruction in EX must NOT write to CSRs (WB suppression). The CSR write from the trap entry itself (mepc/mcause/mstatus update) happens on the NEXT clock edge after trap detection.

---

## 11. Interface Contracts

### 11.1 From Pipeline (via ID/EX, EX/MEM)
- CSR operation signals from decoded instruction
- `pc_current` = PC of instruction in EX stage
- Trap flags: `is_ecall`, `is_ebreak`, `is_illegal`, `misaligned_trap`

### 11.2 To IF Stage (PC Control)
- `trap_taken`, `trap_target` — for trap entry redirection
- `mret_taken`, `mret_target` — for MRET redirection

### 11.3 To WB Stage
- `csr_rdata` — old CSR value for writeback to rd
- `wb_en_out` — 0 for traps and MRET, passes through `wb_en_in` otherwise

---

## 12. Design Notes and Constraints

1. **Read-only fields:** misa is entirely RO. mstatus bits other than [7:3] are RO zero. mip bits are RO (hardware-driven). Writes to RO fields are silently ignored.

2. **CSR write enable:** Writes only occur when a valid CSR instruction is in the pipeline and not being flushed. `is_csr` signal gates writes.

3. **Trap during CSR instruction:** If a CSR instruction itself causes a trap (e.g., illegal instruction), the CSR is NOT written. Trap takes priority.

4. **MRET detection:** Detect via instruction encoding `0x30200073` at the SYSTEM opcode/funct3=000 path. MRET is NOT a CSR instruction — it does NOT write to rd, does NOT read/write mepc as a normal CSR access (it uses mepc for PC restore, not CSR read).

5. **Gate count estimate:** ~1,200 GE (7 × 32b registers = 224 FFs ≈ 900 GE + decode logic ≈ 200 GE + trap FSM ≈ 100 GE).

---

## 13. Research References

| Source | Relevance |
|--------|-----------|
| B2 (Privileged Spec) | CSR addresses, fields, reset values, trap entry/exit sequences |
| B11 (TTP029) | Full machine-mode CSR implementation on TinyQV |
| B4 (L10 §1) | CSR decode and operation types |
| B14 (riscv-tests) | CSR test coverage requirements |

---

## 14. Per-Module Gate Checklist

- [ ] 7 CSRs implemented with correct addresses
- [ ] misa read-only, reset = 0x4000_0100
- [ ] mstatus: MIE[3], MPIE[7]; all other bits RO zero
- [ ] mtvec: BASE[31:2], MODE[1:0] (direct only)
- [ ] mepc: captures PC on trap, bit[1:0]=0
- [ ] mcause: Interrupt[31], Exception Code[30:0]
- [ ] mie: MTIE[7], MEIE[11]; others RO zero
- [ ] mip: driven by irq_timer/irq_external pins; RO from SW
- [ ] 6 CSR instruction variants supported
- [ ] RO fields ignore writes
- [ ] Trap entry: save mepc/mcause, update mstatus, redirect PC
- [ ] MRET: restore PC from mepc, restore MIE from MPIE
- [ ] WB suppressed on trap entry
- [ ] Interrupt gating: mip & mie & mstatus.MIE
- [ ] FR-010, FR-011, IFR-004 trace confirmed
