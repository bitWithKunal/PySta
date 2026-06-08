"""
Time utility functions for PySTA.
Handles time unit conversions and formatting.
"""

import re
from typing import Union, Optional
from enum import Enum

from Src.utils.logger import get_logger

logger = get_logger(__name__)


class TimeUnit(Enum):
    """Time units supported in STA."""
    FS = 1e-15  # femtosecond
    PS = 1e-12  # picosecond
    NS = 1e-9  # nanosecond
    US = 1e-6  # microsecond
    MS = 1e-3  # millisecond
    S = 1  # second

    @classmethod
    def from_string(cls, unit_str: str):
        """Convert string to TimeUnit."""
        unit_map = {
            'fs': cls.FS,
            'ps': cls.PS,
            'ns': cls.NS,
            'us': cls.US,
            'ms': cls.MS,
            's': cls.S
        }
        return unit_map.get(unit_str.lower(), cls.NS)

    def to_string(self) -> str:
        """Convert TimeUnit to string."""
        unit_map = {
            self.FS: 'fs',
            self.PS: 'ps',
            self.NS: 'ns',
            self.US: 'us',
            self.MS: 'ms',
            self.S: 's'
        }
        return unit_map.get(self, 'ns')


class TimeUtils:
    """Utility class for time operations."""

    DEFAULT_UNIT = TimeUnit.NS
    DISPLAY_PRECISION = 3

    @staticmethod
    def parse_time_string(time_str: str) -> float:
        """
        Parse time string with unit to seconds.

        Args:
            time_str: Time string (e.g., "1.2ns", "5ps", "0.1")

        Returns:
            Time in seconds
        """
        if not time_str:
            return 0.0

        time_str = str(time_str).strip().lower()

        # Extract number and unit
        match = re.match(r'^([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*([a-z]*)$', time_str)
        if not match:
            logger.warning(f"Could not parse time string: {time_str}")
            return 0.0

        value, unit = match.groups()
        value = float(value)

        if not unit:
            return value * TimeUtils.DEFAULT_UNIT.value

        # Convert to seconds
        unit_enum = TimeUnit.from_string(unit)
        return value * unit_enum.value

    @staticmethod
    def format_time(time_sec: float, unit: Optional[TimeUnit] = None,
                    precision: Optional[int] = None) -> str:
        """
        Format time in seconds to readable string.

        Args:
            time_sec: Time in seconds
            unit: Desired output unit (auto if None)
            precision: Number of decimal places

        Returns:
            Formatted time string
        """
        if time_sec is None:
            return "N/A"

        if unit is None:
            # Auto-select unit
            abs_time = abs(time_sec)
            if abs_time >= 1.0:
                unit = TimeUnit.S
            elif abs_time >= 1e-3:
                unit = TimeUnit.MS
            elif abs_time >= 1e-6:
                unit = TimeUnit.US
            elif abs_time >= 1e-9:
                unit = TimeUnit.NS
            elif abs_time >= 1e-12:
                unit = TimeUnit.PS
            else:
                unit = TimeUnit.FS

        # Convert to selected unit
        converted = time_sec / unit.value

        precision = precision or TimeUtils.DISPLAY_PRECISION
        return f"{converted:.{precision}f} {unit.to_string()}"

    @staticmethod
    def format_slack(slack_sec: float) -> str:
        """
        Format slack with color indicator.

        Args:
            slack_sec: Slack in seconds

        Returns:
            Formatted slack string
        """
        formatted = TimeUtils.format_time(slack_sec)

        if slack_sec < 0:
            return f"VIOLATION ({formatted})"
        elif slack_sec < 100e-12:  # 100ps
            return f"MARGINAL ({formatted})"
        else:
            return f"MET ({formatted})"

    @staticmethod
    def seconds_to_picoseconds(seconds: float) -> float:
        """Convert seconds to picoseconds."""
        return seconds * 1e12

    @staticmethod
    def picoseconds_to_seconds(picoseconds: float) -> float:
        """Convert picoseconds to seconds."""
        return picoseconds * 1e-12