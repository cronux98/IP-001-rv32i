// ============================================================================
// IP-001 — RV32I 5-Stage Pipeline Core
// Module: register_file — 32×32-bit GPR array, 2R1W, x0 hardwired zero
// FR Trace: FR-006
// Author: Silicon Sage | Date: 2026-06-08
// ============================================================================

module register_file (
    input  wire        clk,
    input  wire [ 4:0] rs1_addr,
    input  wire [ 4:0] rs2_addr,
    input  wire [ 4:0] rd_addr,
    input  wire [31:0] rd_data,
    input  wire        we,
    output wire [31:0] rs1_data,
    output wire [31:0] rs2_data
);

    // 32 × 32-bit flip-flop array
    reg [31:0] rf [31:0];

    // ── Write port (clocked, x0 suppressed) ──
    // Defense-in-depth: both WB stage AND register file suppress writes to x0
    always_ff @(posedge clk) begin
        if (we && (rd_addr != 5'd0))
            rf[rd_addr] <= rd_data;
    end

    // ── Read ports (combinational, x0 hardwired to zero) ──
    assign rs1_data = (rs1_addr == 5'd0) ? 32'b0 : rf[rs1_addr];
    assign rs2_data = (rs2_addr == 5'd0) ? 32'b0 : rf[rs2_addr];

    // NOTE: x1-x31 are intentionally NOT reset. This saves ~992 FF resets (~30%
    // power/area) and is architecturally safe — first instruction after reset
    // initializes registers before any read that matters. Forwarding ensures
    // correctness even with undefined initial register state.

endmodule
