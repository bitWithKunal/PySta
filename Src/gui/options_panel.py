"""
Options panel for PySTA GUI.
Configuration options for STA analysis.
"""

from typing import Dict, Any
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QCheckBox, QLabel, QDoubleSpinBox, QSpinBox,
                             QComboBox, QPushButton, QGridLayout, QTabWidget)
from PyQt6.QtCore import pyqtSignal, Qt

from Src.utils.config_loader import STAConfig, ConfigLoader
from Src.utils.logger import get_logger

logger = get_logger(__name__)


class OptionsPanel(QWidget):
    """Configuration options for STA analysis."""

    config_changed = pyqtSignal(STAConfig)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = STAConfig()
        self.setup_ui()
        self.load_config()

    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout()

        # Create tab widget for options
        tab_widget = QTabWidget()

        # General options tab
        general_tab = self.create_general_tab()
        tab_widget.addTab(general_tab, "General")

        # OCV options tab
        ocv_tab = self.create_ocv_tab()
        tab_widget.addTab(ocv_tab, "OCV")

        # SI options tab
        si_tab = self.create_si_tab()
        tab_widget.addTab(si_tab, "SI")

        # Path options tab
        path_tab = self.create_path_tab()
        tab_widget.addTab(path_tab, "Paths")

        # Report options tab
        report_tab = self.create_report_tab()
        tab_widget.addTab(report_tab, "Reports")

        layout.addWidget(tab_widget)

        # Buttons
        button_layout = QHBoxLayout()

        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_config)
        button_layout.addWidget(self.apply_button)

        self.reset_button = QPushButton("Reset to Defaults")
        self.reset_button.clicked.connect(self.reset_config)
        button_layout.addWidget(self.reset_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def create_general_tab(self) -> QWidget:
        """Create general options tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Analysis options group
        analysis_group = QGroupBox("Analysis Options")
        analysis_layout = QVBoxLayout()

        self.setup_check = QCheckBox("Enable Setup Analysis")
        self.setup_check.setChecked(True)
        analysis_layout.addWidget(self.setup_check)

        self.hold_check = QCheckBox("Enable Hold Analysis")
        self.hold_check.setChecked(True)
        analysis_layout.addWidget(self.hold_check)

        self.ocv_check = QCheckBox("Enable OCV Derating")
        self.ocv_check.stateChanged.connect(self.toggle_ocv_options)
        analysis_layout.addWidget(self.ocv_check)

        self.si_check = QCheckBox("Enable SI Analysis")
        self.si_check.stateChanged.connect(self.toggle_si_options)
        analysis_layout.addWidget(self.si_check)

        self.derate_check = QCheckBox("Enable Derating")
        analysis_layout.addWidget(self.derate_check)

        analysis_group.setLayout(analysis_layout)
        layout.addWidget(analysis_group)

        # Corner selection
        corner_group = QGroupBox("Process Corner")
        corner_layout = QHBoxLayout()

        corner_layout.addWidget(QLabel("Corner:"))
        self.corner_combo = QComboBox()
        self.corner_combo.addItems(["typical", "best", "worst"])
        corner_layout.addWidget(self.corner_combo)

        corner_group.setLayout(corner_layout)
        layout.addWidget(corner_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_ocv_tab(self) -> QWidget:
        """Create OCV options tab."""
        widget = QWidget()
        layout = QGridLayout()

        # OCV derate factors
        row = 0

        # Data path derates
        layout.addWidget(QLabel("Data Path Derate:"), row, 0)
        self.data_derate_spin = QDoubleSpinBox()
        self.data_derate_spin.setRange(0.5, 2.0)
        self.data_derate_spin.setSingleStep(0.05)
        self.data_derate_spin.setValue(1.0)
        layout.addWidget(self.data_derate_spin, row, 1)

        row += 1
        layout.addWidget(QLabel("Clock Path Derate:"), row, 0)
        self.clock_derate_spin = QDoubleSpinBox()
        self.clock_derate_spin.setRange(0.5, 2.0)
        self.clock_derate_spin.setSingleStep(0.05)
        self.clock_derate_spin.setValue(1.0)
        layout.addWidget(self.clock_derate_spin, row, 1)

        row += 1
        layout.addWidget(QLabel("Early Path Derate:"), row, 0)
        self.early_derate_spin = QDoubleSpinBox()
        self.early_derate_spin.setRange(0.5, 2.0)
        self.early_derate_spin.setSingleStep(0.05)
        self.early_derate_spin.setValue(0.95)
        layout.addWidget(self.early_derate_spin, row, 1)

        row += 1
        layout.addWidget(QLabel("Late Path Derate:"), row, 0)
        self.late_derate_spin = QDoubleSpinBox()
        self.late_derate_spin.setRange(0.5, 2.0)
        self.late_derate_spin.setSingleStep(0.05)
        self.late_derate_spin.setValue(1.05)
        layout.addWidget(self.late_derate_spin, row, 1)

        # Enable/disable based on OCV checkbox
        self.set_ocv_widgets_enabled(False)

        widget.setLayout(layout)
        return widget

    def create_si_tab(self) -> QWidget:
        """Create SI options tab."""
        widget = QWidget()
        layout = QGridLayout()

        row = 0

        # Coupling threshold
        layout.addWidget(QLabel("Coupling Threshold (%):"), row, 0)
        self.coupling_spin = QDoubleSpinBox()
        self.coupling_spin.setRange(0, 100)
        self.coupling_spin.setSingleStep(5)
        self.coupling_spin.setSuffix("%")
        self.coupling_spin.setValue(10)
        layout.addWidget(self.coupling_spin, row, 1)

        row += 1
        layout.addWidget(QLabel("Noise Margin (%):"), row, 0)
        self.noise_spin = QDoubleSpinBox()
        self.noise_spin.setRange(0, 100)
        self.noise_spin.setSingleStep(5)
        self.noise_spin.setSuffix("%")
        self.noise_spin.setValue(20)
        layout.addWidget(self.noise_spin, row, 1)

        row += 1
        layout.addWidget(QLabel("Aggressor Count:"), row, 0)
        self.aggressor_spin = QSpinBox()
        self.aggressor_spin.setRange(0, 10)
        self.aggressor_spin.setValue(3)
        layout.addWidget(self.aggressor_spin, row, 1)

        # Enable/disable based on SI checkbox
        self.set_si_widgets_enabled(False)

        widget.setLayout(layout)
        return widget

    def create_path_tab(self) -> QWidget:
        """Create path options tab."""
        widget = QWidget()
        layout = QGridLayout()

        row = 0

        # Max paths per clock
        layout.addWidget(QLabel("Max Paths per Clock:"), row, 0)
        self.max_paths_spin = QSpinBox()
        self.max_paths_spin.setRange(1, 1000)
        self.max_paths_spin.setValue(10)
        layout.addWidget(self.max_paths_spin, row, 1)

        row += 1
        layout.addWidget(QLabel("Max Path Depth:"), row, 0)
        self.max_depth_spin = QSpinBox()
        self.max_depth_spin.setRange(1, 500)
        self.max_depth_spin.setValue(100)
        layout.addWidget(self.max_depth_spin, row, 1)

        row += 1

        # Path filtering
        filter_group = QGroupBox("Path Filtering")
        filter_layout = QVBoxLayout()

        self.filter_violations_check = QCheckBox("Show violations only")
        filter_layout.addWidget(self.filter_violations_check)

        self.filter_by_slack_check = QCheckBox("Filter by slack threshold")
        filter_layout.addWidget(self.filter_by_slack_check)

        slack_layout = QHBoxLayout()
        slack_layout.addWidget(QLabel("Slack threshold (ps):"))
        self.slack_threshold_spin = QDoubleSpinBox()
        self.slack_threshold_spin.setRange(0, 1000)
        self.slack_threshold_spin.setValue(10)
        self.slack_threshold_spin.setSuffix(" ps")
        slack_layout.addWidget(self.slack_threshold_spin)
        slack_layout.addStretch()
        filter_layout.addLayout(slack_layout)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group, row, 0, 1, 2)

        widget.setLayout(layout)
        return widget

    def create_report_tab(self) -> QWidget:
        """Create report options tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Report format
        format_group = QGroupBox("Report Format")
        format_layout = QVBoxLayout()

        self.rpt_check = QCheckBox("Generate .rpt files")
        self.rpt_check.setChecked(True)
        format_layout.addWidget(self.rpt_check)

        self.excel_check = QCheckBox("Generate .xlsx files")
        self.excel_check.setChecked(True)
        format_layout.addWidget(self.excel_check)

        format_group.setLayout(format_layout)
        layout.addWidget(format_group)

        # Report content
        content_group = QGroupBox("Report Content")
        content_layout = QVBoxLayout()

        self.details_check = QCheckBox("Include timing details")
        self.details_check.setChecked(True)
        content_layout.addWidget(self.details_check)

        self.cap_check = QCheckBox("Include capacitance")
        self.cap_check.setChecked(True)
        content_layout.addWidget(self.cap_check)

        self.transition_check = QCheckBox("Include transition times")
        self.transition_check.setChecked(True)
        content_layout.addWidget(self.transition_check)

        self.summary_check = QCheckBox("Include summary")
        self.summary_check.setChecked(True)
        content_layout.addWidget(self.summary_check)

        content_group.setLayout(content_layout)
        layout.addWidget(content_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def toggle_ocv_options(self, state):
        """Enable/disable OCV options based on checkbox."""
        enabled = state == Qt.CheckState.Checked.value
        self.set_ocv_widgets_enabled(enabled)

    def set_ocv_widgets_enabled(self, enabled: bool):
        """Enable or disable OCV widgets."""
        self.data_derate_spin.setEnabled(enabled)
        self.clock_derate_spin.setEnabled(enabled)
        self.early_derate_spin.setEnabled(enabled)
        self.late_derate_spin.setEnabled(enabled)

    def toggle_si_options(self, state):
        """Enable/disable SI options based on checkbox."""
        enabled = state == Qt.CheckState.Checked.value
        self.set_si_widgets_enabled(enabled)

    def set_si_widgets_enabled(self, enabled: bool):
        """Enable or disable SI widgets."""
        self.coupling_spin.setEnabled(enabled)
        self.noise_spin.setEnabled(enabled)
        self.aggressor_spin.setEnabled(enabled)

    def load_config(self):
        """Load configuration from file."""
        self.config = ConfigLoader.load_config()
        self.update_ui_from_config()

    def update_ui_from_config(self):
        """Update UI elements from config."""
        # General options
        self.setup_check.setChecked(self.config.enable_setup)
        self.hold_check.setChecked(self.config.enable_hold)
        self.ocv_check.setChecked(self.config.enable_ocv)
        self.si_check.setChecked(self.config.enable_si)
        self.derate_check.setChecked(self.config.enable_derating)

        # OCV options
        self.data_derate_spin.setValue(self.config.ocv_derate_data)
        self.clock_derate_spin.setValue(self.config.ocv_derate_clock)
        self.early_derate_spin.setValue(self.config.ocv_derate_early)
        self.late_derate_spin.setValue(self.config.ocv_derate_late)

        # SI options
        self.coupling_spin.setValue(self.config.si_aggressor_coupling_threshold * 100)
        self.noise_spin.setValue(self.config.si_noise_margin * 100)

        # Path options
        self.max_paths_spin.setValue(self.config.max_paths_per_clock)
        self.max_depth_spin.setValue(self.config.max_path_depth)

        # Report options
        self.details_check.setChecked(self.config.report_timing_details)
        self.cap_check.setChecked(self.config.report_capacitance)
        self.transition_check.setChecked(self.config.report_transition)

        # Enable/disable tabs based on checkboxes
        self.set_ocv_widgets_enabled(self.config.enable_ocv)
        self.set_si_widgets_enabled(self.config.enable_si)

    def update_config_from_ui(self):
        """Update config from UI elements."""
        self.config.enable_setup = self.setup_check.isChecked()
        self.config.enable_hold = self.hold_check.isChecked()
        self.config.enable_ocv = self.ocv_check.isChecked()
        self.config.enable_si = self.si_check.isChecked()
        self.config.enable_derating = self.derate_check.isChecked()

        self.config.ocv_derate_data = self.data_derate_spin.value()
        self.config.ocv_derate_clock = self.clock_derate_spin.value()
        self.config.ocv_derate_early = self.early_derate_spin.value()
        self.config.ocv_derate_late = self.late_derate_spin.value()

        self.config.si_aggressor_coupling_threshold = self.coupling_spin.value() / 100
        self.config.si_noise_margin = self.noise_spin.value() / 100

        self.config.max_paths_per_clock = self.max_paths_spin.value()
        self.config.max_path_depth = self.max_depth_spin.value()

        self.config.report_timing_details = self.details_check.isChecked()
        self.config.report_capacitance = self.cap_check.isChecked()
        self.config.report_transition = self.transition_check.isChecked()

    def apply_config(self):
        """Apply current configuration."""
        self.update_config_from_ui()
        ConfigLoader.save_config(self.config)
        self.config_changed.emit(self.config)
        logger.info("Configuration applied")

    def reset_config(self):
        """Reset configuration to defaults."""
        self.config = STAConfig()
        self.update_ui_from_config()
        self.apply_config()

    def get_config(self) -> STAConfig:
        """Get current configuration."""
        self.update_config_from_ui()
        return self.config