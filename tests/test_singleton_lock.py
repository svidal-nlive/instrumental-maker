from pathlib import Path
from typing import Any

import app.simple_runner as sr


def _alive(pid: int) -> bool:  # pragma: no cover - trivial shim
    return True


def _dead(pid: int) -> bool:  # pragma: no cover - trivial shim
    return False


def test_singleton_lock_host_mismatch(tmp_path: Path, monkeypatch: Any):
    lock = tmp_path / "simple_runner.pid"
    lock.write_text("otherhost:123")
    monkeypatch.setattr(sr.socket, "gethostname", lambda: "thishost")
    monkeypatch.setattr(sr, "_pid_is_running", _alive)
    # Should refuse to acquire when lock host differs
    got = sr.acquire_singleton_lock_for_tests(lock)
    assert got is None
    assert lock.read_text().strip() == "otherhost:123"


def test_singleton_lock_stale_same_host_acquires(tmp_path: Path, monkeypatch: Any):
    lock = tmp_path / "simple_runner.pid"
    lock.write_text("thishost:123")
    monkeypatch.setattr(sr.socket, "gethostname", lambda: "thishost")
    monkeypatch.setattr(sr, "_pid_is_running", _dead)
    monkeypatch.setattr(sr.os, "getpid", lambda: 9999)
    got = sr.acquire_singleton_lock_for_tests(lock)
    assert got == 9999
    assert lock.read_text().strip() == "thishost:9999"


def test_singleton_lock_same_pid_reuse(tmp_path: Path, monkeypatch: Any):
    lock = tmp_path / "simple_runner.pid"
    lock.write_text("thishost:9999")
    monkeypatch.setattr(sr.socket, "gethostname", lambda: "thishost")
    monkeypatch.setattr(sr.os, "getpid", lambda: 9999)
    # Even if _pid_is_running would say False, same-PID reuse returns pid
    monkeypatch.setattr(sr, "_pid_is_running", _dead)
    got = sr.acquire_singleton_lock_for_tests(lock)
    assert got == 9999


def test_singleton_lock_legacy_numeric_running(tmp_path: Path, monkeypatch: Any):
    lock = tmp_path / "simple_runner.pid"
    lock.write_text("123")
    # Hostname not encoded in legacy format; treat as running if pid alive
    monkeypatch.setattr(sr, "_pid_is_running", _alive)
    monkeypatch.setattr(sr.os, "getpid", lambda: 9999)
    got = sr.acquire_singleton_lock_for_tests(lock)
    assert got is None
    assert lock.read_text().strip() == "123"
