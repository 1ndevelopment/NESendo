"""Qt GUI wrapper for NESendo NES emulator."""
import sys
import os
import threading
import time
import pickle
import json
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QFileDialog, QMessageBox, QFrame, QGridLayout,
    QGroupBox, QSlider, QSpinBox, QCheckBox, QComboBox, QTextEdit,
    QSplitter, QSizePolicy, QProgressBar, QStatusBar, QMenuBar, QMenu,
    QAction, QToolBar, QTabWidget, QScrollArea, QButtonGroup, QDialog,
    QDesktopWidget
)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt, QSize, QPropertyAnimation, QEasingCurve, QSettings, QIODevice
from PyQt5.QtGui import QPixmap, QImage, QFont, QKeySequence, QPalette, QColor, QIcon, QPainter, QLinearGradient
from PyQt5.QtMultimedia import QAudioOutput, QAudioFormat, QAudioDeviceInfo

from ..nes_env import NESEnv


class EmulationThread(QThread):
    """Thread for running the NES emulation."""
    
    frame_ready = pyqtSignal(object)  # Emits the screen frame
    audio_ready = pyqtSignal(object)  # Emits audio data
    emulation_error = pyqtSignal(str)  # Emits error messages
    fps_updated = pyqtSignal(float)  # Emits current FPS
    
    def __init__(self, rom_path: str):
        super().__init__()
        self.rom_path = rom_path
        self.env: Optional[NESEnv] = None
        self.running = False
        self.paused = False
        self.fastforward = False
        self.fastforward_speed = 2.0  # Default 2x speed
        self.current_action = 0
        self.target_fps = 60
        self.frame_duration = 1.0 / self.target_fps
        
        # FPS calculation variables
        self.frame_count = 0
        self.fps_start_time = time.time()
        self.current_fps = 0.0
        
    def run(self):
        """Main emulation loop."""
        try:
            # Initialize the NES environment
            self.env = NESEnv(self.rom_path)
            self.env.reset()
            self.running = True
            self.paused = False
            self.fastforward = False
            
            last_frame_time = time.time()
            
            while self.running:
                current_time = time.time()
                
                # Skip emulation step if paused
                if self.paused:
                    time.sleep(0.001)
                    continue
                
                # Calculate frame duration based on fastforward state
                current_frame_duration = self.frame_duration
                if self.fastforward:
                    current_frame_duration = self.frame_duration / self.fastforward_speed
                
                # Frame rate limiting
                if current_time - last_frame_time >= current_frame_duration:
                    if self.env and not self.env.done:
                        # Step the emulation
                        _, _, terminated, truncated, _ = self.env.step(self.current_action)
                        
                        if terminated or truncated:
                            self.env.reset()
                        
                        # Emit the current frame
                        self.frame_ready.emit(self.env.screen)
                        
                        # Get and emit audio data (this clears the buffer to prevent overflow)
                        audio_data = self.env.get_and_clear_audio_buffer()
                        if audio_data is not None and len(audio_data) > 0:
                            # Convert to numpy array for consistency
                            audio_data = np.array(audio_data, dtype=np.float32)
                            self.audio_ready.emit(audio_data)
                        
                        # Calculate and emit FPS
                        self.frame_count += 1
                        if self.frame_count % 30 == 0:  # Update FPS every 30 frames
                            elapsed_time = current_time - self.fps_start_time
                            if elapsed_time > 0:
                                self.current_fps = self.frame_count / elapsed_time
                                self.fps_updated.emit(self.current_fps)
                        
                        last_frame_time = current_time
                    else:
                        time.sleep(0.001)  # Small sleep to prevent busy waiting
                else:
                    time.sleep(0.001)
                    
        except Exception as e:
            self.emulation_error.emit(str(e))
        finally:
            if self.env:
                self.env.close()
                self.env = None
    
    def set_action(self, action: int):
        """Set the current controller action."""
        self.current_action = action
    
    def set_fps(self, fps: int):
        """Set the target FPS."""
        self.target_fps = fps
        self.frame_duration = 1.0 / fps
    
    def reset_fps_calculation(self):
        """Reset FPS calculation variables."""
        self.frame_count = 0
        self.fps_start_time = time.time()
        self.current_fps = 0.0
    
    def pause(self):
        """Pause the emulation."""
        self.paused = True
    
    def resume(self):
        """Resume the emulation."""
        self.paused = False
    
    def is_paused(self):
        """Check if emulation is paused."""
        return self.paused
    
    def toggle_fastforward(self):
        """Toggle fastforward mode."""
        self.fastforward = not self.fastforward
    
    def set_fastforward_speed(self, speed: float):
        """Set the fastforward speed multiplier."""
        self.fastforward_speed = max(1.0, speed)  # Ensure minimum 1x speed
    
    def is_fastforward(self):
        """Check if emulation is in fastforward mode."""
        return self.fastforward
    
    def stop(self):
        """Stop the emulation thread."""
        self.running = False
        self.wait()


class GameDisplayWidget(QLabel):
    """Widget for displaying the NES game screen."""
    
    def __init__(self):
        super().__init__()
        # Set initial size to 2x scale
        self.setMinimumSize(256, 240)  # Minimum NES resolution
        self.setScaledContents(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("""
            QLabel {
                border: none;
                background-color: #0f1419;
                color: #cbd5e0;
                font-size: 14px;
                font-weight: 500;
            }
        """)
        self.setAlignment(Qt.AlignCenter)
        
        # Track if we're showing the logo (vs game content)
        self.showing_logo = True
        
        # Load and display the logo image instead of text
        self.load_logo()
        
        # Enable focus to capture keyboard input
        self.setFocusPolicy(Qt.StrongFocus)
    
    def load_logo(self):
        """Load and display the NESendo logo image."""
        try:
            # Get the path to the logo image
            logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'nesendo-snakes-logo.png')
            
            # Load the image
            pixmap = QPixmap(logo_path)
            
            if not pixmap.isNull():
                # Get the widget size
                widget_size = self.size()
                widget_width = widget_size.width()
                widget_height = widget_size.height()
                
                # Calculate the maximum size that fits within the widget while maintaining aspect ratio
                # Leave some padding (10% on each side)
                max_width = int(widget_width * 0.8)
                max_height = int(widget_height * 0.8)
                
                # Scale the pixmap to fit within the maximum size while maintaining aspect ratio
                scaled_pixmap = pixmap.scaled(
                    max_width, max_height,
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                
                # Create a new pixmap with the widget size and transparent background
                final_pixmap = QPixmap(widget_size)
                final_pixmap.fill(Qt.transparent)
                
                # Create a painter to center the scaled logo
                painter = QPainter(final_pixmap)
                painter.setRenderHint(QPainter.Antialiasing)
                
                # Calculate the position to center the logo
                x = (widget_width - scaled_pixmap.width()) // 2
                y = (widget_height - scaled_pixmap.height()) // 2
                
                # Draw the scaled logo at the center
                painter.drawPixmap(x, y, scaled_pixmap)
                painter.end()
                
                self.setPixmap(final_pixmap)
            else:
                # Fallback to text if image loading fails
                self.setText("No ROM loaded")
        except Exception as e:
            # Fallback to text if there's any error loading the image
            self.setText("No ROM loaded")
    
    def resizeEvent(self, event):
        """Handle widget resize events to update logo scaling."""
        super().resizeEvent(event)
        # Reload logo with new size if we're currently showing the logo
        if self.showing_logo:
            self.load_logo()
        
    def update_frame(self, screen_data):
        """Update the display with new frame data."""
        if screen_data is not None:
            # Mark that we're no longer showing the logo
            self.showing_logo = False
            
            # Convert numpy array to QImage
            height, width, channels = screen_data.shape
            bytes_per_line = channels * width
            
            # Ensure the data is in the right format (RGB)
            if channels == 3:
                # Convert to bytes and ensure contiguous array
                data = screen_data.astype('uint8').tobytes()
                qimage = QImage(data, width, height, bytes_per_line, QImage.Format_RGB888)
            else:
                # Convert to RGB if needed
                rgb_data = screen_data[:, :, :3] if channels >= 3 else screen_data
                data = rgb_data.astype('uint8').tobytes()
                qimage = QImage(data, width, height, bytes_per_line, QImage.Format_RGB888)
            
            # Convert to pixmap and display
            pixmap = QPixmap.fromImage(qimage)
            self.setPixmap(pixmap)
    
    def show_logo(self):
        """Show the logo image (used when no ROM is loaded)."""
        self.showing_logo = True
        self.load_logo()
    
    def keyPressEvent(self, event):
        """Forward key press events to parent window."""
        # Forward to parent window for processing
        if self.parent():
            self.parent().keyPressEvent(event)
        else:
            super().keyPressEvent(event)
    
    def keyReleaseEvent(self, event):
        """Forward key release events to parent window."""
        # Forward to parent window for processing
        if self.parent():
            self.parent().keyReleaseEvent(event)
        else:
            super().keyReleaseEvent(event)
    
    def focusInEvent(self, event):
        """Handle focus in events."""
        super().focusInEvent(event)
        # Update input status when game display gains focus
        if hasattr(self.parent(), 'input_status_label'):
            self.parent().input_status_label.setText("Input: Capturing")
    
    def focusOutEvent(self, event):
        """Handle focus out events."""
        super().focusOutEvent(event)
        # Update input status when game display loses focus
        if hasattr(self.parent(), 'input_status_label'):
            self.parent().input_status_label.setText("Input: Not Focused")


class ControlPanel(QWidget):
    """Panel containing emulation controls."""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.apply_dark_theme()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        
        # Controls info
        controls_group = QGroupBox("🎯 Controls")
        controls_layout = QVBoxLayout()
        
        controls_text = QTextEdit()
        controls_text.setMaximumHeight(150)
        controls_text.setPlainText(
            "🎮 Keyboard Controls:\n"
            "W - Up\n"
            "A - Left\n"
            "S - Down\n"
            "D - Right\n"
            "O - A Button\n"
            "P - B Button\n"
            "Enter - Start\n"
            "Space - Select\n"
            "Escape - Exit"
        )
        controls_text.setReadOnly(True)
        controls_layout.addWidget(controls_text)
        controls_group.setLayout(controls_layout)
        
        layout.addWidget(controls_group)
        
        self.setLayout(layout)
    
    def apply_dark_theme(self):
        """Apply dark theme styling to all widgets."""
        # Group box styling
        group_style = """
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                color: #cbd5e0;
                border: 2px solid #2d3748;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """
        
        # Button styling
        button_style = """
            QPushButton {
                background-color: #2d3748;
                border: 2px solid #2d3748;
                border-radius: 6px;
                color: #cbd5e0;
                font-weight: 500;
                font-size: 12px;
                padding: 8px 16px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #2d5a27;
                border-color: #2d5a27;
            }
            QPushButton:pressed {
                background-color: #1a3d1a;
                border-color: #1a3d1a;
            }
            QPushButton:disabled {
                background-color: #1a202c;
                border-color: #2d3748;
                color: #718096;
            }
        """
        
        # Spin box styling
        spinbox_style = """
            QSpinBox {
                background-color: #1a202c;
                border: 1px solid #2d3748;
                border-radius: 4px;
                color: #cbd5e0;
                padding: 4px;
                font-size: 12px;
            }
            QSpinBox:hover {
                border-color: #2d5a27;
            }
            QSpinBox:focus {
                border-color: #2d5a27;
            }
        """
        
        # Combo box styling
        combobox_style = """
            QComboBox {
                background-color: #1a202c;
                border: 1px solid #2d3748;
                border-radius: 4px;
                color: #cbd5e0;
                padding: 4px;
                font-size: 12px;
            }
            QComboBox:hover {
                border-color: #2d5a27;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #cbd5e0;
                margin-right: 5px;
            }
        """
        
        # Text edit styling
        textedit_style = """
            QTextEdit {
                background-color: #1a202c;
                border: 1px solid #2d3748;
                border-radius: 4px;
                color: #cbd5e0;
                font-size: 11px;
                padding: 8px;
            }
            QTextEdit:focus {
                border-color: #2d5a27;
            }
        """
        
        # Apply styles
        self.setStyleSheet(group_style + button_style + spinbox_style + combobox_style + textedit_style)
    


class NESendoGUI(QMainWindow):
    """Main GUI window for NESendo."""
    
    def load_recent_files(self):
        """Load recent files from settings."""
        recent_files = self.settings.value('recent_files', [])
        if isinstance(recent_files, str):
            recent_files = [recent_files]
        # Filter out files that no longer exist
        return [f for f in recent_files if os.path.exists(f)]
    
    def save_recent_files(self):
        """Save recent files to settings."""
        self.settings.setValue('recent_files', self.recent_files)
    
    def add_to_recent_files(self, file_path):
        """Add a file to the recent files list."""
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        self.recent_files.insert(0, file_path)
        # Keep only the last 10 files
        self.recent_files = self.recent_files[:10]
        self.save_recent_files()
        self.update_recent_menu()
    
    def update_recent_menu(self):
        """Update the recent files menu."""
        self.recent_menu.clear()
        if not self.recent_files:
            no_recent_action = QAction('No recent files', self)
            no_recent_action.setEnabled(False)
            self.recent_menu.addAction(no_recent_action)
        else:
            for i, file_path in enumerate(self.recent_files):
                file_name = os.path.basename(file_path)
                action = QAction(f'&{i+1} {file_name}', self)
                action.triggered.connect(lambda checked, path=file_path: self.load_recent_rom(path))
                self.recent_menu.addAction(action)
    
    def load_recent_rom(self, file_path):
        """Load a ROM from the recent files list."""
        if os.path.exists(file_path):
            # Stop any existing emulation before loading new ROM
            if self.is_emulation_running():
                self.status_bar.showMessage("Stopping current emulation...", 1000)
                self.stop_emulation()
            
            self.rom_path = file_path
            self.rom_status_label.setText(f"ROM: {os.path.basename(file_path)}")
            self.status_bar.showMessage(f"Loaded ROM: {os.path.basename(file_path)}", 3000)
            
            # Clear existing states for the new ROM
            self.clear_states()
            
            # Automatically start emulation after loading the ROM
            try:
                self.start_emulation()
            except Exception as e:
                # If automatic start fails, show the logo and display error
                self.game_display.show_logo()
                QMessageBox.critical(self, "Start Error", f"Failed to start emulation: {str(e)}")
        else:
            # Remove non-existent file from recent list
            if file_path in self.recent_files:
                self.recent_files.remove(file_path)
                self.save_recent_files()
                self.update_recent_menu()
            QMessageBox.warning(self, "File Not Found", f"The file {file_path} no longer exists.")
    
    def __init__(self):
        super().__init__()
        self.rom_path = None
        self.emulation_thread = None
        self.current_action = 0
        self.settings = QSettings('NESendo', 'NESendo')
        self.recent_files = self.load_recent_files()
        
        # Audio settings
        self.audio_enabled = True
        self.master_volume = 0.75
        self.audio_output = None
        self.audio_format = None
        
        # State management
        self.state_slots = {}  # Dictionary to store state data for slots 1-4
        self.state_directory = os.path.join(os.path.expanduser("~"), ".nesendo", "states")
        self.ensure_state_directory()
        
        self.init_keymapping()
        self.init_ui()
        self.setup_shortcuts()
        self.apply_dark_theme()
        self.init_audio()
        
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("NESendo")
        # Start with a reasonable window size
        self.setGeometry(100, 100, 600, 500)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create game display widget that fills the entire window
        self.game_display = GameDisplayWidget()
        self.setCentralWidget(self.game_display)
        
        # Remove any margins or spacing
        self.centralWidget().setContentsMargins(0, 0, 0, 0)
        
        # Create status bar
        self.create_status_bar()
        
        # Resize window to fit game display
        self.resize_to_fit_game()
    
    def create_menu_bar(self):
        """Create the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('&File')
        
        load_action = QAction('&Load ROM...', self)
        load_action.setShortcut('Ctrl+O')
        load_action.triggered.connect(self.load_rom)
        file_menu.addAction(load_action)
        
        # Load recent submenu
        self.recent_menu = file_menu.addMenu('Load &Recent')
        self.update_recent_menu()
        
        file_menu.addSeparator()
        
        exit_action = QAction('E&xit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Emulation menu
        emu_menu = menubar.addMenu('&Emulation')
        
        start_action = QAction('&Start', self)
        start_action.setShortcut('F5')
        start_action.triggered.connect(self.start_emulation)
        emu_menu.addAction(start_action)
        
        stop_action = QAction('S&top', self)
        stop_action.setShortcut('F6')
        stop_action.triggered.connect(self.stop_emulation)
        emu_menu.addAction(stop_action)
        
        reset_action = QAction('&Reset', self)
        reset_action.setShortcut('F7')
        reset_action.triggered.connect(self.reset_emulation)
        emu_menu.addAction(reset_action)
        
        emu_menu.addSeparator()
        
        # Pause/Resume actions
        self.pause_action = QAction('&Pause', self)
        self.pause_action.setShortcut('F8')
        self.pause_action.triggered.connect(self.pause_emulation)
        self.pause_action.setEnabled(False)  # Initially disabled
        emu_menu.addAction(self.pause_action)
        
        self.resume_action = QAction('&Resume', self)
        self.resume_action.setShortcut('F9')
        self.resume_action.triggered.connect(self.resume_emulation)
        self.resume_action.setEnabled(False)  # Initially disabled
        emu_menu.addAction(self.resume_action)
        
        emu_menu.addSeparator()
        
        # Fastforward action
        self.fastforward_action = QAction('&Fast Forward', self)
        self.fastforward_action.setShortcut('F10')
        self.fastforward_action.setCheckable(True)  # Make it a toggle action
        self.fastforward_action.triggered.connect(self.toggle_fastforward)
        self.fastforward_action.setEnabled(False)  # Initially disabled
        emu_menu.addAction(self.fastforward_action)
        
        # Fastforward speed submenu
        fastforward_menu = emu_menu.addMenu('Fast Forward &Speed')
        
        self.speed_2x_action = QAction('&2x Speed', self)
        self.speed_2x_action.setCheckable(True)
        self.speed_2x_action.setChecked(True)  # Default speed
        self.speed_2x_action.triggered.connect(lambda: self.set_fastforward_speed(2.0))
        fastforward_menu.addAction(self.speed_2x_action)
        
        self.speed_4x_action = QAction('&4x Speed', self)
        self.speed_4x_action.setCheckable(True)
        self.speed_4x_action.triggered.connect(lambda: self.set_fastforward_speed(4.0))
        fastforward_menu.addAction(self.speed_4x_action)
        
        self.speed_8x_action = QAction('&8x Speed', self)
        self.speed_8x_action.setCheckable(True)
        self.speed_8x_action.triggered.connect(lambda: self.set_fastforward_speed(8.0))
        fastforward_menu.addAction(self.speed_8x_action)
        
        emu_menu.addSeparator()
        
        # Save State submenu
        save_state_menu = emu_menu.addMenu('&Save State')
        
        save_state_1_action = QAction('Save State &1', self)
        save_state_1_action.setShortcut('F1')
        save_state_1_action.triggered.connect(lambda: self.save_state(1))
        save_state_menu.addAction(save_state_1_action)
        
        save_state_2_action = QAction('Save State &2', self)
        save_state_2_action.setShortcut('F2')
        save_state_2_action.triggered.connect(lambda: self.save_state(2))
        save_state_menu.addAction(save_state_2_action)
        
        save_state_3_action = QAction('Save State &3', self)
        save_state_3_action.setShortcut('F3')
        save_state_3_action.triggered.connect(lambda: self.save_state(3))
        save_state_menu.addAction(save_state_3_action)
        
        save_state_4_action = QAction('Save State &4', self)
        save_state_4_action.setShortcut('F4')
        save_state_4_action.triggered.connect(lambda: self.save_state(4))
        save_state_menu.addAction(save_state_4_action)
        
        save_state_menu.addSeparator()
        
        # Add file-based save option to Save State submenu
        save_state_file_action = QAction('Save State to &File...', self)
        save_state_file_action.setShortcut('Ctrl+Shift+S')
        save_state_file_action.triggered.connect(self.save_state_to_file_dialog)
        save_state_menu.addAction(save_state_file_action)
        
        
        # Load State submenu
        load_state_menu = emu_menu.addMenu('&Load State')
        
        load_state_1_action = QAction('Load State &1', self)
        load_state_1_action.setShortcut('Shift+F1')
        load_state_1_action.triggered.connect(lambda: self.load_state(1))
        load_state_menu.addAction(load_state_1_action)
        
        load_state_2_action = QAction('Load State &2', self)
        load_state_2_action.setShortcut('Shift+F2')
        load_state_2_action.triggered.connect(lambda: self.load_state(2))
        load_state_menu.addAction(load_state_2_action)
        
        load_state_3_action = QAction('Load State &3', self)
        load_state_3_action.setShortcut('Shift+F3')
        load_state_3_action.triggered.connect(lambda: self.load_state(3))
        load_state_menu.addAction(load_state_3_action)
        
        load_state_4_action = QAction('Load State &4', self)
        load_state_4_action.setShortcut('Shift+F4')
        load_state_4_action.triggered.connect(lambda: self.load_state(4))
        load_state_menu.addAction(load_state_4_action)
        
        # Add file-based save/load options
        load_state_menu.addSeparator()
        
        load_state_file_action = QAction('Load State from &File...', self)
        load_state_file_action.setShortcut('Ctrl+Shift+L')
        load_state_file_action.triggered.connect(self.load_state_from_file_dialog)
        load_state_menu.addAction(load_state_file_action)
        
        emu_menu.addSeparator()
        
        state_manager_action = QAction('State &Manager...', self)
        state_manager_action.setShortcut('F8')
        state_manager_action.triggered.connect(self.show_state_manager)
        emu_menu.addAction(state_manager_action)
        
        # Settings menu
        settings_menu = menubar.addMenu('&Settings')
        
        # Audio settings
        audio_menu = settings_menu.addMenu('&Audio')
        
        self.audio_enable_action = QAction('&Enable Audio', self, checkable=True)
        self.audio_enable_action.setChecked(self.audio_enabled)
        self.audio_enable_action.triggered.connect(self.toggle_audio_enabled)
        audio_menu.addAction(self.audio_enable_action)
        
        audio_menu.addSeparator()
        
        # Volume controls
        self.volume_mute_action = QAction('&Mute', self)
        self.volume_mute_action.triggered.connect(self.mute_audio)
        audio_menu.addAction(self.volume_mute_action)
        
        self.volume_50_action = QAction('Volume &50%', self)
        self.volume_50_action.triggered.connect(lambda: self.set_audio_volume(0.5))
        audio_menu.addAction(self.volume_50_action)
        
        self.volume_75_action = QAction('Volume &75%', self)
        self.volume_75_action.triggered.connect(lambda: self.set_audio_volume(0.75))
        audio_menu.addAction(self.volume_75_action)
        
        self.volume_100_action = QAction('Volume &100%', self)
        self.volume_100_action.triggered.connect(lambda: self.set_audio_volume(1.0))
        audio_menu.addAction(self.volume_100_action)
        
        audio_menu.addSeparator()
        
        audio_volume_action = QAction('&Volume Settings...', self)
        audio_volume_action.triggered.connect(self.show_audio_settings)
        audio_menu.addAction(audio_volume_action)
        
        
        
        # View menu
        view_menu = menubar.addMenu('&View')
        
        fullscreen_action = QAction('&Fullscreen', self)
        fullscreen_action.setShortcut('F11')
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)
        
        # Help menu
        help_menu = menubar.addMenu('&Help')
        
        about_action = QAction('&About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    
    def create_status_bar(self):
        """Create the status bar."""
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #1a202c;
                color: #cbd5e0;
                border-top: 1px solid #2d3748;
                font-size: 11px;
            }
        """)
        
        # Add status labels
        self.rom_status_label = QLabel("No ROM loaded")
        self.fps_status_label = QLabel("FPS: --")
        self.scale_status_label = QLabel("Scale: 2x")
        self.input_status_label = QLabel("Input: Ready")
        self.state_status_label = QLabel("States: --")
        
        self.status_bar.addWidget(self.rom_status_label)
        self.status_bar.addPermanentWidget(self.fps_status_label)
        self.status_bar.addPermanentWidget(self.scale_status_label)
        self.status_bar.addPermanentWidget(self.state_status_label)
        self.status_bar.addPermanentWidget(self.input_status_label)
        
        self.setStatusBar(self.status_bar)
    
    def resize_to_fit_game(self):
        """Set initial window size to a reasonable default."""
        # Set a reasonable initial size (2x scale)
        initial_width = 512
        initial_height = 480
        
        # Calculate window decorations height
        menu_height = self.menuBar().height()
        status_height = self.status_bar.height()
        
        # Calculate window size
        window_width = initial_width
        window_height = initial_height + menu_height + status_height
        
        # Set the initial window size
        self.resize(window_width, window_height)
        
        # Center the window on screen
        self.center_window()
    
    def center_window(self):
        """Center the window on the screen."""
        desktop = QDesktopWidget()
        screen = desktop.screenGeometry()
        size = self.geometry()
        self.move(
            (screen.width() - size.width()) // 2,
            (screen.height() - size.height()) // 2
        )
    
    def init_keymapping(self):
        """Initialize the keymapping system."""
        # NES controller mapping matching NESEnv layout
        self.key_mapping = {
            Qt.Key_W: 16,        # Up
            Qt.Key_A: 64,        # Left  
            Qt.Key_S: 32,        # Down
            Qt.Key_D: 128,       # Right
            Qt.Key_O: 2,         # A Button
            Qt.Key_P: 1,         # B Button
            Qt.Key_Return: 8,    # Start
            Qt.Key_Space: 4,     # Select
        }
        
        # Track pressed keys
        self.pressed_keys = set()
        
    
    def apply_dark_theme(self):
        """Apply dark theme to the main window."""
        # Set application-wide dark theme
        app = QApplication.instance()
        app.setStyle('Fusion')
        
        # Create midnight dark palette
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(15, 20, 25))  # #0f1419
        palette.setColor(QPalette.WindowText, QColor(203, 213, 224))  # #cbd5e0
        palette.setColor(QPalette.Base, QColor(26, 32, 44))  # #1a202c
        palette.setColor(QPalette.AlternateBase, QColor(45, 55, 72))  # #2d3748
        palette.setColor(QPalette.ToolTipBase, QColor(15, 20, 25))
        palette.setColor(QPalette.ToolTipText, QColor(203, 213, 224))
        palette.setColor(QPalette.Text, QColor(203, 213, 224))
        palette.setColor(QPalette.Button, QColor(45, 55, 72))
        palette.setColor(QPalette.ButtonText, QColor(203, 213, 224))
        palette.setColor(QPalette.BrightText, QColor(255, 255, 255))
        palette.setColor(QPalette.Link, QColor(45, 90, 39))  # #2d5a27
        palette.setColor(QPalette.Highlight, QColor(45, 90, 39))
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        
        app.setPalette(palette)
        
        # Set window styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0f1419;
                color: #cbd5e0;
            }
            QMenuBar {
                background-color: #1a202c;
                color: #cbd5e0;
                border-bottom: 1px solid #2d3748;
                font-size: 12px;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 4px 8px;
            }
            QMenuBar::item:selected {
                background-color: #2d5a27;
            }
            QMenu {
                background-color: #1a202c;
                color: #cbd5e0;
                border: 1px solid #2d3748;
            }
            QMenu::item:selected {
                background-color: #2d5a27;
            }
        """)
        
    def setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Key mapping is now handled in init_keymapping()
        pass
    
    def init_audio(self):
        """Initialize audio output."""
        try:
            # Create audio format with better settings
            self.audio_format = QAudioFormat()
            self.audio_format.setSampleRate(44100)
            self.audio_format.setChannelCount(1)  # Mono
            self.audio_format.setSampleSize(16)   # 16-bit
            self.audio_format.setCodec("audio/pcm")
            self.audio_format.setByteOrder(QAudioFormat.LittleEndian)
            self.audio_format.setSampleType(QAudioFormat.SignedInt)
            
            # Check if the format is supported
            if not QAudioDeviceInfo.defaultOutputDevice().isFormatSupported(self.audio_format):
                # Try a more compatible format
                self.audio_format.setSampleRate(22050)
                if not QAudioDeviceInfo.defaultOutputDevice().isFormatSupported(self.audio_format):
                    self.audio_format.setSampleRate(44100)
                    self.audio_format.setSampleSize(8)  # Fallback to 8-bit
            
            # Create audio output with buffer size settings
            self.audio_output = QAudioOutput(self.audio_format)
            self.audio_output.setVolume(self.master_volume)
            self.audio_output.setBufferSize(4096)  # Set buffer size for smoother playback
            
            # Initialize audio device
            self.audio_device = None
            
        except Exception as e:
            print(f"Failed to initialize audio: {e}")
            self.audio_output = None
    
    def play_audio(self, audio_data):
        """Play audio data."""
        if not self.audio_enabled or not self.audio_output:
            return
        
        try:
            # Convert numpy array to bytes
            if audio_data.dtype != np.int16:
                # Apply aggressive smoothing filter to reduce static and artifacts
                audio_data = np.clip(audio_data, -1.0, 1.0)
                
                # Apply multi-stage smoothing to reduce high-frequency noise
                if len(audio_data) > 2:
                    # First pass: basic smoothing
                    for i in range(1, len(audio_data)):
                        audio_data[i] = 0.6 * audio_data[i] + 0.4 * audio_data[i-1]
                    
                    # Second pass: additional smoothing
                    for i in range(2, len(audio_data)):
                        audio_data[i] = 0.7 * audio_data[i] + 0.3 * audio_data[i-2]
                
                # Convert to int16 with proper scaling
                audio_data = (audio_data * 24576).astype(np.int16)  # Restore some amplitude
            
            # Initialize audio device if not already done
            if self.audio_device is None:
                self.audio_device = self.audio_output.start()
            
            # Write audio data directly without buffering to prevent overflow
            if self.audio_device and self.audio_device.isOpen():
                # Convert to bytes
                audio_bytes = audio_data.tobytes()
                
                # Write in smaller chunks to prevent audio dropouts
                chunk_size = 512  # Even smaller chunks for smoother playback
                for i in range(0, len(audio_bytes), chunk_size):
                    chunk = audio_bytes[i:i + chunk_size]
                    if chunk:
                        self.audio_device.write(chunk)
                
        except Exception as e:
            print(f"Failed to play audio: {e}")
    
    def set_audio_volume(self, volume):
        """Set the audio volume."""
        self.master_volume = max(0.0, min(1.0, volume))
        if self.audio_output:
            self.audio_output.setVolume(self.master_volume)
        
        # Update emulator volume if running
        if self.emulation_thread and self.emulation_thread.env:
            self.emulation_thread.env.set_master_volume(self.master_volume)
    
    def set_audio_enabled(self, enabled):
        """Enable or disable audio."""
        self.audio_enabled = enabled
        
        # Update menu state
        self.audio_enable_action.setChecked(enabled)
        
        # Update emulator audio setting if running
        if self.emulation_thread and self.emulation_thread.env:
            self.emulation_thread.env.set_audio_enabled(enabled)
    
    def toggle_audio_enabled(self):
        """Toggle audio enabled state."""
        self.set_audio_enabled(not self.audio_enabled)
        status = "enabled" if self.audio_enabled else "disabled"
        self.status_bar.showMessage(f"Audio {status}", 2000)
    
    def mute_audio(self):
        """Mute audio by setting volume to 0."""
        self.set_audio_volume(0.0)
        self.status_bar.showMessage("Audio muted", 2000)
        
    def keyPressEvent(self, event):
        """Handle key press events."""
        # Only process game controls if emulation is running
        if self.emulation_thread and self.emulation_thread.isRunning():
            key = event.key()
            if key in self.key_mapping:
                self.pressed_keys.add(key)
                self.update_action()
                event.accept()  # Consume the event to prevent menu shortcuts
                return
        
        # Allow certain keys to pass through for UI navigation
        if event.key() in [Qt.Key_Escape, Qt.Key_F11, Qt.Key_Alt, Qt.Key_Control, Qt.Key_Shift]:
            super().keyPressEvent(event)
        else:
            # Consume all other keys during emulation
            if self.emulation_thread and self.emulation_thread.isRunning():
                event.accept()
            else:
                super().keyPressEvent(event)
    
    def keyReleaseEvent(self, event):
        """Handle key release events."""
        # Only process game controls if emulation is running
        if self.emulation_thread and self.emulation_thread.isRunning():
            key = event.key()
            if key in self.key_mapping:
                self.pressed_keys.discard(key)
                self.update_action()
                event.accept()  # Consume the event to prevent menu shortcuts
                return
        
        # Allow certain keys to pass through for UI navigation
        if event.key() in [Qt.Key_Escape, Qt.Key_F11, Qt.Key_Alt, Qt.Key_Control, Qt.Key_Shift]:
            super().keyReleaseEvent(event)
        else:
            # Consume all other keys during emulation
            if self.emulation_thread and self.emulation_thread.isRunning():
                event.accept()
            else:
                super().keyReleaseEvent(event)
    
    def update_action(self):
        """Update the current controller action based on pressed keys."""
        action = 0
        for key in self.pressed_keys:
            if key in self.key_mapping:
                action |= self.key_mapping[key]
        
        self.current_action = action
        if self.emulation_thread:
            self.emulation_thread.set_action(action)
    
    def focusInEvent(self, event):
        """Handle focus in events."""
        super().focusInEvent(event)
        # If emulation is running, ensure game display has focus
        if self.emulation_thread and self.emulation_thread.isRunning():
            self.game_display.setFocus()
    
    def mousePressEvent(self, event):
        """Handle mouse press events."""
        super().mousePressEvent(event)
        # If emulation is running, set focus to game display when clicked
        if self.emulation_thread and self.emulation_thread.isRunning():
            self.game_display.setFocus()
    
    def load_rom(self):
        """Load a ROM file and automatically start emulation."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select NES ROM", "", "NES ROMs (*.nes);;All Files (*)"
        )
        if file_path:
            # Stop any existing emulation before loading new ROM
            if self.is_emulation_running():
                self.status_bar.showMessage("Stopping current emulation...", 1000)
                self.stop_emulation()
            
            self.rom_path = file_path
            self.rom_status_label.setText(f"ROM: {os.path.basename(file_path)}")
            self.status_bar.showMessage(f"Loaded ROM: {os.path.basename(file_path)}", 3000)
            
            # Add to recent files
            self.add_to_recent_files(file_path)
            
            # Clear existing states for the new ROM
            self.clear_states()
            
            # Automatically start emulation after loading the ROM
            try:
                self.start_emulation()
            except Exception as e:
                # If automatic start fails, show the logo and display error
                self.game_display.show_logo()
                QMessageBox.critical(self, "Start Error", f"Failed to start emulation: {str(e)}")
    
    def is_emulation_running(self):
        """Check if emulation is currently running."""
        return self.emulation_thread is not None and self.emulation_thread.isRunning()
    
    def start_emulation(self):
        """Start the NES emulation."""
        if not self.rom_path:
            QMessageBox.warning(self, "No ROM", "Please load a ROM file first.")
            return
        
        # Stop any existing emulation first
        if self.is_emulation_running():
            self.status_bar.showMessage("Stopping current emulation...", 1000)
            self.stop_emulation()
            # Give a moment for the thread to stop
            if self.emulation_thread:
                self.emulation_thread.wait(1000)  # Wait up to 1 second
        
        try:
            # Create and start emulation thread
            self.emulation_thread = EmulationThread(self.rom_path)
            self.emulation_thread.frame_ready.connect(self.game_display.update_frame)
            self.emulation_thread.audio_ready.connect(self.play_audio)
            self.emulation_thread.emulation_error.connect(self.handle_emulation_error)
            self.emulation_thread.fps_updated.connect(self.update_fps_display)
            self.emulation_thread.start()
            
            # Load existing states for this ROM (disabled to prevent segfaults)
            # self.load_existing_states()
            
            # Update status
            self.status_bar.showMessage("Emulation started", 2000)
            self.input_status_label.setText("Input: Capturing")
            
            # Update menu state
            self.pause_action.setEnabled(True)
            self.resume_action.setEnabled(False)
            self.fastforward_action.setEnabled(True)
            self.fastforward_action.setChecked(False)
            # Enable speed menu items
            self.speed_2x_action.setEnabled(True)
            self.speed_4x_action.setEnabled(True)
            self.speed_8x_action.setEnabled(True)
            
            # Set focus to game display to capture keyboard input
            self.game_display.setFocus()
            
            # Reset FPS calculation
            self.emulation_thread.reset_fps_calculation()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start emulation: {str(e)}")
    
    def stop_emulation(self):
        """Stop the NES emulation."""
        if self.emulation_thread:
            self.emulation_thread.stop()
            # Wait for the thread to finish
            if self.emulation_thread.isRunning():
                self.emulation_thread.wait(2000)  # Wait up to 2 seconds
            self.emulation_thread = None
            
            # Clean up audio to stop any playing audio
            if self.audio_output:
                self.audio_output.stop()
            if self.audio_device:
                self.audio_device = None
            
            # Show logo instead of text
            self.game_display.show_logo()
            
            # Update status
            self.status_bar.showMessage("Emulation stopped", 2000)
            self.input_status_label.setText("Input: Ready")
            
            # Update menu state
            self.pause_action.setEnabled(False)
            self.resume_action.setEnabled(False)
            self.fastforward_action.setEnabled(False)
            self.fastforward_action.setChecked(False)
            # Disable speed menu items
            self.speed_2x_action.setEnabled(False)
            self.speed_4x_action.setEnabled(False)
            self.speed_8x_action.setEnabled(False)
    
    def reset_emulation(self):
        """Reset the NES emulation."""
        if self.emulation_thread and self.emulation_thread.env:
            try:
                self.emulation_thread.env.reset()
            except Exception as e:
                QMessageBox.warning(self, "Reset Error", f"Failed to reset emulation: {str(e)}")
    
    def pause_emulation(self):
        """Pause the NES emulation."""
        if self.emulation_thread and self.is_emulation_running():
            self.emulation_thread.pause()
            self.status_bar.showMessage("Emulation paused", 2000)
            self.input_status_label.setText("Input: Paused")
            # Update menu state
            self.pause_action.setEnabled(False)
            self.resume_action.setEnabled(True)
    
    def resume_emulation(self):
        """Resume the NES emulation."""
        if self.emulation_thread and self.is_emulation_running():
            self.emulation_thread.resume()
            self.status_bar.showMessage("Emulation resumed", 2000)
            self.input_status_label.setText("Input: Capturing")
            # Update menu state
            self.pause_action.setEnabled(True)
            self.resume_action.setEnabled(False)
    
    def toggle_fastforward(self):
        """Toggle fastforward mode."""
        if self.emulation_thread and self.is_emulation_running():
            self.emulation_thread.toggle_fastforward()
            is_fastforward = self.emulation_thread.is_fastforward()
            
            if is_fastforward:
                self.status_bar.showMessage(f"Fast forward enabled ({self.emulation_thread.fastforward_speed}x)", 2000)
                self.input_status_label.setText(f"Input: Fast Forward ({self.emulation_thread.fastforward_speed}x)")
            else:
                self.status_bar.showMessage("Fast forward disabled", 2000)
                self.input_status_label.setText("Input: Capturing")
            
            # Update menu state
            self.fastforward_action.setChecked(is_fastforward)
    
    def set_fastforward_speed(self, speed: float):
        """Set the fastforward speed."""
        if self.emulation_thread and self.is_emulation_running():
            self.emulation_thread.set_fastforward_speed(speed)
            
            # Update the checked state of speed menu items (mutual exclusivity)
            self.speed_2x_action.setChecked(speed == 2.0)
            self.speed_4x_action.setChecked(speed == 4.0)
            self.speed_8x_action.setChecked(speed == 8.0)
            
            # Update status if fastforward is currently active
            if self.emulation_thread.is_fastforward():
                self.status_bar.showMessage(f"Fast forward speed set to {speed}x", 2000)
                self.input_status_label.setText(f"Input: Fast Forward ({speed}x)")
    
    def update_fps(self, fps):
        """Update the emulation FPS."""
        if self.emulation_thread:
            self.emulation_thread.set_fps(fps)
        self.fps_status_label.setText(f"FPS: {fps}")
    
    def update_fps_display(self, current_fps):
        """Update the FPS display with current FPS."""
        self.fps_status_label.setText(f"FPS: {current_fps:.1f}")
    
    def update_scale(self, scale_text):
        """Update the display scale."""
        scale = int(scale_text[0])  # Extract number from "2x", "3x", etc.
        # Calculate the new size based on scale
        new_width = 256 * scale
        new_height = 240 * scale
        
        # Resize the window to accommodate the new scale
        menu_height = self.menuBar().height()
        status_height = self.status_bar.height()
        window_width = new_width
        window_height = new_height + menu_height + status_height
        
        self.resize(window_width, window_height)
        self.scale_status_label.setText(f"Scale: {scale_text}")
    
    def update_scale_status(self):
        """Update the scale status based on current display size."""
        if hasattr(self, 'game_display'):
            current_width = self.game_display.width()
            current_height = self.game_display.height()
            
            # Calculate approximate scale based on current size
            # Assuming aspect ratio is maintained
            scale_x = current_width / 256
            scale_y = current_height / 240
            
            # Use the smaller scale to maintain aspect ratio
            scale = min(scale_x, scale_y)
            
            # Round to nearest integer scale
            scale_int = round(scale)
            if scale_int < 1:
                scale_int = 1
            
            self.scale_status_label.setText(f"Scale: ~{scale_int}x")
    
    def resize_game_display_with_aspect_ratio(self, available_width, available_height):
        """Resize the game display while maintaining the NES aspect ratio (4:3)."""
        # NES aspect ratio is 4:3 (256:240)
        nes_aspect_ratio = 256.0 / 240.0
        
        # Calculate the maximum size that fits in available space while maintaining aspect ratio
        if available_width / available_height > nes_aspect_ratio:
            # Available space is wider than NES aspect ratio
            # Height is the limiting factor
            new_height = available_height
            new_width = int(new_height * nes_aspect_ratio)
        else:
            # Available space is taller than NES aspect ratio
            # Width is the limiting factor
            new_width = available_width
            new_height = int(new_width / nes_aspect_ratio)
        
        # Center the game display in the available space
        x_offset = (available_width - new_width) // 2
        y_offset = (available_height - new_height) // 2
        
        # Resize and position the game display
        self.game_display.setGeometry(x_offset, y_offset, new_width, new_height)
    
    def toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
    
    def show_about(self):
        """Show the About dialog."""
        about_text = (
            "NESendo ~\n\n"
            "• A modern NES emulator with a PyQt5 GUI and C++ core\n"
            "• Open-source, educational, and development focused\n\n"
            "© 2025 1ndevelopment - Licensed under MIT License"
        )
        QMessageBox.about(self, "About NESendo GUI", about_text)

    
    def show_settings_dialog(self):
        """Show the main settings dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.setModal(True)
        dialog.resize(500, 400)
        
        layout = QVBoxLayout()
        
        # Create tab widget for different settings categories
        tab_widget = QTabWidget()
        
        # Audio settings tab
        audio_tab = QWidget()
        audio_layout = QVBoxLayout()
        
        audio_enable_checkbox = QCheckBox("Enable Audio")
        audio_enable_checkbox.setChecked(True)
        audio_layout.addWidget(audio_enable_checkbox)
        
        audio_volume_label = QLabel("Volume:")
        audio_layout.addWidget(audio_volume_label)
        audio_volume_slider = QSlider(Qt.Horizontal)
        audio_volume_slider.setRange(0, 100)
        audio_volume_slider.setValue(50)
        audio_layout.addWidget(audio_volume_slider)
        
        audio_tab.setLayout(audio_layout)
        tab_widget.addTab(audio_tab, "Audio")
        
        
        
        layout.addWidget(tab_widget)
        
        # Buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        
        # Apply midnight dark theme to dialog
        dialog.setStyleSheet("""
            QDialog {
                background-color: #0f1419;
                color: #cbd5e0;
            }
            QTabWidget::pane {
                border: 1px solid #2d3748;
                background-color: #1a202c;
            }
            QTabBar::tab {
                background-color: #2d3748;
                color: #cbd5e0;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #2d5a27;
            }
            QCheckBox {
                color: #cbd5e0;
                font-size: 12px;
            }
            QLabel {
                color: #cbd5e0;
                font-size: 12px;
            }
            QSpinBox, QComboBox, QSlider, QTextEdit {
                background-color: #1a202c;
                border: 1px solid #2d3748;
                color: #cbd5e0;
                padding: 4px;
            }
            QPushButton {
                background-color: #2d3748;
                border: 1px solid #2d3748;
                color: #cbd5e0;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2d5a27;
            }
        """)
        
        if dialog.exec_() == QDialog.Accepted:
            # Apply settings
            self.update_fps(fps_spinbox.value())
            self.update_scale(scale_combo.currentText())
    
    def show_audio_settings(self):
        """Show audio settings dialog."""
        dialog = AudioSettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            # Apply audio settings
            self.set_audio_enabled(dialog.enable_audio_checkbox.isChecked())
            self.set_audio_volume(dialog.master_volume_slider.value() / 100.0)
            self.status_bar.showMessage("Audio settings updated", 2000)
    
    
    
    
    def handle_emulation_error(self, error_msg):
        """Handle emulation errors."""
        QMessageBox.critical(self, "Emulation Error", f"Emulation error: {error_msg}")
        self.stop_emulation()
    
    def ensure_state_directory(self):
        """Ensure the state directory exists."""
        os.makedirs(self.state_directory, exist_ok=True)
    
    def get_state_filename(self, slot: int = None, custom_path: str = None) -> str:
        """Get the filename for a state slot or custom path."""
        if custom_path:
            return custom_path
        
        if slot is None:
            return None
            
        rom_name = os.path.splitext(os.path.basename(self.rom_path))[0] if self.rom_path else "unknown"
        return os.path.join(self.state_directory, f"{rom_name}_slot_{slot}.state")
    
    def save_state(self, slot: int):
        """Save the current emulation state to a slot."""
        if not self.is_emulation_running():
            QMessageBox.warning(self, "No Emulation", "No emulation is currently running.")
            return
        
        try:
            # Create a backup of the current state in the C++ emulator
            self.emulation_thread.env._backup()
            
            # Get the state data from the emulator
            state_data = self.capture_emulator_state()
            
            # Save to slot
            self.state_slots[slot] = state_data
            
            # Save to file
            filename = self.get_state_filename(slot)
            self.save_state_to_file(state_data, filename)
            
            # Show success message
            self.status_bar.showMessage(f"State saved to slot {slot}", 2000)
            self.update_state_status()
            
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save state: {str(e)}")
    
    def load_state(self, slot: int):
        """Load a saved state from a slot."""
        if not self.is_emulation_running():
            QMessageBox.warning(self, "No Emulation", "No emulation is currently running.")
            return
        
        try:
            # Check if we have a state in memory for this slot
            if slot in self.state_slots:
                # We have a state in memory, just restore the C++ backup
                if self.emulation_thread and self.emulation_thread.env:
                    self.emulation_thread.env._restore()
            else:
                # For file-based savestates, we can't safely restore the full state
                # because the C++ backup/restore mechanism doesn't work with file data
                QMessageBox.warning(self, "Limited Functionality", 
                    f"File-based savestate loading is limited. For full functionality, "
                    f"save and load states within the same session using slots 1-4.")
                return
            
            # Show success message
            self.status_bar.showMessage(f"State loaded from slot {slot}", 2000)
            
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load state: {str(e)}")
    
    
    def capture_emulator_state(self) -> Dict[str, Any]:
        """Capture the current emulator state."""
        if not self.emulation_thread or not self.emulation_thread.env:
            raise RuntimeError("No emulation running")
        
        env = self.emulation_thread.env
        
        # Capture all the necessary state data
        state_data = {
            'rom_path': self.rom_path,
            'screen': env.screen.copy() if hasattr(env, 'screen') else None,
            'ram': env.ram.copy() if hasattr(env, 'ram') else None,
            'controllers': [env.controllers[0].copy(), env.controllers[1].copy()] if hasattr(env, 'controllers') else None,
            'done': env.done if hasattr(env, 'done') else False,
            'timestamp': time.time()
        }
        
        return state_data
    
    def restore_emulator_state(self, state_data: Dict[str, Any]):
        """Restore the emulator state from captured data."""
        if not self.emulation_thread or not self.emulation_thread.env:
            raise RuntimeError("No emulation running")
        
        env = self.emulation_thread.env
        
        # For now, we'll just update the Python-level state
        # The C++ state restoration is handled separately
        try:
            if state_data.get('done') is not None:
                env.done = state_data['done']
        except Exception as e:
            # If there's an error updating the state, just log it and continue
            print(f"Warning: Could not restore some state data: {e}")
    
    def restore_emulator_state_from_data(self, state_data: Dict[str, Any]):
        """Restore the emulator state from file data."""
        if not self.emulation_thread or not self.emulation_thread.env:
            raise RuntimeError("No emulation running")
        
        env = self.emulation_thread.env
        
        try:
            # For file-based savestates, we can only restore basic Python state
            # The C++ emulator state cannot be safely restored from file data
            # without causing memory corruption
            
            # Restore basic state
            if state_data.get('done') is not None:
                env.done = state_data['done']
                
            print("Warning: File-based savestate loading only restores basic state.")
            print("For full state restoration, use in-memory savestates (save and load in same session).")
                
        except Exception as e:
            print(f"Warning: Could not restore some state data: {e}")
    
    def save_state_to_file(self, state_data: Dict[str, Any], filename: str):
        """Save state data to a file."""
        # Create a serializable version of the state
        serializable_state = {
            'rom_path': state_data['rom_path'],
            'ram': state_data['ram'].tolist() if state_data['ram'] is not None else None,
            'controllers': [state_data['controllers'][0].tolist(), state_data['controllers'][1].tolist()] if state_data['controllers'] else None,
            'done': state_data['done'],
            'timestamp': state_data['timestamp'],
            'version': '1.0'
        }
        
        with open(filename, 'wb') as f:
            pickle.dump(serializable_state, f)
    
    def load_state_from_file(self, filename: str) -> Dict[str, Any]:
        """Load state data from a file."""
        try:
            with open(filename, 'rb') as f:
                serializable_state = pickle.load(f)
            
            # Convert back to numpy arrays with error handling
            state_data = {
                'rom_path': serializable_state.get('rom_path'),
                'ram': None,
                'controllers': None,
                'done': serializable_state.get('done', False),
                'timestamp': serializable_state.get('timestamp', 0)
            }
            
            # Safely convert RAM data
            if serializable_state.get('ram') is not None:
                try:
                    state_data['ram'] = np.array(serializable_state['ram'])
                except Exception as e:
                    print(f"Warning: Could not convert RAM data: {e}")
                    state_data['ram'] = None
            
            # Safely convert controller data
            if serializable_state.get('controllers') is not None:
                try:
                    state_data['controllers'] = [
                        np.array(serializable_state['controllers'][0]),
                        np.array(serializable_state['controllers'][1])
                    ]
                except Exception as e:
                    print(f"Warning: Could not convert controller data: {e}")
                    state_data['controllers'] = None
            
            return state_data
            
        except Exception as e:
            print(f"Error loading state file {filename}: {e}")
            raise
    
    def update_state_status(self):
        """Update the state status indicator in the status bar."""
        if not self.state_slots:
            self.state_status_label.setText("States: --")
        else:
            slots = sorted(self.state_slots.keys())
            self.state_status_label.setText(f"States: {', '.join(map(str, slots))}")
    
    def clear_states(self):
        """Clear all saved states."""
        self.state_slots.clear()
        self.update_state_status()
    
    def load_existing_states(self):
        """Load existing state files for the current ROM."""
        if not self.rom_path:
            return
        
        rom_name = os.path.splitext(os.path.basename(self.rom_path))[0]
        
        # Check for existing state files
        for slot in range(1, 5):
            filename = os.path.join(self.state_directory, f"{rom_name}_slot_{slot}.state")
            if os.path.exists(filename):
                try:
                    state_data = self.load_state_from_file(filename)
                    self.state_slots[slot] = state_data
                except Exception as e:
                    # If loading fails, just skip this slot
                    print(f"Failed to load state slot {slot}: {e}")
        
        self.update_state_status()
    
    def save_state_to_file_dialog(self):
        """Show dialog to save state to a file."""
        if not self.is_emulation_running():
            QMessageBox.warning(self, "No Emulation", "No emulation is currently running.")
            return
        
        # Get default filename based on current ROM
        if self.rom_path:
            rom_name = os.path.splitext(os.path.basename(self.rom_path))[0]
            default_filename = f"{rom_name}_savestate.state"
        else:
            default_filename = "savestate.state"
        
        # Show file dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save State to File", 
            os.path.join(self.state_directory, default_filename),
            "NES State Files (*.state);;All Files (*)"
        )
        
        if file_path:
            try:
                # Create a backup of the current state in the C++ emulator
                self.emulation_thread.env._backup()
                
                # Get the state data from the emulator
                state_data = self.capture_emulator_state()
                
                # Save to file
                self.save_state_to_file(state_data, file_path)
                
                # Also store in a temporary slot for full restoration capability
                # Use slot 0 as a temporary slot for file-based states
                self.state_slots[0] = state_data
                
                # Show success message
                self.status_bar.showMessage(f"State saved to {os.path.basename(file_path)}", 3000)
                
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save state to file: {str(e)}")
    
    def load_state_from_file_dialog(self):
        """Show dialog to load state from a file."""
        if not self.is_emulation_running():
            QMessageBox.warning(self, "No Emulation", "No emulation is currently running.")
            return
        
        # Show file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Load State from File", 
            self.state_directory,
            "NES State Files (*.state);;All Files (*)"
        )
        
        if file_path:
            try:
                # Load state data from file
                state_data = self.load_state_from_file(file_path)
                
                # Check if the ROM matches
                if state_data.get('rom_path') != self.rom_path:
                    reply = QMessageBox.question(
                        self, 
                        "ROM Mismatch", 
                        f"The savestate was created with a different ROM:\n"
                        f"Savestate ROM: {os.path.basename(state_data.get('rom_path', 'Unknown'))}\n"
                        f"Current ROM: {os.path.basename(self.rom_path) if self.rom_path else 'Unknown'}\n\n"
                        f"Do you want to load it anyway? This may cause issues.",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    if reply != QMessageBox.Yes:
                        return
                
                # Store the loaded state in temporary slot 0
                # This allows us to use the C++ restore mechanism
                self.state_slots[0] = state_data
                
                # Use the same mechanism as quick loads
                # This will restore the most recent C++ backup
                if self.emulation_thread and self.emulation_thread.env:
                    self.emulation_thread.env._restore()
                
                # Show success message
                self.status_bar.showMessage(f"State loaded from {os.path.basename(file_path)}", 3000)
                
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Failed to load state from file: {str(e)}")
    
    def show_state_manager(self):
        """Show the state manager dialog."""
        dialog = StateManagerDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            # Refresh state status after any changes
            self.update_state_status()
    
    def showEvent(self, event):
        """Handle window show events."""
        super().showEvent(event)
        # Resize to fit game display when window is shown
        self.resize_to_fit_game()
    
    def resizeEvent(self, event):
        """Handle window resize events."""
        super().resizeEvent(event)
        # Make the game display fill the available space
        if hasattr(self, 'game_display'):
            # Get the available space (window size minus menu and status bar)
            menu_height = self.menuBar().height()
            status_height = self.status_bar.height()
            available_width = self.width()
            available_height = self.height() - menu_height - status_height
            
            # Resize game display to fill the available space while maintaining aspect ratio
            self.resize_game_display_with_aspect_ratio(available_width, available_height)
            
            # Update scale status based on current size
            self.update_scale_status()
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self.emulation_thread:
            self.emulation_thread.stop()
        
        # Clean up audio
        if self.audio_output:
            self.audio_output.stop()
            self.audio_output = None
        if self.audio_device:
            self.audio_device = None
        
        event.accept()


class AudioSettingsDialog(QDialog):
    """Dialog for configuring audio settings."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()
        self.apply_dark_theme()
    
    def init_ui(self):
        """Initialize the audio settings dialog UI."""
        self.setWindowTitle("Audio Settings")
        self.setModal(True)
        self.resize(400, 300)
        
        layout = QVBoxLayout()
        
        # Audio enable/disable
        enable_group = QGroupBox("Audio Output")
        enable_layout = QVBoxLayout()
        
        self.enable_audio_checkbox = QCheckBox("Enable Audio")
        self.enable_audio_checkbox.setChecked(self.parent.audio_enabled)
        enable_layout.addWidget(self.enable_audio_checkbox)
        
        enable_group.setLayout(enable_layout)
        layout.addWidget(enable_group)
        
        # Volume control
        volume_group = QGroupBox("Volume Control")
        volume_layout = QVBoxLayout()
        
        # Master volume
        master_layout = QHBoxLayout()
        master_layout.addWidget(QLabel("Master Volume:"))
        self.master_volume_slider = QSlider(Qt.Horizontal)
        self.master_volume_slider.setRange(0, 100)
        self.master_volume_slider.setValue(int(self.parent.master_volume * 100))
        self.master_volume_label = QLabel(f"{int(self.parent.master_volume * 100)}%")
        self.master_volume_slider.valueChanged.connect(
            lambda v: self.master_volume_label.setText(f"{v}%")
        )
        master_layout.addWidget(self.master_volume_slider)
        master_layout.addWidget(self.master_volume_label)
        volume_layout.addLayout(master_layout)
        
        # Sound effects volume
        sfx_layout = QHBoxLayout()
        sfx_layout.addWidget(QLabel("Sound Effects:"))
        self.sfx_volume_slider = QSlider(Qt.Horizontal)
        self.sfx_volume_slider.setRange(0, 100)
        self.sfx_volume_slider.setValue(80)
        self.sfx_volume_label = QLabel("80%")
        self.sfx_volume_slider.valueChanged.connect(
            lambda v: self.sfx_volume_label.setText(f"{v}%")
        )
        sfx_layout.addWidget(self.sfx_volume_slider)
        sfx_layout.addWidget(self.sfx_volume_label)
        volume_layout.addLayout(sfx_layout)
        
        # Music volume
        music_layout = QHBoxLayout()
        music_layout.addWidget(QLabel("Music:"))
        self.music_volume_slider = QSlider(Qt.Horizontal)
        self.music_volume_slider.setRange(0, 100)
        self.music_volume_slider.setValue(70)
        self.music_volume_label = QLabel("70%")
        self.music_volume_slider.valueChanged.connect(
            lambda v: self.music_volume_label.setText(f"{v}%")
        )
        music_layout.addWidget(self.music_volume_slider)
        music_layout.addWidget(self.music_volume_label)
        volume_layout.addLayout(music_layout)
        
        volume_group.setLayout(volume_layout)
        layout.addWidget(volume_group)
        
        # Audio quality
        quality_group = QGroupBox("Audio Quality")
        quality_layout = QVBoxLayout()
        
        # Sample rate
        sample_layout = QHBoxLayout()
        sample_layout.addWidget(QLabel("Sample Rate:"))
        self.sample_rate_combo = QComboBox()
        self.sample_rate_combo.addItems(["22050 Hz", "44100 Hz", "48000 Hz"])
        self.sample_rate_combo.setCurrentText("44100 Hz")
        sample_layout.addWidget(self.sample_rate_combo)
        quality_layout.addLayout(sample_layout)
        
        # Buffer size
        buffer_layout = QHBoxLayout()
        buffer_layout.addWidget(QLabel("Buffer Size:"))
        self.buffer_size_combo = QComboBox()
        self.buffer_size_combo.addItems(["Small (64)", "Medium (128)", "Large (256)", "Extra Large (512)"])
        self.buffer_size_combo.setCurrentText("Medium (128)")
        buffer_layout.addWidget(self.buffer_size_combo)
        quality_layout.addLayout(buffer_layout)
        
        # Audio device
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("Audio Device:"))
        self.audio_device_combo = QComboBox()
        self.audio_device_combo.addItems(["Default", "Primary Sound Driver", "DirectSound", "WASAPI"])
        self.audio_device_combo.setCurrentText("Default")
        device_layout.addWidget(self.audio_device_combo)
        quality_layout.addLayout(device_layout)
        
        quality_group.setLayout(quality_layout)
        layout.addWidget(quality_group)
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        test_button = QPushButton("Test Audio")
        test_button.clicked.connect(self.test_audio)
        button_layout.addWidget(test_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def apply_dark_theme(self):
        """Apply dark theme to the dialog."""
        self.setStyleSheet("""
            QDialog {
                background-color: #0f1419;
                color: #cbd5e0;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                color: #cbd5e0;
                border: 2px solid #2d3748;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QLabel {
                color: #cbd5e0;
                font-size: 12px;
            }
            QCheckBox {
                color: #cbd5e0;
                font-size: 12px;
            }
            QSlider::groove:horizontal {
                border: 1px solid #2d3748;
                height: 8px;
                background: #1a202c;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #2d5a27;
                border: 1px solid #2d5a27;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: #1a3d1a;
            }
            QComboBox {
                background-color: #1a202c;
                border: 1px solid #2d3748;
                border-radius: 4px;
                color: #cbd5e0;
                padding: 4px;
                font-size: 12px;
            }
            QComboBox:hover {
                border-color: #2d5a27;
            }
            QPushButton {
                background-color: #2d3748;
                border: 1px solid #2d3748;
                color: #cbd5e0;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2d5a27;
            }
        """)
    
    def test_audio(self):
        """Test audio output."""
        try:
            # Generate a simple test tone (440 Hz sine wave)
            sample_rate = 44100
            duration = 0.5  # 0.5 seconds
            frequency = 440  # A4 note
            
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            test_tone = np.sin(2 * np.pi * frequency * t) * 0.3  # 30% volume
            
            # Play the test tone
            self.parent.play_audio(test_tone)
            QMessageBox.information(self, "Audio Test", "Test tone played successfully!")
            
        except Exception as e:
            QMessageBox.warning(self, "Audio Test Failed", f"Failed to play test tone: {str(e)}")


class StateManagerDialog(QDialog):
    """Dialog for managing save states."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()
        self.apply_dark_theme()
        self.load_state_info()
    
    def init_ui(self):
        """Initialize the state manager dialog UI."""
        self.setWindowTitle("State Manager")
        self.setModal(True)
        self.resize(600, 400)
        
        layout = QVBoxLayout()
        
        # State slots table
        self.state_table = QTextEdit()
        self.state_table.setReadOnly(True)
        self.state_table.setMaximumHeight(200)
        layout.addWidget(QLabel("Saved States:"))
        layout.addWidget(self.state_table)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.load_state_info)
        button_layout.addWidget(refresh_button)
        
        clear_all_button = QPushButton("Clear All")
        clear_all_button.clicked.connect(self.clear_all_states)
        button_layout.addWidget(clear_all_button)
        
        button_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def apply_dark_theme(self):
        """Apply dark theme to the dialog."""
        self.setStyleSheet("""
            QDialog {
                background-color: #0f1419;
                color: #cbd5e0;
            }
            QLabel {
                color: #cbd5e0;
                font-size: 12px;
                font-weight: bold;
            }
            QTextEdit {
                background-color: #1a202c;
                border: 1px solid #2d3748;
                border-radius: 4px;
                color: #cbd5e0;
                font-size: 11px;
                padding: 8px;
            }
            QPushButton {
                background-color: #2d3748;
                border: 1px solid #2d3748;
                color: #cbd5e0;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2d5a27;
            }
        """)
    
    def load_state_info(self):
        """Load and display state information."""
        if not self.parent.state_slots:
            self.state_table.setPlainText("No saved states found.")
            return
        
        info_text = "Slot | ROM | Timestamp\n"
        info_text += "-" * 50 + "\n"
        
        for slot in sorted(self.parent.state_slots.keys()):
            state_data = self.parent.state_slots[slot]
            rom_name = os.path.basename(state_data.get('rom_path', 'Unknown'))
            timestamp = state_data.get('timestamp', 0)
            time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
            info_text += f"{slot:4} | {rom_name:20} | {time_str}\n"
        
        self.state_table.setPlainText(info_text)
    
    def clear_all_states(self):
        """Clear all saved states."""
        reply = QMessageBox.question(
            self, "Clear All States", 
            "Are you sure you want to clear all saved states? This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.parent.clear_states()
            self.load_state_info()


def main():
    """Main entry point for the GUI application."""
    # Suppress Wayland warnings
    os.environ['QT_LOGGING_RULES'] = 'qt.qpa.wayland.debug=false'
    os.environ['QT_QPA_PLATFORM'] = 'xcb'  # Force X11 backend to avoid Wayland issues
    
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("NESendo")
    app.setApplicationVersion("8.2.1")
    app.setOrganizationName("NESendo")
    
    # Create and show main window
    window = NESendoGUI()
    window.show()
    
    # Start the application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
