#!/usr/bin/env python3
"""Test script to run all usage scenarios from documentation - runs sequentially with progress."""

import subprocess
import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

# Fix Windows encoding issues
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONLEGACYWINDOWSSTDIO"] = "0"
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

# Define all usage scenarios from documentation
USAGE_SCENARIOS = [
    {
        "name": "Navigate to example.com",
        "task": "Navigate to example.com and show the page",
        "app_name": "demo",
        "start_url": "https://example.com",
    },
    {
        "name": "Wikipedia search",
        "task": "Search for Python programming language",
        "app_name": "wikipedia",
        "start_url": "https://wikipedia.org",
    },
    {
        "name": "Linear create project",
        "task": "Create a project in Linear",
        "app_name": "linear",
        "start_url": "https://linear.app",
    },
    {
        "name": "Notion create page",
        "task": "Create a new page in Notion",
        "app_name": "notion",
        "start_url": "https://notion.so",
    },
    {
        "name": "Linear filter issues",
        "task": "Filter issues by status",
        "app_name": "linear",
        "start_url": "https://linear.app",
    },
]


def run_scenario(scenario: Dict[str, str], scenario_num: int, total: int) -> Tuple[bool, str]:
    """Run a single scenario and return success status and output."""
    print(f"\n{'='*80}")
    print(f"[{scenario_num}/{total}] Running: {scenario['name']}")
    print(f"Task: {scenario['task']}")
    print(f"App: {scenario['app_name']} | URL: {scenario['start_url']}")
    print(f"{'='*80}\n")
    
    cmd = [
        sys.executable,
        "-m",
        "parallax.runner.cli",
        scenario["task"],
        "--app-name",
        scenario["app_name"],
        "--start-url",
        scenario["start_url"],
    ]
    
    # Set environment for subprocess
    env = os.environ.copy()
    if sys.platform == "win32":
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONLEGACYWINDOWSSTDIO"] = "0"
    
    try:
        # Run with real-time output for first scenario, capture for others
        if scenario_num == 1:
            # First scenario: show output
            result = subprocess.run(
                cmd,
                timeout=300,  # 5 minute timeout per scenario
                env=env,
            )
            return result.returncode == 0, ""
        else:
            # Other scenarios: capture output
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,  # 5 minute timeout per scenario
                env=env,
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                error_output = result.stderr or result.stdout
                return False, error_output
    except subprocess.TimeoutExpired:
        return False, "Timeout after 5 minutes"
    except Exception as e:
        return False, str(e)


def main():
    """Run all usage scenarios and report results."""
    print("\n" + "="*80)
    print("PARALLAX USAGE SCENARIOS TEST")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    print(f"\nTotal scenarios: {len(USAGE_SCENARIOS)}")
    print("Note: Some scenarios may require API keys or authentication")
    print("="*80)
    
    results: List[Tuple[str, bool, str]] = []
    
    for idx, scenario in enumerate(USAGE_SCENARIOS, 1):
        success, output = run_scenario(scenario, idx, len(USAGE_SCENARIOS))
        results.append((scenario["name"], success, output))
        
        # Print immediate result
        status = "[PASS]" if success else "[FAIL]"
        print(f"\n{status}: {scenario['name']}")
        if not success and output:
            # Print last 10 lines of error output
            lines = output.split('\n')
            error_lines = lines[-10:] if len(lines) > 10 else lines
            print("  Error output:")
            for line in error_lines:
                if line.strip():
                    print(f"    {line}")
    
    # Print final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for name, success, output in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status}: {name}")
    
    print("\n" + "="*80)
    print(f"Results: {passed}/{total} scenarios passed")
    print("="*80)
    
    # Exit with error code if any failed
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
