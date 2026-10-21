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


def _screen_markup(html: str) -> str:
    screen, marker, _print = html.partition('<div class="invoice-print">')
    assert marker
    return screen


def _print_markup(html: str) -> str:
    _screen, marker, printed = html.partition('<div class="invoice-print">')
    assert marker
    return printed


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
    print_html = _print_markup(html)
    assert payload["ok"] is True
    assert "SYN-INV-001" in html
    assert "schemeID=INV" in html
    assert "2026-01-15" in html
    assert "RON" in html
    assert "Furnizor Sintetic SRL" in html
    assert "Client Sintetic SA" in html
    assert "RO-SYN-001" in html
    assert "RO-SYN-002" in html
    assert "Identificare comercială" in html
    assert "ID fiscal" in html
    assert "Furnizor" in print_html
    assert "Client" in print_html
    assert print_html.count("RO-SYN-001") == 1
    assert print_html.count("RO-SYN-002") == 1
    assert response.headers["Cache-Control"] == "no-store"


def test_screen_layout_has_three_compact_header_zones_and_separate_print_css(
    local_client: tuple[FlaskClient, str],
) -> None:
    client, csrf_token = local_client
    xml = _append_invoice_children(
        MINIMAL_XML,
        b'<cac:LegalMonetaryTotal><cbc:PayableAmount currencyID="RON">0012.3400</cbc:PayableAmount>'
        b"</cac:LegalMonetaryTotal>",
    )
    response = _render(client, csrf_token, xml)
    html = response.get_json()["invoice_html"]
    screen_html = _screen_markup(html)
    css = (Path(__file__).parents[1] / "src" / "xmltopdf" / "static" / "css" / "app.css").read_text(
        encoding="utf-8"
    )
    print_css = css[css.index("@media print"):]

    header_start = screen_html.index('<header class="screen-header">')
    supplier = screen_html.index('<section class="screen-party">', header_start)
    document = screen_html.index('<section class="screen-document"', supplier)
    customer = screen_html.index('<section class="screen-party">', document)
    assert supplier < document < customer
    assert 'class="screen-total-band"' in screen_html
    assert "0012.3400" in screen_html
    assert 'class="invoice-lines screen-lines"' in screen_html
    assert ".screen-header" in css[:css.index("@page")]
    assert ".screen-total-band" in css[:css.index("@page")]
    assert "grid-template-columns: minmax(0, 1fr);" in css[css.index(".screen-header {"):css.index("@page")]
    assert "grid-template-columns: minmax(0, 1fr);" in css[css.index(".screen-bottom-grid {"):css.index("@page")]
    assert "overflow-x: auto;" in css[css.index(".invoice-screen .table-scroll"):css.index("@page")]
    assert ".screen-header" not in print_css
    assert ".screen-total-band" not in print_css


def test_screen_label_value_styles_keep_pairs_inline_and_values_wrappable() -> None:
    css = (Path(__file__).parents[1] / "src" / "xmltopdf" / "static" / "css" / "app.css").read_text(
        encoding="utf-8"
    )
    screen_css = css[: css.index("@page")]
    pair_rule = re.search(r"\.screen-pair\s*\{([^}]*)\}", screen_css)
    label_rule = re.search(r"\.screen-pair dt\s*\{([^}]*)\}", screen_css)
    value_rule = re.search(r"\.screen-pair dd\s*\{([^}]*)\}", screen_css)
    total_rule = re.search(r"\.screen-total\s*\{([^}]*)\}", screen_css)
    detail_rule = re.search(r"\.screen-detail\s*\{([^}]*)\}", screen_css)

    assert pair_rule is not None and "display: flex;" in pair_rule.group(1)
    assert "grid-template-columns" not in pair_rule.group(1)
    assert label_rule is not None and "max-width: 45%;" in label_rule.group(1)
    assert value_rule is not None and "flex: 1 1 0;" in value_rule.group(1)
    assert "min-width: 0;" in value_rule.group(1)
    assert "overflow-wrap: anywhere;" in value_rule.group(1)
    assert total_rule is not None and "flex-direction: row;" in total_rule.group(1)
    assert "flex-wrap: wrap;" in total_rule.group(1)
    assert detail_rule is not None and "display: inline-block;" in detail_rule.group(1)


@pytest.mark.parametrize("line_count", [1, 2, 10, 30, 100])
def test_all_invoice_lines_are_rendered_in_xml_order(
    local_client: tuple[FlaskClient, str], line_count: int
) -> None:
    client, csrf_token = local_client
    response = _render(client, csrf_token, _invoice_with_lines(line_count))

    assert response.status_code == 200
    html = _screen_markup(response.get_json()["invoice_html"])
    positions = [html.index(f"Articol {index:03}") for index in range(1, line_count + 1)]
    assert positions == sorted(positions)
    assert html.count("<tbody>") == 1
    assert html.count("<tr>") == line_count + 1


def test_line_tax_category_is_displayed_once_in_the_tax_column(
    local_client: tuple[FlaskClient, str],
) -> None:
    client, csrf_token = local_client
    xml = _invoice_with_lines(1)
    xml = re.sub(
        rb"<cac:ClassifiedTaxCategory>.*?</cac:ClassifiedTaxCategory>",
        b'<cac:ClassifiedTaxCategory>\n'
        b'  <cbc:ID schemeID="SYN-CAT">S</cbc:ID>\n'
        b"  <cbc:Name>Categorie sintetica</cbc:Name>\n"
        b'  <cbc:Percent unitCode="SYN-PERCENT">19</cbc:Percent>\n'
        b'  <cbc:TaxExemptionReasonCode listID="LIST-ATTR-SYN">SYN-REASON-CODE</cbc:TaxExemptionReasonCode>\n'
        b"  <cbc:TaxExemptionReason>Motiv sintetic</cbc:TaxExemptionReason>\n"
        b'  <cac:TaxScheme><cbc:ID schemeID="SYN-SCHEME">VAT-SYN</cbc:ID>'
        b"<cbc:Name>Schema fiscala sintetica</cbc:Name>"
        b'<cbc:TaxTypeCode schemeID="SYN-TYPE">VAT-TYPE-SYN</cbc:TaxTypeCode></cac:TaxScheme>\n'
        b"</cac:ClassifiedTaxCategory>",
        xml,
        count=1,
        flags=re.DOTALL,
    )
    html = _render(client, csrf_token, xml).get_json()["invoice_html"]
    screen_html = _screen_markup(html)
    print_html = _print_markup(html)

    assert screen_html.count('aria-label="Categorie TVA linie"') == 1
    assert print_html.count('class="print-tax-category"') == 1
    for value in (
        "SYN-CAT",
        "Categorie sintetica",
        "19",
        "SYN-PERCENT",
        "SYN-REASON-CODE",
        "Motiv sintetic",
        "LIST-ATTR-SYN",
        "VAT-SYN",
        "SYN-SCHEME",
        "Schema fiscala sintetica",
        "VAT-TYPE-SYN",
        "SYN-TYPE",
    ):
        assert screen_html.count(value) == 1
        assert print_html.count(value) == 1
    assert "screen-tax-category" in screen_html
    assert "Cod categorie" not in screen_html


def test_screen_line_keeps_item_codes_and_line_tax_data_without_repeating_same_category(
    local_client: tuple[FlaskClient, str],
) -> None:
    client, csrf_token = local_client
    xml = _invoice_with_lines(1)
    line_tax = b"""<cac:TaxTotal>
      <cbc:TaxAmount currencyID="RON">1.9000</cbc:TaxAmount>
      <cbc:RoundingAmount currencyID="RON">0.0000</cbc:RoundingAmount>
      <cac:TaxSubtotal>
        <cbc:TaxableAmount currencyID="RON">10.0000</cbc:TaxableAmount>
        <cbc:TaxAmount currencyID="RON">1.9000</cbc:TaxAmount>
        <cbc:CalculationSequenceNumeric>1</cbc:CalculationSequenceNumeric>
        <cbc:TransactionCurrencyTaxAmount currencyID="EUR">0.9500</cbc:TransactionCurrencyTaxAmount>
        <cbc:Percent>19.00</cbc:Percent>
        <cbc:BaseUnitMeasure unitCode="C62">2.000</cbc:BaseUnitMeasure>
        <cbc:PerUnitAmount currencyID="RON">0.1000</cbc:PerUnitAmount>
        <cbc:TierRange>SYN-TIER-RANGE</cbc:TierRange>
        <cbc:TierRatePercent>2.00</cbc:TierRatePercent>
        <cac:TaxCategory><cbc:ID>S</cbc:ID><cbc:Percent>19</cbc:Percent>
          <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
        </cac:TaxCategory>
      </cac:TaxSubtotal>
    </cac:TaxTotal>"""
    xml = xml.replace(b"    <cac:Item>", line_tax + b"\n    <cac:Item>", 1)
    xml = xml.replace(
        b"<cbc:Name>Articol 001</cbc:Name>",
        b"<cbc:Name>Articol 001</cbc:Name>"
        b'<cac:SellersItemIdentification><cbc:ID schemeID="SUP">SUP-CODE-01</cbc:ID></cac:SellersItemIdentification>'
        b'<cac:StandardItemIdentification><cbc:ID schemeID="STD">STD-CODE-01</cbc:ID></cac:StandardItemIdentification>',
        1,
    )
    html = _screen_markup(_render(client, csrf_token, xml).get_json()["invoice_html"])

    for value in (
        "SUP-CODE-01",
        "STD-CODE-01",
        "schemeID=SUP",
        "schemeID=STD",
        "1.9000",
        "0.0000",
        "10.0000",
        "0.9500",
        "19.00",
        "2.000",
        "C62",
        "0.1000",
        "SYN-TIER-RANGE",
        "2.00",
    ):
        assert value in html
    assert html.count('aria-label="Categorie TVA linie"') == 1


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
    xml = _append_invoice_children(_invoice_with_lines(2), extra)
    rendered = _render(client, csrf_token, xml).get_json()["invoice_html"]
    html = _screen_markup(rendered)
    print_html = _print_markup(rendered)

    assert "Total TVA 1" in html
    assert "Subtotal 1" in html
    assert "Subtotal 2" in html
    assert "8.5000" in html
    assert "25.0000" in html
    assert "TVA în moneda tranzacției" in html
    assert "Interval de tier" in html
    assert "12.00" in html
    assert re.search(
        r'class="screen-value">\s*8\.5000\s*</span>\s*<span class="screen-unit">RON</span>', html
    )
    assert "De plată" in html
    assert html.count("Mijloc de plată ") == 2
    assert "RO00SYNTHETIC0000000001" in html
    assert "BANK-SYN" in html
    assert "REF-SYN-1" in html and "REF-SYN-2" in html
    assert html.count('class="screen-record screen-payment"') == 2
    assert 'class="screen-total-band"' in html
    assert 'class="screen-total screen-payable"' in html
    assert 'class="screen-tax-table"' in html
    assert 'class="screen-bottom-grid"' in html
    assert "Destinatar sintetic" in html
    assert "Depozit sintetic" in html
    assert "Brașov" in html
    for label in (
        "Număr",
        "Denumire",
        "ID fiscal",
        "Telefon",
        "Stradă",
        "Localitate",
        "Cod mijloc de plată",
        "IBAN / ID cont",
        "Data livrării",
        "Descriere locație",
    ):
        assert re.search(
            rf'<div class="screen-pair"><dt>{re.escape(label)}</dt><dd>.*?</dd></div>',
            html,
            re.DOTALL,
        )
    assert re.search(
        r'<span class="screen-total-label">De plată</span>\s*'
        r'<span class="screen-total-value">.*?</span>',
        html,
        re.DOTALL,
    )
    assert re.search(
        r'<span class="screen-detail"><strong>Interval de tier:</strong>\s*'
        r'<span class="screen-value">.*?</span>',
        html,
        re.DOTALL,
    )
    for value in (
        "Articol 001",
        "Articol 002",
        "8.5000",
        "25.0000",
        "4.7500",
        "1.2500",
        "TVA în moneda tranzacției",
        "19.00",
        "2.000",
        "C62",
        "0.5000",
        "treapta sintetică",
        "2.50",
        "Standard",
        "TVA sintetic",
        "12.00",
        "10.00",
        "11.00",
        "1.00",
        "2.00",
        "3.00",
        "0.01",
        "0.0000",
        "Scutire sintetică",
        "INSTR-SYN",
        "Plată sintetică",
        "IBAN",
        "Cont sintetic",
        "Sucursală sintetică",
        "BR-SYN",
        "RO00SYNTHETIC0000000001",
        "BANK-SYN",
        "REF-SYN-1",
        "REF-SYN-2",
        "2026-02-01",
        "2026-01-20",
        "09:30:00",
        "Destinatar sintetic",
        "LOC-SYN",
        "Depozit sintetic",
        "Brașov",
        "RO",
    ):
        assert value in html

    for value in (
        "Articol 001",
        "Articol 002",
        "8.5000",
        "25.0000",
        "4.7500",
        "1.2500",
        "TVA moneda tranzacției",
        "2.000",
        "C62",
        "0.5000",
        "treapta sintetică",
        "2.50",
        "0.0000",
        "Standard",
        "Scutire sintetică",
        "TVA sintetic",
        "10.00",
        "11.00",
        "12.00",
        "1.00",
        "2.00",
        "3.00",
        "0.01",
        "REF-SYN-1",
        "REF-SYN-2",
        "INSTR-SYN",
        "Plată sintetică",
        "IBAN",
        "Cont sintetic",
        "Sucursală sintetică",
        "BR-SYN",
        "RO00SYNTHETIC0000000001",
        "BANK-SYN",
        "2026-02-01",
        "2026-01-20",
        "09:30:00",
        "Destinatar sintetic",
        "LOC-SYN",
        "Depozit sintetic",
        "Brașov",
        "RO",
    ):
        assert value in print_html
    assert print_html.count("Articol 001") == 1
    assert print_html.count("Articol 002") == 1
    assert print_html.count("REF-SYN-1") == 1
    assert print_html.count("REF-SYN-2") == 1
    assert print_html.count("Subtotal 1:") == 1
    assert print_html.count("Subtotal 2:") == 1
    assert print_html.count("Mijloc 1") == 1
    assert print_html.count("Mijloc 2") == 1
    assert print_html.count("8.5000") == 1
    assert re.search(r'class="print-money">\s*8\.5000\s*<span class="print-currency">RON</span>', print_html)
    assert re.search(r'class="print-money">\s*12\.00\s*<span class="print-currency">RON</span>', print_html)


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
    print_html = _print_markup(html)

    assert "0010.2300" in html
    assert "Descriere lungă cu diacritice: ăîșțâ" in html
    assert "detaliu sintetic" in html
    assert "&lt;script&gt;alert(&#39;synthetic&#39;)&lt;/script&gt;" in html
    assert "<script>alert('synthetic')</script>" not in html
    assert "0010.2300" in print_html
    assert "Descriere lungă cu diacritice: ăîșțâ" in print_html
    assert "&lt;script&gt;alert(&#39;synthetic&#39;)&lt;/script&gt;" in print_html
    assert "<script>alert('synthetic')</script>" not in print_html


@pytest.mark.parametrize("line_count", [1, 10, 30, 100])
def test_print_layout_renders_every_synthetic_line_in_order(
    local_client: tuple[FlaskClient, str], line_count: int
) -> None:
    client, csrf_token = local_client
    rendered = _render(client, csrf_token, _invoice_with_lines(line_count)).get_json()["invoice_html"]
    print_html = _print_markup(rendered)

    positions = [print_html.index(f"Articol {index:03}") for index in range(1, line_count + 1)]
    assert positions == sorted(positions)
    assert print_html.count("<tbody>") == 1
    assert print_html.count("<tr>") == line_count + 1


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
