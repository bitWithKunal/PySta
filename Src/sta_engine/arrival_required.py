"""
Enhanced Arrival and Required Time Calculator for STA Engine.
Properly propagates timing with validation and constraint handling.
"""

from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict
import heapq
from functools import lru_cache

from Src.timing_graph.graph_nodes import TimingNode, TimingEdge, TimingSense
from Src.timing_graph.graph_edges import EdgeManager
from Src.sdc_parser.clock_constraints import Clock, ClockConstraints
from Src.sdc_parser.timing_exceptions import ExceptionManager
from Src.sta_engine.delay_calculator import DelayCalculator
from Src.utils.logger import get_logger
from Src.utils.time_utils import TimeUtils

logger = get_logger(__name__)


class ArrivalRequiredCalculator:
    """
    Enhanced calculator for arrival and required times with proper validation
    and constraint handling.
    """

    # Minimum timing values (1fs - never zero)
    MIN_DELAY = 1e-15
    MIN_SLEW = 1e-15
    DEFAULT_LOAD = 5e-15  # 5fF default load

    def __init__(self, edge_manager: EdgeManager, delay_calculator: DelayCalculator,
                 clock_constraints: ClockConstraints, exception_manager: ExceptionManager = None):
        self.edge_manager = edge_manager
        self.delay_calculator = delay_calculator
        self.clock_constraints = clock_constraints
        self.exception_manager = exception_manager

        # Analysis modes
        self.analysis_type = 'setup'  # 'setup' or 'hold'

        # Validation flags
        self.validation_enabled = True
        self.strict_mode = False  # If True, raise errors; if False, use defaults

        # Statistics
        self.stats = {
            'nodes_processed': 0,
            'startpoints_processed': 0,
            'endpoints_processed': 0,
            'missing_clocks': 0,
            'missing_constraints': 0,
            'zero_arrivals': 0,
            'infinite_required': 0
        }

        # Caches
        self._clock_cache: Dict[str, Optional[Clock]] = {}
        self._topo_order: Optional[List[TimingNode]] = None
        self._reverse_topo: Optional[List[TimingNode]] = None
        self._input_delay_cache: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._output_delay_cache: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._setup_time_cache: Dict[str, float] = {}
        self._hold_time_cache: Dict[str, float] = {}

        # Node timing cache for quick lookup
        self._node_arrivals: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._node_required: Dict[str, Dict[str, float]] = defaultdict(dict)

    def calculate_arrival_times(self) -> bool:
        """
        Forward propagate arrival times with validation.

        Returns:
            True if calculation successful
        """
        logger.info(f"Calculating arrival times for {self.analysis_type} analysis")

        # Reset stats
        self.stats = {k: 0 for k in self.stats}

        # Get topological order
        if self._topo_order is None:
            self._topo_order = self.edge_manager.get_topological_order()

        if not self._topo_order:
            logger.error("No topological order found - graph may be empty or cyclic")
            return False

        logger.debug(f"Processing {len(self._topo_order)} nodes in topological order")

        # Reset arrival times
        self._reset_arrival_times()

        # Process in topological order
        zero_count = 0
        for node in self._topo_order:
            self._update_node_arrival(node)
            self.stats['nodes_processed'] += 1

            # Track zero arrivals for debugging
            if node.arrival_rise <= self.MIN_DELAY and node.arrival_fall <= self.MIN_DELAY:
                if node.is_startpoint():
                    # Startpoints can have zero arrival (that's fine)
                    pass
                else:
                    zero_count += 1
                    if zero_count < 10:  # Log first 10 only
                        logger.warning(f"Node {node.name} has near-zero arrival times: "
                                     f"rise={node.arrival_rise*1e12:.3f}ps, "
                                     f"fall={node.arrival_fall*1e12:.3f}ps")

        if zero_count > 0:
            logger.warning(f"Found {zero_count} nodes with near-zero arrival times")

        logger.info(f"Arrival time calculation complete. Processed {self.stats['nodes_processed']} nodes, "
                   f"{self.stats['startpoints_processed']} startpoints")

        return True

    def _reset_arrival_times(self):
        """Reset arrival times and slews for all nodes."""
        reset_count = 0
        for node in self.edge_manager.get_all_nodes():
            if node.arrival_rise != 0.0 or node.arrival_fall != 0.0:
                reset_count += 1
            node.arrival_rise = 0.0
            node.arrival_fall = 0.0
            node.slew_rise = 0.0
            node.slew_fall = 0.0
            node.attributes['arrival_valid'] = False

        logger.debug(f"Reset arrival times for {reset_count} nodes")

    def _update_node_arrival(self, node: TimingNode):
        """Update arrival time for a node based on its predecessors."""
        incoming_edges = self.edge_manager.get_incoming_edges(node)

        if not incoming_edges:
            self._handle_startpoint(node)
            return

        rise_arrivals = []
        fall_arrivals = []
        rise_slews = []
        fall_slews = []
        valid_paths = False

        for edge in incoming_edges:
            from_node = edge.from_node

            # Check if from_node has valid arrival times
            has_valid_arrival = False
            for in_trans in ['rise', 'fall']:
                in_arrival = from_node.get_arrival(in_trans)
                if in_arrival > self.MIN_DELAY or from_node.is_startpoint():
                    has_valid_arrival = True
                    break

            if not has_valid_arrival:
                continue

            for in_trans in ['rise', 'fall']:
                in_arrival = from_node.get_arrival(in_trans)
                in_slew = from_node.get_slew(in_trans)

                # Skip if arrival is invalid
                if in_arrival <= self.MIN_DELAY and not from_node.is_startpoint():
                    continue

                # Get output transition based on timing sense
                out_trans = edge.get_propagated_transition(in_trans)

                # Get load capacitance
                load = node.capacitance
                if load <= self.MIN_DELAY:
                    # Try to get from attributes
                    load = node.attributes.get('load', self.DEFAULT_LOAD)
                    if load <= self.MIN_DELAY:
                        load = self.DEFAULT_LOAD

                # Calculate delay and slew
                try:
                    delay = self.delay_calculator.calculate_cell_delay(
                        edge, in_slew, load, out_trans
                    )
                    # Ensure minimum delay
                    delay = max(delay, self.MIN_DELAY)

                    out_slew = self.delay_calculator.calculate_output_slew(
                        edge, in_slew, load, out_trans
                    )
                    out_slew = max(out_slew, self.MIN_DELAY)

                    out_arrival = in_arrival + delay

                    if out_trans == 'rise':
                        rise_arrivals.append(out_arrival)
                        rise_slews.append(out_slew)
                    else:
                        fall_arrivals.append(out_arrival)
                        fall_slews.append(out_slew)

                    valid_paths = True

                except Exception as e:
                    logger.warning(f"Error calculating delay for edge {edge.from_node.name}->{edge.to_node.name}: {e}")

        if not valid_paths:
            # No valid incoming paths, treat as startpoint
            self._handle_startpoint(node)
            return

        # For setup (max), for hold (min)
        if self.analysis_type == 'setup':
            if rise_arrivals:
                node.arrival_rise = max(rise_arrivals)
                node.slew_rise = max(rise_slews) if rise_slews else self.MIN_SLEW
            if fall_arrivals:
                node.arrival_fall = max(fall_arrivals)
                node.slew_fall = max(fall_slews) if fall_slews else self.MIN_SLEW
        else:  # hold
            if rise_arrivals:
                node.arrival_rise = min(rise_arrivals)
                node.slew_rise = min(rise_slews) if rise_slews else self.MIN_SLEW
            if fall_arrivals:
                node.arrival_fall = min(fall_arrivals)
                node.slew_fall = min(fall_slews) if fall_slews else self.MIN_SLEW

        node.attributes['arrival_valid'] = True

        # Cache for quick lookup
        self._node_arrivals[node.name] = {
            'rise': node.arrival_rise,
            'fall': node.arrival_fall
        }

    def _handle_startpoint(self, node: TimingNode):
        """Handle arrival time for startpoints with proper constraints."""
        self.stats['startpoints_processed'] += 1

        if not node.is_startpoint():
            # Not a startpoint but has no inputs - log warning
            logger.warning(f"Node {node.name} has no inputs but is not marked as startpoint")
            node.arrival_rise = self.MIN_DELAY
            node.arrival_fall = self.MIN_DELAY
            node.slew_rise = self.MIN_SLEW
            node.slew_fall = self.MIN_SLEW
            return

        if node.clock_pin and node.clock:
            self._handle_clock_startpoint(node)
        elif node.node_type.value == 'primary_input':
            self._apply_input_delay(node)
        else:
            # Default for other startpoints
            node.arrival_rise = self.MIN_DELAY
            node.arrival_fall = self.MIN_DELAY
            node.slew_rise = self.MIN_SLEW
            node.slew_fall = self.MIN_SLEW

        node.attributes['arrival_valid'] = True

    def _handle_clock_startpoint(self, node: TimingNode):
        """Handle clock pin startpoints with proper clock attributes."""
        clock = self._get_clock(node.clock)

        if clock:
            # Get waveform times
            rise_time, fall_time = clock.get_waveform()

            # Add latency
            latency = clock.latency
            if hasattr(clock, 'latency_source') and clock.latency_source:
                # Source latency is already included in waveform
                pass

            node.arrival_rise = rise_time + latency
            node.arrival_fall = fall_time + latency

            # Get transition times
            node.slew_rise = clock.transition_rise if clock.transition_rise else self.MIN_SLEW * 10
            node.slew_fall = clock.transition_fall if clock.transition_fall else self.MIN_SLEW * 10

            logger.debug(f"Clock pin {node.name}: rise={node.arrival_rise*1e12:.2f}ps, "
                        f"fall={node.arrival_fall*1e12:.2f}ps")
        else:
            # Clock not found - log warning
            self.stats['missing_clocks'] += 1
            logger.warning(f"Clock '{node.clock}' not found for pin {node.name}")

            # Use default values
            node.arrival_rise = self.MIN_DELAY
            node.arrival_fall = self.MIN_DELAY
            node.slew_rise = self.MIN_SLEW * 10
            node.slew_fall = self.MIN_SLEW * 10

    def _get_clock(self, clock_name: str) -> Optional[Clock]:
        """Get clock with caching."""
        if not clock_name:
            return None

        if clock_name not in self._clock_cache:
            if self.clock_constraints:
                self._clock_cache[clock_name] = self.clock_constraints.get_clock_by_name(clock_name)
            else:
                self._clock_cache[clock_name] = None

        return self._clock_cache[clock_name]

    def _apply_input_delay(self, node: TimingNode):
        """Apply input delay constraints to primary input."""
        if not self.exception_manager:
            node.arrival_rise = self.MIN_DELAY
            node.arrival_fall = self.MIN_DELAY
            node.slew_rise = self.MIN_SLEW
            node.slew_fall = self.MIN_SLEW
            return

        # Get pin name (without hierarchy)
        pin_name = node.name.split('/')[-1] if '/' in node.name else node.name
        cache_key = f"{pin_name}_{self.analysis_type}"

        # Check cache
        if cache_key in self._input_delay_cache:
            delays = self._input_delay_cache[cache_key]
            node.arrival_rise = delays.get('rise', self.MIN_DELAY)
            node.arrival_fall = delays.get('fall', self.MIN_DELAY)
            node.slew_rise = delays.get('slew_rise', self.MIN_SLEW)
            node.slew_fall = delays.get('slew_fall', self.MIN_SLEW)
            return

        # Get delays from exception manager
        delay_type = 'max' if self.analysis_type == 'setup' else 'min'

        # Try to get clock for this input
        clock_name = None
        if node.clock:
            clock_name = node.clock

        delay_rise = self.exception_manager.get_input_delay(pin_name, clock_name, 'rise', delay_type)
        delay_fall = self.exception_manager.get_input_delay(pin_name, clock_name, 'fall', delay_type)

        slew_rise = self.exception_manager.get_input_transition(pin_name, clock_name, 'rise', 'max')
        slew_fall = self.exception_manager.get_input_transition(pin_name, clock_name, 'fall', 'max')

        # Apply delays (use 0 if None - input can launch at time 0)
        node.arrival_rise = delay_rise if delay_rise is not None else self.MIN_DELAY
        node.arrival_fall = delay_fall if delay_fall is not None else self.MIN_DELAY
        node.slew_rise = slew_rise if slew_rise is not None else self.MIN_SLEW
        node.slew_fall = slew_fall if slew_fall is not None else self.MIN_SLEW

        # Cache results
        self._input_delay_cache[cache_key] = {
            'rise': node.arrival_rise,
            'fall': node.arrival_fall,
            'slew_rise': node.slew_rise,
            'slew_fall': node.slew_fall
        }

        logger.debug(f"Applied input delay to {node.name}: rise={node.arrival_rise*1e12:.2f}ps")

    def calculate_required_times(self) -> bool:
        """
        Backward propagate required times with validation.

        Returns:
            True if calculation successful
        """
        logger.info(f"Calculating required times for {self.analysis_type} analysis")

        # Get reverse topological order
        if self._reverse_topo is None:
            self._reverse_topo = self.edge_manager.get_reverse_topological_order()

        if not self._reverse_topo:
            logger.error("No reverse topological order found")
            return False

        # Reset required times
        self._reset_required_times()

        # Process in reverse topological order
        for node in self._reverse_topo:
            self._update_node_required(node)

        # Check for endpoints with infinite required times
        infinite_count = 0
        for node in self.edge_manager.get_all_nodes():
            if node.is_endpoint() and (node.required_rise == float('inf') or node.required_fall == float('inf')):
                infinite_count += 1
                if infinite_count < 10:
                    logger.warning(f"Endpoint {node.name} has infinite required time")

        self.stats['infinite_required'] = infinite_count
        if infinite_count > 0:
            logger.warning(f"Found {infinite_count} endpoints with infinite required times")

        logger.info(f"Required time calculation complete. Processed {len(self._reverse_topo)} nodes")

        return True

    def _reset_required_times(self):
        """Reset required times for all nodes."""
        reset_count = 0
        for node in self.edge_manager.get_all_nodes():
            if node.required_rise != float('inf') or node.required_fall != float('inf'):
                reset_count += 1
            node.required_rise = float('inf')
            node.required_fall = float('inf')
            node.attributes['required_valid'] = False

        # Set required times at endpoints
        endpoint_count = self._set_endpoint_required_times()

        logger.debug(f"Reset required times for {reset_count} nodes, set {endpoint_count} endpoints")

    def _set_endpoint_required_times(self) -> int:
        """Set required times at timing endpoints."""
        endpoint_count = 0

        for node in self.edge_manager.get_all_nodes():
            if not (node.is_endpoint() or
                   (node.pin_name and node.pin_name.upper() in ['D', 'DATA'] and
                    node.cell_type and 'DFF' in node.cell_type.upper())):
                continue

            if node.clock:
                clock = self._get_clock(node.clock)
                if clock:
                    self._set_clock_endpoint_required(node, clock)
                    endpoint_count += 1
                else:
                    self.stats['missing_clocks'] += 1
                    logger.warning(f"Clock '{node.clock}' not found for endpoint {node.name}")
            elif node.node_type.value == 'primary_output':
                self._apply_output_delay(node)
                endpoint_count += 1
            else:
                # Default endpoint with no clock - use default period
                if self.analysis_type == 'setup':
                    node.required_rise = 10e-9  # 10ns default
                    node.required_fall = 10e-9
                else:  # hold
                    node.required_rise = 0.0
                    node.required_fall = 0.0
                endpoint_count += 1

        logger.info(f"Set required times for {endpoint_count} endpoints")
        return endpoint_count

    def _set_clock_endpoint_required(self, node: TimingNode, clock: Clock):
        """Set required time for clocked endpoint with proper constraints."""
        # Get clock edge times
        rise_edge, fall_edge = clock.get_waveform()

        # Get uncertainty
        uncertainty = self.delay_calculator.calculate_clock_uncertainty(
            node.clock, node.clock, self.analysis_type
        )

        # Get setup/hold times from node attributes or LIB
        if self.analysis_type == 'setup':
            # Setup: required = next clock edge - uncertainty - setup_time
            setup_time = self._get_setup_time(node)
            next_edge = rise_edge + clock.period
            required = next_edge - uncertainty - setup_time
        else:  # hold
            # Hold: required = current clock edge + uncertainty + hold_time
            hold_time = self._get_hold_time(node)
            required = rise_edge + uncertainty + hold_time

        node.required_rise = required
        node.required_fall = required
        node.attributes['required_valid'] = True

        # Cache
        self._node_required[node.name] = {
            'rise': required,
            'fall': required
        }

        logger.debug(f"Endpoint {node.name}: required={required*1e12:.2f}ps, "
                    f"setup={self._get_setup_time(node)*1e12:.2f}ps")

    def _get_setup_time(self, node: TimingNode) -> float:
        """Get setup time from node attributes or cache."""
        # Check cache
        if node.name in self._setup_time_cache:
            return self._setup_time_cache[node.name]

        setup_time = 0.0

        # Check node attributes first
        if 'setup_time' in node.attributes:
            setup_time = node.attributes['setup_time']
        elif node.cell_type in node.attributes.get('dff_constraints', {}):
            setup_time = node.attributes['dff_constraints'][node.cell_type].get('setup', 0.0)
        elif node.cell_type and 'DFF' in node.cell_type.upper():
            # Default based on cell name
            if 'X1' in node.cell_type:
                setup_time = 50e-12
            elif 'X2' in node.cell_type:
                setup_time = 60e-12
            else:
                setup_time = 55e-12
            logger.debug(f"Using default setup time {setup_time*1e12:.1f}ps for {node.cell_type}")

        # Ensure minimum
        setup_time = max(setup_time, self.MIN_DELAY)

        self._setup_time_cache[node.name] = setup_time
        return setup_time

    def _get_hold_time(self, node: TimingNode) -> float:
        """Get hold time from node attributes or cache."""
        # Check cache
        if node.name in self._hold_time_cache:
            return self._hold_time_cache[node.name]

        hold_time = 0.0

        # Check node attributes first
        if 'hold_time' in node.attributes:
            hold_time = node.attributes['hold_time']
        elif node.cell_type in node.attributes.get('dff_constraints', {}):
            hold_time = node.attributes['dff_constraints'][node.cell_type].get('hold', 0.0)
        elif node.cell_type and 'DFF' in node.cell_type.upper():
            # Default based on cell name
            if 'X1' in node.cell_type:
                hold_time = 20e-12
            elif 'X2' in node.cell_type:
                hold_time = 25e-12
            else:
                hold_time = 22e-12
            logger.debug(f"Using default hold time {hold_time*1e12:.1f}ps for {node.cell_type}")

        # Ensure minimum
        hold_time = max(hold_time, self.MIN_DELAY)

        self._hold_time_cache[node.name] = hold_time
        return hold_time

    def _apply_output_delay(self, node: TimingNode):
        """Apply output delay constraints to primary output."""
        if not self.exception_manager:
            if self.analysis_type == 'setup':
                node.required_rise = 10e-9  # 10ns default
                node.required_fall = 10e-9
            else:
                node.required_rise = 0.0
                node.required_fall = 0.0
            return

        # Get pin name
        pin_name = node.name.split('/')[-1] if '/' in node.name else node.name
        cache_key = f"{pin_name}_{self.analysis_type}"

        # Check cache
        if cache_key in self._output_delay_cache:
            delays = self._output_delay_cache[cache_key]
            node.required_rise = delays.get('rise', float('inf'))
            node.required_fall = delays.get('fall', float('inf'))
            return

        # Get clock period (use default if not available)
        clock_period = 10e-9  # 10ns default
        if self.clock_constraints and self.clock_constraints.get_all_clocks():
            clock_period = self.clock_constraints.get_all_clocks()[0].period

        if self.analysis_type == 'setup':
            # Setup: required = clock_period - output_delay
            delay_rise = self.exception_manager.get_output_delay(pin_name, None, 'rise', 'max')
            delay_fall = self.exception_manager.get_output_delay(pin_name, None, 'fall', 'max')

            node.required_rise = clock_period - delay_rise if delay_rise is not None else clock_period
            node.required_fall = clock_period - delay_fall if delay_fall is not None else clock_period
        else:  # hold
            # Hold: required = output_delay
            delay_rise = self.exception_manager.get_output_delay(pin_name, None, 'rise', 'min')
            delay_fall = self.exception_manager.get_output_delay(pin_name, None, 'fall', 'min')

            node.required_rise = delay_rise if delay_rise is not None else 0.0
            node.required_fall = delay_fall if delay_fall is not None else 0.0

        node.attributes['required_valid'] = True

        # Cache results
        self._output_delay_cache[cache_key] = {
            'rise': node.required_rise,
            'fall': node.required_fall
        }

    def _update_node_required(self, node: TimingNode):
        """Update required time for a node based on its successors."""
        outgoing_edges = self.edge_manager.get_outgoing_edges(node)

        if not outgoing_edges:
            return

        rise_required = float('inf')
        fall_required = float('inf')
        valid_successors = False

        for edge in outgoing_edges:
            to_node = edge.to_node

            for out_trans in ['rise', 'fall']:
                out_required = to_node.get_required(out_trans)
                if out_required == float('inf'):
                    continue

                valid_successors = True

                # Handle different timing senses
                if edge.timing_sense == TimingSense.POSITIVE_UNATE:
                    in_trans = out_trans
                    delay = self._get_edge_delay(edge, node, to_node, in_trans, out_trans)
                    if delay < float('inf'):
                        in_required = out_required - delay

                        if in_trans == 'rise':
                            rise_required = min(rise_required, in_required)
                        else:
                            fall_required = min(fall_required, in_required)

                elif edge.timing_sense == TimingSense.NEGATIVE_UNATE:
                    in_trans = 'fall' if out_trans == 'rise' else 'rise'
                    delay = self._get_edge_delay(edge, node, to_node, in_trans, out_trans)
                    if delay < float('inf'):
                        in_required = out_required - delay

                        if in_trans == 'rise':
                            rise_required = min(rise_required, in_required)
                        else:
                            fall_required = min(fall_required, in_required)

                else:  # NON_UNATE
                    for in_trans in ['rise', 'fall']:
                        delay = self._get_edge_delay(edge, node, to_node, in_trans, out_trans)
                        if delay < float('inf'):
                            in_required = out_required - delay

                            if in_trans == 'rise':
                                rise_required = min(rise_required, in_required)
                            else:
                                fall_required = min(fall_required, in_required)

        if valid_successors:
            # Update node required times
            if rise_required != float('inf'):
                node.required_rise = min(node.required_rise, rise_required)
            if fall_required != float('inf'):
                node.required_fall = min(node.required_fall, fall_required)

    def _get_edge_delay(self, edge: TimingEdge, from_node: TimingNode,
                        to_node: TimingNode, in_trans: str, out_trans: str) -> float:
        """Get or calculate edge delay with validation."""
        # Check if edge already has calculated delay
        delay = edge.get_delay(in_trans)

        if delay > self.MIN_DELAY:
            return delay

        # Calculate delay
        try:
            in_slew = from_node.get_slew(in_trans)
            if in_slew <= self.MIN_DELAY:
                in_slew = self.MIN_SLEW

            load = to_node.capacitance
            if load <= self.MIN_DELAY:
                load = to_node.attributes.get('load', self.DEFAULT_LOAD)

            delay = self.delay_calculator.calculate_cell_delay(
                edge, in_slew, load, out_trans
            )

            # Ensure minimum
            delay = max(delay, self.MIN_DELAY)

            # Cache on edge
            edge.set_delay(delay, in_trans)

            return delay

        except Exception as e:
            logger.warning(f"Error calculating edge delay: {e}")
            return float('inf')

    def calculate_slacks(self) -> Dict[str, Dict[str, float]]:
        """Calculate slacks for all endpoints."""
        slacks = {}

        for node in self.edge_manager.get_all_nodes():
            if node.is_endpoint() or (node.pin_name and node.pin_name.upper() in ['D', 'DATA']):
                node.calculate_slack()

                if node.slack_rise != 0 or node.slack_fall != 0:
                    slacks[node.name] = {
                        'rise': node.slack_rise,
                        'fall': node.slack_fall
                    }

        logger.info(f"Calculated slacks for {len(slacks)} endpoints")
        return slacks

    def validate_timing(self) -> Dict[str, Any]:
        """Validate timing calculations and return issues."""
        issues = {
            'nodes_without_arrival': [],
            'endpoints_without_required': [],
            'zero_slack_endpoints': [],
            'missing_clock_constraints': []
        }

        # Check nodes without valid arrival times
        for node in self.edge_manager.get_all_nodes():
            if not node.attributes.get('arrival_valid', False) and not node.is_startpoint():
                issues['nodes_without_arrival'].append(node.name)

        # Check endpoints without required times
        for node in self.edge_manager.get_all_nodes():
            if node.is_endpoint():
                if node.required_rise == float('inf') and node.required_fall == float('inf'):
                    issues['endpoints_without_required'].append(node.name)

        # Check for zero slack at endpoints
        for node in self.edge_manager.get_all_nodes():
            if node.is_endpoint():
                if abs(node.slack_rise) < self.MIN_DELAY and abs(node.slack_fall) < self.MIN_DELAY:
                    issues['zero_slack_endpoints'].append(node.name)

        return issues

    def get_arrival_stats(self) -> Dict[str, Any]:
        """Get statistics about arrival times."""
        arrivals = []
        for node in self.edge_manager.get_all_nodes():
            if node.arrival_rise > self.MIN_DELAY:
                arrivals.append(node.arrival_rise)
            if node.arrival_fall > self.MIN_DELAY:
                arrivals.append(node.arrival_fall)

        if not arrivals:
            return {'max': 0, 'min': 0, 'avg': 0, 'count': 0}

        return {
            'max': max(arrivals),
            'max_ps': max(arrivals) * 1e12,
            'min': min(arrivals),
            'min_ps': min(arrivals) * 1e12,
            'avg': sum(arrivals) / len(arrivals),
            'avg_ps': sum(arrivals) / len(arrivals) * 1e12,
            'count': len(arrivals)
        }

    def print_summary(self):
        """Print calculation summary."""
        logger.info("=" * 60)
        logger.info(f"Arrival/Required Calculator Summary ({self.analysis_type})")
        logger.info("=" * 60)
        logger.info(f"Nodes processed: {self.stats['nodes_processed']}")
        logger.info(f"Startpoints processed: {self.stats['startpoints_processed']}")
        logger.info(f"Missing clocks: {self.stats['missing_clocks']}")
        logger.info(f"Missing constraints: {self.stats['missing_constraints']}")
        logger.info(f"Zero arrivals: {self.stats['zero_arrivals']}")
        logger.info(f"Infinite required: {self.stats['infinite_required']}")

        arrival_stats = self.get_arrival_stats()
        if arrival_stats['count'] > 0:
            logger.info(f"\nArrival times:")
            logger.info(f"  Max: {arrival_stats['max_ps']:.2f}ps")
            logger.info(f"  Min: {arrival_stats['min_ps']:.2f}ps")
            logger.info(f"  Avg: {arrival_stats['avg_ps']:.2f}ps")

        issues = self.validate_timing()
        has_issues = any(issues.values())
        if has_issues:
            logger.info("\nValidation issues:")
            for issue_type, issue_list in issues.items():
                if issue_list:
                    logger.info(f"  {issue_type}: {len(issue_list)}")

        logger.info("=" * 60)

    def clear_caches(self):
        """Clear all internal caches."""
        self._clock_cache.clear()
        self._input_delay_cache.clear()
        self._output_delay_cache.clear()
        self._setup_time_cache.clear()
        self._hold_time_cache.clear()
        self._node_arrivals.clear()
        self._node_required.clear()
        self._topo_order = None
        self._reverse_topo = None
        logger.debug("ArrivalRequiredCalculator caches cleared")