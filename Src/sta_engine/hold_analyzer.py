"""
Hold analyzer for STA engine.
Performs hold timing analysis.
"""

from typing import Dict, List, Any

from Src.sta_engine.base_analyzer import BaseAnalyzer
from Src.utils.logger import get_logger

logger = get_logger(__name__)


class HoldAnalyzer(BaseAnalyzer):
    """Performs hold timing analysis."""

    @property
    def analysis_type(self) -> str:
        return 'hold'

    def get_paths(self, max_paths: int) -> List[Dict[str, Any]]:
        """Get hold paths."""
        return self.path_extractor.get_all_hold_paths(max_paths)