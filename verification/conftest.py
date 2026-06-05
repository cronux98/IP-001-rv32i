"""
conftest.py — Shared test fixtures for IP-001 RV32I verification.

Provides common fixtures used across all verification tests:
- SpikeGRM instance
- Scoreboard instance
- Coverage model
- Pipeline monitor
- Instruction generator
- Temporary directories
"""

import sys
import os
import tempfile
import pytest
from pathlib import Path

# Add project paths
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "grm" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "verification"))

from spike_grm import SpikeGRM, GRMState, TraceEntry, SpikeRunner
from grm_config import config, GRMConfig


@pytest.fixture(scope="session")
def grm():
    """Session-scoped SpikeGRM instance."""
    return SpikeGRM(config)


@pytest.fixture(scope="session")
def spike_available():
    """Check if Spike is available (skip tests if not)."""
    runner = SpikeRunner(config)
    return runner.is_available()


@pytest.fixture(scope="session")
def toolchain_available():
    """Check if RISC-V toolchain is available."""
    import subprocess
    for tool in ['riscv64-unknown-elf-gcc', 'riscv64-unknown-elf-as',
                 'riscv64-unknown-elf-ld']:
        if subprocess.run(['which', tool], capture_output=True).returncode != 0:
            return False
    return True


@pytest.fixture
def temp_dir():
    """Temporary directory for test artifacts."""
    with tempfile.TemporaryDirectory(prefix="ip001_verify_") as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def scoreboard():
    """Scoreboard instance."""
    from env.scoreboard import Scoreboard
    return Scoreboard(config)


@pytest.fixture
def coverage_model():
    """Fresh coverage model."""
    from env.coverage import CoverageModel
    return CoverageModel()


@pytest.fixture
def pipeline_monitor():
    """Pipeline monitor instance."""
    from env.pipeline_monitor import PipelineMonitor
    return PipelineMonitor()


@pytest.fixture
def instruction_generator():
    """Instruction generator with fixed seed."""
    from env.instruction_generator import InstructionGenerator
    return InstructionGenerator(seed=42, num_instructions=100)


@pytest.fixture
def trace_comparer():
    """Trace comparer with default bases."""
    from env.trace_compare import TraceComparer
    return TraceComparer(grm_base=0x80000000, dut_base=0x00000000)


LINKER_SCRIPT = f"""
OUTPUT_ARCH(riscv)
ENTRY(_start)

MEMORY
{{
    IMEM (rx)  : ORIGIN = 0x80000000, LENGTH = 32K
    DMEM (rw)  : ORIGIN = 0x80001000, LENGTH = 4K
}}

SECTIONS
{{
    .text : {{ *(.text.init) *(.text) *(.text.*) }} > IMEM
    .rodata : {{ *(.rodata) *(.rodata.*) }} > IMEM
    .htif 0x80001000 (NOLOAD) : {{
        . = ALIGN(8);
        tohost = .;
        . += 8;
        fromhost = .;
        . += 8;
    }}
    .data 0x80001020 : {{ *(.data) *(.data.*) *(.sdata*) }} > DMEM
    .bss : {{ *(.bss) *(.bss.*) *(.sbss*) }} > DMEM
    . = ALIGN(16);
    _stack_top = ORIGIN(DMEM) + LENGTH(DMEM);
}}
"""

ASM_PREFIX = """\
.section .text.init
.globl _start
_start:
"""

ASM_EXIT = """\
    # Exit via tohost
    li a0, 1
    la t0, tohost
    sw a0, 0(t0)
"""


def grm_run(asm_body: str) -> GRMState:
    """Compile assembly, run through Spike, return GRMState.

    Adds proper entry/exit wrappers automatically.
    """
    import subprocess
    from spike_grm import SpikeGRM

    full_asm = ASM_PREFIX + asm_body + "\n" + ASM_EXIT

    with tempfile.NamedTemporaryFile(mode='w', suffix='.S', delete=False) as f:
        f.write(full_asm)
        asm_path = f.name

    obj_path = asm_path + '.o'
    elf_path = asm_path + '.elf'
    ld_path = asm_path + '.ld'

    try:
        with open(ld_path, 'w') as f:
            f.write(LINKER_SCRIPT)

        r = subprocess.run(
            [config.RISCV_GCC, '-march=rv32i', '-mabi=ilp32', '-nostdlib',
             '-nostartfiles', '-static', '-T', ld_path,
             '-o', elf_path, asm_path],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode != 0:
            raise RuntimeError(f"Build failed:\n{r.stderr}")

        grm = SpikeGRM(config)
        return grm.run_and_get_state(elf_path, timeout=15)
    finally:
        for p in [asm_path, obj_path, elf_path, ld_path]:
            try:
                os.unlink(p)
            except OSError:
                pass


def pytest_configure(config):
    """Add custom markers."""
    config.addinivalue_line("markers", "requires_spike: test requires Spike simulator")
    config.addinivalue_line("markers", "requires_toolchain: test requires RISC-V toolchain")
    config.addinivalue_line("markers", "slow: test takes a long time")
