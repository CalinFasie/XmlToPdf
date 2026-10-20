# Imprimare și salvare PDF

## Fluxul utilizatorului

Butonul „Tipărește / Salvează PDF” este inclus în fragmentul facturii numai după ce XML-ul a fost acceptat și randat. Butonul apelează `window.print()` numai la clicul utilizatorului. La trimiterea unui nou XML, conținutul anterior este eliminat înaintea cererii; la eroare nu se inserează factura anterioară și butonul ei de imprimare nu rămâne disponibil.

Aplicația nu generează PDF pe server, nu oferă un endpoint PDF și nu persistă factura sau PDF-ul. Dialogul browserului permite imprimarea sau alegerea opțiunii „Save as PDF”. Browserul vizat este Microsoft Edge pe Windows.

## CSS de imprimare

`src/xmltopdf/static/css/app.css` definește `@page` cu `A4 landscape` și margini de `10mm`. În `@media print`:

- antetul aplicației, selectorul de fișier, mesajele de status și butonul de imprimare sunt ascunse;
- rămâne vizibil conținutul din `#invoice-container`, fără fundal de pagină, umbre sau stilul de card al ecranului;
- `.table-scroll` nu mai decupează pe orizontală; tabelul are lățime de 100%, fără `min-width: 820px`, iar coloanele pot încadra textul lung;
- `<thead>` este declarat `table-header-group` pentru repetarea antetului tabelului în paginile următoare, în măsura suportului Edge;
- tabelul, rândurile și secțiunile mari pot fi fragmentate. Nu se aplică `break-inside: avoid` întregului tabel sau blocurilor care pot depăși pagina;
- titlurile evită, pe cât permite motorul de imprimare, să rămână singure la sfârșitul paginii; nu se adaugă numerotare ori subsoluri artificiale.

Stilurile nu ascund linii și nu reduc setul de câmpuri din HTML. Edge și setările imprimantei pot influența încadrarea și fragmentarea conținutului.

## Setări și verificare manuală

În Edge Print Preview, verifică următoarele setări:

1. Paper size: **A4**.
2. Layout: **Landscape**.
3. Margins: **Default**, pentru a păstra marginea CSS de 10 mm.
4. Scale: **Default** sau **100%**; ajustează numai dacă previzualizarea taie coloane.
5. Headers and footers: dezactivate pentru a evita URL-ul și data adăugate de browser.
6. Confirmă că print preview include numai factura și că butonul și formularul nu apar.

Pentru acceptare, verifică facturi exclusiv sintetice cu 1, 10, 30 și 100 de linii, descrieri lungi cu diacritice, mai multe subtotaluri TVA și mai multe metode de plată. Derulează Print Preview pe toate paginile și confirmă că toate liniile apar în ordine, antetul tabelului se repetă unde permite Edge, coloanele nu sunt tăiate și nu există pagini goale. Salvează un PDF sintetic prin dialog și verifică paginile rezultate.

**Starea acestei versiuni:** testele automate verifică markup-ul, starea butonului, regulile CSS și lipsa regulilor care ascund liniile. Verificarea practică în Edge Print Preview și inspectarea PDF-urilor salvate nu au fost executate; rezultatele vizuale nu sunt declarate ca trecute. O-06 rămâne deschisă până la această verificare.

Setările de imprimare pot suprascrie dimensiunea, orientarea, marginile, scalarea, antetele și subsolurile CSS. Aspectul poate varia cu versiunea Edge, driverul imprimantei și opțiunea de imprimare a fundalurilor.
