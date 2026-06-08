// ============================================================================
// IP-001 — RV32I 5-Stage Pipeline Core
// Module: wb_stage — Writeback: result mux, RF write-enable, x0 suppression
// FR Trace: FR-005
// Author: Silicon Sage | Date: 2026-06-08
// ============================================================================

module wb_stage (
    input  wire [31:0] alu_result,
    input  wire [31:0] mem_rdata,
    input  wire [31:0] pc,
    input  wire [ 4:0] rd_addr,
    input  wire        wb_en_in,
    input  wire [ 1:0] wb_src,
    input  wire        is_csr,
    input  wire [31:0] csr_rdata,
    output reg  [ 4:0] rf_rd_addr,
    output reg  [31:0] rf_rd_data,
    output reg         rf_we
);

    // ── Writeback data mux ──
    // 00 = ALU result
    // 01 = Memory read data
    // 10 = PC + 4 (JAL/JALR link)
    // 11 = CSR read data
    wire [31:0] wb_data;
    assign wb_data = (wb_src == 2'b00) ? alu_result :
                     (wb_src == 2'b01) ? mem_rdata   :
                     (wb_src == 2'b10) ? (pc + 32'd4) :  // JAL/JALR link: PC+4
                     (wb_src == 2'b11) ? csr_rdata    :
                     alu_result;

    // ── Register file write interface ──
    // x0 write suppression: wb_en already suppressed for x0 in CSR block;
    // double-check here for defense-in-depth
    always_comb begin
        rf_rd_addr = rd_addr;
        rf_rd_data = wb_data;
        rf_we      = wb_en_in && (rd_addr != 5'd0);
    end

endmodule
