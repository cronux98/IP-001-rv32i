#!/usr/bin/env python3
"""
instruction_generator.py — Constrained-random RV32I instruction generator.

Generates valid, random RV32I instruction sequences for stress testing
the IP-001 5-stage pipeline architecture. Supports configurable:
- Instruction distribution (weighted by type)
- Hazard density (probability of RAW dependencies)
- Memory access patterns (aligned addresses within D-MEM)
- Branch target ranges (forward/backward)
- Register usage policies (no x0 writes, optional reserved registers)

Usage:
    from env.instruction_generator import InstructionGenerator
    gen = InstructionGenerator(seed=42)
    asm = gen.generate_program(num_instructions=1000)
"""

import random
import sys
from typing import List, Tuple, Set, Optional
from dataclasses import dataclass, field


# ── Instruction Encoding Helpers ──────────────────────────────────────

# R-type: funct7[7] | rs2[5] | rs1[5] | funct3[3] | rd[5] | opcode[7]
def _r_type(funct7: int, rs2: int, rs1: int, funct3: int, rd: int,
            opcode: int = 0b0110011) -> int:
    return ((funct7 & 0x7F) << 25) | ((rs2 & 0x1F) << 20) | \
           ((rs1 & 0x1F) << 15) | ((funct3 & 0x7) << 12) | \
           ((rd & 0x1F) << 7) | (opcode & 0x7F)

# I-type: imm[12] | rs1[5] | funct3[3] | rd[5] | opcode[7]
def _i_type(imm: int, rs1: int, funct3: int, rd: int,
            opcode: int = 0b0010011) -> int:
    return ((imm & 0xFFF) << 20) | ((rs1 & 0x1F) << 15) | \
           ((funct3 & 0x7) << 12) | ((rd & 0x1F) << 7) | (opcode & 0x7F)

# S-type: imm[12:5] | rs2[5] | rs1[5] | funct3[3] | imm[4:0] | opcode[7]
def _s_type(imm: int, rs2: int, rs1: int, funct3: int,
            opcode: int = 0b0100011) -> int:
    return (((imm >> 5) & 0x7F) << 25) | ((rs2 & 0x1F) << 20) | \
           ((rs1 & 0x1F) << 15) | ((funct3 & 0x7) << 12) | \
           ((imm & 0x1F) << 7) | (opcode & 0x7F)

# B-type: imm[12|10:5] | rs2[5] | rs1[5] | funct3[3] | imm[4:1|11] | opcode[7]
def _b_type(imm: int, rs2: int, rs1: int, funct3: int) -> int:
    b_imm = imm & 0x1FFE  # 13-bit signed, LSB=0
    return (((b_imm >> 12) & 1) << 31) | (((b_imm >> 5) & 0x3F) << 25) | \
           ((rs2 & 0x1F) << 20) | ((rs1 & 0x1F) << 15) | \
           ((funct3 & 0x7) << 12) | (((b_imm >> 1) & 0xF) << 8) | \
           (((b_imm >> 11) & 1) << 7) | 0b1100011

# U-type: imm[31:12] | rd[5] | opcode[7]
def _u_type(imm: int, rd: int, opcode: int) -> int:
    return (imm & 0xFFFFF000) | ((rd & 0x1F) << 7) | (opcode & 0x7F)

# J-type: imm[20|10:1|11|19:12] | rd[5] | opcode[7]
def _j_type(imm: int, rd: int) -> int:
    j_imm = imm & 0x1FFFFE  # 21-bit signed, LSB=0
    return (((j_imm >> 20) & 1) << 31) | (((j_imm >> 1) & 0x3FF) << 21) | \
           (((j_imm >> 11) & 1) << 20) | (((j_imm >> 12) & 0xFF) << 12) | \
           ((rd & 0x1F) << 7) | 0b1101111


@dataclass
class InstructionGenerator:
    """Constrained-random RV32I instruction generator.

    Generates valid instruction sequences with configurable properties:
    - Instruction type distribution
    - Register usage policies
    - Memory address ranges
    - Hazard density
    - Branch patterns
    """

    seed: int = 42
    num_instructions: int = 1000
    dmem_base: int = 0x8000_1000
    dmem_size: int = 0x1000

    # Instruction type weights (sum = 100)
    weight_alu: int = 40       # R-type + I-type ALU
    weight_load: int = 15
    weight_store: int = 10
    weight_branch: int = 15
    weight_jump: int = 5
    weight_csr: int = 5
    weight_system: int = 5
    weight_nop: int = 5

    # Hazard density: probability that a new instruction depends on recent result
    hazard_density: float = 0.60

    # Optional reserved registers (not written by generator)
    reserved_registers: Set[int] = field(default_factory=lambda: {0, 2})  # x0, x2(sp)

    def _post_init_(self):
        pass

    def __post_init__(self):
        pass

    def __init__(self, seed: int = 42, num_instructions: int = 1000):
        self.seed = seed
        self.num_instructions = num_instructions
        self.dmem_base = 0x8000_1000
        self.dmem_size = 0x1000
        self.weight_alu = 40
        self.weight_load = 15
        self.weight_store = 10
        self.weight_branch = 15
        self.weight_jump = 5
        self.weight_csr = 5
        self.weight_system = 5
        self.weight_nop = 5
        self.hazard_density = 0.60
        self.reserved_registers = {0, 2}  # x0, x2(sp)

        self._rng = random.Random(seed)
        self._recent_writes: List[Tuple[int, int]] = []  # [(rd, value), ...]
        self._allocated_regs: Set[int] = set()
        self._used_labels: int = 0

    def reset(self):
        """Reset generator state."""
        self._rng = random.Random(self.seed)
        self._recent_writes = []
        self._allocated_regs = set()
        self._used_labels = 0

    def _alloc_reg(self, avoid: Set[int] = None) -> int:
        """Allocate a free writable register."""
        avoid_set = self.reserved_registers | {0}
        if avoid:
            avoid_set |= avoid
        candidates = [r for r in range(1, 32) if r not in avoid_set]
        if not candidates:
            # Fall back to any non-reserved, non-zero register
            candidates = [r for r in range(1, 32) if r not in self.reserved_registers]
        return self._rng.choice(candidates)

    def _random_reg(self, avoid: Set[int] = None) -> int:
        """Pick a random register, optionally avoiding certain registers."""
        avoid_set = {0}  # Always avoid x0 for source unless explicitly used
        if avoid:
            avoid_set |= avoid
        candidates = [r for r in range(1, 32) if r not in avoid_set]
        if not candidates:
            candidates = list(range(32))  # fallback
        return self._rng.choice(candidates)

    def _random_imm12(self) -> int:
        """Generate a random 12-bit signed immediate."""
        return self._rng.randint(-2048, 2047)

    def _random_imm_small(self) -> int:
        """Generate a small immediate (common values)."""
        choices = [0, 1, 2, 4, 8, 16, 32, -1, -4, -8, 255, 0x100]
        if self._rng.random() < 0.7:
            return self._rng.choice(choices)
        return self._rng.randint(-128, 127)

    def _random_shift_amount(self) -> int:
        """Generate shift amount (0-31)."""
        return self._rng.randint(0, 31)

    def _generate_alu_r(self) -> int:
        """Generate a random R-type ALU instruction."""
        funct3_ops = [
            (0, 0x00, "ADD"), (0, 0x20, "SUB"),
            (1, 0x00, "SLL"), (2, 0x00, "SLT"),
            (3, 0x00, "SLTU"), (4, 0x00, "XOR"),
            (5, 0x00, "SRL"), (5, 0x20, "SRA"),
            (6, 0x00, "OR"), (7, 0x00, "AND"),
        ]
        funct3, funct7, _ = self._rng.choice(funct3_ops)
        rd = self._alloc_reg()
        rs1 = self._random_reg()
        rs2 = self._random_reg({rd} if rd == rs1 else None)

        # Maybe depend on recent write for hazard density
        if self._recent_writes and self._rng.random() < self.hazard_density:
            recent_rd, _ = self._rng.choice(self._recent_writes[-3:])
            if recent_rd not in self.reserved_registers and recent_rd != 0:
                rs1 = recent_rd
        if self._recent_writes and self._rng.random() < self.hazard_density * 0.5:
            recent_rd, _ = self._rng.choice(self._recent_writes[-3:])
            if recent_rd not in self.reserved_registers and recent_rd != 0:
                rs2 = recent_rd

        self._recent_writes.append((rd, 0))
        if len(self._recent_writes) > 10:
            self._recent_writes.pop(0)

        return _r_type(funct7, rs2, rs1, funct3, rd)

    def _generate_alu_i(self) -> int:
        """Generate a random I-type ALU instruction."""
        choices = [
            (0, "ADDI"), (2, "SLTI"), (3, "SLTIU"),
            (4, "XORI"), (6, "ORI"), (7, "ANDI"),
        ]

        if self._rng.random() < 0.3:
            # Shift immediate
            funct3 = self._rng.choice([1, 5])  # SLLI or SRLI/SRAI
            if funct3 == 1:
                imm = self._rng.randint(0, 31)
                funct7_bit = 0
            else:
                if self._rng.random() < 0.5:
                    imm = self._rng.randint(0, 31)
                    funct7_bit = 0  # SRLI
                else:
                    imm = self._rng.randint(0, 31)
                    funct7_bit = 1  # SRAI
            rd = self._alloc_reg()
            rs1 = self._random_reg()
            return ((funct7_bit << 30) | ((imm & 0x1F) << 20) |
                    ((rs1 & 0x1F) << 15) | ((funct3 & 0x7) << 12) |
                    ((rd & 0x1F) << 7) | 0b0010011)

        funct3, _ = self._rng.choice(choices)
        rd = self._alloc_reg()
        rs1 = self._random_reg()
        imm = self._random_imm12()

        if self._recent_writes and self._rng.random() < self.hazard_density:
            recent_rd, _ = self._rng.choice(self._recent_writes[-3:])
            if recent_rd not in self.reserved_registers and recent_rd != 0:
                rs1 = recent_rd

        self._recent_writes.append((rd, 0))
        if len(self._recent_writes) > 10:
            self._recent_writes.pop(0)

        return _i_type(imm, rs1, funct3, rd)

    def _generate_load(self) -> int:
        """Generate a random load instruction."""
        funct3 = self._rng.choice([0, 1, 2, 4, 5])  # LB, LH, LW, LBU, LHU
        rd = self._alloc_reg()
        rs1 = self._random_reg()  # base address register
        offset = self._rng.randint(0, min(2047, self.dmem_size - 4)) & ~3

        self._recent_writes.append((rd, 0))
        if len(self._recent_writes) > 10:
            self._recent_writes.pop(0)

        return _i_type(offset, rs1, funct3, rd, opcode=0b0000011)

    def _generate_store(self) -> int:
        """Generate a random store instruction."""
        funct3 = self._rng.choice([0, 1, 2])  # SB, SH, SW
        rs1 = self._random_reg()  # base address
        rs2 = self._random_reg()  # data to store
        offset = self._rng.randint(0, min(2047, self.dmem_size - 4)) & ~3

        return _s_type(offset, rs2, rs1, funct3)

    def _generate_branch(self) -> int:
        """Generate a random branch instruction."""
        funct3 = self._rng.choice([0, 1, 4, 5, 6, 7])  # All 6 branch types
        rs1 = self._random_reg()
        rs2 = self._random_reg({rs1} if self._rng.random() < 0.3 else None)

        # Branch targets: small forward offset (8-64 bytes, 2-16 instructions)
        offset = self._rng.randint(2, 16) * 4

        return _b_type(offset, rs2, rs1, funct3)

    def _generate_lui(self) -> int:
        """Generate LUI instruction."""
        rd = self._alloc_reg()
        imm = self._rng.randint(0, 0xFFFFF) << 12
        return _u_type(imm, rd, 0b0110111)

    def _generate_auipc(self) -> int:
        """Generate AUIPC instruction."""
        rd = self._alloc_reg()
        imm = self._rng.randint(0, 0xFFFFF) << 12
        return _u_type(imm, rd, 0b0010111)

    def _generate_jal(self) -> int:
        """Generate JAL instruction."""
        rd = self._rng.choice([0, 1, 5])  # Often x0 or x1(ra)
        offset = self._rng.randint(1, 32) * 4
        return _j_type(offset, rd)

    def _generate_jalr(self) -> int:
        """Generate JALR instruction."""
        rd = self._rng.choice([0, 1])
        rs1 = self._random_reg()
        offset = self._rng.randint(0, 2047) & ~1  # Aligned
        return _i_type(offset, rs1, 0, rd, opcode=0b1100111)

    def _generate_csr(self) -> int:
        """Generate random CSR instruction."""
        csr_addrs = [0x300, 0x301, 0x304, 0x305, 0x341, 0x342, 0x344]
        csr_addr = self._rng.choice(csr_addrs)
        funct3 = self._rng.choice([1, 2, 3, 5, 6, 7])  # All 6 CSR variants
        rd = self._alloc_reg()
        rs1 = self._random_reg()

        if funct3 in (5, 6, 7):  # Immediate variants: rs1 field is uimm
            rs1 = self._rng.randint(0, 31)
        elif funct3 in (2, 3) and self._rng.random() < 0.3:  # RS/RC with x0 = no-op
            rs1 = 0  # Read without modify

        return ((csr_addr & 0xFFF) << 20) | ((rs1 & 0x1F) << 15) | \
               ((funct3 & 0x7) << 12) | ((rd & 0x1F) << 7) | 0b1110011

    def _generate_nop(self) -> int:
        """Generate a NOP (ADDI x0, x0, 0)."""
        return _i_type(0, 0, 0, 0, 0b0010011)

    def _pick_instruction_type(self) -> str:
        """Randomly pick an instruction type based on weights."""
        total = (self.weight_alu + self.weight_load + self.weight_store +
                 self.weight_branch + self.weight_jump + self.weight_csr +
                 self.weight_system + self.weight_nop)
        r = self._rng.randint(0, total - 1)

        cum = 0
        cum += self.weight_alu
        if r < cum: return "ALU"
        cum += self.weight_load
        if r < cum: return "LOAD"
        cum += self.weight_store
        if r < cum: return "STORE"
        cum += self.weight_branch
        if r < cum: return "BRANCH"
        cum += self.weight_jump
        if r < cum: return "JUMP"
        cum += self.weight_csr
        if r < cum: return "CSR"
        cum += self.weight_system
        if r < cum: return "SYSTEM"
        return "NOP"

    def generate_instruction(self) -> int:
        """Generate a single random RV32I instruction word."""
        instype = self._pick_instruction_type()

        if instype == "ALU":
            if self._rng.random() < 0.5:
                return self._generate_alu_r()
            else:
                return self._generate_alu_i()
        elif instype == "LOAD":
            return self._generate_load()
        elif instype == "STORE":
            return self._generate_store()
        elif instype == "BRANCH":
            return self._generate_branch()
        elif instype == "JUMP":
            if self._rng.random() < 0.5:
                return self._generate_jal()
            else:
                return self._generate_jalr()
        elif instype == "CSR":
            return self._generate_csr()
        elif instype == "SYSTEM":
            # NOP for system at random stream level
            return self._generate_nop()
        else:
            return self._generate_nop()

    def generate_instruction_words(self, count: int = None) -> List[int]:
        """Generate a list of random instruction words.

        Args:
            count: Number of instructions (default: self.num_instructions)

        Returns:
            List of 32-bit instruction words
        """
        if count is None:
            count = self.num_instructions
        self.reset()
        return [self.generate_instruction() for _ in range(count)]

    def generate_asm_program(self, count: int = None,
                             init_regs: bool = True) -> str:
        """Generate a complete assembly program with initialization.

        Args:
            count: Number of random instructions
            init_regs: If True, add register initialization before random seq

        Returns:
            RISC-V assembly source string
        """
        if count is None:
            count = self.num_instructions
        self.reset()

        lines = [
            ".section .text",
            ".globl _start",
            "_start:",
        ]

        # Initialize some registers with known values for interesting behavior
        if init_regs:
            init_values = [
                (3, 0x00000000),   # x3 = 0
                (4, 0x00000001),   # x4 = 1
                (5, 0xFFFFFFFF),   # x5 = -1
                (6, 0x7FFFFFFF),   # x6 = max positive
                (7, 0x80000000),   # x7 = min negative
                (8, 0x00000010),   # x8 = 16
                (9, 0xDEADBEEF),   # x9 = deadbeef
                (10, self.dmem_base + 0x100),  # x10 = data pointer
            ]
            for reg, val in init_values:
                if val == 0:
                    lines.append(f"    addi x{reg}, x0, 0")
                elif -2048 <= val <= 2047:
                    lines.append(f"    addi x{reg}, x0, {val}")
                else:
                    # Load upper + add immediate
                    upper = (val + 0x800) >> 12
                    lower = val & 0xFFF
                    if lower >= 0x800:
                        lower -= 0x1000
                        upper += 1
                    lines.append(f"    lui x{reg}, {upper}")
                    if lower != 0:
                        lines.append(f"    addi x{reg}, x{reg}, {lower}")

        # Generate random instructions
        for _ in range(count):
            word = self.generate_instruction()
            self._used_labels += 1  # Track for potential branch targets
            lines.append(f"    .word 0x{word:08X}")

        # Exit sequence
        lines.append("    # Exit: write 1 to tohost")
        lines.append(f"    li a0, 1")
        lines.append(f"    sw a0, 0(x0)  # This will fault in Spike, marking completion")
        lines.append("")
        return "\n".join(lines)

    def generate_asm_with_hazards(self, hazard_types: List[str] = None,
                                  num_each: int = 5) -> str:
        """Generate assembly targeting specific hazard types.

        Args:
            hazard_types: List of hazard types to generate
                ["RAW_ALU_ALU", "LOAD_USE", "BRANCH", "STORE_AFTER_LOAD", ...]
            num_each: Number of instances of each hazard type

        Returns:
            RISC-V assembly source
        """
        lines = [
            ".section .text",
            ".globl _start",
            "_start:",
            "    # Initialize registers",
            "    addi x3, x0, 1",
            "    addi x4, x0, 2",
            "    addi x5, x0, 3",
            "    addi x6, x0, 100",
        ]

        if hazard_types is None:
            hazard_types = ["RAW_ALU_ALU", "LOAD_USE", "BRANCH"]

        for htype in hazard_types:
            lines.append(f"    # === {htype} hazards ===")
            for i in range(num_each):
                if htype == "RAW_ALU_ALU":
                    blocks = [
                        ("    addi x10, x3, 1\n    add x11, x10, x4\n    addi x0, x0, 0", "ALU→ALU forward (rs1)"),
                        ("    addi x10, x3, 2\n    add x11, x4, x10\n    addi x0, x0, 0", "ALU→ALU forward (rs2)"),
                        ("    addi x10, x3, 5\n    addi x10, x10, 1\n    add x11, x10, x4\n    addi x0, x0, 0", "EX/MEM priority"),
                    ]
                    block, comment = blocks[i % len(blocks)]
                    lines.append(f"    # {comment}")
                    lines.append(block)

                elif htype == "LOAD_USE":
                    lines.append(f"    # Load-use hazard #{i}")
                    lines.append(f"    sw x3, 0(x10)")
                    lines.append(f"    lw x12, 0(x10)")
                    lines.append(f"    add x13, x12, x4  # RAW: LW→ADD, needs stall")
                    lines.append(f"    addi x0, x0, 0")

                elif htype == "BRANCH":
                    lines.append(f"    # Branch hazard #{i}")
                    lines.append(f"    beq x3, x3, 1f")
                    lines.append(f"    addi x0, x0, 0  # Not taken path (NOP)")
                    lines.append(f"1:  addi x14, x14, 1  # Taken path")
                    lines.append(f"    addi x0, x0, 0")

                elif htype == "STORE_AFTER_LOAD":
                    lines.append(f"    sw x3, 0(x10)")
                    lines.append(f"    lw x12, 0(x10)")
                    lines.append(f"    sw x12, 4(x10)  # Store-after-load, no stall")
                    lines.append(f"    addi x0, x0, 0")

        lines.append(f"    # Done — store result to memory")
        lines.append(f"    sw x3, 0(x10)")
        lines.append("")
        return "\n".join(lines)


# Convenience
def generate_random_instructions(count: int = 1000, seed: int = 42) -> List[int]:
    """Quick helper: generate random instruction words."""
    gen = InstructionGenerator(seed=seed, num_instructions=count)
    return gen.generate_instruction_words(count)
