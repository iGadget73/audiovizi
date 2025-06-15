import sys
import subprocess
import numpy as np
import re
import threading

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QSlider, QCheckBox
)
from PyQt6.QtCore import QTimer, Qt
import pyqtgraph as pg


class ResettableSlider(QSlider):
    """Slider, der bei Doppelklick auf seinen Default-Wert zurückspringt."""
    def __init__(self, orientation, default_value, parent=None):
        super().__init__(orientation, parent)
        self.default_value = default_value

    def mouseDoubleClickEvent(self, event):
        self.setValue(self.default_value)


class PCMVisualizerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PCM Audio Visualizer - Time Zoom + Vertical Padding + Cursor")
        self.setGeometry(100, 100, 900, 500)

        self.process = None
        self.running = False

        # --- Audio-Puffer ---
        self.sample_rate = 44100
        self.buffer_seconds = 5
        self.num_samples = self.sample_rate * self.buffer_seconds  # z.B. 220500
        self.audio_data = np.zeros(self.num_samples, dtype=np.float32)
        self.block_size = 1024

        # --- Visual-Einstellungen ---
        self.amplitude_factor = 1.0      # Gain
        self.time_zoom_factor = 1.0      # Horizontaler Zoom: 1.0 = volle Pufferlänge
        self.vertical_padding_factor = 0.0  # Zusätzlicher Platz oben/unten (als Anteil von 1.0)

        # Farben
        self.color_map = {
            "Weiß": "w",
            "Gelb": "y",
            "Rot": "r",
            "Grün": "#009e00",
            "Cyan": "c",
            "Magenta": "m",
            "Blau": "b",
            "Schwarz": "k",
        }
        self.bg_color_map = {
            "Schwarz": "k",
            "Weiß": "w",
            "Rot": "r",
            "Grün": "#009e00",
            "Blau": "b",
            "Gelb": "y",
            "Magenta": "m",
            "Cyan": "c",
        }

        # --- GUI-Aufbau ---
        main_layout = QVBoxLayout()

        # 1) Obere Zeile: Source-Label und Audio-Dropdown (zentriert)
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

        # 2) Zweite Zeile: Slider für Amplitude, Time Zoom, Vertical Padding
        sliders_layout = QHBoxLayout()

        # Amplitude-Slider
        amp_layout = QVBoxLayout()
        amp_label = QLabel("Amplitude")
        amp_layout.addWidget(amp_label)
        self.amp_slider = ResettableSlider(Qt.Orientation.Horizontal, default_value=10)
        self.amp_slider.setRange(1, 200)
        self.amp_slider.setValue(10)  # => amplitude_factor=1.0
        self.amp_slider.valueChanged.connect(self.on_amp_changed)
        amp_layout.addWidget(self.amp_slider)
        self.amp_value_label = QLabel("1.00")
        amp_layout.addWidget(self.amp_value_label)
        sliders_layout.addLayout(amp_layout)

        # Time-Zoom-Slider
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

        # Vertical-Padding-Slider
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

        # 3) Dritte Zeile: Farbdropdowns und Waveform Cursor Checkbox sowie Toggle-Button
        lower_layout = QHBoxLayout()
        # Farbdropdowns
        colors_layout = QHBoxLayout()
        # Wellenfarbe
        wave_color_layout = QVBoxLayout()
        wave_color_label = QLabel("Wellenfarbe")
        wave_color_layout.addWidget(wave_color_label)
        self.wave_color_dropdown = QComboBox()
        self.wave_color_dropdown.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        for name, code in self.color_map.items():
            self.wave_color_dropdown.addItem(name, code)
        self.wave_color_dropdown.currentIndexChanged.connect(self.on_wave_color_changed)
        wave_color_layout.addWidget(self.wave_color_dropdown)
        colors_layout.addLayout(wave_color_layout)
        # Hintergrundfarbe
        bg_color_layout = QVBoxLayout()
        bg_color_label = QLabel("Hintergrund")
        bg_color_layout.addWidget(bg_color_label)
        self.bg_color_dropdown = QComboBox()
        self.bg_color_dropdown.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        for name, code in self.bg_color_map.items():
            self.bg_color_dropdown.addItem(name, code)
        self.bg_color_dropdown.currentIndexChanged.connect(self.on_bg_color_changed)
        bg_color_layout.addWidget(self.bg_color_dropdown)
        colors_layout.addLayout(bg_color_layout)
        lower_layout.addLayout(colors_layout)
        # Waveform Cursor Checkbox
        self.cursor_checkbox = QCheckBox("Zeige Waveform Cursor")
        lower_layout.addWidget(self.cursor_checkbox)
        lower_layout.addStretch(1)
        # Toggle-Button (Start/Stop) mit extra Padding
        self.toggle_button = QPushButton("Start Visualizer")
        self.toggle_button.setFixedWidth(150)
        self.toggle_button.setStyleSheet("padding: 10px; border-radius: 10px; background-color: #aaa; color: black;")
        self.toggle_button.clicked.connect(self.toggle_visualizer)
        lower_layout.addWidget(self.toggle_button)
        main_layout.addLayout(lower_layout)

        # 4) Plot
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.hideAxis('bottom')
        self.plot_widget.hideAxis('left')
        self.plot_widget.setBackground("#000000")
        self.curve = self.plot_widget.plot(self.audio_data, pen="w")
        # Füge einen Cursor als InfiniteLine hinzu; zunächst unsichtbar
        self.cursor_line = pg.InfiniteLine(angle=90, pen=pg.mkPen("w", width=2))
        self.cursor_line.setVisible(False)
        self.plot_widget.addItem(self.cursor_line)
        main_layout.addWidget(self.plot_widget)

        # 5) Timer für Plot-Update
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(50)
        self.setLayout(main_layout)

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
        except Exception:
            self.audio_dropdown.clear()
            self.audio_dropdown.addItem("Error: Cannot Fetch Devices")

    def toggle_visualizer(self):
        if self.running:
            self.stop_visualizer()
            self.toggle_button.setText("Start Visualizer")
            self.toggle_button.setStyleSheet("padding: 10px; box-shadow: 1px 1px 2px #0008; border-radius: 10px; background-color: #aaa; color: black;")
        else:
            self.start_visualizer()
            self.toggle_button.setText("Stop Visualizer")
            self.toggle_button.setStyleSheet("padding: 10px; box-shadow: 1px 1px 2px #0008; border-radius: 10px; background-color: #555555; color: white;")

    def start_visualizer(self):
        if (self.audio_dropdown.currentText() and 
            "No Audio Devices" not in self.audio_dropdown.currentText() and
            "Error:" not in self.audio_dropdown.currentText()):
            self.running = True
            source = self.audio_dropdown.currentData()
            self.thread = threading.Thread(target=self.run_visualizer, args=(source,))
            self.thread.start()
        else:
            print("Kein gültiges Audio-Device ausgewählt.")

    def run_visualizer(self, source):
        ffmpeg_path = "/opt/homebrew/bin/ffmpeg"
        ffmpeg_cmd = [
            ffmpeg_path,
            "-f", "avfoundation",
            "-i", source,
            "-ac", "1",
            "-ar", str(self.sample_rate),
            "-f", "f32le",
            "pipe:"
        ]
        self.process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        bytes_per_sample = 4
        while self.running:
            raw_data = self.process.stdout.read(self.block_size * bytes_per_sample)
            if not raw_data or len(raw_data) < self.block_size * bytes_per_sample:
                break
            chunk = np.frombuffer(raw_data, dtype=np.float32)
            self.audio_data = np.roll(self.audio_data, -len(chunk))
            self.audio_data[-len(chunk):] = chunk
        if self.process:
            self.process.terminate()

    def stop_visualizer(self):
        self.running = False

    def update_plot(self):
        # Horizontaler Ausschnitt (Time Zoom)
        visible_samples = int(self.num_samples / max(self.time_zoom_factor, 1.0))
        start_idx = self.num_samples - visible_samples
        x_data = np.arange(visible_samples)
        y_data = self.audio_data[start_idx:start_idx + visible_samples] * self.amplitude_factor
        self.curve.setData(x_data, y_data)

        self.plot_widget.setXRange(0, visible_samples, padding=0)
        # Fester Y-Bereich: immer [-1, 1] plus vertikales Padding
        vertical_padding = self.vertical_padding_factor
        self.plot_widget.setYRange(-1 - vertical_padding, 1 + vertical_padding, padding=0)
        
        # Cursor: Falls Checkbox aktiviert, zeige vertikale Linie am rechten Rand des sichtbaren Bereichs
        if self.cursor_checkbox.isChecked():
            self.cursor_line.setVisible(True)
            # Ein kleines Gap von z.B. 5 Samples vom rechten Rand
            gap = 5
            cursor_pos = visible_samples - gap
            self.cursor_line.setPos(cursor_pos)
        else:
            self.cursor_line.setVisible(False)

    # --- Slider-/Dropdown-Callbacks ---
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
        self.curve.setPen(color_code)
        self.cursor_line.setPen(pg.mkPen(color_code, width=2))


    def on_bg_color_changed(self):
        bg_color = self.bg_color_dropdown.currentData()
        self.plot_widget.setBackground(bg_color)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PCMVisualizerApp()
    window.show()
    sys.exit(app.exec())
