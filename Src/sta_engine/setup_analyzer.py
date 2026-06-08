"""
Setup analyzer for STA engine.
Performs setup timing analysis.
"""

from typing import Dict, List, Any

from Src.sta_engine.base_analyzer import BaseAnalyzer
from Src.utils.logger import get_logger

logger = get_logger(__name__)


class SetupAnalyzer(BaseAnalyzer):
    """Performs setup timing analysis."""

    @property
    def analysis_type(self) -> str:
        return 'setup'

    def get_paths(self, max_paths: int) -> List[Dict[str, Any]]:
        """Get setup paths."""
        return self.path_extractor.get_all_setup_paths(max_paths)