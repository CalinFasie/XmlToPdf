from __future__ import annotations

import threading
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from xmltopdf.edge_session import (
    PROFILE_MARKER,
    PROFILE_MARKER_CONTENT,
    PROFILE_PREFIX,
    WINDOW_CLASS,
    WM_CLOSE,
    EdgeAppSession,
    EdgeSessionError,
    EdgeWindowTracker,
    ProcessInfo,
    WindowInfo,
    Win32EdgeWindowApi,
    cleanup_stale_profiles,
)


@pytest.fixture
def edge_temp_dir() -> Any:
    with tempfile.TemporaryDirectory(
        prefix=".edge-session-test-",
        dir=Path(__file__).parents[1],
    ) as directory:
        yield Path(directory)


class FakeWindowApi:
    def __init__(self) -> None:
        self.processes: dict[int, ProcessInfo] = {}
        self.windows: dict[int, WindowInfo] = {}
        self.activations: list[int] = []
        self.close_requests: list[int] = []
        self.close_on_message = False
        self.fail_process_snapshot = False

    def snapshot_processes(self) -> dict[int, ProcessInfo]:
        if self.fail_process_snapshot:
            raise OSError("private Win32 error")
        return dict(self.processes)

    def enumerate_windows(self) -> list[WindowInfo]:
        return list(self.windows.values())

    def is_window(self, hwnd: int) -> bool:
        return hwnd in self.windows

    def activate_window(self, hwnd: int) -> bool:
        if not self.is_window(hwnd):
            return False
        self.activations.append(hwnd)
        return True

    def post_close_message(self, hwnd: int) -> bool:
        self.close_requests.append(hwnd)
        if hwnd not in self.windows:
            return False
        if self.close_on_message:
            self.windows.pop(hwnd, None)
        return True


def _write_owned_profile(path: Path) -> None:
    path.mkdir()
    (path / PROFILE_MARKER).write_text(PROFILE_MARKER_CONTENT, encoding="utf-8")


def test_tracker_uses_process_ancestry_and_exact_window_handle() -> None:
    api = FakeWindowApi()
    api.processes = {
        # Popen's initial process has already exited; the surviving Edge child
        # still identifies the app session through its parent PID.
        200: ProcessInfo(pid=200, parent_pid=100, image_name="msedge.exe"),
        201: ProcessInfo(pid=201, parent_pid=200, image_name="msedge.exe"),
        999: ProcessInfo(pid=999, parent_pid=1, image_name="msedge.exe"),
    }
    api.windows = {
        400: WindowInfo(400, 999, WINDOW_CLASS, True),
        500: WindowInfo(500, 200, WINDOW_CLASS, True),
    }
    now = [10.0]
    tracker = EdgeWindowTracker(
        100,
        api,
        close_grace=1.0,
        monotonic=lambda: now[0],
    )

    assert tracker.poll() == "opened"
    assert tracker.hwnd == 500
    assert tracker.related_pids == {100, 200, 201}

    # Minimize, refresh, and open Print/Save as PDF: the original HWND remains.
    api.windows[500] = WindowInfo(500, 200, WINDOW_CLASS, False)
    api.windows[501] = WindowInfo(501, 200, WINDOW_CLASS, True)
    assert tracker.poll() == "present"
    assert tracker.hwnd == 500

    # A transient HWND loss is tolerated; only a sustained close ends the session.
    del api.windows[500]
    assert tracker.poll() == "waiting"
    now[0] += 0.5
    api.windows[500] = WindowInfo(500, 200, WINDOW_CLASS, True)
    assert tracker.poll() == "present"
    del api.windows[500]
    assert tracker.poll() == "waiting"
    now[0] += 1.01
    assert tracker.poll() == "closed"


def test_session_launches_isolated_edge_app_and_activates_existing_window(
    edge_temp_dir: Path,
) -> None:
    api = FakeWindowApi()
    launched: list[tuple[list[str], dict[str, Any]]] = []
    closed: list[str] = []
    closed_event = threading.Event()
    monitor_failures: list[str] = []

    def on_closed() -> None:
        closed.append("closed")
        closed_event.set()

    def process_factory(command: list[str], **kwargs: Any) -> Any:
        launched.append((command, kwargs))
        api.processes = {
            200: ProcessInfo(pid=200, parent_pid=100, image_name="msedge.exe")
        }
        api.windows = {500: WindowInfo(500, 200, WINDOW_CLASS, True)}
        return SimpleNamespace(pid=100)

    session = EdgeAppSession(
        edge_temp_dir / "msedge.exe",
        on_window_closed=on_closed,
        on_monitor_failure=lambda: monitor_failures.append("failed"),
        api=api,
        process_factory=process_factory,
        temp_root=edge_temp_dir,
        startup_timeout=1.0,
        close_grace=0.02,
        cleanup_timeout=0.2,
        poll_interval=0.005,
    )

    session.open_or_activate("http://127.0.0.1:5000/")
    session.open_or_activate("http://127.0.0.1:5000/")

    command, kwargs = launched[0]
    assert command[0] == str(edge_temp_dir / "msedge.exe")
    assert command[1] == "--app=http://127.0.0.1:5000/"
    profile_argument = next(argument for argument in command if argument.startswith("--user-data-dir="))
    profile = Path(profile_argument.split("=", 1)[1])
    assert profile.parent == edge_temp_dir
    assert profile.name.startswith(PROFILE_PREFIX)
    assert profile != Path.home() / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data"
    assert "--no-first-run" in command
    assert "--no-default-browser-check" in command
    assert kwargs == {"close_fds": True}
    assert api.activations == [500, 500]
    assert not closed and not monitor_failures

    # Refresh/minimize and a separate print dialog do not replace the tracked HWND.
    api.windows[500] = WindowInfo(500, 200, WINDOW_CLASS, False)
    api.windows[501] = WindowInfo(501, 200, WINDOW_CLASS, True)
    assert session.tracker is not None
    assert session.tracker.poll() == "present"
    assert closed == []

    del api.windows[500]
    assert closed_event.wait(1.0)
    assert closed == ["closed"]
    api.processes.clear()
    session.cleanup()
    assert not profile.exists()


def test_close_window_targets_only_the_validated_dedicated_edge_hwnd(
    edge_temp_dir: Path,
) -> None:
    api = FakeWindowApi()
    api.close_on_message = True
    api.processes = {200: ProcessInfo(200, 100, "msedge.exe")}
    api.windows = {
        500: WindowInfo(500, 200, WINDOW_CLASS, True),
        900: WindowInfo(900, 999, WINDOW_CLASS, True),
    }
    session = EdgeAppSession(
        edge_temp_dir / "msedge.exe",
        on_window_closed=lambda: None,
        on_monitor_failure=lambda: None,
        api=api,
        process_factory=lambda *_a, **_k: SimpleNamespace(pid=100),
        temp_root=edge_temp_dir,
        startup_timeout=0.5,
        close_grace=0.01,
        poll_interval=0.005,
    )

    session.open_or_activate("http://127.0.0.1:5000/")
    assert session.close_window(timeout=0.2)
    assert api.close_requests == [500]
    assert 500 not in api.windows
    assert 900 in api.windows
    api.processes.clear()
    session.cleanup()


def test_close_window_refuses_reused_or_unassociated_hwnd(edge_temp_dir: Path) -> None:
    api = FakeWindowApi()
    api.processes = {200: ProcessInfo(200, 100, "msedge.exe")}
    api.windows = {500: WindowInfo(500, 200, WINDOW_CLASS, True)}
    session = EdgeAppSession(
        edge_temp_dir / "msedge.exe",
        on_window_closed=lambda: None,
        on_monitor_failure=lambda: None,
        api=api,
        process_factory=lambda *_a, **_k: SimpleNamespace(pid=100),
        temp_root=edge_temp_dir,
        startup_timeout=0.5,
        poll_interval=0.005,
    )
    session.open_or_activate("http://127.0.0.1:5000/")
    assert session.tracker is not None

    # Simulate HWND reuse by a different Edge process after it was tracked.
    api.windows[500] = WindowInfo(500, 999, WINDOW_CLASS, True)
    assert not session.close_window(timeout=0.1)
    assert api.close_requests == []
    assert api.windows[500].pid == 999
    session._monitor_stop.set()
    api.processes.clear()
    session.cleanup()


def test_close_window_failure_keeps_dedicated_window_available(edge_temp_dir: Path) -> None:
    api = FakeWindowApi()
    api.processes = {200: ProcessInfo(200, 100, "msedge.exe")}
    api.windows = {500: WindowInfo(500, 200, WINDOW_CLASS, True)}
    session = EdgeAppSession(
        edge_temp_dir / "msedge.exe",
        on_window_closed=lambda: None,
        on_monitor_failure=lambda: None,
        api=api,
        process_factory=lambda *_a, **_k: SimpleNamespace(pid=100),
        temp_root=edge_temp_dir,
        startup_timeout=0.5,
        poll_interval=0.005,
    )
    session.open_or_activate("http://127.0.0.1:5000/")

    assert not session.close_window(timeout=0.03)
    assert api.close_requests == [500]
    assert 500 in api.windows
    session._monitor_stop.set()
    api.processes.clear()
    session.cleanup()


def test_win32_close_adapter_posts_wm_close_only_to_a_live_hwnd() -> None:
    calls: list[tuple[int, int, int, int]] = []
    api = object.__new__(Win32EdgeWindowApi)
    api._user32 = SimpleNamespace(
        PostMessageW=lambda hwnd, message, wparam, lparam: calls.append(
            (hwnd, message, wparam, lparam)
        ) or 1
    )
    api.is_window = lambda hwnd: hwnd == 500

    assert api.post_close_message(500)
    assert not api.post_close_message(900)
    assert calls == [(500, WM_CLOSE, 0, 0)]


def test_start_failure_removes_only_the_new_owned_profile(edge_temp_dir: Path) -> None:
    api = FakeWindowApi()
    session = EdgeAppSession(
        edge_temp_dir / "msedge.exe",
        on_window_closed=lambda: pytest.fail("No session was started."),
        on_monitor_failure=lambda: pytest.fail("No monitor was started."),
        api=api,
        process_factory=lambda *_a, **_k: (_ for _ in ()).throw(OSError("private detail")),
        temp_root=edge_temp_dir,
        startup_timeout=0.01,
    )

    with pytest.raises(EdgeSessionError) as error:
        session.open_or_activate("http://127.0.0.1:5000/")
    assert "private detail" not in str(error.value)
    assert list(edge_temp_dir.iterdir()) == []


def test_monitor_failure_keeps_recovery_path_and_does_not_report_auto_stop(
    edge_temp_dir: Path,
) -> None:
    api = FakeWindowApi()
    api.fail_process_snapshot = True
    failures = threading.Event()
    stops: list[str] = []
    session = EdgeAppSession(
        edge_temp_dir / "msedge.exe",
        on_window_closed=lambda: stops.append("closed"),
        on_monitor_failure=failures.set,
        api=api,
        process_factory=lambda *_a, **_k: SimpleNamespace(pid=100),
        temp_root=edge_temp_dir,
        startup_timeout=0.5,
        cleanup_timeout=0.02,
        poll_interval=0.005,
    )

    with pytest.raises(EdgeSessionError, match="system tray"):
        session.open_or_activate("http://127.0.0.1:5000/")

    assert failures.wait(0.2)
    assert stops == []
    assert session.profile_path is not None and session.profile_path.exists()
    session.cleanup()
    assert session.profile_path is not None and session.profile_path.exists()


def test_stale_cleanup_removes_only_owned_profiles_when_edge_is_not_running(
    edge_temp_dir: Path,
) -> None:
    owned = edge_temp_dir / f"{PROFILE_PREFIX}old-session"
    unmanaged = edge_temp_dir / f"{PROFILE_PREFIX}not-owned"
    _write_owned_profile(owned)
    unmanaged.mkdir()
    api = FakeWindowApi()

    assert cleanup_stale_profiles(edge_temp_dir, api) == 1
    assert not owned.exists()
    assert unmanaged.exists()

    _write_owned_profile(owned)
    api.processes = {42: ProcessInfo(42, 1, "msedge.exe")}
    assert cleanup_stale_profiles(edge_temp_dir, api) == 0
    assert owned.exists()
