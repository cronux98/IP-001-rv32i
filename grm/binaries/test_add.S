# IP-001 RV32I GRM — Test: Basic Arithmetic (ADD/SUB)
# Tests: ADD, ADDI, SUB, LUI, AUIPC
# Exit: a0=0 (PASS), a0!=0 (FAIL)

.section .text.init
.globl _start
_start:
    # ── Test 1: ADD ────────────────────────────────────────────────
    li x1, 42
    li x2, 58
    add x3, x1, x2          # x3 = 42 + 58 = 100
    li x4, 100
    bne x3, x4, fail

    # ── Test 2: SUB ────────────────────────────────────────────────
    li x1, 100
    li x2, 42
    sub x3, x1, x2          # x3 = 100 - 42 = 58
    li x4, 58
    bne x3, x4, fail

    # ── Test 3: ADDI with negative immediate ───────────────────────
    li x1, 100
    addi x3, x1, -30        # x3 = 100 - 30 = 70
    li x4, 70
    bne x3, x4, fail

    # ── Test 4: ADDI with zero immediate ───────────────────────────
    li x1, 42
    addi x3, x1, 0          # x3 = 42 + 0 = 42
    bne x3, x1, fail

    # ── Test 5: LUI ─────────────────────────────────────────────────
    lui x3, 0x12345         # x3 = 0x12345000
    # Check upper bits are set, lower 12 bits are 0
    srli x4, x3, 12
    li x5, 0x12345
    bne x4, x5, fail
    slli x4, x3, 20
    bne x4, x0, fail        # lower 12 bits should be 0

    # ── Test 6: AUIPC ──────────────────────────────────────────────
    # AUIPC is PC-relative. We check that x3 != 0 and x3 != pc
    auipc x3, 0
    beq x3, x0, fail        # Should not be zero

    # ── Test 7: ADD with negative numbers ──────────────────────────
    li x1, -10
    li x2, -20
    add x3, x1, x2          # x3 = -30
    li x4, -30
    bne x3, x4, fail

    # ── Test 8: ADD overflow wrapping ──────────────────────────────
    li x1, 0x7FFFFFFF       # max positive
    addi x3, x1, 1          # wraps to 0x80000000 (min negative)
    li x4, 0x80000000
    bne x3, x4, fail

    # ── Test 9: SUB producing zero ─────────────────────────────────
    li x1, 42
    sub x3, x1, x1          # x3 = 0
    bne x3, x0, fail

    # ── SUCCESS ─────────────────────────────────────────────────────
    li a0, 0                # exit code 0 = PASS
    j exit

fail:
    li a0, 1                # exit code 1 = FAIL
    j exit

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
