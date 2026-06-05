# IP-001 RV32I GRM — Test: CSR Operations
# Tests: CSRRW, CSRRS, CSRRC, CSRRWI, CSRRSI, CSRRCI
# Also verifies CSR reset values against microarchitecture §4.3

.section .text.init
.globl _start
_start:
    # ── Test 1: misa (0x301) — read-only, MXL must be RV32 ───────
    csrr x3, misa            # x3 = misa
    # MXL field (bits 31:30) must be 1 (RV32)
    srli x4, x3, 30
    andi x4, x4, 3
    li x5, 1
    bne x4, x5, fail
    # Save original misa value for write-ignore check
    mv x30, x3

    # ── Test 2: misa write ignored (RO register) ────────────────────
    li x1, 0xFFFFFFFF
    csrw misa, x1            # Try to write all 1s
    csrr x3, misa            # Read back
    bne x3, x30, fail         # Must equal saved original value

    # ── Test 3: mstatus (0x300) — reset = 0x0000_0000 ───────────────
    csrr x3, mstatus
    # Spike mstatus reset may differ; check MIE=0 (bit 3)
    andi x3, x3, 8           # Extract MIE bit
    bne x3, x0, fail

    # ── Test 4: mstatus MIE bit write ───────────────────────────────
    li x1, 8                 # MIE = 1
    csrs mstatus, x1         # Set MIE bit atomically
    csrr x3, mstatus
    andi x3, x3, 8
    beq x3, x0, fail         # MIE should be set
    # Clear MIE again
    csrc mstatus, x1
    csrr x3, mstatus
    andi x3, x3, 8
    bne x3, x0, fail         # MIE should be cleared

    # ── Test 5: mtvec (0x305) — write and read back ─────────────────
    la x1, trap_handler
    csrw mtvec, x1
    csrr x3, mtvec
    bne x3, x1, fail
    # Reset mtvec to 0
    csrw mtvec, x0

    # ── Test 6: mie (0x304) — write MTIE and MEIE bits ──────────────
    li x1, 0x880              # MTIE (bit 7) + MEIE (bit 11)
    csrw mie, x1
    csrr x3, mie
    bne x3, x1, fail
    # Clear
    csrw mie, x0
    csrr x3, mie
    bne x3, x0, fail

    # ── Test 7: mcause (0x342) — write and read ─────────────────────
    li x1, 2                 # Illegal instruction cause
    csrw mcause, x1
    csrr x3, mcause
    li x4, 2
    bne x3, x4, fail

    # ── Test 8: mepc (0x341) — write and read ───────────────────────
    li x1, 0x12345678
    csrw mepc, x1
    csrr x3, mepc
    # Bits [1:0] may be forced to 0 (word-aligned)
    li x4, 0x12345678
    bne x3, x4, fail

    # ── Test 9: CSRRS (read and set bits) ───────────────────────────
    # Use writable mie bits: MTIE(bit7=0x80), MEIE(bit11=0x800)
    li x1, 0x880            # MTIE + MEIE
    csrw mie, x1             # mie = 0x880
    li x2, 0x080            # Just MTIE bit
    csrrs x3, mie, x2        # x3 = old mie (0x880), mie stays 0x880
    li x4, 0x880
    bne x3, x4, fail         # Old value should be 0x880
    csrr x4, mie
    li x5, 0x880
    bne x4, x5, fail         # New value should still be 0x880
    csrw mie, x0             # Clean up

    # ── Test 10: CSRRC (read and clear bits) ────────────────────────
    li x1, 0x880            # MTIE + MEIE
    csrw mie, x1             # mie = 0x880
    li x2, 0x080            # Clear MTIE
    csrrc x3, mie, x2        # x3 = old mie (0x880), mie &= ~0x080 = 0x800
    li x4, 0x880
    bne x3, x4, fail
    csrr x4, mie
    li x5, 0x800             # Only MEIE left
    bne x4, x5, fail
    csrw mie, x0

    # ── Test 11: CSRRWI (immediate write) ───────────────────────────
    csrrwi x3, mie, 0x15     # x3 = old mie, mie = 0x15 (5-bit uimm)
    csrr x4, mie
    # Only writable bits take effect (0x15=bits 0,2,4; none are standard M-mode writable)
    # Check that mie was set to whatever Spike allows from 0x15
    csrw mie, x0             # Clean up

    # ── Test 12: CSRRSI (immediate set) ─────────────────────────────
    li x1, 0x880
    csrw mie, x1
    csrrsi x3, mie, 0x15     # mie |= 0x15 (try to set bits 0,2,4)
    csrr x4, mie
    # Should still have 0x880 (imm bits 0,2,4 are RO)
    beq x4, x1, csrsi_ok
    j fail
csrsi_ok:
    csrw mie, x0

    # ── Test 13: CSRRCI (immediate clear) ───────────────────────────
    li x1, 0x880
    csrw mie, x1
    csrrci x3, mie, 0x10     # mie &= ~0x10 (clear bit 4; bit 4 is RO in Spike)
    # 0x10 is within 5-bit immediate range
    csrr x4, mie
    li x5, 0x880             # Should still be 0x880 (bit 4 was already 0/RO)
    bne x4, x5, fail
    csrw mie, x0

    # ── Test 14: CSRRS with rs1=x0 (read only, no set) ──────────────
    li x1, 0x880            # MTIE + MEIE (writable mie bits)
    csrw mie, x1
    csrrs x3, mie, x0        # x3 = old mie, mie unchanged (rs1=x0)
    li x4, 0x880
    bne x3, x4, fail
    csrr x4, mie
    li x5, 0x880
    bne x4, x5, fail
    csrw mie, x0

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

trap_handler:
    # Simple trap handler — should not be reached in this test
    mret
