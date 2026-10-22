# Distribuția Windows

**Release public:** [XmlToPdf v0.1.0 — Windows](https://github.com/CalinFasie/XmlToPdf/releases/tag/v0.1.0)<br>
**Stadiul proiectului:** [docs/PROJECT_STATUS.md](PROJECT_STATUS.md)

## Pachetul onefile

Distribuția este un singur `dist\XmlToPdf.exe`, construit cu PyInstaller `--onefile` și `console=False`. Executabilul include runtime-ul Python, Flask/Werkzeug, lxml, Jinja2, Pillow, pystray, șabloanele HTML și CSS-ul local. Copiază numai EXE-ul în directorul ales. Nu este necesar Python separat; Microsoft Edge trebuie instalat.

PyInstaller extrage componentele sale într-un director temporar la pornire, ceea ce poate prelungi pornirea față de `--onedir`. Directorul respectiv conține codul și resursele pachetului. Încărcarea XML este procesată în memorie de aplicație; XML-urile și alte documente ale utilizatorului nu sunt scrise în directorul de extragere. Nu folosi acel director pentru date persistente.

## Construirea și verificarea pachetului

Construirea se face pe Windows, din sursele repository-ului. Python și dependențele de dezvoltare sunt necesare numai pe calculatorul care construiește aplicația; utilizatorul EXE-ului nu instalează Python separat. Scriptul rezolvă căile față de propria locație și poate fi lansat din orice director. Pentru un checkout nou, rulează din rădăcina repository-ului:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\tools\build_windows.ps1
$Executable = (Resolve-Path -LiteralPath .\dist\XmlToPdf.exe).Path
Get-Item -LiteralPath $Executable | Select-Object FullName, Length
Get-FileHash -LiteralPath $Executable -Algorithm SHA256
```

Versiunea aplicației este `0.1.0`, declarată în `pyproject.toml`. Scriptul `tools/build_windows.ps1` folosește specificația `XmlToPdf.spec`, construiește un singur EXE onefile fără consolă, include șabloanele/CSS-ul și dependențele runtime, colectează bibliotecile dinamice lxml și exclude `pytest` și `tests`. Rezultatul este `dist\XmlToPdf.exe`. `build/` și `dist/` sunt artefacte locale ignorate de Git; nu le adăuga la commit sau pachetul public.

Înainte de distribuire, inspectează conținutul arhivei PyInstaller și confirmă că nu conține XML/PDF de factură, teste/fixture-uri sau secrete. Cu PyInstaller instalat în `.venv`, lista de membri se poate consulta astfel:

```powershell
& .\.venv\Scripts\pyi-archive_viewer.exe -l .\dist\XmlToPdf.exe
```

Compară lista cu așteptarea: runtime-ul aplicației și dependențele sunt incluse; `tests`, fixture-uri, mostre private, `.env`, chei și tokenuri nu trebuie să apară. Verifică și directorul `dist/`; pachetul livrat conține numai `XmlToPdf.exe`. Hash-ul SHA-256 se calculează după build și se publică împreună cu acel fișier pentru verificarea integrității. Hash-ul este specific fiecărui build. Repetarea procedurii este documentată, dar byte-for-byte reproducerea nu este garantată când resolverul instalează versiuni diferite ale dependențelor permise de `pyproject.toml`.

Versiunile folosite la o verificare se pot nota cu:

```powershell
python --version
.\.venv\Scripts\python.exe -m pip show PyInstaller
```

Release-ul v0.1.0 este public. Pentru o versiune viitoare, crearea tagului, a Release-ului și a pachetului public necesită aprobarea explicită a etapei respective.

## Utilizare pentru utilizatorul final

Aceste instrucțiuni se aplică EXE-ului Windows 0.1.0 publicat în [Release-ul oficial](https://github.com/CalinFasie/XmlToPdf/releases/tag/v0.1.0).

1. Descarcă `XmlToPdf.exe` din [Release-ul v0.1.0](https://github.com/CalinFasie/XmlToPdf/releases/tag/v0.1.0).
2. Copiază singurul fișier EXE într-un director ales și pornește-l prin dublu-click. Nu este necesar Python; este necesar Microsoft Edge.
3. În fereastra Edge dedicată, selectează fișierul XML e-Factura (maximum 10 MiB) și pornește procesarea. XML-ul este procesat local, în memorie.
4. Pentru a obține PDF-ul, apasă „Tipărește / Salvează PDF”, apoi alege „Save as PDF” sau o imprimantă din dialogul Edge. Confirmă A4 și Landscape în previzualizare.
5. Închide XmlToPdf cu X-ul ferestrei Edge dedicate, butonul web „Închide aplicația” sau comanda „Închide XmlToPdf” din system tray. Serverul local și pictograma tray se opresc controlat.

Închiderea unei file, refresh-ul, minimizarea sau Print Preview nu opresc aplicația. Documentele încărcate nu sunt salvate intenționat de XmlToPdf.

## Pornire și oprire

La prima pornire, launcherul creează o singură instanță, activează ruta de oprire numai pentru această rulare, leagă serverul Werkzeug exclusiv la `127.0.0.1:5000`, așteaptă un răspuns HTTP local și pornește Microsoft Edge cu `--app=http://127.0.0.1:5000/`. Fereastra folosește un `--user-data-dir` temporar unic; profilul Edge obișnuit nu este folosit. Pagina oferă butonul „Închide aplicația”; acesta cere confirmare și trimite un `POST` local protejat de verificările Host, Origin și CSRF. Serverul transmite răspunsul înainte ca launcherul să trimită `WM_CLOSE` către HWND-ul validat al ferestrei dedicate. Tray-ul folosește aceeași cale; după confirmarea dispariției ferestrei, oprirea eliberează portul, așteaptă threadurile HTTP active și elimină iconul. Dacă fereastra nu poate fi închisă, serverul rămâne activ și apare o eroare vizibilă.

Iconul din zona de notificări oferă:

- **Deschide XmlToPdf** — activează fereastra Edge dedicată existentă sau încearcă să o pornească din nou dacă nu mai există. Nu închide și nu controlează alte ferestre sau procese Edge.
- **Închide XmlToPdf** — solicită închiderea numai a ferestrei Edge dedicate și apoi apelează aceeași logică de oprire controlată ca butonul din pagina web.

Închiderea cu X a ferestrei Edge dedicate oprește XmlToPdf. Minimizarea, refresh-ul, navigarea și dialogul Print / Save as PDF nu opresc serverul; nici închiderea altor ferestre sau sesiuni Edge nu afectează aplicația. Ruta HTTP de oprire nu este înregistrată de comanda de dezvoltare `python -m xmltopdf`, care se oprește cu `Ctrl+C`. Dacă Edge nu pornește sau nu poate fi monitorizat, serverul rămâne activ, apare un mesaj de recuperare, iar tray-ul poate opri aplicația. O a doua lansare a XmlToPdf este detectată prin mutex și îndrumă utilizatorul către iconul existent. Dacă portul 5000 este ocupat de un proces necunoscut, aplicația afișează o eroare și nu lansează Edge.

Aplicația nu pornește automat odată cu Windows și nu instalează servicii sau înregistrări în registry. Comanda de dezvoltare `python -m xmltopdf` rămâne disponibilă și pornește serverul local pentru oprire cu `Ctrl+C`.

## Securitate și confidențialitate

Serverul rămâne pe loopback. Se păstrează verificările Host, Origin, CSRF și plafonul de 10 MiB; parserul XML securizat, șabloanele escapate și răspunsurile `no-store` rămân neschimbate. Nu se folosesc resurse externe. Jurnalizarea HTTP a launcherului nu include URL-uri de cereri, nume de fișiere sau date de factură. Erorile de pornire sunt prezentate prin mesaje Windows generice, fără traceback.

Profilul temporar Edge este creat de launcher sub directorul temporar Windows și poartă un marker intern. Edge poate scrie acolo cache, cookie-uri, stare de sesiune, preferințe, date de descărcare/printare și rapoarte de diagnostic, în funcție de versiunea instalată. XmlToPdf nu salvează intenționat XML-urile încărcate ori PDF-uri în acel profil. Launcherul șterge doar directoarele cu markerul propriu după ce nu mai există procese Edge care le folosesc. Oprirea web sau din tray închide mai întâi fereastra dedicată; dacă fereastra sau procesele Edge asociate rămân active, profilul nu este șters atunci. La o pornire ulterioară, profilurile marcate rămase sunt șterse numai când snapshot-ul proceselor nu găsește procese Edge; în caz de incertitudine, profilul este păstrat.

## Verificare și limite

Testele automatizate folosesc XML-uri sintetice și simulează Edge, system tray și API-urile Windows. Ele verifică secvența pornire server → browser/tray și oprirea controlată; un test de integrare pornește serverul Werkzeug pe un port loopback efemer și confirmă că portul poate fi legat din nou după oprire.

### Task 006B — verificări executate

- `pytest`: 111 teste trecute. Testul de socket local a fost rulat cu permisiunea necesară pentru loopback.
- `git diff --check`: fără erori.
- `tools/build_windows.ps1` a fost lansat din `D:\Github`, în afara repository-ului. Build-ul a reușit cu Windows 11, Python 3.13.14 și PyInstaller 6.22.3.
- Rezultatul este `dist\XmlToPdf.exe` (24.032.259 octeți). Executabilul are subsistemul Windows GUI (`Subsystem=2`), fără subsistem de consolă. După eliminarea folderului onedir generat anterior, `dist` conține numai acest EXE.
- Arhiva executabilului conține runtime-ul Python, backendul Windows pystray și șabloanele/CSS-ul. Inspecția nu a găsit teste, fixture-uri, XML-uri sau PDF-uri în pachet.
- Testele verifică încărcarea șabloanelor dintr-un director onefile simulat, legarea acțiunilor din meniu, mutexul și eliberarea portului.

### Verificări manuale în sesiunea Task 006B

La acel moment, interfața nativă Edge/system tray și un al doilea calculator nu au fost disponibile pentru verificarea manuală de către Codex. Validarea manuală ulterioară făcută de utilizator este consemnată la „Validarea manuală finală pentru v0.1.0” de mai jos.

### Task 006C — verificări executate

- `pytest`: 118 teste trecute. Testele HTTP loopback au fost rulate cu permisiunea necesară pentru conexiuni locale.
- `git diff --check`: fără erori.
- `tools/build_windows.ps1`: build onefile reușit cu Python 3.13.14 și PyInstaller 6.22.3; `dist\XmlToPdf.exe` are 24.035.244 octeți, iar `dist/` conține numai acest executabil.
- Testul de integrare folosește un port loopback efemer și date sintetice: răspunsul HTTP de oprire a fost citit integral, controllerul a încheiat serverul și a apelat oprirea iconului, iar portul a putut fi legat din nou.
- În sesiunea Task 006C, Codex nu a putut verifica manual butonul în Edge, pornirea prin dublu-click sau meniul tray. Utilizatorul a validat ulterior aceste fluxuri; vezi secțiunea de validare manuală finală.

### Task 006D — verificări executate

- `pytest`: 124 teste trecute, inclusiv scenarii sintetice pentru arborele de procese, identificarea HWND, minimizare/refresh/Print, închiderea ferestrei, pornire eșuată și oprire idempotentă.
- `git diff --check`: fără erori.
- `tools/build_windows.ps1`: build PyInstaller onefile reușit cu Python 3.13.14 și PyInstaller 6.22.3; `dist\XmlToPdf.exe` are 24.048.894 octeți.
- Probe locale ale API-urilor Win32 de enumerare a proceselor și ferestrelor: apelurile au reușit.
- Probă automatizată cu EXE-ul real și Microsoft Edge în sesiunea Windows: pagina locală a răspuns `200`, a fost găsită fereastra Edge vizibilă asociată arborelui de procese XmlToPdf, trimiterea `WM_CLOSE` către acel HWND a dus la ieșirea launcherului cu codul `0`, portul 5000 a putut fi legat din nou și profilul nou creat nu a rămas pe disc. Proba nu a încărcat o factură și nu a verificat vizual interfața sau imprimarea.
- În sesiunea Task 006D, interfața Edge și system tray nu a fost disponibilă pentru control manual în Codex; acea limitare a fost ulterior închisă prin validarea manuală a utilizatorului consemnată mai jos.

### Task 006E — închiderea ferestrei dedicate din tray și web

- `pytest`: 131 teste trecute. Acoperă asocierea HWND–PID, refuzul unui HWND reutilizat de alt PID, trimiterea `WM_CLOSE` numai către handle-ul urmărit, eșecul controlat, oprirea simultană și ordinea răspuns HTTP → închiderea Edge → oprirea serverului.
- `git diff --check`: fără erori.
- `tools/build_windows.ps1`: build PyInstaller onefile reușit cu Python 3.13.14 și PyInstaller 6.22.3; `dist/XmlToPdf.exe` are 24.052.668 octeți și rămâne exclus din Git.
- Probă de integrare cu EXE-ul reconstruit: pagina locală a răspuns, POST-ul de oprire cu token CSRF a primit HTTP 202, HWND-ul Edge nou identificat în arborele EXE-ului a dispărut, procesul launcherului a ieșit cu codul 0, iar portul 5000 a putut fi legat din nou. Nu existau ferestre Edge obișnuite vizibile la începutul probei, deci această rulare nu a verificat manual păstrarea lor.
- Testele automatizate simulează comanda tray și confirmă că închiderea HWND-ului precedă oprirea serverului. Interacțiunea manuală cu tray și Print / Save as PDF nu a fost disponibilă în sesiunea Codex Task 006E; utilizatorul a confirmat ulterior verificarea acestor fluxuri pe Windows, inclusiv pe un al doilea calculator.

### Validarea manuală finală pentru v0.1.0

Următoarele rezultate au fost confirmate manual de utilizator pe Windows, pe calculatorul de dezvoltare și pe un al doilea calculator:

- `XmlToPdf.exe` pornește fără fereastră CMD și deschide fereastra Edge dedicată.
- XML-ul poate fi încărcat și factura este afișată.
- Print / Save as PDF funcționează în Edge cu layout A4 Landscape.
- Toate cele trei metode de închidere au fost verificate: X-ul ferestrei Edge dedicate, butonul web și system tray. Serverul se oprește, portul 5000 se eliberează, iar pictograma tray dispare.
- Celelalte ferestre Edge rămân neafectate.
- Executabilul a fost copiat și validat și pe al doilea calculator.

Aceasta este confirmarea manuală furnizată de utilizator; build-ul și testele automate de pregătire v0.1.0 se raportează separat în secțiunea de rezultate a acestei versiuni. O-06 rămâne deschisă pentru testarea extinsă a paginării facturilor lungi; confirmarea unei pagini pentru factura scurtă de referință nu închide această decizie.

### Task 007 — rezultate build v0.1.0

- Versiunea din `pyproject.toml`: `0.1.0`.
- Build Windows reușit cu Python 3.13.14, PyInstaller 6.22.3 și Windows 11.
- `dist\XmlToPdf.exe`: 24.052.950 octeți (aproximativ 22,94 MiB).
- SHA-256 pentru acest build: `E4AD5CF06AFED0B80F5B8F9BB92897C64A15838DFF81B2F025480EEDC05CAE2E`.
- Teste: `pytest` — 131 trecute; `git diff --check` fără erori.
- Arhiva PyInstaller a fost inspectată recursiv (876 membri): nu au fost găsite căi de XML/PDF, teste, fixture-uri, mostre, fișiere de mediu sau chei. Specificația exclude explicit `pytest` și `tests`. Directorul `dist/` conține numai EXE-ul.
- Task 007 nu a publicat atunci un Release, tag Git sau pachet public; v0.1.0 a fost publicat ulterior în Task 008. EXE-ul și directoarele `build/`/`dist/` rămân artefacte locale ignorate de Git.
