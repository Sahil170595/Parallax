#!/usr/bin/env python3
"""
Authentication Helper for Parallax

This script helps you authenticate with websites (Linear, Notion, etc.) 
by opening a browser with persistent context. Your login session will be saved
and reused by Parallax workflows.

Usage:
    python authenticate.py linear
    python authenticate.py notion
    python authenticate.py <app-name> --user-data-dir ./browser_data
"""

import sys
import os
import argparse
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

# Fix Windows encoding issues
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONLEGACYWINDOWSSTDIO"] = "0"


async def authenticate(app_name: str, user_data_dir: str = None, start_url: str = None):
    """Open browser for manual authentication."""
    
    # Default URLs for common apps
    default_urls = {
        "linear": "https://linear.app",
        "notion": "https://notion.so",
    }
    
    if not start_url:
        start_url = default_urls.get(app_name.lower(), "https://example.com")
    
    # Default user data directory
    if not user_data_dir:
        user_data_dir = Path.home() / ".parallax" / "browser_data" / app_name
    
    user_data_path = Path(user_data_dir).expanduser().resolve()
    user_data_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n🔐 Authentication Helper for {app_name}")
    print(f"📁 User data directory: {user_data_path}")
    print(f"🌐 Starting URL: {start_url}")
    print("\n📝 Instructions:")
    print("   1. Log in to your account in the browser that opens")
    print("   2. Your session will be saved automatically")
    print("   3. Close the browser when done")
    print("   4. Parallax will reuse this session for future workflows\n")
    
    async with async_playwright() as p:
        # Chrome args to disable automation detection and security warnings
        chrome_args = [
            "--disable-blink-features=AutomationControlled",  # Remove automation indicators
            "--disable-dev-shm-usage",  # Overcome limited resource problems
            "--no-first-run",  # Skip first run wizards
            "--no-default-browser-check",  # Skip default browser check
            "--disable-infobars",  # Disable info bars
        ]
        
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_path),
            headless=False,
            channel="chrome" if sys.platform == "win32" else None,
            args=chrome_args,
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        
        # Remove automation indicators from page
        page = browser.pages[0] if browser.pages else await browser.new_page()
        
        # Remove webdriver property
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Remove automation indicators
            window.chrome = {
                runtime: {}
            };
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        
        await page.goto(start_url)
        
        print("✅ Browser opened! Please log in...")
        print("   (Press Ctrl+C to close when finished)\n")
        
        try:
            # Keep browser open until user closes it
            await page.wait_for_timeout(3600000)  # 1 hour timeout
        except KeyboardInterrupt:
            print("\n\n✅ Authentication session saved!")
            print(f"   Your login will be reused from: {user_data_path}\n")
        finally:
            await browser.close()


def main():
    parser = argparse.ArgumentParser(
        description="Authenticate with websites for Parallax workflows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python authenticate.py linear
  python authenticate.py notion
  python authenticate.py custom --start-url https://example.com --user-data-dir ./my_browser_data
        """
    )
    parser.add_argument(
        "app_name",
        help="Name of the app (e.g., 'linear', 'notion')"
    )
    parser.add_argument(
        "--user-data-dir",
        help="Path to browser user data directory (default: ~/.parallax/browser_data/<app_name>)"
    )
    parser.add_argument(
        "--start-url",
        help="URL to open (default: based on app_name)"
    )
    
    args = parser.parse_args()
    
    try:
        asyncio.run(authenticate(
            app_name=args.app_name,
            user_data_dir=args.user_data_dir,
            start_url=args.start_url
        ))
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

