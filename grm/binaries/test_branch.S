# IP-001 RV32I GRM — Test: Branch and Jump Instructions
# Tests: BEQ, BNE, BLT, BGE, BLTU, BGEU, JAL, JALR

.section .text.init
.globl _start
_start:
    # ── Test 1: BEQ (taken) ────────────────────────────────────────
    li x1, 42
    li x2, 42
    beq x1, x2, beq_taken_ok
    j fail
beq_taken_ok:

    # ── Test 2: BEQ (not taken) ────────────────────────────────────
    li x1, 42
    li x2, 43
    beq x1, x2, fail
    # Falls through → OK

    # ── Test 3: BNE (taken) ────────────────────────────────────────
    li x1, 42
    li x2, 43
    bne x1, x2, bne_taken_ok
    j fail
bne_taken_ok:

    # ── Test 4: BNE (not taken) ────────────────────────────────────
    li x1, 42
    li x2, 42
    bne x1, x2, fail
    # Falls through → OK

    # ── Test 5: BLT signed (taken: -2 < 5) ─────────────────────────
    li x1, -2
    li x2, 5
    blt x1, x2, blt_taken_ok
    j fail
blt_taken_ok:

    # ── Test 6: BLT signed (not taken: 5 < -2) ─────────────────────
    li x1, 5
    li x2, -2
    blt x1, x2, fail
    # Falls through → OK

    # ── Test 7: BGE signed (taken: 5 >= -2) ────────────────────────
    li x1, 5
    li x2, -2
    bge x1, x2, bge_taken_ok
    j fail
bge_taken_ok:

    # ── Test 8: BGE signed (not taken: -5 >= 2) ────────────────────
    li x1, -5
    li x2, 2
    bge x1, x2, fail
    # Falls through → OK

    # ── Test 9: BLTU unsigned (taken: 1 < 0xFFFFFFFF) ──────────────
    li x1, 1
    li x2, -1               # 0xFFFFFFFF unsigned
    bltu x1, x2, bltu_taken_ok
    j fail
bltu_taken_ok:

    # ── Test 10: BLTU unsigned (not taken: 0xFFFFFFFF < 1) ─────────
    li x1, -1               # 0xFFFFFFFF
    li x2, 1
    bltu x1, x2, fail
    # Falls through → OK

    # ── Test 11: BGEU unsigned (taken: 0xFFFFFFFF >= 1) ────────────
    li x1, -1               # 0xFFFFFFFF
    li x2, 1
    bgeu x1, x2, bgeu_taken_ok
    j fail
bgeu_taken_ok:

    # ── Test 12: BGEU unsigned (not taken: 1 >= 0xFFFFFFFF) ────────
    li x1, 1
    li x2, -1               # 0xFFFFFFFF
    bgeu x1, x2, fail
    # Falls through → OK

    # ── Test 13: JAL (jump and link) ────────────────────────────────
    li x1, 0
    jal x3, jal_target
    j fail                  # Should not reach here
jal_target:
    # x3 = return address (PC+4 of JAL)
    bne x3, x0, jal_link_ok # Link should not be zero
    j fail
jal_link_ok:

    # ── Test 14: JALR (jump and link register) ─────────────────────
    la x4, jalr_target
    li x1, 0
    jalr x3, 0(x4)
    j fail
jalr_target:
    bne x3, x0, jalr_link_ok
    j fail
jalr_link_ok:

    # ── Test 15: JALR LSB cleared ──────────────────────────────────
    la x4, jalr_target2
    addi x4, x4, 1          # Set LSB (should be cleared)
    jalr x5, 0(x4)
    j fail
jalr_target2:
    # If we got here, JALR cleared LSB correctly
    j success_check

    j fail

success_check:
    # ── SUCCESS ─────────────────────────────────────────────────────
    li a0, 0
    j exit

fail:
    li a0, 1

exit:
    # Store exit code in DMEM for trace verification
    li x5, 0x80001020
    sw a0, 0(x5)
    # Write to tohost for Spike termination (format: (code<<1)|1)
    slli a1, a0, 1
    ori a1, a1, 1
    la t0, tohost
    sw a1, 0(t0)
1:  j 1b  # Spin forever
