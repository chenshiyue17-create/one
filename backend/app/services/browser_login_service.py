"""
Browser-based XHS login service with captcha relay.

Opens a real Chromium browser (headless with xvfb on Linux, visible on macOS)
and relays screenshots + captcha interactions between server and frontend.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import time
import uuid
import platform
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from loguru import logger

# Playwright imports - lazy loaded
_playwright_async_api = None

def _get_playwright():
    global _playwright_async_api
    if _playwright_async_api is None:
        from playwright.async_api import async_playwright
        _playwright_async_api = async_playwright
    return _playwright_async_api


class LoginState(str, Enum):
    IDLE = "idle"
    LOADING = "loading"
    QR_READY = "qr_ready"
    QR_SCANNED = "qr_scanned"
    CAPTCHA_NEEDED = "captcha_needed"
    CAPTCHA_SUBMITTED = "captcha_submitted"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    EXPIRED = "expired"
    ERROR = "error"


@dataclass
class BrowserSession:
    session_id: str
    state: LoginState = LoginState.IDLE
    status_text: str = ""
    screenshot_b64: str | None = None
    qr_image_b64: str | None = None
    captcha_image_b64: str | None = None
    cookies: dict[str, str] = field(default_factory=dict)
    user_info: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    created_at: float = field(default_factory=time.time)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _browser: Any = None
    _context: Any = None
    _page: Any = None
    _playwright: Any = None
    _task: asyncio.Task | None = None
    # Callbacks
    on_state_change: Callable[[str, LoginState, str], Any] | None = None
    on_captcha: Callable[[str, str], Any] | None = None
    on_success: Callable[[str, dict], Any] | None = None


class BrowserLoginManager:
    """Singleton manager for browser login sessions."""

    _instance: BrowserLoginManager | None = None
    _sessions: dict[str, BrowserSession] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def create_session(cls) -> BrowserSession:
        session_id = str(uuid.uuid4())[:12]
        session = BrowserSession(session_id=session_id)
        cls._sessions[session_id] = session
        return session

    @classmethod
    def get_session(cls, session_id: str) -> BrowserSession | None:
        return cls._sessions.get(session_id)

    @classmethod
    def remove_session(cls, session_id: str):
        cls._sessions.pop(session_id, None)

    @classmethod
    async def cleanup_all(cls):
        for session in list(cls._sessions.values()):
            await cls._close_browser(session)
        cls._sessions.clear()

    @staticmethod
    async def _close_browser(session: BrowserSession):
        try:
            if session._context:
                await session._context.close()
        except Exception:
            pass
        try:
            if session._browser:
                await session._browser.close()
        except Exception:
            pass
        try:
            if session._playwright:
                await session._playwright.stop()
        except Exception:
            pass
        session._browser = None
        session._context = None
        session._page = None
        session._playwright = None

    @staticmethod
    async def _capture_screenshot(page) -> str:
        """Capture page screenshot as base64 PNG."""
        try:
            data = await page.screenshot(type="png", full_page=False)
            return base64.b64encode(data).decode("ascii")
        except Exception as e:
            logger.warning(f"Screenshot failed: {e}")
            return ""

    @staticmethod
    async def _capture_element_screenshot(page, selector: str) -> str | None:
        """Capture a specific element as base64 PNG."""
        try:
            element = await page.query_selector(selector)
            if element:
                data = await element.screenshot(type="png")
                return base64.b64encode(data).decode("ascii")
        except Exception as e:
            logger.warning(f"Element screenshot failed for '{selector}': {e}")
        return None

    @staticmethod
    async def _is_captcha_visible(page) -> tuple[bool, str | None]:
        """Check if a captcha/verification dialog is visible on page."""
        captcha_selectors = [
            ".captcha", ".verify-captcha", ".geetest_panel",
            ".verify-wrap", ".redcaptcha-wrapper", ".slider-captcha",
            ".puzzle-slider", ".verify-box", ".captcha-box",
            "#captcha", "#verify", '[class*="captcha"]', '[class*="verify"]',
            '.sec-code', '.sms-code-box', '.verification-code',
        ]
        for selector in captcha_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    visible = await element.is_visible()
                    if visible:
                        return True, selector
            except Exception:
                continue
        return False, None

    @staticmethod
    async def _detect_qr_code(page) -> str | None:
        """Detect QR code image on XHS login page, return base64."""
        qr_selectors = [
            ".qrcode-img", ".login-qrcode-img", ".qrcode-image",
            'img[src*="qrcode"]', 'img[src*="qr_code"]',
            ".qrcode-wrapper img", ".qr-code img",
            'canvas[class*="qr"]', ".login-container img[src*='data:image']",
        ]
        for selector in qr_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    visible = await element.is_visible()
                    if visible:
                        data = await element.screenshot(type="png")
                        return base64.b64encode(data).decode("ascii")
            except Exception:
                continue
        return None

    @staticmethod
    async def _detect_login_success(page) -> bool:
        """Check if login was successful (user is logged in)."""
        success_indicators = [
            ".user-info", ".user-center", ".user-avatar",
            ".logged-in", ".login-success",
            'a[href*="/user/profile"]', '.avatar-wrapper',
            ".nav-user", ".header-user",
        ]
        current_url = page.url
        # If we're redirected away from login page, likely logged in
        if "login" not in current_url.lower() and "passport" not in current_url.lower():
            if "xiaohongshu.com" in current_url.lower():
                return True
        
        for selector in success_indicators:
            try:
                element = await page.query_selector(selector)
                if element:
                    visible = await element.is_visible()
                    if visible:
                        return True
            except Exception:
                continue
        return False

    async def start_login_flow(self, session_id: str):
        """Main login flow - runs in background task."""
        session = self._sessions.get(session_id)
        if not session:
            return

        async with session._lock:
            try:
                await self._run_login_flow(session)
            except asyncio.CancelledError:
                session.state = LoginState.ERROR
                session.error_message = "Login flow cancelled"
                self._notify(session)
            except Exception as e:
                logger.exception(f"Login flow error: {e}")
                session.state = LoginState.ERROR
                session.error_message = str(e)
                self._notify(session)

    def _notify(self, session: BrowserSession):
        """Notify listeners of state change."""
        if session.on_state_change:
            try:
                session.on_state_change(session.session_id, session.state, session.status_text)
            except Exception:
                pass

    async def _run_login_flow(self, session: BrowserSession):
        session.state = LoginState.LOADING
        session.status_text = "正在启动浏览器..."
        self._notify(session)

        pw = _get_playwright()
        session._playwright = await pw().start()

        # Launch arguments for headless server
        launch_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-blink-features=AutomationControlled",
        ]
        
        # Use headless=new on Linux for better compatibility
        headless = "new" if platform.system() == "Linux" else False
        
        # On macOS dev, use visible browser
        is_dev = os.environ.get("BROWSER_LOGIN_HEADLESS", "").lower() not in ("1", "true", "yes")
        if is_dev and platform.system() == "Darwin":
            headless = False

        session._browser = await session._playwright.chromium.launch(
            headless=headless if isinstance(headless, bool) else True,
            args=launch_args,
        )

        # Create context with realistic viewport
        session._context = await session._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
        )
        session._page = await session._context.new_page()

        # Navigate to XHS login
        session.status_text = "正在打开小红书登录页面..."
        self._notify(session)

        await session._page.goto("https://www.xiaohongshu.com", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        # Click login button if present
        try:
            login_btn = await session._page.query_selector('text="登录"')
            if login_btn:
                await login_btn.click()
                await asyncio.sleep(2)
        except Exception:
            pass

        # Look for QR code
        session.status_text = "正在获取二维码..."
        self._notify(session)
        
        # Try to switch to QR code login if needed
        try:
            qr_tab = await session._page.query_selector('text="扫码登录"')
            if qr_tab:
                await qr_tab.click()
                await asyncio.sleep(2)
        except Exception:
            pass

        qr_b64 = await self._detect_qr_code(session._page)
        
        if qr_b64:
            session.qr_image_b64 = qr_b64
            session.screenshot_b64 = await self._capture_screenshot(session._page)
            session.state = LoginState.QR_READY
            session.status_text = "请使用小红书 App 扫描二维码"
        else:
            # Fallback: capture full page screenshot showing QR area
            session.screenshot_b64 = await self._capture_screenshot(session._page)
            session.state = LoginState.QR_READY
            session.status_text = "请用小红书 App 扫描页面中的二维码（如看不到二维码请刷新）"

        self._notify(session)

        # Poll for login completion or captcha
        max_wait = 180  # 3 minutes timeout
        poll_interval = 1.5
        start = time.time()

        while time.time() - start < max_wait:
            # Check for captcha first
            has_captcha, captcha_selector = await self._is_captcha_visible(session._page)
            if has_captcha:
                logger.info(f"Captcha detected via selector: {captcha_selector}")
                captcha_b64 = await self._capture_element_screenshot(session._page, captcha_selector)
                if not captcha_b64:
                    captcha_b64 = await self._capture_screenshot(session._page)
                
                session.captcha_image_b64 = captcha_b64
                session.screenshot_b64 = await self._capture_screenshot(session._page)
                session.state = LoginState.CAPTCHA_NEEDED
                session.status_text = "检测到验证码，请在下方输入验证码"
                self._notify(session)
                
                # Wait for captcha to be solved (up to 120s)
                captcha_start = time.time()
                while time.time() - captcha_start < 120:
                    await asyncio.sleep(1)
                    if session.state != LoginState.CAPTCHA_NEEDED:
                        # Captcha was submitted or flow changed
                        break
                
                # If still waiting for captcha, continue polling
                if session.state == LoginState.CAPTCHA_NEEDED:
                    continue
                else:
                    # Re-check login success
                    pass

            # Check login success
            login_ok = await self._detect_login_success(session._page)
            if login_ok:
                session.state = LoginState.LOGIN_SUCCESS
                session.status_text = "登录成功！正在获取 Cookie..."
                self._notify(session)

                # Get cookies
                cookies_list = await session._context.cookies()
                cookies_dict = {}
                for c in cookies_list:
                    cookies_dict[c["name"]] = c["value"]

                session.cookies = cookies_dict
                session.screenshot_b64 = await self._capture_screenshot(session._page)
                
                await self._close_browser(session)
                logger.info(f"Login successful, {len(cookies_dict)} cookies captured")
                return

            # Check for QR scan status
            try:
                current_url = session._page.url
                page_text = await session._page.inner_text("body")
                
                if any(word in page_text for word in ["已扫码", "扫码成功", "请在手机上确认"]):
                    if session.state != LoginState.QR_SCANNED:
                        session.state = LoginState.QR_SCANNED
                        session.status_text = "已扫码，请在手机端确认登录"
                        session.screenshot_b64 = await self._capture_screenshot(session._page)
                        self._notify(session)
                
                if any(word in page_text for word in ["已过期", "二维码已过期", "expired"]):
                    session.state = LoginState.EXPIRED
                    session.status_text = "二维码已过期，请刷新重试"
                    self._notify(session)
                    await self._close_browser(session)
                    return
            except Exception:
                pass

            await asyncio.sleep(poll_interval)

        # Timeout
        session.state = LoginState.EXPIRED
        session.status_text = "登录超时，请刷新重试"
        self._notify(session)
        await self._close_browser(session)

    async def submit_captcha(self, session_id: str, captcha_text: str):
        """Submit captcha answer to the browser."""
        session = self._sessions.get(session_id)
        if not session or not session._page:
            raise ValueError("Session not found or browser closed")

        # Try to find captcha input and submit
        input_selectors = [
            'input[placeholder*="验证码"]', 'input[name*="captcha"]',
            'input[name*="code"]', 'input[type="text"]',
            '.captcha-input input', '.verify-input input',
            'input.sec-code-input',
        ]
        
        input_found = False
        for selector in input_selectors:
            try:
                element = await session._page.query_selector(selector)
                if element and await element.is_visible():
                    await element.click()
                    await asyncio.sleep(0.3)
                    await element.fill(captcha_text)
                    input_found = True
                    break
            except Exception:
                continue

        if not input_found:
            # Try typing directly on the page
            try:
                await session._page.keyboard.type(captcha_text, delay=100)
            except Exception:
                raise ValueError("无法找到验证码输入框")

        # Look for submit/confirm button
        submit_selectors = [
            'button:has-text("确定")', 'button:has-text("提交")',
            'button:has-text("确认")', '.captcha-submit',
            '.verify-submit', 'button[type="submit"]',
        ]
        
        submitted = False
        for selector in submit_selectors:
            try:
                element = await session._page.query_selector(selector)
                if element and await element.is_visible():
                    await element.click()
                    submitted = True
                    break
            except Exception:
                continue

        if not submitted:
            # Try pressing Enter
            await session._page.keyboard.press("Enter")

        session.state = LoginState.CAPTCHA_SUBMITTED
        session.status_text = "验证码已提交，请稍候..."
        session.captcha_image_b64 = None
        self._notify(session)

        # Wait a moment for captcha to process
        await asyncio.sleep(2)

    async def get_session_state(self, session_id: str) -> dict:
        """Get current session state for polling."""
        session = self._sessions.get(session_id)
        if not session:
            return {"session_id": session_id, "state": "not_found"}

        return {
            "session_id": session.session_id,
            "state": session.state.value,
            "status_text": session.status_text,
            "has_qr": session.qr_image_b64 is not None,
            "qr_image_b64": session.qr_image_b64,
            "has_captcha": session.captcha_image_b64 is not None,
            "captcha_image_b64": session.captcha_image_b64,
            "screenshot_b64": session.screenshot_b64,
            "cookies": session.cookies if session.state == LoginState.LOGIN_SUCCESS else None,
            "error_message": session.error_message,
            "cookies_count": len(session.cookies),
        }


# Singleton
browser_login_manager = BrowserLoginManager()
