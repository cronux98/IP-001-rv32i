#!/usr/bin/env python3
"""
compare_trace.py — Compare two execution traces (GRM vs DUT).

Used by Phase 5 cocotb verification to compare Spike GRM trace against
DUT simulation trace. Supports per-instruction register, CSR, and memory
comparison with detailed diff reporting.

Usage:
    python compare_trace.py --grm grm_trace.json --dut dut_trace.json
    python compare_trace.py --grm-trace spike.log --dut-trace dut.log

Author: Sage (GRM Engineer)
Date: 2026-06-05
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from spike_grm import GRMState, TraceParser, TraceEntry, SpikeGRM
from grm_config import config


@dataclass
class ComparisonResult:
    """Result of comparing two traces or states."""

    match: bool
    total_compared: int
    mismatches: List[str]
    grm_only: List[str]   # items only in GRM
    dut_only: List[str]   # items only in DUT

    @property
    def mismatch_count(self) -> int:
        return len(self.mismatches)

    def print_report(self, file=sys.stdout, max_diffs: int = 50):
        """Print a human-readable comparison report."""
        status = "✓ PASS" if self.match else "✗ FAIL"
        print(f"Comparison: {status}", file=file)
        print(f"  Total items compared: {self.total_compared}", file=file)
        print(f"  Mismatches: {self.mismatch_count}", file=file)
        print(f"  GRM-only items: {len(self.grm_only)}", file=file)
        print(f"  DUT-only items: {len(self.dut_only)}", file=file)

        if self.mismatches:
            print(f"\n  Mismatches (showing first {max_diffs}):", file=file)
            for diff in self.mismatches[:max_diffs]:
                print(f"    {diff}", file=file)
            if len(self.mismatches) > max_diffs:
                print(f"    ... and {len(self.mismatches) - max_diffs} more", file=file)


def compare_states(grm_state: GRMState, dut_state: GRMState) -> ComparisonResult:
    """Compare two GRMState snapshots (final state comparison)."""
    match, diffs = grm_state.compare_all(dut_state)
    return ComparisonResult(
        match=match,
        total_compared=(len(grm_state.regfile) + len(grm_state.csr) +
                       len(grm_state.memory)),
        mismatches=diffs,
        grm_only=[],
        dut_only=[]
    )


def compare_traces(grm_trace: List[TraceEntry],
                   dut_trace: List['TraceEntry']) -> ComparisonResult:
    """Compare two execution traces instruction by instruction.

    Traces are aligned by instruction index. For each instruction, compare:
    - PC match
    - Instruction word match
    - Destination register and value match (if written)
    - Store address and value match (if store)

    Note: x0 writes are ignored in both traces (x0 always reads as 0).
    """
    mismatches = []

    max_len = max(len(grm_trace), len(dut_trace))
    grm_only = []
    dut_only = []

    for i in range(max_len):
        if i >= len(grm_trace):
            dut_only.append(f"Instruction {i}: DUT has extra instruction "
                          f"(PC=0x{dut_trace[i].pc:08X})")
            continue
        if i >= len(dut_trace):
            grm_only.append(f"Instruction {i}: GRM has extra instruction "
                          f"(PC=0x{grm_trace[i].pc:08X})")
            continue

        ge = grm_trace[i]
        de = dut_trace[i]

        # Compare PC
        if ge.pc != de.pc:
            mismatches.append(
                f"  Instr {i}: PC mismatch — "
                f"GRM=0x{ge.pc:08X} DUT=0x{de.pc:08X}"
            )

        # Compare instruction word
        if ge.instr_word != de.instr_word:
            mismatches.append(
                f"  Instr {i}: Instruction mismatch — "
                f"GRM=0x{ge.instr_word:08X} DUT=0x{de.instr_word:08X}"
            )

        # Compare register writes (skip x0)
        if ge.rd is not None and ge.rd != 0:
            if de.rd != ge.rd:
                mismatches.append(
                    f"  Instr {i}: Destination register mismatch — "
                    f"GRM=x{ge.rd} DUT=x{de.rd}"
                )
            elif de.rd_value != ge.rd_value:
                mismatches.append(
                    f"  Instr {i}: Register value mismatch — "
                    f"x{ge.rd}=GRM:0x{ge.rd_value:08X} DUT:0x{de.rd_value:08X}"
                )

        # Compare store operations
        if ge.is_store:
            if not de.is_store:
                mismatches.append(
                    f"  Instr {i}: GRM has store, DUT does not"
                )
            elif de.store_addr != ge.store_addr:
                mismatches.append(
                    f"  Instr {i}: Store address mismatch — "
                    f"GRM=0x{ge.store_addr:08X} DUT=0x{de.store_addr:08X}"
                )
            elif de.store_value != ge.store_value:
                mismatches.append(
                    f"  Instr {i}: Store value mismatch @0x{ge.store_addr:08X}"
                    f" — GRM=0x{ge.store_value:08X} DUT=0x{de.store_value:08X}"
                )

    return ComparisonResult(
        match=len(mismatches) == 0 and len(grm_only) == 0 and len(dut_only) == 0,
        total_compared=max_len,
        mismatches=mismatches,
        grm_only=grm_only,
        dut_only=dut_only,
    )


def load_json_state(path: str) -> GRMState:
    """Load a GRMState from a JSON file."""
    with open(path, 'r') as f:
        data = json.load(f)

    state = GRMState()
    # Parse registers
    if 'regfile' in data:
        for k, v in data['regfile'].items():
            state.regfile[int(k)] = int(v)
    # Parse CSRs
    if 'csr' in data:
        for k, v in data['csr'].items():
            addr = int(k, 16)
            state.csr[addr] = int(v)
    # Parse memory
    if 'memory' in data:
        for k, v in data['memory'].items():
            addr = int(k, 16)
            state.memory[addr] = int(v)
    # Parse other fields
    state.pc = data.get('pc', 0)
    state.instret = data.get('instret', 0)

    return state


def load_trace_log(path: str) -> List[TraceEntry]:
    """Parse a Spike/DUT trace log file into TraceEntry list."""
    return TraceParser.parse_file(path)


def main():
    parser = argparse.ArgumentParser(
        description="Compare GRM and DUT execution traces for IP-001 RV32I",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Comparison Modes:
  State comparison: Compare final architectural state snapshots (JSON)
  Trace comparison: Compare instruction-by-instruction traces (log files)

Examples:
  %(prog)s --grm-state grm_state.json --dut-state dut_state.json
  %(prog)s --grm-trace spike.log --dut-trace dut.log
        """
    )

    # State comparison mode
    parser.add_argument('--grm-state', metavar='JSON',
                        help='GRM state JSON file')
    parser.add_argument('--dut-state', metavar='JSON',
                        help='DUT state JSON file')

    # Trace comparison mode
    parser.add_argument('--grm-trace', metavar='LOG',
                        help='Spike trace log file')
    parser.add_argument('--dut-trace', metavar='LOG',
                        help='DUT trace log file')

    # Options
    parser.add_argument('--max-diffs', type=int, default=50,
                        help='Maximum diffs to show (default: 50)')
    parser.add_argument('--json-out', metavar='FILE',
                        help='Write comparison result as JSON')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Only print pass/fail status')

    args = parser.parse_args()

    # Determine mode
    state_mode = args.grm_state or args.dut_state
    trace_mode = args.grm_trace or args.dut_trace

    if state_mode and trace_mode:
        print("Error: Cannot use both state and trace modes.", file=sys.stderr)
        sys.exit(1)
    if not state_mode and not trace_mode:
        print("Error: Specify --grm-state/--dut-state or --grm-trace/--dut-trace",
              file=sys.stderr)
        sys.exit(1)

    if state_mode:
        if not args.grm_state or not args.dut_state:
            print("Error: Both --grm-state and --dut-state required for state comparison",
                  file=sys.stderr)
            sys.exit(1)

        grm_state = load_json_state(args.grm_state)
        dut_state = load_json_state(args.dut_state)
        result = compare_states(grm_state, dut_state)

    else:  # trace_mode
        if not args.grm_trace or not args.dut_trace:
            print("Error: Both --grm-trace and --dut-trace required for trace comparison",
                  file=sys.stderr)
            sys.exit(1)

        grm_trace = load_trace_log(args.grm_trace)
        dut_trace = load_trace_log(args.dut_trace)
        result = compare_traces(grm_trace, dut_trace)

    # Output
    if not args.quiet:
        result.print_report(max_diffs=args.max_diffs)

    if args.json_out:
        with open(args.json_out, 'w') as f:
            json.dump({
                'match': result.match,
                'total_compared': result.total_compared,
                'mismatch_count': result.mismatch_count,
                'mismatches': result.mismatches,
                'grm_only': result.grm_only,
                'dut_only': result.dut_only,
            }, f, indent=2)

    sys.exit(0 if result.match else 1)


if __name__ == "__main__":
    main()
