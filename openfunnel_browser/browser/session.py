"""
Minimal browser session for GTM data extraction
Focuses only on essential CDP operations needed for web scraping
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
import tempfile
import subprocess
import json
import websockets
import html2text

logger = logging.getLogger(__name__)


class BrowserSession:
	"""Minimal browser session focused on GTM data extraction"""
	
	def __init__(self, headless: bool = True):
		self.headless = headless
		self.browser_process = None
		self.websocket = None
		self.page_id = None
		self.session_id = None
		self._request_id = 0
		
	async def start(self):
		"""Start Chrome browser and connect via CDP"""
		# Create user data directory
		self.user_data_dir = tempfile.mkdtemp()
		
		# Chrome launch arguments
		chrome_args = [
			'--remote-debugging-port=9222',
			f'--user-data-dir={self.user_data_dir}',
			'--no-first-run',
			'--no-default-browser-check',
			'--disable-extensions',
			'--disable-background-timer-throttling',
			'--disable-backgrounding-occluded-windows',
			'--disable-renderer-backgrounding',
		]
		
		if self.headless:
			chrome_args.extend(['--headless', '--disable-gpu'])
		else:
			# Headful mode - add window size for visibility
			chrome_args.extend(['--window-size=1200,800'])
		
		# Find Chrome executable
		chrome_paths = [
			'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',  # macOS
			'/Applications/Chromium.app/Contents/MacOS/Chromium',  # macOS Chromium
			'google-chrome',  # Linux
			'chromium',  # Linux Chromium
			'chrome',  # Generic
		]
		
		chrome_exe = None
		for path in chrome_paths:
			if Path(path).exists() or path in ['google-chrome', 'chromium', 'chrome']:
				try:
					# Test if the command works
					result = subprocess.run([path, '--version'], 
										   capture_output=True, timeout=5)
					if result.returncode == 0:
						chrome_exe = path
						break
				except (subprocess.TimeoutExpired, FileNotFoundError):
					continue
		
		if not chrome_exe:
			raise Exception("Chrome/Chromium not found. Please install Chrome or Chromium browser.")
		
		logger.info(f"🌐 Using Chrome at: {chrome_exe}")
		
		# Launch Chrome
		self.browser_process = subprocess.Popen(
			[chrome_exe] + chrome_args,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE
		)
		
		# Wait for Chrome to start
		await asyncio.sleep(2)
		
		# Get available targets
		import httpx
		async with httpx.AsyncClient() as client:
			response = await client.get('http://localhost:9222/json')
			targets = response.json()
		
		# Find or create a page target
		page_target = None
		for target in targets:
			if target['type'] == 'page':
				page_target = target
				break
		
		if not page_target:
			# Create new page
			async with httpx.AsyncClient() as client:
				response = await client.post('http://localhost:9222/json/new?about:blank')
				page_target = response.json()
		
		self.page_id = page_target['id']
		
		# Connect to the page's WebSocket
		self.websocket = await websockets.connect(page_target['webSocketDebuggerUrl'])
		
		# Enable necessary domains
		await self._send_command('Runtime.enable')
		await self._send_command('Page.enable')  
		await self._send_command('DOM.enable')
		
		logger.info("🚀 Browser session started successfully")
		
	async def close(self):
		"""Close browser session"""
		if self.websocket:
			await self.websocket.close()
		if self.browser_process:
			self.browser_process.terminate()
			self.browser_process.wait()
		logger.info("🔚 Browser session closed")
	
	async def navigate(self, url: str):
		"""Navigate to URL"""
		await self._send_command('Page.navigate', {'url': url})
		await asyncio.sleep(3)  # Wait for page load
		logger.info(f"📍 Navigated to: {url}")
	
	async def get_page_content(self) -> str:
		"""Get page HTML content"""
		response = await self._send_command('DOM.getDocument')
		root_node_id = response['result']['root']['nodeId']
		
		html_response = await self._send_command('DOM.getOuterHTML', {
			'nodeId': root_node_id
		})
		return html_response['result']['outerHTML']
	
	async def get_page_text(self) -> str:
		"""Get page content as clean text"""
		html_content = await self.get_page_content()
		
		# Convert HTML to text
		h = html2text.HTML2Text()
		h.ignore_images = True
		h.ignore_links = True
		h.body_width = 0
		return h.handle(html_content)
	
	async def scroll(self, direction: str = 'down', pixels: int = 1000):
		"""Scroll page up or down"""
		script = f"""
		window.scrollBy(0, {pixels if direction == 'down' else -pixels});
		"""
		await self._send_command('Runtime.evaluate', {'expression': script})
		await asyncio.sleep(1)  # Wait for scroll to complete
		logger.info(f"📜 Scrolled {direction} {pixels} pixels")
	
	async def scroll_to_bottom(self):
		"""Instantly scroll to the very bottom of the page"""
		script = """
		window.scrollTo(0, document.body.scrollHeight);
		"""
		await self._send_command('Runtime.evaluate', {'expression': script})
		await asyncio.sleep(2)  # Wait for content to load/render
		logger.info("📜 Scrolled to bottom of page")
	
	async def scroll_to_top(self):
		"""Instantly scroll to the very top of the page"""
		script = """
		window.scrollTo(0, 0);
		"""
		await self._send_command('Runtime.evaluate', {'expression': script})
		await asyncio.sleep(1)  # Wait for scroll to complete
		logger.info("📜 Scrolled to top of page")
	
	async def click_element(self, selector: str):
		"""Click element by CSS selector"""
		# Handle :contains() pseudo-selector for clicking
		if ':contains(' in selector:
			import re
			match = re.search(r':contains\("([^"]+)"\)', selector)
			if match:
				search_text = match.group(1)
				base_selector = selector.split(':contains(')[0] or '*'
				script = f"""
				var elements = Array.from(document.querySelectorAll('{base_selector}')).filter(el => 
					el.innerText && el.innerText.includes('{search_text}')
				);
				if (elements.length > 0) {{
					elements[0].click();
					true;
				}} else {{
					false;
				}}
				"""
			else:
				return False
		else:
			script = f"""
			var element = document.querySelector('{selector}');
			if (element) {{
				element.click();
				true;
			}} else {{
				false;
			}}
			"""
		
		try:
			response = await self._send_command('Runtime.evaluate', {'expression': script})
			result = response.get('result', {})
			success = result.get('value', False)
			
			if success:
				await asyncio.sleep(3)  # Wait for navigation/action
				logger.info(f"🖱️ Successfully clicked: {selector}")
				return True
			else:
				logger.warning(f"⚠️ Element not found: {selector}")
				return False
		except Exception as e:
			logger.error(f"❌ Failed to click {selector}: {e}")
			return False
	
	async def type_text(self, selector: str, text: str, clear: bool = True):
		"""Type text into input field"""
		clear_script = f"document.querySelector('{selector}').value = '';" if clear else ""
		script = f"""
		{clear_script}
		document.querySelector('{selector}').value = '{text}';
		document.querySelector('{selector}').dispatchEvent(new Event('input', {{bubbles: true}}));
		"""
		try:
			await self._send_command('Runtime.evaluate', {'expression': script})
			logger.info(f"⌨️ Typed text into {selector}")
			return True
		except Exception as e:
			logger.error(f"❌ Failed to type into {selector}: {e}")
			return False
	
	async def find_elements(self, selector: str) -> List[Dict[str, Any]]:
		"""Find elements by CSS selector or text content"""
		# Handle :contains() pseudo-selector manually since it's not standard CSS
		if ':contains(' in selector:
			# Extract the text to search for
			import re
			match = re.search(r':contains\("([^"]+)"\)', selector)
			if match:
				search_text = match.group(1)
				base_selector = selector.split(':contains(')[0] or '*'
				script = f"""
				Array.from(document.querySelectorAll('{base_selector}')).filter(el => 
					el.innerText && el.innerText.includes('{search_text}')
				).map((el, i) => ({{
					index: i,
					text: (el.innerText || el.textContent || '').trim(),
					tag: el.tagName.toLowerCase(),
					href: el.href || '',
					classes: el.className || '',
					visible: el.offsetParent !== null
				}}))
				"""
			else:
				return []
		else:
			script = f"""
			Array.from(document.querySelectorAll('{selector}')).map((el, i) => ({{
				index: i,
				text: (el.innerText || el.textContent || '').trim(),
				tag: el.tagName.toLowerCase(),
				href: el.href || '',
				classes: el.className || '',
				visible: el.offsetParent !== null
			}}))
			"""
		
		try:
			response = await self._send_command('Runtime.evaluate', {'expression': script})
			result = response.get('result', {})
			if 'value' in result:
				return result['value']
			else:
				return []
		except Exception as e:
			logger.error(f"❌ Failed to find elements {selector}: {e}")
			return []
	
	async def get_current_url(self) -> str:
		"""Get current page URL"""
		script = "window.location.href"
		response = await self._send_command('Runtime.evaluate', {'expression': script})
		result = response.get('result', {})
		if 'value' in result:
			return result['value']
		elif 'result' in result and 'value' in result['result']:
			return result['result']['value']
		else:
			# Fallback: try getting from page info
			import httpx
			async with httpx.AsyncClient() as client:
				response = await client.get('http://localhost:9222/json')
				targets = response.json()
				for target in targets:
					if target['id'] == self.page_id:
						return target.get('url', 'about:blank')
			return 'about:blank'
	
	async def _send_command(self, method: str, params: Optional[Dict[str, Any]] = None):
		"""Send CDP command"""
		self._request_id += 1
		message = {
			'id': self._request_id,
			'method': method,
			'params': params or {}
		}
		
		await self.websocket.send(json.dumps(message))
		
		# Wait for response
		while True:
			response_text = await self.websocket.recv()
			response = json.loads(response_text)
			
			if 'id' in response and response['id'] == self._request_id:
				if 'error' in response:
					raise Exception(f"CDP Error: {response['error']}")
				return response
			# Ignore other messages (events, etc.)