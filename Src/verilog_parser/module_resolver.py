"""
Module resolver for Verilog parser.
Handles module instantiation and hierarchy.
"""

from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path

from Src.utils.logger import get_logger

logger = get_logger(__name__)


class ModuleInstance:
    """Represents an instance of a module."""

    def __init__(self, name: str, module_type: str, parent=None):
        self.name: str = name
        self.module_type: str = module_type
        self.parent: Optional[ModuleInstance] = parent
        self.children: List[ModuleInstance] = []
        self.connections: Dict[str, str] = {}  # port -> net
        self.parameters: Dict[str, str] = {}  # parameter -> value

        # Hierarchical name
        if parent:
            self.hier_name = f"{parent.hier_name}/{name}"
        else:
            self.hier_name = name

    def add_child(self, instance: 'ModuleInstance'):
        """Add a child instance."""
        self.children.append(instance)

    def add_connection(self, port: str, net: str):
        """Add a port connection."""
        self.connections[port] = net

    def get_full_path(self) -> str:
        """Get full hierarchical path."""
        return self.hier_name

    def find_instance(self, name: str) -> Optional['ModuleInstance']:
        """Find instance by name in hierarchy."""
        if self.name == name:
            return self

        for child in self.children:
            result = child.find_instance(name)
            if result:
                return result

        return None


class ModuleResolver:
    """Resolves module hierarchy and flattens netlist."""

    def __init__(self):
        self.modules: Dict[str, Dict] = {}  # module_name -> module_data
        self.top_modules: List[str] = []
        self.instances: Dict[str, ModuleInstance] = {}
        self.root_instances: List[ModuleInstance] = []

        # Flattened netlist
        self.flattened_cells: List[Dict] = []  # cells in flattened design
        self.flattened_nets: Set[str] = set()  # all nets in design
        self.port_to_net: Dict[str, str] = {}  # port -> net mapping

    def add_module(self, module_name: str, module_data: Dict):
        """Add a module definition."""
        self.modules[module_name] = module_data

        # Check if this could be a top module
        if self._is_top_candidate(module_name):
            self.top_modules.append(module_name)

    def _is_top_candidate(self, module_name: str) -> bool:
        """Check if module could be a top-level module."""
        module = self.modules.get(module_name, {})

        # A module is top if it's not instantiated anywhere
        # This will be determined later when building hierarchy
        return True

    def build_hierarchy(self, top_module: Optional[str] = None) -> List[ModuleInstance]:
        """
        Build module hierarchy starting from top module.

        Args:
            top_module: Name of top module (auto-detect if None)

        Returns:
            List of root instances
        """
        # Determine top module if not specified
        if not top_module:
            top_module = self._find_top_module()
            if not top_module:
                logger.error("Could not determine top module")
                return []

        logger.info(f"Building hierarchy with top module: {top_module}")

        # Create root instance
        root = ModuleInstance(top_module, top_module, None)
        self.root_instances = [root]
        self.instances[top_module] = root

        # Recursively build hierarchy
        self._build_instance_hierarchy(root, top_module)

        # Flatten the design
        self._flatten_design()

        return self.root_instances

    def _find_top_module(self) -> Optional[str]:
        """
        Find the top-level module.
        Uses heuristic: module with most ports or not instantiated elsewhere.
        """
        # Count instantiations
        instantiation_count: Dict[str, int] = {}

        for module_name, module_data in self.modules.items():
            # Count instantiations in this module
            for item in module_data.get('items', []):
                if item['type'] == 'instantiation':
                    cell_type = item['module_name']
                    instantiation_count[cell_type] = instantiation_count.get(cell_type, 0) + 1

        # Find modules that are never instantiated
        not_instantiated = []
        for module_name in self.modules:
            if instantiation_count.get(module_name, 0) == 0:
                not_instantiated.append(module_name)

        if len(not_instantiated) == 1:
            return not_instantiated[0]
        elif len(not_instantiated) > 1:
            # Multiple candidates, pick the one with most ports
            best_candidate = None
            max_ports = -1

            for candidate in not_instantiated:
                module = self.modules.get(candidate, {})
                ports = len(module.get('ports', []))
                if ports > max_ports:
                    max_ports = ports
                    best_candidate = candidate

            return best_candidate

        # If all modules are instantiated, use the one with most ports
        best_candidate = None
        max_ports = -1

        for module_name in self.modules:
            module = self.modules.get(module_name, {})
            ports = len(module.get('ports', []))
            if ports > max_ports:
                max_ports = ports
                best_candidate = module_name

        return best_candidate

    def _build_instance_hierarchy(self, parent_instance: ModuleInstance, module_name: str):
        """
        Recursively build instance hierarchy.

        Args:
            parent_instance: Parent module instance
            module_name: Name of module to instantiate
        """
        module = self.modules.get(module_name)
        if not module:
            logger.warning(f"Module {module_name} not found")
            return

        # Process each instantiation in this module
        for item in module.get('items', []):
            if item['type'] == 'instantiation':
                cell_type = item['module_name']
                instances = item['instances']

                for inst in instances:
                    inst_name = inst['name']

                    # Create instance
                    instance = ModuleInstance(
                        name=inst_name,
                        module_type=cell_type,
                        parent=parent_instance
                    )

                    # Add connections
                    for port, net in inst.get('connections', {}).items():
                        instance.add_connection(port, net)

                    # Add parameters
                    for param, value in inst.get('parameters', {}).items():
                        instance.parameters[param] = value

                    # Add to parent
                    parent_instance.add_child(instance)
                    self.instances[instance.hier_name] = instance

                    # Recursively build if module is defined
                    if cell_type in self.modules:
                        self._build_instance_hierarchy(instance, cell_type)

    def _flatten_design(self):
        """Flatten the hierarchical design into a netlist."""
        self.flattened_cells = []
        self.flattened_nets = set()
        self.port_to_net = {}

        # Process all instances in DFS order
        for root in self.root_instances:
            self._flatten_instance(root, "")

    def _flatten_instance(self, instance: ModuleInstance, prefix: str):
        """
        Flatten a single instance.

        Args:
            instance: Module instance to flatten
            prefix: Hierarchical prefix for nets
        """
        # Generate cell name with hierarchy
        cell_name = instance.hier_name

        # Get module definition
        module = self.modules.get(instance.module_type, {})

        # Determine pin mapping
        pin_to_net = {}
        for port_name, net_name in instance.connections.items():
            # Resolve full net name
            if net_name.startswith('{'):
                # Handle bus connections
                full_net = net_name
            else:
                # Simple net
                if '.' in net_name or '[' in net_name:
                    full_net = net_name
                else:
                    full_net = f"{prefix}{net_name}"

            pin_to_net[port_name] = full_net
            self.flattened_nets.add(full_net)

        # Add cell to flattened list
        cell_info = {
            'name': cell_name,
            'type': instance.module_type,
            'pins': pin_to_net,
            'parameters': instance.parameters.copy(),
            'hierarchy': instance.hier_name
        }
        self.flattened_cells.append(cell_info)

        # Process children
        for child in instance.children:
            child_prefix = f"{prefix}{instance.name}_"
            self._flatten_instance(child, child_prefix)

    def get_flat_cells(self) -> List[Dict]:
        """Get flattened list of cells."""
        return self.flattened_cells

    def get_flat_nets(self) -> Set[str]:
        """Get flattened set of nets."""
        return self.flattened_nets

    def resolve_hierarchical_net(self, hier_net: str) -> str:
        """
        Resolve hierarchical net name to flat name.

        Args:
            hier_net: Hierarchical net name (e.g., "top/u1/net")

        Returns:
            Flattened net name
        """
        # Simple implementation - can be enhanced
        return hier_net.replace('/', '_')

    def get_all_instances(self) -> Dict[str, ModuleInstance]:
        """Get all instances by hierarchical name."""
        return self.instances