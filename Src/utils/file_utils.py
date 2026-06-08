"""
File utility functions for PySTA.
Handles file operations and validation with better error handling.
"""

import os
import re
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
import chardet

from Src.utils.logger import get_logger

logger = get_logger(__name__)

class FileUtils:
    """Utility class for file operations."""

    SUPPORTED_EXTENSIONS = {
        '.lib': 'Liberty Library',
        '.v': 'Verilog Netlist',
        '.sdc': 'SDC Constraints',
        '.vhd': 'VHDL (experimental)',
        '.vhdl': 'VHDL (experimental)'
    }

    @staticmethod
    def validate_file(file_path: str, expected_ext: Optional[str] = None,
                     case_sensitive: bool = False) -> Tuple[bool, str]:
        """
        Validate if file exists and has correct extension.

        Args:
            file_path: Path to the file
            expected_ext: Expected file extension (e.g., '.lib')
            case_sensitive: Whether extension check is case sensitive

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not file_path:
            return False, "No file path provided"

        path = Path(file_path)

        # Check if file exists
        if not path.exists():
            return False, f"File does not exist: {file_path}"

        if not path.is_file():
            return False, f"Path is not a file: {file_path}"

        # Check file size (empty file?)
        if path.stat().st_size == 0:
            return False, f"File is empty: {file_path}"

        # Check extension if expected
        if expected_ext:
            file_suffix = path.suffix.lower() if not case_sensitive else path.suffix
            expected = expected_ext.lower() if not case_sensitive else expected_ext

            # Handle case where expected_ext doesn't start with dot
            if not expected.startswith('.'):
                expected = '.' + expected

            if file_suffix != expected:
                return False, (f"Invalid file type. Expected {expected_ext} file, "
                             f"got {path.suffix}")

        # Try to read first few bytes to verify it's readable
        try:
            with open(path, 'rb') as f:
                header = f.read(1024)
                if not header:
                    return False, f"File appears to be empty or unreadable: {file_path}"
        except Exception as e:
            return False, f"Cannot read file: {str(e)}"

        return True, "File is valid"

    @staticmethod
    def read_file_with_encoding(file_path: str) -> str:
        """
        Read file with automatic encoding detection.

        Args:
            file_path: Path to the file

        Returns:
            File content as string
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Try common encodings first
        encodings_to_try = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']

        for encoding in encodings_to_try:
            try:
                with open(path, 'r', encoding=encoding) as f:
                    content = f.read()
                    logger.debug(f"Successfully read {file_path} with {encoding} encoding")
                    return content
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.warning(f"Error reading with {encoding}: {e}")
                continue

        # Fallback to chardet detection
        try:
            with open(path, 'rb') as f:
                raw_data = f.read()
                result = chardet.detect(raw_data)
                encoding = result['encoding'] or 'utf-8'

                content = raw_data.decode(encoding, errors='replace')
                logger.info(f"Detected encoding {encoding} for {file_path}")
                return content
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            raise

    @staticmethod
    def find_files(directory: str, pattern: str, recursive: bool = True) -> List[Path]:
        """
        Find files matching pattern in directory.

        Args:
            directory: Directory to search
            pattern: File pattern (e.g., "*.v")
            recursive: Search subdirectories recursively

        Returns:
            List of matching file paths
        """
        path = Path(directory)
        if not path.exists() or not path.is_dir():
            return []

        if recursive:
            return list(path.rglob(pattern))
        else:
            return list(path.glob(pattern))

    @staticmethod
    def get_file_size(file_path: str) -> str:
        """
        Get human-readable file size.

        Args:
            file_path: Path to the file

        Returns:
            Formatted file size (e.g., "1.23 MB")
        """
        try:
            size = os.path.getsize(file_path)

            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.2f} {unit}"
                size /= 1024.0

            return f"{size:.2f} TB"
        except Exception:
            return "Unknown"

    @staticmethod
    def extract_comments(content: str, file_type: str) -> str:
        """
        Remove comments from file content.

        Args:
            content: File content
            file_type: Type of file ('verilog', 'sdc', 'liberty')

        Returns:
            Content without comments
        """
        if file_type == 'verilog':
            # Remove // comments
            content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
            # Remove /* */ comments
            content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        elif file_type == 'sdc':
            # Remove # comments
            content = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
        elif file_type == 'liberty':
            # Remove /* */ comments
            content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

        # Remove empty lines
        lines = [line for line in content.split('\n') if line.strip()]
        return '\n'.join(lines)

    @staticmethod
    def is_binary_file(file_path: str) -> bool:
        """
        Check if file is binary.

        Args:
            file_path: Path to the file

        Returns:
            True if file appears to be binary
        """
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                if b'\0' in chunk:  # Null bytes indicate binary
                    return True

                # Check text/binary ratio
                text_chars = bytes(range(32, 127)) + b'\n\r\t\f\b'
                non_text = sum(1 for byte in chunk if byte not in text_chars)
                return non_text > len(chunk) * 0.3
        except Exception:
            return True

    @staticmethod
    def get_file_info(file_path: str) -> Dict[str, Any]:
        """
        Get detailed file information.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with file information
        """
        path = Path(file_path)

        # Basic info
        info = {
            'name': path.name,
            'stem': path.stem,
            'suffix': path.suffix,
            'size': FileUtils.get_file_size(file_path),
            'size_bytes': 0,
            'modified': 'N/A',
            'directory': str(path.parent),
            'exists': path.exists(),
            'is_file': False,
            'is_binary': False,
            'detected_type': 'unknown'
        }

        if path.exists():
            try:
                info['size_bytes'] = path.stat().st_size
                info['modified'] = datetime.fromtimestamp(path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                info['is_file'] = path.is_file()
                info['is_binary'] = FileUtils.is_binary_file(file_path)

                # Detect file type from content if possible
                if info['is_file'] and not info['is_binary'] and info['size_bytes'] > 0:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            first_line = f.readline().strip().lower()
                            second_line = f.readline().strip().lower() if f else ''

                        # Liberty detection
                        if 'library' in first_line or 'library' in second_line:
                            info['detected_type'] = 'liberty'
                        # Verilog detection
                        elif first_line.startswith('module') or 'module' in first_line:
                            info['detected_type'] = 'verilog'
                        # SDC detection
                        elif first_line.startswith('create_clock') or 'create_clock' in first_line:
                            info['detected_type'] = 'sdc'
                        elif 'set_clock' in first_line or 'set_input_delay' in first_line:
                            info['detected_type'] = 'sdc'
                        # Check by extension as fallback
                        elif path.suffix.lower() == '.lib':
                            info['detected_type'] = 'liberty'
                        elif path.suffix.lower() == '.v':
                            info['detected_type'] = 'verilog'
                        elif path.suffix.lower() == '.sdc':
                            info['detected_type'] = 'sdc'
                    except Exception:
                        # Fallback to extension-based detection
                        if path.suffix.lower() == '.lib':
                            info['detected_type'] = 'liberty'
                        elif path.suffix.lower() == '.v':
                            info['detected_type'] = 'verilog'
                        elif path.suffix.lower() == '.sdc':
                            info['detected_type'] = 'sdc'
            except Exception as e:
                logger.warning(f"Error getting file info for {file_path}: {e}")

        return info

    @staticmethod
    def ensure_directory(file_path: str) -> Path:
        """
        Ensure directory exists for a file path.

        Args:
            file_path: Path to file

        Returns:
            Path object of the directory
        """
        path = Path(file_path)
        directory = path.parent
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @staticmethod
    def get_file_extension(file_path: str) -> str:
        """
        Get file extension with proper handling.

        Args:
            file_path: Path to file

        Returns:
            File extension (e.g., '.lib')
        """
        path = Path(file_path)
        return path.suffix.lower()

    @staticmethod
    def get_filename_without_extension(file_path: str) -> str:
        """
        Get filename without extension.

        Args:
            file_path: Path to file

        Returns:
            Filename without extension
        """
        path = Path(file_path)
        return path.stem

    @staticmethod
    def is_text_file(file_path: str) -> bool:
        """
        Check if file is a text file.

        Args:
            file_path: Path to file

        Returns:
            True if file appears to be text
        """
        return not FileUtils.is_binary_file(file_path)

    @staticmethod
    def count_lines(file_path: str) -> int:
        """
        Count lines in a text file.

        Args:
            file_path: Path to file

        Returns:
            Number of lines
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return sum(1 for _ in f)
        except Exception:
            return 0