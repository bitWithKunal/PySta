# PySTA main entry point 
# !/usr/bin/env python3
"""
PySTA - Python Static Timing Analyzer
Main entry point for the application.
"""

import sys
import os
import traceback
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtCore import Qt, QTimer

from Src.gui.main_window import MainWindow
from Src.utils.logger import get_logger, get_log_file
from Src.utils.config_loader import ConfigLoader

# Initialize logger
logger = get_logger(__name__)


class PySTAApplication:
    """Main application class for PySTA."""

    def __init__(self):
        self.app = None
        self.main_window = None
        self.splash = None

    def initialize(self):
        """Initialize the application."""
        try:
            # Create Qt Application
            self.app = QApplication(sys.argv)
            self.app.setApplicationName("PySTA")
            self.app.setOrganizationName("PySTA")
            self.app.setApplicationVersion("1.0.0")

            # Set application font
            font = QFont("Segoe UI", 9)
            self.app.setFont(font)

            # Show splash screen
            self.show_splash()

            # Process events to show splash
            self.app.processEvents()

            # Load configuration
            self.load_configuration()

            # Initialize main window (delayed to show splash)
            QTimer.singleShot(1500, self.create_main_window)

            return True

        except Exception as e:
            logger.error(f"Failed to initialize application: {e}", exc_info=True)
            self.show_error_dialog("Initialization Error", str(e))
            return False

    def show_splash(self):
        """Show splash screen."""
        try:
            # Create splash pixmap
            splash_path = Path(__file__).parent / "Resources" / "splash.png"
            if splash_path.exists():
                pixmap = QPixmap(str(splash_path))
            else:
                # Create a simple text splash if image doesn't exist
                pixmap = QPixmap(600, 300)
                pixmap.fill(Qt.GlobalColor.darkBlue)

            self.splash = QSplashScreen(pixmap)
            self.splash.show()

            # Show messages on splash
            self.splash.showMessage(
                "Initializing PySTA...",
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
                Qt.GlobalColor.white
            )

        except Exception as e:
            logger.warning(f"Could not show splash screen: {e}")

    def load_configuration(self):
        """Load application configuration."""
        try:
            if self.splash:
                self.splash.showMessage(
                    "Loading configuration...",
                    Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
                    Qt.GlobalColor.white
                )
                self.app.processEvents()

            config = ConfigLoader.load_config()
            logger.info(f"Configuration loaded: {config}")

        except Exception as e:
            logger.warning(f"Could not load configuration: {e}")

    def create_main_window(self):
        """Create and show main window."""
        try:
            if self.splash:
                self.splash.showMessage(
                    "Creating main window...",
                    Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
                    Qt.GlobalColor.white
                )
                self.app.processEvents()

            # Create main window
            self.main_window = MainWindow()

            # Close splash and show main window
            if self.splash:
                self.splash.finish(self.main_window)

            self.main_window.show()

            logger.info("Main window created and displayed")

        except Exception as e:
            logger.error(f"Failed to create main window: {e}", exc_info=True)
            if self.splash:
                self.splash.close()
            self.show_error_dialog("Window Creation Error", str(e))

    def show_error_dialog(self, title: str, message: str):
        """Show error dialog."""
        error_dialog = QMessageBox()
        error_dialog.setIcon(QMessageBox.Icon.Critical)
        error_dialog.setWindowTitle(title)
        error_dialog.setText(message)
        error_dialog.setDetailedText(traceback.format_exc())
        error_dialog.exec()

    def run(self):
        """Run the application."""
        try:
            logger.info("=" * 60)
            logger.info("PySTA Starting")
            logger.info("=" * 60)
            logger.info(f"Python version: {sys.version}")
            logger.info(f"Log file: {get_log_file()}")

            # Initialize and run
            if self.initialize():
                logger.info("Application initialized successfully")

                # Run the application
                exit_code = self.app.exec()

                logger.info(f"Application exiting with code {exit_code}")
                return exit_code
            else:
                return 1

        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            self.show_error_dialog("Fatal Error", str(e))
            return 1

        finally:
            logger.info("PySTA shutdown complete")

    def cleanup(self):
        """Cleanup resources before exit."""
        try:
            if self.main_window:
                self.main_window.close()

            logger.info("Cleanup completed")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def check_dependencies():
    """Check if all required dependencies are installed."""
    required_packages = [
        'PyQt6',
        'networkx',
        'numpy',
        'pandas',
        'openpyxl',
        'matplotlib',
        'scipy'
    ]

    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    if missing:
        print("Missing required packages:")
        for package in missing:
            print(f"  - {package}")
        print("\nInstall them using:")
        print(f"pip install {' '.join(missing)}")
        return False

    return True


def setup_environment():
    """Setup environment variables and paths."""
    # Create necessary directories
    directories = [
        "Logs",
        "Reports",
        "Config",
        "Resources"
    ]

    for directory in directories:
        Path(directory).mkdir(exist_ok=True)

    # Set environment variables
    os.environ['PYSTA_ROOT'] = str(Path(__file__).parent)


def main():
    """Main entry point."""
    try:
        # Setup environment
        setup_environment()

        # Check dependencies
        if not check_dependencies():
            input("Press Enter to exit...")
            return 1

        # Create and run application
        app = PySTAApplication()
        exit_code = app.run()

        # Cleanup
        app.cleanup()

        return exit_code

    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        return 130

    except Exception as e:
        print(f"Unexpected error: {e}")
        traceback.print_exc()
        input("Press Enter to exit...")
        return 1


if __name__ == "__main__":
    sys.exit(main())