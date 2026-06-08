// ============================================================================
// IP-001 — RV32I 5-Stage Pipeline Core
// Module: id_stage — Instruction Decode: RV32I decoder, immediate extract, RF read
// FR Trace: FR-002, FR-011
// Author: Silicon Sage | Date: 2026-06-08
// ============================================================================

module id_stage (
    input  wire        clk,
    input  wire        rst_sync_n,
    input  wire [31:0] instr,
    input  wire [31:0] pc,
    input  wire [31:0] rf_rs1_data,
    input  wire [31:0] rf_rs2_data,
    output reg  [ 4:0] rf_rs1_addr,
    output reg  [ 4:0] rf_rs2_addr,
    output reg  [ 4:0] rd_addr,
    output reg  [31:0] imm,
    output reg  [ 3:0] alu_op,
    output reg         alu_src_a,
    output reg         alu_src_b,
    output reg         mem_read,
    output reg         mem_write,
    output reg  [ 1:0] mem_width,
    output reg         mem_sign_ext,
    output reg         wb_en,
    output reg  [ 1:0] wb_src,
    output reg  [ 2:0] branch_op,
    output reg         is_branch,
    output reg         is_jal,
    output reg         is_jalr,
    output reg         is_csr,
    output reg         is_ecall,
    output reg         is_ebreak,
    output reg         is_illegal,
    output reg         is_mret,
    output reg  [ 1:0] csr_op,
    output reg  [11:0] csr_addr,
    output reg  [ 2:0] funct3,
    output reg  [31:0] jal_target,
    output reg  [31:0] jalr_target
);

    // ── Instruction field extraction ──
    wire [6:0] opcode;
    wire [2:0] funct3_in;
    wire [6:0] funct7;
    wire [4:0] rs1, rs2, rd;

    assign opcode   = instr[6:0];
    assign rd       = instr[11:7];
    assign funct3_in = instr[14:12];
    assign rs1      = instr[19:15];
    assign rs2      = instr[24:20];
    assign funct7   = instr[31:25];

    // ── Immediate generation (I, S, B, U, J types) ──
    wire [31:0] imm_i, imm_s, imm_b, imm_u, imm_j;
    assign imm_i = {{21{instr[31]}}, instr[30:20]};
    assign imm_s = {{21{instr[31]}}, instr[30:25], instr[11:7]};
    assign imm_b = {{20{instr[31]}}, instr[7], instr[30:25], instr[11:8], 1'b0};
    assign imm_u = {instr[31:12], 12'b0};
    assign imm_j = {{12{instr[31]}}, instr[19:12], instr[20], instr[30:21], 1'b0};

    // ── Decode helper signals ──
    wire is_alu_reg, is_alu_imm, is_load, is_store;
    wire is_branch_instr, is_jal_instr, is_jalr_instr;
    wire is_lui, is_auipc;
    wire is_csr_instr;
    wire is_system;

    // ── Opcode decode ──
    assign is_alu_reg     = (opcode == 7'b0110011);  // OP
    assign is_alu_imm     = (opcode == 7'b0010011);  // OP-IMM
    assign is_load        = (opcode == 7'b0000011);  // LOAD
    assign is_store       = (opcode == 7'b0100011);  // STORE
    assign is_branch_instr = (opcode == 7'b1100011); // BRANCH
    assign is_jal_instr   = (opcode == 7'b1101111);  // JAL
    assign is_jalr_instr  = (opcode == 7'b1100111);  // JALR
    assign is_lui         = (opcode == 7'b0110111);  // LUI
    assign is_auipc       = (opcode == 7'b0010111);  // AUIPC
    assign is_csr_instr   = (opcode == 7'b1110011);  // SYSTEM
    assign is_system      = (opcode == 7'b1110011);

    // ── Register file addresses ──
    always @(*) begin
        rf_rs1_addr = rs1;
        rf_rs2_addr = rs2;
        rd_addr     = rd;
    end

    // NOTE: rs1_data / rs2_data passthrough REMOVED — was a combinational
    // loop because the top module wired id_stage.rs1_data back onto the same
    // net as register_file.rs1_data. The register file directly drives the
    // ID/EX pipeline register capture; no id_stage passthrough is needed.

    // ── Immediate selection ──
    always @(*) begin
        case (1'b1)
            is_alu_imm:  imm = imm_i;
            is_load:     imm = imm_i;
            is_jalr_instr: imm = imm_i;
            is_store:    imm = imm_s;
            is_branch_instr: imm = imm_b;
            is_lui:      imm = imm_u;
            is_auipc:    imm = imm_u;
            is_jal_instr: imm = imm_j;
            default:     imm = imm_i;
        endcase
    end

    // ── JAL/JALR target calculation (combinational) ──
    always @(*) begin
        jal_target  = pc + imm;
        jalr_target = (rf_rs1_data + imm) & ~32'h1;  // Clear LSB
    end

    // ── ALU operation decode ──
    // alu_op[3:0]: {funct7_bit5, funct3}
    // ADD=0000, SUB=1000, SLL=0001, SLT=0010, SLTU=0011
    // XOR=0100, SRL=0101 (funct7_bit5=0), SRA=1101 (funct7_bit5=1)
    // OR=0110, AND=0111
    // Special: LUI=1111 (pass imm), AUIPC=1110 (ADD pc+imm), BRANCH=0100 (for comparison)
    always @(*) begin
        if (is_lui) begin
            alu_op = 4'b1111;  // Pass-through imm (handled in EX)
        end
        else if (is_auipc) begin
            alu_op = 4'b0000;  // ADD (pc + imm handled by alu_src_a/b)
        end
        else if (is_branch_instr) begin
            // Branch comparison — uses funct3 for condition, ALU does SUB internally
            alu_op = {funct7[5], funct3_in};
        end
        else if (is_alu_reg || is_alu_imm) begin
            alu_op = {funct7[5], funct3_in};
        end
        else begin
            // LOAD, STORE, JAL, JALR: default to ADD
            alu_op = 4'b0000;
        end
    end

    // ── ALU source select ──
    always @(*) begin
        if (is_auipc) begin
            alu_src_a = 1'b1;  // PC
        end
        else if (is_jal_instr || is_jalr_instr) begin
            alu_src_a = 1'b1;  // PC (for link address)
        end
        else begin
            alu_src_a = 1'b0;  // rs1
        end

        if (is_alu_imm || is_load || is_store || is_lui || is_auipc || is_jal_instr || is_jalr_instr) begin
            alu_src_b = 1'b1;  // immediate
        end
        else begin
            alu_src_b = 1'b0;  // rs2
        end
    end

    // ── Memory control ──
    always @(*) begin
        mem_read  = is_load;
        mem_write = is_store;

        case (funct3_in)
            3'b000: mem_width = 2'b00;  // Byte
            3'b001: mem_width = 2'b01;  // Halfword
            3'b010: mem_width = 2'b10;  // Word
            default: mem_width = 2'b10;  // Default to word
        endcase

        // Sign extension: LB/LH=1, LBU/LHU=0
        mem_sign_ext = (funct3_in == 3'b000) || (funct3_in == 3'b001);
    end

    // ── Writeback control ──
    always @(*) begin
        // Determine WB enable
        wb_en = is_alu_reg || is_alu_imm || is_load || is_lui || is_auipc
             || is_jal_instr || is_jalr_instr || is_csr_instr;

        // WB source select: 00=ALU, 01=MEM, 10=PC+4, 11=CSR
        if (is_load)
            wb_src = 2'b01;  // Memory
        else if (is_jal_instr || is_jalr_instr)
            wb_src = 2'b10;  // PC+4 (link address)
        else if (is_csr_instr)
            wb_src = 2'b11;  // CSR
        else
            wb_src = 2'b00;  // ALU result
    end

    // ── Branch control ──
    always @(*) begin
        is_branch = is_branch_instr;
        branch_op = funct3_in;  // funct3 encodes branch condition
    end

    // ── Jump signals ──
    always @(*) begin
        is_jal  = is_jal_instr;
        is_jalr = is_jalr_instr;
    end

    // ── CSR control ──
    always @(*) begin
        is_csr = is_csr_instr && (funct3_in != 3'b000);  // funct3=000 is ECALL/EBREAK/MRET
        csr_op = funct3_in[1:0];
        csr_addr = instr[31:20];
    end

    // ── System instruction decode ──
    always @(*) begin
        if (is_system && funct3_in == 3'b000) begin
            case (instr[31:20])
                12'h000: begin is_ecall=1; is_ebreak=0; is_mret=0; end  // ECALL
                12'h001: begin is_ecall=0; is_ebreak=1; is_mret=0; end  // EBREAK
                12'h302: begin is_ecall=0; is_ebreak=0; is_mret=1; end  // MRET
                default: begin is_ecall=0; is_ebreak=0; is_mret=0; end
            endcase
        end
        else begin
            is_ecall  = 1'b0;
            is_ebreak = 1'b0;
            is_mret   = 1'b0;
        end
    end

    // ── Illegal instruction detection ──
    // Catches: undefined opcodes, RV32I instructions not in our subset
    // Simplified: any opcode not explicitly decoded is illegal
    always @(*) begin
        is_illegal = ~(is_alu_reg || is_alu_imm || is_load || is_store
                    || is_branch_instr || is_jal_instr || is_jalr_instr
                    || is_lui || is_auipc || is_system);
    end

    // ── funct3 passthrough ──
    always @(*) begin
        funct3 = funct3_in;
    end

endmodule
