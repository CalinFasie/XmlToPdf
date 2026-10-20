# Mapare UBL–HTML — propunere pentru Task 004

Acest document descrie maparea folosită de prototipul HTML. Este o propunere de prezentare, fără interpretări sau calcule fiscale noi. **O-05 rămâne deschisă** până la review-ul utilizatorului.

## Reguli generale

- Sursa afișării este modelul `Invoice` rezultat din `parse_invoice`; șablonul nu interpretează XML și nu caută elemente UBL.
- Valorile `UblText`, `Amount` și `Quantity` sunt afișate numai când au conținut disponibil. Câmpurile absente sunt omise, fără substituenți precum `0`, `N/A` sau `-`.
- `Amount.value` și `Quantity.value` păstrează textul din model. `currency_id` și `unit_code` sunt afișate separat, alături de valoare. Atributele suplimentare reținute de model sunt prezentate ca metadate.
- Secvențele și aparițiile repetate sunt păstrate în ordinea XML; interfața le numerotează numai pentru a le distinge vizual.
- Datele provenite din UBL sunt inserate prin escaparea automată Jinja2. Șabloanele nu folosesc filtrul `safe` pentru date.

## Antet și părți

| Model intern | Prezentare HTML |
|---|---|
| `Invoice.invoice_id`, `issue_date`, `due_date`, `invoice_type_code`, `document_currency_code`, `tax_currency_code` | Titlul și zona de metadate a facturii; datele opționale lipsă sunt omise. |
| `Invoice.supplier`, `Invoice.customer` | Carduri distincte Furnizor și Client. |
| `Party.party_names`, `Party.endpoint_ids` | Denumirile și identificatorii electronici, fiecare apariție separat. |
| `Party.identifications[].id` | Identificare comercială; atributele, inclusiv schemele disponibile, rămân lângă valoare. |
| `Party.legal_entities[]` | Denumire legală, identificator companie, formă juridică și codul formei juridice. |
| `Party.tax_schemes[]` | Identificator fiscal și câmpurile disponibile ale schemei fiscale. |
| `Party.postal_addresses[]` / `Address` | Câmpurile adresei separat: identificator, stradă, detaliu suplimentar, număr, localitate, cod poștal, regiune, fiecare linie de adresă și țara. |
| `Party.contacts[]` / `Contact` | Identificator, persoană, telefon, fax, e-mail și notă de contact. |

## Linii, preț și TVA

| Model intern | Prezentare HTML |
|---|---|
| `Invoice.lines[]` / `InvoiceLine` | Tabel în ordinea XML, cu identificator, articol/descriere, cantitate, preț, valoare netă și clasificare TVA. |
| `InvoiceLine.item.names[]`, `descriptions[]` | Toate denumirile și descrierile articolului, pe rânduri distincte. Textul lung se încadrează și păstrează liniile noi. |
| `Item.sellers_item_identification`, `standard_item_identification` | Cod articol furnizor și identificator standard, când există. |
| `InvoiceLine.invoiced_quantity` | Textul cantității și `unit_code` distinct. |
| `InvoiceLine.price.price_amount`, `base_quantity` | Prețul unitar cu moneda declarată și baza prețului cu unitatea declarată. |
| `InvoiceLine.line_extension_amount` | Valoarea netă, păstrată textual, cu moneda declarată separat. |
| `Item.classified_tax_categories[]` / `TaxCategory` | Categoria, denumirea, procentul, codul și motivele de scutire și câmpurile schemei fiscale. |
| `InvoiceLine.tax_totals[]` | Totalurile TVA de linie și toate subtotalurile lor, inclusiv valorile, procentele, baza/unitatea, intervalele și categoria TVA disponibile. |

## TVA și totaluri document

| Model intern | Prezentare HTML |
|---|---|
| `Invoice.tax_totals[]` / `TaxTotal` | Fiecare total TVA în secțiunea TVA a documentului; include valoarea, rotunjirea și toate subtotalurile. |
| `TaxSubtotal` | Bază impozabilă, TVA, ordine de calcul, TVA în moneda tranzacției, procent, măsură și valoare pe unitate, intervale și categoria asociată. |
| `Invoice.legal_monetary_total` / `LegalMonetaryTotal` | Valoare netă linii, total fără TVA, total cu TVA, reduceri, costuri suplimentare, plăți în avans, rotunjire la plată și suma de plată. |

Nicio valoare financiară nu este recalculată, rotunjită, localizată sau reconciliată. Moneda fiecărei sume provine din obiectul `Amount` corespunzător.

## Plată și livrare

| Model intern | Prezentare HTML |
|---|---|
| `Invoice.payment_means[]` / `PaymentMeans` | Toate mijloacele de plată, cu cod, scadență, canal, identificatorul instrucțiunii, fiecare notă și fiecare referință de plată. |
| `payee_financial_account`, `payer_financial_account` / `FinancialAccount` | Identificator/IBAN, denumire, tip de cont, monedă, instituție financiară și sucursală, când există. |
| `Invoice.deliveries[]` / `Delivery` | Data și ora fiecărei livrări, destinatarul și locul de livrare. |
| `Delivery.delivery_party` / `Party` | Aceleași câmpuri de parte și adresă, sub titlul Destinatar. |
| `Delivery.delivery_location` / `DeliveryLocation` | Identificatorul și toate descrierile locației, plus adresa disponibilă. |

## Domeniu vizual curent

Șablonul oferă o vizualizare HTML lizibilă și adaptabilă pentru ecran. Stilurile finale de imprimare A4, paginarea fizică și numerotarea paginilor nu fac parte din Task 004.
