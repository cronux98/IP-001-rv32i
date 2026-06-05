#!/usr/bin/env python3
"""
test_pipeline.py — Verify pipeline control: stall, flush, NOP, reset.

Usage:
    pytest verification/tests/test_pipeline.py -v
"""

import sys, pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "grm" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "verification"))
sys.path.insert(0, str(PROJECT_ROOT / "verification" / "tests"))

from helpers import grm_run


@pytest.fixture(scope="module")
def tools_ok():
    import subprocess
    for tool in ['riscv64-unknown-elf-as', 'riscv64-unknown-elf-ld', 'spike']:
        if subprocess.run(['which', tool], capture_output=True).returncode != 0:
            return False
    return True


class TestNormalFlow:
    def test_sequential_no_hazards(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "\n".join(f"    addi x{i}, x0, {i}" for i in range(1, 11))
        state = grm_run(body)
        for i in range(1, 11):
            assert state.regfile[i] == i
        assert state.regfile[0] == 0

    def test_nop_no_side_effects(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    addi x5, x0, 42\n    addi x0, x0, 0\n"
                "    addi x0, x0, 0\n    addi x0, x0, 0\n    addi x6, x5, 0\n")
        state = grm_run(body)
        assert state.regfile[5] == 42
        assert state.regfile[6] == 42


class TestStallFlushInteraction:
    def test_load_use_result_correct(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    addi x5, x0, 77\n    sw x5, 0(x31)\n    lw x6, 0(x31)\n"
                "    addi x7, x6, 23\n")
        state = grm_run(body)
        assert state.regfile[7] == 100

    def test_multiple_stalls(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    addi x5, x0, 10\n    addi x8, x0, 20\n"
                "    sw x5, 0(x31)\n    sw x8, 4(x31)\n"
                "    lw x6, 0(x31)\n    lw x9, 4(x31)\n    add x10, x6, x9\n")
        state = grm_run(body)
        assert state.regfile[10] == 30

    def test_branch_flush_correct(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    li x5, 5\n    li x6, 5\n    beq x5, x6, 1f\n"
                "    li x7, 999\n    li x8, 888\n1:  li x7, 42\n    li x8, 43\n")
        state = grm_run(body)
        assert state.regfile[7] == 42
        assert state.regfile[8] == 43

    def test_jal_flush_correct(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    j 1f\n    li x5, 999\n    li x6, 888\n1:  li x5, 0x123\n"
        state = grm_run(body)
        assert state.regfile[5] == 0x123


class TestPipelineEdgeCases:
    def test_all_registers(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "\n".join(f"    addi x{i}, x0, {i*7}" for i in range(1, 32))
        state = grm_run(body)
        for i in range(1, 32):
            assert state.regfile[i] == i * 7

    def test_dependency_chain(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        lines = ["    addi x1, x0, 1"]
        lines.extend(f"    addi x{i}, x{i-1}, 1" for i in range(2, 32))
        state = grm_run("\n".join(lines))
        for i in range(1, 32):
            assert state.regfile[i] == i

    def test_zero_result_chain(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    addi x5, x0, 5\n    sub x6, x5, x5\n"
                "    add x7, x6, x0\n    addi x8, x7, 10\n")
        state = grm_run(body)
        assert state.regfile[6] == 0
        assert state.regfile[7] == 0
        assert state.regfile[8] == 10

    def test_max_values(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    lui x5, 0x80000\n    srli x6, x5, 1\n    srai x7, x5, 1\n")
        state = grm_run(body)
        assert state.regfile[5] == 0x80000000
        assert state.regfile[6] == 0x40000000
        assert state.regfile[7] == 0xC0000000

    def test_loop(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    li x5, 0\n    li x6, 10\n"
                "1:  addi x5, x5, 1\n    addi x6, x6, -1\n    bnez x6, 1b\n")
        state = grm_run(body)
        assert state.regfile[5] == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
