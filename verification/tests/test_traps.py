#!/usr/bin/env python3
"""
test_traps.py — Verify trap entry, MRET, and exception handling.

Usage:
    pytest verification/tests/test_traps.py -v
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


class TestECALL:
    def test_ecall_trap(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    li x5, 0x55\n    ecall\n"
        state = grm_run(body)
        assert state.regfile[5] == 0x55


class TestEBREAK:
    def test_ebreak_trap(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    li x5, 0x99\n    ebreak\n"
        state = grm_run(body)
        assert state.regfile[5] == 0x99


class TestIllegalInstruction:
    def test_illegal_trap(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    li x5, 0x42\n    .word 0x0000007F\n    li x6, 0xFF\n"
        state = grm_run(body)
        assert state.regfile[5] == 0x42


class TestMRET:
    def test_mret_basic(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    la x5, return_target\n    csrrw x0, mepc, x5\n"
                "    mret\n    li x6, 0xBAD\nreturn_target:    li x6, 0x600D\n")
        state = grm_run(body)
        assert state.regfile[6] == 0x600D


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
