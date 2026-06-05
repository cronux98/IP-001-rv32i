# IP-001 RV32I GRM — Test: Shift Operations
# Tests: SLL, SRL, SRA, SLLI, SRLI, SRAI

.section .text.init
.globl _start
_start:
    # ── Test 1: SLL (shift left logical) ────────────────────────────
    li x1, 1
    li x2, 10
    sll x3, x1, x2          # x3 = 1 << 10 = 1024
    li x4, 1024
    bne x3, x4, fail

    # ── Test 2: SLL by 0 ────────────────────────────────────────────
    li x1, 42
    sll x3, x1, x0          # x3 = 42 << 0 = 42
    bne x3, x1, fail

    # ── Test 3: SLLI ────────────────────────────────────────────────
    li x1, 1
    slli x3, x1, 5          # x3 = 32
    li x4, 32
    bne x3, x4, fail

    # ── Test 4: SRL (shift right logical) ───────────────────────────
    li x1, 0x80000000       # MSB set
    li x2, 1
    srl x3, x1, x2          # x3 = 0x40000000 (zero-fill)
    li x4, 0x40000000
    bne x3, x4, fail

    # ── Test 5: SRL by 31 (shift all the way) ───────────────────────
    li x1, 0x80000000
    li x2, 31
    srl x3, x1, x2          # x3 = 1
    li x4, 1
    bne x3, x4, fail

    # ── Test 6: SRA (arithmetic right shift, sign-preserving) ───────
    li x1, 0x80000000       # -2147483648 (signed)
    li x2, 1
    sra x3, x1, x2          # x3 = 0xC0000000 (sign-fill)
    li x4, 0xC0000000
    bne x3, x4, fail

    # ── Test 7: SRA by 31 (all sign bits) ───────────────────────────
    li x1, 0x80000000
    li x2, 31
    sra x3, x1, x2          # x3 = 0xFFFFFFFF (all sign bits)
    li x4, 0xFFFFFFFF
    bne x3, x4, fail

    # ── Test 8: SRA positive number ─────────────────────────────────
    li x1, 0x40000000       # positive
    li x2, 1
    sra x3, x1, x2          # x3 = 0x20000000 (zero-fill, same as SRL)
    li x4, 0x20000000
    bne x3, x4, fail

    # ── Test 9: SRLI ────────────────────────────────────────────────
    li x1, 0x80000000
    srli x3, x1, 4          # x3 = 0x08000000
    li x4, 0x08000000
    bne x3, x4, fail

    # ── Test 10: SRAI ───────────────────────────────────────────────
    li x1, 0x80000000
    srai x3, x1, 4          # x3 = 0xF8000000
    li x4, 0xF8000000
    bne x3, x4, fail

    # ── Test 11: Shift by > 31 (only lower 5 bits used) ─────────────
    # shift amount = 33 → 33 & 0x1F = 1
    li x1, 0x80000000
    li x2, 33
    srl x3, x1, x2          # same as srl by 1
    li x4, 0x40000000
    bne x3, x4, fail

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
