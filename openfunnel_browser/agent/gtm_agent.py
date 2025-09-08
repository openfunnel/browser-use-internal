"""
GTM Agent - Clean, focused data extraction agent
Only URL + instructions → extracted data
"""
import asyncio
import logging
from typing import Dict, Any
from ..browser.session import BrowserSession
from ..llm.base import BaseLLM
from ..tools.gtm_tools import GTMTools
from ..tools.planner import ReconnaissancePlanner

logger = logging.getLogger(__name__)


class GTMAgent:
	"""GTM-focused data extraction agent"""
	
	def __init__(self, llm: BaseLLM, headless: bool = True):
		self.llm = llm
		self.headless = headless
		self.browser = None
		self.tools = None
		self.planner = None
	
	async def extract(self, url: str, instructions: str) -> Dict[str, Any]:
		"""
		Extract data from URL using instructions
		
		Args:
			url: Target website URL
			instructions: What to extract
			
		Returns:
			Extraction results with data and metadata
		"""
		logger.info(f"🎯 GTM Agent starting extraction from: {url}")
		logger.info(f"📝 Instructions: {instructions}")
		
		try:
			# Start browser session
			self.browser = BrowserSession(headless=self.headless)
			await self.browser.start()
			
			# Initialize tools
			self.tools = GTMTools(self.browser, self.llm)
			self.planner = ReconnaissancePlanner(self.browser, self.llm)
			
			# STEP 1: Navigate to URL
			await self.tools.navigate_to_url(url)
			
			# STEP 2: MANDATORY RECONNAISSANCE
			logger.info("🕵️ Starting reconnaissance planning...")
			recon_result = await self.planner.create_extraction_plan(instructions)
			
			if recon_result['status'] == 'completed':
				logger.info("✅ Reconnaissance completed - executing plan...")
				
				# STEP 3: Execute extraction based on plan
				extraction_result = await self._execute_extraction_plan(instructions, recon_result)
				
				return {
					"url": url,
					"instructions": instructions,
					"reconnaissance": recon_result,
					"extraction": extraction_result,
					"status": "completed"
				}
			else:
				logger.error("❌ Reconnaissance failed, falling back to direct extraction")
				# Fallback: direct extraction without plan
				extraction_result = await self.tools.smart_paginate_and_extract(instructions)
				
				return {
					"url": url,
					"instructions": instructions,
					"reconnaissance": recon_result,
					"extraction": extraction_result,
					"status": "completed_with_fallback"
				}
				
		except Exception as e:
			logger.error(f"❌ GTM extraction failed: {e}")
			return {
				"url": url,
				"instructions": instructions,
				"status": "failed",
				"error": str(e)
			}
		finally:
			# Clean up browser session
			if self.browser:
				await self.browser.close()
	
	async def _execute_extraction_plan(self, instructions: str, recon_result: Dict[str, Any]) -> Dict[str, Any]:
		"""Execute extraction based on reconnaissance plan"""
		logger.info("🚀 Executing reconnaissance-guided extraction...")
		
		try:
			# NUCLEAR OPTION: If instructions mention "ALL pages", force multi-page
			force_multipage_keywords = ['all pages', 'all results', 'every page', 'each page', 'through all', 'not just the first page']
			force_multipage = any(keyword in instructions.lower() for keyword in force_multipage_keywords)
			
			if force_multipage:
				logger.info("🚨 *** NUCLEAR OPTION TRIGGERED ***")
				logger.info(f"   Instructions contain multi-page keywords: {instructions}")
				logger.info("   🚀 FORCING MULTI-PAGE EXTRACTION REGARDLESS OF DETECTION")
				return await self.tools.smart_paginate_and_extract(instructions, max_pages=20)
			
			# Check if pagination was detected by reconnaissance
			pagination_analysis = recon_result.get('pagination_analysis', {})
			pagination_found = pagination_analysis.get('pagination_found', False)
			pagination_candidates = pagination_analysis.get('total_candidates', 0)
			
			# Debug logging
			logger.info(f"🔍 DEBUGGING Pagination Analysis:")
			logger.info(f"   - pagination_found: {pagination_found}")
			logger.info(f"   - total_candidates: {pagination_candidates}")
			logger.info(f"   - method_used: {pagination_analysis.get('method_used', 'N/A')}")
			logger.info(f"   - current_page: {pagination_analysis.get('current_page', 'N/A')}")
			logger.info(f"   - total_pages: {pagination_analysis.get('total_pages', 'N/A')}")
			
			# Try manual pagination detection 
			manual_pagination_check = await self.tools.detect_pagination()
			logger.info(f"🔍 Manual pagination check:")
			logger.info(f"   - Found: {manual_pagination_check.get('pagination_found', False)}")
			logger.info(f"   - Method: {manual_pagination_check.get('method_used', 'N/A')}")
			logger.info(f"   - Elements: {len(manual_pagination_check.get('pagination_elements', []))}")
			
			# If EITHER reconnaissance OR manual check finds pagination, use multi-page
			if (pagination_found or pagination_candidates > 0 or 
				manual_pagination_check.get('pagination_found', False)):
				
				logger.info("🚀 *** USING MULTI-PAGE EXTRACTION ***")
				logger.info("   Reasons:")
				if pagination_found:
					logger.info(f"   ✓ Reconnaissance found pagination")
				if pagination_candidates > 0:
					logger.info(f"   ✓ Reconnaissance found {pagination_candidates} candidates")
				if manual_pagination_check.get('pagination_found', False):
					logger.info(f"   ✓ Manual check found pagination")
				
				# FORCE multi-page extraction
				return await self.tools.smart_paginate_and_extract(instructions, max_pages=20)
				
			else:
				logger.info("📄 NO PAGINATION DETECTED BY ANY METHOD - single page extraction")
				logger.info(f"   - Reconnaissance: {pagination_found}")
				logger.info(f"   - Manual check: {manual_pagination_check.get('pagination_found', False)}")
				# Single page extraction with strategic scrolling
				
				# Scroll through different sections to capture all content
				await self.tools.scroll_page("up", 5)  # Go to top
				await asyncio.sleep(1)
				
				top_data = await self.tools.extract_data(f"{instructions} (top section)")
				
				await self.tools.scroll_page("down", 3)  # Middle
				await asyncio.sleep(1)
				
				middle_data = await self.tools.extract_data(f"{instructions} (middle section)")
				
				await self.tools.scroll_page("down", 5)  # Bottom
				await asyncio.sleep(1)
				
				bottom_data = await self.tools.extract_data(f"{instructions} (bottom section)")
				
				# Combine all sections
				consolidated_data = []
				for section_data in [top_data, middle_data, bottom_data]:
					if section_data['status'] == 'completed' and section_data.get('extracted_content'):
						consolidated_data.append(section_data['extracted_content'])
				
				combined_content = "\\n\\n".join(consolidated_data)
				
				return {
					"action": "single_page_extraction",
					"instructions": instructions,
					"sections_processed": len(consolidated_data),
					"consolidated_data": combined_content,
					"detailed_sections": [top_data, middle_data, bottom_data],
					"status": "completed"
				}
				
		except Exception as e:
			logger.error(f"❌ Plan execution failed: {e}")
			return {
				"action": "execute_extraction_plan",
				"status": "failed",
				"error": str(e)
			}


# Simple function interface for easy usage
async def extract_gtm_data(url: str, instructions: str, llm: BaseLLM, headless: bool = True) -> Dict[str, Any]:
	"""
	Simple function to extract GTM data
	
	Args:
		url: Website URL
		instructions: What to extract
		llm: Language model instance
		headless: Run browser in headless mode
		
	Returns:
		Extraction results
	"""
	agent = GTMAgent(llm, headless=headless)
	return await agent.extract(url, instructions)