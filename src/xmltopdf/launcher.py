"""Windows system-tray launcher for the local XmlToPdf web application."""

from __future__ import annotations

import ctypes
import errno
import http.client
import os
import socket
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from werkzeug.serving import ThreadedWSGIServer, WSGIRequestHandler

from . import LOCAL_HOST, LOCAL_PORT, create_app
from .edge_session import EdgeAppSession, EdgeSessionError

APP_URL = f"http://{LOCAL_HOST}:{LOCAL_PORT}/"
STARTUP_TIMEOUT_SECONDS = 10.0
READINESS_POLL_SECONDS = 0.1
MUTEX_NAME = r"Local\CalinFasie.XmlToPdf"
ERROR_ALREADY_EXISTS = 183
MB_OK = 0x00000000
MB_ICONERROR = 0x00000010
MB_ICONWARNING = 0x00000030
MB_ICONINFORMATION = 0x00000040
EDGE_CLOSE_TIMEOUT_SECONDS = 5.0


EdgeUnavailableError = EdgeSessionError


class PortInUseError(RuntimeError):
    """Raised when another process already owns the configured loopback port."""


class SingleInstanceError(RuntimeError):
    """Raised when Windows cannot create the single-instance mutex."""


class QuietRequestHandler(WSGIRequestHandler):
    """Avoid writing request details to the launcher output streams."""

    def log(self, _type: str, _message: str, *args: Any) -> None:
        return


class LocalThreadedWSGIServer(ThreadedWSGIServer):
    """Threaded Werkzeug server that does not allow another process to reuse its port."""

    allow_reuse_address = False
    daemon_threads = False
    block_on_close = True

    def server_bind(self) -> None:
        try:
            exclusive_option = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
            if exclusive_option is not None:
                self.socket.setsockopt(socket.SOL_SOCKET, exclusive_option, 1)
            super().server_bind()
        except OSError as error:
            if _port_is_occupied(error):
                raise PortInUseError from None
            raise RuntimeError from None


@dataclass(frozen=True)
class SingleInstanceHandle:
    handle: int
    owns_mutex: bool
    already_running: bool


class LauncherController:
    """Own the server lifecycle and connect tray actions to it."""

    def __init__(
        self,
        server: Any,
        server_thread: threading.Thread,
        *,
        icon: Any | None = None,
    ) -> None:
        self.server = server
        self.server_thread = server_thread
        self.icon = icon
        self._stop_lock = threading.Lock()
        self._stop_finished = threading.Event()
        self._stop_started = False
        self._stop_error: BaseException | None = None
        self._shutdown_lock = threading.Condition()
        self._shutdown_worker_active = False
        self._window_close_started = False
        self._pending_responses = 0
        self._edge_window_closer: Callable[[], bool] | None = None
        self._shutdown_failure_reporter: Callable[[], None] | None = None

    def configure_edge_shutdown(
        self,
        close_window: Callable[[], bool],
        report_failure: Callable[[], None],
    ) -> None:
        """Register the dedicated-window close operation for launcher shutdown."""
        with self._shutdown_lock:
            self._edge_window_closer = close_window
            self._shutdown_failure_reporter = report_failure

    def open_interface(
        self,
        *,
        edge_opener: Callable[[str], None],
        message_box: Callable[[str, str, int], None],
    ) -> None:
        """Open the local page in Edge without touching any other Edge process."""
        try:
            edge_opener(APP_URL)
        except (EdgeSessionError, OSError):
            message_box(
                "Fereastra Microsoft Edge dedicată nu a putut fi pornită sau urmărită. "
                "Serverul XmlToPdf rămâne activ; folosește system tray pentru a-l opri "
                f"sau deschide manual {APP_URL}.",
                "XmlToPdf",
                MB_OK | MB_ICONWARNING,
            )

    def stop(self) -> None:
        """Stop the WSGI server, release its socket, join its thread, and hide the tray icon."""
        with self._stop_lock:
            owns_stop = not self._stop_started
            if owns_stop:
                self._stop_started = True

        if not owns_stop:
            self._stop_finished.wait()
            if self._stop_error is not None:
                raise RuntimeError("XmlToPdf shutdown did not complete cleanly.") from self._stop_error
            return

        try:
            try:
                if self.server_thread.is_alive():
                    self.server.shutdown()
            finally:
                try:
                    self.server.server_close()
                finally:
                    if self.server_thread.is_alive():
                        self.server_thread.join()
                    if self.icon is not None:
                        self.icon.stop()
        except BaseException as error:
            self._stop_error = error
            raise
        finally:
            self._stop_finished.set()

    def stop_after_response(self, response: Any) -> bool:
        """Schedule shutdown only after the WSGI response has been transmitted."""
        with self._shutdown_lock:
            if self._window_close_started or self._stop_started:
                return False
            self._pending_responses += 1

        def response_closed() -> None:
            with self._shutdown_lock:
                self._pending_responses = max(0, self._pending_responses - 1)
                self._shutdown_lock.notify_all()

        try:
            response.call_on_close(response_closed)
        except Exception:
            response_closed()
            return False
        return self.request_stop()

    def request_stop(self) -> bool:
        """Start the shared, nonblocking shutdown path used by tray and web UI."""
        with self._shutdown_lock:
            if self._stop_started or self._shutdown_worker_active:
                return True
            self._shutdown_worker_active = True
            worker = threading.Thread(
                target=self._run_requested_shutdown,
                name="XmlToPdf-controlled-shutdown",
                daemon=False,
            )
            try:
                worker.start()
            except Exception:
                self._shutdown_worker_active = False
                self._shutdown_lock.notify_all()
                return False
            return True

    def _run_requested_shutdown(self) -> None:
        try:
            with self._shutdown_lock:
                while self._pending_responses and not self._stop_started:
                    self._shutdown_lock.wait()
                if self._stop_started:
                    return
                self._window_close_started = True
                close_window = self._edge_window_closer

            if close_window is not None and not close_window():
                reporter = self._shutdown_failure_reporter
                if reporter is not None:
                    reporter()
                return
            self.stop()
        except Exception:
            reporter = self._shutdown_failure_reporter
            if reporter is not None:
                try:
                    reporter()
                except Exception:
                    pass
        finally:
            with self._shutdown_lock:
                self._window_close_started = False
                self._shutdown_worker_active = False
                self._shutdown_lock.notify_all()

    def wait_for_requested_shutdown(self, timeout: float | None = None) -> bool:
        """Wait for a test or orderly launcher teardown, never from a tray callback."""
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._shutdown_lock:
            while self._shutdown_worker_active:
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    return False
                self._shutdown_lock.wait(remaining)
        return True


def create_local_server(
    host: str,
    port: int,
    app: Any,
    *,
    request_handler: type[WSGIRequestHandler],
) -> LocalThreadedWSGIServer:
    """Bind an exclusive threaded server to the configured loopback interface."""
    return LocalThreadedWSGIServer(host, port, app, handler=request_handler)


def find_edge_executable(
    environ: Mapping[str, str] | None = None,
) -> Path | None:
    """Find Edge in its standard per-machine or per-user installation directories."""
    env = os.environ if environ is None else environ

    candidates: list[Path] = []
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        base = env.get(variable)
        if base:
            candidates.append(Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe")

    local_app_data = env.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(
            Path(local_app_data) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        )

    return next((candidate for candidate in candidates if candidate.is_file()), None)


def wait_until_ready(
    timeout: float = STARTUP_TIMEOUT_SECONDS,
    *,
    monotonic: Callable[[], float] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> bool:
    """Probe only the bound loopback address until the Flask app returns HTTP 200."""
    get_time = time.monotonic if monotonic is None else monotonic
    pause = time.sleep if sleep is None else sleep
    deadline = get_time() + timeout

    while True:
        connection = http.client.HTTPConnection(LOCAL_HOST, LOCAL_PORT, timeout=0.5)
        try:
            connection.request("GET", "/", headers={"Connection": "close"})
            response = connection.getresponse()
            response.read()
            if response.status == 200:
                return True
        except (OSError, http.client.HTTPException):
            pass
        finally:
            connection.close()

        remaining = deadline - get_time()
        if remaining <= 0:
            return False
        pause(min(READINESS_POLL_SECONDS, remaining))


def create_tray_icon(
    open_action: Callable[[], None],
    exit_action: Callable[[], None],
) -> Any:
    """Build the in-memory icon and menu without writing user data to disk."""
    import pystray
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (64, 64), (35, 83, 125, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((5, 5, 59, 59), radius=10, outline=(255, 255, 255, 255), width=3)
    draw.text((19, 14), "X", fill=(255, 255, 255, 255), stroke_width=1)

    menu = pystray.Menu(
        pystray.MenuItem("Deschide XmlToPdf", lambda _icon, _item: open_action()),
        pystray.MenuItem("Închide XmlToPdf", lambda _icon, _item: exit_action()),
    )
    return pystray.Icon("XmlToPdf", image, "XmlToPdf", menu)


def show_windows_message(message: str, title: str, flags: int) -> None:
    """Show a native Windows message without relying on stdout or a console."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    message_box = user32.MessageBoxW
    message_box.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint)
    message_box.restype = ctypes.c_int
    message_box(None, message, title, flags)


def acquire_single_instance() -> SingleInstanceHandle:
    """Create a per-user-session mutex so a second launcher cannot start a server."""
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_mutex = kernel32.CreateMutexW
        create_mutex.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p)
        create_mutex.restype = ctypes.c_void_p
        ctypes.set_last_error(0)
        handle = create_mutex(None, True, MUTEX_NAME)
        if not handle:
            raise SingleInstanceError
        already_running = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
        return SingleInstanceHandle(
            handle=handle,
            owns_mutex=not already_running,
            already_running=already_running,
        )
    except SingleInstanceError:
        raise
    except Exception as error:
        raise SingleInstanceError from error


def release_single_instance(mutex: SingleInstanceHandle) -> None:
    """Release and close the mutex handle, including a handle to an existing mutex."""
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.ReleaseMutex.argtypes = (ctypes.c_void_p,)
        kernel32.ReleaseMutex.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
        kernel32.CloseHandle.restype = ctypes.c_int
        if mutex.owns_mutex:
            kernel32.ReleaseMutex(mutex.handle)
        kernel32.CloseHandle(mutex.handle)
    except Exception:
        return


def _port_is_occupied(error: OSError) -> bool:
    return error.errno == errno.EADDRINUSE or getattr(error, "winerror", None) == 10048


def run_windowed_launcher(
    *,
    app_factory: Callable[[], Any] | None = None,
    server_factory: Callable[..., Any] | None = None,
    thread_factory: Callable[..., Any] | None = None,
    readiness_check: Callable[..., bool] | None = None,
    edge_opener: Callable[[str], None] | None = None,
    edge_session_factory: Callable[..., Any] | None = None,
    tray_factory: Callable[[Callable[[], None], Callable[[], None]], Any] | None = None,
    message_box: Callable[[str, str, int], None] | None = None,
    mutex_acquirer: Callable[[], SingleInstanceHandle] | None = None,
    mutex_releaser: Callable[[SingleInstanceHandle], None] | None = None,
) -> int:
    """Run the local server and tray event loop without console output."""
    create_application = create_app if app_factory is None else app_factory
    bind_server = create_local_server if server_factory is None else server_factory
    make_thread = threading.Thread if thread_factory is None else thread_factory
    wait_ready = wait_until_ready if readiness_check is None else readiness_check
    make_edge_session = EdgeAppSession if edge_session_factory is None else edge_session_factory
    make_tray = create_tray_icon if tray_factory is None else tray_factory
    show_message = show_windows_message if message_box is None else message_box
    acquire_mutex = acquire_single_instance if mutex_acquirer is None else mutex_acquirer
    release_mutex = release_single_instance if mutex_releaser is None else mutex_releaser

    try:
        mutex = acquire_mutex()
    except Exception:
        show_message(
            "XmlToPdf nu a putut verifica dacă rulează deja.",
            "XmlToPdf",
            MB_OK | MB_ICONERROR,
        )
        return 1

    if mutex.already_running:
        release_mutex(mutex)
        show_message(
            "XmlToPdf rulează deja. Folosește iconul existent din zona de notificări.",
            "XmlToPdf",
            MB_OK | MB_ICONINFORMATION,
        )
        return 0

    server = None
    controller: LauncherController | None = None
    server_thread: threading.Thread | None = None
    edge_session: Any | None = None
    controller_reference: dict[str, LauncherController] = {}

    def report_edge_monitor_failure() -> None:
        show_message(
            "XmlToPdf nu mai poate urmări fereastra Edge dedicată. Serverul rămâne activ; "
            "folosește system tray pentru a-l opri.",
            "XmlToPdf",
            MB_OK | MB_ICONWARNING,
        )

    def launch_browser(url: str) -> None:
        nonlocal edge_session
        if edge_opener is not None:
            edge_opener(url)
            return
        if edge_session is None:
            executable = find_edge_executable()
            if executable is None:
                raise EdgeSessionError("Microsoft Edge was not found.")
            if controller is None:
                raise EdgeSessionError("The XmlToPdf server is not ready.")
            edge_session = make_edge_session(
                executable=executable,
                on_window_closed=controller.stop,
                on_monitor_failure=report_edge_monitor_failure,
            )
            close_window = getattr(edge_session, "close_window", None)
            if callable(close_window):
                controller.configure_edge_shutdown(
                    lambda: bool(close_window(timeout=EDGE_CLOSE_TIMEOUT_SECONDS)),
                    lambda: show_message(
                        "Fereastra XmlToPdf nu a putut fi închisă. Aplicația și serverul au rămas active; "
                        "încearcă din nou sau închide fereastra Edge dedicată cu X.",
                        "XmlToPdf",
                        MB_OK | MB_ICONWARNING,
                    ),
                )
        edge_session.open_or_activate(url)

    def schedule_web_shutdown(response: Any) -> bool:
        active_controller = controller_reference.get("controller")
        if active_controller is None:
            return False
        return active_controller.stop_after_response(response)

    try:
        if app_factory is None:
            app = create_app(
                enable_shutdown=True,
                shutdown_scheduler=schedule_web_shutdown,
            )
        else:
            app = create_application()
        app.logger.disabled = True
        server = bind_server(
            LOCAL_HOST,
            LOCAL_PORT,
            app,
            request_handler=QuietRequestHandler,
        )
        server_thread = make_thread(
            target=server.serve_forever,
            name="XmlToPdf-local-server",
            daemon=False,
        )
        controller = LauncherController(server, server_thread)
        controller_reference["controller"] = controller
        server_thread.start()

        if not wait_ready(timeout=STARTUP_TIMEOUT_SECONDS):
            show_message(
                "Serverul local XmlToPdf nu a devenit disponibil.",
                "XmlToPdf",
                MB_OK | MB_ICONERROR,
            )
            return 1

        tray_icon = make_tray(
            lambda: controller.open_interface(
                edge_opener=launch_browser,
                message_box=show_message,
            ),
            controller.request_stop,
        )
        controller.icon = tray_icon

        controller.open_interface(edge_opener=launch_browser, message_box=show_message)
        tray_icon.run()
        return 0
    except PortInUseError:
        show_message(
            "Portul local 5000 este ocupat de altă aplicație. Închide aplicația care îl folosește și încearcă din nou.",
            "XmlToPdf",
            MB_OK | MB_ICONERROR,
        )
        return 1
    except OSError as error:
        if _port_is_occupied(error):
            show_message(
                "Portul local 5000 este ocupat de altă aplicație. Închide aplicația care îl folosește și încearcă din nou.",
                "XmlToPdf",
                MB_OK | MB_ICONERROR,
            )
        else:
            show_message(
                "Serverul local XmlToPdf nu a putut porni.",
                "XmlToPdf",
                MB_OK | MB_ICONERROR,
            )
        return 1
    except Exception:
        show_message(
            "XmlToPdf s-a oprit din cauza unei erori. Repornește aplicația.",
            "XmlToPdf",
            MB_OK | MB_ICONERROR,
        )
        return 1
    finally:
        try:
            if controller is not None:
                controller.stop()
            elif server is not None:
                server.server_close()
        except Exception:
            show_message(
                "XmlToPdf nu a putut încheia complet oprirea serverului.",
                "XmlToPdf",
                MB_OK | MB_ICONERROR,
            )
        finally:
            try:
                if edge_session is not None:
                    edge_session.cleanup()
            except Exception:
                show_message(
                    "Profilul temporar Edge nu a putut fi curățat în siguranță; "
                    "va fi verificat la următoarea pornire XmlToPdf.",
                    "XmlToPdf",
                    MB_OK | MB_ICONWARNING,
                )
            finally:
                release_mutex(mutex)


def main() -> int:
    """Entry point for the PyInstaller windowed executable."""
    return run_windowed_launcher()
