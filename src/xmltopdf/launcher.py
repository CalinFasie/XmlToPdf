"""Windows console launcher for the local XmlToPdf web application."""

from __future__ import annotations

import errno
import http.client
import os
import socket
import subprocess
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from werkzeug.serving import ThreadedWSGIServer, WSGIRequestHandler

from . import LOCAL_HOST, LOCAL_PORT, create_app

APP_URL = f"http://{LOCAL_HOST}:{LOCAL_PORT}/"
STARTUP_TIMEOUT_SECONDS = 10.0
READINESS_POLL_SECONDS = 0.1


class EdgeUnavailableError(RuntimeError):
    """Raised when Microsoft Edge cannot be found or launched."""


class PortInUseError(RuntimeError):
    """Raised when another process already owns the configured loopback port."""


class QuietRequestHandler(WSGIRequestHandler):
    """Avoid writing request details to the launcher console."""

    def log(self, _type: str, _message: str, *args: Any) -> None:
        return


class LocalThreadedWSGIServer(ThreadedWSGIServer):
    """Threaded Werkzeug server that does not allow another process to reuse its port."""

    allow_reuse_address = False

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


def open_edge(
    url: str = APP_URL,
    *,
    environ: Mapping[str, str] | None = None,
    popen: Callable[..., Any] | None = None,
) -> None:
    """Start Microsoft Edge directly, without shell expansion or default-browser changes."""
    executable = find_edge_executable(environ=environ)
    if executable is None:
        raise EdgeUnavailableError("Microsoft Edge was not found.")

    start_process = subprocess.Popen if popen is None else popen
    try:
        start_process([str(executable), url], close_fds=True)
    except OSError as error:
        raise EdgeUnavailableError("Microsoft Edge could not be started.") from error


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


def _port_is_occupied(error: OSError) -> bool:
    return error.errno == errno.EADDRINUSE or getattr(error, "winerror", None) == 10048


def run_launcher(
    *,
    app_factory: Callable[[], Any] | None = None,
    server_factory: Callable[..., Any] | None = None,
    thread_factory: Callable[..., Any] | None = None,
    readiness_check: Callable[..., bool] | None = None,
    edge_opener: Callable[[str], None] | None = None,
    output: Callable[[str], None] | None = None,
) -> int:
    """Run the local server, wait for readiness, then open Edge and serve until stopped."""
    create_application = create_app if app_factory is None else app_factory
    bind_server = create_local_server if server_factory is None else server_factory
    make_thread = threading.Thread if thread_factory is None else thread_factory
    wait_ready = wait_until_ready if readiness_check is None else readiness_check
    launch_browser = open_edge if edge_opener is None else edge_opener
    write_output = print if output is None else output

    try:
        app = create_application()
        server = bind_server(
            LOCAL_HOST,
            LOCAL_PORT,
            app,
            request_handler=QuietRequestHandler,
        )
    except PortInUseError:
        write_output(
            "Portul local 5000 este deja ocupat. "
            "Inchide aplicatia care il foloseste si incearca din nou."
        )
        return 1
    except OSError as error:
        if _port_is_occupied(error):
            write_output(
                "Portul local 5000 este deja ocupat. "
                "Inchide aplicatia care il foloseste si incearca din nou."
            )
        else:
            write_output("Serverul local XmlToPdf nu a putut porni.")
        return 1
    except Exception:
        write_output("Serverul local XmlToPdf nu a putut porni.")
        return 1

    server_thread = None
    thread_started = False
    try:
        server_thread = make_thread(
            target=server.serve_forever,
            name="XmlToPdf-local-server",
            daemon=False,
        )
        server_thread.start()
        thread_started = True

        if not wait_ready(timeout=STARTUP_TIMEOUT_SECONDS):
            write_output("Serverul local XmlToPdf nu a devenit disponibil.")
            return 1

        try:
            launch_browser(APP_URL)
        except (EdgeUnavailableError, OSError):
            write_output(
                "Microsoft Edge nu a putut fi deschis. Serverul ruleaza; deschide manual "
                f"{APP_URL} in Microsoft Edge."
            )

        write_output(f"XmlToPdf ruleaza la {APP_URL}")
        write_output("Pentru oprire, apasa Ctrl+C sau inchide aceasta fereastra.")
        try:
            server_thread.join()
        except KeyboardInterrupt:
            write_output("Se opreste serverul XmlToPdf.")
        return 0
    except KeyboardInterrupt:
        write_output("Se opreste serverul XmlToPdf.")
        return 0
    except Exception:
        write_output("Serverul local XmlToPdf s-a oprit din cauza unei erori.")
        return 1
    finally:
        try:
            if thread_started and server_thread is not None:
                server.shutdown()
                server_thread.join()
        finally:
            server.server_close()


def main() -> int:
    """Console entry point used by the portable Windows distribution."""
    return run_launcher()
