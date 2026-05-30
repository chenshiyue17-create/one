from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel

from backend.app.core.config import get_settings
from backend.app.core.deps import get_current_user
from backend.app.models import User

router = APIRouter(prefix="/ops", tags=["ops"])


class OpsActionRequest(BaseModel):
    confirm: bool = False


def _run(command: list[str], timeout: int = 20, cwd: Path | None = None) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-8000:],
            "stderr": completed.stderr[-8000:],
        }
    except FileNotFoundError as exc:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": str(exc)}
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": (exc.stdout or "")[-8000:] if isinstance(exc.stdout, str) else "",
            "stderr": f"Command timed out after {timeout}s",
        }


def _tail_file(path: Path, lines: int) -> str:
    if not path.exists():
        return f"[missing] {path}"
    result = _run(["tail", "-n", str(lines), str(path)], timeout=10)
    return result["stdout"] or result["stderr"]


def _safe_tail_count(value: int) -> int:
    return max(20, min(value, 1000))


def _latest_tmp_deploy_log() -> Path | None:
    candidates = [Path(item) for item in glob.glob("/tmp/xhs-*.log")]
    candidates = [item for item in candidates if item.exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _require_ops_token(confirm: bool, token: str | None) -> None:
    settings = get_settings()
    if not settings.system_ops_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SYSTEM_OPS_TOKEN 未配置，高危操作已禁用。",
        )
    if not confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="需要二次确认。")
    if token != settings.system_ops_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="运维 Token 不正确。")


class OpenFolderRequest(BaseModel):
    path: str
    reveal_file: str | None = None


def _open_folder_result(target_path: Path) -> dict[str, Any]:
    """Open a folder only when the current machine has a real desktop session."""
    if sys.platform == "darwin":
        subprocess.run(["open", str(target_path)], check=True)
        subprocess.run(["osascript", "-e", 'tell application "Finder" to activate'], check=False)
        return {"ok": True, "opened": True, "path": str(target_path), "message": "已在 Finder 中打开目录"}

    if sys.platform.startswith("win"):
        os.startfile(str(target_path))
        return {"ok": True, "opened": True, "path": str(target_path), "message": "已在资源管理器中打开目录"}

    opener = shutil.which("xdg-open")
    has_desktop = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    if opener and has_desktop:
        subprocess.run([opener, str(target_path)], check=True)
        return {"ok": True, "opened": True, "path": str(target_path), "message": "已在文件管理器中打开目录"}

    return {
        "ok": True,
        "opened": False,
        "path": str(target_path),
        "message": "当前运行环境没有可用的图形文件管理器，请直接使用返回的目录路径。",
    }


@router.post("/open-folder")
def open_folder(payload: OpenFolderRequest, _: User = Depends(get_current_user)):
    """Open a folder in the local file explorer."""
    # 安全性检查：仅允许打开项目内的目录
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    raw_path = Path(payload.path)
    target_path = raw_path.resolve() if raw_path.is_absolute() else (project_root / raw_path).resolve()
    
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="目录不存在")
    
    if project_root not in target_path.parents and target_path != project_root:
        raise HTTPException(status_code=403, detail="禁止访问项目外目录")

    try:
        if payload.reveal_file and sys.platform == "darwin":
            raw_reveal = Path(payload.reveal_file)
            reveal_path = raw_reveal.resolve() if raw_reveal.is_absolute() else (project_root / raw_reveal).resolve()
            if not reveal_path.exists():
                raise HTTPException(status_code=404, detail="文件不存在")
            if project_root not in reveal_path.parents and reveal_path != project_root:
                raise HTTPException(status_code=403, detail="禁止访问项目外文件")
            subprocess.run(["open", "-R", str(reveal_path)], check=True)
            subprocess.run(["osascript", "-e", 'tell application "Finder" to activate'], check=False)
            return {"ok": True, "opened": True, "path": str(reveal_path), "message": "已在 Finder 中定位下载文件"}
        return _open_folder_result(target_path)
    except subprocess.CalledProcessError as exc:
        raise HTTPException(status_code=500, detail=f"打开目录失败：{exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/status")
def ops_status(_: User = Depends(get_current_user)) -> dict[str, Any]:
    settings = get_settings()
    service = _run(["systemctl", "is-active", settings.ops_service_name], timeout=8)
    service_detail = _run(["systemctl", "status", settings.ops_service_name, "--no-pager"], timeout=10)
    nginx = _run(["sudo", "-n", "nginx", "-t"], timeout=10)
    frontend_index = Path(settings.frontend_build_dir) / "index.html"
    deploy_log = _latest_tmp_deploy_log()
    return {
        "checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "ops_enabled": bool(settings.system_ops_token),
        "service": {
            "name": settings.ops_service_name,
            "active": service["stdout"].strip() or service["stderr"].strip(),
            "ok": service["ok"] and service["stdout"].strip() == "active",
            "detail": service_detail["stdout"][-4000:] or service_detail["stderr"][-4000:],
        },
        "nginx": {"ok": nginx["ok"], "message": nginx["stderr"] or nginx["stdout"]},
        "frontend": {
            "build_dir": settings.frontend_build_dir,
            "built": frontend_index.exists(),
            "built_at": datetime.fromtimestamp(frontend_index.stat().st_mtime).astimezone().isoformat(timespec="seconds")
            if frontend_index.exists()
            else None,
        },
        "logs": {
            "latest_tmp_deploy_log": str(deploy_log) if deploy_log else None,
            "service_log_command": f"journalctl -u {settings.ops_service_name}",
        },
    }


@router.get("/logs")
def ops_logs(
    type: Literal["deploy", "service", "nginx"] = Query("service"),
    tail: int = Query(200, ge=20, le=1000),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    settings = get_settings()
    lines = _safe_tail_count(tail)
    if type == "service":
        result = _run(["journalctl", "-u", settings.ops_service_name, "-n", str(lines), "--no-pager"], timeout=15)
        content = result["stdout"] or result["stderr"]
        source = f"journalctl -u {settings.ops_service_name}"
    elif type == "nginx":
        primary = Path("/var/log/nginx/error.log")
        result = _run(["sudo", "-n", "tail", "-n", str(lines), str(primary)], timeout=10)
        content = result["stdout"] or result["stderr"] or _tail_file(primary, lines)
        source = str(primary)
    else:
        candidates = [
            Path.home() / "xhs-deploy.log",
            Path.home() / "xhs-status-runtime-deploy.log",
        ]
        latest = _latest_tmp_deploy_log()
        if latest:
            candidates.insert(0, latest)
        existing = next((item for item in candidates if item.exists()), candidates[0])
        content = _tail_file(existing, lines)
        source = str(existing)
    return {"type": type, "source": source, "tail": lines, "content": content}


@router.post("/actions/restart-service")
def restart_service(
    payload: OpsActionRequest,
    x_system_ops_token: str | None = Header(default=None),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    _require_ops_token(payload.confirm, x_system_ops_token)
    settings = get_settings()
    result = _run(["sudo", "-n", "systemctl", "restart", settings.ops_service_name], timeout=30)
    return {"action": "restart-service", **result}


@router.post("/actions/reload-nginx")
def reload_nginx(
    payload: OpsActionRequest,
    x_system_ops_token: str | None = Header(default=None),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    _require_ops_token(payload.confirm, x_system_ops_token)
    test = _run(["sudo", "-n", "nginx", "-t"], timeout=20)
    if not test["ok"]:
        return {"action": "reload-nginx", **test}
    result = _run(["sudo", "-n", "systemctl", "reload", "nginx"], timeout=20)
    return {"action": "reload-nginx", **result}


@router.post("/actions/rebuild-frontend")
def rebuild_frontend(
    payload: OpsActionRequest,
    x_system_ops_token: str | None = Header(default=None),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    _require_ops_token(payload.confirm, x_system_ops_token)
    project_root = Path(__file__).resolve().parents[3]
    script = (
        "set -e; "
        "cd frontend; "
        "VITE_APP_BASE=/spider-xhs/ npm run build "
        "> /tmp/xhs-frontend-rebuild.log 2>&1"
    )
    result = _run(["bash", "-lc", script], timeout=180, cwd=project_root)
    return {"action": "rebuild-frontend", "log": "/tmp/xhs-frontend-rebuild.log", "cwd": str(project_root), **result}


@router.post("/actions/deploy-check")
def deploy_check(
    payload: OpsActionRequest,
    x_system_ops_token: str | None = Header(default=None),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    _require_ops_token(payload.confirm, x_system_ops_token)
    result = _run(["bash", "-lc", "curl -fsS http://127.0.0.1:8000/api/health && echo && curl -fsS http://127.0.0.1:8000/api/system/status >/dev/null"], timeout=30)
    return {"action": "deploy-check", **result}
