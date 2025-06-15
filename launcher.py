import subprocess
import sys
import os
import shutil

def log(msg):
    with open("/tmp/audivizi_launcher.log", "a") as f:
        f.write(msg + "\n")

log("Launcher gestartet")

ffmpeg_path = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
log(f"ffmpeg path: {ffmpeg_path}")

try:
    subprocess.Popen(
        [ffmpeg_path, "-f", "avfoundation", "-i", ":0", "-t", "1", "-y", "/tmp/test.wav"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    log("ffmpeg launched")
except Exception as e:
    log(f"ffmpeg error: {e}")

try:
    base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    resource_path = os.path.abspath(os.path.join(base_path, "..", "Resources"))
    script_path = os.path.join(resource_path, "script-vizi-1.py")
    log(f"Launching script: {script_path}")
    subprocess.Popen(['python3', script_path])
except Exception as e:
    log(f"Script launch error: {e}")

sys.exit(0)
