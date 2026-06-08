// ============================================================================
// IP-001 — RV32I 5-Stage Pipeline Core
// Module: mem_stage — Memory Access: D-mem interface, byte enable, sign extend
// FR Trace: FR-004, FR-009
// Author: Silicon Sage | Date: 2026-06-08
// ============================================================================

module mem_stage (
    input  wire        clk,
    input  wire        rst_sync_n,
    input  wire        flush_mem,
    input  wire [31:0] alu_result,
    input  wire [31:0] rs2_data,
    input  wire [ 4:0] rd_addr,
    input  wire        mem_read,
    input  wire        mem_write,
    input  wire [ 1:0] mem_width,
    input  wire        mem_sign_ext,
    input  wire        wb_en_in,
    input  wire [ 1:0] wb_src,
    input  wire [31:0] pc,
    input  wire        is_jal,
    input  wire        is_jalr,
    // D-memory interface
    output reg  [31:0] d_addr,
    output reg  [31:0] d_wdata,
    output reg  [ 3:0] d_be,
    output reg         d_we,
    input  wire [31:0] d_rdata,
    // Writeback outputs
    output reg  [31:0] alu_result_out,
    output reg  [31:0] mem_rdata,
    output reg  [ 4:0] rd_addr_out,
    output reg         wb_en_out,
    output reg  [ 1:0] wb_src_out,
    output reg  [31:0] pc_out,
    output reg         misaligned_trap,
    // CSR passthrough
    input  wire        is_csr,
    input  wire [31:0] csr_rdata,
    output reg         is_csr_out,
    output reg  [31:0] csr_rdata_out
);

    // ── D-memory address ──
    always @(*) begin
        d_addr = alu_result;
    end

    // ── D-memory write data alignment ──
    always @(*) begin
        case (mem_width)
            2'b00: d_wdata = {4{rs2_data[7:0]}};    // SB: replicate byte to all lanes
            2'b01: d_wdata = {2{rs2_data[15:0]}};   // SH: replicate halfword
            2'b10: d_wdata = rs2_data;               // SW: full word
            default: d_wdata = rs2_data;
        endcase
    end

    // ── D-memory byte enable ──
    always @(*) begin
        case (mem_width)
            2'b00: begin  // Byte
                case (alu_result[1:0])
                    2'b00: d_be = 4'b0001;
                    2'b01: d_be = 4'b0010;
                    2'b10: d_be = 4'b0100;
                    2'b11: d_be = 4'b1000;
                endcase
            end
            2'b01: begin  // Halfword
                case (alu_result[1])
                    1'b0: d_be = 4'b0011;
                    1'b1: d_be = 4'b1100;
                endcase
            end
            2'b10: d_be = 4'b1111;  // Word
            default: d_be = 4'b1111;
        endcase
    end

    // ── D-memory write enable ──
    always @(*) begin
        d_we = mem_write;
    end

    // ── Misaligned access detection ──
    always @(*) begin
        case (mem_width)
            2'b00: misaligned_trap = 1'b0;  // Byte: always aligned
            2'b01: misaligned_trap = alu_result[0];  // Halfword: must be halfword-aligned
            2'b10: misaligned_trap = (alu_result[1:0] != 2'b00);  // Word: must be word-aligned
            default: misaligned_trap = 1'b0;
        endcase
        // Only check when actually doing a memory access
        if (~mem_read && ~mem_write)
            misaligned_trap = 1'b0;
    end

    // ── Load data alignment and sign/zero extension ──
    always @(*) begin
        case (mem_width)
            2'b00: begin  // LB / LBU
                case (alu_result[1:0])
                    2'b00: mem_rdata = {{24{mem_sign_ext & d_rdata[7]}}, d_rdata[7:0]};
                    2'b01: mem_rdata = {{24{mem_sign_ext & d_rdata[15]}}, d_rdata[15:8]};
                    2'b10: mem_rdata = {{24{mem_sign_ext & d_rdata[23]}}, d_rdata[23:16]};
                    2'b11: mem_rdata = {{24{mem_sign_ext & d_rdata[31]}}, d_rdata[31:24]};
                endcase
            end
            2'b01: begin  // LH / LHU
                case (alu_result[1])
                    1'b0: mem_rdata = {{16{mem_sign_ext & d_rdata[15]}}, d_rdata[15:0]};
                    1'b1: mem_rdata = {{16{mem_sign_ext & d_rdata[31]}}, d_rdata[31:16]};
                endcase
            end
            2'b10: mem_rdata = d_rdata;  // LW
            default: mem_rdata = d_rdata;
        endcase
    end

    // ── Passthrough signals to MEM/WB ──
    always @(*) begin
        alu_result_out = alu_result;
        rd_addr_out    = rd_addr;
        wb_en_out      = wb_en_in;
        wb_src_out     = wb_src;
        pc_out         = pc;
        is_csr_out     = is_csr;
        csr_rdata_out  = csr_rdata;
    end

endmodule
