"""
Clock waveform plotter for PySTA.
Visualizes clock waveforms and timing relationships.
"""

import matplotlib

matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from typing import List, Optional, Tuple, Dict, Any
from pathlib import Path

from Src.sdc_parser.clock_constraints import Clock
from Src.utils.logger import get_logger
from Src.utils.time_utils import TimeUtils

logger = get_logger(__name__)


class ClockWaveformPlotter:
    """Plotter for clock waveforms."""

    def __init__(self):
        self.colors = {
            'clock': '#FFD700',
            'rise': '#00FF00',
            'fall': '#FF0000',
            'uncertainty': '#FFA500',
            'latency': '#87CEEB',
            'text': '#000000',
            'grid': '#CCCCCC'
        }
        self.figure_size = (12, 6)
        self.dpi = 100

    def plot_clock_waveform(self, clock: Clock, output_file: str = None,
                            num_cycles: int = 3, show_uncertainty: bool = True,
                            show_latency: bool = True) -> Optional[plt.Figure]:
        """
        Plot a single clock waveform.

        Args:
            clock: Clock object
            output_file: Path to save the plot (optional)
            num_cycles: Number of cycles to show
            show_uncertainty: Show clock uncertainty as shaded region
            show_latency: Show clock latency

        Returns:
            matplotlib Figure object if output_file is None
        """
        try:
            # Create figure
            fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)

            # Generate time axis
            period = clock.get_period()
            max_time = period * num_cycles
            t = np.linspace(0, max_time, 1000)

            # Generate waveform
            waveform = self._generate_waveform(clock, t)

            # Plot waveform
            ax.plot(t * 1e12, waveform, color=self.colors['clock'],
                    linewidth=2, label=f"Clock: {clock.name}")

            # Add clock edges
            self._plot_clock_edges(ax, clock, num_cycles)

            # Add uncertainty shading
            if show_uncertainty and clock.uncertainty > 0:
                self._plot_uncertainty(ax, clock, num_cycles)

            # Add latency arrows
            if show_latency and clock.latency > 0:
                self._plot_latency(ax, clock)

            # Format plot
            ax.set_xlabel('Time (ps)', fontsize=12)
            ax.set_ylabel('Voltage (V)', fontsize=12)
            ax.set_title(f'Clock Waveform: {clock.name}', fontsize=14, fontweight='bold')
            ax.set_ylim(-0.1, 1.1)
            ax.set_xlim(0, max_time * 1e12)
            ax.grid(True, alpha=0.3, color=self.colors['grid'])

            # Add legend
            ax.legend(loc='upper right')

            # Add clock information
            info_text = (f"Period: {TimeUtils.format_time(period)}\n"
                         f"Frequency: {1 / period:.2f} Hz\n"
                         f"Duty Cycle: {clock.waveform[1] / period * 100:.1f}%\n"
                         f"Latency: {TimeUtils.format_time(clock.latency)}\n"
                         f"Uncertainty: {TimeUtils.format_time(clock.uncertainty)}")

            ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
                    verticalalignment='top', bbox=dict(boxstyle='round',
                                                       facecolor='wheat', alpha=0.5))

            plt.tight_layout()

            # Save or return
            if output_file:
                plt.savefig(output_file, dpi=self.dpi, bbox_inches='tight')
                plt.close(fig)
                logger.info(f"Clock waveform saved to {output_file}")
                return None
            else:
                return fig

        except Exception as e:
            logger.error(f"Failed to plot clock waveform: {e}", exc_info=True)
            return None

    def plot_all_clocks(self, clocks: List[Clock], output_file: str = None,
                        num_cycles: int = 2) -> Optional[plt.Figure]:
        """
        Plot multiple clock waveforms on the same axis.

        Args:
            clocks: List of Clock objects
            output_file: Path to save the plot
            num_cycles: Number of cycles to show

        Returns:
            matplotlib Figure object if output_file is None
        """
        try:
            fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)

            colors = plt.cm.Set3(np.linspace(0, 1, len(clocks)))

            for i, clock in enumerate(clocks):
                # Generate time axis
                period = clock.get_period()
                max_time = max(c.get_period() for c in clocks) * num_cycles
                t = np.linspace(0, max_time, 1000)

                # Generate waveform
                waveform = self._generate_waveform(clock, t)

                # Plot with offset for visibility
                offset = i * 1.2
                ax.plot(t * 1e12, waveform + offset, color=colors[i],
                        linewidth=2, label=f"{clock.name} (T={TimeUtils.format_time(period)})")

            # Format plot
            ax.set_xlabel('Time (ps)', fontsize=12)
            ax.set_ylabel('Voltage (V) + offset', fontsize=12)
            ax.set_title('Multiple Clock Waveforms', fontsize=14, fontweight='bold')
            ax.set_xlim(0, max_time * 1e12)
            ax.grid(True, alpha=0.3, color=self.colors['grid'])
            ax.legend(loc='upper right')

            plt.tight_layout()

            if output_file:
                plt.savefig(output_file, dpi=self.dpi, bbox_inches='tight')
                plt.close(fig)
                logger.info(f"Multi-clock waveform saved to {output_file}")
                return None
            else:
                return fig

        except Exception as e:
            logger.error(f"Failed to plot multiple clock waveforms: {e}", exc_info=True)
            return None

    def plot_clock_relationship(self, launch_clock: Clock, capture_clock: Clock,
                                output_file: str = None) -> Optional[plt.Figure]:
        """
        Plot relationship between launch and capture clocks.

        Args:
            launch_clock: Launch clock
            capture_clock: Capture clock
            output_file: Path to save the plot

        Returns:
            matplotlib Figure object if output_file is None
        """
        try:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), dpi=self.dpi)

            # Generate time axis
            max_period = max(launch_clock.get_period(), capture_clock.get_period())
            max_time = max_period * 3
            t = np.linspace(0, max_time, 1000)

            # Plot launch clock
            waveform1 = self._generate_waveform(launch_clock, t)
            ax1.plot(t * 1e12, waveform1, color='blue', linewidth=2,
                     label=f"Launch: {launch_clock.name}")
            ax1.set_ylabel('Voltage (V)', fontsize=10)
            ax1.set_title('Launch Clock', fontsize=12)
            ax1.set_ylim(-0.1, 1.1)
            ax1.grid(True, alpha=0.3)
            ax1.legend()

            # Plot capture clock
            waveform2 = self._generate_waveform(capture_clock, t)
            ax2.plot(t * 1e12, waveform2, color='red', linewidth=2,
                     label=f"Capture: {capture_clock.name}")
            ax2.set_xlabel('Time (ps)', fontsize=10)
            ax2.set_ylabel('Voltage (V)', fontsize=10)
            ax2.set_title('Capture Clock', fontsize=12)
            ax2.set_ylim(-0.1, 1.1)
            ax2.grid(True, alpha=0.3)
            ax2.legend()

            # Add relationship annotation
            phase_diff = (capture_clock.waveform[0] - launch_clock.waveform[0]) / launch_clock.period * 360
            fig.suptitle(f'Clock Relationship - Phase Difference: {phase_diff:.1f}°',
                         fontsize=14, fontweight='bold')

            plt.tight_layout()

            if output_file:
                plt.savefig(output_file, dpi=self.dpi, bbox_inches='tight')
                plt.close(fig)
                logger.info(f"Clock relationship plot saved to {output_file}")
                return None
            else:
                return fig

        except Exception as e:
            logger.error(f"Failed to plot clock relationship: {e}", exc_info=True)
            return None

    def _generate_waveform(self, clock: Clock, t: np.ndarray) -> np.ndarray:
        """
        Generate clock waveform values.

        Args:
            clock: Clock object
            t: Time array

        Returns:
            Waveform values
        """
        period = clock.get_period()
        rise_time = clock.waveform[0]
        fall_time = clock.waveform[1]

        # Generate waveform
        t_mod = np.mod(t, period)
        waveform = np.zeros_like(t)

        # Rise edge
        rise_mask = (t_mod >= rise_time) & (t_mod < fall_time)
        waveform[rise_mask] = 1.0

        # Add transitions (simplified)
        for i in range(len(t)):
            t_mod_i = t_mod[i]
            if abs(t_mod_i - rise_time) < period * 0.01:
                waveform[i] = 0.5  # Rising edge
            elif abs(t_mod_i - fall_time) < period * 0.01:
                waveform[i] = 0.5  # Falling edge

        return waveform

    def _plot_clock_edges(self, ax: plt.Axes, clock: Clock, num_cycles: int):
        """
        Plot clock edge markers.

        Args:
            ax: Matplotlib axes
            clock: Clock object
            num_cycles: Number of cycles
        """
        period = clock.get_period()

        for cycle in range(num_cycles):
            base_time = cycle * period

            # Rise edges
            rise_time = base_time + clock.waveform[0]
            ax.axvline(x=rise_time * 1e12, color='green', linestyle='--', alpha=0.5, linewidth=1)
            ax.text(rise_time * 1e12, 1.05, '↑', ha='center', va='bottom', color='green', fontsize=12)

            # Fall edges
            fall_time = base_time + clock.waveform[1]
            ax.axvline(x=fall_time * 1e12, color='red', linestyle='--', alpha=0.5, linewidth=1)
            ax.text(fall_time * 1e12, 1.05, '↓', ha='center', va='bottom', color='red', fontsize=12)

    def _plot_uncertainty(self, ax: plt.Axes, clock: Clock, num_cycles: int):
        """
        Plot clock uncertainty as shaded region.

        Args:
            ax: Matplotlib axes
            clock: Clock object
            num_cycles: Number of cycles
        """
        period = clock.get_period()
        uncertainty = clock.uncertainty

        for cycle in range(num_cycles):
            base_time = cycle * period

            # Uncertainty around rise edges
            rise_time = base_time + clock.waveform[0]
            rect = patches.Rectangle(
                ((rise_time - uncertainty / 2) * 1e12, -0.1),
                uncertainty * 1e12, 1.2,
                linewidth=0, facecolor=self.colors['uncertainty'], alpha=0.3
            )
            ax.add_patch(rect)

            # Uncertainty around fall edges
            fall_time = base_time + clock.waveform[1]
            rect = patches.Rectangle(
                ((fall_time - uncertainty / 2) * 1e12, -0.1),
                uncertainty * 1e12, 1.2,
                linewidth=0, facecolor=self.colors['uncertainty'], alpha=0.3
            )
            ax.add_patch(rect)

    def _plot_latency(self, ax: plt.Axes, clock: Clock):
        """
        Plot clock latency as arrows.

        Args:
            ax: Matplotlib axes
            clock: Clock object
        """
        latency = clock.latency

        # Draw arrow indicating latency
        ax.annotate('', xy=(latency * 1e12, 0.5), xytext=(0, 0.5),
                    arrowprops=dict(arrowstyle='<->', color=self.colors['latency'],
                                    linewidth=2))

        # Add label
        ax.text(latency * 1e12 / 2, 0.6, f'Latency: {TimeUtils.format_time(latency)}',
                ha='center', va='bottom', color=self.colors['latency'],
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))