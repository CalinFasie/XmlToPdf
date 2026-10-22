"""Isolated Microsoft Edge app window lifecycle for the Windows launcher."""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


PROFILE_PREFIX = "xmltopdf-edge-"
PROFILE_MARKER = ".xmltopdf-owned-profile"
PROFILE_MARKER_CONTENT = "XmlToPdf temporary Edge profile v1\n"
WINDOW_CLASS = "Chrome_WidgetWin_1"
PROCESS_POLL_SECONDS = 0.1
WINDOW_CLOSE_GRACE_SECONDS = 1.0
WINDOW_STARTUP_TIMEOUT_SECONDS = 20.0
PROFILE_CLEANUP_TIMEOUT_SECONDS = 3.0


class EdgeSessionError(RuntimeError):
    """Raised when a dedicated Edge session cannot be started or monitored."""


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    parent_pid: int
    image_name: str


@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    pid: int
    class_name: str
    visible: bool


class EdgeWindowApi(Protocol):
    def snapshot_processes(self) -> Mapping[int, ProcessInfo]: ...

    def enumerate_windows(self) -> list[WindowInfo]: ...

    def is_window(self, hwnd: int) -> bool: ...

    def activate_window(self, hwnd: int) -> bool: ...


class Win32EdgeWindowApi:
    """Small Win32 adapter for process ancestry and top-level Edge windows."""

    TH32CS_SNAPPROCESS = 0x00000002
    SW_RESTORE = 9
    MAX_PATH = 260

    def __init__(self) -> None:
        if os.name != "nt":
            raise EdgeSessionError("Windows window monitoring is unavailable.")

        from ctypes import wintypes

        self._wintypes = wintypes
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
        self._kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        self._kernel32.Process32FirstW.argtypes = (
            wintypes.HANDLE,
            ctypes.c_void_p,
        )
        self._kernel32.Process32FirstW.restype = wintypes.BOOL
        self._kernel32.Process32NextW.argtypes = (
            wintypes.HANDLE,
            ctypes.c_void_p,
        )
        self._kernel32.Process32NextW.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        self._kernel32.CloseHandle.restype = wintypes.BOOL
        self._user32.EnumWindows.argtypes = (ctypes.c_void_p, wintypes.LPARAM)
        self._user32.EnumWindows.restype = wintypes.BOOL
        self._user32.GetWindowThreadProcessId.argtypes = (
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        )
        self._user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self._user32.IsWindow.argtypes = (wintypes.HWND,)
        self._user32.IsWindow.restype = wintypes.BOOL
        self._user32.IsWindowVisible.argtypes = (wintypes.HWND,)
        self._user32.IsWindowVisible.restype = wintypes.BOOL
        self._user32.GetClassNameW.argtypes = (
            wintypes.HWND,
            wintypes.LPWSTR,
            ctypes.c_int,
        )
        self._user32.GetClassNameW.restype = ctypes.c_int
        self._user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
        self._user32.ShowWindow.restype = wintypes.BOOL
        self._user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
        self._user32.SetForegroundWindow.restype = wintypes.BOOL

    def snapshot_processes(self) -> Mapping[int, ProcessInfo]:
        from ctypes import wintypes

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * self.MAX_PATH),
            ]

        snapshot = self._kernel32.CreateToolhelp32Snapshot(self.TH32CS_SNAPPROCESS, 0)
        invalid_handle = ctypes.c_void_p(-1).value
        if not snapshot or snapshot == invalid_handle:
            raise EdgeSessionError("The Windows process list could not be read.")

        processes: dict[int, ProcessInfo] = {}
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        try:
            if not self._kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
                raise EdgeSessionError("The Windows process list could not be read.")
            while True:
                process = ProcessInfo(
                    pid=int(entry.th32ProcessID),
                    parent_pid=int(entry.th32ParentProcessID),
                    image_name=str(entry.szExeFile),
                )
                processes[process.pid] = process
                entry.dwSize = ctypes.sizeof(entry)
                if not self._kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                    break
        finally:
            self._kernel32.CloseHandle(snapshot)
        return processes

    def enumerate_windows(self) -> list[WindowInfo]:
        from ctypes import wintypes

        windows: list[WindowInfo] = []
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def visit(hwnd: int, _lparam: int) -> bool:
            class_name = ctypes.create_unicode_buffer(256)
            if not self._user32.GetClassNameW(hwnd, class_name, len(class_name)):
                return True
            pid = wintypes.DWORD()
            self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            windows.append(
                WindowInfo(
                    hwnd=int(hwnd),
                    pid=int(pid.value),
                    class_name=class_name.value,
                    visible=bool(self._user32.IsWindowVisible(hwnd)),
                )
            )
            return True

        callback = callback_type(visit)
        if not self._user32.EnumWindows(callback, 0):
            raise EdgeSessionError("The Windows window list could not be read.")
        return windows

    def is_window(self, hwnd: int) -> bool:
        return bool(self._user32.IsWindow(hwnd))

    def activate_window(self, hwnd: int) -> bool:
        if not self.is_window(hwnd):
            return False
        self._user32.ShowWindow(hwnd, self.SW_RESTORE)
        return bool(self._user32.SetForegroundWindow(hwnd))


def discover_edge_processes(
    root_pid: int,
    processes: Mapping[int, ProcessInfo],
    known_pids: set[int] | None = None,
) -> set[int]:
    """Return Edge descendants while retaining ancestry discovered in earlier snapshots."""
    related = {root_pid} if known_pids is None else set(known_pids) | {root_pid}
    changed = True
    while changed:
        changed = False
        for process in processes.values():
            if (
                process.parent_pid in related
                and process.image_name.casefold() == "msedge.exe"
                and process.pid not in related
            ):
                related.add(process.pid)
                changed = True
    return related


class EdgeWindowTracker:
    """Track the exact app HWND after associating it with this launch's process tree."""

    def __init__(
        self,
        root_pid: int,
        api: EdgeWindowApi,
        *,
        close_grace: float = WINDOW_CLOSE_GRACE_SECONDS,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.root_pid = root_pid
        self.api = api
        self.close_grace = close_grace
        self.monotonic = monotonic
        self.related_pids: set[int] = {root_pid}
        self.hwnd: int | None = None
        self._missing_since: float | None = None

    def poll(self) -> str:
        """Return waiting, opened, present, or closed; transient states never mean shutdown."""
        try:
            processes = self.api.snapshot_processes()
            self.related_pids = discover_edge_processes(
                self.root_pid,
                processes,
                self.related_pids,
            )
        except Exception:
            if self.hwnd is None:
                raise

        if self.hwnd is not None:
            if self.api.is_window(self.hwnd):
                self._missing_since = None
                return "present"
            now = self.monotonic()
            if self._missing_since is None:
                self._missing_since = now
                return "waiting"
            if now - self._missing_since < self.close_grace:
                return "waiting"
            return "closed"

        windows = self.api.enumerate_windows()
        candidates = [
            window
            for window in windows
            if window.visible
            and window.class_name == WINDOW_CLASS
            and window.pid in self.related_pids
        ]
        if not candidates:
            return "waiting"
        candidates.sort(key=lambda window: (window.pid != self.root_pid, window.hwnd))
        self.hwnd = candidates[0].hwnd
        return "opened"


def _is_owned_profile(path: Path, temp_root: Path) -> bool:
    try:
        root = temp_root.resolve(strict=True)
        if path.is_symlink() or not path.is_dir() or not path.name.startswith(PROFILE_PREFIX):
            return False
        resolved = path.resolve(strict=True)
        marker = path / PROFILE_MARKER
        return (
            resolved.parent == root
            and not marker.is_symlink()
            and marker.is_file()
            and marker.read_text(encoding="utf-8") == PROFILE_MARKER_CONTENT
        )
    except (OSError, RuntimeError):
        return False


def remove_owned_profile(path: Path, temp_root: Path) -> bool:
    """Remove only a direct, marked child of the configured temporary root."""
    if not _is_owned_profile(path, temp_root):
        return False
    try:
        shutil.rmtree(path)
    except OSError:
        return False
    return True


def cleanup_stale_profiles(temp_root: Path, api: EdgeWindowApi) -> int:
    """Clean old launcher profiles only when no Edge process is running in this user session."""
    try:
        root = temp_root.resolve(strict=True)
        processes = api.snapshot_processes()
    except (OSError, RuntimeError):
        return 0
    if any(process.image_name.casefold() == "msedge.exe" for process in processes.values()):
        return 0

    removed = 0
    try:
        candidates = tuple(root.glob(f"{PROFILE_PREFIX}*"))
    except OSError:
        return 0
    for candidate in candidates:
        if remove_owned_profile(candidate, root):
            removed += 1
    return removed


class EdgeAppSession:
    """Launch, monitor, activate, and clean one isolated Edge app session."""

    def __init__(
        self,
        executable: Path,
        *,
        on_window_closed: Callable[[], None],
        on_monitor_failure: Callable[[], None],
        api: EdgeWindowApi | None = None,
        process_factory: Callable[..., Any] = subprocess.Popen,
        temp_root: Path | None = None,
        startup_timeout: float = WINDOW_STARTUP_TIMEOUT_SECONDS,
        close_grace: float = WINDOW_CLOSE_GRACE_SECONDS,
        cleanup_timeout: float = PROFILE_CLEANUP_TIMEOUT_SECONDS,
        poll_interval: float = PROCESS_POLL_SECONDS,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.executable = Path(executable)
        self.on_window_closed = on_window_closed
        self.on_monitor_failure = on_monitor_failure
        self.api = Win32EdgeWindowApi() if api is None else api
        self.process_factory = process_factory
        self.temp_root = Path(tempfile.gettempdir()) if temp_root is None else Path(temp_root)
        self.startup_timeout = startup_timeout
        self.close_grace = close_grace
        self.cleanup_timeout = cleanup_timeout
        self.poll_interval = poll_interval
        self.monotonic = monotonic
        self.sleep = sleep
        self.profile_path: Path | None = None
        self.root_pid: int | None = None
        self.tracker: EdgeWindowTracker | None = None
        self._monitor_thread: threading.Thread | None = None
        self._monitor_stop = threading.Event()
        self._window_ready = threading.Event()
        self._monitor_failed = threading.Event()
        self._launch_lock = threading.Lock()
        self._closed = False

    def _new_profile(self) -> Path:
        self.temp_root.mkdir(parents=True, exist_ok=True)
        cleanup_stale_profiles(self.temp_root, self.api)
        profile = Path(tempfile.mkdtemp(prefix=PROFILE_PREFIX, dir=self.temp_root))
        try:
            (profile / PROFILE_MARKER).write_text(PROFILE_MARKER_CONTENT, encoding="utf-8")
        except OSError:
            shutil.rmtree(profile, ignore_errors=True)
            raise EdgeSessionError("The temporary Edge profile could not be prepared.") from None
        self.profile_path = profile
        return profile

    def open_or_activate(self, url: str) -> None:
        """Open the dedicated window, wait for its HWND, or restore the existing window."""
        with self._launch_lock:
            if self._closed:
                raise EdgeSessionError("The XmlToPdf Edge session has already closed.")
            tracker = self.tracker
            if tracker is not None and tracker.hwnd is not None:
                if self.api.is_window(tracker.hwnd):
                    self.api.activate_window(tracker.hwnd)
                    return
            if self._monitor_thread is not None and self._monitor_thread.is_alive():
                thread = self._monitor_thread
            else:
                self._release_finished_session()
                profile = self._new_profile()
                command = [
                    str(self.executable),
                    f"--app={url}",
                    f"--user-data-dir={profile}",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-background-mode",
                ]
                try:
                    process = self.process_factory(command, close_fds=True)
                except Exception as error:
                    remove_owned_profile(profile, self.temp_root)
                    self.profile_path = None
                    raise EdgeSessionError("Microsoft Edge could not be started.") from error
                self.root_pid = int(process.pid)
                self.tracker = EdgeWindowTracker(
                    self.root_pid,
                    self.api,
                    close_grace=self.close_grace,
                    monotonic=self.monotonic,
                )
                self._monitor_stop.clear()
                self._window_ready.clear()
                self._monitor_failed.clear()
                thread = threading.Thread(
                    target=self._monitor,
                    name="XmlToPdf-Edge-window-monitor",
                    daemon=True,
                )
                self._monitor_thread = thread
                try:
                    thread.start()
                except Exception as error:
                    self._monitor_thread = None
                    self._monitor_failed.set()
                    try:
                        self.on_monitor_failure()
                    except Exception:
                        pass
                    raise EdgeSessionError(
                        "The dedicated Edge window could not be monitored; use the system tray to stop XmlToPdf."
                    ) from error

        deadline = self.monotonic() + self.startup_timeout
        while not self._window_ready.is_set():
            if self._monitor_failed.is_set():
                raise EdgeSessionError(
                    "The dedicated Edge window could not be monitored. "
                    "XmlToPdf remains available from the system tray."
                )
            remaining = deadline - self.monotonic()
            if remaining <= 0:
                break
            self._window_ready.wait(min(self.poll_interval, remaining))
        if not self._window_ready.is_set():
            raise EdgeSessionError(
                "The dedicated Microsoft Edge window did not become available. "
                "XmlToPdf remains available from the system tray."
            )
        tracker = self.tracker
        if tracker is not None and tracker.hwnd is not None:
            self.api.activate_window(tracker.hwnd)

    def _monitor(self) -> None:
        tracker = self.tracker
        if tracker is None:
            return
        consecutive_errors = 0
        while not self._monitor_stop.is_set():
            try:
                state = tracker.poll()
                consecutive_errors = 0
                if state == "opened":
                    self._window_ready.set()
                elif state == "closed":
                    self._closed = True
                    try:
                        self.on_window_closed()
                    except Exception:
                        try:
                            self.on_monitor_failure()
                        except Exception:
                            pass
                    return
            except Exception:
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    self._monitor_failed.set()
                    try:
                        self.on_monitor_failure()
                    except Exception:
                        pass
                    return
            self._monitor_stop.wait(self.poll_interval)

    def _release_finished_session(self) -> None:
        if self.profile_path is None:
            return
        if self.root_pid is None:
            remove_owned_profile(self.profile_path, self.temp_root)
            self.profile_path = None
            return
        if self._related_edge_processes_alive():
            raise EdgeSessionError(
                "Microsoft Edge is still starting. Use its dedicated window or close XmlToPdf from the system tray."
            )
        remove_owned_profile(self.profile_path, self.temp_root)
        self.profile_path = None
        self.root_pid = None
        self.tracker = None
        self._monitor_thread = None

    def _related_edge_processes_alive(self) -> bool:
        if self.root_pid is None:
            return False
        try:
            processes = self.api.snapshot_processes()
        except Exception:
            return True
        related = discover_edge_processes(
            self.root_pid,
            processes,
            set() if self.tracker is None else self.tracker.related_pids,
        )
        if self.tracker is not None:
            self.tracker.related_pids = related
        return any(
            pid in processes and processes[pid].image_name.casefold() == "msedge.exe"
            for pid in related
        )

    def cleanup(self) -> None:
        """Stop monitoring and remove the owned profile only after its Edge tree exits."""
        self._monitor_stop.set()
        current_thread = threading.current_thread()
        thread = self._monitor_thread
        if thread is not None and thread is not current_thread:
            thread.join(timeout=2.0)
            if thread.is_alive():
                return

        deadline = self.monotonic() + self.cleanup_timeout
        while self._related_edge_processes_alive() and self.monotonic() < deadline:
            self.sleep(min(self.poll_interval, max(0.0, deadline - self.monotonic())))

        if self.profile_path is not None and not self._related_edge_processes_alive():
            if remove_owned_profile(self.profile_path, self.temp_root):
                self.profile_path = None
