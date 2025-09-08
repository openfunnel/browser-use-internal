#!/usr/bin/env python3
"""
Test GTM Agent for extracting ALL company data with automatic pagination
URL: https://13f.info/form-d?from=2025-08-01&to=2025-08-17&types=other+technology&forms=D
"""
import asyncio
import os
from browser_use import ChatOpenAI
from browser_use.gtm_agent import GTMAgent

async def main():
	# Check API key
	api_key = os.getenv('OPENAI_API_KEY')
	if not api_key:
		print("⚠️  OPENAI_API_KEY not found")
		print("Set it with: export OPENAI_API_KEY='your-key-here'")
		return

	print("🚀 GTM Agent: Extracting ALL company data with auto-pagination")
	
	# Create LLM instance
	llm = ChatOpenAI(model='gpt-4o-mini')
	
	# Target URL
	url = "https://13f.info/form-d?from=2025-08-01&to=2025-08-17&types=other+technology&forms=D"
	
	# Create GTM agent specialized for company data extraction
	gtm_agent = GTMAgent(
		llm=llm,
		extraction_query="company names and business details",
		max_pages=10,  # Safety limit
		debug=True
	)
	
	print(f"📋 Starting GTM extraction from: {url}")
	print("🔄 Agent will automatically handle pagination...")
	
	try:
		# Extract ALL data across ALL pages
		results = await gtm_agent.extract_all_data(url)
		
		print("\n✅ GTM Extraction completed!")
		print("=" * 60)
		print("RESULTS SUMMARY:")
		print("=" * 60)
		print(f"📊 Total entries found: {results['total_entries']}")
		print(f"📄 Pages processed: {results['pages_processed']}")
		print(f"🎯 Extraction query: {results['extraction_query']}")
		print(f"📝 Status: {results['status']}")
		
		print("\n" + "=" * 60)
		print("EXTRACTED DATA:")
		print("=" * 60)
		
		for i, data_entry in enumerate(results['data'], 1):
			print(f"\n--- Entry {i} ---")
			print(data_entry[:500] + "..." if len(str(data_entry)) > 500 else data_entry)
		
	except Exception as e:
		print(f"❌ GTM extraction failed: {e}")
		raise

if __name__ == '__main__':
	asyncio.run(main())