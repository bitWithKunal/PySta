/**
 * Synthesized Gate-Level Netlist for SPI Slave
 * Mapped to simple library with INV, NAND, NOR, and DFF cells
 */

module spi_slave (
    input  wire        sclk,
    input  wire        mosi,
    output wire        miso,
    input  wire        cs_n,
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  tx_data,
    output wire [7:0]  rx_data,
    output wire        data_valid
);

// ============================================================================
// Internal Net Declarations
// ============================================================================

// Synchronization nets
wire        sclk_meta, sclk_sync;
wire        cs_meta, cs_sync;
wire        sclk_prev;
wire        sclk_posedge, sclk_negedge;

// Control nets
wire        transfer_active;
wire        transfer_active_next;
wire [2:0]  bit_count;
wire [2:0]  bit_count_next;
wire        bit_count_inc;
wire        bit_count_reset;
wire        bit_count_max;

// Data nets
wire [7:0]  shift_reg;
wire [7:0]  shift_reg_next;
wire        shift_load;
wire        shift_enable;
wire        miso_int;
wire        data_valid_int;
wire        data_valid_next;

// Clock and reset
wire        clk_int;
wire        rst_int;

// ============================================================================
// Clock and Reset Buffering
// ============================================================================

INV_X1 U1 (.A(rst_n), .Y(rst_int));
BUF_X1 U2 (.A(clk), .Y(clk_int));

// ============================================================================
// Synchronization Flip-Flops (Clock Domain Crossing)
// ============================================================================

// SCLK synchronization (2-stage synchronizer)
DFF_X1 sync_sclk_meta (
    .CK(clk_int),
    .D(sclk),
    .RN(rst_int),
    .Q(sclk_meta)
);

DFF_X1 sync_sclk_sync (
    .CK(clk_int),
    .D(sclk_meta),
    .RN(rst_int),
    .Q(sclk_sync)
);

// CS synchronization
DFF_X1 sync_cs_meta (
    .CK(clk_int),
    .D(cs_n),
    .RN(rst_int),
    .Q(cs_meta)
);

DFF_X1 sync_cs_sync (
    .CK(clk_int),
    .D(cs_meta),
    .RN(rst_int),
    .Q(cs_sync)
);

// ============================================================================
// SCLK Edge Detection
// ============================================================================

DFF_X1 sclk_prev_reg (
    .CK(clk_int),
    .D(sclk_sync),
    .RN(rst_int),
    .Q(sclk_prev)
);

// sclk_posedge = sclk_sync & ~sclk_prev
INV_X1 U3 (.A(sclk_prev), .Y(net1));
NAND2_X1 U4 (.A(sclk_sync), .B(net1), .Y(net2));
INV_X1 U5 (.A(net2), .Y(sclk_posedge));

// sclk_negedge = ~sclk_sync & sclk_prev
INV_X1 U6 (.A(sclk_sync), .Y(net3));
NAND2_X1 U7 (.A(net3), .B(sclk_prev), .Y(net4));
INV_X1 U8 (.A(net4), .Y(sclk_negedge));

// ============================================================================
// Transfer Control Logic
// ============================================================================

// transfer_active flip-flop
DFF_X1 transfer_reg (
    .CK(clk_int),
    .D(transfer_active_next),
    .RN(rst_int),
    .Q(transfer_active)
);

// transfer_active_next = (cs_sync & transfer_active) ? 0 : 
//                        (!cs_sync & !transfer_active) ? 1 : transfer_active
INV_X1 U9 (.A(cs_sync), .Y(net5));
NAND2_X1 U10 (.A(net5), .B(transfer_active), .Y(net6));
INV_X1 U11 (.A(net6), .Y(net7));
NAND2_X1 U12 (.A(cs_sync), .B(transfer_active), .Y(net8));
NOR2_X1 U13 (.A(net7), .B(net8), .Y(transfer_active_next));

// ============================================================================
// Bit Counter
// ============================================================================

// Counter control signals
// bit_count_inc = transfer_active & sclk_posedge
NAND2_X1 U14 (.A(transfer_active), .B(sclk_posedge), .Y(net9));
INV_X1 U15 (.A(net9), .Y(bit_count_inc));

// bit_count_reset = cs_sync | !transfer_active
INV_X1 U16 (.A(transfer_active), .Y(net10));
NOR2_X1 U17 (.A(cs_sync), .B(net10), .Y(bit_count_reset));

// Bit counter flip-flops
DFF_X1 bit0_reg (
    .CK(clk_int),
    .D(bit_count_next[0]),
    .RN(rst_int),
    .Q(bit_count[0])
);

DFF_X1 bit1_reg (
    .CK(clk_int),
    .D(bit_count_next[1]),
    .RN(rst_int),
    .Q(bit_count[1])
);

DFF_X1 bit2_reg (
    .CK(clk_int),
    .D(bit_count_next[2]),
    .RN(rst_int),
    .Q(bit_count[2])
);

// Counter increment logic
// bit_count_next = bit_count_reset ? 0 : (bit_count_inc ? bit_count+1 : bit_count)

// bit_count+1 logic
INV_X1 U18 (.A(bit_count[0]), .Y(net11));
NAND2_X1 U19 (.A(bit_count[0]), .B(bit_count[1]), .Y(net12));
NAND2_X1 U20 (.A(net11), .B(bit_count[1]), .Y(net13));

NOR2_X1 U21 (.A(net12), .B(bit_count_inc), .Y(bit_count_next[1])); // Simplified

// bit_count_max = bit_count == 7
NAND2_X1 U22 (.A(bit_count[0]), .B(bit_count[1]), .Y(net14));
NAND2_X1 U23 (.A(net14), .B(bit_count[2]), .Y(bit_count_max));

// ============================================================================
// Shift Register
// ============================================================================

// shift_load = !cs_sync & !transfer_active
INV_X1 U24 (.A(cs_sync), .Y(net15));
NAND2_X1 U25 (.A(net15), .B(transfer_active), .Y(net16));
INV_X1 U26 (.A(net16), .Y(shift_load));

// shift_enable = transfer_active & sclk_posedge
NAND2_X1 U27 (.A(transfer_active), .B(sclk_posedge), .Y(shift_enable));

// Shift register bits
DFF_X1 shift0_reg (
    .CK(clk_int),
    .D(shift_reg_next[0]),
    .RN(rst_int),
    .Q(shift_reg[0])
);

DFF_X1 shift1_reg (
    .CK(clk_int),
    .D(shift_reg_next[1]),
    .RN(rst_int),
    .Q(shift_reg[1])
);

DFF_X1 shift2_reg (
    .CK(clk_int),
    .D(shift_reg_next[2]),
    .RN(rst_int),
    .Q(shift_reg[2])
);

DFF_X1 shift3_reg (
    .CK(clk_int),
    .D(shift_reg_next[3]),
    .RN(rst_int),
    .Q(shift_reg[3])
);

DFF_X1 shift4_reg (
    .CK(clk_int),
    .D(shift_reg_next[4]),
    .RN(rst_int),
    .Q(shift_reg[4])
);

DFF_X1 shift5_reg (
    .CK(clk_int),
    .D(shift_reg_next[5]),
    .RN(rst_int),
    .Q(shift_reg[5])
);

DFF_X1 shift6_reg (
    .CK(clk_int),
    .D(shift_reg_next[6]),
    .RN(rst_int),
    .Q(shift_reg[6])
);

DFF_X1 shift7_reg (
    .CK(clk_int),
    .D(shift_reg_next[7]),
    .RN(rst_int),
    .Q(shift_reg[7])
);

// Shift register input logic
// shift_reg_next = shift_load ? tx_data : 
//                  (shift_enable ? {shift_reg[6:0], mosi} : shift_reg)

// MISO output
assign miso_int = shift_reg[7];

// MISO output enable (only when transfer_active)
NAND2_X1 U28 (.A(transfer_active), .B(miso_int), .Y(net17));
INV_X1 U29 (.A(transfer_active), .Y(net18));
NAND2_X1 U30 (.A(net18), .B(1'b1), .Y(net19)); // Tri-state control

// For simplicity, direct output (in real design would be tri-state)
assign miso = miso_int;

// ============================================================================
// Receive Data Register
// ============================================================================

// data_valid = bit_count_max & sclk_posedge
NAND2_X1 U31 (.A(bit_count_max), .B(sclk_posedge), .Y(data_valid_int));

DFF_X1 data_valid_reg (
    .CK(clk_int),
    .D(data_valid_int),
    .RN(rst_int),
    .Q(data_valid)
);

// RX Data registers
DFF_X1 rx0_reg (
    .CK(clk_int),
    .D(shift_reg[0]),
    .RN(rst_int),
    .Q(rx_data[0])
);

DFF_X1 rx1_reg (
    .CK(clk_int),
    .D(shift_reg[1]),
    .RN(rst_int),
    .Q(rx_data[1])
);

DFF_X1 rx2_reg (
    .CK(clk_int),
    .D(shift_reg[2]),
    .RN(rst_int),
    .Q(rx_data[2])
);

DFF_X1 rx3_reg (
    .CK(clk_int),
    .D(shift_reg[3]),
    .RN(rst_int),
    .Q(rx_data[3])
);

DFF_X1 rx4_reg (
    .CK(clk_int),
    .D(shift_reg[4]),
    .RN(rst_int),
    .Q(rx_data[4])
);

DFF_X1 rx5_reg (
    .CK(clk_int),
    .D(shift_reg[5]),
    .RN(rst_int),
    .Q(rx_data[5])
);

DFF_X1 rx6_reg (
    .CK(clk_int),
    .D(shift_reg[6]),
    .RN(rst_int),
    .Q(rx_data[6])
);

DFF_X1 rx7_reg (
    .CK(clk_int),
    .D(shift_reg[7]),
    .RN(rst_int),
    .Q(rx_data[7])
);

endmodule