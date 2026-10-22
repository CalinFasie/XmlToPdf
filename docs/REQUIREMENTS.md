# XmlToPdf — Cerințe pentru prima versiune

> **Statut:** Draft consolidat; fundația Flask, parserul UBL, modelul intern, încărcarea XML securizată, afișarea HTML, fluxul de imprimare din browser și launcherul Windows onefile cu system tray sunt implementate<br>
> **Versiune document:** 0.3<br>
> **Data:** 2026-10-20<br>
> **Cale propusă în repository:** `docs/REQUIREMENTS.md`<br>
> **Repository:** `https://github.com/CalinFasie/XmlToPdf`<br>
> **Mediu principal:** Windows, aplicație web locală

## 1. Scop

XmlToPdf permite consultarea locală, în browser, a unei facturi românești e-Factura reprezentate ca XML UBL, într-un format clasic, lizibil. Utilizatorul poate imprima factura sau o poate salva ca PDF **numai prin acțiune explicită**, utilizând dialogul de imprimare al browserului.

Motivul proiectului este independența față de disponibilitatea conversiei oferite de ANAF și posibilitatea unor personalizări viitoare. Nu urmărim reproducerea identică pixel cu pixel a PDF-ului ANAF.

**Principiu:** XML-ul este sursa datelor; HTML-ul este reprezentarea vizuală; PDF-ul este un rezultat opțional al imprimării din browser.

## 2. Decizii confirmate

| ID | Decizie |
|---|---|
| D-01 | Aplicație web **locală**, utilizată pe Windows. |
| D-02 | Procesare în **Python**, cu **Flask** pentru serverul local. |
| D-03 | **lxml** pentru parsare XML UBL; **Jinja2 + HTML/CSS** pentru afișare. |
| D-04 | Microsoft Edge pe Windows este browserul țintă pentru acceptarea MVP; factura este afișată ca HTML, fără vizualizator PDF integrat. |
| D-05 | **Imprimare / Save as PDF** prin dialogul browserului, nu prin generarea unui PDF în backend în prima versiune. |
| D-06 | Funcționare **offline** după instalarea dependențelor. Fără ANAF, hosting public sau servicii externe. |
| D-07 | Numărul de linii de factură este variabil; paginarea documentului tipărit este automată. |
| D-08 | Aspectul inițial de imprimare este **A4 landscape**, inspirat de PDF-ul ANAF furnizat. |
| D-09 | Nu sunt necesare bază de date, istoric al documentelor ori stocare permanentă a facturilor. |
| D-10 | Dezvoltare cu **Codex**, cod versionat în Git/GitHub. |
| D-11 | Valorile financiare se afișează așa cum sunt declarate în XML. Diferențele aritmetice nu produc avertizări, nu modifică sumele și nu blochează vizualizarea sau imprimarea. |
| D-12 | Nu urmărim reproducerea identică a PDF-ului între browsere, versiuni sau configurații de imprimare; pentru MVP vizăm funcționarea în Microsoft Edge pe Windows. |
| D-14 | XML-ul este acceptat numai dacă este bine format, are QName-ul UBL `Invoice` și îndeplinește condițiile minime din FR-04; acestea sunt reguli de afișare, nu validare XSD/fiscală. |
| D-15 | Textul zecimal al sumelor se afișează ca în XML după eliminarea spațiilor exterioare; nu se localizează, rotunjește, recalculează și nu se schimbă separatorul sau zerourile zecimale. |
| D-16 | Corpul cererii de încărcare este limitat la 10 MiB (10 × 1.024 × 1.024 = 10.485.760 octeți); cererile mai mari sunt respinse înainte de parsare. |

Alegerea bibliotecilor este o direcție tehnică pentru MVP, nu o justificare pentru adăugarea unor componente suplimentare.

**D-13 confirmată:** launcherul Windows este un singur EXE PyInstaller `--onefile`, fără consolă, cu oprire controlată din interfața web locală, system tray sau prin închiderea ferestrei Edge dedicate lansate cu `--app`. Fereastra folosește un director de profil temporar unic, separat de profilul obișnuit Edge; închiderea filei, refresh-ul, minimizarea și dialogul Print nu declanșează oprirea. Microsoft Edge trebuie instalat pe calculatorul țintă, Python separat nu este necesar. Pornirea poate dura mai mult din cauza extragerii temporare a componentelor PyInstaller. XML-urile încărcate rămân în memorie și nu sunt salvate intenționat în profilul Edge sau directorul de extragere. Edge poate crea acolo cache, cookie-uri, stare de sesiune, preferințe și fișiere de diagnostic. Launcherul șterge numai profilurile marcate ca fiind create de el și numai după ce procesele Edge nu le mai folosesc; dacă Edge rămâne activ după oprirea din pagină/tray, profilul poate rămâne temporar și este curățat la următoarea pornire când nu mai rulează procese Edge. Modul de dezvoltare `python -m xmltopdf` nu oferă oprirea procesului prin HTTP și nu lansează Edge dedicat. Detaliile sunt în `docs/WINDOWS_DISTRIBUTION.md`.

## 3. Domeniul primei versiuni (MVP)

### 3.1. Intrare

- **FR-01 — Selectare XML.** Utilizatorul poate alege prin browser un fișier XML local și îi transmite conținutul serverului de pe propriul calculator. Corpul cererii nu poate depăși 10 MiB (10.485.760 octeți).
- **FR-02 — Tip de document.** MVP-ul acceptă numai QName-ul `{urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}Invoice`, indiferent de prefixul XML folosit. Documentele `CreditNote`, un `Invoice` din alt namespace sau tipurile necunoscute primesc un mesaj de „tip nesuportat”; nu sunt interpretate ca facturi obișnuite.
- **FR-03 — Parsare corectă.** Interpretarea elementelor UBL folosește URI-urile namespace-urilor, nu presupune existența unor prefixe XML literale specifice.
- **FR-04 — Condiții minime și erori.** XML-ul trebuie să fie bine format și să conțină exact un element nevid pentru fiecare câmp obligatoriu de mai jos:
  - elementele directe ale rădăcinii `Invoice`: `cbc:ID`, `cbc:IssueDate` și `cbc:DocumentCurrencyCode`;
  - câte un `cac:AccountingSupplierParty/cac:Party` și `cac:AccountingCustomerParty/cac:Party`, fiecare cu cel puțin o denumire nevidă în `cac:PartyName/cbc:Name` sau `cac:PartyLegalEntity/cbc:RegistrationName`;
  - cel puțin un `cac:InvoiceLine`; fiecare linie trebuie să aibă `cbc:ID`, `cbc:InvoicedQuantity`, `cbc:LineExtensionAmount` nevid și un `cac:Item` cu cel puțin un `cbc:Name` sau `cbc:Description` nevid.

  Lipsa, valoarea goală sau duplicarea ambiguă a unui câmp obligatoriu produce un mesaj inteligibil, fără traceback ori detalii interne. Aceste condiții definesc numai dacă aplicația poate afișa factura; ele nu validează XSD, EN 16931, RO_CIUS sau validitatea fiscală. Celelalte câmpuri, inclusiv prețul unitar, TVA, totalurile, scadența, adresele și plata, sunt opționale pentru acceptarea aplicației.
- **FR-05 — Câmpuri opționale.** Absența unui câmp opțional nu blochează conversia și nu duce la afișarea unor date inventate.

### 3.2. Conținutul facturii

- **FR-06 — Antet.** Se afișează, când există, numărul facturii, data emiterii, data scadenței, codul tipului și moneda.
- **FR-07 — Părți.** Se afișează furnizorul și clientul cu denumire, identificatorii relevanți **păstrați pe roluri distincte**, adrese și date de contact disponibile.
- **FR-08 — Linii.** Se afișează toate elementele `InvoiceLine`, în ordinea din XML, cu identificator, denumire/descriere, cantitate, unitate de măsură, preț, valoare netă și încadrare TVA, când sunt disponibile.
- **FR-09 — TVA.** Se afișează informațiile privind TVA la nivel de document, inclusiv toate subtotalurile și categoriile existente; se păstrează distinct clasificarea TVA de la nivelul liniilor.
- **FR-10 — Totaluri.** Se afișează valorile monetare declarate în XML: valoarea netă, valoarea fără TVA, valoarea cu TVA, reduceri, taxe suplimentare, TVA și suma de plată, după disponibilitatea lor.
- **FR-11 — Plată.** Se afișează toate elementele repetate `PaymentMeans`, inclusiv informațiile de cont bancar prezente.
- **FR-12 — Livrare.** Se afișează data, partea și adresa de livrare atunci când sunt prezente în XML.
- **FR-13 — Fidelitate și neintervenție.** Valorile financiare sunt afișate din XML, fără corectare sau recalculare automată. Eventualele neconcordanțe aritmetice **nu sunt afișate ca avertizări** și **nu împiedică afișarea, imprimarea sau salvarea PDF prin browser**. Reconcilierea financiară nu este o condiție pentru MVP.
- **FR-14 — Afișarea textuală a sumelor.** Pentru fiecare sumă se afișează textul zecimal rezultat din conținutul XML după eliminarea spațiilor albe exterioare. Se păstrează separatorul zecimal și zerourile finale; nu se adaugă separatori de mii, nu se localizează, rotunjește sau convertește suma. Moneda declarată se afișează distinct, fără a modifica textul sumei. Procentele, cantitățile și unitățile se afișează tot din valorile declarate. Dacă sunt necesare calcule interne, se folosește `Decimal`, nu `float`, iar rezultatul nu înlocuiește textul afișat.

**Limită explicită:** afișarea fidelă nu echivalează cu validarea completă XSD/EN 16931/RO_CIUS. Aplicația nu certifică validitatea fiscală a documentului.

### 3.3. Vizualizare în browser

- **FR-15 — Afișare HTML.** Factura este reprezentată ca pagină HTML locală, cu aspect clasic de factură.
- **FR-16 — Lungime variabilă.** Vizualizarea pe ecran permite derularea verticală pentru un număr variabil de linii; nu există paginare fizică pe ecran.
- **FR-17 — Lizibilitate.** Textul lung se încadrează sau se rupe într-un mod lizibil; câmpurile și coloanele nu se suprapun. Diacriticele românești sunt afișate corect.
- **FR-18 — Înlocuirea documentului.** Utilizatorul poate selecta un alt XML, fără a fi obligat să salveze documentul curent.

### 3.4. Imprimare / PDF

- **FR-19 — Acțiune explicită.** Utilizatorul poate declanșa dialogul de imprimare al browserului; acesta alege imprimarea sau „Save as PDF”.
- **FR-20 — Fără PDF automat.** Backend-ul nu creează fișiere PDF pentru simpla vizualizare și nu salvează automat documente în directorul XML-ului.
- **FR-21 — Format tipărit.** CSS-ul de imprimare țintește A4 landscape; controalele aplicației nu apar în documentul imprimat.
- **FR-22 — Paginare automată.** Tabelul se poate extinde pe mai multe pagini, cu repetarea antetelor unde motorul browserului permite; niciun rând nu trebuie omis.
- **FR-23 — Blocuri coerente.** Totalurile, plata și livrarea sunt prezentate după liniile facturii, fără suprapuneri, tăieri sau fragmentări evitabile.
- **FR-24 — Pagini inutile.** Șablonul nu trebuie să introducă deliberat pagini goale sau o pagină suplimentară care conține doar un subsol. Se verifică practic în browserele acceptate.

**Limitare acceptată:** aplicația nu controlează în întregime opțiunile dialogului de imprimare (antete/subsoluri ale browserului, margini, scalare, imprimanta selectată). Nu se urmărește compatibilitatea vizuală exactă a PDF-urilor între browsere și nici identitatea pixel cu pixel cu documentul ANAF. Rămân obligatorii lizibilitatea, afișarea integrală a datelor și paginarea funcțională în browserul principal vizat: Microsoft Edge pe Windows.

## 4. Cerințe nefuncționale

| ID | Cerință | Verificare propusă |
|---|---|---|
| NFR-01 | Funcționare offline după instalare. | Conversie și imprimare fără acces la internet. |
| NFR-02 | Server accesibil doar local, pe `127.0.0.1`, nu pe interfața LAN. | Verificare configurație și acces local. |
| NFR-03 | Fără cereri către ANAF, CDN-uri sau resurse externe pentru funcționare. | Inspectarea codului, resurselor și traficului în teste. |
| NFR-04 | XML-ul este intrare neîncredere. Parserul nu încarcă DTD, nu rezolvă entități, nu face acces la rețea, nu procesează XInclude și respinge documentele care conțin elemente XInclude; nu folosește recuperarea XML-ului malformat sau modul `huge_tree`. Documentele cu `DOCTYPE` sunt respinse. | Teste sintetice pentru DTD/XXE, XInclude, XML malformat și acces la fișiere/rețea; se verifică setările explicite ale parserului. |
| NFR-05 | XML-ul încărcat nu se salvează intenționat pe disc și datele facturii/conținutul XML/numele fișierului nu se scriu în loguri. Răspunsurile cu facturi folosesc `Cache-Control: no-store`. | Audit al rutelor, jurnalizării, stocării temporare și antetelor HTTP. |
| NFR-06 | HTML-ul escapează datele provenite din XML pentru a preveni injectarea de markup/script. | Test cu valori de intrare ce conțin caractere speciale. |
| NFR-07 | Corpul cererii de încărcare are plafon de **10 MiB (10 × 1.024 × 1.024 = 10.485.760 octeți)**. Plafonul se verifică pe octeții efectiv primiți, nu doar pe `Content-Length`, iar depășirea este respinsă înainte de parsarea XML. Parserul rămâne în limitele implicite sigure și nu activează `huge_tree`. | Cerere de cel mult 10 MiB acceptată dacă XML-ul îndeplinește FR-04; cerere peste 10 MiB respinsă înainte de parser. Include caz de `Content-Length` lipsă sau incorect. |
| NFR-08 | Mesajele de eroare sunt lizibile și nu divulgă tracebacks sau date confidențiale. | Teste pentru fișier invalid și operații eșuate. |
| NFR-09 | Pornirea și oprirea aplicației locale sunt previzibile, fără a lăsa servere reziduale. | Test manual pe Windows. |
| NFR-10 | Testele trebuie să poată rula pe date sintetice ori anonimizate. | Audit Git și rularea suitei de teste. |
| NFR-11 | Serverul ascultă numai pe `127.0.0.1`. Rutele verifică `Host` pentru adresa locală și portul aplicației; un `Origin` prezent trebuie să corespundă aceleiași origini, iar POST-ul de încărcare verifică tokenul CSRF. | Cererile cu Host greșit, Origin cross-site sau token CSRF lipsă/invalid sunt respinse; accesul prin interfața LAN nu reușește. |

**Notă de confidențialitate:** browserul și sistemul de operare pot folosi cache ori fișiere temporare. Cerința este lipsa stocării permanente *intenționate de aplicație*, nu o garanție că niciun byte nu ajunge vreodată pe disc.

## 5. Interfața minimă

Pagina inițială conține:

- o zonă de selectare a fișierului XML, cu mesaj vizibil privind plafonul de 10 MiB;
- o acțiune „Deschide / Afișează factura”;
- un spațiu pentru mesaje de eroare și status.

După procesare se afișează factura și comenzile:

- „Alt XML”;
- „Tipărește / Salvează PDF”, care apelează dialogul de imprimare al browserului.

În executabilul Windows este disponibil butonul „Închide aplicația”. Acesta cere confirmare și trimite o comandă locală `POST` protejată cu verificările Host, Origin și CSRF. După transmiterea răspunsului de confirmare, launcherul cere închiderea numai a ferestrei Edge dedicate, identificată prin HWND și PID-ul urmărit, apoi oprește serverul și launcherul. Comanda din system tray folosește aceeași ordine. La pornirea EXE-ului se deschide o fereastră Edge `--app` cu profil temporar separat; închiderea acelei ferestre cu X oprește controlat serverul și launcherul. Dacă fereastra nu poate fi închisă, aplicația rămâne activă și afișează o eroare. Minimizarea, refresh-ul și dialogul Print nu opresc aplicația. Nicio comandă HTTP de oprire nu este disponibilă în modul de dezvoltare `python -m xmltopdf`.

Nu sunt necesare conturi, autentificare, istoric, administrare șabloane, dashboard sau previzualizator PDF separat.

## 6. Criterii de acceptare pentru MVP

| ID | Scenariu | Condiție de acceptare |
|---|---|---|
| AC-01 | XML privat de referință `7004378.xml` (numai verificare locală, dacă fișierul este disponibil) | Poate fi interpretat și afișat local, fără acces la ANAF/internet. Nu se copiază în repository, teste publice, loguri sau artefacte CI. |
| AC-02 | Acoperire eșantion | Toate liniile `InvoiceLine`, toate aparițiile `PaymentMeans`, părțile, livrarea, TVA și câmpurile `LegalMonetaryTotal` prezente în XML se regăsesc în HTML; testul public echivalent folosește fixture sintetic. |
| AC-03 | Fidelitate textuală | Valorile financiare afișate păstrează textul zecimal din XML, inclusiv separatorul și zerourile finale; nu sunt localizate, rotunjite ori înlocuite prin recalculări și nu depind de PDF-ul de referință. |
| AC-04 | Exemplu de paginare ANAF | Pentru documentul de referință, tipărirea nu produce artificial o pagină care conține exclusiv numărul paginii. |
| AC-05 | Factură sintetică cu 1 linie | Se afișează integral, iar imprimarea nu omite câmpuri. |
| AC-06 | Facturi sintetice cu 10, 30 și 100 de linii | Toate liniile apar, în ordine; imprimarea trece corect între pagini, când este necesar. |
| AC-07 | Descrieri foarte lungi | Textul nu se suprapune peste alte câmpuri și nu este tăiat nejustificat. |
| AC-08 | Mai multe subtotaluri TVA | Categoriile și valorile sunt păstrate distinct. |
| AC-09 | Câmpuri opționale lipsă | Se afișează fără date inventate și fără erori nejustificate. |
| AC-10 | XML malformat / tip nesuportat | Utilizatorul primește un mesaj clar; nu apare un traceback în pagină. |
| AC-11 | Verificare offline | Afișarea și dialogul de imprimare funcționează fără conexiune la internet. |
| AC-12 | Abandonarea vizualizării | Niciun PDF nu este salvat automat de backend. |
| AC-13 | Imprimare în browserul țintă | În Microsoft Edge pe Windows, controalele web nu apar în documentul imprimat; conținutul este lizibil pe A4 landscape, fără omisiuni sau suprapuneri. Setările de imprimare ale testului sunt documentate. |
| AC-14 | Securitate XML/HTML | XML-ul cu `DOCTYPE`, entități externe, XInclude sau structură malformată este respins fără acces la fișiere/rețea; textul XML care conține markup este afișat ca text, nu executat de browser. |
| AC-15 | Valori financiare neconcordante (eșantion sintetic) | Se afișează exact valorile declarate; nu apare avertisment de reconciliere; utilizatorul poate imprima ori salva prin browser. |
| AC-16 | Pornire și oprire prin launcher | `XmlToPdf.exe` pornește fără consolă un singur server pe `127.0.0.1:5000`, așteaptă răspunsul local și apoi lansează Edge cu `--app=http://127.0.0.1:5000/` și un director temporar unic prin `--user-data-dir`; profilul Edge obișnuit nu este folosit. O a doua instanță nu pornește alt server și indică folosirea iconului deja activ; un proces necunoscut care ocupă portul este raportat separat și nu este deschis în Edge. Dacă Edge sau monitorizarea ferestrei eșuează, serverul rămâne controlabil din tray și se afișează o eroare. Tray-ul activează fereastra dedicată existentă sau raportează absența ei. Comanda explicită din tray sau interfața web trimite `WM_CLOSE` numai către HWND-ul dedicat validat și așteaptă dispariția lui înainte de oprirea serverului, a tray-ului și a launcherului; dacă închiderea eșuează, serverul rămâne activ și eroarea este raportată. Închiderea ferestrei dedicate cu X oprește prin aceeași metodă comună serverul, tray-ul și launcherul; portul este eliberat. Minimizarea, refresh-ul și dialogul Print nu declanșează oprirea. Închiderea altor ferestre/sesiuni Edge nu afectează XmlToPdf. |
| AC-17 | Limită încărcare | Cererile de până la 10 MiB sunt procesate numai dacă îndeplinesc celelalte criterii; cererile care depășesc 10 MiB sunt respinse înainte de parsare, inclusiv când antetul `Content-Length` lipsește sau este fals. |
| AC-18 | Câmpuri minime | Cazurile sintetice verifică acceptarea câmpurilor minime din FR-04 și mesaje clare pentru fiecare câmp obligatoriu absent, gol sau duplicat ambiguu. Câmpurile opționale absente nu sunt inventate. |
| AC-19 | Cereri locale | Testele confirmă respingerea Host-ului nepermis, a Origin-ului cross-site și a POST-ului fără token CSRF valid; nicio rută nu este accesibilă de pe LAN. |
| AC-20 | Distribuție portabilă Windows | `dist/XmlToPdf.exe` este singurul fișier necesar pentru rulare și poate fi copiat și pornit dintr-un director arbitrar, fără folder `_internal`, consolă sau instalare separată de Python. Executabilul onefile include runtime-ul Python, dependențele, șabloanele și CSS-ul; aplicația funcționează offline, cu Microsoft Edge instalat. Build-ul și pornirea se verifică pe Windows; funcționarea pe un calculator fără Python instalat se confirmă manual înaintea distribuției finale. Pornirea poate dura mai mult din cauza extragerii temporare PyInstaller, în care aplicația nu salvează documente ale utilizatorului. |
| AC-21 | Oprire din interfața web a launcherului | Numai launcherul EXE afișează „Închide aplicația” și oferă ruta `POST /shutdown`. Cererea verifică Host, Origin și CSRF; GET nu declanșează oprirea. Răspunsul generic este transmis înainte de închiderea solicitată a ferestrei Edge dedicate. Apoi aceeași oprire comună folosită de tray eliberează portul și elimină iconul; eșecul închiderii HWND este raportat, iar serverul rămâne activ. Modul `python -m xmltopdf` nu oferă ruta sau butonul. Refresh-ul și navigarea nu opresc serverul; închiderea ferestrei Edge dedicate este o comandă explicită de oprire, iar închiderea unei alte file sau ferestre Edge nu afectează aplicația. |

Testele de paginare se vor executa în Microsoft Edge pe Windows. Setările concrete de imprimare utilizate în verificare vor fi documentate. Nu se solicită comparații de fidelitate PDF între Edge, Chrome sau alte browsere.

## 7. În afara domeniului MVP

- Comunicare cu ANAF/SPV; trimitere, descărcare sau semnare de facturi.
- Validare fiscală completă ori corectarea facturilor emise.
- Editarea datelor din factură.
- Suport garantat pentru `CreditNote` și orice alt tip UBL în afară de `Invoice`.
- Conversie în loturi, istoric sau arhivă documentară.
- Găzduire publică, acces LAN sau acces de pe alte dispozitive.
- Bază de date, autentificare ori administrare utilizatori.
- Generare PDF în backend, export PDF automat sau control programatic asupra dialogului browserului.
- Șabloane configurabile de utilizator în prima versiune.
- Reproducere pixel-perfect a aspectului ANAF.

## 8. Referințe de analiză și date de test

- `7004378.xml` — exemplu real de document UBL `Invoice`.
- `7004378.pdf` — exemplu vizual ANAF asociat documentului XML; are două pagini, a doua doar cu numerotare.
- Capturile interfeței ANAF — referință orientativă pentru flux, **nu** cerință de reproducere a interfeței ANAF.

Exemplele pot conține date reale și **nu trebuie comise** în repository-ul public. Păstrează mostrele reale numai în `samples/private/` (ignorat în Git) sau în afara repository-ului. Fixture-urile din `tests/fixtures/` și testele publice/CI vor folosi exclusiv date sintetice sau anonimizate.

## 9. Întrebări deschise înainte de implementare

| ID | Decizie de finalizat | Direcție curentă |
|---|---|---|
| O-05 | Ce câmpuri secundare apar în layoutul de bază | Se finalizează după maparea UBL–HTML; fără valori inventate. |
| O-06 | Regulile exacte pentru paginare și numerotare | Se validează în Microsoft Edge, fără cerințe de identitate vizuală între browsere. |

**Decizii închise:** O-01 este rezolvată prin D-13; plafonul de încărcare este 10 MiB (fosta O-03); condițiile minime de acceptare sunt cele din FR-04 (fosta O-07); nu se emit avertismente de reconciliere financiară și nu se blochează imprimarea din acest motiv (fosta O-04); nu este necesară compatibilitatea PDF între browsere (fosta O-02). Rămân deschise O-05 și O-06.

## 10. Definiția de finalizare a MVP-ului

MVP-ul este gata pentru acceptare numai dacă:

1. Scenariile AC relevante sunt executate, iar rezultatele sunt documentate.
2. Aplicația poate fi pornită pe Windows prin pașii descriși în `README.md`; launcherul este criteriu pentru etapa de distribuție, nu o condiție a prototipului inițial.
3. Componentele de parsare și prezentare sunt separate și testabile.
4. Testele nu folosesc documente reale în repository-ul public.
5. Problemele cunoscute și limitările imprimării din browser sunt descrise explicit.
6. Niciun rezultat al unui test neexecutat nu este prezentat drept verificat.
