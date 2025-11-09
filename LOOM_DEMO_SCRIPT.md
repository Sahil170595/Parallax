# Parallax Loom Demo Script

**Duration:** ~10-12 minutes  
**Audience:** Developers, Product Managers, Technical Decision Makers

---

## Pre-Demo Setup Checklist

- [ ] Terminal open with project directory
- [ ] Browser ready (Chrome recommended)
- [ ] API key configured (`.env` file with `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`)
- [ ] Playwright browsers installed: `python -m playwright install --with-deps`
- [ ] Test that CLI works: `python -m parallax.runner.cli --help`

---

## Demo Script

### Part 1: Introduction & Overview (2 minutes)

**What to Say:**
> "Today I'm showing you Parallax, an autonomous multi-agent system that captures complex web workflows. It uses AI to understand natural language tasks, executes them in a browser, and captures every state change - even when URLs don't change."

**What to Show:**
1. Open terminal in project directory
2. Show project structure: `ls` or `dir`
3. Show README.md briefly
4. Explain the four-agent architecture:
   - **Agent A1: Interpreter** - Converts natural language → execution plans
   - **Agent A2: Navigator** - Executes plans in live browser
   - **Agent A3: Observer** - Captures UI states and screenshots
   - **Agent A4: Archivist** - Organizes data into datasets

**Key Points:**
- "No hardcoded selectors - it uses semantic understanding"
- "Captures modals, toasts, async transitions - things that break traditional automation"
- "Production-ready with retry logic, rate limiting, error recovery"

---

### Part 2: Simple Example - Wikipedia Search (3 minutes)

**What to Say:**
> "Let's start with a simple example: searching Wikipedia. This demonstrates the basic workflow."

**Commands to Run:**
```bash
# Show the command
python -m parallax.runner.cli run "Search for Python programming language" \
  --app-name wikipedia \
  --start-url https://wikipedia.org
```

**What to Show:**
1. **Before running:** Explain what will happen
   - "Parallax will generate a plan, open a browser, execute the search, and capture all states"
2. **During execution:** Point out the progress bar
   - "Notice the real-time progress and beautiful CLI output"
   - "It's generating a plan, executing steps, capturing screenshots"
3. **After completion:** Show the output
   ```bash
   # Navigate to output directory
   cd datasets/wikipedia/search-for-python-programming-language
   
   # Show the files
   ls
   # or
   dir
   ```

**What to Highlight:**
- `report.html` - "Open this in your browser for a visual timeline"
- `steps.jsonl` - "Machine-readable state data"
- `dataset.db` - "SQLite database with all states"
- Screenshots - "Multi-viewport captures (desktop, tablet, mobile)"

**Open report.html:**
- Show the timeline view
- Click through different states
- Point out screenshots for each state
- Show metadata (modals, toasts, form states)

**Key Points:**
- "Notice it captured the search box interaction"
- "It detected the page transition even though the URL structure is complex"
- "All states are timestamped and documented"

---

### Part 3: Complex Example - Multi-Step Workflow (4 minutes)

**What to Say:**
> "Now let's see a more complex workflow - exploring a website and navigating through multiple pages."

**Commands to Run:**
```bash
# Example.com exploration
python -m parallax.runner.cli run "Navigate to example.com and explore all tabs" \
  --app-name demo \
  --start-url https://example.com
```

**What to Show:**
1. **Explain the complexity:**
   - "This task requires understanding what 'explore all tabs' means"
   - "It needs to identify navigation elements, click them, and capture each state"
2. **During execution:**
   - "Watch how it systematically explores the site"
   - "Notice the retry logic if something doesn't work immediately"
3. **Show the results:**
   ```bash
   cd datasets/demo/navigate-to-example-com-and-explore-all-tabs
   ```

**Open report.html:**
- Show multiple states captured
- Demonstrate the timeline navigation
- Show how it captured different pages/views

**Key Points:**
- "It understood the task semantically"
- "Captured every state change, even subtle ones"
- "The report shows the complete workflow journey"

---

### Part 4: Advanced Features (2 minutes)

**What to Say:**
> "Let me show you some of the advanced features that make Parallax production-ready."

**Show Configuration:**
```bash
# Open config file
cat configs/config.yaml
# or
type configs\config.yaml
```

**Highlight:**
- Multi-viewport capture (desktop, tablet, mobile)
- Vision-based enhancements (optional)
- Self-healing workflows
- Cost tracking
- Prometheus metrics

**Show Error Handling:**
```bash
# Try an invalid URL to show validation
python -m parallax.runner.cli run "test" --start-url "example.com"
```

**What to Show:**
- "Notice the clear error message - it validates URLs upfront"
- "This prevents opaque errors deep in execution"

**Show Strategy Learning:**
```bash
# Show strategies directory
ls datasets/_strategies/
# or
dir datasets\_strategies\
```

**Explain:**
- "Parallax learns from failures and improves strategies"
- "Strategies are stored and reused for better success rates"

---

### Part 5: Output Formats & Use Cases (1 minute)

**What to Say:**
> "Parallax produces multiple output formats for different use cases."

**Show Output Formats:**
1. **JSONL** - "For programmatic processing and analysis"
2. **SQLite** - "For querying and data analysis"
3. **HTML Report** - "For visual review and documentation"
4. **Playwright Trace** - "For debugging and replay"

**Use Cases:**
- "Documentation generation - automatically create workflow docs"
- "Testing - capture real user workflows for test cases"
- "Training - teach AI systems by example"
- "Analysis - understand how users interact with your app"

---

### Part 6: Closing & Next Steps (1 minute)

**What to Say:**
> "Parallax is production-ready and handles real-world complexity. Let me show you how to get started."

**Show Quick Start:**
```bash
# Show installation
cat README.md | grep -A 10 "Installation"
# or
type README.md | findstr /C:"Installation"
```

**Key Takeaways:**
1. "Natural language → automated execution"
2. "Captures everything - modals, toasts, async transitions"
3. "Production-ready with error handling and monitoring"
4. "Multiple output formats for different use cases"

**Next Steps:**
- "Check out the documentation in `docs/`"
- "Try the examples in `demos/`"
- "Read `FIXES_APPLIED.md` for recent improvements"

---

## Progression Instructions

### How to Progress Through the Demo

1. **Start Recording:**
   - Begin with Part 1 (Introduction)
   - Have terminal and browser ready

2. **Part 1 → Part 2:**
   - After explaining architecture, immediately run the Wikipedia example
   - Don't pause - show the live execution

3. **Part 2 → Part 3:**
   - After showing Wikipedia results, immediately run the complex example
   - Keep momentum going

4. **Part 3 → Part 4:**
   - After showing complex workflow, switch to showing features
   - This is a good place for a brief pause if needed

5. **Part 4 → Part 5:**
   - Show configuration and error handling
   - Then explain output formats

6. **Part 5 → Part 6:**
   - Wrap up with use cases and next steps

### Tips for Smooth Progression

- **Practice the commands beforehand** - Know exactly what to type
- **Have browser tabs ready** - Pre-open example.com, wikipedia.org
- **Test the workflows** - Make sure they work before recording
- **Keep terminal history** - Use up arrow to repeat commands
- **Have report.html ready** - Pre-open one report to show structure
- **Pause strategically** - Brief pauses between major sections are fine

### What to Do If Something Goes Wrong

- **If a workflow fails:** Show the error handling - "Notice how it gracefully handles failures"
- **If API key missing:** Show the helpful error message
- **If browser doesn't start:** Show the troubleshooting steps
- **Turn mistakes into features:** "This demonstrates the error recovery system"

### Timing Breakdown

- Part 1: 2 minutes
- Part 2: 3 minutes (1 min setup, 1 min execution, 1 min results)
- Part 3: 4 minutes (1 min setup, 2 min execution, 1 min results)
- Part 4: 2 minutes
- Part 5: 1 minute
- Part 6: 1 minute
- **Total: ~13 minutes** (with buffer for questions/demos)

---

## Post-Demo Checklist

- [ ] Stop recording
- [ ] Review video for clarity
- [ ] Add timestamps/chapters if needed
- [ ] Upload to Loom
- [ ] Share link with team

---

## Alternative Shorter Demo (5 minutes)

If you need a shorter version:

1. **Introduction** (30 seconds)
2. **Wikipedia Example** (2 minutes) - Show execution and results
3. **Advanced Features** (1.5 minutes) - Configuration, error handling
4. **Closing** (1 minute) - Use cases and next steps

Skip Part 3 (complex example) and Part 5 (output formats) for the shorter version.

---

## Demo Commands Cheat Sheet

```bash
# Test CLI works
python -m parallax.runner.cli --help

# Simple example
python -m parallax.runner.cli run "Search for Python programming language" \
  --app-name wikipedia \
  --start-url https://wikipedia.org

# Complex example
python -m parallax.runner.cli run "Navigate to example.com and explore all tabs" \
  --app-name demo \
  --start-url https://example.com

# Show error handling
python -m parallax.runner.cli run "test" --start-url "example.com"

# View results
cd datasets/wikipedia/search-for-python-programming-language
# Open report.html in browser
```

---

**Good luck with your demo! 🎯**

