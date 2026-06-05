#!/usr/bin/env python3
"""
pipeline_monitor.py — Pipeline behavior analysis for IP-001 RV32I.

Analyzes instruction streams to detect:
- RAW (Read-After-Write) hazards of all types
- Load-use dependencies requiring stalls
- Forwarding opportunities
- Branch/jump patterns
- Sequences that trigger pipeline events (stall, flush)

This is a static analysis tool — it reads instruction streams and
predicts pipeline behavior without executing them.

Usage:
    from env.pipeline_monitor import PipelineMonitor
    pm = PipelineMonitor()
    hazards = pm.analyze_instruction_stream(instructions)
"""

from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field
from enum import Enum


# ── Instruction Decoding Helpers ──────────────────────────────────────

# RV32I opcode map
OPCODES = {
    0b0110111: "LUI",
    0b0010111: "AUIPC",
    0b1101111: "JAL",
    0b1100111: "JALR",
    0b1100011: "BRANCH",
    0b0000011: "LOAD",
    0b0100011: "STORE",
    0b0010011: "ALUI",
    0b0110011: "ALU",
    0b0001111: "FENCE",
    0b1110011: "SYSTEM",
}

# funct3 decode for loads
LOAD_FUNCT3 = {0: "LB", 1: "LH", 2: "LW", 4: "LBU", 5: "LHU"}

# funct3 decode for stores
STORE_FUNCT3 = {0: "SB", 1: "SH", 2: "SW"}

# funct3 decode for branches
BRANCH_FUNCT3 = {0: "BEQ", 1: "BNE", 4: "BLT", 5: "BGE", 6: "BLTU", 7: "BGEU"}


@dataclass
class DecodedInstr:
    """Decoded RV32I instruction."""

    word: int
    opcode: int
    rd: int
    rs1: int
    rs2: int
    funct3: int
    funct7: int
    immediate: int  # 32-bit sign-extended immediate
    mnemonic: str
    is_load: bool
    is_store: bool
    is_branch: bool
    is_jump: bool
    is_jal: bool
    is_jalr: bool
    is_alu_r: bool       # R-type ALU
    is_alu_i: bool       # I-type ALU
    is_csr: bool
    is_system: bool      # ECALL, EBREAK, MRET
    writes_rd: bool      # Does this instruction write to rd?
    uses_rs1: bool       # Does it read rs1?
    uses_rs2: bool       # Does it read rs2?

    @staticmethod
    def decode(word: int) -> 'DecodedInstr':
        """Decode a 32-bit RV32I instruction word."""
        opcode = word & 0x7F
        rd = (word >> 7) & 0x1F
        funct3 = (word >> 12) & 0x7
        rs1 = (word >> 15) & 0x1F
        rs2 = (word >> 20) & 0x1F
        funct7 = (word >> 25) & 0x7F

        # Extract immediate
        imm_i = _sign_extend((word >> 20) & 0xFFF, 12)
        imm_s = _sign_extend(((word >> 25) << 5) | ((word >> 7) & 0x1F), 12)
        imm_b = _sign_extend(
            ((word >> 31) << 12) | (((word >> 7) & 1) << 11) |
            (((word >> 25) & 0x3F) << 5) | (((word >> 8) & 0xF) << 1), 13
        )
        imm_u = (word & 0xFFFFF000)
        imm_j = _sign_extend(
            ((word >> 31) << 20) | (((word >> 12) & 0xFF) << 12) |
            (((word >> 20) & 1) << 11) | (((word >> 21) & 0x3FF) << 1), 21
        )

        is_load = opcode == 0b0000011
        is_store = opcode == 0b0100011
        is_branch = opcode == 0b1100011
        is_jal = opcode == 0b1101111
        is_jalr = opcode == 0b1100111
        is_jump = is_jal or is_jalr
        is_alu_r = opcode == 0b0110011
        is_alu_i = opcode == 0b0010011
        is_csr = opcode == 0b1110011 and funct3 != 0
        is_system = opcode == 0b1110011 and funct3 == 0
        is_lui = opcode == 0b0110111
        is_auipc = opcode == 0b0010111
        is_fence = opcode == 0b0001111

        # Determine if rd is written
        writes_rd = (is_alu_r or is_alu_i or is_load or is_jal or is_jalr or
                     is_lui or is_auipc or is_csr) and rd != 0

        # Determine if rs1/rs2 are used
        uses_rs1 = not (is_lui or is_auipc or is_jal or is_fence)
        uses_rs2 = is_alu_r or is_branch or is_store

        # Determine immediate
        if is_lui or is_auipc:
            immediate = imm_u
        elif is_jal:
            immediate = imm_j
        elif is_branch:
            immediate = imm_b
        elif is_store:
            immediate = imm_s
        else:
            immediate = imm_i

        # Mnemonic
        mnemonic = _get_mnemonic(opcode, funct3, funct7, is_system, word)

        return DecodedInstr(
            word=word, opcode=opcode, rd=rd, rs1=rs1, rs2=rs2,
            funct3=funct3, funct7=funct7, immediate=immediate,
            mnemonic=mnemonic, is_load=is_load, is_store=is_store,
            is_branch=is_branch, is_jump=is_jump, is_jal=is_jal,
            is_jalr=is_jalr, is_alu_r=is_alu_r, is_alu_i=is_alu_i,
            is_csr=is_csr, is_system=is_system, writes_rd=writes_rd,
            uses_rs1=uses_rs1, uses_rs2=uses_rs2,
        )


def _sign_extend(value: int, bits: int) -> int:
    """Sign-extend a value to 32 bits."""
    sign_bit = 1 << (bits - 1)
    return (value & (sign_bit - 1)) - (value & sign_bit)


def _get_mnemonic(opcode: int, funct3: int, funct7: int,
                   is_system: bool, word: int) -> str:
    """Get instruction mnemonic from opcode/funct3/funct7."""
    if opcode == 0b0110111: return "LUI"
    if opcode == 0b0010111: return "AUIPC"
    if opcode == 0b1101111: return "JAL"
    if opcode == 0b1100111: return "JALR"
    if opcode == 0b1100011: return BRANCH_FUNCT3.get(funct3, "???")
    if opcode == 0b0000011: return LOAD_FUNCT3.get(funct3, "???")
    if opcode == 0b0100011: return STORE_FUNCT3.get(funct3, "???")
    if opcode == 0b0001111: return "FENCE"
    if opcode == 0b1110011:
        if is_system:
            # ECALL / EBREAK / MRET
            imm12 = (word >> 20) & 0xFFF
            if imm12 == 0: return "ECALL"
            if imm12 == 1: return "EBREAK"
            if word == 0x30200073: return "MRET"
            return "SYSTEM"
        else:
            return {1: "CSRRW", 2: "CSRRS", 3: "CSRRC",
                    5: "CSRRWI", 6: "CSRRSI", 7: "CSRRCI"}.get(funct3, "CSR???")
    if opcode == 0b0010011:
        if funct3 == 0: return "ADDI"
        if funct3 == 1: return "SLLI"
        if funct3 == 2: return "SLTI"
        if funct3 == 3: return "SLTIU"
        if funct3 == 4: return "XORI"
        if funct3 == 5: return ("SRAI" if (funct7 >> 5) else "SRLI")
        if funct3 == 6: return "ORI"
        if funct3 == 7: return "ANDI"
    if opcode == 0b0110011:
        if funct3 == 0: return ("SUB" if (funct7 >> 5) else "ADD")
        if funct3 == 1: return "SLL"
        if funct3 == 2: return "SLT"
        if funct3 == 3: return "SLTU"
        if funct3 == 4: return "XOR"
        if funct3 == 5: return ("SRA" if (funct7 >> 5) else "SRL")
        if funct3 == 6: return "OR"
        if funct3 == 7: return "AND"
    return "???"


# ── Hazard Detection ─────────────────────────────────────────────────

@dataclass
class HazardInfo:
    """Information about a detected hazard."""

    producer_idx: int      # Index of producing instruction
    consumer_idx: int      # Index of consuming instruction
    producer_rd: int       # Register being produced
    hazard_type: str       # "RAW_ALU_ALU", "RAW_LOAD_ALU", "RAW_ALU_STORE", etc.
    needs_stall: bool      # Does this hazard require a stall?
    forwarding_possible: bool  # Can forwarding resolve this?
    forwarding_path: str   # Which forwarding path: "EXMEM", "MEMWB", "NONE"


@dataclass
class PipelineMonitor:
    """Static analysis of pipeline behavior for instruction streams.

    Analyzes sequences of instructions without executing them to predict:
    - Where stalls are needed (load-use)
    - Where forwarding resolves hazards
    - Branch/jump flush patterns
    """

    hazards_detected: List[HazardInfo] = field(default_factory=list)
    load_use_stalls: int = 0
    forwarding_opportunities: int = 0
    alu_alu_hazards: int = 0
    load_alu_hazards: int = 0
    branch_patterns: int = 0
    store_after_load: int = 0

    def analyze_stream(self, instructions: List[DecodedInstr]) -> List[HazardInfo]:
        """Analyze an instruction stream for pipeline hazards.

        For 5-stage pipeline:
        - Instr in EX stage: look back 1 (producer in MEM/EX boundary)
          → RAW from instr at i-1 (EX/MEM forwarding needed)
        - Instr in EX stage: look back 2 (producer in WB/MEM boundary)
          → RAW from instr at i-2 (MEM/WB forwarding needed)
        - Instr in EX stage: if producer at i-1 is LOAD
          → Load-use stall needed

        Returns list of HazardInfo objects.
        """
        self.hazards_detected = []
        self.load_use_stalls = 0
        self.forwarding_opportunities = 0
        self.alu_alu_hazards = 0
        self.load_alu_hazards = 0
        self.store_after_load = 0

        for i, instr in enumerate(instructions):
            if not instr.uses_rs1 and not instr.uses_rs2:
                continue

            # Check producer at i-1 (EX/MEM boundary)
            if i >= 1:
                producer = instructions[i - 1]
                if producer.writes_rd and producer.rd != 0:
                    # Check rs1 dependency
                    if instr.uses_rs1 and producer.rd == instr.rs1:
                        htype = "RAW_LOAD_ALU" if producer.is_load else "RAW_ALU_ALU"
                        needs_stall = producer.is_load
                        fwd_path = "NONE" if producer.is_load else "EXMEM"
                        haz = HazardInfo(
                            producer_idx=i-1, consumer_idx=i,
                            producer_rd=producer.rd,
                            hazard_type=htype,
                            needs_stall=needs_stall,
                            forwarding_possible=not producer.is_load,
                            forwarding_path=fwd_path,
                        )
                        self.hazards_detected.append(haz)
                        if needs_stall:
                            self.load_use_stalls += 1
                            self.load_alu_hazards += 1
                        else:
                            self.forwarding_opportunities += 1
                            self.alu_alu_hazards += 1

                    # Check rs2 dependency
                    if instr.uses_rs2 and producer.rd == instr.rs2:
                        if instr.is_store:
                            htype = "RAW_STORE_DATA"
                            needs_stall = False  # forwarding handles it
                        else:
                            htype = "RAW_LOAD_ALU" if producer.is_load else "RAW_ALU_ALU"
                            needs_stall = producer.is_load
                        fwd_path = "NONE" if producer.is_load else "EXMEM"
                        haz = HazardInfo(
                            producer_idx=i-1, consumer_idx=i,
                            producer_rd=producer.rd,
                            hazard_type=htype,
                            needs_stall=needs_stall,
                            forwarding_possible=not producer.is_load,
                            forwarding_path=fwd_path,
                        )
                        # Avoid double-counting same producer→consumer pair
                        if not any(h.producer_idx == i-1 and h.consumer_idx == i
                                  and h.producer_rd == producer.rd
                                  for h in self.hazards_detected):
                            self.hazards_detected.append(haz)
                            if instr.is_store:
                                self.store_after_load += 1
                            elif needs_stall:
                                self.load_use_stalls += 1
                                self.load_alu_hazards += 1
                            else:
                                self.forwarding_opportunities += 1
                                self.alu_alu_hazards += 1

            # Check producer at i-2 (MEM/WB boundary)
            if i >= 2:
                producer = instructions[i - 2]
                # Only if i-1 doesn't also write same register (EX/MEM priority)
                if producer.writes_rd and producer.rd != 0:
                    prev_producer = instructions[i - 1]
                    if prev_producer.writes_rd and prev_producer.rd == producer.rd:
                        continue  # i-1 writes same reg, i-2 value is stale

                    if instr.uses_rs1 and producer.rd == instr.rs1:
                        fwd_path = "MEMWB"
                        haz = HazardInfo(
                            producer_idx=i-2, consumer_idx=i,
                            producer_rd=producer.rd,
                            hazard_type="RAW_ALU_ALU_MEMWB",
                            needs_stall=False,
                            forwarding_possible=True,
                            forwarding_path=fwd_path,
                        )
                        self.hazards_detected.append(haz)
                        self.forwarding_opportunities += 1

                    if instr.uses_rs2 and producer.rd == instr.rs2:
                        if not any(h.producer_idx == i-2 and h.consumer_idx == i
                                  and h.producer_rd == producer.rd
                                  for h in self.hazards_detected):
                            haz = HazardInfo(
                                producer_idx=i-2, consumer_idx=i,
                                producer_rd=producer.rd,
                                hazard_type="RAW_STORE_DATA_MEMWB" if instr.is_store
                                else "RAW_ALU_ALU_MEMWB",
                                needs_stall=False,
                                forwarding_possible=True,
                                forwarding_path="MEMWB",
                            )
                            self.hazards_detected.append(haz)
                            self.forwarding_opportunities += 1

        return self.hazards_detected

    def report(self) -> str:
        """Generate a pipeline analysis report."""
        lines = [
            "=" * 50,
            "PIPELINE HAZARD ANALYSIS",
            "=" * 50,
            f"  Total hazards detected: {len(self.hazards_detected)}",
            f"  ALU→ALU hazards (forwarding): {self.alu_alu_hazards}",
            f"  Load→ALU hazards (stall needed): {self.load_alu_hazards}",
            f"  Store-after-load patterns: {self.store_after_load}",
            f"  Load-use stalls predicted: {self.load_use_stalls}",
            f"  Forwarding opportunities: {self.forwarding_opportunities}",
            "",
            "  Detailed Hazards:",
        ]

        for i, haz in enumerate(self.hazards_detected[:30]):
            stall = " [STALL]" if haz.needs_stall else ""
            fwd = f" (fwd={haz.forwarding_path})" if haz.forwarding_possible else ""
            lines.append(
                f"    instr[{haz.producer_idx}]→instr[{haz.consumer_idx}]: "
                f"x{haz.producer_rd} {haz.hazard_type}{stall}{fwd}"
            )

        if len(self.hazards_detected) > 30:
            lines.append(
                f"    ... and {len(self.hazards_detected) - 30} more hazards"
            )

        return "\n".join(lines)

    def print_report(self):
        """Print analysis report."""
        print(self.report())


def analyze_instruction_words(words: List[int]) -> Tuple[List[DecodedInstr],
                                                         List[HazardInfo]]:
    """Quick analysis: decode words and analyze hazards."""
    instructions = [DecodedInstr.decode(w) for w in words]
    pm = PipelineMonitor()
    hazards = pm.analyze_stream(instructions)
    return instructions, hazards
