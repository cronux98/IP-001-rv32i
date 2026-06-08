// ============================================================================
// IP-001 — RV32I 5-Stage Pipeline Core
// Module: rv32i_core — Top-level pipeline integration
// FR Trace: All (FR-001 through FR-013)
// Author: Silicon Sage | Date: 2026-06-08
// ============================================================================

module rv32i_core (
    input  wire        clk,
    input  wire        rst_n,           // Async reset (active low)
    input  wire        irq_timer,       // Machine timer interrupt
    input  wire        irq_external,    // Machine external interrupt
    // Instruction memory interface (Harvard)
    output wire [31:0] i_addr,
    input  wire [31:0] i_rdata,
    // Data memory interface (Harvard)
    output wire [31:0] d_addr,
    output wire [31:0] d_wdata,
    input  wire [31:0] d_rdata,
    output wire [ 3:0] d_be,
    output wire        d_we
);

    // ========================================================================
    // Reset Synchronizer (2-stage FF chain — async assertion, sync deassertion)
    // ========================================================================
    reg [1:0] rst_sync_ff;
    wire rst_sync_n;

    always @(posedge clk or negedge rst_n) begin
        if (~rst_n) begin
            rst_sync_ff <= 2'b00;
        end
        else begin
            rst_sync_ff <= {rst_sync_ff[0], 1'b1};
        end
    end

    assign rst_sync_n = rst_sync_ff[1];

    // ========================================================================
    // Pipeline Registers
    // ========================================================================

    // ── IF/ID Register ──
    reg [31:0] if_id_pc, if_id_pc_plus4, if_id_instr;
    reg         if_id_valid;  // Valid flag (cleared on flush)

    // ── ID/EX Register ──
    reg [31:0] id_ex_pc;
    reg [31:0] id_ex_rs1_data, id_ex_rs2_data;
    reg [31:0] id_ex_imm;
    reg [ 4:0] id_ex_rd_addr, id_ex_rs1_addr, id_ex_rs2_addr;
    reg [ 3:0] id_ex_alu_op;
    reg        id_ex_alu_src_a, id_ex_alu_src_b;
    reg        id_ex_mem_read, id_ex_mem_write;
    reg [ 1:0] id_ex_mem_width;
    reg        id_ex_mem_sign_ext;
    reg        id_ex_wb_en;
    reg [ 1:0] id_ex_wb_src;
    reg [ 2:0] id_ex_branch_op;
    reg        id_ex_is_branch;
    reg        id_ex_is_jal, id_ex_is_jalr;
    reg        id_ex_is_csr;
    reg        id_ex_is_ecall, id_ex_is_ebreak, id_ex_is_illegal, id_ex_is_mret;
    reg [ 1:0] id_ex_csr_op;
    reg [11:0] id_ex_csr_addr;

    // ── EX/MEM Register ──
    reg [31:0] ex_mem_pc;
    reg [31:0] ex_mem_alu_result, ex_mem_rs2_data;
    reg [ 4:0] ex_mem_rd_addr;
    reg        ex_mem_mem_read, ex_mem_mem_write;
    reg [ 1:0] ex_mem_mem_width;
    reg        ex_mem_mem_sign_ext;
    reg        ex_mem_wb_en;
    reg [ 1:0] ex_mem_wb_src;
    reg        ex_mem_is_csr;
    reg [ 1:0] ex_mem_csr_op;
    reg [11:0] ex_mem_csr_addr;
    reg        ex_mem_is_ecall, ex_mem_is_ebreak, ex_mem_is_illegal, ex_mem_is_mret;
    reg        ex_mem_is_jal, ex_mem_is_jalr;

    // ── MEM/WB Register ──
    reg [31:0] mem_wb_pc;
    reg [31:0] mem_wb_alu_result, mem_wb_mem_rdata;
    reg [ 4:0] mem_wb_rd_addr;
    reg        mem_wb_wb_en;
    reg [ 1:0] mem_wb_wb_src;
    reg        mem_wb_is_csr;
    reg [31:0] mem_wb_csr_rdata;

    // ========================================================================
    // Wire declarations for module interconnects
    // ========================================================================

    // ── IF Stage → pipeline ──
    wire [31:0] if_pc, if_pc_plus4;

    // ── ID Stage outputs ──
    wire [ 4:0] id_rf_rs1_addr, id_rf_rs2_addr, id_rd_addr;
    wire [31:0] id_rs1_data, id_rs2_data, id_imm;
    wire [ 3:0] id_alu_op;
    wire        id_alu_src_a, id_alu_src_b;
    wire        id_mem_read, id_mem_write;
    wire [ 1:0] id_mem_width;
    wire        id_mem_sign_ext;
    wire        id_wb_en;
    wire [ 1:0] id_wb_src;
    wire [ 2:0] id_branch_op;
    wire        id_is_branch, id_is_jal, id_is_jalr;
    wire        id_is_csr, id_is_ecall, id_is_ebreak, id_is_illegal, id_is_mret;
    wire [ 1:0] id_csr_op;
    wire [11:0] id_csr_addr;
    wire [ 2:0] id_funct3;
    wire [31:0] id_jal_target, id_jalr_target;

    // ── EX Stage outputs ──
    wire [31:0] ex_alu_result, ex_rs2_data_out;
    wire [ 4:0] ex_rd_addr_out;
    wire        ex_mem_read_out, ex_mem_write_out;
    wire [ 1:0] ex_mem_width_out;
    wire        ex_mem_sign_ext_out;
    wire        ex_wb_en_out;
    wire [ 1:0] ex_wb_src_out;
    wire        ex_is_ecall_out, ex_is_ebreak_out, ex_is_illegal_out, ex_is_mret_out;
    wire        ex_is_csr_out;
    wire [ 1:0] ex_csr_op_out;
    wire [11:0] ex_csr_addr_out;
    wire [31:0] ex_pc_out;
    wire        ex_is_jal_out, ex_is_jalr_out;
    wire        ex_branch_taken;
    wire [31:0] ex_branch_target;

    // ── MEM Stage outputs ──
    wire [31:0] mem_alu_result_out, mem_mem_rdata;
    wire [ 4:0] mem_rd_addr_out;
    wire        mem_wb_en_out;
    wire [ 1:0] mem_wb_src_out;
    wire [31:0] mem_pc_out;
    wire        mem_is_csr_out;
    wire [31:0] mem_csr_rdata_out;
    wire        mem_misaligned_trap;

    // ── WB Stage outputs ──
    wire [ 4:0] wb_rf_rd_addr;
    wire [31:0] wb_rf_rd_data;
    wire        wb_rf_we;

    // ── Forwarding Unit outputs ──
    wire [ 1:0] fwd_a_sel, fwd_b_sel;
    wire [31:0] fwd_exmem_data, fwd_memwb_data;

    // ── Hazard Unit outputs ──
    wire stall_from_hazard;

    // ── Pipeline Control outputs ──
    wire        if_id_reg_en, id_ex_reg_en, ex_mem_reg_en, mem_wb_reg_en;
    wire        stall_if, stall_id;
    wire        flush_if, flush_id, flush_ex, flush_mem;
    wire        nop_into_ex;
    wire        pc_write_en;

    // ── CSR Block outputs ──
    wire [31:0] csr_rdata;
    wire        csr_wb_en;
    wire        trap_taken;
    wire [31:0] trap_target;
    wire        mret_taken;
    wire [31:0] mret_target;
    wire        flush_pipeline_from_csr;

    // ========================================================================
    // Module Instantiations
    // ========================================================================

    // ── IF Stage ──
    if_stage u_if (
        .clk           (clk),
        .rst_sync_n    (rst_sync_n),
        .pc_write_en   (pc_write_en),
        .flush_if      (flush_if),
        .branch_taken  (ex_branch_taken),
        .branch_target (ex_branch_target),
        .is_jal        (id_is_jal),
        .jal_target    (id_jal_target),
        .is_jalr       (id_is_jalr),
        .jalr_target   (id_jalr_target),
        .trap_taken    (trap_taken),
        .trap_target   (trap_target),
        .mret_taken    (mret_taken),
        .mret_target   (mret_target),
        .pc            (if_pc),
        .pc_plus4      (if_pc_plus4),
        .i_addr        (i_addr)
    );

    // ── Register File ──
    register_file u_rf (
        .clk       (clk),
        .rs1_addr  (id_rf_rs1_addr),
        .rs2_addr  (id_rf_rs2_addr),
        .rd_addr   (wb_rf_rd_addr),
        .rd_data   (wb_rf_rd_data),
        .we        (wb_rf_we),
        .rs1_data  (id_rs1_data),
        .rs2_data  (id_rs2_data)
    );

    // ── ID Stage ──
    id_stage u_id (
        .clk         (clk),
        .rst_sync_n  (rst_sync_n),
        .instr       (if_id_instr),
        .pc          (if_id_pc),
        .rf_rs1_data (id_rs1_data),
        .rf_rs2_data (id_rs2_data),
        .rf_rs1_addr (id_rf_rs1_addr),
        .rf_rs2_addr (id_rf_rs2_addr),
        .rd_addr     (id_rd_addr),
        .rs1_data    (id_rs1_data),
        .rs2_data    (id_rs2_data),
        .imm         (id_imm),
        .alu_op      (id_alu_op),
        .alu_src_a   (id_alu_src_a),
        .alu_src_b   (id_alu_src_b),
        .mem_read    (id_mem_read),
        .mem_write   (id_mem_write),
        .mem_width   (id_mem_width),
        .mem_sign_ext(id_mem_sign_ext),
        .wb_en       (id_wb_en),
        .wb_src      (id_wb_src),
        .branch_op   (id_branch_op),
        .is_branch   (id_is_branch),
        .is_jal      (id_is_jal),
        .is_jalr     (id_is_jalr),
        .is_csr      (id_is_csr),
        .is_ecall    (id_is_ecall),
        .is_ebreak   (id_is_ebreak),
        .is_illegal  (id_is_illegal),
        .is_mret     (id_is_mret),
        .csr_op      (id_csr_op),
        .csr_addr    (id_csr_addr),
        .funct3      (id_funct3),
        .jal_target  (id_jal_target),
        .jalr_target (id_jalr_target)
    );

    // ── EX Stage ──
    ex_stage u_ex (
        .clk            (clk),
        .rst_sync_n     (rst_sync_n),
        .flush_ex       (flush_ex),
        .rs1_data_in    (id_ex_rs1_data),
        .rs2_data_in    (id_ex_rs2_data),
        .imm            (id_ex_imm),
        .alu_op         (id_ex_alu_op),
        .alu_src_a      (id_ex_alu_src_a),
        .alu_src_b      (id_ex_alu_src_b),
        .mem_read       (id_ex_mem_read),
        .mem_write      (id_ex_mem_write),
        .mem_width      (id_ex_mem_width),
        .mem_sign_ext   (id_ex_mem_sign_ext),
        .wb_en_in       (id_ex_wb_en),
        .wb_src         (id_ex_wb_src),
        .branch_op      (id_ex_branch_op),
        .is_branch      (id_ex_is_branch),
        .is_jal         (id_ex_is_jal),
        .is_jalr        (id_ex_is_jalr),
        .is_csr         (id_ex_is_csr),
        .is_ecall       (id_ex_is_ecall),
        .is_ebreak      (id_ex_is_ebreak),
        .is_illegal     (id_ex_is_illegal),
        .is_mret        (id_ex_is_mret),
        .csr_op         (id_ex_csr_op),
        .csr_addr       (id_ex_csr_addr),
        .pc             (id_ex_pc),
        .rd_addr        (id_ex_rd_addr),
        .fwd_a_sel      (fwd_a_sel),
        .fwd_b_sel      (fwd_b_sel),
        .exmem_fwd_data (fwd_exmem_data),
        .memwb_fwd_data (fwd_memwb_data),
        .alu_result     (ex_alu_result),
        .branch_taken   (ex_branch_taken),
        .branch_target  (ex_branch_target),
        .rs2_data_out   (ex_rs2_data_out),
        .rd_addr_out    (ex_rd_addr_out),
        .mem_read_out   (ex_mem_read_out),
        .mem_write_out  (ex_mem_write_out),
        .mem_width_out  (ex_mem_width_out),
        .mem_sign_ext_out(ex_mem_sign_ext_out),
        .wb_en_out      (ex_wb_en_out),
        .wb_src_out     (ex_wb_src_out),
        .is_ecall_out   (ex_is_ecall_out),
        .is_ebreak_out  (ex_is_ebreak_out),
        .is_illegal_out (ex_is_illegal_out),
        .is_mret_out    (ex_is_mret_out),
        .is_csr_out     (ex_is_csr_out),
        .csr_op_out     (ex_csr_op_out),
        .csr_addr_out   (ex_csr_addr_out),
        .pc_out         (ex_pc_out),
        .is_jal_out     (ex_is_jal_out),
        .is_jalr_out    (ex_is_jalr_out)
    );

    // ── MEM Stage ──
    mem_stage u_mem (
        .clk              (clk),
        .rst_sync_n       (rst_sync_n),
        .flush_mem        (flush_mem),
        .alu_result       (ex_mem_alu_result),
        .rs2_data         (ex_mem_rs2_data),
        .rd_addr          (ex_mem_rd_addr),
        .mem_read         (ex_mem_mem_read),
        .mem_write        (ex_mem_mem_write),
        .mem_width        (ex_mem_mem_width),
        .mem_sign_ext     (ex_mem_mem_sign_ext),
        .wb_en_in         (ex_mem_wb_en),
        .wb_src           (ex_mem_wb_src),
        .pc               (ex_mem_pc),
        .is_jal           (ex_mem_is_jal),
        .is_jalr          (ex_mem_is_jalr),
        .d_addr           (d_addr),
        .d_wdata          (d_wdata),
        .d_be             (d_be),
        .d_we             (d_we),
        .d_rdata          (d_rdata),
        .alu_result_out   (mem_alu_result_out),
        .mem_rdata        (mem_mem_rdata),
        .rd_addr_out      (mem_rd_addr_out),
        .wb_en_out        (mem_wb_en_out),
        .wb_src_out       (mem_wb_src_out),
        .pc_out           (mem_pc_out),
        .misaligned_trap  (mem_misaligned_trap),
        .is_csr           (ex_mem_is_csr),
        .csr_rdata        (csr_rdata),
        .is_csr_out       (mem_is_csr_out),
        .csr_rdata_out    (mem_csr_rdata_out)
    );

    // ── WB Stage ──
    wb_stage u_wb (
        .alu_result  (mem_wb_alu_result),
        .mem_rdata   (mem_wb_mem_rdata),
        .pc          (mem_wb_pc),
        .rd_addr     (mem_wb_rd_addr),
        .wb_en_in    (mem_wb_wb_en),
        .wb_src      (mem_wb_wb_src),
        .is_csr      (mem_wb_is_csr),
        .csr_rdata   (mem_wb_csr_rdata),
        .rf_rd_addr  (wb_rf_rd_addr),
        .rf_rd_data  (wb_rf_rd_data),
        .rf_we       (wb_rf_we)
    );

    // ── Forwarding Unit ──
    forwarding_unit u_fwd (
        .id_ex_rs1_addr (id_ex_rs1_addr),
        .id_ex_rs2_addr (id_ex_rs2_addr),
        .ex_mem_wb_en   (ex_mem_wb_en),
        .ex_mem_rd_addr (ex_mem_rd_addr),
        .ex_mem_alu_result(ex_mem_alu_result),
        .mem_wb_wb_en   (mem_wb_wb_en),
        .mem_wb_rd_addr (mem_wb_rd_addr),
        .mem_wb_wb_data (mem_wb_alu_result),  // WB data from MEM/WB ALU result (used as forwarding data)
        .fwd_a_sel      (fwd_a_sel),
        .fwd_b_sel      (fwd_b_sel),
        .exmem_fwd_data (fwd_exmem_data),
        .memwb_fwd_data (fwd_memwb_data)
    );

    // ── Hazard Unit ──
    hazard_unit u_hazard (
        .id_ex_mem_read  (id_ex_mem_read),
        .id_ex_rd_addr   (id_ex_rd_addr),
        .if_id_rs1_addr  (if_id_instr[19:15]),
        .if_id_rs2_addr  (if_id_instr[24:20]),
        .stall_if        (stall_from_hazard),
        .stall_id        (stall_from_hazard)  // same as stall_if — both driven by hazard unit
    );

    // ── Pipeline Control ──
    // Combine stall_from_hazard with flush_pipeline_from_csr
    wire combined_stall;
    assign combined_stall = stall_from_hazard;

    pipeline_control u_ctrl (
        .stall_from_hazard (combined_stall),
        .branch_taken      (ex_branch_taken),
        .is_jal            (id_is_jal),
        .is_jalr           (id_is_jalr),
        .trap_taken        (trap_taken),
        .mret_taken        (mret_taken),
        .rst_sync_n        (rst_sync_n),
        .if_id_reg_en      (if_id_reg_en),
        .id_ex_reg_en      (id_ex_reg_en),
        .ex_mem_reg_en     (ex_mem_reg_en),
        .mem_wb_reg_en     (mem_wb_reg_en),
        .stall_if          (stall_if),
        .stall_id          (stall_id),
        .flush_if          (flush_if),
        .flush_id          (flush_id),
        .flush_ex          (flush_ex),
        .flush_mem         (flush_mem),
        .nop_into_ex       (nop_into_ex),
        .pc_write_en       (pc_write_en)
    );

    // ── CSR Block ──
    csr_block u_csr (
        .clk              (clk),
        .rst_sync_n       (rst_sync_n),
        .csr_op           (ex_mem_csr_op),
        .csr_addr         (ex_mem_csr_addr),
        .rs1_data         (ex_mem_alu_result),  // CSR rs1 data from EX stage
        .rd_addr          (ex_mem_rd_addr),
        .wb_en_in         (ex_mem_wb_en && ex_mem_is_csr),
        .is_ecall         (ex_mem_is_ecall),
        .is_ebreak        (ex_mem_is_ebreak),
        .is_illegal       (ex_mem_is_illegal),
        .misaligned_trap  (mem_misaligned_trap),
        .pc_current       (ex_mem_pc),
        .irq_timer        (irq_timer),
        .irq_external     (irq_external),
        .csr_rdata        (csr_rdata),
        .wb_en_out        (csr_wb_en),
        .trap_taken       (trap_taken),
        .trap_target      (trap_target),
        .mret_taken       (mret_taken),
        .mret_target      (mret_target),
        .flush_pipeline   (flush_pipeline_from_csr)
    );

    // ========================================================================
    // Pipeline Register Updates (clocked)
    // ========================================================================

    // ── NOP definition (all control signals zeroed) ──
    // When nop_into_ex=1 or flush_id=1, ID/EX captures all-zero control signals

    always @(posedge clk or negedge rst_sync_n) begin
        if (~rst_sync_n) begin
            // ── IF/ID reset ──
            if_id_pc       <= 32'd0;
            if_id_pc_plus4 <= 32'd0;
            if_id_instr    <= 32'h00000013;  // NOP (ADDI x0, x0, 0)
            if_id_valid    <= 1'b0;

            // ── ID/EX reset ──
            id_ex_pc         <= 32'd0;
            id_ex_rs1_data   <= 32'd0;
            id_ex_rs2_data   <= 32'd0;
            id_ex_imm        <= 32'd0;
            id_ex_rd_addr    <= 5'd0;
            id_ex_rs1_addr   <= 5'd0;
            id_ex_rs2_addr   <= 5'd0;
            id_ex_alu_op     <= 4'd0;
            id_ex_alu_src_a  <= 1'b0;
            id_ex_alu_src_b  <= 1'b0;
            id_ex_mem_read   <= 1'b0;
            id_ex_mem_write  <= 1'b0;
            id_ex_mem_width  <= 2'b0;
            id_ex_mem_sign_ext <= 1'b0;
            id_ex_wb_en      <= 1'b0;
            id_ex_wb_src     <= 2'b0;
            id_ex_branch_op  <= 3'b0;
            id_ex_is_branch  <= 1'b0;
            id_ex_is_jal     <= 1'b0;
            id_ex_is_jalr    <= 1'b0;
            id_ex_is_csr     <= 1'b0;
            id_ex_is_ecall   <= 1'b0;
            id_ex_is_ebreak  <= 1'b0;
            id_ex_is_illegal <= 1'b0;
            id_ex_is_mret    <= 1'b0;
            id_ex_csr_op     <= 2'b0;
            id_ex_csr_addr   <= 12'd0;

            // ── EX/MEM reset ──
            ex_mem_pc         <= 32'd0;
            ex_mem_alu_result <= 32'd0;
            ex_mem_rs2_data   <= 32'd0;
            ex_mem_rd_addr    <= 5'd0;
            ex_mem_mem_read   <= 1'b0;
            ex_mem_mem_write  <= 1'b0;
            ex_mem_mem_width  <= 2'b0;
            ex_mem_mem_sign_ext <= 1'b0;
            ex_mem_wb_en      <= 1'b0;
            ex_mem_wb_src     <= 2'b0;
            ex_mem_is_csr     <= 1'b0;
            ex_mem_csr_op     <= 2'b0;
            ex_mem_csr_addr   <= 12'd0;
            ex_mem_is_ecall   <= 1'b0;
            ex_mem_is_ebreak  <= 1'b0;
            ex_mem_is_illegal <= 1'b0;
            ex_mem_is_mret    <= 1'b0;
            ex_mem_is_jal     <= 1'b0;
            ex_mem_is_jalr    <= 1'b0;

            // ── MEM/WB reset ──
            mem_wb_pc         <= 32'd0;
            mem_wb_alu_result <= 32'd0;
            mem_wb_mem_rdata  <= 32'd0;
            mem_wb_rd_addr    <= 5'd0;
            mem_wb_wb_en      <= 1'b0;
            mem_wb_wb_src     <= 2'b0;
            mem_wb_is_csr     <= 1'b0;
            mem_wb_csr_rdata  <= 32'd0;
        end
        else begin
            // ── IF/ID Register ──
            if (if_id_reg_en) begin
                if (flush_if) begin
                    if_id_pc       <= 32'd0;
                    if_id_pc_plus4 <= 32'd0;
                    if_id_instr    <= 32'h00000013;  // NOP
                    if_id_valid    <= 1'b0;
                end
                else begin
                    if_id_pc       <= if_pc;
                    if_id_pc_plus4 <= if_pc_plus4;
                    if_id_instr    <= i_rdata;
                    if_id_valid    <= 1'b1;
                end
            end

            // ── ID/EX Register ──
            if (id_ex_reg_en) begin
                if (flush_id || nop_into_ex) begin
                    // Insert NOP bubble
                    id_ex_pc         <= 32'd0;
                    id_ex_rs1_data   <= 32'd0;
                    id_ex_rs2_data   <= 32'd0;
                    id_ex_imm        <= 32'd0;
                    id_ex_rd_addr    <= 5'd0;
                    id_ex_rs1_addr   <= 5'd0;
                    id_ex_rs2_addr   <= 5'd0;
                    id_ex_alu_op     <= 4'd0;
                    id_ex_alu_src_a  <= 1'b0;
                    id_ex_alu_src_b  <= 1'b0;
                    id_ex_mem_read   <= 1'b0;
                    id_ex_mem_write  <= 1'b0;
                    id_ex_mem_width  <= 2'b0;
                    id_ex_mem_sign_ext <= 1'b0;
                    id_ex_wb_en      <= 1'b0;
                    id_ex_wb_src     <= 2'b0;
                    id_ex_branch_op  <= 3'b0;
                    id_ex_is_branch  <= 1'b0;
                    id_ex_is_jal     <= 1'b0;
                    id_ex_is_jalr    <= 1'b0;
                    id_ex_is_csr     <= 1'b0;
                    id_ex_is_ecall   <= 1'b0;
                    id_ex_is_ebreak  <= 1'b0;
                    id_ex_is_illegal <= 1'b0;
                    id_ex_is_mret    <= 1'b0;
                    id_ex_csr_op     <= 2'b0;
                    id_ex_csr_addr   <= 12'd0;
                end
                else begin
                    id_ex_pc         <= if_id_pc;
                    id_ex_rs1_data   <= id_rs1_data;
                    id_ex_rs2_data   <= id_rs2_data;
                    id_ex_imm        <= id_imm;
                    id_ex_rd_addr    <= id_rd_addr;
                    id_ex_rs1_addr   <= id_rf_rs1_addr;
                    id_ex_rs2_addr   <= id_rf_rs2_addr;
                    id_ex_alu_op     <= id_alu_op;
                    id_ex_alu_src_a  <= id_alu_src_a;
                    id_ex_alu_src_b  <= id_alu_src_b;
                    id_ex_mem_read   <= id_mem_read;
                    id_ex_mem_write  <= id_mem_write;
                    id_ex_mem_width  <= id_mem_width;
                    id_ex_mem_sign_ext <= id_mem_sign_ext;
                    id_ex_wb_en      <= id_wb_en;
                    id_ex_wb_src     <= id_wb_src;
                    id_ex_branch_op  <= id_branch_op;
                    id_ex_is_branch  <= id_is_branch;
                    id_ex_is_jal     <= id_is_jal;
                    id_ex_is_jalr    <= id_is_jalr;
                    id_ex_is_csr     <= id_is_csr;
                    id_ex_is_ecall   <= id_is_ecall;
                    id_ex_is_ebreak  <= id_is_ebreak;
                    id_ex_is_illegal <= id_is_illegal;
                    id_ex_is_mret    <= id_is_mret;
                    id_ex_csr_op     <= id_csr_op;
                    id_ex_csr_addr   <= id_csr_addr;
                end
            end

            // ── EX/MEM Register ──
            if (ex_mem_reg_en) begin
                if (flush_ex) begin
                    ex_mem_pc         <= 32'd0;
                    ex_mem_alu_result <= 32'd0;
                    ex_mem_rs2_data   <= 32'd0;
                    ex_mem_rd_addr    <= 5'd0;
                    ex_mem_mem_read   <= 1'b0;
                    ex_mem_mem_write  <= 1'b0;
                    ex_mem_mem_width  <= 2'b0;
                    ex_mem_mem_sign_ext <= 1'b0;
                    ex_mem_wb_en      <= 1'b0;
                    ex_mem_wb_src     <= 2'b0;
                    ex_mem_is_csr     <= 1'b0;
                    ex_mem_csr_op     <= 2'b0;
                    ex_mem_csr_addr   <= 12'd0;
                    ex_mem_is_ecall   <= 1'b0;
                    ex_mem_is_ebreak  <= 1'b0;
                    ex_mem_is_illegal <= 1'b0;
                    ex_mem_is_mret    <= 1'b0;
                    ex_mem_is_jal     <= 1'b0;
                    ex_mem_is_jalr    <= 1'b0;
                end
                else begin
                    ex_mem_pc         <= ex_pc_out;
                    ex_mem_alu_result <= ex_alu_result;
                    ex_mem_rs2_data   <= ex_rs2_data_out;
                    ex_mem_rd_addr    <= ex_rd_addr_out;
                    ex_mem_mem_read   <= ex_mem_read_out;
                    ex_mem_mem_write  <= ex_mem_write_out;
                    ex_mem_mem_width  <= ex_mem_width_out;
                    ex_mem_mem_sign_ext <= ex_mem_sign_ext_out;
                    ex_mem_wb_en      <= ex_wb_en_out;
                    ex_mem_wb_src     <= ex_wb_src_out;
                    ex_mem_is_csr     <= ex_is_csr_out;
                    ex_mem_csr_op     <= ex_csr_op_out;
                    ex_mem_csr_addr   <= ex_csr_addr_out;
                    ex_mem_is_ecall   <= ex_is_ecall_out;
                    ex_mem_is_ebreak  <= ex_is_ebreak_out;
                    ex_mem_is_illegal <= ex_is_illegal_out;
                    ex_mem_is_mret    <= ex_is_mret_out;
                    ex_mem_is_jal     <= ex_is_jal_out;
                    ex_mem_is_jalr    <= ex_is_jalr_out;
                end
            end

            // ── MEM/WB Register ──
            if (mem_wb_reg_en) begin
                if (flush_mem) begin
                    mem_wb_pc         <= 32'd0;
                    mem_wb_alu_result <= 32'd0;
                    mem_wb_mem_rdata  <= 32'd0;
                    mem_wb_rd_addr    <= 5'd0;
                    mem_wb_wb_en      <= 1'b0;
                    mem_wb_wb_src     <= 2'b0;
                    mem_wb_is_csr     <= 1'b0;
                    mem_wb_csr_rdata  <= 32'd0;
                end
                else begin
                    mem_wb_pc         <= mem_pc_out;
                    mem_wb_alu_result <= mem_alu_result_out;
                    mem_wb_mem_rdata  <= mem_mem_rdata;
                    mem_wb_rd_addr    <= mem_rd_addr_out;
                    mem_wb_wb_en      <= mem_wb_en_out;
                    mem_wb_wb_src     <= mem_wb_src_out;
                    mem_wb_is_csr     <= mem_is_csr_out;
                    mem_wb_csr_rdata  <= mem_csr_rdata_out;
                end
            end
        end
    end

endmodule
