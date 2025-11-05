# API Documentation

## Agents

### Agent A1: Interpreter

**Module:** `parallax.agents.interpreter`

#### `Interpreter`

Converts natural language tasks into execution plans.

```python
from parallax.agents.interpreter import Interpreter
from parallax.llm.openai_provider import OpenAIPlanner
from parallax.core.constitution import FailureStore

# Initialize
provider = OpenAIPlanner()
failure_store = FailureStore(Path("datasets/_constitution_failures"))
interpreter = Interpreter(provider, failure_store=failure_store)

# Generate plan
plan = await interpreter.plan("Create a project in Linear", {"start_url": "https://linear.app"})
```

**Methods:**

- `plan(task: str, context: Optional[dict] = None) -> ExecutionPlan`
  - Generates an execution plan from a natural language task
  - Validates plan against Interpreter constitution
  - Returns `ExecutionPlan` with ordered steps

---

### Agent A2: Navigator

**Module:** `parallax.agents.navigator`

#### `Navigator`

Executes plans in a live browser.

```python
from parallax.agents.navigator import Navigator
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.launch()
    page = await browser.new_page()
    
    navigator = Navigator(
        page,
        observer=observer,
        default_wait_ms=1000,
        scroll_margin_px=64,
        vision_analyzer=vision_analyzer,
        task_context="Create a project in Linear"
    )
    
    await navigator.execute(plan, action_budget=30)
```

**Methods:**

- `execute(plan: ExecutionPlan, action_budget: int = 30) -> None`
  - Executes each step of the plan sequentially
  - Handles errors with retries and vision-based fallbacks
  - Monitors for completion using vision analysis

**Attributes:**

- `action_count: int` - Number of actions executed
- `constitution: AgentConstitution` - Navigator constitution for validation

---

### Agent A3: Observer

**Module:** `parallax.agents.observer`

#### `Observer`

Captures UI states and screenshots.

```python
from parallax.agents.observer import Observer
from parallax.observer.detectors import Detectors
from pathlib import Path

detectors = Detectors(config, vision_analyzer=vision_analyzer)
observer = Observer(
    page,
    detectors,
    save_dir=Path("output"),
    task_context="Create a project in Linear"
)

state = await observer.observe("click(button[Create])")
```

**Methods:**

- `observe(action_desc: Optional[str]) -> Optional[UIState]`
  - Captures current UI state with screenshots and metadata
  - Validates state capture against Observer constitution
  - Returns `UIState` object or `None` if capture failed

**Properties:**

- `states: List[UIState]` - List of all captured states

---

### Agent A4: Archivist

**Module:** `parallax.agents.archivist`

#### `Archivist`

Organizes captured data into datasets.

```python
from parallax.agents.archivist import Archivist
from pathlib import Path

archivist = Archivist(Path("datasets"))

dataset_path = archivist.write_states(
    app="linear",
    task_slug="create-project",
    states=observer.states,
    trace_zip="trace.zip"
)
```

**Methods:**

- `write_states(app: str, task_slug: str, states: Iterable[UIState], trace_zip: str = "trace.zip") -> Path`
  - Writes states to JSONL, SQLite, and generates reports
  - Validates dataset creation against Archivist constitution
  - Returns path to created dataset directory

---

## Core Schemas

### `PlanStep`

A single step in an execution plan.

```python
from parallax.core.schemas import PlanStep

step = PlanStep(
    action="click",
    role="button",
    name="Create",
    selector="button[data-testid='create']",
    value=None
)
```

**Attributes:**
- `action: str` - Action type ("navigate", "click", "type", "submit")
- `target: Optional[str]` - Target URL for navigation
- `role: Optional[str]` - ARIA role for semantic selection
- `name: Optional[str]` - ARIA name or accessible name
- `selector: Optional[str]` - CSS selector or data-testid
- `value: Optional[str]` - Value for type actions

---

### `ExecutionPlan`

A complete execution plan with ordered steps.

```python
from parallax.core.schemas import ExecutionPlan, PlanStep

plan = ExecutionPlan(steps=[
    PlanStep(action="navigate", target="https://linear.app"),
    PlanStep(action="click", role="button", name="Create"),
    PlanStep(action="type", selector="input[name='name']", value="My Project"),
    PlanStep(action="submit", selector="button[type='submit']")
])
```

**Attributes:**
- `steps: List[PlanStep]` - Ordered list of steps

---

### `UIState`

A captured UI state with screenshots and metadata.

```python
from parallax.core.schemas import UIState

state = UIState(
    id="state_abc12345",
    url="https://linear.app/projects",
    description="Project list page",
    has_modal=False,
    action="click(button[Create])",
    screenshots={
        "full": "00_full.png",
        "mobile": "00_mobile.png",
        "tablet": "00_tablet.png"
    },
    metadata={
        "roles": [...],
        "has_toast": False,
        "form_validity": None,
        "role_diff": 0.0
    },
    state_signature="abc12345..."
)
```

**Attributes:**
- `id: str` - Unique identifier
- `url: str` - Current page URL
- `description: str` - Human-readable description
- `has_modal: bool` - Whether a modal is present
- `action: Optional[str]` - Action description
- `screenshots: Dict[str, str]` - Viewport name to filename mapping
- `metadata: Dict[str, Any]` - Additional metadata
- `state_signature: Optional[str]` - Hash signature for deduplication

---

## LLM Providers

### OpenAI Provider

**Module:** `parallax.llm.openai_provider`

```python
from parallax.llm.openai_provider import OpenAIPlanner

planner = OpenAIPlanner(model="gpt-4.1-mini")
plan = await planner.generate_plan("Create a project in Linear", {})
```

### Anthropic Provider

**Module:** `parallax.llm.anthropic_provider`

```python
from parallax.llm.anthropic_provider import AnthropicPlanner

planner = AnthropicPlanner(model="claude-3-5-sonnet-20241022")
plan = await planner.generate_plan("Create a project in Linear", {})
```

### Local Provider

**Module:** `parallax.llm.local_provider`

```python
from parallax.llm.local_provider import LocalPlanner

planner = LocalPlanner(base_url="http://localhost:11434")
plan = await planner.generate_plan("Create a project in Linear", {})
```

---

## Vision Analyzer

**Module:** `parallax.vision.analyzer`

### `VisionAnalyzer`

Provides vision-based analysis for completion detection, state significance, and element location.

```python
from parallax.vision.analyzer import VisionAnalyzer

analyzer = VisionAnalyzer(provider="openai")

# Completion detection
completion = await analyzer.analyze_completion(
    screenshot_bytes,
    task_context="Create a project in Linear",
    workflow_states=states
)

# State significance
significance = await analyzer.analyze_significance(
    screenshot_bytes,
    task_context="Create a project in Linear",
    current_state={"url": "...", "has_modal": False},
    previous_state=None
)

# Element location
location = await analyzer.find_element_vision(
    screenshot_bytes,
    description="Create button",
    action_type="click"
)
```

**Methods:**

- `analyze_completion(screenshot_bytes, task_context, workflow_states) -> Dict[str, Any]`
  - Determines if workflow is complete from screenshot
  - Returns `{"is_complete": bool, "confidence": float, "reasoning": str}`

- `analyze_significance(screenshot_bytes, task_context, current_state, previous_state) -> Dict[str, Any]`
  - Categorizes state significance (critical/supporting/optional)
  - Returns `{"significance": str, "confidence": float, "reasoning": str, "key_elements": list}`

- `find_element_vision(screenshot_bytes, description, action_type) -> Dict[str, Any]`
  - Locates element using vision analysis
  - Returns `{"element_found": bool, "x": int, "y": int, "confidence": float}`

---

## Constitution System

**Module:** `parallax.core.constitution`

### `AgentConstitution`

Validates agent outputs against quality gates.

```python
from parallax.core.constitution import AgentConstitution, ValidationRule, ValidationLevel

constitution = AgentConstitution(
    agent_name="A1_Interpreter",
    rules=[
        ValidationRule(
            name="plan_structure",
            description="Plan must have valid structure",
            level=ValidationLevel.CRITICAL,
            validator=validate_plan_structure
        )
    ]
)

report = constitution.validate(task, plan, context)
if not report.passed:
    # Handle failures
    pass
```

### `FailureStore`

Stores constitution failures for analysis.

```python
from parallax.core.constitution import FailureStore
from pathlib import Path

failure_store = FailureStore(Path("datasets/_constitution_failures"))
failure_store.save_failure(report)

# Query failures
stats = failure_store.get_stats()
failures = failure_store.list_failures(agent="A1_Interpreter")
```

---

## CLI

**Module:** `parallax.runner.cli`

### `run`

Main CLI command for running workflows.

```bash
python -m parallax.runner.cli run "Create a project in Linear" --app-name linear --start-url https://linear.app
```

**Arguments:**
- `task: str` - Natural language task description
- `--app-name: str` - Application name (default: "linear")
- `--start-url: str` - Starting URL (default: "https://linear.app")

---

## Configuration

**File:** `configs/config.yaml`

```yaml
llm:
  provider: openai  # openai | anthropic | local | auto
  model: gpt-4.1-mini

navigation:
  action_budget: 30
  default_wait_ms: 1000
  self_heal_attempts: 1

observer:
  role_diff_threshold: 0.2
  capture_viewports:
    - full
    - mobile
    - tablet

vision:
  enabled: false
  provider: openai  # openai | anthropic

output:
  base_dir: datasets
```

---

## Examples

### Basic Workflow

```python
from parallax.agents.interpreter import Interpreter
from parallax.agents.navigator import Navigator
from parallax.agents.observer import Observer
from parallax.agents.archivist import Archivist
from parallax.llm.openai_provider import OpenAIPlanner
from parallax.observer.detectors import Detectors
from playwright.async_api import async_playwright
from pathlib import Path

async def run_workflow(task: str):
    # Initialize agents
    planner = OpenAIPlanner()
    interpreter = Interpreter(planner)
    
    # Generate plan
    plan = await interpreter.plan(task, {"start_url": "https://linear.app"})
    
    # Setup browser
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Initialize detectors and observer
        detectors = Detectors({})
        observer = Observer(page, detectors, save_dir=Path("output"))
        
        # Initialize navigator
        navigator = Navigator(page, observer=observer)
        
        # Execute plan
        await navigator.execute(plan)
        
        # Save dataset
        archivist = Archivist(Path("datasets"))
        archivist.write_states("linear", "create-project", observer.states)
        
        await browser.close()

# Run workflow
import asyncio
asyncio.run(run_workflow("Create a project in Linear"))
```

---

## Error Handling

### Constitution Violations

```python
from parallax.core.constitution import ConstitutionViolation

try:
    await navigator.execute(plan)
except ConstitutionViolation as e:
    print(f"Constitution violation: {e}")
    for failure in e.failures:
        print(f"  - {failure.rule_name}: {failure.reason}")
```

### Retry Logic

The Navigator automatically retries failed steps up to 3 times. If a step continues to fail, it attempts vision-based fallback (if available) or continues to the next step.

---

## Metrics

**Module:** `parallax.core.metrics`

Prometheus metrics are automatically collected:

- `parallax_workflow_success_total` - Successful workflows
- `parallax_workflow_failure_total` - Failed workflows
- `parallax_states_per_workflow` - States captured per workflow
- `parallax_llm_tokens_total` - LLM tokens used
- `parallax_trace_size_bytes` - Playwright trace size

Access metrics at `http://localhost:9090/metrics` (if metrics server is enabled).

