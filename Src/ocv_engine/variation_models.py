"""
Variation models for OCV engine.
Models process, voltage, temperature variations.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import random
import math

from Src.utils.logger import get_logger

logger = get_logger(__name__)


class VariationType(Enum):
    """Types of variations."""
    PROCESS = "process"
    VOLTAGE = "voltage"
    TEMPERATURE = "temperature"
    RANDOM = "random"
    SYSTEMATIC = "systematic"


class VariationCorner(Enum):
    """Process corners."""
    TYPICAL = "typical"
    BEST = "best"
    WORST = "worst"
    FAST = "fast"
    SLOW = "slow"


@dataclass
class VariationParameters:
    """Parameters for variation modeling."""

    type: VariationType
    mean: float = 1.0
    sigma: float = 0.05
    min_val: float = 0.8
    max_val: float = 1.2

    # Temperature coefficient (ppm/°C)
    temp_coeff: float = 1000

    # Voltage coefficient (%/V)
    voltage_coeff: float = 10.0

    # Spatial correlation distance (um)
    correlation_distance: float = 100

    def get_variation(self, sigma_level: float = 3.0) -> float:
        """
        Get variation value at given sigma level.

        Args:
            sigma_level: Number of sigmas

        Returns:
            Variation factor
        """
        variation = self.mean + sigma_level * self.sigma
        return max(self.min_val, min(self.max_val, variation))


class VariationModel:
    """Models process, voltage, and temperature variations."""

    def __init__(self):
        # Default parameters
        self.parameters: Dict[VariationType, VariationParameters] = {}
        self._setup_defaults()

        # Current corner
        self.corner = VariationCorner.TYPICAL

        # Location-based variations
        self.location_variations: Dict[str, float] = {}

        logger.info("Variation model initialized")

    def _setup_defaults(self):
        """Setup default variation parameters."""
        self.parameters[VariationType.PROCESS] = VariationParameters(
            type=VariationType.PROCESS,
            mean=1.0,
            sigma=0.03,
            min_val=0.85,
            max_val=1.15
        )

        self.parameters[VariationType.VOLTAGE] = VariationParameters(
            type=VariationType.VOLTAGE,
            mean=1.0,
            sigma=0.02,
            min_val=0.9,
            max_val=1.1,
            voltage_coeff=10.0
        )

        self.parameters[VariationType.TEMPERATURE] = VariationParameters(
            type=VariationType.TEMPERATURE,
            mean=1.0,
            sigma=0.01,
            min_val=0.95,
            max_val=1.05,
            temp_coeff=1000
        )

        self.parameters[VariationType.RANDOM] = VariationParameters(
            type=VariationType.RANDOM,
            mean=1.0,
            sigma=0.02,
            min_val=0.96,
            max_val=1.04
        )

        self.parameters[VariationType.SYSTEMATIC] = VariationParameters(
            type=VariationType.SYSTEMATIC,
            mean=1.0,
            sigma=0.015,
            min_val=0.97,
            max_val=1.03,
            correlation_distance=100
        )

    def set_corner(self, corner: VariationCorner):
        """Set process corner."""
        self.corner = corner
        logger.debug(f"Set variation corner to {corner.value}")

    def get_variation(self, cell_type: str = "",
                      location: Optional[Tuple[float, float]] = None) -> float:
        """
        Get total variation factor for a cell.

        Args:
            cell_type: Type of cell (for cell-specific variation)
            location: Physical location (x, y) in microns

        Returns:
            Combined variation factor
        """
        variation = 1.0

        # Process variation
        proc_var = self._get_process_variation(cell_type)
        variation *= proc_var

        # Voltage variation
        volt_var = self._get_voltage_variation(location)
        variation *= volt_var

        # Temperature variation
        temp_var = self._get_temperature_variation(location)
        variation *= temp_var

        # Systematic variation
        sys_var = self._get_systematic_variation(location)
        variation *= sys_var

        return variation

    def _get_process_variation(self, cell_type: str) -> float:
        """
        Get process variation factor.

        Args:
            cell_type: Type of cell

        Returns:
            Process variation factor
        """
        params = self.parameters[VariationType.PROCESS]

        # Corner-based variation
        if self.corner == VariationCorner.TYPICAL:
            return params.mean
        elif self.corner == VariationCorner.BEST:
            return params.min_val
        elif self.corner == VariationCorner.WORST:
            return params.max_val
        elif self.corner == VariationCorner.FAST:
            return params.mean - params.sigma
        elif self.corner == VariationCorner.SLOW:
            return params.mean + params.sigma

        return params.mean

    def _get_voltage_variation(self, location: Optional[Tuple[float, float]]) -> float:
        """
        Get voltage variation factor.

        Args:
            location: Physical location

        Returns:
            Voltage variation factor
        """
        params = self.parameters[VariationType.VOLTAGE]

        # Voltage variation depends on location (IR drop)
        if location:
            # Simulate IR drop based on distance from center
            x, y = location
            distance = math.sqrt(x * x + y * y)
            drop = distance * 0.001  # 1mV per micron
            variation = 1.0 - drop * (params.voltage_coeff / 100.0)
            return max(params.min_val, min(params.max_val, variation))

        return params.mean

    def _get_temperature_variation(self, location: Optional[Tuple[float, float]]) -> float:
        """
        Get temperature variation factor.

        Args:
            location: Physical location

        Returns:
            Temperature variation factor
        """
        params = self.parameters[VariationType.TEMPERATURE]

        # Temperature varies with power density
        if location:
            # Simulate temperature gradient
            x, y = location
            temp_rise = (abs(x) + abs(y)) * 0.01  # 0.01°C per micron
            variation = 1.0 + temp_rise * (params.temp_coeff / 1e6)
            return max(params.min_val, min(params.max_val, variation))

        return params.mean

    def _get_systematic_variation(self, location: Optional[Tuple[float, float]]) -> float:
        """
        Get systematic variation factor.

        Args:
            location: Physical location

        Returns:
            Systematic variation factor
        """
        params = self.parameters[VariationType.SYSTEMATIC]

        if location and location in self.location_variations:
            return self.location_variations[location]

        # Generate location-based variation
        if location:
            # Use location hash for deterministic variation
            x, y = location
            hash_val = (hash((int(x * 10), int(y * 10))) % 1000) / 1000.0
            variation = params.mean + (hash_val - 0.5) * 2 * params.sigma
            self.location_variations[location] = variation
            return variation

        return params.mean

    def get_random_variation(self) -> float:
        """
        Get random variation factor.

        Returns:
            Random variation factor
        """
        params = self.parameters[VariationType.RANDOM]

        # Generate random variation
        variation = random.gauss(params.mean, params.sigma)
        return max(params.min_val, min(params.max_val, variation))

    def get_spatial_variation(self, location1: Tuple[float, float],
                              location2: Tuple[float, float]) -> float:
        """
        Get spatial correlation between two locations.

        Args:
            location1: First location (x, y)
            location2: Second location (x, y)

        Returns:
            Correlation coefficient (0-1)
        """
        params = self.parameters[VariationType.SYSTEMATIC]

        # Calculate distance
        x1, y1 = location1
        x2, y2 = location2
        distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

        # Exponential correlation model
        correlation = math.exp(-distance / params.correlation_distance)

        return correlation

    def apply_voltage_scaling(self, delay: float, voltage: float,
                              nominal_voltage: float = 1.0) -> float:
        """
        Apply voltage scaling to delay.

        Args:
            delay: Original delay
            voltage: Operating voltage
            nominal_voltage: Nominal voltage

        Returns:
            Voltage-scaled delay
        """
        # Delay inversely proportional to voltage (simplified)
        voltage_ratio = nominal_voltage / voltage
        return delay * voltage_ratio

    def apply_temperature_scaling(self, delay: float, temperature: float,
                                  nominal_temperature: float = 25.0) -> float:
        """
        Apply temperature scaling to delay.

        Args:
            delay: Original delay
            temperature: Operating temperature (°C)
            nominal_temperature: Nominal temperature (°C)

        Returns:
            Temperature-scaled delay
        """
        params = self.parameters[VariationType.TEMPERATURE]

        # Delay increases with temperature
        temp_diff = temperature - nominal_temperature
        scaling = 1.0 + temp_diff * (params.temp_coeff / 1e6)

        return delay * scaling

    def get_variation_budget(self, cell_type: str = "") -> Dict[str, float]:
        """
        Get variation budget breakdown.

        Args:
            cell_type: Type of cell

        Returns:
            Dictionary of variation contributions
        """
        budget = {}

        for var_type, params in self.parameters.items():
            if var_type == VariationType.PROCESS:
                budget['process'] = params.get_variation(3) - params.mean
            elif var_type == VariationType.VOLTAGE:
                budget['voltage'] = params.get_variation(3) - params.mean
            elif var_type == VariationType.TEMPERATURE:
                budget['temperature'] = params.get_variation(3) - params.mean
            elif var_type == VariationType.RANDOM:
                budget['random'] = params.sigma * 3
            elif var_type == VariationType.SYSTEMATIC:
                budget['systematic'] = params.sigma * 2

        return budget

    def get_summary(self) -> str:
        """Get variation model summary."""
        lines = []
        lines.append("=" * 60)
        lines.append("Variation Model Summary")
        lines.append("=" * 60)
        lines.append(f"Current corner: {self.corner.value}")
        lines.append("")

        lines.append("Parameters:")
        for var_type, params in self.parameters.items():
            lines.append(f"  {var_type.value}:")
            lines.append(f"    mean: {params.mean:.3f}")
            lines.append(f"    sigma: {params.sigma:.3f}")
            lines.append(f"    range: [{params.min_val:.3f}, {params.max_val:.3f}]")

        lines.append("")
        lines.append("Variation Budget (3σ):")
        budget = self.get_variation_budget()
        for name, value in budget.items():
            lines.append(f"  {name}: {value * 100:.1f}%")

        lines.append("=" * 60)

        return "\n".join(lines)