# AGENTS.md — Instrucțiuni pentru Codex în XmlToPdf

## Contextul proiectului

XmlToPdf este o aplicație **web locală pe Windows**, scrisă în Python, care afișează documente RO e-Factura UBL `Invoice` într-un format clasic de factură. Afișarea se face ca HTML, iar imprimarea/salvarea PDF se realizează **numai la cerere**, prin dialogul browserului. Aplicația funcționează offline după instalare.

Înainte de o schimbare substanțială, citește secțiunile relevante din:

- `docs/PROJECT_STATUS.md` — versiunea publicată, ce este implementat, verificările, limitările și următoarea etapă recomandată. Consultă-l la începutul fiecărui task.
- `docs/REQUIREMENTS.md` — cerințe și criterii de acceptare;
- `docs/DECISIONS.md` — decizii confirmate și întrebări deschise;
- `README.md` — stadiul proiectului și modul de lucru.

Nu trata presupunerile din conversație ca decizii aprobate. Dacă există contradicții între documente, semnalează-le și solicită clarificare înainte de implementare.

## Limba și convențiile

- Documentația și explicațiile către utilizator: **română**.
- Numele de module, funcții, clase și identificatori Python: **engleză**.
- Păstrează neschimbate numele tehnice UBL, namespace-urile, comenzile și căile cunoscute.
- Preferă implementări simple, testabile și dependențe puține.

## Fluxul de lucru

1. Verifică `git status` și citește codul relevant înainte de editare.
2. Dacă taskul este de explorare sau read-only, **nu crea și nu modifica fișiere**.
3. Pentru modificări ample, prezintă planul și criteriile de acceptare înainte de implementare.
4. Lucrează doar în domeniul taskului aprobat; evită refactorizări necerute.
5. Adaugă sau adaptează teste pentru comportamentul modificat.
6. Rulează verificările disponibile și declară exact ce a fost și ce nu a fost executat.
7. La final, rezumă fișierele schimbate, testele, rezultatele și limitările.
8. După un milestone important, actualizează `docs/PROJECT_STATUS.md` cu stadiul, verificările relevante și problemele rămase deschise.

## Reguli funcționale care nu se negociază implicit

- **XML-ul este sursa de adevăr.** Păstrează valorile financiare declarate în XML; nu recalcula și nu înlocui totaluri pentru afișare.
- **Nu emite avertizări de reconciliere financiară și nu bloca afișarea/imprimarea din cauza diferențelor aritmetice.** XML-ul malformat sau tipul nesuportat poate produce eroare explicită.
- Respectă URI-urile namespace-urilor UBL; nu presupune prefixe XML literale.
- Păstrează toate elementele repetate relevante: `InvoiceLine`, `PaymentMeans`, `TaxSubtotal`.
- Nu inventa valori lipsă. Pentru câmpurile minime de acceptare și tratarea câmpurilor opționale, urmează `docs/REQUIREMENTS.md`.
- Afișează textul zecimal al sumelor așa cum apare în conținutul XML după eliminarea spațiilor albe exterioare: nu localiza separatorul, nu adăuga separatori de mii, nu rotunji și nu recalcula. Păstrează moneda și unitățile distincte. Dacă o operație internă cere calcule, folosește `Decimal`, nu `float`, și nu înlocui textul afișat.
- Afișarea se face în HTML, cu număr variabil de linii. Imprimarea este **A4 landscape** și trebuie să permită paginare automată fără omisiuni ori suprapuneri.
- PDF-ul nu se generează de backend în MVP. Acțiunea de imprimare deschide dialogul browserului. Nu urmări compatibilitate pixel-perfect între browsere.
- Nu introduce comunicare cu ANAF, hosting public, autentificare, bază de date, istoric sau motor PDF nou fără aprobare explicită.

## Securitate și confidențialitate

- Procesează datele local; serverul trebuie să asculte pe `127.0.0.1`, nu pe `0.0.0.0`.
- Nu introduce acces la internet, CDN-uri, fonturi remote sau servicii externe în fluxul de conversie.
- Tratează XML-ul drept intrare neîncredere: corpul cererii de încărcare nu poate depăși **10 MiB**; respinge depășirea înainte de parsarea XML. Dezactivează DTD-urile și entitățile externe, accesul la rețea, XInclude și recuperarea XML-ului malformat; nu activa modul `huge_tree`.
- Nu salva XML-ul încărcat pe disc și nu folosi numele furnizat de client ca o cale. Limitează memoria și timpul de procesare prin setările serverului/parserului compatibile cu plafonul de 10 MiB.
- Verifică `Host` și `Origin` pentru originea locală permisă și protejează POST-ul de încărcare contra CSRF; escapează automat conținutul XML introdus în HTML.
- Folosește `Cache-Control: no-store` pentru răspunsurile cu facturi. Nu afișa datele facturilor, conținutul XML sau numele fișierului în loguri, rapoarte ori mesaje Codex dacă nu sunt necesare.
- Nu adăuga în Git documente reale sau date personale. `7004378.xml` și `7004378.pdf` sunt exclusiv referințe locale; folosește teste sintetice/anonimizate pentru commituri.
- Mostrele reale se păstrează numai în `samples/private/` sau la căile exacte ignorate din `.gitignore`. Înainte de staging/commit, verifică `git status`, `git diff --staged` și fișierele ignorate; regulile `.gitignore` nu protejează împotriva `git add -f`.
- Fixture-urile XML/PDF versionate se păstrează în `tests/fixtures/` și conțin numai date sintetice sau anonimizate; nu se adaugă mostre reale sub această cale.
- Nu include chei, tokenuri sau fișiere `.env` în commituri.

## Git și autorizarea operațiilor

- Păstrează schimbările existente ale utilizatorului; nu suprascrie lucrări nelegate de task.
- Nu executa `git reset --hard`, `git clean -fd`, ștergeri de branch sau alte operații distructive fără aprobare explicită.
- Propune branch-uri de lucru pentru implementări. Nu face push, merge, release sau schimbări în repository-ul remote fără aprobare explicită.
- Nu comite facturi reale sau alte fișiere sensibile. Verifică `git status` și `git diff --staged` înainte de un commit.
- Dacă taskul cere doar redactarea documentației, nu începe implementarea aplicației.

## Criterii de închidere a unui task

- Comportamentul este conform cerințelor aprobate.
- Testele relevante sunt rulate sau imposibilitatea rulării este descrisă corect.
- Nu există modificări în afara domeniului aprobat.
- Documentația este actualizată numai dacă schimbarea o cere.
- Rezumatul final distinge faptele verificate de presupuneri și de activitățile rămase.
