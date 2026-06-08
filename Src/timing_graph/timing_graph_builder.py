"""
Enhanced Timing Graph Builder for PySTA.
Builds timing graph from netlist and library with proper clock and constraint handling.
"""

from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict

from Src.liberty_parser.cell_library import CellLibrary, Cell, TimingArc, TimingSense as LibTimingSense
from Src.verilog_parser.module_resolver import ModuleResolver
from Src.timing_graph.graph_nodes import TimingNode, NodeType, TimingEdge, TimingSense as GraphTimingSense
from Src.timing_graph.graph_edges import EdgeManager
from Src.sta_engine.delay_calculator import DelayCalculator
from Src.sdc_parser.clock_constraints import ClockConstraints, Clock
from Src.sdc_parser.timing_exceptions import ExceptionManager
from Src.utils.logger import get_logger

logger = get_logger(__name__)


class TimingGraphBuilder:
    """Builds timing graph from netlist and library with enhanced constraint handling."""

    def __init__(self, cell_library: CellLibrary, module_resolver: ModuleResolver):
        self.cell_library = cell_library
        self.module_resolver = module_resolver

        self.edge_manager = EdgeManager()
        self.nodes: Dict[str, TimingNode] = {}  # name -> node

        # Create delay calculator
        self.delay_calculator = DelayCalculator(cell_library)

        # Clock constraints
        self.clock_constraints: Optional[ClockConstraints] = None
        self.exception_manager: Optional[ExceptionManager] = None

        # Clock pin mapping
        self.clock_pins: Dict[str, List[TimingNode]] = defaultdict(list)  # clock_name -> nodes
        self.pin_to_clock: Dict[str, str] = {}  # pin_name -> clock_name

        # Net capacitance tracking
        self.net_capacitance: Dict[str, float] = defaultdict(float)
        self.net_fanout: Dict[str, int] = defaultdict(int)

        # DFF constraint storage
        self.dff_constraints: Dict[str, Dict[str, float]] = defaultdict(lambda: {'setup': 0.0, 'hold': 0.0})

        # Start/End points
        self.startpoints: List[TimingNode] = []
        self.endpoints: List[TimingNode] = []

        # Validation flags
        self.graph_built = False
        self.has_cycles = False

    def build_graph(self, clock_constraints: ClockConstraints = None,
                    exception_manager: ExceptionManager = None) -> bool:
        """
        Build the complete timing graph with validation.

        Args:
            clock_constraints: Clock constraints from SDC
            exception_manager: Timing exceptions from SDC

        Returns:
            True if graph built successfully
        """
        logger.info("=" * 60)
        logger.info("Building timing graph")
        logger.info("=" * 60)

        self.clock_constraints = clock_constraints
        self.exception_manager = exception_manager

        # Clear existing graph
        self.nodes.clear()
        self.edge_manager.clear()
        self.startpoints.clear()
        self.endpoints.clear()
        self.clock_pins.clear()
        self.pin_to_clock.clear()
        self.dff_constraints.clear()

        # Validation checks
        if not self.cell_library:
            logger.error("Cell library not provided")
            return False

        if not self.module_resolver:
            logger.error("Module resolver not provided")
            return False

        # Step 1: Extract DFF constraints from library
        self._extract_dff_constraints()

        # Step 2: Create nodes for all pins
        self._create_nodes()
        logger.info(f"Created {len(self.nodes)} nodes")

        # Step 3: Create edges based on cell timing arcs
        self._create_edges()
        logger.info(f"Created {self.edge_manager.get_num_edges()} edges")

        # Step 4: Add net delays and loads
        self._add_net_info()
        logger.info(f"Tracked {len(self.net_capacitance)} nets")

        # Step 5: Apply clock constraints to nodes
        self._apply_clock_constraints()
        logger.info(f"Applied clocks to {len(self.clock_pins)} clock pins")

        # Step 6: Identify start and end points
        self._identify_start_end_points()
        logger.info(f"Identified {len(self.startpoints)} start points, {len(self.endpoints)} end points")

        # Step 7: Validate graph
        self.has_cycles = self.edge_manager.has_cycle()
        if self.has_cycles:
            logger.warning("Timing graph contains cycles - check for combinational loops")
        else:
            logger.info("Graph is acyclic - good for timing analysis")

        self.graph_built = True

        # Print summary
        self.print_summary()

        return True

    def _extract_dff_constraints(self):
        """Extract setup/hold constraints from DFF cells in library."""
        logger.debug("Extracting DFF constraints from library")

        dff_count = 0
        for cell_name, cell in self.cell_library.cells.items():
            # Check if this is a sequential cell (DFF, latch, etc.)
            if cell.is_sequential or any(seq in cell_name.upper() for seq in ['DFF', 'LATCH', 'FF', 'REG']):
                dff_count += 1

                # Look for setup/hold timing arcs
                setup_time = 0.0
                hold_time = 0.0

                # Check timing arcs for setup/hold
                for arc in cell.timing_arcs:
                    if hasattr(arc, 'timing_type') and arc.timing_type:
                        arc_type = str(arc.timing_type).lower()

                        if 'setup' in arc_type:
                            if hasattr(arc, 'rise_constraint') and arc.rise_constraint:
                                setup_time = max(setup_time, float(arc.rise_constraint))
                            elif hasattr(arc, 'fall_constraint') and arc.fall_constraint:
                                setup_time = max(setup_time, float(arc.fall_constraint))
                            elif hasattr(arc, 'setup_time') and arc.setup_time:
                                setup_time = max(setup_time, arc.setup_time)

                        elif 'hold' in arc_type:
                            if hasattr(arc, 'rise_constraint') and arc.rise_constraint:
                                hold_time = max(hold_time, float(arc.rise_constraint))
                            elif hasattr(arc, 'fall_constraint') and arc.fall_constraint:
                                hold_time = max(hold_time, float(arc.fall_constraint))
                            elif hasattr(arc, 'hold_time') and arc.hold_time:
                                hold_time = max(hold_time, arc.hold_time)

                # Also check pin attributes for constraints
                for pin_name, pin in cell.pins.items():
                    if pin_name.upper() in ['D', 'DATA']:
                        if hasattr(pin, 'attributes'):
                            attrs = pin.attributes
                            if 'setup' in attrs:
                                setup_time = max(setup_time, float(attrs['setup']))
                            if 'hold' in attrs:
                                hold_time = max(hold_time, float(attrs['hold']))

                # Store constraints
                if setup_time > 0 or hold_time > 0:
                    self.dff_constraints[cell_name] = {
                        'setup': setup_time,
                        'hold': hold_time
                    }
                    logger.debug(f"Cell {cell_name}: setup={setup_time*1e12:.2f}ps, hold={hold_time*1e12:.2f}ps")

        logger.info(f"Extracted constraints from {len(self.dff_constraints)} DFF cells out of {dff_count} sequential cells")

    def _create_nodes(self):
        """Create nodes for all pins in the design."""
        flat_cells = self.module_resolver.get_flat_cells()

        if not flat_cells:
            logger.error("No flattened cells found from module resolver")
            return

        node_count = 0
        for cell in flat_cells:
            cell_name = cell['name']
            cell_type = cell['type']
            pins = cell['pins']

            # Get cell from library
            lib_cell = self.cell_library.get_cell(cell_type)

            for port_name, net_name in pins.items():
                # Create node name (hierarchical)
                node_name = f"{cell_name}/{port_name}"

                # Determine node type
                node_type = NodeType.CELL_INPUT
                is_clock_pin = False
                pin_direction = 'input'

                if lib_cell:
                    pin = lib_cell.get_pin(port_name)
                    if pin:
                        pin_direction = pin.direction
                        if pin.direction == 'output':
                            node_type = NodeType.CELL_OUTPUT
                        if hasattr(pin, 'is_clock') and pin.is_clock:
                            is_clock_pin = True
                            node_type = NodeType.CLOCK

                # Create node
                node = TimingNode(
                    name=node_name,
                    node_type=node_type,
                    instance=cell_name,
                    cell_type=cell_type,
                    clock_pin=is_clock_pin,
                    pin_name=port_name,
                    net_name=net_name,
                    direction=pin_direction
                )

                # Store capacitance if output
                if node_type == NodeType.CELL_OUTPUT and lib_cell:
                    pin = lib_cell.get_pin(port_name)
                    if pin and hasattr(pin, 'capacitance'):
                        node.capacitance = pin.capacitance

                # Store DFF constraints if this is a D pin
                if cell_type in self.dff_constraints and port_name.upper() in ['D', 'DATA']:
                    node.attributes['setup_time'] = self.dff_constraints[cell_type]['setup']
                    node.attributes['hold_time'] = self.dff_constraints[cell_type]['hold']
                    logger.debug(f"Added constraints to {node_name}: setup={self.dff_constraints[cell_type]['setup']*1e12:.2f}ps")

                # Store library cell reference
                node.attributes['lib_cell'] = lib_cell
                node.attributes['lib_pin'] = pin if lib_cell else None

                self.nodes[node_name] = node
                node_count += 1

        logger.debug(f"Created {node_count} nodes")

        # Create nodes for primary inputs/outputs if missing
        self._create_primary_io_nodes(flat_cells)

    def _create_primary_io_nodes(self, flat_cells: List[Dict]):
        """Create nodes for primary inputs/outputs not connected to cells."""
        # Collect all nets that appear as pins
        all_nets = set()
        connected_nets = set()

        for cell in flat_cells:
            for port_name, net_name in cell['pins'].items():
                all_nets.add(net_name)

        # Find nets that appear as inputs to top-level but not driven
        # This is simplified - in real implementation, would use port definitions
        for net_name in all_nets:
            # Check if this net has a driver
            has_driver = False
            for cell in flat_cells:
                lib_cell = self.cell_library.get_cell(cell['type'])
                for port_name, pin_net in cell['pins'].items():
                    if pin_net == net_name and lib_cell:
                        pin = lib_cell.get_pin(port_name)
                        if pin and pin.direction == 'output':
                            has_driver = True
                            break
                if has_driver:
                    break

            if not has_driver:
                # This is a primary input
                node_name = f"PI_{net_name}"
                node = TimingNode(
                    name=node_name,
                    node_type=NodeType.PRIMARY_INPUT,
                    instance=None,
                    cell_type=None,
                    clock_pin=False,
                    pin_name=None,
                    net_name=net_name,
                    direction='input'
                )
                self.nodes[node_name] = node
                logger.debug(f"Created primary input node for net: {net_name}")

    def _create_edges(self):
        """Create edges based on cell timing arcs."""
        flat_cells = self.module_resolver.get_flat_cells()

        if not flat_cells:
            logger.error("No flattened cells found")
            return

        edge_count = 0
        missing_arcs = 0

        for cell in flat_cells:
            cell_name = cell['name']
            cell_type = cell['type']
            pins = cell['pins']

            # Get cell from library
            lib_cell = self.cell_library.get_cell(cell_type)
            if not lib_cell:
                logger.warning(f"Cell type {cell_type} not found in library - using default timing")
                self._create_default_edges(cell, cell_name)
                continue

            # Create edges for each timing arc
            if not lib_cell.timing_arcs:
                logger.debug(f"No timing arcs found for {cell_type}, using default arcs")
                self._create_default_edges(cell, cell_name, lib_cell)
                continue

            for arc in lib_cell.timing_arcs:
                from_pin = arc.from_pin
                to_pin = arc.to_pin

                # Skip if pins not in this instance
                if from_pin not in pins or to_pin not in pins:
                    continue

                # Get node names
                from_node_name = f"{cell_name}/{from_pin}"
                to_node_name = f"{cell_name}/{to_pin}"

                from_node = self.nodes.get(from_node_name)
                to_node = self.nodes.get(to_node_name)

                if not from_node or not to_node:
                    logger.warning(f"Missing nodes for arc: {from_node_name} -> {to_node_name}")
                    missing_arcs += 1
                    continue

                # Convert timing sense
                timing_sense = GraphTimingSense.NON_UNATE
                if hasattr(arc, 'timing_sense'):
                    if arc.timing_sense == LibTimingSense.POSITIVE_UNATE:
                        timing_sense = GraphTimingSense.POSITIVE_UNATE
                    elif arc.timing_sense == LibTimingSense.NEGATIVE_UNATE:
                        timing_sense = GraphTimingSense.NEGATIVE_UNATE

                # Create edge
                edge = TimingEdge(
                    from_node=from_node,
                    to_node=to_node,
                    timing_sense=timing_sense,
                    cell_instance=cell_name,
                    cell_type=cell_type,
                    arc_type=arc.timing_type.value if hasattr(arc, 'timing_type') and arc.timing_type else 'combinational'
                )

                # Store delay calculation data
                edge.attributes['arc'] = arc
                edge.attributes['from_pin'] = from_pin
                edge.attributes['to_pin'] = to_pin

                # Store delay coefficients if available
                if hasattr(arc, 'rise_delay_coeff'):
                    edge.attributes['rise_coeff'] = arc.rise_delay_coeff
                if hasattr(arc, 'fall_delay_coeff'):
                    edge.attributes['fall_coeff'] = arc.fall_delay_coeff

                self.edge_manager.add_edge(edge)
                edge_count += 1

        logger.info(f"Created {edge_count} timing edges, {missing_arcs} missing arcs skipped")

    def _create_default_edges(self, cell: Dict, cell_name: str, lib_cell: Cell = None):
        """Create default timing edges for cells without library arcs."""
        pins = cell['pins']

        # Identify input and output pins
        input_pins = []
        output_pins = []

        if lib_cell:
            for pin_name in pins:
                pin = lib_cell.get_pin(pin_name)
                if pin:
                    if pin.direction == 'input':
                        input_pins.append(pin_name)
                    elif pin.direction == 'output':
                        output_pins.append(pin_name)
        else:
            # Guess based on pin names
            for pin_name in pins:
                if pin_name.upper() in ['CLK', 'CK', 'D', 'A', 'B', 'S', 'RST']:
                    input_pins.append(pin_name)
                elif pin_name.upper() in ['Q', 'QN', 'Y', 'Z', 'OUT']:
                    output_pins.append(pin_name)

        # Create edges from each input to each output
        for in_pin in input_pins:
            for out_pin in output_pins:
                from_node_name = f"{cell_name}/{in_pin}"
                to_node_name = f"{cell_name}/{out_pin}"

                from_node = self.nodes.get(from_node_name)
                to_node = self.nodes.get(to_node_name)

                if from_node and to_node:
                    edge = TimingEdge(
                        from_node=from_node,
                        to_node=to_node,
                        timing_sense=GraphTimingSense.NON_UNATE,
                        cell_instance=cell_name,
                        cell_type=cell['type'],
                        arc_type='combinational'
                    )
                    edge.attributes['default_arc'] = True
                    self.edge_manager.add_edge(edge)

    def _add_net_info(self):
        """Add net delay and capacitance information."""
        flat_cells = self.module_resolver.get_flat_cells()

        # Calculate net capacitance and fanout
        net_loads = defaultdict(float)
        net_drivers = defaultdict(list)
        net_load_pins = defaultdict(list)

        for cell in flat_cells:
            pins = cell['pins']
            cell_type = cell['type']
            lib_cell = self.cell_library.get_cell(cell_type)

            for port_name, net_name in pins.items():
                if lib_cell:
                    pin = lib_cell.get_pin(port_name)
                    if pin:
                        if pin.direction == 'input':
                            # Add input pin capacitance to net
                            if hasattr(pin, 'capacitance'):
                                net_loads[net_name] += pin.capacitance
                            net_load_pins[net_name].append(f"{cell['name']}/{port_name}")
                        elif pin.direction == 'output':
                            net_drivers[net_name].append(f"{cell['name']}/{port_name}")

        self.net_capacitance = dict(net_loads)

        # Calculate fanout for each net
        for net_name, loads in net_load_pins.items():
            self.net_fanout[net_name] = len(loads)

        # Assign loads and fanout to output nodes
        for node_name, node in self.nodes.items():
            if node.node_type == NodeType.CELL_OUTPUT:
                # Find net connected to this output
                for cell in flat_cells:
                    if cell['name'] == node.instance:
                        for port_name, net_name in cell['pins'].items():
                            if port_name == node.pin_name:
                                node.attributes['net'] = net_name
                                node.attributes['load'] = net_loads.get(net_name, 5e-15)  # Default 5fF
                                node.attributes['fanout'] = self.net_fanout.get(net_name, 1)
                                node.capacitance = node.attributes['load']
                                break

    def _apply_clock_constraints(self):
        """Apply clock constraints from SDC to timing nodes."""
        if not self.clock_constraints:
            logger.warning("No clock constraints provided - clocks will not be applied")
            return

        clocks = self.clock_constraints.get_all_clocks()
        if not clocks:
            logger.warning("No clocks defined in constraints")
            return

        logger.info(f"Applying {len(clocks)} clocks to timing graph")

        # Create mapping from clock name to Clock object
        clock_map = {clock.name: clock for clock in clocks}

        # Find clock pins in the graph
        clock_pin_count = 0
        for node in self.nodes.values():
            if node.clock_pin or (node.pin_name and node.pin_name.upper() in ['CLK', 'CK']):
                # Try to find which clock this pin belongs to
                assigned = False

                # Check if node net matches any clock source
                if hasattr(node, 'net_name') and node.net_name:
                    for clock in clocks:
                        if node.net_name in clock.sources:
                            node.clock = clock.name
                            self.clock_pins[clock.name].append(node)
                            self.pin_to_clock[node.name] = clock.name
                            assigned = True
                            clock_pin_count += 1
                            break

                # If not assigned, check if instance name suggests a clock domain
                if not assigned and node.instance:
                    for clock in clocks:
                        if clock.name.lower() in node.instance.lower():
                            node.clock = clock.name
                            self.clock_pins[clock.name].append(node)
                            self.pin_to_clock[node.name] = clock.name
                            assigned = True
                            clock_pin_count += 1
                            break

                # Default to first clock if still not assigned
                if not assigned and clocks:
                    node.clock = clocks[0].name
                    self.clock_pins[clocks[0].name].append(node)
                    self.pin_to_clock[node.name] = clocks[0].name
                    clock_pin_count += 1

        # Apply clock attributes to nodes
        for clock_name, nodes in self.clock_pins.items():
            clock = clock_map.get(clock_name)
            if clock:
                for node in nodes:
                    # Store clock object reference
                    node.attributes['clock_obj'] = clock
                    node.attributes['clock_period'] = clock.period
                    node.attributes['clock_waveform'] = clock.waveform
                    node.attributes['clock_latency'] = clock.latency
                    node.attributes['clock_uncertainty'] = clock.uncertainty

        logger.info(f"Assigned {clock_pin_count} clock pins to {len(self.clock_pins)} clock domains")

    def _identify_start_end_points(self):
        """Identify start and end points for timing paths."""
        all_nodes = self.edge_manager.get_all_nodes()

        for node in all_nodes:
            fan_in = self.edge_manager.get_fan_in(node)
            fan_out = self.edge_manager.get_fan_out(node)

            # Start points: primary inputs and clock pins with no inputs
            if node.node_type == NodeType.PRIMARY_INPUT:
                node.is_startpoint = True
                self.startpoints.append(node)
            elif node.clock_pin and fan_in == 0:
                node.is_startpoint = True
                self.startpoints.append(node)
            elif fan_in == 0 and node.node_type != NodeType.PRIMARY_OUTPUT:
                # Node with no inputs but not output - treat as startpoint
                node.is_startpoint = True
                self.startpoints.append(node)

            # End points: primary outputs and sequential inputs with no outputs
            if node.node_type == NodeType.PRIMARY_OUTPUT:
                node.is_endpoint = True
                self.endpoints.append(node)
            elif fan_out == 0 and node.node_type != NodeType.PRIMARY_INPUT:
                # Check if this is a D pin of a DFF
                if node.pin_name and node.pin_name.upper() in ['D', 'DATA']:
                    if node.cell_type and any(seq in node.cell_type.upper() for seq in ['DFF', 'LATCH', 'FF']):
                        node.is_endpoint = True
                        self.endpoints.append(node)
                else:
                    node.is_endpoint = True
                    self.endpoints.append(node)

        # Remove duplicates
        self.startpoints = list(dict.fromkeys(self.startpoints))
        self.endpoints = list(dict.fromkeys(self.endpoints))

    def get_node(self, name: str) -> Optional[TimingNode]:
        """Get node by name."""
        return self.nodes.get(name)

    def get_all_nodes(self) -> List[TimingNode]:
        """Get all nodes."""
        return list(self.nodes.values())

    def get_startpoints(self) -> List[TimingNode]:
        """Get all start points."""
        return self.startpoints

    def get_endpoints(self) -> List[TimingNode]:
        """Get all end points."""
        return self.endpoints

    def get_node_by_instance_pin(self, instance: str, pin: str) -> Optional[TimingNode]:
        """Get node by instance and pin name."""
        node_name = f"{instance}/{pin}"
        return self.nodes.get(node_name)

    def get_net_capacitance(self, net_name: str) -> float:
        """Get capacitance of a net."""
        return self.net_capacitance.get(net_name, 5e-15)  # Default 5fF

    def get_net_fanout(self, net_name: str) -> int:
        """Get fanout of a net."""
        return self.net_fanout.get(net_name, 1)

    def get_clocks_on_pin(self, pin_name: str) -> List[str]:
        """Get clocks associated with a pin."""
        clocks = []
        if pin_name in self.pin_to_clock:
            clocks.append(self.pin_to_clock[pin_name])
        return clocks

    def get_clock_pins(self, clock_name: str) -> List[TimingNode]:
        """Get all pins belonging to a clock domain."""
        return self.clock_pins.get(clock_name, [])

    def get_dff_constraint(self, cell_type: str, constraint_type: str = 'setup') -> float:
        """Get DFF constraint value."""
        if cell_type in self.dff_constraints:
            return self.dff_constraints[cell_type].get(constraint_type, 0.0)
        return 0.0

    def to_networkx(self):
        """Convert to NetworkX graph for visualization."""
        try:
            import networkx as nx

            G = nx.DiGraph()

            # Add nodes
            for node in self.get_all_nodes():
                G.add_node(node.name,
                          type=node.node_type.value if node.node_type else 'unknown',
                          instance=node.instance,
                          cell_type=node.cell_type,
                          clock=node.clock)

            # Add edges
            for edge in self.edge_manager.get_all_edges():
                G.add_edge(edge.from_node.name, edge.to_node.name,
                          delay_rise=edge.delay_rise,
                          delay_fall=edge.delay_fall,
                          sense=edge.timing_sense.value if edge.timing_sense else 'unknown')

            return G
        except ImportError:
            logger.warning("NetworkX not available for graph conversion")
            return None

    def validate_graph(self) -> Dict[str, Any]:
        """Validate the timing graph and return issues."""
        issues = {
            'missing_clocks': [],
            'nodes_without_edges': [],
            'floating_nets': [],
            'multi_driver_nets': [],
            'zero_delay_edges': []
        }

        # Check for nodes with no connections
        for node in self.get_all_nodes():
            if (self.edge_manager.get_fan_in(node) == 0 and
                self.edge_manager.get_fan_out(node) == 0):
                issues['nodes_without_edges'].append(node.name)

        # Check for floating nets
        for net_name, capacitance in self.net_capacitance.items():
            drivers = [n for n in self.get_all_nodes()
                      if n.attributes.get('net') == net_name and
                      n.direction == 'output']
            if not drivers:
                issues['floating_nets'].append(net_name)

        # Check for multi-driver nets
        net_drivers = defaultdict(list)
        for node in self.get_all_nodes():
            if node.direction == 'output' and 'net' in node.attributes:
                net_drivers[node.attributes['net']].append(node.name)

        for net, drivers in net_drivers.items():
            if len(drivers) > 1:
                issues['multi_driver_nets'].append(f"{net}: {drivers}")

        # Check for zero delay edges
        for edge in self.edge_manager.get_all_edges():
            if edge.delay_rise == 0 and edge.delay_fall == 0:
                issues['zero_delay_edges'].append(f"{edge.from_node.name}->{edge.to_node.name}")

        # Check for missing clock pins
        if self.clock_constraints:
            for clock in self.clock_constraints.get_all_clocks():
                if clock.name not in self.clock_pins:
                    issues['missing_clocks'].append(clock.name)

        return issues

    def print_summary(self):
        """Print detailed graph summary."""
        logger.info("=" * 60)
        logger.info("Timing Graph Summary")
        logger.info("=" * 60)
        logger.info(f"Total nodes: {len(self.nodes)}")
        logger.info(f"Total edges: {self.edge_manager.get_num_edges()}")
        logger.info(f"Start points: {len(self.startpoints)}")
        logger.info(f"End points: {len(self.endpoints)}")
        logger.info(f"Clock domains: {len(self.clock_pins)}")

        # Node type breakdown
        type_counts = defaultdict(int)
        for node in self.get_all_nodes():
            if node.node_type:
                type_counts[node.node_type.value] += 1

        logger.info("\nNode types:")
        for type_name, count in sorted(type_counts.items()):
            logger.info(f"  {type_name}: {count}")

        # Clock pin breakdown
        if self.clock_pins:
            logger.info("\nClock domains:")
            for clock_name, pins in self.clock_pins.items():
                logger.info(f"  {clock_name}: {len(pins)} pins")

        # DFF constraints
        if self.dff_constraints:
            logger.info(f"\nDFF cells with constraints: {len(self.dff_constraints)}")
            # Show first few as sample
            sample_count = 0
            for cell, constraints in self.dff_constraints.items():
                if sample_count < 5:
                    logger.info(f"  {cell}: setup={constraints['setup']*1e12:.2f}ps, hold={constraints['hold']*1e12:.2f}ps")
                    sample_count += 1
                else:
                    break

        # Fanout statistics
        if self.net_fanout:
            avg_fanout = sum(self.net_fanout.values()) / len(self.net_fanout)
            max_fanout = max(self.net_fanout.values())
            logger.info(f"\nNet statistics:")
            logger.info(f"  Average fanout: {avg_fanout:.2f}")
            logger.info(f"  Maximum fanout: {max_fanout}")

        # Validation results
        issues = self.validate_graph()
        has_issues = any(issues.values())
        if has_issues:
            logger.info("\nValidation issues:")
            for issue_type, issue_list in issues.items():
                if issue_list:
                    logger.info(f"  {issue_type}: {len(issue_list)}")
        else:
            logger.info("\nValidation: No issues found")

        logger.info("=" * 60)

    def get_graph_stats(self) -> Dict[str, Any]:
        """Get detailed graph statistics."""
        return {
            'num_nodes': len(self.nodes),
            'num_edges': self.edge_manager.get_num_edges(),
            'num_startpoints': len(self.startpoints),
            'num_endpoints': len(self.endpoints),
            'num_clock_domains': len(self.clock_pins),
            'num_dff_constraints': len(self.dff_constraints),
            'has_cycles': self.has_cycles,
            'graph_built': self.graph_built,
            'node_types': {
                node_type.value: sum(1 for n in self.get_all_nodes()
                                    if n.node_type and n.node_type.value == node_type.value)
                for node_type in NodeType
            },
            'clock_domains': {
                clock_name: len(pins)
                for clock_name, pins in self.clock_pins.items()
            },
            'fanout_stats': {
                'avg': sum(self.net_fanout.values()) / len(self.net_fanout) if self.net_fanout else 0,
                'max': max(self.net_fanout.values()) if self.net_fanout else 0,
                'total_nets': len(self.net_fanout)
            }
        }