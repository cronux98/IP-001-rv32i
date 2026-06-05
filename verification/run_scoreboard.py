#!/usr/bin/env python3
"""
run_scoreboard.py — Run full scoreboard across all verification tests.

Orchestrates the complete verification flow:
1. Runs all test suites
2. Collects scoreboard results
3. Generates coverage report
4. Produces summary

Usage:
    python verification/run_scoreboard.py
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "grm" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "verification"))

from env.scoreboard import Scoreboard, ScoreboardResult
from env.coverage import CoverageModel
from env.pipeline_monitor import PipelineMonitor, DecodedInstr


def main():
    print("=" * 60)
    print("IP-001 RV32I VERIFICATION — FULL SCOREBOARD RUN")
    print("=" * 60)

    sb = Scoreboard()

    # Check toolchain
    print(f"\nSpike available: {sb.spike_available}")
    print(f"Toolchain available: {sb.toolchain_available}")

    if not sb.spike_available:
        print("\nERROR: Spike not available. Cannot run tests.")
        sys.exit(1)

    if not sb.toolchain_available:
        print("\nWARNING: RISC-V toolchain not fully available. Some tests will be skipped.")

    # ── Run instruction tests ────────────────────────────────
    print("\n" + "─" * 40)
    print("1. Instruction Tests")
    print("─" * 40)

    # ADD test
    sb.run_asm_test("T5.1.1 ADD", """\
.section .text
.globl _start
_start:
    addi x1, x0, 10
    addi x2, x0, 20
    add x3, x1, x2
""", expected_regs={3: 30})

    # SUB test
    sb.run_asm_test("T5.1.2 SUB", """\
.section .text
.globl _start
_start:
    addi x1, x0, 50
    addi x2, x0, 20
    sub x3, x1, x2
""", expected_regs={3: 30})

    # AND/OR/XOR
    sb.run_asm_test("T5.1.3 AND/OR/XOR", """\
.section .text
.globl _start
_start:
    addi x1, x0, 0xFF
    addi x2, x0, 0x0F
    and x3, x1, x2
    or x4, x1, x2
    xor x5, x1, x2
""", expected_regs={3: 0x0F, 4: 0xFF, 5: 0xF0})

    # LUI
    sb.run_asm_test("T5.1.4 LUI", """\
.section .text
.globl _start
_start:
    lui x3, 0x12345
""", expected_regs={3: 0x12345000})

    # Load/Store
    sb.run_asm_test("T5.1.5 LW/SW", """\
.section .text
.globl _start
_start:
    addi x1, x0, 0xBEEF
    sw x1, 0(x0)
    lw x2, 0(x0)
""", expected_regs={2: 0xBEEF})

    # x0 invariance
    sb.run_asm_test("T5.1.6 x0 invariance", """\
.section .text
.globl _start
_start:
    addi x0, x0, 42
    add x3, x0, x0
""", expected_regs={0: 0, 3: 0})

    # ── Run forwarding tests ─────────────────────────────────
    print("\n" + "─" * 40)
    print("2. Forwarding Tests")
    print("─" * 40)

    # EX/MEM forward
    sb.run_asm_test("T5.2.1 EX/MEM→EX (rs1)", """\
.section .text
.globl _start
_start:
    addi x5, x0, 100
    addi x6, x5, 50
""", expected_regs={6: 150})

    # EX/MEM priority
    sb.run_asm_test("T5.2.2 EX/MEM priority", """\
.section .text
.globl _start
_start:
    addi x5, x0, 100
    addi x5, x5, 200
    add x6, x5, x0
""", expected_regs={6: 300})

    # Store after load
    sb.run_asm_test("T5.2.3 Store-after-load", """\
.section .text
.globl _start
_start:
    addi x5, x0, 0xFEED
    sw x5, 0(x0)
    lw x6, 0(x0)
    sw x6, 4(x0)
    lw x7, 4(x0)
""", expected_regs={7: 0xFEED})

    # ── Run hazard tests ────────────────────────────────────
    print("\n" + "─" * 40)
    print("3. Hazard Tests")
    print("─" * 40)

    sb.run_asm_test("T5.3.1 Load-use (rs1)", """\
.section .text
.globl _start
_start:
    addi x5, x0, 123
    sw x5, 0(x0)
    lw x6, 0(x0)
    addi x7, x6, 77
""", expected_regs={7: 200})

    sb.run_asm_test("T5.3.2 BEQ taken", """\
.section .text
.globl _start
_start:
    addi x5, x0, 5
    addi x6, x0, 5
    beq x5, x6, 1f
    addi x7, x0, 999
1:  addi x7, x0, 42
""", expected_regs={7: 42})

    sb.run_asm_test("T5.3.3 JAL link", """\
.section .text
.globl _start
_start:
    jal x3, 1f
1:  nop
""")

    # ── Run CSR tests ───────────────────────────────────────
    print("\n" + "─" * 40)
    print("4. CSR Tests")
    print("─" * 40)

    sb.run_asm_test("T5.4.1 CSRRW mtvec", """\
.section .text
.globl _start
_start:
    li x5, 0x100
    csrrw x6, mtvec, x5
    csrrw x7, mtvec, x0
""", expected_regs={7: 0x100})

    sb.run_asm_test("T5.4.2 misa read-only", """\
.section .text
.globl _start
_start:
    csrrw x5, misa, x0
    li x6, 0xDEADBEEF
    csrrw x0, misa, x6
    csrrw x7, misa, x0
""")

    # ── Run trap tests ──────────────────────────────────────
    print("\n" + "─" * 40)
    print("5. Trap Tests")
    print("─" * 40)

    sb.run_asm_test("T5.5.1 ECALL trap", """\
.section .text
.globl _start
_start:
    li x5, 0x55
    ecall
""")

    sb.run_asm_test("T5.5.2 MRET", """\
.section .text
.globl _start
_start:
    la x5, return_target
    csrrw x0, mepc, x5
    mret
    li x6, 0xBAD
return_target:
    li x6, 0x600D
""", expected_regs={6: 0x600D})

    # ── Summary ─────────────────────────────────────────────
    print()
    sb.print_summary()

    # Export results
    results_path = PROJECT_ROOT / "verification" / "scoreboard_results.json"
    with open(results_path, 'w') as f:
        json.dump(sb.as_dict(), f, indent=2)
    print(f"\nResults saved to {results_path}")

    return 0 if all(r.passed for r in sb.results) else 1


if __name__ == "__main__":
    sys.exit(main())
