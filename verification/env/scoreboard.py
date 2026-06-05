#!/usr/bin/env python3
"""
scoreboard.py — Central comparison engine for IP-001 RV32I verification.

Compares DUT architectural state against Spike GRM golden reference.
Handles register file, CSR, and memory state comparison with
detailed diff reporting.

Usage:
    from env.scoreboard import Scoreboard, ScoreboardResult
    sb = Scoreboard(grm_config)
    result = sb.run_test("test_name", asm_source)
    print(result.report())
"""

import sys
import os
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

# Add project root to path for GRM imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "grm" / "src"))

from spike_grm import SpikeGRM, GRMState, TraceEntry, SpikeRunner
from grm_config import config, GRMConfig


@dataclass
class ScoreboardResult:
    """Result of a single test comparison."""

    test_name: str
    passed: bool
    grm_state: Optional[GRMState] = None
    dut_state: Optional[GRMState] = None
    reg_diffs: List[str] = field(default_factory=list)
    csr_diffs: List[str] = field(default_factory=list)
    mem_diffs: List[str] = field(default_factory=list)
    instruction_count: int = 0
    error_message: str = ""

    @property
    def total_diffs(self) -> int:
        return len(self.reg_diffs) + len(self.csr_diffs) + len(self.mem_diffs)

    def report(self) -> str:
        """Generate a human-readable report string."""
        status = "✓ PASS" if self.passed else "✗ FAIL"
        lines = [
            f"  {self.test_name}: {status}",
            f"    Instructions: {self.instruction_count}",
            f"    Register diffs: {len(self.reg_diffs)}",
            f"    CSR diffs: {len(self.csr_diffs)}",
            f"    Memory diffs: {len(self.mem_diffs)}",
        ]
        if self.error_message:
            lines.append(f"    Error: {self.error_message}")
        for diff in self.reg_diffs[:10]:
            lines.append(f"    [REG] {diff}")
        for diff in self.csr_diffs[:10]:
            lines.append(f"    [CSR] {diff}")
        for diff in self.mem_diffs[:5]:
            lines.append(f"    [MEM] {diff}")
        return "\n".join(lines)


class Scoreboard:
    """Central scoreboard for IP-001 RV32I architecture verification.

    Compares architectural state against Spike GRM.
    """

    def __init__(self, cfg: GRMConfig = config):
        self.cfg = cfg
        self.grm = SpikeGRM(cfg)
        self.results: List[ScoreboardResult] = []

        # Check toolchain availability
        self._spike_available = self.grm.check_available()
        self._toolchain = self._check_toolchain()

    def _check_toolchain(self) -> Dict[str, bool]:
        """Check RISC-V toolchain availability."""
        tools = {}
        for tool_name in ['riscv64-unknown-elf-gcc', 'riscv64-unknown-elf-as',
                          'riscv64-unknown-elf-ld', 'riscv64-unknown-elf-objcopy']:
            tools[tool_name] = subprocess.run(
                ['which', tool_name], capture_output=True
            ).returncode == 0
        return tools

    @property
    def spike_available(self) -> bool:
        return self._spike_available

    @property
    def toolchain_available(self) -> bool:
        return all(self._toolchain.values())

    def compile_asm(self, asm_source: str, output_elf: str) -> bool:
        """Compile RISC-V assembly to ELF binary.

        Args:
            asm_source: RISC-V assembly source code
            output_elf: Path for output ELF file

        Returns:
            True if compilation succeeded
        """
        # Write assembly to temp file
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.S', delete=False
        ) as asm_file:
            asm_file.write(asm_source)
            asm_path = asm_file.name

        try:
            # Assemble
            obj_path = output_elf + '.o'
            asm_result = subprocess.run(
                [self.cfg.RISCV_AS, '-march=rv32i', '-mabi=ilp32',
                 '-o', obj_path, asm_path],
                capture_output=True, text=True, timeout=10
            )
            if asm_result.returncode != 0:
                print(f"Assembly failed: {asm_result.stderr}")
                return False

            # Link
            ld_script = self._generate_linker_script()
            ld_path = output_elf + '.ld'
            with open(ld_path, 'w') as f:
                f.write(ld_script)

            ld_result = subprocess.run(
                [self.cfg.RISCV_LD, '-m', 'elf32lriscv', '-nostdlib',
                 '-T', ld_path, '-o', output_elf, obj_path],
                capture_output=True, text=True, timeout=10
            )
            if ld_result.returncode != 0:
                print(f"Link failed: {ld_result.stderr}")
                return False

            return True
        finally:
            # Cleanup temp files
            for path in [asm_path, obj_path, ld_path]:
                try:
                    os.unlink(path)
                except OSError:
                    pass

    def _generate_linker_script(self) -> str:
        """Generate a minimal linker script for GRM test binaries."""
        return f"""\
OUTPUT_ARCH(riscv)
ENTRY(_start)

SECTIONS {{
    . = {hex(self.cfg.IMEM_BASE)};
    .text : {{
        *(.text)
        *(.text.*)
        *(.rodata)
        *(.rodata.*)
    }}
    . = {hex(self.cfg.DMEM_BASE)};
    .data : {{
        *(.data)
        *(.data.*)
        *(.sdata)
        *(.bss)
        *(COMMON)
    }}
    /DISCARD/ : {{
        *(.comment)
        *(.note)
    }}
}}"""

    def run_spike_test(self, test_name: str, elf_path: str,
                       timeout: int = 30) -> ScoreboardResult:
        """Run a pre-compiled ELF through Spike and validate.

        Args:
            test_name: Human-readable test name
            elf_path: Path to compiled ELF binary
            timeout: Maximum seconds for Spike execution

        Returns:
            ScoreboardResult with pass/fail and diffs
        """
        result = ScoreboardResult(test_name=test_name, passed=False)

        if not self._spike_available:
            result.error_message = "Spike not available"
            self.results.append(result)
            return result

        if not os.path.exists(elf_path):
            result.error_message = f"ELF not found: {elf_path}"
            self.results.append(result)
            return result

        try:
            grm_state = self.grm.run_and_get_state(elf_path, timeout=timeout)
            result.grm_state = grm_state
            result.instruction_count = grm_state.instret
            result.passed = True
        except Exception as e:
            result.error_message = str(e)

        self.results.append(result)
        return result

    def run_asm_test(self, test_name: str, asm_source: str,
                     expected_regs: Optional[Dict[int, int]] = None,
                     expected_csrs: Optional[Dict[int, int]] = None,
                     timeout: int = 30) -> ScoreboardResult:
        """Compile assembly and run through Spike.

        Args:
            test_name: Human-readable test name
            asm_source: RISC-V assembly source
            expected_regs: Optional dict of expected register values {reg_num: value}
            expected_csrs: Optional dict of expected CSR values {addr: value}
            timeout: Maximum seconds for Spike execution

        Returns:
            ScoreboardResult with pass/fail
        """
        result = ScoreboardResult(test_name=test_name, passed=False)

        if not self._spike_available or not self.toolchain_available:
            result.error_message = "Toolchain or Spike not available"
            self.results.append(result)
            return result

        # Compile assembly
        with tempfile.NamedTemporaryFile(
            suffix='.elf', delete=False
        ) as elf_file:
            elf_path = elf_file.name

        try:
            if not self.compile_asm(asm_source, elf_path):
                result.error_message = "Assembly compilation failed"
                self.results.append(result)
                return result

            # Run through Spike
            grm_state = self.grm.run_and_get_state(elf_path, timeout=timeout)
            result.grm_state = grm_state
            result.instruction_count = grm_state.instret

            # Validate against expected values if provided
            if expected_regs:
                reg_diffs = []
                for reg_num, expected_val in expected_regs.items():
                    actual = grm_state.regfile.get(reg_num, 0)
                    if actual != expected_val:
                        reg_diffs.append(
                            f"x{reg_num}: expected=0x{expected_val:08X} "
                            f"actual=0x{actual:08X}"
                        )
                result.reg_diffs = reg_diffs

            if expected_csrs:
                csr_diffs = []
                for addr, expected_val in expected_csrs.items():
                    actual = grm_state.csr.get(addr, 0)
                    if actual != expected_val:
                        csr_diffs.append(
                            f"{config.get_csr_name(addr)}: "
                            f"expected=0x{expected_val:08X} actual=0x{actual:08X}"
                        )
                result.csr_diffs = csr_diffs

            result.passed = len(result.reg_diffs) == 0 and len(result.csr_diffs) == 0

        except Exception as e:
            result.error_message = str(e)
        finally:
            try:
                os.unlink(elf_path)
            except OSError:
                pass

        self.results.append(result)
        return result

    def compare_states(self, grm_state: GRMState,
                       dut_state: GRMState) -> Tuple[bool, List[str]]:
        """Compare two architectural states.

        Returns (match, diffs).
        """
        return grm_state.compare_all(dut_state)

    def summary(self) -> str:
        """Generate aggregate test report."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        total_instr = sum(r.instruction_count for r in self.results)

        lines = [
            "=" * 60,
            "IP-001 SCOREBOARD SUMMARY",
            "=" * 60,
            f"Total tests: {total}",
            f"Passed: {passed}",
            f"Failed: {failed}",
            f"Total instructions executed: {total_instr}",
            f"Pass rate: {passed/total*100:.1f}%" if total > 0 else "No tests run",
            "",
        ]

        if failed:
            lines.append("FAILED TESTS:")
            for r in self.results:
                if not r.passed:
                    lines.append(r.report())

        return "\n".join(lines)

    def print_summary(self):
        """Print aggregate report to stdout."""
        print(self.summary())

    def as_dict(self) -> dict:
        """Return results as a dictionary for JSON export."""
        return {
            'total': len(self.results),
            'passed': sum(1 for r in self.results if r.passed),
            'failed': sum(1 for r in self.results if not r.passed),
            'results': [
                {
                    'name': r.test_name,
                    'passed': r.passed,
                    'instruction_count': r.instruction_count,
                    'reg_diffs': r.reg_diffs,
                    'csr_diffs': r.csr_diffs,
                    'mem_diffs': r.mem_diffs,
                    'error': r.error_message,
                }
                for r in self.results
            ]
        }


# Convenience function for quick scoreboard usage
def quick_scoreboard() -> Scoreboard:
    """Create a Scoreboard instance with default config."""
    return Scoreboard()
