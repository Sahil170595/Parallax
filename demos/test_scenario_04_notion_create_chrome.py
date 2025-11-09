#!/usr/bin/env python3
"""Test scenario: Create a new page in Notion using Chrome browser"""

import sys
import os
import subprocess
import tempfile
import yaml
from pathlib import Path

# Fix Windows encoding issues
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONLEGACYWINDOWSSTDIO"] = "0"

def create_chrome_config():
    """Create a temporary config file with Chrome channel enabled."""
    # Load base config
    base_config_path = Path("configs/config.yaml")
    if base_config_path.exists():
        with open(base_config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    else:
        config = {}
    
    # Ensure playwright section exists
    if "playwright" not in config:
        config["playwright"] = {}
    
    # Set Chrome channel
    config["playwright"]["project"] = "chromium"
    config["playwright"]["channel"] = "chrome"
    config["playwright"]["headless"] = False  # Show browser for debugging
    # Use persistent context for authentication
    # Set this to the path where you saved your authentication session
    # Run: python authenticate.py notion
    # Then uncomment and set the path below:
    # config["playwright"]["user_data_dir"] = str(Path.home() / ".parallax" / "browser_data" / "notion")
    
    # Create temporary config file
    temp_dir = Path(tempfile.gettempdir())
    temp_config = temp_dir / "parallax_chrome_config.yaml"
    
    with open(temp_config, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False)
    
    return temp_config

if __name__ == "__main__":
    # Create Chrome config
    chrome_config = create_chrome_config()
    
    # Set environment variable to use the Chrome config
    original_config = os.environ.get("PARALLAX_CONFIG")
    os.environ["PARALLAX_CONFIG"] = str(chrome_config)
    
    try:
        cmd = [
            sys.executable,
            "-m",
            "parallax.runner.cli",
            "Create a new page in Notion",
            "--app-name",
            "notion",
            "--start-url",
            "https://notion.so",
        ]
        
        env = os.environ.copy()
        if sys.platform == "win32":
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONLEGACYWINDOWSSTDIO"] = "0"
        
        print(f"[Chrome Test] Using Chrome browser (config: {chrome_config})")
        print(f"[Chrome Test] Running: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, env=env)
        
        # Clean up temp config
        if chrome_config.exists():
            chrome_config.unlink()
        
        sys.exit(result.returncode)
    except Exception as e:
        print(f"[Chrome Test] Error: {e}", file=sys.stderr)
        # Clean up temp config
        if chrome_config.exists():
            chrome_config.unlink()
        sys.exit(1)
    finally:
        # Restore original config env var if it existed
        if original_config:
            os.environ["PARALLAX_CONFIG"] = original_config
        elif "PARALLAX_CONFIG" in os.environ:
            del os.environ["PARALLAX_CONFIG"]

