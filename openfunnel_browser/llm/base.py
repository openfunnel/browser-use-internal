"""
Base LLM interface for GTM tasks
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseLLM(ABC):
	"""Base class for LLM implementations"""
	
	@abstractmethod
	async def generate(self, messages: List[Dict[str, str]]) -> str:
		"""Generate response from messages"""
		pass
	
	@abstractmethod
	async def extract_data(self, content: str, query: str) -> str:
		"""Extract specific data from content"""
		pass