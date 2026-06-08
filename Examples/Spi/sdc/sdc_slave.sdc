###############################################################################
# SDC Constraints for SPI Slave
# SPI Interface running at 50MHz, System Clock at 100MHz
###############################################################################

# =============================================================================
# Clock Definitions
# =============================================================================

# System clock - 100MHz
create_clock -name sys_clk -period 10.0 [get_ports clk]

# SPI clock - 50MHz (generated externally)
create_clock -name spi_clk -period 20.0 [get_ports sclk]

# Generated clock for internal SPI timing
create_generated_clock -name spi_clk_int -source [get_ports sclk] \
    -divide_by 1 [get_pins spi_slave/sclk_sync_reg/Q]

# Clock groups - asynchronous relationship
set_clock_groups -asynchronous \
    -group [get_clocks sys_clk] \
    -group [get_clocks spi_clk]

# =============================================================================
# Clock Characteristics
# =============================================================================

# Clock latency
set_clock_latency -source -rise 0.5 [get_clocks sys_clk]
set_clock_latency -source -fall 0.5 [get_clocks sys_clk]
set_clock_latency -rise 0.2 [get_clocks sys_clk]
set_clock_latency -fall 0.2 [get_clocks sys_clk]

set_clock_latency -source -rise 0.3 [get_clocks spi_clk]
set_clock_latency -source -fall 0.3 [get_clocks spi_clk]
set_clock_latency -rise 0.1 [get_clocks spi_clk]
set_clock_latency -fall 0.1 [get_clocks spi_clk]

# Clock uncertainty
set_clock_uncertainty -setup 0.2 [get_clocks sys_clk]
set_clock_uncertainty -hold 0.1 [get_clocks sys_clk]

set_clock_uncertainty -setup 0.3 [get_clocks spi_clk]
set_clock_uncertainty -hold 0.15 [get_clocks spi_clk]

# Clock transition
set_clock_transition -rise 0.1 [get_clocks sys_clk]
set_clock_transition -fall 0.1 [get_clocks sys_clk]

set_clock_transition -rise 0.15 [get_clocks spi_clk]
set_clock_transition -fall 0.15 [get_clocks spi_clk]

# =============================================================================
# Input Delays
# =============================================================================

# SPI inputs
set_input_delay -clock spi_clk -max 5.0 [get_ports mosi]
set_input_delay -clock spi_clk -min 1.0 [get_ports mosi]

set_input_delay -clock spi_clk -max 5.0 [get_ports cs_n]
set_input_delay -clock spi_clk -min 1.0 [get_ports cs_n]

# System inputs
set_input_delay -clock sys_clk -max 2.0 [get_ports tx_data*]
set_input_delay -clock sys_clk -min 0.5 [get_ports tx_data*]

set_input_delay -clock sys_clk -max 2.0 [get_ports rst_n]
set_input_delay -clock sys_clk -min 0.5 [get_ports rst_n]

# =============================================================================
# Output Delays
# =============================================================================

# SPI outputs
set_output_delay -clock spi_clk -max 4.0 [get_ports miso]
set_output_delay -clock spi_clk -min 0.5 [get_ports miso]

# System outputs
set_output_delay -clock sys_clk -max 3.0 [get_ports rx_data*]
set_output_delay -clock sys_clk -min 0.5 [get_ports rx_data*]

set_output_delay -clock sys_clk -max 3.0 [get_ports data_valid]
set_output_delay -clock sys_clk -min 0.5 [get_ports data_valid]

# =============================================================================
# Input Transition and Load
# =============================================================================

set_input_transition -rise 0.2 [get_ports mosi]
set_input_transition -fall 0.2 [get_ports mosi]

set_input_transition -rise 0.2 [get_ports cs_n]
set_input_transition -fall 0.2 [get_ports cs_n]

set_input_transition -rise 0.1 [get_ports tx_data*]
set_input_transition -fall 0.1 [get_ports tx_data*]

set_input_transition -rise 0.1 [get_ports rst_n]
set_input_transition -fall 0.1 [get_ports rst_n]

set_load -pin_load 0.05 [get_ports miso]
set_load -pin_load 0.05 [get_ports rx_data*]
set_load -pin_load 0.05 [get_ports data_valid]

# =============================================================================
# Timing Exceptions
# =============================================================================

# False paths
set_false_path -from [get_ports rst_n]  # Reset is asynchronous

# Multicycle paths for cross-domain paths
set_multicycle_path -setup 2 -from [get_clocks spi_clk] -to [get_clocks sys_clk]
set_multicycle_path -hold 1 -from [get_clocks spi_clk] -to [get_clocks sys_clk]

set_multicycle_path -setup 2 -from [get_clocks sys_clk] -to [get_clocks spi_clk]
set_multicycle_path -hold 1 -from [get_clocks sys_clk] -to [get_clocks spi_clk]

# Max delay constraints
set_max_delay 8.0 -from [get_ports tx_data*] -to [get_ports rx_data*]

# =============================================================================
# Operating Conditions (for OCV)
# =============================================================================

set_operating_conditions -analysis_type on_chip_variation \
    -library slow -max slow -min fast

# =============================================================================
# Derating Factors (for OCV)
# =============================================================================

set_timing_derate -early 0.95 -cell_delay -net_delay
set_timing_derate -late 1.05 -cell_delay -net_delay

set_timing_derate -early 0.98 -cell_delay -net_delay [get_clocks sys_clk]
set_timing_derate -late 1.02 -cell_delay -net_delay [get_clocks sys_clk]

set_timing_derate -early 0.98 -cell_delay -net_delay [get_clocks spi_clk]
set_timing_derate -late 1.02 -cell_delay -net_delay [get_clocks spi_clk]