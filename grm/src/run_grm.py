#!/usr/bin/env python3
"""
run_grm.py — CLI to run an ELF binary through the RV32I GRM and dump state.

Usage:
    python run_grm.py <elf_file> [--json output.json] [--summary]

Examples:
    python run_grm.py grm/binaries/test_add.elf
    python run_grm.py grm/binaries/test_add.elf --json state.json --summary

Author: Sage (GRM Engineer)
Date: 2026-06-05
"""

import sys
import argparse
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from spike_grm import SpikeGRM, GRMState
from grm_config import config


def main():
    parser = argparse.ArgumentParser(
        description="IP-001 RV32I Golden Reference Model CLI Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s grm/binaries/test_add.elf
  %(prog)s grm/binaries/test_add.elf --json state.json
  %(prog)s grm/binaries/test_add.elf --summary --verbose
        """
    )
    parser.add_argument('elf', help='Path to RV32I ELF binary')
    parser.add_argument('--json', '-j', metavar='FILE',
                        help='Write final state to JSON file')
    parser.add_argument('--summary', '-s', action='store_true',
                        help='Print state summary')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    parser.add_argument('--timeout', '-t', type=int, default=30,
                        help='Spike timeout in seconds (default: 30)')
    parser.add_argument('--check', '-c', action='store_true',
                        help='Check Spike availability only')

    args = parser.parse_args()

    grm = SpikeGRM()

    # Check command
    if args.check:
        if grm.check_available():
            print(f"Spike found: {grm.get_version()}")
            sys.exit(0)
        else:
            print("Spike NOT found. Install: riscv-isa-sim", file=sys.stderr)
            sys.exit(1)

    # Verify ELF exists
    elf_path = Path(args.elf)
    if not elf_path.exists():
        print(f"Error: ELF file not found: {args.elf}", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"Running Spike GRM on: {args.elf}")
        print(f"  ISA: {config.SPIKE_ISA}")
        print(f"  Memory: {config.get_spike_memory_args()}")
        print()

    # Run
    try:
        result = grm.run_elf(str(elf_path), timeout=args.timeout)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except TimeoutError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(3)

    if result.returncode != 0:
        print(f"Spike exited with code {result.returncode}", file=sys.stderr)
        if result.stderr:
            # Show first 20 lines of error output
            lines = result.stderr.strip().split('\n')
            for line in lines[:20]:
                print(f"  {line}", file=sys.stderr)
        sys.exit(result.returncode)

    if args.verbose:
        print(f"Instructions retired: {result.instruction_count}")
        print()

    # Optional summary
    if args.summary:
        grm.print_trace_summary()

    # Optional JSON output
    if args.json:
        state = grm.get_final_state()
        if state:
            state.to_json(args.json)
            if args.verbose:
                print(f"\nState written to: {args.json}")

    sys.exit(0)


if __name__ == "__main__":
    main()
