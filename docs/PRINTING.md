# Imprimare și salvare PDF

## Fluxul utilizatorului

După acceptarea XML-ului, ruta existentă de încărcare randează din același obiect `Invoice` atât prezentarea obișnuită pentru ecran, cât și prezentarea compactă pentru imprimare. Pagina afișează numai versiunea de ecran; `@media print` o ascunde și afișează șablonul dedicat de imprimare. Nu există parser, rută de încărcare sau generator PDF separat.

Butonul „Tipărește / Salvează PDF” este disponibil numai pentru o factură acceptată și apelează `window.print()` la clicul utilizatorului. Aplicația nu generează PDF pe server și nu persistă factura sau PDF-ul. Utilizatorul poate selecta „Save as PDF” în dialogul Microsoft Edge.

## Organizarea pentru imprimare

Șablonul `src/xmltopdf/templates/invoice_print.html`, inclus prin `invoice_bundle.html`, folosește același model ca șablonul de ecran `invoice.html`. Stilurile dedicate se află în `src/xmltopdf/static/css/app.css`, sub `@media print`.

Versiunea de imprimare urmează această ordine:

1. antet compact în trei coloane pentru furnizor, datele facturii și client;
2. tabel orizontal cu toate valorile `LegalMonetaryTotal` disponibile;
3. totalul TVA și fiecare subtotal cu valorile, categoria, procentul și motivele existente;
4. tabelul tuturor liniilor, în ordinea XML, cu denumiri/descrieri, identificatori, cantități și unități, prețuri, valori nete și clasificarea TVA;
5. toate metodele de plată, conturile și informațiile de livrare, în secțiuni compacte alăturate.

Valorile și atributele expuse de model sunt randate prin Jinja2, care escapează conținutul XML. Sumele păstrează textul zecimal și moneda; nu se recalculează, rotunjesc sau localizează. Versiunea de ecran rămâne neschimbată ca structură și stil.

## Format și reguli CSS

CSS-ul solicită `@page { size: A4 landscape; margin: 8mm; }`. Aceasta este dimensiunea cerută de pagină, nu o garanție: destinația, driverul și setările dialogului de imprimare pot schimba hârtia, orientarea, marginile ori scalarea.

Stilurile de imprimare:

- ascund controalele aplicației și versiunea de ecran, apoi afișează versiunea dedicată pentru hârtie;
- folosesc fundal alb, fără umbre și chenare decorative imbricate;
- așază furnizorul și clientul de o parte și de alta a datelor facturii;
- grupează totalurile într-un tabel orizontal și păstrează detaliile TVA în rânduri compacte;
- permit antetului tabelului de linii să se repete în paginile următoare, în măsura în care motorul Edge aplică regula;
- evită fragmentarea unui rând de linie care încape pe pagină, dar lasă tabelul și secțiunile să continue pe pagini;
- nu folosesc scalare CSS forțată, înălțimi fixe, text ascuns sau `overflow: hidden` pentru a încadra conținutul.

Fontul general pentru versiunea tipărită este 9 pt, iar celulele tabelului de linii 8,5 pt. Pentru facturi cu multe câmpuri sau descrieri lungi, documentul poate avea mai multe pagini.

## Verificare automată și manuală

Testele folosesc XML sintetic și verifică șablonul separat, escaparea HTML, păstrarea valorilor financiare și a câmpurilor, precum și afișarea tuturor liniilor sintetice cu 1, 10, 30 și 100 de poziții. Aceste teste nu determină numărul de pagini PDF.

Pentru verificarea manuală în Edge, folosește exclusiv un XML sintetic echivalent structural cu o factură scurtă: 2 linii, 2 metode de plată, subtotaluri TVA, totaluri, furnizor, client și livrare. Criteriul acestei iterații este exact o pagină A4 landscape, lizibilă și completă, fără informații tăiate. Același layout trebuie verificat cu 1, 10, 30 și 100 de linii, descrieri lungi cu diacritice, mai multe subtotaluri TVA și metode de plată; facturile mari trebuie să continue pe pagini fără omisiuni.

În Print Preview, verifică:

1. Paper size: **A4**.
2. Layout: **Landscape**.
3. Margins: **Default** sau setarea care păstrează marginile CSS solicitate.
4. Scale: **Default** sau **100%**; nu ajusta pentru a ascunde ori tăia conținut.
5. Headers and footers: dezactivate dacă nu dorești elementele adăugate de browser.
6. Numărul de pagini, lizibilitatea, toate câmpurile și absența tăierilor ori suprapunerilor.

**Stare de verificare:** testele automate pot confirma conținutul și structura HTML, dar Edge nu a produs un PDF în verificarea headless disponibilă anterior (procesul s-a încheiat cu `0xC0000005`). Nu există o măsurare Edge nouă pentru șablonul dedicat; nu se afirmă că rezultatul de o pagină a fost atins. O-06 rămâne deschisă până la verificarea manuală în Microsoft Edge și confirmarea utilizatorului.
