"""
Enhanced SDC parser for PySTA.
Supports multiple SDC files, source directives, and hierarchical constraints.
"""

import re
from typing import Dict, List, Optional, Tuple, Any, Set
from pathlib import Path

from Src.sdc_parser.clock_constraints import Clock, ClockConstraints
from Src.sdc_parser.timing_exceptions import TimingException, ExceptionType, ExceptionManager
from Src.utils.logger import get_logger
from Src.utils.file_utils import FileUtils
from Src.utils.time_utils import TimeUtils

logger = get_logger(__name__)

class SDCParser:
    """Enhanced parser for SDC constraint files with multi-file support."""

    def __init__(self):
        self.clock_constraints = ClockConstraints()
        self.exception_manager = ExceptionManager()
        self.current_clock: Optional[Clock] = None
        self.line_number = 0
        self.current_file: Optional[Path] = None
        self.sourced_files: Set[str] = set()

        # Multi-file support
        self.sdc_files: List[Path] = []
        self.search_paths: List[Path] = []

        # Command patterns
        self.commands = {
            'create_clock': self._parse_create_clock,
            'create_generated_clock': self._parse_create_generated_clock,
            'set_clock_latency': self._parse_set_clock_latency,
            'set_clock_uncertainty': self._parse_set_clock_uncertainty,
            'set_clock_transition': self._parse_set_clock_transition,
            'set_input_delay': self._parse_set_input_delay,
            'set_output_delay': self._parse_set_output_delay,
            'set_input_transition': self._parse_set_input_transition,
            'set_load': self._parse_set_load,
            'set_driving_cell': self._parse_set_driving_cell,
            'set_false_path': self._parse_set_false_path,
            'set_multicycle_path': self._parse_set_multicycle_path,
            'set_max_delay': self._parse_set_max_delay,
            'set_min_delay': self._parse_set_min_delay,
            'set_case_analysis': self._parse_set_case_analysis,
            'set_disable_timing': self._parse_set_disable_timing,
            'set_operating_conditions': self._parse_set_operating_conditions,
            'set_timing_derate': self._parse_set_timing_derate,
            'source': self._parse_source,
        }

        # Operating conditions
        self.operating_conditions: Dict[str, Any] = {}
        self.derating_factors: List[Dict[str, Any]] = []

    def add_search_path(self, path: str):
        """Add a directory to the search path for sourced files."""
        search_path = Path(path)
        if search_path.exists() and search_path.is_dir():
            self.search_paths.append(search_path)
            logger.debug(f"Added SDC search path: {path}")

    def parse_file(self, file_path: str) -> Tuple[ClockConstraints, ExceptionManager]:
        """
        Parse a single SDC file.

        Args:
            file_path: Path to .sdc file

        Returns:
            Tuple of (ClockConstraints, ExceptionManager)
        """
        logger.info(f"Parsing SDC file: {file_path}")

        # Validate file
        is_valid, error = FileUtils.validate_file(file_path, '.sdc')
        if not is_valid:
            logger.error(f"Invalid SDC file: {error}")
            raise ValueError(error)

        # Reset for this file
        self.current_file = Path(file_path)
        self.line_number = 0
        self.sourced_files.add(file_path)

        # Read file content
        content = FileUtils.read_file_with_encoding(file_path)

        # Remove comments
        content = FileUtils.extract_comments(content, 'sdc')

        # Parse line by line
        self._parse_content(content)

        logger.info(f"Successfully parsed SDC file: {len(self.clock_constraints.clocks)} clocks, "
                   f"{len(self.exception_manager.exceptions)} exceptions")

        return self.clock_constraints, self.exception_manager

    def parse_files(self, file_paths: List[str]) -> Tuple[ClockConstraints, ExceptionManager]:
        """
        Parse multiple SDC files and merge constraints.

        Args:
            file_paths: List of paths to .sdc files

        Returns:
            Tuple of merged (ClockConstraints, ExceptionManager)
        """
        logger.info(f"Parsing {len(file_paths)} SDC files")

        self.sdc_files = [Path(f) for f in file_paths]

        # Add file directories to search path
        for file_path in file_paths:
            self.add_search_path(str(Path(file_path).parent))

        # Parse each file
        for file_path in file_paths:
            try:
                self.parse_file(file_path)
            except Exception as e:
                logger.error(f"Failed to parse {file_path}: {e}")
                continue

        logger.info(f"Total constraints: {len(self.clock_constraints.clocks)} clocks, "
                   f"{len(self.exception_manager.exceptions)} exceptions from {len(file_paths)} files")

        return self.clock_constraints, self.exception_manager

    def parse_directory(self, directory: str, pattern: str = "*.sdc") -> Tuple[ClockConstraints, ExceptionManager]:
        """
        Parse all SDC files in a directory.

        Args:
            directory: Directory path
            pattern: File pattern (default: "*.sdc")

        Returns:
            Tuple of merged constraints
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            raise ValueError(f"Directory does not exist: {directory}")

        sdc_files = list(dir_path.glob(pattern))
        logger.info(f"Found {len(sdc_files)} SDC files in {directory}")

        return self.parse_files([str(f) for f in sdc_files])

    def _parse_content(self, content: str):
        """Parse SDC file content."""
        lines = content.split('\n')
        i = 0
        while i < len(lines):
            self.line_number = i + 1
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            # Handle multi-line commands
            while line.endswith('\\'):
                i += 1
                if i < len(lines):
                    line = line[:-1] + lines[i].strip()
                else:
                    break

            try:
                self._parse_command(line)
            except Exception as e:
                logger.error(f"Parse error at {self.current_file}:{self.line_number}: {e}")

            i += 1

    def _parse_command(self, line: str):
        """Parse a single SDC command."""
        # Extract command name
        match = re.match(r'(\w+)\s+', line)
        if not match:
            return

        cmd = match.group(1)

        # Find and execute parser
        parser = self.commands.get(cmd)
        if parser:
            parser(line)
        else:
            logger.debug(f"Ignoring unknown command: {cmd}")

    def _parse_source(self, line: str):
        """Parse source command to include another SDC file."""
        args = self._parse_arguments(line)

        filename = args.get('sources', [''])[0] if args.get('sources') else None
        if not filename:
            logger.warning("source command missing filename")
            return

        # Search for file
        file_path = self._find_sdc_file(filename)

        if file_path and str(file_path) not in self.sourced_files:
            logger.info(f"Sourcing SDC file: {filename}")
            self.parse_file(str(file_path))
        elif file_path:
            logger.warning(f"Already sourced file: {filename}")
        else:
            logger.warning(f"Sourced file not found: {filename}")

    def _find_sdc_file(self, filename: str) -> Optional[Path]:
        """Find an SDC file in search paths."""
        # Check relative to current file
        if self.current_file:
            candidate = self.current_file.parent / filename
            if candidate.exists():
                return candidate

        # Check search paths
        for search_path in self.search_paths:
            candidate = search_path / filename
            if candidate.exists():
                return candidate

        return None

    def _parse_create_clock(self, line: str):
        """Parse create_clock command."""
        args = self._parse_arguments(line)

        name = args.get('-name', '')
        period_str = args.get('-period', '')
        waveform = args.get('-waveform', [0, float(period_str)/2 if period_str else 0])
        sources = args.get('sources', [])

        if not period_str:
            logger.error("create_clock missing period")
            return

        # Parse period
        period = TimeUtils.parse_time_string(period_str)

        # Parse waveform
        if isinstance(waveform, str):
            waveform = [float(x) for x in waveform.split()]
        rise_time = float(waveform[0]) if waveform else 0
        fall_time = float(waveform[1]) if len(waveform) > 1 else period/2

        # Create clock
        clock_name = name or f"clock_{len(self.clock_constraints.clocks)}"

        # Check for duplicate clock
        existing = self.clock_constraints.get_clock_by_name(clock_name)
        if existing:
            logger.warning(f"Clock {clock_name} already exists, overwriting")

        clock = Clock(
            name=clock_name,
            period=period,
            waveform=(rise_time, fall_time),
            sources=sources
        )

        self.clock_constraints.add_clock(clock)
        logger.debug(f"Created clock: {clock.name} with period {period}s")

    def _parse_create_generated_clock(self, line: str):
        """Parse create_generated_clock command."""
        args = self._parse_arguments(line)

        name = args.get('-name', '')
        source = args.get('-source', '')
        divide_by = args.get('-divide_by')
        multiply_by = args.get('-multiply_by')
        duty_cycle = args.get('-duty_cycle', 50)
        invert = '-invert' in args
        edges = args.get('-edges', [])
        edge_shift = args.get('-edge_shift', [])

        if not source:
            logger.error("create_generated_clock missing source")
            return

        # Get master clock
        master_clock = self.clock_constraints.get_clock_by_source(source)
        if not master_clock:
            logger.warning(f"Master clock not found for source: {source}")
            return

        # Create generated clock
        clock_name = name or f"genclock_{len(self.clock_constraints.clocks)}"

        # Check for duplicate
        existing = self.clock_constraints.get_clock_by_name(clock_name)
        if existing:
            logger.warning(f"Clock {clock_name} already exists, overwriting")

        clock = Clock(
            name=clock_name,
            period=master_clock.period,
            waveform=master_clock.waveform,
            sources=[source],
            is_generated=True,
            master_clock=master_clock,
            divide_by=int(divide_by) if divide_by else None,
            multiply_by=int(multiply_by) if multiply_by else None
        )

        self.clock_constraints.add_clock(clock)
        logger.debug(f"Created generated clock: {clock.name}")

    def _parse_set_clock_latency(self, line: str):
        """Parse set_clock_latency command."""
        args = self._parse_arguments(line)

        latency_str = args.get('value', '')
        if not latency_str:
            return

        latency = TimeUtils.parse_time_string(latency_str)
        clock_list = args.get('-clock', [])
        source = '-source' in args
        early = '-early' in args
        late = '-late' in args
        rise = '-rise' in args
        fall = '-fall' in args
        targets = args.get('targets', [])

        # Apply to clocks
        for clock_name in clock_list:
            clock = self.clock_constraints.get_clock_by_name(clock_name)
            if clock:
                clock.latency = latency
                clock.latency_source = source
                logger.debug(f"Set latency {latency}s for clock {clock_name}")

    def _parse_set_clock_uncertainty(self, line: str):
        """Parse set_clock_uncertainty command."""
        args = self._parse_arguments(line)

        uncertainty_str = args.get('value', '')
        if not uncertainty_str:
            return

        uncertainty = TimeUtils.parse_time_string(uncertainty_str)
        from_clock = args.get('-from', [''])
        to_clock = args.get('-to', [''])
        rise = '-rise' in args
        fall = '-fall' in args
        setup = '-setup' in args
        hold = '-hold' in args

        # Store uncertainty
        for from_clk in from_clock:
            for to_clk in to_clock:
                self.clock_constraints.add_uncertainty(
                    from_clk if from_clk else None,
                    to_clk if to_clk else None,
                    uncertainty,
                    'setup' if setup else 'hold'
                )
                logger.debug(f"Set uncertainty {uncertainty}s between {from_clk} and {to_clk}")

    def _parse_set_clock_transition(self, line: str):
        """Parse set_clock_transition command."""
        args = self._parse_arguments(line)

        transition_str = args.get('value', '')
        if not transition_str:
            return

        transition = TimeUtils.parse_time_string(transition_str)
        clock_list = args.get('-clock', [])
        rise = '-rise' in args
        fall = '-fall' in args
        min_val = '-min' in args
        max_val = '-max' in args

        # Apply to clocks
        for clock_name in clock_list:
            clock = self.clock_constraints.get_clock_by_name(clock_name)
            if clock:
                if rise or (not rise and not fall):
                    clock.transition_rise = transition
                if fall or (not rise and not fall):
                    clock.transition_fall = transition
                logger.debug(f"Set transition {transition}s for clock {clock_name}")

    def _parse_set_input_delay(self, line: str):
        """Parse set_input_delay command."""
        args = self._parse_arguments(line)

        delay_str = args.get('value', '')
        if not delay_str:
            return

        delay = TimeUtils.parse_time_string(delay_str)
        clock_name = args.get('-clock', [''])[0]
        rise = '-rise' in args
        fall = '-fall' in args
        min_val = '-min' in args
        max_val = '-max' in args
        targets = args.get('targets', [])
        source_latency_included = '-source_latency_included' in args
        network_latency_included = '-network_latency_included' in args

        exception = TimingException(
            type=ExceptionType.INPUT_DELAY,
            from_pins=targets,
            to_pins=[],
            delay=delay,
            clock=clock_name,
            rise=rise,
            fall=fall,
            min_max='min' if min_val else ('max' if max_val else 'both')
        )

        self.exception_manager.add_exception(exception)
        logger.debug(f"Added input delay {delay}s on {targets}")

    def _parse_set_output_delay(self, line: str):
        """Parse set_output_delay command."""
        args = self._parse_arguments(line)

        delay_str = args.get('value', '')
        if not delay_str:
            return

        delay = TimeUtils.parse_time_string(delay_str)
        clock_name = args.get('-clock', [''])[0]
        rise = '-rise' in args
        fall = '-fall' in args
        min_val = '-min' in args
        max_val = '-max' in args
        targets = args.get('targets', [])
        source_latency_included = '-source_latency_included' in args
        network_latency_included = '-network_latency_included' in args

        exception = TimingException(
            type=ExceptionType.OUTPUT_DELAY,
            from_pins=targets,
            to_pins=[],
            delay=delay,
            clock=clock_name,
            rise=rise,
            fall=fall,
            min_max='min' if min_val else ('max' if max_val else 'both')
        )

        self.exception_manager.add_exception(exception)
        logger.debug(f"Added output delay {delay}s on {targets}")

    def _parse_set_input_transition(self, line: str):
        """Parse set_input_transition command."""
        args = self._parse_arguments(line)

        transition_str = args.get('value', '')
        if not transition_str:
            return

        transition = TimeUtils.parse_time_string(transition_str)
        clock_list = args.get('-clock', [])
        rise = '-rise' in args
        fall = '-fall' in args
        min_val = '-min' in args
        max_val = '-max' in args
        targets = args.get('targets', [])

        exception = TimingException(
            type=ExceptionType.INPUT_TRANSITION,
            from_pins=targets,
            to_pins=[],
            delay=transition,
            clock=clock_list[0] if clock_list else None,
            rise=rise,
            fall=fall,
            min_max='min' if min_val else ('max' if max_val else 'both')
        )

        self.exception_manager.add_exception(exception)
        logger.debug(f"Added input transition {transition}s on {targets}")

    def _parse_set_load(self, line: str):
        """Parse set_load command."""
        args = self._parse_arguments(line)

        load_str = args.get('value', '')
        if not load_str:
            return

        # Parse load value (could be in pf, ff, etc.)
        load = TimeUtils.parse_time_string(load_str)  # Reuse time parser for now

        pin_list = args.get('pins', [])
        wire_load = '-wire_load' in args

        exception = TimingException(
            type=ExceptionType.LOAD,
            from_pins=pin_list,
            to_pins=[],
            delay=load
        )

        self.exception_manager.add_exception(exception)
        logger.debug(f"Added load {load}F on {pin_list}")

    def _parse_set_false_path(self, line: str):
        """Parse set_false_path command."""
        args = self._parse_arguments(line)

        from_list = args.get('-from', [])
        to_list = args.get('-to', [])
        through_list = args.get('-through', [])
        rise = '-rise' in args
        fall = '-fall' in args
        setup = '-setup' in args
        hold = '-hold' in args

        exception = TimingException(
            type=ExceptionType.FALSE_PATH,
            from_pins=from_list,
            to_pins=to_list,
            through_pins=through_list,
            rise=rise,
            fall=fall,
            setup=setup,
            hold=hold
        )

        self.exception_manager.add_exception(exception)
        logger.debug(f"Added false path: from {from_list} to {to_list}")

    def _parse_set_multicycle_path(self, line: str):
        """Parse set_multicycle_path command."""
        args = self._parse_arguments(line)

        value_str = args.get('value', '')
        if not value_str:
            return

        value = int(value_str)
        from_list = args.get('-from', [])
        to_list = args.get('-to', [])
        through_list = args.get('-through', [])
        rise = '-rise' in args
        fall = '-fall' in args
        setup = '-setup' in args
        hold = '-hold' in args
        start = '-start' in args
        end = '-end' in args

        exception = TimingException(
            type=ExceptionType.MULTICYCLE_PATH,
            from_pins=from_list,
            to_pins=to_list,
            through_pins=through_list,
            value=value,
            rise=rise,
            fall=fall,
            setup=setup,
            hold=hold,
            start=start,
            end=end
        )

        self.exception_manager.add_exception(exception)
        logger.debug(f"Added multicycle path: {value} cycles from {from_list} to {to_list}")

    def _parse_set_max_delay(self, line: str):
        """Parse set_max_delay command."""
        args = self._parse_arguments(line)

        delay_str = args.get('value', '')
        if not delay_str:
            return

        delay = TimeUtils.parse_time_string(delay_str)
        from_list = args.get('-from', [])
        to_list = args.get('-to', [])
        through_list = args.get('-through', [])
        rise = '-rise' in args
        fall = '-fall' in args

        exception = TimingException(
            type=ExceptionType.MAX_DELAY,
            from_pins=from_list,
            to_pins=to_list,
            through_pins=through_list,
            delay=delay,
            rise=rise,
            fall=fall
        )

        self.exception_manager.add_exception(exception)
        logger.debug(f"Added max delay {delay}s from {from_list} to {to_list}")

    def _parse_set_min_delay(self, line: str):
        """Parse set_min_delay command."""
        args = self._parse_arguments(line)

        delay_str = args.get('value', '')
        if not delay_str:
            return

        delay = TimeUtils.parse_time_string(delay_str)
        from_list = args.get('-from', [])
        to_list = args.get('-to', [])
        through_list = args.get('-through', [])
        rise = '-rise' in args
        fall = '-fall' in args

        exception = TimingException(
            type=ExceptionType.MIN_DELAY,
            from_pins=from_list,
            to_pins=to_list,
            through_pins=through_list,
            delay=delay,
            rise=rise,
            fall=fall
        )

        self.exception_manager.add_exception(exception)
        logger.debug(f"Added min delay {delay}s from {from_list} to {to_list}")

    def _parse_set_case_analysis(self, line: str):
        """Parse set_case_analysis command."""
        args = self._parse_arguments(line)

        value = args.get('value', '')
        pin = args.get('pin', '')

        if value and pin:
            exception = TimingException(
                type=ExceptionType.CASE_ANALYSIS,
                from_pins=[pin],
                to_pins=[],
                value=value
            )
            self.exception_manager.add_exception(exception)
            logger.debug(f"Added case analysis: {pin}={value}")

    def _parse_set_disable_timing(self, line: str):
        """Parse set_disable_timing command."""
        args = self._parse_arguments(line)

        from_pin = args.get('-from', [''])[0]
        to_pin = args.get('-to', [''])[0]
        cell_list = args.get('cells', [])

        for cell in cell_list:
            exception = TimingException(
                type=ExceptionType.DISABLE_TIMING,
                from_pins=[cell],
                to_pins=[from_pin, to_pin]
            )
            self.exception_manager.add_exception(exception)
            logger.debug(f"Disabled timing for {cell} from {from_pin} to {to_pin}")

    def _parse_set_operating_conditions(self, line: str):
        """Parse set_operating_conditions command."""
        args = self._parse_arguments(line)

        analysis_type = args.get('-analysis_type', 'single')
        library = args.get('-library', '')
        max_library = args.get('-max', '')
        min_library = args.get('-min', '')

        self.operating_conditions = {
            'analysis_type': analysis_type,
            'library': library,
            'max_library': max_library,
            'min_library': min_library
        }

        logger.debug(f"Set operating conditions: {self.operating_conditions}")

    def _parse_set_timing_derate(self, line: str):
        """Parse set_timing_derate command."""
        args = self._parse_arguments(line)

        derate_str = args.get('value', '')
        if not derate_str:
            return

        derate = float(derate_str)
        early = '-early' in args
        late = '-late' in args
        cell_delay = '-cell_delay' in args
        net_delay = '-net_delay' in args
        clock = args.get('-clock', [])

        derate_info = {
            'derate': derate,
            'early': early,
            'late': late,
            'cell_delay': cell_delay,
            'net_delay': net_delay,
            'clocks': clock
        }

        self.derating_factors.append(derate_info)
        logger.debug(f"Added timing derate: {derate}")

    def _parse_set_driving_cell(self, line: str):
        """Parse set_driving_cell command."""
        args = self._parse_arguments(line)

        lib_cell = args.get('-lib_cell', '')
        from_pin = args.get('-pin', '')
        clock = args.get('-clock', [''])[0]
        rise = '-rise' in args
        fall = '-fall' in args
        min_val = '-min' in args
        max_val = '-max' in args
        targets = args.get('targets', [])

        if lib_cell:
            exception = TimingException(
                type=ExceptionType.DRIVING_CELL,
                from_pins=targets,
                to_pins=[],
                value=lib_cell,
                clock=clock,
                rise=rise,
                fall=fall,
                min_max='min' if min_val else ('max' if max_val else 'both')
            )
            self.exception_manager.add_exception(exception)
            logger.debug(f"Added driving cell {lib_cell} on {targets}")

    def _parse_arguments(self, line: str) -> Dict[str, Any]:
        """
        Parse SDC command arguments.

        Returns:
            Dictionary of arguments
        """
        args = {}

        # Remove command name
        line = re.sub(r'^\w+\s+', '', line)

        # Parse options
        i = 0
        tokens = self._tokenize(line)

        while i < len(tokens):
            token = tokens[i]

            if token.startswith('-'):
                # This is an option
                option = token
                i += 1

                if i < len(tokens) and not tokens[i].startswith('-'):
                    # Option has value
                    if option in ['-waveform', '-edges', '-edge_shift']:
                        # Collect multiple values
                        values = []
                        while i < len(tokens) and not tokens[i].startswith('-'):
                            values.append(tokens[i])
                            i += 1
                        args[option] = values
                    else:
                        args[option] = tokens[i]
                        i += 1
                else:
                    # Flag option
                    args[option] = True
            else:
                # Collect targets/sources
                targets = []
                while i < len(tokens):
                    targets.append(tokens[i])
                    i += 1

                if targets:
                    # Try to determine if this is a value or target
                    if len(targets) == 1 and targets[0].replace('.', '').replace('-', '').isdigit():
                        args['value'] = targets[0]
                    else:
                        args['targets' if 'targets' not in args else 'sources'] = targets
                break

        # Special handling for value position
        if 'sources' in args and not args.get('sources'):
            # First token might be the value
            first_tokens = self._tokenize(line.split('-')[0].strip())
            if first_tokens:
                args['value'] = first_tokens[0]

        return args

    def _tokenize(self, line: str) -> List[str]:
        """
        Tokenize line respecting brackets and quotes.

        Args:
            line: Input line

        Returns:
            List of tokens
        """
        tokens = []
        current = []
        in_brackets = 0
        in_quotes = False
        quote_char = None

        for char in line:
            if char in ['"', "'"] and not in_brackets:
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif quote_char == char:
                    in_quotes = False
                    quote_char = None
                current.append(char)
            elif char == '[' and not in_quotes:
                in_brackets += 1
                current.append(char)
            elif char == ']' and not in_quotes:
                in_brackets -= 1
                current.append(char)
            elif char.isspace() and not in_quotes and in_brackets == 0:
                if current:
                    tokens.append(''.join(current))
                    current = []
            else:
                current.append(char)

        if current:
            tokens.append(''.join(current))

        return tokens

    def get_parser_info(self) -> Dict[str, Any]:
        """Get information about parsed SDC files."""
        return {
            'files': [str(f) for f in self.sdc_files],
            'total_files': len(self.sdc_files),
            'sourced_files': list(self.sourced_files),
            'clocks': len(self.clock_constraints.clocks),
            'generated_clocks': len(self.clock_constraints.generated_clocks),
            'exceptions': len(self.exception_manager.exceptions),
            'search_paths': [str(p) for p in self.search_paths],
            'operating_conditions': self.operating_conditions,
            'derating_factors': self.derating_factors
        }

    def print_summary(self):
        """Print parsing summary."""
        info = self.get_parser_info()

        logger.info("=" * 60)
        logger.info("SDC Parser Summary")
        logger.info("=" * 60)
        logger.info(f"Files parsed: {info['total_files']}")
        logger.info(f"Clocks defined: {info['clocks']}")
        logger.info(f"Generated clocks: {info['generated_clocks']}")
        logger.info(f"Timing exceptions: {info['exceptions']}")
        logger.info(f"Search paths: {len(info['search_paths'])}")

        if info['operating_conditions']:
            logger.info(f"\nOperating conditions: {info['operating_conditions']}")

        if info['derating_factors']:
            logger.info(f"\nDerating factors: {len(info['derating_factors'])}")

        logger.info("=" * 60)