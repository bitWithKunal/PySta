"""
Fanout noise model for SI engine.
Models noise due to high fanout nets and coupling.
"""

from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict
import math

from Src.utils.logger import get_logger
from Src.utils.time_utils import TimeUtils

logger = get_logger(__name__)


class FanoutNoiseModel:
    """Models noise effects in high fanout nets."""

    def __init__(self):
        # Noise parameters
        self.fanout_threshold = 10  # Fanout threshold for noise consideration
        self.coupling_factor = 0.1  # Coupling capacitance factor
        self.noise_margin = 0.2  # 20% noise margin
        self.aggressor_activity = 0.5  # Default aggressor switching activity

        # Technology parameters
        self.vdd = 1.0  # Supply voltage in Volts
        self.vth = 0.3  # Threshold voltage in Volts

        # Wire parameters
        self.wire_resistance_per_um = 0.1  # Ohms per micron
        self.wire_capacitance_per_um = 0.2e-15  # Farads per micron
        self.coupling_capacitance_per_um = 0.1e-15  # Farads per micron

        # Buffer insertion parameters
        self.max_fanout_without_buffer = 8
        self.buffer_delay = 20e-12  # 20ps buffer delay

        # Noise analysis results
        self.noise_analysis: Dict[str, Dict[str, Any]] = {}

        logger.info("Fanout noise model initialized")

    def analyze_fanout_noise(self, net_name: str, fanout: int,
                             wire_length: float = None) -> Dict[str, Any]:
        """
        Analyze noise in a fanout net.

        Args:
            net_name: Name of the net
            fanout: Number of loads
            wire_length: Estimated wire length in meters

        Returns:
            Dictionary with noise analysis results
        """
        # Estimate wire length if not provided
        if wire_length is None:
            wire_length = self._estimate_wire_length(fanout)

        # Calculate wire parameters
        wire_resistance = wire_length * self.wire_resistance_per_um * 1e6
        wire_capacitance = wire_length * self.wire_capacitance_per_um
        coupling_capacitance = wire_length * self.coupling_capacitance_per_um * fanout

        # Calculate noise components
        dc_noise = self._calculate_dc_noise(wire_resistance, fanout)
        ac_noise = self._calculate_ac_noise(coupling_capacitance, fanout)
        switching_noise = self._calculate_switching_noise(fanout)

        total_noise = dc_noise + ac_noise + switching_noise

        # Check if noise exceeds margin
        noise_exceeds = total_noise > self.noise_margin * self.vdd

        # Calculate required buffering
        buffering_needed = self._calculate_buffering_needed(fanout, total_noise)

        # Calculate delay impact
        delay_impact = self._calculate_delay_impact(wire_resistance, wire_capacitance, fanout)

        result = {
            'net_name': net_name,
            'fanout': fanout,
            'wire_length': wire_length,
            'wire_resistance': wire_resistance,
            'wire_capacitance': wire_capacitance,
            'coupling_capacitance': coupling_capacitance,
            'noise_components': {
                'dc_noise': dc_noise,
                'ac_noise': ac_noise,
                'switching_noise': switching_noise,
                'total_noise': total_noise
            },
            'noise_voltage': total_noise,
            'noise_margin': self.noise_margin * self.vdd,
            'noise_exceeds_margin': noise_exceeds,
            'buffering_needed': buffering_needed,
            'buffers_required': buffering_needed[0] if buffering_needed else 0,
            'delay_impact': delay_impact,
            'is_critical': noise_exceeds or fanout > self.max_fanout_without_buffer * 2
        }

        self.noise_analysis[net_name] = result
        return result

    def _estimate_wire_length(self, fanout: int) -> float:
        """
        Estimate wire length based on fanout.

        Args:
            fanout: Number of loads

        Returns:
            Estimated wire length in meters
        """
        # Simple model: length proportional to sqrt(fanout)
        base_length = 100e-6  # 100um base
        return base_length * math.sqrt(fanout)

    def _calculate_dc_noise(self, wire_resistance: float, fanout: int) -> float:
        """
        Calculate DC noise (IR drop).

        Args:
            wire_resistance: Wire resistance in Ohms
            fanout: Number of loads

        Returns:
            DC noise voltage in Volts
        """
        # Assume each load draws 1uA leakage current
        leakage_current = fanout * 1e-6
        dc_drop = wire_resistance * leakage_current
        return min(dc_drop, 0.1 * self.vdd)  # Cap at 10% of VDD

    def _calculate_ac_noise(self, coupling_capacitance: float, fanout: int) -> float:
        """
        Calculate AC noise (coupling).

        Args:
            coupling_capacitance: Coupling capacitance in Farads
            fanout: Number of loads

        Returns:
            AC noise voltage in Volts
        """
        # Total load capacitance (simplified)
        load_cap = fanout * 10e-15  # 10fF per load

        if load_cap == 0:
            return 0

        # Coupling noise: V_noise = (C_coup / (C_coup + C_load)) * V_swing
        coupling_ratio = coupling_capacitance / (coupling_capacitance + load_cap)
        ac_noise = coupling_ratio * self.vdd * self.aggressor_activity

        return ac_noise

    def _calculate_switching_noise(self, fanout: int) -> float:
        """
        Calculate switching noise (simultaneous switching).

        Args:
            fanout: Number of loads

        Returns:
            Switching noise voltage in Volts
        """
        # Simultaneous switching noise increases with fanout
        if fanout <= 1:
            return 0

        # Simple model: noise proportional to sqrt(fanout)
        switching_factor = 0.01 * math.sqrt(fanout - 1)
        return switching_factor * self.vdd

    def _calculate_buffering_needed(self, fanout: int, noise: float) -> Tuple[int, List[int]]:
        """
        Calculate buffering needed to mitigate noise.

        Args:
            fanout: Number of loads
            noise: Total noise voltage

        Returns:
            Tuple of (number_of_buffers, buffer_positions)
        """
        if fanout <= self.max_fanout_without_buffer and noise <= self.noise_margin * self.vdd:
            return (0, [])

        # Determine number of buffers needed
        if fanout > self.max_fanout_without_buffer * 4:
            num_buffers = 3
        elif fanout > self.max_fanout_without_buffer * 2:
            num_buffers = 2
        else:
            num_buffers = 1

        # Calculate buffer positions (simplified - evenly distributed)
        positions = [fanout // (num_buffers + 1) * (i + 1) for i in range(num_buffers)]

        return (num_buffers, positions)

    def _calculate_delay_impact(self, wire_resistance: float,
                                wire_capacitance: float, fanout: int) -> float:
        """
        Calculate delay impact due to fanout.

        Args:
            wire_resistance: Wire resistance in Ohms
            wire_capacitance: Wire capacitance in Farads
            fanout: Number of loads

        Returns:
            Additional delay in seconds
        """
        # Load capacitance
        load_cap = fanout * 10e-15  # 10fF per load
        total_cap = wire_capacitance + load_cap

        # Elmore delay
        delay = 0.5 * wire_resistance * total_cap

        # Additional delay due to fanout (RC tree effect)
        if fanout > 1:
            # Distributed RC effect
            delay *= (1 + 0.1 * math.log2(fanout))

        return delay

    def get_critical_fanout_nets(self, threshold: float = None) -> List[Dict[str, Any]]:
        """
        Get nets critical due to fanout noise.

        Args:
            threshold: Noise threshold for criticality

        Returns:
            List of critical nets with analysis
        """
        if threshold is None:
            threshold = self.noise_margin * self.vdd

        critical = []

        for net_name, analysis in self.noise_analysis.items():
            if analysis.get('noise_exceeds_margin', False) or \
                    analysis.get('fanout', 0) > self.max_fanout_without_buffer * 2:
                critical.append(analysis)

        # Sort by noise voltage
        critical.sort(key=lambda x: x.get('noise_voltage', 0), reverse=True)

        return critical

    def suggest_buffering(self, net_name: str) -> Dict[str, Any]:
        """
        Suggest buffering strategy for a net.

        Args:
            net_name: Name of the net

        Returns:
            Dictionary with buffering suggestions
        """
        if net_name not in self.noise_analysis:
            return {'error': 'Net not analyzed'}

        analysis = self.noise_analysis[net_name]
        fanout = analysis['fanout']
        num_buffers, positions = analysis['buffering_needed']

        if num_buffers == 0:
            return {
                'net_name': net_name,
                'buffering_needed': False,
                'message': 'No buffering needed'
            }

        # Calculate delay after buffering
        original_delay = analysis['delay_impact']

        # With buffers, delay is reduced but buffer delay added
        buffered_delay = (original_delay / (num_buffers + 1)) + num_buffers * self.buffer_delay

        suggestion = {
            'net_name': net_name,
            'fanout': fanout,
            'buffering_needed': True,
            'num_buffers': num_buffers,
            'buffer_positions': positions,
            'original_delay': original_delay,
            'buffered_delay': buffered_delay,
            'delay_improvement': original_delay - buffered_delay,
            'buffer_cells': ['BUFX2'] * num_buffers,  # Suggested buffer types
            'estimated_area_overhead': num_buffers * 10,  # 10 units per buffer
            'estimated_power_overhead': num_buffers * 5e-6  # 5uW per buffer
        }

        return suggestion

    def calculate_max_fanout(self, target_delay: float) -> int:
        """
        Calculate maximum fanout for a given delay target.

        Args:
            target_delay: Maximum allowed delay in seconds

        Returns:
            Maximum fanout count
        """
        # Binary search for max fanout
        low, high = 1, 1000

        while low < high:
            mid = (low + high + 1) // 2
            delay = self._calculate_delay_impact(0, 0, mid)  # Simplified

            if delay <= target_delay:
                low = mid
            else:
                high = mid - 1

        return low

    def get_noise_summary(self) -> Dict[str, Any]:
        """Get summary of fanout noise analysis."""
        if not self.noise_analysis:
            return {}

        critical_nets = self.get_critical_fanout_nets()

        # Calculate statistics
        fanouts = [a['fanout'] for a in self.noise_analysis.values()]
        noises = [a['noise_voltage'] for a in self.noise_analysis.values()]
        delays = [a['delay_impact'] for a in self.noise_analysis.values()]

        summary = {
            'nets_analyzed': len(self.noise_analysis),
            'critical_nets': len(critical_nets),
            'avg_fanout': sum(fanouts) / len(fanouts) if fanouts else 0,
            'max_fanout': max(fanouts) if fanouts else 0,
            'avg_noise': sum(noises) / len(noises) if noises else 0,
            'max_noise': max(noises) if noises else 0,
            'avg_delay_impact': sum(delays) / len(delays) if delays else 0,
            'max_delay_impact': max(delays) if delays else 0,
            'fanout_threshold': self.fanout_threshold,
            'noise_margin': self.noise_margin,
            'critical_nets_list': critical_nets[:10]  # Top 10
        }

        return summary

    def print_summary(self):
        """Print fanout noise analysis summary."""
        summary = self.get_noise_summary()

        if not summary:
            logger.info("No fanout noise analysis results available")
            return

        logger.info("=" * 60)
        logger.info("Fanout Noise Analysis Summary")
        logger.info("=" * 60)
        logger.info(f"Nets analyzed: {summary['nets_analyzed']}")
        logger.info(f"Critical nets: {summary['critical_nets']}")
        logger.info(f"Average fanout: {summary['avg_fanout']:.1f}")
        logger.info(f"Maximum fanout: {summary['max_fanout']}")
        logger.info(f"Average noise voltage: {summary['avg_noise'] * 1000:.2f}mV")
        logger.info(f"Maximum noise voltage: {summary['max_noise'] * 1000:.2f}mV")
        logger.info(f"Average delay impact: {TimeUtils.format_time(summary['avg_delay_impact'])}")
        logger.info(f"Maximum delay impact: {TimeUtils.format_time(summary['max_delay_impact'])}")

        if summary['critical_nets_list']:
            logger.info("\nTop Critical Nets:")
            for net in summary['critical_nets_list'][:5]:
                logger.info(f"  {net['net_name']}: fanout={net['fanout']}, "
                            f"noise={net['noise_voltage'] * 1000:.1f}mV, "
                            f"buffers={net['buffers_required']}")

        logger.info("=" * 60)

    def reset(self):
        """Reset the fanout noise model."""
        self.noise_analysis.clear()
        logger.debug("Fanout noise model reset")