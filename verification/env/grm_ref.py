"""
IP-001 RV32I - Spike Golden Reference Model Integration
Runs RV32I programs through Spike and captures architectural state.
"""

import subprocess
import struct
import os

SPIKE_PATH = os.environ.get("SPIKE", "/usr/local/bin/spike")


class SpikeState:
    """Captured architectural state after running Spike."""

    def __init__(self):
        self.regs = {i: 0 for i in range(32)}  # x0-x31
        self.pc = 0
        self.memory = {}  # addr → byte (only written addresses)
        self.csr = {}  # CSR name → value
        self.exit_code = 0
        self.instruction_count = 0


def run_spike(elf_path: str, max_instr: int = 50000) -> SpikeState:
    """Run an RV32I ELF through Spike and return architectural state.

    Spike's -l commit log goes to stderr. We redirect via shell to a temp
    file (needed because Python file objects buffer and data is lost on kill).
    """
    import tempfile

    fd, log_path = tempfile.mkstemp(suffix='.log')
    os.close(fd)

    cmd = (
        f"{SPIKE_PATH} --isa=rv32i --priv=m "
        f"-m0x40000000:0x80000 -l {elf_path} "
        f"2>{log_path} 1>/dev/null"
    )

    proc = subprocess.Popen(cmd, shell=True)
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

    with open(log_path, 'r') as logf:
        stdout = logf.read()
    os.unlink(log_path)

    state = SpikeState()
    if not stdout:
        return state

    # Parse Spike commit log
    # Format examples:
    #   core 0: 0x40000000 (0x00100093) li   ra, 1       (load immediate, no reg write shown)
    #   core 0: 0x40000034 (0x002085b3) add  a1, ra, sp  (reg-to-reg, no reg write shown)  
    #   core 0: 0x40000038 (0x00b52023) sw   a1, 0(a0)   (store, no reg write shown)
    #   core 0: 0x40000030 (0x00001537) auipc a0, 0x1    (x10 gets new value shown as: x10 0xVALUE on next line)
    # The ACTUAL register write lines appear as separate lines, NOT combined with the instruction.
    # Actually in Spike -l output, the format depends on the version. Let me check...
    
    # In this Spike version, register writes are shown as separate lines:
    # core 0: 3 0x40000000 (0x00100093) x1  0x00000001
    # AND stores are shown inline: sw reg, offset(base_reg)
    
    # Approach: Parse all lines. Track last committed register values.
    # For stores, look for sw/sh/sb in the disassembly and resolve addresses.
    
    x10_val = 0  # Track a0 (data base pointer)
    
    for line in stdout.splitlines():
        line = line.strip()
        if not line or 'core' not in line:
            continue

        try:
            # Extract the part after ')' which contains instruction or register write
            paren_close = line.rfind(')')
            if paren_close == -1:
                continue
            rest = line[paren_close + 1:].strip()
            if not rest:
                continue
            tokens = rest.split()

            # Check for register write: xN 0xVALUE
            if len(tokens) >= 2 and tokens[0].startswith('x'):
                try:
                    rd = int(tokens[0][1:])
                    val = int(tokens[1], 16)
                except (ValueError, IndexError):
                    continue
                state.regs[rd] = val
                if rd == 10:
                    x10_val = val
                state.instruction_count += 1
                continue

            # Check for memory store: sw/sh/sb
            if tokens and tokens[0] in ('sw', 'sh', 'sb'):
                # Format: sw src_reg, offset(base_reg)
                # e.g., sw a1, 16(a0) or sw a1, 0(a0)
                if len(tokens) >= 2:
                    try:
                        src = tokens[1].rstrip(',')
                        # Resolve source register
                        src_val = _resolve_reg(state.regs, src)
                        # Parse offset(base_reg)
                        offset_str = tokens[2] if len(tokens) > 2 else '0(x0)'
                        off, base = _parse_store_addr(offset_str)
                        base_val = _resolve_reg(state.regs, base)
                        addr = (base_val + off) & 0xFFFFFFFF
                        
                        # Determine width
                        if tokens[0] == 'sb':
                            for b in range(1):
                                state.memory[addr + b] = (src_val >> (b * 8)) & 0xFF
                        elif tokens[0] == 'sh':
                            for b in range(2):
                                state.memory[addr + b] = (src_val >> (b * 8)) & 0xFF
                        else:  # sw
                            for b in range(4):
                                state.memory[addr + b] = (src_val >> (b * 8)) & 0xFF
                    except (ValueError, IndexError, AttributeError):
                        pass

        except (ValueError, IndexError):
            continue

    state.regs[0] = 0  # x0 is always zero
    return state


# RISC-V ABI register name → number mapping
_ABI_MAP = {
    'zero': 0, 'ra': 1, 'sp': 2, 'gp': 3, 'tp': 4,
    't0': 5, 't1': 6, 't2': 7, 's0': 8, 's1': 9,
    'a0': 10, 'a1': 11, 'a2': 12, 'a3': 13, 'a4': 14, 'a5': 15,
    'a6': 16, 'a7': 17, 's2': 18, 's3': 19, 's4': 20, 's5': 21,
    's6': 22, 's7': 23, 's8': 24, 's9': 25, 's10': 26, 's11': 27,
    't3': 28, 't4': 29, 't5': 30, 't6': 31,
}
for i in range(32):
    _ABI_MAP[f'x{i}'] = i


def _resolve_reg(regs, name):
    """Resolve register name (ABI or xN) to its value."""
    name = name.strip().rstrip(',')
    reg_num = _ABI_MAP.get(name)
    if reg_num is not None:
        return regs.get(reg_num, 0)
    if name.startswith('x'):
        try:
            return regs.get(int(name[1:]), 0)
        except ValueError:
            return 0
    return 0


def _parse_store_addr(offset_str):
    """Parse store address format: '16(a0)' -> (offset, base_reg_name)."""
    offset_str = offset_str.strip()
    paren_open = offset_str.find('(')
    paren_close = offset_str.find(')')
    if paren_open != -1 and paren_close != -1:
        off = int(offset_str[:paren_open])
        base = offset_str[paren_open + 1:paren_close]
        return off, base
    # Fallback: try as hex
    try:
        return int(offset_str, 16), 'x0'
    except ValueError:
        return 0, 'x0'


def compare_states(spike: SpikeState, rtl_regs: dict, rtl_mem: dict,
                   test_name: str = "") -> tuple:
    """Compare Spike GRM state against RTL state.

    Spike may use a different base address (e.g., 0x40000000) than RTL
    (0x00000000). We normalize by comparing addresses relative to
    their respective data sections (offset 0x1000 from base).

    Returns: (passed: bool, errors: list[str])
    """
    errors = []

    # Compare registers (skip x0)
    for r in range(1, 32):
        g = spike.regs.get(r, 0)
        s = rtl_regs.get(r, 0)
        if g != s:
            errors.append(f"  x{r}: Spike=0x{g:08x}  RTL=0x{s:08x}")

    # Compare memory: normalize to offsets within data section
    # Spike data at (base + 0x1000), RTL data at 0x1000
    spike_base = 0x40000000 if any(a >= 0x40000000 for a in spike.memory) else 0
    rtl_base = 0

    for spike_addr, byte_val in spike.memory.items():
        offset = spike_addr - spike_base
        rtl_addr = offset + rtl_base
        rtl_byte = rtl_mem.get(rtl_addr)
        if rtl_byte is None:
            errors.append(
                f"  MEM[offset 0x{offset:04x}]: Spike=0x{byte_val:02x}  RTL=unwritten"
            )
        elif rtl_byte != byte_val:
            errors.append(
                f"  MEM[offset 0x{offset:04x}]: Spike=0x{byte_val:02x}  RTL=0x{rtl_byte:02x}"
            )

    if errors:
        header = f"FAIL: {test_name or 'unnamed'}" if test_name else "FAIL"
        return False, [header] + errors
    else:
        msg = f"PASS: {test_name or 'unnamed'} ({spike.instruction_count} instructions)"
        return True, [msg]


def run_grm_compare(test_name: str, asm_source: str, rtl_regs: dict,
                    rtl_mem: dict) -> tuple:
    """Full GRM comparison workflow: assemble → Spike → compare.

    Returns: (passed, report_lines)
    """
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".S", mode="w", delete=False) as f:
        f.write(asm_source)
        asm_path = f.name

    elf_path = asm_path.replace(".S", ".elf")

    # Assemble
    gcc = os.environ.get("RISCV_GCC", "/usr/bin/riscv64-unknown-elf-gcc")
    link_ld = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "link.ld"
    )
    subprocess.run(
        [
            gcc,
            "-march=rv32i",
            "-mabi=ilp32",
            "-nostdlib",
            "-nostartfiles",
            f"-T{link_ld}",
            "-o",
            elf_path,
            asm_path,
        ],
        capture_output=True,
        timeout=10,
    )

    spike_state = run_spike(elf_path)
    passed, lines = compare_states(spike_state, rtl_regs, rtl_mem, test_name)

    # Cleanup
    os.unlink(asm_path)
    if os.path.exists(elf_path):
        os.unlink(elf_path)

    return passed, lines
