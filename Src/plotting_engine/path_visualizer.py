"""
Path visualizer for PySTA.
Visualizes timing paths with detailed stage information.
"""

import matplotlib

matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path

from Src.timing_graph.graph_nodes import TimingNode, TimingEdge
from Src.utils.logger import get_logger
from Src.utils.time_utils import TimeUtils

logger = get_logger(__name__)


class PathVisualizer:
    """Visualizer for timing paths."""

    def __init__(self):
        self.colors = {
            'cell': '#87CEEB',
            'net': '#98FB98',
            'clock': '#FFD700',
            'data': '#FFA07A',
            'critical': '#FF6B6B',
            'text': '#000000',
            'grid': '#CCCCCC',
            'background': '#FFFFFF'
        }
        self.figure_size = (14, 8)
        self.dpi = 100

    def visualize_path(self, path: Dict[str, Any], output_file: str = None,
                       show_details: bool = True) -> Optional[plt.Figure]:
        """
        Visualize a single timing path.

        Args:
            path: Path dictionary with stages
            output_file: Path to save the visualization
            show_details: Show detailed timing information

        Returns:
            matplotlib Figure object if output_file is None
        """
        try:
            fig = plt.figure(figsize=self.figure_size, dpi=self.dpi)

            if show_details:
                # Create two subplots: path diagram and timing chart
                gs = fig.add_gridspec(2, 2, height_ratios=[2, 1], width_ratios=[3, 1])
                ax_path = fig.add_subplot(gs[0, 0])
                ax_timing = fig.add_subplot(gs[0, 1])
                ax_summary = fig.add_subplot(gs[1, :])
            else:
                ax_path = fig.add_subplot(111)
                ax_timing = None
                ax_summary = None

            # Draw path diagram
            self._draw_path_diagram(ax_path, path)

            # Draw timing chart if requested
            if ax_timing and show_details:
                self._draw_timing_chart(ax_timing, path)

            # Draw summary if requested
            if ax_summary and show_details:
                self._draw_path_summary(ax_summary, path)

            # Add title
            slack = path.get('slack', 0)
            slack_color = self._get_slack_color(slack)
            title = (f"Timing Path: {path.get('from', 'Unknown')} → {path.get('to', 'Unknown')}\n"
                     f"Slack: {TimeUtils.format_time(slack)}")
            fig.suptitle(title, fontsize=14, fontweight='bold', color=slack_color)

            plt.tight_layout()

            if output_file:
                plt.savefig(output_file, dpi=self.dpi, bbox_inches='tight')
                plt.close(fig)
                logger.info(f"Path visualization saved to {output_file}")
                return None
            else:
                return fig

        except Exception as e:
            logger.error(f"Failed to visualize path: {e}", exc_info=True)
            return None

    def visualize_paths(self, paths: List[Dict[str, Any]], output_file: str = None,
                        max_paths: int = 10) -> Optional[plt.Figure]:
        """
        Visualize multiple timing paths.

        Args:
            paths: List of path dictionaries
            output_file: Path to save the visualization
            max_paths: Maximum number of paths to show

        Returns:
            matplotlib Figure object if output_file is None
        """
        try:
            num_paths = min(len(paths), max_paths)
            cols = 2
            rows = (num_paths + cols - 1) // cols

            fig, axes = plt.subplots(rows, cols, figsize=(16, 6 * rows), dpi=self.dpi)
            if rows == 1 and cols == 1:
                axes = np.array([axes])
            axes = axes.flatten()

            for i in range(num_paths):
                ax = axes[i]
                path = paths[i]

                # Draw simplified path diagram
                self._draw_path_diagram(ax, path, simplified=True)

                # Add path info
                slack = path.get('slack', 0)
                ax.set_title(f"Path {i + 1}: Slack={TimeUtils.format_time(slack)}",
                             color=self._get_slack_color(slack))

            # Hide unused subplots
            for i in range(num_paths, len(axes)):
                axes[i].set_visible(False)

            plt.tight_layout()

            if output_file:
                plt.savefig(output_file, dpi=self.dpi, bbox_inches='tight')
                plt.close(fig)
                logger.info(f"Multi-path visualization saved to {output_file}")
                return None
            else:
                return fig

        except Exception as e:
            logger.error(f"Failed to visualize multiple paths: {e}", exc_info=True)
            return None

    def _draw_path_diagram(self, ax: plt.Axes, path: Dict[str, Any],
                           simplified: bool = False):
        """
        Draw path diagram.

        Args:
            ax: Matplotlib axes
            path: Path dictionary
            simplified: Draw simplified version
        """
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 6)
        ax.set_aspect('equal')
        ax.axis('off')

        stages = path.get('stages', [])

        if not stages:
            ax.text(5, 3, "No path stages available", ha='center', va='center')
            return

        # Calculate positions
        num_stages = len(stages)
        x_positions = np.linspace(1, 9, num_stages)

        # Draw stages
        for i, stage in enumerate(stages):
            x = x_positions[i]

            # Draw stage box
            stage_type = stage.get('type', 'cell')
            color = self.colors.get(stage_type, self.colors['cell'])

            if simplified:
                # Simplified box
                rect = patches.Rectangle((x - 0.4, 2.5), 0.8, 1, linewidth=1,
                                         edgecolor='black', facecolor=color, alpha=0.7)
                ax.add_patch(rect)

                # Add stage name
                name = stage.get('name', f'Stage{i + 1}')
                if len(name) > 10:
                    name = name[:10] + '...'
                ax.text(x, 3, name, ha='center', va='center', fontsize=8)
            else:
                # Detailed box with timing info
                rect = patches.Rectangle((x - 0.6, 1.5), 1.2, 3, linewidth=2,
                                         edgecolor='black', facecolor=color, alpha=0.7)
                ax.add_patch(rect)

                # Add stage details
                ax.text(x, 3.5, stage.get('name', f'Stage{i + 1}'),
                        ha='center', va='center', fontsize=10, fontweight='bold')

                delay = stage.get('delay', 0)
                ax.text(x, 2.8, f"Delay: {TimeUtils.format_time(delay)}",
                        ha='center', va='center', fontsize=8)

                slew = stage.get('slew', 0)
                ax.text(x, 2.2, f"Slew: {TimeUtils.format_time(slew)}",
                        ha='center', va='center', fontsize=8)

            # Draw connections
            if i < num_stages - 1:
                next_x = x_positions[i + 1]

                # Draw arrow
                if simplified:
                    ax.annotate('', xy=(next_x - 0.4, 3), xytext=(x + 0.4, 3),
                                arrowprops=dict(arrowstyle='->', color='gray', linewidth=1))
                else:
                    # Add net delay
                    net_delay = stage.get('net_delay', 0)
                    mid_x = (x + next_x) / 2

                    ax.annotate('', xy=(next_x - 0.6, 3), xytext=(x + 0.6, 3),
                                arrowprops=dict(arrowstyle='->', color='gray', linewidth=1.5))

                    ax.text(mid_x, 3.2, f"net: {TimeUtils.format_time(net_delay)}",
                            ha='center', va='bottom', fontsize=7, color='gray')

        # Add start and end markers
        if not simplified:
            ax.text(x_positions[0] - 0.8, 3, 'Start', ha='right', va='center',
                    fontweight='bold', color='green')
            ax.text(x_positions[-1] + 0.8, 3, 'End', ha='left', va='center',
                    fontweight='bold', color='red')

    def _draw_timing_chart(self, ax: plt.Axes, path: Dict[str, Any]):
        """
        Draw timing chart for the path.

        Args:
            ax: Matplotlib axes
            path: Path dictionary
        """
        stages = path.get('stages', [])

        if not stages:
            ax.text(0.5, 0.5, "No timing data", ha='center', va='center')
            return

        # Prepare data
        delays = [stage.get('delay', 0) * 1e12 for stage in stages]  # Convert to ps
        cumulative = np.cumsum([0] + delays[:-1])

        # Create bar chart
        y_pos = np.arange(len(stages))
        bars = ax.barh(y_pos, delays, left=cumulative, height=0.6, alpha=0.7)

        # Color bars based on stage type
        for i, (bar, stage) in enumerate(zip(bars, stages)):
            stage_type = stage.get('type', 'cell')
            if stage_type == 'clock':
                bar.set_color(self.colors['clock'])
            elif stage_type == 'critical':
                bar.set_color(self.colors['critical'])
            else:
                bar.set_color(self.colors['cell'])

            # Add delay label
            width = bar.get_width()
            ax.text(cumulative[i] + width / 2, i, f"{width:.1f}ps",
                    ha='center', va='center', fontsize=8)

        # Format chart
        ax.set_xlabel('Delay (ps)')
        ax.set_ylabel('Stage')
        ax.set_yticks(y_pos)
        ax.set_yticklabels([stage.get('name', f'S{i + 1}')[:15] for i, stage in enumerate(stages)])
        ax.set_title('Path Delay Breakdown')
        ax.grid(True, alpha=0.3, axis='x')

        # Add total delay line
        total_delay = path.get('delay', 0) * 1e12
        ax.axvline(x=total_delay, color='red', linestyle='--', linewidth=2,
                   label=f'Total: {total_delay:.1f}ps')
        ax.legend()

    def _draw_path_summary(self, ax: plt.Axes, path: Dict[str, Any]):
        """
        Draw path summary.

        Args:
            ax: Matplotlib axes
            path: Path dictionary
        """
        ax.axis('off')

        # Prepare summary text
        summary_lines = [
            "PATH SUMMARY",
            "=" * 40,
            f"From: {path.get('from', 'Unknown')}",
            f"To: {path.get('to', 'Unknown')}",
            f"Clock: {path.get('clock', 'Unknown')}",
            "",
            "TIMING",
            "-" * 20,
            f"Path Delay: {TimeUtils.format_time(path.get('delay', 0))}",
            f"Required: {TimeUtils.format_time(path.get('required', 0))}",
            f"Slack: {TimeUtils.format_time(path.get('slack', 0))}",
        ]

        # Add stage summary
        stages = path.get('stages', [])
        if stages:
            summary_lines.extend(["", "STAGES", "-" * 20])
            for i, stage in enumerate(stages[:5]):  # Show first 5 stages
                summary_lines.append(
                    f"{i + 1}. {stage.get('name', 'Unknown')}: "
                    f"{TimeUtils.format_time(stage.get('delay', 0))}"
                )

            if len(stages) > 5:
                summary_lines.append(f"... and {len(stages) - 5} more")

        # Add text to axis
        y_pos = 0.95
        for line in summary_lines:
            if line.startswith("=") or line.startswith("-"):
                ax.text(0.05, y_pos, line, transform=ax.transAxes,
                        fontfamily='monospace', fontsize=9)
            elif ":" in line:
                parts = line.split(":", 1)
                ax.text(0.05, y_pos, parts[0] + ":", transform=ax.transAxes,
                        fontweight='bold', fontsize=9)
                ax.text(0.4, y_pos, parts[1], transform=ax.transAxes,
                        fontsize=9)
            else:
                ax.text(0.05, y_pos, line, transform=ax.transAxes,
                        fontweight='bold' if line.isupper() else 'normal',
                        fontsize=9)
            y_pos -= 0.03

    def _get_slack_color(self, slack: float) -> str:
        """Get color based on slack value."""
        if slack < 0:
            return '#FF0000'  # Red for violations
        elif slack < 100e-12:  # 100ps
            return '#FFA500'  # Orange for marginal
        else:
            return '#00FF00'  # Green for met