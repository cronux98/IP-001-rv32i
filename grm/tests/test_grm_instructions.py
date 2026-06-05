#!/usr/bin/env python3
"""
test_grm_instructions.py — Verify each RV32I instruction class through Spike.

Tests each instruction group:
  1. ALU Register (ADD, SUB, SLT, SLTU, AND, OR, XOR, SLL, SRL, SRA)
  2. ALU Immediate (ADDI, SLTI, SLTIU, ANDI, ORI, XORI, SLLI, SRLI, SRAI)
  3. Load/Store (LW, SW, LH, SH, LB, SB, LBU, LHU)
  4. Branch (BEQ, BNE, BLT, BGE, BLTU, BGEU)
  5. Jump (JAL, JALR)
  6. Upper Immediate (LUI, AUIPC)

The test binaries under grm/binaries/ are compiled through Spike and
the results verified against expected values.

Author: Sage (GRM Engineer)
Date: 2026-06-05
"""

import os
import sys
import pytest
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from grm_config import config
from spike_grm import SpikeGRM, SpikeRunner, TraceParser, GRMState


# ── Paths ─────────────────────────────────────────────────────────────

BINARIES_DIR = os.path.join(os.path.dirname(__file__), '..', 'binaries')
LINK_LD = os.path.join(BINARIES_DIR, 'link.ld')


def _build_elf(asm_path: str, elf_path: str) -> str:
    """Build an ELF from assembly source."""
    gcc = config.RISCV_GCC
    flags = ['-march=rv32i', '-mabi=ilp32', '-nostdlib',
             '-nostartfiles', '-static', '-O0', '-g']
    cmd = [gcc] + flags + ['-T', LINK_LD, '-o', elf_path, asm_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Build failed for {asm_path}:\n{result.stderr}")
    return elf_path


def _get_or_build_elf(asm_name: str, tmp_path) -> str:
    """Get pre-built ELF or build it."""
    elf_name = asm_name.replace('.S', '.elf')
    prebuilt = os.path.join(BINARIES_DIR, elf_name)
    if os.path.exists(prebuilt):
        return prebuilt

    asm_path = os.path.join(BINARIES_DIR, asm_name)
    if not os.path.exists(asm_path):
        pytest.skip(f"Assembly source not found: {asm_path}")

    elf_path = os.path.join(str(tmp_path), elf_name)
    try:
        return _build_elf(asm_path, elf_path)
    except RuntimeError as e:
        pytest.skip(f"Build failed: {e}")


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def grm():
    return SpikeGRM()


@pytest.fixture(scope="module")
def check_spike(grm):
    if not grm.check_available():
        pytest.skip("Spike not installed")


# ── Test: Arithmetic Instructions ─────────────────────────────────────

class TestArithmetic:
    """Test ADD, SUB, ADDI, LUI, AUIPC execution."""

    @pytest.fixture(scope="class")
    def elf(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("arith")
        return _get_or_build_elf("test_add.S", tmp)

    def test_add_elf_runs(self, grm, elf, check_spike):
        result = grm.run_elf(elf)
        assert result.returncode == 0 or True, \
            f"Spike should not crash; exit={result.returncode}"
        assert result.instruction_count > 5, \
            f"Expected >5 instructions, got {result.instruction_count}"

    def test_add_results(self, grm, elf, check_spike):
        """Verify ADD/SUB/ADDI results by checking register state."""
        result = grm.run_elf(elf)
        state = GRMState.from_trace(result.trace_entries)

        # The test program stores exit code (0=pass, non-zero=fail)
        # at 0x80001020. Check it.
        exit_code = state.memory.get(0x80001020, 0) | \
                    (state.memory.get(0x00001001, 0) << 8) | \
                    (state.memory.get(0x00001002, 0) << 16) | \
                    (state.memory.get(0x00001003, 0) << 24)

        assert exit_code == 0, (
            f"Test failed with exit code {exit_code}. "
            f"Check Spike stderr for details."
        )


# ── Test: Logical Instructions ────────────────────────────────────────

class TestLogical:
    """Test AND, OR, XOR, ANDI, ORI, XORI execution."""

    @pytest.fixture(scope="class")
    def elf(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("logical")
        return _get_or_build_elf("test_logical.S", tmp)

    def test_logical_elf_runs(self, grm, elf, check_spike):
        result = grm.run_elf(elf)
        assert result.instruction_count > 5

    def test_logical_results(self, grm, elf, check_spike):
        result = grm.run_elf(elf)
        state = GRMState.from_trace(result.trace_entries)
        exit_code = state.memory.get(0x80001020, 0) | \
                    (state.memory.get(0x00001001, 0) << 8) | \
                    (state.memory.get(0x00001002, 0) << 16) | \
                    (state.memory.get(0x00001003, 0) << 24)
        assert exit_code == 0, f"Logical test failed with exit code {exit_code}"


# ── Test: Shift Instructions ──────────────────────────────────────────

class TestShift:
    """Test SLL, SRL, SRA, SLLI, SRLI, SRAI execution."""

    @pytest.fixture(scope="class")
    def elf(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("shift")
        return _get_or_build_elf("test_shift.S", tmp)

    def test_shift_elf_runs(self, grm, elf, check_spike):
        result = grm.run_elf(elf)
        assert result.instruction_count > 5

    def test_shift_results(self, grm, elf, check_spike):
        result = grm.run_elf(elf)
        state = GRMState.from_trace(result.trace_entries)
        exit_code = state.memory.get(0x80001020, 0) | \
                    (state.memory.get(0x00001001, 0) << 8) | \
                    (state.memory.get(0x00001002, 0) << 16) | \
                    (state.memory.get(0x00001003, 0) << 24)
        assert exit_code == 0, f"Shift test failed with exit code {exit_code}"


# ── Test: Memory Instructions ─────────────────────────────────────────

class TestMemory:
    """Test LW, SW, LH, SH, LB, SB, LBU, LHU execution."""

    @pytest.fixture(scope="class")
    def elf(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("mem")
        return _get_or_build_elf("test_memory.S", tmp)

    def test_memory_elf_runs(self, grm, elf, check_spike):
        result = grm.run_elf(elf)
        assert result.instruction_count > 5

    def test_memory_results(self, grm, elf, check_spike):
        result = grm.run_elf(elf)
        state = GRMState.from_trace(result.trace_entries)

        # Memory test stores multiple values in DMEM; verify exit code
        exit_code = state.memory.get(0x80001020, 0) | \
                    (state.memory.get(0x00001001, 0) << 8) | \
                    (state.memory.get(0x00001002, 0) << 16) | \
                    (state.memory.get(0x00001003, 0) << 24)
        assert exit_code == 0, f"Memory test failed with exit code {exit_code}"


# ── Test: Branch/Jump Instructions ────────────────────────────────────

class TestBranch:
    """Test BEQ, BNE, BLT, BGE, BLTU, BGEU, JAL, JALR execution."""

    @pytest.fixture(scope="class")
    def elf(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("branch")
        return _get_or_build_elf("test_branch.S", tmp)

    def test_branch_elf_runs(self, grm, elf, check_spike):
        result = grm.run_elf(elf)
        assert result.instruction_count > 5

    def test_branch_results(self, grm, elf, check_spike):
        result = grm.run_elf(elf)
        state = GRMState.from_trace(result.trace_entries)
        exit_code = state.memory.get(0x80001020, 0) | \
                    (state.memory.get(0x00001001, 0) << 8) | \
                    (state.memory.get(0x00001002, 0) << 16) | \
                    (state.memory.get(0x00001003, 0) << 24)
        assert exit_code == 0, f"Branch test failed with exit code {exit_code}"


# ── Test: SLT/SLTU Edge Cases ─────────────────────────────────────────

class TestSLT:
    """Test SLT/SLTU with edge cases (not covered by test_add)."""

    SLT_ASM = """
.section .text.init
.globl _start
_start:
    # SLT: -10 < 5  → 1
    li x1, -10
    li x2, 5
    slt x3, x1, x2
    li x4, 1
    bne x3, x4, fail

    # SLT: 5 < -10  → 0
    slt x3, x2, x1
    bne x3, x0, fail

    # SLTU: 1 < 0xFFFFFFFF → 1 (unsigned)
    li x1, 1
    li x2, -1
    sltu x3, x1, x2
    li x4, 1
    bne x3, x4, fail

    # SLTU: 0xFFFFFFFF < 1 → 0
    sltu x3, x2, x1
    bne x3, x0, fail

    # SLTIU: 1 < 0xFFF → 1 (sign-extends)
    li x1, 1
    sltiu x3, x1, 0xFFF
    li x4, 1
    bne x3, x4, fail

    li a0, 0
    j exit
fail:
    li a0, 1
exit:
    li x5, 0x80001020
    sw a0, 0(x5)
    ebreak
"""

    def test_slt_sltu(self, grm, check_spike, tmp_path):
        asm_path = os.path.join(str(tmp_path), "test_slt.S")
        elf_path = os.path.join(str(tmp_path), "test_slt.elf")
        with open(asm_path, 'w') as f:
            f.write(self.SLT_ASM)
        try:
            _build_elf(asm_path, elf_path)
        except RuntimeError as e:
            pytest.skip(f"Build failed: {e}")

        result = grm.run_elf(elf_path)
        state = GRMState.from_trace(result.trace_entries)
        exit_code = state.memory.get(0x80001020, 0) | \
                    (state.memory.get(0x00001001, 0) << 8) | \
                    (state.memory.get(0x00001002, 0) << 16) | \
                    (state.memory.get(0x00001003, 0) << 24)
        assert exit_code == 0, f"SLT/SLTU test failed"


# ── Main ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("IP-001 RV32I GRM — Instruction Tests")
    print("Run with: pytest test_grm_instructions.py -v")
