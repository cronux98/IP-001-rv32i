# IP-001 RV32I — Cocotb Verification Makefile

TOPLEVEL_LANG = verilog

PROJ = /home/smdadmin/vlsi-team/projects/IP-001-rv32i

VERILOG_SOURCES = $(PROJ)/rtl/modules/register_file.v \
                  $(PROJ)/rtl/modules/forwarding_unit.v \
                  $(PROJ)/rtl/modules/hazard_unit.v \
                  $(PROJ)/rtl/modules/if_stage.v \
                  $(PROJ)/rtl/modules/id_stage.v \
                  $(PROJ)/rtl/modules/ex_stage.v \
                  $(PROJ)/rtl/modules/mem_stage.v \
                  $(PROJ)/rtl/modules/wb_stage.v \
                  $(PROJ)/rtl/modules/csr_block.v \
                  $(PROJ)/rtl/modules/pipeline_control.v \
                  $(PROJ)/rtl/top/rv32i_core.v

TOPLEVEL = rv32i_core
COCOTB_TEST_MODULES = tests.test_runner
COCOTB_HDL_TIMEUNIT = 1ns
COCOTB_HDL_TIMEPRECISION = 1ps

export MEM_BIN ?= $(PROJ)/verification/tmp/test_prog.bin

include $(shell cocotb-config --makefiles)/Makefile.sim
