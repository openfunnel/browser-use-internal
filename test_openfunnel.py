#!/usr/bin/env python3
"""
Test script for OpenFunnel Browser GTM Agent
Clean, minimal implementation with just URL + instructions
"""
import asyncio
import logging
import os
from openfunnel_browser import GTMAgent, AnthropicLLM, OpenAILLM

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def main():
	"""Test the OpenFunnel GTM Agent"""
	
	# Check API keys and initialize LLM
	anthropic_key = os.getenv('ANTHROPIC_API_KEY')
	openai_key = os.getenv('OPENAI_API_KEY')
	
	if anthropic_key:
		print("🧠 Using Claude Sonnet 4 (Best Model)")
		llm = AnthropicLLM(api_key=anthropic_key, model='claude-sonnet-4-20250514')
	elif openai_key:
		print("🤖 Using GPT-4o-mini (Fallback)")
		llm = OpenAILLM(api_key=openai_key, model='gpt-4o-mini')
	else:
		print("⚠️  No API keys found!")
		print("Set ANTHROPIC_API_KEY for Claude Sonnet (recommended)")
		print("Or set OPENAI_API_KEY for GPT-4o-mini")
		return
	
	print("🎯 OpenFunnel GTM Agent Test!")
	print("=" * 60)
	
	# Test case
	url = "https://13f.info/form-d?from=2025-08-01&to=2025-08-17&types=other+technology&forms=D"
	instructions = "Extract all company names from this page. Make sure to go through ALL pages of results, not just the first page."
	
	print(f"📍 URL: {url}")
	print(f"📝 Instructions: {instructions}")
	print("\\n" + "=" * 60)
	print("🚀 Starting extraction...")
	print("=" * 60)
	
	try:
		# Create and run GTM agent (headful so you can see what's happening)
		agent = GTMAgent(llm, headless=False)
		result = await agent.extract(url, instructions)
		
		print("\\n✅ Extraction completed!")
		print("=" * 60)
		print("📊 RESULTS:")
		print("=" * 60)
		
		# Display results
		if result['status'] == 'completed':
			print(f"🎯 Status: {result['status']}")
			
			if 'reconnaissance' in result:
				recon = result['reconnaissance']
				print(f"🕵️ Reconnaissance: {recon.get('status', 'N/A')}")
				if recon.get('pagination_analysis'):
					pag_info = recon['pagination_analysis']
					print(f"📄 Pagination Found: {pag_info.get('pagination_found', False)}")
					print(f"📄 Candidates: {pag_info.get('total_candidates', 0)}")
			
			if 'extraction' in result:
				extraction = result['extraction']
				print(f"📊 Extraction Status: {extraction.get('status', 'N/A')}")
				
				if 'pages_processed' in extraction:
					print(f"📄 Pages Processed: {extraction['pages_processed']}")
					print(f"✅ Successful Extractions: {extraction.get('successful_extractions', 0)}")
				
				# Show extracted data
				if extraction.get('consolidated_data'):
					print("\\n📋 EXTRACTED DATA:")
					print("-" * 40)
					print(extraction['consolidated_data'])
				elif extraction.get('consolidated_data') == '':  # Empty but present
					print("\\n⚠️ No data found matching the query")
				else:
					print("\\n⚠️ No consolidated data available")
		else:
			print(f"❌ Extraction failed: {result.get('error', 'Unknown error')}")
		
	except Exception as e:
		print(f"💥 Test failed with error: {e}")
		import traceback
		traceback.print_exc()


if __name__ == '__main__':
	asyncio.run(main())