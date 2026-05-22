from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
import subprocess
import os
import asyncio
from pathlib import Path

# 从我们刚搬过来的引擎中导入
import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent.parent

from application.app import XHS
from module.settings import Settings
from module.model import ExtractParams, ExtractData

router = APIRouter(prefix="/fast-downloader", tags=["Fast Downloader"])

# 全局引擎实例
_xhs_instance: Optional[XHS] = None

async def get_xhs():
    global _xhs_instance
    if _xhs_instance is None:
        settings = Settings(BASE_DIR / "data" / "downloader_volume").run()
        _xhs_instance = XHS(**settings)
        await _xhs_instance.__aenter__()
    return _xhs_instance

@router.post("/detail", response_model=ExtractData)
async def handle_detail(extract: ExtractParams, xhs: XHS = Depends(get_xhs)):
    # 直接复用之前在 app.py 里写的 handle 逻辑
    async with xhs.semaphore:
        url = await xhs.extract_links(extract.url)
        if not url:
            msg = "提取链接失败"
            data = None
        else:
            try:
                data = await xhs._deal_extract(
                    url[0],
                    extract.download,
                    extract.index,
                    not extract.skip,
                    extract.cookie,
                    extract.proxy,
                    extract.work_path,
                    task_id=extract.task_id
                )
                msg = "成功"
            except Exception as e:
                msg = f"发生错误: {str(e)}"
                data = None
        return ExtractData(message=msg, params=extract, data=data)

@router.get("/tasks")
async def get_tasks(xhs: XHS = Depends(get_xhs)):
    return xhs.progress_tasks

@router.get("/user/notes")
async def get_user_notes(url: str, xhs: XHS = Depends(get_xhs)):
    # 模拟外部调用
    from backend.app.api.platforms.xhs.crawl import CrawlUserNotesRequest
    payload = CrawlUserNotesRequest(account_id=1, user_url=url, save_to_library=False)
    # 我们直接内部转换
    from backend.app.api.platforms.xhs.crawl import crawl_user_notes
    from backend.app.core.database import SessionLocal
    # 模拟 FastAPI 调用上下文比较复杂，我们还是走 HTTP 代理简化逻辑
    return await xhs._proxy_all_in_one("/api/xhs/crawl/user-notes", payload.dict())

@router.post("/search")
async def search_notes(params: dict, xhs: XHS = Depends(get_xhs)):
    payload = {
        "account_id": 1,
        "keyword": params.get("keyword"),
        "page": params.get("page", 1),
        "save_to_library": False
    }
    return await xhs._proxy_all_in_one("/api/xhs/crawl/search-notes", payload)

@router.post("/ext/sync_cookie")
async def sync_cookie_to_ext(payload: dict, xhs: XHS = Depends(get_xhs)):
    cookie = payload.get("cookie")
    aio_payload = {
        "platform": "xhs",
        "sub_type": "pc",
        "cookie_string": cookie,
        "sync_creator": True
    }
    return await xhs._proxy_all_in_one("/api/accounts/import-cookie", aio_payload)

@router.post("/ext/save")
async def ext_save_note(note_data: dict, xhs: XHS = Depends(get_xhs)):
    payload = {
        "account_id": 1, 
        "fetch_comments": False,
        "notes": [{
            "note_id": note_data.get("作品ID"),
            "note_url": note_data.get("作品链接"),
            "title": note_data.get("作品标题"),
            "content": note_data.get("作品描述"),
            "author_name": note_data.get("作者昵称"),
            "cover_url": note_data.get("封面地址"),
            "video_url": note_data.get("下载地址")[0] if note_data.get("作品类型") == "视频" else "",
            "image_urls": note_data.get("下载地址") if note_data.get("作品类型") != "视频" else [],
            "raw": note_data
        }]
    }
    return await xhs._proxy_all_in_one("/api/notes/batch-save", payload)

@router.get("/login/browser")
async def browser_cookie_login(xhs: XHS = Depends(get_xhs)):
    import browser_cookie3
    import requests
    print("正在尝试从本地浏览器提取小红书 Cookie...")
    try:
        # 尝试从 Chrome 提取
        cj = browser_cookie3.chrome(domain_name='.xiaohongshu.com')
        cookies = requests.utils.dict_from_cookiejar(cj)
        if not cookies:
            # 尝试从 Edge 提取
            cj = browser_cookie3.edge(domain_name='.xiaohongshu.com')
            cookies = requests.utils.dict_from_cookiejar(cj)
        
        if not cookies:
            return {"success": False, "error": "未在 Chrome 或 Edge 中检测到有效的小红书登录状态。"}
        
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        return {"success": True, "cookie": cookie_str}
    except Exception as e:
        return {"success": False, "error": f"提取失败: {str(e)}"}

@router.get("/login")
async def browser_login(xhs: XHS = Depends(get_xhs)):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://www.xiaohongshu.com")
        try:
            await page.wait_for_selector(".user-info", timeout=300000)
            cookies = await context.cookies()
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            await browser.close()
            return {"success": True, "cookie": cookie_str}
        except:
            await browser.close()
            return {"success": False, "error": "登录超时"}
