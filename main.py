from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence


ROOT = Path(__file__).resolve().parent


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the Spider_XHS product platform.")
    parser.add_argument("--host", default="127.0.0.1", help="Backend host.")
    parser.add_argument("--port", type=int, default=8000, help="Backend port.")
    parser.add_argument("--reload", action="store_true", help="Enable Uvicorn reload.")
    parser.add_argument("--with-frontend", action="store_true", help="Also start the frontend Vite dev server.")
    parser.add_argument("--frontend-port", type=int, default=5173, help="Frontend dev server port.")
    return parser.parse_args(argv)


def resolve_npm_executable() -> str:
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        raise FileNotFoundError("npm was not found on PATH; install Node.js or start the frontend manually.")
    return npm


def build_frontend_command(port: int, npm_executable: Optional[str] = None) -> list[str]:
    npm = npm_executable or resolve_npm_executable()
    return [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(port)]


def start_frontend(port: int) -> Optional[subprocess.Popen]:
    frontend_dir = ROOT / "frontend"
    package_json = frontend_dir / "package.json"
    if not package_json.exists():
        print("frontend/package.json not found; skipping frontend startup.")
        return None

    command = build_frontend_command(port)
    print(f"Starting frontend at http://127.0.0.1:{port}")
    return subprocess.Popen(command, cwd=str(frontend_dir))


def kill_process_on_port(port: int) -> None:
    """Find and kill any process listening on the given port."""
    try:
        if sys.platform == "win32":
            # Windows implementation
            output = subprocess.check_output(["netstat", "-ano", "-p", "tcp"], encoding="utf-8")
            for line in output.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    pid = parts[-1]
                    print(f"Cleaning up existing process on port {port} (PID: {pid})...")
                    subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
        else:
            # macOS/Linux implementation using lsof
            try:
                output = subprocess.check_output(["lsof", "-t", f"-i:{port}"], encoding="utf-8")
                pids = output.strip().split("\n")
                for pid in pids:
                    if pid:
                        print(f"Cleaning up existing process on port {port} (PID: {pid})...")
                        subprocess.run(["kill", "-9", pid], capture_output=True)
            except subprocess.CalledProcessError:
                # lsof returns non-zero if no process is found
                pass
    except Exception as e:
        print(f"Error while cleaning up port {port}: {e}")


def open_browser(url: str, delay: float = 1.5) -> None:
    """Wait for a short delay and then open the given URL in the default browser."""
    import time
    import webbrowser

    def _open():
        time.sleep(delay)
        print(f"Automatically opening {url}...")
        webbrowser.open(url)

    import threading
    threading.Thread(target=_open, daemon=True).start()


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    # Resolve host/port: CLI args take precedence, then YAML/env config defaults
    host = args.host
    port = args.port
    try:
        from backend.app.core.config import get_settings
        settings = get_settings()
        # Use config values only when CLI args are at their defaults
        if host == "127.0.0.1" and settings.server_host:
            host = settings.server_host
        if port == 8000 and settings.server_port:
            port = settings.server_port
    except Exception:
        pass

    # Kill existing processes on target ports to avoid "Port already in use"
    kill_process_on_port(port)
    if args.with_frontend:
        kill_process_on_port(args.frontend_port)

    frontend_process = start_frontend(args.frontend_port) if args.with_frontend else None

    # Auto-open browser if frontend is being started
    if args.with_frontend:
        # We target the frontend port
        open_browser(f"http://127.0.0.1:{args.frontend_port}")

    print(f"Starting backend at http://{host}:{port}")
    try:
        import uvicorn

        uvicorn.run("backend.app.main:app", host=host, port=port, reload=args.reload)
    finally:
        if frontend_process and frontend_process.poll() is None:
            frontend_process.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
