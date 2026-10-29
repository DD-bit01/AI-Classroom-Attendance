import os
import sys
import subprocess
import webbrowser
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / "venv" / "Scripts" / "python.exe"

def main():
    python_cmd = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    print("=" * 65)
    print("  AURA // AI CLASSROOM ATTENDANCE MANAGEMENT SYSTEM")
    print("=" * 65)
    print(f"[*] Python Interpreter: {python_cmd}")
    print("[*] Starting FastAPI Server on http://localhost:8000 ...")

    # Start uvicorn server binding to 0.0.0.0 so both localhost and 127.0.0.1 work
    cmd = [python_cmd, "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
    
    # Open browser after a short delay
    def open_browser():
        time.sleep(1.2)
        webbrowser.open("http://127.0.0.1:8000")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    try:
        subprocess.run(cmd, cwd=str(ROOT))
    except KeyboardInterrupt:
        print("\n[*] Server stopped.")

if __name__ == "__main__":
    main()
