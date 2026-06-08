"""
Timing panel for PySTA GUI.
Displays timing graph and path visualization.
"""

from typing import Dict, List, Optional, Any
import tempfile
import webbrowser

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QComboBox, QGroupBox, QCheckBox,
                             QSpinBox, QFileDialog, QMessageBox)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPixmap

from Src.timing_graph.timing_graph_builder import TimingGraphBuilder
from Src.timing_graph.path_extractor import PathExtractor
from Src.plotting_engine.timing_plotter import TimingPlotter
from Src.plotting_engine.path_visualizer import PathVisualizer
from Src.plotting_engine.clock_waveform_plotter import ClockWaveformPlotter
from Src.utils.logger import get_logger
from Src.utils.time_utils import TimeUtils

logger = get_logger(__name__)


class TimingPanel(QWidget):
    """Panel for timing visualization."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.graph_builder = None
        self.path_extractor = None
        self.timing_plotter = TimingPlotter()
        self.path_visualizer = PathVisualizer()
        self.clock_plotter = ClockWaveformPlotter()

        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout()

        # Controls
        controls_layout = QHBoxLayout()

        # Graph controls
        graph_group = QGroupBox("Graph Controls")
        graph_layout = QHBoxLayout()

        self.show_graph_btn = QPushButton("Show Timing Graph")
        self.show_graph_btn.clicked.connect(self.show_timing_graph)
        graph_layout.addWidget(self.show_graph_btn)

        self.export_graph_btn = QPushButton("Export Graph")
        self.export_graph_btn.clicked.connect(self.export_graph)
        graph_layout.addWidget(self.export_graph_btn)

        graph_group.setLayout(graph_layout)
        controls_layout.addWidget(graph_group)

        # Path controls
        path_group = QGroupBox("Path Controls")
        path_layout = QHBoxLayout()

        path_layout.addWidget(QLabel("Path Type:"))
        self.path_type_combo = QComboBox()
        self.path_type_combo.addItems(["Setup Worst", "Setup Best", "Hold Worst", "Hold Best"])
        path_layout.addWidget(self.path_type_combo)

        self.num_paths_spin = QSpinBox()
        self.num_paths_spin.setRange(1, 100)
        self.num_paths_spin.setValue(10)
        self.num_paths_spin.setSuffix(" paths")
        path_layout.addWidget(self.num_paths_spin)

        self.show_paths_btn = QPushButton("Show Paths")
        self.show_paths_btn.clicked.connect(self.show_timing_paths)
        path_layout.addWidget(self.show_paths_btn)

        path_group.setLayout(path_layout)
        controls_layout.addWidget(path_group)

        # Clock controls
        clock_group = QGroupBox("Clock Controls")
        clock_layout = QHBoxLayout()

        self.clock_combo = QComboBox()
        self.clock_combo.addItem("All Clocks")
        clock_layout.addWidget(self.clock_combo)

        self.show_waveform_btn = QPushButton("Show Waveforms")
        self.show_waveform_btn.clicked.connect(self.show_clock_waveforms)
        clock_layout.addWidget(self.show_waveform_btn)

        clock_group.setLayout(clock_layout)
        controls_layout.addWidget(clock_group)

        layout.addLayout(controls_layout)

        # Visualization area
        self.plot_label = QLabel()
        self.plot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.plot_label.setMinimumHeight(400)
        self.plot_label.setStyleSheet("border: 1px solid gray; background-color: white;")
        layout.addWidget(self.plot_label)

        # Status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)

        self.setLayout(layout)

    def set_data(self, data: dict):
        """Set parsed data."""
        self.graph_builder = data.get('graph_builder')

        # Update clock combo
        clock_constraints = data.get('clock_constraints')
        if clock_constraints:
            self.clock_combo.clear()
            self.clock_combo.addItem("All Clocks")
            for clock in clock_constraints.get_all_clocks():
                self.clock_combo.addItem(clock.name)

    def show_timing_graph(self):
        """Show the timing graph visualization."""
        if not self.graph_builder:
            self.status_label.setText("No timing graph available")
            return

        try:
            # Convert to NetworkX and plot
            G = self.graph_builder.to_networkx()

            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
                temp_file = f.name

            # Plot graph
            self.timing_plotter.plot_graph(G, temp_file)

            # Open in browser
            webbrowser.open(f'file://{temp_file}')

            self.status_label.setText("Timing graph opened in browser")
            logger.info("Timing graph visualization opened")

        except Exception as e:
            self.status_label.setText(f"Error showing graph: {str(e)}")
            logger.error(f"Failed to show timing graph: {e}", exc_info=True)

    def show_timing_paths(self):
        """Show timing paths visualization."""
        if not self.graph_builder:
            self.status_label.setText("No timing graph available")
            return

        try:
            # Get path type
            path_type = self.path_type_combo.currentText()
            num_paths = self.num_paths_spin.value()

            # Extract paths
            path_extractor = PathExtractor(self.graph_builder.edge_manager)

            if 'Setup' in path_type:
                if 'Worst' in path_type:
                    paths = path_extractor.get_worst_setup_paths(num_paths)
                else:
                    paths = path_extractor.get_best_setup_paths(num_paths)
            else:
                if 'Worst' in path_type:
                    paths = path_extractor.get_worst_hold_paths(num_paths)
                else:
                    paths = path_extractor.get_best_hold_paths(num_paths)

            if not paths:
                self.status_label.setText("No paths found")
                return

            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
                temp_file = f.name

            # Visualize paths
            self.path_visualizer.visualize_paths(paths, temp_file)

            # Open in browser
            webbrowser.open(f'file://{temp_file}')

            self.status_label.setText(f"Showing {len(paths)} timing paths")
            logger.info(f"Timing paths visualization opened: {len(paths)} paths")

        except Exception as e:
            self.status_label.setText(f"Error showing paths: {str(e)}")
            logger.error(f"Failed to show timing paths: {e}", exc_info=True)

    def show_clock_waveforms(self):
        """Show clock waveforms."""
        if not hasattr(self, 'clock_constraints') or not self.clock_constraints:
            self.status_label.setText("No clock constraints available")
            return

        try:
            # Get selected clock
            clock_name = self.clock_combo.currentText()

            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                temp_file = f.name

            if clock_name == "All Clocks":
                # Plot all clocks
                clocks = self.clock_constraints.get_all_clocks()
                self.clock_plotter.plot_all_clocks(clocks, temp_file)
            else:
                # Plot single clock
                clock = self.clock_constraints.get_clock_by_name(clock_name)
                if clock:
                    self.clock_plotter.plot_clock_waveform(clock, temp_file)

            # Load and display image
            pixmap = QPixmap(temp_file)
            scaled_pixmap = pixmap.scaled(
                self.plot_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.plot_label.setPixmap(scaled_pixmap)

            self.status_label.setText(f"Showing clock waveforms")

        except Exception as e:
            self.status_label.setText(f"Error showing waveforms: {str(e)}")
            logger.error(f"Failed to show clock waveforms: {e}", exc_info=True)

    def export_graph(self):
        """Export timing graph to file."""
        if not self.graph_builder:
            self.status_label.setText("No timing graph available")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Graph",
            "timing_graph",
            "Graph Files (*.graphml *.gml *.dot);;All Files (*)"
        )

        if file_path:
            try:
                G = self.graph_builder.to_networkx()

                if file_path.endswith('.graphml'):
                    import networkx as nx
                    nx.write_graphml(G, file_path)
                elif file_path.endswith('.gml'):
                    import networkx as nx
                    nx.write_gml(G, file_path)
                elif file_path.endswith('.dot'):
                    import networkx as nx
                    nx.drawing.nx_pydot.write_dot(G, file_path)

                self.status_label.setText(f"Graph exported to {file_path}")
                logger.info(f"Timing graph exported to {file_path}")

            except Exception as e:
                self.status_label.setText(f"Error exporting graph: {str(e)}")
                logger.error(f"Failed to export graph: {e}", exc_info=True)

    def resizeEvent(self, event):
        """Handle resize event."""
        super().resizeEvent(event)

        # Rescale image if present
        if self.plot_label.pixmap() and not self.plot_label.pixmap().isNull():
            scaled_pixmap = self.plot_label.pixmap().scaled(
                self.plot_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.plot_label.setPixmap(scaled_pixmap)