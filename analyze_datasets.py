#!/usr/bin/env python3
"""Analyze captured workflow states to verify execution"""

import json
from pathlib import Path

def analyze_dataset(dataset_path):
    """Analyze a dataset to verify execution"""
    dataset_path = Path(dataset_path)
    steps_file = dataset_path / "steps.jsonl"
    
    if not steps_file.exists():
        print(f"❌ Steps file not found: {steps_file}")
        return
    
    print(f"\n{'='*80}")
    print(f"Analyzing: {dataset_path.name}")
    print(f"{'='*80}\n")
    
    states = []
    with steps_file.open('r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                states.append(json.loads(line))
    
    print(f"Total States Captured: {len(states)}\n")
    
    # Analyze URLs
    urls = [s.get('url', 'N/A') for s in states]
    unique_urls = set(urls)
    
    print(f"Unique URLs: {len(unique_urls)}")
    print(f"URL Changes: {len(unique_urls) - 1}\n")
    
    print("State Progression:")
    print("-" * 80)
    for i, state in enumerate(states):
        url = state.get('url', 'N/A')
        action = state.get('action', 'N/A')
        description = state.get('description', 'N/A')[:50]
        
        # Check if URL changed from previous
        prev_url = states[i-1].get('url', '') if i > 0 else ''
        url_changed = "🔄" if url != prev_url and i > 0 else "  "
        
        print(f"{i:2d}. {url_changed} URL: {url[:70]}")
        print(f"    Action: {action}")
        print(f"    Description: {description}")
        print()
    
    # Check for actual navigation
    url_transitions = []
    for i in range(1, len(states)):
        prev_url = states[i-1].get('url', '')
        curr_url = states[i].get('url', '')
        if prev_url != curr_url:
            url_transitions.append((i-1, prev_url, i, curr_url))
    
    print(f"\nURL Transitions: {len(url_transitions)}")
    if url_transitions:
        print("-" * 80)
        for prev_idx, prev_url, curr_idx, curr_url in url_transitions[:10]:
            print(f"State {prev_idx} → {curr_idx}:")
            print(f"  {prev_url[:60]}")
            print(f"  → {curr_url[:60]}")
            print()
    
    # Check screenshots
    screenshot_dir = dataset_path
    screenshots = list(screenshot_dir.glob("*_full.png"))
    print(f"\nScreenshots Found: {len(screenshots)}")
    
    # Verify screenshots exist for each state
    missing_screenshots = []
    for i, state in enumerate(states):
        screenshot_file = screenshot_dir / f"{i:02d}_full.png"
        if not screenshot_file.exists():
            missing_screenshots.append(i)
    
    if missing_screenshots:
        print(f"⚠️  Missing screenshots for states: {missing_screenshots}")
    else:
        print("✅ All screenshots present")
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY:")
    print(f"  States: {len(states)}")
    print(f"  Unique URLs: {len(unique_urls)}")
    print(f"  URL Transitions: {len(url_transitions)}")
    print(f"  Screenshots: {len(screenshots)}")
    
    if len(url_transitions) > 0:
        print("  ✅ VERIFIED: Actual navigation occurred")
    elif len(unique_urls) > 1:
        print("  ✅ VERIFIED: Multiple URLs captured")
    else:
        print("  ⚠️  WARNING: No URL changes detected - may be same page")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    # Analyze Linear dataset
    linear_path = Path("datasets/linear/explore-linear-s-website-and-navigate-through-the-main-pages")
    if linear_path.exists():
        analyze_dataset(linear_path)
    
    # Analyze Notion dataset
    notion_path = Path("datasets/notion/explore-notion-s-website-and-navigate-through-the-main-pages")
    if notion_path.exists():
        analyze_dataset(notion_path)




