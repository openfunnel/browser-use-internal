"""
Simplified Tools class for browser-use with only core actions:
- search
- pagination 
- scroll
- filter
- extract_structured_data (content extraction)
- dropdown operations

This removes all unnecessary fluff and keeps only essential browser automation actions.
"""
import asyncio
import logging
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from browser_use.agent.views import ActionModel, ActionResult
from browser_use.browser import BrowserSession
from browser_use.browser.events import (
	ClickElementEvent,
	GetDropdownOptionsEvent,
	NavigateToUrlEvent,
	ScrollEvent,
	ScrollToTextEvent,
	TypeTextEvent,
)
from browser_use.browser.views import BrowserError
from browser_use.tools.registry.service import Registry
from browser_use.tools.views import (
	ClickElementAction,
	DoneAction,
	GetDropdownOptionsAction,
	GoToUrlAction,
	InputTextAction,
	ScrollAction,
	SearchGoogleAction,
	SelectDropdownOptionAction,
)

logger = logging.getLogger(__name__)

Context = TypeVar('Context')
T = TypeVar('T', bound=BaseModel)


def handle_browser_error(e: BrowserError) -> ActionResult:
	"""Handle browser errors gracefully"""
	if e.long_term_memory is not None:
		if e.short_term_memory is not None:
			return ActionResult(
				extracted_content=e.short_term_memory, 
				error=e.long_term_memory, 
				include_extracted_content_only_once=True
			)
		else:
			return ActionResult(error=e.long_term_memory)
	raise e


class SimpleTools(Generic[Context]):
	"""Simplified browser automation tools with only core actions"""
	
	def __init__(self):
		self.registry = Registry[Context]([])  # No excluded actions
		self._register_core_actions()
		self._register_done_action()

	def _register_core_actions(self):
		"""Register only the core actions needed"""

		# NAVIGATION ACTION (needed for Agent initial actions)
		@self.registry.action(
			'Navigate to a URL',
			param_model=GoToUrlAction,
		)
		async def go_to_url(params: GoToUrlAction, browser_session: BrowserSession):
			try:
				event = browser_session.event_bus.dispatch(
					NavigateToUrlEvent(url=params.url, new_tab=params.new_tab)
				)
				await event
				await event.event_result(raise_if_any=True, raise_if_none=False)
				
				memory = f'Navigated to {params.url}'
				logger.info(f'🔗 {memory}')
				return ActionResult(extracted_content=memory, long_term_memory=memory)
			except Exception as e:
				logger.error(f'Navigation failed: {e}')
				return ActionResult(error=f'Failed to navigate to {params.url}: {str(e)}')

		# 1. SEARCH ACTION
		@self.registry.action(
			'Search Google for a query. Use clear, specific search terms.',
			param_model=SearchGoogleAction,
		)
		async def search_google(params: SearchGoogleAction, browser_session: BrowserSession):
			search_url = f'https://www.google.com/search?q={params.query}&udm=14'
			
			try:
				event = browser_session.event_bus.dispatch(
					NavigateToUrlEvent(url=search_url, new_tab=False)
				)
				await event
				await event.event_result(raise_if_any=True, raise_if_none=False)
				
				memory = f"Searched Google for '{params.query}'"
				logger.info(f'🔍 {memory}')
				return ActionResult(extracted_content=memory, long_term_memory=memory)
			except Exception as e:
				logger.error(f'Search failed: {e}')
				return ActionResult(error=f'Search failed for "{params.query}": {str(e)}')

		# 2. PAGINATION ACTION (intelligent pagination handling)
		@self.registry.action(
			'Click pagination elements (Next/Previous buttons, page numbers, Load More). Automatically detects pagination patterns. Only use indices from browser_state.',
			param_model=ClickElementAction,
		)
		async def click_element(params: ClickElementAction, browser_session: BrowserSession):
			try:
				assert params.index != 0, 'Cannot click element with index 0'
				
				node = await browser_session.get_element_by_index(params.index)
				if node is None:
					raise ValueError(f'Element index {params.index} not found')

				event = browser_session.event_bus.dispatch(ClickElementEvent(node=node))
				await event
				click_metadata = await event.event_result(raise_if_any=True, raise_if_none=False)
				
				memory = f'Clicked element {params.index}'
				logger.info(f'🖱️ {memory}')
				
				return ActionResult(
					long_term_memory=memory,
					metadata=click_metadata if isinstance(click_metadata, dict) else None,
				)
			except BrowserError as e:
				return handle_browser_error(e)
			except Exception as e:
				return ActionResult(error=f'Click failed on element {params.index}: {str(e)}')

		# 3. SCROLL ACTIONS
		@self.registry.action(
			'Scroll the page up or down by number of pages. Use large numbers (like 10) to get to bottom quickly.',
			param_model=ScrollAction,
		)
		async def scroll(params: ScrollAction, browser_session: BrowserSession):
			try:
				pixels = int(params.num_pages * 1000)
				event = browser_session.event_bus.dispatch(
					ScrollEvent(
						direction='down' if params.down else 'up', 
						amount=pixels
					)
				)
				await event
				await event.event_result(raise_if_any=True, raise_if_none=False)
				
				direction = 'down' if params.down else 'up'
				memory = f'Scrolled {direction} {params.num_pages} pages'
				logger.info(f'🔍 {memory}')
				
				return ActionResult(extracted_content=memory, long_term_memory=memory)
			except Exception as e:
				return ActionResult(error='Scroll action failed')

		@self.registry.action('Scroll directly to specific text on the page')
		async def scroll_to_text(text: str, browser_session: BrowserSession):
			event = browser_session.event_bus.dispatch(ScrollToTextEvent(text=text))
			
			try:
				await event.event_result(raise_if_any=True, raise_if_none=False)
				memory = f'Scrolled to text: {text}'
				logger.info(f'🔍 {memory}')
				return ActionResult(extracted_content=memory, long_term_memory=memory)
			except Exception:
				memory = f"Text '{text}' not found on page"
				return ActionResult(extracted_content=memory, long_term_memory=memory)

		# 4. FILTER ACTION (input text for search/filter fields)
		@self.registry.action(
			'Input text into form fields for filtering/searching. Only use indices from browser_state.',
			param_model=InputTextAction,
		)
		async def input_text(params: InputTextAction, browser_session: BrowserSession):
			try:
				node = await browser_session.get_element_by_index(params.index)
				if node is None:
					raise ValueError(f'Element index {params.index} not found')

				event = browser_session.event_bus.dispatch(
					TypeTextEvent(
						node=node, 
						text=params.text, 
						clear_existing=params.clear_existing
					)
				)
				await event
				input_metadata = await event.event_result(raise_if_any=True, raise_if_none=False)
				
				memory = f"Input '{params.text}' into element {params.index}"
				logger.info(f'⌨️ {memory}')
				
				return ActionResult(
					extracted_content=memory,
					long_term_memory=memory,
					metadata=input_metadata if isinstance(input_metadata, dict) else None,
				)
			except BrowserError as e:
				return handle_browser_error(e)
			except Exception as e:
				return ActionResult(error=f'Input failed on element {params.index}: {str(e)}')

		# 5. CONTENT EXTRACTION ACTION
		@self.registry.action(
			'Extract structured data from the current page based on a query. Only use when on the right page.',
		)
		async def extract_structured_data(
			query: str,
			extract_links: bool,
			browser_session: BrowserSession,
			page_extraction_llm,
			start_from_char: int = 0,
		):
			try:
				# Get page content
				cdp_session = await browser_session.get_or_create_cdp_session()
				body_id = await cdp_session.cdp_client.send.DOM.getDocument(session_id=cdp_session.session_id)
				page_html_result = await cdp_session.cdp_client.send.DOM.getOuterHTML(
					params={'backendNodeId': body_id['root']['backendNodeId']}, 
					session_id=cdp_session.session_id
				)
				page_html = page_html_result['outerHTML']
				current_url = await browser_session.get_current_page_url()
				
				# Convert to clean markdown
				import html2text
				h = html2text.HTML2Text()
				h.ignore_links = not extract_links
				h.ignore_images = True
				h.body_width = 0
				content = h.handle(page_html)
				
				# Apply start_from_char if specified
				if start_from_char > 0:
					if start_from_char >= len(content):
						return ActionResult(error=f'start_from_char ({start_from_char}) exceeds content length')
					content = content[start_from_char:]
				
				# Truncate if too long
				MAX_CHAR_LIMIT = 30000
				if len(content) > MAX_CHAR_LIMIT:
					content = content[:MAX_CHAR_LIMIT]
				
				# Create extraction prompt
				system_prompt = """Extract information from webpage markdown that is relevant to the query. 
Only use information available in the webpage. If information is not available, mention that.
Output the relevant information concisely without conversational format."""
				
				prompt = f'<query>\n{query}\n</query>\n\n<webpage_content>\n{content}\n</webpage_content>'
				
				from browser_use.llm.messages import SystemMessage, UserMessage
				response = await asyncio.wait_for(
					page_extraction_llm.ainvoke([
						SystemMessage(content=system_prompt), 
						UserMessage(content=prompt)
					]), timeout=120.0
				)
				
				extracted_content = f'<url>\n{current_url}\n</url>\n<query>\n{query}\n</query>\n<result>\n{response.completion}\n</result>'
				memory = f'Extracted content from {current_url} for query: {query}'
				
				logger.info(f'📄 {memory}')
				return ActionResult(
					extracted_content=extracted_content,
					long_term_memory=memory,
				)
			except Exception as e:
				return ActionResult(error=f'Content extraction failed: {str(e)}')

		# 6. DROPDOWN ACTIONS
		@self.registry.action(
			'Get dropdown options from a dropdown element. Only use on dropdown/select elements.',
			param_model=GetDropdownOptionsAction,
		)
		async def get_dropdown_options(params: GetDropdownOptionsAction, browser_session: BrowserSession):
			try:
				node = await browser_session.get_element_by_index(params.index)
				if node is None:
					raise ValueError(f'Element index {params.index} not found')

				event = browser_session.event_bus.dispatch(GetDropdownOptionsEvent(node=node))
				dropdown_data = await event.event_result(timeout=3.0, raise_if_none=True, raise_if_any=True)

				if not dropdown_data:
					raise ValueError('Failed to get dropdown options')

				return ActionResult(
					extracted_content=dropdown_data['short_term_memory'],
					long_term_memory=dropdown_data['long_term_memory'],
					include_extracted_content_only_once=True,
				)
			except Exception as e:
				return ActionResult(error=f'Failed to get dropdown options: {str(e)}')

		@self.registry.action(
			'Select dropdown option by exact text match.',
			param_model=SelectDropdownOptionAction,
		)
		async def select_dropdown_option(params: SelectDropdownOptionAction, browser_session: BrowserSession):
			try:
				node = await browser_session.get_element_by_index(params.index)
				if node is None:
					raise ValueError(f'Element index {params.index} not found')

				from browser_use.browser.events import SelectDropdownOptionEvent
				event = browser_session.event_bus.dispatch(
					SelectDropdownOptionEvent(node=node, text=params.text)
				)
				selection_data = await event.event_result()

				if not selection_data:
					raise ValueError('Failed to select dropdown option')

				if selection_data.get('success') == 'true':
					msg = selection_data.get('message', f'Selected option: {params.text}')
					return ActionResult(
						extracted_content=msg,
						long_term_memory=f"Selected '{params.text}' at index {params.index}",
					)
				else:
					error_msg = selection_data.get('error', f'Failed to select: {params.text}')
					return ActionResult(error=error_msg)
			except Exception as e:
				return ActionResult(error=f'Dropdown selection failed: {str(e)}')

		# 7. IMPROVED PAGINATION DETECTION
		@self.registry.action(
			'Detect pagination controls including page numbers, Next/Previous buttons, and navigation elements.',
		)
		async def detect_pagination(browser_session: BrowserSession):
			"""Enhanced pagination detection with better pattern recognition"""
			try:
				# Get current page elements
				selector_map = await browser_session.get_selector_map()
				current_url = await browser_session.get_current_page_url()
				
				pagination_info = {
					'has_pagination': False,
					'next_button_index': None,
					'page_buttons': [],
					'current_page': 1,
					'total_pages': 'unknown',
					'pagination_type': 'none',
					'all_candidates': []
				}
				
				logger.info(f'🔍 Analyzing {len(selector_map)} elements for pagination...')
				
				# Enhanced pagination detection patterns
				next_patterns = ['next', '>', '→', 'forward', 'continue', 'mehr', 'siguiente']
				page_number_patterns = [r'\d+', 'page']
				
				candidates = []
				
				for idx, element in selector_map.items():
					if not element.attributes:
						continue
					
					# Get all text content from element
					element_texts = []
					
					# Check various text sources
					if hasattr(element, 'text_content') and element.text_content:
						element_texts.append(element.text_content.lower().strip())
					
					# Check attributes
					for attr in ['title', 'aria-label', 'alt', 'value', 'class', 'id']:
						if element.attributes.get(attr):
							element_texts.append(element.attributes.get(attr).lower().strip())
					
					# Check href for page patterns
					href = element.attributes.get('href', '')
					if href:
						element_texts.append(href.lower())
					
					# Combine all text
					combined_text = ' '.join(element_texts)
					
					# Score this element for pagination likelihood
					score = 0
					element_type = 'unknown'
					
					# Check if it's a clickable element
					if element.node_name.lower() in ['a', 'button', 'span', 'div']:
						
						# Look for next button patterns
						for pattern in next_patterns:
							if pattern in combined_text:
								score += 3
								element_type = 'next_button'
								break
						
						# Look for numeric page indicators
						import re
						if re.search(r'\b\d{1,3}\b', combined_text):
							score += 2
							element_type = 'page_number'
						
						# Check for common pagination classes/IDs
						pagination_classes = ['pag', 'next', 'page', 'nav', 'btn', 'link']
						for cls in pagination_classes:
							if cls in combined_text:
								score += 1
								break
						
						# Check if href contains pagination patterns
						if 'page=' in href or '/page/' in href or 'p=' in href:
							score += 2
							element_type = 'page_link'
						
						# Boost score for likely interactive elements
						if any(x in combined_text for x in ['click', 'button', 'link']):
							score += 1
					
					if score > 0:
						candidates.append({
							'index': idx,
							'score': score,
							'type': element_type,
							'text': combined_text[:100],
							'node_name': element.node_name,
							'href': href
						})
				
				# Sort candidates by score
				candidates.sort(key=lambda x: x['score'], reverse=True)
				pagination_info['all_candidates'] = candidates[:10]  # Top 10 for debugging
				
				# Identify pagination elements
				next_buttons = [c for c in candidates if c['type'] == 'next_button' and c['score'] >= 3]
				page_numbers = [c for c in candidates if c['type'] in ['page_number', 'page_link'] and c['score'] >= 2]
				
				# Determine pagination status
				if next_buttons or page_numbers:
					pagination_info['has_pagination'] = True
					
					if next_buttons:
						pagination_info['next_button_index'] = next_buttons[0]['index']
						pagination_info['pagination_type'] = 'next_button'
					elif page_numbers:
						pagination_info['page_buttons'] = [p['index'] for p in page_numbers[:5]]
						pagination_info['pagination_type'] = 'page_numbers'
					
					# Try to determine current page and total pages
					try:
						current_page_candidates = [p for p in page_numbers if 'current' in p['text'] or 'active' in p['text']]
						if current_page_candidates:
							import re
							match = re.search(r'\d+', current_page_candidates[0]['text'])
							if match:
								pagination_info['current_page'] = int(match.group())
					except:
						pass
				
				# Enhanced logging
				memory = f"Pagination: {pagination_info['has_pagination']}, Type: {pagination_info['pagination_type']}"
				if pagination_info['next_button_index']:
					memory += f", Next at idx {pagination_info['next_button_index']}"
				if pagination_info['page_buttons']:
					memory += f", Pages at idx {pagination_info['page_buttons'][:3]}"
				memory += f", Found {len(candidates)} candidates"
				
				logger.info(f'🔍 {memory}')
				
				# Debug output for troubleshooting
				if candidates:
					logger.info(f"🔍 Top pagination candidates:")
					for i, c in enumerate(candidates[:5]):
						logger.info(f"  {i+1}. idx:{c['index']} score:{c['score']} type:{c['type']} text:'{c['text'][:50]}'")
				else:
					logger.warning("🔍 No pagination candidates found!")
				
				return ActionResult(
					extracted_content=f"Pagination Analysis: {memory}\nTop candidates: {candidates[:3]}",
					long_term_memory=memory,
					metadata=pagination_info
				)
				
			except Exception as e:
				logger.error(f'Pagination detection failed: {e}')
				return ActionResult(error=f'Failed to detect pagination: {str(e)}')

		# 8. EXTRACT ALL DATA WITH AUTO-PAGINATION
		@self.registry.action(
			'Extract ALL data from current and subsequent pages using automatic pagination. Continues until no more pages.',
		)
		async def extract_all_paginated_data(
			query: str,
			browser_session: BrowserSession,
			page_extraction_llm,
			max_pages: int = 20,
		):
			"""Extract data from all pages automatically"""
			try:
				all_data = []
				current_page = 1
				
				logger.info(f'🔄 Starting paginated extraction for: {query}')
				
				while current_page <= max_pages:
					logger.info(f'📄 Processing page {current_page}...')
					
					# Scroll to load all content on current page
					event = browser_session.event_bus.dispatch(
						ScrollEvent(direction='down', amount=3000)
					)
					await event
					await event.event_result(raise_if_any=True, raise_if_none=False)
					
					# Extract data from current page
					current_url = await browser_session.get_current_page_url()
					
					# Get page content
					cdp_session = await browser_session.get_or_create_cdp_session()
					body_id = await cdp_session.cdp_client.send.DOM.getDocument(session_id=cdp_session.session_id)
					page_html_result = await cdp_session.cdp_client.send.DOM.getOuterHTML(
						params={'backendNodeId': body_id['root']['backendNodeId']}, 
						session_id=cdp_session.session_id
					)
					page_html = page_html_result['outerHTML']
					
					# Convert to markdown
					import html2text
					h = html2text.HTML2Text()
					h.ignore_links = False
					h.ignore_images = True
					h.body_width = 0
					content = h.handle(page_html)
					
					# Truncate if too long
					if len(content) > 30000:
						content = content[:30000]
					
					# Extract data using LLM
					system_prompt = f"""Extract all {query} from this webpage content. 
Return only the relevant data in a clean, structured format.
Focus on extracting complete information for each item found."""
					
					prompt = f'<query>\nExtract all {query}\n</query>\n\n<page_content>\n{content}\n</page_content>'
					
					from browser_use.llm.messages import SystemMessage, UserMessage
					response = await asyncio.wait_for(
						page_extraction_llm.ainvoke([
							SystemMessage(content=system_prompt), 
							UserMessage(content=prompt)
						]), timeout=120.0
					)
					
					page_data = response.completion
					all_data.append({
						'page': current_page,
						'url': current_url,
						'data': page_data
					})
					
					# Check for next page
					pagination_result = await self.detect_pagination(browser_session)
					pagination_info = pagination_result.metadata or {}
					
					if not pagination_info.get('has_pagination'):
						logger.info(f'✅ No more pages found. Completed extraction at page {current_page}')
						break
					
					# Try to navigate to next page
					next_index = pagination_info.get('next_button_index')
					page_buttons = pagination_info.get('page_buttons', [])
					
					clicked_successfully = False
					
					# Try next button first
					if next_index:
						logger.info(f'🔄 Clicking Next button at index {next_index}...')
						try:
							node = await browser_session.get_element_by_index(next_index)
							if node:
								click_event = browser_session.event_bus.dispatch(ClickElementEvent(node=node))
								await click_event
								await click_event.event_result(raise_if_any=True, raise_if_none=False)
								clicked_successfully = True
								logger.info(f'✅ Successfully clicked Next button')
						except Exception as e:
							logger.warning(f'Failed to click Next button: {e}')
					
					# If no next button, try page number buttons
					elif page_buttons and current_page < len(page_buttons) + 1:
						target_page_idx = min(current_page, len(page_buttons) - 1) if current_page < len(page_buttons) else len(page_buttons) - 1
						if target_page_idx >= 0:
							page_index = page_buttons[target_page_idx]
							logger.info(f'🔄 Clicking page button at index {page_index}...')
							try:
								node = await browser_session.get_element_by_index(page_index)
								if node:
									click_event = browser_session.event_bus.dispatch(ClickElementEvent(node=node))
									await click_event
									await click_event.event_result(raise_if_any=True, raise_if_none=False)
									clicked_successfully = True
									logger.info(f'✅ Successfully clicked page button')
							except Exception as e:
								logger.warning(f'Failed to click page button: {e}')
					
					if clicked_successfully:
						# Wait for page to load
						await asyncio.sleep(3)
						current_page += 1
						logger.info(f'📄 Moved to page {current_page}')
					else:
						logger.info('❌ No more navigation options found, ending pagination')
						break
				
				# Consolidate all data
				consolidated_data = []
				for page_result in all_data:
					consolidated_data.append(f"Page {page_result['page']}: {page_result['data']}")
				
				final_result = f"COMPLETE DATASET ACROSS {len(all_data)} PAGES:\n\n" + "\n\n".join(consolidated_data)
				
				memory = f'Extracted data from {len(all_data)} pages for query: {query}'
				logger.info(f'📊 {memory}')
				
				return ActionResult(
					extracted_content=final_result,
					long_term_memory=memory,
					metadata={'pages_processed': len(all_data), 'query': query}
				)
				
			except Exception as e:
				logger.error(f'Paginated extraction failed: {e}')
				return ActionResult(error=f'Failed to extract paginated data: {str(e)}')

	def _register_done_action(self):
		"""Register task completion action"""
		@self.registry.action(
			'Complete the task and provide results summary. Set success=True if completed successfully.',
			param_model=DoneAction,
		)
		async def done(params: DoneAction):
			memory = f'Task completed: {params.success}'
			return ActionResult(
				is_done=True,
				success=params.success,
				extracted_content=params.text,
				long_term_memory=memory,
			)

	# Action execution
	async def act(
		self,
		action: ActionModel,
		browser_session: BrowserSession,
		page_extraction_llm=None,
		file_system=None,
		sensitive_data=None,
		available_file_paths=None,
	) -> ActionResult:
		"""Execute a simplified action"""
		for action_name, params in action.model_dump(exclude_unset=True).items():
			if params is not None:
				try:
					result = await self.registry.execute_action(
						action_name=action_name,
						params=params,
						browser_session=browser_session,
						page_extraction_llm=page_extraction_llm,
					)
				except BrowserError as e:
					result = handle_browser_error(e)
				except Exception as e:
					logger.error(f"Action '{action_name}' failed: {str(e)}")
					result = ActionResult(error=str(e))

				if isinstance(result, ActionResult):
					return result
				elif isinstance(result, str):
					return ActionResult(extracted_content=result)
				else:
					return ActionResult()
		return ActionResult()