# Frequently Asked Questions

## General

### What is Parallax?

Parallax is an autonomous multi-agent system that captures web workflows. It converts natural language tasks into execution plans, executes them in a live browser, captures UI states (including non-URL states like modals and toasts), and produces structured datasets.

### How does Parallax work?

Parallax uses four agents:
1. **Interpreter** - Converts natural language → execution plans
2. **Navigator** - Executes plans in live browser
3. **Observer** - Captures UI states and screenshots
4. **Archivist** - Organizes data into datasets

### What makes Parallax different?

Parallax detects **non-URL state changes** (modals, toasts, forms, async transitions) that other systems miss. It also includes a **constitution system** for quality gates and **vision-based enhancements** for better completion detection.

---

## Installation

**New to Parallax?** See the [Quick Start Guide](QUICKSTART.md) for step-by-step installation instructions.

### What Python version do I need?

Python 3.11 or higher is required.

### How do I install Parallax?

```bash
pip install -e .
python -m playwright install --with-deps
```

See the [Quick Start Guide](QUICKSTART.md) for detailed instructions.

### Do I need API keys?

Yes, at least one API key is required for LLM planning:
- `OPENAI_API_KEY` for OpenAI
- `ANTHROPIC_API_KEY` for Anthropic

Vision features require one of these API keys as well.

See the [Quick Start Guide](QUICKSTART.md) for API key setup.

---

## Usage

**New to Parallax?** See the [Quick Start Guide](QUICKSTART.md) for examples and common workflows.

### How do I run a workflow?

```bash
python -m parallax.runner.cli run "YOUR TASK HERE" --app-name APP_NAME --start-url START_URL
```

See the [Quick Start Guide](QUICKSTART.md) for more examples and the [Usage Guide](USAGE.md) for detailed instructions.

### What are good task descriptions?

Be specific and clear:
- ✅ "Create a project in Linear"
- ✅ "Filter issues by status in Linear"
- ❌ "Do something"
- ❌ "Click stuff"

### How do I view the results?

Open `report.html` in your browser to see:
- Timeline of captured states
- Screenshots for each state
- Metadata (modals, toasts, forms)

---

## Configuration

### Where is the configuration file?

`configs/config.yaml`

### How do I change the LLM provider?

Edit `configs/config.yaml`:
```yaml
llm:
  provider: openai  # or anthropic | local | auto
```

### How do I enable vision features?

Edit `configs/config.yaml`:
```yaml
vision:
  enabled: true
  provider: openai
```

And set the appropriate API key:
```bash
export OPENAI_API_KEY=sk-proj-...
```

---

## Troubleshooting

### "OPENAI_API_KEY is required"

**Solution:** Set `OPENAI_API_KEY` in `.env` file or environment variables.

```bash
export OPENAI_API_KEY=sk-proj-...
```

### "Plan generation failed"

**Solution:** 
- Check LLM provider configuration in `configs/config.yaml`
- Ensure API key is valid
- Check API key has sufficient credits

### "Element not found"

**Solution:**
- Check if element exists on page
- Try using semantic selectors (role + name) instead of CSS
- Enable vision features for visual fallback
- Increase `default_wait_ms` for slow-loading sites

### "Action budget exceeded"

**Solution:** Increase `action_budget` in `configs/config.yaml`:

```yaml
navigation:
  action_budget: 50  # Increase from default 30
```

### "Authentication redirect detected"

**Solution:** The workflow detected an authentication redirect. You may need to:
- Log in manually before running workflow
- Use authenticated browser context
- Handle authentication in custom code

### "Constitution violation"

**Solution:** Check failure store for details:

```bash
python -m parallax.core.constitution_cli stats
python -m parallax.core.constitution_cli list --agent A2_Navigator
```

---

## Features

### What are non-URL states?

UI state changes that don't involve URL changes:
- **Modals/Dialogs** - Popup dialogs
- **Toasts** - Notification messages
- **Forms** - Form state changes
- **Async Loads** - Loading states
- **Role-Tree Changes** - Structural changes

### How does vision-based completion detection work?

Vision LLMs analyze screenshots to determine if the workflow is complete. They look for:
- Success indicators (e.g., "Success" messages)
- Completion states (e.g., form submitted, confirmation shown)
- Task-specific completion criteria

### What is the constitution system?

Quality gates that ensure reliable outputs:
- **Per-Agent Validation** - Each agent must pass validation
- **Failure Tracking** - Structured failure storage for analysis
- **Continuous Improvement** - Data-driven enhancement

---

## Performance

### How fast is Parallax?

Simple workflows typically complete in < 30 seconds. Complex workflows may take 1-2 minutes.

### How can I make it faster?

- Increase `action_budget` (if needed)
- Decrease `default_wait_ms` (may cause failures)
- Enable `headless: true`
- Use faster LLM models

### How can I make it more reliable?

- Increase `self_heal_attempts`
- Increase `loader_timeout_ms` for slow sites
- Enable vision features for better completion detection
- Use semantic selectors (role + name)

---

## Outputs

### What outputs does Parallax generate?

Each workflow creates:
- `steps.jsonl` - JSONL format with all states
- `dataset.db` - SQLite database
- `report.html` - HTML report with timeline
- `report.md` - Markdown report
- `trace.zip` - Playwright trace for replay
- `XX_full.png`, `XX_mobile.png`, `XX_tablet.png` - Screenshots

### How do I query the SQLite database?

```python
import sqlite3

conn = sqlite3.connect("datasets/linear/create-project/dataset.db")
cursor = conn.cursor()

# Get all states
cursor.execute("SELECT * FROM states")
states = cursor.fetchall()

# Get screenshots for a state
cursor.execute("SELECT * FROM screenshots WHERE state_id = ?", ("state_abc12345",))
screenshots = cursor.fetchall()
```

### How do I read the JSONL file?

```python
import json

with open("datasets/linear/create-project/steps.jsonl", "r") as f:
    for line in f:
        state = json.loads(line)
        print(f"State: {state['description']}, URL: {state['url']}")
```

---

## Development

### How do I contribute?

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

### How do I run tests?

```bash
# Unit tests
pytest -q

# E2E tests
npx playwright test
```

### How do I add a new LLM provider?

1. Create provider class in `parallax/llm/`
2. Implement `generate_plan()` method
3. Add to `_planner_from_config()` in `parallax/runner/cli.py`

### How do I add a new state detector?

1. Add detection logic to `parallax/observer/detectors.py`
2. Call from `capture_state()` method
3. Add to metadata in `UIState`

---

## Security & Privacy

### Does Parallax store my API keys?

No, API keys are only stored in `.env` file (which is gitignored). They are never logged or exposed.

### Does Parallax redact sensitive information?

Yes, PII redaction is enabled by default. Configure in `configs/config.yaml`:

```yaml
capture:
  redact:
    enabled: true
    selectors:
      - input[type="password"]
      - input[type="email"]
      - [data-sensitive="true"]
```

### What data does Parallax capture?

Parallax captures:
- Screenshots of UI states
- URLs and page structure
- ARIA role trees
- Form states
- Metadata (modals, toasts, etc.)

No user credentials or sensitive data (if redaction is enabled).

---

## Limitations

### What are Parallax's limitations?

1. **Authentication:** Requires manual login or authenticated context
2. **Complex Workflows:** May struggle with very complex multi-step workflows
3. **Dynamic Content:** May miss rapidly changing content
4. **Vision Features:** Requires API keys and may increase costs

### What browsers are supported?

- Chromium (default)
- Firefox
- WebKit

### What websites work best?

Websites with:
- Good ARIA support
- Semantic HTML
- Stable selectors
- Clear UI patterns

---

## Support

### Where can I get help?

- **GitHub Issues:** For bugs and feature requests
- **GitHub Discussions:** For questions and discussions
- **Documentation:** See [docs/](.) for detailed guides

### How do I report a bug?

Create a GitHub issue with:
- Description of the bug
- Steps to reproduce
- Expected vs actual behavior
- Environment details (Python version, OS, etc.)
- Relevant logs

---

## See Also

- [Usage Guide](USAGE.md) - Detailed usage instructions
- [Configuration Reference](CONFIGURATION.md) - Complete configuration options
- [Architecture](ARCHITECTURE.md) - System architecture
- [API Reference](API.md) - Complete API reference

