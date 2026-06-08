"""
Enhanced Liberty parser for PySTA.
Supports multiple Liberty files, library concatenation, and include directives.
Robust parsing with better error handling and support for all Liberty syntax variants.
"""

import re
from typing import Dict, List, Optional, Any, Tuple, Set, Union
from pathlib import Path

from Src.liberty_parser.cell_library import CellLibrary, Cell, Pin
from Src.liberty_parser.timing_arc_extractor import TimingArcExtractor
from Src.utils.logger import get_logger
from Src.utils.file_utils import FileUtils

logger = get_logger(__name__)


class LibertyParser:
    """Enhanced parser for Liberty (.lib) files with multi-file support."""

    def __init__(self):
        self.library: Optional[CellLibrary] = None
        self.current_group = None
        self.group_stack: List[Dict[str, Any]] = []
        self.attributes: Dict[str, Any] = {}
        self.parsed_data: Dict[str, Any] = {}
        self.line_number = 0
        self.current_file: Optional[Path] = None
        self.included_files: Set[str] = set()

        # Multi-file support
        self.lib_files: List[Path] = []
        self.merged_library: Optional[CellLibrary] = None

        # Statistics
        self.parse_stats: Dict[str, int] = {
            'cells': 0,
            'pins': 0,
            'timing_arcs': 0,
            'errors': 0,
            'warnings': 0
        }

    def parse_file(self, file_path: str) -> CellLibrary:
        """
        Parse a single Liberty file.

        Args:
            file_path: Path to .lib file

        Returns:
            CellLibrary object
        """
        logger.info(f"Parsing Liberty file: {file_path}")

        # Validate file
        is_valid, error = FileUtils.validate_file(file_path, '.lib')
        if not is_valid:
            logger.error(f"Invalid Liberty file: {error}")
            raise ValueError(error)

        # Reset parser state for this file
        self._reset_parser()
        self.current_file = Path(file_path)

        # Read and parse file
        content = self._read_with_includes(file_path)

        # Parse content
        self._parse_content(content)

        # Build library from parsed data
        library = self._build_library()

        # Extract timing arcs
        if library:
            extractor = TimingArcExtractor(library)
            for cell_name in library.cells:
                if cell_name in self.parsed_data:
                    try:
                        extractor.extract_arcs_from_data(cell_name, self.parsed_data[cell_name])
                        self.parse_stats['timing_arcs'] += len(library.cells[cell_name].timing_arcs)
                    except Exception as e:
                        logger.warning(f"Failed to extract timing arcs for cell {cell_name}: {e}")
                        self.parse_stats['warnings'] += 1

        logger.info(f"Successfully parsed {len(library.cells)} cells from {file_path}")
        logger.debug(f"Parse stats: {self.parse_stats}")
        return library

    def parse_files(self, file_paths: List[str]) -> CellLibrary:
        """
        Parse multiple Liberty files and merge them into a single library.

        Args:
            file_paths: List of paths to .lib files

        Returns:
            Merged CellLibrary object
        """
        logger.info(f"Parsing {len(file_paths)} Liberty files")

        self.lib_files = [Path(f) for f in file_paths]
        self.merged_library = CellLibrary("merged_library")

        # Track cell conflicts
        cell_conflicts: Dict[str, List[str]] = {}

        for file_path in file_paths:
            try:
                library = self.parse_file(file_path)

                # Merge cells
                for cell_name, cell in library.cells.items():
                    if cell_name not in self.merged_library.cells:
                        self.merged_library.add_cell(cell)
                    else:
                        # Handle cell name conflict
                        if cell_name not in cell_conflicts:
                            cell_conflicts[cell_name] = []
                        cell_conflicts[cell_name].append(str(file_path))

                        # Rename duplicate cell with library prefix
                        lib_name = Path(file_path).stem
                        new_cell_name = f"{lib_name}__{cell_name}"
                        logger.warning(f"Cell '{cell_name}' already exists, renaming to '{new_cell_name}'")
                        cell.name = new_cell_name
                        self.merged_library.add_cell(cell)

                # Merge library attributes (keep first occurrence)
                if not self.merged_library.time_unit:
                    self.merged_library.time_unit = library.time_unit
                if not self.merged_library.delay_model:
                    self.merged_library.delay_model = library.delay_model

            except Exception as e:
                logger.error(f"Failed to parse {file_path}: {e}")
                self.parse_stats['errors'] += 1
                continue

        # Log merge statistics
        logger.info(f"Merged library: {len(self.merged_library.cells)} total cells from {len(file_paths)} files")
        if cell_conflicts:
            logger.warning(f"Cell name conflicts resolved: {len(cell_conflicts)} cells renamed")

        return self.merged_library

    def parse_directory(self, directory: str, pattern: str = "*.lib") -> CellLibrary:
        """
        Parse all Liberty files in a directory.

        Args:
            directory: Directory path
            pattern: File pattern (default: "*.lib")

        Returns:
            Merged CellLibrary object
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            raise ValueError(f"Directory does not exist: {directory}")

        lib_files = list(dir_path.glob(pattern))
        logger.info(f"Found {len(lib_files)} Liberty files in {directory}")

        return self.parse_files([str(f) for f in lib_files])

    def _reset_parser(self):
        """Reset parser state for a new file."""
        self.current_group = None
        self.group_stack = []
        self.attributes = {}
        self.parsed_data = {}
        self.line_number = 0
        self.included_files.clear()
        self.parse_stats = {
            'cells': 0,
            'pins': 0,
            'timing_arcs': 0,
            'errors': 0,
            'warnings': 0
        }

    def _read_with_includes(self, file_path: str) -> str:
        """
        Read file content and process include directives.

        Args:
            file_path: Path to main file

        Returns:
            Combined content with includes expanded
        """
        main_path = Path(file_path)
        self.included_files.add(str(main_path))

        content = FileUtils.read_file_with_encoding(file_path)

        # Process include directives
        include_pattern = r'#include\s+"([^"]+)"'

        def process_include(match):
            include_file = match.group(1)
            include_path = main_path.parent / include_file

            if str(include_path) in self.included_files:
                logger.warning(f"Circular include detected: {include_file}")
                self.parse_stats['warnings'] += 1
                return f"\n/* Circular include: {include_file} */\n"

            if include_path.exists():
                logger.info(f"Including file: {include_file}")
                self.included_files.add(str(include_path))
                include_content = FileUtils.read_file_with_encoding(str(include_path))
                return f"\n/* Begin include: {include_file} */\n{include_content}\n/* End include: {include_file} */\n"
            else:
                logger.warning(f"Include file not found: {include_file}")
                self.parse_stats['warnings'] += 1
                return f"\n/* Missing include: {include_file} */\n"

        # Process all includes
        content = re.sub(include_pattern, process_include, content)

        return content

    def _parse_content(self, content: str):
        """Parse Liberty file content."""
        # Remove comments
        content = FileUtils.extract_comments(content, 'liberty')

        # Parse line by line
        lines = content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            self.line_number = i + 1

            if not line:
                i += 1
                continue

            # Handle multi-line statements
            while line.endswith('\\'):
                i += 1
                if i < len(lines):
                    line = line[:-1] + lines[i].strip()
                else:
                    break

            try:
                self._parse_line(line)
            except Exception as e:
                logger.error(f"Parse error at {self.current_file}:{self.line_number}: {e}")
                self.parse_stats['errors'] += 1

            i += 1

    def _parse_line(self, line: str):
        """Parse a single line of Liberty file with improved syntax handling."""
        if not line:
            return

        # Handle group opening - various formats
        if line.endswith('{'):
            # Format 1: cell (name) {
            match = re.match(r'(\w+)\s*\(\s*([^)]+)\s*\)\s*{', line)
            if match:
                group_type = match.group(1)
                group_name = match.group(2).strip().strip('"\'')
                self._handle_group_open(group_type, group_name)
                return

            # Format 2: timing () {
            match = re.match(r'(\w+)\s*\(\s*\)\s*{', line)
            if match:
                group_type = match.group(1)
                self._handle_group_open(group_type, None)
                return

            # Format 3: group_name {
            match = re.match(r'(\w+)\s*{', line)
            if match:
                group_type = match.group(1)
                self._handle_group_open(group_type, None)
                return

            # Format 4: ff (IQ, IQN) { ... }
            match = re.match(r'(\w+)\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)\s*{', line)
            if match:
                group_type = match.group(1)
                group_name = f"{match.group(2).strip()},{match.group(3).strip()}"
                self._handle_group_open(group_type, group_name)
                return

            logger.warning(f"Could not parse group opening: {line}")
            self.parse_stats['warnings'] += 1
            return

        # Handle group closing
        if line == '}':
            self._handle_group_close()
            return

        # Handle simple attribute (key : value;)
        if ':' in line:
            line = line.rstrip(';').strip()
            parts = line.split(':', 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                self._handle_attribute(key, value)
                return

        # Handle complex attribute with parentheses
        if '(' in line and ')' in line:
            self._handle_complex_attribute(line)
            return

        # Ignore other lines (could be empty or malformed)
        if line.strip():
            logger.debug(f"Ignoring line: {line}")

    def _handle_group_open(self, group_type: str, group_name: Optional[str]):
        """Handle opening of a group."""
        # Create new group
        group = {
            'type': group_type,
            'name': group_name,
            'attributes': {},
            'children': [],
            'file': str(self.current_file),
            'line': self.line_number
        }

        # Add to parent if exists
        if self.group_stack:
            parent = self.group_stack[-1]
            parent['children'].append(group)
        else:
            # This is the library group
            self.parsed_data = group

        self.group_stack.append(group)
        self.current_group = group

        logger.debug(f"Opened group: {group_type} at {self.current_file}:{self.line_number}")

    def _handle_group_close(self):
        """Handle closing of a group."""
        if self.group_stack:
            closed_group = self.group_stack.pop()
            self.current_group = self.group_stack[-1] if self.group_stack else None

            # If this was a cell group, add to cell list
            if closed_group['type'] == 'cell' and closed_group['name']:
                cell_name = closed_group['name']
                self.parsed_data[cell_name] = closed_group
                self.parse_stats['cells'] += 1
                logger.debug(f"Found cell: {cell_name}")

            # If this was a pin group, count it
            elif closed_group['type'] == 'pin':
                self.parse_stats['pins'] += 1

            logger.debug(f"Closed group: {closed_group['type']} at {self.current_file}:{self.line_number}")

    def _handle_attribute(self, key: str, value: str):
        """Handle simple attribute."""
        parsed_value = self._parse_value(value)

        if self.current_group:
            self.current_group['attributes'][key] = parsed_value
            logger.debug(f"Attribute: {key} = {parsed_value}")

    def _handle_complex_attribute(self, line: str):
        """Handle complex attribute with parentheses."""
        line = line.rstrip(';').strip()

        # Find the key (text before first '(')
        key_match = re.match(r'(\w+)\s*\(', line)
        if not key_match:
            return

        key = key_match.group(1)
        content = line[line.index('('):]

        try:
            parsed_content = self._parse_parentheses(content)

            if self.current_group:
                if key not in self.current_group['attributes']:
                    self.current_group['attributes'][key] = []
                self.current_group['attributes'][key].append(parsed_content)
                logger.debug(f"Complex attribute: {key}")

        except Exception as e:
            logger.warning(f"Failed to parse complex attribute '{key}': {e}")
            self.parse_stats['warnings'] += 1

    def _parse_value(self, value: str) -> Any:
        """Parse attribute value with improved type detection."""
        value = value.strip()

        # Handle empty value
        if not value:
            return None

        # Handle quoted strings
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return value[1:-1]

        # Handle numbers (integers and floats)
        try:
            if '.' in value or 'e' in value.lower():
                return float(value)
            # Check if it's a valid integer
            if value.isdigit() or (value[0] in '+-' and value[1:].isdigit()):
                return int(value)
        except ValueError:
            pass

        # Handle boolean
        if value.lower() == 'true':
            return True
        if value.lower() == 'false':
            return False

        # Handle arrays (values in parentheses)
        if value.startswith('(') and value.endswith(')'):
            return self._parse_parentheses(value)

        # Handle simple strings
        return value

    def _parse_parentheses(self, text: str) -> Any:
        """
        Parse content within parentheses.
        Handles nested parentheses and various separator styles.
        """
        text = text.strip()

        # Remove outer parentheses
        if text.startswith('(') and text.endswith(')'):
            text = text[1:-1].strip()

        # Handle empty parentheses
        if not text:
            return []

        # Check if it's a list (contains commas)
        if ',' in text:
            items = []
            current = ''
            paren_level = 0
            bracket_level = 0

            for char in text:
                if char == '(':
                    paren_level += 1
                    current += char
                elif char == ')':
                    paren_level -= 1
                    current += char
                elif char == '[':
                    bracket_level += 1
                    current += char
                elif char == ']':
                    bracket_level -= 1
                    current += char
                elif char == ',' and paren_level == 0 and bracket_level == 0:
                    if current.strip():
                        items.append(self._parse_value(current.strip()))
                    current = ''
                else:
                    current += char

            # Add last item
            if current.strip():
                items.append(self._parse_value(current.strip()))

            # If it's a simple list of numbers/strings, return as list
            return items

        # Single value
        return self._parse_value(text)

    def _build_library(self) -> CellLibrary:
        """Build cell library from parsed data."""
        # Get library attributes
        lib_attrs = self.parsed_data.get('attributes', {}) if isinstance(self.parsed_data, dict) else {}

        # Create library with name
        lib_name = "unknown"
        if 'library' in lib_attrs and isinstance(lib_attrs['library'], dict):
            lib_name = lib_attrs['library'].get('name', self.current_file.stem if self.current_file else 'unknown')
        else:
            lib_name = self.current_file.stem if self.current_file else 'unknown'

        library = CellLibrary(str(lib_name))

        # Set library attributes
        if 'delay_model' in lib_attrs:
            library.delay_model = str(lib_attrs['delay_model'])

        if 'time_unit' in lib_attrs:
            time_unit = str(lib_attrs['time_unit'])
            if '1ns' in time_unit:
                library.time_unit = '1ns'
            elif '1ps' in time_unit:
                library.time_unit = '1ps'

        if 'voltage_unit' in lib_attrs:
            library.voltage_unit = str(lib_attrs['voltage_unit'])

        if 'current_unit' in lib_attrs:
            library.current_unit = str(lib_attrs['current_unit'])

        if 'capacitance_unit' in lib_attrs:
            library.capacitance_unit = str(lib_attrs['capacitance_unit'])

        # Process each cell
        cells_found = 0
        for key, value in self.parsed_data.items():
            if isinstance(value, dict) and value.get('type') == 'cell':
                try:
                    self._build_cell(library, key, value)
                    cells_found += 1
                except Exception as e:
                    logger.warning(f"Failed to build cell '{key}': {e}")
                    self.parse_stats['warnings'] += 1

        logger.debug(f"Built {cells_found} cells for library {lib_name}")
        return library

    def _build_cell(self, library: CellLibrary, cell_name: str, cell_data: Dict[str, Any]):
        """Build a single cell from parsed data."""
        cell = Cell(name=cell_name)

        # Set cell attributes
        attrs = cell_data.get('attributes', {})

        if 'area' in attrs:
            try:
                cell.area = float(attrs['area'])
            except (ValueError, TypeError):
                logger.warning(f"Invalid area value for cell {cell_name}: {attrs['area']}")

        # Check if sequential (has ff or latch group)
        for child in cell_data.get('children', []):
            if child.get('type') in ['ff', 'latch']:
                cell.is_sequential = True
                break

        # Create pins
        self._build_pins(cell, cell_data)

        # Add to library
        library.add_cell(cell)

    def _build_pins(self, cell: Cell, cell_data: Dict[str, Any]):
        """Build pins for a cell."""
        for child in cell_data.get('children', []):
            if child.get('type') == 'pin':
                pin_name = child.get('name')
                if not pin_name:
                    continue

                pin_attrs = child.get('attributes', {})

                # Parse capacitance
                capacitance = 0.0
                if 'capacitance' in pin_attrs:
                    try:
                        capacitance = float(pin_attrs['capacitance'])
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid capacitance for pin {pin_name}: {pin_attrs['capacitance']}")

                # Check if clock pin
                is_clock = False
                if 'clock' in pin_attrs:
                    clock_val = pin_attrs['clock']
                    is_clock = clock_val in [True, 'true', 'TRUE', '1', 1]

                # Get direction
                direction = pin_attrs.get('direction', 'unknown')
                if isinstance(direction, str):
                    direction = direction.lower()

                # Create pin
                pin = Pin(
                    name=pin_name,
                    direction=direction,
                    capacitance=capacitance,
                    is_clock=is_clock,
                    function=pin_attrs.get('function')
                )

                cell.add_pin(pin)

    def get_library_info(self) -> Dict[str, Any]:
        """Get information about parsed libraries."""
        info = {
            'files': [str(f) for f in self.lib_files],
            'total_files': len(self.lib_files),
            'merged_cells': len(self.merged_library.cells) if self.merged_library else 0,
            'time_unit': self.merged_library.time_unit if self.merged_library else 'unknown',
            'delay_model': self.merged_library.delay_model if self.merged_library else 'unknown',
            'voltage_unit': self.merged_library.voltage_unit if self.merged_library else 'unknown',
            'current_unit': self.merged_library.current_unit if self.merged_library else 'unknown',
            'capacitance_unit': self.merged_library.capacitance_unit if self.merged_library else 'unknown',
            'parse_stats': self.parse_stats
        }

        if self.merged_library:
            # Count cell types
            sequential = 0
            combinational = 0
            for cell in self.merged_library.cells.values():
                if cell.is_sequential:
                    sequential += 1
                else:
                    combinational += 1

            info['sequential_cells'] = sequential
            info['combinational_cells'] = combinational

            # Count pins
            total_pins = sum(len(cell.pins) for cell in self.merged_library.cells.values())
            info['total_pins'] = total_pins

        return info

    def print_summary(self):
        """Print parsing summary."""
        info = self.get_library_info()

        logger.info("=" * 60)
        logger.info("Liberty Parser Summary")
        logger.info("=" * 60)
        logger.info(f"Files parsed: {info['total_files']}")
        logger.info(f"Total cells: {info['merged_cells']}")
        logger.info(f"  Sequential: {info.get('sequential_cells', 0)}")
        logger.info(f"  Combinational: {info.get('combinational_cells', 0)}")
        logger.info(f"Total pins: {info.get('total_pins', 0)}")
        logger.info(f"Time unit: {info['time_unit']}")
        logger.info(f"Delay model: {info['delay_model']}")

        if info['parse_stats']:
            logger.info("\nParse Statistics:")
            logger.info(f"  Cells found: {info['parse_stats'].get('cells', 0)}")
            logger.info(f"  Pins found: {info['parse_stats'].get('pins', 0)}")
            logger.info(f"  Timing arcs: {info['parse_stats'].get('timing_arcs', 0)}")
            logger.info(f"  Warnings: {info['parse_stats'].get('warnings', 0)}")
            logger.info(f"  Errors: {info['parse_stats'].get('errors', 0)}")

        logger.info("=" * 60)