# Authentication Guide for Parallax

Parallax now supports authentication using persistent browser contexts. This allows you to log in once and reuse your session across multiple workflow runs.

## Quick Start

### Step 1: Authenticate

Run the authentication helper script:

```bash
# For Linear
python authenticate.py linear

# For Notion
python authenticate.py notion

# Custom app
python authenticate.py myapp --start-url https://example.com
```

This will:
1. Open a Chrome browser
2. Navigate to the app's login page
3. Let you log in manually
4. Save your session to `~/.parallax/browser_data/<app_name>`

### Step 2: Configure Parallax

Edit `configs/config.yaml` and uncomment/add the `user_data_dir` option:

```yaml
playwright:
  headless: true
  project: chromium
  channel: chrome
  user_data_dir: ~/.parallax/browser_data/linear  # Path to your saved session
```

Or set it per-test by updating the test files:

```python
config["playwright"]["user_data_dir"] = str(Path.home() / ".parallax" / "browser_data" / "linear")
```

### Step 3: Run Your Workflows

Now your workflows will use the authenticated session:

```bash
python demos/test_scenario_03_linear_create_chrome.py
python demos/test_scenario_04_notion_create_chrome.py
```

## How It Works

- **Persistent Context**: Playwright's persistent browser context saves cookies, localStorage, and session data
- **Reusable Sessions**: Once authenticated, your session persists across workflow runs
- **Secure**: Sessions are stored locally in your user data directory

## Custom User Data Directory

You can specify a custom location:

```bash
python authenticate.py linear --user-data-dir ./my_browser_data/linear
```

Then update your config:

```yaml
playwright:
  user_data_dir: ./my_browser_data/linear
```

## Multiple Apps

Each app can have its own authentication session:

```bash
python authenticate.py linear    # Saves to ~/.parallax/browser_data/linear
python authenticate.py notion    # Saves to ~/.parallax/browser_data/notion
```

## Troubleshooting

**Browser shows "not secure" or automation warnings?** 
The authentication script now includes flags to disable automation detection. If you still see warnings:
- Make sure you're using the latest version of the authenticate script
- Try deleting the user data directory and re-authenticating:
  ```bash
  rm -rf ~/.parallax/browser_data/linear
  python authenticate.py linear
  ```

**Session expired?** Re-run the authentication script:
```bash
python authenticate.py linear
```

**Want to start fresh?** Delete the user data directory:
```bash
rm -rf ~/.parallax/browser_data/linear
```

**Using Windows?** The authentication script automatically uses Chrome if available.

**Authentication still not working?**
- The browser now removes automation indicators (`navigator.webdriver` is hidden)
- Chrome security warnings are disabled
- A realistic user agent is set
- If sites still detect automation, they may have advanced detection - try authenticating manually in a regular Chrome window first, then copy cookies (advanced)

## Example: Full Workflow

```bash
# 1. Authenticate with Linear
python authenticate.py linear

# 2. Update config.yaml to include:
#    user_data_dir: ~/.parallax/browser_data/linear

# 3. Run your workflow
python demos/test_scenario_03_linear_create_chrome.py
```

Your workflow will now run authenticated! 🎉

