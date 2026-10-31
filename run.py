import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
backend=subprocess.Popen([sys.executable,'-m','backend.server'],cwd=ROOT)
frontend=subprocess.Popen([sys.executable,'frontend/server.py'],cwd=ROOT)
try:
    backend.wait()
finally:
    frontend.terminate()
