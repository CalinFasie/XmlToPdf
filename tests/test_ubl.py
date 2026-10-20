from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from xmltopdf.ubl import (
    MAX_XML_BYTES,
    AmbiguousFieldError,
    Invoice,
    MalformedXmlError,
    MissingRequiredFieldError,
    UnsupportedDocumentError,
    XmlSecurityError,
    XmlTooLargeError,
    parse_invoice,
)

FIXTURE = Path(__file__).parent / "fixtures" / "ubl_invoice_minimal.xml"
MINIMAL_XML = FIXTURE.read_bytes()


def _replace_once(xml: bytes, old: bytes, new: bytes) -> bytes:
    assert xml.count(old) == 1
    return xml.replace(old, new, 1)


def _append_to_invoice(xml: bytes, fragment: bytes) -> bytes:
    return _replace_once(xml, b"</Invoice>", fragment + b"</Invoice>")


def _replace_supplier_block(xml: bytes, replacement: bytes) -> bytes:
    pattern = rb"  <cac:AccountingSupplierParty>.*?  </cac:AccountingSupplierParty>\n"
    changed, count = re.subn(pattern, replacement, xml, count=1, flags=re.DOTALL)
    assert count == 1
    return changed


def _replace_customer_block(xml: bytes, replacement: bytes) -> bytes:
    pattern = rb"  <cac:AccountingCustomerParty>.*?  </cac:AccountingCustomerParty>\n"
    changed, count = re.subn(pattern, replacement, xml, count=1, flags=re.DOTALL)
    assert count == 1
    return changed


def test_parses_synthetic_invoice_with_one_line_and_role_specific_ids() -> None:
    invoice = parse_invoice(MINIMAL_XML)

    assert isinstance(invoice, Invoice)
    assert invoice.invoice_id.value == "SYN-INV-001"
    assert invoice.issue_date.value == "2026-01-15"
    assert invoice.document_currency_code.value == "RON"
    assert invoice.supplier.party_names[0].value == "Furnizor Sintetic SRL"
    assert invoice.customer.legal_entities[0].registration_name.value == "Client Sintetic SA"
    assert invoice.supplier.identifications[0].id.value == "RO-SYN-001"
    assert invoice.customer.tax_schemes[0].company_id.value == "RO-SYN-002"
    assert invoice.supplier.identifications[0].id.attributes[0].name == "schemeID"
    assert invoice.supplier.postal_addresses[0].street_name.value == "Strada Exemplului"
    assert invoice.supplier.contacts[0].electronic_mail.value == "furnizor@example.invalid"
    assert invoice.lines[0].item.names[0].value == "Produs Sintetic"
    assert invoice.lines[0].item.classified_tax_categories[0].percent.value == "19"


def test_parser_module_import_does_not_require_flask() -> None:
    code = """import builtins
original_import = builtins.__import__
def import_without_flask(name, *args, **kwargs):
    if name == \"flask\" or name.startswith(\"flask.\"):
        raise AssertionError(\"Flask import attempted\")
    return original_import(name, *args, **kwargs)
builtins.__import__ = import_without_flask
from xmltopdf.ubl import parse_invoice
assert callable(parse_invoice)
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_preserves_all_invoice_lines_in_xml_order() -> None:
    line = b"""  <cac:InvoiceLine>
    <cbc:ID>2</cbc:ID>
    <cbc:InvoicedQuantity unitCode="C62">1</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="RON">3.25</cbc:LineExtensionAmount>
    <cac:Item><cbc:Description>Al doilea produs</cbc:Description></cac:Item>
  </cac:InvoiceLine>
"""
    invoice = parse_invoice(_append_to_invoice(MINIMAL_XML, line))

    assert [item.id.value for item in invoice.lines] == ["1", "2"]
    assert invoice.lines[1].item.descriptions[0].value == "Al doilea produs"


def test_preserves_multiple_payment_means_and_account_attributes() -> None:
    payments = """  <cac:PaymentMeans>
    <cbc:PaymentMeansCode listID="UNCL4461">30</cbc:PaymentMeansCode>
    <cbc:PaymentID>PAY-SYN-1</cbc:PaymentID>
    <cac:PayeeFinancialAccount>
      <cbc:ID schemeID="IBAN">RO00SYN000000000001</cbc:ID>
      <cbc:Name>Cont sintetic</cbc:Name>
      <cac:FinancialInstitutionBranch>
        <cbc:ID>BANK-SYN</cbc:ID>
        <cac:FinancialInstitution><cbc:ID>FI-SYN</cbc:ID></cac:FinancialInstitution>
      </cac:FinancialInstitutionBranch>
    </cac:PayeeFinancialAccount>
  </cac:PaymentMeans>
  <cac:PaymentMeans>
    <cbc:PaymentMeansCode>42</cbc:PaymentMeansCode>
    <cbc:InstructionNote>Instrucțiune sintetică</cbc:InstructionNote>
    <cac:PayerFinancialAccount><cbc:ID>PAYR-SYN</cbc:ID></cac:PayerFinancialAccount>
  </cac:PaymentMeans>
""".encode("utf-8")
    invoice = parse_invoice(_append_to_invoice(MINIMAL_XML, payments))

    assert len(invoice.payment_means) == 2
    assert invoice.payment_means[0].payment_means_code.value == "30"
    assert invoice.payment_means[0].payment_means_code.attributes[0].value == "UNCL4461"
    assert invoice.payment_means[0].payee_financial_account.id.value == "RO00SYN000000000001"
    assert invoice.payment_means[0].payee_financial_account.id.attributes[0].value == "IBAN"
    assert invoice.payment_means[0].payee_financial_account.financial_institution_id.value == "FI-SYN"
    assert invoice.payment_means[1].payer_financial_account.id.value == "PAYR-SYN"
    assert invoice.payment_means[1].instruction_notes[0].value == "Instrucțiune sintetică"


def test_preserves_multiple_tax_totals_and_tax_subtotals() -> None:
    tax_totals = b"""  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="RON">0.01</cbc:TaxAmount>
    <cac:TaxSubtotal>
      <cbc:TaxableAmount currencyID="RON">99.99</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="RON">0.01</cbc:TaxAmount>
      <cbc:Percent>19.00</cbc:Percent>
      <cac:TaxCategory><cbc:ID>S</cbc:ID><cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:TaxCategory>
    </cac:TaxSubtotal>
    <cac:TaxSubtotal>
      <cbc:TaxableAmount currencyID="RON">0.00</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="RON">0.00</cbc:TaxAmount>
      <cbc:Percent>0.00</cbc:Percent>
      <cac:TaxCategory><cbc:ID>Z</cbc:ID><cbc:TaxExemptionReason>Motiv sintetic</cbc:TaxExemptionReason></cac:TaxCategory>
    </cac:TaxSubtotal>
  </cac:TaxTotal>
  <cac:TaxTotal><cbc:TaxAmount currencyID="EUR">1.0000</cbc:TaxAmount></cac:TaxTotal>
"""
    invoice = parse_invoice(_append_to_invoice(MINIMAL_XML, tax_totals))

    assert len(invoice.tax_totals) == 2
    assert len(invoice.tax_totals[0].subtotals) == 2
    assert invoice.tax_totals[0].subtotals[0].tax_category.id.value == "S"
    assert invoice.tax_totals[0].subtotals[0].tax_category.tax_scheme.id.value == "VAT"
    assert invoice.tax_totals[0].subtotals[1].tax_category.tax_exemption_reasons[0].value == "Motiv sintetic"
    assert invoice.tax_totals[1].tax_amount.currency_id == "EUR"


def test_accepts_different_prefixes_for_the_same_namespace_uris() -> None:
    xml = MINIMAL_XML
    xml = xml.replace(
        b'xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"',
        b'xmlns:inv="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"',
    )
    xml = xml.replace(b"xmlns:cbc=", b"xmlns:basic=").replace(b"cbc:", b"basic:")
    xml = xml.replace(b"xmlns:cac=", b"xmlns:agg=").replace(b"cac:", b"agg:")
    xml = xml.replace(b"<Invoice ", b"<inv:Invoice ").replace(b"</Invoice>", b"</inv:Invoice>")

    invoice = parse_invoice(xml)

    assert invoice.invoice_id.value == "SYN-INV-001"
    assert invoice.lines[0].invoiced_quantity.unit_code == "C62"


def test_optional_fields_can_be_absent_without_invented_values() -> None:
    invoice = parse_invoice(MINIMAL_XML)

    assert invoice.due_date is None
    assert invoice.invoice_type_code is None
    assert invoice.tax_currency_code is None
    assert invoice.tax_totals == ()
    assert invoice.legal_monetary_total is None
    assert invoice.payment_means == ()
    assert invoice.deliveries == ()
    assert invoice.lines[0].price is not None
    assert invoice.lines[0].tax_totals == ()


@pytest.mark.parametrize(
    ("old", "tag"),
    [
        (b"<cbc:ID>SYN-INV-001</cbc:ID>", "Invoice/ID"),
        (b"<cbc:IssueDate>2026-01-15</cbc:IssueDate>", "Invoice/IssueDate"),
        (b"<cbc:DocumentCurrencyCode>RON</cbc:DocumentCurrencyCode>", "Invoice/DocumentCurrencyCode"),
        (b"<cbc:ID>1</cbc:ID>", "InvoiceLine[1]/ID"),
        (b'<cbc:InvoicedQuantity unitCode="C62">2.000</cbc:InvoicedQuantity>', "InvoiceLine[1]/InvoicedQuantity"),
        (b'<cbc:LineExtensionAmount currencyID="RON">10.00</cbc:LineExtensionAmount>', "InvoiceLine[1]/LineExtensionAmount"),
    ],
)
@pytest.mark.parametrize("mode", ["missing", "empty", "duplicate"])
def test_each_required_scalar_rejects_missing_empty_or_ambiguous(
    old: bytes, tag: str, mode: str
) -> None:
    if mode == "missing":
        replacement = b""
    elif mode == "empty":
        opening, closing = old.split(b">", 1)[0] + b">", old.rsplit(b"<", 1)[1]
        replacement = opening + b"   <" + closing
    else:
        replacement = old + old
    xml = _replace_once(MINIMAL_XML, old, replacement)
    expected = AmbiguousFieldError if mode == "duplicate" else MissingRequiredFieldError

    with pytest.raises(expected, match=re.escape(tag)):
        parse_invoice(xml)


@pytest.mark.parametrize("role", ["supplier", "customer"])
@pytest.mark.parametrize("mode", ["missing", "empty", "duplicate"])
def test_each_required_party_role_and_name_is_checked(role: str, mode: str) -> None:
    if role == "supplier":
        block = re.search(
            rb"  <cac:AccountingSupplierParty>.*?  </cac:AccountingSupplierParty>\n",
            MINIMAL_XML,
            re.DOTALL,
        ).group()
        name = b"<cbc:Name>Furnizor Sintetic SRL</cbc:Name>"
        replace_block = _replace_supplier_block
    else:
        block = re.search(
            rb"  <cac:AccountingCustomerParty>.*?  </cac:AccountingCustomerParty>\n",
            MINIMAL_XML,
            re.DOTALL,
        ).group()
        name = b"<cbc:RegistrationName>Client Sintetic SA</cbc:RegistrationName>"
        replace_block = _replace_customer_block

    if mode == "missing":
        xml = replace_block(MINIMAL_XML, b"")
        expected = MissingRequiredFieldError
    elif mode == "empty":
        text = name.split(b">", 1)[1].split(b"<", 1)[0]
        xml = _replace_once(MINIMAL_XML, name, name.replace(text, b"   "))
        expected = MissingRequiredFieldError
    else:
        xml = replace_block(MINIMAL_XML, block + block)
        expected = AmbiguousFieldError

    with pytest.raises(expected):
        parse_invoice(xml)


@pytest.mark.parametrize("mode", ["missing", "empty", "duplicate"])
def test_required_item_name_or_description_is_checked(mode: str) -> None:
    name = b"<cbc:Name>Produs Sintetic</cbc:Name>"
    if mode == "missing":
        xml = _replace_once(MINIMAL_XML, name, b"")
        expected = MissingRequiredFieldError
    elif mode == "empty":
        xml = _replace_once(MINIMAL_XML, name, b"<cbc:Name>   </cbc:Name>")
        expected = MissingRequiredFieldError
    else:
        xml = _replace_once(MINIMAL_XML, name, name + name)
        expected = AmbiguousFieldError

    with pytest.raises(expected, match="Item/Name"):
        parse_invoice(xml)


@pytest.mark.parametrize("role", ["supplier", "customer"])
def test_duplicate_party_element_is_rejected(role: str) -> None:
    if role == "supplier":
        match = re.search(
            rb"  <cac:AccountingSupplierParty>.*?  </cac:AccountingSupplierParty>\n",
            MINIMAL_XML,
            re.DOTALL,
        )
        replace_block = _replace_supplier_block
    else:
        match = re.search(
            rb"  <cac:AccountingCustomerParty>.*?  </cac:AccountingCustomerParty>\n",
            MINIMAL_XML,
            re.DOTALL,
        )
        replace_block = _replace_customer_block
    role_block = match.group()
    party = re.search(rb"    <cac:Party>.*?    </cac:Party>", role_block, re.DOTALL).group()
    xml = replace_block(MINIMAL_XML, role_block.replace(party, party + party))

    with pytest.raises(AmbiguousFieldError):
        parse_invoice(xml)


@pytest.mark.parametrize("role", ["supplier", "customer"])
def test_required_party_container_must_be_present(role: str) -> None:
    if role == "supplier":
        match = re.search(
            rb"  <cac:AccountingSupplierParty>.*?  </cac:AccountingSupplierParty>\n",
            MINIMAL_XML,
            re.DOTALL,
        )
        replace_block = _replace_supplier_block
    else:
        match = re.search(
            rb"  <cac:AccountingCustomerParty>.*?  </cac:AccountingCustomerParty>\n",
            MINIMAL_XML,
            re.DOTALL,
        )
        replace_block = _replace_customer_block
    role_block = match.group()
    party = re.search(rb"    <cac:Party>.*?    </cac:Party>", role_block, re.DOTALL).group()

    with pytest.raises(MissingRequiredFieldError, match="Party"):
        parse_invoice(replace_block(MINIMAL_XML, role_block.replace(party, b"")))


def test_rejects_invoice_without_any_lines() -> None:
    start = MINIMAL_XML.index(b"  <cac:InvoiceLine>")
    close = b"  </cac:InvoiceLine>\n"
    end = MINIMAL_XML.index(close, start) + len(close)

    with pytest.raises(MissingRequiredFieldError, match="InvoiceLine"):
        parse_invoice(MINIMAL_XML[:start] + MINIMAL_XML[end:])


def test_rejects_missing_or_duplicate_item_element() -> None:
    item = b"""    <cac:Item>
      <cbc:Name>Produs Sintetic</cbc:Name>
      <cac:ClassifiedTaxCategory>
        <cbc:ID>S</cbc:ID>
        <cbc:Percent>19</cbc:Percent>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:ClassifiedTaxCategory>
    </cac:Item>
"""
    with pytest.raises(MissingRequiredFieldError, match="Item"):
        parse_invoice(_replace_once(MINIMAL_XML, item, b""))
    with pytest.raises(AmbiguousFieldError, match="Item"):
        parse_invoice(_replace_once(MINIMAL_XML, item, item + item))


@pytest.mark.parametrize(
    "xml",
    [
        b'<Other xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"/>',
        b'<Invoice xmlns="urn:unsupported"/>',
        b'<CreditNote xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"/>',
    ],
)
def test_rejects_unsupported_root_or_namespace(xml: bytes) -> None:
    with pytest.raises(UnsupportedDocumentError):
        parse_invoice(xml)


def test_rejects_malformed_xml_without_parser_details() -> None:
    with pytest.raises(MalformedXmlError) as error:
        parse_invoice(b"<Invoice><broken>")

    assert "line" not in str(error.value).lower()
    assert "column" not in str(error.value).lower()


def test_rejects_doctype_and_external_entity_without_expanding_it() -> None:
    xml = (
        b'<!DOCTYPE Invoice [<!ENTITY ext SYSTEM "file:///not-read-synthetic.xml">]>'
        b'<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">'
        + b"<cbc:ID>&ext;</cbc:ID></Invoice>"
    )

    with pytest.raises(XmlSecurityError) as error:
        parse_invoice(xml)

    assert "file:///" not in str(error.value)
    assert "not-read-synthetic.xml" not in str(error.value)


def test_doctype_token_inside_comment_is_not_treated_as_a_declaration() -> None:
    xml = MINIMAL_XML.replace(
        b"  <cbc:ID>SYN-INV-001</cbc:ID>",
        b"  <!-- <!DOCTYPE is comment text> -->\n  <cbc:ID>SYN-INV-001</cbc:ID>",
    )

    assert parse_invoice(xml).invoice_id.value == "SYN-INV-001"


def test_rejects_xinclude_without_processing_it() -> None:
    xml = MINIMAL_XML.replace(
        b"<Invoice ",
        b'<Invoice xmlns:xi="http://www.w3.org/2001/XInclude" ',
    )
    xml = _append_to_invoice(
        xml,
        b'<xi:include href="file:///not-read.xml" parse="text"/>',
    )

    with pytest.raises(XmlSecurityError, match="XInclude"):
        parse_invoice(xml)


def test_rejects_input_over_10_mib_before_xml_parsing() -> None:
    oversized = MINIMAL_XML + (b" " * (MAX_XML_BYTES + 1))

    with pytest.raises(XmlTooLargeError):
        parse_invoice(oversized)


def test_preserves_decimal_text_and_separate_currency_and_unit_attributes() -> None:
    xml = MINIMAL_XML.replace(
        b">10.00</cbc:LineExtensionAmount>",
        b"> 0010.2300 </cbc:LineExtensionAmount>",
    )
    xml = xml.replace(
        b">2.000</cbc:InvoicedQuantity>",
        b"> 2.5000 </cbc:InvoicedQuantity>",
    )
    invoice = parse_invoice(xml)

    assert invoice.lines[0].line_extension_amount.value == "0010.2300"
    assert invoice.lines[0].line_extension_amount.currency_id == "RON"
    assert invoice.lines[0].invoiced_quantity.value == "2.5000"
    assert invoice.lines[0].invoiced_quantity.unit_code == "C62"


def test_preserves_all_legal_monetary_total_fields_without_reconciliation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    totals = b"""  <cac:TaxTotal><cbc:TaxAmount currencyID="RON">900.00</cbc:TaxAmount></cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="RON">10.00</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="RON">12.34</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="RON">99.99</cbc:TaxInclusiveAmount>
    <cbc:AllowanceTotalAmount currencyID="RON">1.00</cbc:AllowanceTotalAmount>
    <cbc:ChargeTotalAmount currencyID="RON">2.00</cbc:ChargeTotalAmount>
    <cbc:PrepaidAmount currencyID="RON">3.00</cbc:PrepaidAmount>
    <cbc:PayableRoundingAmount currencyID="RON">0.01</cbc:PayableRoundingAmount>
    <cbc:PayableAmount currencyID="RON">4.00</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
"""

    with caplog.at_level("WARNING"):
        invoice = parse_invoice(_append_to_invoice(MINIMAL_XML, totals))

    assert invoice.tax_totals[0].tax_amount.value == "900.00"
    total = invoice.legal_monetary_total
    assert total.line_extension_amount.value == "10.00"
    assert total.tax_exclusive_amount.value == "12.34"
    assert total.tax_inclusive_amount.value == "99.99"
    assert total.allowance_total_amount.value == "1.00"
    assert total.charge_total_amount.value == "2.00"
    assert total.prepaid_amount.value == "3.00"
    assert total.payable_rounding_amount.value == "0.01"
    assert total.payable_amount.value == "4.00"
    assert caplog.records == []


def test_parses_delivery_party_date_and_location_address() -> None:
    delivery = b"""  <cac:Delivery>
    <cbc:ActualDeliveryDate>2026-01-20</cbc:ActualDeliveryDate>
    <cbc:ActualDeliveryTime>09:30:00</cbc:ActualDeliveryTime>
    <cac:DeliveryParty><cac:PartyName><cbc:Name>Destinatar Sintetic</cbc:Name></cac:PartyName></cac:DeliveryParty>
    <cac:DeliveryLocation>
      <cbc:ID>LOC-SYN</cbc:ID>
      <cac:Address><cbc:CityName>Brasov</cbc:CityName><cbc:PostalZone>500000</cbc:PostalZone></cac:Address>
    </cac:DeliveryLocation>
  </cac:Delivery>
"""
    invoice = parse_invoice(_append_to_invoice(MINIMAL_XML, delivery))

    assert len(invoice.deliveries) == 1
    assert invoice.deliveries[0].actual_delivery_date.value == "2026-01-20"
    assert invoice.deliveries[0].delivery_party.party_names[0].value == "Destinatar Sintetic"
    assert invoice.deliveries[0].delivery_location.address.city_name.value == "Brasov"
