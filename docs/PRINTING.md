# Imprimare și salvare PDF

## Fluxul utilizatorului

Butonul „Tipărește / Salvează PDF” este inclus în fragmentul facturii numai după ce XML-ul a fost acceptat și randat. Butonul apelează `window.print()` numai la clicul utilizatorului. La trimiterea unui nou XML, conținutul anterior este eliminat înaintea cererii; la eroare nu se inserează factura anterioară și butonul ei de imprimare nu rămâne disponibil.

Aplicația nu generează PDF pe server, nu oferă un endpoint PDF și nu persistă factura sau PDF-ul. Dialogul browserului permite imprimarea sau alegerea opțiunii „Save as PDF”. Browserul vizat este Microsoft Edge pe Windows.

## CSS de imprimare

`src/xmltopdf/static/css/app.css` solicită prin `@page` formatul `A4 landscape` și margini de `10mm`. Aceasta este o indicație CSS, nu o garanție asupra hârtiei folosite: destinația aleasă (Save as PDF sau imprimantă), driverul, formatele disponibile și setările dialogului de imprimare pot schimba dimensiunea efectivă, orientarea, marginile și scalarea.

În `@media print`:

- antetul aplicației, selectorul de fișier, mesajele de status și butonul de imprimare sunt ascunse;
- rămâne vizibil conținutul din `#invoice-container`, cu fundal alb explicit și fără umbre sau stilul de card al ecranului; textul și fundalurile nu depind de imprimarea fundalurilor colorate;
- se reduc marginile și paddingurile la secțiuni și carduri imbricate; datele rămân afișate, iar blocurile mari se pot fragmenta când este nevoie;
- clasificarea TVA de pe o linie apare o singură dată, în format compact, cu etichete scurte; codurile, procentele, schema fiscală, motivele și atributele disponibile rămân vizibile;
- rândurile individuale ale tabelului evită ruperea între pagini, dacă încap pe o pagină; tabelul și secțiunile mari rămân fragmentabile;
- valorile TVA și totalurile folosesc eticheta, suma și moneda împreună când există spațiu; metodele de plată multiple sunt dispuse în două coloane la imprimare, iar câmpurile de plată/livrare folosesc spațiere compactă;
- se folosește tip de 9 pt pentru textul general și 8,5 pt în tabel, cu etichete mai mici, dar lizibile;
- `.table-scroll` nu mai decupează pe orizontală; tabelul are lățime de 100%, fără `min-width: 820px`, iar coloanele pot încadra textul lung;
- `<thead>` este declarat `table-header-group` pentru repetarea antetului tabelului în paginile următoare, în măsura suportului Edge;
- tabelul și secțiunile mari pot fi fragmentate. `break-inside: avoid` se limitează la un rând individual, pentru a păstra împreună liniile care încap pe pagină; nu se aplică întregului tabel, secțiunilor sau cardurilor de plată/livrare;
- titlurile evită, pe cât permite motorul de imprimare, să rămână singure la sfârșitul paginii; nu se adaugă numerotare ori subsoluri artificiale.

Stilurile nu ascund linii și nu reduc setul de câmpuri din HTML. Repetarea antetului tabelului și afișarea tuturor liniilor sunt păstrate. Pentru un document sintetic cu două linii, ținta este de cel mult două pagini A4 landscape, fără o pagină finală care conține doar adresa din cauza spațierii evitabile; rezultatul trebuie măsurat în Edge și nu este garantat pentru orice conținut sau destinație de imprimare.

## Setări și verificare manuală

În Edge Print Preview, verifică următoarele setări:

1. Paper size: **A4**.
2. Layout: **Landscape**.
3. Margins: **Default**, pentru a păstra marginea CSS de 10 mm.
4. Scale: **Default** sau **100%**; ajustează numai dacă previzualizarea taie coloane.
5. Headers and footers: dezactivate pentru a evita URL-ul și data adăugate de browser.
6. Confirmă că print preview include numai factura și că butonul și formularul nu apar.

Pentru acceptare, verifică facturi exclusiv sintetice cu 1, 2, 10, 30 și 100 de linii, descrieri lungi cu diacritice, mai multe subtotaluri TVA și mai multe metode de plată. Derulează Print Preview pe toate paginile și confirmă că toate liniile apar în ordine, antetul tabelului se repetă unde permite Edge, coloanele nu sunt tăiate și nu există pagini goale. Salvează un PDF sintetic prin dialog și verifică paginile rezultate. În special, verifică faptul că documentul cu două linii rămâne lizibil și că livrarea nu este împinsă singură pe ultima pagină de paddinguri sau de reguli de evitare a ruperii.

Verificările manuale raportate de utilizator au produs mai întâi patru pagini, apoi trei pagini pentru documentul cu două linii, cu conținutul ultimei metode de plată și livrarea pe pagina a treia. Numărul de pagini pentru această schimbare se consemnează doar după o nouă măsurare efectivă în Edge.

**Starea acestei versiuni:** testele automate verifică markup-ul, păstrarea tuturor valorilor și atributelor TVA sintetice, liniile pentru 1, 2, 10, 30 și 100 de poziții, moneda lângă sumele și regulile CSS. Încercarea de tipărire Edge headless cu date sintetice s-a încheiat cu codul `0xC0000005` înainte de crearea PDF-ului; numărul de pagini nu a putut fi măsurat. O-06 rămâne deschisă până la verificarea efectivă a paginării și a fragmentării în Microsoft Edge.

Setările de imprimare pot suprascrie dimensiunea, orientarea, marginile, scalarea, antetele și subsolurile CSS. Aspectul și paginarea pot varia cu versiunea Edge, driverul imprimantei, destinația și opțiunile dialogului. `@page { size: A4 landscape; }` definește formatul solicitat de pagină; configurarea efectivă a destinației rămâne determinantă.
