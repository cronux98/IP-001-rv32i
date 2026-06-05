#!/usr/bin/env python3
"""
spike_grm.py — Golden Reference Model for IP-001 RV32I Core.

Wraps the Spike RISC-V ISA simulator to provide:
- Programmatic invocation with correct ISA/memory configuration
- Instruction-level execution trace parsing
- Register file, CSR, and memory state capture
- Comparison interface for Phase 5 cocotb scoreboard

Author: Sage (GRM Engineer)
Date: 2026-06-05
Project: IP-001 — RV32I 5-Stage Pipeline Core
"""

import os
import re
import sys
import json
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Iterator, Tuple
from collections import namedtuple
from dataclasses import dataclass, field

# Import project configuration
from grm_config import config, GRMConfig

# ── Data Structures ─────────────────────────────────────────────────────

TraceEntry = namedtuple('TraceEntry', [
    'index',            # int: 0-based instruction index
    'pc',               # int: program counter
    'instr_word',       # int: 32-bit instruction encoding
    'rd',               # int or None: destination register number
    'rd_value',         # int or None: value written to rd
    'rd_prev',          # int or None: old value of rd (if known)
    'is_store',         # bool: this is a store instruction
    'store_addr',       # int or None: store address
    'store_value',      # int or None: store value
    'is_branch',        # bool: this is a branch/jump instruction
    'branch_taken',     # bool or None: conditional branch was taken
    'branch_target',    # int or None: branch/jump target PC
])

@dataclass
class GRMState:
    """Architectural state snapshot at a point in execution."""

    regfile: Dict[int, int] = field(default_factory=lambda: {i: 0 for i in range(32)})
    csr: Dict[int, int] = field(default_factory=dict)
    memory: Dict[int, int] = field(default_factory=dict)  # byte address → byte value
    pc: int = 0
    instret: int = 0

    def __post_init__(self):
        """Initialize with reset values."""
        self.regfile[0] = 0  # x0 always zero
        self.pc = config.RESET_PC
        # Initialize CSRs to reset values
        for addr, val in config.CSR_RESET.items():
            self.csr[addr] = val

    @staticmethod
    def from_trace(trace: List[TraceEntry]) -> 'GRMState':
        """Reconstruct final GRMState from a complete execution trace."""
        state = GRMState()

        # Register file state is the cumulative result of all writes
        # x0 stays 0 regardless of writes
        state.regfile[0] = 0
        for entry in trace:
            if entry.rd is not None and entry.rd != 0:
                state.regfile[entry.rd] = entry.rd_value
            if entry.is_store:
                # Store value as bytes in memory (little-endian)
                state._apply_store(entry.store_addr, entry.store_value,
                                   entry.instr_word & 0x707f)  # approximate size from opcode
            state.pc = entry.pc
            state.instret = entry.index + 1

        return state

    def _apply_store(self, addr: int, value: int, size_hint: int = 4):
        """Apply a store to the memory dict."""
        # Determine store size from instruction word (simplified)
        for i in range(4):  # default word store
            self.memory[addr + i] = (value >> (8 * i)) & 0xFF

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dictionary."""
        return {
            'regfile': {str(k): v for k, v in self.regfile.items()},
            'csr': {f"0x{k:03X}": v for k, v in self.csr.items()},
            'memory': {f"0x{k:08X}": v for k, v in self.memory.items()},
            'pc': self.pc,
            'instret': self.instret,
        }

    def to_json(self, filepath: str) -> None:
        """Write state to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    def compare_regs(self, other: 'GRMState') -> List[str]:
        """Compare register files, return list of differences."""
        diffs = []
        for i in range(32):
            if i == 0:
                continue  # x0 always zero, don't compare
            if self.regfile.get(i, 0) != other.regfile.get(i, 0):
                diffs.append(
                    f"x{i:2d} ({config.get_reg_name(i):4s}): "
                    f"GRM=0x{self.regfile.get(i, 0):08X}  "
                    f"DUT=0x{other.regfile.get(i, 0):08X}"
                )
        return diffs

    def compare_csrs(self, other: 'GRMState') -> List[str]:
        """Compare CSR state, return list of differences."""
        diffs = []
        all_addrs = set(self.csr.keys()) | set(other.csr.keys())
        for addr in sorted(all_addrs):
            v1 = self.csr.get(addr, 0)
            v2 = other.csr.get(addr, 0)
            if v1 != v2:
                diffs.append(
                    f"{config.get_csr_name(addr)} (0x{addr:03X}): "
                    f"GRM=0x{v1:08X}  DUT=0x{v2:08X}"
                )
        return diffs

    def compare_memory(self, other: 'GRMState') -> List[str]:
        """Compare memory state, return list of differences."""
        diffs = []
        all_addrs = set(self.memory.keys()) | set(other.memory.keys())
        for addr in sorted(all_addrs):
            v1 = self.memory.get(addr, 0)
            v2 = other.memory.get(addr, 0)
            if v1 != v2:
                diffs.append(
                    f"mem[0x{addr:08X}]: GRM=0x{v1:02X}  DUT=0x{v2:02X}"
                )
        return diffs

    def compare_all(self, other: 'GRMState') -> Tuple[bool, List[str]]:
        """Full comparison: registers, CSRs, memory. Returns (match, diffs)."""
        diffs = []
        diffs.extend(self.compare_regs(other))
        diffs.extend(self.compare_csrs(other))
        diffs.extend(self.compare_memory(other))
        return len(diffs) == 0, diffs


# ── Spike Log Parser ───────────────────────────────────────────────────

class TraceParser:
    """Parse Spike commit log (-l output) into structured TraceEntry objects."""

    # Spike commit log format examples:
    # core   0: 0x00000000 (0x00000093) x1  0x00000000            # reg write
    # core   0: 0x00000004 (0x00a00113) x2  0x0000000a            # reg write
    # core   0: 0x00000008 (0x0020a023) mem 0x00001000 0x0000000a  # store
    # core   0: 0x0000000c (0x00000073)                            # ECALL (no write)
    # core   0: 0x00001000 (0x30529073) csr 0x305 0x00000000 x5 0x00000000  # CSR insn
    # core   0: 3 0x00000008 (0x0020a023) mem 0x00001000 0x0000000a  # with priv

    REG_WRITE_RE = re.compile(
        r'core\s+\d+:\s+(?:\d+\s+)?(0x[0-9a-fA-F]+)\s+\((0x[0-9a-fA-F]+)\)\s+x(\d+)\s+(0x[0-9a-fA-F]+)'
    )
    STORE_RE = re.compile(
        r'core\s+\d+:\s+(?:\d+\s+)?(0x[0-9a-fA-F]+)\s+\((0x[0-9a-fA-F]+)\)\s+mem\s+(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)'
    )
    CSR_RE = re.compile(
        r'core\s+\d+:\s+(?:\d+\s+)?(0x[0-9a-fA-F]+)\s+\((0x[0-9a-fA-F]+)\)\s+csr\s+(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)'
    )
    # For lines with no register write (e.g., branches, ECALL)
    BASIC_RE = re.compile(
        r'core\s+\d+:\s+(?:\d+\s+)?(0x[0-9a-fA-F]+)\s+\((0x[0-9a-fA-F]+)\)'
    )

    @staticmethod
    def parse_line(line: str) -> Optional[TraceEntry]:
        """Parse a single Spike trace line into a TraceEntry."""
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('//'):
            return None

        # Try store match first (has 'mem' keyword)
        m = TraceParser.STORE_RE.match(line)
        if m:
            pc = int(m.group(1), 16)
            instr = int(m.group(2), 16)
            addr = int(m.group(3), 16)
            value = int(m.group(4), 16)
            return TraceEntry(
                index=-1,  # filled by caller
                pc=pc, instr_word=instr,
                rd=None, rd_value=None, rd_prev=None,
                is_store=True, store_addr=addr, store_value=value,
                is_branch=False, branch_taken=None, branch_target=None
            )

        # Try CSR match
        m = TraceParser.CSR_RE.match(line)
        if m:
            pc = int(m.group(1), 16)
            instr = int(m.group(2), 16)
            # CSR traces in Spike: "csr <addr> <new_csr_value> x<rd> <old_csr_value>"
            # Actually different versions format differently; we capture what we can
            return TraceEntry(
                index=-1,
                pc=pc, instr_word=instr,
                rd=None, rd_value=None, rd_prev=None,
                is_store=False, store_addr=None, store_value=None,
                is_branch=False, branch_taken=None, branch_target=None
            )

        # Try register write match
        m = TraceParser.REG_WRITE_RE.match(line)
        if m:
            pc = int(m.group(1), 16)
            instr = int(m.group(2), 16)
            rd = int(m.group(3))
            value = int(m.group(4), 16)
            return TraceEntry(
                index=-1,
                pc=pc, instr_word=instr,
                rd=rd, rd_value=value, rd_prev=None,
                is_store=False, store_addr=None, store_value=None,
                is_branch=TraceParser._is_branch_instr(instr),
                branch_taken=TraceParser._check_branch_taken(instr, pc),
                branch_target=None
            )

        # Try basic match (no register write)
        m = TraceParser.BASIC_RE.match(line)
        if m:
            pc = int(m.group(1), 16)
            instr = int(m.group(2), 16)
            return TraceEntry(
                index=-1,
                pc=pc, instr_word=instr,
                rd=None, rd_value=None, rd_prev=None,
                is_store=False, store_addr=None, store_value=None,
                is_branch=TraceParser._is_branch_instr(instr),
                branch_taken=None, branch_target=None
            )

        return None

    @staticmethod
    def parse_file(filepath: str) -> List[TraceEntry]:
        """Parse a complete Spike log file into a list of TraceEntry objects."""
        entries = []
        with open(filepath, 'r') as f:
            for line in f:
                entry = TraceParser.parse_line(line)
                if entry is not None:
                    entries.append(entry)

        # Fill in indices
        entries = [
            entry._replace(index=i) for i, entry in enumerate(entries)
        ]
        return entries

    @staticmethod
    def parse_output(output: str) -> List[TraceEntry]:
        """Parse Spike output string into TraceEntry list."""
        entries = []
        for line in output.splitlines():
            entry = TraceParser.parse_line(line)
            if entry is not None:
                entries.append(entry)

        entries = [
            entry._replace(index=i) for i, entry in enumerate(entries)
        ]
        return entries

    @staticmethod
    def _is_branch_instr(instr_word: int) -> bool:
        """Check if instruction is a branch/jump."""
        opcode = instr_word & 0x7F
        return opcode in (0b1100011, 0b1101111, 0b1100111)

    @staticmethod
    def _check_branch_taken(instr_word: int, pc: int) -> Optional[bool]:
        """Determine if a branch was taken (heuristic from trace context)."""
        opcode = instr_word & 0x7F
        if opcode == 0b1101111:  # JAL
            return True
        if opcode == 0b1100111:  # JALR
            return True
        # For conditional branches, we can't determine from a single trace line
        return None


# ── Spike Runner ───────────────────────────────────────────────────────

class SpikeRunner:
    """Manage Spike subprocess execution."""

    def __init__(self, cfg: GRMConfig = config):
        self.cfg = cfg
        self._spike_path: Optional[str] = None

    def find_spike(self) -> Optional[str]:
        """Locate the spike binary."""
        if self._spike_path:
            return self._spike_path

        # Try configured path first
        path = shutil.which(self.cfg.SPIKE_BINARY)
        if path:
            self._spike_path = path
            return path
        return None

    def is_available(self) -> bool:
        """Check if Spike is installed and runnable."""
        return self.find_spike() is not None

    def get_version(self) -> str:
        """Get Spike version string."""
        if not self.is_available():
            return "Spike not found"
        try:
            result = subprocess.run(
                [self._spike_path, "--help"],
                capture_output=True, text=True, timeout=5
            )
            first_line = result.stdout.split('\n')[0] if result.stdout else "unknown"
            return first_line.strip()
        except Exception as e:
            return f"Error: {e}"

    def run(self, elf_path: str, timeout: int = 30,
            extra_args: Optional[List[str]] = None) -> 'SpikeResult':
        """Run a single ELF binary through Spike.

        Args:
            elf_path: Path to ELF binary
            timeout: Maximum seconds to wait
            extra_args: Additional Spike arguments

        Returns:
            SpikeResult with exit code, trace output, stderr
        """
        if not self.is_available():
            raise RuntimeError(
                f"Spike binary '{self.cfg.SPIKE_BINARY}' not found. "
                f"Install spike: git clone https://github.com/riscv-software-src/riscv-isa-sim"
            )

        if not os.path.exists(elf_path):
            raise FileNotFoundError(f"ELF binary not found: {elf_path}")

        args = [
            self._spike_path,
            f"--isa={self.cfg.SPIKE_ISA}",
            f"--priv={self.cfg.SPIKE_PRIV}",
            self.cfg.get_spike_memory_args(),  # -m0x2000 (no space)
        ]

        # Use a temp file for commit log (--log-commits gives verbose format)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as logf:
            log_path = logf.name

        try:
            args.extend(["--log-commits", f"--log={log_path}"])
            if extra_args:
                args.extend(extra_args)
            args.append(elf_path)

            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            # Read the commit log from the temp file
            with open(log_path, 'r') as f:
                log_output = f.read()
            
            return SpikeResult(
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                args=args,
                trace_entries=TraceParser.parse_output(log_output),
            )
        except subprocess.TimeoutExpired:
            if os.path.exists(log_path):
                os.unlink(log_path)
            raise TimeoutError(f"Spike timed out after {timeout}s: {elf_path}")
        except Exception as e:
            if os.path.exists(log_path):
                os.unlink(log_path)
            return SpikeResult(
                returncode=-1,
                stdout="",
                stderr=str(e),
                args=args,
                trace_entries=[],
            )
        finally:
            # Cleanup temp log file
            if 'log_path' in dir() and os.path.exists(log_path):
                try:
                    os.unlink(log_path)
                except OSError:
                    pass

    def run_to_completion(self, elf_path: str, output_json: Optional[str] = None,
                          timeout: int = 30) -> GRMState:
        """Run an ELF through Spike and return final GRMState.

        Args:
            elf_path: Path to ELF binary
            output_json: If set, write state to this JSON path
            timeout: Maximum seconds

        Returns:
            GRMState with final register/memory/CSR state
        """
        result = self.run(elf_path, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(
                f"Spike exited with code {result.returncode}\n"
                f"stderr: {result.stderr[:500]}"
            )

        trace = result.trace_entries
        state = GRMState.from_trace(trace)

        if output_json:
            state.to_json(output_json)

        return state


@dataclass
class SpikeResult:
    """Result of a Spike simulation run."""
    returncode: int
    stdout: str
    stderr: str
    args: List[str]
    trace_entries: List[TraceEntry]

    @property
    def instruction_count(self) -> int:
        return len(self.trace_entries)

    def __bool__(self) -> bool:
        return self.returncode == 0


# ── Main GRM Class ─────────────────────────────────────────────────────

class SpikeGRM:
    """Golden Reference Model for IP-001 RV32I Core.

    Wraps Spike RISC-V simulator for instruction-level verification.

    Usage:
        grm = SpikeGRM()
        trace = grm.run_elf("test.elf")
        state = grm.get_final_state()
        print(f"Executed {state.instret} instructions")
        print(f"x10 (a0) = 0x{state.regfile[10]:08X}")
    """

    def __init__(self, cfg: GRMConfig = config):
        self.cfg = cfg
        self.runner = SpikeRunner(cfg)
        self._last_result: Optional[SpikeResult] = None
        self._final_state: Optional[GRMState] = None

    def check_available(self) -> bool:
        """Verify Spike is installed and accessible."""
        return self.runner.is_available()

    def get_version(self) -> str:
        """Return Spike version string."""
        return self.runner.get_version()

    def run_elf(self, elf_path: str, timeout: int = 30) -> SpikeResult:
        """Run an ELF binary through Spike and capture trace."""
        self._last_result = self.runner.run(elf_path, timeout=timeout)
        if self._last_result.returncode == 0:
            self._final_state = GRMState.from_trace(
                self._last_result.trace_entries
            )
        return self._last_result

    def run_and_get_state(self, elf_path: str, timeout: int = 30) -> GRMState:
        """Run ELF and return final architectural state directly."""
        return self.runner.run_to_completion(elf_path, timeout=timeout)

    def get_final_state(self) -> Optional[GRMState]:
        """Get final architectural state after last run."""
        return self._final_state

    def get_trace(self) -> List[TraceEntry]:
        """Get execution trace from last run."""
        if self._last_result:
            return self._last_result.trace_entries
        return []

    def print_trace_summary(self, file=sys.stdout):
        """Print a summary of the last simulation run."""
        if not self._last_result:
            print("No simulation run yet.", file=file)
            return

        result = self._last_result
        print(f"Spike simulation: {'PASS' if result else 'FAIL'}", file=file)
        print(f"  Return code: {result.returncode}", file=file)
        print(f"  Instructions retired: {result.instruction_count}", file=file)

        if self._final_state:
            state = self._final_state
            print(f"  Final PC: 0x{state.pc:08X}", file=file)
            # Print non-zero registers
            nonzero = {k: v for k, v in state.regfile.items() if v != 0 and k != 0}
            if nonzero:
                print(f"  Non-zero registers ({len(nonzero)}):")
                for reg, val in sorted(nonzero.items()):
                    print(f"    x{reg:2d} ({config.get_reg_name(reg):4s}) = 0x{val:08X}")

            # Print CSR values (non-reset)
            print("  CSR state:")
            for addr in sorted(config.IMPLEMENTED_CSRS):
                val = state.csr.get(addr, 0)
                print(f"    {config.get_csr_name(addr):8s} = 0x{val:08X}")

    def compare_with(self, dut_state: GRMState) -> Tuple[bool, List[str]]:
        """Compare final GRM state with DUT state. Returns (match, diffs)."""
        if not self._final_state:
            return False, ["No GRM state available. Run an ELF first."]
        return self._final_state.compare_all(dut_state)


# ── Convenience Functions ──────────────────────────────────────────────

def quick_run(elf_path: str) -> SpikeResult:
    """Quick helper: run an ELF and get the result."""
    grm = SpikeGRM()
    return grm.run_elf(elf_path)


def quick_state(elf_path: str) -> GRMState:
    """Quick helper: run an ELF and get final state."""
    grm = SpikeGRM()
    return grm.run_and_get_state(elf_path)


# ── Self-Test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("IP-001 RV32I GRM — Spike Wrapper Self-Check")
    print("=" * 60)

    grm = SpikeGRM()

    print(f"\n1. Spike availability: ", end="")
    available = grm.check_available()
    print("✓ FOUND" if available else "✗ NOT FOUND")

    if available:
        print(f"   Version: {grm.get_version()}")

    sys.exit(0 if available else 1)
