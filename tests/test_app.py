import logging
import re
from pathlib import Path

import pytest
from flask.testing import FlaskClient
from werkzeug import formparser

from xmltopdf import create_app, ubl

APP_ORIGIN = "http://127.0.0.1:5000"
APP_BASE_URL = f"{APP_ORIGIN}/"
SYNTHETIC_XML = (Path(__file__).parent / "fixtures" / "ubl_invoice_minimal.xml").read_bytes()
CSRF_PATTERN = re.compile(rb'data-csrf-token="([^"]+)"')


@pytest.fixture
def local_client() -> tuple[FlaskClient, str]:
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()
    response = client.get("/", base_url=APP_BASE_URL)
    match = CSRF_PATTERN.search(response.data)
    assert match is not None
    return client, match.group(1).decode("ascii")


def post_xml(
    client: FlaskClient,
    csrf_token: str | None,
    body: bytes,
    *,
    origin: str | None = APP_ORIGIN,
    host: str | None = None,
    content_type: str = "application/xml",
    environ_overrides: dict[str, object] | None = None,
):
    headers = {"Content-Type": content_type}
    if origin is not None:
        headers["Origin"] = origin
    if csrf_token is not None:
        headers["X-CSRF-Token"] = csrf_token
    if host is not None:
        headers["Host"] = host
    return client.post(
        "/upload",
        base_url=APP_BASE_URL,
        data=body,
        headers=headers,
        environ_overrides=environ_overrides,
    )


def test_homepage_offers_raw_xml_upload_and_no_store(local_client: tuple[FlaskClient, str]) -> None:
    client, _csrf_token = local_client
    response = client.get("/", base_url=APP_BASE_URL)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b"<title>XmlToPdf</title>" in response.data
    assert "Fundația aplicației web locale este pornită.".encode() in response.data
    assert b'type="file"' in response.data
    assert b"required" in response.data
    assert b"body: file" in response.data
    assert b"FormData" not in response.data
    assert response.headers["Cache-Control"] == "no-store"


def test_session_cookie_uses_http_only_and_strict_same_site() -> None:
    app = create_app()
    response = app.test_client().get("/", base_url=APP_BASE_URL)

    cookie_header = response.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie_header
    assert "SameSite=Strict" in cookie_header


def test_valid_synthetic_xml_is_passed_to_existing_parser_and_returns_generic_message(
    local_client: tuple[FlaskClient, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, csrf_token = local_client
    parsed_inputs: list[bytes] = []
    original_parser = ubl.parse_invoice

    def capture_parser_input(xml_content: bytes):
        parsed_inputs.append(xml_content)
        return original_parser(xml_content)

    monkeypatch.setattr(ubl, "parse_invoice", capture_parser_input)
    response = post_xml(client, csrf_token, SYNTHETIC_XML)

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "message": "Documentul XML a fost acceptat."}
    assert parsed_inputs == [SYNTHETIC_XML]
    assert b"SYN-INV-001" not in response.data
    assert response.headers["Cache-Control"] == "no-store"


def test_malformed_xml_returns_safe_message_and_does_not_log_content(
    local_client: tuple[FlaskClient, str], caplog: pytest.LogCaptureFixture
) -> None:
    client, csrf_token = local_client
    marker = b"PRIVATE-SYNTHETIC-MARKER"
    malformed_xml = b"<Invoice>" + marker + b"<broken></Invoice>"

    with caplog.at_level(logging.DEBUG):
        response = post_xml(client, csrf_token, malformed_xml)

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "message": "Documentul XML nu este bine format."}
    assert marker not in response.data
    assert marker.decode() not in caplog.text
    assert response.headers["Cache-Control"] == "no-store"


def test_unsupported_ubl_document_returns_clear_message(local_client: tuple[FlaskClient, str]) -> None:
    client, csrf_token = local_client
    credit_note_xml = SYNTHETIC_XML.replace(b"<Invoice ", b"<CreditNote ", 1).replace(
        b"</Invoice>", b"</CreditNote>"
    )

    response = post_xml(client, csrf_token, credit_note_xml)

    assert response.status_code == 422
    assert response.get_json() == {"ok": False, "message": "Tipul documentului XML nu este suportat."}


def test_empty_file_body_is_rejected(local_client: tuple[FlaskClient, str]) -> None:
    client, csrf_token = local_client

    response = post_xml(client, csrf_token, b"", environ_overrides={"CONTENT_LENGTH": "0"})

    assert response.status_code == 400
    assert response.get_json()["message"] == "Fișierul XML este gol sau lipsește."


def test_missing_file_body_with_unknown_length_is_rejected(local_client: tuple[FlaskClient, str]) -> None:
    client, csrf_token = local_client

    response = post_xml(
        client,
        csrf_token,
        b"",
        environ_overrides={"CONTENT_LENGTH": None, "wsgi.input_terminated": True},
    )

    assert response.status_code == 400
    assert response.get_json()["message"] == "Fișierul XML este gol sau lipsește."


def test_body_without_content_length_is_read_when_wsgi_marks_stream_terminated(
    local_client: tuple[FlaskClient, str],
) -> None:
    client, csrf_token = local_client

    response = post_xml(
        client,
        csrf_token,
        SYNTHETIC_XML,
        environ_overrides={"CONTENT_LENGTH": None, "wsgi.input_terminated": True},
    )

    assert response.status_code == 200
    assert response.get_json()["message"] == "Documentul XML a fost acceptat."


def test_body_at_exactly_10_mib_is_allowed(local_client: tuple[FlaskClient, str]) -> None:
    client, csrf_token = local_client
    xml_at_limit = SYNTHETIC_XML + b" " * (ubl.MAX_XML_BYTES - len(SYNTHETIC_XML))

    response = post_xml(client, csrf_token, xml_at_limit)

    assert response.status_code == 200
    assert response.get_json()["message"] == "Documentul XML a fost acceptat."


def test_body_without_length_and_without_termination_signal_is_rejected(
    local_client: tuple[FlaskClient, str],
) -> None:
    client, csrf_token = local_client

    response = post_xml(
        client,
        csrf_token,
        SYNTHETIC_XML,
        environ_overrides={"CONTENT_LENGTH": None},
    )

    assert response.status_code == 411
    assert response.get_json()["message"] == "Lungimea corpului XML nu poate fi verificată în siguranță."


def test_oversized_body_is_rejected_before_parser_even_with_short_content_length(
    local_client: tuple[FlaskClient, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, csrf_token = local_client
    oversized = SYNTHETIC_XML + b" " * ubl.MAX_XML_BYTES

    def parser_must_not_run(_xml_content: bytes):
        raise AssertionError("Parserul nu trebuie apelat pentru un corp prea mare.")

    monkeypatch.setattr(ubl, "parse_invoice", parser_must_not_run)
    response = post_xml(
        client,
        csrf_token,
        oversized,
        environ_overrides={"CONTENT_LENGTH": "1", "wsgi.input_terminated": True},
    )

    assert response.status_code == 413
    assert response.get_json()["message"] == "XML-ul depășește limita de 10 MiB."


def test_inaccurately_large_content_length_is_rejected_before_parser(
    local_client: tuple[FlaskClient, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, csrf_token = local_client

    def parser_must_not_run(_xml_content: bytes):
        raise AssertionError("Parserul nu trebuie apelat pentru o lungime declarată prea mare.")

    monkeypatch.setattr(ubl, "parse_invoice", parser_must_not_run)
    response = post_xml(
        client,
        csrf_token,
        SYNTHETIC_XML,
        environ_overrides={"CONTENT_LENGTH": str(ubl.MAX_XML_BYTES + 1)},
    )

    assert response.status_code == 413
    assert response.get_json()["message"] == "XML-ul depășește limita de 10 MiB."


def test_disallowed_host_is_rejected_before_parser(
    local_client: tuple[FlaskClient, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, csrf_token = local_client

    def parser_must_not_run(_xml_content: bytes):
        raise AssertionError("Parserul nu trebuie apelat pentru Host nepermis.")

    monkeypatch.setattr(ubl, "parse_invoice", parser_must_not_run)
    response = post_xml(client, csrf_token, SYNTHETIC_XML, host="attacker.example")

    assert response.status_code == 400
    assert response.get_json()["message"] == "Cererea trebuie trimisă către adresa locală permisă."


def test_disallowed_origin_is_rejected_before_parser(
    local_client: tuple[FlaskClient, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, csrf_token = local_client

    def parser_must_not_run(_xml_content: bytes):
        raise AssertionError("Parserul nu trebuie apelat pentru Origin nepermis.")

    monkeypatch.setattr(ubl, "parse_invoice", parser_must_not_run)
    response = post_xml(client, csrf_token, SYNTHETIC_XML, origin="http://attacker.example")

    assert response.status_code == 403
    assert response.get_json()["message"] == "Originea cererii nu este permisă."


@pytest.mark.parametrize("csrf_token", [None, "token-invalid"])
def test_missing_or_invalid_csrf_token_is_rejected(
    local_client: tuple[FlaskClient, str], csrf_token: str | None
) -> None:
    client, _valid_token = local_client

    response = post_xml(client, csrf_token, SYNTHETIC_XML)

    assert response.status_code == 403
    assert response.get_json()["message"] == "Cererea nu are un token CSRF valid."


def test_raw_upload_does_not_use_multipart_spooling_or_write_temporary_files(
    local_client: tuple[FlaskClient, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, csrf_token = local_client
    spooling_calls: list[bool] = []

    def fail_if_spooled(*_args, **_kwargs):
        spooling_calls.append(True)
        raise AssertionError("Upload-ul XML nu trebuie să creeze un fișier temporar.")

    monkeypatch.setattr(formparser, "SpooledTemporaryFile", fail_if_spooled)
    response = post_xml(client, csrf_token, SYNTHETIC_XML)

    assert response.status_code == 200
    assert spooling_calls == []


def test_upload_requires_xml_content_type(local_client: tuple[FlaskClient, str]) -> None:
    client, csrf_token = local_client

    response = post_xml(client, csrf_token, SYNTHETIC_XML, content_type="multipart/form-data")

    assert response.status_code == 415
    assert response.get_json()["message"] == "Trimite conținut XML pentru procesare."
