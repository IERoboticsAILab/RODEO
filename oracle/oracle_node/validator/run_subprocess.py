import os
import sys
import subprocess
from pathlib import Path

def run_rosbag_validator(bag_path: str):
    """
    Run ros1 validator as a child process.
    Returns tuple exit_code, combined_output_text.
    """
    module_file = Path(__file__).parent / "ros1_validator.py"
    cmd = [sys.executable, str(module_file), "--bag", bag_path]
    env = os.environ.copy()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
        out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        return proc.returncode, out
    except Exception as e:
        return 99, f"Validator failed to start, {e}"
