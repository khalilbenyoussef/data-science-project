"""start.ps1 / stop.ps1 : garde-fous du lancement local de FinOVA (lecture du source)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    raw = (ROOT / name).read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), f"{name} : BOM UTF-8 requis (Windows PowerShell 5.1)"
    return raw[3:].decode("utf-8")


def test_start_checks_env_build_port_and_records_pid():
    start = _read("start.ps1")
    for needle in (r".venv\Scripts\python.exe", r"dashboard_app\web\dist\index.html",
                   "Get-NetTCPConnection -LocalPort $Port -State Listen", "OwningProcess",
                   '$env:PYTHONPATH = "src"', '"--host", "127.0.0.1"', "$Port = 8000",
                   "dashboard_app.api.app:app", ".finova.pid", "/api/health"):
        assert needle in start, needle


def test_stop_only_kills_the_recorded_server():
    stop = _read("stop.ps1")
    assert ".finova.pid" in stop and '-notlike "python*"' in stop
    assert "taskkill.exe /PID $serverPid /T /F" in stop
    assert "Get-NetTCPConnection" not in stop  # jamais « le processus du port »


def test_pid_file_is_ignored():
    assert ".finova.pid" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
