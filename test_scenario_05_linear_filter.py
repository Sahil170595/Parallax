#!/usr/bin/env python3
"""Test scenario: Filter issues by status in Linear"""

import sys
import os
import subprocess

# Fix Windows encoding issues
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONLEGACYWINDOWSSTDIO"] = "0"

if __name__ == "__main__":
    cmd = [
        sys.executable,
        "-m",
        "parallax.runner.cli",
        "Filter issues by status",
        "--app-name",
        "linear",
        "--start-url",
        "https://linear.app",
    ]
    
    env = os.environ.copy()
    if sys.platform == "win32":
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONLEGACYWINDOWSSTDIO"] = "0"
    
    subprocess.run(cmd, env=env)



