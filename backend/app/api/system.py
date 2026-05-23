from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx
from fastapi import APIRouter
from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.models import PlatformAccount, Task

router = APIRouter(prefix="/system", tags=["system"])

REMOTE_HEALTH_URL = "http://47.87.68.74/spider-xhs/api/health"
REMOTE_DOCS_URL = "http://47.87.68.74/spider-xhs/docs"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f}{unit}" if unit != "B" else f"{int(size)}B"
        size /= 1024
    return f"{value}B"


def _read_meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, raw = line.split(":", 1)
            parts = raw.strip().split()
            if parts and parts[0].isdigit():
                values[key] = int(parts[0]) * 1024
    except Exception:
        return values
    return values


def _runtime_info() -> dict[str, Any]:
    meminfo = _read_meminfo()
    memory_total = meminfo.get("MemTotal", 0)
    memory_available = meminfo.get("MemAvailable", 0)
    swap_total = meminfo.get("SwapTotal", 0)
    swap_free = meminfo.get("SwapFree", 0)

    frontend_index = Path(os.environ.get("FRONTEND_BUILD_DIR", "./frontend/dist")) / "index.html"
    frontend_built_at = None
    if frontend_index.exists():
        frontend_built_at = datetime.fromtimestamp(frontend_index.stat().st_mtime).astimezone().isoformat(timespec="seconds")

    return {
        "pid": os.getpid(),
        "frontend_built_at": frontend_built_at,
        "memory": {
            "total": memory_total,
            "available": memory_available,
            "used_percent": round((1 - memory_available / memory_total) * 100, 1) if memory_total else None,
            "total_label": _format_bytes(memory_total) if memory_total else "unknown",
            "available_label": _format_bytes(memory_available) if memory_available else "unknown",
        },
        "swap": {
            "total": swap_total,
            "free": swap_free,
            "used_percent": round((1 - swap_free / swap_total) * 100, 1) if swap_total else None,
            "total_label": _format_bytes(swap_total) if swap_total else "0B",
            "free_label": _format_bytes(swap_free) if swap_free else "0B",
        },
    }


def _database_summary() -> dict[str, Any]:
    tasks = {
        "running_count": 0,
        "failed_count": 0,
        "latest_error": None,
        "latest_success_at": None,
    }
    accounts = {
        "total_count": 0,
        "active_count": 0,
        "expired_count": 0,
        "latest_status_message": None,
    }
    try:
        with SessionLocal() as db:
            tasks["running_count"] = db.scalar(select(func.count()).select_from(Task).where(Task.status == "running")) or 0
            tasks["failed_count"] = db.scalar(select(func.count()).select_from(Task).where(Task.status == "failed")) or 0
            latest_failed = db.scalars(
                select(Task)
                .where(Task.status == "failed")
                .order_by(Task.finished_at.desc().nullslast(), Task.created_at.desc())
                .limit(1)
            ).first()
            if latest_failed:
                payload_error = None
                if isinstance(latest_failed.payload, dict):
                    payload_error = latest_failed.payload.get("error") or latest_failed.payload.get("message")
                tasks["latest_error"] = payload_error or latest_failed.error_type or "任务失败"
            latest_success = db.scalars(
                select(Task)
                .where(Task.status.in_(["completed", "success"]))
                .order_by(Task.finished_at.desc().nullslast(), Task.created_at.desc())
                .limit(1)
            ).first()
            if latest_success:
                value = latest_success.finished_at or latest_success.created_at
                tasks["latest_success_at"] = value.astimezone().isoformat(timespec="seconds") if value else None

            accounts["total_count"] = db.scalar(select(func.count()).select_from(PlatformAccount)) or 0
            accounts["active_count"] = db.scalar(
                select(func.count()).select_from(PlatformAccount).where(PlatformAccount.status.in_(["active", "healthy"]))
            ) or 0
            accounts["expired_count"] = db.scalar(
                select(func.count()).select_from(PlatformAccount).where(PlatformAccount.status == "expired")
            ) or 0
            latest_problem = db.scalars(
                select(PlatformAccount)
                .where(PlatformAccount.status.notin_(["active", "healthy"]))
                .order_by(PlatformAccount.updated_at.desc())
                .limit(1)
            ).first()
            if latest_problem:
                accounts["latest_status_message"] = latest_problem.status_message or latest_problem.status
    except Exception as exc:
        tasks["latest_error"] = f"状态汇总读取失败：{exc}"
    return {"tasks": tasks, "accounts": accounts}


async def _probe_url(name: str, url: str, timeout: float = 4.0) -> dict[str, Any]:
    started = perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
        latency_ms = round((perf_counter() - started) * 1000)
        ok = 200 <= response.status_code < 300
        payload: Any = None
        try:
            payload = response.json()
        except ValueError:
            payload = None
        return {
            "name": name,
            "ok": ok,
            "status": "online" if ok else "degraded",
            "http_code": response.status_code,
            "latency_ms": latency_ms,
            "url": url,
            "message": "正常" if ok else f"HTTP {response.status_code}",
            "payload": payload,
        }
    except Exception as exc:
        latency_ms = round((perf_counter() - started) * 1000)
        return {
            "name": name,
            "ok": False,
            "status": "offline",
            "http_code": None,
            "latency_ms": latency_ms,
            "url": url,
            "message": str(exc),
            "payload": None,
        }


@router.get("/status")
async def system_status() -> dict[str, Any]:
    remote_api = await _probe_url("公网 API", REMOTE_HEALTH_URL)
    remote_docs = await _probe_url("公网 Docs", REMOTE_DOCS_URL)
    local_api = {
        "name": "本地后端",
        "ok": True,
        "status": "online",
        "http_code": 200,
        "latency_ms": 0,
        "url": "/api/health",
        "message": "正常",
        "payload": {"status": "ok", "service": "spider-xhs"},
    }
    checks = [local_api, remote_api, remote_docs]
    return {
        "ok": all(item["ok"] for item in checks),
        "status": "online" if all(item["ok"] for item in checks) else "degraded",
        "checked_at": _now_iso(),
        "runtime": _runtime_info(),
        **_database_summary(),
        "checks": checks,
    }
