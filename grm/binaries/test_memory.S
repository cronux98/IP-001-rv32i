# IP-001 RV32I GRM — Test: Memory Operations (Load/Store)
# Tests: LW, SW, LH, SH, LB, SB, LBU, LHU

.section .text.init
.globl _start
_start:
    # Set up data memory pointer
    li x10, 0x80001000       # D-mem base

    # ── Test 1: SW + LW (word) ─────────────────────────────────────
    li x1, 0xDEADBEEF
    sw x1, 0(x10)
    lw x3, 0(x10)
    bne x3, x1, fail

    # ── Test 2: SW + LW at offset ──────────────────────────────────
    li x1, 0xCAFEBABE
    sw x1, 16(x10)
    lw x3, 16(x10)
    bne x3, x1, fail

    # ── Test 3: SH + LH (half-word, signed) ────────────────────────
    li x1, 0x0000ABCD
    sh x1, 32(x10)          # stores 0xABCD at offset 32
    lh x3, 32(x10)          # load signed half-word → sign-extended
    # 0xABCD = -21555 signed
    li x4, 0xFFFFABCD
    bne x3, x4, fail

    # ── Test 4: SH + LHU (half-word, unsigned) ─────────────────────
    sh x1, 32(x10)
    lhu x3, 32(x10)         # load unsigned half-word → zero-extended
    li x4, 0x0000ABCD
    bne x3, x4, fail

    # ── Test 5: SB + LB (byte, signed) ─────────────────────────────
    li x1, 0x000000FF        # -1 in 8-bit signed
    sb x1, 64(x10)          # stores 0xFF
    lb x3, 64(x10)          # load signed byte → sign-extended
    li x4, 0xFFFFFFFF
    bne x3, x4, fail

    # ── Test 6: SB + LBU (byte, unsigned) ──────────────────────────
    sb x1, 64(x10)
    lbu x3, 64(x10)
    li x4, 0x000000FF
    bne x3, x4, fail

    # ── Test 7: Half-word at offset 2 ──────────────────────────────
    li x1, 0x00001234
    sh x1, 2(x10)           # half-word at non-zero aligned offset
    lhu x3, 2(x10)
    li x4, 0x00001234
    bne x3, x4, fail

    # ── Test 8: SB at odd offset ───────────────────────────────────
    li x1, 0xAB
    sb x1, 5(x10)           # byte at offset 5
    lbu x3, 5(x10)
    li x4, 0x000000AB
    bne x3, x4, fail

    # ── Test 9: Write then read back (different registers) ─────────
    li x1, 0x11111111
    li x2, 0x22222222
    sw x1, 96(x10)
    sw x2, 100(x10)
    lw x3, 96(x10)
    lw x4, 100(x10)
    bne x3, x1, fail
    bne x4, x2, fail

    # ── Test 10: SW then LW to same register (overwrite) ───────────
    li x1, 0xBEEF0000
    sw x1, 128(x10)
    lw x1, 128(x10)         # x1 overwritten
    li x4, 0xBEEF0000
    bne x1, x4, fail

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
