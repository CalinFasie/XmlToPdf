# XmlToPdf

**Stadiu:** fundația Flask, parserul UBL cu modelul intern, încărcarea securizată în memorie, afișarea HTML compactă, fluxul de imprimare A4 landscape din browser și launcherul Windows PyInstaller `--onefile`, fără consolă și cu system tray, sunt implementate. Launcherul oferă oprirea controlată din pagină și tray; închiderea ferestrei Edge dedicate oprește aceeași instanță. Utilizatorul a confirmat manual un PDF de o pagină pentru factura de referință; regulile generale de paginare rămân deschise. Generarea PDF în backend nu este implementată.

Repository: https://github.com/CalinFasie/XmlToPdf<br>
Director local vizat: `D:\Github\XmlToPdf`

## Scop

XmlToPdf va permite consultarea locală a facturilor românești **RO e-Factura UBL `Invoice`** într-un format clasic de factură, fără a depinde de disponibilitatea conversiei oferite de ANAF.

Utilizatorul va deschide un XML, va vizualiza factura ca pagină HTML în browser și, numai dacă dorește, o va putea imprima sau salva ca PDF prin dialogul standard al browserului.

## Funcționalitate planificată pentru prima versiune

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

### Cerințe

- Windows și Python **3.11 sau mai nou**. Fundația a fost verificată local cu Python 3.13.14.
- Acces la pachetele Python pentru instalarea inițială. După instalare, pagina de pornire nu folosește servicii externe.

Python 3.11 este versiunea minimă declarată: Flask acceptă versiuni mai vechi, dar ciclul de suport al Python 3.10 se încheie în octombrie 2026.

### Instalare, testare și pornire (PowerShell)

Execută comenzile din rădăcina repository-ului:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m xmltopdf
```

Serverul ascultă numai pe `127.0.0.1:5000`, cu modul debug și reloader dezactivate. Deschide manual `http://127.0.0.1:5000/` în browser. Oprește serverul cu `Ctrl+C` în terminal.

### Build și utilizare Windows fără Python separat

Instalează PyInstaller, pystray și celelalte dependențe de build din rădăcina repository-ului. Apoi poți apela scriptul de build din orice director; el rezolvă căile relativ la fișierul propriu:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\tools\build_windows.ps1
```

Build-ul produce un singur fișier `dist\XmlToPdf.exe`. Copiază numai EXE-ul în directorul dorit; nu este necesar un folder `_internal`. La dublu-click, aplicația pornește fără fereastră CMD, leagă serverul la `127.0.0.1:5000`, așteaptă răspunsul local și apoi deschide Microsoft Edge într-o fereastră `--app` cu un profil temporar separat. Închiderea acelei ferestre cu X oprește launcherul; butonul „Închide aplicația” și comanda din system tray rămân metode alternative de oprire. Minimizarea, refresh-ul, dialogul Print și închiderea altor ferestre Edge nu opresc XmlToPdf. Modul de dezvoltare `python -m xmltopdf` nu are buton sau rută HTTP de oprire și nu lansează Edge în profilul temporar dedicat.

Prima pornire poate dura mai mult decât varianta `--onedir`, deoarece PyInstaller extrage temporar bibliotecile incluse. Edge poate crea în profilul temporar cache, cookie-uri, stare de sesiune, preferințe și fișiere de diagnostic; aplicația nu salvează intenționat XML-uri ori PDF-uri acolo, iar XML-ul încărcat este procesat în memorie. Launcherul șterge numai directoarele proprii marcate după terminarea proceselor Edge care le folosesc. Dacă utilizatorul oprește serverul din pagină sau tray cât timp fereastra Edge este încă deschisă, profilul rămâne până când Edge nu îl mai folosește și este curățat la o pornire ulterioară XmlToPdf. Calculatorul țintă trebuie să aibă Windows și Microsoft Edge instalat, dar nu Python, Flask sau lxml instalate separat. Pentru detalii și limitele verificării, vezi [`docs/WINDOWS_DISTRIBUTION.md`](docs/WINDOWS_DISTRIBUTION.md).

## Date de referință și confidențialitate

Documentele locale `7004378.xml` și `7004378.pdf` servesc ca eșantioane de analiză, nu ca fișiere destinate publicării. Pot conține informații reale și **nu trebuie comise în repository-ul public**. Căile lor exacte și `samples/private/` sunt ignorate de `.gitignore`; protecția este disponibilă numai în checkout-urile care conțin și versiunea comisă a acestei reguli.

Pentru documente reale, folosește exclusiv `samples/private/` sau păstrează fișierele în afara repository-ului. Testele publice și CI vor folosi exclusiv date sintetice sau anonimizate. Verifică fișierele staged înainte de fiecare commit; `.gitignore` nu împiedică adăugarea forțată.

## Dezvoltare cu Codex

1. Deschide repository-ul local în Codex.
2. Solicită agentului să citească `AGENTS.md`, cerințele și deciziile relevante.
3. Lucrează pe taskuri mici, cu plan pentru schimbările importante.
4. Revizuiește modificările și rezultatele testelor înainte de publicarea lor în GitHub.

Nu publica fișiere reale de factură și nu începe implementarea doar pe baza faptului că există documentația.
