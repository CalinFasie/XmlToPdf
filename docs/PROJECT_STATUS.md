# Stadiul proiectului XmlToPdf

**Ultima actualizare:** 2026-10-22<br>
**Repository:** [CalinFasie/XmlToPdf](https://github.com/CalinFasie/XmlToPdf)

## Stadiul actual

- **Versiune publicată:** [v0.1.0 — Windows](https://github.com/CalinFasie/XmlToPdf/releases/tag/v0.1.0), construită din commitul `3af565f67299b4a9e9c7d5d923acbf846fdc6bdc`.
- **Ultimul milestone:** distribuția Windows onefile a fost validată de utilizator pe două calculatoare Windows.
- **Teste la publicare:** 131 teste automate trecute.
- **Decizii deschise:** O-05 și O-06 rămân deschise în [`docs/DECISIONS.md`](DECISIONS.md); nu se consideră rezolvate fără aprobare și dovezi corespunzătoare.

## Ce este XmlToPdf

XmlToPdf a fost creat pentru a permite vizualizarea locală, într-un format lizibil de factură, a documentelor românești e-Factura UBL `Invoice`. Utilizatorul poate imprima factura sau o poate salva ca PDF din dialogul Microsoft Edge, independent de disponibilitatea ANAF. XML-ul este procesat local, iar aplicația nu generează PDF în backend.

## Arhitectura actuală

- Python și Flask furnizează aplicația web; serverul ascultă exclusiv pe `127.0.0.1`.
- `lxml` parsează UBL `Invoice` într-un model Python intern, separat de Flask și prezentare.
- Jinja2 produce HTML semantic, iar CSS-ul local separă vizualizarea pe ecran de șablonul de imprimare.
- PDF-ul se obține numai prin Print / Save as PDF din Microsoft Edge; CSS-ul țintește A4 Landscape.
- PyInstaller `--onefile`, fără consolă, distribuie aplicația Windows împreună cu runtime-ul Python și resursele locale.
- Launcherul deschide o fereastră Edge dedicată cu profil temporar. Oprirea comună se poate declanșa din X-ul ferestrei, din butonul web sau din system tray.
- XML-ul încărcat este limitat la 10 MiB, procesat în memorie și protejat de verificările XML și HTTP documentate în [`docs/REQUIREMENTS.md`](REQUIREMENTS.md).

## Evoluția implementării

| Task | Obiectiv | Rezultat |
|---|---|---|
| 001 | Fundația Flask | Aplicație locală minimală, pornire doar pe loopback și teste pentru ruta principală. |
| 002 | Parser și model UBL | Parser `Invoice` securizat cu lxml și model intern tipizat; elementele repetate și valorile declarate sunt păstrate. |
| 003 | Încărcare XML securizată | Integrare Flask pentru procesare în memorie, cu plafon de 10 MiB și controale Host, Origin și CSRF. |
| 004 | Redarea HTML a facturii | Șabloane Jinja2 pentru datele modelului, cu escapare HTML și tratarea câmpurilor opționale. |
| 005 | Imprimare și prezentare compactă | Șablon A4 Landscape separat și afișare web compactă. Factura scurtă de referință a fost verificată pe o pagină; paginarea lungă rămâne deschisă. |
| 006 | Launcher Windows | EXE portabil onefile fără consolă, Edge dedicat și oprire controlată din X, web sau tray. |
| 007 | Pregătire distribuție | Instrucțiuni pentru utilizator/dezvoltator, build și verificarea SHA-256. |
| 008 | Release v0.1.0 | Pachetul Windows și checksum-ul au fost publicate în GitHub Release. |

### Lecții tehnice din Task 006

Varianta inițială `onedir` nu îndeplinea cerința distribuției într-un singur EXE portabil; soluția a trecut la PyInstaller `onefile`, fără consolă. Pentru ca închiderea browserului să fie fiabilă, launcherul folosește o fereastră Edge dedicată, identificată prin sesiunea și HWND-ul ei, nu monitorizarea tuturor proceselor Edge sau durata procesului inițial pornit.

Cele trei căi de închidere au fost reunite într-o secvență comună, controlată și idempotentă, care eliberează serverul local. Testele automate și validarea manuală pe două calculatoare au confirmat funcționarea distribuției și a metodelor de oprire.

## Decizii esențiale

- Aplicația rămâne locală, offline după instalare și orientată spre Windows/Edge.
- XML-ul este sursa de adevăr: sumele se afișează textual, fără recalculare, rotunjire sau reconciliere.
- Parserul, modelul, HTTP-ul și prezentarea sunt separate; XML-ul este tratat ca intrare neîncredere.
- PDF-ul se obține prin browser. Nu există backend PDF, integrare ANAF sau validare fiscală completă.

Acesta este un rezumat, nu un registru nou. Deciziile și stările lor autoritative se află în [`docs/DECISIONS.md`](DECISIONS.md).

## Limitări cunoscute

- **O-06 — paginarea facturilor lungi:** sunt necesare teste multipagină mai ample cu documente sintetice. Validarea unei facturi scurte pe o pagină nu închide O-06.
- **O-05 — câmpurile secundare:** selecția și prezentarea tuturor câmpurilor secundare rămân deschise, chiar dacă modelul și șabloanele afișează deja multe câmpuri opționale.
- Nu există integrare ANAF/SPV, validator fiscal/XSD complet sau motor de generare PDF în backend.
- Distribuția publicată necesită Windows și Microsoft Edge. Python nu trebuie instalat separat pentru EXE.

## Următoarea etapă recomandată

Validează O-06 folosind facturi exclusiv sintetice cu 1, 2, 10, 30 și 100 de linii, descrieri lungi și conținut repetabil. Verifică Print Preview și PDF-ul rezultat în Edge, inclusiv ruperile dintre pagini, repetarea antetului, vizibilitatea tuturor liniilor și poziționarea totalurilor/plăților/livrării. Înregistrează rezultatele în [`docs/PRINTING.md`](PRINTING.md) și actualizează acest status.

Orice modificare viitoare a layoutului de imprimare trebuie să aibă teste de regresie și verificare practică multipagină înainte de acceptare. Păstrează O-06 deschisă până când criteriile sunt îndeplinite și decizia este aprobată explicit.
