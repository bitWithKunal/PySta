"""
OCV analyzer for PySTA.
Performs on-chip variation analysis with derating.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

from Src.liberty_parser.cell_library import CellLibrary
from Src.ocv_engine.derate_manager import DerateManager, DerateStage
from Src.ocv_engine.variation_models import VariationModel, VariationType
from Src.timing_graph.graph_nodes import TimingNode, TimingEdge
from Src.utils.logger import get_logger
from Src.utils.time_utils import TimeUtils

logger = get_logger(__name__)


@dataclass
class OCVPathAnalysis:
    """Results of OCV analysis for a path."""

    path_id: str
    nominal_delay: float
    early_delay: float
    late_delay: float
    derated_delay: float
    derate_factors: Dict[str, float] = field(default_factory=dict)
    variation_contribution: Dict[str, float] = field(default_factory=dict)

    def get_derate_ratio(self) -> float:
        """Get derating ratio (late/early)."""
        if self.early_delay > 0:
            return self.late_delay / self.early_delay
        return 1.0

    def get_sigma_level(self) -> float:
        """Get sigma level for variation."""
        # Simplified calculation
        return (self.derated_delay - self.nominal_delay) / (self.nominal_delay * 0.1)


class OCVAnalyzer:
    """Analyzer for on-chip variation effects."""

    def __init__(self, cell_library: CellLibrary):
        self.cell_library = cell_library
        self.derate_manager = DerateManager()
        self.variation_model = VariationModel()

        # Analysis settings
        self.analysis_mode = 'setup'  # 'setup' or 'hold'
        self.ocv_depth = 1.0  # Depth factor for location-based OCV

        # Results storage
        self.path_analyses: Dict[str, OCVPathAnalysis] = {}

        logger.info("OCV Analyzer initialized")

    def set_derates(self, data_derate: float = 1.0, clock_derate: float = 1.0,
                    early_derate: float = 0.95, late_derate: float = 1.05):
        """
        Set derating factors.

        Args:
            data_derate: Data path derate
            clock_derate: Clock path derate
            early_derate: Early path derate
            late_derate: Late path derate
        """
        self.derate_manager.set_separate_derates(
            cell_early=early_derate,
            cell_late=late_derate,
            net_early=early_derate,
            net_late=late_derate,
            clock_early=clock_derate * early_derate,
            clock_late=clock_derate * late_derate
        )

        logger.info(f"Set OCV derates: data={data_derate:.3f}, clock={clock_derate:.3f}, "
                    f"early={early_derate:.3f}, late={late_derate:.3f}")

    def analyze_path(self, path: Dict[str, Any]) -> OCVPathAnalysis:
        """
        Perform OCV analysis on a timing path.

        Args:
            path: Path dictionary with stages

        Returns:
            OCVPathAnalysis results
        """
        path_id = path.get('id', f"path_{len(self.path_analyses)}")
        nominal_delay = path.get('delay', 0.0)
        stages = path.get('stages', [])

        # Calculate early and late delays
        early_delay = 0.0
        late_delay = 0.0
        derate_factors = {}
        variation_contribution = {}

        for i, stage in enumerate(stages):
            stage_delay = stage.get('delay', 0.0)
            cell_type = stage.get('cell_type', '')
            is_clock = stage.get('type') == 'clock'

            # Get derate factors for this stage
            stage_derate = self._get_stage_derate(cell_type, is_clock, stage)
            derate_factors[f"stage_{i}"] = stage_derate

            # Calculate early/late delays
            early_delay += stage_delay * stage_derate['early']
            late_delay += stage_delay * stage_derate['late']

            # Get variation contribution
            variation = self._get_variation_contribution(stage)
            variation_contribution[f"stage_{i}"] = variation
            late_delay += variation

        # Determine derated delay based on analysis mode
        if self.analysis_mode == 'setup':
            # Setup uses late path for data, early for clock
            derated_delay = late_delay
        else:
            # Hold uses early path for data, late for clock
            derated_delay = early_delay

        # Create analysis result
        analysis = OCVPathAnalysis(
            path_id=path_id,
            nominal_delay=nominal_delay,
            early_delay=early_delay,
            late_delay=late_delay,
            derated_delay=derated_delay,
            derate_factors=derate_factors,
            variation_contribution=variation_contribution
        )

        self.path_analyses[path_id] = analysis

        logger.debug(f"OCV analysis for {path_id}: nominal={TimeUtils.format_time(nominal_delay)}, "
                     f"early={TimeUtils.format_time(early_delay)}, "
                     f"late={TimeUtils.format_time(late_delay)}")

        return analysis

    def _get_stage_derate(self, cell_type: str, is_clock: bool,
                          stage: Dict[str, Any]) -> Dict[str, float]:
        """
        Get derating factors for a path stage.

        Args:
            cell_type: Type of cell
            is_clock: Whether this is clock path
            stage: Stage information

        Returns:
            Dictionary with 'early' and 'late' factors
        """
        stage_type = DerateStage.SETUP if self.analysis_mode == 'setup' else DerateStage.HOLD

        # Get cell-specific derate
        cell_early = self.derate_manager.get_cell_derate(cell_type, stage_type, 'early')
        cell_late = self.derate_manager.get_cell_derate(cell_type, stage_type, 'late')

        # Get net derate
        net_early = self.derate_manager.get_net_derate(stage_type, 'early')
        net_late = self.derate_manager.get_net_derate(stage_type, 'late')

        # Get path-specific derate
        if is_clock:
            path_early = self.derate_manager.get_clock_derate(stage_type, 'early')
            path_late = self.derate_manager.get_clock_derate(stage_type, 'late')
        else:
            path_early = self.derate_manager.get_data_derate(stage_type, 'early')
            path_late = self.derate_manager.get_data_derate(stage_type, 'late')

        # Combine factors
        early_factor = cell_early * net_early * path_early
        late_factor = cell_late * net_late * path_late

        # Apply depth-based OCV if enabled
        if 'depth' in stage:
            depth_factor = 1.0 + (stage['depth'] * self.ocv_depth * 0.01)
            late_factor *= depth_factor
            early_factor /= depth_factor

        return {'early': early_factor, 'late': late_factor}

    def _get_variation_contribution(self, stage: Dict[str, Any]) -> float:
        """
        Get variation contribution for a stage.

        Args:
            stage: Stage information

        Returns:
            Variation contribution in seconds
        """
        stage_delay = stage.get('delay', 0.0)

        # Get variation based on cell type
        cell_type = stage.get('cell_type', '')
        variation = self.variation_model.get_variation(cell_type)

        # Scale by stage delay
        contribution = stage_delay * variation

        # Add random variation
        random_var = self.variation_model.get_random_variation()
        contribution += random_var * 1e-12  # Add in ps

        return contribution

    def analyze_paths(self, paths: List[Dict[str, Any]]) -> List[OCVPathAnalysis]:
        """
        Perform OCV analysis on multiple paths.

        Args:
            paths: List of path dictionaries

        Returns:
            List of OCVPathAnalysis results
        """
        analyses = []

        for path in paths:
            analysis = self.analyze_path(path)
            analyses.append(analysis)

        # Sort by derated delay
        analyses.sort(key=lambda x: x.derated_delay, reverse=True)

        logger.info(f"OCV analyzed {len(analyses)} paths")

        return analyses

    def calculate_setup_slack(self, path_delay: float, clock_period: float,
                              clock_uncertainty: float, setup_time: float) -> float:
        """
        Calculate setup slack with OCV.

        Args:
            path_delay: Derated path delay
            clock_period: Clock period
            clock_uncertainty: Clock uncertainty
            setup_time: Setup time requirement

        Returns:
            Setup slack
        """
        # Setup slack = clock_period - clock_uncertainty - setup_time - path_delay
        slack = clock_period - clock_uncertainty - setup_time - path_delay

        # Apply OCV margin
        slack *= self.derate_manager.get_data_derate(DerateStage.SETUP, 'late')

        return slack

    def calculate_hold_slack(self, path_delay: float, hold_time: float) -> float:
        """
        Calculate hold slack with OCV.

        Args:
            path_delay: Derated path delay
            hold_time: Hold time requirement

        Returns:
            Hold slack
        """
        # Hold slack = path_delay - hold_time
        slack = path_delay - hold_time

        # Apply OCV margin
        slack *= self.derate_manager.get_data_derate(DerateStage.HOLD, 'early')

        return slack

    def get_ocv_penalty(self, path: Dict[str, Any]) -> float:
        """
        Get OCV penalty for a path.

        Args:
            path: Path dictionary

        Returns:
            OCV penalty in seconds
        """
        analysis = self.analyze_path(path)
        return analysis.derated_delay - analysis.nominal_delay

    def get_ocv_summary(self) -> Dict[str, Any]:
        """
        Get OCV analysis summary.

        Returns:
            Dictionary with OCV summary
        """
        if not self.path_analyses:
            return {}

        # Calculate statistics
        derated_delays = [a.derated_delay for a in self.path_analyses.values()]
        nominal_delays = [a.nominal_delay for a in self.path_analyses.values()]

        summary = {
            'num_paths': len(self.path_analyses),
            'avg_nominal_delay': sum(nominal_delays) / len(nominal_delays),
            'avg_derated_delay': sum(derated_delays) / len(derated_delays),
            'max_nominal_delay': max(nominal_delays),
            'max_derated_delay': max(derated_delays),
            'min_nominal_delay': min(nominal_delays),
            'min_derated_delay': min(derated_delays),
            'total_ocv_penalty': sum(derated_delays) - sum(nominal_delays),
            'avg_derate_ratio': sum(a.get_derate_ratio() for a in self.path_analyses.values()) / len(
                self.path_analyses),
            'derate_factors': self.derate_manager.get_setup_derates() if self.analysis_mode == 'setup'
            else self.derate_manager.get_hold_derates()
        }

        return summary

    def print_summary(self):
        """Print OCV analysis summary."""
        summary = self.get_ocv_summary()

        if not summary:
            logger.info("No OCV analysis results available")
            return

        logger.info("=" * 60)
        logger.info("OCV Analysis Summary")
        logger.info("=" * 60)
        logger.info(f"Analysis mode: {self.analysis_mode}")
        logger.info(f"Paths analyzed: {summary['num_paths']}")
        logger.info(f"Average nominal delay: {TimeUtils.format_time(summary['avg_nominal_delay'])}")
        logger.info(f"Average derated delay: {TimeUtils.format_time(summary['avg_derated_delay'])}")
        logger.info(f"Max nominal delay: {TimeUtils.format_time(summary['max_nominal_delay'])}")
        logger.info(f"Max derated delay: {TimeUtils.format_time(summary['max_derated_delay'])}")
        logger.info(f"Total OCV penalty: {TimeUtils.format_time(summary['total_ocv_penalty'])}")
        logger.info(f"Average derate ratio: {summary['avg_derate_ratio']:.3f}")

        logger.info("\nDerating Factors:")
        for name, value in summary['derate_factors'].items():
            logger.info(f"  {name}: {value:.3f}")

        logger.info("=" * 60)

    def reset(self):
        """Reset OCV analyzer."""
        self.path_analyses.clear()
        logger.debug("OCV analyzer reset")