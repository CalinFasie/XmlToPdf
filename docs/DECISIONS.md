# XmlToPdf — Registrul deciziilor

> **Statut:** Deciziile de mai jos reflectă acordurile exprimate în explorarea proiectului.<br>
> **Data:** 2026-10-20<br>
> **Repository:** `https://github.com/CalinFasie/XmlToPdf`<br>
> **Vezi și:** `docs/REQUIREMENTS.md`

## Convenții

- **Confirmată:** decizie agreată; schimbarea necesită discuție explicită.
- **Planificată:** direcție agreată, detalii de implementare încă deschise.
- **Deschisă:** nu există încă decizie.

## Decizii confirmate

| ID | Decizie | Motiv și implicații | Stare |
|---|---|---|---|
| D-01 | Aplicația este **web locală**, folosită pe Windows, nu site public. | Evităm hostingul și păstrăm procesarea pe calculatorul utilizatorului. | Confirmată |
| D-02 | Backend Python, cu **Flask**. | Un server local simplu poate primi XML-ul și furniza HTML. | Confirmată |
| D-03 | Parsare XML cu **lxml** și prezentare cu **Jinja2 + HTML/CSS**. | Separăm interpretarea UBL de aspectul documentului. | Confirmată |
| D-04 | Factura se vizualizează ca HTML în **Microsoft Edge pe Windows**, browserul țintă pentru acceptarea MVP. | Nu trebuie creat PDF pentru consultare; alte browsere nu au criteriu de fidelitate pentru MVP. | Confirmată |
| D-05 | PDF-ul se obține la cerere prin **Print / Save as PDF** din browser. | În MVP nu este necesar un motor PDF în backend. | Confirmată |
| D-06 | Funcționarea după instalare este **offline**, fără ANAF sau resurse web externe. | Scopul principal este independența de disponibilitatea serviciului ANAF. | Confirmată |
| D-07 | Numărul de linii este variabil; imprimarea necesită **paginare automată**. | Tabelele pot continua pe mai multe pagini și nu trebuie să piardă linii. | Confirmată |
| D-08 | Layoutul de imprimare pornește de la **A4 landscape**. | PDF-ul ANAF este referință orientativă, nu model pixel-perfect. | Confirmată |
| D-09 | **Fără bază de date, istoric sau stocare permanentă intenționată** a facturilor în MVP. | Păstrăm aplicația mică și reducem expunerea datelor. | Confirmată |
| D-10 | Dezvoltare agentică prin **Codex**, cu Git și GitHub. | Instrucțiunile proiectului și schimbările trebuie să poată fi auditate. | Confirmată |
| D-11 | Sumele și celelalte valori financiare se afișează **așa cum sunt în XML**; nu se emit avertizări de reconciliere și nu se blochează imprimarea pentru diferențe aritmetice. | XmlToPdf este vizualizator, nu validator sau corector fiscal. Erorile de structură XML rămân tratate separat. | Confirmată |
| D-12 | **Fidelitatea PDF între browsere nu este obiectivul MVP.** | Este suficient un flux de imprimare funcțional și lizibil în Microsoft Edge pe Windows; nu cerem identitate între Edge/Chrome. | Confirmată |
| D-13 | Launcherul de distribuție este un EXE Windows cu consolă, împachetat portabil cu **PyInstaller `--onedir`**. | Folderul complet `dist/XmlToPdf` include runtime-ul Python, dependențele și resursele aplicației; calculatorul țintă trebuie să aibă Microsoft Edge, dar nu Python separat. MSI, `--onefile`, servicii și pornirea la logare rămân în afara domeniului. | Confirmată |
| D-14 | XML-ul trebuie să fie bine format, să aibă QName-ul UBL `Invoice` și să îndeplinească setul minim de câmpuri necesare afișării. | Definește când parserul poate produce o factură lizibilă fără a pretinde validare XSD sau fiscală; detaliile sunt în FR-04 din `REQUIREMENTS.md`. | Confirmată |
| D-15 | Textul zecimal al sumelor se păstrează la afișare după eliminarea spațiilor exterioare. | Nu se localizează separatorul, nu se adaugă separatori de mii, nu se rotunjește și nu se recalculează; moneda se afișează separat. | Confirmată |
| D-16 | Corpul cererii de încărcare are o limită maximă de **10 MiB (10 × 1.024 × 1.024 = 10.485.760 octeți)**. | Cererile peste limită se resping înainte de parsarea XML; limita reduce consumul necontrolat de memorie și timp. | Confirmată |

## Decizii deliberate de neimplementare în MVP

- Nu dezvoltăm un serviciu ANAF/SPV și nu trimitem documente către ANAF.
- Nu construim un validator fiscal complet XSD/EN 16931/RO_CIUS.
- Nu edităm datele facturilor și nu corectăm sume.
- Nu dezvoltăm interfață desktop nativă, WebView încorporat sau vizualizator PDF separat.
- Nu introducem încă motor PDF dedicat în Python.
- Nu implementăm acum `CreditNote`, procesare în loturi, șabloane administrabile, autentificare sau istoric.
- Nu încercăm reproducerea pixel cu pixel a PDF-ului furnizat ca referință.

## Întrebări încă deschise

| ID | Întrebare | Când o rezolvăm |
|---|---|---|
| O-05 | Ce câmpuri secundare intră în layoutul inițial? | În etapa de mapare UBL–HTML. |
| O-06 | Ce reguli exacte de rupere a paginii și numerotare funcționează în Microsoft Edge? | În prototipul CSS de imprimare. |

**Decizii închise:** O-01 s-a închis prin D-13. O-03 s-a închis cu plafonul de 10 MiB din D-16; O-07 s-a închis cu setul minim din D-14/FR-04; fosta O-02 (identitate PDF între browsere) și fosta O-04 (avertizări/blocare la reconciliere) rămân închise conform D-11/D-12. O-05 și O-06 rămân deschise.

## Referințe

- `docs/REQUIREMENTS.md` este sursa cerințelor și criteriilor de acceptare.
- `7004378.xml` și `7004378.pdf` sunt documente locale de referință; pot conține date reale, deci **nu se includ în repository-ul public**.
- Capturile interfeței ANAF sunt exemple orientative, nu specificații obligatorii de interfață.

## Modificarea deciziilor

O decizie confirmată se schimbă numai după acord explicit. Actualizează întâi acest fișier și `docs/REQUIREMENTS.md`, apoi implementează schimbarea într-un task separat, cu teste acolo unde este cazul.
