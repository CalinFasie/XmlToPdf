# XmlToPdf

**Stadiu:** fundația Flask, parserul UBL cu modelul intern, încărcarea securizată în memorie, afișarea HTML compactă, fluxul de imprimare A4 landscape din browser și launcherul Windows PyInstaller `--onefile`, fără consolă și cu system tray, sunt implementate. Launcherul oferă oprire comună din pagină și tray: închide mai întâi fereastra Edge dedicată și apoi oprește serverul. Închiderea ferestrei dedicate cu X oprește aceeași instanță. Utilizatorul a confirmat manual un PDF de o pagină pentru factura de referință; regulile generale de paginare rămân deschise. Generarea PDF în backend nu este implementată.

Repository: https://github.com/CalinFasie/XmlToPdf<br>
Director local vizat: `D:\Github\XmlToPdf`

## Scop

XmlToPdf permite consultarea locală a facturilor românești **RO e-Factura UBL `Invoice`** într-un format clasic de factură, fără a depinde de disponibilitatea conversiei oferite de ANAF.

Utilizatorul deschide un XML, vizualizează factura ca pagină HTML în browser și, dacă dorește, o imprimă sau o salvează ca PDF prin dialogul standard al browserului.

## Funcționalitate inclusă în v0.1.0

- Aplicație **web locală**, folosită pe **Windows**, cu server Python accesibil numai pe `127.0.0.1`.
- Backend **Flask**, parser **lxml**, șabloane **Jinja2 + HTML/CSS**.
- Browserul țintă pentru acceptarea MVP este **Microsoft Edge pe Windows**; alte browsere nu au criteriu de fidelitate.
- Vizualizare HTML cu număr variabil de linii; derulare pe ecran.
- Imprimare **A4 landscape** cu paginare automată și antetul tabelului repetat, unde este posibil.
- **Print / Save as PDF** exclusiv la cererea utilizatorului, din browser.
- Fără motor PDF în backend, bază de date, istoric al facturilor sau hosting public în MVP.
- După instalare, procesarea nu are nevoie de internet sau de serviciile ANAF. Distribuția portabilă include runtime-ul Python; Microsoft Edge trebuie instalat separat.
- Se acceptă doar XML bine format cu rădăcina UBL `Invoice` și câmpurile minime descrise în `docs/REQUIREMENTS.md`; nu se pretinde validare fiscală/XSD completă.
- Corpul cererii de încărcare este limitat la **10 MiB**. XML-ul nu se persistă intenționat pe disc și valorile facturii nu se scriu în loguri.
- Sumele sunt afișate cu textul zecimal din XML, fără localizare, separatori de mii, rotunjire sau recalculare. Diferențele aritmetice nu produc avertizări și nu blochează afișarea ori imprimarea.

## Arhitectura conceptuală

```text
Fișier XML UBL
     |
     v
Flask local -> Parser UBL (lxml) -> Model factură -> Jinja2 + HTML/CSS local
                                          |
                    +---------------------+------------------+
                    |                                        |
                    v                                        v
            Vizualizare în browser                   Print / Save as PDF
            (fără PDF intermediar)                   (doar la cerere)
```

## Documentație

- [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) — cerințe și criterii de acceptare.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — decizii confirmate și întrebări deschise.
- [`AGENTS.md`](AGENTS.md) — reguli permanente de lucru pentru Codex.

## Situația implementării

Aplicația acceptă local un XML UBL prin browser, îl procesează în memorie cu parserul UBL existent și afișează factura într-un layout web compact, adaptiv, din același flux. Antetul, banda totalurilor, tabelele și secțiunile de plată/livrare folosesc datele aceluiași model `Invoice`. Prezentarea pentru ecran și șablonul dedicat de imprimare rămân separate. După încărcarea reușită, butonul „Tipărește / Salvează PDF” deschide dialogul browserului. CSS-ul local cere A4 landscape și permite continuarea tabelului pe mai multe pagini. Datele facturii nu sunt păstrate în sesiune sau într-o bază de date. PDF-ul nu este generat de backend.

Maparea câmpurilor modelului în șablon și regulile pentru date opționale sau repetabile sunt descrise în [`docs/UBL_MAPPING.md`](docs/UBL_MAPPING.md). Propunerea nu închide decizia O-05.

### Tipărire și salvare PDF

Fluxul țintă este Microsoft Edge pe Windows. După încărcarea unei facturi, apasă „Tipărește / Salvează PDF”, apoi alege imprimanta sau „Save as PDF” în dialogul Edge. Setarea CSS solicită A4 landscape, cu margini de 8 mm. În Print Preview, verifică **Paper size: A4**, **Layout: Landscape**, **Scale: Default/100%**, **Margins: Default** și dezactivează **Headers and footers** dacă nu dorești antetul și URL-ul browserului. Setările dialogului pot suprascrie CSS-ul.

Utilizatorul a confirmat manual în Edge un PDF A4 Landscape de o pagină pentru factura locală de referință, înaintea schimbărilor de ecran din Task 005F. Task 005F păstrează șablonul și CSS-ul dedicate imprimării neschimbate. Paginarea documentelor mai lungi și variațiile de configurare rămân de verificat; matricea este descrisă în [`docs/PRINTING.md`](docs/PRINTING.md), iar O-06 rămâne deschisă pentru acele cazuri.

### Cerințe pentru dezvoltare

- Pentru lucrul din surse și construirea EXE-ului: Windows și Python **3.11 sau mai nou**. Fundația și build-urile au fost verificate cu Python 3.13.14.
- Pentru utilizarea EXE-ului nu este necesară instalarea separată a Python, Flask sau lxml; este necesar Microsoft Edge.
- Acces la pachetele Python pentru instalarea inițială. După instalare, pagina de pornire nu folosește servicii externe.

Python 3.11 este versiunea minimă declarată: Flask acceptă versiuni mai vechi, dar ciclul de suport al Python 3.10 se încheie în octombrie 2026.

### Dezvoltare: instalare, testare și pornire (PowerShell)

Execută comenzile din rădăcina repository-ului:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m xmltopdf
```

Serverul ascultă numai pe `127.0.0.1:5000`, cu modul debug și reloader dezactivate. Deschide manual `http://127.0.0.1:5000/` în browser. Oprește serverul cu `Ctrl+C` în terminal.

### Utilizare pentru utilizatorul final — EXE Windows 0.1.0

Release-ul GitHub v0.1.0 și pachetul public nu au fost create în etapa de pregătire curentă. După publicare, descarcă numai `XmlToPdf.exe` din [pagina Releases](https://github.com/CalinFasie/XmlToPdf/releases). Pentru rulare nu instala Python și nu copia directoare `build/` sau `dist/`; Microsoft Edge trebuie să fie instalat.

1. Copiază `XmlToPdf.exe` într-un director ales de tine.
2. Pornește EXE-ul prin dublu-click. Se deschide o fereastră Microsoft Edge dedicată; aplicația web și serverul rulează local pe `127.0.0.1`.
3. Selectează fișierul XML e-Factura și pornește procesarea. XML-ul trebuie să fie de cel mult 10 MiB și este procesat în memorie.
4. Pentru PDF, apasă „Tipărește / Salvează PDF”, apoi alege imprimanta sau „Save as PDF” în dialogul Edge. Verifică A4 și Landscape în previzualizare.
5. Închide aplicația cu X-ul ferestrei dedicate, butonul „Închide aplicația” din pagină sau „Închide XmlToPdf” din system tray.

Nu închide fereastra principală cât timp imprimarea este în curs. Închiderea unei file obișnuite, refresh-ul sau minimizarea nu opresc aplicația.

Utilizatorul a confirmat pornirea, încărcarea și imprimarea, precum și toate cele trei metode de închidere pe calculatorul de dezvoltare și a validat executabilul și pe un al doilea calculator. O-06 rămâne deschisă pentru testarea paginării facturilor lungi.

### Construirea EXE-ului (dezvoltatori)

Build-ul necesită mediul Python pentru dezvoltare și dependențele `.[dev]`. Scriptul rezolvă căile relativ la propria locație:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\tools\build_windows.ps1
Get-FileHash -LiteralPath .\dist\XmlToPdf.exe -Algorithm SHA256
```


Build-ul produce `dist\XmlToPdf.exe`; instrucțiunile de verificare a pachetului și de înregistrare a hash-ului sunt în [`docs/WINDOWS_DISTRIBUTION.md`](docs/WINDOWS_DISTRIBUTION.md). Hash-ul SHA-256 identifică fișierul construit și trebuie calculat din nou pentru fiecare build. Versiunile rezolvate ale dependențelor pot influența octeții executabilului.

La dublu-click, aplicația pornește fără fereastră CMD, leagă serverul la `127.0.0.1:5000`, așteaptă răspunsul local și apoi deschide Microsoft Edge într-o fereastră `--app` cu un profil temporar separat. Modul de dezvoltare `python -m xmltopdf` folosește comenzile Python de mai sus, nu are buton sau rută HTTP de oprire și nu lansează Edge în profilul temporar dedicat.

Prima pornire poate dura mai mult decât varianta `--onedir`, deoarece PyInstaller extrage temporar bibliotecile incluse. Edge poate crea în profilul temporar cache, cookie-uri, stare de sesiune, preferințe și fișiere de diagnostic; aplicația nu salvează intenționat XML-uri ori PDF-uri acolo, iar XML-ul încărcat este procesat în memorie. Launcherul șterge numai directoarele proprii marcate după terminarea proceselor Edge care le folosesc. Oprirea din pagină sau tray închide mai întâi fereastra dedicată; dacă Edge încă folosește profilul, acesta rămâne până când procesele asociate se termină și este curățat la o pornire ulterioară XmlToPdf. Calculatorul țintă trebuie să aibă Windows și Microsoft Edge instalat, dar nu Python, Flask sau lxml instalate separat. Pentru detalii și limitele verificării, vezi [`docs/WINDOWS_DISTRIBUTION.md`](docs/WINDOWS_DISTRIBUTION.md).

## Date de referință și confidențialitate

Documentele locale `7004378.xml` și `7004378.pdf` servesc ca eșantioane de analiză, nu ca fișiere destinate publicării. Pot conține informații reale și **nu trebuie comise în repository-ul public**. Căile lor exacte și `samples/private/` sunt ignorate de `.gitignore`; protecția este disponibilă numai în checkout-urile care conțin și versiunea comisă a acestei reguli.

Pentru documente reale, folosește exclusiv `samples/private/` sau păstrează fișierele în afara repository-ului. Testele publice și CI vor folosi exclusiv date sintetice sau anonimizate. Verifică fișierele staged înainte de fiecare commit; `.gitignore` nu împiedică adăugarea forțată.

## Dezvoltare cu Codex

1. Deschide repository-ul local în Codex.
2. Solicită agentului să citească `AGENTS.md`, cerințele și deciziile relevante.
3. Lucrează pe taskuri mici, cu plan pentru schimbările importante.
4. Revizuiește modificările și rezultatele testelor înainte de publicarea lor în GitHub.

Nu publica fișiere reale de factură și nu începe implementarea doar pe baza faptului că există documentația.
