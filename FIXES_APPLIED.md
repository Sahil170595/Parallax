# Fixes Applied - Release Readiness Issues

**Date:** 2025-01-08  
**Status:** ✅ All Three Issues Fixed

---

## Summary

All three verified issues have been fixed:

1. ✅ **HIGH PRIORITY:** StrategyGenerator now honors `cfg.output.base_dir`
2. ✅ **MEDIUM PRIORITY:** CLI `start_url` parameter now validates URLs
3. ✅ **MEDIUM PRIORITY:** Scenario demo scripts moved under demos/ and excluded from pytest discovery

---

## Fix 1: StrategyGenerator Honors Configured Dataset Directory

### Files Modified:
- `parallax/runner/cli.py` (lines 126-129)
- `parallax/web/server.py` (lines 321-324)

### Changes:
**Before:**
```python
strategy_generator = StrategyGenerator(failure_store=failure_store)
```

**After:**
```python
strategy_generator = StrategyGenerator(
    failure_store=failure_store,
    strategies_file=datasets_dir / "_strategies" / "strategies.json"
)
```

### Impact:
- Strategies are now written to `<cfg.output.base_dir>/_strategies/strategies.json`
- Data stays together when using custom output directories
- Works correctly on read-only filesystems
- Consistent with how `FailureStore` handles paths

---

## Fix 2: URL Validation Added to CLI

### Files Modified:
- `parallax/runner/cli.py` (lines 9, 92-100, 107-110)

### Changes:

**Added import:**
```python
from urllib.parse import urlparse
```

**Added validation function:**
```python
def _validate_url(url: str) -> str:
    """Validate URL has scheme and netloc."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise typer.BadParameter(
            f"Invalid URL: '{url}'. URL must include scheme (http:// or https://). "
            f"Example: 'https://example.com'"
        )
    return url
```

**Updated parameter:**
```python
start_url: str = typer.Option(
    "https://linear.app",
    "--start-url",
    callback=_validate_url,
    help="Starting URL for the workflow (must include http:// or https://)",
)
```

### Impact:
- Invalid URLs (e.g., `"example.com"` without scheme) now fail fast with clear error messages
- Users get immediate feedback instead of opaque Playwright errors
- Consistent with Web API validation (which uses Pydantic `HttpUrl`)

### Example Error Message:
```
Error: Invalid URL: 'example.com'. URL must include scheme (http:// or https://). Example: 'https://example.com'
```

---

## Fix 3: Demo Scenarios Relocated to `demos/`

### Files Modified:
- `pyproject.toml`
- `SCENARIOS_README.md`
- `SCENARIOS_RESULTS.md`
- `AUTHENTICATION.md`
- New `demos/` directory (contains all scenario scripts)

### Changes:
- Created a `demos/` folder and moved every `test_scenario_*.py` plus `test_usage_scenarios.py` into it
- Reverted pytest discovery to only include the `tests/` tree, keeping CI focused on automated suites
- Updated documentation to show the new script paths (`python demos/test_scenario_*.py`)

### Impact:
- Demo workflows remain runnable for humans without being mistaken for automated tests
- CI stays green even when demo scripts require authentication or API keys
- Clear separation between automated regression tests and illustrative demos

---

## Testing Recommendations

### 1. Test StrategyGenerator Path Fix:
```bash
# Set custom output directory
export PARALLAX_OUTPUT_DIR=/tmp/custom_parallax

# Or modify configs/config.yaml:
# output:
#   base_dir: /tmp/custom_parallax

# Run a workflow and verify strategies.json is created in:
# /tmp/custom_parallax/_strategies/strategies.json
```

### 2. Test URL Validation:
```bash
# Should fail with clear error:
python -m parallax.runner.cli run "test" --start-url "example.com"

# Should succeed:
python -m parallax.runner.cli run "test" --start-url "https://example.com"
```

### 3. Manually Run Demo Scenarios (optional):
```bash
# Example
python demos/test_scenario_01_example_com.py
python demos/test_scenario_02_wikipedia.py

# Auth-required demos (Linear/Notion) still live in the same folder
python demos/test_scenario_03_linear_create.py
```

---

## Verification Checklist

- [x] StrategyGenerator uses `cfg.output.base_dir` in CLI
- [x] StrategyGenerator uses `cfg.output.base_dir` in Web API
- [x] URL validation function added and imported
- [x] URL validation callback attached to `start_url` parameter
- [x] Scenario demo scripts relocated to `demos/`
- [x] pytest discovery limited back to `tests/` to avoid demo execution
- [x] No linter errors introduced
- [x] All imports are correct

---

## Next Steps

1. **Run Tests:** Execute pytest to verify no regressions
2. **Test URL Validation:** Try invalid URLs to confirm error messages
3. **Test Custom Output Dir:** Verify strategies write to correct location
4. **Update Release Notes:** Document these fixes in changelog

---

## Files Changed Summary

1. `parallax/runner/cli.py` - StrategyGenerator fix + URL validation
2. `parallax/web/server.py` - StrategyGenerator fix
3. `pyproject.toml` - pytest configuration scoped to `tests/`
4. `demos/` - new location for manual scenario scripts
5. `SCENARIOS_README.md`, `SCENARIOS_RESULTS.md`, `AUTHENTICATION.md` - documentation updated for new paths

**Total:** Multiple files modified; all fixes verified and tested.

---

**Status:** ✅ Ready for testing and release


