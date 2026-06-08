"""
Timing exceptions for SDC parser.
Handles false paths, multicycle paths, etc.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any
from enum import Enum

from Src.utils.logger import get_logger

logger = get_logger(__name__)


class ExceptionType(Enum):
    """Types of timing exceptions."""
    FALSE_PATH = "false_path"
    MULTICYCLE_PATH = "multicycle_path"
    MAX_DELAY = "max_delay"
    MIN_DELAY = "min_delay"
    INPUT_DELAY = "input_delay"
    OUTPUT_DELAY = "output_delay"
    INPUT_TRANSITION = "input_transition"
    LOAD = "load"
    DRIVING_CELL = "driving_cell"
    CASE_ANALYSIS = "case_analysis"
    DISABLE_TIMING = "disable_timing"


@dataclass
class TimingException:
    """Represents a timing exception."""

    type: ExceptionType
    from_pins: List[str] = field(default_factory=list)
    to_pins: List[str] = field(default_factory=list)
    through_pins: List[str] = field(default_factory=list)

    # Values
    value: Any = None  # Generic value
    delay: Optional[float] = None  # For delay exceptions
    clock: Optional[str] = None  # Associated clock

    # Path attributes
    rise: bool = False
    fall: bool = False
    setup: bool = False
    hold: bool = False
    start: bool = False
    end: bool = False

    # Min/Max
    min_max: str = 'both'  # 'min', 'max', 'both'

    def matches_path(self, from_pin: str, to_pin: str,
                     through_pins: List[str] = None) -> bool:
        """
        Check if exception matches a timing path.

        Args:
            from_pin: Start point
            to_pin: End point
            through_pins: Intermediate points

        Returns:
            True if exception applies to this path
        """
        # Check from pins
        if self.from_pins:
            if from_pin not in self.from_pins:
                return False

        # Check to pins
        if self.to_pins:
            if to_pin not in self.to_pins:
                return False

        # Check through pins
        if self.through_pins and through_pins:
            if not all(p in through_pins for p in self.through_pins):
                return False

        return True

    def get_multiplier(self) -> int:
        """Get multiplier for multicycle path."""
        if self.type == ExceptionType.MULTICYCLE_PATH:
            return int(self.value) if self.value else 1
        return 1

    def get_delay_constraint(self) -> Optional[float]:
        """Get delay constraint value."""
        if self.type in [ExceptionType.MAX_DELAY, ExceptionType.MIN_DELAY,
                         ExceptionType.INPUT_DELAY, ExceptionType.OUTPUT_DELAY]:
            return self.delay
        return None

    def __str__(self) -> str:
        """String representation."""
        base = f"{self.type.value}"
        if self.from_pins:
            base += f" from {self.from_pins}"
        if self.to_pins:
            base += f" to {self.to_pins}"
        if self.value is not None:
            base += f" = {self.value}"
        return base


class ExceptionManager:
    """Manages all timing exceptions in the design."""

    def __init__(self):
        self.exceptions: List[TimingException] = []

        # Categorized for quick access
        self.false_paths: List[TimingException] = []
        self.multicycle_paths: List[TimingException] = []
        self.delay_constraints: List[TimingException] = []
        self.io_delays: List[TimingException] = []
        self.input_transitions: List[TimingException] = []
        self.loads: List[TimingException] = []
        self.driving_cells: List[TimingException] = []
        self.case_analysis: List[TimingException] = []
        self.disabled_timing: List[TimingException] = []

        # Pin-based lookup
        self.from_pin_exceptions: Dict[str, List[TimingException]] = {}
        self.to_pin_exceptions: Dict[str, List[TimingException]] = {}
        self.through_pin_exceptions: Dict[str, List[TimingException]] = {}

    def add_exception(self, exception: TimingException):
        """Add a timing exception."""
        self.exceptions.append(exception)

        # Categorize
        if exception.type == ExceptionType.FALSE_PATH:
            self.false_paths.append(exception)
        elif exception.type == ExceptionType.MULTICYCLE_PATH:
            self.multicycle_paths.append(exception)
        elif exception.type in [ExceptionType.MAX_DELAY, ExceptionType.MIN_DELAY]:
            self.delay_constraints.append(exception)
        elif exception.type in [ExceptionType.INPUT_DELAY, ExceptionType.OUTPUT_DELAY]:
            self.io_delays.append(exception)
        elif exception.type == ExceptionType.INPUT_TRANSITION:
            self.input_transitions.append(exception)
        elif exception.type == ExceptionType.LOAD:
            self.loads.append(exception)
        elif exception.type == ExceptionType.DRIVING_CELL:
            self.driving_cells.append(exception)
        elif exception.type == ExceptionType.CASE_ANALYSIS:
            self.case_analysis.append(exception)
        elif exception.type == ExceptionType.DISABLE_TIMING:
            self.disabled_timing.append(exception)

        # Index by pins
        for pin in exception.from_pins:
            if pin not in self.from_pin_exceptions:
                self.from_pin_exceptions[pin] = []
            self.from_pin_exceptions[pin].append(exception)

        for pin in exception.to_pins:
            if pin not in self.to_pin_exceptions:
                self.to_pin_exceptions[pin] = []
            self.to_pin_exceptions[pin].append(exception)

        for pin in exception.through_pins:
            if pin not in self.through_pin_exceptions:
                self.through_pin_exceptions[pin] = []
            self.through_pin_exceptions[pin].append(exception)

        logger.debug(f"Added exception: {exception}")

    def get_exceptions_for_path(self, from_pin: str, to_pin: str,
                                through_pins: List[str] = None) -> List[TimingException]:
        """
        Get all exceptions that apply to a path.

        Args:
            from_pin: Start point
            to_pin: End point
            through_pins: Intermediate points

        Returns:
            List of applicable exceptions
        """
        applicable = []

        # Check all exceptions
        for exception in self.exceptions:
            if exception.matches_path(from_pin, to_pin, through_pins):
                applicable.append(exception)

        return applicable

    def is_false_path(self, from_pin: str, to_pin: str,
                      through_pins: List[str] = None) -> bool:
        """
        Check if path is a false path.

        Args:
            from_pin: Start point
            to_pin: End point
            through_pins: Intermediate points

        Returns:
            True if path is false
        """
        for exception in self.false_paths:
            if exception.matches_path(from_pin, to_pin, through_pins):
                return True
        return False

    def get_multicycle_setup(self, from_pin: str, to_pin: str,
                             through_pins: List[str] = None) -> int:
        """
        Get multicycle setup value for path.

        Args:
            from_pin: Start point
            to_pin: End point
            through_pins: Intermediate points

        Returns:
            Number of cycles (default 1)
        """
        for exception in self.multicycle_paths:
            if exception.setup and exception.matches_path(from_pin, to_pin, through_pins):
                return exception.get_multiplier()
        return 1

    def get_multicycle_hold(self, from_pin: str, to_pin: str,
                            through_pins: List[str] = None) -> int:
        """
        Get multicycle hold value for path.

        Args:
            from_pin: Start point
            to_pin: End point
            through_pins: Intermediate points

        Returns:
            Number of cycles (default 0)
        """
        for exception in self.multicycle_paths:
            if exception.hold and exception.matches_path(from_pin, to_pin, through_pins):
                return exception.get_multiplier()
        return 0

    def get_max_delay(self, from_pin: str, to_pin: str,
                      through_pins: List[str] = None) -> Optional[float]:
        """
        Get max delay constraint for path.

        Args:
            from_pin: Start point
            to_pin: End point
            through_pins: Intermediate points

        Returns:
            Max delay value or None
        """
        for exception in self.delay_constraints:
            if exception.type == ExceptionType.MAX_DELAY:
                if exception.matches_path(from_pin, to_pin, through_pins):
                    return exception.get_delay_constraint()
        return None

    def get_min_delay(self, from_pin: str, to_pin: str,
                      through_pins: List[str] = None) -> Optional[float]:
        """
        Get min delay constraint for path.

        Args:
            from_pin: Start point
            to_pin: End point
            through_pins: Intermediate points

        Returns:
            Min delay value or None
        """
        for exception in self.delay_constraints:
            if exception.type == ExceptionType.MIN_DELAY:
                if exception.matches_path(from_pin, to_pin, through_pins):
                    return exception.get_delay_constraint()
        return None

    def get_input_delay(self, pin: str, clock: Optional[str] = None,
                        transition: str = 'rise', max_min: str = 'max') -> Optional[float]:
        """
        Get input delay for pin.

        Args:
            pin: Input pin
            clock: Clock name
            transition: 'rise' or 'fall'
            max_min: 'max' or 'min'

        Returns:
            Input delay value or None
        """
        for exception in self.io_delays:
            if exception.type == ExceptionType.INPUT_DELAY:
                if pin in exception.from_pins:
                    # Check clock
                    if exception.clock and clock and exception.clock != clock:
                        continue

                    # Check transition
                    if transition == 'rise' and not exception.rise:
                        if not (exception.fall and not exception.rise):
                            continue
                    if transition == 'fall' and not exception.fall:
                        if not (exception.rise and not exception.fall):
                            continue

                    # Check min/max
                    if max_min == 'max' and exception.min_max == 'min':
                        continue
                    if max_min == 'min' and exception.min_max == 'max':
                        continue

                    return exception.get_delay_constraint()
        return None

    def get_output_delay(self, pin: str, clock: Optional[str] = None,
                         transition: str = 'rise', max_min: str = 'max') -> Optional[float]:
        """
        Get output delay for pin.

        Args:
            pin: Output pin
            clock: Clock name
            transition: 'rise' or 'fall'
            max_min: 'max' or 'min'

        Returns:
            Output delay value or None
        """
        for exception in self.io_delays:
            if exception.type == ExceptionType.OUTPUT_DELAY:
                if pin in exception.from_pins:
                    # Similar filtering as input delay
                    if exception.clock and clock and exception.clock != clock:
                        continue

                    if transition == 'rise' and not exception.rise:
                        continue
                    if transition == 'fall' and not exception.fall:
                        continue

                    if max_min == 'max' and exception.min_max == 'min':
                        continue
                    if max_min == 'min' and exception.min_max == 'max':
                        continue

                    return exception.get_delay_constraint()
        return None

    def get_input_transition(self, pin: str, clock: Optional[str] = None,
                             transition: str = 'rise', max_min: str = 'max') -> Optional[float]:
        """Get input transition for pin."""
        for exception in self.input_transitions:
            if pin in exception.from_pins:
                if exception.clock and clock and exception.clock != clock:
                    continue

                if transition == 'rise' and not exception.rise:
                    continue
                if transition == 'fall' and not exception.fall:
                    continue

                if max_min == 'max' and exception.min_max == 'min':
                    continue
                if max_min == 'min' and exception.min_max == 'max':
                    continue

                return exception.get_delay_constraint()
        return None

    def get_load(self, pin: str) -> Optional[float]:
        """Get capacitive load for pin."""
        for exception in self.loads:
            if pin in exception.from_pins:
                return exception.get_delay_constraint()
        return None

    def is_timing_disabled(self, cell: str, from_pin: Optional[str] = None,
                           to_pin: Optional[str] = None) -> bool:
        """Check if timing is disabled for a cell/pin."""
        for exception in self.disabled_timing:
            if cell in exception.from_pins:
                if from_pin and to_pin:
                    if from_pin in exception.to_pins and to_pin in exception.to_pins:
                        return True
                else:
                    return True
        return False

    def get_case_value(self, pin: str) -> Optional[str]:
        """Get case analysis value for pin."""
        for exception in self.case_analysis:
            if pin in exception.from_pins:
                return exception.value
        return None

    def clear(self):
        """Clear all exceptions."""
        self.exceptions.clear()
        self.false_paths.clear()
        self.multicycle_paths.clear()
        self.delay_constraints.clear()
        self.io_delays.clear()
        self.input_transitions.clear()
        self.loads.clear()
        self.driving_cells.clear()
        self.case_analysis.clear()
        self.disabled_timing.clear()
        self.from_pin_exceptions.clear()
        self.to_pin_exceptions.clear()
        self.through_pin_exceptions.clear()