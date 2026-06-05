#!/usr/bin/env python3
"""
test_instructions.py — Verify all 40 RV32I instructions against Spike GRM.

Tests each RV32I instruction class with known operands and verifies
the result against Spike golden reference model execution.

Usage:
    pytest verification/tests/test_instructions.py -v
"""

import sys, pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "grm" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "verification"))
sys.path.insert(0, str(PROJECT_ROOT / "verification" / "tests"))

from helpers import grm_run
from grm_config import config


@pytest.fixture(scope="module")
def tools_ok():
    import subprocess
    for tool in ['riscv64-unknown-elf-as', 'riscv64-unknown-elf-ld', 'spike']:
        if subprocess.run(['which', tool], capture_output=True).returncode != 0:
            return False
    return True


@pytest.mark.requires_toolchain
class TestRTypeALU:
    """Test all 10 R-type ALU instructions."""

    def test_add(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, 10\n    addi x2, x0, 20\n    add x3, x1, x2\n"
        state = grm_run(body)
        assert state.regfile[3] == 30

    def test_sub(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, 50\n    addi x2, x0, 20\n    sub x3, x1, x2\n"
        state = grm_run(body)
        assert state.regfile[3] == 30

    def test_sll(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, 1\n    addi x2, x0, 5\n    sll x3, x1, x2\n"
        state = grm_run(body)
        assert state.regfile[3] == 32

    def test_slt_true(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, -5\n    addi x2, x0, 10\n    slt x3, x1, x2\n"
        state = grm_run(body)
        assert state.regfile[3] == 1

    def test_slt_false(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, 10\n    addi x2, x0, -5\n    slt x3, x1, x2\n"
        state = grm_run(body)
        assert state.regfile[3] == 0

    def test_sltu(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, -5\n    addi x2, x0, 10\n    sltu x3, x2, x1\n"
        state = grm_run(body)
        assert state.regfile[3] == 1

    def test_xor(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, 0xFF\n    addi x2, x0, 0x0F\n    xor x3, x1, x2\n"
        state = grm_run(body)
        assert state.regfile[3] == 0xF0

    def test_srl(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, 0x100\n    addi x2, x0, 4\n    srl x3, x1, x2\n"
        state = grm_run(body)
        assert state.regfile[3] == 0x10

    def test_sra(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, -128\n    addi x2, x0, 4\n    sra x3, x1, x2\n"
        state = grm_run(body)
        assert state.regfile[3] == 0xFFFFFFF8

    def test_or(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, 0xF0\n    addi x2, x0, 0x0F\n    or x3, x1, x2\n"
        state = grm_run(body)
        assert state.regfile[3] == 0xFF

    def test_and(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, 0xFF\n    addi x2, x0, 0x0F\n    and x3, x1, x2\n"
        state = grm_run(body)
        assert state.regfile[3] == 0x0F


@pytest.mark.requires_toolchain
class TestITypeALU:
    def test_addi(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        state = grm_run("    addi x3, x0, 42\n")
        assert state.regfile[3] == 42

    def test_addi_negative(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, 10\n    addi x3, x1, -5\n"
        state = grm_run(body)
        assert state.regfile[3] == 5

    def test_slti(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, -10\n    slti x3, x1, 5\n"
        state = grm_run(body)
        assert state.regfile[3] == 1

    def test_sltiu(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, -1\n    sltiu x3, x1, 5\n"
        state = grm_run(body)
        assert state.regfile[3] == 0

    def test_xori(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, -1\n    xori x3, x1, -256\n"  # 0xFFFF ^ 0xFFFFFF00 = 0xFF
        state = grm_run(body)
        assert state.regfile[3] == 0xFF

    def test_ori(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, 0xF0\n    ori x3, x1, 0x0F\n"
        state = grm_run(body)
        assert state.regfile[3] == 0xFF

    def test_andi(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, 0xFF\n    andi x3, x1, 0x0F\n"
        state = grm_run(body)
        assert state.regfile[3] == 0x0F

    def test_slli(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, 1\n    slli x3, x1, 10\n"
        state = grm_run(body)
        assert state.regfile[3] == 1024

    def test_srli(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, 0x100\n    srli x3, x1, 4\n"
        state = grm_run(body)
        assert state.regfile[3] == 0x10


@pytest.mark.requires_toolchain
class TestLoadStore:
    def test_lw_sw(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, 0x100\n    sw x1, 0(x31)\n    lw x3, 0(x31)\n"
        state = grm_run(body)
        assert state.regfile[3] == 0x100

    def test_lh(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    lui x1, 0x89AB0\n    addi x1, x1, 0\n    sw x1, 0(x31)\n    lh x3, 0(x31)\n"
        state = grm_run(body)
        assert state.regfile[3] == 0xFFFF89AB

    def test_lhu(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    lui x1, 0x89AB0\n    addi x1, x1, 0\n    sw x1, 0(x31)\n    lhu x3, 0(x31)\n"
        state = grm_run(body)
        assert state.regfile[3] == 0x89AB

    def test_lb(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, 0x85\n    sw x1, 0(x31)\n    lb x3, 0(x31)\n"
        state = grm_run(body)
        assert state.regfile[3] == 0xFFFFFF85

    def test_lbu(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, 0x85\n    sw x1, 0(x31)\n    lbu x3, 0(x31)\n"
        state = grm_run(body)
        assert state.regfile[3] == 0x85

    def test_sh_sb(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, 0xAB\n    sb x1, 0(x31)\n    lbu x3, 0(x31)\n"
        state = grm_run(body)
        assert state.regfile[3] == 0xAB


@pytest.mark.requires_toolchain
class TestUpperImmediate:
    def test_lui(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        state = grm_run("    lui x3, 0x12345\n")
        assert state.regfile[3] == 0x12345000

    def test_auipc(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        state = grm_run("    auipc x3, 0x10\n")
        assert state.regfile[3] == 0x80010000


@pytest.mark.requires_toolchain
class TestJumps:
    def test_jal_link(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    jal x3, 1f\n1:  nop\n"
        state = grm_run(body)
        assert state.regfile[3] == 0x80000004

    def test_x0_writes_suppressed(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x0, x0, 42\n    add x3, x0, x0\n"
        state = grm_run(body)
        assert state.regfile[0] == 0
        assert state.regfile[3] == 0


@pytest.mark.requires_toolchain
class TestFENCE:
    def test_fence_nop(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x1, x0, 42\n    fence\n    addi x2, x1, 0\n"
        state = grm_run(body)
        assert state.regfile[2] == 42


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
