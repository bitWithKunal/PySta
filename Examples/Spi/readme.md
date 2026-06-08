# SPI Slave Example for PySTA

This directory contains a complete SPI Slave design example for testing PySTA.

## Design Description

The SPI Slave implements a simple 8-bit data transfer interface with the following features:
- SPI Mode 0 (CPOL=0, CPHA=0)
- 8-bit data width
- Full-duplex operation
- Asynchronous clock domains (system clock and SPI clock)
- Active-low reset and chip select

## Files

### RTL Source
- `rtl/spi_slave.v` - Original RTL description

### Synthesized Netlist
- `netlist/spi_slave_netlist.v` - Gate-level netlist mapped to simple library

### Liberty Libraries
- `lib/slow.lib` - Slow process corner (1.2x, 125°C, 0.9V)
- `lib/fast.lib` - Fast process corner (0.8x, -40°C, 1.1V)

### SDC Constraints
- `sdc/spi_slave.sdc` - Complete timing constraints

## Clock Information

- System Clock (clk): 100MHz (period 10ns)
- SPI Clock (sclk): 50MHz (period 20ns)
- Asynchronous clock groups

## Key Paths

1. **System Clock Domain**
   - Input: tx_data[7:0] → DFFs
   - Output: rx_data[7:0], data_valid
   - Critical path: Through control logic

2. **SPI Clock Domain**
   - Input: mosi, cs_n → Synchronizers
   - Output: miso
   - Critical path: Shift register timing

3. **Cross-domain Paths**
   - SPI → System: Data valid generation
   - System → SPI: TX data loading

## Expected Results

- Setup violations: None at 100MHz/50MHz
- Hold violations: Minor on some paths
- Critical paths: Through counter and control logic
- TNS (Total Negative Slack): Should be small or zero

## Usage

1. Load files in PySTA:
   - Liberty: `lib/slow.lib`
   - Netlist: `netlist/spi_slave_netlist.v`
   - SDC: `sdc/spi_slave.sdc`

2. Run analysis:
   - Setup analysis
   - Hold analysis
   - Generate reports

3. View critical paths and timing summaries