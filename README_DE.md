# ARIA

**Automatisierte Ursachenanalyse fur Analyselabore**

[![Live auf AWS](https://img.shields.io/badge/Live%20auf-AWS%20EC2-FF9900?style=flat&logo=amazon-aws)](http://3.78.247.13:8000/causal)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF?style=flat&logo=github-actions)](https://github.com/Anas9-8/ARIA-Automated-Root-cause-Intelligence-for-Analytical-Laboratories/actions)
[![Docker](https://img.shields.io/badge/Deployed%20mit-Docker-2496ED?style=flat&logo=docker)](http://3.78.247.13:8000/health)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116-009688?style=flat&logo=fastapi)](http://3.78.247.13:8000/docs)

---

## Live-Deployment — Keine Installation erforderlich

Die Anwendung lauft auf AWS EC2. Einfach einen der folgenden Links im Browser offnen:

| | Link |
|---|---|
| Dashboard | http://3.78.247.13:8000/causal |
| QC-Ubersicht | http://3.78.247.13:8000/ |
| Ursachenanalyse | http://3.78.247.13:8000/explainer |
| Aktive Warnungen | http://3.78.247.13:8000/alerts |
| API-Dokumentation (Swagger) | http://3.78.247.13:8000/docs |
| Health Check | http://3.78.247.13:8000/health |
| CI/CD-Pipeline | https://github.com/Anas9-8/ARIA-Automated-Root-cause-Intelligence-for-Analytical-Laboratories/actions |

Kein Konto, kein Login, kein Setup. Die vollstandige kausale KI-Analyse und alle interaktiven Diagramme sind live verfugbar.

---

## CI/CD-Pipeline

Jeder `git push` auf `main` lost ein automatisches Deployment aus:

```
git push origin main
       |
       v
GitHub Actions (.github/workflows/deploy.yml)
       |
       v
SSH in AWS EC2 (appleboy/ssh-action)
       |
       +-- git pull origin main
       +-- docker-compose down --remove-orphans
       +-- docker-compose up --build -d
       +-- Health-Check-Schleife: alle 5s /health prufen (60s Timeout)
       +-- /causal und /docs auf Verfugbarkeit prufen
       |
       v
Live unter http://3.78.247.13:8000
```

Das Deployment lauft vollstandig automatisch. Secrets (EC2-IP und privater SSH-Schlussel) sind in GitHub Actions gespeichert und erscheinen nie im Repository.

---

## Das Problem

Jedes Labor fuhrt taglich Qualitatskontrolltests (QC) durch. Wenn ein QC-Lauf fehlschlagt, wissen die Techniker, dass das Ergebnis falsch ist. Aber warum? War es das Reagenz-Los? Das Gerat? Temperaturdrift? Eine zu lang zuruckliegende Kalibrierung?

In den meisten Laboren dauert diese Ursachenforschung Stunden und hangt von Erfahrung ab. ARIA beantwortet die Frage in Sekunden — mit kausaler Inferenz, nicht mit Korrelation.

---

## Losung

ARIA erstellt einen gerichteten azyklischen Graphen (DAG) uber die Laborumgebungsvariablen und verwendet den Backdoor-Schatzwert von DoWhy, um durchschnittliche Behandlungseffekte auf den QC-Z-Score zu berechnen. Anschliessend wird eine naturlichsprachliche Erklarung jedes Fehlers erstellt und kontrafaktische Simulationen ermoglicht: "Wenn die Temperatur 19 Grad statt 27 gewesen ware — hatte dieser Lauf bestanden?"

Die vollstandige Analyse — von Roh-QC-Daten bis zur kontrafaktischen Antwort — ist uber ein Web-Dashboard zuganglich, das vom selben FastAPI-Backend bereitgestellt wird.

---

## Hauptmerkmale

- **Westgard-Multi-Regel-QC-Engine** — sechs Regeln (1-2s, 1-3s, 2-2s, R-4s, 4-1s, 10x) mit abgestuften Zeitfenstern.
- **Kausaler Graph mit DoWhy** — Backdoor-lineare Regression schatzt, wie Temperatur, Kalibrierungsalter und Reagenz-Los den Z-Score kausal beeinflussen.
- **Kontrafaktische Simulation** — Laborbedingungen eines fehlgeschlagenen Laufs anpassen und simulieren, ob sich das Ergebnis andern wurde.
- **Ursachenerkarer** — Naturlichsprachliche Ausgabe fur jeden Fehler mit einer Rangliste der beitragenden Faktoren.
- **FastAPI REST-Backend** — alle Analysen sind per HTTP verfugbar. Geeignet fur LIMS-Integration.
- **HTML-Dashboard** — funf Seiten serverseitig mit Jinja2 gerendert, Diagramme uber Plotly.js.
- **SQLite-Verlauf** — jede QC-Auswertung wird fur Trendverfolgung gespeichert.
- **MCP-Server** — stellt ARIAs Analyse als Tools fur KI-Assistenten bereit.
- **Docker-Deployment** — ein einzelnes `docker-compose up --build -d` startet den gesamten Stack.
- **GitHub Actions CI/CD** — Push auf `main` lost automatisches Deployment auf EC2 aus.

---

## Technologie-Stack

| Tool | Version | Rolle |
|------|---------|-------|
| Python | 3.11 | Gesamte Backend-Logik |
| FastAPI | 0.116 | REST-API + HTML-Seitenbereitstellung |
| Uvicorn | 0.30 | ASGI-Server |
| Jinja2 | 3.1 | HTML-Template-Engine |
| Plotly.js | 2.32 | Alle interaktiven Diagramme |
| DoWhy | 0.11 | Kausales Modell + ATE-Schatzung |
| pgmpy | 0.1.25 | DAG-Backend fur DoWhy |
| scikit-learn | 1.5 | Lineare Regression |
| pandas | 2.2 | Datenladen und -transformation |
| numpy | 1.26 | Z-Score-Berechnung |
| SQLite | stdlib | QC-Ergebnisverlauf |
| MCP | 1.0 | KI-Assistenten-Integration |
| Docker | — | Container-Paketierung |
| GitHub Actions | — | CI/CD-Pipeline |
| AWS EC2 | — | Produktions-Hosting |

---

## Dashboard-Seiten

| Seite | Live-URL | Inhalt |
|-------|----------|--------|
| QC-Ubersicht | [/](http://3.78.247.13:8000/) | KPI-Karten, Status-Donut, Balkendiagramm, durchsuchbare QC-Tabelle |
| Kausalanalyse | [/causal](http://3.78.247.13:8000/causal) | ATE-Balkendiagramm, 7-Knoten-DAG, Ergebnistabelle |
| Ursachenerkarer | [/explainer](http://3.78.247.13:8000/explainer) | Fehler-Schieberegler, Z-Score-Gauge, kontrafaktische Simulation |
| Aktive Warnungen | [/alerts](http://3.78.247.13:8000/alerts) | Alle FAIL-Status-Eintrage mit Schweregrad, Westgard-Regelreferenz |
| Architektur | [/architecture](http://3.78.247.13:8000/architecture) | DatenflussDiagramm, Tool-Stack, kommentierter Dateibaum |

---

## Wie die Kausalanalyse funktioniert

ARIA erstellt einen domaneninformierten DAG mit sieben Knoten:

```
lab_temp_c -----> z_score
hours_since_cal -> z_score
reagent_lot -----> z_score
lab_temp_c -----> hours_since_cal
```

Mithilfe des Backdoor-Kriteriums von DoWhy wird der durchschnittliche Behandlungseffekt jeder vorgelagerten Variable auf den Z-Score geschatzt.

Eine Erhohung von `lab_temp_c` um 1 Grad (uber 22C) addiert ca. +0,35 zur Z-Score-Abweichung. Eine Erhohung von `hours_since_cal` um 10 Stunden fuhrt zu negativem Drift. Reagenz-Los-Effekte werden als numerische Bias-Offsets kodiert.

Kontrafakten werden analytisch berechnet: neuer Z-Score = ursprunglicher Z-Score + Summe((neuer Wert - alter Wert) * ATE).

---

## QC-Engine

Sechs Westgard-Regeln werden pro Gerat-Test-Level-Kombination ausgewertet:

| Regel | Typ | Ausloser |
|-------|-----|----------|
| 1-2s | Warnung | \|z\| > 2,0 (letzter Wert) |
| 1-3s | Ablehnung | \|z\| > 3,0 (letzter Wert) |
| 2-2s | Ablehnung | Zwei aufeinanderfolgende Werte > 2,0 SD in gleicher Richtung |
| R-4s | Ablehnung | Bereich zwischen aufeinanderfolgenden Werten > 4 SD |
| 4-1s | Ablehnung | Vier aufeinanderfolgende Werte alle > 1,0 SD in gleicher Richtung |
| 10x | Ablehnung | Zehn aufeinanderfolgende Werte auf derselben Seite des Mittelwerts |

---

## Datenquellen

Die QC-Zeitreihendaten sind synthetisch generiert. Echte Westgard-Kalibrierungsprotokolle sind in klinischen Einrichtungen vertraulich. Der synthetische Generator ist gegen echte **MIMIC-IV-Demo**-Laborverteilungen (PhysioNet, 2023) kalibriert.

- 180 Tage QC-Daten
- 3 Gerate (INST-A, INST-B, INST-C)
- 8 Tests: Glucose, Kreatinin, Natrium, Kalium, ALT, Hamoglobin, Kalzium, Bilirubin
- 3 QC-Stufen pro Test
- 19 Reagenz-Lose
- 116.640 Datensatze insgesamt

---

## Lokale Entwicklung (Optional)

Die App lauft bereits auf AWS. Eine lokale Installation ist nur notig, wenn der Code bearbeitet werden soll.

**Voraussetzungen:** Python 3.11+, make

```bash
git clone https://github.com/Anas9-8/ARIA-Automated-Root-cause-Intelligence-for-Analytical-Laboratories.git
cd ARIA-Automated-Root-cause-Intelligence-for-Analytical-Laboratories

make setup     # erstellt .venv und installiert Abhangigkeiten
make data      # generiert synthetischen QC-Datensatz
make run       # startet FastAPI unter http://localhost:8000
```

### Docker (lokal)

```bash
docker-compose up --build -d
```

### Tests

```bash
make test
```

---

## Deployment auf AWS EC2

### Ablauf

Der Workflow (`.github/workflows/deploy.yml`) lauft bei jedem Push auf `main`:

1. GitHub Actions verbindet sich per SSH mit der EC2-Instanz.
2. `git pull origin main` ladt den neuesten Code.
3. `docker-compose down --remove-orphans` stoppt und entfernt bestehende Container.
4. `docker-compose up --build -d` baut das Image neu und startet den Container.
5. Eine Schleife pruft `/health` alle 5 Sekunden fur bis zu 60 Sekunden.
6. Abschliessend werden `/causal` und `/docs` auf Verfugbarkeit gepruft.

### Erforderliche GitHub Secrets

| Secret | Wert |
|--------|------|
| `EC2_HOST` | Offentliche IP der EC2-Instanz |
| `EC2_SSH_KEY` | Inhalt der privaten `.pem`-Schlussseldatei |

---

## Kernaussage

Die meisten QC-Systeme sagen Ihnen, DASS ein Experiment fehlgeschlagen ist. ARIA sagt Ihnen, WARUM — und was beim nachsten Mal geandert werden muss.

---

## Autor

Entwickelt von einem Biotechnologischen Assistenten (BTA) mit Machine-Learning-Ingenieurausbildung. Fachwissen aus realer Laborpraxis kombiniert mit kausalen KI-Methoden aus dem PyWhy-Okosystem.
