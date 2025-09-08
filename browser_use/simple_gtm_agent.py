"""
Simple GTM Agent
Just takes URL + instructions and extracts data
"""
import asyncio
import logging
from browser_use.agent.service import Agent
from browser_use.llm.base import BaseChatModel
from browser_use.tools.simple_tools import SimpleTools

logger = logging.getLogger(__name__)


class SimpleGTMAgent:
	"""Simple GTM agent - just URL + instructions"""
	
	def __init__(self, llm: BaseChatModel):
		self.llm = llm
		self.tools = SimpleTools()
	
	async def extract(self, url: str, instructions: str) -> str:
		"""
		Extract data from URL using instructions
		
		Args:
			url: Target website URL
			instructions: What to extract and how
			
		Returns:
			Extracted data as string
		"""
		logger.info(f"🎯 GTM Agent extracting from: {url}")
		
		# Create simple task with planner-first approach
		task = f"""
Go to: {url}

Instructions: {instructions}

MANDATORY RECONNAISSANCE APPROACH:
1. FIRST: Use create_reconnaissance_plan action immediately after navigation
   - This will scout the website like a human would
   - Analyze page structure, data layout, and pagination patterns
   - Create a detailed execution plan with specific tool instructions
   - Identify optimal scrolling strategy and stop conditions

2. THEN: Follow the reconnaissance plan exactly
   - Use the tools and strategies recommended by the planner
   - Execute the plan step by step as instructed
   - The planner will tell you which pagination approach to use
   - The planner will identify where data is located and how to extract it

CRITICAL REQUIREMENTS:
- ALWAYS start with reconnaissance planning - this is like human reconnaissance
- Never skip the planner - it prevents wasted effort and ensures complete extraction
- Follow the planner's recommendations for pagination, scrolling, and extraction
- Go through ALL pages as identified by the planner
- STOP if you see the same content 2+ times (infinite loop protection)

The reconnaissance planner acts as your advance scout - use it first!
"""
		
		# Create agent with simplified tools
		agent = Agent(
			task=task,
			llm=self.llm,
			controller=self.tools
		)
		
		try:
			result = await agent.run()
			
			# Extract the final result
			if hasattr(result, 'all_results'):
				for action_result in result.all_results:
					if action_result.is_done and action_result.extracted_content:
						return action_result.extracted_content
			
			return str(result)
			
		except Exception as e:
			logger.error(f"❌ GTM extraction failed: {e}")
			return f"Extraction failed: {str(e)}"


# Quick function for simple usage
async def extract_gtm_data(url: str, instructions: str, llm: BaseChatModel) -> str:
	"""
	Simple function to extract GTM data
	
	Args:
		url: Website URL
		instructions: What to extract
		llm: Language model
		
	Returns:
		Extracted data as string
	"""
	agent = SimpleGTMAgent(llm)
	return await agent.extract(url, instructions)