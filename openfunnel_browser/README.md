# OpenFunnel Browser

**Clean, minimal browser automation for GTM data extraction**

Built from the ground up for Go-to-Market teams who need reliable data extraction without the complexity of full browser automation frameworks.

## Features

✨ **Simple Interface**: Just URL + instructions → extracted data  
🧠 **Smart Reconnaissance**: Plans extraction strategy before executing  
📄 **Intelligent Pagination**: Automatically handles all page types  
🔄 **Loop Protection**: Prevents infinite loops and duplicate extraction  
🎯 **GTM Focused**: Only the 4 core actions you actually need  

## Core Actions

1. **Search**: Google search navigation
2. **Scroll**: Strategic page scrolling 
3. **Filter**: Input text for search/filter fields
4. **Paginate**: Smart pagination handling
5. **Extract**: LLM-powered data extraction
6. **Plan**: Reconnaissance planning

## Quick Start

```python
import asyncio
from openfunnel_browser import GTMAgent, AnthropicLLM

async def extract_data():
    # Initialize with Claude Sonnet
    llm = AnthropicLLM(api_key="your-key", model="claude-sonnet-4-20250514")
    agent = GTMAgent(llm)
    
    # Extract data with just URL + instructions
    result = await agent.extract(
        url="https://example.com/companies",
        instructions="Extract all company names and their locations"
    )
    
    return result['extraction']['consolidated_data']

# Run extraction
data = asyncio.run(extract_data())
print(data)
```

## Installation

```bash
pip install -r openfunnel_requirements.txt
```

## Requirements

- Chrome/Chromium browser
- Python 3.8+
- API key for Claude Sonnet (recommended) or OpenAI GPT

## Architecture

**Browser Session**: Minimal CDP wrapper for Chrome automation  
**LLM Integration**: Clean abstractions for Claude/GPT  
**GTM Tools**: 6 focused actions for data extraction  
**Reconnaissance Planner**: Smart website analysis before extraction  
**GTM Agent**: Orchestrates the complete extraction workflow  

## Why OpenFunnel Browser?

Unlike complex browser automation frameworks, OpenFunnel Browser is:

- **Focused**: Built specifically for GTM data extraction
- **Simple**: URL + instructions interface  
- **Smart**: Reconnaissance planning prevents wasted effort
- **Reliable**: Infinite loop protection and error handling
- **Clean**: Minimal codebase, easy to understand and modify

Perfect for GTM teams who need reliable data extraction without browser automation complexity.