from __future__ import annotations

import errno
import http.client
import json
import re
import socket
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import xmltopdf
from xmltopdf import LOCAL_HOST, LOCAL_PORT, create_app
from xmltopdf import launcher


class FakeServer:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def serve_forever(self) -> None:
        self.events.append("serve_forever")

    def shutdown(self) -> None:
        self.events.append("shutdown")

    def server_close(self) -> None:
        self.events.append("server_close")


class FakeThread:
    def __init__(
        self,
        *,
        target: Any,
        name: str,
        daemon: bool,
        events: list[str],
    ) -> None:
        self.target = target
        self.name = name
        self.daemon = daemon
        self.events = events
        self.alive = False

    def start(self) -> None:
        self.events.append("thread_start")
        self.alive = True

    def is_alive(self) -> bool:
        return self.alive

    def join(self) -> None:
        self.events.append("thread_join")
        self.alive = False


class FakeIcon:
    def __init__(
        self,
        events: list[str],
        open_action: Any,
        exit_action: Any,
    ) -> None:
        self.events = events
        self.open_action = open_action
        self.exit_action = exit_action

    def run(self) -> None:
        self.events.append("tray_run")
        self.open_action()
        self.exit_action()

    def stop(self) -> None:
        self.events.append("tray_stop")


@pytest.fixture
def project_temp_dir() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(
        prefix=".launcher-test-", dir=Path(__file__).parents[1]
    ) as directory:
        yield Path(directory)


def _owned_mutex() -> launcher.SingleInstanceHandle:
    return launcher.SingleInstanceHandle(handle=1, owns_mutex=True, already_running=False)


def test_windowed_launcher_starts_server_before_edge_and_tray_and_stops_cleanly() -> None:
    events: list[str] = []
    server = FakeServer(events)
    output: list[tuple[str, str, int]] = []
    edge_calls: list[str] = []
    released: list[launcher.SingleInstanceHandle] = []
    thread: FakeThread | None = None

    def thread_factory(**kwargs: Any) -> FakeThread:
        nonlocal thread
        thread = FakeThread(**kwargs, events=events)
        return thread

    def tray_factory(open_action: Any, exit_action: Any) -> FakeIcon:
        events.append("tray_created")
        return FakeIcon(events, open_action, exit_action)

    def server_factory(host: str, port: int, app: Any, **_kwargs: Any) -> FakeServer:
        assert app.logger.disabled
        assert (host, port) == (LOCAL_HOST, LOCAL_PORT)
        events.append("server_bound")
        return server

    def edge_opener(url: str) -> None:
        edge_calls.append(url)
        events.append("edge")

    result = launcher.run_windowed_launcher(
        server_factory=server_factory,
        thread_factory=thread_factory,
        readiness_check=lambda **_kwargs: events.append("ready") or True,
        edge_opener=edge_opener,
        tray_factory=tray_factory,
        message_box=lambda *args: output.append(args),
        mutex_acquirer=_owned_mutex,
        mutex_releaser=released.append,
    )

    assert result == 0
    assert edge_calls == [launcher.APP_URL, launcher.APP_URL]
    assert events.index("server_bound") < events.index("thread_start") < events.index("ready")
    assert events.index("ready") < events.index("tray_created")
    assert events.index("ready") < events.index("edge") < events.index("tray_run")
    assert events.index("shutdown") < events.index("server_close") < events.index("thread_join")
    assert events.index("thread_join") < events.index("tray_stop")
    assert events.count("shutdown") == 1
    assert thread is not None and thread.name == "XmlToPdf-local-server" and not thread.daemon
    assert output == []
    assert released == [_owned_mutex()]


def test_second_instance_reports_existing_tray_without_binding_port_or_opening_edge() -> None:
    messages: list[tuple[str, str, int]] = []
    calls: list[str] = []
    existing = launcher.SingleInstanceHandle(handle=7, owns_mutex=False, already_running=True)

    result = launcher.run_windowed_launcher(
        app_factory=lambda: calls.append("app"),
        server_factory=lambda *_a, **_k: calls.append("server"),
        edge_opener=lambda _url: calls.append("edge"),
        message_box=lambda *args: messages.append(args),
        mutex_acquirer=lambda: existing,
        mutex_releaser=lambda mutex: calls.append(f"release:{mutex.handle}"),
    )

    assert result == 0
    assert calls == ["release:7"]
    assert len(messages) == 1 and "rulează deja" in messages[0][0]
    assert messages[0][2] & launcher.MB_ICONINFORMATION


def test_port_occupied_by_unknown_process_reports_error_without_edge() -> None:
    messages: list[tuple[str, str, int]] = []
    edge_calls: list[str] = []

    def server_factory(*_args: Any, **_kwargs: Any) -> None:
        raise OSError(errno.EADDRINUSE, "private OS detail")

    result = launcher.run_windowed_launcher(
        server_factory=server_factory,
        edge_opener=edge_calls.append,
        message_box=lambda *args: messages.append(args),
        mutex_acquirer=_owned_mutex,
        mutex_releaser=lambda _mutex: None,
    )

    assert result == 1
    assert edge_calls == []
    assert len(messages) == 1 and "5000" in messages[0][0] and "ocupat" in messages[0][0]
    assert "private OS detail" not in messages[0][0]


def test_readiness_failure_shows_safe_message_and_closes_socket() -> None:
    events: list[str] = []
    messages: list[tuple[str, str, int]] = []
    server = FakeServer(events)

    result = launcher.run_windowed_launcher(
        server_factory=lambda *_a, **_k: server,
        thread_factory=lambda **kwargs: FakeThread(**kwargs, events=events),
        readiness_check=lambda **_kwargs: False,
        edge_opener=lambda _url: pytest.fail("Edge must wait for server readiness."),
        tray_factory=lambda *_a: pytest.fail("Tray must not start before readiness."),
        message_box=lambda *args: messages.append(args),
        mutex_acquirer=_owned_mutex,
        mutex_releaser=lambda _mutex: None,
    )

    assert result == 1
    assert "nu a devenit disponibil" in messages[0][0]
    assert events[-3:] == ["shutdown", "server_close", "thread_join"]


def test_real_werkzeug_server_stops_and_releases_its_bound_socket() -> None:
    from flask import Flask

    app = Flask(__name__)
    app.add_url_rule("/", view_func=lambda: "ready")
    server = launcher.create_local_server(
        LOCAL_HOST,
        0,
        app,
        request_handler=launcher.QuietRequestHandler,
    )
    assert not server.daemon_threads and server.block_on_close
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, name="test-server", daemon=False)
    controller = launcher.LauncherController(server, thread)

    thread.start()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        connection = http.client.HTTPConnection(LOCAL_HOST, port, timeout=0.1)
        try:
            connection.request("GET", "/")
            response = connection.getresponse()
            if response.status == 200:
                response.read()
                break
        except OSError:
            time.sleep(0.01)
        finally:
            connection.close()
    else:
        controller.stop()
        pytest.fail("Werkzeug server did not become ready.")

    controller.stop()

    with socket.socket() as probe:
        probe.bind((LOCAL_HOST, port))
        assert not thread.is_alive()


def test_web_shutdown_sends_response_then_stops_server_and_releases_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with socket.socket() as reservation:
        reservation.bind((LOCAL_HOST, 0))
        port = reservation.getsockname()[1]
    monkeypatch.setattr(xmltopdf, "LOCAL_PORT", port)

    controller_reference: dict[str, launcher.LauncherController] = {}

    def schedule_shutdown(response: Any) -> bool:
        return controller_reference["controller"].stop_after_response(response)

    app = create_app(enable_shutdown=True, shutdown_scheduler=schedule_shutdown)
    server = launcher.create_local_server(
        LOCAL_HOST,
        port,
        app,
        request_handler=launcher.QuietRequestHandler,
    )
    server_thread = threading.Thread(
        target=server.serve_forever,
        name="test-web-shutdown-server",
        daemon=False,
    )
    tray_events: list[str] = []
    icon = FakeIcon(tray_events, lambda: None, lambda: None)
    controller = launcher.LauncherController(server, server_thread, icon=icon)
    controller_reference["controller"] = controller
    server_thread.start()

    try:
        connection = http.client.HTTPConnection(LOCAL_HOST, port, timeout=3)
        connection.request("GET", "/", headers={"Connection": "close"})
        home = connection.getresponse()
        homepage = home.read()
        cookie_header = home.getheader("Set-Cookie", "").split(";", 1)[0]
        csrf_match = re.search(rb'data-csrf-token="([^"]+)"', homepage)
        assert csrf_match is not None
        csrf_token = csrf_match.group(1).decode("ascii")
        connection.close()

        shutdown_connection = http.client.HTTPConnection(LOCAL_HOST, port, timeout=3)
        shutdown_connection.request(
            "POST",
            "/shutdown",
            body=b"",
            headers={
                "Host": f"{LOCAL_HOST}:{port}",
                "Origin": f"http://{LOCAL_HOST}:{port}",
                "Cookie": cookie_header,
                "X-CSRF-Token": csrf_token,
                "Connection": "close",
            },
        )
        response = shutdown_connection.getresponse()
        response_body = response.read()
        shutdown_connection.close()

        assert response.status == 202
        assert json.loads(response_body) == {
            "ok": True,
            "message": "XmlToPdf a fost oprită. Poți închide această filă.",
        }
        server_thread.join(timeout=3)
        assert not server_thread.is_alive()
        assert controller._stop_finished.wait(timeout=3)
        assert tray_events == ["tray_stop"]
        with socket.socket() as probe:
            probe.bind((LOCAL_HOST, port))
    finally:
        if server_thread.is_alive():
            controller.stop()


def test_edge_failure_keeps_server_and_tray_available_and_offers_local_url() -> None:
    events: list[str] = []
    messages: list[tuple[str, str, int]] = []
    server = FakeServer(events)
    opened: list[str] = []

    def failing_edge(url: str) -> None:
        opened.append(url)
        raise launcher.EdgeUnavailableError("private OS detail")

    result = launcher.run_windowed_launcher(
        server_factory=lambda *_a, **_k: server,
        thread_factory=lambda **kwargs: FakeThread(**kwargs, events=events),
        readiness_check=lambda **_kwargs: events.append("ready") or True,
        edge_opener=failing_edge,
        tray_factory=lambda open_action, exit_action: FakeIcon(events, open_action, exit_action),
        message_box=lambda *args: messages.append(args),
        mutex_acquirer=_owned_mutex,
        mutex_releaser=lambda _mutex: None,
    )

    assert result == 0
    assert opened == [launcher.APP_URL, launcher.APP_URL]
    assert len(messages) == 2
    assert all(launcher.APP_URL in message[0] for message in messages)
    assert all("private OS detail" not in message[0] for message in messages)
    assert "tray_run" in events and "shutdown" in events


def test_mutex_acquisition_failure_is_reported_without_starting_server() -> None:
    messages: list[tuple[str, str, int]] = []
    started: list[bool] = []

    result = launcher.run_windowed_launcher(
        server_factory=lambda *_a, **_k: started.append(True),
        message_box=lambda *args: messages.append(args),
        mutex_acquirer=lambda: (_ for _ in ()).throw(launcher.SingleInstanceError()),
        mutex_releaser=lambda _mutex: None,
    )

    assert result == 1
    assert started == []
    assert "nu a putut verifica" in messages[0][0]


class FakeWinApiFunction:
    def __init__(self, function: Any) -> None:
        self.function = function
        self.argtypes: Any = None
        self.restype: Any = None

    def __call__(self, *args: Any) -> Any:
        return self.function(*args)


def test_windows_mutex_detects_existing_instance_and_releases_only_owned_mutex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    errors = iter([0, launcher.ERROR_ALREADY_EXISTS])
    calls: list[tuple[str, Any]] = []
    api = SimpleNamespace(
        CreateMutexW=FakeWinApiFunction(lambda *_args: 42),
        ReleaseMutex=FakeWinApiFunction(lambda handle: calls.append(("release", handle)) or 1),
        CloseHandle=FakeWinApiFunction(lambda handle: calls.append(("close", handle)) or 1),
    )
    monkeypatch.setattr(launcher.ctypes, "WinDLL", lambda *_a, **_k: api)
    monkeypatch.setattr(launcher.ctypes, "set_last_error", lambda value: calls.append(("set_error", value)))
    monkeypatch.setattr(launcher.ctypes, "get_last_error", lambda: next(errors))

    first = launcher.acquire_single_instance()
    second = launcher.acquire_single_instance()
    launcher.release_single_instance(first)
    launcher.release_single_instance(second)

    assert first.owns_mutex and not first.already_running
    assert not second.owns_mutex and second.already_running
    assert calls.count(("release", 42)) == 1
    assert calls.count(("close", 42)) == 2
    assert calls.count(("set_error", 0)) == 2


def test_tray_menu_wires_open_and_controlled_exit_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    actions: list[str] = []
    menu_items: list[Any] = []

    class MenuItem:
        def __init__(self, text: str, action: Any) -> None:
            self.text = text
            self.action = action
            menu_items.append(self)

    class Icon:
        def __init__(self, name: str, image: Any, title: str, menu: Any) -> None:
            self.name = name
            self.image = image
            self.title = title
            self.menu = menu

    fake_pystray = SimpleNamespace(Menu=lambda *items: items, MenuItem=MenuItem, Icon=Icon)
    monkeypatch.setitem(sys.modules, "pystray", fake_pystray)
    icon = launcher.create_tray_icon(lambda: actions.append("open"), lambda: actions.append("exit"))

    assert [item.text for item in menu_items] == ["Deschide XmlToPdf", "Închide XmlToPdf"]
    for item in menu_items:
        item.action(icon, item)
    assert actions == ["open", "exit"]


def test_open_edge_uses_explicit_executable_without_shell(project_temp_dir: Path) -> None:
    edge = project_temp_dir / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    edge.parent.mkdir(parents=True)
    edge.touch()
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    launcher.open_edge(
        environ={"ProgramFiles": str(project_temp_dir)},
        popen=lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    assert calls == [(([str(edge), launcher.APP_URL],), {"close_fds": True})]


def test_open_edge_reports_missing_or_failed_executable_safely(project_temp_dir: Path) -> None:
    with pytest.raises(launcher.EdgeUnavailableError):
        launcher.open_edge(environ={}, popen=lambda *_a, **_k: None)

    edge = project_temp_dir / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    edge.parent.mkdir(parents=True)
    edge.touch()

    with pytest.raises(launcher.EdgeUnavailableError) as error:
        launcher.open_edge(
            environ={"ProgramFiles": str(project_temp_dir)},
            popen=lambda *_a, **_k: (_ for _ in ()).throw(OSError("private OS detail")),
        )
    assert "private OS detail" not in str(error.value)


def test_templates_and_static_resources_work_outside_repository_directory(
    project_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(project_temp_dir)
    app = create_app()
    client = app.test_client()

    home = client.get("/", base_url=f"http://{LOCAL_HOST}:{LOCAL_PORT}")
    css = client.get("/static/css/app.css", base_url=f"http://{LOCAL_HOST}:{LOCAL_PORT}")

    assert home.status_code == 200
    assert b"<title>XmlToPdf</title>" in home.data
    assert css.status_code == 200
    assert b"@media print" in css.data
    assert home.headers["Cache-Control"] == "no-store"
    assert css.headers["Cache-Control"] == "no-store"


def test_templates_and_static_resources_resolve_relative_to_frozen_package_module(
    project_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = project_temp_dir / "xmltopdf"
    templates = package / "templates"
    static = package / "static" / "css"
    templates.mkdir(parents=True)
    static.mkdir(parents=True)
    (templates / "index.html").write_text("<title>frozen</title>", encoding="utf-8")
    (static / "app.css").write_text("body { color: black; }", encoding="utf-8")
    monkeypatch.setattr(xmltopdf, "__file__", str(package / "__init__.py"))
    monkeypatch.chdir(Path(__file__).parents[1])

    app = create_app()
    client = app.test_client()
    home = client.get("/", base_url=f"http://{LOCAL_HOST}:{LOCAL_PORT}")
    css = client.get("/static/css/app.css", base_url=f"http://{LOCAL_HOST}:{LOCAL_PORT}")

    assert home.status_code == 200 and b"frozen" in home.data
    assert css.status_code == 200 and b"color: black" in css.data


def test_pyinstaller_spec_is_onefile_windowed_and_contains_runtime_resources() -> None:
    root = Path(__file__).parents[1]
    spec = (root / "XmlToPdf.spec").read_text(encoding="utf-8")
    entry = (root / "tools" / "windows_entry.py").read_text(encoding="utf-8")

    assert '"xmltopdf/templates"' in spec
    assert '"xmltopdf/static"' in spec
    assert 'collect_all("pystray")' in spec
    assert 'collect_dynamic_libs("lxml")' in spec
    assert '"pytest"' in spec and '"tests"' in spec
    assert "console=False" in spec
    assert "COLLECT(" not in spec
    assert "--onedir" not in spec
    assert "print(" not in entry


def test_upload_is_not_written_into_any_application_directory(
    project_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = Path(__file__).parent / "fixtures" / "ubl_invoice_minimal.xml"
    xml_content = fixture.read_bytes()
    monkeypatch.chdir(project_temp_dir)
    client = create_app().test_client()
    home = client.get("/", base_url=f"http://{LOCAL_HOST}:{LOCAL_PORT}")
    with client.session_transaction(base_url=f"http://{LOCAL_HOST}:{LOCAL_PORT}") as session:
        csrf_token = session["csrf_token"]

    response = client.post(
        "/upload",
        data=xml_content,
        content_type="application/xml",
        headers={"Host": f"{LOCAL_HOST}:{LOCAL_PORT}", "X-CSRF-Token": csrf_token},
    )

    assert home.status_code == response.status_code == 200
    assert list(project_temp_dir.iterdir()) == []
