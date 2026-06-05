# Makefile — IP-001 RV32I Verification Environment
#
# Targets:
#   make test            Run all quick tests
#   make test-all        Run all tests including slow
#   make test-instructions  Run instruction tests only
#   make test-forwarding    Run forwarding tests only
#   make test-hazards       Run hazard tests only
#   make test-csr           Run CSR tests only
#   make test-traps         Run trap tests only
#   make test-pipeline      Run pipeline tests only
#   make test-random        Run random tests
#   make test-compliance    Run compliance tests (full suite)
#   make test-quick-compliance  Run quick compliance subset
#   make coverage         Generate coverage report
#   make analyze-pipeline Analyze pipeline hazards in random stream
#   make clean            Remove generated artifacts
#   make lint             Run syntax checks on all Python files

PYTEST = python3 -m pytest
PYTHON = python3

VERIF_DIR = .
ENV_DIR = $(VERIF_DIR)/env
TESTS_DIR = $(VERIF_DIR)/tests
GRM_DIR = ../grm/src

PYTEST_FLAGS = -v --tb=short
PYTEST_QUICK = $(PYTEST_FLAGS) -m "not slow"
PYTEST_SLOW = $(PYTEST_FLAGS) -m "slow or not slow"

.PHONY: test test-all test-quick \
        test-instructions test-forwarding test-hazards \
        test-csr test-traps test-pipeline test-random \
        test-compliance test-quick-compliance \
        coverage analyze-pipeline clean lint

# ── Default target ───────────────────────────────────────────────────

test: test-quick

# ── Full test suite ───────────────────────────────────────────────────

test-all:
	@echo "=== Running ALL tests (including slow) ==="
	$(PYTEST) $(PYTEST_SLOW) $(TESTS_DIR)/

# ── Quick tests (excluding slow) ──────────────────────────────────────

test-quick:
	@echo "=== Running quick tests ==="
	$(PYTEST) $(PYTEST_QUICK) $(TESTS_DIR)/ -x

# ── Individual test suites ────────────────────────────────────────────

test-instructions:
	$(PYTEST) $(PYTEST_FLAGS) $(TESTS_DIR)/test_instructions.py -v

test-forwarding:
	$(PYTEST) $(PYTEST_FLAGS) $(TESTS_DIR)/test_forwarding.py -v

test-hazards:
	$(PYTEST) $(PYTEST_FLAGS) $(TESTS_DIR)/test_hazards.py -v

test-csr:
	$(PYTEST) $(PYTEST_FLAGS) $(TESTS_DIR)/test_csr.py -v

test-traps:
	$(PYTEST) $(PYTEST_FLAGS) $(TESTS_DIR)/test_traps.py -v

test-pipeline:
	$(PYTEST) $(PYTEST_FLAGS) $(TESTS_DIR)/test_pipeline.py -v

test-random:
	$(PYTEST) $(PYTEST_FLAGS) $(TESTS_DIR)/test_random.py -v

test-compliance:
	$(PYTEST) $(PYTEST_FLAGS) -m slow $(TESTS_DIR)/test_compliance.py -v

test-quick-compliance:
	$(PYTEST) $(PYTEST_FLAGS) $(TESTS_DIR)/test_compliance.py -v -k "TestQuickCompliance"

# ── GRM tests (from Phase 4) ──────────────────────────────────────────

test-grm:
	$(PYTHON) $(GRM_DIR)/spike_grm.py
	$(PYTHON) ../grm/tests/test_spike_basic.py
	$(PYTHON) ../grm/tests/test_grm_instructions.py
	$(PYTHON) ../grm/tests/test_grm_csr.py
	$(PYTHON) ../grm/tests/test_grm_traps.py

# ── Coverage ──────────────────────────────────────────────────────────

coverage:
	@echo "=== Running tests with coverage ==="
	$(PYTEST) $(PYTEST_QUICK) $(TESTS_DIR)/ --cov=$(ENV_DIR) --cov=$(GRM_DIR) \
		--cov-report=term-missing --cov-report=html -v

# ── Pipeline analysis ─────────────────────────────────────────────────

analyze-pipeline:
	@echo "=== Analyzing pipeline hazard patterns ==="
	$(PYTHON) -c "\
from env.instruction_generator import InstructionGenerator; \
from env.pipeline_monitor import PipelineMonitor, DecodedInstr; \
from env.coverage import CoverageModel; \
gen = InstructionGenerator(seed=42, num_instructions=1000); \
gen.hazard_density = 0.6; \
words = gen.generate_instruction_words(1000); \
instrs = [DecodedInstr.decode(w) for w in words]; \
pm = PipelineMonitor(); \
hazards = pm.analyze_stream(instrs); \
print(pm.report()); \
cov = CoverageModel(); \
for di in instrs: cov.record_instruction(di.mnemonic); \
print(); print(cov.report());"

# ── Scoreboard run ────────────────────────────────────────────────────

scoreboard:
	@echo "=== Running scoreboard on all tests ==="
	$(PYTHON) run_scoreboard.py

# ── Lint ──────────────────────────────────────────────────────────────

lint:
	@echo "=== Checking Python syntax ==="
	$(PYTHON) -m py_compile $(ENV_DIR)/scoreboard.py && echo "  scoreboard.py: OK"
	$(PYTHON) -m py_compile $(ENV_DIR)/coverage.py && echo "  coverage.py: OK"
	$(PYTHON) -m py_compile $(ENV_DIR)/pipeline_monitor.py && echo "  pipeline_monitor.py: OK"
	$(PYTHON) -m py_compile $(ENV_DIR)/instruction_generator.py && echo "  instruction_generator.py: OK"
	$(PYTHON) -m py_compile $(ENV_DIR)/trace_compare.py && echo "  trace_compare.py: OK"
	$(PYTHON) -m py_compile $(TESTS_DIR)/test_instructions.py && echo "  test_instructions.py: OK"
	$(PYTHON) -m py_compile $(TESTS_DIR)/test_forwarding.py && echo "  test_forwarding.py: OK"
	$(PYTHON) -m py_compile $(TESTS_DIR)/test_hazards.py && echo "  test_hazards.py: OK"
	$(PYTHON) -m py_compile $(TESTS_DIR)/test_csr.py && echo "  test_csr.py: OK"
	$(PYTHON) -m py_compile $(TESTS_DIR)/test_traps.py && echo "  test_traps.py: OK"
	$(PYTHON) -m py_compile $(TESTS_DIR)/test_pipeline.py && echo "  test_pipeline.py: OK"
	$(PYTHON) -m py_compile $(TESTS_DIR)/test_random.py && echo "  test_random.py: OK"
	$(PYTHON) -m py_compile $(TESTS_DIR)/test_compliance.py && echo "  test_compliance.py: OK"
	@echo "=== All files compile OK ==="

# ── Clean ─────────────────────────────────────────────────────────────

clean:
	@echo "=== Cleaning verification artifacts ==="
	rm -f *.o *.elf *.S *.ld *.log
	rm -rf __pycache__ $(TESTS_DIR)/__pycache__ $(ENV_DIR)/__pycache__
	rm -rf .pytest_cache .coverage htmlcov
	rm -rf *.pyc
	@echo "Done."

# ── Help ──────────────────────────────────────────────────────────────

help:
	@echo "IP-001 RV32I Verification Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  make test               Run all quick tests (default)"
	@echo "  make test-all            Run ALL tests including slow"
	@echo "  make test-instructions   Instruction tests"
	@echo "  make test-forwarding     Forwarding path tests"
	@echo "  make test-hazards        Load-use/branch/jump hazard tests"
	@echo "  make test-csr            CSR operation tests"
	@echo "  make test-traps          Trap entry/exit tests"
	@echo "  make test-pipeline       Pipeline control tests"
	@echo "  make test-random         Random instruction stream tests"
	@echo "  make test-compliance     Full riscv-tests compliance suite"
	@echo "  make test-grm            Phase 4 GRM self-tests"
	@echo "  make coverage            Run tests with coverage"
	@echo "  make analyze-pipeline    Run pipeline hazard analysis"
	@echo "  make lint                Syntax check all Python files"
	@echo "  make clean               Remove generated artifacts"
