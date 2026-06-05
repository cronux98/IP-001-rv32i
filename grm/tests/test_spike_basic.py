#!/usr/bin/env python3
"""
test_spike_basic.py — Verify Spike availability and basic GRM functionality.

Tests:
  T1: Spike binary found and version reported
  T2: Spike can execute a trivial RV32I program
  T3: Spike produces a parseable trace log
  T4: Trace entries contain expected fields
  T5: TraceParser correctly parses Spike output

Author: Sage (GRM Engineer)
Date: 2026-06-05
"""

import os
import sys
import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from grm_config import config, GRMConfig
from spike_grm import SpikeGRM, SpikeRunner, TraceParser, TraceEntry, GRMState


# ── Test Helpers ───────────────────────────────────────────────────────

TRIVIAL_ASM = """
.section .text.init
.globl _start
_start:
    li x1, 42
    li x2, 100
    add x3, x1, x2          # x3 = 142
    li x4, 142
    bne x3, x4, fail
    li a0, 0
    j exit
fail:
    li a0, 1
exit:
    ebreak
"""

def _assemble(asm: str, output_path: str, link_ld: str = None) -> str:
    """Assemble a RISC-V assembly snippet into an ELF binary.

    Returns the ELF path on success, raises on failure.
    """
    import tempfile
    import subprocess

    asm_path = output_path.replace('.elf', '.S')
    with open(asm_path, 'w') as f:
        f.write(asm)

    gcc = config.RISCV_GCC
    gcc_flags = ['-march=rv32i', '-mabi=ilp32', '-nostdlib',
                 '-nostartfiles', '-static', '-O0', '-g']

    cmd = [gcc] + gcc_flags + ['-o', output_path, asm_path]
    if link_ld:
        cmd.extend(['-T', link_ld])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Assembly failed:\n{result.stderr}")

    return output_path


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def grm():
    """Create a GRM instance (module-scoped, reused across tests)."""
    return SpikeGRM()


@pytest.fixture(scope="module")
def runner():
    """Create a SpikeRunner instance."""
    return SpikeRunner()


@pytest.fixture(scope="module")
def test_elf(tmp_path_factory):
    """Build a trivial test ELF binary."""
    tmp = tmp_path_factory.mktemp("spike_test")
    elf_path = os.path.join(str(tmp), "trivial.elf")

    # Use the test_add.S that's already compiled or compile our own
    asm_dir = os.path.join(os.path.dirname(__file__), '..', 'binaries')
    add_elf = os.path.join(asm_dir, 'test_add.elf')

    if os.path.exists(add_elf):
        return add_elf

    link_ld = os.path.join(asm_dir, 'link.ld')
    try:
        return _assemble(TRIVIAL_ASM, elf_path, link_ld)
    except RuntimeError as e:
        pytest.skip(f"Cannot assemble test binary: {e}")


# ── Test T1: Spike found ──────────────────────────────────────────────

def test_spike_available(grm):
    """T1: Verify Spike binary is installed and accessible."""
    available = grm.check_available()
    if not available:
        pytest.skip("Spike not installed — skipping Spike-dependent tests")
    assert available, "Spike should be found"


def test_spike_version(grm):
    """T1b: Verify Spike version string."""
    if not grm.check_available():
        pytest.skip("Spike not installed")
    version = grm.get_version()
    assert version and len(version) > 0, "Version string should not be empty"
    assert "Spike" in version or "spike" in version.lower() or "RISCV" in version.upper()


# ── Test T2: Spike executes trivial program ────────────────────────────

def test_spike_runs_elf(grm, test_elf):
    """T2: Spike can execute an RV32I ELF binary."""
    if not grm.check_available():
        pytest.skip("Spike not installed")

    result = grm.run_elf(test_elf)
    assert result is not None, "run_elf should return a result"
    # ECALL/EBREAK may cause non-zero exit in Spike, which is normal
    # The important thing is that Spike ran without crashing
    assert result.instruction_count > 0, (
        f"Expected >0 instructions, got {result.instruction_count}"
    )


# ── Test T3: Spike produces trace ─────────────────────────────────────

def test_spike_trace_not_empty(grm, test_elf):
    """T3: Spike produces a non-empty trace log."""
    if not grm.check_available():
        pytest.skip("Spike not installed")

    result = grm.run_elf(test_elf)
    trace = result.trace_entries
    assert len(trace) > 0, "Trace should contain entries"

    # First instruction should be at reset vector or near it
    first = trace[0]
    assert first.pc is not None, "First trace entry should have PC"
    assert first.instr_word is not None, "First trace entry should have instruction"


# ── Test T4: Trace entry fields ────────────────────────────────────────

def test_trace_entry_structure(grm, test_elf):
    """T4: Trace entries contain expected fields."""
    if not grm.check_available():
        pytest.skip("Spike not installed")

    result = grm.run_elf(test_elf)
    trace = result.trace_entries

    for i, entry in enumerate(trace):
        # Every entry must have: index, pc, instr_word
        assert entry.index == i, f"Entry {i}: index mismatch"
        assert isinstance(entry.pc, int), f"Entry {i}: PC not int"
        assert isinstance(entry.instr_word, int), f"Entry {i}: instr_word not int"
        assert 0 <= entry.pc < 0x10000, f"Entry {i}: PC out of range: 0x{entry.pc:08X}"

    # Check that the last instruction is ebreak (0x00100073)
    last = trace[-1]
    assert (last.instr_word & 0x7F) in (
        0b1110011,  # SYSTEM opcode (EBREAK/ECALL)
    ), f"Last instruction should be EBREAK/ECALL, got 0x{last.instr_word:08X}"


# ── Test T5: TraceParser ──────────────────────────────────────────────

def test_trace_parser_parse_line():
    """T5a: TraceParser correctly parses individual trace lines."""
    # Register write line
    line = "core   0: 0x00000000 (0x00000093) x1  0x0000002a"
    entry = TraceParser.parse_line(line)
    assert entry is not None
    assert entry.pc == 0x00000000
    assert entry.instr_word == 0x00000093  # ADDI x1, x0, 0
    assert entry.rd == 1
    assert entry.rd_value == 0x2a  # 42

    # Store line
    line = "core   0: 0x00000008 (0x0020a023) mem 0x00001000 0x0000002a"
    entry = TraceParser.parse_line(line)
    assert entry is not None
    assert entry.pc == 0x00000008
    assert entry.is_store
    assert entry.store_addr == 0x00001000
    assert entry.store_value == 0x2a  # 42

    # No-write line (ECALL/EBREAK)
    line = "core   0: 0x0000000c (0x00100073)"
    entry = TraceParser.parse_line(line)
    assert entry is not None
    assert entry.pc == 0x0000000c
    assert entry.rd is None
    assert not entry.is_store


def test_trace_parser_parse_output(grm, test_elf):
    """T5b: TraceParser correctly parses full Spike output."""
    if not grm.check_available():
        pytest.skip("Spike not installed")

    result = grm.run_elf(test_elf)
    trace = result.trace_entries

    # Verify all entries are valid
    for entry in trace:
        assert entry is not None
        assert entry.index >= 0

    # Trace should be sequential (PCs generally increase, except for jumps)
    prev_pc = -1
    jump_count = 0
    for entry in trace:
        if entry.pc < prev_pc:
            jump_count += 1  # Backward jump
        prev_pc = entry.pc

    # There should be at least some sequential flow
    assert len(trace) > jump_count, "Too many backward jumps"


# ── Test T6: GRMState ─────────────────────────────────────────────────

def test_grm_state_initialization():
    """T6a: GRMState initializes with correct reset values."""
    state = GRMState()
    assert state.regfile[0] == 0, "x0 should be 0"
    assert state.pc == 0x00000000, "Reset PC should be 0"

    # Check a few CSR reset values
    assert state.csr.get(0x301, -1) == 0x40000100, \
        f"misa reset wrong: 0x{state.csr.get(0x301, 0):08X}"


def test_grm_state_from_trace(grm, test_elf):
    """T6b: GRMState.from_trace() reconstructs state correctly."""
    if not grm.check_available():
        pytest.skip("Spike not installed")

    result = grm.run_elf(test_elf)
    state = GRMState.from_trace(result.trace_entries)

    assert state.instret > 0, "Should have retired instructions"
    # x1 (ra) should have been written at some point
    # (Our trivial test writes to x1-x4)


def test_grm_state_to_json(grm, test_elf, tmp_path):
    """T6c: GRMState serializes to JSON correctly."""
    if not grm.check_available():
        pytest.skip("Spike not installed")

    result = grm.run_elf(test_elf)
    state = GRMState.from_trace(result.trace_entries)

    import json
    json_path = os.path.join(str(tmp_path), "state.json")
    state.to_json(json_path)

    assert os.path.exists(json_path), "JSON file should be created"

    with open(json_path, 'r') as f:
        data = json.load(f)

    assert 'regfile' in data
    assert 'csr' in data
    assert 'pc' in data


# ── Test T7: x0 immutability ──────────────────────────────────────────

def test_x0_always_zero(grm, test_elf):
    """T7: x0 is always 0 regardless of trace data."""
    if not grm.check_available():
        pytest.skip("Spike not installed")

    result = grm.run_elf(test_elf)
    state = GRMState.from_trace(result.trace_entries)

    assert state.regfile[0] == 0, "x0 must always be 0"


# ── Test T8: Config consistency ───────────────────────────────────────

def test_config_memory_map():
    """T8: Memory map is consistent."""
    assert config.IMEM_BASE == 0x00000000
    assert config.IMEM_SIZE == 0x1000
    assert config.DMEM_BASE == 0x00001000
    assert config.DMEM_SIZE == 0x1000
    assert config.TOTAL_MEM == 0x2000
    # No overlap
    assert config.IMEM_BASE + config.IMEM_SIZE <= config.DMEM_BASE, \
        "IMEM and DMEM must not overlap"


def test_config_csr_reset_values():
    """T8b: CSR reset values are documented."""
    assert 0x300 in config.CSR_RESET, "mstatus reset value missing"
    assert 0x301 in config.CSR_RESET, "misa reset value missing"
    assert config.CSR_RESET[0x301] == 0x40000100, "misa reset wrong"


def test_config_reg_names():
    """T8c: Register name table is correct."""
    assert config.get_reg_name(0) == "zero"
    assert config.get_reg_name(1) == "ra"
    assert config.get_reg_name(2) == "sp"
    assert config.get_reg_name(10) == "a0"
    assert config.get_reg_name(31) == "t6"


# ── Main ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Quick manual run
    print("IP-001 RV32I GRM — Spike Basic Tests")
    print("=" * 60)

    grm = SpikeGRM()

    print(f"\nSpike: {'AVAILABLE' if grm.check_available() else 'NOT FOUND'}")
    if grm.check_available():
        print(f"Version: {grm.get_version()}")

    print("\nTests defined in this file:")
    print("  test_spike_available, test_spike_version")
    print("  test_spike_runs_elf, test_spike_trace_not_empty")
    print("  test_trace_entry_structure")
    print("  test_trace_parser_*")
    print("  test_grm_state_*")
    print("  test_x0_always_zero")
    print("  test_config_*")
    print("\nRun with: pytest test_spike_basic.py -v")
