# =============================================================================
# IP-001 RV32I — SDC Timing Constraints (STA-corrected)
# =============================================================================
# PDK: SkyWater 130nm HD | Clock: 50 MHz (20 ns) | TT corner 25°C 1.80V
# =============================================================================

create_clock -name clk -period 20.0 -waveform {0.0 10.0} [get_ports clk]

set_clock_uncertainty -setup 0.4 [get_clocks clk]
set_clock_uncertainty -hold  0.2 [get_clocks clk]

# ── Input Delays ──
set_input_delay -clock clk -max 2.0 [get_ports i_rdata*]
set_input_delay -clock clk -min 0.5 [get_ports i_rdata*]
set_input_delay -clock clk -max 2.0 [get_ports d_rdata*]
set_input_delay -clock clk -min 0.5 [get_ports d_rdata*]

# IRQ inputs: set min delay to avoid hold violations
set_input_delay -clock clk -max 8.0 [get_ports {irq_timer irq_external}]
set_input_delay -clock clk -min 0.5 [get_ports {irq_timer irq_external}]

# ── Output Delays ──
set_output_delay -clock clk -max 1.3 [get_ports i_addr*]
set_output_delay -clock clk -min 0.0 [get_ports i_addr*]
set_output_delay -clock clk -max 1.3 [get_ports {d_addr* d_wdata* d_be*}]
set_output_delay -clock clk -max 1.3 [get_ports d_we]
set_output_delay -clock clk -min 0.0 [get_ports {d_addr* d_wdata* d_be* d_we}]

# ── Reset: async assertion → false path ──
# Reset recovery/removal is a backend concern (requires CTS + reset tree).
# In frontend STA, the reset port fans out to 1,732 FFs without buffering,
# causing artificial violations. These resolve after physical implementation.
set_false_path -from [get_ports rst_n]
set_false_path -to [get_ports rst_n]

# ── Drive/Load ──
set_driving_cell -lib_cell sky130_fd_sc_hd__buf_1 -pin X [all_inputs]
set_load 0.05 [all_outputs]
