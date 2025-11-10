# Changelog

All notable changes to Parallax will be documented in this file.

## [0.1.0] - 2025-11-10

### Added
- Initial release of Parallax multi-agent web automation system
- Four-agent architecture: Interpreter, Navigator, Observer, Archivist
- Natural language task execution with LLM planning
- Multi-viewport screenshot capture (desktop, tablet, mobile)
- Constitution system for quality validation
- Vision-based enhancements for element location fallback
- Multiple output formats: JSONL, SQLite, HTML reports
- Streamlit dashboard for workflow management
- Immersive dashboard for dataset visualization
- Cost tracking for LLM API usage
- Prometheus metrics for observability
- Authentication support with persistent browser contexts
- Comprehensive error handling and retry logic

### Features
- **Interpreter Agent**: Converts natural language → execution plans using GPT-4.1-mini
- **Navigator Agent**: Executes plans with Playwright, handles SPAs, modals, retries
- **Observer Agent**: Captures UI states with multi-viewport screenshots
- **Archivist Agent**: Organizes data into queryable datasets
- **Vision Support**: Optional vision LLM (gpt-4o-mini) for element location fallback
- **Constitution System**: Quality gates ensure reliable outputs
- **Strategy Learning**: Learns from failures to improve future workflows

### Configuration
- Default LLM: `gpt-4.1-mini` (cost-effective, reliable)
- Default vision: `gpt-4o-mini` (enabled by default)
- Max tokens: 2000 (increased for complex workflows)
- Temperature: 0.2 (deterministic output)
- Vision enabled: `true` (fallback for hard-to-locate elements)

### Known Limitations
- Some websites with poor ARIA structure may not be automatable
- Google search workflows may fail due to anti-bot protection
- Authentication required for Linear/Notion workflows
- GPT-5 not recommended (doesn't support temperature control)

### Documentation
- Complete API documentation
- Architecture guide
- Configuration reference
- Quick start guide
- Authentication guide
- FAQ
- Contributing guidelines


