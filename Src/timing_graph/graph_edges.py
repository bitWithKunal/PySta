"""
Graph edges for timing graph.
Manages edges between nodes.
"""

from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

from Src.timing_graph.graph_nodes import TimingNode, TimingEdge, TimingSense
from Src.utils.logger import get_logger

logger = get_logger(__name__)


class EdgeManager:
    """Manages edges in timing graph."""

    def __init__(self):
        # Forward edges: from_node -> list of edges
        self.forward_edges: Dict[TimingNode, List[TimingEdge]] = defaultdict(list)

        # Backward edges: to_node -> list of edges
        self.backward_edges: Dict[TimingNode, List[TimingEdge]] = defaultdict(list)

        # Edge lookup by node pair
        self.edge_map: Dict[Tuple[TimingNode, TimingNode], TimingEdge] = {}

        # Fan-in/Fan-out counts
        self.fan_in: Dict[TimingNode, int] = defaultdict(int)
        self.fan_out: Dict[TimingNode, int] = defaultdict(int)

    def add_edge(self, edge: TimingEdge):
        """
        Add an edge to the graph.

        Args:
            edge: TimingEdge to add
        """
        from_node = edge.from_node
        to_node = edge.to_node

        # Add to forward edges
        self.forward_edges[from_node].append(edge)

        # Add to backward edges
        self.backward_edges[to_node].append(edge)

        # Add to map
        self.edge_map[(from_node, to_node)] = edge

        # Update counts
        self.fan_out[from_node] += 1
        self.fan_in[to_node] += 1

    def remove_edge(self, from_node: TimingNode, to_node: TimingNode):
        """
        Remove an edge from the graph.

        Args:
            from_node: Source node
            to_node: Destination node
        """
        key = (from_node, to_node)
        if key in self.edge_map:
            edge = self.edge_map[key]

            # Remove from lists
            self.forward_edges[from_node].remove(edge)
            self.backward_edges[to_node].remove(edge)

            # Remove from map
            del self.edge_map[key]

            # Update counts
            self.fan_out[from_node] -= 1
            self.fan_in[to_node] -= 1

    def get_edge(self, from_node: TimingNode, to_node: TimingNode) -> Optional[TimingEdge]:
        """Get edge between nodes."""
        return self.edge_map.get((from_node, to_node))

    def get_outgoing_edges(self, node: TimingNode) -> List[TimingEdge]:
        """Get all outgoing edges from node."""
        return self.forward_edges.get(node, [])

    def get_incoming_edges(self, node: TimingNode) -> List[TimingEdge]:
        """Get all incoming edges to node."""
        return self.backward_edges.get(node, [])

    def get_fan_in(self, node: TimingNode) -> int:
        """Get fan-in count for node."""
        return self.fan_in.get(node, 0)

    def get_fan_out(self, node: TimingNode) -> int:
        """Get fan-out count for node."""
        return self.fan_out.get(node, 0)

    def has_cycle(self) -> bool:
        """Check if graph has cycles."""
        visited = set()
        rec_stack = set()

        def dfs(node: TimingNode) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for edge in self.get_outgoing_edges(node):
                next_node = edge.to_node
                if next_node not in visited:
                    if dfs(next_node):
                        return True
                elif next_node in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        # Check all nodes
        all_nodes = set(self.forward_edges.keys()) | set(self.backward_edges.keys())
        for node in all_nodes:
            if node not in visited:
                if dfs(node):
                    return True

        return False

    def get_topological_order(self) -> List[TimingNode]:
        """
        Get nodes in topological order.

        Returns:
            List of nodes in topological order
        """
        # Count incoming edges
        in_degree = {}
        all_nodes = set(self.forward_edges.keys()) | set(self.backward_edges.keys())

        for node in all_nodes:
            in_degree[node] = self.get_fan_in(node)

        # Initialize queue with nodes having 0 in-degree
        queue = [node for node in all_nodes if in_degree[node] == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            for edge in self.get_outgoing_edges(node):
                next_node = edge.to_node
                in_degree[next_node] -= 1
                if in_degree[next_node] == 0:
                    queue.append(next_node)

        # Check if cycle exists
        if len(result) != len(all_nodes):
            logger.warning("Graph has cycle, topological sort incomplete")

        return result

    def get_reverse_topological_order(self) -> List[TimingNode]:
        """Get nodes in reverse topological order."""
        topo = self.get_topological_order()
        return list(reversed(topo))

    def get_predecessors(self, node: TimingNode) -> List[TimingNode]:
        """Get all predecessor nodes."""
        return [edge.from_node for edge in self.get_incoming_edges(node)]

    def get_successors(self, node: TimingNode) -> List[TimingNode]:
        """Get all successor nodes."""
        return [edge.to_node for edge in self.get_outgoing_edges(node)]

    def get_all_nodes(self) -> Set[TimingNode]:
        """Get all nodes in graph."""
        return set(self.forward_edges.keys()) | set(self.backward_edges.keys())

    def get_all_edges(self) -> List[TimingEdge]:
        """Get all edges in graph."""
        return list(self.edge_map.values())

    def get_num_nodes(self) -> int:
        """Get number of nodes."""
        return len(self.get_all_nodes())

    def get_num_edges(self) -> int:
        """Get number of edges."""
        return len(self.edge_map)

    def clear(self):
        """Clear all edges."""
        self.forward_edges.clear()
        self.backward_edges.clear()
        self.edge_map.clear()
        self.fan_in.clear()
        self.fan_out.clear()

    def merge(self, other: 'EdgeManager'):
        """Merge another edge manager into this one."""
        for edge in other.get_all_edges():
            self.add_edge(edge)

    def get_edges_from_instance(self, instance_name: str) -> List[TimingEdge]:
        """Get all edges from a specific instance."""
        edges = []
        for edge in self.get_all_edges():
            if edge.cell_instance == instance_name:
                edges.append(edge)
        return edges

    def get_edges_to_instance(self, instance_name: str) -> List[TimingEdge]:
        """Get all edges to a specific instance."""
        edges = []
        for edge in self.get_all_edges():
            if edge.cell_instance == instance_name:
                edges.append(edge)
        return edges

    def get_node_by_name(self, name: str) -> Optional[TimingNode]:
        """Get node by its name."""
        for node in self.get_all_nodes():
            if node.name == name:
                return node
        return None

    def print_graph_stats(self):
        """Print graph statistics."""
        logger.info(f"Graph stats: {self.get_num_nodes()} nodes, {self.get_num_edges()} edges")

        # Fan-in distribution
        fan_in_dist = defaultdict(int)
        for node, count in self.fan_in.items():
            fan_in_dist[count] += 1

        # Fan-out distribution
        fan_out_dist = defaultdict(int)
        for node, count in self.fan_out.items():
            fan_out_dist[count] += 1

        logger.debug(f"Fan-in distribution: {dict(fan_in_dist)}")
        logger.debug(f"Fan-out distribution: {dict(fan_out_dist)}")

        # Check for cycles
        if self.has_cycle():
            logger.warning("Graph contains cycles!")
        else:
            logger.info("Graph is acyclic")