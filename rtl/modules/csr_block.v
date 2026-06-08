// ============================================================================
// IP-001 — RV32I 5-Stage Pipeline Core
// Module: csr_block — Machine-mode CSRs + Trap Handling
// FR Trace: FR-010, FR-011, IFR-004
// Author: Silicon Sage | Date: 2026-06-08
// ============================================================================

module csr_block (
    input  wire        clk,
    input  wire        rst_sync_n,
    input  wire [ 1:0] csr_op,
    input  wire [11:0] csr_addr,
    input  wire [31:0] rs1_data,
    input  wire [ 4:0] rd_addr,
    input  wire        wb_en_in,
    input  wire        is_ecall,
    input  wire        is_ebreak,
    input  wire        is_illegal,
    input  wire        misaligned_trap,
    input  wire [31:0] pc_current,
    input  wire        irq_timer,
    input  wire        irq_external,
    output reg  [31:0] csr_rdata,
    output reg         wb_en_out,
    output reg         trap_taken,
    output reg  [31:0] trap_target,
    output reg         mret_taken,
    output reg  [31:0] mret_target,
    output reg         flush_pipeline
);

    // ── CSR registers ──
    reg [31:0] mstatus, misa, mtvec, mepc, mcause, mie, mip;

    // ── RISC-V Privileged Spec reset values ──
    localparam MSTATUS_RESET = 32'h00001800;  // MPP=11 (M-mode), MPIE=0, MIE=0
    localparam MISA_RESET    = 32'h40000100;  // MXL=1 (XLEN=32), Ext=I
    localparam MTVEC_RESET   = 32'h00000000;  // Direct mode, base=0
    localparam MEPC_RESET    = 32'h00000000;
    localparam MCAUSE_RESET  = 32'h00000000;
    localparam MIE_RESET     = 32'h00000000;
    localparam MIP_RESET     = 32'h00000000;

    // ── Trap cause codes ──
    localparam CAUSE_ILLEGAL_INSTR  = 32'd2;
    localparam CAUSE_BREAKPOINT     = 32'd3;
    localparam CAUSE_MISALIGNED_LD  = 32'd4;
    localparam CAUSE_MISALIGNED_ST  = 32'd6;
    localparam CAUSE_ECALL_MMODE    = 32'd11;
    localparam CAUSE_MTIMER_IRQ     = 32'h80000007;
    localparam CAUSE_MEXT_IRQ       = 32'h8000000B;

    // ── Internal signals ──
    wire        is_csr_instr;
    wire        csr_write_op;
    reg  [31:0] csr_wdata;
    reg  [31:0] csr_current;
    reg  [31:0] csr_next;
    wire        exception_pending;
    wire        interrupt_pending;
    reg         trap_entry;
    reg  [31:0] trap_cause_val;

    // ── CSR operation decoding ──
    // csr_op: 00=CSRRW, 01=CSRRS, 10=CSRRC, 11=CSRRI (immediate)
    assign is_csr_instr   = wb_en_in && (csr_addr != 12'd0);  // addr=0 not used
    assign csr_write_op   = (csr_op == 2'b00);  // CSRRW
    // csr_op==01=CSRRS, csr_op==10=CSRRC, csr_op==11=CSRRWI (handled via csr_op in write logic)

    // ── Exception/interrupt pending detection ──
    assign exception_pending = is_ecall || is_ebreak || is_illegal || misaligned_trap;
    assign interrupt_pending = (irq_timer && mie[7] && mstatus[3])     // MTIE + MIE
                            || (irq_external && mie[11] && mstatus[3]); // MEIE + MIE

    // ── Trap cause priority (Exceptions > Interrupts) ──
    always @(*) begin
        if (is_ecall)
            trap_cause_val = CAUSE_ECALL_MMODE;
        else if (is_ebreak)
            trap_cause_val = CAUSE_BREAKPOINT;
        else if (is_illegal)
            trap_cause_val = CAUSE_ILLEGAL_INSTR;
        else if (misaligned_trap)
            trap_cause_val = CAUSE_MISALIGNED_LD;  // Simplified — real LSU distinguishes load/store
        else if (irq_timer && mie[7] && mstatus[3])
            trap_cause_val = CAUSE_MTIMER_IRQ;
        else if (irq_external && mie[11] && mstatus[3])
            trap_cause_val = CAUSE_MEXT_IRQ;
        else
            trap_cause_val = 32'd0;
    end

    always @(*) begin
        trap_entry = exception_pending || interrupt_pending;
    end

    // ── CSR address decode → current value ──
    always @(*) begin
        case (csr_addr)
            12'h300: csr_current = mstatus;
            12'h301: csr_current = misa;
            12'h304: csr_current = mie;
            12'h305: csr_current = mtvec;
            12'h341: csr_current = mepc;
            12'h342: csr_current = mcause;
            12'h344: csr_current = mip;
            default: csr_current = 32'd0;
        endcase
    end

    // ── CSR write data computation ──
    always @(*) begin
        case (csr_op)
            2'b00: csr_wdata = rs1_data;              // CSRRW
            2'b01: csr_wdata = csr_current | rs1_data; // CSRRS
            2'b10: csr_wdata = csr_current & ~rs1_data; // CSRRC
            2'b11: csr_wdata = {27'd0, rs1_data[4:0]};  // CSRRWI (zimm)
            default: csr_wdata = rs1_data;
        endcase
    end

    // ── CSR next value computation (with RO field protection) ──
    always @(*) begin
        case (csr_addr)
            12'h300: begin  // mstatus: only MIE[3], MPIE[7] writable
                csr_next = csr_wdata;
                // Restrict to legal writable fields
                csr_next[31:8] = csr_current[31:8];  // Preserve upper bits
            end
            12'h301: csr_next = misa;               // misa is read-only
            12'h304: csr_next = csr_wdata;          // mie: all writable
            12'h305: csr_next = {csr_wdata[31:2], 2'b00};  // mtvec: MODE=direct only
            12'h341: csr_next = csr_wdata;          // mepc: all writable
            12'h342: csr_next = csr_wdata;          // mcause: all writable
            12'h344: csr_next = mip;                // mip: read-only (external interrupts only)
            default:  csr_next = csr_current;       // No change for invalid addresses
        endcase
    end

    // ── CSR output: read data to WB stage ──
    always @(*) begin
        if (is_csr_instr) begin
            csr_rdata   = csr_current;
            wb_en_out   = (rd_addr != 5'd0);  // Suppress x0 write
        end
        else if (trap_entry) begin
            // On trap, csr_rdata delivers trap handling signals (not used for RF write)
            csr_rdata   = 32'd0;
            wb_en_out   = 1'b0;
        end
        else begin
            csr_rdata   = 32'd0;
            wb_en_out   = 1'b0;
        end
    end

    // ── Trap/MRET control outputs ──
    always @(*) begin
        if (trap_entry) begin
            trap_taken   = 1'b1;
            trap_target  = {mtvec[31:2], 2'b00};  // Direct mode only
            mret_taken   = 1'b0;
            mret_target  = 32'd0;
            flush_pipeline = 1'b1;
        end
        // MRET path is handled by the EX stage; csr_block provides mepc
        // The top-level routes is_mret from decoder → pipeline_control
        // mret_taken/mret_target = mepc are set by the top module
        else begin
            trap_taken   = 1'b0;
            trap_target  = 32'd0;
            mret_taken   = 1'b0;
            mret_target  = mepc;
            flush_pipeline = 1'b0;
        end
    end

    // ── CSR register update (clocked) ──
    always @(posedge clk or negedge rst_sync_n) begin
        if (~rst_sync_n) begin
            mstatus <= MSTATUS_RESET;
            misa    <= MISA_RESET;
            mtvec   <= MTVEC_RESET;
            mepc    <= MEPC_RESET;
            mcause  <= MCAUSE_RESET;
            mie     <= MIE_RESET;
            mip     <= MIP_RESET;
        end
        else begin
            // ── mip: external interrupt inputs (clocked to avoid glitches) ──
            mip[7]  <= irq_timer;     // MTIP
            mip[11] <= irq_external;   // MEIP

            // ── Trap entry: save context ──
            if (trap_entry) begin
                mcause      <= trap_cause_val;
                mepc        <= pc_current;
                mstatus[7]  <= mstatus[3];  // MPIE ← MIE
                mstatus[3]  <= 1'b0;        // MIE ← 0 (disable interrupts)
            end
            // ── CSR instruction write ──
            else if (is_csr_instr) begin
                case (csr_addr)
                    12'h300: mstatus <= csr_next;
                    12'h301: ;       // misa is read-only
                    12'h304: mie     <= csr_next;
                    12'h305: mtvec   <= csr_next;
                    12'h341: mepc    <= csr_next;
                    12'h342: mcause  <= csr_next;
                    12'h344: ;       // mip is read-only
                    default: ;       // invalid address — no write
                endcase
            end
        end
    end

endmodule
