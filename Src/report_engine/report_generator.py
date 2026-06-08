"""
Report generator for PySTA.
Coordinates generation of all report formats.
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import json

from Src.report_engine.excel_report_writer import ExcelReportWriter
from Src.report_engine.rpt_report_writer import RptReportWriter
from Src.report_engine.summary_builder import SummaryBuilder
from Src.utils.logger import get_logger
from Src.utils.time_utils import TimeUtils

logger = get_logger(__name__)


class ReportGenerator:
    """Generates timing analysis reports in multiple formats."""

    def __init__(self):
        self.reports_dir = Path("Reports")
        self.reports_dir.mkdir(exist_ok=True)

        self.excel_writer = ExcelReportWriter()
        self.rpt_writer = RptReportWriter()
        self.summary_builder = SummaryBuilder()

        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def generate_all_reports(self, results: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate all report formats.

        Args:
            results: Analysis results dictionary

        Returns:
            Dictionary mapping report types to file paths
        """
        report_paths = {}

        try:
            # Generate Excel report
            excel_path = self.reports_dir / f"timing_report_{self.timestamp}.xlsx"
            if self.excel_writer.write_report(results, str(excel_path)):
                report_paths['excel'] = str(excel_path)

            # Generate RPT reports
            # Setup report
            if 'setup_results' in results:
                setup_path = self.reports_dir / f"setup_report_{self.timestamp}.rpt"
                if self.rpt_writer.write_setup_report(results['setup_results'], str(setup_path)):
                    report_paths['setup_rpt'] = str(setup_path)

            # Hold report
            if 'hold_results' in results:
                hold_path = self.reports_dir / f"hold_report_{self.timestamp}.rpt"
                if self.rpt_writer.write_hold_report(results['hold_results'], str(hold_path)):
                    report_paths['hold_rpt'] = str(hold_path)

            # Generate summary
            summary_path = self.reports_dir / f"summary_{self.timestamp}.txt"
            if self.summary_builder.write_summary(results, str(summary_path)):
                report_paths['summary'] = str(summary_path)

            # Generate JSON report for machine parsing
            json_path = self.reports_dir / f"timing_data_{self.timestamp}.json"
            if self._write_json_report(results, str(json_path)):
                report_paths['json'] = str(json_path)

            logger.info(f"Generated {len(report_paths)} report files in {self.reports_dir}")

        except Exception as e:
            logger.error(f"Failed to generate reports: {e}", exc_info=True)

        return report_paths

    def generate_setup_report(self, results: Dict[str, Any]) -> Optional[str]:
        """
        Generate only setup timing report.

        Args:
            results: Analysis results

        Returns:
            Path to generated report or None
        """
        if 'setup_results' not in results:
            logger.error("No setup results available")
            return None

        file_path = self.reports_dir / f"setup_report_{self.timestamp}.rpt"

        if self.rpt_writer.write_setup_report(results['setup_results'], str(file_path)):
            logger.info(f"Setup report generated: {file_path}")
            return str(file_path)

        return None

    def generate_hold_report(self, results: Dict[str, Any]) -> Optional[str]:
        """
        Generate only hold timing report.

        Args:
            results: Analysis results

        Returns:
            Path to generated report or None
        """
        if 'hold_results' not in results:
            logger.error("No hold results available")
            return None

        file_path = self.reports_dir / f"hold_report_{self.timestamp}.rpt"

        if self.rpt_writer.write_hold_report(results['hold_results'], str(file_path)):
            logger.info(f"Hold report generated: {file_path}")
            return str(file_path)

        return None

    def generate_excel_report(self, results: Dict[str, Any]) -> Optional[str]:
        """
        Generate Excel format report.

        Args:
            results: Analysis results

        Returns:
            Path to generated report or None
        """
        file_path = self.reports_dir / f"timing_report_{self.timestamp}.xlsx"

        if self.excel_writer.write_report(results, str(file_path)):
            logger.info(f"Excel report generated: {file_path}")
            return str(file_path)

        return None

    def generate_summary(self, results: Dict[str, Any]) -> Optional[str]:
        """
        Generate text summary.

        Args:
            results: Analysis results

        Returns:
            Path to generated summary or None
        """
        file_path = self.reports_dir / f"summary_{self.timestamp}.txt"

        if self.summary_builder.write_summary(results, str(file_path)):
            logger.info(f"Summary generated: {file_path}")
            return str(file_path)

        return None

    def _write_json_report(self, results: Dict[str, Any], file_path: str) -> bool:
        """
        Write JSON format report for machine parsing.

        Args:
            results: Analysis results
            file_path: Output file path

        Returns:
            True if successful
        """
        try:
            # Prepare serializable data
            report_data = {
                'timestamp': datetime.now().isoformat(),
                'summary': self._prepare_summary_data(results),
                'setup': self._prepare_paths_data(results.get('setup_results', {})),
                'hold': self._prepare_paths_data(results.get('hold_results', {})),
                'clocks': self._prepare_clocks_data(results.get('clock_constraints')),
                'statistics': self._prepare_statistics_data(results)
            }

            with open(file_path, 'w') as f:
                json.dump(report_data, f, indent=2, default=str)

            return True

        except Exception as e:
            logger.error(f"Failed to write JSON report: {e}")
            return False

    def _prepare_summary_data(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare summary data for JSON."""
        summary = {}

        if 'graph_builder' in results:
            gb = results['graph_builder']
            summary['design'] = {
                'nodes': len(gb.get_all_nodes()),
                'edges': gb.edge_manager.get_num_edges(),
                'startpoints': len(gb.get_startpoints()),
                'endpoints': len(gb.get_endpoints())
            }

        if 'setup_results' in results:
            setup = results['setup_results']
            summary['setup'] = {
                'total_paths': setup.get('total_paths', 0),
                'violations': setup.get('violations', 0),
                'worst_slack': setup.get('worst_slack', 0),
                'tns': setup.get('tns', 0),
                'wns': setup.get('wns', 0)
            }

        if 'hold_results' in results:
            hold = results['hold_results']
            summary['hold'] = {
                'total_paths': hold.get('total_paths', 0),
                'violations': hold.get('violations', 0),
                'worst_slack': hold.get('worst_slack', 0),
                'tns': hold.get('tns', 0),
                'wns': hold.get('wns', 0)
            }

        return summary

    def _prepare_paths_data(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Prepare paths data for JSON."""
        paths = []

        for path in results.get('paths', [])[:100]:  # Limit to 100 paths
            path_data = {
                'from': path.get('from', ''),
                'to': path.get('to', ''),
                'clock': path.get('clock', ''),
                'delay': path.get('delay', 0),
                'required': path.get('required', 0),
                'slack': path.get('slack', 0),
                'stages': len(path.get('stages', []))
            }
            paths.append(path_data)

        return paths

    def _prepare_clocks_data(self, clock_constraints) -> List[Dict[str, Any]]:
        """Prepare clocks data for JSON."""
        if not clock_constraints:
            return []

        clocks = []
        for clock in clock_constraints.get_all_clocks():
            clock_data = {
                'name': clock.name,
                'period': clock.get_period(),
                'waveform': list(clock.waveform),
                'latency': clock.latency,
                'uncertainty': clock.uncertainty,
                'sources': clock.sources,
                'generated': clock.is_generated
            }
            clocks.append(clock_data)

        return clocks

    def _prepare_statistics_data(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare statistics data for JSON."""
        stats = {}

        # Slack statistics
        if 'setup_results' in results:
            setup_slacks = [p.get('slack', 0) for p in results['setup_results'].get('paths', [])]
            if setup_slacks:
                stats['setup_slack'] = {
                    'min': min(setup_slacks),
                    'max': max(setup_slacks),
                    'mean': sum(setup_slacks) / len(setup_slacks),
                    'std': (sum((x - sum(setup_slacks) / len(setup_slacks)) ** 2 for x in setup_slacks) / len(
                        setup_slacks)) ** 0.5
                }

        if 'hold_results' in results:
            hold_slacks = [p.get('slack', 0) for p in results['hold_results'].get('paths', [])]
            if hold_slacks:
                stats['hold_slack'] = {
                    'min': min(hold_slacks),
                    'max': max(hold_slacks),
                    'mean': sum(hold_slacks) / len(hold_slacks),
                    'std': (sum((x - sum(hold_slacks) / len(hold_slacks)) ** 2 for x in hold_slacks) / len(
                        hold_slacks)) ** 0.5
                }

        return stats

    def get_report_paths(self) -> List[str]:
        """Get all generated report paths."""
        return [str(p) for p in self.reports_dir.glob(f"*_{self.timestamp}.*")]

    def archive_reports(self, archive_name: str = None) -> Optional[str]:
        """
        Archive all reports into a zip file.

        Args:
            archive_name: Name of archive file

        Returns:
            Path to archive file or None
        """
        import zipfile

        if not archive_name:
            archive_name = f"pysta_reports_{self.timestamp}"

        archive_path = self.reports_dir / f"{archive_name}.zip"

        try:
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for report_file in self.get_report_paths():
                    zipf.write(report_file, arcname=Path(report_file).name)

            logger.info(f"Reports archived to {archive_path}")
            return str(archive_path)

        except Exception as e:
            logger.error(f"Failed to archive reports: {e}")
            return None