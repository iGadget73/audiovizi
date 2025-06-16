import sys
import subprocess
import numpy as np
import re

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QSlider, QCheckBox
)
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal
import pyqtgraph as pg
import shutil
ffmpeg_path = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"

class VisualSettings:
    def __init__(self):
        self.threshold_orange = 0.7
        self.threshold_red = 0.9

        self.wave_color = "#ffffff"       # Basisfarbe
        self.bg_color = "#000000"
        self.color_orange = "#ffa500"
        self.color_red = "#ff0000"

        self.wave_color_map = {
            "Grün": "#009e00",
            "Weiß": "#ffffff",
            "Gelb": "#ffff00",
            "Rot": "#ff0000",
            "Cyan": "#00ffff",
            "Magenta": "#ff00ff",
            "Blau": "#0000ff",
            "Schwarz": "#000000",
        }
        self.bg_color_map = {
            "Schwarz": "#000000",
            "Weiß": "#ffffff",
            "Rot": "#ff0000",
            "Grün": "#009e00",
            "Blau": "#0000ff",
            "Gelb": "#ffff00",
            "Magenta": "#ff00ff",
            "Cyan": "#00ffff",
        }

class ResettableSlider(QSlider):
    def __init__(self, orientation, default_value, parent=None):
        super().__init__(orientation, parent)
        self.default_value = default_value

    def mouseDoubleClickEvent(self, event):
        self.setValue(self.default_value)


class AudioCaptureThread(QThread):
    """Thread, der kontinuierlich Audiodaten von ffmpeg liest."""

    data_ready = pyqtSignal(object)

    def __init__(self, source, sample_rate, block_size):
        super().__init__()
        self.source = source
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.running = True

    def run(self):
        ffmpeg_cmd = [
            ffmpeg_path,
            "-f", "avfoundation",
            "-i", self.source,
            "-ac", "1",
            "-ar", str(self.sample_rate),
            "-f", "f32le",
            "pipe:"
        ]
        process = subprocess.Popen(
            ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        bytes_per_sample = 4
        while self.running:
            raw_data = process.stdout.read(self.block_size * bytes_per_sample)
            if not raw_data or len(raw_data) < self.block_size * bytes_per_sample:
                break
            chunk = np.frombuffer(raw_data, dtype=np.float32)
            self.data_ready.emit(chunk)
        process.terminate()

    def stop(self):
        self.running = False


class PCMVisualizerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PCM Audio Visualizer - Time Zoom + Vertical Padding + Cursor")
        self.setGeometry(100, 100, 900, 500)

        self.capture_thread = None
        self.running = False

        # --- Audio-Puffer ---
        self.sample_rate = 44100
        self.buffer_seconds = 5
        self.num_samples = self.sample_rate * self.buffer_seconds
        self.audio_data = np.zeros(self.num_samples, dtype=np.float32)
        self.block_size = 1024

        # --- Visual-Einstellungen ---
        self.amplitude_factor = 1.0
        self.time_zoom_factor = 1.0
        self.vertical_padding_factor = 0.0

        # Einstellungen
        self.settings = VisualSettings()

        # --- GUI ---
        main_layout = QVBoxLayout()

        # 1) Audio-Quelle
        source_layout = QHBoxLayout()
        source_layout.addStretch(1)
        source_label = QLabel("Source:")
        source_layout.addWidget(source_label)
        self.audio_dropdown = QComboBox()
        self.audio_dropdown.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.refresh_audio_sources()
        source_layout.addWidget(self.audio_dropdown)
        source_layout.addStretch(1)
        main_layout.addLayout(source_layout)

        # 2) Slider
        sliders_layout = QHBoxLayout()

        # Amplitude
        amp_layout = QVBoxLayout()
        amp_label = QLabel("Amplitude")
        amp_layout.addWidget(amp_label)
        self.amp_slider = ResettableSlider(Qt.Orientation.Horizontal, default_value=100)
        self.amp_slider.setRange(1, 200)
        self.amp_slider.setValue(100)
        self.amp_slider.valueChanged.connect(self.on_amp_changed)
        amp_layout.addWidget(self.amp_slider)
        self.amp_value_label = QLabel("8.00")
        amp_layout.addWidget(self.amp_value_label)
        sliders_layout.addLayout(amp_layout)

        # Time Zoom
        zoom_layout = QVBoxLayout()
        zoom_label = QLabel("Time Zoom")
        zoom_layout.addWidget(zoom_label)
        self.zoom_slider = ResettableSlider(Qt.Orientation.Horizontal, default_value=10)
        self.zoom_slider.setRange(1, 100)
        self.zoom_slider.setValue(10)
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        zoom_layout.addWidget(self.zoom_slider)
        self.zoom_value_label = QLabel("1.00")
        zoom_layout.addWidget(self.zoom_value_label)
        sliders_layout.addLayout(zoom_layout)

        # Vert. Padding
        pad_layout = QVBoxLayout()
        pad_label = QLabel("Vert. Padding")
        pad_layout.addWidget(pad_label)
        self.pad_slider = ResettableSlider(Qt.Orientation.Horizontal, default_value=0)
        self.pad_slider.setRange(0, 100)
        self.pad_slider.setValue(0)
        self.pad_slider.valueChanged.connect(self.on_pad_changed)
        pad_layout.addWidget(self.pad_slider)
        self.pad_value_label = QLabel("0.00")
        pad_layout.addWidget(self.pad_value_label)
        sliders_layout.addLayout(pad_layout)

        main_layout.addLayout(sliders_layout)

        # 3) Farbeinstellungen
        lower_layout = QHBoxLayout()
        colors_layout = QHBoxLayout()

        # Wellenfarbe
        wave_color_layout = QVBoxLayout()
        wave_color_label = QLabel("Wellenfarbe")
        wave_color_layout.addWidget(wave_color_label)
        self.wave_color_dropdown = QComboBox()
        self.wave_color_dropdown.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        for name, code in self.settings.wave_color_map.items():
            self.wave_color_dropdown.addItem(name, code)
        self.wave_color_dropdown.currentIndexChanged.connect(self.on_wave_color_changed)
        wave_color_layout.addWidget(self.wave_color_dropdown)
        colors_layout.addLayout(wave_color_layout)

        # Hintergrund
        bg_color_layout = QVBoxLayout()
        bg_color_label = QLabel("Hintergrund")
        bg_color_layout.addWidget(bg_color_label)
        self.bg_color_dropdown = QComboBox()
        self.bg_color_dropdown.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        for name, code in self.settings.bg_color_map.items():
            self.bg_color_dropdown.addItem(name, code)
        self.bg_color_dropdown.currentIndexChanged.connect(self.on_bg_color_changed)
        bg_color_layout.addWidget(self.bg_color_dropdown)
        colors_layout.addLayout(bg_color_layout)

        lower_layout.addLayout(colors_layout)

        # 4) Checkboxes (Cursor oben, Levelmeter darunter)
        checkbox_layout = QVBoxLayout()
        self.cursor_checkbox = QCheckBox("Zeige Waveform Cursor")
        checkbox_layout.addWidget(self.cursor_checkbox)

        self.levelmeter_checkbox = QCheckBox("Levelmeter-Farbstufen")
        self.levelmeter_checkbox.setChecked(True)
        checkbox_layout.addWidget(self.levelmeter_checkbox)

        lower_layout.addLayout(checkbox_layout)
        lower_layout.addStretch(1)

        # Start/Stop-Button
        self.toggle_button = QPushButton("Start Visualizer")
        self.toggle_button.setFixedWidth(150)
        self.toggle_button.setStyleSheet(
            "padding: 10px; border-radius: 10px; background-color: #aaa; color: black;"
        )
        self.toggle_button.clicked.connect(self.toggle_visualizer)
        lower_layout.addWidget(self.toggle_button)

        main_layout.addLayout(lower_layout)

        # 5) Plot
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.hideAxis("bottom")
        self.plot_widget.hideAxis("left")
        self.plot_widget.setBackground(self.settings.bg_color)

        # Kurven
        # Basiskurve (immer sichtbar in Levelmeter-Modus)
        self.curve_base = self.plot_widget.plot(
            pen=self.settings.wave_color, name="Base"
        )
        # Orange- und Rot-Layer (werden nur dort gezeichnet, wo amplitude > thresh)
        self.curve_orange = self.plot_widget.plot(
            pen=self.settings.color_orange, name="Orange"
        )
        self.curve_red = self.plot_widget.plot(
            pen=self.settings.color_red, name="Red"
        )
        # Einzelkurve (wenn Levelmeter deaktiviert)
        self.single_curve = self.plot_widget.plot(
            pen=self.settings.wave_color, name="SingleCurve"
        )

        # Die Z-Reihenfolge anpassen, damit Rot über Orange über Weiß liegt
        self.curve_base.setZValue(0)
        self.curve_orange.setZValue(1)
        self.curve_red.setZValue(2)

        # Cursor
        self.cursor_line = pg.InfiniteLine(
            angle=90, pen=pg.mkPen(self.settings.wave_color, width=2)
        )
        self.cursor_line.setVisible(False)
        self.plot_widget.addItem(self.cursor_line)

        main_layout.addWidget(self.plot_widget)

        # 6) Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        # Update-Intervall leicht erhöht für geringere CPU-Last
        self.timer.start(100)

        self.setLayout(main_layout)

    # -----------------------------------------------------------------------
    # Audio-Device-Scan
    # -----------------------------------------------------------------------
    def refresh_audio_sources(self):
        ffmpeg_path = "/opt/homebrew/bin/ffmpeg"
        try:
            result = subprocess.run(
                [ffmpeg_path, "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            output = result.stderr
            audio_section = re.split(r'AVFoundation audio devices:', output)
            self.audio_dropdown.clear()
            if len(audio_section) < 2:
                self.audio_dropdown.addItem("No Audio Devices Found")
                return
            audio_lines = audio_section[1]
            matches = re.findall(r'\[(\d+)\]\s+(.*)', audio_lines)
            if not matches:
                self.audio_dropdown.addItem("No Audio Devices Found")
            else:
                for idx, name in matches:
                    source_string = f":{idx}"
                    display_name = f"{idx} - {name}"
                    self.audio_dropdown.addItem(display_name, source_string)

                for i in range(self.audio_dropdown.count()):
                    if "soundcraft" in self.audio_dropdown.itemText(i).lower():
                        self.audio_dropdown.setCurrentIndex(i)
                        break

        except Exception:
            self.audio_dropdown.clear()
            self.audio_dropdown.addItem("Error: Cannot Fetch Devices")

    # -----------------------------------------------------------------------
    # Start/Stop
    # -----------------------------------------------------------------------
    def toggle_visualizer(self):
        if self.running:
            self.stop_visualizer()
            self.toggle_button.setText("Start Visualizer")
            self.toggle_button.setStyleSheet(
                "padding: 10px; box-shadow: 1px 1px 2px #0008;"
                "border-radius: 10px; background-color: #aaa; color: black;"
            )
        else:
            self.start_visualizer()
            self.toggle_button.setText("Stop Visualizer")
            self.toggle_button.setStyleSheet(
                "padding: 10px; box-shadow: 1px 1px 2px #0008;"
                "border-radius: 10px; background-color: #555555; color: white;"
            )

    def start_visualizer(self):
        if (
            self.audio_dropdown.currentText()
            and "No Audio Devices" not in self.audio_dropdown.currentText()
            and "Error:" not in self.audio_dropdown.currentText()
        ):
            self.running = True
            source = self.audio_dropdown.currentData()
            self.capture_thread = AudioCaptureThread(
                source, self.sample_rate, self.block_size
            )
            self.capture_thread.data_ready.connect(self.update_audio_buffer)
            self.capture_thread.start()
        else:
            print("Kein gültiges Audio-Device ausgewählt.")

    def update_audio_buffer(self, chunk):
        self.audio_data = np.roll(self.audio_data, -len(chunk))
        self.audio_data[-len(chunk):] = chunk

    def stop_visualizer(self):
        self.running = False
        if self.capture_thread:
            self.capture_thread.stop()
            self.capture_thread.wait()
            self.capture_thread = None

    # -----------------------------------------------------------------------
    # Plot-Update
    # -----------------------------------------------------------------------
    def update_plot(self):
        visible_samples = int(self.num_samples / max(self.time_zoom_factor, 1.0))
        start_idx = self.num_samples - visible_samples
        x_data = np.arange(visible_samples)
        y_data = self.audio_data[start_idx:start_idx + visible_samples] * self.amplitude_factor
        abs_vals = np.abs(y_data)

        if self.levelmeter_checkbox.isChecked():
            # Levelmeter an -> wir blenden single_curve aus
            self.single_curve.hide()

            self.curve_base.show()
            self.curve_orange.show()
            self.curve_red.show()

            # 1) Basiskurve: gesamte Welle (keine Lücken)
            self.curve_base.setData(x_data, y_data, connect="all")

            # 2) Orange nur dort, wo amplitude >= threshold_orange und < threshold_red
            y_orange = np.where(
                (abs_vals >= self.settings.threshold_orange) & 
                (abs_vals < self.settings.threshold_red),
                y_data, 
                np.nan
            )
            self.curve_orange.setData(x_data, y_orange, connect="finite")

            # 3) Rot nur dort, wo amplitude >= threshold_red
            y_red = np.where(abs_vals >= self.settings.threshold_red, y_data, np.nan)
            self.curve_red.setData(x_data, y_red, connect="finite")

        else:
            # Levelmeter aus -> nur single_curve
            self.single_curve.show()
            self.curve_base.hide()
            self.curve_orange.hide()
            self.curve_red.hide()

            self.single_curve.setData(x_data, y_data, connect="all")

        self.plot_widget.setXRange(0, visible_samples, padding=0)
        vertical_padding = self.vertical_padding_factor
        self.plot_widget.setYRange(-1 - vertical_padding, 1 + vertical_padding, padding=0)

        # Cursor
        if self.cursor_checkbox.isChecked():
            self.cursor_line.setVisible(True)
            gap = 5
            cursor_pos = visible_samples - gap
            self.cursor_line.setPos(cursor_pos)
        else:
            self.cursor_line.setVisible(False)

    # -----------------------------------------------------------------------
    # Slider-/Dropdown-Callbacks
    # -----------------------------------------------------------------------
    def on_amp_changed(self, value):
        self.amplitude_factor = value / 10.0
        self.amp_value_label.setText(f"{self.amplitude_factor:.2f}")

    def on_zoom_changed(self, value):
        new_val = value / 10.0
        if new_val < 1.0:
            new_val = 1.0
        self.time_zoom_factor = new_val
        self.zoom_value_label.setText(f"{self.time_zoom_factor:.2f}")

    def on_pad_changed(self, value):
        self.vertical_padding_factor = value / 100.0
        self.pad_value_label.setText(f"{self.vertical_padding_factor:.2f}")

    def on_wave_color_changed(self):
        color_code = self.wave_color_dropdown.currentData()
        self.settings.wave_color = color_code

        # Basiskurve + Single-Kurve + Cursor
        self.curve_base.setPen(self.settings.wave_color)
        self.single_curve.setPen(self.settings.wave_color)
        self.cursor_line.setPen(pg.mkPen(self.settings.wave_color, width=2))

    def on_bg_color_changed(self):
        bg_color = self.bg_color_dropdown.currentData()
        self.settings.bg_color = bg_color
        self.plot_widget.setBackground(self.settings.bg_color)


if __name__ == "__main__":
    # Mic-Zugriffsabfrage auslösen (nur einmalig, ohne Aufnahme)
    try:
        subprocess.run([
            ffmpeg_path,
            "-f", "avfoundation",
            "-list_devices", "true",
            "-i", ""
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    app = QApplication(sys.argv)
    window = PCMVisualizerApp()
    window.show()
    sys.exit(app.exec())

