from __future__ import annotations

import threading
import time
import uuid
import asyncio
import base64
from dataclasses import dataclass, replace
from typing import Any


LOGIN_SUCCESS_SELECTORS = [
    ".main-container .user .link-wrapper .channel",
    ".user-info",
    "[class*='user'] [class*='avatar']",
]

CAPTCHA_SELECTORS = [
    "iframe[src*='captcha']",
    "iframe[src*='redcaptcha']",
    "[class*='captcha']",
    "[id*='captcha']",
    "[class*='verify']",
    "[id*='verify']",
    ".red-captcha",
    ".geetest_panel",
    ".yidun",
]

CAPTCHA_TEXT_KEYWORDS = ["验证码", "安全验证", "滑块", "拖动", "验证", "captcha", "verify"]


@dataclass
class BrowserQrState:
    session_key: str
    status: str
    message: str
    qr_image_data_url: str | None = None
    qr_url: str | None = None
    cookies: dict[str, str] | None = None


@dataclass
class _BrowserSession:
    key: str
    created_at: float
    ready: threading.Event
    stop: threading.Event
    thread: threading.Thread
    state: BrowserQrState


class XhsBrowserLoginManager:
    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl_seconds = ttl_seconds
        self._lock = threading.RLock()
        self._sessions: dict[str, _BrowserSession] = {}

    def create_session(self) -> BrowserQrState:
        session_key = uuid.uuid4().hex
        ready = threading.Event()
        stop = threading.Event()
        session = _BrowserSession(
            key=session_key,
            created_at=time.time(),
            ready=ready,
            stop=stop,
            thread=threading.Thread(),
            state=BrowserQrState(
                session_key=session_key,
                status="starting",
                message="服务器浏览器正在生成二维码",
                qr_url="https://www.xiaohongshu.com/explore",
            ),
        )
        thread = threading.Thread(
            target=self._run_browser_session,
            args=(session,),
            name=f"xhs-browser-login-{session_key[:8]}",
            daemon=True,
        )
        session.thread = thread
        with self._lock:
            self._sessions[session_key] = session
        thread.start()

        if not ready.wait(timeout=75):
            self.close_session(session_key)
            raise RuntimeError("服务器浏览器二维码生成超时")

        state = self._get_state(session_key)
        if state.status == "expired":
            self.close_session(session_key)
            raise RuntimeError(state.message)
        return state

    def poll_session(self, session_key: str) -> BrowserQrState:
        with self._lock:
            session = self._sessions.get(session_key)
            if session is None:
                return BrowserQrState(
                    session_key=session_key,
                    status="expired",
                    message="服务器浏览器登录会话已失效，请刷新二维码",
                )
            if time.time() - session.created_at > self.ttl_seconds and session.state.status not in {"confirmed", "expired"}:
                session.stop.set()
                session.state = replace(session.state, status="expired", message="二维码已过期，请刷新")
            return self._copy_state(session.state)

    def close_session(self, session_key: str) -> None:
        with self._lock:
            session = self._sessions.pop(session_key, None)
        if session is not None:
            session.stop.set()

    def _get_state(self, session_key: str) -> BrowserQrState:
        with self._lock:
            session = self._sessions.get(session_key)
            if session is None:
                return BrowserQrState(session_key=session_key, status="expired", message="服务器浏览器登录会话已失效")
            return self._copy_state(session.state)

    def _set_state(self, session: _BrowserSession, **updates: Any) -> None:
        with self._lock:
            session.state = replace(session.state, **updates)

    def _run_browser_session(self, session: _BrowserSession) -> None:
        asyncio.run(self._run_browser_session_async(session))

    async def _run_browser_session_async(self, session: _BrowserSession) -> None:
        from playwright.async_api import async_playwright

        playwright = None
        browser = None
        context = None
        page = None
        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/121.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
                locale="zh-CN",
            )
            page = await context.new_page()
            await page.goto("https://www.xiaohongshu.com/explore", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_selector(".login-container .qrcode-img", timeout=60000)
            qr_image_data_url = await page.locator(".login-container .qrcode-img").first.get_attribute("src")
            if not qr_image_data_url:
                raise RuntimeError("登录页未返回二维码图片")
            self._set_state(
                session,
                status="pending",
                message="请使用小红书 App 扫描二维码，并在手机端确认登录",
                qr_image_data_url=qr_image_data_url,
                qr_url=page.url,
            )
            session.ready.set()

            while not session.stop.is_set():
                if time.time() - session.created_at > self.ttl_seconds:
                    self._set_state(session, status="expired", message="二维码已过期，请刷新", qr_url=page.url)
                    break
                try:
                    state = await self._inspect_page(session, page, context)
                    self._set_state(session, **state)
                    if state.get("status") == "confirmed":
                        break
                except Exception as exc:
                    self._set_state(
                        session,
                        status="pending",
                        message=f"检查服务器浏览器登录状态失败，稍后自动重试（{exc}）",
                        qr_url=page.url if page else "https://www.xiaohongshu.com/explore",
                    )
                session.stop.wait(timeout=2)
        except Exception as exc:
            self._set_state(session, status="expired", message=f"服务器浏览器二维码生成失败: {exc}")
            session.ready.set()
        finally:
            for resource in (context, browser):
                if resource is None:
                    continue
                try:
                    await resource.close()
                except Exception:
                    pass
            if playwright is not None:
                try:
                    await playwright.stop()
                except Exception:
                    pass

    async def _inspect_page(self, session: _BrowserSession, page: Any, context: Any) -> dict[str, Any]:
        captcha = await self._detect_captcha(page)
        if captcha:
            screenshot_data_url = await self._page_screenshot_data_url(page)
            return {
                "status": "captcha",
                "message": f"服务器浏览器触发验证码：{captcha}。该验证码不会弹到本地网页，已显示服务器页面截图；请刷新二维码重试，或改用本地登录同步/手机号登录。",
                "qr_image_data_url": screenshot_data_url,
                "qr_url": page.url,
            }

        for selector in LOGIN_SUCCESS_SELECTORS:
            if await page.locator(selector).count() > 0:
                cookies = self._cookies_to_dict(await context.cookies())
                if cookies.get("web_session") or cookies.get("customer_session"):
                    return {
                        "status": "confirmed",
                        "message": f"浏览器登录成功，已获取 cookies：{', '.join(sorted(cookies)[:8])}",
                        "qr_url": page.url,
                        "cookies": cookies,
                    }
                return {
                    "status": "scanned",
                    "message": f"已确认扫码，正在等待登录 cookies 写入（url={page.url}）",
                    "qr_url": page.url,
                }

        if await page.locator(".login-container .qrcode-img").count() == 0:
            return {
                "status": "scanned",
                "message": f"已扫码或页面跳转中，请稍候（url={page.url}）",
                "qr_url": page.url,
            }

        return {
            "status": "pending",
            "message": f"等待扫码确认（url={page.url}）",
            "qr_url": page.url,
        }

    async def _detect_captcha(self, page: Any) -> str | None:
        for selector in CAPTCHA_SELECTORS:
            try:
                if await page.locator(selector).count() > 0:
                    return selector
            except Exception:
                continue
        try:
            body_text = (await page.locator("body").inner_text(timeout=1000)).lower()
        except Exception:
            return None
        for keyword in CAPTCHA_TEXT_KEYWORDS:
            if keyword.lower() in body_text:
                return keyword
        return None

    @staticmethod
    async def _page_screenshot_data_url(page: Any) -> str:
        image_bytes = await page.screenshot(full_page=False, type="png")
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    @staticmethod
    def _cookies_to_dict(cookies: list[dict[str, Any]]) -> dict[str, str]:
        result: dict[str, str] = {}
        for cookie in cookies:
            domain = str(cookie.get("domain") or "")
            name = str(cookie.get("name") or "")
            value = str(cookie.get("value") or "")
            if name and value and "xiaohongshu.com" in domain:
                result[name] = value
        return result

    @staticmethod
    def _copy_state(state: BrowserQrState) -> BrowserQrState:
        cookies = dict(state.cookies) if state.cookies else None
        return replace(state, cookies=cookies)


browser_login_manager = XhsBrowserLoginManager()


def get_browser_login_manager() -> XhsBrowserLoginManager:
    return browser_login_manager
