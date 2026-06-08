"""
Timing plotter for PySTA.
Visualizes timing graphs and distributions.
"""

import matplotlib

matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path
import networkx as nx

from Src.timing_graph.graph_nodes import TimingNode, TimingEdge
from Src.utils.logger import get_logger
from Src.utils.time_utils import TimeUtils

logger = get_logger(__name__)


class TimingPlotter:
    """Plotter for timing analysis visualizations."""

    def __init__(self):
        self.colors = {
            'primary_input': '#98FB98',
            'primary_output': '#FFA07A',
            'cell_input': '#87CEEB',
            'cell_output': '#DDA0DD',
            'clock': '#FFD700',
            'critical': '#FF6B6B',
            'violation': '#FF4444',
            'met': '#44FF44',
            'text': '#000000',
            'grid': '#CCCCCC'
        }
        self.figure_size = (12, 8)
        self.dpi = 100

    def plot_graph(self, G: nx.DiGraph, output_file: str = None,
                   highlight_paths: List[List[str]] = None) -> Optional[plt.Figure]:
        """
        Plot timing graph.

        Args:
            G: NetworkX directed graph
            output_file: Path to save the plot
            highlight_paths: List of paths to highlight

        Returns:
            matplotlib Figure object if output_file is None
        """
        try:
            fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)

            # Create layout
            pos = nx.spring_layout(G, k=2, iterations=50)

            # Draw nodes with colors based on type
            node_colors = []
            for node in G.nodes():
                node_type = G.nodes[node].get('type', 'cell_input')
                node_colors.append(self.colors.get(node_type, '#CCCCCC'))

            nx.draw_networkx_nodes(G, pos, node_color=node_colors,
                                   node_size=500, alpha=0.8, ax=ax)

            # Draw edges
            edge_colors = []
            edge_widths = []

            for u, v in G.edges():
                # Check if edge is in highlighted paths
                is_highlighted = False
                if highlight_paths:
                    for path in highlight_paths:
                        if u in path and v in path:
                            is_highlighted = True
                            break

                if is_highlighted:
                    edge_colors.append('red')
                    edge_widths.append(3)
                else:
                    edge_colors.append('gray')
                    edge_widths.append(1)

            nx.draw_networkx_edges(G, pos, edge_color=edge_colors,
                                   width=edge_widths, alpha=0.6, ax=ax,
                                   arrows=True, arrowsize=15)

            # Draw labels
            labels = {node: node.split('/')[-1] for node in G.nodes()}
            nx.draw_networkx_labels(G, pos, labels, font_size=8, ax=ax)

            # Add title and legend
            ax.set_title(f'Timing Graph - {G.number_of_nodes()} nodes, '
                         f'{G.number_of_edges()} edges', fontsize=14, fontweight='bold')
            ax.axis('off')

            # Add legend
            legend_elements = []
            for node_type, color in self.colors.items():
                if any(G.nodes[node].get('type') == node_type for node in G.nodes()):
                    legend_elements.append(plt.Line2D([0], [0], marker='o', color='w',
                                                      markerfacecolor=color, markersize=10,
                                                      label=node_type.replace('_', ' ').title()))

            if legend_elements:
                ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1, 1))

            plt.tight_layout()

            if output_file:
                plt.savefig(output_file, dpi=self.dpi, bbox_inches='tight')
                plt.close(fig)
                logger.info(f"Timing graph saved to {output_file}")
                return None
            else:
                return fig

        except Exception as e:
            logger.error(f"Failed to plot timing graph: {e}", exc_info=True)
            return None

    def plot_slack_distribution(self, slacks: List[float], output_file: str = None,
                                threshold: float = 0) -> Optional[plt.Figure]:
        """
        Plot slack distribution histogram.

        Args:
            slacks: List of slack values in seconds
            output_file: Path to save the plot
            threshold: Slack threshold for violations

        Returns:
            matplotlib Figure object if output_file is None
        """
        try:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=self.dpi)

            # Convert to picoseconds for better readability
            slacks_ps = [s * 1e12 for s in slacks]
            threshold_ps = threshold * 1e12

            # Histogram
            n, bins, patches = ax1.hist(slacks_ps, bins=30, alpha=0.7, edgecolor='black')

            # Color bars based on slack
            for i, patch in enumerate(patches):
                if bins[i] < threshold_ps:
                    patch.set_facecolor(self.colors['violation'])
                else:
                    patch.set_facecolor(self.colors['met'])

            ax1.axvline(x=threshold_ps, color='red', linestyle='--', linewidth=2,
                        label=f'Threshold: {threshold_ps:.1f}ps')
            ax1.set_xlabel('Slack (ps)')
            ax1.set_ylabel('Number of Paths')
            ax1.set_title('Slack Distribution')
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # Cumulative distribution
            sorted_slacks = np.sort(slacks_ps)
            cumulative = np.arange(1, len(sorted_slacks) + 1) / len(sorted_slacks)

            ax2.plot(sorted_slacks, cumulative, 'b-', linewidth=2)
            ax2.axvline(x=threshold_ps, color='red', linestyle='--', linewidth=2)
            ax2.axhline(y=0.5, color='gray', linestyle=':', alpha=0.5)

            # Shade violation region
            violation_mask = sorted_slacks < threshold_ps
            if any(violation_mask):
                ax2.fill_between(sorted_slacks[violation_mask], 0,
                                 cumulative[violation_mask],
                                 color='red', alpha=0.3, label='Violations')

            ax2.set_xlabel('Slack (ps)')
            ax2.set_ylabel('Cumulative Probability')
            ax2.set_title('Cumulative Slack Distribution')
            ax2.grid(True, alpha=0.3)

            # Add statistics
            stats_text = (f"Total paths: {len(slacks)}\n"
                          f"Mean slack: {np.mean(slacks_ps):.1f}ps\n"
                          f"Median slack: {np.median(slacks_ps):.1f}ps\n"
                          f"Std dev: {np.std(slacks_ps):.1f}ps\n"
                          f"Min slack: {np.min(slacks_ps):.1f}ps\n"
                          f"Max slack: {np.max(slacks_ps):.1f}ps\n"
                          f"Violations: {sum(s < threshold for s in slacks)}")

            ax2.text(0.98, 0.98, stats_text, transform=ax2.transAxes,
                     verticalalignment='top', horizontalalignment='right',
                     bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

            plt.tight_layout()

            if output_file:
                plt.savefig(output_file, dpi=self.dpi, bbox_inches='tight')
                plt.close(fig)
                logger.info(f"Slack distribution saved to {output_file}")
                return None
            else:
                return fig

        except Exception as e:
            logger.error(f"Failed to plot slack distribution: {e}", exc_info=True)
            return None

    def plot_delay_histogram(self, delays: List[float], output_file: str = None,
                             bins: int = 30) -> Optional[plt.Figure]:
        """
        Plot delay histogram.

        Args:
            delays: List of delay values in seconds
            output_file: Path to save the plot
            bins: Number of histogram bins

        Returns:
            matplotlib Figure object if output_file is None
        """
        try:
            fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)

            # Convert to picoseconds
            delays_ps = [d * 1e12 for d in delays]

            # Create histogram
            ax.hist(delays_ps, bins=bins, alpha=0.7, color='steelblue',
                    edgecolor='black', linewidth=1)

            # Add statistics
            mean_delay = np.mean(delays_ps)
            median_delay = np.median(delays_ps)
            std_delay = np.std(delays_ps)

            ax.axvline(x=mean_delay, color='red', linestyle='--', linewidth=2,
                       label=f'Mean: {mean_delay:.1f}ps')
            ax.axvline(x=median_delay, color='green', linestyle=':', linewidth=2,
                       label=f'Median: {median_delay:.1f}ps')

            ax.set_xlabel('Delay (ps)')
            ax.set_ylabel('Frequency')
            ax.set_title('Path Delay Distribution')
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Add stats box
            stats_text = (f"Count: {len(delays)}\n"
                          f"Mean: {mean_delay:.1f}ps\n"
                          f"Median: {median_delay:.1f}ps\n"
                          f"Std Dev: {std_delay:.1f}ps\n"
                          f"Min: {np.min(delays_ps):.1f}ps\n"
                          f"Max: {np.max(delays_ps):.1f}ps")

            ax.text(0.98, 0.98, stats_text, transform=ax.transAxes,
                    verticalalignment='top', horizontalalignment='right',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

            plt.tight_layout()

            if output_file:
                plt.savefig(output_file, dpi=self.dpi, bbox_inches='tight')
                plt.close(fig)
                logger.info(f"Delay histogram saved to {output_file}")
                return None
            else:
                return fig

        except Exception as e:
            logger.error(f"Failed to plot delay histogram: {e}", exc_info=True)
            return None

    def plot_scatter(self, x_data: List[float], y_data: List[float],
                     x_label: str, y_label: str, title: str,
                     output_file: str = None) -> Optional[plt.Figure]:
        """
        Create a scatter plot.

        Args:
            x_data: X-axis data
            y_data: Y-axis data
            x_label: X-axis label
            y_label: Y-axis label
            title: Plot title
            output_file: Path to save the plot

        Returns:
            matplotlib Figure object if output_file is None
        """
        try:
            fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)

            # Convert to appropriate units
            x_vals = [x * 1e12 for x in x_data]
            y_vals = [y * 1e12 for y in y_data]

            # Create scatter plot
            scatter = ax.scatter(x_vals, y_vals, alpha=0.6, c='steelblue',
                                 edgecolors='black', linewidth=0.5)

            # Add trend line
            z = np.polyfit(x_vals, y_vals, 1)
            p = np.poly1d(z)
            ax.plot(x_vals, p(x_vals), "r--", alpha=0.8,
                    label=f'Trend: y={z[0]:.2f}x+{z[1]:.2f}')

            ax.set_xlabel(f'{x_label} (ps)')
            ax.set_ylabel(f'{y_label} (ps)')
            ax.set_title(title)
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Add correlation coefficient
            corr = np.corrcoef(x_vals, y_vals)[0, 1]
            ax.text(0.02, 0.98, f'Correlation: {corr:.3f}',
                    transform=ax.transAxes, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

            plt.tight_layout()

            if output_file:
                plt.savefig(output_file, dpi=self.dpi, bbox_inches='tight')
                plt.close(fig)
                logger.info(f"Scatter plot saved to {output_file}")
                return None
            else:
                return fig

        except Exception as e:
            logger.error(f"Failed to create scatter plot: {e}", exc_info=True)
            return None

    def plot_comparison(self, data1: List[float], data2: List[float],
                        label1: str, label2: str, title: str,
                        output_file: str = None) -> Optional[plt.Figure]:
        """
        Create a comparison plot (side-by-side histograms).

        Args:
            data1: First dataset
            data2: Second dataset
            label1: Label for first dataset
            label2: Label for second dataset
            title: Plot title
            output_file: Path to save the plot

        Returns:
            matplotlib Figure object if output_file is None
        """
        try:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=self.dpi)

            # Convert to picoseconds
            d1_ps = [d * 1e12 for d in data1]
            d2_ps = [d * 1e12 for d in data2]

            # Histograms
            ax1.hist(d1_ps, bins=30, alpha=0.7, color='blue', label=label1,
                     edgecolor='black', linewidth=1)
            ax1.hist(d2_ps, bins=30, alpha=0.5, color='red', label=label2,
                     edgecolor='black', linewidth=1)
            ax1.set_xlabel('Value (ps)')
            ax1.set_ylabel('Frequency')
            ax1.set_title('Distribution Comparison')
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # Box plot
            bp = ax2.boxplot([d1_ps, d2_ps], labels=[label1, label2],
                             patch_artist=True)

            # Color boxes
            bp['boxes'][0].set_facecolor('blue')
            bp['boxes'][1].set_facecolor('red')

            ax2.set_ylabel('Value (ps)')
            ax2.set_title('Box Plot Comparison')
            ax2.grid(True, alpha=0.3, axis='y')

            plt.suptitle(title, fontsize=14, fontweight='bold')
            plt.tight_layout()

            if output_file:
                plt.savefig(output_file, dpi=self.dpi, bbox_inches='tight')
                plt.close(fig)
                logger.info(f"Comparison plot saved to {output_file}")
                return None
            else:
                return fig

        except Exception as e:
            logger.error(f"Failed to create comparison plot: {e}", exc_info=True)
            return None

    def create_timing_report_figure(self, setup_results: Dict, hold_results: Dict,
                                    output_file: str = None) -> Optional[plt.Figure]:
        """
        Create a comprehensive timing report figure.

        Args:
            setup_results: Setup analysis results
            hold_results: Hold analysis results
            output_file: Path to save the figure

        Returns:
            matplotlib Figure object if output_file is None
        """
        try:
            fig = plt.figure(figsize=(16, 10), dpi=self.dpi)

            # Create grid for subplots
            gs = fig.add_gridspec(2, 3, height_ratios=[1, 1], width_ratios=[1, 1, 1])

            # Setup slack distribution
            ax_setup = fig.add_subplot(gs[0, 0])
            setup_slacks = setup_results.get('slacks', [])
            if setup_slacks:
                ax_setup.hist([s * 1e12 for s in setup_slacks], bins=20,
                              color='blue', alpha=0.7, edgecolor='black')
                ax_setup.axvline(x=0, color='red', linestyle='--', linewidth=2)
            ax_setup.set_xlabel('Setup Slack (ps)')
            ax_setup.set_ylabel('Count')
            ax_setup.set_title('Setup Slack Distribution')
            ax_setup.grid(True, alpha=0.3)

            # Hold slack distribution
            ax_hold = fig.add_subplot(gs[0, 1])
            hold_slacks = hold_results.get('slacks', [])
            if hold_slacks:
                ax_hold.hist([s * 1e12 for s in hold_slacks], bins=20,
                             color='green', alpha=0.7, edgecolor='black')
                ax_hold.axvline(x=0, color='red', linestyle='--', linewidth=2)
            ax_hold.set_xlabel('Hold Slack (ps)')
            ax_hold.set_ylabel('Count')
            ax_hold.set_title('Hold Slack Distribution')
            ax_hold.grid(True, alpha=0.3)

            # Path delay scatter
            ax_scatter = fig.add_subplot(gs[0, 2])
            setup_delays = [p.get('delay', 0) * 1e12 for p in setup_results.get('paths', [])]
            hold_delays = [p.get('delay', 0) * 1e12 for p in hold_results.get('paths', [])]

            if setup_delays and hold_delays:
                ax_scatter.scatter(setup_delays[:min(50, len(setup_delays))],
                                   hold_delays[:min(50, len(hold_delays))],
                                   alpha=0.6, c='purple', edgecolors='black')
            ax_scatter.set_xlabel('Setup Path Delay (ps)')
            ax_scatter.set_ylabel('Hold Path Delay (ps)')
            ax_scatter.set_title('Path Delay Correlation')
            ax_scatter.grid(True, alpha=0.3)

            # Timing summary table
            ax_table = fig.add_subplot(gs[1, :])
            ax_table.axis('off')

            # Create summary table data
            summary_data = [
                ['Metric', 'Setup', 'Hold'],
                ['Total Paths',
                 str(len(setup_results.get('paths', []))),
                 str(len(hold_results.get('paths', [])))],
                ['Violations',
                 str(setup_results.get('violations', 0)),
                 str(hold_results.get('violations', 0))],
                ['Worst Slack (ps)',
                 f"{setup_results.get('worst_slack', 0) * 1e12:.1f}",
                 f"{hold_results.get('worst_slack', 0) * 1e12:.1f}"],
                ['TNS (ps)',
                 f"{setup_results.get('tns', 0) * 1e12:.1f}",
                 f"{hold_results.get('tns', 0) * 1e12:.1f}"],
                ['Mean Slack (ps)',
                 f"{np.mean(setup_slacks) * 1e12:.1f}" if setup_slacks else 'N/A',
                 f"{np.mean(hold_slacks) * 1e12:.1f}" if hold_slacks else 'N/A']
            ]

            table = ax_table.table(cellText=summary_data, loc='center',
                                   cellLoc='center', colWidths=[0.2, 0.2, 0.2])
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1, 2)

            # Color header
            for i in range(3):
                table[(0, i)].set_facecolor('#404040')
                table[(0, i)].set_text_props(weight='bold', color='white')

            ax_table.set_title('Timing Summary', fontsize=14, fontweight='bold', pad=20)

            plt.suptitle('PySTA Timing Analysis Report', fontsize=16, fontweight='bold')
            plt.tight_layout()

            if output_file:
                plt.savefig(output_file, dpi=self.dpi, bbox_inches='tight')
                plt.close(fig)
                logger.info(f"Timing report figure saved to {output_file}")
                return None
            else:
                return fig

        except Exception as e:
            logger.error(f"Failed to create timing report figure: {e}", exc_info=True)
            return None