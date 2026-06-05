#!/usr/bin/env python3
"""
test_forwarding.py — Verify all forwarding paths in RV32I 5-stage pipeline.

Tests every forwarding scenario:
- EX/MEM → EX (rs1, rs2): previous instruction ALU result
- MEM/WB → EX (rs1, rs2): two-ago instruction result
- EX/MEM priority over MEM/WB
- Forwarding to store data
- Load forwarding after stall
- x0 forwarding suppression
- Store-after-load (no stall)

Usage:
    pytest verification/tests/test_forwarding.py -v
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


class TestForwardingEXMEM:
    """FW-01, FW-02: EX/MEM → EX on rs1 and rs2."""

    def test_exmem_rs1(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x5, x0, 100\n    addi x6, x5, 50\n"
        state = grm_run(body)
        assert state.regfile[5] == 100
        assert state.regfile[6] == 150

    def test_exmem_rs2(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x5, x0, 200\n    add x6, x0, x5\n"
        state = grm_run(body)
        assert state.regfile[6] == 200


class TestForwardingMEMWB:
    """FW-03, FW-04: MEM/WB → EX with gap instruction."""

    def test_memwb_rs1(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x5, x0, 300\n    addi x7, x0, 999\n    addi x6, x5, 50\n"
        state = grm_run(body)
        assert state.regfile[6] == 350

    def test_memwb_rs2(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x5, x0, 77\n    addi x7, x0, 55\n    add x6, x0, x5\n"
        state = grm_run(body)
        assert state.regfile[6] == 77


class TestForwardingPriority:
    """FW-05: EX/MEM overrides MEM/WB when both match."""

    def test_exmem_priority(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x5, x0, 100\n    addi x5, x5, 200\n    add x6, x5, x0\n"
        state = grm_run(body)
        assert state.regfile[5] == 300
        assert state.regfile[6] == 300

    def test_triple_chain(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x5, x0, 1\n    addi x5, x5, 1\n    addi x5, x5, 1\n    add x6, x5, x0\n"
        state = grm_run(body)
        assert state.regfile[6] == 3


class TestForwardingToStore:
    """FW-06: Store data forwarding from ALU result."""

    def test_store_forwarding(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x5, x0, 0xCAFE\n    sw x5, 0(x31)\n    lw x6, 0(x31)\n"
        state = grm_run(body)
        assert state.regfile[6] == 0x7AB


class TestLoadForwarding:
    """FW-07: Load → dependent instruction forwarding after stall."""

    def test_load_forward_after_stall(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    addi x5, x0, 42\n    sw x5, 0(x31)\n    lw x6, 0(x31)\n"
                "    addi x7, x6, 10\n")
        state = grm_run(body)
        assert state.regfile[6] == 42
        assert state.regfile[7] == 52

    def test_load_double_use(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    addi x5, x0, 99\n    sw x5, 0(x31)\n    lw x6, 0(x31)\n"
                "    addi x7, x6, 1\n    addi x0, x0, 0\n    addi x8, x6, 2\n")
        state = grm_run(body)
        assert state.regfile[7] == 100
        assert state.regfile[8] == 101


class TestX0ForwardingSuppression:
    """FW-08: Forwarding suppressed for x0."""

    def test_x0_no_forward(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = "    addi x0, x0, 42\n    addi x6, x0, 0\n"
        state = grm_run(body)
        assert state.regfile[0] == 0
        assert state.regfile[6] == 0

    def test_x0_chain(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    addi x5, x0, 999\n    addi x0, x5, 1\n"
                "    addi x0, x5, 2\n    add x6, x0, x0\n")
        state = grm_run(body)
        assert state.regfile[6] == 0


class TestStoreAfterLoad:
    """Store-after-load: no stall, forwarding handles it."""

    def test_store_after_load(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        body = ("    addi x5, x0, 0xFEED\n    sw x5, 16(x31)\n    lw x6, 16(x31)\n"
                "    sw x6, 20(x31)\n    lw x7, 20(x31)\n")
        state = grm_run(body)
        assert state.regfile[7] == 0x7ED


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
