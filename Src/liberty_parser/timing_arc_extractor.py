"""
Timing Arc Extractor for PySTA.
Extracts timing arcs from Liberty parsed data.
"""

from typing import Dict, Any, Optional

from Src.liberty_parser.cell_library import CellLibrary, Cell, TimingArc, TimingSense, TimingType
from Src.utils.logger import get_logger

logger = get_logger(__name__)

class TimingArcExtractor:
    """Extracts timing arcs from parsed Liberty cell data."""

    def __init__(self, library: CellLibrary):
        self.library = library

    def extract_arcs_from_data(self, cell_name: str, data: Dict[str, Any]):
        """
        Extract timing arcs from a cell's parsed data.
        
        Args:
            cell_name: Name of the cell
            data: Parsed cell group data
        """
        cell = self.library.get_cell(cell_name)
        if not cell:
            return

        for child in data.get('children', []):
            if child.get('type') == 'pin':
                self._extract_pin_timing(cell, child)

    def _extract_pin_timing(self, cell: Cell, pin_data: Dict[str, Any]):
        pin_name = pin_data.get('name')
        if not pin_name:
            return
            
        for child in pin_data.get('children', []):
            if child.get('type') == 'timing':
                self._extract_timing_arc(cell, pin_name, child)

    def _extract_timing_arc(self, cell: Cell, pin_name: str, timing_data: Dict[str, Any]):
        attrs = timing_data.get('attributes', {})
        related_pin = attrs.get('related_pin')
        
        if not related_pin:
            return
            
        timing_sense_str = attrs.get('timing_sense', 'non_unate')
        timing_type_str = attrs.get('timing_type', 'combinational')
        
        # Convert strings to Enums
        timing_sense = TimingSense.NON_UNATE
        if isinstance(timing_sense_str, str):
            ts_upper = timing_sense_str.upper()
            if hasattr(TimingSense, ts_upper):
                timing_sense = TimingSense[ts_upper]
                
        timing_type = TimingType.COMBINATIONAL
        if isinstance(timing_type_str, str):
            tt_upper = timing_type_str.upper()
            if hasattr(TimingType, tt_upper):
                timing_type = TimingType[tt_upper]

        arc = TimingArc(
            from_pin=str(related_pin),
            to_pin=pin_name,
            timing_sense=timing_sense,
            timing_type=timing_type
        )
        cell.timing_arcs.append(arc)
