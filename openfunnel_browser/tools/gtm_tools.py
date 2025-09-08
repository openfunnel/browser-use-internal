"""
GTM Tools - Only the essential 4 actions + extraction
Clean, focused implementation for data extraction tasks
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from ..browser.session import BrowserSession
from ..llm.base import BaseLLM

logger = logging.getLogger(__name__)


class GTMTools:
	"""GTM-focused browser automation tools"""
	
	def __init__(self, browser_session: BrowserSession, llm: BaseLLM):
		self.browser = browser_session
		self.llm = llm
		self.visited_urls = set()
		self.extracted_data = []
	
	async def search_google(self, query: str) -> Dict[str, Any]:
		"""Search Google and navigate to results"""
		search_url = f"https://www.google.com/search?q={query}&udm=14"
		await self.browser.navigate(search_url)
		
		return {
			"action": "search_google",
			"query": query,
			"url": search_url,
			"status": "completed"
		}
	
	async def navigate_to_url(self, url: str) -> Dict[str, Any]:
		"""Navigate to specific URL"""
		await self.browser.navigate(url)
		current_url = await self.browser.get_current_url()
		
		return {
			"action": "navigate",
			"target_url": url,
			"actual_url": current_url,
			"status": "completed"
		}
	
	async def scroll_page(self, direction: str = "down", amount: int = 3) -> Dict[str, Any]:
		"""Scroll page up or down"""
		pixels = amount * 1000  # Convert pages to pixels
		await self.browser.scroll(direction, pixels)
		
		return {
			"action": "scroll",
			"direction": direction,
			"amount": f"{amount} pages ({pixels} pixels)",
			"status": "completed"
		}
	
	async def scroll_to_bottom(self) -> Dict[str, Any]:
		"""Instantly scroll to the very bottom of the page"""
		await self.browser.scroll_to_bottom()
		
		return {
			"action": "scroll_to_bottom",
			"description": "Scrolled instantly to bottom of page",
			"status": "completed"
		}
	
	async def scroll_to_top(self) -> Dict[str, Any]:
		"""Instantly scroll to the very top of the page"""
		await self.browser.scroll_to_top()
		
		return {
			"action": "scroll_to_top", 
			"description": "Scrolled instantly to top of page",
			"status": "completed"
		}
	
	async def filter_search(self, input_selector: str, filter_text: str) -> Dict[str, Any]:
		"""Input text into search/filter fields"""
		success = await self.browser.type_text(input_selector, filter_text, clear=True)
		
		return {
			"action": "filter_search",
			"selector": input_selector,
			"text": filter_text,
			"status": "completed" if success else "failed"
		}
	
	async def click_pagination(self, selector: str) -> Dict[str, Any]:
		"""Click pagination elements (Next, page numbers, etc.)"""
		success = await self.browser.click_element(selector)
		
		if success:
			# Wait for navigation and check if URL changed
			await asyncio.sleep(3)
			current_url = await self.browser.get_current_url()
			
			return {
				"action": "click_pagination",
				"selector": selector,
				"new_url": current_url,
				"status": "completed"
			}
		else:
			return {
				"action": "click_pagination", 
				"selector": selector,
				"status": "failed"
			}
	
	async def extract_data(self, query: str) -> Dict[str, Any]:
		"""Extract structured data from current page"""
		try:
			# Get page content
			page_text = await self.browser.get_page_text()
			current_url = await self.browser.get_current_url()
			
			# Truncate if too long
			if len(page_text) > 15000:
				page_text = page_text[:15000] + "\\n[Content truncated...]"
			
			# Use LLM to extract data
			extracted_content = await self.llm.extract_data(page_text, query)
			
			# Store extraction result
			result = {
				"action": "extract_data",
				"url": current_url,
				"query": query,
				"extracted_content": extracted_content,
				"content_length": len(page_text),
				"status": "completed"
			}
			
			self.extracted_data.append(result)
			logger.info(f"📄 Extracted data from {current_url}")
			
			return result
			
		except Exception as e:
			logger.error(f"❌ Data extraction failed: {e}")
			return {
				"action": "extract_data",
				"query": query,
				"status": "failed",
				"error": str(e)
			}
	
	async def detect_pagination(self) -> Dict[str, Any]:
		"""Detect pagination controls on current page"""
		try:
			# Scroll directly to bottom to find pagination (much faster)
			await self.browser.scroll_to_bottom()
			await asyncio.sleep(1)
			
			# Look for common pagination selectors
			pagination_selectors = [
				'a[aria-label*="next" i]',
				'a[aria-label*="Next" i]', 
				'button[aria-label*="next" i]',
				'a:contains("Next")',
				'a:contains(">")',
				'a:contains("→")',
				'.pagination a',
				'.pager a',
				'[class*="next"]',
				'[class*="pagination"]'
			]
			
			found_pagination = []
			
			for selector in pagination_selectors:
				elements = await self.browser.find_elements(selector)
				if elements:
					for elem in elements:
						if elem['visible'] and ('next' in elem['text'].lower() or '>' in elem['text']):
							found_pagination.append({
								'selector': selector,
								'text': elem['text'][:50],
								'tag': elem['tag']
							})
			
			return {
				"action": "detect_pagination",
				"pagination_found": len(found_pagination) > 0,
				"pagination_elements": found_pagination[:5],  # Top 5 candidates
				"status": "completed"
			}
			
		except Exception as e:
			logger.error(f"❌ Pagination detection failed: {e}")
			return {
				"action": "detect_pagination",
				"status": "failed", 
				"error": str(e)
			}
	
	async def smart_paginate_and_extract(self, query: str, max_pages: int = 10) -> Dict[str, Any]:
		"""Intelligently paginate through all pages and extract data"""
		logger.info(f"🧠 Starting smart pagination for: {query}")
		
		all_extractions = []
		current_page = 1
		consecutive_failures = 0
		visited_urls = set()
		
		while current_page <= max_pages and consecutive_failures < 3:
			try:
				current_url = await self.browser.get_current_url()
				
				# Check if we've seen this URL before (infinite loop detection)
				if current_url in visited_urls:
					logger.warning(f"🔄 Already visited {current_url}, stopping pagination")
					break
				
				visited_urls.add(current_url)
				
				logger.info(f"📄 Processing page {current_page}: {current_url}")
				
				# Extract data from current page
				extraction_result = await self.extract_data(query)
				
				if extraction_result['status'] == 'completed':
					all_extractions.append(extraction_result)
					consecutive_failures = 0
					logger.info(f"✅ Successfully extracted data from page {current_page}")
				else:
					consecutive_failures += 1
					logger.warning(f"⚠️ Failed to extract from page {current_page}")
				
				# Try to find and click next page
				pagination_info = await self.detect_pagination()
				
				if not pagination_info['pagination_found']:
					logger.info(f"🏁 No more pagination found, stopping at page {current_page}")
					break
				
				# Try clicking the first pagination element
				clicked_next = False
				for pag_elem in pagination_info['pagination_elements']:
					result = await self.click_pagination(pag_elem['selector'])
					if result['status'] == 'completed':
						clicked_next = True
						logger.info(f"🖱️ Successfully clicked pagination: {pag_elem['text']}")
						break
				
				if not clicked_next:
					logger.info(f"❌ Could not click any pagination elements, stopping")
					break
				
				current_page += 1
				await asyncio.sleep(3)  # Wait between pages
				
			except Exception as e:
				consecutive_failures += 1
				logger.error(f"❌ Page {current_page} failed: {e}")
				if consecutive_failures >= 3:
					break
		
		# Consolidate all extracted data
		consolidated_data = "\\n\\n".join([
			f"PAGE {i+1} ({ext['url']}):\\n{ext['extracted_content']}"
			for i, ext in enumerate(all_extractions)
			if ext.get('extracted_content')
		])
		
		return {
			"action": "smart_paginate_and_extract",
			"query": query,
			"pages_processed": current_page - 1,
			"successful_extractions": len(all_extractions),
			"consolidated_data": consolidated_data,
			"all_extractions": all_extractions,
			"status": "completed"
		}