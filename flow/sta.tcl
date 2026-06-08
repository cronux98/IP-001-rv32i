# IP-001 RV32I — OpenSTA Timing Analysis (v4)
read_liberty /home/smdadmin/OpenROAD-flow-scripts/flow/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
read_verilog flow/synth_netlist.v
link_design rv32i_core
source constraints/IP_001.sdc

# Exclude reset sync flop — its 851-fanout is a backend buffer-tree issue
set_false_path -through [get_pins _17207_/Q]

puts "\n========================================"
puts "  SETUP — Worst Path (reset excluded)"
puts "========================================"
report_checks -path_delay max -format full -digits 3 -fields {slew cap fanout nets}

puts "\n========================================"
puts "  NEXT 3 SETUP"
puts "========================================"
report_checks -path_delay max -format full -digits 3 -fields {slew cap fanout nets} -endpoint_count 3

puts "\n========================================"
puts "  HOLD — Top 5"
puts "========================================"
report_checks -path_delay min -format full -digits 3 -endpoint_count 5
