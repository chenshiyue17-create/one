from __future__ import annotations

from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, HttpUrl

from xhs_utils.browser_cookie import get_xhs_cookies_from_browser


class CookieReadRequest(BaseModel):
    browser_type: Literal["chrome", "edge", "firefox", "safari", "auto"] = "auto"


class CookiePushRequest(CookieReadRequest):
    server_base_url: HttpUrl
    access_token: str = Field(min_length=8)
    sub_type: Literal["pc", "creator"] = "pc"
    sync_creator: bool = True


def _read_cookie(browser_type: str) -> str:
    selected_browser = None if browser_type == "auto" else browser_type
    cookie_string, error = get_xhs_cookies_from_browser(selected_browser)
    if error or not cookie_string:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"未读取到小红书登录 Cookie：{error or '浏览器未登录或 Cookie 为空'}",
        )
    return cookie_string


def create_app() -> FastAPI:
    app = FastAPI(title="Spider XHS Local Login Helper")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "xhs-local-helper", "bind": "127.0.0.1:8765"}

    @app.post("/xhs/cookies/read")
    def read_cookies(payload: CookieReadRequest) -> dict[str, object]:
        cookie_string = _read_cookie(payload.browser_type)
        names = []
        for item in cookie_string.split(";"):
            name = item.strip().split("=", 1)[0]
            if name:
                names.append(name)
        return {
            "ok": True,
            "browser_type": payload.browser_type,
            "cookie_count": len(names),
            "cookie_names": names[:40],
            "has_required": any(name in {"a1", "web_session", "customer_session"} for name in names),
        }

    @app.post("/xhs/cookies/push-to-server")
    async def push_to_server(payload: CookiePushRequest) -> dict[str, object]:
        cookie_string = _read_cookie(payload.browser_type)
        endpoint = str(payload.server_base_url).rstrip("/") + "/api/accounts/import-cookie"
        request_body = {
            "platform": "xhs",
            "sub_type": payload.sub_type,
            "cookie_string": cookie_string,
            "sync_creator": payload.sync_creator,
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    endpoint,
                    json=request_body,
                    headers={"Authorization": f"Bearer {payload.access_token}"},
                )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"服务器连接失败：{exc}") from exc
        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json().get("detail", detail)
            except ValueError:
                pass
            raise HTTPException(status_code=response.status_code, detail=detail)
        return {"ok": True, "server": endpoint, "account": response.json()}

    return app


app = create_app()
