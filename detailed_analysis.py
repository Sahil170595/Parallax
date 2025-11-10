#!/usr/bin/env python3
"""Detailed analysis of workflow execution"""

import json
from pathlib import Path
from PIL import Image

def detailed_analysis(dataset_path):
    """Detailed analysis with screenshot verification"""
    dataset_path = Path(dataset_path)
    steps_file = dataset_path / "steps.jsonl"
    
    print(f"\n{'='*80}")
    print(f"DETAILED ANALYSIS: {dataset_path.name}")
    print(f"{'='*80}\n")
    
    states = []
    with steps_file.open('r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                states.append(json.loads(line))
    
    print("Step-by-Step Execution Analysis:\n")
    
    for i, state in enumerate(states):
        url = state.get('url', 'N/A')
        action = state.get('action', 'N/A')
        description = state.get('description', 'N/A')
        metadata = state.get('metadata', {})
        
        # Check screenshot
        screenshot_file = dataset_path / f"{i:02d}_full.png"
        screenshot_exists = screenshot_file.exists()
        screenshot_size = "N/A"
        if screenshot_exists:
            try:
                img = Image.open(screenshot_file)
                screenshot_size = f"{img.size[0]}x{img.size[1]}"
            except:
                screenshot_size = "Error reading"
        
        # Check for state changes
        has_modal = metadata.get('has_modal', False)
        has_toast = 'toast' in description.lower() or metadata.get('has_toast', False)
        structure_changed = 'Structure changed' in description
        
        print(f"State {i:2d}:")
        print(f"  Action: {action}")
        print(f"  URL: {url}")
        print(f"  Screenshot: {'✅' if screenshot_exists else '❌'} {screenshot_size}")
        print(f"  Changes: {'Modal' if has_modal else ''} {'Toast' if has_toast else ''} {'Structure' if structure_changed else ''}")
        print(f"  Description: {description[:80]}")
        
        # Show URL change if occurred
        if i > 0:
            prev_url = states[i-1].get('url', '')
            if url != prev_url:
                print(f"  🔄 NAVIGATED: {prev_url[:50]} → {url[:50]}")
        print()
    
    # Verify screenshot quality
    print("\nScreenshot Quality Check:")
    print("-" * 80)
    valid_screenshots = 0
    invalid_screenshots = []
    
    for i in range(len(states)):
        screenshot_file = dataset_path / f"{i:02d}_full.png"
        if screenshot_file.exists():
            try:
                img = Image.open(screenshot_file)
                if img.size[0] > 100 and img.size[1] > 100:
                    valid_screenshots += 1
                else:
                    invalid_screenshots.append((i, f"Too small: {img.size}"))
            except Exception as e:
                invalid_screenshots.append((i, f"Error: {str(e)}"))
        else:
            invalid_screenshots.append((i, "Missing"))
    
    print(f"Valid screenshots: {valid_screenshots}/{len(states)}")
    if invalid_screenshots:
        print(f"⚠️  Invalid/Missing screenshots:")
        for idx, reason in invalid_screenshots:
            print(f"  State {idx}: {reason}")
    else:
        print("✅ All screenshots are valid")
    
    # Action success rate
    print("\nAction Success Analysis:")
    print("-" * 80)
    successful_actions = 0
    failed_actions = 0
    
    for state in states:
        action = state.get('action', '')
        if '[FAILED]' in action:
            failed_actions += 1
        elif action and not action.startswith('wait'):
            successful_actions += 1
    
    total_actions = successful_actions + failed_actions
    if total_actions > 0:
        success_rate = (successful_actions / total_actions) * 100
        print(f"Successful actions: {successful_actions}")
        print(f"Failed actions: {failed_actions}")
        print(f"Success rate: {success_rate:.1f}%")
    
    print(f"\n{'='*80}\n")

if __name__ == "__main__":
    linear_path = Path("datasets/linear/explore-linear-s-website-and-navigate-through-the-main-pages")
    if linear_path.exists():
        detailed_analysis(linear_path)
    
    notion_path = Path("datasets/notion/explore-notion-s-website-and-navigate-through-the-main-pages")
    if notion_path.exists():
        detailed_analysis(notion_path)






