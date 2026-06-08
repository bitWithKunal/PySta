"""
Base analyzer for STA engine.
Common functionality for setup and hold analysis.
"""

from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict
from abc import ABC, abstractmethod

from Src.timing_graph.graph_nodes import TimingNode, TimingEdge
from Src.timing_graph.graph_edges import EdgeManager
from Src.timing_graph.path_extractor import PathExtractor
from Src.sta_engine.delay_calculator import DelayCalculator
from Src.sta_engine.arrival_required import ArrivalRequiredCalculator
from Src.sdc_parser.clock_constraints import ClockConstraints
from Src.sdc_parser.timing_exceptions import ExceptionManager
from Src.ocv_engine.ocv_analyzer import OCVAnalyzer
from Src.si_engine.si_analyzer import SIAnalyzer
from Src.utils.logger import get_logger
from Src.utils.time_utils import TimeUtils

logger = get_logger(__name__)


class BaseAnalyzer(ABC):
    """Base class for timing analyzers."""

    def __init__(self, edge_manager: EdgeManager, delay_calculator: DelayCalculator,
                 clock_constraints: ClockConstraints, exception_manager: ExceptionManager = None,
                 ocv_analyzer: OCVAnalyzer = None, si_analyzer: SIAnalyzer = None):

        self.edge_manager = edge_manager
        self.delay_calculator = delay_calculator
        self.clock_constraints = clock_constraints
        self.exception_manager = exception_manager
        self.ocv_analyzer = ocv_analyzer
        self.si_analyzer = si_analyzer

        self.path_extractor = PathExtractor(edge_manager)
        self.arrival_calculator = ArrivalRequiredCalculator(
            edge_manager, delay_calculator, clock_constraints, exception_manager
        )

        # Analysis results
        self.paths: List[Dict[str, Any]] = []
        self.violations: List[Dict[str, Any]] = []
        self.metrics: Dict[str, Any] = {}

        # Caches
        self._clock_list_cache: Optional[List[str]] = None

    @property
    @abstractmethod
    def analysis_type(self) -> str:
        """Return analysis type ('setup' or 'hold')."""
        pass

    @abstractmethod
    def get_paths(self, max_paths: int) -> List[Dict[str, Any]]:
        """Get paths for this analysis type."""
        pass

    def analyze(self, max_paths: int = 100) -> Dict[str, Any]:
        """
        Perform timing analysis.

        Args:
            max_paths: Maximum number of paths to report

        Returns:
            Dictionary with analysis results
        """
        logger.info(f"Starting {self.analysis_type} timing analysis")

        # Set analysis type for arrival calculator
        self.arrival_calculator.analysis_type = self.analysis_type

        # Calculate arrival times
        self.arrival_calculator.calculate_arrival_times()

        # Calculate required times
        self.arrival_calculator.calculate_required_times()

        # Calculate slacks
        self._calculate_slacks()

        # Extract paths
        self.paths = self.get_paths(max_paths)

        if not self.paths:
            logger.warning(f"No {self.analysis_type} paths found")
            return self._empty_result()

        logger.info(f"Found {len(self.paths)} {self.analysis_type} paths")

        # Apply exceptions
        if self.exception_manager:
            self._apply_exceptions()

        # Apply OCV if available
        if self.ocv_analyzer:
            self._apply_ocv()

        # Apply SI if available
        if self.si_analyzer:
            self._apply_si()

        # Calculate metrics
        self._calculate_metrics()

        # Log summary
        self._log_summary()

        return self._build_result()

    def _calculate_slacks(self):
        """Calculate slacks for all endpoints."""
        slack_count = 0
        for node in self.edge_manager.get_all_nodes():
            node.calculate_slack()
            if node.slack_rise != 0 or node.slack_fall != 0:
                slack_count += 1

        logger.debug(f"Calculated slacks for {slack_count} nodes")

    def _apply_exceptions(self):
        """Apply timing exceptions to paths."""
        exception_count = 0
        for path in self.paths:
            from_pin = path.get('from', '')
            to_pin = path.get('to', '')

            # Check if path is false
            if self.exception_manager.is_false_path(from_pin, to_pin):
                path['slack'] = float('inf')
                path['is_false'] = True
                exception_count += 1
                continue

            # Apply multicycle
            if self.analysis_type == 'setup':
                mcycles = self.exception_manager.get_multicycle_setup(from_pin, to_pin)
                if mcycles > 1:
                    clock_period = path.get('clock_period', 10e-9)
                    path['required'] += (mcycles - 1) * clock_period
                    path['slack'] = path['required'] - path['arrival']
                    path['multicycle'] = mcycles
                    exception_count += 1

                # Apply max delay
                max_delay = self.exception_manager.get_max_delay(from_pin, to_pin)
                if max_delay is not None:
                    path['required'] = max_delay
                    path['slack'] = max_delay - path['arrival']
                    exception_count += 1
            else:  # hold
                mcycles = self.exception_manager.get_multicycle_hold(from_pin, to_pin)
                if mcycles > 0:
                    clock_period = path.get('clock_period', 10e-9)
                    path['required'] += mcycles * clock_period
                    path['slack'] = path['arrival'] - path['required']
                    path['multicycle'] = mcycles
                    exception_count += 1

                # Apply min delay
                min_delay = self.exception_manager.get_min_delay(from_pin, to_pin)
                if min_delay is not None:
                    path['required'] = min_delay
                    path['slack'] = path['arrival'] - min_delay
                    exception_count += 1

        if exception_count > 0:
            logger.debug(f"Applied {exception_count} exceptions to {self.analysis_type} paths")

    def _apply_ocv(self):
        """Apply OCV analysis to paths."""
        if not self.ocv_analyzer:
            return

        self.ocv_analyzer.analysis_mode = self.analysis_type
        try:
            ocv_paths = self.ocv_analyzer.analyze_paths(self.paths)

            for i, path in enumerate(self.paths):
                if i < len(ocv_paths):
                    ocv = ocv_paths[i]
                    path['nominal_delay'] = ocv.nominal_delay
                    path['early_delay'] = ocv.early_delay
                    path['late_delay'] = ocv.late_delay

                    # Use appropriate delay for this analysis
                    if self.analysis_type == 'setup':
                        path['delay'] = ocv.late_delay
                    else:
                        path['delay'] = ocv.early_delay

                    path['ocv_derate'] = ocv.get_derate_ratio()
                    path['slack'] = self._recalculate_slack(path)

            logger.debug(f"Applied OCV to {len(ocv_paths)} {self.analysis_type} paths")
        except Exception as e:
            logger.warning(f"Error applying OCV: {e}")

    def _apply_si(self):
        """Apply SI analysis to paths."""
        if not self.si_analyzer:
            return

        si_count = 0
        for path in self.paths:
            try:
                si_penalty = self.si_analyzer.get_path_si_penalty(path)
                if si_penalty > 0:
                    path['si_penalty'] = si_penalty
                    path['delay'] += si_penalty
                    path['slack'] -= si_penalty
                    path['si_affected'] = True
                    si_count += 1
            except Exception as e:
                logger.warning(f"Error applying SI to path: {e}")

        if si_count > 0:
            logger.debug(f"Applied SI to {si_count} {self.analysis_type} paths")

    def _recalculate_slack(self, path: Dict[str, Any]) -> float:
        """Recalculate slack after modifications."""
        if self.analysis_type == 'setup':
            return path.get('required', 0) - path.get('arrival', 0)
        else:
            return path.get('arrival', 0) - path.get('required', 0)

    def _calculate_metrics(self):
        """Calculate timing metrics."""
        if not self.paths:
            self.metrics = self._empty_metrics()
            return

        # Filter out false paths
        valid_paths = [p for p in self.paths if p.get('slack', 0) != float('inf')]

        if not valid_paths:
            self.metrics = self._empty_metrics()
            return

        slacks = [p.get('slack', 0) for p in valid_paths]
        negative_slacks = [s for s in slacks if s < 0]

        # Update violations list
        self.violations = [p for p in valid_paths if p.get('slack', 0) < 0]

        # Calculate metrics
        self.metrics = {
            'worst_slack': min(slacks),
            'tns': abs(sum(negative_slacks)) if negative_slacks else 0,
            'wns': min(negative_slacks) if negative_slacks else 0,
            'mean_slack': sum(slacks) / len(slacks),
            'median_slack': sorted(slacks)[len(slacks) // 2],
            'std_slack': self._calculate_std(slacks)
        }

        logger.debug(f"{self.analysis_type.capitalize()} metrics: "
                     f"worst_slack={self.metrics['worst_slack'] * 1e12:.2f}ps, "
                     f"violations={len(self.violations)}")

    @staticmethod
    def _calculate_std(values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        return (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5

    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics dictionary."""
        return {
            'worst_slack': 0,
            'tns': 0,
            'wns': 0,
            'mean_slack': 0,
            'median_slack': 0,
            'std_slack': 0
        }

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result dictionary."""
        return {
            'paths': [],
            'violations': [],
            'total_paths': 0,
            'violations': 0,
            'worst_slack': 0,
            'tns': 0,
            'wns': 0,
            'clocks': self._get_clock_list(),
            'slacks': []
        }

    def _build_result(self) -> Dict[str, Any]:
        """Build result dictionary."""
        return {
            'paths': self.paths,
            'violations': self.violations,
            'total_paths': len(self.paths),
            'violations': len(self.violations),
            'worst_slack': self.metrics.get('worst_slack', 0),
            'tns': self.metrics.get('tns', 0),
            'wns': self.metrics.get('wns', 0),
            'clocks': self._get_clock_list(),
            'slacks': [p.get('slack', 0) for p in self.paths]
        }

    def _get_clock_list(self) -> List[str]:
        """Get list of clocks in design with caching."""
        if self._clock_list_cache is not None:
            return self._clock_list_cache

        clocks = set()
        for path in self.paths:
            if 'clock' in path and path['clock']:
                clocks.add(path['clock'])

        if self.clock_constraints:
            for clock in self.clock_constraints.get_all_clocks():
                clocks.add(clock.name)

        self._clock_list_cache = list(clocks)
        return self._clock_list_cache

    def _log_summary(self):
        """Log analysis summary."""
        logger.info("=" * 60)
        logger.info(f"{self.analysis_type.capitalize()} Timing Analysis Summary")
        logger.info("=" * 60)
        logger.info(f"Total paths analyzed: {len(self.paths)}")
        logger.info(f"Violations: {len(self.violations)}")
        logger.info(f"Worst slack: {TimeUtils.format_time(self.metrics.get('worst_slack', 0))}")
        logger.info(f"TNS: {TimeUtils.format_time(self.metrics.get('tns', 0))}")
        logger.info(f"WNS: {TimeUtils.format_time(self.metrics.get('wns', 0))}")
        logger.info("=" * 60)

    def get_worst_paths(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get worst paths (most negative slack)."""
        valid_paths = [p for p in self.paths if p.get('slack', 0) != float('inf')]
        sorted_paths = sorted(valid_paths, key=lambda x: x.get('slack', 0))
        return sorted_paths[:n]

    def get_paths_by_clock(self, clock_name: str) -> List[Dict[str, Any]]:
        """Get paths for a specific clock."""
        return [p for p in self.paths if p.get('clock') == clock_name]

    def get_violation_stats(self) -> Dict[str, Any]:
        """Get violation statistics."""
        if not self.violations:
            return {'count': 0}

        slacks = [v.get('slack', 0) for v in self.violations]

        # Group by clock
        by_clock = defaultdict(list)
        for v in self.violations:
            by_clock[v.get('clock', 'unknown')].append(v)

        clock_stats = {}
        for clock, vio_list in by_clock.items():
            clock_slacks = [v.get('slack', 0) for v in vio_list]
            clock_stats[clock] = {
                'count': len(vio_list),
                'worst': min(clock_slacks),
                'avg': sum(clock_slacks) / len(clock_slacks) if clock_slacks else 0
            }

        return {
            'count': len(self.violations),
            'worst_slack': min(slacks),
            'avg_slack': sum(slacks) / len(slacks),
            'by_clock': clock_stats,
            'total_negative_slack': self.metrics.get('tns', 0)
        }

    def print_path(self, path: Dict[str, Any], detailed: bool = True):
        """Print a timing path."""
        print(f"\n{'=' * 60}")
        print(f"{self.analysis_type.capitalize()} Path: {path.get('from', 'Unknown')} -> "
              f"{path.get('to', 'Unknown')}")
        print(f"{'=' * 60}")
        print(f"Clock: {path.get('clock', 'Unknown')}")
        print(f"Path Delay: {TimeUtils.format_time(path.get('delay', 0))}")
        print(f"Required: {TimeUtils.format_time(path.get('required', 0))}")
        print(f"Slack: {TimeUtils.format_time(path.get('slack', 0))}")
        print(f"Status: {'VIOLATION' if path.get('slack', 0) < 0 else 'MET'}")

        if detailed:
            print(f"\nPath Stages:")
            print(f"{'-' * 60}")

            for i, stage in enumerate(path.get('stages', [])):
                print(f"{i + 1:2d}. {stage.get('type', 'cell'):8} "
                      f"{stage.get('name', 'Unknown'):30} "
                      f"delay={TimeUtils.format_time(stage.get('delay', 0))} "
                      f"slew={TimeUtils.format_time(stage.get('slew', 0))}")

            if 'ocv_derate' in path:
                print(f"\nOCV Derate: {path['ocv_derate']:.3f}")
            if 'si_penalty' in path:
                print(f"SI Penalty: {TimeUtils.format_time(path['si_penalty'])}")

    def reset(self):
        """Reset analyzer state."""
        self.paths.clear()
        self.violations.clear()
        self.metrics.clear()
        self._clock_list_cache = None
        logger.debug(f"{self.analysis_type.capitalize()} analyzer reset")