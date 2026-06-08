/**
 * SPI Slave Interface
 * ===================
 * A simple SPI slave implementation with 8-bit data transfer
 * 
 * Features:
 * - 8-bit data transfer
 * - Mode 0 (CPOL=0, CPHA=0)
 * - Full-duplex operation
 * - Simple register interface
 */

module spi_slave (
    // SPI Interface
    input  wire        sclk,           // SPI Clock
    input  wire        mosi,           // Master Out Slave In
    output reg         miso,           // Master In Slave Out
    input  wire        cs_n,           // Chip Select (active low)
    
    // Parallel Interface
    input  wire        clk,            // System Clock
    input  wire        rst_n,           // System Reset (active low)
    input  wire [7:0]  tx_data,        // Data to transmit
    output reg  [7:0]  rx_data,        // Data received
    output reg         data_valid       // Received data valid pulse
);

// ============================================================================
// Internal Signals
// ============================================================================
reg  [2:0]  bit_count;                  // Bit counter (0-7)
reg  [7:0]  shift_reg;                   // Shift register for RX/TX
reg         sclk_meta, sclk_sync;        // SCLK synchronization
reg         cs_meta, cs_sync;            // CS synchronization
reg         sclk_prev;                    // Previous SCLK for edge detection
reg         transfer_active;               // Transfer in progress
wire        sclk_posedge;                  // SCLK rising edge
wire        sclk_negedge;                  // SCLK falling edge

// ============================================================================
// Synchronization (Clock Domain Crossing)
// ============================================================================
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        sclk_meta <= 1'b0;
        sclk_sync <= 1'b0;
        cs_meta   <= 1'b1;
        cs_sync   <= 1'b1;
    end else begin
        sclk_meta <= sclk;
        sclk_sync <= sclk_meta;
        cs_meta   <= cs_n;
        cs_sync   <= cs_meta;
    end
end

// ============================================================================
// Edge Detection
// ============================================================================
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        sclk_prev <= 1'b0;
    end else begin
        sclk_prev <= sclk_sync;
    end
end

assign sclk_posedge = sclk_sync & ~sclk_prev;
assign sclk_negedge = ~sclk_sync & sclk_prev;

// ============================================================================
// Transfer Control
// ============================================================================
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        transfer_active <= 1'b0;
        bit_count <= 3'b0;
        shift_reg <= 8'b0;
        rx_data <= 8'b0;
        data_valid <= 1'b0;
        miso <= 1'bz;
    end else begin
        // Default values
        data_valid <= 1'b0;
        
        // Chip select active low starts transfer
        if (!cs_sync && !transfer_active) begin
            transfer_active <= 1'b1;
            bit_count <= 3'b0;
            shift_reg <= tx_data;  // Load TX data
        end
        
        // Transfer in progress
        if (transfer_active) begin
            // Sample MOSI on SCLK rising edge (Mode 0)
            if (sclk_posedge) begin
                shift_reg <= {shift_reg[6:0], mosi};
                bit_count <= bit_count + 1'b1;
            end
            
            // Drive MISO on SCLK falling edge (Mode 0)
            if (sclk_negedge) begin
                miso <= shift_reg[7];
            end
            
            // Check if transfer complete
            if (bit_count == 3'b111 && sclk_posedge) begin
                rx_data <= {shift_reg[6:0], mosi};
                data_valid <= 1'b1;
            end
        end
        
        // Chip select deasserted ends transfer
        if (cs_sync && transfer_active) begin
            transfer_active <= 1'b0;
            miso <= 1'bz;
        end
    end
end

endmodule