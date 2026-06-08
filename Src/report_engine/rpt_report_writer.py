"""
RPT report writer for PySTA.
Generates EDA-style text format timing reports.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from Src.utils.logger import get_logger
from Src.utils.time_utils import TimeUtils

logger = get_logger(__name__)


class RptReportWriter:
    """Writes timing reports in EDA-style text format."""

    def __init__(self):
        self.line_width = 80
        self.separator = "=" * self.line_width

    def write_setup_report(self, results: Dict[str, Any], file_path: str) -> bool:
        """
        Write setup timing report.

        Args:
            results: Setup analysis results
            file_path: Output file path

        Returns:
            True if successful
        """
        try:
            with open(file_path, 'w') as f:
                self._write_header(f, "SETUP TIMING REPORT")

                # Write summary
                self._write_setup_summary(f, results)

                # Write clock summary
                if 'clocks' in results:
                    self._write_clock_summary(f, results['clocks'])

                # Write path details
                self._write_path_details(f, results.get('paths', []), 'setup')

                # Write violation summary
                self._write_violation_summary(f, results)

                # Write footer
                self._write_footer(f)

            logger.info(f"Setup RPT report written to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to write setup RPT report: {e}", exc_info=True)
            return False

    def write_hold_report(self, results: Dict[str, Any], file_path: str) -> bool:
        """
        Write hold timing report.

        Args:
            results: Hold analysis results
            file_path: Output file path

        Returns:
            True if successful
        """
        try:
            with open(file_path, 'w') as f:
                self._write_header(f, "HOLD TIMING REPORT")

                # Write summary
                self._write_hold_summary(f, results)

                # Write clock summary
                if 'clocks' in results:
                    self._write_clock_summary(f, results['clocks'])

                # Write path details
                self._write_path_details(f, results.get('paths', []), 'hold')

                # Write violation summary
                self._write_violation_summary(f, results)

                # Write footer
                self._write_footer(f)

            logger.info(f"Hold RPT report written to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to write hold RPT report: {e}", exc_info=True)
            return False

    def _write_header(self, f, title: str):
        """Write report header."""
        f.write(f"{self.separator}\n")
        f.write(f"{title:^{self.line_width}}\n")
        f.write(f"{self.separator}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{self.separator}\n\n")

    def _write_footer(self, f):
        """Write report footer."""
        f.write(f"\n{self.separator}\n")
        f.write("End of Report\n")
        f.write(f"{self.separator}\n")

    def _write_setup_summary(self, f, results: Dict[str, Any]):
        """Write setup timing summary."""
        f.write("Setup Timing Summary\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total paths analyzed: {results.get('total_paths', 0)}\n")
        f.write(f"Violations: {results.get('violations', 0)}\n")
        f.write(f"Worst slack: {TimeUtils.format_time(results.get('worst_slack', 0))}\n")
        f.write(f"Total Negative Slack (TNS): {TimeUtils.format_time(results.get('tns', 0))}\n")
        f.write(f"Worst Negative Slack (WNS): {TimeUtils.format_time(results.get('wns', 0))}\n")

        if results.get('violations', 0) > 0:
            f.write(f"\n!!! VIOLATIONS DETECTED !!!\n")

        f.write("\n")

    def _write_hold_summary(self, f, results: Dict[str, Any]):
        """Write hold timing summary."""
        f.write("Hold Timing Summary\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total paths analyzed: {results.get('total_paths', 0)}\n")
        f.write(f"Violations: {results.get('violations', 0)}\n")
        f.write(f"Worst slack: {TimeUtils.format_time(results.get('worst_slack', 0))}\n")
        f.write(f"Total Negative Slack (TNS): {TimeUtils.format_time(results.get('tns', 0))}\n")
        f.write(f"Worst Negative Slack (WNS): {TimeUtils.format_time(results.get('wns', 0))}\n")

        if results.get('violations', 0) > 0:
            f.write(f"\n!!! VIOLATIONS DETECTED !!!\n")

        f.write("\n")

    def _write_clock_summary(self, f, clocks: List[Any]):
        """Write clock summary."""
        f.write("Clock Summary\n")
        f.write("-" * 40 + "\n")

        for clock in clocks:
            if hasattr(clock, 'name'):
                f.write(f"\nClock: {clock.name}\n")
                f.write(f"  Period: {TimeUtils.format_time(clock.get_period())}\n")
                f.write(f"  Frequency: {1e9 / clock.get_period():.3f} MHz\n")
                f.write(f"  Waveform: {TimeUtils.format_time(clock.waveform[0])} / "
                        f"{TimeUtils.format_time(clock.waveform[1])}\n")
                f.write(f"  Latency: {TimeUtils.format_time(clock.latency)}\n")
                f.write(f"  Uncertainty: {TimeUtils.format_time(clock.uncertainty)}\n")
                if clock.sources:
                    f.write(f"  Sources: {', '.join(clock.sources)}\n")

        f.write("\n")

    def _write_path_details(self, f, paths: List[Dict], analysis_type: str):
        """Write detailed path information."""
        if not paths:
            f.write("No paths to report\n\n")
            return

        f.write(f"\n{'=' * 60}\n")
        f.write(f"Timing Path Details (Top {min(20, len(paths))} paths)\n")
        f.write(f"{'=' * 60}\n\n")

        for i, path in enumerate(paths[:20]):  # Show top 20 paths
            self._write_single_path(f, path, i + 1, analysis_type)
            f.write("\n" + "-" * 60 + "\n\n")

    def _write_single_path(self, f, path: Dict, index: int, analysis_type: str):
        """Write single path details."""
        slack = path.get('slack', 0)
        slack_str = TimeUtils.format_time(slack)

        # Path header
        f.write(f"Path {index}: {'VIOLATION' if slack < 0 else 'MET'}\n")
        f.write(f"  From: {path.get('from', 'Unknown')}\n")
        f.write(f"  To: {path.get('to', 'Unknown')}\n")
        f.write(f"  Clock: {path.get('clock', 'Unknown')}\n")
        f.write(f"  Path Delay: {TimeUtils.format_time(path.get('delay', 0))}\n")
        f.write(f"  Required: {TimeUtils.format_time(path.get('required', 0))}\n")
        f.write(f"  Slack: {slack_str}\n")

        # Path stages
        stages = path.get('stages', [])
        if stages:
            f.write("\n  Path Stages:\n")
            f.write("  " + "-" * 40 + "\n")

            total_delay = 0
            for j, stage in enumerate(stages):
                stage_delay = stage.get('delay', 0)
                total_delay += stage_delay

                f.write(f"  {j + 1:2d}. {stage.get('type', 'cell'):8} "
                        f"{stage.get('name', 'Unknown'):30} "
                        f"delay={TimeUtils.format_time(stage_delay):>10} "
                        f"slew={TimeUtils.format_time(stage.get('slew', 0)):>10}\n")

            f.write(f"  {' ' * 42}Total: {TimeUtils.format_time(total_delay):>10}\n")

        # Add detailed timing numbers
        f.write("\n  Detailed Timing:\n")
        f.write(f"    Arrival: {TimeUtils.format_time(path.get('arrival', 0))}\n")

        if analysis_type == 'setup':
            f.write(f"    Setup time: {TimeUtils.format_time(path.get('setup_time', 0))}\n")
        else:
            f.write(f"    Hold time: {TimeUtils.format_time(path.get('hold_time', 0))}\n")

        f.write(f"    Uncertainty: {TimeUtils.format_time(path.get('uncertainty', 0))}\n")

        # Add OCV info if available
        if 'ocv_derate' in path:
            f.write(f"    OCV derate: {path.get('ocv_derate', 1.0):.3f}\n")

        # Add SI info if available
        if 'si_penalty' in path:
            f.write(f"    SI penalty: {TimeUtils.format_time(path.get('si_penalty', 0))}\n")

    def _write_violation_summary(self, f, results: Dict[str, Any]):
        """Write violation summary."""
        violations = [p for p in results.get('paths', []) if p.get('slack', 0) < 0]

        if not violations:
            f.write("\nNo timing violations found.\n")
            return

        f.write(f"\n{'=' * 60}\n")
        f.write(f"Timing Violations Summary ({len(violations)} violations)\n")
        f.write(f"{'=' * 60}\n\n")

        # Sort by slack (most negative first)
        violations.sort(key=lambda x: x.get('slack', 0))

        f.write(f"{'Slack':>12} {'From':<30} {'To':<30}\n")
        f.write("-" * 74 + "\n")

        for vio in violations[:50]:  # Show top 50 violations
            slack = vio.get('slack', 0)
            from_pin = vio.get('from', 'Unknown')
            to_pin = vio.get('to', 'Unknown')

            # Truncate if too long
            if len(from_pin) > 28:
                from_pin = from_pin[:25] + "..."
            if len(to_pin) > 28:
                to_pin = to_pin[:25] + "..."

            f.write(f"{TimeUtils.format_time(slack):>12} {from_pin:<30} {to_pin:<30}\n")

        f.write("\n")

        # Violation statistics
        f.write("Violation Statistics:\n")
        f.write(f"  Total violations: {len(violations)}\n")
        f.write(f"  Worst slack: {TimeUtils.format_time(violations[0].get('slack', 0))}\n")

        if len(violations) > 1:
            avg_slack = sum(v.get('slack', 0) for v in violations) / len(violations)
            f.write(f"  Average slack: {TimeUtils.format_time(avg_slack)}\n")