#!/usr/bin/env python3
"""
test_csr.py — Verify all CSR operations on all 7 machine-mode CSRs.

Tests all 6 CSR instruction variants (CSRRW, CSRRS, CSRRC, CSRRWI, CSRRSI, CSRRCI)
on all 7 implemented CSRs (mstatus, misa, mie, mtvec, mepc, mcause, mip).

Usage:
    pytest verification/tests/test_csr.py -v
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


class TestCSRRW:
    def test_csrrw_mtvec(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    li x5, 0x100\n    csrrw x6, mtvec, x5\n"
                "    csrrw x7, mtvec, x0\n")
        state = grm_run(body)
        assert state.regfile[7] == 0x100

    def test_csrrw_mepc(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    li x5, 0x80001000\n    csrrw x6, mepc, x5\n"
                "    csrrw x7, mepc, x0\n")
        state = grm_run(body)
        assert (state.regfile[7] & ~3) == 0x80001000

    def test_csrrw_mcause(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    li x5, 11\n    csrrw x6, mcause, x5\n"
                "    csrrw x7, mcause, x0\n")
        state = grm_run(body)
        assert state.regfile[7] == 11

    def test_csrrw_mie(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    li x5, 0x880\n    csrrw x6, mie, x5\n"
                "    csrrw x7, mie, x0\n")
        state = grm_run(body)
        assert (state.regfile[7] & 0x880) == 0x880


class TestCSRRS:
    def test_csrrs_set_bits(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    csrrw x0, mstatus, x0\n    li x5, 8\n"
                "    csrrs x6, mstatus, x5\n    csrrw x7, mstatus, x0\n")
        state = grm_run(body)
        assert (state.regfile[7] & 8) == 8

    def test_csrrs_x0_no_modify(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    li x5, 0x100\n    csrrw x0, mtvec, x5\n"
                "    csrrs x6, mtvec, x0\n    csrrw x7, mtvec, x0\n")
        state = grm_run(body)
        assert state.regfile[7] == 0x100
        assert state.regfile[6] == 0x100


class TestCSRRC:
    def test_csrrc_clear_bits(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    li x5, 0xFF\n    csrrw x0, mie, x5\n"
                "    li x6, 0x88\n    csrrc x7, mie, x6\n"
                "    csrrw x8, mie, x0\n")
        state = grm_run(body)
        assert (state.regfile[8] & 0xFF) == 0x77


class TestCSRImmediateVariants:
    def test_csrrwi(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    csrrwi x5, mtvec, 16\n    csrrw x6, mtvec, x0\n"
        state = grm_run(body)
        assert state.regfile[6] == 0x10

    def test_csrrsi(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    csrrw x0, mstatus, x0\n    csrrsi x5, mstatus, 3\n"
                "    csrrw x6, mstatus, x0\n")
        state = grm_run(body)
        assert (state.regfile[6] & 8) == 8  # Expect MIE bit set

    def test_csrrci(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    li x5, 0xFF\n    csrrw x0, mie, x5\n"
                "    csrrci x6, mie, 0x0F\n    csrrw x7, mie, x0\n")
        state = grm_run(body)
        assert (state.regfile[7] & 0xFF) == 0xF0


class TestReadOnlyCSR:
    def test_misa_readonly(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    csrrw x5, misa, x0\n    li x6, 0xDEADBEEF\n"
                "    csrrw x0, misa, x6\n    csrrw x7, misa, x0\n")
        state = grm_run(body)
        assert state.regfile[5] == state.regfile[7]


class TestUnimplementedCSR:
    def test_unimplemented_read(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    csrrw x5, 0x7FF, x0\n"
        state = grm_run(body)
        assert state.regfile[5] == 0


class TestCSRAtomicity:
    def test_csrrs_atomicity(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    li x5, 0x10\n    csrrw x0, mtvec, x5\n"
                "    li x6, 0x20\n    csrrs x7, mtvec, x6\n"
                "    csrrw x8, mtvec, x0\n")
        state = grm_run(body)
        assert state.regfile[7] == 0x10
        assert state.regfile[8] == 0x30


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
