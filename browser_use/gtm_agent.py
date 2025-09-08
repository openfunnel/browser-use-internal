"""
Specialized GTM (Go-to-Market) Data Extraction Agent
Automatically handles pagination, filtering, search, and scrolling to extract ALL data from websites
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from browser_use.agent.service import Agent
from browser_use.browser import BrowserSession
from browser_use.llm.base import BaseChatModel
from browser_use.tools.simple_tools import SimpleTools

logger = logging.getLogger(__name__)


class GTMAgent:
	"""Specialized agent for extracting company/business data with automatic pagination"""
	
	def __init__(
		self,
		llm: BaseChatModel,
		max_pages: int = 50,  # Safety limit
		extraction_query: str = "company names and details",
		debug: bool = False
	):
		self.llm = llm
		self.max_pages = max_pages
		self.extraction_query = extraction_query
		self.debug = debug
		self.tools = SimpleTools()
		self.extracted_data: List[Dict[str, Any]] = []
		
	async def extract_all_data(self, url: str) -> Dict[str, Any]:
		"""
		Extract ALL data from a paginated website
		
		Args:
			url: Target URL to extract data from
			
		Returns:
			Dictionary containing all extracted data and metadata
		"""
		logger.info(f"🚀 GTM Agent starting full extraction from: {url}")
		
		# Create specialized task for pagination
		task = self._build_pagination_task(url)
		
		# Create agent with GTM-optimized system prompt
		import os
		current_dir = os.path.dirname(__file__)
		gtm_prompt_path = os.path.join(current_dir, 'agent', 'system_prompt_gtm.md')
		
		agent = Agent(
			task=task,
			llm=self.llm,
			controller=self.tools,
			system_prompt_file_path=gtm_prompt_path,
		)
		
		# Execute extraction
		try:
			result = await agent.run()
			
			# Process and structure results
			structured_result = self._process_results(result, url)
			
			logger.info(f"✅ GTM extraction completed. Found data across {structured_result['pages_processed']} pages")
			return structured_result
			
		except Exception as e:
			logger.error(f"❌ GTM extraction failed: {e}")
			raise
	
	def _build_pagination_task(self, url: str) -> str:
		"""Build universal GTM task prompt"""
		return f"""
UNIVERSAL GTM DATA EXTRACTION:

Target URL: {url}
Extract: {self.extraction_query}

EXECUTION PROTOCOL:
1. Navigate to target URL
2. Analyze page structure and available filters
3. Apply any relevant filters (date ranges, categories, types, etc.)
4. Scroll to ensure all content is loaded
5. Extract data from current page using extract_structured_data
6. Detect pagination controls using detect_pagination  
7. Navigate through ALL pages systematically
8. Continue until no more pages exist
9. Consolidate complete dataset from all pages

CRITICAL SUCCESS FACTORS:
✅ Process ALL available pages (never stop at page 1)
✅ Apply filters before extraction when available
✅ Handle any pagination pattern (buttons, numbers, load more)
✅ Extract complete, clean dataset
✅ Verify no pages were missed

Max Pages: {self.max_pages}
"""

	def _get_gtm_system_prompt(self) -> str:
		"""Get specialized system prompt for GTM data extraction"""
		return """
You are a SPECIALIZED GTM DATA EXTRACTION AGENT.

Your core expertise:
- AUTOMATIC PAGINATION HANDLING across all website types
- Complete data extraction from multi-page listings  
- Intelligent filtering and search within websites
- Comprehensive scrolling and content discovery

PAGINATION MASTERY:
- Always assume websites have multiple pages of data
- Automatically detect and handle ALL pagination patterns:
  * Next/Previous buttons
  * Numbered page links  
  * "Load More" buttons
  * Infinite scroll
  * Dynamic loading
- Never stop at page 1 - always check for more pages
- Consolidate data from ALL pages before completing task

EXTRACTION PROTOCOLS:
- Scroll through entire page before extracting
- Use structured data extraction for clean results
- Handle dynamic content loading
- Filter out duplicate entries across pages
- Maintain data integrity across page transitions

TOOLS SPECIALIZATION:
- go_to_url: Navigate to target pages
- scroll: Ensure all content is loaded
- click_element: Handle pagination controls
- extract_structured_data: Extract clean, structured data
- input_text: Use site search/filters when available
- dropdown operations: Handle filter controls

SUCCESS CRITERIA:
✅ Processed ALL available pages
✅ Extracted complete dataset
✅ No pagination opportunities missed
✅ Clean, consolidated results

Remember: You are optimized for COMPLETE data extraction, not partial results.
"""

	def _process_results(self, agent_result, url: str) -> Dict[str, Any]:
		"""Process agent results into structured format"""
		
		# Extract final data from agent results
		final_data = []
		pages_processed = 0
		
		if hasattr(agent_result, 'all_results'):
			for result in agent_result.all_results:
				if result.extracted_content and 'company' in result.extracted_content.lower():
					# This is likely extracted company data
					final_data.append(result.extracted_content)
				
				# Count pagination actions
				if hasattr(result, 'long_term_memory') and result.long_term_memory:
					if 'page' in result.long_term_memory.lower() or 'next' in result.long_term_memory.lower():
						pages_processed += 1
		
		# Structure final results
		return {
			'url': url,
			'extraction_query': self.extraction_query,
			'total_entries': len(final_data),
			'pages_processed': max(1, pages_processed),
			'data': final_data,
			'status': 'completed',
			'raw_agent_result': agent_result
		}

# Convenience function for quick GTM extractions
async def extract_gtm_data(
	url: str,
	llm: BaseChatModel,
	extraction_query: str = "company names and details",
	max_pages: int = 50
) -> Dict[str, Any]:
	"""
	Quick function to extract GTM data from any paginated website
	
	Args:
		url: Website URL to extract from
		llm: Language model to use
		extraction_query: What data to extract (default: company names)
		max_pages: Maximum pages to process (safety limit)
		
	Returns:
		Complete extraction results with metadata
	"""
	agent = GTMAgent(
		llm=llm,
		max_pages=max_pages,
		extraction_query=extraction_query
	)
	
	return await agent.extract_all_data(url)