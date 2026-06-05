#!/usr/bin/env python3
"""
test_hazards.py — Verify pipeline hazard handling: load-use stalls, branches, jumps.

Usage:
    pytest verification/tests/test_hazards.py -v
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


class TestLoadUseStall:
    def test_load_use_rs1(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    addi x5, x0, 123\n    sw x5, 0(x31)\n    lw x6, 0(x31)\n"
                "    addi x7, x6, 77\n")
        state = grm_run(body)
        assert state.regfile[7] == 200

    def test_load_use_rs2(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    addi x5, x0, 50\n    sw x5, 0(x31)\n    lw x6, 0(x31)\n"
                "    add x7, x0, x6\n")
        state = grm_run(body)
        assert state.regfile[7] == 50

    def test_no_stall_no_dep(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    addi x5, x0, 99\n    sw x5, 0(x31)\n    lw x6, 0(x31)\n"
                "    addi x7, x3, 55\n")
        state = grm_run(body)
        assert state.regfile[7] == 55

    def test_no_stall_x0(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    addi x5, x0, 999\n    sw x5, 0(x31)\n    lw x0, 0(x31)\n"
                "    addi x6, x0, 0\n")
        state = grm_run(body)
        assert state.regfile[6] == 0

    def test_double_load_use(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    addi x5, x0, 10\n    addi x8, x0, 20\n"
                "    sw x5, 0(x31)\n    sw x8, 4(x31)\n"
                "    lw x6, 0(x31)\n    addi x7, x6, 5\n"
                "    lw x9, 4(x31)\n    addi x10, x9, 3\n")
        state = grm_run(body)
        assert state.regfile[7] == 15
        assert state.regfile[10] == 23


class TestBranchHazards:
    def test_beq_taken(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    addi x5, x0, 5\n    addi x6, x0, 5\n"
                "    beq x5, x6, 1f\n    addi x7, x0, 999\n1:  addi x7, x0, 42\n")
        state = grm_run(body)
        assert state.regfile[7] == 42

    def test_bne_taken(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    addi x5, x0, 5\n    addi x6, x0, 7\n"
                "    bne x5, x6, 1f\n    addi x7, x0, 999\n1:  addi x7, x0, 77\n")
        state = grm_run(body)
        assert state.regfile[7] == 77

    def test_blt_taken(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    addi x5, x0, 10\n    addi x6, x0, 5\n"
                "    blt x6, x5, 1f\n    addi x7, x0, 999\n1:  addi x7, x0, 55\n")
        state = grm_run(body)
        assert state.regfile[7] == 55

    def test_bge_taken(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    addi x5, x0, 10\n    addi x6, x0, 10\n"
                "    bge x5, x6, 1f\n    addi x7, x0, 999\n1:  addi x7, x0, 88\n")
        state = grm_run(body)
        assert state.regfile[7] == 88

    def test_bltu_taken(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    addi x5, x0, 2047\n    addi x6, x0, -1\n"
                "    bltu x5, x6, 1f\n    addi x7, x0, 999\n1:  addi x7, x0, 33\n")
        state = grm_run(body)
        assert state.regfile[7] == 33

    def test_bgeu_not_taken(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    addi x5, x0, 5\n    addi x6, x0, 10\n"
                "    bgeu x5, x6, 1f\n    addi x7, x0, 100\n1:  addi x0, x0, 0\n")
        state = grm_run(body)
        assert state.regfile[7] == 100

    def test_branch_with_fwd_ops(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    addi x5, x0, 5\n    addi x5, x5, 5\n    addi x6, x0, 10\n"
                "    beq x5, x6, 1f\n    addi x7, x0, 999\n1:  addi x7, x0, 55\n")
        state = grm_run(body)
        assert state.regfile[7] == 55


class TestJumpHazards:
    def test_jal_target_and_link(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    jal x1, target\n    addi x0, x0, 0\ntarget:    addi x2, x0, 42\n"
        state = grm_run(body)
        assert state.regfile[2] == 42
        assert state.regfile[1] >= 0x80000004  # JAL link near start

    def test_jalr_link(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x5, x0, 0x10\n    jalr x1, x5, 0\n    addi x2, x0, 42\n"
        state = grm_run(body)
        assert state.regfile[1] == 0x80000008


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
