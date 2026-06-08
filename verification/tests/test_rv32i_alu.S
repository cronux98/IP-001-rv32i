# IP-001 RV32I Test: Register ALU + Memory + Branch + Jump
# Uses PC-relative addressing to work with any link base
# Stores results to D-mem starting at data_base for spike/rtl portability

.section .text
.globl _start

_start:
    # Initialize registers with known values
    li x1,  0x00000001    # x1 = 1
    li x2,  0x00000002    # x2 = 2
    li x3,  0x00000000    # x3 = 0
    li x4,  0xFFFFFFFF    # x4 = -1 (signed)
    li x5,  0x7FFFFFFF    # x5 = max positive signed
    li x6,  0x80000000    # x6 = min negative signed  
    li x7,  0x0000000F    # x7 = 15 (shift test)
    li x8,  0x12345678    # x8 = pattern
    li x9,  0x0F0F0F0F    # x9 = alternating

    # x10 = D-mem base (PC-relative from data_base label)
    la x10, data_base

    # === ADD ===
    add x11, x1, x2       # x11 = 1+2 = 3
    sw  x11, 0(x10)       # [data_base+0] = 3

    add x11, x1, x4       # x11 = 1 + (-1) = 0
    sw  x11, 4(x10)       # [data_base+4] = 0

    add x11, x4, x4       # x11 = (-1) + (-1) = -2
    sw  x11, 8(x10)       # [data_base+8] = -2

    # === SUB ===
    sub x11, x2, x1       # x11 = 2 - 1 = 1
    sw  x11, 12(x10)      # [data_base+12] = 1

    sub x11, x1, x2       # x11 = 1 - 2 = -1
    sw  x11, 16(x10)      # [data_base+16] = -1

    # === AND ===
    and x11, x8, x9       # x11 = 0x12345678 & 0x0F0F0F0F = 0x02040608
    sw  x11, 20(x10)      # [data_base+20]

    # === OR ===
    or  x11, x8, x9       # x11 = 0x12345678 | 0x0F0F0F0F = 0x1F3F5F7F
    sw  x11, 24(x10)      # [data_base+24]

    # === XOR ===
    xor x11, x8, x9       # x11 = 0x12345678 ^ 0x0F0F0F0F = 0x1D3B5977
    sw  x11, 28(x10)      # [data_base+28]

    # === SLL (shift left logical) ===
    sll x11, x1, x7       # x11 = 1 << 15 = 0x8000
    sw  x11, 32(x10)      # [data_base+32]

    # === SRL (shift right logical) ===
    srl x11, x6, x7       # x11 = 0x80000000 >> 15 = 0x00010000
    sw  x11, 36(x10)      # [data_base+36]

    # === SRA (shift right arithmetic) ===
    sra x11, x6, x7       # x11 = 0x80000000 >>> 15 = 0xFFFF0001
    sw  x11, 40(x10)      # [data_base+40]

    # === SLT (signed) ===
    slt x11, x4, x1       # x11 = (-1 < 1) = 1
    sw  x11, 44(x10)      # [data_base+44] = 1

    slt x11, x1, x4       # x11 = (1 < -1) = 0
    sw  x11, 48(x10)      # [data_base+48] = 0

    # === SLTU (unsigned) ===
    sltu x11, x1, x4       # x11 = (1 < 0xFFFFFFFF) = 1
    sw  x11, 52(x10)       # [data_base+52] = 1

    # === Test x0 hardwired to zero ===
    addi x0, x1, 42        # write 43 to x0 (should be suppressed)
    add  x11, x0, x0       # x11 = 0 + 0 = 0
    sw   x11, 56(x10)      # [data_base+56] = 0

    # === Test LUI ===
    lui x11, 0x12345       # x11 = 0x12345000
    sw  x11, 60(x10)       # [data_base+60]

    # === Store/Load to verify memory ===
    li x12, 0xDEADBEEF
    sw  x12, 128(x10)      # store to [data_base+128]
    lw  x13, 128(x10)      # load back
    sw  x13, 64(x10)       # [data_base+64] should be 0xDEADBEEF

    # === BRANCH tests ===
    li x14, 5
    li x15, 5
    beq x14, x15, branch_equal
    sw  x0, 68(x10)        # should be skipped
branch_equal:
    li x11, 1
    sw  x11, 68(x10)       # [data_base+68] = 1  (BEQ taken)

    bne x14, x15, branch_not_equal
    li x11, 2
    sw  x11, 72(x10)       # [data_base+72] = 2  (BNE not taken)
    j branch_done
branch_not_equal:
    sw  x0, 72(x10)

branch_done:
    li x14, 3
    li x15, 7
    blt x14, x15, blt_taken
    sw  x0, 76(x10)
    j blt_done
blt_taken:
    li x11, 3
    sw  x11, 76(x10)       # [data_base+76] = 3  (BLT taken)
blt_done:

    # === JAL test ===
    jal x16, jal_target
    li x11, 0              # should be skipped
    sw x11, 80(x10)
jal_target:
    li x11, 4
    sw  x11, 80(x10)       # [data_base+80] = 4

    # Verify x16 = return address 
    sw  x16, 84(x10)       # [data_base+84] = PC+4 of JAL

    # === JALR test ===
    la x17, jalr_target
    jalr x18, 0(x17)
    li x11, 0
    sw x11, 88(x10)
jalr_target:
    li x11, 5
    sw x11, 88(x10)        # [data_base+88] = 5
    sw x18, 92(x10)        # [data_base+92] = return address

    # === Store byte/halfword ===
    li x19, 0x12345678
    addi x20, x10, 256     # x20 = data_base + 256 (temp scratch area)
    sb  x19, 0(x20)        # store byte: scratch[0] = 0x78
    sh  x19, 2(x20)        # store half: scratch[2] = 0x5678    
    lb  x21, 0(x20)        # load signed byte 
    sw  x21, 96(x10)       # [data_base+96] should be 0x00000078
    lbu x22, 0(x20)        # load unsigned byte
    sw  x22, 100(x10)      # [data_base+100] should be 0x00000078
    lh  x23, 2(x20)
    sw  x23, 104(x10)      # [data_base+104] should be sign-extended 0x5678
    lhu x24, 2(x20)
    sw  x24, 108(x10)      # [data_base+108] should be 0x00005678

    # === Done: write test summary to output area ===
    # Magic word at data_base+1024 indicates test completion
    li x25, 0xCAFEBABE
    sw  x25, 1024(x10)    # [data_base+1024] = 0xCAFEBABE

    # Halt
halt:
    j halt

# Place data section at 0x1000 offset from wherever code is
.section .data
.globl data_base
data_base:
    .skip 4096            # Reserve 4KB for test results + scratch
