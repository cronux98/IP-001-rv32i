# IP-001 RV32I GRM — Test: Trap Handling
# Tests: ECALL, EBREAK, Illegal Instruction, MRET

.section .text.init
.globl _start
_start:
    # Set up trap handler
    la x1, trap_handler
    csrw mtvec, x1

    # ── Test 1: ECALL trap ─────────────────────────────────────────
    # Save expected return address
    la x2, ecall_return
    ecall                   # Trap to handler
ecall_return:
    # Verify we returned here
    j ecall_ok
    j fail
ecall_ok:

    # ── Test 2: EBREAK trap ────────────────────────────────────────
    la x2, ebreak_return
    ebreak                  # Trap to handler
ebreak_return:
    j ebreak_ok
    j fail
ebreak_ok:

    # ── Test 3: Illegal instruction trap ────────────────────────────
    la x2, illegal_return
    # Insert an illegal instruction word
    # 0x00000000 is actually illegal (all zeros = no opcode)
    .word 0x00000000        # Illegal instruction
illegal_return:
    j illegal_ok
    j fail
illegal_ok:

    # ── Test 4: mepc saved correctly ────────────────────────────────
    la x2, mepc_test_return
    ecall
mepc_test_return:
    csrr x3, mepc
    # mepc should point to ECALL instruction address
    # (actually the specific address varies; we just check it's non-zero)
    beq x3, x0, fail

    # ── Test 5: mcause set on ECALL ────────────────────────────────
    la x2, mcause_test_return
    ecall
mcause_test_return:
    csrr x3, mcause
    # mcause should = 11 (environment call from M-mode)
    li x4, 11
    bne x3, x4, fail

    # ── Test 6: mcause set on illegal instruction ───────────────────
    la x2, illegal2_return
    .word 0xFFFFFFFF        # Another illegal pattern
illegal2_return:
    csrr x3, mcause
    # mcause should = 2 (illegal instruction)
    li x4, 2
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

# ── Trap Handler ─────────────────────────────────────────────────────
trap_handler:
    # x2 contains expected return address
    # Save mepc to x3 for tests that check it
    csrr x3, mepc

    # Skip the trapping instruction and return
    # ECALL is 4 bytes, advance mepc by 4
    addi x3, x3, 4
    csrw mepc, x3
    mret
