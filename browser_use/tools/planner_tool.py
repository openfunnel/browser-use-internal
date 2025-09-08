"""
Smart Planner Tool - Reconnaissance and Planning System
Acts like a human who first scouts the website to understand structure and create execution plan
"""
import asyncio
import logging
from typing import Dict, Any, List
from pydantic import BaseModel
from browser_use.browser import BrowserSession
from browser_use.browser.events import ScrollEvent
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import SystemMessage, UserMessage

logger = logging.getLogger(__name__)


class WebsiteAnalysis(BaseModel):
	"""Structured analysis of website for planning"""
	data_structure: str  # How data is organized (table, cards, list, etc.)
	data_columns: List[str]  # What columns/fields contain the target data
	pagination_type: str  # none, numbered_pages, next_prev, load_more, infinite_scroll
	pagination_location: str  # top, bottom, both, sidebar
	estimated_pages: str  # rough estimate or "unknown"
	stop_condition: str  # How to detect when we've reached the end
	extraction_strategy: str  # Best approach for extracting data
	special_notes: str  # Any unique characteristics or challenges


class SmartPlanner:
	"""Smart planning system that scouts websites and creates execution plans"""
	
	def __init__(self, browser_session: BrowserSession, llm: BaseChatModel):
		self.browser_session = browser_session
		self.llm = llm
	
	async def create_extraction_plan(self, query: str) -> Dict[str, Any]:
		"""
		Scout the website and create a detailed extraction plan
		
		Args:
			query: What data to extract (e.g., "company names")
			
		Returns:
			Detailed execution plan with specific instructions
		"""
		logger.info(f"🕵️ Starting reconnaissance for: {query}")
		
		# PHASE 1: Initial page analysis
		initial_analysis = await self._analyze_current_page(query)
		
		# PHASE 2: Scroll exploration to understand full page structure  
		scroll_analysis = await self._explore_page_structure()
		
		# PHASE 3: Pagination reconnaissance
		pagination_analysis = await self._analyze_pagination()
		
		# PHASE 4: Create comprehensive execution plan
		execution_plan = await self._create_execution_plan(
			query, initial_analysis, scroll_analysis, pagination_analysis
		)
		
		logger.info(f"📋 Reconnaissance complete. Plan created.")
		return execution_plan
	
	async def _analyze_current_page(self, query: str) -> Dict[str, Any]:
		"""Analyze the current page structure and data layout"""
		logger.info("🔍 Phase 1: Analyzing current page structure...")
		
		try:
			# Get page content for analysis
			current_url = await self.browser_session.get_current_page_url()
			
			# Get page HTML for analysis
			cdp_session = await self.browser_session.get_or_create_cdp_session()
			body_id = await cdp_session.cdp_client.send.DOM.getDocument(session_id=cdp_session.session_id)
			page_html_result = await cdp_session.cdp_client.send.DOM.getOuterHTML(
				params={'backendNodeId': body_id['root']['backendNodeId']}, 
				session_id=cdp_session.session_id
			)
			page_html = page_html_result['outerHTML']
			
			# Convert to readable format
			import html2text
			h = html2text.HTML2Text()
			h.ignore_images = True
			h.body_width = 0
			content = h.handle(page_html)
			
			# Limit content for analysis
			if len(content) > 15000:
				content = content[:15000] + "...\n[Content truncated for analysis]"
			
			# LLM analysis of page structure
			system_prompt = """You are a website reconnaissance expert. Analyze this webpage to understand its data structure.

Focus on:
1. How is the target data organized? (table rows, card layout, list items, etc.)
2. What HTML elements/patterns contain the data?
3. How many items are visible on this page?
4. What columns/fields are available?
5. Is there any indication of more data (pagination hints, "showing X of Y", etc.)?

Be specific and technical in your analysis."""

			prompt = f"""
RECONNAISSANCE TARGET: {query}
URL: {current_url}

WEBPAGE CONTENT:
{content}

Analyze this page structure for extracting "{query}". Provide specific technical details about data organization and extraction approach.
"""
			
			response = await asyncio.wait_for(
				self.llm.ainvoke([
					SystemMessage(content=system_prompt),
					UserMessage(content=prompt)
				]), timeout=60.0
			)
			
			return {
				'url': current_url,
				'analysis': response.completion,
				'content_preview': content[:1000],
				'page_type': 'initial'
			}
			
		except Exception as e:
			logger.error(f"Page analysis failed: {e}")
			return {'error': str(e)}
	
	async def _explore_page_structure(self) -> Dict[str, Any]:
		"""Explore page by scrolling to understand full structure"""
		logger.info("🔍 Phase 2: Exploring page structure through scrolling...")
		
		try:
			structure_info = {
				'scroll_positions_analyzed': [],
				'content_changes': [],
				'dynamic_loading_detected': False
			}
			
			# Scroll to different positions and analyze
			positions = [
				('top', 'up', 5000),
				('middle', 'down', 2000), 
				('bottom', 'down', 5000)
			]
			
			for position_name, direction, amount in positions:
				logger.info(f"📍 Analyzing {position_name} section...")
				
				# Scroll to position
				scroll_event = self.browser_session.event_bus.dispatch(
					ScrollEvent(direction=direction, amount=amount)
				)
				await scroll_event
				await scroll_event.event_result(raise_if_any=True, raise_if_none=False)
				await asyncio.sleep(2)  # Wait for any dynamic loading
				
				# Check if content changed (simplified check)
				current_url = await self.browser_session.get_current_page_url()
				structure_info['scroll_positions_analyzed'].append({
					'position': position_name,
					'url': current_url,
					'timestamp': f"scroll_{len(structure_info['scroll_positions_analyzed'])}"
				})
			
			logger.info(f"✅ Explored {len(positions)} scroll positions")
			return structure_info
			
		except Exception as e:
			logger.error(f"Page structure exploration failed: {e}")
			return {'error': str(e)}
	
	async def _analyze_pagination(self) -> Dict[str, Any]:
		"""Analyze pagination controls and patterns"""
		logger.info("🔍 Phase 3: Analyzing pagination controls...")
		
		try:
			# Scroll to bottom to find pagination controls
			scroll_event = self.browser_session.event_bus.dispatch(
				ScrollEvent(direction='down', amount=3000)
			)
			await scroll_event
			await scroll_event.event_result(raise_if_any=True, raise_if_none=False)
			await asyncio.sleep(1)
			
			# Get interactive elements for pagination analysis
			selector_map = await self.browser_session.get_selector_map()
			
			pagination_candidates = []
			pagination_keywords = ['next', 'previous', 'page', '>', '<', '→', '←', 'more', 'load']
			
			for idx, element in selector_map.items():
				if not element.attributes:
					continue
				
				# Check element text and attributes
				element_text = ' '.join([
					element.attributes.get('title', ''),
					element.attributes.get('aria-label', ''),
					element.attributes.get('class', ''),
					element.attributes.get('id', ''),
					str(getattr(element, 'text_content', ''))
				]).lower()
				
				# Look for pagination indicators
				for keyword in pagination_keywords:
					if keyword in element_text:
						pagination_candidates.append({
							'index': idx,
							'element_type': element.node_name,
							'text': element_text[:100],
							'keyword_found': keyword,
							'position_y': element.absolute_position.y if element.absolute_position else 0
						})
						break
			
			# Also scroll to top to check for top pagination
			scroll_event = self.browser_session.event_bus.dispatch(
				ScrollEvent(direction='up', amount=5000)
			)
			await scroll_event
			await scroll_event.event_result(raise_if_any=True, raise_if_none=False)
			await asyncio.sleep(1)
			
			return {
				'pagination_candidates': pagination_candidates[:10],  # Top 10 candidates
				'total_candidates_found': len(pagination_candidates),
				'analysis_complete': True
			}
			
		except Exception as e:
			logger.error(f"Pagination analysis failed: {e}")
			return {'error': str(e)}
	
	async def _create_execution_plan(self, query: str, initial_analysis: Dict, 
									 scroll_analysis: Dict, pagination_analysis: Dict) -> Dict[str, Any]:
		"""Create comprehensive execution plan based on reconnaissance"""
		logger.info("🎯 Phase 4: Creating comprehensive execution plan...")
		
		try:
			# Combine all analysis data
			reconnaissance_data = {
				'query': query,
				'initial_analysis': initial_analysis.get('analysis', ''),
				'scroll_exploration': scroll_analysis,
				'pagination_info': pagination_analysis
			}
			
			# LLM creates specific execution plan
			system_prompt = """You are an expert web scraping strategist. Based on the reconnaissance data, create a detailed execution plan.

Create a plan that includes:

1. DATA STRUCTURE: How data is organized (table, cards, list, etc.)
2. EXTRACTION STRATEGY: Best approach to extract the target data
3. PAGINATION STRATEGY: How to handle pagination (if any)
4. SCROLL STRATEGY: How to scroll to capture all data
5. STOP CONDITIONS: How to detect when extraction is complete
6. TOOLS TO USE: Which specific tools should be used and in what order
7. ESTIMATED PAGES: Rough estimate of how many pages to expect
8. SPECIAL CONSIDERATIONS: Any unique challenges or edge cases

Make the plan specific and actionable with exact tool names and parameters."""

			prompt = f"""
RECONNAISSANCE DATA:
{reconnaissance_data}

Create a detailed, step-by-step execution plan for extracting "{query}" from this website.
"""
			
			response = await asyncio.wait_for(
				self.llm.ainvoke([
					SystemMessage(content=system_prompt),
					UserMessage(content=prompt)
				]), timeout=90.0
			)
			
			execution_plan = {
				'query': query,
				'reconnaissance_summary': {
					'initial_analysis': initial_analysis,
					'structure_exploration': scroll_analysis,
					'pagination_analysis': pagination_analysis
				},
				'execution_strategy': response.completion,
				'plan_created_at': 'reconnaissance_complete',
				'confidence_level': 'high' if not any('error' in analysis for analysis in [initial_analysis, scroll_analysis, pagination_analysis]) else 'medium'
			}
			
			logger.info("📋 Comprehensive execution plan created")
			return execution_plan
			
		except Exception as e:
			logger.error(f"Execution plan creation failed: {e}")
			return {'error': str(e)}