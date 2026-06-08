"""
Derate manager for OCV engine.
Handles derating factors for on-chip variation analysis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

from Src.utils.logger import get_logger

logger = get_logger(__name__)


class DerateType(Enum):
    """Types of derating."""
    CELL = "cell"
    NET = "net"
    CLOCK = "clock"
    DATA = "data"
    EARLY = "early"
    LATE = "late"


class DerateStage(Enum):
    """Stages for derating."""
    SETUP = "setup"
    HOLD = "hold"
    BOTH = "both"


@dataclass
class DerateFactor:
    """Derating factor for a specific condition."""

    type: DerateType
    stage: DerateStage
    early_factor: float = 1.0
    late_factor: float = 1.0
    condition: Optional[str] = None
    cell_types: List[str] = field(default_factory=list)

    def apply_early(self, value: float) -> float:
        """Apply early path derating."""
        return value * self.early_factor

    def apply_late(self, value: float) -> float:
        """Apply late path derating."""
        return value * self.late_factor

    def applies_to_cell(self, cell_type: str) -> bool:
        """Check if derate applies to cell type."""
        if not self.cell_types:
            return True
        return cell_type in self.cell_types

    def __str__(self) -> str:
        """String representation."""
        return (f"Derate({self.type.value}, early={self.early_factor:.3f}, "
                f"late={self.late_factor:.3f})")


class DerateManager:
    """Manages derating factors for OCV analysis."""

    def __init__(self):
        self.derate_factors: List[DerateFactor] = []

        # Default derate factors
        self._setup_defaults()

    def _setup_defaults(self):
        """Setup default derating factors."""
        # Cell derating
        self.add_derate(DerateFactor(
            type=DerateType.CELL,
            stage=DerateStage.BOTH,
            early_factor=0.95,
            late_factor=1.05
        ))

        # Net derating
        self.add_derate(DerateFactor(
            type=DerateType.NET,
            stage=DerateStage.BOTH,
            early_factor=0.98,
            late_factor=1.02
        ))

        # Clock path derating
        self.add_derate(DerateFactor(
            type=DerateType.CLOCK,
            stage=DerateStage.BOTH,
            early_factor=0.98,
            late_factor=1.02
        ))

        # Data path derating
        self.add_derate(DerateFactor(
            type=DerateType.DATA,
            stage=DerateStage.BOTH,
            early_factor=0.95,
            late_factor=1.05
        ))

        # Setup specific
        self.add_derate(DerateFactor(
            type=DerateType.LATE,
            stage=DerateStage.SETUP,
            early_factor=1.0,
            late_factor=1.1
        ))

        # Hold specific
        self.add_derate(DerateFactor(
            type=DerateType.EARLY,
            stage=DerateStage.HOLD,
            early_factor=0.9,
            late_factor=1.0
        ))

    def add_derate(self, factor: DerateFactor):
        """Add a derating factor."""
        self.derate_factors.append(factor)
        logger.debug(f"Added derate factor: {factor}")

    def clear_derates(self):
        """Clear all derating factors."""
        self.derate_factors.clear()
        logger.debug("Cleared all derate factors")

    def get_cell_derate(self, cell_type: str, stage: DerateStage = DerateStage.BOTH,
                        path_type: str = 'late') -> float:
        """
        Get cell derating factor.

        Args:
            cell_type: Type of cell
            stage: Setup/hold stage
            path_type: 'early' or 'late'

        Returns:
            Derating factor
        """
        factor = 1.0

        for derate in self.derate_factors:
            if derate.type in [DerateType.CELL, DerateType.BOTH]:
                if derate.stage in [stage, DerateStage.BOTH]:
                    if derate.applies_to_cell(cell_type):
                        if path_type == 'early':
                            factor *= derate.early_factor
                        else:
                            factor *= derate.late_factor

        return factor

    def get_net_derate(self, stage: DerateStage = DerateStage.BOTH,
                       path_type: str = 'late') -> float:
        """
        Get net derating factor.

        Args:
            stage: Setup/hold stage
            path_type: 'early' or 'late'

        Returns:
            Derating factor
        """
        factor = 1.0

        for derate in self.derate_factors:
            if derate.type == DerateType.NET:
                if derate.stage in [stage, DerateStage.BOTH]:
                    if path_type == 'early':
                        factor *= derate.early_factor
                    else:
                        factor *= derate.late_factor

        return factor

    def get_clock_derate(self, stage: DerateStage = DerateStage.BOTH,
                         path_type: str = 'late') -> float:
        """
        Get clock path derating factor.

        Args:
            stage: Setup/hold stage
            path_type: 'early' or 'late'

        Returns:
            Derating factor
        """
        factor = 1.0

        for derate in self.derate_factors:
            if derate.type == DerateType.CLOCK:
                if derate.stage in [stage, DerateStage.BOTH]:
                    if path_type == 'early':
                        factor *= derate.early_factor
                    else:
                        factor *= derate.late_factor

        return factor

    def get_data_derate(self, stage: DerateStage = DerateStage.BOTH,
                        path_type: str = 'late') -> float:
        """
        Get data path derating factor.

        Args:
            stage: Setup/hold stage
            path_type: 'early' or 'late'

        Returns:
            Derating factor
        """
        factor = 1.0

        for derate in self.derate_factors:
            if derate.type == DerateType.DATA:
                if derate.stage in [stage, DerateStage.BOTH]:
                    if path_type == 'early':
                        factor *= derate.early_factor
                    else:
                        factor *= derate.late_factor

        return factor

    def apply_derating(self, value: float, cell_type: Optional[str] = None,
                       is_clock: bool = False, stage: DerateStage = DerateStage.BOTH,
                       path_type: str = 'late') -> float:
        """
        Apply all relevant derating factors.

        Args:
            value: Original value
            cell_type: Type of cell (for cell-specific derating)
            is_clock: Whether this is a clock path
            stage: Setup/hold stage
            path_type: 'early' or 'late'

        Returns:
            Derated value
        """
        derated = value

        # Apply cell derating if cell type provided
        if cell_type:
            cell_derate = self.get_cell_derate(cell_type, stage, path_type)
            derated *= cell_derate

        # Apply net derating
        net_derate = self.get_net_derate(stage, path_type)
        derated *= net_derate

        # Apply path-specific derating
        if is_clock:
            path_derate = self.get_clock_derate(stage, path_type)
        else:
            path_derate = self.get_data_derate(stage, path_type)

        derated *= path_derate

        return derated

    def get_setup_derates(self) -> Dict[str, float]:
        """
        Get all derating factors for setup analysis.

        Returns:
            Dictionary of derate factors
        """
        return {
            'cell_early': self.get_cell_derate('', DerateStage.SETUP, 'early'),
            'cell_late': self.get_cell_derate('', DerateStage.SETUP, 'late'),
            'net_early': self.get_net_derate(DerateStage.SETUP, 'early'),
            'net_late': self.get_net_derate(DerateStage.SETUP, 'late'),
            'clock_early': self.get_clock_derate(DerateStage.SETUP, 'early'),
            'clock_late': self.get_clock_derate(DerateStage.SETUP, 'late'),
            'data_early': self.get_data_derate(DerateStage.SETUP, 'early'),
            'data_late': self.get_data_derate(DerateStage.SETUP, 'late')
        }

    def get_hold_derates(self) -> Dict[str, float]:
        """
        Get all derating factors for hold analysis.

        Returns:
            Dictionary of derate factors
        """
        return {
            'cell_early': self.get_cell_derate('', DerateStage.HOLD, 'early'),
            'cell_late': self.get_cell_derate('', DerateStage.HOLD, 'late'),
            'net_early': self.get_net_derate(DerateStage.HOLD, 'early'),
            'net_late': self.get_net_derate(DerateStage.HOLD, 'late'),
            'clock_early': self.get_clock_derate(DerateStage.HOLD, 'early'),
            'clock_late': self.get_clock_derate(DerateStage.HOLD, 'late'),
            'data_early': self.get_data_derate(DerateStage.HOLD, 'early'),
            'data_late': self.get_data_derate(DerateStage.HOLD, 'late')
        }

    def set_unified_derate(self, early: float, late: float):
        """
        Set unified derating factors.

        Args:
            early: Early path derate
            late: Late path derate
        """
        # Clear existing
        self.clear_derates()

        # Add unified derates
        self.add_derate(DerateFactor(
            type=DerateType.CELL,
            stage=DerateStage.BOTH,
            early_factor=early,
            late_factor=late
        ))

        self.add_derate(DerateFactor(
            type=DerateType.NET,
            stage=DerateStage.BOTH,
            early_factor=early,
            late_factor=late
        ))

        logger.info(f"Set unified derate: early={early:.3f}, late={late:.3f}")

    def set_separate_derates(self, cell_early: float, cell_late: float,
                             net_early: float, net_late: float,
                             clock_early: float, clock_late: float):
        """
        Set separate derating factors for different components.

        Args:
            cell_early: Early cell derate
            cell_late: Late cell derate
            net_early: Early net derate
            net_late: Late net derate
            clock_early: Early clock derate
            clock_late: Late clock derate
        """
        self.clear_derates()

        self.add_derate(DerateFactor(
            type=DerateType.CELL,
            stage=DerateStage.BOTH,
            early_factor=cell_early,
            late_factor=cell_late
        ))

        self.add_derate(DerateFactor(
            type=DerateType.NET,
            stage=DerateStage.BOTH,
            early_factor=net_early,
            late_factor=net_late
        ))

        self.add_derate(DerateFactor(
            type=DerateType.CLOCK,
            stage=DerateStage.BOTH,
            early_factor=clock_early,
            late_factor=clock_late
        ))

        logger.info(f"Set separate derates: cell=({cell_early:.3f},{cell_late:.3f}), "
                    f"net=({net_early:.3f},{net_late:.3f}), "
                    f"clock=({clock_early:.3f},{clock_late:.3f})")

    def get_derate_summary(self) -> str:
        """Get summary of derating factors."""
        lines = []
        lines.append("=" * 60)
        lines.append("Derating Factors Summary")
        lines.append("=" * 60)

        setup_derates = self.get_setup_derates()
        hold_derates = self.get_hold_derates()

        lines.append("\nSetup Analysis:")
        lines.append(f"  Cell: early={setup_derates['cell_early']:.3f}, "
                     f"late={setup_derates['cell_late']:.3f}")
        lines.append(f"  Net:  early={setup_derates['net_early']:.3f}, "
                     f"late={setup_derates['net_late']:.3f}")
        lines.append(f"  Clock: early={setup_derates['clock_early']:.3f}, "
                     f"late={setup_derates['clock_late']:.3f}")
        lines.append(f"  Data:  early={setup_derates['data_early']:.3f}, "
                     f"late={setup_derates['data_late']:.3f}")

        lines.append("\nHold Analysis:")
        lines.append(f"  Cell: early={hold_derates['cell_early']:.3f}, "
                     f"late={hold_derates['cell_late']:.3f}")
        lines.append(f"  Net:  early={hold_derates['net_early']:.3f}, "
                     f"late={hold_derates['net_late']:.3f}")
        lines.append(f"  Clock: early={hold_derates['clock_early']:.3f}, "
                     f"late={hold_derates['clock_late']:.3f}")
        lines.append(f"  Data:  early={hold_derates['data_early']:.3f}, "
                     f"late={hold_derates['data_late']:.3f}")

        lines.append("\n" + "=" * 60)

        return "\n".join(lines)