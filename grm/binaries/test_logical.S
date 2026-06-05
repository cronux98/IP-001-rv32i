# IP-001 RV32I GRM — Test: Logical Operations
# Tests: AND, OR, XOR, ANDI, ORI, XORI

.section .text.init
.globl _start
_start:
    # ── Test 1: AND ─────────────────────────────────────────────────
    li x1, 0xFF00FF00
    li x2, 0x0F0F0F0F
    and x3, x1, x2          # x3 = 0x0F000F00
    li x4, 0x0F000F00
    bne x3, x4, fail

    # ── Test 2: OR ─────────────────────────────────────────────────
    li x1, 0xFF00FF00
    li x2, 0x0F0F0F0F
    or x3, x1, x2           # x3 = 0xFF0FFF0F
    li x4, 0xFF0FFF0F
    bne x3, x4, fail

    # ── Test 3: XOR ─────────────────────────────────────────────────
    li x1, 0xFF00FF00
    li x2, 0x0F0F0F0F
    xor x3, x1, x2          # x3 = 0xF00FF00F
    li x4, 0xF00FF00F
    bne x3, x4, fail

    # ── Test 4: ANDI ────────────────────────────────────────────────
    li x1, 0xFF
    andi x3, x1, 0x0F       # x3 = 0x0F
    li x4, 0x0F
    bne x3, x4, fail

    # ── Test 5: ORI ─────────────────────────────────────────────────
    li x1, 0xF0
    ori x3, x1, 0x0F        # x3 = 0xFF
    li x4, 0xFF
    bne x3, x4, fail

    # ── Test 6: XORI ────────────────────────────────────────────────
    li x1, 0xFF
    xori x3, x1, 0x0F       # x3 = 0xF0
    li x4, 0xF0
    bne x3, x4, fail

    # ── Test 7: XOR a,a = 0 ─────────────────────────────────────────
    li x1, 0xDEADBEEF
    xor x3, x1, x1
    bne x3, x0, fail

    # ── Test 8: AND with zero ───────────────────────────────────────
    li x1, 0xDEADBEEF
    and x3, x1, x0
    bne x3, x0, fail

    # ── Test 9: OR with zero ────────────────────────────────────────
    li x1, 0xDEADBEEF
    or x3, x1, x0
    bne x3, x1, fail

    # ── Test 10: AND -1,x = x ───────────────────────────────────────
    li x1, 0x1234
    and x3, x1, x1
    bne x3, x1, fail

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
