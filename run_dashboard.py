"""
Simple script to run the Streamlit dashboard.
"""
import subprocess
import sys
from pathlib import Path

def main() -> None:
    """Launch the Streamlit dashboard."""
    dashboard_path = Path(__file__).parent / "streamlit_dashboard.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(dashboard_path)]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()





