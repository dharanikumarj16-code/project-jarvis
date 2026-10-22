import os
import asyncio
from playwright.async_api import async_playwright, Browser, Page
from app.permissions import check_permission, PermissionLevel

class BrowserManager:
    _instance = None

    def __init__(self):
        self.playwright = None
        self.browser: Browser = None
        self.page: Page = None
        self.element_mapping = {}  # element_id -> locator info
        
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def start_browser(self):
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
            self.page = await self.browser.new_page()
            # Setup downloads path
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.downloads_dir = os.path.join(base_dir, "downloads")
            os.makedirs(self.downloads_dir, exist_ok=True)
        return {"success": True}

    async def close_browser(self):
        if self.playwright:
            await self.browser.close()
            await self.playwright.stop()
            self.playwright = None
            self.browser = None
            self.page = None
        return {"success": True}

    async def _ensure_running(self):
        if not self.page:
            await self.start_browser()

    async def open_url(self, url: str):
        if not check_permission("browser_open_url", PermissionLevel.LOW_RISK, {"url": url}):
            return {"success": False, "error": "Permission denied"}
        await self._ensure_running()
        try:
            if not url.startswith("http"):
                url = "https://" + url
            await self.page.goto(url, timeout=30000)
            return {"success": True, "url": self.page.url, "title": await self.page.title()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_current_url(self):
        if not self.page:
            return {"success": False, "error": "Browser not running"}
        return {"success": True, "url": self.page.url}

    async def get_page_title(self):
        if not self.page:
            return {"success": False, "error": "Browser not running"}
        return {"success": True, "title": await self.page.title()}

    async def go_back(self):
        if not self.page:
            return {"success": False, "error": "Browser not running"}
        try:
            await self.page.go_back()
            return {"success": True, "url": self.page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def scroll(self, direction: str = "down"):
        if not check_permission("browser_scroll", PermissionLevel.LOW_RISK, {"direction": direction}):
            return {"success": False, "error": "Permission denied"}
        if not self.page:
            return {"success": False, "error": "Browser not running"}
        try:
            if direction == "down":
                await self.page.evaluate("window.scrollBy(0, window.innerHeight)")
            elif direction == "up":
                await self.page.evaluate("window.scrollBy(0, -window.innerHeight)")
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_page_state(self):
        if not check_permission("browser_get_state", PermissionLevel.READ, {}):
            return {"success": False, "error": "Permission denied"}
        await self._ensure_running()
        self.element_mapping = {}
        
        try:
            state = {
                "url": self.page.url,
                "title": await self.page.title(),
                "interactive_elements": []
            }
            
            # Basic DOM compression for LLM context
            js_script = """
            () => {
                const elements = Array.from(document.querySelectorAll('a, button, input, select, textarea'));
                return elements.map((el, index) => {
                    const rect = el.getBoundingClientRect();
                    // Basic visibility check
                    if (rect.width === 0 || rect.height === 0 || rect.top < 0 || rect.top > window.innerHeight) return null;
                    return {
                        tag: el.tagName.toLowerCase(),
                        text: el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || el.id || '',
                        index: index
                    };
                }).filter(e => e !== null && e.text.trim() !== '');
            }
            """
            raw_elements = await self.page.evaluate(js_script)
            
            for el in raw_elements:
                element_id = f"{el['tag']}_{el['index']}"
                self.element_mapping[element_id] = el
                
                state["interactive_elements"].append({
                    "id": element_id,
                    "text": el["text"][:50].strip()
                })
                
            return {"success": True, "state": state}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def click_element(self, element_id: str):
        if not check_permission("browser_click", PermissionLevel.ACTION, {"element_id": element_id}):
            return {"success": False, "error": "Permission denied"}
        if not self.page:
            return {"success": False, "error": "Browser not running"}
        
        try:
            if element_id not in self.element_mapping:
                return {"success": False, "error": f"Element {element_id} not found."}
            
            index = self.element_mapping[element_id]["index"]
            js_click = f"""
            () => {{
                const elements = Array.from(document.querySelectorAll('a, button, input, select, textarea'));
                if (elements[{index}]) {{
                    elements[{index}].click();
                    return true;
                }}
                return false;
            }}
            """
            if await self.page.evaluate(js_click):
                # Wait for any navigation
                try:
                    await self.page.wait_for_load_state('networkidle', timeout=2000)
                except:
                    pass
                return {"success": True, "message": f"Clicked {element_id}", "new_url": self.page.url}
            return {"success": False, "error": "Element could not be clicked"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def type_text(self, element_id: str, text: str):
        if not check_permission("browser_type", PermissionLevel.ACTION, {"element_id": element_id, "text": text}):
            return {"success": False, "error": "Permission denied"}
        if not self.page:
            return {"success": False, "error": "Browser not running"}
        
        try:
            if element_id not in self.element_mapping:
                return {"success": False, "error": f"Element {element_id} not found."}
            
            index = self.element_mapping[element_id]["index"]
            js_type = f"""
            () => {{
                const elements = Array.from(document.querySelectorAll('a, button, input, select, textarea'));
                const el = elements[{index}];
                if (el) {{
                    el.value = {repr(text)};
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return true;
                }}
                return false;
            }}
            """
            if await self.page.evaluate(js_type):
                return {"success": True, "message": f"Typed text into {element_id}"}
            return {"success": False, "error": "Element could not be typed into"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

async def open_url(url: str): return await BrowserManager.get_instance().open_url(url)
async def scroll(direction: str = "down"): return await BrowserManager.get_instance().scroll(direction)
async def get_page_state(): return await BrowserManager.get_instance().get_page_state()
async def click_element(element_id: str): return await BrowserManager.get_instance().click_element(element_id)
async def type_text(element_id: str, text: str): return await BrowserManager.get_instance().type_text(element_id, text)
async def close_browser(): return await BrowserManager.get_instance().close_browser()
