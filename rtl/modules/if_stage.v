// ============================================================================
// IP-001 — RV32I 5-Stage Pipeline Core
// Module: if_stage — Instruction Fetch: PC gen, I-mem addr, PC+4, target mux
// FR Trace: FR-001, FR-009, FR-012
// Author: Silicon Sage | Date: 2026-06-08
// ============================================================================

module if_stage (
    input  wire        clk,
    input  wire        rst_sync_n,
    input  wire        pc_write_en,
    input  wire        flush_if,
    input  wire        branch_taken,
    input  wire [31:0] branch_target,
    input  wire        is_jal,
    input  wire [31:0] jal_target,
    input  wire        is_jalr,
    input  wire [31:0] jalr_target,
    input  wire        trap_taken,
    input  wire [31:0] trap_target,
    input  wire        mret_taken,
    input  wire [31:0] mret_target,
    output reg  [31:0] pc,
    output reg  [31:0] pc_plus4,
    output reg  [31:0] i_addr
);

    // ── Next PC mux (priority: trap > MRET > branch > JALR > JAL > PC+4) ──
    wire [31:0] next_pc;
    assign next_pc = trap_taken   ? trap_target    :
                     mret_taken   ? mret_target    :
                     branch_taken ? branch_target  :
                     is_jalr      ? jalr_target    :
                     is_jal       ? jal_target     :
                     pc_plus4;

    // ── PC register ──
    always_ff @(posedge clk or negedge rst_sync_n) begin
        if (~rst_sync_n) begin
            pc <= 32'h0000_0000;  // Reset vector = 0x00000000
        end
        else if (pc_write_en) begin
            pc <= next_pc;
        end
    end

    // ── PC+4 (combinational) ──
    always_comb begin
        pc_plus4 = pc + 32'd4;
    end

    // ── Instruction memory address (word-aligned) ──
    always_comb begin
        i_addr = pc;
    end

endmodule
