#!/usr/bin/env python3
"""
Simple browser-use test script
Run with: uv run python simple_test.py
"""
import asyncio
import os
from browser_use import Agent, ChatOpenAI

async def main():
	# Check if API key is set
	api_key = os.getenv('OPENAI_API_KEY')
	if not api_key:
		print("⚠️  OPENAI_API_KEY not found in environment")
		print("Set it with: export OPENAI_API_KEY='your-key-here'")
		return

	print("🚀 Starting browser automation test...")
	
	# Create LLM instance
	llm = ChatOpenAI(model='gpt-4o-mini')
	
	# Simple task
	task = "Go to google.com and search for 'python automation'. Tell me what the first result title is."
	
	# Create and run agent
	agent = Agent(task=task, llm=llm)
	result = await agent.run()
	
	print("✅ Task completed!")
	print(f"Result: {result}")

if __name__ == '__main__':
	asyncio.run(main())