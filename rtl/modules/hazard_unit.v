// ============================================================================
// IP-001 — RV32I 5-Stage Pipeline Core
// Module: hazard_unit — Load-use hazard detection and stall generation
// FR Trace: FR-008
// Author: Silicon Sage | Date: 2026-06-08
// ============================================================================

module hazard_unit (
    input  wire        id_ex_mem_read,
    input  wire [ 4:0] id_ex_rd_addr,
    input  wire [ 4:0] if_id_rs1_addr,
    input  wire [ 4:0] if_id_rs2_addr,
    output wire        stall_if,
    output wire        stall_id
);

    // ── Load-use hazard detection ──
    // Hazard exists when:
    //   1. Instruction in EX is a load (mem_read = 1)
    //   2. Load destination is NOT x0
    //   3. Load destination matches either source register of ID instruction
    wire load_use_hazard;

    assign load_use_hazard = id_ex_mem_read
                          && (id_ex_rd_addr != 5'd0)
                          && (  (id_ex_rd_addr == if_id_rs1_addr)
                              || (id_ex_rd_addr == if_id_rs2_addr));

    // ── Stall outputs ──
    // Both IF and ID are stalled for exactly one cycle.
    // The load moves to MEM in the next cycle and forwarding from MEM/WB
    // resolves the dependency. No consecutive stalls possible.
    assign stall_if = load_use_hazard;
    assign stall_id = load_use_hazard;

    // NOTE: Store-after-load does NOT trigger a stall. The store instruction
    // doesn't need the load result until MEM stage, giving an extra cycle
    // for forwarding from MEM/WB to supply the store data.

endmodule
