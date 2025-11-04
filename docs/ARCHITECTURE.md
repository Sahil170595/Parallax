# Architecture Documentation

## System Overview

Parallax is a multi-agent system for capturing web workflows. It consists of four agents that work together to execute natural language tasks and capture UI states.

```
┌─────────────┐
│   Task      │
│ "Create a   │
│  project"   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent A1: Interpreter                     │
│  Converts natural language → Execution plan                   │
│  Uses LLM (OpenAI/Anthropic/Local)                           │
│  Validates plan against constitution                          │
└───────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
                 ┌───────────────┐
                 │ ExecutionPlan │
                 │  - Step 1     │
                 │  - Step 2     │
                 │  - Step 3     │
                 └───────┬───────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent A2: Navigator                        │
│  Executes plan in live browser                                │
│  Uses Playwright for automation                                │
│  Semantic selectors (role > label > data-testid > CSS)        │
│  Retry logic + vision fallbacks                               │
└───────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent A3: Observer                         │
│  Captures UI states and screenshots                           │
│  Detects non-URL states (modals, toasts, forms)              │
│  Multi-viewport capture (desktop, tablet, mobile)           │
│  Validates state capture against constitution                 │
└───────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent A4: Archivist                       │
│  Organizes data into datasets                                 │
│  Writes JSONL, SQLite, HTML reports                          │
│  Validates dataset creation against constitution              │
└───────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
                 ┌───────────────┐
                 │   Dataset      │
                 │  - steps.jsonl│
                 │  - dataset.db │
                 │  - report.html│
                 │  - screenshots│
                 └───────────────┘
```

---

## Agent Responsibilities

### Agent A1: Interpreter

**Purpose:** Convert natural language tasks into structured execution plans.

**Responsibilities:**
- Accept natural language task descriptions
- Use LLM provider to generate step-by-step plans
- Validate plans against Interpreter constitution
- Track failures for continuous improvement

**Input:** Natural language task (e.g., "Create a project in Linear")

**Output:** `ExecutionPlan` with ordered `PlanStep` objects

**Constitution Rules:**
- ✅ Plan must have valid structure
- ✅ Plan must have at least one step
- ✅ All steps must have valid actions

---

### Agent A2: Navigator

**Purpose:** Execute plans in a live browser.

**Responsibilities:**
- Execute each step of the plan sequentially
- Handle element selection using semantic selectors
- Retry failed steps (up to 3 times)
- Use vision-based fallbacks when selectors fail
- Monitor for workflow completion using vision analysis
- Detect authentication redirects
- Enforce action budget limits

**Input:** `ExecutionPlan` from Interpreter

**Output:** Executed actions, captured states (via Observer)

**Selector Priority:**
1. `role + name` (ARIA role + accessible name)
2. `label` (associated label element)
3. `data-testid` (test ID attribute)
4. `CSS selector` (fallback)

**Constitution Rules:**
- ✅ Navigation must complete without page crashes
- ⚠️ Action budget should not be exceeded (warning)

---

### Agent A3: Observer

**Purpose:** Capture UI states and screenshots.

**Responsibilities:**
- Capture UI state after each action
- Detect non-URL state changes (modals, toasts, forms)
- Capture multi-viewport screenshots (desktop, tablet, mobile)
- Generate state signatures for deduplication
- Analyze state significance using vision (if enabled)
- Validate state capture against Observer constitution

**Input:** Playwright Page object, action description

**Output:** `UIState` objects with screenshots and metadata

**State Detection:**
- **Modals:** `role="dialog"`, `aria-modal="true"`
- **Toasts:** `role="status"`, `role="alert"`, `.toast` class
- **Forms:** `:invalid` → `:valid` transitions
- **Role-Tree Diff:** Jaccard similarity (threshold: 0.2)
- **Async Loads:** `aria-busy`, `role="progressbar"`, spinner classes

**Constitution Rules:**
- ✅ State must be captured successfully
- ✅ Screenshots must be saved
- ⚠️ State should have meaningful description (warning)

---

### Agent A4: Archivist

**Purpose:** Organize captured data into datasets.

**Responsibilities:**
- Write states to JSONL format
- Create SQLite database with states and screenshots
- Generate Markdown reports
- Generate HTML reports with timeline
- Validate dataset creation against Archivist constitution

**Input:** List of `UIState` objects

**Output:** Dataset directory with files:
- `steps.jsonl` - JSONL format with all states
- `dataset.db` - SQLite database
- `report.md` - Markdown report
- `report.html` - HTML report with timeline
- `XX_full.png`, `XX_mobile.png`, `XX_tablet.png` - Screenshots

**Constitution Rules:**
- ✅ All required files must exist
- ✅ Data integrity must be maintained
- ⚠️ Dataset should have at least 1 state (warning)

---

## Data Flow

### 1. Planning Phase

```
Task → Interpreter → LLM Provider → ExecutionPlan
                      ↓
                 Constitution Validation
                      ↓
                   Plan (if valid)
```

### 2. Execution Phase

```
Plan → Navigator → Playwright → Browser
         ↓
    Observer → Detectors → UIState
         ↓
    Vision Analyzer (if enabled)
         ↓
    Constitution Validation
```

### 3. Archiving Phase

```
UIState[] → Archivist → DatasetStore → Dataset Directory
                           ↓
                    Constitution Validation
```

---

## State Detection

### Non-URL State Detection

Parallax detects UI state changes without relying on URL changes:

1. **Modal Detection**
   - Checks for `role="dialog"` elements
   - Verifies `aria-modal="true"`
   - Captures focus crops for modals

2. **Toast Detection**
   - Checks for `role="status"` or `role="alert"` elements
   - Looks for `.toast` class heuristics
   - Captures transient notifications

3. **Form State Detection**
   - Tracks `:invalid` → `:valid` transitions
   - Monitors form validity changes
   - Captures form submission states

4. **Role-Tree Diff**
   - Extracts ARIA role tree
   - Computes Jaccard similarity with previous state
   - Captures when similarity < threshold (0.2)

5. **Async Load Detection**
   - Checks for `aria-busy` attributes
   - Looks for `role="progressbar"` elements
   - Detects spinner classes

6. **State Signature**
   - Generates hash-based signature from URL, role tree, and metadata
   - Used for deduplication

---

## Vision-Based Enhancements

When vision features are enabled (`vision.enabled: true`), Parallax uses vision LLMs for:

1. **Completion Detection**
   - Analyzes screenshots to determine if workflow is complete
   - Returns confidence score and reasoning
   - Used to early-terminate workflows

2. **State Significance Analysis**
   - Categorizes states as `critical`, `supporting`, or `optional`
   - Identifies key UI elements
   - Provides reasoning for categorization

3. **Element Location (Fallback)**
   - Locates elements visually when selectors fail
   - Returns (x, y) coordinates for mouse clicks
   - Used as fallback when semantic selectors fail

**Heuristic Fallbacks:**
- If vision API keys are missing, uses simple heuristics
- Completion: checks if 3+ states captured
- Significance: uses rule-based categorization

---

## Constitution System

The Constitution System ensures quality gates for each agent:

### Validation Levels

1. **CRITICAL** - Must pass or workflow fails
2. **WARNING** - Should pass, but can continue
3. **INFO** - Best practice suggestions

### Failure Tracking

- Failures stored in `datasets/_constitution_failures/constitution_failures.jsonl`
- Structured format for analysis
- Queryable by agent, rule, level

### Continuous Improvement

- Failure data used to improve prompts
- Pattern analysis for common failures
- Data-driven enhancement

---

## Error Handling

### Retry Strategy

1. **Step Retries:** Navigator retries failed steps up to 3 times
2. **Vision Fallback:** If selector fails, attempts vision-based location
3. **Auto-Heal:** Configurable retry attempts at workflow level (`self_heal_attempts`)

### Error Recovery

1. **Authentication Redirects:** Detected and handled (breaks workflow)
2. **Page Crashes:** Detected and logged
3. **Constitution Violations:** Critical failures raise exceptions, warnings are logged

---

## Configuration

### Configuration File

`configs/config.yaml` controls:

- **LLM Provider:** `openai`, `anthropic`, `local`, or `auto`
- **Navigation:** Action budget, wait times, retry attempts
- **Observer:** Detection thresholds, viewport settings
- **Vision:** Enable/disable, provider selection
- **Output:** Base directory for datasets
- **Playwright:** Browser type, headless mode

---

## Metrics & Observability

### Prometheus Metrics

- `parallax_workflow_success_total` - Successful workflows
- `parallax_workflow_failure_total` - Failed workflows
- `parallax_states_per_workflow` - States per workflow
- `parallax_llm_tokens_total` - LLM tokens used
- `parallax_trace_size_bytes` - Trace size

### Structured Logging

- Uses `structlog` for structured logging
- Logs include agent, action, state, errors
- Queryable format for analysis

---

## Extensibility

### Adding New Agents

1. Create agent class in `parallax/agents/`
2. Implement constitution rules in `parallax/agents/constitutions.py`
3. Wire into CLI in `parallax/runner/cli.py`

### Adding New LLM Providers

1. Create provider class extending `PlannerProvider`
2. Implement `generate_plan()` method
3. Add to `_planner_from_config()` in `parallax/runner/cli.py`

### Adding New State Detectors

1. Add detection logic to `parallax/observer/detectors.py`
2. Update `capture_state()` method
3. Add to metadata in `UIState`

---

## Security & Privacy

### PII Redaction

- Screenshots can be redacted using `parallax.core.capture`
- Masks password fields
- Configurable redaction rules

### API Keys

- Stored in `.env` file (gitignored)
- Loaded via `python-dotenv`
- Never logged or exposed

---

## Performance

### Optimizations

1. **Action Budget:** Limits maximum actions per workflow
2. **State Deduplication:** Signature-based deduplication
3. **Multi-Viewport:** Parallel screenshot capture
4. **Vision Fallback:** Only used when selectors fail

### Targets

- **Speed:** < 30 seconds for simple workflows
- **Reliability:** > 90% success rate
- **Accuracy:** > 95% state capture accuracy

---

## Future Enhancements

1. **Smart Healing:** Learn from failures and modify plans
2. **Better Vision Heuristics:** OCR-based text extraction
3. **Concurrent Execution:** Parallel workflows
4. **Better Error Messages:** User-friendly error guidance
5. **Config Validation:** Schema-based validation
6. **Progress Reporting:** Progress bars and ETAs

