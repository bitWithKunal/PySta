"""
Summary builder for PySTA.
Builds text summary of timing analysis results.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from Src.utils.logger import get_logger
from Src.utils.time_utils import TimeUtils

logger = get_logger(__name__)


class SummaryBuilder:
    """Builds text summary of timing analysis."""

    def __init__(self):
        self.separator = "=" * 80

    def build_summary(self, results: Dict[str, Any]) -> str:
        """
        Build analysis summary text.

        Args:
            results: Analysis results dictionary

        Returns:
            Formatted summary string
        """
        lines = []

        # Header
        lines.append(self.separator)
        lines.append("PySTA TIMING ANALYSIS SUMMARY")
        lines.append(self.separator)
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Design Information
        lines.extend(self._build_design_info(results))

        # Clock Information
        lines.extend(self._build_clock_info(results))

        # Setup Timing Summary
        lines.extend(self._build_setup_summary(results))

        # Hold Timing Summary
        lines.extend(self._build_hold_summary(results))

        # Violation Summary
        lines.extend(self._build_violation_summary(results))

        # OCV Summary (if available)
        lines.extend(self._build_ocv_summary(results))

        # SI Summary (if available)
        lines.extend(self._build_si_summary(results))

        # Footer
        lines.append("")
        lines.append(self.separator)
        lines.append("End of Summary")
        lines.append(self.separator)

        return "\n".join(lines)

    def write_summary(self, results: Dict[str, Any], file_path: str) -> bool:
        """
        Write summary to file.

        Args:
            results: Analysis results
            file_path: Output file path

        Returns:
            True if successful
        """
        try:
            summary = self.build_summary(results)

            with open(file_path, 'w') as f:
                f.write(summary)

            logger.info(f"Summary written to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to write summary: {e}", exc_info=True)
            return False

    def _build_design_info(self, results: Dict[str, Any]) -> List[str]:
        """Build design information section."""
        lines = ["DESIGN INFORMATION", "-" * 40]

        if 'graph_builder' in results:
            gb = results['graph_builder']
            lines.append(f"Total nodes: {len(gb.get_all_nodes())}")
            lines.append(f"Total edges: {gb.edge_manager.get_num_edges()}")
            lines.append(f"Start points: {len(gb.get_startpoints())}")
            lines.append(f"End points: {len(gb.get_endpoints())}")

            # Node type breakdown
            node_types = {}
            for node in gb.get_all_nodes():
                node_types[node.node_type.value] = node_types.get(node.node_type.value, 0) + 1

            if node_types:
                lines.append("")
                lines.append("Node types:")
                for ntype, count in node_types.items():
                    lines.append(f"  {ntype}: {count}")
        else:
            lines.append("No design information available")

        lines.append("")
        return lines

    def _build_clock_info(self, results: Dict[str, Any]) -> List[str]:
        """Build clock information section."""
        lines = ["CLOCK INFORMATION", "-" * 40]

        if 'clock_constraints' in results:
            clocks = results['clock_constraints'].get_all_clocks()

            if clocks:
                for clock in clocks:
                    lines.append(f"\nClock: {clock.name}")
                    lines.append(f"  Period: {TimeUtils.format_time(clock.get_period())}")
                    lines.append(f"  Frequency: {1e9 / clock.get_period():.3f} MHz")
                    lines.append(f"  Waveform: {TimeUtils.format_time(clock.waveform[0])} / "
                                 f"{TimeUtils.format_time(clock.waveform[1])}")
                    lines.append(f"  Latency: {TimeUtils.format_time(clock.latency)}")
                    lines.append(f"  Uncertainty: {TimeUtils.format_time(clock.uncertainty)}")

                    if clock.is_generated and clock.master_clock:
                        lines.append(f"  Generated from: {clock.master_clock.name}")
                        if clock.divide_by:
                            lines.append(f"  Divide by: {clock.divide_by}")
                        if clock.multiply_by:
                            lines.append(f"  Multiply by: {clock.multiply_by}")

                    if clock.sources:
                        lines.append(f"  Sources: {', '.join(clock.sources)}")
            else:
                lines.append("No clocks defined")
        else:
            lines.append("No clock constraints available")

        lines.append("")
        return lines

    def _build_setup_summary(self, results: Dict[str, Any]) -> List[str]:
        """Build setup timing summary section."""
        lines = ["SETUP TIMING SUMMARY", "-" * 40]

        if 'setup_results' in results:
            setup = results['setup_results']

            total_paths = setup.get('total_paths', 0)
            violations = setup.get('violations', 0)

            lines.append(f"Total paths analyzed: {total_paths}")
            lines.append(
                f"Violations: {violations} ({(violations / total_paths * 100) if total_paths > 0 else 0:.1f}%)")
            lines.append(f"Worst slack: {TimeUtils.format_time(setup.get('worst_slack', 0))}")
            lines.append(f"Total Negative Slack (TNS): {TimeUtils.format_time(setup.get('tns', 0))}")
            lines.append(f"Worst Negative Slack (WNS): {TimeUtils.format_time(setup.get('wns', 0))}")

            # Slack statistics
            slacks = [p.get('slack', 0) for p in setup.get('paths', [])]
            if slacks:
                pos_slacks = [s for s in slacks if s >= 0]
                neg_slacks = [s for s in slacks if s < 0]

                lines.append("")
                lines.append("Slack Statistics:")
                lines.append(f"  Positive slacks: {len(pos_slacks)}")
                if pos_slacks:
                    lines.append(f"    Min: {TimeUtils.format_time(min(pos_slacks))}")
                    lines.append(f"    Max: {TimeUtils.format_time(max(pos_slacks))}")
                    lines.append(f"    Avg: {TimeUtils.format_time(sum(pos_slacks) / len(pos_slacks))}")

                lines.append(f"  Negative slacks: {len(neg_slacks)}")
                if neg_slacks:
                    lines.append(f"    Min: {TimeUtils.format_time(min(neg_slacks))}")
                    lines.append(f"    Max: {TimeUtils.format_time(max(neg_slacks))}")
                    lines.append(f"    Avg: {TimeUtils.format_time(sum(neg_slacks) / len(neg_slacks))}")
        else:
            lines.append("No setup analysis results available")

        lines.append("")
        return lines

    def _build_hold_summary(self, results: Dict[str, Any]) -> List[str]:
        """Build hold timing summary section."""
        lines = ["HOLD TIMING SUMMARY", "-" * 40]

        if 'hold_results' in results:
            hold = results['hold_results']

            total_paths = hold.get('total_paths', 0)
            violations = hold.get('violations', 0)

            lines.append(f"Total paths analyzed: {total_paths}")
            lines.append(
                f"Violations: {violations} ({(violations / total_paths * 100) if total_paths > 0 else 0:.1f}%)")
            lines.append(f"Worst slack: {TimeUtils.format_time(hold.get('worst_slack', 0))}")
            lines.append(f"Total Negative Slack (TNS): {TimeUtils.format_time(hold.get('tns', 0))}")
            lines.append(f"Worst Negative Slack (WNS): {TimeUtils.format_time(hold.get('wns', 0))}")

            # Slack statistics
            slacks = [p.get('slack', 0) for p in hold.get('paths', [])]
            if slacks:
                pos_slacks = [s for s in slacks if s >= 0]
                neg_slacks = [s for s in slacks if s < 0]

                lines.append("")
                lines.append("Slack Statistics:")
                lines.append(f"  Positive slacks: {len(pos_slacks)}")
                if pos_slacks:
                    lines.append(f"    Min: {TimeUtils.format_time(min(pos_slacks))}")
                    lines.append(f"    Max: {TimeUtils.format_time(max(pos_slacks))}")
                    lines.append(f"    Avg: {TimeUtils.format_time(sum(pos_slacks) / len(pos_slacks))}")

                lines.append(f"  Negative slacks: {len(neg_slacks)}")
                if neg_slacks:
                    lines.append(f"    Min: {TimeUtils.format_time(min(neg_slacks))}")
                    lines.append(f"    Max: {TimeUtils.format_time(max(neg_slacks))}")
                    lines.append(f"    Avg: {TimeUtils.format_time(sum(neg_slacks) / len(neg_slacks))}")
        else:
            lines.append("No hold analysis results available")

        lines.append("")
        return lines

    def _build_violation_summary(self, results: Dict[str, Any]) -> List[str]:
        """Build violation summary section."""
        lines = ["VIOLATION SUMMARY", "-" * 40]

        violations = []

        # Collect setup violations
        if 'setup_results' in results:
            for path in results['setup_results'].get('paths', []):
                if path.get('slack', 0) < 0:
                    path['type'] = 'setup'
                    violations.append(path)

        # Collect hold violations
        if 'hold_results' in results:
            for path in results['hold_results'].get('paths', []):
                if path.get('slack', 0) < 0:
                    path['type'] = 'hold'
                    violations.append(path)

        if not violations:
            lines.append("No timing violations found.")
        else:
            lines.append(f"Total violations: {len(violations)}")
            lines.append("")
            lines.append("Top 10 Worst Violations:")
            lines.append("-" * 40)

            # Sort by slack (most negative first)
            violations.sort(key=lambda x: x.get('slack', 0))

            for i, vio in enumerate(violations[:10]):
                lines.append(f"{i + 1:2d}. {vio.get('type', '').upper():5} "
                             f"Slack: {TimeUtils.format_time(vio.get('slack', 0)):>12} "
                             f"From: {vio.get('from', 'Unknown'):30} "
                             f"To: {vio.get('to', 'Unknown')}")

        lines.append("")
        return lines

    def _build_ocv_summary(self, results: Dict[str, Any]) -> List[str]:
        """Build OCV summary section if available."""
        lines = []

        if 'ocv_analyzer' in results:
            ocv = results['ocv_analyzer']
            summary = ocv.get_ocv_summary()

            if summary:
                lines.append("OCV ANALYSIS SUMMARY")
                lines.append("-" * 40)
                lines.append(f"Analysis mode: {summary.get('analysis_mode', 'N/A')}")
                lines.append(f"Paths analyzed: {summary.get('num_paths', 0)}")
                lines.append(f"Average OCV penalty: {TimeUtils.format_time(summary.get('avg_ocv_penalty', 0))}")
                lines.append(f"Maximum OCV penalty: {TimeUtils.format_time(summary.get('max_ocv_penalty', 0))}")

                # Derate factors
                derates = summary.get('derate_factors', {})
                if derates:
                    lines.append("")
                    lines.append("Derate Factors:")
                    for name, value in derates.items():
                        lines.append(f"  {name}: {value:.3f}")

                lines.append("")

        return lines

    def _build_si_summary(self, results: Dict[str, Any]) -> List[str]:
        """Build SI summary section if available."""
        lines = []

        if 'si_analyzer' in results:
            si = results['si_analyzer']
            summary = si.get_si_summary() if hasattr(si, 'get_si_summary') else {}

            if summary:
                lines.append("SIGNAL INTEGRITY SUMMARY")
                lines.append("-" * 40)
                lines.append(f"Coupling threshold: {summary.get('coupling_threshold', 0) * 100:.1f}%")
                lines.append(f"Noise margin: {summary.get('noise_margin', 0) * 100:.1f}%")
                lines.append(f"Average SI penalty: {TimeUtils.format_time(summary.get('avg_penalty', 0))}")
                lines.append(f"Maximum SI penalty: {TimeUtils.format_time(summary.get('max_penalty', 0))}")
                lines.append(f"Nets affected: {summary.get('nets_affected', 0)}")
                lines.append("")

        return lines