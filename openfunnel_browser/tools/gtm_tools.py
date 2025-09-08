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
	
	async def detect_pagination_llm(self) -> Dict[str, Any]:
		"""Detect pagination using LLM analysis of page content - more reliable!"""
		try:
			logger.info("🧠 Using LLM-based pagination detection...")
			
			# Get page text content 
			page_text = await self.browser.get_page_text()
			current_url = await self.browser.get_current_url()
			
			# Focus on the end of the page where pagination usually is
			if len(page_text) > 8000:
				page_sample = page_text[:2000] + "\n\n[...content truncated...]\n\n" + page_text[-4000:]
			else:
				page_sample = page_text
			
			# LLM analysis prompt
			pagination_prompt = f"""Analyze this webpage content to detect pagination controls.

URL: {current_url}

WEBPAGE CONTENT:
{page_sample}

Look for pagination patterns like "← Previous 1 2 3 4 Next →", "Page 1 of 5", "Next" buttons, etc.

Answer:
PAGINATION_FOUND: Yes/No
CURRENT_PAGE: X
TOTAL_PAGES: X or Unknown  
NEXT_ELEMENTS: Next, 2, 3, etc
REASONING: Brief explanation"""
			
			llm_response = await self.llm.generate([{"role": "user", "content": pagination_prompt}])
			
			# Parse LLM response
			pagination_found = "PAGINATION_FOUND: Yes" in llm_response
			current_page, total_pages, next_elements = 1, "Unknown", []
			
			for line in llm_response.split('\n'):
				line = line.strip()
				if line.startswith('CURRENT_PAGE:'):
					try:
						current_page = int(line.split(':')[1].strip())
					except:
						pass
				elif line.startswith('TOTAL_PAGES:'):
					total_pages = line.split(':', 1)[1].strip()
				elif line.startswith('NEXT_ELEMENTS:'):
					elements_text = line.split(':', 1)[1].strip()
					next_elements = [elem.strip() for elem in elements_text.split(',') if elem.strip()]
			
			# Find clickable elements for LLM suggestions
			clickable_elements = []
			if pagination_found and next_elements:
				for element_text in next_elements[:5]:
					if element_text and element_text.lower() not in ['none', 'unknown']:
						elements = await self.browser.find_elements(f'a:contains("{element_text}")')
						if not elements:
							elements = await self.browser.find_elements(f'*:contains("{element_text}")')
						
						for elem in elements[:2]:
							if elem['visible'] and elem['tag'] in ['a', 'button']:
								clickable_elements.append({
									'text': elem['text'][:50],
									'tag': elem['tag'],
									'href': elem.get('href', ''),
									'method': 'llm'
								})
			
			logger.info(f"🧠 LLM found: {pagination_found} | Page {current_page}/{total_pages} | {len(clickable_elements)} elements")
			
			return {
				"method": "llm",
				"pagination_found": pagination_found,
				"current_page": current_page,
				"total_pages": total_pages,
				"pagination_elements": clickable_elements,
				"llm_analysis": llm_response,
				"status": "completed"
			}
			
		except Exception as e:
			logger.error(f"❌ LLM pagination detection failed: {e}")
			return {"method": "llm", "status": "failed", "error": str(e), "pagination_found": False}

	async def detect_pagination_css(self) -> Dict[str, Any]:
		"""Fallback: Detect pagination using CSS selectors"""
		try:
			logger.info("🔍 Using CSS-based pagination detection (fallback)...")
			
			# Scroll to bottom first
			await self.browser.scroll_to_bottom()
			await asyncio.sleep(1)
			
			# CSS selector approach
			pagination_selectors = [
				'a:contains("Next")', 'a:contains(">")', 'a:contains("2")', 'a:contains("3")',
				'.pagination a', '.pager a', '[class*="next"]', 'a[href*="page"]'
			]
			
			found_pagination = []
			for selector in pagination_selectors:
				elements = await self.browser.find_elements(selector)
				for elem in elements:
					elem_text = elem['text'].lower().strip()
					if elem['visible'] and (elem_text.isdigit() or 'next' in elem_text or '>' in elem_text):
						found_pagination.append({
							'text': elem['text'][:50],
							'tag': elem['tag'],
							'href': elem.get('href', ''),
							'method': 'css'
						})
						
			logger.info(f"🔍 CSS found: {len(found_pagination)} pagination elements")
			
			return {
				"method": "css",
				"pagination_found": len(found_pagination) > 0,
				"pagination_elements": found_pagination[:5],
				"status": "completed"
			}
			
		except Exception as e:
			logger.error(f"❌ CSS pagination detection failed: {e}")
			return {"method": "css", "status": "failed", "error": str(e), "pagination_found": False}

	async def detect_pagination(self) -> Dict[str, Any]:
		"""Hybrid pagination detection: LLM-first with CSS fallback"""
		logger.info("🔍 Starting hybrid pagination detection...")
		
		# METHOD 1: Try LLM-based detection first (more reliable)
		llm_result = await self.detect_pagination_llm()
		
		if llm_result['status'] == 'completed' and llm_result['pagination_found']:
			logger.info("✅ LLM successfully detected pagination")
			return {
				"action": "hybrid_pagination_detection",
				"method_used": "llm", 
				"pagination_found": True,
				"pagination_elements": llm_result['pagination_elements'],
				"llm_analysis": llm_result.get('llm_analysis', ''),
				"current_page": llm_result.get('current_page', 1),
				"total_pages": llm_result.get('total_pages', 'Unknown'),
				"status": "completed"
			}
		
		# METHOD 2: Fallback to CSS-based detection
		logger.info("🔄 LLM detection failed/found nothing, trying CSS fallback...")
		css_result = await self.detect_pagination_css()
		
		if css_result['status'] == 'completed' and css_result['pagination_found']:
			logger.info("✅ CSS fallback successfully detected pagination") 
			return {
				"action": "hybrid_pagination_detection",
				"method_used": "css",
				"pagination_found": True,
				"pagination_elements": css_result['pagination_elements'],
				"status": "completed"
			}
		
		# METHOD 3: No pagination found by either method
		logger.info("❌ No pagination detected by either LLM or CSS methods")
		return {
			"action": "hybrid_pagination_detection",
			"method_used": "both_failed",
			"pagination_found": False,
			"pagination_elements": [],
			"llm_result": llm_result,
			"css_result": css_result,
			"status": "completed"
		}
	
	async def smart_paginate_and_extract(self, query: str, max_pages: int = 10) -> Dict[str, Any]:
		"""Intelligently paginate through all pages and extract data"""
		logger.info(f"🧠 *** STARTING MULTI-PAGE EXTRACTION FOR: {query} ***")
		logger.info(f"🎯 Max pages to process: {max_pages}")
		
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
				
				# Try clicking pagination elements - be more aggressive
				clicked_next = False
				
				# First try clicking "Next" or ">" buttons
				next_buttons = [elem for elem in pagination_info['pagination_elements'] 
							   if 'next' in elem['text'].lower() or '>' in elem['text']]
				
				for pag_elem in next_buttons:
					logger.info(f"🖱️ Attempting to click Next button: {pag_elem['text']}")
					# Try clicking by text instead of selector
					text_to_click = pag_elem['text'].strip()
					success = await self.browser.click_element(f'a:contains("{text_to_click}")')
					
					if success:
						clicked_next = True
						logger.info(f"✅ Successfully clicked Next: {text_to_click}")
						break
					else:
						# Fallback: try clicking any element with "Next" text
						success = await self.browser.click_element('a:contains("Next")')
						if success:
							clicked_next = True
							logger.info(f"✅ Successfully clicked Next (fallback)")
							break
				
				# If no Next button worked, try page numbers (2, 3, 4, etc.)
				if not clicked_next:
					page_numbers = [elem for elem in pagination_info['pagination_elements'] 
								   if elem['text'].strip().isdigit()]
					
					for pag_elem in page_numbers[:1]:  # Try first page number
						text_to_click = pag_elem['text'].strip()
						logger.info(f"🖱️ Attempting to click page number: {text_to_click}")
						success = await self.browser.click_element(f'a:contains("{text_to_click}")')
						
						if success:
							clicked_next = True
							logger.info(f"✅ Successfully clicked page: {text_to_click}")
							break
				
				# If still nothing worked, try clicking common pagination text
				if not clicked_next:
					common_pagination_texts = ["Next", ">", "→", "2", "3"]
					for text in common_pagination_texts:
						logger.info(f"🖱️ Trying fallback click: {text}")
						success = await self.browser.click_element(f'a:contains("{text}")')
						if success:
							clicked_next = True
							logger.info(f"✅ Successfully clicked fallback: {text}")
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