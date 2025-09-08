#!/usr/bin/env python3
"""
Test simplified browser-use tools to extract company names from 13f.info
Task: Get all company names from https://13f.info/form-d?from=2025-08-01&to=2025-08-17&types=other+technology&forms=D
"""
import asyncio
import os
from browser_use import Agent, ChatOpenAI
from browser_use.tools.simple_tools import SimpleTools

async def main():
	# Check API key
	api_key = os.getenv('OPENAI_API_KEY')
	if not api_key:
		print("⚠️  OPENAI_API_KEY not found")
		print("Set it with: export OPENAI_API_KEY='your-key-here'")
		return

	print("🚀 Testing simplified tools: Company name extraction from 13f.info")
	
	# Create LLM instance
	llm = ChatOpenAI(model='gpt-4o-mini')
	
	# Create simplified tools
	simple_tools = SimpleTools()
	
	# Task: Extract company names from the specific URL
	task = """
	Navigate to https://13f.info/form-d?from=2025-08-01&to=2025-08-17&types=other+technology&forms=D
	
	Once on the page, extract ALL company names listed on this page.
	
	Use these steps:
	1. Navigate to the URL
	2. Let the page fully load
	3. Scroll through the entire page to see all results
	4. Extract all company names from the listings
	5. Return a complete list of company names found
	
	Focus only on getting the company names - ignore other details.
	"""
	
	# Create agent with simplified tools
	agent = Agent(
		task=task, 
		llm=llm,
		controller=simple_tools  # Use our simplified tools
	)
	
	print("📋 Starting extraction...")
	result = await agent.run()
	
	print("\n✅ Company extraction completed!")
	print("=" * 50)
	print("RESULTS:")
	print("=" * 50)
	
	if result and hasattr(result, 'all_results'):
		for action_result in result.all_results:
			if action_result.is_done and action_result.extracted_content:
				print(action_result.extracted_content)
				break
	else:
		print(f"Raw result: {result}")

if __name__ == '__main__':
	asyncio.run(main())