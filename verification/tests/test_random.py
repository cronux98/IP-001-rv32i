#!/usr/bin/env python3
"""
test_random.py — Constrained random instruction stream stress tests.

Generates random RV32I instruction sequences and verifies execution
against Spike GRM. Two independent Spike invocations must produce
identical register state.

Usage:
    pytest verification/tests/test_random.py -v
"""

import sys, pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "grm" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "verification"))

from grm_config import config


@pytest.fixture(scope="module")
def tools_ok():
    import subprocess
    for tool in ['riscv64-unknown-elf-gcc', 'spike']:
        if subprocess.run(['which', tool], capture_output=True).returncode != 0:
            return False
    return True


class TestRandomSmall:
    def test_random_100_seed1(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "verification" / "tests"))
        from helpers import grm_run
        from env.instruction_generator import InstructionGenerator

        gen = InstructionGenerator(seed=1, num_instructions=100)
        asm = gen.generate_asm_program(count=100, init_regs=True)
        state = grm_run(asm, timeout=20)
        assert state.instret > 50

    def test_random_deterministic(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "verification" / "tests"))
        from helpers import grm_run
        from env.instruction_generator import InstructionGenerator

        gen = InstructionGenerator(seed=99, num_instructions=50)
        asm = gen.generate_asm_program(count=50, init_regs=True)
        state1 = grm_run(asm, timeout=15)
        state2 = grm_run(asm, timeout=15)
        match, diffs = state1.compare_all(state2)
        assert match, f"Same ELF produced different results:\n" + "\n".join(diffs[:5])

    def test_pipeline_analysis(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "verification" / "tests"))
        from helpers import grm_run
        from env.instruction_generator import InstructionGenerator
        from env.pipeline_monitor import PipelineMonitor, DecodedInstr
        from env.coverage import CoverageModel

        gen = InstructionGenerator(seed=42, num_instructions=200)
        gen.hazard_density = 0.6
        words = gen.generate_instruction_words(count=200)
        instrs = [DecodedInstr.decode(w) for w in words]
        pm = PipelineMonitor()
        hazards = pm.analyze_stream(instrs)

        cov = CoverageModel()
        for di in instrs:
            cov.record_instruction(di.mnemonic)

        ci, ct, cp = cov.instruction_coverage()
        print(f"\n  Hazards: {len(hazards)}, ALU→ALU: {pm.alu_alu_hazards}, "
              f"Load→ALU: {pm.load_alu_hazards}, "
              f"Coverage: {ci}/{ct} ({cp:.1f}%)")

        asm = gen.generate_asm_program(count=200, init_regs=True)
        state = grm_run(asm, timeout=20)
        assert state.regfile[0] == 0

    def test_random_coverage(self, tools_ok):
        if not tools_ok: pytest.skip("Toolchain/Spike not available")
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "verification"))
        from env.instruction_generator import InstructionGenerator
        from env.coverage import CoverageModel
        from env.pipeline_monitor import DecodedInstr

        gen = InstructionGenerator(seed=12345, num_instructions=500)
        words = gen.generate_instruction_words(count=500)
        cov = CoverageModel()
        for w in words:
            instr = DecodedInstr.decode(w)
            cov.record_instruction(instr.mnemonic)
        ci, ct, cp = cov.instruction_coverage()
        print(f"\n  Coverage: {ci}/{ct} ({cp:.1f}%)")
        assert ci >= 20, f"Should cover at least 20 types, got {ci}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
