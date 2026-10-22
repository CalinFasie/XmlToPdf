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

## Pornire și control din system tray

La prima pornire, launcherul creează o singură instanță, construiește aplicația prin `create_app()`, leagă serverul Werkzeug exclusiv la `127.0.0.1:5000`, așteaptă un răspuns HTTP local și apoi încearcă să deschidă pagina în Microsoft Edge. Iconul din zona de notificări oferă:

- **Deschide XmlToPdf** — lansează Edge către pagina locală. Nu închide și nu controlează alte ferestre sau procese Edge.
- **Închide XmlToPdf** — oprește controlat serverul, eliberează portul, așteaptă threadul serverului și elimină iconul.

Închiderea Edge nu oprește serverul; folosește comanda din tray. Dacă Edge nu este disponibil, aplicația rămâne activă, iar un mesaj afișează URL-ul local pentru deschidere manuală. O a doua lansare a XmlToPdf este detectată prin mutex și îndrumă utilizatorul către iconul existent. Dacă portul 5000 este ocupat de un proces necunoscut, aplicația afișează o eroare și nu lansează Edge.

Aplicația nu pornește automat odată cu Windows și nu instalează servicii sau înregistrări în registry. Comanda de dezvoltare `python -m xmltopdf` rămâne disponibilă și pornește serverul local pentru oprire cu `Ctrl+C`.

## Securitate și confidențialitate

Serverul rămâne pe loopback. Se păstrează verificările Host, Origin, CSRF și plafonul de 10 MiB; parserul XML securizat, șabloanele escapate și răspunsurile `no-store` rămân neschimbate. Nu se folosesc resurse externe. Jurnalizarea HTTP a launcherului nu include URL-uri de cereri, nume de fișiere sau date de factură. Erorile de pornire sunt prezentate prin mesaje Windows generice, fără traceback.

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
