"""
Clock constraints for SDC parser.
Defines clock objects and constraints.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

from Src.utils.logger import get_logger
from Src.utils.time_utils import TimeUtils

logger = get_logger(__name__)


class ClockType(Enum):
    """Types of clocks."""
    PRIMARY = "primary"
    GENERATED = "generated"
    VIRTUAL = "virtual"


@dataclass
class Clock:
    """Represents a clock in the design."""

    name: str
    period: float  # in seconds
    waveform: Tuple[float, float]  # (rise_time, fall_time) in seconds
    sources: List[str] = field(default_factory=list)  # source pins/ports
    type: ClockType = ClockType.PRIMARY
    is_generated: bool = False
    master_clock: Optional['Clock'] = None
    divide_by: Optional[int] = None
    multiply_by: Optional[int] = None

    # Clock attributes
    latency: float = 0.0  # network latency
    latency_source: bool = False  # source latency
    transition_rise: Optional[float] = None
    transition_fall: Optional[float] = None
    uncertainty: float = 0.0

    def get_edge_times(self, edge_type: str = 'rise', num_edges: int = 2) -> List[float]:
        """
        Get clock edge times.

        Args:
            edge_type: 'rise' or 'fall'
            num_edges: Number of edges to return

        Returns:
            List of edge times
        """
        times = []
        base_time = self.waveform[0] if edge_type == 'rise' else self.waveform[1]

        for i in range(num_edges):
            times.append(base_time + i * self.period)

        return times

    def get_period(self) -> float:
        """Get clock period considering generated clock factors."""
        if self.is_generated and self.master_clock:
            period = self.master_clock.period
            if self.divide_by:
                period *= self.divide_by
            if self.multiply_by:
                period /= self.multiply_by
            return period
        return self.period

    def get_waveform(self) -> Tuple[float, float]:
        """Get clock waveform considering generated clock factors."""
        if self.is_generated and self.master_clock:
            rise, fall = self.master_clock.waveform
            if self.divide_by:
                # For divide, edges are spaced further
                rise *= self.divide_by
                fall *= self.divide_by
            if self.multiply_by:
                # For multiply, edges are closer
                rise /= self.multiply_by
                fall /= self.multiply_by
            return (rise, fall)
        return self.waveform

    def __str__(self) -> str:
        """String representation."""
        period_str = TimeUtils.format_time(self.period)
        return f"Clock {self.name}: period={period_str}, waveform={self.waveform}"


@dataclass
class ClockGroup:
    """Group of related clocks."""
    name: str
    clocks: List[Clock] = field(default_factory=list)
    asynchronous: bool = False
    logically_exclusive: bool = False
    physically_exclusive: bool = False


class ClockConstraints:
    """Manages all clock constraints in the design."""

    def __init__(self):
        self.clocks: Dict[str, Clock] = {}
        self.clock_groups: Dict[str, ClockGroup] = {}
        self.generated_clocks: Dict[str, Clock] = {}
        self.virtual_clocks: Dict[str, Clock] = {}

        # Clock uncertainties
        self.uncertainties: List[Dict[str, Any]] = []

        # Clock latency
        self.latencies: List[Dict[str, Any]] = []

    def add_clock(self, clock: Clock):
        """Add a clock to the constraints."""
        if clock.name in self.clocks:
            logger.warning(f"Clock {clock.name} already exists. Overwriting.")

        self.clocks[clock.name] = clock

        if clock.is_generated:
            self.generated_clocks[clock.name] = clock
        elif clock.type == ClockType.VIRTUAL:
            self.virtual_clocks[clock.name] = clock

    def get_clock_by_name(self, name: str) -> Optional[Clock]:
        """Get clock by name."""
        return self.clocks.get(name)

    def get_clock_by_source(self, source: str) -> Optional[Clock]:
        """Find clock that has the given source."""
        for clock in self.clocks.values():
            if source in clock.sources:
                return clock
        return None

    def get_clocks_on_pin(self, pin_name: str) -> List[Clock]:
        """Get all clocks that are defined on the given pin."""
        clocks = []
        for clock in self.clocks.values():
            if pin_name in clock.sources:
                clocks.append(clock)
        return clocks

    def add_uncertainty(self, from_clock: Optional[str], to_clock: Optional[str],
                        uncertainty: float, type: str = 'setup'):
        """Add clock uncertainty."""
        self.uncertainties.append({
            'from_clock': from_clock,
            'to_clock': to_clock,
            'uncertainty': uncertainty,
            'type': type
        })

    def get_uncertainty(self, from_clock: Optional[Clock], to_clock: Optional[Clock],
                        type: str = 'setup') -> float:
        """
        Get uncertainty between two clocks.

        Args:
            from_clock: Source clock
            to_clock: Destination clock
            type: 'setup' or 'hold'

        Returns:
            Uncertainty value in seconds
        """
        from_name = from_clock.name if from_clock else None
        to_name = to_clock.name if to_clock else None

        # Find matching uncertainty
        for unc in self.uncertainties:
            if unc['type'] != type and unc['type'] != 'both':
                continue

            from_match = (unc['from_clock'] is None or
                          unc['from_clock'] == from_name)
            to_match = (unc['to_clock'] is None or
                        unc['to_clock'] == to_name)

            if from_match and to_match:
                return unc['uncertainty']

        # Default uncertainty
        return 0.0

    def add_clock_group(self, group: ClockGroup):
        """Add a clock group."""
        self.clock_groups[group.name] = group

    def are_clocks_related(self, clock1: Clock, clock2: Clock) -> bool:
        """
        Check if two clocks are related (same or generated from same master).

        Args:
            clock1: First clock
            clock2: Second clock

        Returns:
            True if clocks are related
        """
        if clock1.name == clock2.name:
            return True

        # Check generated clock relationship
        if clock1.is_generated and clock2.is_generated:
            if clock1.master_clock and clock2.master_clock:
                return clock1.master_clock.name == clock2.master_clock.name

        # Check master-generated relationship
        if clock1.is_generated:
            return clock1.master_clock and clock1.master_clock.name == clock2.name
        if clock2.is_generated:
            return clock2.master_clock and clock2.master_clock.name == clock1.name

        return False

    def get_all_clocks(self) -> List[Clock]:
        """Get all clocks."""
        return list(self.clocks.values())

    def get_primary_clocks(self) -> List[Clock]:
        """Get all primary clocks."""
        return [c for c in self.clocks.values()
                if not c.is_generated and c.type != ClockType.VIRTUAL]

    def get_generated_clocks(self) -> List[Clock]:
        """Get all generated clocks."""
        return list(self.generated_clocks.values())

    def get_virtual_clocks(self) -> List[Clock]:
        """Get all virtual clocks."""
        return list(self.virtual_clocks.values())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for reporting."""
        return {
            'clocks': [
                {
                    'name': c.name,
                    'period': c.period,
                    'waveform': c.waveform,
                    'sources': c.sources,
                    'type': c.type.value,
                    'is_generated': c.is_generated,
                    'master_clock': c.master_clock.name if c.master_clock else None,
                    'divide_by': c.divide_by,
                    'multiply_by': c.multiply_by,
                    'latency': c.latency
                }
                for c in self.clocks.values()
            ],
            'uncertainties': self.uncertainties
        }