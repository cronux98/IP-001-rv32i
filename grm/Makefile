# IP-001 RV32I GRM — Makefile
# Build and test targets for the Golden Reference Model

GRM_DIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
SRC_DIR := $(GRM_DIR)src
TEST_DIR := $(GRM_DIR)tests
BIN_DIR := $(GRM_DIR)binaries

PYTHON := python3
SPIKE := spike

# ── Default target ─────────────────────────────────────────────────
.PHONY: all
all: check-spike test

# ── Spike check ────────────────────────────────────────────────────
.PHONY: check-spike
check-spike:
	@echo "=== Checking Spike availability ==="
	@which $(SPIKE) > /dev/null 2>&1 && \
		$(SPIKE) --help 2>&1 | head -1 && \
		echo "Spike: AVAILABLE" || \
		(echo "Spike: NOT FOUND — install riscv-isa-sim" && false)

# ── Toolchain check ────────────────────────────────────────────────
.PHONY: check-toolchain
check-toolchain:
	@echo "=== Checking RISC-V toolchain ==="
	@which riscv64-unknown-elf-gcc > /dev/null 2>&1 && \
		echo "riscv64-unknown-elf-gcc: AVAILABLE" || \
		echo "riscv64-unknown-elf-gcc: NOT FOUND"
	@which riscv64-unknown-elf-objcopy > /dev/null 2>&1 && \
		echo "riscv64-unknown-elf-objcopy: AVAILABLE" || \
		echo "riscv64-unknown-elf-objcopy: NOT FOUND"
	@which riscv64-unknown-elf-objdump > /dev/null 2>&1 && \
		echo "riscv64-unknown-elf-objdump: AVAILABLE" || \
		echo "riscv64-unknown-elf-objdump: NOT FOUND"

# ── Self-check (GRM source verification) ──────────────────────────
.PHONY: self-check
self-check:
	@echo "=== GRM self-check ==="
	cd $(SRC_DIR) && $(PYTHON) spike_grm.py

# ── Run all self-tests ────────────────────────────────────────────
.PHONY: test
test: test-spike-basic test-instructions test-csr test-traps

.PHONY: test-spike-basic
test-spike-basic:
	@echo "=== Test: Spike Basic ==="
	cd $(GRM_DIR) && $(PYTHON) -m pytest $(TEST_DIR)/test_spike_basic.py -v -s 2>&1 || true

.PHONY: test-instructions
test-instructions:
	@echo "=== Test: Instructions ==="
	cd $(GRM_DIR) && $(PYTHON) -m pytest $(TEST_DIR)/test_grm_instructions.py -v -s 2>&1 || true

.PHONY: test-csr
test-csr:
	@echo "=== Test: CSR ==="
	cd $(GRM_DIR) && $(PYTHON) -m pytest $(TEST_DIR)/test_grm_csr.py -v -s 2>&1 || true

.PHONY: test-traps
test-traps:
	@echo "=== Test: Traps ==="
	cd $(GRM_DIR) && $(PYTHON) -m pytest $(TEST_DIR)/test_grm_traps.py -v -s 2>&1 || true

# ── Run a specific ELF through GRM ────────────────────────────────
.PHONY: run
run:
	cd $(GRM_DIR) && $(PYTHON) $(SRC_DIR)/run_grm.py $(ELF) --summary --verbose

# ── Build test binaries ───────────────────────────────────────────
RISCV_GCC := riscv64-unknown-elf-gcc
RISCV_AS := riscv64-unknown-elf-as
RISCV_LD := riscv64-unknown-elf-ld
GCCFLAGS := -march=rv32i -mabi=ilp32 -nostdlib -nostartfiles -static -O0
LDFLAGS := -nostdlib -T $(BIN_DIR)/link.ld

.PHONY: build-all
build-all: build-add build-logical build-shift build-mem build-branch build-csr-test build-trap-test

build-add: $(BIN_DIR)/test_add.elf
$(BIN_DIR)/test_add.elf: $(BIN_DIR)/test_add.S $(BIN_DIR)/link.ld
	$(RISCV_GCC) $(GCCFLAGS) -o $@ $< $(LDFLAGS)

build-logical: $(BIN_DIR)/test_logical.elf
$(BIN_DIR)/test_logical.elf: $(BIN_DIR)/test_logical.S $(BIN_DIR)/link.ld
	$(RISCV_GCC) $(GCCFLAGS) -o $@ $< $(LDFLAGS)

build-shift: $(BIN_DIR)/test_shift.elf
$(BIN_DIR)/test_shift.elf: $(BIN_DIR)/test_shift.S $(BIN_DIR)/link.ld
	$(RISCV_GCC) $(GCCFLAGS) -o $@ $< $(LDFLAGS)

build-mem: $(BIN_DIR)/test_memory.elf
$(BIN_DIR)/test_memory.elf: $(BIN_DIR)/test_memory.S $(BIN_DIR)/link.ld
	$(RISCV_GCC) $(GCCFLAGS) -o $@ $< $(LDFLAGS)

build-branch: $(BIN_DIR)/test_branch.elf
$(BIN_DIR)/test_branch.elf: $(BIN_DIR)/test_branch.S $(BIN_DIR)/link.ld
	$(RISCV_GCC) $(GCCFLAGS) -o $@ $< $(LDFLAGS)

build-csr-test: $(BIN_DIR)/test_csr.elf
$(BIN_DIR)/test_csr.elf: $(BIN_DIR)/test_csr.S $(BIN_DIR)/link.ld
	$(RISCV_GCC) $(GCCFLAGS) -o $@ $< $(LDFLAGS)

build-trap-test: $(BIN_DIR)/test_traps.elf
$(BIN_DIR)/test_traps.elf: $(BIN_DIR)/test_traps.S $(BIN_DIR)/link.ld
	$(RISCV_GCC) $(GCCFLAGS) -o $@ $< $(LDFLAGS)

# ── Clean ─────────────────────────────────────────────────────────
.PHONY: clean
clean:
	rm -f $(BIN_DIR)/*.elf $(BIN_DIR)/*.o
	rm -f /tmp/spike_grm_trace_*.log
	rm -f $(GRM_DIR)/*.json
	rm -rf $(GRM_DIR)/__pycache__ $(SRC_DIR)/__pycache__ $(TEST_DIR)/__pycache__
	find $(GRM_DIR) -name '*.pyc' -delete

# ── riscv-tests integration ───────────────────────────────────────
RISCV_TESTS_DIR ?= /tmp/riscv-tests

.PHONY: riscv-tests-build
riscv-tests-build:
	@echo "=== Building riscv-tests (RV32I) ==="
	@if [ ! -d $(RISCV_TESTS_DIR) ]; then \
		git clone https://github.com/riscv-software-src/riscv-tests $(RISCV_TESTS_DIR); \
	fi
	cd $(RISCV_TESTS_DIR) && autoconf && ./configure --prefix=$(RISCV_TESTS_DIR)/install && make ISA=rv32i

.PHONY: riscv-tests-run
riscv-tests-run:
	@echo "=== Running riscv-tests through Spike ==="
	@for test in $(RISCV_TESTS_DIR)/isa/rv32ui-p-*; do \
		if [ -x "$$test" ] || file "$$test" | grep -q ELF; then \
			echo -n "$$(basename $$test): "; \
			$(SPIKE) --isa=rv32i "$$test" 2>&1 > /dev/null && echo "PASS" || echo "FAIL"; \
		fi \
	done

# ── Help ──────────────────────────────────────────────────────────
.PHONY: help
help:
	@echo "IP-001 RV32I GRM Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  all              — check Spike + run all tests"
	@echo "  check-spike      — verify Spike is installed"
	@echo "  check-toolchain  — verify RISC-V toolchain"
	@echo "  self-check       — GRM source self-check"
	@echo "  test             — run all self-tests"
	@echo "  test-*           — run individual test groups"
	@echo "  build-all        — build all test binaries"
	@echo "  build-*          — build individual test binary"
	@echo "  run ELF=<file>   — run a specific ELF through GRM"
	@echo "  riscv-tests-build — clone and build riscv-tests"
	@echo "  riscv-tests-run  — run riscv-tests through Spike"
	@echo "  clean            — remove build artifacts"
	@echo "  help             — this message"
