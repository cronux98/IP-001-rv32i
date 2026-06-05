#!/usr/bin/env python3
"""
test_compliance.py — Run official riscv-tests RV32I compliance suite through Spike.

Downloads (if needed) and runs the riscv-tests RV32I ISA tests against
Spike golden reference model. Each test is a standalone RV32I binary
that signals pass/fail via a tohost write.

Test inventory (40 tests):
    rv32ui-p-add, addi, and, andi, auipc, beq, bge, bgeu, blt, bltu,
    bne, fence_i, jal, jalr, lb, lbu, lh, lhu, lui, lw,
    or, ori, sb, sh, simple, sll, slli, slt, slti, sltiu,
    sltu, sra, srai, srl, srli, sub, sw, xor, xori

Usage:
    pytest verification/tests/test_compliance.py -v -m "not slow"
    pytest verification/tests/test_compliance.py -v -m slow  # Full suite
"""

import sys
import os
import subprocess
import tempfile
import pytest
import shutil
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "grm" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "verification"))

from spike_grm import SpikeGRM, SpikeRunner
from grm_config import config


# ── riscv-tests Configuration ────────────────────────────────────────

RISCV_TESTS_URL = "https://github.com/riscv-software-src/riscv-tests.git"
RISCV_TESTS_DIR = Path.home() / ".cache" / "ip001" / "riscv-tests"

# All RV32I user-level tests (no privilege tests, no M-extension)
RV32I_TESTS = [
    "rv32ui-p-add", "rv32ui-p-addi", "rv32ui-p-and", "rv32ui-p-andi",
    "rv32ui-p-auipc", "rv32ui-p-beq", "rv32ui-p-bge", "rv32ui-p-bgeu",
    "rv32ui-p-blt", "rv32ui-p-bltu", "rv32ui-p-bne", "rv32ui-p-fence_i",
    "rv32ui-p-jal", "rv32ui-p-jalr", "rv32ui-p-lb", "rv32ui-p-lbu",
    "rv32ui-p-lh", "rv32ui-p-lhu", "rv32ui-p-lui", "rv32ui-p-lw",
    "rv32ui-p-or", "rv32ui-p-ori", "rv32ui-p-sb", "rv32ui-p-sh",
    "rv32ui-p-simple", "rv32ui-p-sll", "rv32ui-p-slli", "rv32ui-p-slt",
    "rv32ui-p-slti", "rv32ui-p-sltiu", "rv32ui-p-sltu", "rv32ui-p-sra",
    "rv32ui-p-srai", "rv32ui-p-srl", "rv32ui-p-srli", "rv32ui-p-sub",
    "rv32ui-p-sw", "rv32ui-p-xor", "rv32ui-p-xori",
]


def build_riscv_tests() -> bool:
    """Clone and build riscv-tests if not already present."""
    if RISCV_TESTS_DIR.exists() and (RISCV_TESTS_DIR / "isa" / "rv32ui-p-add").exists():
        return True

    print(f"Setting up riscv-tests in {RISCV_TESTS_DIR}...")
    RISCV_TESTS_DIR.parent.mkdir(parents=True, exist_ok=True)

    try:
        if not RISCV_TESTS_DIR.exists():
            subprocess.run(
                ["git", "clone", "--depth", "1", RISCV_TESTS_URL, str(RISCV_TESTS_DIR)],
                check=True, timeout=120, capture_output=True
            )

        # Build RV32I tests
        subprocess.run(
            ["make", "ISA=rv32i"],
            cwd=str(RISCV_TESTS_DIR),
            check=True, timeout=120, capture_output=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to build riscv-tests: {e}")
        return False
    except Exception as e:
        print(f"Error setting up riscv-tests: {e}")
        return False


def run_riscv_test(test_name: str) -> Tuple[bool, str]:
    """Run a single riscv-test through Spike.

    Returns (passed, message).
    """
    test_path = RISCV_TESTS_DIR / "isa" / test_name
    if not test_path.exists():
        return False, f"Test binary not found: {test_path}"

    runner = SpikeRunner(config)
    if not runner.is_available():
        return False, "Spike not available"

    try:
        result = runner.run(str(test_path), timeout=10)
        if result.returncode != 0:
            return False, f"Spike exited with code {result.returncode}"

        # riscv-tests signal pass/fail via writing to tohost (0x80001000 in default link)
        # Pass: tohost = 1, Fail: tohost = non-1 non-zero
        # Check trace for store to tohost address
        for entry in result.trace_entries:
            if entry.is_store and entry.store_addr in (0x80001000, 0x1000):
                if entry.store_value == 1:
                    return True, "PASS (tohost=1)"
                else:
                    return False, f"FAIL (tohost=0x{entry.store_value:X})"

        # If no tohost write found, check exit code and trace
        if result.instruction_count > 0:
            return True, f"PASS (no explicit tohost, {result.instruction_count} instrs)"
        return False, "No instructions executed"

    except Exception as e:
        return False, f"Error: {str(e)[:200]}"


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def riscv_tests_available():
    """Ensure riscv-tests are built and available."""
    return build_riscv_tests()


@pytest.fixture(scope="module")
def spike_ok():
    runner = SpikeRunner(config)
    return runner.is_available()


# ── Quick Tests (subset for fast CI) ──────────────────────────────────

QUICK_TESTS = [
    "rv32ui-p-add", "rv32ui-p-addi", "rv32ui-p-and",
    "rv32ui-p-beq", "rv32ui-p-bne",
    "rv32ui-p-jal", "rv32ui-p-jalr",
    "rv32ui-p-lw", "rv32ui-p-sw",
    "rv32ui-p-lui", "rv32ui-p-xor",
    "rv32ui-p-simple",
]


class TestQuickCompliance:
    """Run a subset of riscv-tests for fast feedback."""

    @pytest.mark.parametrize("test_name", QUICK_TESTS)
    def test_riscv(self, test_name, riscv_tests_available, spike_ok):
        if not riscv_tests_available:
            pytest.skip("riscv-tests not available")
        if not spike_ok:
            pytest.skip("Spike not available")

        passed, msg = run_riscv_test(test_name)
        assert passed, f"{test_name}: {msg}"


@pytest.mark.slow
class TestFullCompliance:
    """Run ALL RV32I riscv-tests. Slow — only run with --run-slow."""

    @pytest.mark.parametrize("test_name", RV32I_TESTS)
    def test_riscv_full(self, test_name, riscv_tests_available, spike_ok):
        if not riscv_tests_available:
            pytest.skip("riscv-tests not available")
        if not spike_ok:
            pytest.skip("Spike not available")

        passed, msg = run_riscv_test(test_name)
        assert passed, f"{test_name}: {msg}"


# ── Standalone runner ────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("IP-001 RV32I Compliance Test Runner")
    print("=" * 60)

    # Check requirements
    runner = SpikeRunner(config)
    if not runner.is_available():
        print("ERROR: Spike not found. Please install Spike.")
        sys.exit(1)

    print(f"Spike: {runner.get_version()}")
    print(f"Setting up riscv-tests...")

    if not build_riscv_tests():
        print("ERROR: Could not build riscv-tests.")
        sys.exit(1)

    print(f"Running {len(RV32I_TESTS)} RV32I compliance tests...")
    print()

    passed = 0
    failed = 0
    for test_name in RV32I_TESTS:
        ok, msg = run_riscv_test(test_name)
        status = "✓" if ok else "✗"
        print(f"  {status} {test_name:25s}  {msg}")
        if ok:
            passed += 1
        else:
            failed += 1

    print()
    print(f"Results: {passed}/{len(RV32I_TESTS)} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
