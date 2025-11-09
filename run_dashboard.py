"""
Simple script to run the Streamlit dashboard.
"""
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    dashboard_path = Path(__file__).parent / "streamlit_dashboard.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(dashboard_path)], check=True)





