"""
Enhanced Verilog parser for PySTA.
Supports multiple Verilog files, include directives, and hierarchical design.
"""

import re
from typing import Dict, List, Optional, Tuple, Any, Set
from pathlib import Path
from collections import defaultdict

from Src.verilog_parser.module_resolver import ModuleResolver
from Src.verilog_parser.netlist_builder import NetlistBuilder
from Src.utils.logger import get_logger
from Src.utils.file_utils import FileUtils

logger = get_logger(__name__)

class VerilogParser:
    """Enhanced parser for gate-level Verilog netlists with multi-file support."""

    def __init__(self):
        self.module_resolver = ModuleResolver()
        self.netlist_builder = NetlistBuilder()
        self.current_module: Optional[str] = None
        self.module_data: Dict[str, Any] = {}
        self.line_number = 0
        self.current_file: Optional[Path] = None
        self.included_files: Set[str] = set()

        # Multi-file support
        self.verilog_files: List[Path] = []
        self.include_paths: List[Path] = []
        self.define_macros: Dict[str, str] = {}

        # Module statistics
        self.module_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def add_include_path(self, path: str):
        """Add a directory to the include path."""
        include_path = Path(path)
        if include_path.exists() and include_path.is_dir():
            self.include_paths.append(include_path)
            logger.debug(f"Added include path: {path}")

    def add_define(self, macro: str, value: str = "1"):
        """Add a define macro."""
        self.define_macros[macro] = value
        logger.debug(f"Added define: {macro}={value}")

    def parse_file(self, file_path: str) -> ModuleResolver:
        """
        Parse a single Verilog file.

        Args:
            file_path: Path to .v file

        Returns:
            ModuleResolver with parsed hierarchy
        """
        logger.info(f"Parsing Verilog file: {file_path}")

        # Validate file
        is_valid, error = FileUtils.validate_file(file_path, '.v')
        if not is_valid:
            logger.error(f"Invalid Verilog file: {error}")
            raise ValueError(error)

        # Reset state for this file
        self.current_file = Path(file_path)
        self.line_number = 0

        # Read and preprocess content
        content = self._preprocess_file(file_path)

        # Parse modules in this file
        self._parse_modules(content)

        logger.info(f"Successfully parsed modules from {file_path}")
        return self.module_resolver

    def parse_files(self, file_paths: List[str], top_module: Optional[str] = None) -> ModuleResolver:
        """
        Parse multiple Verilog files and build complete hierarchy.

        Args:
            file_paths: List of paths to .v files
            top_module: Name of top module (auto-detect if None)

        Returns:
            ModuleResolver with complete hierarchy
        """
        logger.info(f"Parsing {len(file_paths)} Verilog files")

        self.verilog_files = [Path(f) for f in file_paths]

        # Parse each file
        for file_path in file_paths:
            try:
                self.parse_file(file_path)
            except Exception as e:
                logger.error(f"Failed to parse {file_path}: {e}")
                continue

        # Build hierarchy
        if top_module:
            logger.info(f"Building hierarchy with top module: {top_module}")
            self.module_resolver.build_hierarchy(top_module)
        else:
            # Auto-detect top module
            top = self.module_resolver._find_top_module()
            if top:
                logger.info(f"Auto-detected top module: {top}")
                self.module_resolver.build_hierarchy(top)

        # Build netlist
        self.netlist_builder.build_from_parser(self.module_resolver)

        # Update statistics
        self._update_statistics()

        logger.info(f"Complete hierarchy built: {len(self.module_resolver.modules)} modules, "
                   f"{len(self.netlist_builder.cells)} cells, {len(self.netlist_builder.nets)} nets")

        return self.module_resolver

    def parse_directory(self, directory: str, pattern: str = "*.v",
                       recursive: bool = True) -> ModuleResolver:
        """
        Parse all Verilog files in a directory.

        Args:
            directory: Directory path
            pattern: File pattern (default: "*.v")
            recursive: Search subdirectories recursively

        Returns:
            ModuleResolver with complete hierarchy
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            raise ValueError(f"Directory does not exist: {directory}")

        if recursive:
            verilog_files = list(dir_path.rglob(pattern))
        else:
            verilog_files = list(dir_path.glob(pattern))

        logger.info(f"Found {len(verilog_files)} Verilog files in {directory}")

        # Add directory to include paths
        self.add_include_path(directory)

        return self.parse_files([str(f) for f in verilog_files])

    def _preprocess_file(self, file_path: str) -> str:
        """
        Preprocess Verilog file (handle `include, `define, etc.).

        Args:
            file_path: Path to Verilog file

        Returns:
            Preprocessed content
        """
        content = FileUtils.read_file_with_encoding(file_path)

        # Track this file
        self.included_files.add(file_path)

        # Process `define macros first
        content = self._process_defines(content)

        # Process `include directives
        content = self._process_includes(content, Path(file_path).parent)

        return content

    def _process_defines(self, content: str) -> str:
        """Process `define macros."""
        define_pattern = r'`define\s+(\w+)(?:\s+(.+))?'

        def replace_define(match):
            macro = match.group(1)
            value = match.group(2) if match.group(2) else "1"
            self.define_macros[macro] = value.strip()
            return ""  # Remove define line

        # Remove define lines
        content = re.sub(define_pattern, replace_define, content, flags=re.MULTILINE)

        # Replace macro usages
        for macro, value in self.define_macros.items():
            pattern = rf'`{macro}\b'
            content = re.sub(pattern, value, content)

        return content

    def _process_includes(self, content: str, base_dir: Path) -> str:
        """Process `include directives."""
        include_pattern = r'`include\s+"([^"]+)"'

        def process_include(match):
            include_file = match.group(1)

            # Search for include file
            include_path = self._find_include_file(include_file, base_dir)

            if include_path and str(include_path) not in self.included_files:
                logger.info(f"Including file: {include_file}")
                return self._preprocess_file(str(include_path))
            elif include_path:
                logger.warning(f"Circular include detected: {include_file}")
                return f"\n/* Circular include: {include_file} */\n"
            else:
                logger.warning(f"Include file not found: {include_file}")
                return f"\n/* Missing include: {include_file} */\n"

        # Process all includes
        content = re.sub(include_pattern, process_include, content)

        return content

    def _find_include_file(self, filename: str, base_dir: Path) -> Optional[Path]:
        """Find an include file in search paths."""
        # Check relative to current file
        candidate = base_dir / filename
        if candidate.exists():
            return candidate

        # Check include paths
        for include_path in self.include_paths:
            candidate = include_path / filename
            if candidate.exists():
                return candidate

        return None

    def _parse_modules(self, content: str):
        """Split content into individual modules and parse each."""
        # Remove comments
        content = FileUtils.extract_comments(content, 'verilog')

        # Find module boundaries
        module_pattern = r'module\s+(\w+)\s*(?:#|\(|;)'
        lines = content.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i]
            self.line_number = i + 1

            # Look for module start
            if 'module' in line:
                module_name = self._extract_module_name(line)
                if module_name:
                    # Find module end
                    module_content, end_i = self._extract_module_content(lines, i)
                    self._parse_single_module(module_name, module_content)
                    i = end_i
                else:
                    i += 1
            else:
                i += 1

    def _extract_module_name(self, line: str) -> Optional[str]:
        """Extract module name from module declaration line."""
        match = re.search(r'module\s+(\w+)', line)
        if match:
            return match.group(1)
        return None

    def _extract_module_content(self, lines: List[str], start_idx: int) -> Tuple[str, int]:
        """
        Extract complete module content.

        Args:
            lines: All lines
            start_idx: Index of module line

        Returns:
            Tuple of (module_content, end_index)
        """
        content = []
        brace_count = 0
        i = start_idx

        while i < len(lines):
            line = lines[i]
            content.append(line)

            # Count braces to find module end
            brace_count += line.count('{') - line.count('}')

            # Check for module end (when braces balanced and 'endmodule' found)
            if brace_count <= 0 and 'endmodule' in line:
                break

            i += 1

        return '\n'.join(content), i

    def _parse_single_module(self, module_name: str, content: str):
        """Parse a single module."""
        logger.debug(f"Parsing module: {module_name} from {self.current_file}")

        # Initialize module data
        module = {
            'name': module_name,
            'ports': [],
            'items': [],
            'file': str(self.current_file),
            'line': self.line_number
        }

        # Extract port list
        port_list = self._extract_port_list(content)
        module['ports'] = port_list

        # Extract declarations and instantiations
        items = self._extract_module_items(content)
        module['items'] = items

        # Update statistics
        self.module_stats[module_name]['instances'] = len([i for i in items if i['type'] == 'instantiation'])
        self.module_stats[module_name]['nets'] = len([i for i in items if i['type'] == 'net_declaration'])

        # Add to resolver
        self.module_resolver.add_module(module_name, module)

    def _extract_port_list(self, content: str) -> List[Dict]:
        """Extract module port list."""
        ports = []

        # Find port list between module name and first ';'
        match = re.search(r'module\s+\w+\s*\(\s*(.*?)\s*\)\s*;', content, re.DOTALL)
        if match:
            port_text = match.group(1)
            # Split ports
            for port in port_text.split(','):
                port = port.strip()
                if port:
                    # Check for direction
                    direction = 'inout'  # default
                    if 'input' in port:
                        direction = 'input'
                        port = port.replace('input', '').strip()
                    elif 'output' in port:
                        direction = 'output'
                        port = port.replace('output', '').strip()

                    # Check for bus
                    bus_match = re.search(r'(\w+)\s*\[\s*(\d+):(\d+)\s*\]', port)
                    if bus_match:
                        name = bus_match.group(1)
                        msb = int(bus_match.group(2))
                        lsb = int(bus_match.group(3))
                        ports.append({
                            'name': name,
                            'direction': direction,
                            'msb': msb,
                            'lsb': lsb,
                            'width': abs(msb - lsb) + 1
                        })
                    else:
                        # Simple port
                        ports.append({
                            'name': port.strip(),
                            'direction': direction,
                            'width': 1
                        })

        return ports

    def _extract_module_items(self, content: str) -> List[Dict]:
        """Extract all items from module (nets, instances, etc.)."""
        items = []

        # Remove module header and endmodule
        content = re.sub(r'module\s+.*?;', '', content, flags=re.DOTALL)
        content = re.sub(r'endmodule', '', content)

        # Split into statements
        statements = self._split_statements(content)

        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue

            # Check for wire/reg declarations
            if any(stmt.startswith(kw) for kw in ['wire', 'reg', 'supply0', 'supply1']):
                items.append(self._parse_net_declaration(stmt))

            # Check for gate/instance instantiations
            elif '(' in stmt and ')' in stmt:
                items.append(self._parse_instantiation(stmt))

            # Check for parameter declarations
            elif stmt.startswith('parameter'):
                items.append(self._parse_parameter_declaration(stmt))

        return items

    def _split_statements(self, content: str) -> List[str]:
        """Split content into statements ending with semicolon."""
        statements = []
        current = []
        in_string = False

        for char in content:
            current.append(char)
            if char == ';' and not in_string:
                statements.append(''.join(current))
                current = []
            elif char == '"':
                in_string = not in_string

        # Add last statement if any
        if current:
            statements.append(''.join(current))

        return statements

    def _parse_net_declaration(self, stmt: str) -> Dict:
        """Parse net declaration (wire, reg, etc.)."""
        stmt = stmt.rstrip(';').strip()
        tokens = stmt.split()

        net_type = tokens[0]
        net_names = []
        range_info = None

        # Check for range
        range_match = re.search(r'\[\s*(\d+):(\d+)\s*\]', stmt)
        if range_match:
            msb = int(range_match.group(1))
            lsb = int(range_match.group(2))
            range_info = {'msb': msb, 'lsb': lsb, 'width': abs(msb - lsb) + 1}

        # Extract net names
        for token in tokens[1:]:
            if '[' not in token and ']' not in token:
                for name in token.split(','):
                    name = name.strip()
                    if name:
                        net_names.append(name)

        return {
            'type': 'net_declaration',
            'net_type': net_type,
            'nets': net_names,
            'range': range_info
        }

    def _parse_parameter_declaration(self, stmt: str) -> Dict:
        """Parse parameter declaration."""
        stmt = stmt.rstrip(';').strip()
        stmt = stmt.replace('parameter', '').strip()

        parameters = {}
        for param in stmt.split(','):
            param = param.strip()
            if '=' in param:
                name, value = param.split('=', 1)
                parameters[name.strip()] = value.strip()

        return {
            'type': 'parameter_declaration',
            'parameters': parameters
        }

    def _parse_instantiation(self, stmt: str) -> Dict:
        """Parse module or gate instantiation."""
        stmt = stmt.rstrip(';').strip()

        # Check for parameterized instantiation
        param_match = re.search(r'#\s*\(\s*(.*?)\s*\)', stmt)
        params = {}
        if param_match:
            params = self._parse_parameters(param_match.group(1))
            stmt = stmt.replace(param_match.group(0), '').strip()

        # Split into module type and rest
        match = re.match(r'(\w+)\s+(.*)', stmt)
        if not match:
            return {'type': 'unknown', 'error': 'Could not parse instantiation'}

        module_name = match.group(1)
        rest = match.group(2)

        # Parse instances
        instances = self._parse_instances(rest)

        return {
            'type': 'instantiation',
            'module_name': module_name,
            'instances': instances,
            'parameters': params
        }

    def _parse_parameters(self, param_text: str) -> Dict[str, str]:
        """Parse parameter assignments."""
        params = {}

        # Handle named parameters
        for assignment in param_text.split(','):
            assignment = assignment.strip()
            if '=' in assignment:
                name, value = assignment.split('=', 1)
                params[name.strip()] = value.strip()
            else:
                # Positional parameters
                params[str(len(params))] = assignment.strip()

        return params

    def _parse_instances(self, instance_text: str) -> List[Dict]:
        """Parse multiple instances."""
        instances = []

        # Split by commas, but careful with parentheses
        current = ''
        paren_level = 0
        bracket_level = 0

        for char in instance_text:
            if char == '(':
                paren_level += 1
            elif char == ')':
                paren_level -= 1
            elif char == '[':
                bracket_level += 1
            elif char == ']':
                bracket_level -= 1

            if char == ',' and paren_level == 0 and bracket_level == 0:
                if current.strip():
                    instances.append(self._parse_single_instance(current.strip()))
                current = ''
            else:
                current += char

        if current.strip():
            instances.append(self._parse_single_instance(current.strip()))

        return instances

    def _parse_single_instance(self, instance_text: str) -> Dict:
        """Parse a single instance."""
        # Get instance name and connections
        match = re.match(r'(\w+)\s*\(\s*(.*?)\s*\)', instance_text, re.DOTALL)
        if not match:
            return {'name': 'unknown', 'connections': {}}

        inst_name = match.group(1)
        conn_text = match.group(2)

        connections = self._parse_connections(conn_text)

        return {
            'name': inst_name,
            'connections': connections
        }

    def _parse_connections(self, conn_text: str) -> Dict[str, str]:
        """Parse port connections."""
        connections = {}

        # Handle named connections (.port(net))
        named_pattern = r'\.(\w+)\s*\(\s*([^)]*)\s*\)'
        for match in re.finditer(named_pattern, conn_text):
            port = match.group(1)
            net = match.group(2).strip()
            connections[port] = net

        # If no named connections, assume ordered list
        if not connections:
            nets = [n.strip() for n in conn_text.split(',')]
            for i, net in enumerate(nets):
                connections[str(i)] = net

        return connections

    def _update_statistics(self):
        """Update overall statistics."""
        self.module_stats['total']['modules'] = len(self.module_resolver.modules)
        self.module_stats['total']['files'] = len(self.verilog_files)
        self.module_stats['total']['cells'] = len(self.netlist_builder.cells)
        self.module_stats['total']['nets'] = len(self.netlist_builder.nets)

    def get_parser_info(self) -> Dict[str, Any]:
        """Get information about parsed files."""
        return {
            'files': [str(f) for f in self.verilog_files],
            'total_files': len(self.verilog_files),
            'modules': len(self.module_resolver.modules),
            'cells': len(self.netlist_builder.cells),
            'nets': len(self.netlist_builder.nets),
            'include_paths': [str(p) for p in self.include_paths],
            'defines': self.define_macros,
            'module_stats': dict(self.module_stats)
        }

    def print_summary(self):
        """Print parsing summary."""
        info = self.get_parser_info()

        logger.info("=" * 60)
        logger.info("Verilog Parser Summary")
        logger.info("=" * 60)
        logger.info(f"Files parsed: {info['total_files']}")
        logger.info(f"Modules found: {info['modules']}")
        logger.info(f"Total cells: {info['cells']}")
        logger.info(f"Total nets: {info['nets']}")
        logger.info(f"Include paths: {len(info['include_paths'])}")
        logger.info(f"Defined macros: {len(info['defines'])}")

        if info['module_stats']:
            logger.info("\nModule statistics:")
            for module, stats in info['module_stats'].items():
                if module != 'total':
                    logger.info(f"  {module}: {stats.get('instances', 0)} instances, "
                               f"{stats.get('nets', 0)} nets")

        logger.info("=" * 60)