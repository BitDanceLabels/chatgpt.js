import asyncio
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from playwright.async_api import BrowserContext, Page, async_playwright


class ChatGPTController:
    """Manage a persistent ChatGPT browser session and expose helpers."""

    def __init__(
        self,
        user_data_dir: Path,
        chatgpt_js_path: Path,
        headless: bool = True,
        nav_timeout_ms: int = 30000,
        start_url: str = "https://chatgpt.com",
        executable_path: Optional[str] = None,
        bypass_csp: bool = True,
        chromium_args: Optional[list[str]] = None,
        ignore_default_args: Optional[list[str]] = None,
    ) -> None:
        self._user_data_dir = user_data_dir
        self._chatgpt_js_path = chatgpt_js_path
        self._headless = headless
        self._nav_timeout_ms = nav_timeout_ms
        self._start_url = start_url
        self._executable_path = executable_path
        self._bypass_csp = bypass_csp
        self._chromium_args = chromium_args or []
        self._ignore_default_args = ignore_default_args

        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._lock = asyncio.Lock()

    @property
    def ready(self) -> bool:
        return self._page is not None

    async def start(self) -> None:
        if self._page:
            return

        if not self._chatgpt_js_path.exists():
            raise FileNotFoundError(f"chatgpt.js not found at {self._chatgpt_js_path}")

        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            str(self._user_data_dir),
            headless=self._headless,
            executable_path=self._executable_path,
            bypass_csp=self._bypass_csp,
            args=self._chromium_args,
            ignore_default_args=self._ignore_default_args,
        )
        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()

        await self._page.goto(self._start_url, wait_until="domcontentloaded", timeout=self._nav_timeout_ms)
        # Inject chatgpt.js so the page has the helper API.
        await self._page.add_script_tag(path=str(self._chatgpt_js_path))

    async def shutdown(self) -> None:
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()

    async def status(self) -> dict[str, Any]:
        if not self._page:
            return {"ready": False, "idle": False}
        try:
            idle = await self._page.evaluate(
                """async () => {
                    if (typeof chatgpt === 'undefined' || !chatgpt.isIdle) return false;
                    return await chatgpt.isIdle();
                }"""
            )
            return {"ready": True, "idle": bool(idle)}
        except Exception:
            return {"ready": True, "idle": False}

    async def ask(self, prompt: str, timeout: int = 60) -> str:
        await self._ensure_ready()
        async with self._lock:
            try:
                return await self._page.evaluate(
                    """async (prompt, timeout) => {
                        if (typeof chatgpt === 'undefined' || !chatgpt.ask) {
                            throw new Error('chatgpt.js is not available');
                        }
                        return await chatgpt.ask(prompt, { timeout });
                    }""",
                    prompt,
                    timeout,
                )
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"ask failed: {exc}") from exc

    async def continue_last(self) -> str:
        await self._ensure_ready()
        async with self._lock:
            try:
                return await self._page.evaluate(
                    """async () => {
                        if (!chatgpt.continue) throw new Error('chatgpt.continue unavailable');
                        return await chatgpt.continue();
                    }"""
                )
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"continue failed: {exc}") from exc

    async def stop(self) -> bool:
        await self._ensure_ready()
        async with self._lock:
            try:
                return await self._page.evaluate(
                    """async () => {
                        if (!chatgpt.stop) return false;
                        await chatgpt.stop();
                        return true;
                    }"""
                )
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"stop failed: {exc}") from exc

    async def history(self) -> Any:
        await self._ensure_ready()
        try:
            return await self._page.evaluate(
                """async () => {
                    if (chatgpt.getChatData) return await chatgpt.getChatData();
                    if (chatgpt.getConversation) return await chatgpt.getConversation();
                    return null;
                }"""
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"history failed: {exc}") from exc

    async def last_reply(self) -> Optional[str]:
        await self._ensure_ready()
        try:
            return await self._page.evaluate(
                """async () => {
                    if (chatgpt.getLastReply) return await chatgpt.getLastReply();
                    if (chatgpt.getLastResponse) return await chatgpt.getLastResponse();
                    return null;
                }"""
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"last_reply failed: {exc}") from exc

    async def clear(self) -> bool:
        await self._ensure_ready()
        async with self._lock:
            try:
                return await self._page.evaluate(
                    """async () => {
                        if (chatgpt.clearChats) { await chatgpt.clearChats(); return true; }
                        const newChatBtn = document.querySelector('a[href="/"]') || document.querySelector('a[href="/chat"]');
                        if (newChatBtn) { newChatBtn.click(); return true; }
                        return false;
                    }"""
                )
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"clear failed: {exc}") from exc

    async def _ensure_ready(self) -> None:
        if not self._page:
            raise HTTPException(status_code=503, detail="ChatGPT page not ready")


def build_controller() -> ChatGPTController:
    repo_root = Path(__file__).resolve().parents[2]
    chatgpt_js_path = repo_root / "chatgpt.js"

    user_data_dir = Path(os.getenv("USER_DATA_DIR", repo_root / ".chatgpt-session"))
    headless = os.getenv("HEADLESS", "true").lower() != "false"
    nav_timeout_ms = int(os.getenv("NAV_TIMEOUT_MS", "30000"))
    executable_path = os.getenv("CHROME_EXECUTABLE")
    bypass_csp = os.getenv("BYPASS_CSP", "true").lower() != "false"
    ignore_automation_flag = os.getenv("IGNORE_AUTOMATION_FLAG", "true").lower() != "false"
    chromium_args_env = os.getenv("CHROMIUM_ARGS", "")
    chromium_args = chromium_args_env.split() if chromium_args_env else []
    ignore_default_args = ["--disable-blink-features=AutomationControlled"] if ignore_automation_flag else None

    return ChatGPTController(
        user_data_dir=user_data_dir,
        chatgpt_js_path=chatgpt_js_path,
        headless=headless,
        nav_timeout_ms=nav_timeout_ms,
        executable_path=executable_path,
        bypass_csp=bypass_csp,
        chromium_args=chromium_args,
        ignore_default_args=ignore_default_args,
    )
