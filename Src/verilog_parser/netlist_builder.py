"""
Netlist builder for Verilog parser.
Builds and manages netlist data structures.
"""

from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict
from dataclasses import dataclass, field

from Src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class NetlistNet:
    """Represents a net in the netlist."""
    name: str
    width: int = 1
    is_clock: bool = False
    is_reset: bool = False
    is_power: bool = False
    is_ground: bool = False
    drivers: List[str] = field(default_factory=list)  # Cell pins driving this net
    loads: List[str] = field(default_factory=list)  # Cell pins load this net
    capacitance: float = 0.0  # Total load capacitance
    resistance: float = 0.0  # Net resistance
    fanout: int = 0

    def add_driver(self, pin_name: str):
        """Add a driver pin to this net."""
        if pin_name not in self.drivers:
            self.drivers.append(pin_name)
            self.fanout = len(self.loads)

    def add_load(self, pin_name: str):
        """Add a load pin to this net."""
        if pin_name not in self.loads:
            self.loads.append(pin_name)
            self.fanout = len(self.loads)

    def is_multi_driver(self) -> bool:
        """Check if net has multiple drivers."""
        return len(self.drivers) > 1

    def has_driver(self) -> bool:
        """Check if net has at least one driver."""
        return len(self.drivers) > 0


@dataclass
class NetlistCell:
    """Represents a cell instance in the netlist."""
    name: str
    cell_type: str
    module: str
    pins: Dict[str, str] = field(default_factory=dict)  # pin -> net mapping
    parameters: Dict[str, str] = field(default_factory=dict)
    is_sequential: bool = False
    is_clock_gate: bool = False
    is_level_shifter: bool = False
    is_isolation: bool = False

    def get_pin_net(self, pin_name: str) -> Optional[str]:
        """Get net connected to a pin."""
        return self.pins.get(pin_name)

    def get_all_nets(self) -> Set[str]:
        """Get all nets connected to this cell."""
        return set(self.pins.values())


class NetlistBuilder:
    """Builds and manages netlist from parsed Verilog."""

    def __init__(self):
        self.cells: Dict[str, NetlistCell] = {}  # cell name -> cell
        self.nets: Dict[str, NetlistNet] = {}  # net name -> net
        self.ports: Dict[str, Dict[str, Any]] = {}  # port name -> port info

        # Hierarchical information
        self.hierarchy: Dict[str, List[str]] = defaultdict(list)  # parent -> children
        self.instances: Dict[str, str] = {}  # instance name -> module name

        # Clock and reset nets
        self.clock_nets: Set[str] = set()
        self.reset_nets: Set[str] = set()

        # Power and ground nets
        self.power_nets: Set[str] = {'VDD', 'VCC', 'VPWR'}
        self.ground_nets: Set[str] = {'VSS', 'GND', 'VGROUND'}

        logger.info("Netlist builder initialized")

    def build_from_parser(self, module_resolver) -> bool:
        """
        Build netlist from module resolver.

        Args:
            module_resolver: ModuleResolver instance with parsed data

        Returns:
            True if successful
        """
        try:
            # Get flattened cells
            flat_cells = module_resolver.get_flat_cells()

            # Build cells and nets
            for cell_info in flat_cells:
                self._add_cell(cell_info)

            # Analyze net connections
            self._analyze_nets()

            # Identify special nets
            self._identify_special_nets()

            # Calculate fanouts
            self._calculate_fanouts()

            logger.info(f"Netlist built: {len(self.cells)} cells, {len(self.nets)} nets")
            return True

        except Exception as e:
            logger.error(f"Failed to build netlist: {e}", exc_info=True)
            return False

    def _add_cell(self, cell_info: Dict[str, Any]):
        """Add a cell to the netlist."""
        cell_name = cell_info['name']
        cell_type = cell_info['type']
        module_name = cell_info.get('module', cell_type)
        pins = cell_info.get('pins', {})
        parameters = cell_info.get('parameters', {})

        # Determine if sequential
        is_sequential = self._is_sequential_cell(cell_type)

        # Create cell
        cell = NetlistCell(
            name=cell_name,
            cell_type=cell_type,
            module=module_name,
            pins=pins,
            parameters=parameters,
            is_sequential=is_sequential,
            is_clock_gate='clock_gate' in cell_type.lower() or 'icg' in cell_type.lower(),
            is_level_shifter='level_shifter' in cell_type.lower() or 'ls' in cell_type.lower(),
            is_isolation='isolation' in cell_type.lower() or 'iso' in cell_type.lower()
        )

        self.cells[cell_name] = cell

        # Add nets from pins
        for pin_name, net_name in pins.items():
            self._add_net(net_name)

            # Record connection
            if self._is_output_pin(cell_type, pin_name):
                self.nets[net_name].add_driver(f"{cell_name}/{pin_name}")
            else:
                self.nets[net_name].add_load(f"{cell_name}/{pin_name}")

    def _add_net(self, net_name: str):
        """Add a net to the netlist if it doesn't exist."""
        if net_name not in self.nets:
            self.nets[net_name] = NetlistNet(name=net_name)

    def _is_sequential_cell(self, cell_type: str) -> bool:
        """Determine if a cell is sequential."""
        seq_keywords = ['DFF', 'LATCH', 'FF', 'REG', 'flop', 'latch']
        cell_upper = cell_type.upper()
        return any(keyword in cell_upper for keyword in seq_keywords)

    def _is_output_pin(self, cell_type: str, pin_name: str) -> bool:
        """Determine if a pin is an output."""
        # Common output pin names
        output_pins = {'Q', 'QN', 'Z', 'Y', 'OUT'}
        pin_upper = pin_name.upper()

        # Check if pin name suggests output
        if pin_upper in output_pins:
            return True

        # Check if pin name starts with 'out' or ends with 'z'
        if pin_upper.startswith('OUT') or pin_upper.endswith('Z'):
            return True

        # Default to input for safety
        return False

    def _analyze_nets(self):
        """Analyze net connections and properties."""
        for net_name, net in self.nets.items():
            # Check for multiple drivers
            if net.is_multi_driver():
                logger.warning(f"Net {net_name} has multiple drivers: {net.drivers}")

            # Check for floating nets
            if not net.has_driver():
                logger.warning(f"Net {net_name} has no driver")

            if not net.loads:
                logger.debug(f"Net {net_name} has no loads")

    def _identify_special_nets(self):
        """Identify clock, reset, power, and ground nets."""
        for net_name, net in self.nets.items():
            net_upper = net_name.upper()

            # Clock nets
            if any(ck in net_upper for ck in ['CLK', 'CK', 'CLOCK']):
                net.is_clock = True
                self.clock_nets.add(net_name)

            # Reset nets
            if any(rs in net_upper for rs in ['RST', 'RESET', 'RN']):
                net.is_reset = True
                self.reset_nets.add(net_name)

            # Power nets
            if any(pw in net_upper for pw in ['VDD', 'VCC', 'VPWR', 'VDD']):
                net.is_power = True
                self.power_nets.add(net_name)

            # Ground nets
            if any(gnd in net_upper for gnd in ['VSS', 'GND', 'VGROUND']):
                net.is_ground = True
                self.ground_nets.add(net_name)

    def _calculate_fanouts(self):
        """Calculate fanout for each net."""
        for net in self.nets.values():
            net.fanout = len(net.loads)

    def get_cell(self, name: str) -> Optional[NetlistCell]:
        """Get cell by name."""
        return self.cells.get(name)

    def get_net(self, name: str) -> Optional[NetlistNet]:
        """Get net by name."""
        return self.nets.get(name)

    def get_cells_by_type(self, cell_type: str) -> List[NetlistCell]:
        """Get all cells of a given type."""
        return [c for c in self.cells.values() if c.cell_type == cell_type]

    def get_sequential_cells(self) -> List[NetlistCell]:
        """Get all sequential cells."""
        return [c for c in self.cells.values() if c.is_sequential]

    def get_clock_nets(self) -> List[NetlistNet]:
        """Get all clock nets."""
        return [self.nets[name] for name in self.clock_nets if name in self.nets]

    def get_reset_nets(self) -> List[NetlistNet]:
        """Get all reset nets."""
        return [self.nets[name] for name in self.reset_nets if name in self.nets]

    def get_high_fanout_nets(self, threshold: int = 100) -> List[NetlistNet]:
        """Get nets with fanout above threshold."""
        return [n for n in self.nets.values() if n.fanout > threshold]

    def get_floating_nets(self) -> List[NetlistNet]:
        """Get nets with no driver."""
        return [n for n in self.nets.values() if not n.has_driver()]

    def get_unloaded_nets(self) -> List[NetlistNet]:
        """Get nets with no loads."""
        return [n for n in self.nets.values() if not n.loads]

    def get_multi_driver_nets(self) -> List[NetlistNet]:
        """Get nets with multiple drivers."""
        return [n for n in self.nets.values() if n.is_multi_driver()]

    def get_path_from_to(self, from_cell: str, to_cell: str) -> Optional[List[str]]:
        """
        Find a path between two cells.

        Args:
            from_cell: Starting cell name
            to_cell: Ending cell name

        Returns:
            List of nets forming the path, or None if no path
        """
        # Simple BFS implementation
        visited = set()
        queue = [(from_cell, [])]

        while queue:
            cell_name, path = queue.pop(0)

            if cell_name == to_cell:
                return path

            if cell_name in visited:
                continue

            visited.add(cell_name)
            cell = self.cells.get(cell_name)

            if cell:
                for net_name in cell.get_all_nets():
                    net = self.nets.get(net_name)
                    if net:
                        for load in net.loads:
                            next_cell = load.split('/')[0]
                            if next_cell not in visited:
                                queue.append((next_cell, path + [net_name]))

        return None

    def get_fanout_cone(self, start_net: str, max_depth: int = 10) -> Dict[str, Any]:
        """
        Get fanout cone from a starting net.

        Args:
            start_net: Starting net name
            max_depth: Maximum depth to traverse

        Returns:
            Dictionary with fanout cone information
        """
        cone = {
            'start_net': start_net,
            'cells': set(),
            'nets': set(),
            'depth': 0,
            'endpoints': set()
        }

        if start_net not in self.nets:
            return cone

        queue = [(start_net, 0)]
        visited_nets = set()
        visited_cells = set()

        while queue:
            net_name, depth = queue.pop(0)

            if depth > max_depth or net_name in visited_nets:
                continue

            visited_nets.add(net_name)
            cone['nets'].add(net_name)
            cone['depth'] = max(cone['depth'], depth)

            net = self.nets.get(net_name)
            if net:
                for load in net.loads:
                    cell_name = load.split('/')[0]
                    cell = self.cells.get(cell_name)

                    if cell and cell_name not in visited_cells:
                        visited_cells.add(cell_name)
                        cone['cells'].add(cell_name)

                        # Add output nets of this cell
                        for pin_name, out_net in cell.pins.items():
                            if self._is_output_pin(cell.cell_type, pin_name):
                                if out_net not in visited_nets:
                                    queue.append((out_net, depth + 1))

        # Convert sets to lists for JSON serialization
        cone['cells'] = list(cone['cells'])
        cone['nets'] = list(cone['nets'])

        return cone

    def get_netlist_stats(self) -> Dict[str, Any]:
        """Get netlist statistics."""
        sequential = self.get_sequential_cells()
        high_fanout = self.get_high_fanout_nets()
        floating = self.get_floating_nets()
        unloaded = self.get_unloaded_nets()
        multi_driver = self.get_multi_driver_nets()

        return {
            'total_cells': len(self.cells),
            'total_nets': len(self.nets),
            'sequential_cells': len(sequential),
            'combinational_cells': len(self.cells) - len(sequential),
            'clock_nets': len(self.clock_nets),
            'reset_nets': len(self.reset_nets),
            'high_fanout_nets': len(high_fanout),
            'floating_nets': len(floating),
            'unloaded_nets': len(unloaded),
            'multi_driver_nets': len(multi_driver),
            'avg_fanout': sum(n.fanout for n in self.nets.values()) / len(self.nets) if self.nets else 0,
            'max_fanout': max((n.fanout for n in self.nets.values()), default=0)
        }

    def print_netlist_summary(self):
        """Print netlist summary."""
        stats = self.get_netlist_stats()

        logger.info("=" * 60)
        logger.info("Netlist Summary")
        logger.info("=" * 60)
        logger.info(f"Total cells: {stats['total_cells']}")
        logger.info(f"  Sequential: {stats['sequential_cells']}")
        logger.info(f"  Combinational: {stats['combinational_cells']}")
        logger.info(f"Total nets: {stats['total_nets']}")
        logger.info(f"Clock nets: {stats['clock_nets']}")
        logger.info(f"Reset nets: {stats['reset_nets']}")
        logger.info(f"Average fanout: {stats['avg_fanout']:.2f}")
        logger.info(f"Maximum fanout: {stats['max_fanout']}")
        logger.info(f"High fanout nets (>100): {stats['high_fanout_nets']}")
        logger.info(f"Floating nets: {stats['floating_nets']}")
        logger.info(f"Unloaded nets: {stats['unloaded_nets']}")
        logger.info(f"Multi-driver nets: {stats['multi_driver_nets']}")
        logger.info("=" * 60)

    def reset(self):
        """Reset the netlist builder."""
        self.cells.clear()
        self.nets.clear()
        self.ports.clear()
        self.hierarchy.clear()
        self.instances.clear()
        self.clock_nets.clear()
        self.reset_nets.clear()
        logger.debug("Netlist builder reset")