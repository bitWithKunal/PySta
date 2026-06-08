"""
Cell library data structures for Liberty parser.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

from Src.utils.logger import get_logger

logger = get_logger(__name__)


class TimingSense(Enum):
    """Timing sense types."""
    POSITIVE_UNATE = "positive_unate"
    NEGATIVE_UNATE = "negative_unate"
    NON_UNATE = "non_unate"


class TimingType(Enum):
    """Timing arc types."""
    COMBINATIONAL = "combinational"
    RISING_EDGE = "rising_edge"
    FALLING_EDGE = "falling_edge"
    SETUP_RISING = "setup_rising"
    SETUP_FALLING = "setup_falling"
    HOLD_RISING = "hold_rising"
    HOLD_FALLING = "hold_falling"


@dataclass
class Pin:
    """Represents a cell pin."""
    name: str
    direction: str  # "input", "output", "inout"
    capacitance: float = 0.0  # in Farads
    is_clock: bool = False
    related_pins: List[str] = field(default_factory=list)
    function: Optional[str] = None
    internal_pin: Optional[str] = None

    def __post_init__(self):
        if self.related_pins is None:
            self.related_pins = []


@dataclass
class TimingArc:
    """Represents a timing arc between pins."""
    from_pin: str
    to_pin: str
    timing_sense: TimingSense
    timing_type: TimingType

    # Delay model coefficients
    rise_delay_coeff: Dict[str, float] = field(default_factory=dict)
    fall_delay_coeff: Dict[str, float] = field(default_factory=dict)

    # Slew model coefficients
    rise_slew_coeff: Dict[str, float] = field(default_factory=dict)
    fall_slew_coeff: Dict[str, float] = field(default_factory=dict)

    # Constraint values (for timing checks)
    setup_time: Optional[float] = None
    hold_time: Optional[float] = None
    min_period: Optional[float] = None

    # Operating conditions
    when_condition: Optional[str] = None
    related_output_pin: Optional[str] = None

    def get_delay(self, input_slew: float, output_load: float,
                  rise: bool = True) -> float:
        """
        Calculate delay using non-linear delay model.

        Args:
            input_slew: Input transition time in seconds
            output_load: Output load capacitance in Farads
            rise: True for rise delay, False for fall delay

        Returns:
            Cell delay in seconds
        """
        coeff = self.rise_delay_coeff if rise else self.fall_delay_coeff

        if not coeff:
            # Simple linear model as fallback
            return (input_slew * 0.5 + output_load * 1000) * 1e-12

        # Simplified NLDM calculation (can be enhanced)
        # delay = a0 + a1*load + a2*slew + a3*load*slew
        delay = (coeff.get('a0', 0) +
                 coeff.get('a1', 0) * output_load * 1e15 +  # Convert to fF
                 coeff.get('a2', 0) * input_slew * 1e12 +  # Convert to ps
                 coeff.get('a3', 0) * output_load * 1e15 * input_slew * 1e12)

        return max(delay * 1e-12, 1e-15)  # Convert to seconds, ensure > 0


@dataclass
class Cell:
    """Represents a standard cell."""
    name: str
    area: float = 0.0
    is_sequential: bool = False
    is_macro: bool = False

    # Pins and timing arcs
    pins: Dict[str, Pin] = field(default_factory=dict)
    timing_arcs: List[TimingArc] = field(default_factory=list)

    # Leakage and power
    leakage_power: float = 0.0
    internal_power: Dict[str, float] = field(default_factory=dict)

    # Operating conditions
    operating_conditions: Optional[str] = None

    def add_pin(self, pin: Pin):
        """Add a pin to the cell."""
        self.pins[pin.name] = pin

    def get_pin(self, pin_name: str) -> Optional[Pin]:
        """Get pin by name."""
        return self.pins.get(pin_name)

    def get_timing_arcs(self, from_pin: Optional[str] = None,
                        to_pin: Optional[str] = None) -> List[TimingArc]:
        """
        Get timing arcs matching the given pins.

        Args:
            from_pin: Source pin name (optional)
            to_pin: Destination pin name (optional)

        Returns:
            List of matching timing arcs
        """
        arcs = self.timing_arcs

        if from_pin:
            arcs = [a for a in arcs if a.from_pin == from_pin]
        if to_pin:
            arcs = [a for a in arcs if a.to_pin == to_pin]

        return arcs


class CellLibrary:
    """Represents a complete Liberty library."""

    def __init__(self, name: str = "default"):
        self.name: str = name
        self.cells: Dict[str, Cell] = {}

        # Library attributes
        self.delay_model: str = "table_lookup"
        self.time_unit: str = "1ns"
        self.voltage_unit: str = "1V"
        self.current_unit: str = "1mA"
        self.power_unit: str = "1mW"
        self.capacitance_unit: str = "1pF"

        # Operating conditions
        self.nominal_process: float = 1.0
        self.nominal_temperature: float = 25.0
        self.nominal_voltage: float = 1.0

        # Default values
        self.default_leakage_power_density: float = 0.0
        self.default_max_transition: float = 1e-9
        self.default_cell_leakage_power: float = 0.0

    def add_cell(self, cell: Cell):
        """Add a cell to the library."""
        self.cells[cell.name] = cell

    def get_cell(self, cell_name: str) -> Optional[Cell]:
        """Get cell by name."""
        return self.cells.get(cell_name)

    def has_cell(self, cell_name: str) -> bool:
        """Check if cell exists in library."""
        return cell_name in self.cells

    def get_all_cells(self) -> List[Cell]:
        """Get all cells in library."""
        return list(self.cells.values())

    def get_cells_by_type(self, sequential: bool) -> List[Cell]:
        """
        Get cells filtered by type.

        Args:
            sequential: True for sequential cells, False for combinational

        Returns:
            List of matching cells
        """
        return [c for c in self.cells.values() if c.is_sequential == sequential]

    def get_flops(self) -> List[Cell]:
        """Get all flip-flops in library."""
        return [c for c in self.cells.values()
                if c.is_sequential and not c.is_macro]

    def get_latches(self) -> List[Cell]:
        """Get all latches in library."""
        # In Liberty, latches are sequential but with special timing
        return [c for c in self.cells.values()
                if c.is_sequential and any(
                "latch" in pin.function.lower()
                for pin in c.pins.values() if pin.function
            )]