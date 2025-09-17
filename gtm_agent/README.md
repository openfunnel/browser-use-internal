# GTM Agent

A Playwright + LLM powered browser agent focused on extracting company names from arbitrary web pages for go-to-market workflows.

## Features

- Modular tool system combining DOM, action, vision, and inference capabilities
- Configurable orchestration loop for sense → reason → act automation
- JSON-formatted output capturing company names with optional context

## Getting Started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
playwright install chromium
```

Then run tests to verify the base scaffolding:

```bash
pytest
```
