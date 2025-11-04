# Contributing to Parallax

Thank you for your interest in contributing to Parallax! This document provides guidelines and instructions for contributing.

## Getting Started

### 1. Fork and Clone

```bash
git clone https://github.com/YOUR_USERNAME/Parallax.git
cd Parallax
```

### 2. Install Dependencies

```bash
pip install -e ".[dev]"
python -m playwright install --with-deps
```

### 3. Set Up Environment

Create a `.env` file:

```bash
cp .env.example .env
# Edit .env and add your API keys
```

---

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

- Write clean, documented code
- Add docstrings to new functions/classes
- Follow existing code style
- Add tests for new features

### 3. Run Tests

```bash
# Run unit tests
pytest -q

# Run with coverage
pytest --cov=parallax --cov-report=html

# Run e2e tests
npx playwright test
```

### 4. Check Code Quality

```bash
# Format code
black parallax/

# Lint code
ruff check parallax/

# Type check
mypy parallax/
```

### 5. Commit Changes

```bash
git add .
git commit -m "feat: add new feature"
```

Follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `test:` - Tests
- `refactor:` - Code refactoring
- `style:` - Code style changes

### 6. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Create a Pull Request on GitHub.

---

## Code Style

### Python Style

- Follow PEP 8
- Use type hints
- Add docstrings to public functions/classes
- Keep functions small and focused

### Example

```python
from typing import Optional
from pathlib import Path

def process_file(file_path: Path, output_dir: Optional[Path] = None) -> Path:
    """
    Process a file and save to output directory.
    
    Args:
        file_path: Path to input file
        output_dir: Optional output directory (default: same as input)
    
    Returns:
        Path to output file
    
    Raises:
        FileNotFoundError: If input file doesn't exist
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Process file...
    output = output_dir or file_path.parent
    return output / f"processed_{file_path.name}"
```

---

## Testing

### Unit Tests

Place unit tests in `tests/unit/`:

```python
# tests/unit/test_my_feature.py
import pytest
from parallax.my_module import my_function

def test_my_function():
    result = my_function("input")
    assert result == "expected_output"
```

### Integration Tests

Place integration tests in `tests/integration/`:

```python
# tests/integration/test_my_integration.py
import pytest
from parallax.agents.interpreter import Interpreter
from parallax.llm.local_provider import LocalPlanner

@pytest.mark.asyncio
async def test_interpreter_with_local_provider():
    planner = LocalPlanner()
    interpreter = Interpreter(planner)
    plan = await interpreter.plan("Test task")
    assert len(plan.steps) > 0
```

### E2E Tests

Place e2e tests in `tests/e2e/`:

```python
# tests/e2e/test_workflow.py
from playwright.async_api import async_playwright
import pytest

@pytest.mark.asyncio
async def test_full_workflow():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        # Test workflow...
        await browser.close()
```

---

## Adding New Features

### Adding a New Agent

1. Create agent class in `parallax/agents/`:

```python
# parallax/agents/my_agent.py
from parallax.core.logging import get_logger

log = get_logger("my_agent")

class MyAgent:
    def __init__(self, ...):
        pass
    
    async def execute(self, ...):
        """Execute agent logic."""
        pass
```

2. Add constitution rules in `parallax/agents/constitutions.py`:

```python
def validate_my_agent_output(input_data, output_data, context):
    """Validate MyAgent output."""
    # Validation logic
    return True, "Validation passed", {}
```

3. Wire into CLI in `parallax/runner/cli.py`:

```python
my_agent = MyAgent(...)
await my_agent.execute(...)
```

### Adding a New LLM Provider

1. Create provider class in `parallax/llm/`:

```python
# parallax/llm/my_provider.py
from parallax.agents.interpreter import PlannerProvider
from parallax.core.schemas import ExecutionPlan

class MyPlanner(PlannerProvider):
    async def generate_plan(self, task: str, context: dict) -> ExecutionPlan:
        """Generate plan using MyProvider."""
        # Implementation
        pass
```

2. Add to `_planner_from_config()` in `parallax/runner/cli.py`:

```python
def _planner_from_config(cfg: dict):
    provider = cfg.get("llm", {}).get("provider", "openai")
    if provider == "my_provider":
        return MyPlanner()
    # ...
```

### Adding New State Detectors

1. Add detection logic to `parallax/observer/detectors.py`:

```python
async def detect_my_state(self, page):
    """Detect my custom state."""
    # Detection logic
    return detected_state
```

2. Call from `capture_state()`:

```python
async def capture_state(self, page, ...):
    # ... existing logic ...
    my_state = await self.detect_my_state(page)
    metadata["my_state"] = my_state
```

---

## Documentation

### Adding Documentation

1. **API Documentation:** Add docstrings to public functions/classes
2. **Usage Guides:** Add to `docs/USAGE.md`
3. **Architecture Docs:** Add to `docs/ARCHITECTURE.md`
4. **Examples:** Add to `docs/EXAMPLES.md` (if created)

### Docstring Format

Use Google-style docstrings:

```python
def my_function(param1: str, param2: int = 10) -> bool:
    """
    Brief description of function.
    
    Longer description explaining what the function does, its purpose,
    and any important details.
    
    Args:
        param1: Description of param1
        param2: Description of param2 (default: 10)
    
    Returns:
        Description of return value
    
    Raises:
        ValueError: When param1 is invalid
    
    Example:
        >>> result = my_function("test", 20)
        >>> print(result)
        True
    """
    pass
```

---

## Pull Request Process

### Before Submitting

1. ✅ All tests pass
2. ✅ Code is formatted (`black`)
3. ✅ Code is linted (`ruff`)
4. ✅ Type checks pass (`mypy`)
5. ✅ Documentation updated
6. ✅ No merge conflicts

### PR Description

Include:
- **What:** Description of changes
- **Why:** Reason for changes
- **How:** Implementation details
- **Testing:** How to test changes

**Example:**

```markdown
## What
Adds support for custom LLM providers.

## Why
Allows users to use their own LLM providers without modifying core code.

## How
- Created `PlannerProvider` base class
- Added `CustomPlanner` implementation
- Updated CLI to support custom providers

## Testing
- Added unit tests for `CustomPlanner`
- Added integration test for custom provider workflow
- Tested with local Ollama instance
```

---

## Code Review

### Review Checklist

- [ ] Code follows style guidelines
- [ ] Tests are included and pass
- [ ] Documentation is updated
- [ ] No breaking changes (or documented)
- [ ] Performance is acceptable
- [ ] Error handling is appropriate

### Responding to Feedback

- Be respectful and constructive
- Address all feedback
- Ask questions if unclear
- Update PR based on feedback

---

## Issue Reporting

### Bug Reports

Include:
- **Description:** What happened
- **Expected:** What should happen
- **Actual:** What actually happened
- **Steps to Reproduce:** How to reproduce
- **Environment:** Python version, OS, dependencies
- **Logs:** Relevant error logs

**Example:**

```markdown
## Description
Navigator fails to click button with data-testid attribute.

## Expected
Button should be clicked successfully.

## Actual
ElementNotFound error.

## Steps to Reproduce
1. Run: `python -m parallax.runner.cli run "Click button with data-testid='submit'"`
2. Error occurs

## Environment
- Python: 3.11.0
- OS: Windows 10
- Parallax: 1.0.0

## Logs
```
[ERROR] Element not found: button[data-testid='submit']
```
```

### Feature Requests

Include:
- **Description:** What feature you want
- **Use Case:** Why you need it
- **Proposed Solution:** How it could work
- **Alternatives:** Other solutions considered

---

## Questions?

- **GitHub Issues:** For bugs and feature requests
- **Discussions:** For questions and discussions
- **Email:** For sensitive issues

---

## License

By contributing, you agree that your contributions will be licensed under the Apache-2.0 License.

---

## Thank You!

Thank you for contributing to Parallax! Your contributions make this project better for everyone.

