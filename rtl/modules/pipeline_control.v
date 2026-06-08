// ============================================================================
// IP-001 — RV32I 5-Stage Pipeline Core
// Module: pipeline_control — Stall, flush, and NOP insertion for 5-stage pipe
// FR Trace: FR-013
// Author: Silicon Sage | Date: 2026-06-08
// ============================================================================

module pipeline_control (
    input  wire stall_from_hazard,
    input  wire branch_taken,
    input  wire is_jal,
    input  wire is_jalr,
    input  wire trap_taken,
    input  wire mret_taken,
    input  wire rst_sync_n,
    output reg  if_id_reg_en,
    output reg  id_ex_reg_en,
    output wire ex_mem_reg_en,
    output wire mem_wb_reg_en,
    output reg  stall_if,
    output reg  stall_id,
    output reg  flush_if,
    output reg  flush_id,
    output reg  flush_ex,
    output reg  flush_mem,
    output reg  nop_into_ex,
    output reg  pc_write_en
);

    // EX/MEM and MEM/WB are always enabled — they advance or get flushed
    // via NOP insertion at their inputs, not by disabling the register.
    assign ex_mem_reg_en  = 1'b1;
    assign mem_wb_reg_en  = 1'b1;

    // ── Flush/Stall priority logic (combinational) ──
    // Priority: Reset > Trap > MRET > Branch > JAL/JALR > Stall > Normal
    always @(*) begin
        if (~rst_sync_n) begin
            // RESET: flush ALL stages
            flush_if      = 1'b1;
            flush_id      = 1'b1;
            flush_ex      = 1'b1;
            flush_mem     = 1'b1;
            stall_if      = 1'b0;
            stall_id      = 1'b0;
            nop_into_ex   = 1'b0;
        end
        else if (trap_taken) begin
            // TRAP ENTRY: flush IF, ID, EX
            // Trapping instruction is in EX — prevent its WB
            flush_if      = 1'b1;
            flush_id      = 1'b1;
            flush_ex      = 1'b1;
            flush_mem     = 1'b0;
            stall_if      = 1'b0;
            stall_id      = 1'b0;
            nop_into_ex   = 1'b0;
        end
        else if (mret_taken) begin
            // MRET: flush IF, ID, EX — return to mepc
            flush_if      = 1'b1;
            flush_id      = 1'b1;
            flush_ex      = 1'b1;
            flush_mem     = 1'b0;
            stall_if      = 1'b0;
            stall_id      = 1'b0;
            nop_into_ex   = 1'b0;
        end
        else if (branch_taken) begin
            // TAKEN BRANCH: flush IF, ID (2-cycle penalty)
            // Branch resolves in EX; IF/ID fetched wrong sequential instrs
            flush_if      = 1'b1;
            flush_id      = 1'b1;
            flush_ex      = 1'b0;
            flush_mem     = 1'b0;
            stall_if      = 1'b0;
            stall_id      = 1'b0;
            nop_into_ex   = 1'b0;
        end
        else if (is_jal || is_jalr) begin
            // JAL/JALR: flush IF only (decoded in ID, IF fetched next sequential)
            flush_if      = 1'b1;
            flush_id      = 1'b0;
            flush_ex      = 1'b0;
            flush_mem     = 1'b0;
            stall_if      = 1'b0;
            stall_id      = 1'b0;
            nop_into_ex   = 1'b0;
        end
        else if (stall_from_hazard) begin
            // LOAD-USE STALL: freeze IF+ID, inject NOP bubble into EX
            flush_if      = 1'b0;
            flush_id      = 1'b0;
            flush_ex      = 1'b0;
            flush_mem     = 1'b0;
            stall_if      = 1'b1;
            stall_id      = 1'b1;
            nop_into_ex   = 1'b1;
        end
        else begin
            // NORMAL: advance all stages
            flush_if      = 1'b0;
            flush_id      = 1'b0;
            flush_ex      = 1'b0;
            flush_mem     = 1'b0;
            stall_if      = 1'b0;
            stall_id      = 1'b0;
            nop_into_ex   = 1'b0;
        end
    end

    // ── Pipeline register write enables ──
    // PC and IF/ID register freeze on stall; ID/EX freezes on stall
    always @(*) begin
        pc_write_en   = ~stall_if && ~flush_if;
        if_id_reg_en  = ~stall_if;
        id_ex_reg_en  = ~stall_id;
    end

endmodule
