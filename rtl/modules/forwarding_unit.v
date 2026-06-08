// ============================================================================
// IP-001 — RV32I 5-Stage Pipeline Core
// Module: forwarding_unit — RAW hazard resolution via operand forwarding
// FR Trace: FR-007
// Author: Silicon Sage | Date: 2026-06-08
// ============================================================================

module forwarding_unit (
    input  wire [ 4:0] id_ex_rs1_addr,
    input  wire [ 4:0] id_ex_rs2_addr,
    input  wire        ex_mem_wb_en,
    input  wire [ 4:0] ex_mem_rd_addr,
    input  wire [31:0] ex_mem_alu_result,
    input  wire        mem_wb_wb_en,
    input  wire [ 4:0] mem_wb_rd_addr,
    input  wire [31:0] mem_wb_wb_data,
    output reg  [ 1:0] fwd_a_sel,
    output reg  [ 1:0] fwd_b_sel,
    output wire [31:0] exmem_fwd_data,
    output wire [31:0] memwb_fwd_data
);

    // ── Internal match signals ──
    wire ex_fwd_a, ex_fwd_b;
    wire mem_fwd_a, mem_fwd_b;

    // EX/MEM forwarding matches
    assign ex_fwd_a = ex_mem_wb_en
                   && (ex_mem_rd_addr != 5'd0)
                   && (ex_mem_rd_addr == id_ex_rs1_addr);

    assign ex_fwd_b = ex_mem_wb_en
                   && (ex_mem_rd_addr != 5'd0)
                   && (ex_mem_rd_addr == id_ex_rs2_addr);

    // MEM/WB forwarding matches (suppressed when EX/MEM already matches)
    assign mem_fwd_a = mem_wb_wb_en
                    && (mem_wb_rd_addr != 5'd0)
                    && (mem_wb_rd_addr == id_ex_rs1_addr)
                    && ~ex_fwd_a;      // EX/MEM priority

    assign mem_fwd_b = mem_wb_wb_en
                    && (mem_wb_rd_addr != 5'd0)
                    && (mem_wb_rd_addr == id_ex_rs2_addr)
                    && ~ex_fwd_b;      // EX/MEM priority

    // ── Output mux select encoding ──
    // 00 = no forwarding (use ID/EX register data)
    // 01 = forward from EX/MEM (most recent)
    // 10 = forward from MEM/WB (previous)
    always @(*) begin
        fwd_a_sel = ex_fwd_a ? 2'b01 : (mem_fwd_a ? 2'b10 : 2'b00);
        fwd_b_sel = ex_fwd_b ? 2'b01 : (mem_fwd_b ? 2'b10 : 2'b00);
    end

    // ── Forwarding data passthrough (wired directly from pipeline registers) ──
    assign exmem_fwd_data = ex_mem_alu_result;
    assign memwb_fwd_data = mem_wb_wb_data;

endmodule
