"""
Smart Pagination System for GTM Agent
Handles complex pagination patterns with intelligent scrolling and extraction
"""
import asyncio
import logging
from typing import Set, List, Dict, Any
from browser_use.browser import BrowserSession
from browser_use.browser.events import ScrollEvent, ClickElementEvent
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import SystemMessage, UserMessage

logger = logging.getLogger(__name__)


class SmartPaginationExtractor:
	"""Intelligent pagination and data extraction system"""
	
	def __init__(self, browser_session: BrowserSession, llm: BaseChatModel):
		self.browser_session = browser_session
		self.llm = llm
		self.visited_urls: Set[str] = set()
		self.extracted_data: List[Dict[str, Any]] = []
		self.pagination_history: List[Dict[str, Any]] = []
		self.content_hashes: Set[str] = set()  # Track content to detect duplicates
		self.consecutive_same_content = 0  # Count consecutive identical content
		self.last_content_hash = None
		
	async def extract_all_data(self, query: str, max_pages: int = 20) -> Dict[str, Any]:
		"""
		Smart extraction with comprehensive pagination handling
		"""
		logger.info(f"🧠 Starting smart pagination extraction for: {query}")
		
		current_page = 1
		consecutive_failures = 0
		max_consecutive_failures = 3
		
		while current_page <= max_pages and consecutive_failures < max_consecutive_failures:
			logger.info(f"📄 Processing page {current_page}...")
			
			try:
				# Get current URL for tracking
				current_url = await self.browser_session.get_current_page_url()
				url_key = self._normalize_url(current_url)
				
				# Check if we've already processed this exact page
				if url_key in self.visited_urls:
					logger.warning(f"🔄 Already visited {url_key}, ending pagination")
					break
				
				self.visited_urls.add(url_key)
				
				# SMART EXTRACTION STRATEGY
				page_data = await self._smart_page_extraction(query, current_page)
				
				if page_data and page_data.get('content'):
					# Check for duplicate content (infinite loop detection)
					content_hash = self._hash_content(page_data['content'])
					
					if content_hash == self.last_content_hash:
						self.consecutive_same_content += 1
						logger.warning(f"🔄 Same content detected {self.consecutive_same_content} times in a row")
						
						if self.consecutive_same_content >= 2:
							logger.error(f"🛑 INFINITE LOOP DETECTED: Same content {self.consecutive_same_content} times. Stopping pagination.")
							break
					else:
						self.consecutive_same_content = 0  # Reset counter
						self.last_content_hash = content_hash
					
					# Only add if content is new
					if content_hash not in self.content_hashes:
						self.content_hashes.add(content_hash)
						self.extracted_data.append(page_data)
						consecutive_failures = 0  # Reset failure counter
						logger.info(f"✅ Extracted NEW data from page {current_page}")
					else:
						logger.warning(f"🔄 Duplicate content detected on page {current_page}, but continuing...")
				else:
					consecutive_failures += 1
					logger.warning(f"⚠️ No data extracted from page {current_page}")
				
				# SMART PAGINATION DETECTION & NAVIGATION
				pagination_success = await self._smart_pagination_navigation(current_page)
				
				if not pagination_success:
					logger.info(f"🏁 No more pages found after page {current_page}")
					break
					
				current_page += 1
				
				# Safety wait between pages
				await asyncio.sleep(2)
				
			except Exception as e:
				consecutive_failures += 1
				logger.error(f"❌ Page {current_page} failed: {e}")
				
				if consecutive_failures >= max_consecutive_failures:
					logger.error(f"💔 Too many consecutive failures, stopping")
					break
		
		# Consolidate results
		return self._consolidate_results(query, current_page - 1)
	
	async def _smart_page_extraction(self, query: str, page_num: int) -> Dict[str, Any]:
		"""
		Smart page extraction with optimal scrolling strategy
		"""
		logger.info(f"🔍 Smart extraction strategy for page {page_num}")
		
		# STEP 1: Scroll to top first
		await self._scroll_to_position('top')
		await asyncio.sleep(1)
		
		# STEP 2: Check for top pagination controls
		top_pagination = await self._detect_pagination_at_position('top')
		
		# STEP 3: Progressive scroll and extract
		content_chunks = []
		
		# Extract content while scrolling down
		for scroll_position in ['top', 'middle', 'bottom']:
			await self._scroll_to_position(scroll_position)
			await asyncio.sleep(1)
			
			# Extract content at this position
			chunk = await self._extract_content_chunk(query, scroll_position)
			if chunk:
				content_chunks.append(chunk)
		
		# STEP 4: Check for bottom pagination controls
		bottom_pagination = await self._detect_pagination_at_position('bottom')
		
		# Combine all content
		combined_content = self._combine_content_chunks(content_chunks)
		
		return {
			'page': page_num,
			'url': await self.browser_session.get_current_page_url(),
			'content': combined_content,
			'top_pagination': top_pagination,
			'bottom_pagination': bottom_pagination,
			'extraction_method': 'smart_progressive'
		}
	
	async def _smart_pagination_navigation(self, current_page: int) -> bool:
		"""
		Smart pagination navigation with multiple fallback strategies
		"""
		logger.info(f"🧭 Smart pagination navigation from page {current_page}")
		
		# Strategy 1: Try bottom pagination first (most common)
		await self._scroll_to_position('bottom')
		await asyncio.sleep(1)
		
		bottom_success = await self._try_pagination_click('bottom')
		if bottom_success:
			logger.info(f"✅ Successfully navigated using bottom pagination")
			return True
		
		# Strategy 2: Try top pagination if bottom failed
		await self._scroll_to_position('top')
		await asyncio.sleep(1)
		
		top_success = await self._try_pagination_click('top')
		if top_success:
			logger.info(f"✅ Successfully navigated using top pagination")
			return True
		
		# Strategy 3: Look for "Load More" or infinite scroll triggers
		load_more_success = await self._try_load_more()
		if load_more_success:
			logger.info(f"✅ Successfully triggered load more")
			return True
		
		logger.info(f"❌ No pagination options found")
		return False
	
	async def _scroll_to_position(self, position: str):
		"""Scroll to specific position on page"""
		if position == 'top':
			# Scroll to top
			scroll_event = self.browser_session.event_bus.dispatch(
				ScrollEvent(direction='up', amount=10000)
			)
		elif position == 'middle':
			# Scroll to middle
			scroll_event = self.browser_session.event_bus.dispatch(
				ScrollEvent(direction='down', amount=1000)
			)
		elif position == 'bottom':
			# Scroll to bottom
			scroll_event = self.browser_session.event_bus.dispatch(
				ScrollEvent(direction='down', amount=10000)
			)
		
		await scroll_event
		await scroll_event.event_result(raise_if_any=True, raise_if_none=False)
	
	async def _detect_pagination_at_position(self, position: str) -> Dict[str, Any]:
		"""Detect pagination controls at specific position"""
		try:
			selector_map = await self.browser_session.get_selector_map()
			
			pagination_elements = []
			next_patterns = ['next', '>', '→', 'forward', 'more']
			page_patterns = ['1', '2', '3', '4', '5', 'page']
			
			for idx, element in selector_map.items():
				if not element.attributes:
					continue
				
				# Get element position (rough approximation)
				element_y = element.absolute_position.y if element.absolute_position else 0
				viewport_height = 800  # Approximate
				
				is_at_position = False
				if position == 'top' and element_y < viewport_height / 3:
					is_at_position = True
				elif position == 'bottom' and element_y > viewport_height * 2 / 3:
					is_at_position = True
				
				if is_at_position:
					element_text = ' '.join([
						element.attributes.get('title', ''),
						element.attributes.get('aria-label', ''),
						element.attributes.get('alt', ''),
						element.attributes.get('class', '')
					]).lower()
					
					# Check for pagination patterns
					for pattern in next_patterns + page_patterns:
						if pattern in element_text:
							pagination_elements.append({
								'index': idx,
								'text': element_text[:100],
								'pattern': pattern,
								'position': position
							})
							break
			
			return {
				'found': len(pagination_elements) > 0,
				'elements': pagination_elements[:5],  # Top 5 candidates
				'position': position
			}
			
		except Exception as e:
			logger.warning(f"Pagination detection failed at {position}: {e}")
			return {'found': False, 'elements': [], 'position': position}
	
	async def _try_pagination_click(self, position: str) -> bool:
		"""Try to click pagination controls at position"""
		try:
			pagination_info = await self._detect_pagination_at_position(position)
			
			if not pagination_info['found']:
				return False
			
			# Try clicking the best candidate
			for element in pagination_info['elements']:
				if 'next' in element['text'] or '>' in element['text']:
					logger.info(f"🖱️ Trying to click pagination at index {element['index']}")
					
					try:
						node = await self.browser_session.get_element_by_index(element['index'])
						if node:
							click_event = self.browser_session.event_bus.dispatch(ClickElementEvent(node=node))
							await click_event
							await click_event.event_result(raise_if_any=True, raise_if_none=False)
							
							# Wait for navigation
							await asyncio.sleep(4)
							return True
					except Exception as e:
						logger.warning(f"Click failed for index {element['index']}: {e}")
						continue
			
			return False
			
		except Exception as e:
			logger.error(f"Pagination click failed: {e}")
			return False
	
	async def _try_load_more(self) -> bool:
		"""Try to trigger load more or infinite scroll"""
		try:
			# Scroll to very bottom to trigger infinite scroll
			for _ in range(3):
				scroll_event = self.browser_session.event_bus.dispatch(
					ScrollEvent(direction='down', amount=2000)
				)
				await scroll_event
				await scroll_event.event_result(raise_if_any=True, raise_if_none=False)
				await asyncio.sleep(2)
			
			# Check if new content loaded by comparing page height or content
			# This is a simplified check - in practice you'd compare DOM changes
			return False  # Placeholder - implement based on specific site behavior
			
		except Exception as e:
			logger.warning(f"Load more failed: {e}")
			return False
	
	async def _extract_content_chunk(self, query: str, position: str) -> str:
		"""Extract content from current scroll position"""
		try:
			# Get page content at current scroll position
			cdp_session = await self.browser_session.get_or_create_cdp_session()
			body_id = await cdp_session.cdp_client.send.DOM.getDocument(session_id=cdp_session.session_id)
			page_html_result = await cdp_session.cdp_client.send.DOM.getOuterHTML(
				params={'backendNodeId': body_id['root']['backendNodeId']}, 
				session_id=cdp_session.session_id
			)
			page_html = page_html_result['outerHTML']
			
			# Convert to markdown (simplified)
			import html2text
			h = html2text.HTML2Text()
			h.ignore_images = True
			h.body_width = 0
			content = h.handle(page_html)
			
			# Truncate for processing
			if len(content) > 10000:
				content = content[:10000]
			
			# Quick LLM extraction
			system_prompt = f"Extract {query} from this webpage section. Return only relevant data, be concise."
			prompt = f"<section_position>{position}</section_position>\n<content>{content}</content>"
			
			response = await asyncio.wait_for(
				self.llm.ainvoke([
					SystemMessage(content=system_prompt), 
					UserMessage(content=prompt)
				]), timeout=60.0
			)
			
			return response.completion
			
		except Exception as e:
			logger.warning(f"Content extraction failed at {position}: {e}")
			return ""
	
	def _combine_content_chunks(self, chunks: List[str]) -> str:
		"""Combine content chunks intelligently"""
		# Remove duplicates and combine
		unique_chunks = []
		for chunk in chunks:
			if chunk and chunk not in unique_chunks:
				unique_chunks.append(chunk)
		
		return "\n\n".join(unique_chunks)
	
	def _normalize_url(self, url: str) -> str:
		"""Normalize URL for comparison (remove fragments, params that don't affect content)"""
		from urllib.parse import urlparse, parse_qs
		
		parsed = urlparse(url)
		# Keep main URL structure but remove tracking params
		return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
	
	def _consolidate_results(self, query: str, pages_processed: int) -> Dict[str, Any]:
		"""Consolidate all extracted data"""
		all_content = []
		for page_data in self.extracted_data:
			if page_data.get('content'):
				all_content.append(f"Page {page_data['page']}: {page_data['content']}")
		
		consolidated = "\n\n".join(all_content)
		
		return {
			'query': query,
			'pages_processed': pages_processed,
			'total_content': consolidated,
			'extraction_summary': f"Smart pagination extraction completed: {pages_processed} pages processed, {len(self.visited_urls)} unique URLs visited, {len(self.content_hashes)} unique content blocks",
			'urls_visited': list(self.visited_urls)
		}
	
	def _hash_content(self, content: str) -> str:
		"""Create hash of content for duplicate detection"""
		import hashlib
		# Normalize content by removing extra whitespace and convert to lowercase
		normalized = ' '.join(content.lower().split())
		return hashlib.md5(normalized.encode()).hexdigest()[:16]  # Short hash for efficiency