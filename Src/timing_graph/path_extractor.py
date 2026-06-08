"""
Path extractor for timing graph.
Extracts and analyzes timing paths.
"""

from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict
import heapq

from Src.timing_graph.graph_nodes import TimingNode, NodeType
from Src.timing_graph.graph_edges import EdgeManager
from Src.utils.logger import get_logger
from Src.utils.time_utils import TimeUtils

logger = get_logger(__name__)


class PathExtractor:
    """Extracts timing paths from the timing graph."""

    def __init__(self, edge_manager: EdgeManager):
        self.edge_manager = edge_manager

        # Cache for extracted paths
        self.path_cache: Dict[str, List[Dict[str, Any]]] = {}

        logger.info("Path extractor initialized")

    def get_all_setup_paths(self, max_paths: int = 100) -> List[Dict[str, Any]]:
        """
        Extract all setup timing paths.

        Args:
            max_paths: Maximum number of paths to extract

        Returns:
            List of setup paths
        """
        cache_key = f"setup_{max_paths}"
        if cache_key in self.path_cache:
            return self.path_cache[cache_key]

        paths = []

        # Get all startpoints and endpoints
        startpoints = self._get_setup_startpoints()
        endpoints = self._get_setup_endpoints()

        # For each startpoint-endpoint pair, find paths
        for start in startpoints:
            for end in endpoints:
                if self._is_valid_path(start, end, 'setup'):
                    found_paths = self._find_paths(start, end, max_paths - len(paths))
                    paths.extend(found_paths)

                    if len(paths) >= max_paths:
                        break

            if len(paths) >= max_paths:
                break

        # Sort by slack (worst first)
        paths.sort(key=lambda x: x.get('slack', float('inf')))

        # Trim to max_paths
        paths = paths[:max_paths]

        self.path_cache[cache_key] = paths
        return paths

    def get_all_hold_paths(self, max_paths: int = 100) -> List[Dict[str, Any]]:
        """
        Extract all hold timing paths.

        Args:
            max_paths: Maximum number of paths to extract

        Returns:
            List of hold paths
        """
        cache_key = f"hold_{max_paths}"
        if cache_key in self.path_cache:
            return self.path_cache[cache_key]

        paths = []

        # Get all startpoints and endpoints for hold
        startpoints = self._get_hold_startpoints()
        endpoints = self._get_hold_endpoints()

        # For each startpoint-endpoint pair, find paths
        for start in startpoints:
            for end in endpoints:
                if self._is_valid_path(start, end, 'hold'):
                    found_paths = self._find_paths(start, end, max_paths - len(paths))
                    paths.extend(found_paths)

                    if len(paths) >= max_paths:
                        break

            if len(paths) >= max_paths:
                break

        # Sort by slack (worst first for hold means most negative)
        paths.sort(key=lambda x: x.get('slack', float('inf')))

        # Trim to max_paths
        paths = paths[:max_paths]

        self.path_cache[cache_key] = paths
        return paths

    def _get_setup_startpoints(self) -> List[TimingNode]:
        """Get startpoints for setup analysis."""
        startpoints = []

        for node in self.edge_manager.get_all_nodes():
            # Clock pins of sequential cells are startpoints
            if node.node_type == NodeType.CELL_INPUT and node.clock_pin:
                startpoints.append(node)
            # Primary inputs are startpoints
            elif node.node_type == NodeType.PRIMARY_INPUT:
                startpoints.append(node)

        return startpoints

    def _get_setup_endpoints(self) -> List[TimingNode]:
        """Get endpoints for setup analysis."""
        endpoints = []

        for node in self.edge_manager.get_all_nodes():
            # Data pins of sequential cells are endpoints
            if node.node_type == NodeType.CELL_INPUT and not node.clock_pin:
                # Check if this cell is sequential
                if self._is_sequential_cell(node):
                    endpoints.append(node)
            # Primary outputs are endpoints
            elif node.node_type == NodeType.PRIMARY_OUTPUT:
                endpoints.append(node)

        return endpoints

    def _get_hold_startpoints(self) -> List[TimingNode]:
        """Get startpoints for hold analysis."""
        # Same as setup startpoints
        return self._get_setup_startpoints()

    def _get_hold_endpoints(self) -> List[TimingNode]:
        """Get endpoints for hold analysis."""
        # Same as setup endpoints
        return self._get_setup_endpoints()

    def _is_sequential_cell(self, node: TimingNode) -> bool:
        """Check if node belongs to a sequential cell."""
        if node.cell_type:
            # This would check the library
            # For now, assume DFF and latch are sequential
            seq_keywords = ['DFF', 'LATCH', 'FF', 'REG']
            return any(keyword in node.cell_type.upper() for keyword in seq_keywords)
        return False

    def _is_valid_path(self, start: TimingNode, end: TimingNode,
                       analysis_type: str) -> bool:
        """Check if a path between start and end is valid."""
        # Must be different nodes
        if start == end:
            return False

        # Check if they're in the same clock domain
        if start.clock != end.clock:
            return False

        # Check if path exists
        return self._path_exists(start, end)

    def _path_exists(self, start: TimingNode, end: TimingNode,
                     visited: Set[TimingNode] = None) -> bool:
        """Check if a path exists between start and end using DFS."""
        if visited is None:
            visited = set()

        if start == end:
            return True

        visited.add(start)

        for edge in self.edge_manager.get_outgoing_edges(start):
            next_node = edge.to_node
            if next_node not in visited:
                if self._path_exists(next_node, end, visited):
                    return True

        return False

    def _find_paths(self, start: TimingNode, end: TimingNode,
                    max_paths: int) -> List[Dict[str, Any]]:
        """Find all paths between start and end."""
        paths = []
        self._dfs_find_paths(start, end, [start], set(), paths, max_paths)
        return paths

    def _dfs_find_paths(self, current: TimingNode, target: TimingNode,
                        path: List[TimingNode], visited: Set[TimingNode],
                        paths: List[Dict[str, Any]], max_paths: int):
        """DFS to find all paths."""
        if len(paths) >= max_paths:
            return

        if current == target:
            # Found a path
            path_dict = self._create_path_dict(path)
            paths.append(path_dict)
            return

        visited.add(current)

        for edge in self.edge_manager.get_outgoing_edges(current):
            next_node = edge.to_node
            if next_node not in visited:
                path.append(next_node)
                self._dfs_find_paths(next_node, target, path, visited, paths, max_paths)
                path.pop()

        visited.remove(current)

    def _create_path_dict(self, nodes: List[TimingNode]) -> Dict[str, Any]:
        """Create a path dictionary from a list of nodes."""
        if len(nodes) < 2:
            return {}

        stages = []
        total_delay = 0.0

        for i in range(len(nodes) - 1):
            from_node = nodes[i]
            to_node = nodes[i + 1]

            # Get edge between nodes
            edge = self.edge_manager.get_edge(from_node, to_node)

            if edge:
                # Get delay and slew from edge
                delay = edge.get_delay('rise')  # Use rise as default
                slew = edge.get_output_slew('rise')

                stage = {
                    'type': 'cell' if edge.cell_instance else 'net',
                    'name': f"{from_node.instance}/{from_node.name}" if from_node.instance else from_node.name,
                    'from_pin': from_node.name,
                    'to_pin': to_node.name,
                    'cell_type': edge.cell_type,
                    'instance': edge.cell_instance,
                    'delay': delay,
                    'slew': slew,
                    'transition': 'rise'  # Default
                }

                stages.append(stage)
                total_delay += delay

        # Get first and last nodes
        start_node = nodes[0]
        end_node = nodes[-1]

        # Calculate arrival and required times
        arrival = end_node.get_arrival('rise')
        required = end_node.get_required('rise')
        slack = required - arrival

        path_dict = {
            'from': f"{start_node.instance}/{start_node.name}" if start_node.instance else start_node.name,
            'to': f"{end_node.instance}/{end_node.name}" if end_node.instance else end_node.name,
            'clock': start_node.clock,
            'stages': stages,
            'delay': total_delay,
            'arrival': arrival,
            'required': required,
            'slack': slack,
            'start_type': start_node.node_type.value,
            'end_type': end_node.node_type.value,
            'stage_count': len(stages)
        }

        return path_dict

    def get_worst_setup_paths(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get worst setup paths (most negative slack)."""
        paths = self.get_all_setup_paths(n * 2)  # Get extra, then sort
        paths.sort(key=lambda x: x.get('slack', 0))
        return paths[:n]

    def get_best_setup_paths(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get best setup paths (most positive slack)."""
        paths = self.get_all_setup_paths(n * 2)
        paths.sort(key=lambda x: x.get('slack', 0), reverse=True)
        return paths[:n]

    def get_worst_hold_paths(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get worst hold paths (most negative slack)."""
        paths = self.get_all_hold_paths(n * 2)
        paths.sort(key=lambda x: x.get('slack', 0))
        return paths[:n]

    def get_best_hold_paths(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get best hold paths (most positive slack)."""
        paths = self.get_all_hold_paths(n * 2)
        paths.sort(key=lambda x: x.get('slack', 0), reverse=True)
        return paths[:n]

    def get_paths_by_clock(self, clock_name: str, analysis_type: str = 'setup',
                           max_paths: int = 50) -> List[Dict[str, Any]]:
        """Get paths for a specific clock domain."""
        if analysis_type == 'setup':
            paths = self.get_all_setup_paths(max_paths * 2)
        else:
            paths = self.get_all_hold_paths(max_paths * 2)

        return [p for p in paths if p.get('clock') == clock_name][:max_paths]

    def get_path_statistics(self) -> Dict[str, Any]:
        """Get statistics about extracted paths."""
        setup_paths = self.get_all_setup_paths(1000)
        hold_paths = self.get_all_hold_paths(1000)

        stats = {
            'setup': {
                'count': len(setup_paths),
                'violations': len([p for p in setup_paths if p.get('slack', 0) < 0]),
                'avg_stages': sum(p.get('stage_count', 0) for p in setup_paths) / len(
                    setup_paths) if setup_paths else 0,
                'avg_delay': sum(p.get('delay', 0) for p in setup_paths) / len(setup_paths) if setup_paths else 0
            },
            'hold': {
                'count': len(hold_paths),
                'violations': len([p for p in hold_paths if p.get('slack', 0) < 0]),
                'avg_stages': sum(p.get('stage_count', 0) for p in hold_paths) / len(hold_paths) if hold_paths else 0,
                'avg_delay': sum(p.get('delay', 0) for p in hold_paths) / len(hold_paths) if hold_paths else 0
            }
        }

        return stats

    def clear_cache(self):
        """Clear the path cache."""
        self.path_cache.clear()
        logger.debug("Path cache cleared")