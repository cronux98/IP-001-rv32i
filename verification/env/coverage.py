#!/usr/bin/env python3
"""
coverage.py — Functional coverage model for IP-001 RV32I verification.

Tracks instruction type coverage, ALU operation coverage, forwarding paths,
CSR operations, trap types, and pipeline events.

Usage:
    from env.coverage import CoverageModel
    cov = CoverageModel()
    cov.record_instruction("ADD")
    cov.record_forwarding("EXMEM_FWD_RS1")
    print(cov.report())
"""

import json
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict


# ── Coverage Bin Definitions ──────────────────────────────────────────

# All 40 unique RV32I instructions
RV32I_INSTRUCTIONS = {
    # R-type ALU (10)
    "ADD", "SUB", "SLL", "SLT", "SLTU", "XOR", "SRL", "SRA", "OR", "AND",
    # I-type ALU (9)
    "ADDI", "SLTI", "SLTIU", "XORI", "ORI", "ANDI", "SLLI", "SRLI", "SRAI",
    # Load (5)
    "LW", "LH", "LB", "LHU", "LBU",
    # Store (3)
    "SW", "SH", "SB",
    # Branch (6)
    "BEQ", "BNE", "BLT", "BGE", "BLTU", "BGEU",
    # Upper immediate (2)
    "LUI", "AUIPC",
    # Jump (2)
    "JAL", "JALR",
    # SYSTEM (8)
    "ECALL", "EBREAK", "CSRRW", "CSRRS", "CSRRC", "CSRRWI", "CSRRSI", "CSRRCI",
    # FENCE (2) — treated as NOP
    "FENCE", "FENCE_I",
}

# ALU operations (matches alu_op encoding in id_stage.md)
ALU_OPERATIONS = {
    "ADD", "SUB", "SLL", "SLT", "SLTU", "XOR", "SRL", "SRA",
    "OR", "AND", "LUI", "AUIPC", "BEQ_CMP", "BNE_CMP",
}

# Branch comparisons
BRANCH_TYPES = {"BEQ", "BNE", "BLT", "BGE", "BLTU", "BGEU"}
BRANCH_OUTCOMES = {"TAKEN", "NOT_TAKEN"}

# Forwarding paths
FORWARDING_PATHS = {
    "EXMEM_FWD_RS1",    # EX/MEM → EX stage, operand A (rs1)
    "EXMEM_FWD_RS2",    # EX/MEM → EX stage, operand B (rs2)
    "MEMWB_FWD_RS1",    # MEM/WB → EX stage, operand A (rs1)
    "MEMWB_FWD_RS2",    # MEM/WB → EX stage, operand B (rs2)
    "EXMEM_PRIORITY",   # EX/MEM overrides MEM/WB
    "FWD_TO_STORE",     # Forwarding to store data (rs2 → MEM)
    "FWD_SUPPRESS_X0",  # Forwarding suppressed for x0 destination
}

# CSR operations
CSR_ADDRESSES = {
    0x300, 0x301, 0x304, 0x305, 0x341, 0x342, 0x344
}

CSR_VARIANTS = {
    "CSRRW", "CSRRS", "CSRRC", "CSRRWI", "CSRRSI", "CSRRCI"
}

# Trap types
TRAP_TYPES = {
    "ILLEGAL_INSTRUCTION",     # mcause=2
    "BREAKPOINT",              # mcause=3 (EBREAK)
    "MISALIGNED_LOAD",         # mcause=4
    "MISALIGNED_STORE",        # mcause=6
    "ECALL_M",                 # mcause=11
    "MRET",                    # Trap return
}

# Pipeline events
PIPELINE_EVENTS = {
    "NORMAL_ADVANCE",      # All stages advance
    "STALL_IF_ID",         # IF + ID stalled (load-use)
    "FLUSH_IF_ID",         # IF + ID flushed (branch)
    "FLUSH_IF",            # IF only flushed (JAL/JALR)
    "FLUSH_IF_ID_EX",      # IF + ID + EX flushed (trap/MRET)
    "FLUSH_ALL",           # All stages flushed (reset)
    "NOP_INTO_EX",         # NOP bubble inserted into EX
    "STALL_FLUSH_SIMUL",   # Stall + flush simultaneously
}

# Hazard conditions
HAZARD_CONDITIONS = {
    "LOAD_USE_RS1",        # Load-use on rs1 (stall triggered)
    "LOAD_USE_RS2",        # Load-use on rs2 (stall triggered)
    "LOAD_USE_BOTH",       # Load-use on both rs1 and rs2
    "NO_HAZARD",           # No hazard (no stall)
    "STORE_AFTER_LOAD",    # Store after load (no stall, forwarding)
    "X0_DEPENDENCY",       # Dependency on x0 (no stall)
    "RAW_ALU_ALU",         # RAW ALU→ALU (forwarding, no stall)
    "RAW_LOAD_ALU",        # RAW load→ALU (stall + forwarding)
}


@dataclass
class CoverageModel:
    """Functional coverage model for IP-001 RV32I 5-stage pipeline core.

    Tracks coverage across multiple dimensions:
    - Instructions (40 types)
    - ALU operations (14 ops)
    - Forwarding paths (7 categories)
    - CSR operations (7 CSRs × 6 variants)
    - Trap types (6 types)
    - Pipeline events (8 events)
    - Branch outcomes (6 types × 2 outcomes)
    - Hazard conditions (8 conditions)
    - Register usage (32 registers)
    """

    # Track which bins have been hit
    instructions: Set[str] = field(default_factory=set)
    alu_operations: Set[str] = field(default_factory=set)
    branch_outcomes: Dict[str, Set[str]] = field(default_factory=
        lambda: defaultdict(set))  # branch_type → {TAKEN, NOT_TAKEN}
    forwarding_paths: Set[str] = field(default_factory=set)
    csr_operations: Dict[int, Set[str]] = field(default_factory=
        lambda: defaultdict(set))  # csr_addr → {variant}
    trap_types: Set[str] = field(default_factory=set)
    pipeline_events: Set[str] = field(default_factory=set)
    hazard_conditions: Set[str] = field(default_factory=set)
    registers_written: Set[int] = field(default_factory=set)
    registers_read: Set[int] = field(default_factory=set)

    # Counters
    total_instructions: int = 0
    total_forwarding_events: int = 0
    total_stalls: int = 0
    total_flushes: int = 0

    def record_instruction(self, name: str):
        """Record that an instruction type was exercised."""
        self.instructions.add(name.upper())
        self.total_instructions += 1

    def record_alu_operation(self, op: str):
        """Record an ALU operation."""
        self.alu_operations.add(op.upper())

    def record_branch_outcome(self, branch_type: str, taken: bool):
        """Record a branch outcome."""
        self.branch_outcomes[branch_type.upper()].add(
            "TAKEN" if taken else "NOT_TAKEN"
        )

    def record_forwarding(self, path: str):
        """Record a forwarding path activation."""
        self.forwarding_paths.add(path.upper())
        self.total_forwarding_events += 1

    def record_csr_operation(self, csr_addr: int, variant: str):
        """Record a CSR operation."""
        self.csr_operations[csr_addr].add(variant.upper())

    def record_trap(self, trap_type: str):
        """Record a trap type."""
        self.trap_types.add(trap_type.upper())

    def record_pipeline_event(self, event: str):
        """Record a pipeline event."""
        self.pipeline_events.add(event.upper())
        if "STALL" in event.upper():
            self.total_stalls += 1
        if "FLUSH" in event.upper():
            self.total_flushes += 1

    def record_hazard(self, condition: str):
        """Record a hazard condition."""
        self.hazard_conditions.add(condition.upper())

    def record_register_write(self, reg_num: int):
        """Record that a register was written."""
        if 0 <= reg_num <= 31:
            self.registers_written.add(reg_num)

    def record_register_read(self, reg_num: int):
        """Record that a register was read."""
        if 0 <= reg_num <= 31:
            self.registers_read.add(reg_num)

    # ── Coverage Metrics ──────────────────────────────────────────

    def instruction_coverage(self) -> Tuple[int, int, float]:
        """(covered, total, percentage) for instructions."""
        total = len(RV32I_INSTRUCTIONS)
        covered = len(self.instructions & RV32I_INSTRUCTIONS)
        return covered, total, (covered / total * 100) if total > 0 else 0.0

    def alu_coverage(self) -> Tuple[int, int, float]:
        """(covered, total, percentage) for ALU operations."""
        total = len(ALU_OPERATIONS)
        covered = len(self.alu_operations & ALU_OPERATIONS)
        return covered, total, (covered / total * 100) if total > 0 else 0.0

    def branch_coverage(self) -> Tuple[int, int, float]:
        """(covered, total, percentage) for branch outcomes."""
        total = len(BRANCH_TYPES) * 2  # taken + not-taken
        covered = sum(len(outcomes) for outcomes in self.branch_outcomes.values())
        return covered, total, (covered / total * 100) if total > 0 else 0.0

    def forwarding_coverage(self) -> Tuple[int, int, float]:
        """(covered, total, percentage) for forwarding paths."""
        total = len(FORWARDING_PATHS)
        covered = len(self.forwarding_paths & FORWARDING_PATHS)
        return covered, total, (covered / total * 100) if total > 0 else 0.0

    def csr_coverage(self) -> Tuple[int, int, float]:
        """(covered, total, percentage) for CSR operations."""
        total = len(CSR_ADDRESSES) * len(CSR_VARIANTS)
        covered = sum(len(variants) for variants in self.csr_operations.values())
        return covered, total, (covered / total * 100) if total > 0 else 0.0

    def trap_coverage(self) -> Tuple[int, int, float]:
        """(covered, total, percentage) for trap types."""
        total = len(TRAP_TYPES)
        covered = len(self.trap_types & TRAP_TYPES)
        return covered, total, (covered / total * 100) if total > 0 else 0.0

    def pipeline_event_coverage(self) -> Tuple[int, int, float]:
        """(covered, total, percentage) for pipeline events."""
        total = len(PIPELINE_EVENTS)
        covered = len(self.pipeline_events & PIPELINE_EVENTS)
        return covered, total, (covered / total * 100) if total > 0 else 0.0

    def hazard_coverage(self) -> Tuple[int, int, float]:
        """(covered, total, percentage) for hazard conditions."""
        total = len(HAZARD_CONDITIONS)
        covered = len(self.hazard_conditions & HAZARD_CONDITIONS)
        return covered, total, (covered / total * 100) if total > 0 else 0.0

    def register_write_coverage(self) -> Tuple[int, int, float]:
        """(covered, total, percentage) for register writes (x1-x31)."""
        total = 31  # x1 through x31
        covered = len(self.registers_written - {0})
        return covered, total, (covered / total * 100) if total > 0 else 0.0

    def overall_coverage(self) -> float:
        """Compute weighted overall coverage percentage."""
        metrics = [
            (self.instruction_coverage(), 0.20),
            (self.alu_coverage(), 0.10),
            (self.branch_coverage(), 0.10),
            (self.forwarding_coverage(), 0.15),
            (self.csr_coverage(), 0.15),
            (self.trap_coverage(), 0.10),
            (self.pipeline_event_coverage(), 0.10),
            (self.hazard_coverage(), 0.10),
        ]
        weighted_sum = sum((m[2] / 100) * w for (m, w) in metrics)
        return weighted_sum * 100

    # ── Reporting ──────────────────────────────────────────────────

    def report(self) -> str:
        """Generate a coverage report string."""
        lines = [
            "=" * 60,
            "IP-001 FUNCTIONAL COVERAGE REPORT",
            "=" * 60,
            f"  Total instructions executed: {self.total_instructions}",
            f"  Total forwarding events: {self.total_forwarding_events}",
            f"  Total stalls: {self.total_stalls}",
            f"  Total flushes: {self.total_flushes}",
            "",
        ]

        # Instruction coverage
        c, t, p = self.instruction_coverage()
        lines.append(f"  Instruction Types:    {c:2d}/{t:2d} ({p:5.1f}%)")
        if c < t:
            missing = RV32I_INSTRUCTIONS - self.instructions
            lines.append(f"    Missing: {sorted(missing)}")

        # ALU coverage
        c, t, p = self.alu_coverage()
        lines.append(f"  ALU Operations:        {c:2d}/{t:2d} ({p:5.1f}%)")
        if c < t:
            missing = ALU_OPERATIONS - self.alu_operations
            lines.append(f"    Missing: {sorted(missing)}")

        # Branch coverage
        c, t, p = self.branch_coverage()
        lines.append(f"  Branch Outcomes:       {c:2d}/{t:2d} ({p:5.1f}%)")
        for bt in sorted(BRANCH_TYPES):
            outcomes = self.branch_outcomes.get(bt, set())
            taken = "✓" if "TAKEN" in outcomes else "✗"
            not_taken = "✓" if "NOT_TAKEN" in outcomes else "✗"
            lines.append(f"    {bt:6s}: taken={taken} not-taken={not_taken}")

        # Forwarding coverage
        c, t, p = self.forwarding_coverage()
        lines.append(f"  Forwarding Paths:      {c:2d}/{t:2d} ({p:5.1f}%)")
        if c < t:
            missing = FORWARDING_PATHS - self.forwarding_paths
            lines.append(f"    Missing: {sorted(missing)}")

        # CSR coverage
        c, t, p = self.csr_coverage()
        lines.append(f"  CSR Operations:        {c:2d}/{t:2d} ({p:5.1f}%)")
        for addr in sorted(CSR_ADDRESSES):
            variants = self.csr_operations.get(addr, set())
            hit = len(variants)
            lines.append(f"    0x{addr:03X}: {hit}/{len(CSR_VARIANTS)} variants")

        # Trap coverage
        c, t, p = self.trap_coverage()
        lines.append(f"  Trap Types:            {c:2d}/{t:2d} ({p:5.1f}%)")
        if c < t:
            missing = TRAP_TYPES - self.trap_types
            lines.append(f"    Missing: {sorted(missing)}")

        # Pipeline event coverage
        c, t, p = self.pipeline_event_coverage()
        lines.append(f"  Pipeline Events:       {c:2d}/{t:2d} ({p:5.1f}%)")

        # Hazard coverage
        c, t, p = self.hazard_coverage()
        lines.append(f"  Hazard Conditions:     {c:2d}/{t:2d} ({p:5.1f}%)")

        # Register coverage
        c, t, p = self.register_write_coverage()
        lines.append(f"  Registers Written:     {c:2d}/{t:2d} ({p:5.1f}%)")

        # Overall
        overall = self.overall_coverage()
        lines.append(f"\n  OVERALL COVERAGE:     {overall:5.1f}%")
        lines.append(f"  Target:               ≥ 95.0%")
        lines.append("=" * 60)

        return "\n".join(lines)

    def print_report(self):
        """Print coverage report to stdout."""
        print(self.report())

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export."""
        return {
            'instruction_coverage': {
                'covered': self.instruction_coverage()[0],
                'total': self.instruction_coverage()[1],
                'percent': self.instruction_coverage()[2],
                'covered_set': sorted(self.instructions),
                'missing': sorted(RV32I_INSTRUCTIONS - self.instructions),
            },
            'alu_coverage': {
                'covered': self.alu_coverage()[0],
                'total': self.alu_coverage()[1],
                'percent': self.alu_coverage()[2],
                'covered_set': sorted(self.alu_operations),
                'missing': sorted(ALU_OPERATIONS - self.alu_operations),
            },
            'branch_coverage': {
                'covered': self.branch_coverage()[0],
                'total': self.branch_coverage()[1],
                'percent': self.branch_coverage()[2],
                'details': {
                    bt: sorted(outcomes)
                    for bt, outcomes in self.branch_outcomes.items()
                },
            },
            'forwarding_coverage': {
                'covered': self.forwarding_coverage()[0],
                'total': self.forwarding_coverage()[1],
                'percent': self.forwarding_coverage()[2],
                'covered_set': sorted(self.forwarding_paths),
                'missing': sorted(FORWARDING_PATHS - self.forwarding_paths),
            },
            'csr_coverage': {
                'covered': self.csr_coverage()[0],
                'total': self.csr_coverage()[1],
                'percent': self.csr_coverage()[2],
                'details': {
                    f"0x{addr:03X}": sorted(variants)
                    for addr, variants in self.csr_operations.items()
                },
            },
            'trap_coverage': {
                'covered': self.trap_coverage()[0],
                'total': self.trap_coverage()[1],
                'percent': self.trap_coverage()[2],
                'covered_set': sorted(self.trap_types),
                'missing': sorted(TRAP_TYPES - self.trap_types),
            },
            'pipeline_event_coverage': {
                'covered': self.pipeline_event_coverage()[0],
                'total': self.pipeline_event_coverage()[1],
                'percent': self.pipeline_event_coverage()[2],
            },
            'hazard_coverage': {
                'covered': self.hazard_coverage()[0],
                'total': self.hazard_coverage()[1],
                'percent': self.hazard_coverage()[2],
            },
            'register_coverage': {
                'written': self.register_write_coverage()[0],
                'total': self.register_write_coverage()[1],
                'percent': self.register_write_coverage()[2],
            },
            'overall_percent': self.overall_coverage(),
            'counters': {
                'total_instructions': self.total_instructions,
                'total_forwarding_events': self.total_forwarding_events,
                'total_stalls': self.total_stalls,
                'total_flushes': self.total_flushes,
            },
        }


# Convenience function
def create_coverage_model() -> CoverageModel:
    """Create a fresh coverage model."""
    return CoverageModel()
