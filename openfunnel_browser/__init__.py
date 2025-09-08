"""
OpenFunnel Browser - GTM-focused browser automation
Minimal, clean implementation for data extraction tasks
"""

from .agent.gtm_agent import GTMAgent
from .llm.base import BaseLLM
from .llm.anthropic import AnthropicLLM
from .llm.openai import OpenAILLM

__version__ = "0.1.0"

__all__ = [
	"GTMAgent",
	"BaseLLM", 
	"AnthropicLLM",
	"OpenAILLM"
]