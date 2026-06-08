"""
Enhanced Delay Calculator for STA Engine.
Properly calculates delays with multiple models and never returns zero.
"""

from typing import Dict, List, Optional, Tuple, Any, Union
from functools import lru_cache
import math

from Src.liberty_parser.cell_library import CellLibrary, Cell, TimingArc
from Src.timing_graph.graph_nodes import TimingNode, TimingEdge
from Src.utils.logger import get_logger
from Src.utils.time_utils import TimeUtils

logger = get_logger(__name__)


class DelayCalculator:
    """
    Enhanced delay calculator with multiple models and proper fallbacks.
    Never returns zero delay - always returns at least 1fs.
    """

    # Minimum delay (1fs) - never return zero
    MIN_DELAY = 1e-15
    MIN_SLEW = 1e-15

    # Default delays based on cell type (in seconds)
    DEFAULT_BASE_DELAYS = {
        'INV': {'rise': 15e-12, 'fall': 12e-12},
        'BUF': {'rise': 20e-12, 'fall': 18e-12},
        'CLKBUF': {'rise': 25e-12, 'fall': 22e-12},
        'NAND': {'rise': 25e-12, 'fall': 22e-12},
        'NOR': {'rise': 25e-12, 'fall': 22e-12},
        'AND': {'rise': 30e-12, 'fall': 27e-12},
        'OR': {'rise': 30e-12, 'fall': 27e-12},
        'XOR': {'rise': 45e-12, 'fall': 42e-12},
        'XNOR': {'rise': 45e-12, 'fall': 42e-12},
        'MUX': {'rise': 35e-12, 'fall': 32e-12},
        'DFF': {'rise': 60e-12, 'fall': 55e-12},
        'DFFX1': {'rise': 60e-12, 'fall': 55e-12},
        'DFFX2': {'rise': 70e-12, 'fall': 65e-12},
        'LATCH': {'rise': 50e-12, 'fall': 45e-12}
    }

    # Default output slews
    DEFAULT_BASE_SLEWS = {
        'INV': {'rise': 25e-12, 'fall': 20e-12},
        'BUF': {'rise': 30e-12, 'fall': 25e-12},
        'CLKBUF': {'rise': 35e-12, 'fall': 30e-12},
        'NAND': {'rise': 35e-12, 'fall': 30e-12},
        'NOR': {'rise': 35e-12, 'fall': 30e-12},
        'AND': {'rise': 40e-12, 'fall': 35e-12},
        'OR': {'rise': 40e-12, 'fall': 35e-12},
        'XOR': {'rise': 50e-12, 'fall': 45e-12},
        'DFF': {'rise': 60e-12, 'fall': 55e-12},
        'LATCH': {'rise': 55e-12, 'fall': 50e-12}
    }

    # Technology parameters
    DEFAULT_TECH_NODE = 28e-9  # 28nm
    DEFAULT_WIRE_RESISTANCE_PER_UM = 0.1  # Ohms/um
    DEFAULT_WIRE_CAP_PER_UM = 0.2e-15  # F/um
    DEFAULT_VIA_DELAY = 2e-15  # 2fs per via

    def __init__(self, cell_library: CellLibrary):
        self.cell_library = cell_library

        # Technology parameters (can be overridden)
        self.tech_node = self.DEFAULT_TECH_NODE
        self.wire_resistance_per_um = self.DEFAULT_WIRE_RESISTANCE_PER_UM
        self.wire_cap_per_um = self.DEFAULT_WIRE_CAP_PER_UM
        self.via_delay = self.DEFAULT_VIA_DELAY

        # Delay model selection
        self.use_liberty_model = True
        self.use_rc_model = True
        self.fallback_to_defaults = True

        # Caches for performance
        self._delay_cache: Dict[str, float] = {}
        self._slew_cache: Dict[str, float] = {}
        self._base_delay_cache: Dict[str, float] = {}
        self._base_slew_cache: Dict[str, float] = {}
        self._fanout_cache: Dict[str, int] = {}

        # Statistics
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'liberty_arcs_used': 0,
            'simple_model_used': 0,
            'defaults_used': 0,
            'warnings_issued': 0
        }

        logger.info("Enhanced delay calculator initialized")

    def _get_cache_key(self, prefix: str, edge_id: int, transition: str,
                      input_slew: float, output_load: float) -> str:
        """Generate cache key for delay/slew calculations."""
        return f"{prefix}_{edge_id}_{transition}_{input_slew:.2e}_{output_load:.2e}"

    def calculate_cell_delay(self, edge: TimingEdge, input_slew: float,
                            output_load: float, transition: str = 'rise') -> float:
        """
        Calculate cell delay for a timing arc.
        Never returns zero - always at least MIN_DELAY.

        Args:
            edge: Timing edge
            input_slew: Input transition time (s)
            output_load: Output load capacitance (F)
            transition: 'rise' or 'fall'

        Returns:
            Cell delay in seconds (>= MIN_DELAY)
        """
        # Validate inputs
        if input_slew <= 0:
            input_slew = self.MIN_SLEW
            self._log_warning(f"Invalid input slew {input_slew}, using MIN_SLEW")

        if output_load <= 0:
            output_load = 5e-15  # 5fF default
            self._log_warning(f"Invalid output load {output_load}, using 5fF")

        # Create cache key
        cache_key = self._get_cache_key('delay', id(edge), transition, input_slew, output_load)

        # Check cache
        if cache_key in self._delay_cache:
            self.stats['cache_hits'] += 1
            return self._delay_cache[cache_key]

        self.stats['cache_misses'] += 1

        delay = None

        # Try Liberty model first
        if self.use_liberty_model:
            arc = edge.attributes.get('arc')
            if arc and isinstance(arc, TimingArc):
                try:
                    # Check if arc has coefficients for this transition
                    if transition == 'rise' and arc.rise_delay_coeff:
                        delay = self._calculate_from_coeff(
                            arc.rise_delay_coeff, input_slew, output_load, transition
                        )
                        self.stats['liberty_arcs_used'] += 1
                    elif transition == 'fall' and arc.fall_delay_coeff:
                        delay = self._calculate_from_coeff(
                            arc.fall_delay_coeff, input_slew, output_load, transition
                        )
                        self.stats['liberty_arcs_used'] += 1
                except Exception as e:
                    self._log_warning(f"Error using Liberty delay model: {e}")

        # If Liberty model failed or not available, use simple model
        if delay is None or delay <= self.MIN_DELAY:
            delay = self._calculate_simple_cell_delay(input_slew, output_load, transition, edge)
            self.stats['simple_model_used'] += 1

        # Apply modifiers
        delay = self._apply_delay_modifiers(delay, edge, transition)

        # Ensure minimum delay
        delay = max(delay, self.MIN_DELAY)

        # Cache the calculated delay
        self._delay_cache[cache_key] = delay
        edge.attributes['calculated_delay'] = delay
        edge.attributes['input_slew'] = input_slew
        edge.attributes['output_load'] = output_load

        return delay

    def _calculate_from_coeff(self, coeff: Dict[str, float], input_slew: float,
                             output_load: float, transition: str) -> float:
        """Calculate delay from Liberty coefficients."""
        if not coeff:
            return 0.0

        # Convert load to fF for numerical stability
        load_fF = output_load * 1e15

        # Simple linear model: delay = a0 + a1*load + a2*slew + a3*load*slew
        delay = (coeff.get('a0', 0) * 1e-12 +  # Convert to seconds
                 coeff.get('a1', 0) * load_fF * 1e-12 +
                 coeff.get('a2', 0) * input_slew +
                 coeff.get('a3', 0) * load_fF * input_slew * 1e12 * 1e-12)

        # If we got exactly zero, use a small default
        if delay <= 0:
            delay = 10e-12  # 10ps default

        return delay

    def _calculate_simple_cell_delay(self, input_slew: float, output_load: float,
                                     transition: str, edge: TimingEdge) -> float:
        """Calculate cell delay using enhanced linear model."""
        # Get base delay for this cell type
        base_delay = self._get_base_delay(edge.cell_type, transition)

        # Input slew contribution (10-30% of input slew)
        slew_contrib = input_slew * 0.2

        # Load contribution (convert to fF)
        load_fF = output_load * 1e15
        load_contrib = load_fF * 2e-12  # 2ps per fF

        # Fanout contribution
        fanout = edge.attributes.get('fanout', 1)
        fanout_contrib = (fanout - 1) * 3e-12  # 3ps per additional fanout

        # Transition factor (fall typically faster)
        trans_factor = 1.0 if transition == 'rise' else 0.95

        # Calculate total delay
        delay = (base_delay + slew_contrib + load_contrib + fanout_contrib) * trans_factor

        # Add routing factor if available
        if 'routing_factor' in edge.attributes:
            delay *= edge.attributes['routing_factor']

        return delay

    @lru_cache(maxsize=256)
    def _get_base_delay(self, cell_type: str, transition: str) -> float:
        """Get base delay for a cell type with caching."""
        if not cell_type:
            return 20e-12  # Default 20ps

        cell_upper = cell_type.upper()

        # Check if we have exact match
        if cell_upper in self.DEFAULT_BASE_DELAYS:
            gate_delays = self.DEFAULT_BASE_DELAYS[cell_upper]
            delay = gate_delays.get(transition, gate_delays['rise'])
            self.stats['defaults_used'] += 1
            return delay

        # Try partial matches
        for gate_type in self.DEFAULT_BASE_DELAYS:
            if gate_type in cell_upper:
                gate_delays = self.DEFAULT_BASE_DELAYS[gate_type]
                delay = gate_delays.get(transition, gate_delays['rise'])
                self.stats['defaults_used'] += 1
                return delay

        # Absolute default
        self.stats['defaults_used'] += 1
        return 20e-12 if transition == 'rise' else 18e-12

    def _apply_delay_modifiers(self, delay: float, edge: TimingEdge, transition: str) -> float:
        """Apply various modifiers to delay."""
        # OCV derating
        if 'ocv_derate' in edge.attributes:
            delay *= edge.attributes['ocv_derate']

        # SI penalty
        if 'si_penalty' in edge.attributes:
            delay += edge.attributes['si_penalty']

        # Temperature effect
        if 'temp_factor' in edge.attributes:
            delay *= edge.attributes['temp_factor']

        # Voltage effect
        if 'voltage_factor' in edge.attributes:
            delay *= edge.attributes['voltage_factor']

        # Process variation
        if 'process_factor' in edge.attributes:
            delay *= edge.attributes['process_factor']

        return delay

    def calculate_output_slew(self, edge: TimingEdge, input_slew: float,
                             output_load: float, transition: str = 'rise') -> float:
        """Calculate output slew with validation."""
        # Validate inputs
        if input_slew <= 0:
            input_slew = self.MIN_SLEW

        if output_load <= 0:
            output_load = 5e-15

        # Create cache key
        cache_key = self._get_cache_key('slew', id(edge), transition, input_slew, output_load)

        # Check cache
        if cache_key in self._slew_cache:
            return self._slew_cache[cache_key]

        slew = None

        # Try Liberty model
        if self.use_liberty_model:
            arc = edge.attributes.get('arc')
            if arc:
                if transition == 'rise' and hasattr(arc, 'rise_slew_coeff') and arc.rise_slew_coeff:
                    slew = self._calculate_slew_from_coeff(
                        arc.rise_slew_coeff, input_slew, output_load
                    )
                elif transition == 'fall' and hasattr(arc, 'fall_slew_coeff') and arc.fall_slew_coeff:
                    slew = self._calculate_slew_from_coeff(
                        arc.fall_slew_coeff, input_slew, output_load
                    )

        # Fallback to simple model
        if slew is None or slew <= self.MIN_SLEW:
            slew = self._calculate_simple_output_slew(input_slew, output_load, transition, edge)

        # Ensure minimum
        slew = max(slew, self.MIN_SLEW)

        # Cache
        self._slew_cache[cache_key] = slew
        edge.attributes['output_slew'] = slew

        return slew

    def _calculate_slew_from_coeff(self, coeff: Dict[str, float],
                                   input_slew: float, output_load: float) -> float:
        """Calculate slew from Liberty coefficients."""
        if not coeff:
            return 30e-12

        load_fF = output_load * 1e15

        slew = (coeff.get('b0', 30e-12) +
                coeff.get('b1', 1.5e-3) * load_fF * 1e-12 +
                coeff.get('b2', 0.4) * input_slew +
                coeff.get('b3', 0.05) * load_fF * input_slew * 1e12 * 1e-12)

        return max(slew, self.MIN_SLEW)

    def _calculate_simple_output_slew(self, input_slew: float, output_load: float,
                                      transition: str, edge: TimingEdge) -> float:
        """Calculate output slew using simple model."""
        base_slew = self._get_base_slew(edge.cell_type, transition)

        load_fF = output_load * 1e15
        load_effect = load_fF * 4e-12
        slew_effect = input_slew * 0.6
        fanout_effect = edge.attributes.get('fanout', 1) * 3e-12

        slew = base_slew + load_effect + slew_effect + fanout_effect

        if transition == 'fall':
            slew *= 0.95

        return max(slew, self.MIN_SLEW)

    @lru_cache(maxsize=256)
    def _get_base_slew(self, cell_type: str, transition: str) -> float:
        """Get base output slew for a cell type."""
        if not cell_type:
            return 30e-12

        cell_upper = cell_type.upper()

        for gate_type in self.DEFAULT_BASE_SLEWS:
            if gate_type in cell_upper:
                gate_slews = self.DEFAULT_BASE_SLEWS[gate_type]
                return gate_slews.get(transition, gate_slews['rise'])

        return 30e-12 if transition == 'rise' else 25e-12

    def calculate_net_delay(self, from_node: TimingNode, to_node: TimingNode,
                           net_name: str, transition: str = 'rise') -> float:
        """Calculate net delay with RC model."""
        # Get net capacitance
        net_cap = from_node.attributes.get('load', 5e-15)

        # Estimate wire length based on fanout
        fanout = self._estimate_fanout(net_name)
        wire_length = fanout * 10e-6  # 10um per fanout

        # Wire RC
        wire_resistance = wire_length * self.wire_resistance_per_um * 1e6
        wire_capacitance = wire_length * self.wire_cap_per_um

        # Total capacitance
        total_cap = net_cap + wire_capacitance

        # Elmore delay for RC network
        net_delay = 0.5 * wire_resistance * total_cap

        # Add via delays
        via_count = max(1, int(math.log2(fanout + 1)))
        net_delay += via_count * self.via_delay

        # Transition effect
        if transition == 'fall':
            net_delay *= 0.98

        return max(net_delay, self.MIN_DELAY)

    @lru_cache(maxsize=512)
    def _estimate_fanout(self, net_name: str) -> int:
        """Estimate fanout of a net with caching."""
        if not net_name:
            return 1

        net_lower = net_name.lower()

        if 'clock' in net_lower or 'clk' in net_lower:
            return 20
        elif 'reset' in net_lower or 'rst' in net_lower:
            return 15
        elif 'data' in net_lower:
            return 8
        elif '[' in net_name:  # Bus
            return 6
        else:
            return 3

    def calculate_clock_uncertainty(self, from_clock: Optional[str],
                                    to_clock: Optional[str],
                                    analysis_type: str = 'setup') -> float:
        """Calculate clock uncertainty."""
        if not from_clock or not to_clock:
            return 50e-12 if analysis_type == 'setup' else 20e-12

        if from_clock == to_clock:
            # Same clock
            return 50e-12 if analysis_type == 'setup' else 20e-12
        else:
            # Different clocks
            return 120e-12 if analysis_type == 'setup' else 50e-12

    def calculate_path_delay(self, edges: List[TimingEdge],
                            transitions: List[str],
                            input_slew: float,
                            output_load: float) -> Tuple[float, List[float]]:
        """Calculate total delay for a path."""
        total_delay = 0.0
        stage_delays = []
        current_slew = input_slew

        for i, edge in enumerate(edges):
            # Determine load for this stage
            if i == len(edges) - 1:
                load = output_load
            else:
                load = edges[i + 1].to_node.capacitance or 5e-15

            # Calculate cell delay
            delay = self.calculate_cell_delay(edge, current_slew, load, transitions[i])
            current_slew = self.calculate_output_slew(edge, current_slew, load, transitions[i])

            # Add net delay if not the last stage
            if i < len(edges) - 1:
                net_delay = self.calculate_net_delay(
                    edge.to_node, edges[i + 1].from_node,
                    f"net_{i}", transitions[i]
                )
                delay += net_delay

            total_delay += delay
            stage_delays.append(delay)

        return total_delay, stage_delays

    def _log_warning(self, message: str):
        """Log warning with rate limiting."""
        if self.stats['warnings_issued'] < 100:
            logger.warning(message)
        elif self.stats['warnings_issued'] == 100:
            logger.warning("Too many warnings - suppressing further warnings")

        self.stats['warnings_issued'] += 1

    def clear_cache(self):
        """Clear all caches."""
        self._delay_cache.clear()
        self._slew_cache.clear()
        self._base_delay_cache.clear()
        self._base_slew_cache.clear()
        self._fanout_cache.clear()
        logger.debug("Delay calculator caches cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache and usage statistics."""
        total = self.stats['cache_hits'] + self.stats['cache_misses']
        hit_rate = (self.stats['cache_hits'] / total * 100) if total > 0 else 0

        return {
            'cache_hits': self.stats['cache_hits'],
            'cache_misses': self.stats['cache_misses'],
            'total_cache_requests': total,
            'cache_hit_rate': f"{hit_rate:.1f}%",
            'liberty_arcs_used': self.stats['liberty_arcs_used'],
            'simple_model_used': self.stats['simple_model_used'],
            'defaults_used': self.stats['defaults_used'],
            'warnings_issued': self.stats['warnings_issued']
        }

    def print_summary(self):
        """Print delay calculator summary."""
        stats = self.get_stats()

        logger.info("=" * 60)
        logger.info("Delay Calculator Summary")
        logger.info("=" * 60)
        logger.info(f"Cache hits: {stats['cache_hits']}")
        logger.info(f"Cache misses: {stats['cache_misses']}")
        logger.info(f"Cache hit rate: {stats['cache_hit_rate']}")
        logger.info(f"Liberty arcs used: {stats['liberty_arcs_used']}")
        logger.info(f"Simple model used: {stats['simple_model_used']}")
        logger.info(f"Defaults used: {stats['defaults_used']}")
        logger.info(f"Warnings issued: {stats['warnings_issued']}")
        logger.info("=" * 60)