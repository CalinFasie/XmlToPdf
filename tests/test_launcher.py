from __future__ import annotations

import errno
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

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
        interrupt_first_join: bool = False,
    ) -> None:
        self.target = target
        self.name = name
        self.daemon = daemon
        self.events = events
        self.interrupt_first_join = interrupt_first_join
        self.join_count = 0

    def start(self) -> None:
        self.events.append("thread_start")

    def join(self) -> None:
        self.join_count += 1
        self.events.append("thread_join")
        if self.interrupt_first_join and self.join_count == 1:
            raise KeyboardInterrupt


@pytest.fixture
def project_temp_dir() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix=".launcher-test-", dir=Path(__file__).parents[1]) as directory:
        yield Path(directory)


def test_launcher_binds_loopback_fixed_port_reuses_app_and_waits_before_edge() -> None:
    events: list[str] = []
    app = object()
    server = FakeServer(events)
    thread: FakeThread | None = None
    passed_config: dict[str, Any] = {}
    output: list[str] = []

    def app_factory() -> object:
        events.append("create_app")
        return app

    def server_factory(host: str, port: int, passed_app: object, **kwargs: Any) -> FakeServer:
        events.append("make_server")
        passed_config.update(host=host, port=port, app=passed_app, **kwargs)
        return server

    def thread_factory(**kwargs: Any) -> FakeThread:
        nonlocal thread
        thread = FakeThread(**kwargs, events=events, interrupt_first_join=True)
        return thread

    def readiness_check(*, timeout: float) -> bool:
        assert timeout == launcher.STARTUP_TIMEOUT_SECONDS
        events.append("ready")
        return True

    def edge_opener(url: str) -> None:
        assert url == launcher.APP_URL
        events.append("edge")

    result = launcher.run_launcher(
        app_factory=app_factory,
        server_factory=server_factory,
        thread_factory=thread_factory,
        readiness_check=readiness_check,
        edge_opener=edge_opener,
        output=output.append,
    )

    assert result == 0
    assert passed_config == {
        "host": LOCAL_HOST,
        "port": LOCAL_PORT,
        "app": app,
        "request_handler": launcher.QuietRequestHandler,
    }
    assert launcher.LocalThreadedWSGIServer.allow_reuse_address is False
    assert launcher.LocalThreadedWSGIServer.multithread is True
    assert thread is not None and thread.name == "XmlToPdf-local-server" and thread.daemon is False
    assert events.index("thread_start") < events.index("ready") < events.index("edge")
    assert events[-4:] == ["thread_join", "shutdown", "thread_join", "server_close"]
    assert "XmlToPdf ruleaza la http://127.0.0.1:5000/" in output
    assert "Se opreste serverul XmlToPdf." in output
    assert all(line.isascii() for line in output)


def test_port_occupied_stops_before_starting_thread_or_browser() -> None:
    output: list[str] = []
    browser_calls: list[str] = []
    app_calls: list[bool] = []

    def server_factory(*_args: Any, **_kwargs: Any) -> None:
        raise OSError(errno.EADDRINUSE, "address already in use")

    result = launcher.run_launcher(
        app_factory=lambda: app_calls.append(True),
        server_factory=server_factory,
        edge_opener=browser_calls.append,
        output=output.append,
    )

    assert result == 1
    assert app_calls == [True]
    assert browser_calls == []
    assert len(output) == 1 and "5000" in output[0] and "ocupat" in output[0]
    assert output[0].isascii()


def test_exclusive_bind_conflict_has_safe_console_message() -> None:
    output: list[str] = []

    def server_factory(*_args: Any, **_kwargs: Any) -> None:
        raise launcher.PortInUseError

    result = launcher.run_launcher(server_factory=server_factory, output=output.append)

    assert result == 1
    assert output == [
        "Portul local 5000 este deja ocupat. "
        "Inchide aplicatia care il foloseste si incearca din nou."
    ]
    assert output[0].isascii()


def test_edge_failure_keeps_server_running_until_controlled_stop() -> None:
    events: list[str] = []
    server = FakeServer(events)
    output: list[str] = []
    thread: FakeThread | None = None

    def thread_factory(**kwargs: Any) -> FakeThread:
        nonlocal thread
        thread = FakeThread(**kwargs, events=events, interrupt_first_join=True)
        return thread

    def edge_failure(_url: str) -> None:
        events.append("edge_failed")
        raise launcher.EdgeUnavailableError("not included in user-facing message")

    result = launcher.run_launcher(
        app_factory=create_app,
        server_factory=lambda *_args, **_kwargs: server,
        thread_factory=thread_factory,
        readiness_check=lambda **_kwargs: events.append("ready") or True,
        edge_opener=edge_failure,
        output=output.append,
    )

    assert result == 0
    assert events.index("ready") < events.index("edge_failed") < events.index("thread_join")
    assert any("deschide manual http://127.0.0.1:5000/" in line for line in output)
    assert all("not included" not in line for line in output)
    assert "shutdown" in events and "server_close" in events


def test_server_readiness_failure_does_not_open_edge_and_closes_server() -> None:
    events: list[str] = []
    server = FakeServer(events)
    output: list[str] = []

    result = launcher.run_launcher(
        app_factory=create_app,
        server_factory=lambda *_args, **_kwargs: server,
        thread_factory=lambda **kwargs: FakeThread(**kwargs, events=events),
        readiness_check=lambda **_kwargs: False,
        edge_opener=lambda _url: pytest.fail("Edge nu trebuie pornit înainte ca serverul să fie gata."),
        output=output.append,
    )

    assert result == 1
    assert "shutdown" in events and "server_close" in events
    assert any("nu a devenit disponibil" in line for line in output)


def test_open_edge_uses_explicit_executable_and_argument_list(project_temp_dir: Path) -> None:
    edge = project_temp_dir / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    edge.parent.mkdir(parents=True)
    edge.touch()
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    launcher.open_edge(
        environ={"ProgramFiles": str(project_temp_dir)},
        popen=lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    assert calls == [(([str(edge), launcher.APP_URL],), {"close_fds": True})]


def test_open_edge_reports_missing_executable_without_using_default_browser() -> None:
    with pytest.raises(launcher.EdgeUnavailableError):
        launcher.open_edge(environ={}, popen=lambda *_a, **_k: None)


def test_open_edge_wraps_process_start_failure(project_temp_dir: Path) -> None:
    edge = project_temp_dir / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    edge.parent.mkdir(parents=True)
    edge.touch()

    def fail_to_start(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("private OS detail")

    with pytest.raises(launcher.EdgeUnavailableError) as error:
        launcher.open_edge(
            environ={"ProgramFiles": str(project_temp_dir)},
            popen=fail_to_start,
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


def test_pyinstaller_spec_bundles_package_resources_and_excludes_development_files() -> None:
    spec = Path(__file__).parents[1] / "XmlToPdf.spec"
    text = spec.read_text(encoding="utf-8")

    assert '"xmltopdf/templates"' in text
    assert '"xmltopdf/static"' in text
    assert '"pytest"' in text and '"tests"' in text
    assert "collect_dynamic_libs(\"lxml\")" in text
