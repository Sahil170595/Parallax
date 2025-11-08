# Usage Scenario Test Files

This directory contains individual test files for each usage scenario from the documentation.

## Test Files

1. **test_scenario_01_example_com.py** - Navigate to example.com and show the page
2. **test_scenario_02_wikipedia.py** - Search for Python programming language on Wikipedia
3. **test_scenario_03_linear_create.py** - Create a project in Linear (requires authentication)
4. **test_scenario_03_linear_create_chrome.py** - Create a project in Linear using Chrome (requires authentication)
5. **test_scenario_03_linear_free.py** - Explore Linear website (no authentication required)
6. **test_scenario_04_notion_create.py** - Create a new page in Notion (requires authentication)
7. **test_scenario_04_notion_create_chrome.py** - Create a new page in Notion using Chrome (requires authentication)
8. **test_scenario_04_notion_free.py** - Explore Notion website (no authentication required)
9. **test_scenario_05_linear_filter.py** - Filter issues by status in Linear (requires authentication)

## Usage

Run each scenario individually:

```bash
# Windows
python test_scenario_01_example_com.py
python test_scenario_02_wikipedia.py
python test_scenario_03_linear_create.py
python test_scenario_04_notion_create.py
python test_scenario_05_linear_filter.py

# Linux/Mac
python3 test_scenario_01_example_com.py
python3 test_scenario_02_wikipedia.py
python3 test_scenario_03_linear_create.py
python3 test_scenario_04_notion_create.py
python3 test_scenario_05_linear_filter.py
```

## Notes

- Each scenario runs independently
- Results are saved to `datasets/{app-name}/{task-slug}/`
- Some scenarios may require API keys (OpenAI or Anthropic)
- Some scenarios may require authentication (Linear, Notion)
  - For authenticated workflows, run `python authenticate.py linear` (or `notion`) first
  - Then configure `user_data_dir` in `configs/config.yaml` or use the `*_chrome.py` test files
- Chrome test files (`*_chrome.py`) use installed Chrome browser for better compatibility
- Free test files (`*_free.py`) explore public pages without authentication



