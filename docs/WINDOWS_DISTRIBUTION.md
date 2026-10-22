# Distribuția Windows

## Pachetul onefile

Distribuția este un singur `dist\XmlToPdf.exe`, construit cu PyInstaller `--onefile` și `console=False`. Executabilul include runtime-ul Python, Flask/Werkzeug, lxml, Jinja2, Pillow, pystray, șabloanele HTML și CSS-ul local. Copiază numai EXE-ul în directorul ales. Nu este necesar Python separat; Microsoft Edge trebuie instalat.

PyInstaller extrage componentele sale într-un director temporar la pornire, ceea ce poate prelungi pornirea față de `--onedir`. Directorul respectiv conține codul și resursele pachetului. Încărcarea XML este procesată în memorie de aplicație; XML-urile și alte documente ale utilizatorului nu sunt scrise în directorul de extragere. Nu folosi acel director pentru date persistente.

## Construirea

Folosește Windows și mediul virtual al repository-ului. Scriptul rezolvă căile față de propria locație și poate fi lansat din orice director:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\tools\build_windows.ps1
```

Specificația `XmlToPdf.spec` activează onefile și fereastra fără consolă, include șabloanele/CSS-ul și dependențele tray, colectează bibliotecile dinamice lxml și exclude testele. Rezultatul este `dist\XmlToPdf.exe`. `build/` și `dist/` sunt artefacte locale și sunt ignorate de Git; nu comite executabilul.

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

### Verificări manuale rămase

În această sesiune nu a fost controlabilă interfața nativă Microsoft Edge/system tray. Nu au fost executate dublu-click-ul pe o copie izolată a EXE-ului, verificarea vizuală a meniului, încărcarea prin Edge, Print / Save as PDF, oprirea efectivă din tray sau repornirea. Nu a fost disponibil un calculator fără Python instalat. Aceste verificări rămân necesare înaintea distribuției finale.

### Task 006C — verificări executate

- `pytest`: 118 teste trecute. Testele HTTP loopback au fost rulate cu permisiunea necesară pentru conexiuni locale.
- `git diff --check`: fără erori.
- `tools/build_windows.ps1`: build onefile reușit cu Python 3.13.14 și PyInstaller 6.22.3; `dist\XmlToPdf.exe` are 24.035.244 octeți, iar `dist/` conține numai acest executabil.
- Testul de integrare folosește un port loopback efemer și date sintetice: răspunsul HTTP de oprire a fost citit integral, controllerul a încheiat serverul și a apelat oprirea iconului, iar portul a putut fi legat din nou.
- Nu a fost posibilă verificarea manuală a butonului în Microsoft Edge, copierea și pornirea EXE-ului prin dublu-click sau interacțiunea cu iconul system tray. Aceste verificări rămân necesare înaintea distribuirii buildului nou.

### Task 006D — verificări executate

- `pytest`: 124 teste trecute, inclusiv scenarii sintetice pentru arborele de procese, identificarea HWND, minimizare/refresh/Print, închiderea ferestrei, pornire eșuată și oprire idempotentă.
- `git diff --check`: fără erori.
- `tools/build_windows.ps1`: build PyInstaller onefile reușit cu Python 3.13.14 și PyInstaller 6.22.3; `dist\XmlToPdf.exe` are 24.048.894 octeți.
- Probe locale ale API-urilor Win32 de enumerare a proceselor și ferestrelor: apelurile au reușit.
- Probă automatizată cu EXE-ul real și Microsoft Edge în sesiunea Windows: pagina locală a răspuns `200`, a fost găsită fereastra Edge vizibilă asociată arborelui de procese XmlToPdf, trimiterea `WM_CLOSE` către acel HWND a dus la ieșirea launcherului cu codul `0`, portul 5000 a putut fi legat din nou și profilul nou creat nu a rămas pe disc. Proba nu a încărcat o factură și nu a verificat vizual interfața sau imprimarea.
- Interfața UI Microsoft Edge și system tray nu a fost disponibilă pentru control manual în Codex. Rămân neverificate vizual: încărcarea unui XML sintetic în fereastra Edge, Print / Save as PDF, minimizarea/refresh-ul prin UI, meniul tray și faptul că alte ferestre Edge rămân deschise. Acestea necesită validare manuală înainte de distribuție.

### Task 006E — închiderea ferestrei dedicate din tray și web

- `pytest`: 131 teste trecute. Acoperă asocierea HWND–PID, refuzul unui HWND reutilizat de alt PID, trimiterea `WM_CLOSE` numai către handle-ul urmărit, eșecul controlat, oprirea simultană și ordinea răspuns HTTP → închiderea Edge → oprirea serverului.
- `git diff --check`: fără erori.
- `tools/build_windows.ps1`: build PyInstaller onefile reușit cu Python 3.13.14 și PyInstaller 6.22.3; `dist/XmlToPdf.exe` are 24.052.668 octeți și rămâne exclus din Git.
- Probă de integrare cu EXE-ul reconstruit: pagina locală a răspuns, POST-ul de oprire cu token CSRF a primit HTTP 202, HWND-ul Edge nou identificat în arborele EXE-ului a dispărut, procesul launcherului a ieșit cu codul 0, iar portul 5000 a putut fi legat din nou. Nu existau ferestre Edge obișnuite vizibile la începutul probei, deci această rulare nu a verificat manual păstrarea lor.
- Testele automatizate simulează comanda tray și confirmă că închiderea HWND-ului precedă oprirea serverului. Interacțiunea manuală cu meniul nativ tray nu a fost disponibilă în această sesiune; nici fluxul Print / Save as PDF nu a fost repetat. Aceste verificări vizuale rămân pentru confirmare manuală pe Windows.
