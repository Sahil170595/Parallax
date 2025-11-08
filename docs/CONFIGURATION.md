# Configuration Reference

Complete reference for all configuration options in Parallax.

**New to Parallax?** See the [Quick Start Guide](QUICKSTART.md) for basic setup and configuration.

## Configuration File

Configuration is stored in `configs/config.yaml`. The file is loaded automatically when running workflows.

## Configuration Sections

### LLM Provider

```yaml
llm:
  provider: auto  # openai | anthropic | local | auto
  planner:
    max_tokens: 1200
    temperature: 0.2
    timeout_ms: 10000
```

**Options:**
- `provider`: LLM provider to use
  - `openai` - OpenAI GPT models (requires `OPENAI_API_KEY`)
  - `anthropic` - Anthropic Claude models (requires `ANTHROPIC_API_KEY`)
  - `local` - Local LLM (Ollama, vLLM, etc.)
  - `auto` - Automatically select based on available API keys

- `planner.max_tokens`: Maximum tokens for plan generation (default: 1200)
- `planner.temperature`: Temperature for plan generation (default: 0.2)
- `planner.timeout_ms`: Timeout for LLM requests in milliseconds (default: 10000)

---

### Navigation

```yaml
navigation:
  action_budget: 30
  default_wait_ms: 1000
  self_heal_attempts: 1
  scroll_margin_px: 64
```

**Options:**
- `action_budget`: Maximum number of actions per workflow (default: 30)
- `default_wait_ms`: Wait time between actions in milliseconds (default: 1000)
- `self_heal_attempts`: Number of retry attempts on failure (default: 1)
- `scroll_margin_px`: Margin for scrolling elements into view (default: 64)

---

### Capture Settings

```yaml
capture:
  desktop_viewport: { width: 1366, height: 832 }
  tablet_viewport: { width: 834, height: 1112 }
  mobile_viewport: { width: 390, height: 844 }
  crop_focus_padding_px: 16
  redact:
    enabled: true
    selectors:
      - input[type="password"]
      - input[type="email"]
      - [data-sensitive="true"]
```

**Options:**
- `desktop_viewport`: Desktop viewport dimensions (default: 1366x832)
- `tablet_viewport`: Tablet viewport dimensions (default: 834x1112)
- `mobile_viewport`: Mobile viewport dimensions (default: 390x844)
- `crop_focus_padding_px`: Padding for focus crops (default: 16)
- `redact.enabled`: Enable PII redaction (default: true)
- `redact.selectors`: CSS selectors for elements to redact

---

### Observer

```yaml
observer:
  role_diff_threshold: 0.2
  loader_timeout_ms: 8000
  detection_poll_ms: 150
```

**Options:**
- `role_diff_threshold`: Jaccard similarity threshold for role-tree diff (default: 0.2)
- `loader_timeout_ms`: Timeout for loader detection in milliseconds (default: 8000)
- `detection_poll_ms`: Polling interval for state detection in milliseconds (default: 150)

---

### Output

```yaml
output:
  base_dir: datasets
```

**Options:**
- `base_dir`: Base directory for storing datasets (default: `datasets`)

---

### Metrics

```yaml
metrics:
  prometheus_port: 9109
```

**Options:**
- `prometheus_port`: Port for Prometheus metrics server (default: 9109)

**Note:** Metrics server is not started by default. To enable, configure Prometheus to scrape this port.

---

### Playwright

```yaml
playwright:
  headless: true
  project: chromium  # chromium | firefox | webkit
  # channel: chrome  # Optional: Use installed Chrome instead of Chromium (set to "chrome" to enable)
  # user_data_dir: ~/.parallax/browser_data/linear  # Optional: Path to persistent browser context (saves cookies/sessions for authentication)
```

**Options:**
- `headless`: Run browser in headless mode (default: true)
- `project`: Browser to use (default: `chromium`)
  - `chromium` - Chromium browser
  - `firefox` - Firefox browser
  - `webkit` - WebKit browser
- `channel`: Browser channel (optional)
  - `chrome` - Use installed Chrome browser instead of Chromium (better compatibility, recommended for authentication)
  - Only works with `project: chromium`
- `user_data_dir`: Path to persistent browser context (optional)
  - Saves cookies, localStorage, and session data
  - Enables authentication workflows
  - Example: `~/.parallax/browser_data/linear`
  - See [Authentication Guide](../../AUTHENTICATION.md) for setup instructions

---

### Vision

```yaml
vision:
  enabled: false  # Enable vision-based enhancements
  provider: openai  # openai | anthropic
```

**Options:**
- `enabled`: Enable vision-based enhancements (default: false)
- `provider`: Vision LLM provider (default: `openai`)
  - `openai` - OpenAI vision models (requires `OPENAI_API_KEY`)
  - `anthropic` - Anthropic vision models (requires `ANTHROPIC_API_KEY`)

**Vision Features:**
- **Completion Detection:** Early termination when workflow is complete
- **State Significance:** Categorizes states as critical/supporting/optional
- **Element Location:** Visual fallback when selectors fail

---

## Environment Variables

### Required (for LLM planning)

At least one API key is required:

```bash
# OpenAI
OPENAI_API_KEY=sk-proj-...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

### Optional (for vision features)

```bash
# Vision features require OPENAI_API_KEY or ANTHROPIC_API_KEY
# No additional environment variables needed
```

### Optional (for local LLM)

```bash
# Local LLM base URL (e.g., Ollama, vLLM)
LOCAL_LLM_BASE_URL=http://localhost:11434
```

---

## Configuration Priority

1. **Environment Variables** - Highest priority
2. **config.yaml** - Default configuration
3. **Hardcoded Defaults** - Fallback defaults in code

---

## Example Configuration

### Minimal Configuration

```yaml
llm:
  provider: openai

navigation:
  action_budget: 30

output:
  base_dir: datasets
```

### Full Configuration

```yaml
llm:
  provider: auto
  planner:
    max_tokens: 1200
    temperature: 0.2
    timeout_ms: 10000

navigation:
  action_budget: 50
  default_wait_ms: 2000
  self_heal_attempts: 3
  scroll_margin_px: 64

capture:
  desktop_viewport: { width: 1920, height: 1080 }
  tablet_viewport: { width: 1024, height: 1366 }
  mobile_viewport: { width: 375, height: 667 }
  crop_focus_padding_px: 16
  redact:
    enabled: true
    selectors:
      - input[type="password"]
      - input[type="email"]
      - [data-sensitive="true"]

observer:
  role_diff_threshold: 0.2
  loader_timeout_ms: 8000
  detection_poll_ms: 150

output:
  base_dir: datasets

metrics:
  prometheus_port: 9109

playwright:
  headless: false
  project: chromium
  channel: chrome  # Use installed Chrome for better compatibility
  # user_data_dir: ~/.parallax/browser_data/myapp  # Enable for authenticated workflows

vision:
  enabled: true
  provider: openai
```

---

## Configuration Tips

### Performance

- **Increase `action_budget`** for complex workflows
- **Decrease `default_wait_ms`** for faster execution (may cause failures)
- **Enable `headless: true`** for faster execution

### Reliability

- **Increase `self_heal_attempts`** for better retry handling
- **Increase `loader_timeout_ms`** for slow-loading sites
- **Decrease `role_diff_threshold`** for more sensitive state detection

### Quality

- **Enable `vision.enabled`** for better completion detection
- **Enable `redact.enabled`** for PII protection
- **Adjust viewport sizes** for different screen sizes

---

## Troubleshooting

### Configuration Not Loading

Check that `configs/config.yaml` exists and is valid YAML.

### API Keys Not Working

Ensure environment variables are set correctly:
```bash
echo $OPENAI_API_KEY  # Should show your API key
```

### Vision Features Not Working

Ensure vision is enabled in config:
```yaml
vision:
  enabled: true
  provider: openai
```

And that the appropriate API key is set:
```bash
export OPENAI_API_KEY=sk-proj-...
```

---

## Advanced Configuration

### Custom Redaction Selectors

Add custom selectors for PII redaction:

```yaml
capture:
  redact:
    enabled: true
    selectors:
      - input[type="password"]
      - input[type="email"]
      - [data-sensitive="true"]
      - .ssn-input  # Custom selector
      - #credit-card  # Custom selector
```

### Custom Viewports

Define custom viewport sizes:

```yaml
capture:
  desktop_viewport: { width: 1920, height: 1080 }
  tablet_viewport: { width: 1024, height: 1366 }
  mobile_viewport: { width: 375, height: 667 }
```

### Multiple Browser Support

Switch between browsers:

```yaml
playwright:
  project: chromium  # or firefox | webkit
```

### Chrome Channel Support

Use installed Chrome browser for better compatibility and authentication:

```yaml
playwright:
  project: chromium
  channel: chrome  # Use installed Chrome instead of Chromium
```

**Benefits:**
- Better compatibility with websites
- Improved authentication support
- More realistic browser fingerprint

### Persistent Context for Authentication

Save browser sessions for authenticated workflows:

```yaml
playwright:
  user_data_dir: ~/.parallax/browser_data/linear
```

**Setup:**
1. Run `python authenticate.py linear` to log in once
2. Configure `user_data_dir` in `config.yaml`
3. Your workflows will use the saved session

See [Authentication Guide](../../AUTHENTICATION.md) for detailed instructions.

---

## See Also

- [Usage Guide](USAGE.md) - How to use Parallax
- [Architecture](ARCHITECTURE.md) - System architecture
- [API Reference](API.md) - Complete API reference

