import re
from pathlib import Path

import pytest
from flask.testing import FlaskClient

from xmltopdf import create_app

APP_ORIGIN = "http://127.0.0.1:5000"
APP_BASE_URL = f"{APP_ORIGIN}/"
SYNTHETIC_XML = (Path(__file__).parent / "fixtures" / "ubl_invoice_minimal.xml").read_bytes()
CSRF_PATTERN = re.compile(rb'data-csrf-token="([^"]+)"')
CSS_PATH = Path(__file__).parents[1] / "src" / "xmltopdf" / "static" / "css" / "app.css"


@pytest.fixture
def local_client() -> tuple[FlaskClient, str, bytes]:
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()
    homepage = client.get("/", base_url=APP_BASE_URL)
    match = CSRF_PATTERN.search(homepage.data)
    assert match is not None
    return client, match.group(1).decode("ascii"), homepage.data


def _upload(client: FlaskClient, csrf_token: str, xml: bytes):
    return client.post(
        "/upload",
        base_url=APP_BASE_URL,
        data=xml,
        headers={
            "Content-Type": "application/xml",
            "Origin": APP_ORIGIN,
            "X-CSRF-Token": csrf_token,
        },
    )


def test_print_control_is_rendered_only_for_an_accepted_invoice(
    local_client: tuple[FlaskClient, str, bytes],
) -> None:
    client, csrf_token, homepage = local_client

    assert b"Tip\xc4\x83re\xc8\x99te / Salveaz\xc4\x83 PDF" not in homepage
    assert b'class="print-button"' not in homepage

    response = _upload(client, csrf_token, SYNTHETIC_XML)

    assert response.status_code == 200
    invoice_html = response.get_json()["invoice_html"]
    assert 'class="print-button"' in invoice_html
    assert 'type="button"' in invoice_html
    assert 'data-action="print"' in invoice_html
    assert "Tipărește / Salvează PDF" in invoice_html


def test_print_requires_an_explicit_click_and_upload_clears_previous_invoice(
    local_client: tuple[FlaskClient, str, bytes],
) -> None:
    _client, _csrf_token, homepage = local_client
    source = homepage.decode("utf-8")
    click_start = source.index('invoiceContainer.addEventListener("click"')
    upload_start = source.index('form.addEventListener("submit"')
    click_handler = source[click_start:upload_start]
    upload_handler = source[upload_start:]

    assert "window.print()" in click_handler
    assert "window.print()" not in upload_handler
    assert upload_handler.index("invoiceContainer.replaceChildren();") < upload_handler.index("await fetch(")
    assert upload_handler.index("if (!response.ok)") < upload_handler.index("invoiceContainer.innerHTML = result.invoice_html;")


def test_invalid_upload_does_not_return_a_printable_invoice(
    local_client: tuple[FlaskClient, str, bytes],
) -> None:
    client, csrf_token, _homepage = local_client

    response = _upload(client, csrf_token, b"<Invoice>")

    assert response.status_code == 400
    assert "invoice_html" not in response.get_json()


def test_print_css_sets_a4_landscape_and_hides_web_controls() -> None:
    css = CSS_PATH.read_text(encoding="utf-8")
    print_css = css[css.index("@media print"):]

    assert re.search(r"@page\s*\{\s*size:\s*A4 landscape;\s*margin:\s*10mm;", css, re.IGNORECASE)
    assert re.search(
        r"\.app-header,\s*\.upload-panel,\s*#upload-status,\s*\.invoice-actions\s*\{\s*display:\s*none",
        print_css,
        re.DOTALL,
    )
    assert re.search(r"background:\s*#fff\s*!important;", print_css)
    assert "box-shadow: none;" in print_css


def test_print_css_uses_white_background_and_readable_type() -> None:
    css = CSS_PATH.read_text(encoding="utf-8")
    print_css = css[css.index("@media print"):]

    assert re.search(r":root,\s*html,\s*body\s*\{[^}]*background:\s*#fff\s*!important", print_css)
    assert "background-color: #fff !important;" in print_css
    assert "font-size: 9pt;" in print_css
    assert "font-size: 8.5pt;" in print_css
    assert "print-color-adjust: economy;" in print_css
    assert not re.search(r"break-inside:\s*avoid|page-break-inside:\s*avoid", print_css)


def test_print_table_fits_and_can_continue_across_pages() -> None:
    css = CSS_PATH.read_text(encoding="utf-8")
    print_css = css[css.index("@media print"):]

    assert re.search(r"\.table-scroll\s*\{[^}]*overflow:\s*visible", print_css, re.DOTALL)
    assert re.search(r"\.invoice-lines\s*\{[^}]*width:\s*100%;[^}]*min-width:\s*0", print_css, re.DOTALL)
    assert re.search(r"\.invoice-lines thead\s*\{\s*display:\s*table-header-group", print_css)
    assert re.search(r"\.invoice-lines\s*\{[^}]*break-inside:\s*auto", print_css, re.DOTALL)
    assert re.search(r"\.invoice-lines tr\s*\{[^}]*break-inside:\s*auto", print_css, re.DOTALL)
    assert not re.search(r"\.invoice-lines[^{}]*\{[^}]*display:\s*none", print_css, re.DOTALL)
    assert "overflow: hidden" not in print_css
    assert "max-height:" not in print_css
    assert "page-break-inside: avoid" not in print_css[:print_css.index(".grand-total")]
