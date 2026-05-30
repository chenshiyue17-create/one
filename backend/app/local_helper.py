from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, HttpUrl

from xhs_utils.browser_cookie import get_xhs_cookies_from_browser
from backend.app.core.config import get_settings


class CookieReadRequest(BaseModel):
    browser_type: Literal["chrome", "edge", "firefox", "safari", "auto"] = "auto"


class CookiePushRequest(CookieReadRequest):
    server_base_url: HttpUrl
    access_token: str = Field(min_length=8)
    sub_type: Literal["pc", "creator"] = "pc"
    sync_creator: bool = True


class HelperLoginRequest(BaseModel):
    server_base_url: HttpUrl
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6, max_length=128)


class HelperRefreshRequest(BaseModel):
    server_base_url: HttpUrl
    refresh_token: str = Field(min_length=8)


def _root_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _workbench_file() -> Path:
    return _root_dir() / "local-helper-workbench.html"


def _local_build_label() -> str:
    try:
        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=str(_root_dir()), text=True).strip()
    except Exception:
        sha = "unknown"
    return f"版本 {sha} · 本地工作台"


def _default_server_base_url() -> str:
    return str(get_settings().launcher_default_server_base_url).rstrip("/")


def _desktop_entry_name() -> str:
    return get_settings().launcher_desktop_entry_name


def _workbench_meta() -> dict[str, str]:
    root = _root_dir()
    server_base_url = _default_server_base_url()
    return {
        "server_base_url": server_base_url,
        "desktop_entry_name": _desktop_entry_name(),
        "project_root": str(root),
        "project_label": root.name,
        "server_accounts_url": f"{server_base_url}/platforms/xhs/accounts",
        "server_home_url": f"{server_base_url}/",
    }


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

    @app.middleware("http")
    async def allow_private_network(request: Request, call_next):
        origin = request.headers.get("origin", "*") or "*"
        req_headers = request.headers.get("access-control-request-headers", "*") or "*"

        if request.method == "OPTIONS":
            response = Response(status_code=204)
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = req_headers
            response.headers["Access-Control-Allow-Private-Network"] = "true"
            response.headers["Access-Control-Max-Age"] = "600"
            return response

        response = await call_next(request)
        response.headers.setdefault("Access-Control-Allow-Origin", origin)
        response.headers.setdefault("Vary", "Origin")
        response.headers.setdefault("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        response.headers.setdefault("Access-Control-Allow-Headers", req_headers)
        response.headers.setdefault("Access-Control-Allow-Private-Network", "true")
        return response

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "xhs-local-helper", "bind": "127.0.0.1:8765"}

    @app.get("/")
    def workbench() -> Response:
        workbench_file = _workbench_file()
        if not workbench_file.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="本地工作台页面不存在")
        meta = _workbench_meta()
        html = workbench_file.read_text(encoding="utf-8")
        html = html.replace("__LOCAL_WORKBENCH_VERSION__", _local_build_label())
        html = html.replace("__DEFAULT_SERVER_BASE_URL__", meta["server_base_url"])
        html = html.replace("__DESKTOP_ENTRY_NAME__", meta["desktop_entry_name"])
        html = html.replace("__PROJECT_ROOT__", meta["project_root"])
        html = html.replace("__PROJECT_LABEL__", meta["project_label"])
        html = html.replace("__SERVER_ACCOUNTS_URL__", meta["server_accounts_url"])
        html = html.replace("__SERVER_HOME_URL__", meta["server_home_url"])
        return Response(content=html, media_type="text/html; charset=utf-8")

    @app.get("/meta")
    def workbench_meta() -> dict[str, str]:
        meta = _workbench_meta()
        meta["build_label"] = _local_build_label()
        return meta

    @app.post("/server/login")
    async def server_login(payload: HelperLoginRequest) -> dict[str, object]:
        endpoint = str(payload.server_base_url).rstrip("/") + "/api/auth/login"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    endpoint,
                    json={"username": payload.username, "password": payload.password},
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
        body = response.json()
        return {
            "ok": True,
            "server": endpoint,
            "access_token": body.get("access_token"),
            "refresh_token": body.get("refresh_token"),
            "token_type": body.get("token_type", "bearer"),
            "user": body.get("user"),
        }

    @app.post("/server/refresh")
    async def server_refresh(payload: HelperRefreshRequest) -> dict[str, object]:
        endpoint = str(payload.server_base_url).rstrip("/") + "/api/auth/refresh"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    endpoint,
                    json={"refresh_token": payload.refresh_token},
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
        body = response.json()
        return {
            "ok": True,
            "server": endpoint,
            "access_token": body.get("access_token"),
            "token_type": body.get("token_type", "bearer"),
        }

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
