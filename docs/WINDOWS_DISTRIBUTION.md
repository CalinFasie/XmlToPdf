# Distribuția Windows

## Pachetul portabil

Task 006 folosește un EXE cu consolă construit cu PyInstaller `--onedir`. Fișierul țintă este `dist\XmlToPdf\XmlToPdf.exe`, iar distribuția este folderul complet `dist\XmlToPdf`. Acesta conține runtime-ul Python, pachetele Flask/Werkzeug/Jinja2, lxml și fișierele aplicației. Microsoft Edge trebuie instalat separat; Python nu.

Pachetul nu este MSI/Setup, nu se instalează în Program Files și nu se înregistrează în Windows. Copiază folderul de distribuție ca unitate și păstrează structura din interior. Fișierul `.spec` este versiunea controlată a rețetei de build. `build/` și `dist/` sunt artefacte generate și ignorate de Git.

## Construirea

Folosește Windows și un mediu virtual cu dependențele de dezvoltare instalate. Din rădăcina repository-ului, rulează:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm --distpath .\dist --workpath .\build .\XmlToPdf.spec
```

Specificația caută sursele relativ la fișierul `.spec`, include toate șabloanele și resursele statice ale pachetului, colectează bibliotecile dinamice lxml și exclude testele. Build-ul nu include mostre private. Nu comite binarele din `dist/`.

## Pornire și oprire

Pornește `dist\XmlToPdf\XmlToPdf.exe` din Explorer sau dintr-un terminal. Launcherul creează aplicația prin `create_app()`, leagă serverul la `127.0.0.1:5000`, așteaptă un răspuns HTTP local și apoi pornește explicit `msedge.exe` cu pagina aplicației. Nu folosește browserul implicit și nu pornește un alt port.

- Dacă portul 5000 este ocupat, launcherul afișează un mesaj și se încheie fără a deschide browserul.
- Dacă Edge lipsește sau nu pornește, serverul rămâne activ, iar URL-ul este afișat pentru a-l deschide manual în Microsoft Edge.
- `Ctrl+C` închide serverul și eliberează portul; procesul Edge nu este închis.
- Închiderea ferestrei consolei încheie procesul launcherului; sistemul de operare închide socketul, iar Edge rămâne deschis. Pentru oprirea controlată, folosește `Ctrl+C`.

Aplicația păstrează Host, Origin, CSRF, limita de încărcare de 10 MiB, parserul XML securizat și lipsa stocării intenționate. XML-ul este procesat local în memorie; factura nu este trimisă către servicii externe.

## Verificare și limite

Testele automatizate folosesc doar date sintetice și simulează deschiderea Edge și ciclul de viață al serverului. Build-ul pe Windows, pornirea dintr-un director de lucru diferit, deschiderea Edge, încărcarea XML-ului sintetic, imprimarea și scenariul de port ocupat trebuie verificate înainte de acceptarea pachetului. Confirmarea finală că aplicația funcționează pe un calculator Windows fără Python separat necesită o astfel de verificare manuală; testele automate nu demonstrează acest lucru.

### Rezultatele verificării Task 006

- Build-ul `--onedir` a reușit pe Windows 11 cu Python 3.13.14 și PyInstaller 6.22.3; artefactul este `dist\XmlToPdf\XmlToPdf.exe`.
- Folderul construit conține 126 fișiere, însumează 31.145.568 octeți și include runtime-ul Python, șabloanele și CSS-ul. Verificarea nu a găsit XML, PDF, teste sau `.venv` în distribuție.
- `pytest`: 106 teste trecute; `git diff --check`: fără erori.
- Portul `127.0.0.1:5000` era deja ocupat înaintea testului. Build-ul final a fost pornit din alt director și a afișat mesajul de port ocupat, apoi s-a închis fără traceback și fără a porni Edge ori un al doilea server.
- Testele automate acoperă upload-ul, randarea, securitatea, resource lookup independent de directorul curent, deschiderea Edge simulată și închiderea serverului.
- Pornirea cu port liber, verificarea vizuală a ferestrei Edge, încărcarea prin interfața Edge și imprimarea PDF nu au putut fi atribuite build-ului final, deoarece portul fix era ocupat și Edge nu era disponibil pentru control vizual în sesiunea de test.
- Nu a fost disponibil un calculator fără Python instalat separat. Acceptarea finală a folderului portabil rămâne condiționată de verificarea manuală pe un astfel de calculator.
