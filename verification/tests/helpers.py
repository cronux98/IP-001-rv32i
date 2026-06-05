"""
Helpers for IP-001 verification tests.

Provides grm_run() for compiling assembly and running through Spike.
All test files import from here.
"""

import tempfile, os, subprocess
from pathlib import Path
from grm_config import config
from spike_grm import SpikeGRM, GRMState

LINKER_SCRIPT = """\
OUTPUT_ARCH(riscv)
ENTRY(_start)

MEMORY
{
    IMEM (rx)  : ORIGIN = 0x80000000, LENGTH = 32K
    DMEM (rw)  : ORIGIN = 0x80001000, LENGTH = 4K
}

SECTIONS
{
    .text : { *(.text.init) *(.text) *(.text.*) } > IMEM
    .rodata : { *(.rodata) *(.rodata.*) } > IMEM
    .htif 0x80001000 (NOLOAD) : {
        . = ALIGN(8);
        tohost = .;
        . += 8;
        fromhost = .;
        . += 8;
    }
    .data 0x80001020 : { *(.data) *(.data.*) *(.sdata*) } > DMEM
    .bss : { *(.bss) *(.bss.*) *(.sbss*) } > DMEM
    . = ALIGN(16);
    _stack_top = ORIGIN(DMEM) + LENGTH(DMEM);
}
"""

ASM_PREFIX = """\
.section .text.init
.globl _start
_start:
    # Set up data pointer in x31 (points to DMEM at 0x80001020, above HTIF)
    lui x31, 0x80001
    addi x31, x31, 0x020
"""

ASM_EXIT = """\
    # Exit via tohost (preserves all registers except t3=x28)
    lui t3, 0x80001
    li t4, 1
    sw t4, 0(t3)
"""


def grm_run(asm_body: str, timeout: int = 15) -> GRMState:
    """Compile RV32I assembly, run through Spike, return final GRMState.

    Args:
        asm_body: Assembly instructions (without entry/exit wrappers)
        timeout: Max seconds for Spike execution

    Returns:
        GRMState with final register/CSR/memory state
    """
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

        # Use as + ld directly to avoid CRT startup code
        r = subprocess.run(
            [config.RISCV_AS, '-march=rv32i', '-mabi=ilp32',
             '-o', obj_path, asm_path],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode != 0:
            raise RuntimeError(f"Assembly failed:\n{r.stderr}")

        r = subprocess.run(
            [config.RISCV_LD, '-m', 'elf32lriscv', '-nostdlib',
             '-T', ld_path, '-o', elf_path, obj_path],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode != 0:
            raise RuntimeError(f"Link failed:\n{r.stderr}")

        grm = SpikeGRM(config)
        return grm.run_and_get_state(elf_path, timeout=timeout)
    finally:
        for p in [asm_path, obj_path, elf_path, ld_path]:
            try:
                os.unlink(p)
            except OSError:
                pass
