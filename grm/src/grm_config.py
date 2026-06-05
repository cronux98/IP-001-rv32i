#!/usr/bin/env python3
"""
grm_config.py — GRM platform configuration for IP-001 RV32I Core.

Defines memory map, CSR addresses, reset values, and toolchain paths.
Matches microarchitecture specification exactly.

Author: Sage (GRM Engineer)
Date: 2026-06-05
Project: IP-001 — RV32I 5-Stage Pipeline Core
"""

from dataclasses import dataclass, field
from typing import Dict

@dataclass
class GRMConfig:
    """Platform configuration for the RV32I 5-stage pipeline core GRM."""

    # ── Memory Map (must match microarchitecture §3) ──────────────────
    # NOTE: Spike has a built-in HTIF debug device at 0x0-0x1000.
    # GRM test binaries are linked at 0x80000000 (Spike default memory).
    # The DUT uses 0x00000000 per microarch spec; GRM comparison handles
    # this offset transparently.
    IMEM_BASE: int = 0x8000_0000    # Instruction memory base (Spike-compatible)
    IMEM_SIZE: int = 0x1000          # 4 KB instruction memory
    DMEM_BASE: int = 0x8000_1000    # Data memory base (Spike-compatible)
    DMEM_SIZE: int = 0x1000          # 4 KB data memory
    TOTAL_MEM: int = 0x2000          # 8 KB total

    # ── DUT Memory Map (actual hardware addresses) ───────────────────
    DUT_IMEM_BASE: int = 0x0000_0000
    DUT_DMEM_BASE: int = 0x0000_1000

    # ── Reset Configuration ──────────────────────────────────────────
    RESET_VECTOR: int = 0x8000_0000
    RESET_PC: int = 0x8000_0000

    # ── CSR Addresses (RISC-V Privileged Spec v1.12) ─────────────────
    # These must match the csr_block module spec §4
    CSR_MSTATUS: int = 0x300    # Machine Status Register
    CSR_MISA: int = 0x301       # Machine ISA Register
    CSR_MIE: int = 0x304        # Machine Interrupt Enable
    CSR_MTVEC: int = 0x305      # Machine Trap Vector Base Address
    CSR_MSCRATCH: int = 0x340   # Machine Scratch (not implemented, but tracked)
    CSR_MEPC: int = 0x341       # Machine Exception PC
    CSR_MCAUSE: int = 0x342     # Machine Cause Register
    CSR_MTVAL: int = 0x343      # Machine Trap Value (not implemented, but tracked)
    CSR_MIP: int = 0x344        # Machine Interrupt Pending
    CSR_MCYCLE: int = 0xB00     # Machine Cycle Counter (not implemented)
    CSR_MINSTRET: int = 0xB02   # Machine Instructions Retired (not implemented)

    # Our implemented CSR subset
    IMPLEMENTED_CSRS: tuple = (0x300, 0x301, 0x304, 0x305, 0x341, 0x342, 0x344)

    # ── CSR Reset Values (must match microarchitecture §4.3) ──────────
    CSR_RESET: Dict[int, int] = field(default_factory=lambda: {
        0x300: 0x0000_0000,    # mstatus: MIE=0, MPIE=0, all others 0
        0x301: 0x4000_0100,    # misa: MXL=1 (RV32), Extensions=0 (RV32I only)
        0x304: 0x0000_0000,    # mie: all interrupts disabled
        0x305: 0x0000_0000,    # mtvec: direct mode, base=0
        0x341: 0x0000_0000,    # mepc: undefined until first trap
        0x342: 0x0000_0000,    # mcause: undefined until first trap
        0x344: 0x0000_0000,    # mip: no interrupts pending
    })

    # ── mstatus bit fields (microarchitecture §4.2 of csr_block.md) ──
    MSTATUS_MIE_MASK: int = 0x00000008     # bit 3
    MSTATUS_MPIE_MASK: int = 0x00000080    # bit 7
    MSTATUS_MPP_MASK: int = 0x00001800     # bits 12:11 (not implemented in M-mode only)

    # ── mie bit fields ──────────────────────────────────────────────
    MIE_MTIE_MASK: int = 0x00000080        # bit 7: Machine Timer Interrupt Enable
    MIE_MEIE_MASK: int = 0x00000800        # bit 11: Machine External Interrupt Enable

    # ── mcause trap codes (microarchitecture §5 of csr_block.md) ────
    MCAUSE_EXC_ILLEGAL_INSTR: int = 2
    MCAUSE_EXC_BREAKPOINT: int = 3
    MCAUSE_EXC_MISALIGNED_LOAD: int = 4
    MCAUSE_EXC_MISALIGNED_STORE: int = 6
    MCAUSE_EXC_ECALL_M: int = 11
    MCAUSE_IRQ_TIMER: int = 0x80000007     # bit 31 set + code 7
    MCAUSE_IRQ_EXTERNAL: int = 0x8000000B  # bit 31 set + code 11

    # ── Spike Configuration ─────────────────────────────────────────
    SPIKE_BINARY: str = "spike"
    SPIKE_ISA: str = "rv32i"
    SPIKE_PRIV: str = "m"

    # ── RISC-V GNU Toolchain ────────────────────────────────────────
    RISCV_GCC: str = "riscv64-unknown-elf-gcc"
    RISCV_OBJCOPY: str = "riscv64-unknown-elf-objcopy"
    RISCV_OBJDUMP: str = "riscv64-unknown-elf-objdump"
    RISCV_AS: str = "riscv64-unknown-elf-as"
    RISCV_LD: str = "riscv64-unknown-elf-ld"

    # ── Build Flags ─────────────────────────────────────────────────
    GCC_FLAGS: tuple = ("-march=rv32i", "-mabi=ilp32", "-nostdlib",
                        "-nostartfiles", "-static", "-O0", "-g")
    LD_FLAGS: tuple = ("-melf32lriscv", "-nostdlib")

    # ── Register Names ──────────────────────────────────────────────
    REG_NAMES: tuple = (
        "zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2",
        "s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5",
        "a6", "a7", "s2", "s3", "s4", "s5", "s6", "s7",
        "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6"
    )

    # ── RV32I Opcode Classification (for instruction analysis) ─────
    # opcode[6:0] → instruction class
    OPCODE_LUI: int = 0b0110111
    OPCODE_AUIPC: int = 0b0010111
    OPCODE_JAL: int = 0b1101111
    OPCODE_JALR: int = 0b1100111
    OPCODE_BRANCH: int = 0b1100011
    OPCODE_LOAD: int = 0b0000011
    OPCODE_STORE: int = 0b0100011
    OPCODE_ALUI: int = 0b0010011      # I-type ALU
    OPCODE_ALU: int = 0b0110011       # R-type ALU
    OPCODE_FENCE: int = 0b0001111
    OPCODE_SYSTEM: int = 0b1110011

    # MRET instruction encoding (for detection)
    MRET_ENCODING: int = 0x30200073

    @staticmethod
    def get_csr_name(addr: int) -> str:
        """Return human-readable CSR name for an address."""
        csr_names = {
            0x300: "mstatus", 0x301: "misa", 0x304: "mie",
            0x305: "mtvec", 0x340: "mscratch", 0x341: "mepc",
            0x342: "mcause", 0x343: "mtval", 0x344: "mip",
            0xB00: "mcycle", 0xB02: "minstret",
        }
        return csr_names.get(addr, f"csr_0x{addr:03X}")

    @staticmethod
    def get_reg_name(reg_num: int) -> str:
        """Return ABI register name for register number."""
        names = GRMConfig.REG_NAMES
        if 0 <= reg_num < 32:
            return names[reg_num]
        return f"x{reg_num}"

    def is_implemented_csr(self, addr: int) -> bool:
        """Check if a CSR address is in our implemented subset."""
        return addr in self.IMPLEMENTED_CSRS

    def get_spike_memory_args(self) -> str:
        """Build Spike -m argument for memory regions.
        
        Uses simple size form: -m0x2000 gives 8KB at Spike's default
        memory base (0x80000000). Test binaries must be linked at 0x80000000.
        
        Note: This Spike version requires -m<val> with NO space.
        """
        return f"-m0x{self.TOTAL_MEM:x}"


# Singleton instance for easy import
config = GRMConfig()
