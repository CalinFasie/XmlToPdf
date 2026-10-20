import re
from pathlib import Path

import pytest
from flask.testing import FlaskClient

from xmltopdf import create_app

APP_ORIGIN = "http://127.0.0.1:5000"
APP_BASE_URL = f"{APP_ORIGIN}/"
MINIMAL_XML = (Path(__file__).parent / "fixtures" / "ubl_invoice_minimal.xml").read_bytes()
CSRF_PATTERN = re.compile(rb'data-csrf-token="([^"]+)"')
LINE_PATTERN = re.compile(rb"  <cac:InvoiceLine>.*?  </cac:InvoiceLine>\r?\n", re.DOTALL)


@pytest.fixture
def local_client() -> tuple[FlaskClient, str]:
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()
    homepage = client.get("/", base_url=APP_BASE_URL)
    match = CSRF_PATTERN.search(homepage.data)
    assert match is not None
    return client, match.group(1).decode("ascii")


def _invoice_with_lines(count: int, invoice_id: str = "SYN-INV-001") -> bytes:
    match = LINE_PATTERN.search(MINIMAL_XML)
    assert match is not None
    line_template = match.group()
    lines = []
    for index in range(1, count + 1):
        line = line_template.replace(b"<cbc:ID>1</cbc:ID>", f"<cbc:ID>{index}</cbc:ID>".encode(), 1)
        line = line.replace(
            b"<cbc:Name>Produs Sintetic</cbc:Name>",
            f"<cbc:Name>Articol {index:03}</cbc:Name>".encode(),
            1,
        )
        lines.append(line)
    xml = MINIMAL_XML[: match.start()] + MINIMAL_XML[match.end() :]
    xml = xml.replace(b"</Invoice>", b"".join(lines) + b"</Invoice>")
    return xml.replace(b"SYN-INV-001", invoice_id.encode(), 1)


def _append_invoice_children(xml: bytes, children: bytes) -> bytes:
    return xml.replace(b"</Invoice>", children + b"</Invoice>")


def _render(client: FlaskClient, csrf_token: str, xml: bytes):
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


def test_invoice_rendering_shows_header_parties_and_distinct_identifiers(
    local_client: tuple[FlaskClient, str],
) -> None:
    client, csrf_token = local_client
    xml = MINIMAL_XML.replace(
        b"<cbc:ID>SYN-INV-001</cbc:ID>",
        b'<cbc:ID schemeID="INV">SYN-INV-001</cbc:ID>',
        1,
    )
    response = _render(client, csrf_token, xml)

    assert response.status_code == 200
    payload = response.get_json()
    html = payload["invoice_html"]
    assert payload["ok"] is True
    assert "SYN-INV-001" in html
    assert "schemeID: INV" in html
    assert "2026-01-15" in html
    assert "RON" in html
    assert "Furnizor Sintetic SRL" in html
    assert "Client Sintetic SA" in html
    assert "RO-SYN-001" in html
    assert "RO-SYN-002" in html
    assert "Identificare comercială" in html
    assert "Identificator fiscal" in html
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("line_count", [1, 2, 10, 30, 100])
def test_all_invoice_lines_are_rendered_in_xml_order(
    local_client: tuple[FlaskClient, str], line_count: int
) -> None:
    client, csrf_token = local_client
    response = _render(client, csrf_token, _invoice_with_lines(line_count))

    assert response.status_code == 200
    html = response.get_json()["invoice_html"]
    positions = [html.index(f"Articol {index:03}") for index in range(1, line_count + 1)]
    assert positions == sorted(positions)
    assert html.count("<tbody>") == 1
    assert html.count("<tr>") == line_count + 1


def test_line_tax_category_is_displayed_once_in_the_tax_column(
    local_client: tuple[FlaskClient, str],
) -> None:
    client, csrf_token = local_client
    html = _render(client, csrf_token, _invoice_with_lines(1)).get_json()["invoice_html"]

    assert html.count("Categorie TVA linie") == 1
    assert html.count("Procent TVA") == 1
    assert "Schemă fiscală — ID" in html


def test_absent_optional_sections_are_omitted_without_placeholder_values(
    local_client: tuple[FlaskClient, str],
) -> None:
    client, csrf_token = local_client
    html = _render(client, csrf_token, MINIMAL_XML).get_json()["invoice_html"]

    assert "Scadență" not in html
    assert "TVA la nivel de document" not in html
    assert "Totaluri" not in html
    assert "Mijloc de plată" not in html
    assert "Livrare" not in html
    assert "N/A" not in html


def test_repeated_tax_subtotals_totals_payment_means_and_delivery_are_rendered(
    local_client: tuple[FlaskClient, str],
) -> None:
    client, csrf_token = local_client
    extra = """<cac:TaxTotal>
  <cbc:TaxAmount currencyID="RON">8.5000</cbc:TaxAmount>
  <cac:TaxSubtotal>
    <cbc:TaxableAmount currencyID="RON">25.0000</cbc:TaxableAmount>
    <cbc:TaxAmount currencyID="RON">4.7500</cbc:TaxAmount>
    <cbc:TransactionCurrencyTaxAmount currencyID="EUR">1.2500</cbc:TransactionCurrencyTaxAmount>
    <cbc:Percent>19.00</cbc:Percent>
    <cbc:BaseUnitMeasure unitCode="C62">2.000</cbc:BaseUnitMeasure>
    <cbc:PerUnitAmount currencyID="RON">0.5000</cbc:PerUnitAmount>
    <cbc:TierRange>treapta sintetică</cbc:TierRange>
    <cbc:TierRatePercent>2.50</cbc:TierRatePercent>
    <cac:TaxCategory>
      <cbc:ID>S</cbc:ID><cbc:Name>Standard</cbc:Name><cbc:Percent>19</cbc:Percent>
      <cac:TaxScheme><cbc:ID>VAT</cbc:ID><cbc:Name>TVA sintetic</cbc:Name><cbc:TaxTypeCode>VAT</cbc:TaxTypeCode></cac:TaxScheme>
    </cac:TaxCategory>
  </cac:TaxSubtotal>
  <cac:TaxSubtotal>
    <cbc:TaxableAmount currencyID="RON">10.0000</cbc:TaxableAmount>
    <cbc:TaxAmount currencyID="RON">0.0000</cbc:TaxAmount>
    <cac:TaxCategory><cbc:ID>E</cbc:ID><cbc:TaxExemptionReason>Scutire sintetică</cbc:TaxExemptionReason></cac:TaxCategory>
  </cac:TaxSubtotal>
</cac:TaxTotal>
<cac:LegalMonetaryTotal>
  <cbc:LineExtensionAmount currencyID="RON">10.00</cbc:LineExtensionAmount>
  <cbc:TaxExclusiveAmount currencyID="RON">11.00</cbc:TaxExclusiveAmount>
  <cbc:TaxInclusiveAmount currencyID="RON">12.00</cbc:TaxInclusiveAmount>
  <cbc:AllowanceTotalAmount currencyID="RON">1.00</cbc:AllowanceTotalAmount>
  <cbc:ChargeTotalAmount currencyID="RON">2.00</cbc:ChargeTotalAmount>
  <cbc:PrepaidAmount currencyID="RON">3.00</cbc:PrepaidAmount>
  <cbc:PayableRoundingAmount currencyID="RON">0.01</cbc:PayableRoundingAmount>
  <cbc:PayableAmount currencyID="RON">12.00</cbc:PayableAmount>
</cac:LegalMonetaryTotal>
<cac:PaymentMeans>
  <cbc:PaymentMeansCode>30</cbc:PaymentMeansCode><cbc:PaymentDueDate>2026-02-01</cbc:PaymentDueDate>
  <cbc:PaymentChannelCode>IBAN</cbc:PaymentChannelCode><cbc:InstructionID>INSTR-SYN</cbc:InstructionID>
  <cbc:InstructionNote>Plată sintetică</cbc:InstructionNote><cbc:PaymentID>REF-SYN-1</cbc:PaymentID>
  <cac:PayeeFinancialAccount>
    <cbc:ID>RO00SYNTHETIC0000000001</cbc:ID><cbc:Name>Cont sintetic</cbc:Name>
    <cbc:AccountTypeCode>IBAN</cbc:AccountTypeCode><cbc:CurrencyCode>RON</cbc:CurrencyCode>
    <cac:FinancialInstitutionBranch>
      <cbc:ID>BR-SYN</cbc:ID><cbc:Name>Sucursală sintetică</cbc:Name>
      <cac:FinancialInstitution><cbc:ID>BANK-SYN</cbc:ID></cac:FinancialInstitution>
    </cac:FinancialInstitutionBranch>
  </cac:PayeeFinancialAccount>
</cac:PaymentMeans>
<cac:PaymentMeans><cbc:PaymentMeansCode>42</cbc:PaymentMeansCode><cbc:PaymentID>REF-SYN-2</cbc:PaymentID></cac:PaymentMeans>
<cac:Delivery>
  <cbc:ActualDeliveryDate>2026-01-20</cbc:ActualDeliveryDate><cbc:ActualDeliveryTime>09:30:00</cbc:ActualDeliveryTime>
  <cac:DeliveryParty><cac:PartyName><cbc:Name>Destinatar sintetic</cbc:Name></cac:PartyName></cac:DeliveryParty>
  <cac:DeliveryLocation><cbc:ID>LOC-SYN</cbc:ID><cbc:Description>Depozit sintetic</cbc:Description>
    <cac:Address><cbc:CityName>Brașov</cbc:CityName><cac:Country><cbc:IdentificationCode>RO</cbc:IdentificationCode></cac:Country></cac:Address>
  </cac:DeliveryLocation>
</cac:Delivery>
""".encode("utf-8")
    xml = _append_invoice_children(_invoice_with_lines(1), extra)
    html = _render(client, csrf_token, xml).get_json()["invoice_html"]

    assert "Total TVA 1" in html
    assert "Subtotal TVA 1" in html
    assert "Subtotal TVA 2" in html
    assert "8.5000" in html
    assert "25.0000" in html
    assert "TVA în moneda tranzacției" in html
    assert "Interval de tier" in html
    assert "12.00" in html
    assert "De plată" in html
    assert html.count("Mijloc de plată ") == 2
    assert "RO00SYNTHETIC0000000001" in html
    assert "BANK-SYN" in html
    assert "REF-SYN-1" in html and "REF-SYN-2" in html
    assert "Destinatar sintetic" in html
    assert "Depozit sintetic" in html
    assert "Brașov" in html


def test_decimal_text_diacritics_and_long_descriptions_are_preserved_and_escaped(
    local_client: tuple[FlaskClient, str],
) -> None:
    client, csrf_token = local_client
    long_description = "Descriere lungă cu diacritice: ăîșțâ — " + ("detaliu sintetic " * 250)
    xml = _invoice_with_lines(1)
    xml = xml.replace(
        b"<cbc:Name>Articol 001</cbc:Name>",
        b"<cbc:Name>&lt;script&gt;alert('synthetic')&lt;/script&gt; &amp; "
        + long_description.encode()
        + b"</cbc:Name>",
    )
    xml = xml.replace(b">10.00</cbc:LineExtensionAmount>", b"> 0010.2300 </cbc:LineExtensionAmount>")
    html = _render(client, csrf_token, xml).get_json()["invoice_html"]

    assert "0010.2300" in html
    assert "Descriere lungă cu diacritice: ăîșțâ" in html
    assert "detaliu sintetic" in html
    assert "&lt;script&gt;alert(&#39;synthetic&#39;)&lt;/script&gt;" in html
    assert "<script>alert('synthetic')</script>" not in html


def test_new_upload_replaces_old_invoice_and_old_content_is_not_kept_in_session(
    local_client: tuple[FlaskClient, str],
) -> None:
    client, csrf_token = local_client
    first = _render(client, csrf_token, _invoice_with_lines(1, "SYN-OLD-INVOICE"))
    second = _render(client, csrf_token, _invoice_with_lines(1, "SYN-NEW-INVOICE"))
    homepage = client.get("/", base_url=APP_BASE_URL)

    assert "SYN-OLD-INVOICE" in first.get_json()["invoice_html"]
    assert "SYN-NEW-INVOICE" in second.get_json()["invoice_html"]
    assert "SYN-OLD-INVOICE" not in second.get_json()["invoice_html"]
    assert b"invoiceContainer.replaceChildren();" in homepage.data
    assert b"fileInput.value = \"\";" in homepage.data
    with client.session_transaction(base_url=APP_BASE_URL) as session:
        assert "csrf_token" in session
        assert not any("invoice" in key for key in session)


def test_local_stylesheet_is_available_without_external_resources(
    local_client: tuple[FlaskClient, str],
) -> None:
    client, _csrf_token = local_client
    homepage = client.get("/", base_url=APP_BASE_URL)
    stylesheet = client.get("/static/css/app.css", base_url=APP_BASE_URL)

    assert b"https://" not in homepage.data and b"http://" not in homepage.data
    assert stylesheet.status_code == 200
    assert stylesheet.mimetype == "text/css"
    assert b"@import" not in stylesheet.data
    assert b"url(http" not in stylesheet.data.lower()
