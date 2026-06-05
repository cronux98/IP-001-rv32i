# Register File — 32×32-bit General Purpose Registers

**Module:** `register_file`  
**Parent:** IP-001 RV32I 5-Stage Pipeline Core  
**Phase:** 3 — Microarch Designer  
**FR Trace:** FR-006  
**Research Ref:** B5(Roy §5:DPRAM design), B11(TTP029:rotate RF), B12(TTP041:VHDL RF), B16(GAP006:NEORV32 RF options)  

---

## 1. Functional Description

The register file implements 32 general-purpose registers, each 32 bits wide, conforming to the RV32I integer register specification. It provides two combinational read ports (for rs1 and rs2 in the ID stage) and one clocked write port (from the WB stage). Register x0 is hardwired to zero — writes to x0 are ignored, and reads from x0 always return 0x00000000.

**Implementation:** Flip-flop array (32 × 32 DFFs), inferred by synthesis from a Verilog `reg [31:0] rf [0:31]` with proper `always_ff` write and `assign` reads.

---

## 2. Port List

| Signal | Direction | Width | Description |
|--------|-----------|-------|-------------|
| `clk` | Input | 1 | 50 MHz system clock |
| `rs1_addr` | Input | 5 | Read address port 1 (rs1 field from ID stage) |
| `rs2_addr` | Input | 5 | Read address port 2 (rs2 field from ID stage) |
| `rd_addr` | Input | 5 | Write address (rd field from WB stage) |
| `rd_data` | Input | 32 | Write data (from WB stage) |
| `we` | Input | 1 | Write enable (from WB stage, already x0-suppressed) |
| `rs1_data` | Output | 32 | Read data port 1 |
| `rs2_data` | Output | 32 | Read data port 2 |

---

## 3. Internal Block Diagram

```
  we ---------------+
  rd_addr[4:0] -----+----+
                     |    |
  +------------------+    |
  |                       v
  |            +-----------------------+
  |            |   WRITE DECODE        |
  |            |   5→32 one-hot        |
  |            +----------+------------+
  |                       |
  |             wr_sel[31:0] (one-hot, bit 0 suppressed by we logic)
  |                       |
  |     +----+----+----+--+--+----+----+
  |     |    |    |    |  |  |    |    |
  v     v    v    v    v  v  v    v    v
+--+  +--+ +--+ +--+ +--+  +--+ +--+ +--+
|x0|  |x1| |x2| |x3| ...  |x29||x30||x31|
| 0|  |FF| |FF| |FF|      |FF | |FF | |FF |
+--+  +--+ +--+ +--+       +--+ +--+ +--+
  |     |    |    |          |    |    |
  |     +----+----+----+-----+----+    |
  |                     |             |
  |     +---------------+             |
  |     |                             |
  |     v                             v
  |  READ MUX 1                  READ MUX 2
  |  (32:1, rs1_addr)            (32:1, rs2_addr)
  |     |                             |
  |     v                             v
  +--> rs1_data[31:0]           rs2_data[31:0]

  Note: x0 output is ALWAYS 0. The read mux for rs1 and rs2 includes
  a bypass: if addr == 0, output = 0 regardless of stored value.
```

---

## 4. x0 Implementation

Register x0 (index 0) is special:

- **Read:** When `rs1_addr == 5'd0`, `rs1_data = 32'b0`. When `rs2_addr == 5'd0`, `rs2_data = 32'b0`. This is a MUX-level bypass — the flip-flop at index 0 may still store a value, but it is never read.
- **Write:** Write enable to x0 is already suppressed by the WB stage (`rf_we = wb_en && rd_addr != 0`). However, as a defense-in-depth measure, the register file itself also ignores writes to x0 in hardware.

Implementation alternatives:
1. **Hardwire x0 output:** A 2:1 mux at each read port: `addr == 0 ? 32'b0 : rf[addr]`. This is the simplest and most robust approach.
2. **Never write x0 + reset x0 to zero at startup:** Works but depends on initialization. Option 1 is preferred.

---

## 5. Timing Behavior

### 5.1 Read (Combinational)
- `rs1_data` and `rs2_data` are combinational outputs of `rs1_addr` and `rs2_addr` respectively.
- Read latency: MUX propagation delay ≈ 5 gate delays (32:1 mux tree) ≈ ~400 ps at sky130hd.
- No clock involved in reads.

### 5.2 Write (Clocked)
- On the rising edge of `clk`, if `we == 1` and `rd_addr != 0`, write `rd_data` to `rf[rd_addr]`.
- Write happens at the end of the WB stage cycle.
- Read-during-write behavior: If the ID stage reads a register being written in the same cycle (WB), the read returns the OLD value (write hasn't happened yet). This is natural behavior for edge-triggered write. The forwarding unit handles this by forwarding data from MEM/WB before the write occurs.

---

## 6. Interface Contracts

### 6.1 From ID Stage
- `rs1_addr = instr[19:15]` — always valid (even for instructions that don't use rs1, reads are harmless)
- `rs2_addr = instr[24:20]` — always valid

### 6.2 From WB Stage
- `rd_addr` — destination register (0 = x0, write suppressed)
- `rd_data` — result from writeback mux
- `we` — already x0-suppressed by WB stage; RF re-checks for safety

### 6.3 To ID Stage
- `rs1_data`, `rs2_data` — directly to ID stage; also captured in ID/EX pipeline register for forwarding

---

## 7. Design Notes and Constraints

1. **Synthesis approach:** Flip-flop array inferred from:
   ```verilog
   reg [31:0] rf [31:0];
   always_ff @(posedge clk)
       if (we && rd_addr != 5'd0)
           rf[rd_addr] <= rd_data;
   assign rs1_data = (rs1_addr == 5'd0) ? 32'b0 : rf[rs1_addr];
   assign rs2_data = (rs2_addr == 5'd0) ? 32'b0 : rf[rs2_addr];
   ```

2. **No explicit reset:** x1-x31 are undefined at startup. No reset signal toggles 992 FFs (saves power and area). Software must initialize registers before use. This is architecturally safe because: (a) the first instruction after reset initializes registers via LI/ADDI, and (b) forwarding ensures correct operation regardless of RF state.

3. **SRAM macro alternative (NOT used):** OpenRAM single-port 64×32 macro. Rejected for AD-008: adds integration complexity, read-during-write analysis, and lacking reset behavior is problematic for verification.

4. **Gate count estimate:** ~4,000 GE (32 × 32 FFs = 1,024 FFs × ~4 GE/FF). This is the single largest block in the design (~32% of 12.5k GE budget). Acceptable given simplicity and robustness.

5. **Critical path:** Read mux propagation: ~400 ps. Not on any critical path (reads feed into ID stage, which has >15 ns of slack).

---

## 8. Research References

| Source | Relevance |
|--------|-----------|
| B5 (Roy §5) | DPRAM design, read-during-write timing, Verilog inference patterns |
| B11 (TTP029) | Rotate-based register file (alternative approach, small area) |
| B12 (TTP041) | VHDL register file with x0 hardwired zero |
| B16 (GAP006) | NEORV32 REGFILE_HW_RST option — confirms FF array with optional reset |
| B17 (PicoRV32) | x0 bypass mux pattern |

---

## 9. Per-Module Gate Checklist

- [ ] 32 registers × 32 bits = 1024 FFs
- [ ] 2 read ports (combinational)
- [ ] 1 write port (clocked)
- [ ] x0 hardwired: read returns 0, write ignored
- [ ] Double x0 write protection (WB + RF both check)
- [ ] No reset on x1-x31 (documented choice)
- [ ] Read-during-write: returns old value (correct for forwarding)
- [ ] Read ports always active (rs1/rs2 always read)
- [ ] Write on rising clock edge
- [ ] FR-006 trace confirmed
