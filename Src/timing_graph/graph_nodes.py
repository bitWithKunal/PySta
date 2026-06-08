"""
Graph nodes for timing graph.
Defines node types in the timing graph.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any
from enum import Enum

from Src.utils.logger import get_logger

logger = get_logger(__name__)


class NodeType(Enum):
    """Types of nodes in timing graph."""
    PRIMARY_INPUT = "primary_input"
    PRIMARY_OUTPUT = "primary_output"
    CELL_INPUT = "cell_input"
    CELL_OUTPUT = "cell_output"
    CLOCK = "clock"
    CONSTANT = "constant"
    INTERNAL = "internal"


class TimingSense(Enum):
    """Timing sense for edge."""
    POSITIVE_UNATE = "positive_unate"
    NEGATIVE_UNATE = "negative_unate"
    NON_UNATE = "non_unate"


@dataclass
class TimingNode:
    """Base class for timing graph nodes."""

    name: str
    node_type: NodeType
    instance: Optional[str] = None  # Instance name for hierarchical nodes
    cell_type: Optional[str] = None  # Cell type for cell pins

    # Timing data
    arrival_rise: float = 0.0  # Rise arrival time
    arrival_fall: float = 0.0  # Fall arrival time
    required_rise: float = float('inf')  # Rise required time
    required_fall: float = float('inf')  # Fall required time
    slack_rise: float = 0.0  # Rise slack
    slack_fall: float = 0.0  # Fall slack

    # Slew
    slew_rise: float = 0.0  # Rise slew
    slew_fall: float = 0.0  # Fall slew

    # Capacitance
    capacitance: float = 0.0  # Output load capacitance

    # Clock info
    clock: Optional[str] = None  # Associated clock
    clock_pin: bool = False  # Is this a clock pin

    # Additional attributes
    attributes: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if not isinstance(other, TimingNode):
            return False
        return self.name == other.name

    def reset_timing(self):
        """Reset timing values."""
        self.arrival_rise = 0.0
        self.arrival_fall = 0.0
        self.required_rise = float('inf')
        self.required_fall = float('inf')
        self.slack_rise = 0.0
        self.slack_fall = 0.0

    def get_arrival(self, transition: str = 'rise') -> float:
        """Get arrival time for transition."""
        return self.arrival_rise if transition == 'rise' else self.arrival_fall

    def set_arrival(self, time: float, transition: str = 'rise'):
        """Set arrival time for transition."""
        if transition == 'rise':
            self.arrival_rise = time
        else:
            self.arrival_fall = time

    def get_required(self, transition: str = 'rise') -> float:
        """Get required time for transition."""
        return self.required_rise if transition == 'rise' else self.required_fall

    def set_required(self, time: float, transition: str = 'rise'):
        """Set required time for transition."""
        if transition == 'rise':
            self.required_rise = time
        else:
            self.required_fall = time

    def get_slack(self, transition: str = 'rise') -> float:
        """Get slack for transition."""
        return self.slack_rise if transition == 'rise' else self.slack_fall

    def calculate_slack(self):
        """Calculate slack for both transitions."""
        if self.required_rise != float('inf'):
            self.slack_rise = self.required_rise - self.arrival_rise
        if self.required_fall != float('inf'):
            self.slack_fall = self.required_fall - self.arrival_fall

    def get_worst_slack(self) -> float:
        """Get worst (most negative) slack."""
        return min(self.slack_rise, self.slack_fall)

    def get_best_slack(self) -> float:
        """Get best (most positive) slack."""
        return max(self.slack_rise, self.slack_fall)

    def is_startpoint(self) -> bool:
        """Check if node is a start point for timing."""
        return self.node_type in [NodeType.PRIMARY_INPUT, NodeType.CLOCK]

    def is_endpoint(self) -> bool:
        """Check if node is an end point for timing."""
        return self.node_type == NodeType.PRIMARY_OUTPUT

    def is_sequential_input(self) -> bool:
        """Check if node is input to sequential cell."""
        return self.node_type == NodeType.CELL_INPUT and self.clock_pin

    def __str__(self) -> str:
        """String representation."""
        return f"{self.name} ({self.node_type.value})"


@dataclass
class TimingEdge:
    """Edge in timing graph."""

    from_node: TimingNode
    to_node: TimingNode

    # Delay values
    delay_rise: float = 0.0
    delay_fall: float = 0.0

    # Slew values
    output_slew_rise: float = 0.0
    output_slew_fall: float = 0.0

    # Timing sense
    timing_sense: TimingSense = TimingSense.NON_UNATE

    # Cell info
    cell_instance: Optional[str] = None
    cell_type: Optional[str] = None
    arc_type: Optional[str] = None

    # Additional attributes
    is_clock_edge: bool = False
    is_constant: bool = False
    attributes: Dict[str, Any] = field(default_factory=dict)

    def get_delay(self, transition: str = 'rise') -> float:
        """Get delay for transition."""
        return self.delay_rise if transition == 'rise' else self.delay_fall

    def set_delay(self, delay: float, transition: str = 'rise'):
        """Set delay for transition."""
        if transition == 'rise':
            self.delay_rise = delay
        else:
            self.delay_fall = delay

    def get_output_slew(self, transition: str = 'rise') -> float:
        """Get output slew for transition."""
        return self.output_slew_rise if transition == 'rise' else self.output_slew_fall

    def set_output_slew(self, slew: float, transition: str = 'rise'):
        """Set output slew for transition."""
        if transition == 'rise':
            self.output_slew_rise = slew
        else:
            self.output_slew_fall = slew

    def get_propagated_transition(self, input_transition: str) -> str:
        """
        Get output transition based on input and timing sense.

        Args:
            input_transition: 'rise' or 'fall'

        Returns:
            Output transition
        """
        if self.timing_sense == TimingSense.POSITIVE_UNATE:
            return input_transition
        elif self.timing_sense == TimingSense.NEGATIVE_UNATE:
            return 'fall' if input_transition == 'rise' else 'rise'
        else:
            # For non-unate, take worst
            return input_transition

    def __str__(self) -> str:
        """String representation."""
        return f"{self.from_node.name} -> {self.to_node.name}"