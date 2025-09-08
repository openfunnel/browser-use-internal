"""
Anthropic Claude integration for GTM tasks
"""
import asyncio
from typing import List, Dict, Any
from .base import BaseLLM


class AnthropicLLM(BaseLLM):
	"""Claude Sonnet implementation"""
	
	def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
		self.api_key = api_key
		self.model = model
		self._client = None
	
	@property
	def client(self):
		if self._client is None:
			import anthropic
			self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
		return self._client
	
	async def generate(self, messages: List[Dict[str, str]]) -> str:
		"""Generate response from messages"""
		# Convert to Claude format
		claude_messages = []
		system_message = ""
		
		for msg in messages:
			if msg["role"] == "system":
				system_message = msg["content"]
			else:
				claude_messages.append({
					"role": msg["role"],
					"content": msg["content"]
				})
		
		response = await self.client.messages.create(
			model=self.model,
			max_tokens=4096,
			system=system_message,
			messages=claude_messages
		)
		
		return response.content[0].text
	
	async def extract_data(self, content: str, query: str) -> str:
		"""Extract specific data from content"""
		messages = [
			{
				"role": "system",
				"content": "Extract the requested information from the provided content. Be precise and only extract what is asked for. Return data in a clean, structured format."
			},
			{
				"role": "user", 
				"content": f"Query: {query}\n\nContent:\n{content}"
			}
		]
		
		return await self.generate(messages)