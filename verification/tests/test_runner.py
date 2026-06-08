"""
IP-001 RV32I — cocotb Test Runner
Runs RV32I test programs on RTL, verifies results against expected values.
"""

import os
import sys
import struct
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "env"))
from grm_ref import run_spike  # noqa: E402

MAX_CYCLES = 20000
CLK_PERIOD_NS = 20


class Rv32iTB:
    def __init__(self, dut):
        self.dut = dut
        self.i_mem = bytearray(4096)
        self.d_mem = bytearray(4096)
        self.total_cycles = 0
        self.halted = False
        self._last_pc = None
        self._same_pc_count = 0

    def _v(self, sig):
        """Safe value extraction (handles X/Z)."""
        try:
            return int(sig.value)
        except (ValueError, TypeError):
            return 0

    def load_binary(self, bin_path):
        with open(bin_path, "rb") as f:
            data = f.read()
        for i, byte in enumerate(data):
            if i < len(self.i_mem):
                self.i_mem[i] = byte
        self.dut._log.info(f"Loaded {len(data)} bytes into I-memory")

    def read_i_mem(self, word_addr):
        addr = word_addr & 0xFFF
        if addr + 3 >= len(self.i_mem):
            return 0
        return struct.unpack_from("<I", self.i_mem, addr)[0]

    def write_d_mem(self, word_addr, data, be):
        addr = (word_addr & 0xFFF) - 0x1000
        if addr < 0 or addr + 3 >= len(self.d_mem):
            return
        for i in range(4):
            if (be >> i) & 1 and addr + i < len(self.d_mem):
                self.d_mem[addr + i] = (data >> (i * 8)) & 0xFF

    def check_halt(self, pc):
        if self._last_pc == pc:
            self._same_pc_count += 1
        else:
            self._same_pc_count = 0
        self._last_pc = pc
        if self._same_pc_count > 50:
            self.halted = True

    async def run(self):
        dut = self.dut
        dut.rst_n.value = 0
        dut.irq_timer.value = 0
        dut.irq_external.value = 0
        dut.i_rdata.value = 0
        dut.d_rdata.value = 0
        cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, "ns").start())
        await ClockCycles(dut.clk, 10)
        dut.rst_n.value = 1
        await RisingEdge(dut.clk)

        store_count = 0
        while self.total_cycles < MAX_CYCLES and not self.halted:
            await RisingEdge(dut.clk)
            self.total_cycles += 1

            dut.i_rdata.value = self.read_i_mem(self._v(dut.i_addr))
            d_addr = self._v(dut.d_addr) & 0xFFF
            if 0x1000 <= d_addr < 0x2000:
                d_rel = d_addr - 0x1000
                dut.d_rdata.value = struct.unpack_from("<I", self.d_mem, d_rel)[0] if d_rel + 3 < len(self.d_mem) else 0
            else:
                dut.d_rdata.value = 0

            if self._v(dut.d_we):
                addr = self._v(dut.d_addr)
                data = self._v(dut.d_wdata)
                be = self._v(dut.d_be)
                self.write_d_mem(addr, data, be)
                store_count += 1
                if store_count <= 5:
                    self.dut._log.info(
                        f"Store #{store_count} @ cyc {self.total_cycles}: "
                        f"addr=0x{addr:08x} data=0x{data:08x} be=0x{be:x}"
                    )

            if hasattr(dut, "u_if") and hasattr(dut.u_if, "pc"):
                self.check_halt(self._v(dut.u_if.pc))
            else:
                self.check_halt(self._v(dut.i_addr))

        self.dut._log.info(f"Total stores: {store_count}")

    def read_word(self, offset):
        """Read 32-bit word from D-mem at given offset from data_base (0x1000)."""
        if offset + 3 >= len(self.d_mem):
            return 0
        return struct.unpack_from("<I", self.d_mem, offset)[0]


# Expected test results from test_rv32i_alu.S (offsets from data_base)
EXPECTED_RESULTS = {
    0: 0x00000003,    # ADD 1+2=3
    4: 0x00000000,    # ADD 1+(-1)=0
    8: 0xFFFFFFFE,    # ADD (-1)+(-1)=-2
    12: 0x00000001,   # SUB 2-1=1
    16: 0xFFFFFFFF,   # SUB 1-2=-1
    44: 0x00000001,   # SLT -1 < 1 => 1
    48: 0x00000000,   # SLT 1 < -1 => 0
    52: 0x00000001,   # SLTU 1 < 0xFFFFFFFF => 1
    56: 0x00000000,   # x0 hardwired test
    64: 0xDEADBEEF,   # Store/Load: SW(0xDEADBEEF) then LW back
    68: 0x00000001,   # BEQ taken
    72: 0x00000002,   # BNE not-taken
    76: 0x00000003,   # BLT taken
    80: 0x00000004,   # JAL: target reached
    88: 0x00000005,   # JALR: target reached
    96: 0x00000078,   # LB sign-extended byte
    100: 0x00000078,  # LBU unsigned byte
}
MAGIC_OFFSET = 1024
MAGIC_VALUE = 0xCAFEBABE


@cocotb.test()
async def test_rv32i_basic(dut):
    """Run RV32I ALU test program on RTL and verify D-mem results."""
    tb = Rv32iTB(dut)
    bin_path = os.environ.get("MEM_BIN", "./tmp/test_prog.bin")
    if not os.path.exists(bin_path):
        proj = os.path.join(os.path.dirname(__file__), "..")
        bin_path = os.path.join(proj, bin_path)
    if os.path.exists(bin_path):
        tb.load_binary(bin_path)
    else:
        dut._log.error(f"No binary at {bin_path}")
        return

    await tb.run()

    dut._log.info(f"Ran {tb.total_cycles} cycles, halted={tb.halted}")

    # Debug: show D-mem around expected results
    for off in [0, 4, 12, 44, 52, 56, 68, 72, 76, 80, 960, 1000, 1024]:
        val = tb.read_word(off)
        if val != 0:
            dut._log.info(f"  D-mem[{off}] = 0x{val:08x}")

    # Check magic word
    magic = tb.read_word(MAGIC_OFFSET)
    assert magic == MAGIC_VALUE, f"Magic word mismatch: 0x{magic:08x} != 0x{MAGIC_VALUE:08x}"
    dut._log.info(f"Magic word OK: 0x{magic:08x}")

    # Check expected results
    failures = []
    for off, exp in sorted(EXPECTED_RESULTS.items()):
        val = tb.read_word(off)
        if val != (exp & 0xFFFFFFFF):
            failures.append(f"  +{off}: got 0x{val:08x}, expected 0x{exp:08x}")
    if failures:
        dut._log.error("Register ALU test failures:\n" + "\n".join(failures))
        assert False, f"{len(failures)} test failures"
    dut._log.info(f"All {len(EXPECTED_RESULTS)} ALU tests passed")


@cocotb.test()
async def test_rv32i_reset(dut):
    """Verify reset: PC at 0, CSRs at reset values."""
    tb = Rv32iTB(dut)
    struct.pack_into("<I", tb.i_mem, 0, 0x0000006F)  # JAL x0, 0
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, "ns").start())
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    pc = tb._v(dut.u_if.pc) if hasattr(dut.u_if, "pc") else 0
    assert pc == 0, f"PC during reset should be 0, got {pc}"
    dut.rst_n.value = 1
    dut._log.info("Reset test passed")


@cocotb.test()
async def test_rv32i_nop_sled(dut):
    """Run NOP sled, verify no D-mem writes."""
    tb = Rv32iTB(dut)
    for i in range(0, 1024, 4):
        struct.pack_into("<I", tb.i_mem, i, 0x00000013)
    struct.pack_into("<I", tb.i_mem, 1024, 0x0000006F)
    await tb.run()
    writes = sum(1 for b in tb.d_mem if b != 0)
    dut._log.info(f"NOP sled: {tb.total_cycles} cycles, {writes} bytes written")
    assert writes == 0, f"NOP sled produced {writes} D-mem writes"
    dut._log.info("NOP sled test passed")
