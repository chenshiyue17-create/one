"""
Browser-based XHS login API with captcha relay.

POST /browser-login/start     - Start browser login session
GET  /browser-login/{id}      - Poll session state  
POST /browser-login/{id}/captcha - Submit captcha answer
DELETE /browser-login/{id}    - Cancel session
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from loguru import logger

from backend.app.core.deps import get_current_user
from backend.app.models import User
from backend.app.services.browser_login_service import (
    browser_login_manager,
    LoginState,
)

router = APIRouter(prefix="/browser-login", tags=["browser-login"])


class BrowserLoginStartResponse(BaseModel):
    session_id: str
    state: str
    status_text: str


class CaptchaSubmitRequest(BaseModel):
    captcha_text: str = Field(min_length=1, max_length=20)


class BrowserLoginStateResponse(BaseModel):
    session_id: str
    state: str
    status_text: str
    has_qr: bool
    qr_image_b64: str | None = None
    has_captcha: bool
    captcha_image_b64: str | None = None
    screenshot_b64: str | None = None
    cookies: dict | None = None
    error_message: str | None = None
    cookies_count: int = 0


@router.post("/start", response_model=BrowserLoginStartResponse)
async def start_browser_login(
    current_user: User = Depends(get_current_user),
) -> BrowserLoginStartResponse:
    """Start a new browser-based login session."""
    session = browser_login_manager.create_session()

    # Launch login flow in background
    session._task = asyncio.create_task(
        browser_login_manager.start_login_flow(session.session_id)
    )

    # Wait briefly for state to initialize
    await asyncio.sleep(0.5)
    state = await browser_login_manager.get_session_state(session.session_id)

    return BrowserLoginStartResponse(
        session_id=session.session_id,
        state=state["state"],
        status_text=state["status_text"],
    )


@router.get("/{session_id}", response_model=BrowserLoginStateResponse)
async def get_browser_login_state(
    session_id: str,
    current_user: User = Depends(get_current_user),
) -> BrowserLoginStateResponse:
    """Poll for current session state, including QR code, captcha, or success."""
    state = await browser_login_manager.get_session_state(session_id)
    if state["state"] == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="登录会话未找到或已过期")

    return BrowserLoginStateResponse(**state)


@router.post("/{session_id}/captcha")
async def submit_captcha(
    session_id: str,
    payload: CaptchaSubmitRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Submit captcha answer for the browser session."""
    try:
        await browser_login_manager.submit_captcha(session_id, payload.captcha_text)
        return {"ok": True, "session_id": session_id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete("/{session_id}")
async def cancel_browser_login(
    session_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Cancel a browser login session."""
    session = browser_login_manager.get_session(session_id)
    if session:
        if session._task and not session._task.done():
            session._task.cancel()
        await browser_login_manager._close_browser(session)
        browser_login_manager.remove_session(session_id)
    return {"ok": True, "session_id": session_id}


@router.post("/{session_id}/import-cookies")
async def import_browser_cookies(
    session_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    """After successful login, import cookies to the account system."""
    from sqlalchemy.orm import Session

    state = await browser_login_manager.get_session_state(session_id)
    if state["state"] != LoginState.LOGIN_SUCCESS.value or not state["cookies"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="登录尚未完成，无法导入 Cookie",
        )

    cookies_dict = state["cookies"]
    if not cookies_dict.get("web_session") and not cookies_dict.get("a1"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cookie 数据不完整，缺少必要字段",
        )

    # Build cookie string
    cookie_string = "; ".join(f"{k}={v}" for k, v in cookies_dict.items())

    # Use the existing account import logic
    from backend.app.core.database import SessionLocal
    from backend.app.adapters.xhs.pc_login_adapter import XhsPcLoginAdapter
    from backend.app.adapters.xhs.creator_login_adapter import XhsCreatorLoginAdapter
    from backend.app.adapters.xhs.pc_api_adapter import XhsPcApiAdapter
    from backend.app.services.account_service import (
        cookie_header_from_text,
        enrich_user_info_with_xhs_self_profile,
        serialize_account,
        upsert_platform_account_from_login,
    )
    from xhs_utils.cookie_util import trans_cookies

    db = SessionLocal()
    try:
        pc_adapter = XhsPcLoginAdapter()
        creator_adapter = XhsCreatorLoginAdapter()

        # Get user info using PC adapter
        user_info = pc_adapter.get_user_info(trans_cookies(cookie_string))

        # Enrich with self profile
        try:
            self_profile = XhsPcApiAdapter(cookie_header_from_text(cookie_string)).get_self_info()
            user_info = enrich_user_info_with_xhs_self_profile(user_info, self_profile)
        except Exception:
            pass

        # Upsert PC account
        account, action = upsert_platform_account_from_login(
            db=db,
            user_id=current_user.id,
            platform="xhs",
            sub_type="pc",
            user_info=user_info,
            cookies_text=cookie_string,
        )

        # Also sync creator
        creator_result = None
        try:
            creator_result = creator_adapter.exchange_from_user_cookies(trans_cookies(cookie_string))
            creator_cookies_text = json.dumps(
                creator_result["cookies"], ensure_ascii=False, separators=(",", ":")
            )
            creator_user_info = creator_adapter.get_user_info(creator_result["cookies"])
            creator_account, _ = upsert_platform_account_from_login(
                db=db,
                user_id=current_user.id,
                platform="xhs",
                sub_type="creator",
                user_info=creator_user_info,
                cookies_text=creator_cookies_text,
            )
        except Exception:
            pass

        db.commit()
        db.refresh(account)

        # Cleanup session
        session = browser_login_manager.get_session(session_id)
        if session:
            await browser_login_manager._close_browser(session)
            browser_login_manager.remove_session(session_id)

        result = serialize_account(account, action)
        if creator_result:
            result["creator_synced"] = True

        return {"ok": True, "account": result}

    except Exception as e:
        db.rollback()
        logger.exception("Cookie import failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导入 Cookie 失败: {e}",
        ) from e
    finally:
        db.close()
