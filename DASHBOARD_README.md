# Parallax Streamlit Dashboard

A beautiful, interactive dashboard for visualizing and running Parallax workflow captures.

## Features

- 🚀 **Run New Tasks**: Execute workflows directly from the dashboard with real-time progress
- 📚 **View Datasets**: Browse all captured workflows with detailed state viewers
- 📊 **Task Analytics**: Visualize metrics, distributions, and insights across all datasets
- 🖼️ **Screenshot Timeline**: View state progression with multi-viewport screenshots
- 📈 **Interactive Charts**: Plotly-powered visualizations for workflow analysis

## Quick Start

**New to Parallax?** See the [Quick Start Guide](../docs/QUICKSTART.md) for installation and setup.

### Install Dependencies

```bash
# Install from project (includes all dependencies)
pip install -e .

# Install Playwright browsers
python -m playwright install --with-deps
```

### Run the Dashboard

```bash
# Using the helper script (recommended)
python run_dashboard.py

# Or directly with Streamlit
streamlit run streamlit_dashboard.py
```

The dashboard will open in your browser at `http://localhost:8501`

**Note:** Make sure you have set up your API keys in `.env` (see [Quick Start Guide](../docs/QUICKSTART.md)).

## Usage

### Running a Task

1. Navigate to **"Run New Task"** in the sidebar
2. Enter:
   - **Task Description**: What you want Parallax to do (e.g., "Navigate to example.com and explore all tabs")
   - **App Name**: Name for organizing this task (e.g., "demo")
   - **Start URL**: Initial URL to navigate to
   - **Action Budget**: Maximum number of actions to execute
3. Click **"🚀 Run Task"**
4. Watch real-time progress as the workflow executes
5. View captured states and screenshots when complete

### Viewing Datasets

1. Navigate to **"View Datasets"** in the sidebar
2. Browse all captured workflows
3. Use search and filters to find specific datasets
4. Click **"View Details"** to see:
   - State timeline visualization
   - Screenshot viewer with slider
   - Multi-viewport screenshots (desktop, mobile, tablet)
   - State metadata and actions

### Analytics

1. Navigate to **"Task Analytics"** in the sidebar
2. View overall metrics:
   - Total datasets and states
   - Unique apps
   - Average states per dataset
3. Explore visualizations:
   - App distribution pie chart
   - States distribution histogram

## Dashboard Pages

### Run New Task
- Execute new workflows
- Real-time progress tracking
- Plan visualization
- State preview after completion

### View Datasets
- Browse all captured workflows
- Search and filter datasets
- Detailed state viewer
- Screenshot timeline
- Multi-viewport support

### Task Analytics
- Overall metrics dashboard
- App distribution charts
- States distribution analysis
- Dataset statistics

## Configuration

The dashboard uses the same configuration as the CLI (`configs/config.yaml`):

- **Provider**: LLM provider (openai, local, auto)
- **Action Budget**: Maximum actions per workflow
- **Headless**: Browser visibility setting

## Tips

- Use the **search** feature to quickly find specific datasets
- The **state viewer** supports keyboard navigation with the slider
- **Screenshots** are displayed in full resolution - use the expand button for details
- **Analytics** update automatically as new datasets are created

## Troubleshooting

### Dashboard won't start
- Ensure Streamlit is installed: `pip install streamlit`
- Check that all dependencies are installed: `pip install -e .`

### Tasks fail to run
- Verify your API keys are set in `.env` or environment variables
- Check that Playwright browsers are installed: `playwright install`
- Review the error messages in the dashboard for specific issues

### No datasets showing
- Run a task first to create a dataset
- Check that the `datasets/` directory exists and is readable
- Verify dataset files are in the expected format

## Next Steps

- Customize the dashboard styling in `streamlit_dashboard.py`
- Add new visualizations in the analytics page
- Extend the state viewer with additional metadata
- Integrate with external monitoring tools

