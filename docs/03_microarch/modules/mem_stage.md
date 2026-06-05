# MEM Stage — Memory Access Unit (LSU)

**Module:** `mem_stage`  
**Parent:** IP-001 RV32I 5-Stage Pipeline Core  
**Phase:** 3 — Microarch Designer  
**FR Trace:** FR-004, FR-009 (misaligned trap)  
**Research Ref:** B1(RV32I §2.3:loads/stores), B9(TTP010:LSU), B10(TTP021:byte-enable pattern)  

---

## 1. Functional Description

The MEM stage performs all load and store operations to the data memory interface. It generates byte-enable signals for sub-word stores, sign/zero-extends load data to 32 bits, and detects misaligned memory accesses (trap).

Key functions:
1. **Address generation:** Passes ALU-computed effective address to D-memory
2. **Byte-enable generation:** Produces `d_be[3:0]` for SB/SH/SW based on address[1:0] and access width
3. **Store data alignment:** Prepares write data for sub-word stores (replicates byte to correct lane)
4. **Load data extraction and extension:** Extracts the correct byte/halfword from `d_rdata[31:0]` based on address[1:0] and sign/zero-extends
5. **Misaligned access detection:** Checks alignment for LW/LH/SH/SW; signals trap on misaligned access
6. **Writeback data selection:** Provides `mem_rdata` for the WB stage when this is a load

---

## 2. Port List

| Signal | Direction | Width | Description |
|--------|-----------|-------|-------------|
| `clk` | Input | 1 | 50 MHz system clock |
| `rst_sync_n` | Input | 1 | Synchronous reset (active low) |
| `flush_mem` | Input | 1 | Flush MEM stage (from pipeline control, trap only) |
| `alu_result` | Input | 32 | Effective address from EX/MEM register |
| `rs2_data` | Input | 32 | Store data from EX/MEM register |
| `mem_read` | Input | 1 | Load instruction |
| `mem_write` | Input | 1 | Store instruction |
| `mem_width` | Input | 2 | Access width: 00=byte, 01=halfword, 10=word |
| `mem_sign_ext` | Input | 1 | Sign-extend load: 1=signed, 0=unsigned |
| `rd_addr` | Input | 5 | Destination register |
| `wb_en` | Input | 1 | Writeback enable |
| `wb_src` | Input | 2 | Writeback source |
| `pc` | Input | 32 | PC (pass-through) |
| `csr_rdata` | Input | 32 | CSR read data (pass-through for CSR instructions) |
| `alu_result_out` | Output | 32 | ALU result pass-through (to MEM/WB) |
| `mem_rdata` | Output | 32 | Load data (sign/zero extended, to MEM/WB) |
| `rd_addr_out` | Output | 5 | Destination register (to MEM/WB) |
| `wb_en_out` | Output | 1 | Writeback enable (to MEM/WB) |
| `wb_src_out` | Output | 2 | Writeback source (to MEM/WB) |
| `pc_out` | Output | 32 | PC pass-through (to MEM/WB) |
| `csr_rdata_out` | Output | 32 | CSR read data pass-through (to MEM/WB) |
| `d_addr` | Output | 32 | Data memory address |
| `d_wdata` | Output | 32 | Data memory write data |
| `d_rdata` | Input | 32 | Data memory read data |
| `d_be` | Output | 4 | Byte enable (one-hot per byte lane) |
| `d_we` | Output | 1 | Write enable (1 = store) |
| `misaligned_trap` | Output | 1 | Misaligned access detected |

---

## 3. Internal Block Diagram

```
  alu_result[31:0]
       |
       +-----------> d_addr[31:0] (to D-Memory)
       |
       |        +-----------------------------+
       +------->|  ALIGNMENT CHECK            |
       |        |  LW:   addr[1:0] != 00 → trap|
       |        |  LH:   addr[0]   != 0  → trap|
       |        |  SH:   addr[0]   != 0  → trap|
       |        |  SW:   addr[1:0] != 00 → trap|
       |        |  LB/SB: always aligned       |
       |        +--------------+--------------+
       |                       |
       |              misaligned_trap (to CSR block)
       |
       |        +-----------------------------+
       +------->|  BYTE-ENABLE GEN            |
  mem_width ----+                             |
  alu_result[1:0]--+                          |
                   |  SB: be = 4'b0001 << addr[1:0]
                   |  SH: be = addr[1] ? 4'b1100 : 4'b0011
                   |  SW: be = 4'b1111
                   +--------------+----------+
                                  |
                            d_be[3:0] (to D-Memory)

  rs2_data[31:0] ---+
  (byte replication  |
   for SB/SH)        +-----> d_wdata[31:0] (to D-Memory)

  d_rdata[31:0] --->+----------------------------+
                     | LOAD DATA EXTRACT + EXTEND |
  alu_result[1:0] -->+                            |
  mem_width[1:0] --->+  LB:  byte at addr[1:0]   |
  mem_sign_ext ----->+  LH:  half at addr[1]     |
                     |  LW:  full word            |
                     |  Sign/zero extend → 32b    |
                     +-------------+-------------+
                                   |
                             mem_rdata[31:0] (to MEM/WB)
```

---

## 4. Store Data Alignment

For SB and SH, the store data byte/halfword must be placed at the correct byte lane:

```
SB with addr[1:0] == 00: d_wdata = {24'b0, rs2_data[7:0]}
SB with addr[1:0] == 01: d_wdata = {16'b0, rs2_data[7:0], 8'b0}
SB with addr[1:0] == 10: d_wdata = {8'b0, rs2_data[7:0], 16'b0}
SB with addr[1:0] == 11: d_wdata = {rs2_data[7:0], 24'b0}

SH with addr[1] == 0: d_wdata = {16'b0, rs2_data[15:0]}
SH with addr[1] == 1: d_wdata = {rs2_data[15:0], 16'b0}

SW: d_wdata = rs2_data[31:0]
```

**Alternative approach:** Use byte-enable-aware memory. Store data is replicated across all 4 byte lanes: `d_wdata = {4{rs2_data[7:0]}}` for SB, `d_wdata = {2{rs2_data[15:0]}}` for SH. The byte-enable signals determine which bytes are actually written. This is simpler and standard for SRAM with byte-enable.

---

## 5. Load Data Extraction and Extension

```
Load from d_rdata[31:0], using alu_result[1:0] to select byte/halfword:

LB (mem_width=00, sign_ext=1):
  Byte selected by: alu_result[1:0]
  Raw: selected_byte = d_rdata[alu_result[1:0]*8 +: 8]
  Extended: {{24{selected_byte[7]}}, selected_byte}

LBU (mem_width=00, sign_ext=0):
  Extended: {24'b0, selected_byte}

LH (mem_width=01, sign_ext=1):
  Halfword selected by: alu_result[1]
  Raw: half = d_rdata[alu_result[1]*16 +: 16]
  Extended: {{16{half[15]}}, half}

LHU (mem_width=01, sign_ext=0):
  Extended: {16'b0, half}

LW (mem_width=10):
  mem_rdata = d_rdata[31:0] (full word)

All loads use sign/zero extension to produce 32-bit value.
```

---

## 6. Timing Behavior

- **MEM stage is active for all instructions.** Non-memory instructions pass through with `mem_read=0`, `mem_write=0`, `d_be=0`, `d_we=0`.
- **Load:** `d_addr` valid in MEM stage. `d_rdata` sampled at end of cycle (synchronous memory). `mem_rdata` = sign/zero-extended value, captured in MEM/WB register.
- **Store:** `d_addr`, `d_wdata`, `d_be`, `d_we` all valid in MEM stage. Memory performs write at rising edge.
- **Misaligned trap:** Detected in MEM stage. `misaligned_trap` goes to CSR block, which triggers trap entry and flushes MEM and EX stages.

---

## 7. Interface Contracts

### 7.1 From EX/MEM Pipeline Register
- All inputs come from EX/MEM register. Includes ALU result (effective address), rs2 data (store data), and all control signals.

### 7.2 To D-Memory Interface (IFR-002)
- `d_addr` — effective address (from ALU). Byte-granularity.
- `d_wdata` — store data, byte-replicated for sub-word stores.
- `d_be` — byte enable, one-hot per byte lane.
- `d_we` — write enable, asserted for store instructions.
- `d_rdata` — read data from memory, sampled at cycle end.
- No bus protocol handshake — synchronous memory assumed.

### 7.3 To MEM/WB Pipeline Register
- `alu_result_out` — ALU result (for ALU-type instructions that write back)
- `mem_rdata` — load data (for load instructions that write back)
- `rd_addr_out`, `wb_en_out`, `wb_src_out`, `pc_out`, `csr_rdata_out` — pass-through

### 7.4 To CSR Block
- `misaligned_trap` — asserted when a memory access is misaligned. CSR block captures this as trap cause.

---

## 8. Design Notes and Constraints

1. **Byte-replication for stores:** Store data is replicated across all 4 byte lanes with `d_be` determining actual writes. This simplifies wiring — no need for per-byte-position shifting logic. The backend memory macro uses byte-enable to selectively write.

2. **Synchronous memory model:** One-cycle read: address presented at cycle N, data available at cycle N (for registered-read memory) or captured at N+1 (for next-cycle-read). The IF stage model uses same-cycle read (address at IF clock, data sampled at next edge). The MEM stage should define which timing model is used. Default: address → memory → `d_rdata` available at the same cycle's end (registered output from SRAM macro). If SRAM has 1-cycle read latency, add pipeline stall logic.

3. **`mem_rdata` default:** When `mem_read = 0` (non-load instruction), `mem_rdata = 0`. This is the result for non-loads in the writeback mux.

4. **Simultaneous load + store:** Not possible. `mem_read` and `mem_write` are mutually exclusive per RV32I ISA (no instruction does both).

5. **Gate count estimate:** ~500 GE (sign/zero extension logic ~100 GE, alignment check ~100 GE, byte-enable generation ~100 GE, data muxes ~200 GE).

---

## 9. Research References

| Source | Relevance |
|--------|-----------|
| B1 (RV32I §2.3) | Load/store semantics, alignment requirements |
| B9 (TTP010) | LSU implementation in 5-stage pipeline |
| B10 (TTP021) | Byte-enable pattern, Harvard D-memory interface |
| B3 (encoding table) | Load/store funct3 codes and widths |
| B5 (Roy §5) | Memory interface timing |

---

## 10. Per-Module Gate Checklist

- [ ] Load: LB/LH/LW/LBU/LHU with correct sign/zero extension
- [ ] Store: SB/SH/SW with correct byte-enable
- [ ] Byte-enable: 4'b1111 for SW, 4'b0011/4'b1100 for SH, 4'b0001<<addr[1:0] for SB
- [ ] Store data byte replication
- [ ] Load data correctly extracted from d_rdata based on addr[1:0]
- [ ] Misaligned LW/LH/SH/SW detection → trap
- [ ] LB/LBU/SB always aligned (no trap)
- [ ] d_we=0 for loads, d_we=1 for stores
- [ ] mem_rdata=0 for non-load instructions
- [ ] FR-004 trace confirmed
