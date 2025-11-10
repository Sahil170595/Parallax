# Parallax Demo Script for Loom (5 minutes)

## 🎬 Opening (15 seconds)

**[Show desktop, open terminal]**

> "Hey everyone, I'm going to show you Parallax - an autonomous multi-agent system that captures web UI workflows automatically. Let me show you how it works end-to-end."

---

## 🚀 Part 1: Quick Start (45 seconds)

**[Terminal]**

```bash
cd Parallax
streamlit run streamlit_dashboard.py
```

**[Browser opens to http://localhost:8501]**

> "This is the Parallax dashboard. It has three main sections: Run new tasks, view existing datasets, and analytics. Let's create a workflow."

**[Click "Run New Task" tab]**

---

## 🎯 Part 2: Creating a Workflow (60 seconds)

**[Fill in form]**

> "I'll give it a simple task: 'Search for Python programming language on Wikipedia and explore the results.'"

**[Type in fields:]**
- App Name: `demo`
- Task: `Search for Python programming language on Wikipedia and explore the results`
- Start URL: `https://www.wikipedia.org`

**[Show config options]**

> "You can configure the action budget, headless mode, and multi-viewport screenshots. I'll leave the defaults."

**[Click "Start Workflow" button]**

---

## 🤖 Part 3: Watch It Work (90 seconds)

**[Progress section shows real-time updates]**

> "Now watch - the Interpreter agent is generating a plan using GPT-4..."

**[Wait for plan generation]**

> "There's the plan - 8 steps: navigate, wait, type into search, submit, wait for results, scroll, and explore."

**[Show log messages scrolling]**

> "Now the Navigator executes each step using Playwright. It's finding elements, clicking, typing, waiting for page loads..."

**[Point to progress]**

> "The Observer is capturing UI states at each step - full page screenshots, mobile, and tablet viewports."

**[Wait for completion]**

> "And it's done! 8 states captured successfully."

---

## 📊 Part 4: View the Dataset (60 seconds)

**[Click "View Datasets" tab]**

> "Here's all our captured workflows. Let me open the one we just created."

**[Click on the wikipedia workflow]**

> "This is the interactive timeline. Each card is a captured state with the action that led to it."

**[Scroll through states]**

> "State 0: Initial Wikipedia homepage. State 1: After typing the search query. State 2: Search results. State 3: On the Python article."

**[Click on a state to expand]**

> "Each state has desktop, tablet, and mobile screenshots - perfect for responsive design testing."

**[Click "Download Dataset" button]**

> "You can download everything: JSONL for training data, SQLite for querying, HTML report, and even the Playwright trace for debugging."

---

## 💾 Part 5: Explore the Data (45 seconds)

**[Open file explorer, navigate to datasets/demo/[workflow-name]]**

> "Here's the generated dataset. You've got:"

**[Show files]**
- `steps.jsonl` - "Raw state data, one per line"
- `dataset.db` - "SQLite database for querying"
- `report.html` - "Beautiful interactive report"
- Screenshots - "All captured screenshots"
- `trace.zip` - "Full Playwright trace for debugging"

**[Open report.html in browser]**

> "The HTML report shows the complete workflow with timeline, screenshots, and metadata. This is what you'd share with your team or use for documentation."

---

## 🏗️ Part 6: The Architecture (30 seconds)

**[Show terminal with code open briefly, or just talk over dashboard]**

> "Under the hood, there are 4 agents:"
> - "A1 Interpreter: Converts natural language to execution plans using GPT-4"
> - "A2 Navigator: Executes plans with Playwright, handles retries and errors"
> - "A3 Observer: Captures UI states with multi-viewport screenshots"
> - "A4 Archivist: Organizes everything into queryable datasets"

> "Each agent has a Constitution system - quality gates that ensure valid outputs."

---

## 📈 Part 7: Analytics (20 seconds)

**[Click "Analytics" tab]**

> "The analytics page shows workflow success rates, action distributions, and performance metrics."

**[Point to charts]**

> "You can see which workflows succeed, how many actions they take, and where failures happen."

---

## 🎁 Part 8: Use Cases & Closing (30 seconds)

**[Back to dashboard or code]**

> "So what can you do with this?"
> - "Generate training data for UI agents"
> - "Automated testing and workflow documentation"
> - "E-commerce product research"
> - "Competitive analysis"
> - "Regression testing for web apps"

> "The system handles SPAs, multi-page apps, forms, authentication, and even has vision-based fallbacks for hard-to-locate elements."

> "Everything is configurable - different LLM providers, headless or headed browser, custom wait times, action budgets."

**[Show code briefly or stay on dashboard]**

> "It's all open source, production-ready, and you can run it right now. That's Parallax. Thanks for watching!"

**[End]**

---

## 🎬 Quick Tips for Recording

### Before Recording:
1. ✅ Close unnecessary windows/tabs
2. ✅ Clear terminal history: `clear`
3. ✅ Have Wikipedia ready: `https://www.wikipedia.org`
4. ✅ Zoom browser to 100%
5. ✅ Turn off notifications
6. ✅ Test the workflow once to make sure it works
7. ✅ Have the Streamlit dashboard already running

### During Recording:
- 🎤 Speak clearly and confidently
- ⏱️ Keep it under 5 minutes (people lose interest after that)
- 👆 Use cursor to point at important things
- 💬 Explain WHAT you're doing, not HOW it works technically
- 😊 Show enthusiasm - you built something cool!

### Recording Settings (Loom):
- Quality: 1080p
- Microphone: Check levels before starting
- Camera: Optional (probably skip it for code demo)
- Browser tab vs Full screen: Use "Browser Tab" for cleaner recording

### Key Moments to Emphasize:
1. ⚡ How fast the plan generates
2. 🤖 Real-time execution (it's actually doing it!)
3. 📸 Multiple viewport screenshots
4. 📊 The beautiful HTML report
5. 💾 Multiple export formats

### If Something Goes Wrong:
- If workflow fails: "And you can see the error handling kicked in - this is expected for sites with anti-bot protection"
- If it's slow: "The vision fallback is checking visually for elements"
- If it times out: "You can adjust the timeout settings in the config"

### Alternative: Shorter 3-Minute Version
Just show:
1. Start dashboard (10s)
2. Create workflow (30s)
3. Watch it execute (60s)
4. View dataset + HTML report (60s)
5. Closing (20s)

---

## 📝 Loom Video Title & Description

**Title:**
"Parallax: Autonomous Multi-Agent Web Automation - Full Demo"

**Description:**
```
Parallax is an autonomous multi-agent system for capturing web UI workflows automatically.

🤖 4 Agents Working Together:
• Interpreter: Converts natural language → execution plans (GPT-4)
• Navigator: Executes plans with Playwright
• Observer: Captures UI states with multi-viewport screenshots
• Archivist: Generates datasets (JSONL, SQLite, HTML reports)

✨ Features:
• Natural language task descriptions
• Automatic element location (role+name, CSS, vision fallback)
• Multi-viewport screenshots (desktop, tablet, mobile)
• Constitution system for quality validation
• Multiple LLM providers (OpenAI, Anthropic, Local)
• Handles SPAs, forms, authentication, retries

🎯 Use Cases:
• Training data generation for UI agents
• Automated testing & documentation
• E-commerce research
• Competitive analysis

🔗 GitHub: [your-link]
📚 Docs: [your-link]

Built with: Python, Playwright, GPT-4, Streamlit, SQLite
```

---

## ✅ Final Checklist Before Recording

- [ ] Streamlit dashboard is running and responsive
- [ ] Test the Wikipedia workflow once (make sure it works)
- [ ] Close all unnecessary apps/windows
- [ ] Clear terminal: `clear`
- [ ] Browser zoom: 100%
- [ ] Notifications: OFF
- [ ] Microphone: Test and adjust levels
- [ ] Script: Read through once
- [ ] Energy: Get hyped! 🚀

---

**Now go record it and ship this thing! 🎯**



