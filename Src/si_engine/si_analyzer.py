"""
SI analyzer for PySTA.
Performs signal integrity analysis including crosstalk delay.
"""

from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict
import math

from Src.liberty_parser.cell_library import CellLibrary
from Src.timing_graph.graph_nodes import TimingNode
from Src.utils.logger import get_logger
from Src.utils.time_utils import TimeUtils

logger = get_logger(__name__)


class SIAnalyzer:
    """Analyzer for signal integrity effects."""

    def __init__(self, cell_library: CellLibrary):
        self.cell_library = cell_library

        # SI parameters
        self.coupling_threshold = 0.1  # 10% coupling ratio threshold
        self.noise_margin = 0.2  # 20% noise margin
        self.aggressor_count = 3  # Default number of aggressors

        # Coupling capacitance ratio by metal layer
        self.coupling_ratios = {
            'M1': 0.05,
            'M2': 0.10,
            'M3': 0.15,
            'M4': 0.12,
            'M5': 0.08,
            'M6': 0.06
        }

        # Noise immunity by cell type
        self.noise_immunity = {
            'INV': 0.3,
            'BUF': 0.35,
            'NAND': 0.4,
            'NOR': 0.4,
            'AND': 0.45,
            'OR': 0.45,
            'XOR': 0.5,
            'DFF': 0.6,
            'LATCH': 0.55
        }

        # Results storage
        self.net_si_analysis: Dict[str, Dict[str, Any]] = {}
        self.path_si_penalties: Dict[str, float] = {}

        logger.info("SI analyzer initialized")

    def set_coupling_threshold(self, threshold: float):
        """Set coupling capacitance threshold."""
        self.coupling_threshold = threshold
        logger.debug(f"Coupling threshold set to {threshold * 100:.1f}%")

    def set_noise_margin(self, margin: float):
        """Set noise margin."""
        self.noise_margin = margin
        logger.debug(f"Noise margin set to {margin * 100:.1f}%")

    def analyze_net(self, net_name: str, aggressors: List[str] = None) -> Dict[str, Any]:
        """
        Analyze SI effects on a net.

        Args:
            net_name: Name of the net to analyze
            aggressors: List of aggressor net names

        Returns:
            Dictionary with SI analysis results
        """
        if aggressors is None:
            aggressors = self._find_aggressors(net_name)

        # Calculate coupling capacitance
        coupling_cap = self._calculate_coupling_capacitance(net_name, aggressors)

        # Calculate noise voltage
        noise_voltage = self._calculate_noise_voltage(net_name, coupling_cap)

        # Check if noise exceeds margin
        noise_exceeds = noise_voltage > self.noise_margin

        # Calculate delay push-out
        delay_penalty = self._calculate_delay_penalty(net_name, coupling_cap, len(aggressors))

        # Calculate slew degradation
        slew_degradation = self._calculate_slew_degradation(net_name, coupling_cap)

        # Determine if net is critical for SI
        is_critical = (coupling_cap > self.coupling_threshold and
                       (noise_exceeds or delay_penalty > 0))

        result = {
            'net_name': net_name,
            'aggressor_count': len(aggressors),
            'aggressors': aggressors[:10],  # Limit to first 10
            'coupling_capacitance': coupling_cap,
            'coupling_ratio': coupling_cap / max(1e-15, self._get_net_capacitance(net_name)),
            'noise_voltage': noise_voltage,
            'noise_exceeds_margin': noise_exceeds,
            'delay_penalty': delay_penalty,
            'slew_degradation': slew_degradation,
            'is_critical': is_critical
        }

        self.net_si_analysis[net_name] = result
        return result

    def _find_aggressors(self, net_name: str) -> List[str]:
        """Find aggressor nets for a given victim net."""
        # In real implementation, this would use physical design data
        # For now, generate synthetic aggressors based on net name

        aggressors = []
        base_name = net_name.split('[')[0] if '[' in net_name else net_name

        # Generate nearby nets
        for i in range(self.aggressor_count):
            agg_name = f"{base_name}_agg{i + 1}"
            aggressors.append(agg_name)

        return aggressors

    def _get_net_capacitance(self, net_name: str) -> float:
        """Get total capacitance of a net."""
        # This would come from extracted parasitics
        # For now, return a reasonable default
        return 50e-15  # 50fF

    def _calculate_coupling_capacitance(self, net_name: str,
                                        aggressors: List[str]) -> float:
        """Calculate coupling capacitance between victim and aggressors."""
        total_coupling = 0.0

        # Get victim capacitance
        victim_cap = self._get_net_capacitance(net_name)

        # Determine metal layer from net name (simplified)
        if 'clk' in net_name.lower():
            layer = 'M4'
        elif 'data' in net_name.lower():
            layer = 'M3'
        else:
            layer = 'M2'

        coupling_ratio = self.coupling_ratios.get(layer, 0.1)

        # Calculate coupling for each aggressor
        for aggressor in aggressors:
            # Assume each aggressor contributes based on proximity
            proximity = 0.5 + 0.5 * hash(aggressor) / float('inf')
            coupling = victim_cap * coupling_ratio * proximity
            total_coupling += coupling

        return total_coupling

    def _calculate_noise_voltage(self, net_name: str, coupling_cap: float) -> float:
        """Calculate induced noise voltage."""
        # Simplified noise model: V_noise = (C_coupling / C_total) * V_swing
        total_cap = self._get_net_capacitance(net_name) + coupling_cap
        coupling_ratio = coupling_cap / total_cap if total_cap > 0 else 0

        # Assume 1V swing
        noise_voltage = coupling_ratio * 1.0

        return noise_voltage

    def _calculate_delay_penalty(self, net_name: str, coupling_cap: float,
                                 num_aggressors: int) -> float:
        """Calculate delay penalty due to crosstalk."""
        # Delay penalty model: penalty = k * C_coupling / C_total * num_aggressors
        total_cap = self._get_net_capacitance(net_name) + coupling_cap
        coupling_ratio = coupling_cap / total_cap if total_cap > 0 else 0

        # Base delay penalty (simplified)
        base_penalty = 10e-12  # 10ps base

        # Scale by coupling ratio and number of aggressors
        penalty = base_penalty * coupling_ratio * num_aggressors

        # Saturation effect
        penalty = min(penalty, 100e-12)  # Max 100ps penalty

        return penalty

    def _calculate_slew_degradation(self, net_name: str, coupling_cap: float) -> float:
        """Calculate slew degradation due to crosstalk."""
        # Slew degradation factor
        total_cap = self._get_net_capacitance(net_name) + coupling_cap
        coupling_ratio = coupling_cap / total_cap if total_cap > 0 else 0

        # Degradation factor (1.0 = no degradation)
        degradation = 1.0 + coupling_ratio * 2.0

        return degradation

    def analyze_path(self, path: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze SI effects on a timing path.

        Args:
            path: Path dictionary

        Returns:
            Path with SI analysis added
        """
        total_si_penalty = 0.0
        affected_stages = []

        stages = path.get('stages', [])

        for i, stage in enumerate(stages):
            # Check if this stage has a net that might be affected
            net_name = stage.get('net', f"net_{i}")

            # Analyze the net
            si_result = self.analyze_net(net_name)

            if si_result['is_critical']:
                # Apply delay penalty to this stage
                penalty = si_result['delay_penalty']
                stage['si_penalty'] = penalty
                stage['si_affected'] = True
                stage['si_details'] = {
                    'aggressors': si_result['aggressor_count'],
                    'noise': si_result['noise_voltage'],
                    'coupling': si_result['coupling_ratio']
                }

                total_si_penalty += penalty
                affected_stages.append(i)

                # Apply slew degradation
                if 'slew' in stage:
                    stage['slew'] *= si_result['slew_degradation']

        # Update path with SI information
        path['si_penalty'] = total_si_penalty
        path['si_affected_stages'] = affected_stages
        path['si_affected'] = len(affected_stages) > 0

        return path

    def get_path_si_penalty(self, path: Dict[str, Any]) -> float:
        """
        Get SI penalty for a path.

        Args:
            path: Path dictionary

        Returns:
            Total SI penalty in seconds
        """
        path_id = f"{path.get('from', '')}_{path.get('to', '')}"

        if path_id in self.path_si_penalties:
            return self.path_si_penalties[path_id]

        # Analyze path and cache result
        analyzed_path = self.analyze_path(path)
        penalty = analyzed_path.get('si_penalty', 0)

        self.path_si_penalties[path_id] = penalty
        return penalty

    def get_critical_nets(self, threshold: float = None) -> List[Dict[str, Any]]:
        """
        Get nets that are critical for SI.

        Args:
            threshold: Criticality threshold

        Returns:
            List of critical nets with analysis
        """
        if threshold is None:
            threshold = self.coupling_threshold

        critical = []

        for net_name, analysis in self.net_si_analysis.items():
            if analysis.get('is_critical', False):
                if analysis.get('coupling_ratio', 0) >= threshold:
                    critical.append(analysis)

        # Sort by coupling ratio
        critical.sort(key=lambda x: x.get('coupling_ratio', 0), reverse=True)

        return critical

    def get_si_summary(self) -> Dict[str, Any]:
        """Get summary of SI analysis."""
        if not self.net_si_analysis:
            return {}

        critical_nets = self.get_critical_nets()

        # Calculate statistics
        coupling_ratios = [a.get('coupling_ratio', 0) for a in self.net_si_analysis.values()]
        noise_levels = [a.get('noise_voltage', 0) for a in self.net_si_analysis.values()]
        penalties = [a.get('delay_penalty', 0) for a in self.net_si_analysis.values()]

        summary = {
            'nets_analyzed': len(self.net_si_analysis),
            'critical_nets': len(critical_nets),
            'avg_coupling_ratio': sum(coupling_ratios) / len(coupling_ratios) if coupling_ratios else 0,
            'max_coupling_ratio': max(coupling_ratios) if coupling_ratios else 0,
            'avg_noise': sum(noise_levels) / len(noise_levels) if noise_levels else 0,
            'max_noise': max(noise_levels) if noise_levels else 0,
            'avg_penalty': sum(penalties) / len(penalties) if penalties else 0,
            'max_penalty': max(penalties) if penalties else 0,
            'total_si_impact': sum(penalties),
            'coupling_threshold': self.coupling_threshold,
            'noise_margin': self.noise_margin,
            'critical_nets_list': critical_nets[:10]  # Top 10
        }

        return summary

    def print_summary(self):
        """Print SI analysis summary."""
        summary = self.get_si_summary()

        if not summary:
            logger.info("No SI analysis results available")
            return

        logger.info("=" * 60)
        logger.info("Signal Integrity Analysis Summary")
        logger.info("=" * 60)
        logger.info(f"Nets analyzed: {summary['nets_analyzed']}")
        logger.info(f"Critical nets: {summary['critical_nets']}")
        logger.info(f"Average coupling ratio: {summary['avg_coupling_ratio'] * 100:.1f}%")
        logger.info(f"Maximum coupling ratio: {summary['max_coupling_ratio'] * 100:.1f}%")
        logger.info(f"Average noise voltage: {summary['avg_noise'] * 100:.1f}% of Vdd")
        logger.info(f"Maximum noise voltage: {summary['max_noise'] * 100:.1f}% of Vdd")
        logger.info(f"Average delay penalty: {TimeUtils.format_time(summary['avg_penalty'])}")
        logger.info(f"Maximum delay penalty: {TimeUtils.format_time(summary['max_penalty'])}")
        logger.info(f"Total SI impact: {TimeUtils.format_time(summary['total_si_impact'])}")

        if summary['critical_nets_list']:
            logger.info("\nTop Critical Nets:")
            for net in summary['critical_nets_list'][:5]:
                logger.info(f"  {net['net_name']}: coupling={net['coupling_ratio'] * 100:.1f}%, "
                            f"penalty={TimeUtils.format_time(net['delay_penalty'])}")

        logger.info("=" * 60)

    def reset(self):
        """Reset SI analyzer state."""
        self.net_si_analysis.clear()
        self.path_si_penalties.clear()
        logger.debug("SI analyzer reset")