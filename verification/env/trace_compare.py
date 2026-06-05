#!/usr/bin/env python3
"""
trace_compare.py — Instruction-level trace comparison for IP-001 RV32I.

Compares GRM (Spike) execution traces against DUT traces at the
instruction level. Handles PC base offset normalization, NOP skipping,
and x0 write suppression.

Usage:
    from env.trace_compare import TraceComparer, compare_traces
    tc = TraceComparer(grm_base=0x80000000, dut_base=0x00000000)
    mismatches = tc.compare(grm_trace_entries, dut_trace_entries)
"""

import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

# Add GRM to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "grm" / "src"))

from spike_grm import TraceEntry


@dataclass
class TraceDiff:
    """A single difference between two trace entries."""

    index: int
    field: str  # "pc", "instr", "rd", "rd_value", "store_addr", "store_value"
    grm_value: str
    dut_value: str

    def __str__(self) -> str:
        return (f"Instr[{self.index}] {self.field}: "
                f"GRM={self.grm_value} DUT={self.dut_value}")


@dataclass
class TraceCompareResult:
    """Result of trace comparison."""

    match: bool
    total_compared: int
    diffs: List[TraceDiff]
    grm_only: List[int]    # Indices only in GRM trace
    dut_only: List[int]    # Indices only in DUT trace
    extra_info: List[str] = field(default_factory=list)

    @property
    def mismatch_count(self) -> int:
        return len(self.diffs) + len(self.grm_only) + len(self.dut_only)


class TraceComparer:
    """Compare GRM and DUT instruction execution traces."""

    def __init__(self, grm_base: int = 0x80000000, dut_base: int = 0x00000000,
                 skip_nops: bool = True, suppress_x0: bool = True):
        self.grm_base = grm_base
        self.dut_base = dut_base
        self.skip_nops = skip_nops
        self.suppress_x0 = suppress_x0

        # NOP encoding: ADDI x0, x0, 0 = 0x00000013
        self.NOP_ENCODING = 0x00000013

    def _is_nop(self, instr_word: int) -> bool:
        """Check if instruction is a NOP."""
        return instr_word == self.NOP_ENCODING

    def _normalize_pc(self, pc: int, is_grm: bool) -> int:
        """Normalize PC by subtracting base offset."""
        if is_grm:
            return pc - self.grm_base
        else:
            return pc - self.dut_base

    def compare(self, grm_trace: List[TraceEntry],
                dut_trace: List[TraceEntry]) -> TraceCompareResult:
        """Compare two execution traces instruction by instruction.

        Args:
            grm_trace: GRM (Spike) trace entries
            dut_trace: DUT trace entries

        Returns:
            TraceCompareResult with mismatches
        """
        diffs = []

        # Filter NOPs if requested
        if self.skip_nops:
            grm_filtered = [e for e in grm_trace if not self._is_nop(e.instr_word)]
            dut_filtered = [e for e in dut_trace if not self._is_nop(e.instr_word)]
        else:
            grm_filtered = list(grm_trace)
            dut_filtered = list(dut_trace)

        max_len = max(len(grm_filtered), len(dut_filtered))
        grm_only = []
        dut_only = []

        for i in range(max_len):
            if i >= len(grm_filtered):
                dut_only.append(i)
                continue
            if i >= len(dut_filtered):
                grm_only.append(i)
                continue

            ge = grm_filtered[i]
            de = dut_filtered[i]

            # Compare normalized PC
            grm_pc = self._normalize_pc(ge.pc, is_grm=True)
            dut_pc = self._normalize_pc(de.pc, is_grm=False)
            if grm_pc != dut_pc:
                diffs.append(TraceDiff(
                    index=i, field="pc",
                    grm_value=f"0x{ge.pc:08X} (norm=0x{grm_pc:08X})",
                    dut_value=f"0x{de.pc:08X} (norm=0x{dut_pc:08X})",
                ))

            # Compare instruction word
            if ge.instr_word != de.instr_word:
                diffs.append(TraceDiff(
                    index=i, field="instr",
                    grm_value=f"0x{ge.instr_word:08X}",
                    dut_value=f"0x{de.instr_word:08X}",
                ))

            # Compare register writes (skip x0 suppression)
            if ge.rd is not None:
                if self.suppress_x0 and ge.rd == 0:
                    continue  # Skip x0 writes

                if de.rd is None:
                    diffs.append(TraceDiff(
                        index=i, field="rd",
                        grm_value=f"x{ge.rd}",
                        dut_value="None (no write)",
                    ))
                elif de.rd != ge.rd:
                    diffs.append(TraceDiff(
                        index=i, field="rd",
                        grm_value=f"x{ge.rd}",
                        dut_value=f"x{de.rd}",
                    ))
                elif de.rd_value != ge.rd_value:
                    diffs.append(TraceDiff(
                        index=i, field="rd_value",
                        grm_value=f"x{ge.rd}=0x{ge.rd_value:08X}",
                        dut_value=f"x{de.rd}=0x{de.rd_value:08X}",
                    ))

            # Compare store operations
            if ge.is_store:
                if not de.is_store:
                    diffs.append(TraceDiff(
                        index=i, field="is_store",
                        grm_value="True",
                        dut_value="False",
                    ))
                else:
                    grm_store = self._normalize_pc(ge.store_addr, is_grm=True)
                    dut_store = self._normalize_pc(de.store_addr, is_grm=False)
                    if ge.store_addr != de.store_addr:
                        diffs.append(TraceDiff(
                            index=i, field="store_addr",
                            grm_value=f"0x{ge.store_addr:08X}",
                            dut_value=f"0x{de.store_addr:08X}",
                        ))
                    elif ge.store_value != de.store_value:
                        diffs.append(TraceDiff(
                            index=i, field="store_value",
                            grm_value=f"0x{ge.store_value:08X}",
                            dut_value=f"0x{de.store_value:08X}",
                        ))

        match = (len(diffs) == 0 and len(grm_only) == 0 and len(dut_only) == 0)

        return TraceCompareResult(
            match=match,
            total_compared=max_len,
            diffs=diffs,
            grm_only=grm_only,
            dut_only=dut_only,
            extra_info=[
                f"GRM trace entries: {len(grm_trace)} (filtered: {len(grm_filtered)})",
                f"DUT trace entries: {len(dut_trace)} (filtered: {len(dut_filtered)})",
                f"NOPs filtered: {self.skip_nops}",
                f"x0 suppressed: {self.suppress_x0}",
                f"GRM base: 0x{self.grm_base:08X}, DUT base: 0x{self.dut_base:08X}",
            ],
        )

    def compare_files(self, grm_log_path: str, dut_log_path: str) -> TraceCompareResult:
        """Compare two trace log files.

        Args:
            grm_log_path: Path to Spike log file
            dut_log_path: Path to DUT trace log file

        Returns:
            TraceCompareResult
        """
        from spike_grm import TraceParser

        grm_trace = TraceParser.parse_file(grm_log_path)
        dut_trace = TraceParser.parse_file(dut_log_path)
        return self.compare(grm_trace, dut_trace)


def compare_traces(grm_trace: List[TraceEntry],
                   dut_trace: List[TraceEntry],
                   grm_base: int = 0x80000000,
                   dut_base: int = 0x00000000) -> TraceCompareResult:
    """Quick function to compare two trace lists."""
    tc = TraceComparer(grm_base=grm_base, dut_base=dut_base)
    return tc.compare(grm_trace, dut_trace)
