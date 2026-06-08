"""
Configuration loader for PySTA.
Handles loading and saving configuration settings.
"""

import json
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict

from Src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class STAConfig:
    """Static Timing Analysis configuration."""

    # Analysis options
    enable_setup: bool = True
    enable_hold: bool = True
    enable_ocv: bool = False
    enable_si: bool = False
    enable_derating: bool = False

    # OCV settings
    ocv_derate_data: float = 1.0
    ocv_derate_clock: float = 1.0
    ocv_derate_early: float = 0.95
    ocv_derate_late: float = 1.05

    # SI settings
    si_aggressor_coupling_threshold: float = 0.1  # 10%
    si_noise_margin: float = 0.2  # 20%

    # Path extraction
    max_paths_per_clock: int = 10
    max_path_depth: int = 100

    # Report settings
    report_violations_only: bool = False
    report_timing_details: bool = True
    report_capacitance: bool = True
    report_transition: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create config from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


class ConfigLoader:
    """Load and save configuration from files."""

    CONFIG_DIR = Path("Config")
    CONFIG_FILE = CONFIG_DIR / "pysta_config.yaml"

    @staticmethod
    def ensure_config_dir():
        """Ensure configuration directory exists."""
        ConfigLoader.CONFIG_DIR.mkdir(exist_ok=True)

    @staticmethod
    def load_config() -> STAConfig:
        """
        Load configuration from file.

        Returns:
            STAConfig object
        """
        ConfigLoader.ensure_config_dir()

        if not ConfigLoader.CONFIG_FILE.exists():
            logger.info("No configuration file found. Using defaults.")
            return STAConfig()

        try:
            with open(ConfigLoader.CONFIG_FILE, 'r') as f:
                if ConfigLoader.CONFIG_FILE.suffix == '.json':
                    data = json.load(f)
                else:
                    data = yaml.safe_load(f)

            logger.info(f"Configuration loaded from {ConfigLoader.CONFIG_FILE}")
            return STAConfig.from_dict(data)

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return STAConfig()

    @staticmethod
    def save_config(config: STAConfig, format: str = 'yaml'):
        """
        Save configuration to file.

        Args:
            config: STAConfig object
            format: 'json' or 'yaml'
        """
        ConfigLoader.ensure_config_dir()

        file_path = ConfigLoader.CONFIG_DIR / f"pysta_config.{format}"
        data = asdict(config)

        try:
            with open(file_path, 'w') as f:
                if format == 'json':
                    json.dump(data, f, indent=2)
                else:
                    yaml.dump(data, f, default_flow_style=False)

            logger.info(f"Configuration saved to {file_path}")

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")

    @staticmethod
    def export_to_dict(config: STAConfig) -> Dict[str, Any]:
        """Export configuration to dictionary."""
        return asdict(config)