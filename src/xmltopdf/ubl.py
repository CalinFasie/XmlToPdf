"""Parse the supported UBL Invoice subset into immutable Python data."""

from __future__ import annotations

from dataclasses import dataclass

from lxml import etree

INVOICE_NS = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
CBC_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
CAC_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
XINCLUDE_NS = "http://www.w3.org/2001/XInclude"
MAX_XML_BYTES = 10 * 1024 * 1024


class InvoiceParseError(ValueError):
    """Base error for safe, user-facing invoice parsing failures."""


class MalformedXmlError(InvoiceParseError):
    """Raised when input is not well-formed XML."""


class UnsupportedDocumentError(InvoiceParseError):
    """Raised when the document root is not the supported UBL Invoice QName."""


class XmlSecurityError(InvoiceParseError):
    """Raised when the XML uses a prohibited feature such as a DTD or XInclude."""


class XmlTooLargeError(InvoiceParseError):
    """Raised when the in-memory XML input exceeds the configured safety limit."""


class MissingRequiredFieldError(InvoiceParseError):
    """Raised when a required field is missing or empty."""


class AmbiguousFieldError(InvoiceParseError):
    """Raised when duplicate required or singleton fields are ambiguous."""


@dataclass(frozen=True, slots=True)
class XmlAttribute:
    name: str
    value: str


@dataclass(frozen=True, slots=True)
class UblText:
    value: str | None
    attributes: tuple[XmlAttribute, ...] = ()


@dataclass(frozen=True, slots=True)
class Amount:
    value: str | None
    currency_id: str | None
    attributes: tuple[XmlAttribute, ...] = ()


@dataclass(frozen=True, slots=True)
class Quantity:
    value: str | None
    unit_code: str | None
    attributes: tuple[XmlAttribute, ...] = ()


@dataclass(frozen=True, slots=True)
class Country:
    identification_code: UblText | None
    name: UblText | None


@dataclass(frozen=True, slots=True)
class Address:
    id: UblText | None
    street_name: UblText | None
    additional_street_name: UblText | None
    building_number: UblText | None
    city_name: UblText | None
    postal_zone: UblText | None
    country_subentity: UblText | None
    address_lines: tuple[UblText, ...]
    country: Country | None


@dataclass(frozen=True, slots=True)
class Contact:
    id: UblText | None
    name: UblText | None
    telephone: UblText | None
    telefax: UblText | None
    electronic_mail: UblText | None
    note: UblText | None


@dataclass(frozen=True, slots=True)
class PartyIdentification:
    id: UblText | None


@dataclass(frozen=True, slots=True)
class PartyLegalEntity:
    registration_name: UblText | None
    company_id: UblText | None
    company_legal_form: UblText | None
    company_legal_form_code: UblText | None


@dataclass(frozen=True, slots=True)
class TaxScheme:
    id: UblText | None
    name: UblText | None
    tax_type_code: UblText | None


@dataclass(frozen=True, slots=True)
class PartyTaxScheme:
    company_id: UblText | None
    tax_scheme: TaxScheme | None


@dataclass(frozen=True, slots=True)
class Party:
    party_names: tuple[UblText, ...]
    endpoint_ids: tuple[UblText, ...]
    identifications: tuple[PartyIdentification, ...]
    legal_entities: tuple[PartyLegalEntity, ...]
    tax_schemes: tuple[PartyTaxScheme, ...]
    postal_addresses: tuple[Address, ...]
    contacts: tuple[Contact, ...]


@dataclass(frozen=True, slots=True)
class TaxCategory:
    id: UblText | None
    name: UblText | None
    percent: UblText | None
    tax_exemption_reason_code: UblText | None
    tax_exemption_reasons: tuple[UblText, ...]
    tax_scheme: TaxScheme | None


@dataclass(frozen=True, slots=True)
class TaxSubtotal:
    taxable_amount: Amount | None
    tax_amount: Amount | None
    calculation_sequence_numeric: UblText | None
    transaction_currency_tax_amount: Amount | None
    percent: UblText | None
    base_unit_measure: Quantity | None
    per_unit_amount: Amount | None
    tier_range: UblText | None
    tier_rate_percent: UblText | None
    tax_category: TaxCategory | None


@dataclass(frozen=True, slots=True)
class TaxTotal:
    tax_amount: Amount | None
    rounding_amount: Amount | None
    subtotals: tuple[TaxSubtotal, ...]


@dataclass(frozen=True, slots=True)
class ItemIdentification:
    id: UblText | None


@dataclass(frozen=True, slots=True)
class Item:
    names: tuple[UblText, ...]
    descriptions: tuple[UblText, ...]
    sellers_item_identification: ItemIdentification | None
    standard_item_identification: ItemIdentification | None
    classified_tax_categories: tuple[TaxCategory, ...]


@dataclass(frozen=True, slots=True)
class Price:
    price_amount: Amount | None
    base_quantity: Quantity | None


@dataclass(frozen=True, slots=True)
class InvoiceLine:
    id: UblText
    invoiced_quantity: Quantity
    line_extension_amount: Amount
    item: Item
    price: Price | None
    tax_totals: tuple[TaxTotal, ...]


@dataclass(frozen=True, slots=True)
class LegalMonetaryTotal:
    line_extension_amount: Amount | None
    tax_exclusive_amount: Amount | None
    tax_inclusive_amount: Amount | None
    allowance_total_amount: Amount | None
    charge_total_amount: Amount | None
    prepaid_amount: Amount | None
    payable_rounding_amount: Amount | None
    payable_amount: Amount | None


@dataclass(frozen=True, slots=True)
class FinancialAccount:
    id: UblText | None
    name: UblText | None
    account_type_code: UblText | None
    currency_code: UblText | None
    financial_institution_id: UblText | None
    branch_id: UblText | None
    branch_name: UblText | None


@dataclass(frozen=True, slots=True)
class PaymentMeans:
    payment_means_code: UblText | None
    payment_due_date: UblText | None
    payment_channel_code: UblText | None
    instruction_id: UblText | None
    instruction_notes: tuple[UblText, ...]
    payment_ids: tuple[UblText, ...]
    payee_financial_account: FinancialAccount | None
    payer_financial_account: FinancialAccount | None


@dataclass(frozen=True, slots=True)
class DeliveryLocation:
    id: UblText | None
    descriptions: tuple[UblText, ...]
    address: Address | None


@dataclass(frozen=True, slots=True)
class Delivery:
    actual_delivery_date: UblText | None
    actual_delivery_time: UblText | None
    delivery_party: Party | None
    delivery_location: DeliveryLocation | None


@dataclass(frozen=True, slots=True)
class Invoice:
    invoice_id: UblText
    issue_date: UblText
    due_date: UblText | None
    invoice_type_code: UblText | None
    document_currency_code: UblText
    tax_currency_code: UblText | None
    supplier: Party
    customer: Party
    lines: tuple[InvoiceLine, ...]
    tax_totals: tuple[TaxTotal, ...]
    legal_monetary_total: LegalMonetaryTotal | None
    payment_means: tuple[PaymentMeans, ...]
    deliveries: tuple[Delivery, ...]


def _qname(namespace: str, local_name: str) -> str:
    return f"{{{namespace}}}{local_name}"


def _contains_doctype_declaration(xml_content: bytes) -> bool:
    # Markup is ASCII-compatible for the supported XML encodings; dropping NUL
    # bytes also exposes the token in UTF-16/UTF-32 byte streams. Ignore contexts
    # where the same characters are ordinary comment, CDATA, or PI content.
    normalized = xml_content.replace(b"\x00", b"")
    index = 0
    ignored_sections = (
        (b"<!--", b"-->"),
        (b"<![CDATA[", b"]]>"),
        (b"<?", b"?>"),
    )
    while index < len(normalized):
        for opening, closing in ignored_sections:
            if normalized.startswith(opening, index):
                end = normalized.find(closing, index + len(opening))
                if end < 0:
                    return False
                index = end + len(closing)
                break
        else:
            if normalized.startswith(b"<!DOCTYPE", index):
                return True
            index += 1
    return False


def _children(parent: etree._Element, namespace: str, local_name: str) -> list[etree._Element]:
    tag = _qname(namespace, local_name)
    return [child for child in parent if child.tag == tag]


def _attributes(element: etree._Element) -> tuple[XmlAttribute, ...]:
    return tuple(XmlAttribute(name, value) for name, value in element.attrib.items())


def _text(element: etree._Element) -> str | None:
    value = (element.text or "").strip()
    return value or None


def _ubl_text(element: etree._Element) -> UblText:
    return UblText(_text(element), _attributes(element))


def _optional_element(
    parent: etree._Element, namespace: str, local_name: str, path: str
) -> etree._Element | None:
    matches = _children(parent, namespace, local_name)
    if len(matches) > 1:
        raise AmbiguousFieldError(f"Câmp ambiguu: {path}.")
    return matches[0] if matches else None


def _required_element(
    parent: etree._Element, namespace: str, local_name: str, path: str
) -> etree._Element:
    element = _optional_element(parent, namespace, local_name, path)
    if element is None:
        raise MissingRequiredFieldError(f"Lipsește câmpul obligatoriu: {path}.")
    return element


def _optional_text(parent: etree._Element, local_name: str, path: str) -> UblText | None:
    element = _optional_element(parent, CBC_NS, local_name, path)
    return _ubl_text(element) if element is not None else None


def _optional_texts(parent: etree._Element, local_name: str) -> tuple[UblText, ...]:
    return tuple(_ubl_text(element) for element in _children(parent, CBC_NS, local_name))


def _required_text(parent: etree._Element, local_name: str, path: str) -> UblText:
    element = _required_element(parent, CBC_NS, local_name, path)
    value = _ubl_text(element)
    if value.value is None:
        raise MissingRequiredFieldError(f"Lipsește câmpul obligatoriu: {path}.")
    return value


def _make_amount(element: etree._Element) -> Amount:
    return Amount(_text(element), element.get("currencyID"), _attributes(element))


def _optional_amount(parent: etree._Element, local_name: str, path: str) -> Amount | None:
    element = _optional_element(parent, CBC_NS, local_name, path)
    return _make_amount(element) if element is not None else None


def _required_amount(parent: etree._Element, local_name: str, path: str) -> Amount:
    element = _required_element(parent, CBC_NS, local_name, path)
    amount = _make_amount(element)
    if amount.value is None:
        raise MissingRequiredFieldError(f"Lipsește câmpul obligatoriu: {path}.")
    return amount


def _make_quantity(element: etree._Element) -> Quantity:
    return Quantity(_text(element), element.get("unitCode"), _attributes(element))


def _required_quantity(parent: etree._Element, local_name: str, path: str) -> Quantity:
    element = _required_element(parent, CBC_NS, local_name, path)
    quantity = _make_quantity(element)
    if quantity.value is None:
        raise MissingRequiredFieldError(f"Lipsește câmpul obligatoriu: {path}.")
    return quantity


def _optional_quantity(parent: etree._Element, local_name: str, path: str) -> Quantity | None:
    element = _optional_element(parent, CBC_NS, local_name, path)
    return _make_quantity(element) if element is not None else None


def _parse_country(element: etree._Element) -> Country:
    return Country(
        _optional_text(element, "IdentificationCode", "Country/IdentificationCode"),
        _optional_text(element, "Name", "Country/Name"),
    )


def _parse_address(element: etree._Element) -> Address:
    country_element = _optional_element(element, CAC_NS, "Country", "Address/Country")
    address_lines: list[UblText] = []
    for address_line in _children(element, CAC_NS, "AddressLine"):
        address_lines.extend(_optional_texts(address_line, "Line"))
    return Address(
        id=_optional_text(element, "ID", "Address/ID"),
        street_name=_optional_text(element, "StreetName", "Address/StreetName"),
        additional_street_name=_optional_text(
            element, "AdditionalStreetName", "Address/AdditionalStreetName"
        ),
        building_number=_optional_text(element, "BuildingNumber", "Address/BuildingNumber"),
        city_name=_optional_text(element, "CityName", "Address/CityName"),
        postal_zone=_optional_text(element, "PostalZone", "Address/PostalZone"),
        country_subentity=_optional_text(element, "CountrySubentity", "Address/CountrySubentity"),
        address_lines=tuple(address_lines),
        country=_parse_country(country_element) if country_element is not None else None,
    )


def _parse_contact(element: etree._Element) -> Contact:
    return Contact(
        id=_optional_text(element, "ID", "Contact/ID"),
        name=_optional_text(element, "Name", "Contact/Name"),
        telephone=_optional_text(element, "Telephone", "Contact/Telephone"),
        telefax=_optional_text(element, "Telefax", "Contact/Telefax"),
        electronic_mail=_optional_text(element, "ElectronicMail", "Contact/ElectronicMail"),
        note=_optional_text(element, "Note", "Contact/Note"),
    )


def _parse_tax_scheme(element: etree._Element | None) -> TaxScheme | None:
    if element is None:
        return None
    return TaxScheme(
        id=_optional_text(element, "ID", "TaxScheme/ID"),
        name=_optional_text(element, "Name", "TaxScheme/Name"),
        tax_type_code=_optional_text(element, "TaxTypeCode", "TaxScheme/TaxTypeCode"),
    )


def _parse_party_legal_entity(element: etree._Element) -> PartyLegalEntity:
    return PartyLegalEntity(
        registration_name=_optional_text(
            element, "RegistrationName", "PartyLegalEntity/RegistrationName"
        ),
        company_id=_optional_text(element, "CompanyID", "PartyLegalEntity/CompanyID"),
        company_legal_form=_optional_text(
            element, "CompanyLegalForm", "PartyLegalEntity/CompanyLegalForm"
        ),
        company_legal_form_code=_optional_text(
            element, "CompanyLegalFormCode", "PartyLegalEntity/CompanyLegalFormCode"
        ),
    )


def _parse_party_tax_scheme(element: etree._Element) -> PartyTaxScheme:
    scheme = _optional_element(element, CAC_NS, "TaxScheme", "PartyTaxScheme/TaxScheme")
    return PartyTaxScheme(
        company_id=_optional_text(element, "CompanyID", "PartyTaxScheme/CompanyID"),
        tax_scheme=_parse_tax_scheme(scheme),
    )


def _parse_party(element: etree._Element, role: str, *, require_name: bool) -> Party:
    party_names: list[UblText] = []
    for party_name in _children(element, CAC_NS, "PartyName"):
        party_names.extend(_optional_texts(party_name, "Name"))
    legal_entities = tuple(
        _parse_party_legal_entity(item)
        for item in _children(element, CAC_NS, "PartyLegalEntity")
    )
    if require_name and not any(
        item.value is not None for item in party_names
    ) and not any(
        entity.registration_name is not None and entity.registration_name.value is not None
        for entity in legal_entities
    ):
        raise MissingRequiredFieldError(
            f"Lipsește câmpul obligatoriu: {role}/PartyName/Name sau "
            "PartyLegalEntity/RegistrationName."
        )

    identifications = tuple(
        PartyIdentification(
            id=_optional_text(item, "ID", f"{role}/PartyIdentification/ID")
        )
        for item in _children(element, CAC_NS, "PartyIdentification")
    )
    tax_schemes = tuple(
        _parse_party_tax_scheme(item)
        for item in _children(element, CAC_NS, "PartyTaxScheme")
    )
    addresses = tuple(
        _parse_address(item) for item in _children(element, CAC_NS, "PostalAddress")
    )
    contacts = tuple(
        _parse_contact(item) for item in _children(element, CAC_NS, "Contact")
    )
    return Party(
        party_names=tuple(party_names),
        endpoint_ids=_optional_texts(element, "EndpointID"),
        identifications=identifications,
        legal_entities=legal_entities,
        tax_schemes=tax_schemes,
        postal_addresses=addresses,
        contacts=contacts,
    )


def _parse_tax_category(element: etree._Element) -> TaxCategory:
    scheme = _optional_element(element, CAC_NS, "TaxScheme", "TaxCategory/TaxScheme")
    return TaxCategory(
        id=_optional_text(element, "ID", "TaxCategory/ID"),
        name=_optional_text(element, "Name", "TaxCategory/Name"),
        percent=_optional_text(element, "Percent", "TaxCategory/Percent"),
        tax_exemption_reason_code=_optional_text(
            element, "TaxExemptionReasonCode", "TaxCategory/TaxExemptionReasonCode"
        ),
        tax_exemption_reasons=_optional_texts(element, "TaxExemptionReason"),
        tax_scheme=_parse_tax_scheme(scheme),
    )


def _parse_tax_subtotal(element: etree._Element) -> TaxSubtotal:
    category = _optional_element(element, CAC_NS, "TaxCategory", "TaxSubtotal/TaxCategory")
    base_unit = _optional_element(element, CBC_NS, "BaseUnitMeasure", "TaxSubtotal/BaseUnitMeasure")
    return TaxSubtotal(
        taxable_amount=_optional_amount(element, "TaxableAmount", "TaxSubtotal/TaxableAmount"),
        tax_amount=_optional_amount(element, "TaxAmount", "TaxSubtotal/TaxAmount"),
        calculation_sequence_numeric=_optional_text(
            element, "CalculationSequenceNumeric", "TaxSubtotal/CalculationSequenceNumeric"
        ),
        transaction_currency_tax_amount=_optional_amount(
            element, "TransactionCurrencyTaxAmount", "TaxSubtotal/TransactionCurrencyTaxAmount"
        ),
        percent=_optional_text(element, "Percent", "TaxSubtotal/Percent"),
        base_unit_measure=_make_quantity(base_unit) if base_unit is not None else None,
        per_unit_amount=_optional_amount(element, "PerUnitAmount", "TaxSubtotal/PerUnitAmount"),
        tier_range=_optional_text(element, "TierRange", "TaxSubtotal/TierRange"),
        tier_rate_percent=_optional_text(
            element, "TierRatePercent", "TaxSubtotal/TierRatePercent"
        ),
        tax_category=_parse_tax_category(category) if category is not None else None,
    )


def _parse_tax_total(element: etree._Element) -> TaxTotal:
    return TaxTotal(
        tax_amount=_optional_amount(element, "TaxAmount", "TaxTotal/TaxAmount"),
        rounding_amount=_optional_amount(element, "RoundingAmount", "TaxTotal/RoundingAmount"),
        subtotals=tuple(
            _parse_tax_subtotal(item)
            for item in _children(element, CAC_NS, "TaxSubtotal")
        ),
    )


def _parse_item_identification(element: etree._Element | None) -> ItemIdentification | None:
    if element is None:
        return None
    return ItemIdentification(id=_optional_text(element, "ID", "ItemIdentification/ID"))


def _parse_item(element: etree._Element, line_number: int) -> Item:
    name_elements = _children(element, CBC_NS, "Name")
    names = tuple(_ubl_text(item) for item in name_elements)
    descriptions = _optional_texts(element, "Description")
    if len(name_elements) > 1:
        raise AmbiguousFieldError(
            f"Câmp ambiguu: InvoiceLine[{line_number}]/Item/Name."
        )
    if not any(value.value is not None for value in (*names, *descriptions)):
        raise MissingRequiredFieldError(
            f"Lipsește câmpul obligatoriu: InvoiceLine[{line_number}]/Item/Name sau Description."
        )
    sellers_id = _optional_element(
        element, CAC_NS, "SellersItemIdentification", "Item/SellersItemIdentification"
    )
    standard_id = _optional_element(
        element, CAC_NS, "StandardItemIdentification", "Item/StandardItemIdentification"
    )
    return Item(
        names=names,
        descriptions=descriptions,
        sellers_item_identification=_parse_item_identification(sellers_id),
        standard_item_identification=_parse_item_identification(standard_id),
        classified_tax_categories=tuple(
            _parse_tax_category(item)
            for item in _children(element, CAC_NS, "ClassifiedTaxCategory")
        ),
    )


def _parse_price(element: etree._Element | None) -> Price | None:
    if element is None:
        return None
    return Price(
        price_amount=_optional_amount(element, "PriceAmount", "Price/PriceAmount"),
        base_quantity=_optional_quantity(element, "BaseQuantity", "Price/BaseQuantity"),
    )


def _parse_invoice_line(element: etree._Element, index: int) -> InvoiceLine:
    path = f"InvoiceLine[{index}]"
    item_element = _required_element(element, CAC_NS, "Item", f"{path}/Item")
    price_element = _optional_element(element, CAC_NS, "Price", f"{path}/Price")
    return InvoiceLine(
        id=_required_text(element, "ID", f"{path}/ID"),
        invoiced_quantity=_required_quantity(
            element, "InvoicedQuantity", f"{path}/InvoicedQuantity"
        ),
        line_extension_amount=_required_amount(
            element, "LineExtensionAmount", f"{path}/LineExtensionAmount"
        ),
        item=_parse_item(item_element, index),
        price=_parse_price(price_element),
        tax_totals=tuple(
            _parse_tax_total(item) for item in _children(element, CAC_NS, "TaxTotal")
        ),
    )


def _parse_legal_monetary_total(element: etree._Element | None) -> LegalMonetaryTotal | None:
    if element is None:
        return None
    return LegalMonetaryTotal(
        line_extension_amount=_optional_amount(
            element, "LineExtensionAmount", "LegalMonetaryTotal/LineExtensionAmount"
        ),
        tax_exclusive_amount=_optional_amount(
            element, "TaxExclusiveAmount", "LegalMonetaryTotal/TaxExclusiveAmount"
        ),
        tax_inclusive_amount=_optional_amount(
            element, "TaxInclusiveAmount", "LegalMonetaryTotal/TaxInclusiveAmount"
        ),
        allowance_total_amount=_optional_amount(
            element, "AllowanceTotalAmount", "LegalMonetaryTotal/AllowanceTotalAmount"
        ),
        charge_total_amount=_optional_amount(
            element, "ChargeTotalAmount", "LegalMonetaryTotal/ChargeTotalAmount"
        ),
        prepaid_amount=_optional_amount(
            element, "PrepaidAmount", "LegalMonetaryTotal/PrepaidAmount"
        ),
        payable_rounding_amount=_optional_amount(
            element, "PayableRoundingAmount", "LegalMonetaryTotal/PayableRoundingAmount"
        ),
        payable_amount=_optional_amount(
            element, "PayableAmount", "LegalMonetaryTotal/PayableAmount"
        ),
    )


def _parse_financial_account(element: etree._Element | None) -> FinancialAccount | None:
    if element is None:
        return None
    branch = _optional_element(
        element, CAC_NS, "FinancialInstitutionBranch", "FinancialAccount/FinancialInstitutionBranch"
    )
    institution = (
        _optional_element(branch, CAC_NS, "FinancialInstitution", "FinancialInstitutionBranch/FinancialInstitution")
        if branch is not None
        else None
    )
    return FinancialAccount(
        id=_optional_text(element, "ID", "FinancialAccount/ID"),
        name=_optional_text(element, "Name", "FinancialAccount/Name"),
        account_type_code=_optional_text(element, "AccountTypeCode", "FinancialAccount/AccountTypeCode"),
        currency_code=_optional_text(element, "CurrencyCode", "FinancialAccount/CurrencyCode"),
        financial_institution_id=(
            _optional_text(institution, "ID", "FinancialInstitution/ID")
            if institution is not None
            else None
        ),
        branch_id=(
            _optional_text(branch, "ID", "FinancialInstitutionBranch/ID")
            if branch is not None
            else None
        ),
        branch_name=(
            _optional_text(branch, "Name", "FinancialInstitutionBranch/Name")
            if branch is not None
            else None
        ),
    )


def _parse_payment_means(element: etree._Element) -> PaymentMeans:
    payee = _optional_element(
        element, CAC_NS, "PayeeFinancialAccount", "PaymentMeans/PayeeFinancialAccount"
    )
    payer = _optional_element(
        element, CAC_NS, "PayerFinancialAccount", "PaymentMeans/PayerFinancialAccount"
    )
    return PaymentMeans(
        payment_means_code=_optional_text(element, "PaymentMeansCode", "PaymentMeans/PaymentMeansCode"),
        payment_due_date=_optional_text(element, "PaymentDueDate", "PaymentMeans/PaymentDueDate"),
        payment_channel_code=_optional_text(element, "PaymentChannelCode", "PaymentMeans/PaymentChannelCode"),
        instruction_id=_optional_text(element, "InstructionID", "PaymentMeans/InstructionID"),
        instruction_notes=_optional_texts(element, "InstructionNote"),
        payment_ids=_optional_texts(element, "PaymentID"),
        payee_financial_account=_parse_financial_account(payee),
        payer_financial_account=_parse_financial_account(payer),
    )


def _parse_delivery_location(element: etree._Element | None) -> DeliveryLocation | None:
    if element is None:
        return None
    address_element = _optional_element(element, CAC_NS, "Address", "DeliveryLocation/Address")
    return DeliveryLocation(
        id=_optional_text(element, "ID", "DeliveryLocation/ID"),
        descriptions=_optional_texts(element, "Description"),
        address=_parse_address(address_element) if address_element is not None else None,
    )


def _parse_delivery(element: etree._Element) -> Delivery:
    party_element = _optional_element(element, CAC_NS, "DeliveryParty", "Delivery/DeliveryParty")
    location_element = _optional_element(
        element, CAC_NS, "DeliveryLocation", "Delivery/DeliveryLocation"
    )
    return Delivery(
        actual_delivery_date=_optional_text(element, "ActualDeliveryDate", "Delivery/ActualDeliveryDate"),
        actual_delivery_time=_optional_text(element, "ActualDeliveryTime", "Delivery/ActualDeliveryTime"),
        delivery_party=(
            _parse_party(party_element, "DeliveryParty", require_name=False)
            if party_element is not None
            else None
        ),
        delivery_location=_parse_delivery_location(location_element),
    )


def _required_role_party(root: etree._Element, role: str) -> Party:
    wrapper = _required_element(root, CAC_NS, role, role)
    party = _required_element(wrapper, CAC_NS, "Party", f"{role}/Party")
    return _parse_party(party, role, require_name=True)


def parse_invoice(xml_content: bytes) -> Invoice:
    """Parse a well-formed UBL Invoice byte string into an immutable data model.

    Only the supported Invoice QName and FR-04 display minimum are required; this
    function does not validate XSD, EN 16931, RO_CIUS, or fiscal correctness.
    """
    if not isinstance(xml_content, bytes):
        raise TypeError("xml_content trebuie să fie bytes.")
    if len(xml_content) > MAX_XML_BYTES:
        raise XmlTooLargeError("Documentul XML depășește limita permisă de 10 MiB.")
    if _contains_doctype_declaration(xml_content):
        raise XmlSecurityError("Documentele XML cu DOCTYPE nu sunt acceptate.")

    parser = etree.XMLParser(
        resolve_entities=False,
        load_dtd=False,
        no_network=True,
        recover=False,
        huge_tree=False,
    )
    try:
        root = etree.fromstring(xml_content, parser=parser)
    except (etree.XMLSyntaxError, ValueError, OSError):
        raise MalformedXmlError("Documentul XML nu este bine format.") from None

    if root.getroottree().docinfo.doctype:
        raise XmlSecurityError("Documentele XML cu DOCTYPE nu sunt acceptate.")
    if any(element.tag == _qname(XINCLUDE_NS, "include") for element in root.iter()):
        raise XmlSecurityError("Documentele XML cu XInclude nu sunt acceptate.")
    if root.tag != _qname(INVOICE_NS, "Invoice"):
        raise UnsupportedDocumentError("Tipul sau namespace-ul documentului XML nu este suportat.")

    invoice_id = _required_text(root, "ID", "Invoice/ID")
    issue_date = _required_text(root, "IssueDate", "Invoice/IssueDate")
    currency = _required_text(root, "DocumentCurrencyCode", "Invoice/DocumentCurrencyCode")

    invoice_line_elements = _children(root, CAC_NS, "InvoiceLine")
    if not invoice_line_elements:
        raise MissingRequiredFieldError("Lipsește câmpul obligatoriu: InvoiceLine.")

    legal_total_element = _optional_element(
        root, CAC_NS, "LegalMonetaryTotal", "LegalMonetaryTotal"
    )
    return Invoice(
        invoice_id=invoice_id,
        issue_date=issue_date,
        due_date=_optional_text(root, "DueDate", "Invoice/DueDate"),
        invoice_type_code=_optional_text(root, "InvoiceTypeCode", "Invoice/InvoiceTypeCode"),
        document_currency_code=currency,
        tax_currency_code=_optional_text(root, "TaxCurrencyCode", "Invoice/TaxCurrencyCode"),
        supplier=_required_role_party(root, "AccountingSupplierParty"),
        customer=_required_role_party(root, "AccountingCustomerParty"),
        lines=tuple(_parse_invoice_line(item, index) for index, item in enumerate(invoice_line_elements, 1)),
        tax_totals=tuple(
            _parse_tax_total(item) for item in _children(root, CAC_NS, "TaxTotal")
        ),
        legal_monetary_total=_parse_legal_monetary_total(legal_total_element),
        payment_means=tuple(
            _parse_payment_means(item) for item in _children(root, CAC_NS, "PaymentMeans")
        ),
        deliveries=tuple(
            _parse_delivery(item) for item in _children(root, CAC_NS, "Delivery")
        ),
    )
