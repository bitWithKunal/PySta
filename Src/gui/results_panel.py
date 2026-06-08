"""
Results panel for PySTA GUI.
Displays timing analysis results.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QPushButton, QLabel, QComboBox, QGroupBox,
                             QTabWidget, QSplitter, QTextEdit, QTreeWidget,
                             QTreeWidgetItem, QAbstractItemView, QMenu,
                             QFileDialog)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QColor, QBrush, QFont, QAction

from Src.utils.logger import get_logger
from Src.utils.time_utils import TimeUtils

logger = get_logger(__name__)


class ResultsPanel(QWidget):
    """Panel for displaying timing analysis results."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.results = {}
        self.current_paths = []
        self.table = None  # Will be set in create_results_tab
        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout()

        # Summary bar
        summary_layout = QHBoxLayout()

        self.summary_label = QLabel("No analysis results available")
        self.summary_label.setStyleSheet("font-weight: bold; padding: 5px;")
        summary_layout.addWidget(self.summary_label)

        summary_layout.addStretch()

        # Export button
        self.export_btn = QPushButton("Export Results")
        self.export_btn.clicked.connect(self.export_results)
        self.export_btn.setEnabled(False)
        summary_layout.addWidget(self.export_btn)

        layout.addLayout(summary_layout)

        # Create main splitter
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Results tabs
        self.tab_widget = QTabWidget()

        # Setup results tab
        self.setup_tab = self.create_results_tab("Setup")
        self.tab_widget.addTab(self.setup_tab, "Setup Paths")

        # Hold results tab
        self.hold_tab = self.create_results_tab("Hold")
        self.tab_widget.addTab(self.hold_tab, "Hold Paths")

        # Violations tab
        self.violations_tab = self.create_violations_tab()
        self.tab_widget.addTab(self.violations_tab, "Violations")

        # Summary tab
        self.summary_tab = self.create_summary_tab()
        self.tab_widget.addTab(self.summary_tab, "Summary")

        splitter.addWidget(self.tab_widget)

        # Path details
        self.details_widget = self.create_details_widget()
        splitter.addWidget(self.details_widget)

        # Set initial sizes
        splitter.setSizes([600, 300])

        layout.addWidget(splitter)

        self.setLayout(layout)

    def create_results_tab(self, analysis_type: str) -> QWidget:
        """Create a tab for displaying timing paths."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Toolbar
        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("Clock Domain:"))
        self.clock_combo = QComboBox()
        self.clock_combo.addItem("All")
        toolbar.addWidget(self.clock_combo)

        toolbar.addWidget(QLabel("Sort by:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Slack (worst first)", "Slack (best first)", "Path Delay"])
        toolbar.addWidget(self.sort_combo)

        toolbar.addStretch()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_results)
        toolbar.addWidget(self.refresh_btn)

        layout.addLayout(toolbar)

        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Slack", "From", "To", "Path Delay", "Clock", "Type", "Violation"
        ])

        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)

        # Enable sorting
        self.table.setSortingEnabled(True)

        # Selection behavior
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        # Connect selection changed
        self.table.itemSelectionChanged.connect(self.on_path_selected)

        # Context menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        layout.addWidget(self.table)

        widget.setLayout(layout)
        return widget

    def create_violations_tab(self) -> QWidget:
        """Create tab for displaying violations."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Violations table
        self.violations_table = QTableWidget()
        self.violations_table.setColumnCount(6)
        self.violations_table.setHorizontalHeaderLabels([
            "Slack", "From", "To", "Required", "Arrival", "Type"
        ])

        header = self.violations_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.violations_table)

        widget.setLayout(layout)
        return widget

    def create_summary_tab(self) -> QWidget:
        """Create tab for timing summary."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Summary text
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setFont(QFont("Courier New", 10))
        layout.addWidget(self.summary_text)

        widget.setLayout(layout)
        return widget

    def create_details_widget(self) -> QWidget:
        """Create widget for path details."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Title
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("Path Details:"))

        self.copy_details_btn = QPushButton("Copy")
        self.copy_details_btn.clicked.connect(self.copy_path_details)
        title_layout.addWidget(self.copy_details_btn)

        title_layout.addStretch()
        layout.addLayout(title_layout)

        # Path details tree
        self.details_tree = QTreeWidget()
        self.details_tree.setHeaderLabels(["Stage", "Cell/Net", "Delay", "Slew", "Transition"])
        layout.addWidget(self.details_tree)

        # Path metrics
        metrics_layout = QGridLayout()

        metrics_layout.addWidget(QLabel("Path Delay:"), 0, 0)
        self.path_delay_label = QLabel("-")
        metrics_layout.addWidget(self.path_delay_label, 0, 1)

        metrics_layout.addWidget(QLabel("Required Time:"), 0, 2)
        self.required_label = QLabel("-")
        metrics_layout.addWidget(self.required_label, 0, 3)

        metrics_layout.addWidget(QLabel("Slack:"), 1, 0)
        self.slack_label = QLabel("-")
        metrics_layout.addWidget(self.slack_label, 1, 1)

        metrics_layout.addWidget(QLabel("Clock:"), 1, 2)
        self.clock_label = QLabel("-")
        metrics_layout.addWidget(self.clock_label, 1, 3)

        layout.addLayout(metrics_layout)

        widget.setLayout(layout)
        return widget

    def set_results(self, results: dict):
        """Set analysis results."""
        self.results = results

        # Update clocks combo
        self.update_clock_combo()

        # Populate tables
        self.populate_setup_table()
        self.populate_hold_table()
        self.populate_violations_table()
        self.populate_summary()

        # Enable export button
        self.export_btn.setEnabled(True)

        logger.info("Results panel updated with analysis results")

    def update_clock_combo(self):
        """Update clock domain combo box."""
        current = self.clock_combo.currentText()
        self.clock_combo.clear()
        self.clock_combo.addItem("All")

        # Add clocks from results
        setup_results = self.results.get('setup_results', {})
        clocks = setup_results.get('clocks', [])

        for clock in clocks:
            if isinstance(clock, dict):
                clock_name = clock.get('name', 'Unknown')
            else:
                clock_name = str(clock)
            self.clock_combo.addItem(clock_name)

        # Restore previous selection if possible
        index = self.clock_combo.findText(current)
        if index >= 0:
            self.clock_combo.setCurrentIndex(index)

    def populate_setup_table(self):
        """Populate setup paths table."""
        setup_results = self.results.get('setup_results', {})
        paths = setup_results.get('paths', [])

        self.current_paths = paths
        # Get the table from setup_tab
        table = self.setup_tab.findChild(QTableWidget)
        self.populate_table(table, paths, 'setup')

    def populate_hold_table(self):
        """Populate hold paths table."""
        hold_results = self.results.get('hold_results', {})
        paths = hold_results.get('paths', [])

        table = self.hold_tab.findChild(QTableWidget)
        self.populate_table(table, paths, 'hold')

    def populate_table(self, table: QTableWidget, paths: List[Dict],
                       analysis_type: str):
        """Populate a table with timing paths."""
        if not table:
            return

        table.setRowCount(len(paths))

        for row, path in enumerate(paths):
            # Slack
            slack = path.get('slack', 0)
            slack_item = QTableWidgetItem(TimeUtils.format_time(slack))
            if slack < 0:
                slack_item.setForeground(QBrush(QColor(255, 100, 100)))
                slack_item.setBackground(QBrush(QColor(80, 40, 40)))
            elif slack < 100e-12:  # 100ps
                slack_item.setForeground(QBrush(QColor(255, 255, 100)))
                slack_item.setBackground(QBrush(QColor(80, 80, 40)))
            else:
                slack_item.setForeground(QBrush(QColor(100, 255, 100)))
                slack_item.setBackground(QBrush(QColor(40, 80, 40)))

            slack_item.setData(Qt.ItemDataRole.UserRole, path)
            table.setItem(row, 0, slack_item)

            # From
            from_item = QTableWidgetItem(path.get('from', 'Unknown'))
            table.setItem(row, 1, from_item)

            # To
            to_item = QTableWidgetItem(path.get('to', 'Unknown'))
            table.setItem(row, 2, to_item)

            # Path delay
            delay = path.get('delay', 0)
            delay_item = QTableWidgetItem(TimeUtils.format_time(delay))
            table.setItem(row, 3, delay_item)

            # Clock
            clock_item = QTableWidgetItem(path.get('clock', 'Unknown'))
            table.setItem(row, 4, clock_item)

            # Type
            type_item = QTableWidgetItem(analysis_type)
            table.setItem(row, 5, type_item)

            # Violation
            violation = "Yes" if slack < 0 else "No"
            violation_item = QTableWidgetItem(violation)
            if slack < 0:
                violation_item.setForeground(QBrush(QColor(255, 100, 100)))
            table.setItem(row, 6, violation_item)

    def populate_violations_table(self):
        """Populate violations table."""
        violations = []

        # Collect setup violations
        setup_results = self.results.get('setup_results', {})
        for path in setup_results.get('paths', []):
            if path.get('slack', 0) < 0:
                path['type'] = 'setup'
                violations.append(path)

        # Collect hold violations
        hold_results = self.results.get('hold_results', {})
        for path in hold_results.get('paths', []):
            if path.get('slack', 0) < 0:
                path['type'] = 'hold'
                violations.append(path)

        # Sort by slack (most negative first)
        violations.sort(key=lambda x: x.get('slack', 0))

        self.violations_table.setRowCount(len(violations))

        for row, path in enumerate(violations):
            # Slack
            slack = path.get('slack', 0)
            slack_item = QTableWidgetItem(TimeUtils.format_time(slack))
            slack_item.setForeground(QBrush(QColor(255, 100, 100)))
            slack_item.setBackground(QBrush(QColor(80, 40, 40)))
            self.violations_table.setItem(row, 0, slack_item)

            # From
            self.violations_table.setItem(row, 1, QTableWidgetItem(path.get('from', 'Unknown')))

            # To
            self.violations_table.setItem(row, 2, QTableWidgetItem(path.get('to', 'Unknown')))

            # Required
            required = path.get('required', 0)
            self.violations_table.setItem(row, 3, QTableWidgetItem(TimeUtils.format_time(required)))

            # Arrival
            arrival = path.get('arrival', 0)
            self.violations_table.setItem(row, 4, QTableWidgetItem(TimeUtils.format_time(arrival)))

            # Type
            self.violations_table.setItem(row, 5, QTableWidgetItem(path.get('type', 'Unknown')))

    def populate_summary(self):
        """Populate summary tab."""
        summary = []
        summary.append("=" * 80)
        summary.append("PySTA Timing Summary")
        summary.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        summary.append("=" * 80)
        summary.append("")

        # Clock summary
        clock_constraints = self.results.get('clock_constraints')
        if clock_constraints:
            summary.append("Clocks:")
            for clock in clock_constraints.get_all_clocks():
                summary.append(f"  {clock.name}: period={TimeUtils.format_time(clock.period)}")
            summary.append("")

        # Setup summary
        setup_results = self.results.get('setup_results', {})
        if setup_results:
            summary.append("Setup Timing:")
            summary.append(f"  Total paths: {len(setup_results.get('paths', []))}")
            summary.append(f"  Violations: {setup_results.get('violations', 0)}")
            summary.append(f"  Worst slack: {TimeUtils.format_time(setup_results.get('worst_slack', 0))}")
            summary.append(f"  TNS: {TimeUtils.format_time(setup_results.get('tns', 0))}")
            summary.append("")

        # Hold summary
        hold_results = self.results.get('hold_results', {})
        if hold_results:
            summary.append("Hold Timing:")
            summary.append(f"  Total paths: {len(hold_results.get('paths', []))}")
            summary.append(f"  Violations: {hold_results.get('violations', 0)}")
            summary.append(f"  Worst slack: {TimeUtils.format_time(hold_results.get('worst_slack', 0))}")
            summary.append(f"  TNS: {TimeUtils.format_time(hold_results.get('tns', 0))}")
            summary.append("")

        # Design stats
        graph_builder = self.results.get('graph_builder')
        if graph_builder:
            summary.append("Design Statistics:")
            summary.append(f"  Total nodes: {len(graph_builder.get_all_nodes())}")
            summary.append(f"  Total edges: {graph_builder.edge_manager.get_num_edges()}")
            summary.append(f"  Start points: {len(graph_builder.get_startpoints())}")
            summary.append(f"  End points: {len(graph_builder.get_endpoints())}")
            summary.append("")

        summary.append("=" * 80)

        self.summary_text.setText("\n".join(summary))

    def on_path_selected(self):
        """Handle path selection in table."""
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            return

        # Get the first selected item's row
        row = selected_rows[0].row()
        path_item = self.table.item(row, 0)

        if path_item:
            path = path_item.data(Qt.ItemDataRole.UserRole)
            self.show_path_details(path)

    def show_path_details(self, path: Dict):
        """Show detailed path information."""
        # Clear tree
        self.details_tree.clear()

        # Path metrics
        delay = path.get('delay', 0)
        self.path_delay_label.setText(TimeUtils.format_time(delay))

        required = path.get('required', 0)
        self.required_label.setText(TimeUtils.format_time(required))

        slack = path.get('slack', 0)
        slack_text = TimeUtils.format_time(slack)
        if slack < 0:
            slack_text = f"<font color='red'>{slack_text}</font>"
        elif slack < 100e-12:
            slack_text = f"<font color='yellow'>{slack_text}</font>"
        else:
            slack_text = f"<font color='green'>{slack_text}</font>"
        self.slack_label.setText(slack_text)

        clock = path.get('clock', 'Unknown')
        self.clock_label.setText(clock)

        # Path stages
        stages = path.get('stages', [])
        for stage in stages:
            item = QTreeWidgetItem([
                stage.get('type', ''),
                stage.get('name', ''),
                TimeUtils.format_time(stage.get('delay', 0)),
                TimeUtils.format_time(stage.get('slew', 0)),
                stage.get('transition', 'rise')
            ])
            self.details_tree.addTopLevelItem(item)

    def show_context_menu(self, pos):
        """Show context menu for table."""
        menu = QMenu()

        view_path_action = QAction("View Path Details", self)
        view_path_action.triggered.connect(self.view_selected_path)
        menu.addAction(view_path_action)

        plot_path_action = QAction("Plot Path", self)
        plot_path_action.triggered.connect(self.plot_selected_path)
        menu.addAction(plot_path_action)

        export_path_action = QAction("Export Path", self)
        export_path_action.triggered.connect(self.export_selected_path)
        menu.addAction(export_path_action)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def view_selected_path(self):
        """View details of selected path."""
        self.on_path_selected()

    def plot_selected_path(self):
        """Plot selected timing path."""
        # This would connect to plotting engine
        logger.info("Plot path requested")

    def export_selected_path(self):
        """Export selected path to file."""
        # Get selected path
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        path_item = self.table.item(row, 0)

        if path_item:
            path = path_item.data(Qt.ItemDataRole.UserRole)

            # Save to file
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Path",
                "path_details.txt",
                "Text Files (*.txt);;All Files (*)"
            )

            if file_path:
                self.export_path_to_file(path, file_path)

    def export_path_to_file(self, path: Dict, file_path: str):
        """Export path details to file."""
        try:
            with open(file_path, 'w') as f:
                f.write("Timing Path Details\n")
                f.write("=" * 60 + "\n\n")

                f.write(f"From: {path.get('from', 'Unknown')}\n")
                f.write(f"To: {path.get('to', 'Unknown')}\n")
                f.write(f"Clock: {path.get('clock', 'Unknown')}\n")
                f.write(f"Path Delay: {TimeUtils.format_time(path.get('delay', 0))}\n")
                f.write(f"Required: {TimeUtils.format_time(path.get('required', 0))}\n")
                f.write(f"Slack: {TimeUtils.format_time(path.get('slack', 0))}\n\n")

                f.write("Path Stages:\n")
                f.write("-" * 60 + "\n")

                for stage in path.get('stages', []):
                    f.write(f"{stage.get('type', ''):10} {stage.get('name', ''):30} "
                            f"delay={TimeUtils.format_time(stage.get('delay', 0))} "
                            f"slew={TimeUtils.format_time(stage.get('slew', 0))}\n")

            logger.info(f"Path exported to {file_path}")

        except Exception as e:
            logger.error(f"Failed to export path: {e}")

    def copy_path_details(self):
        """Copy path details to clipboard."""
        # Implementation would copy to system clipboard
        pass

    def refresh_results(self):
        """Refresh displayed results."""
        # Re-populate tables based on current filters
        self.populate_setup_table()
        self.populate_hold_table()

    def export_results(self):
        """Export all results to file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Results",
            f"pysta_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*)"
        )

        if file_path:
            try:
                with open(file_path, 'w') as f:
                    # Write summary
                    f.write(self.summary_text.toPlainText())

                    # Write setup paths
                    f.write("\n\nSetup Paths:\n")
                    f.write("=" * 80 + "\n")
                    for path in self.results.get('setup_results', {}).get('paths', []):
                        f.write(f"Slack: {TimeUtils.format_time(path.get('slack', 0))} "
                                f"From: {path.get('from', 'Unknown')} "
                                f"To: {path.get('to', 'Unknown')}\n")

                    # Write hold paths
                    f.write("\n\nHold Paths:\n")
                    f.write("=" * 80 + "\n")
                    for path in self.results.get('hold_results', {}).get('paths', []):
                        f.write(f"Slack: {TimeUtils.format_time(path.get('slack', 0))} "
                                f"From: {path.get('from', 'Unknown')} "
                                f"To: {path.get('to', 'Unknown')}\n")

                logger.info(f"Results exported to {file_path}")

            except Exception as e:
                logger.error(f"Failed to export results: {e}")