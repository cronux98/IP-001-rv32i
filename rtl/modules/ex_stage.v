// ============================================================================
// IP-001 — RV32I 5-Stage Pipeline Core
// Module: ex_stage — Execute: ALU, branch eval, forwarding muxes on ALU inputs
// FR Trace: FR-003, FR-007, FR-009
// Author: Silicon Sage | Date: 2026-06-08
// ============================================================================

module ex_stage (
    input  wire        clk,
    input  wire        rst_sync_n,
    input  wire        flush_ex,
    input  wire [31:0] rs1_data_in,
    input  wire [31:0] rs2_data_in,
    input  wire [31:0] imm,
    input  wire [ 3:0] alu_op,
    input  wire        alu_src_a,
    input  wire        alu_src_b,
    input  wire        mem_read,
    input  wire        mem_write,
    input  wire [ 1:0] mem_width,
    input  wire        mem_sign_ext,
    input  wire        wb_en_in,
    input  wire [ 1:0] wb_src,
    input  wire [ 2:0] branch_op,
    input  wire        is_branch,
    input  wire        is_jal,
    input  wire        is_jalr,
    input  wire        is_csr,
    input  wire        is_ecall,
    input  wire        is_ebreak,
    input  wire        is_illegal,
    input  wire        is_mret,
    input  wire [ 1:0] csr_op,
    input  wire [11:0] csr_addr,
    input  wire [31:0] pc,
    input  wire [ 4:0] rd_addr,
    input  wire [ 1:0] fwd_a_sel,
    input  wire [ 1:0] fwd_b_sel,
    input  wire [31:0] exmem_fwd_data,
    input  wire [31:0] memwb_fwd_data,
    output reg  [31:0] alu_result,
    output reg         branch_taken,
    output reg  [31:0] branch_target,
    output reg  [31:0] rs2_data_out,
    output reg  [ 4:0] rd_addr_out,
    output reg         mem_read_out,
    output reg         mem_write_out,
    output reg  [ 1:0] mem_width_out,
    output reg         mem_sign_ext_out,
    output reg         wb_en_out,
    output reg  [ 1:0] wb_src_out,
    output reg         is_ecall_out,
    output reg         is_ebreak_out,
    output reg         is_illegal_out,
    output reg         is_mret_out,
    output reg         is_csr_out,
    output reg  [ 1:0] csr_op_out,
    output reg  [11:0] csr_addr_out,
    output reg  [31:0] pc_out,
    output reg         is_jal_out,
    output reg         is_jalr_out
);

    // ── Forwarding mux for operand A (rs1 / PC) ──
    wire [31:0] operand_a_raw;
    assign operand_a_raw = alu_src_a ? pc : rs1_data_in;

    wire [31:0] operand_a;
    assign operand_a = (fwd_a_sel == 2'b01) ? exmem_fwd_data :
                       (fwd_a_sel == 2'b10) ? memwb_fwd_data :
                       operand_a_raw;

    // ── Forwarding mux for operand B (rs2 / imm) ──
    wire [31:0] operand_b_raw;
    assign operand_b_raw = alu_src_b ? imm : rs2_data_in;

    wire [31:0] operand_b;
    assign operand_b = (fwd_b_sel == 2'b01) ? exmem_fwd_data :
                       (fwd_b_sel == 2'b10) ? memwb_fwd_data :
                       operand_b_raw;

    // ── ALU ──
    always @(*) begin
        case (alu_op)
            // ADD
            4'b0000: alu_result = operand_a + operand_b;
            // SUB
            4'b1000: alu_result = operand_a - operand_b;
            // SLL
            4'b0001: alu_result = operand_a << operand_b[4:0];
            // SLT (signed)
            4'b0010: alu_result = ($signed(operand_a) < $signed(operand_b)) ? 32'd1 : 32'd0;
            // SLTU
            4'b0011: alu_result = (operand_a < operand_b) ? 32'd1 : 32'd0;
            // XOR
            4'b0100: alu_result = operand_a ^ operand_b;
            // SRL
            4'b0101: alu_result = operand_a >> operand_b[4:0];
            // SRA
            4'b1101: alu_result = $signed(operand_a) >>> operand_b[4:0];
            // OR
            4'b0110: alu_result = operand_a | operand_b;
            // AND
            4'b0111: alu_result = operand_a & operand_b;
            // LUI passthrough (operand_b = imm_u)
            4'b1111: alu_result = operand_b;
            default:  alu_result = operand_a + operand_b;
        endcase
    end

    // ── Branch evaluation ──
    always @(*) begin
        if (is_branch) begin
            case (branch_op)
                3'b000: branch_taken = (operand_a == operand_b);           // BEQ
                3'b001: branch_taken = (operand_a != operand_b);           // BNE
                3'b100: branch_taken = ($signed(operand_a) < $signed(operand_b));  // BLT
                3'b101: branch_taken = ($signed(operand_a) >= $signed(operand_b)); // BGE
                3'b110: branch_taken = (operand_a < operand_b);            // BLTU
                3'b111: branch_taken = (operand_a >= operand_b);           // BGEU
                default: branch_taken = 1'b0;
            endcase
        end
        else begin
            branch_taken = 1'b0;
        end
    end

    // ── Branch target (pc + imm) ──
    always @(*) begin
        branch_target = pc + imm;
    end

    // ── Store data forwarding (rs2 gets forwarded for SW/SH/SB) ──
    always @(*) begin
        rs2_data_out = (fwd_b_sel == 2'b01) ? exmem_fwd_data :
                       (fwd_b_sel == 2'b10) ? memwb_fwd_data :
                       rs2_data_in;
    end

    // ── Passthrough signals to EX/MEM ──
    always @(*) begin
        rd_addr_out     = rd_addr;
        mem_read_out    = mem_read;
        mem_write_out   = mem_write;
        mem_width_out   = mem_width;
        mem_sign_ext_out = mem_sign_ext;
        wb_en_out       = wb_en_in;
        wb_src_out      = wb_src;
        is_ecall_out    = is_ecall;
        is_ebreak_out   = is_ebreak;
        is_illegal_out  = is_illegal;
        is_mret_out     = is_mret;
        is_csr_out      = is_csr;
        csr_op_out      = csr_op;
        csr_addr_out    = csr_addr;
        pc_out          = pc;
        is_jal_out      = is_jal;
        is_jalr_out     = is_jalr;
    end

endmodule
