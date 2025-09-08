"""
OpenAI GPT integration for GTM tasks
"""
import asyncio
from typing import List, Dict, Any
from .base import BaseLLM


class OpenAILLM(BaseLLM):
	"""OpenAI GPT implementation"""
	
	def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
		self.api_key = api_key
		self.model = model
		self._client = None
	
	@property
	def client(self):
		if self._client is None:
			import openai
			self._client = openai.AsyncOpenAI(api_key=self.api_key)
		return self._client
	
	async def generate(self, messages: List[Dict[str, str]]) -> str:
		"""Generate response from messages"""
		response = await self.client.chat.completions.create(
			model=self.model,
			messages=messages,
			max_tokens=4096,
			temperature=0.1
		)
		
		return response.choices[0].message.content
	
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