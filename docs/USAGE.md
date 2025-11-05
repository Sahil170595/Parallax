# Usage Guide

## Quick Start

### 1. Installation

```bash
# Install Python 3.11+
python --version  # Should be 3.11+

# Install dependencies
pip install -e .

# Install Playwright browsers
python -m playwright install --with-deps
```

### 2. Configuration

Create a `.env` file in the project root:

```bash
# OpenAI (for LLM planning and vision)
OPENAI_API_KEY=sk-proj-...

# Anthropic (alternative LLM provider)
ANTHROPIC_API_KEY=sk-ant-...

# Optional: Vision features
# Set OPENAI_API_KEY or ANTHROPIC_API_KEY for vision features
```

### 3. Run Your First Workflow

```bash
python -m parallax.runner.cli run "Navigate to example.com and show the page"
```

Output will be saved to `datasets/demo/navigate-to-example-com-and-show-the-page/`.

---

## Basic Usage

### Running a Workflow

```bash
python -m parallax.runner.cli run "YOUR TASK HERE" --app-name APP_NAME --start-url START_URL
```

**Arguments:**
- `task` - Natural language task description (required)
- `--app-name` - Application name for organizing datasets (default: "linear")
- `--start-url` - Starting URL for the workflow (default: "https://linear.app")

**Examples:**

```bash
# Linear workflows
python -m parallax.runner.cli run "Create a project in Linear" --app-name linear --start-url https://linear.app
python -m parallax.runner.cli run "Filter issues by status" --app-name linear --start-url https://linear.app

# Notion workflows
python -m parallax.runner.cli run "Create a new page in Notion" --app-name notion --start-url https://notion.so

# Wikipedia workflows
python -m parallax.runner.cli run "Search for Python programming language" --app-name wikipedia --start-url https://wikipedia.org
```

---

## Configuration

### Config File

Edit `configs/config.yaml` to customize behavior:

```yaml
# LLM Provider
llm:
  provider: openai  # openai | anthropic | local | auto
  model: gpt-4.1-mini

# Navigation Settings
navigation:
  action_budget: 30        # Maximum actions per workflow
  default_wait_ms: 1000    # Wait time between actions (ms)
  self_heal_attempts: 1    # Retry attempts on failure

# Observer Settings
observer:
  role_diff_threshold: 0.2  # Role-tree similarity threshold
  capture_viewports:
    - full
    - mobile
    - tablet

# Vision Features (Optional)
vision:
  enabled: false  # Enable vision-based enhancements
  provider: openai  # openai | anthropic

# Output Settings
output:
  base_dir: datasets  # Base directory for datasets
```

---

## Understanding Outputs

### Dataset Structure

Each workflow creates a dataset directory:

```
datasets/
└── linear/
    └── create-project-in-linear/
        ├── steps.jsonl      # JSONL format with all states
        ├── dataset.db       # SQLite database
        ├── report.html      # HTML report with timeline
        ├── report.md        # Markdown report
        ├── trace.zip        # Playwright trace for replay
        ├── 00_full.png     # Screenshots by step
        ├── 00_mobile.png
        ├── 00_tablet.png
        ├── 01_full.png
        └── ...
```

### JSONL Format

`steps.jsonl` contains one JSON object per line:

```json
{"id": "state_abc12345", "url": "https://linear.app", "description": "Project list page", "has_modal": false, "action": "navigate(https://linear.app)", "screenshots": {"full": "00_full.png", "mobile": "00_mobile.png", "tablet": "00_tablet.png"}, "metadata": {"roles": [...], "has_toast": false, "form_validity": null, "role_diff": 0.0}, "state_signature": "abc12345..."}
```

### SQLite Database

Query the database:

```python
import sqlite3

conn = sqlite3.connect("datasets/linear/create-project-in-linear/dataset.db")
cursor = conn.cursor()

# Get all states
cursor.execute("SELECT * FROM states")
states = cursor.fetchall()

# Get screenshots for a state
cursor.execute("SELECT * FROM screenshots WHERE state_id = ?", ("state_abc12345",))
screenshots = cursor.fetchall()
```

### HTML Report

Open `report.html` in a browser to view:
- Timeline of states
- Screenshots for each state
- Metadata (modals, toasts, forms)
- Action descriptions

---

## Advanced Usage

### Using Vision Features

Enable vision features in `configs/config.yaml`:

```yaml
vision:
  enabled: true
  provider: openai  # or anthropic
```

Vision features provide:
- **Completion Detection:** Early termination when workflow is complete
- **State Significance:** Categorizes states as critical/supporting/optional
- **Element Location:** Visual fallback when selectors fail

**Note:** Requires API key for vision provider (OpenAI or Anthropic).

### Programmatic Usage

```python
import asyncio
from pathlib import Path
from parallax.agents.interpreter import Interpreter
from parallax.agents.navigator import Navigator
from parallax.agents.observer import Observer
from parallax.agents.archivist import Archivist
from parallax.llm.openai_provider import OpenAIPlanner
from parallax.observer.detectors import Detectors
from parallax.core.constitution import FailureStore
from playwright.async_api import async_playwright

async def run_workflow(task: str, start_url: str):
    # Initialize planner and interpreter
    planner = OpenAIPlanner()
    failure_store = FailureStore(Path("datasets/_constitution_failures"))
    interpreter = Interpreter(planner, failure_store=failure_store)
    
    # Generate plan
    plan = await interpreter.plan(task, {"start_url": start_url})
    print(f"Generated {len(plan.steps)} steps")
    
    # Setup browser
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # Initialize detectors and observer
        detectors = Detectors({})
        observer = Observer(
            page,
            detectors,
            save_dir=Path("output"),
            failure_store=failure_store
        )
        
        # Initialize navigator
        navigator = Navigator(
            page,
            observer=observer,
            default_wait_ms=1000,
            scroll_margin_px=64,
            failure_store=failure_store
        )
        
        # Execute plan
        await navigator.execute(plan, action_budget=30)
        
        # Save dataset
        archivist = Archivist(Path("datasets"), failure_store=failure_store)
        dataset_path = archivist.write_states(
            app="linear",
            task_slug="create-project",
            states=observer.states
        )
        
        print(f"Dataset saved to: {dataset_path}")
        
        await browser.close()

# Run workflow
asyncio.run(run_workflow("Create a project in Linear", "https://linear.app"))
```

---

## Troubleshooting

### Common Issues

#### 1. "OPENAI_API_KEY is required"

**Solution:** Set `OPENAI_API_KEY` in `.env` file or environment variables.

```bash
export OPENAI_API_KEY=sk-proj-...
```

#### 2. "Plan generation failed"

**Solution:** Check LLM provider configuration in `configs/config.yaml`. Ensure API key is valid.

#### 3. "Element not found"

**Solution:** 
- Check if element exists on page
- Try using semantic selectors (role + name) instead of CSS
- Enable vision features for visual fallback

#### 4. "Action budget exceeded"

**Solution:** Increase `action_budget` in `configs/config.yaml`:

```yaml
navigation:
  action_budget: 50  # Increase from default 30
```

#### 5. "Constitution violation"

**Solution:** Check failure store for details:

```bash
python -m parallax.core.constitution_cli stats
python -m parallax.core.constitution_cli list --agent A2_Navigator
```

#### 6. "Authentication redirect detected"

**Solution:** The workflow detected an authentication redirect. You may need to:
- Log in manually before running workflow
- Use authenticated browser context
- Handle authentication in custom code

---

## Best Practices

### 1. Task Descriptions

Be specific and clear:

✅ **Good:**
- "Create a project in Linear"
- "Filter issues by status in Linear"
- "Search for Python programming language on Wikipedia"

❌ **Bad:**
- "Do something"
- "Click stuff"
- "Navigate"

### 2. Starting URLs

Use specific starting URLs:

✅ **Good:**
- `https://linear.app`
- `https://notion.so`
- `https://wikipedia.org`

❌ **Bad:**
- `https://example.com` (unless testing)
- Generic URLs without context

### 3. Action Budget

Set appropriate action budgets:

- **Simple tasks:** 10-20 actions
- **Medium tasks:** 20-30 actions
- **Complex tasks:** 30-50 actions

### 4. Wait Times

Adjust wait times for slow sites:

```yaml
navigation:
  default_wait_ms: 2000  # Increase for slow sites
```

### 5. Vision Features

Enable vision features for:
- Complex workflows with many steps
- Sites with dynamic content
- When selectors frequently fail

**Note:** Vision features require API keys and may increase costs.

---

## CLI Reference

### `run` Command

```bash
python -m parallax.runner.cli run TASK [OPTIONS]
```

**Options:**
- `--app-name TEXT` - Application name (default: "linear")
- `--start-url TEXT` - Starting URL (default: "https://linear.app")

**Examples:**

```bash
# Basic usage
python -m parallax.runner.cli run "Create a project in Linear"

# Custom app and URL
python -m parallax.runner.cli run "Create a page in Notion" --app-name notion --start-url https://notion.so
```

### `constitution` Command

```bash
# View failure statistics
python -m parallax.core.constitution_cli stats

# List failures
python -m parallax.core.constitution_cli list [OPTIONS]
```

**Options:**
- `--agent TEXT` - Filter by agent (e.g., "A1_Interpreter")
- `--level TEXT` - Filter by level (e.g., "critical", "warning")

**Examples:**

```bash
# View all failures
python -m parallax.core.constitution_cli list

# View failures for Navigator
python -m parallax.core.constitution_cli list --agent A2_Navigator

# View critical failures
python -m parallax.core.constitution_cli list --level critical
```

---

## Examples

### Example 1: Simple Navigation

```bash
python -m parallax.runner.cli run "Navigate to example.com and show the page" --app-name demo --start-url https://example.com
```

### Example 2: Form Submission

```bash
python -m parallax.runner.cli run "Search for Python programming language on Wikipedia" --app-name wikipedia --start-url https://wikipedia.org
```

### Example 3: Complex Workflow (with vision)

1. Enable vision in `configs/config.yaml`
2. Set `OPENAI_API_KEY` in `.env`
3. Run workflow:

```bash
python -m parallax.runner.cli run "Create a project in Linear" --app-name linear --start-url https://linear.app
```

---

## Next Steps

- Read [API Documentation](API.md) for programmatic usage
- Read [Architecture Documentation](ARCHITECTURE.md) for system design
- Check [Contributing Guidelines](../CONTRIBUTING.md) to contribute

