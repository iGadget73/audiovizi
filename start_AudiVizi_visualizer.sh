#!/bin/bash
# Automatisch generiertes Startskript für macOS

# Sicherstellen, dass das richtige Python-Environment verwendet wird
PYTHON_EXEC="/opt/homebrew/bin/python3"

# Pfad zum Visualizer-Skript (hier als Beispiel im gleichen Verzeichnis)
SCRIPT_PATH="$(dirname "$0")/pcm_visualizer.py"

# GUI-Skript starten
"$PYTHON_EXEC" "$SCRIPT_PATH"
