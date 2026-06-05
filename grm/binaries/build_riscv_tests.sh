#!/bin/bash
# build_riscv_tests.sh — Build and run official riscv-tests through Spike GRM
# 
# This script clones, builds, and runs the RISC-V compliance test suite
# against the IP-001 RV32I Spike GRM.
#
# Usage:
#   ./build_riscv_tests.sh [--build-only] [--run-only]
#
# Prerequisites:
#   - Spike RISC-V simulator installed
#   - RISC-V GNU toolchain (riscv64-unknown-elf-gcc)
#   - autoconf, automake
#
# Author: Sage (GRM Engineer)
# Date: 2026-06-05

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GRM_DIR="$(dirname "$SCRIPT_DIR")"
RISCV_TESTS_DIR="${RISCV_TESTS_DIR:-/tmp/riscv-tests-ip001}"
SPIKE="${SPIKE:-spike}"
BUILD_ONLY=0
RUN_ONLY=0

# Parse args
for arg in "$@"; do
    case "$arg" in
        --build-only) BUILD_ONLY=1 ;;
        --run-only) RUN_ONLY=1 ;;
        --help|-h)
            echo "Usage: $0 [--build-only] [--run-only]"
            echo "  Build and run riscv-tests RV32I suite through Spike GRM"
            exit 0
            ;;
    esac
done

# ── Build riscv-tests ─────────────────────────────────────────────
if [ $RUN_ONLY -eq 0 ]; then
    echo "=== Building riscv-tests (RV32I) ==="
    
    if [ ! -d "$RISCV_TESTS_DIR" ]; then
        echo "Cloning riscv-tests..."
        git clone --depth 1 https://github.com/riscv-software-src/riscv-tests "$RISCV_TESTS_DIR"
    else
        echo "riscv-tests already cloned at $RISCV_TESTS_DIR"
        cd "$RISCV_TESTS_DIR" && git pull --ff-only 2>/dev/null || true
    fi

    cd "$RISCV_TESTS_DIR"
    
    # Configure and build RV32I tests only
    if [ ! -f "Makefile.in" ]; then
        autoconf
    fi
    
    if [ ! -f "config.status" ]; then
        ./configure --prefix="$RISCV_TESTS_DIR/install"
    fi
    
    echo "Building RV32I tests..."
    make ISA=rv32i -j$(nproc) 2>&1 | tail -5
    
    echo "riscv-tests build complete."
    echo "Test binaries in: $RISCV_TESTS_DIR/isa/"
    ls "$RISCV_TESTS_DIR/isa/rv32ui-p-"* 2>/dev/null | head -10
fi

# ── Run tests through Spike ───────────────────────────────────────
if [ $BUILD_ONLY -eq 0 ]; then
    echo ""
    echo "=== Running riscv-tests through Spike (RV32I) ==="
    echo ""
    
    PASS_COUNT=0
    FAIL_COUNT=0
    TOTAL=0
    
    for test in "$RISCV_TESTS_DIR/isa/rv32ui-p-"*; do
        if [ ! -f "$test" ]; then
            continue
        fi
        
        test_name=$(basename "$test")
        TOTAL=$((TOTAL + 1))
        
        # Run through Spike
        if timeout 10 "$SPIKE" --isa=rv32i -m0x2000 "$test" > /dev/null 2>&1; then
            echo "  PASS: $test_name"
            PASS_COUNT=$((PASS_COUNT + 1))
        else
            rc=$?
            echo "  FAIL: $test_name (rc=$rc)"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    done
    
    echo ""
    echo "=== Results ==="
    echo "  Total:  $TOTAL"
    echo "  Passed: $PASS_COUNT"
    echo "  Failed: $FAIL_COUNT"
    echo ""
    
    if [ $FAIL_COUNT -eq 0 ]; then
        echo "All RV32I compliance tests passed through Spike!"
        exit 0
    else
        echo "Some tests failed. Review failures above."
        exit 1
    fi
fi
