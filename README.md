# XmlToPdf

**Stadiu:** fundația Flask și pagina locală de pornire sunt implementate. Parserul UBL, încărcarea XML, afișarea facturii, imprimarea și launcherul nu sunt încă implementate.

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
- După instalare, procesarea nu are nevoie de internet sau de serviciile ANAF.
- Se acceptă doar XML bine format cu rădăcina UBL `Invoice` și câmpurile minime descrise în `docs/REQUIREMENTS.md`; nu se pretinde validare fiscală/XSD completă.
- Corpul cererii de încărcare este limitat la **10 MiB**. XML-ul nu se persistă intenționat pe disc și valorile facturii nu se scriu în loguri.
- Sumele sunt afișate cu textul zecimal din XML, fără localizare, separatori de mii, rotunjire sau recalculare. Diferențele aritmetice nu produc avertizări și nu blochează afișarea ori imprimarea.

## Arhitectura conceptuală

```text
Fișier XML UBL
     |
     v
Flask local -> Parser UBL (lxml) -> Model factură
                                          |
                                          v
                                  Jinja2 + HTML/CSS
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

Aplicația curentă servește numai pagina HTML de pornire. Nu procesează fișiere XML și nu generează PDF.

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

La distribuire, este planificat un **launcher Windows** care pornește serverul local și deschide automat browserul. Tehnologia de împachetare nu este încă decisă.

## Date de referință și confidențialitate

Documentele locale `7004378.xml` și `7004378.pdf` servesc ca eșantioane de analiză, nu ca fișiere destinate publicării. Pot conține informații reale și **nu trebuie comise în repository-ul public**. Căile lor exacte și `samples/private/` sunt ignorate de `.gitignore`; protecția este disponibilă numai în checkout-urile care conțin și versiunea comisă a acestei reguli.

Pentru documente reale, folosește exclusiv `samples/private/` sau păstrează fișierele în afara repository-ului. Testele publice și CI vor folosi exclusiv date sintetice sau anonimizate. Verifică fișierele staged înainte de fiecare commit; `.gitignore` nu împiedică adăugarea forțată.

## Dezvoltare cu Codex

1. Deschide repository-ul local în Codex.
2. Solicită agentului să citească `AGENTS.md`, cerințele și deciziile relevante.
3. Lucrează pe taskuri mici, cu plan pentru schimbările importante.
4. Revizuiește modificările și rezultatele testelor înainte de publicarea lor în GitHub.

Nu publica fișiere reale de factură și nu începe implementarea doar pe baza faptului că există documentația.
