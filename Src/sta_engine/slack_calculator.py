"""
Slack calculator for STA engine.
Calculates and analyzes timing slack.
"""

from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict
import math

from Src.timing_graph.graph_nodes import TimingNode
from Src.utils.logger import get_logger
from Src.utils.time_utils import TimeUtils

logger = get_logger(__name__)


class SlackCalculator:
    """Calculates and analyzes timing slack."""

    def __init__(self):
        self.slack_thresholds = {
            'critical': -50e-12,   # -50ps
            'violation': 0,         # 0ps
            'marginal': 100e-12,    # 100ps
            'safe': 500e-12         # 500ps
        }

        self.slack_stats = {}

        logger.info("Slack calculator initialized")

    def calculate_slack(self, required_time: float, arrival_time: float,
                        analysis_type: str = 'setup') -> float:
        """
        Calculate slack for a single endpoint.

        Args:
            required_time: Required time
            arrival_time: Arrival time
            analysis_type: 'setup' or 'hold'

        Returns:
            Slack value
        """
        if analysis_type == 'setup':
            slack = required_time - arrival_time
        else:  # hold
            slack = arrival_time - required_time

        return slack

    def classify_slack(self, slack: float) -> str:
        """
        Classify slack value.

        Args:
            slack: Slack value in seconds

        Returns:
            Classification string
        """
        if slack < self.slack_thresholds['critical']:
            return 'critical'
        elif slack < self.slack_thresholds['violation']:
            return 'violation'
        elif slack < self.slack_thresholds['marginal']:
            return 'marginal'
        elif slack < self.slack_thresholds['safe']:
            return 'safe'
        else:
            return 'clean'

    def calculate_path_slack(self, path: Dict[str, Any]) -> float:
        """
        Calculate slack for a timing path.

        Args:
            path: Path dictionary

        Returns:
            Path slack
        """
        required = path.get('required', 0)
        arrival = path.get('arrival', 0)
        analysis_type = path.get('type', 'setup')

        return self.calculate_slack(required, arrival, analysis_type)

    def calculate_slack_distribution(self, slacks: List[float]) -> Dict[str, Any]:
        """
        Calculate slack distribution statistics.

        Args:
            slacks: List of slack values

        Returns:
            Dictionary with distribution statistics
        """
        if not slacks:
            return {}

        # Filter out infinite values
        valid_slacks = [s for s in slacks if s != float('inf') and s != float('-inf')]

        if not valid_slacks:
            return {}

        slacks_ps = [s * 1e12 for s in valid_slacks]

        distribution = {
            'count': len(valid_slacks),
            'min': min(valid_slacks),
            'max': max(valid_slacks),
            'mean': sum(valid_slacks) / len(valid_slacks),
            'median': sorted(valid_slacks)[len(valid_slacks) // 2],
            'std': (sum((s - sum(valid_slacks) / len(valid_slacks)) ** 2 for s in valid_slacks) / len(valid_slacks)) ** 0.5,

            # Convert to ps for readability
            'min_ps': min(slacks_ps),
            'max_ps': max(slacks_ps),
            'mean_ps': sum(slacks_ps) / len(slacks_ps),
            'median_ps': sorted(slacks_ps)[len(slacks_ps) // 2],
            'std_ps': (sum((s - sum(slacks_ps) / len(slacks_ps)) ** 2 for s in slacks_ps) / len(slacks_ps)) ** 0.5
        }

        # Calculate percentiles
        sorted_slacks = sorted(valid_slacks)
        for percentile in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
            idx = min(int(len(sorted_slacks) * percentile / 100), len(sorted_slacks) - 1)
            distribution[f'p{percentile}'] = sorted_slacks[idx]
            distribution[f'p{percentile}_ps'] = sorted_slacks[idx] * 1e12

        # Classification counts
        classification = defaultdict(int)
        for slack in valid_slacks:
            cat = self.classify_slack(slack)
            classification[cat] += 1

        distribution['classification'] = dict(classification)

        return distribution

    def calculate_negative_slack_metrics(self, slacks: List[float]) -> Dict[str, float]:
        """
        Calculate metrics for negative slack.

        Args:
            slacks: List of slack values

        Returns:
            Dictionary with negative slack metrics
        """
        # Filter out infinite values
        valid_slacks = [s for s in slacks if s != float('inf') and s != float('-inf')]
        negative_slacks = [s for s in valid_slacks if s < 0]

        if not negative_slacks:
            return {
                'tns': 0,  # Total Negative Slack
                'wns': 0,  # Worst Negative Slack
                'count': 0,
                'average': 0,
                'fep': 0   # Failing Endpoint Percentage
            }

        metrics = {
            'tns': abs(sum(negative_slacks)),
            'wns': min(negative_slacks),
            'count': len(negative_slacks),
            'average': sum(negative_slacks) / len(negative_slacks),
            'fep': (len(negative_slacks) / len(valid_slacks)) * 100 if valid_slacks else 0
        }

        return metrics

    def calculate_positive_slack_metrics(self, slacks: List[float]) -> Dict[str, float]:
        """
        Calculate metrics for positive slack.

        Args:
            slacks: List of slack values

        Returns:
            Dictionary with positive slack metrics
        """
        # Filter out infinite values
        valid_slacks = [s for s in slacks if s != float('inf') and s != float('-inf')]
        positive_slacks = [s for s in valid_slacks if s >= 0]

        if not positive_slacks:
            return {
                'tps': 0,  # Total Positive Slack
                'wps': 0,  # Worst Positive Slack
                'count': 0,
                'average': 0
            }

        metrics = {
            'tps': sum(positive_slacks),
            'wps': min(positive_slacks),
            'count': len(positive_slacks),
            'average': sum(positive_slacks) / len(positive_slacks)
        }

        return metrics

    def calculate_slack_budget(self, path: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate slack budget breakdown by stage.

        Args:
            path: Path dictionary with stages

        Returns:
            Dictionary with stage contributions to slack
        """
        stages = path.get('stages', [])
        total_delay = path.get('delay', 0)
        required = path.get('required', 0)
        slack = path.get('slack', 0)

        if not stages or total_delay == 0:
            return {}

        budget = {}
        cumulative = 0

        for i, stage in enumerate(stages):
            stage_delay = stage.get('delay', 0)
            cumulative += stage_delay

            # Calculate contribution to slack
            if i == len(stages) - 1:
                # Last stage - remaining delay
                contribution = required - cumulative
            else:
                # Intermediate stage - negative of its delay
                contribution = -stage_delay

            budget[f'stage_{i}'] = {
                'name': stage.get('name', f'Stage{i}'),
                'delay': stage_delay,
                'delay_ps': stage_delay * 1e12,
                'contribution': contribution,
                'contribution_ps': contribution * 1e12,
                'cumulative': cumulative,
                'cumulative_ps': cumulative * 1e12
            }

        budget['total'] = {
            'delay': total_delay,
            'delay_ps': total_delay * 1e12,
            'required': required,
            'required_ps': required * 1e12,
            'slack': slack,
            'slack_ps': slack * 1e12
        }

        return budget

    def find_slack_critical_paths(self, paths: List[Dict[str, Any]],
                                  threshold: float = 0) -> List[Dict[str, Any]]:
        """
        Find paths with slack below threshold.

        Args:
            paths: List of paths
            threshold: Slack threshold

        Returns:
            List of critical paths
        """
        critical = []

        for path in paths:
            slack = path.get('slack', float('inf'))
            if slack != float('inf') and slack < threshold:
                critical.append(path)

        # Sort by slack (most critical first)
        critical.sort(key=lambda x: x.get('slack', 0))

        return critical

    def group_slack_by_clock(self, paths: List[Dict[str, Any]]) -> Dict[str, List[float]]:
        """
        Group slack values by clock domain.

        Args:
            paths: List of paths

        Returns:
            Dictionary mapping clock to list of slacks
        """
        by_clock = defaultdict(list)

        for path in paths:
            clock = path.get('clock', 'unknown')
            slack = path.get('slack', 0)
            if slack != float('inf') and slack != float('-inf'):
                by_clock[clock].append(slack)

        return dict(by_clock)

    def calculate_clock_slack_metrics(self, paths: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate slack metrics per clock domain.

        Args:
            paths: List of paths

        Returns:
            Dictionary with per-clock metrics
        """
        by_clock = self.group_slack_by_clock(paths)

        clock_metrics = {}

        for clock, slacks in by_clock.items():
            if not slacks:
                continue

            clock_metrics[clock] = {
                'paths': len(slacks),
                'worst_slack': min(slacks),
                'best_slack': max(slacks),
                'mean_slack': sum(slacks) / len(slacks),
                'tns': abs(sum(s for s in slacks if s < 0)),
                'violations': len([s for s in slacks if s < 0]),
                'distribution': self.calculate_slack_distribution(slacks)
            }

        return clock_metrics

    def calculate_slack_improvement_potential(self, path: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate potential slack improvement by optimizing stages.

        Args:
            path: Path dictionary

        Returns:
            Dictionary with improvement potential per stage
        """
        stages = path.get('stages', [])
        current_slack = path.get('slack', 0)

        if current_slack >= 0:
            return {'message': 'Path already meets timing', 'current_slack_ps': current_slack * 1e12}

        improvement = {}
        total_delay = path.get('delay', 0)

        for i, stage in enumerate(stages):
            stage_delay = stage.get('delay', 0)
            stage_name = stage.get('name', f'Stage{i}')

            # Assume we can improve stage delay by 10-30%
            for improvement_factor in [0.1, 0.2, 0.3]:
                delay_reduction = stage_delay * improvement_factor
                new_slack = current_slack + delay_reduction

                improvement[f'stage_{i}_{int(improvement_factor * 100)}%'] = {
                    'stage_name': stage_name,
                    'current_delay': stage_delay,
                    'current_delay_ps': stage_delay * 1e12,
                    'reduction': delay_reduction,
                    'reduction_ps': delay_reduction * 1e12,
                    'new_slack': new_slack,
                    'new_slack_ps': new_slack * 1e12,
                    'meets_timing': new_slack >= 0
                }

        # Calculate total improvement potential
        max_improvement = max([v['reduction'] for v in improvement.values()]) if improvement else 0
        improvement['summary'] = {
            'current_slack': current_slack,
            'current_slack_ps': current_slack * 1e12,
            'max_improvement': max_improvement,
            'max_improvement_ps': max_improvement * 1e12,
            'potential_slack': current_slack + max_improvement,
            'potential_slack_ps': (current_slack + max_improvement) * 1e12,
            'can_fix': (current_slack + max_improvement) >= 0
        }

        return improvement

    def generate_slack_report(self, setup_paths: List[Dict[str, Any]] = None,
                              hold_paths: List[Dict[str, Any]] = None) -> str:
        """
        Generate formatted slack report.

        Args:
            setup_paths: List of setup paths
            hold_paths: List of hold paths

        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 80)
        lines.append("SLACK ANALYSIS REPORT")
        lines.append("=" * 80)

        # Setup slack
        if setup_paths:
            setup_slacks = [p.get('slack', 0) for p in setup_paths if p.get('slack', 0) != float('inf')]
            if setup_slacks:
                setup_metrics = self.calculate_negative_slack_metrics(setup_slacks)
                setup_dist = self.calculate_slack_distribution(setup_slacks)

                lines.append("\nSETUP SLACK SUMMARY")
                lines.append("-" * 40)
                lines.append(f"Total paths: {len(setup_paths)}")
                lines.append(f"Valid paths: {len(setup_slacks)}")
                lines.append(f"Violations: {setup_metrics['count']}")
                lines.append(f"WNS: {TimeUtils.format_time(setup_metrics['wns'])}")
                lines.append(f"TNS: {TimeUtils.format_time(setup_metrics['tns'])}")
                lines.append(f"FEP: {setup_metrics['fep']:.1f}%")
                if setup_dist:
                    lines.append(f"Mean slack: {TimeUtils.format_time(setup_dist.get('mean', 0))}")
                    lines.append(f"Median slack: {TimeUtils.format_time(setup_dist.get('median', 0))}")

                    # Classification
                    lines.append("\nSetup Slack Classification:")
                    for cat, count in setup_dist.get('classification', {}).items():
                        percentage = (count / len(setup_slacks)) * 100
                        lines.append(f"  {cat}: {count} paths ({percentage:.1f}%)")

        # Hold slack
        if hold_paths:
            hold_slacks = [p.get('slack', 0) for p in hold_paths if p.get('slack', 0) != float('inf')]
            if hold_slacks:
                hold_metrics = self.calculate_negative_slack_metrics(hold_slacks)
                hold_dist = self.calculate_slack_distribution(hold_slacks)

                lines.append("\n\nHOLD SLACK SUMMARY")
                lines.append("-" * 40)
                lines.append(f"Total paths: {len(hold_paths)}")
                lines.append(f"Valid paths: {len(hold_slacks)}")
                lines.append(f"Violations: {hold_metrics['count']}")
                lines.append(f"WNS: {TimeUtils.format_time(hold_metrics['wns'])}")
                lines.append(f"TNS: {TimeUtils.format_time(hold_metrics['tns'])}")
                lines.append(f"FEP: {hold_metrics['fep']:.1f}%")
                if hold_dist:
                    lines.append(f"Mean slack: {TimeUtils.format_time(hold_dist.get('mean', 0))}")
                    lines.append(f"Median slack: {TimeUtils.format_time(hold_dist.get('median', 0))}")

                    # Classification
                    lines.append("\nHold Slack Classification:")
                    for cat, count in hold_dist.get('classification', {}).items():
                        percentage = (count / len(hold_slacks)) * 100
                        lines.append(f"  {cat}: {count} paths ({percentage:.1f}%)")

        # Percentiles
        if (setup_paths and setup_slacks) or (hold_paths and hold_slacks):
            lines.append("\n\nSLACK PERCENTILES")
            lines.append("-" * 40)

            if setup_paths and setup_slacks and setup_dist:
                lines.append("\nSetup:")
                for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
                    if f'p{p}' in setup_dist:
                        lines.append(f"  p{p}: {TimeUtils.format_time(setup_dist[f'p{p}'])}")

            if hold_paths and hold_slacks and hold_dist:
                lines.append("\nHold:")
                for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
                    if f'p{p}' in hold_dist:
                        lines.append(f"  p{p}: {TimeUtils.format_time(hold_dist[f'p{p}'])}")

        lines.append("\n" + "=" * 80)

        return "\n".join(lines)

    def set_thresholds(self, critical: float = -50e-12, violation: float = 0,
                       marginal: float = 100e-12, safe: float = 500e-12):
        """
        Set slack classification thresholds.

        Args:
            critical: Critical threshold
            violation: Violation threshold
            marginal: Marginal threshold
            safe: Safe threshold
        """
        self.slack_thresholds = {
            'critical': critical,
            'violation': violation,
            'marginal': marginal,
            'safe': safe
        }

        logger.info(f"Slack thresholds updated: critical={critical*1e12:.1f}ps, "
                   f"violation={violation*1e12:.1f}ps, marginal={marginal*1e12:.1f}ps, "
                   f"safe={safe*1e12:.1f}ps")

    def reset(self):
        """Reset calculator state."""
        self.slack_stats.clear()
        logger.debug("Slack calculator reset")