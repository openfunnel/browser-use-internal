"""
Reconnaissance Planner - Smart website analysis for optimal extraction
Acts like human reconnaissance to understand website structure first
"""
import asyncio
import logging
from typing import Dict, Any, List
from ..browser.session import BrowserSession
from ..llm.base import BaseLLM

logger = logging.getLogger(__name__)


class ReconnaissancePlanner:
	"""Smart website reconnaissance and planning system"""
	
	def __init__(self, browser_session: BrowserSession, llm: BaseLLM):
		self.browser = browser_session
		self.llm = llm
	
	async def create_extraction_plan(self, query: str) -> Dict[str, Any]:
		"""
		Scout website and create detailed extraction plan
		Like a human doing reconnaissance before executing
		"""
		logger.info(f"🕵️ Starting reconnaissance for: {query}")
		
		# PHASE 1: Initial page analysis
		initial_analysis = await self._analyze_current_page(query)
		
		# PHASE 2: Structure exploration through scrolling
		structure_analysis = await self._explore_page_structure()
		
		# PHASE 3: Pagination reconnaissance
		pagination_analysis = await self._analyze_pagination_patterns()
		
		# PHASE 4: Create execution plan
		execution_plan = await self._create_execution_strategy(
			query, initial_analysis, structure_analysis, pagination_analysis
		)
		
		logger.info("📋 Reconnaissance complete - execution plan created")
		
		return {
			"query": query,
			"initial_analysis": initial_analysis,
			"structure_analysis": structure_analysis,
			"pagination_analysis": pagination_analysis,
			"execution_plan": execution_plan,
			"status": "completed"
		}
	
	async def _analyze_current_page(self, query: str) -> Dict[str, Any]:
		"""Analyze current page structure and data layout"""
		logger.info("🔍 Phase 1: Analyzing current page structure...")
		
		try:
			current_url = await self.browser.get_current_url()
			page_text = await self.browser.get_page_text()
			
			# Truncate for analysis
			if len(page_text) > 10000:
				page_text = page_text[:10000] + "\\n[Analysis truncated...]"
			
			# LLM analysis of page structure
			analysis_prompt = f"""Analyze this webpage for extracting "{query}". 

Focus on:
1. How is the target data organized? (table rows, card layout, list items, etc.)
2. What HTML patterns contain the data?
3. How many items are visible on this page?
4. Are there any pagination hints ("showing X of Y", page numbers, etc.)?
5. What's the best extraction approach?

URL: {current_url}
Page Content:
{page_text}

Provide a structured analysis of the data layout and extraction approach."""
			
			analysis_result = await self.llm.generate([{
				"role": "user", 
				"content": analysis_prompt
			}])
			
			return {
				"url": current_url,
				"analysis": analysis_result,
				"content_sample": page_text[:500],
				"phase": "initial_analysis"
			}
			
		except Exception as e:
			logger.error(f"❌ Page analysis failed: {e}")
			return {"error": str(e), "phase": "initial_analysis"}
	
	async def _explore_page_structure(self) -> Dict[str, Any]:
		"""Explore page structure through strategic scrolling"""
		logger.info("🔍 Phase 2: Exploring page structure...")
		
		try:
			structure_info = {
				"scroll_positions_analyzed": [],
				"content_changes_detected": False
			}
			
			positions = [
				("top", "up", 3000),
				("middle", "down", 1500), 
				("bottom", "down", 3000)
			]
			
			for position_name, direction, pixels in positions:
				logger.info(f"📍 Analyzing {position_name} section...")
				
				await self.browser.scroll(direction, pixels)
				await asyncio.sleep(1)
				
				current_url = await self.browser.get_current_url()
				structure_info['scroll_positions_analyzed'].append({
					'position': position_name,
					'url': current_url,
					'scroll_direction': direction,
					'pixels': pixels
				})
			
			logger.info(f"✅ Explored {len(positions)} scroll positions")
			return structure_info
			
		except Exception as e:
			logger.error(f"❌ Structure exploration failed: {e}")
			return {"error": str(e), "phase": "structure_exploration"}
	
	async def _analyze_pagination_patterns(self) -> Dict[str, Any]:
		"""Analyze pagination controls and patterns"""
		logger.info("🔍 Phase 3: Analyzing pagination patterns...")
		
		try:
			# Scroll directly to bottom to find pagination (much faster)
			await self.browser.scroll_to_bottom()
			await asyncio.sleep(1)
			
			# Look for pagination elements
			pagination_selectors = [
				'a[aria-label*="next" i]',
				'button[aria-label*="next" i]',
				'.pagination a',
				'.pager a', 
				'[class*="next"]',
				'a:contains("Next")',
				'a:contains(">")',
			]
			
			pagination_candidates = []
			
			for selector in pagination_selectors:
				elements = await self.browser.find_elements(selector)
				for elem in elements:
					if elem['visible']:
						pagination_candidates.append({
							'selector': selector,
							'text': elem['text'][:50],
							'tag': elem['tag'],
							'href': elem.get('href', ''),
							'classes': elem.get('classes', '')
						})
			
			# Also check top of page (scroll to top instantly)
			await self.browser.scroll_to_top()
			await asyncio.sleep(1)
			
			return {
				"pagination_found": len(pagination_candidates) > 0,
				"candidates": pagination_candidates[:10],
				"total_candidates": len(pagination_candidates),
				"phase": "pagination_analysis"
			}
			
		except Exception as e:
			logger.error(f"❌ Pagination analysis failed: {e}")
			return {"error": str(e), "phase": "pagination_analysis"}
	
	async def _create_execution_strategy(self, query: str, initial_analysis: Dict, 
										 structure_analysis: Dict, pagination_analysis: Dict) -> Dict[str, Any]:
		"""Create comprehensive execution strategy based on reconnaissance"""
		logger.info("🎯 Phase 4: Creating execution strategy...")
		
		try:
			# Combine all reconnaissance data
			recon_summary = f"""
RECONNAISSANCE DATA:
Query: {query}

Initial Analysis:
{initial_analysis.get('analysis', 'Failed')}

Structure Exploration:
- Positions analyzed: {len(structure_analysis.get('scroll_positions_analyzed', []))}
- Content changes detected: {structure_analysis.get('content_changes_detected', False)}

Pagination Analysis:
- Pagination found: {pagination_analysis.get('pagination_found', False)}
- Candidates found: {pagination_analysis.get('total_candidates', 0)}
- Best candidates: {pagination_analysis.get('candidates', [])[:3]}
"""
			
			# Get LLM to create execution strategy
			strategy_prompt = f"""{recon_summary}

Based on this reconnaissance data, create a detailed step-by-step execution plan for extracting "{query}".

Include:
1. DATA EXTRACTION STRATEGY: How to extract the target data
2. SCROLLING APPROACH: How to scroll to capture all content  
3. PAGINATION STRATEGY: How to handle pagination (if any)
4. STOP CONDITIONS: How to detect when extraction is complete
5. ESTIMATED PAGES: Rough estimate of pages to process
6. EXECUTION ORDER: Step-by-step action sequence

Make the plan specific and actionable."""
			
			strategy_result = await self.llm.generate([{
				"role": "user",
				"content": strategy_prompt
			}])
			
			return {
				"execution_strategy": strategy_result,
				"reconnaissance_summary": recon_summary,
				"confidence": "high" if not any('error' in x for x in [initial_analysis, structure_analysis, pagination_analysis]) else "medium"
			}
			
		except Exception as e:
			logger.error(f"❌ Strategy creation failed: {e}")
			return {"error": str(e), "phase": "strategy_creation"}