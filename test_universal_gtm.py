#!/usr/bin/env python3
"""
Simple GTM Agent Test with Claude Sonnet
Just URL + instructions
"""
import asyncio
import os
from browser_use.simple_gtm_agent import SimpleGTMAgent

async def test_simple_gtm():
	# Check API keys - try Claude first, fallback to OpenAI
	anthropic_key = os.getenv('ANTHROPIC_API_KEY')
	openai_key = os.getenv('OPENAI_API_KEY')
	
	if anthropic_key:
		print("🧠 Using Claude Sonnet 3.5 (Best Model)")
		from browser_use.llm import ChatAnthropic
		llm = ChatAnthropic(
			model='claude-sonnet-4-20250514',  # Latest Claude Sonnet
			api_key=anthropic_key,
			max_tokens=4096
		)
	elif openai_key:
		print("🤖 Using GPT-4o-mini (Fallback)")
		from browser_use import ChatOpenAI
		llm = ChatOpenAI(model='gpt-4o-mini')
	else:
		print("⚠️  No API keys found!")
		print("Set ANTHROPIC_API_KEY for Claude Sonnet (recommended)")
		print("Or set OPENAI_API_KEY for GPT-4o-mini")
		return

	print("🎯 Smart GTM Agent with Infinite Loop Protection!")
	
	# Create simple GTM agent
	gtm_agent = SimpleGTMAgent(llm)
	
	# Test case: 13F filing data
	url = "https://13f.info/form-d?from=2025-08-01&to=2025-08-17&types=other+technology&forms=D"
	instructions = "Extract all company names from this page. Make sure to go through ALL pages of results, not just the first page. Return a complete list of all company names found."
	
	print(f"\n📋 URL: {url}")
	print(f"📝 Instructions: {instructions}")
	print("\n" + "="*60)
	print("🚀 Starting extraction...")
	print("="*60)
	
	try:
		# Simple extraction with just URL + instructions
		result = await gtm_agent.extract(url, instructions)
		
		print("\n✅ Extraction completed!")
		print("="*60)
		print("📊 RESULTS:")
		print("="*60)
		print(result)
		
	except Exception as e:
		print(f"❌ Extraction failed: {e}")

if __name__ == '__main__':
	asyncio.run(test_simple_gtm())