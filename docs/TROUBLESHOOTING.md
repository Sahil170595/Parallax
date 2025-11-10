# Troubleshooting Guide

Common issues and solutions for Parallax.

## General Issues

### "OPENAI_API_KEY is required"

**Problem:** Missing API key for OpenAI provider.

**Solution:**
1. Create a `.env` file in the project root
2. Add your API key: `OPENAI_API_KEY=sk-proj-...`
3. Restart your application

**Alternative:** Use Anthropic instead:
```bash
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Plan Generation Issues

### "Plan has no steps" / Empty plan generated

**Problem:** LLM generated an empty plan (0 steps).

**Possible Causes:**
- Using GPT-5 (doesn't support temperature control, less deterministic)
- Task description too vague
- LLM API error

**Solutions:**
1. **Use gpt-4.1-mini** (default, more reliable):
   ```python
   planner = OpenAIPlanner(model="gpt-4.1-mini")
   ```

2. **Be more specific** in task description:
   - ❌ "Do something"
   - ✅ "Navigate to example.com and click the About link"

3. **Check API key** is valid and has credits

4. **Check logs** for LLM API errors

---

### "Failed to extract JSON from LLM response"

**Problem:** LLM returned invalid JSON.

**Solutions:**
1. **Check max_tokens** - may need to increase:
   ```yaml
   planner:
     max_tokens: 2000  # Increase for complex workflows
   ```

2. **Check LLM response** in logs (debug mode)

3. **Try different LLM provider** (OpenAI vs Anthropic)

---

## Navigation Issues

### "Element not found" / "Insufficient selector info"

**Problem:** Navigator can't find the element to click/type.

**Possible Causes:**
- Element doesn't exist on page
- Element not visible/loaded yet
- Poor ARIA structure (website issue)
- Selector is incorrect

**Solutions:**
1. **Enable vision fallback** (default: enabled):
   ```yaml
   vision:
     enabled: true  # Visual element location fallback
   ```

2. **Increase wait times**:
   ```yaml
   navigation:
     default_wait_ms: 2000  # Increase from 1000
   ```

3. **Use semantic selectors** (role + name) instead of CSS:
   ```json
   {"action": "click", "role": "button", "name": "Submit"}
   ```

4. **Check if element exists** - some sites have poor HTML structure

5. **Try different site** - some sites (like softlight.com) have 0 ARIA roles

---

### "Timeout 3000ms exceeded" / "wait_for_interactable_failed"

**Problem:** Element exists but not interactable within timeout.

**Solutions:**
1. **Increase wait times** in config
2. **Check if element is hidden** by CSS or JavaScript
3. **Wait for page to load** - add explicit wait steps in plan
4. **Enable vision fallback** for visual element location

---

### "Click failed after all attempts"

**Problem:** All retry attempts failed.

**Solutions:**
1. **Check element exists** on page
2. **Verify element is visible** (not hidden by CSS)
3. **Try different selector** (role+name vs CSS)
4. **Enable vision fallback** (visual location)
5. **Check if site has anti-bot protection** (Google, etc.)

---

## Vision Issues

### "Vision analysis failed"

**Problem:** Vision LLM call failed.

**Solutions:**
1. **Check API key** is valid
2. **Check API credits** available
3. **Check network connection**
4. **Vision will fallback** to heuristics automatically

---

## Authentication Issues

### "Unexpected auth redirect to: /login"

**Problem:** Workflow redirected to login page.

**Solutions:**
1. **Set up persistent browser context**:
   ```yaml
   playwright:
     user_data_dir: ~/.parallax/browser_data/linear
   ```

2. **Authenticate once**:
   ```bash
   python authenticate.py linear
   ```

3. **See [Authentication Guide](../../AUTHENTICATION.md)** for details

---

## Dataset Issues

### "Dataset directory does not exist"

**Problem:** Dataset directory wasn't created.

**Solutions:**
1. **Check write permissions** on datasets directory
2. **Check disk space** available
3. **Check logs** for creation errors

---

### "Missing required files: steps.jsonl"

**Problem:** Dataset files not created.

**Solutions:**
1. **Check if workflow completed** successfully
2. **Check write permissions**
3. **Check logs** for file creation errors

---

## Performance Issues

### Workflow is slow

**Problem:** Workflow takes too long.

**Solutions:**
1. **Reduce action_budget** if workflow is too long
2. **Disable vision** if not needed:
   ```yaml
   vision:
     enabled: false
   ```
3. **Reduce wait times**:
   ```yaml
   navigation:
     default_wait_ms: 500  # Reduce from 1000
   ```
4. **Use headless mode** (default: true)

---

### High API costs

**Problem:** LLM API costs are high.

**Solutions:**
1. **Use gpt-4.1-mini** (default, cost-effective):
   - $0.15 per 1M input tokens
   - $0.60 per 1M output tokens

2. **Disable vision** if not needed:
   ```yaml
   vision:
     enabled: false
   ```

3. **Reduce max_tokens**:
   ```yaml
   planner:
     max_tokens: 1200  # Reduce from 2000
   ```

4. **Use local LLM** for development:
   ```yaml
   provider: local
   ```

---

## Website-Specific Issues

### Softlight.com / Sites with no ARIA roles

**Problem:** Website has 0 ARIA roles, Navigator can't find elements.

**Solution:**
- **This is a website problem**, not a Parallax problem
- Some sites have poor HTML structure
- Try enabling vision fallback (may help)
- **Recommendation:** Use sites with proper ARIA structure

---

### Google search workflows

**Problem:** Google has anti-bot protection, workflows fail.

**Solution:**
- **Avoid Google search workflows**
- Use direct navigation instead:
  - ❌ "Search Google for softlight.com"
  - ✅ "Navigate to softlight.com"

---

### Linear / Notion without authentication

**Problem:** Workflows redirect to login.

**Solution:**
- **Set up authentication** (see [Authentication Guide](../../AUTHENTICATION.md))
- Or use sites that don't require authentication

---

## Configuration Issues

### "Configuration validation error"

**Problem:** Invalid configuration in `configs/config.yaml`.

**Solutions:**
1. **Check YAML syntax** (indentation, quotes)
2. **Check field names** match schema
3. **Check value types** (numbers vs strings)
4. **See [Configuration Guide](CONFIGURATION.md)** for valid options

---

## Logging & Debugging

### Enable debug logging

**Problem:** Need more detailed logs for debugging.

**Solution:**
Set log level in environment:
```bash
export PARALLAX_LOG_LEVEL=debug
```

Or in code:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

### Check constitution failures

**Problem:** Want to see why workflows failed validation.

**Solution:**
Check failure store:
```bash
cat datasets/_constitution_failures/constitution_failures.jsonl
```

Or use CLI:
```bash
python -m parallax.core.constitution_cli list --agent A1_Interpreter
```

---

## Still Having Issues?

1. **Check logs** - Most issues have error messages
2. **Check [FAQ](FAQ.md)** - Common questions answered
3. **Check [Configuration Guide](CONFIGURATION.md)** - All options documented
4. **Open an issue** on GitHub with:
   - Error message
   - Configuration file (redact API keys)
   - Logs (redact sensitive data)
   - Steps to reproduce

---

## Quick Reference

### Common Config Changes

```yaml
# Increase action budget for complex workflows
navigation:
  action_budget: 50  # Default: 30

# Increase wait times for slow sites
navigation:
  default_wait_ms: 2000  # Default: 1000

# Disable vision to reduce costs
vision:
  enabled: false  # Default: true

# Use different LLM provider
provider: anthropic  # Default: auto

# Use persistent browser context for auth
playwright:
  user_data_dir: ~/.parallax/browser_data/linear
```

---

**Last Updated:** November 2025



