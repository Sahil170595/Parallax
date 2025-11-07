# Quick Start Guide

Get up and running with Parallax in 5 minutes.

## Prerequisites

- **Python 3.11+** - Check your version: `python --version`
- **API Key** - At least one LLM provider API key (OpenAI or Anthropic)

## Installation

### Step 1: Clone and Install

```bash
# Clone the repository (if not already done)
git clone <repository-url>
cd Parallax

# Install dependencies
pip install -e .

# Install Playwright browsers
python -m playwright install --with-deps
```

### Step 2: Set Up API Keys

Create a `.env` file in the project root:

```bash
# For OpenAI (recommended for first-time users)
OPENAI_API_KEY=sk-proj-your-key-here

# OR for Anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**Note:** You only need one API key. Parallax will automatically detect and use available keys if `provider: auto` is set in `configs/config.yaml` (default).

### Step 3: Verify Installation

```bash
# Test that Parallax can be imported
python -c "from parallax.runner.cli import app; print('✅ Installation successful!')"
```

## Your First Workflow

### Basic Command

```bash
python -m parallax.runner.cli run "YOUR TASK HERE" --app-name APP_NAME --start-url START_URL
```

### Example: Simple Navigation

```bash
python -m parallax.runner.cli run "Navigate to example.com and show the page" \
  --app-name demo \
  --start-url https://example.com
```

**What happens:**
1. Parallax generates an execution plan from your task
2. Opens a browser and navigates to the start URL
3. Executes the plan step-by-step
4. Captures screenshots and UI states
5. Saves everything to `datasets/demo/navigate-to-example-com-and-show-the-page/`

### Example: Real-World Workflow

```bash
python -m parallax.runner.cli run "Search for Python programming language on Wikipedia" \
  --app-name wikipedia \
  --start-url https://wikipedia.org
```

## Viewing Results

After a workflow completes, navigate to the output directory:

```bash
cd datasets/wikipedia/search-for-python-programming-language-on-wikipedia
```

**Output files:**
- `report.html` - **Open this in your browser** for a visual timeline
- `steps.jsonl` - Machine-readable state data
- `dataset.db` - SQLite database with all states
- `report.md` - Markdown report
- `trace.zip` - Playwright trace for replay
- `*.png` - Screenshots for each state

### Quick View

```bash
# On macOS/Linux
open report.html

# On Windows
start report.html

# On Linux (alternative)
xdg-open report.html
```

## Running the Web Dashboard

For a visual interface, use the Streamlit dashboard:

```bash
# Start the dashboard
python run_dashboard.py

# Or use Streamlit directly
streamlit run streamlit_dashboard.py
```

Then open `http://localhost:8501` in your browser.

## Running the Web Server

For API access and WebSocket progress updates:

```bash
# Start the web server
python run_web.py
```

The server runs on `http://localhost:8000` with:
- **API:** `POST /api/run` - Run workflows programmatically
- **WebSocket:** `/ws` - Real-time progress updates
- **Health:** `/health` - System health check
- **UI:** `http://localhost:8000` - Web interface

## Common Workflows

### Linear Workflows

```bash
python -m parallax.runner.cli run "Create a project in Linear" \
  --app-name linear \
  --start-url https://linear.app

python -m parallax.runner.cli run "Filter issues by status" \
  --app-name linear \
  --start-url https://linear.app
```

### Notion Workflows

```bash
python -m parallax.runner.cli run "Create a new page in Notion" \
  --app-name notion \
  --start-url https://notion.so
```

### Wikipedia Workflows

```bash
python -m parallax.runner.cli run "Search for machine learning" \
  --app-name wikipedia \
  --start-url https://wikipedia.org
```

## Configuration

### Basic Configuration

Edit `configs/config.yaml` to customize behavior:

```yaml
# LLM Provider
llm:
  provider: auto  # auto-detects available API keys

# Navigation Settings
navigation:
  action_budget: 30        # Max actions per workflow
  default_wait_ms: 1000    # Wait between actions (ms)

# Capture Settings
capture:
  redact:
    enabled: true          # Redact PII in screenshots
    selectors:
      - input[type="password"]
      - input[type="email"]
```

### Common Customizations

**Increase action budget for complex workflows:**
```yaml
navigation:
  action_budget: 50  # Default is 30
```

**Enable vision features (requires API key):**
```yaml
vision:
  enabled: true
  provider: openai
```

**Run browser in visible mode:**
```yaml
playwright:
  headless: false  # Default is true
```

See [Configuration Reference](CONFIGURATION.md) for all options.

## Troubleshooting

### "OPENAI_API_KEY is required"

**Solution:** Set your API key in `.env` file:
```bash
echo "OPENAI_API_KEY=sk-proj-your-key" > .env
```

### "Plan generation failed"

**Solution:** 
- Check your API key is valid
- Verify you have credits/quota
- Check `configs/config.yaml` provider setting

### "Element not found"

**Solution:**
- Increase `action_budget` in config
- Enable vision features for better element detection
- Check that the element exists on the page

### "Action budget exceeded"

**Solution:** Increase the action budget:
```yaml
navigation:
  action_budget: 50  # Increase from 30
```

### Browser doesn't start

**Solution:** Reinstall Playwright browsers:
```bash
python -m playwright install --with-deps
```

## Next Steps

- **[Usage Guide](USAGE.md)** - Detailed usage instructions and examples
- **[Configuration Reference](CONFIGURATION.md)** - Complete configuration options
- **[API Documentation](API.md)** - Programmatic usage and API reference
- **[Architecture](ARCHITECTURE.md)** - System design and architecture
- **[FAQ](FAQ.md)** - Frequently asked questions

## Quick Reference

### CLI Command

```bash
python -m parallax.runner.cli run TASK [OPTIONS]

Options:
  --app-name TEXT    Application name (default: "linear")
  --start-url TEXT   Starting URL (default: "https://linear.app")
```

### Output Location

```
datasets/
└── {app-name}/
    └── {task-slug}/
        ├── report.html      # ← Open this!
        ├── steps.jsonl
        ├── dataset.db
        ├── report.md
        ├── trace.zip
        └── *.png            # Screenshots
```

### Environment Variables

```bash
# Required (at least one)
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...

# Optional
LOCAL_LLM_BASE_URL=http://localhost:11434  # For local LLM
```

## Getting Help

- **Documentation:** See `docs/` directory
- **Issues:** [GitHub Issues](https://github.com/YOUR_USERNAME/Parallax/issues)
- **Questions:** [GitHub Discussions](https://github.com/YOUR_USERNAME/Parallax/discussions)

---

**Ready to go?** Try your first workflow:

```bash
python -m parallax.runner.cli run "Navigate to example.com" \
  --app-name demo \
  --start-url https://example.com
```

