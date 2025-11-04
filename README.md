# Parallax

Autonomous multi-agent system that perceives, navigates, and captures complex web workflows — even when no URLs change.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

## Overview

Parallax executes natural-language web tasks end-to-end using Playwright and a provider-agnostic LLM planner. It detects non-URL state changes (dialogs, toasts, async transitions), captures screenshots and role-tree snapshots, and produces a replayable dataset and human-readable report.

**Key Features:**
- 🤖 **Multi-Agent System:** Four agents (Interpreter, Navigator, Observer, Archivist) work together
- 🎯 **Non-URL State Detection:** Captures modals, toasts, forms, and async transitions
- 📸 **Multi-Viewport Capture:** Desktop, tablet, and mobile screenshots
- 🧠 **Vision-Based Enhancements:** Optional vision LLM support for completion detection and element location
- 🏛️ **Constitution System:** Quality gates ensure reliable outputs
- 📊 **Rich Outputs:** JSONL, SQLite, HTML reports with timeline

## Quickstart

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

Create a `.env` file:

```bash
# OpenAI (for LLM planning and vision)
OPENAI_API_KEY=sk-proj-...

# Anthropic (alternative LLM provider)
ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Run Your First Workflow

```bash
python -m parallax.runner.cli run "Navigate to example.com and show the page"
```

Output will be saved to `datasets/demo/navigate-to-example-com-and-show-the-page/`.

## Usage

### Basic Usage

```bash
python -m parallax.runner.cli run "YOUR TASK HERE" --app-name APP_NAME --start-url START_URL
```

**Examples:**

```bash
# Linear workflows
python -m parallax.runner.cli run "Create a project in Linear" --app-name linear --start-url https://linear.app

# Notion workflows
python -m parallax.runner.cli run "Create a new page in Notion" --app-name notion --start-url https://notion.so

# Wikipedia workflows
python -m parallax.runner.cli run "Search for Python programming language" --app-name wikipedia --start-url https://wikipedia.org
```

### Configuration

Edit `configs/config.yaml` to customize:

- **LLM Provider:** `openai`, `anthropic`, `local`, or `auto`
- **Navigation:** Action budget, wait times, retry attempts
- **Observer:** Detection thresholds, viewport settings
- **Vision:** Enable/disable vision features

See [Configuration Guide](docs/USAGE.md#configuration) for details.

## Outputs

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
        └── XX_full.png      # Screenshots by step
```

### Viewing Reports

Open `report.html` in your browser to see:
- Timeline of captured states
- Screenshots for each state
- Metadata (modals, toasts, forms)
- Action descriptions

## Architecture

Parallax uses a four-agent architecture:

1. **Agent A1: Interpreter** - Converts natural language → execution plans
2. **Agent A2: Navigator** - Executes plans in live browser
3. **Agent A3: Observer** - Captures UI states and screenshots
4. **Agent A4: Archivist** - Organizes data into datasets

See [Architecture Documentation](docs/ARCHITECTURE.md) for details.

## Documentation

- **[API Documentation](docs/API.md)** - Complete API reference
- **[Usage Guide](docs/USAGE.md)** - Detailed usage instructions
- **[Architecture](docs/ARCHITECTURE.md)** - System design and architecture
- **[Configuration Reference](docs/CONFIGURATION.md)** - Complete configuration options
- **[FAQ](docs/FAQ.md)** - Frequently asked questions
- **[Contributing](CONTRIBUTING.md)** - Guidelines for contributing

## Development

### Setup

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest -q

# Run e2e tests
npx playwright test
```

### Code Quality

```bash
# Format code
black parallax/

# Lint code
ruff check parallax/

# Type check
mypy parallax/
```

## Features

### Non-URL State Detection

Parallax detects UI state changes without relying on URL changes:

- ✅ **Modals/Dialogs:** Detects `role="dialog"` elements
- ✅ **Toasts:** Detects `role="status"` and `role="alert"` elements
- ✅ **Forms:** Tracks `:invalid` → `:valid` transitions
- ✅ **Role-Tree Diff:** Computes Jaccard similarity for structural changes
- ✅ **Async Loads:** Detects loading states and spinners

### Vision-Based Enhancements

Optional vision LLM support for:

- **Completion Detection:** Early termination when workflow is complete
- **State Significance:** Categorizes states as critical/supporting/optional
- **Element Location:** Visual fallback when selectors fail

### Constitution System

Quality gates ensure reliable outputs:

- **Per-Agent Validation:** Each agent must pass validation
- **Failure Tracking:** Structured failure storage for analysis
- **Continuous Improvement:** Data-driven enhancement

## Examples

### Example 1: Simple Navigation

```bash
python -m parallax.runner.cli run "Navigate to example.com and show the page" --app-name demo --start-url https://example.com
```

### Example 2: Form Submission

```bash
python -m parallax.runner.cli run "Search for Python programming language on Wikipedia" --app-name wikipedia --start-url https://wikipedia.org
```

### Example 3: Programmatic Usage

```python
from parallax.agents.interpreter import Interpreter
from parallax.agents.navigator import Navigator
from parallax.agents.observer import Observer
from parallax.agents.archivist import Archivist
from parallax.llm.openai_provider import OpenAIPlanner
from playwright.async_api import async_playwright

# Initialize agents and run workflow
# See docs/USAGE.md for complete example
```

## License

Apache-2.0 License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Support

- **Issues:** [GitHub Issues](https://github.com/YOUR_USERNAME/Parallax/issues)
- **Documentation:** [docs/](docs/)
- **Questions:** [GitHub Discussions](https://github.com/YOUR_USERNAME/Parallax/discussions)

