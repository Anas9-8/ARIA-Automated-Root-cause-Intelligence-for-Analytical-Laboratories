
# ARIA

ARIA ist ein intelligentes System zur Qualitätskontrolle im medizinischen Labor,
das Fehlerursachen automatisch erkennt und erklärt.

Automatisierte Ursachenanalyse für Analyselabore

## Das Problem

Jedes Labor führt täglich Qualitätskontrolltests (QC) durch.
Wenn ein QC-Lauf fehlschlägt, wissen die Techniker, dass das Ergebnis
falsch ist. Häufig verbringen sie Stunden mit der Ursachenforschung:
War es das Reagenz-Los? Das Gerät? Die Temperatur? Die Kalibrierung?

ARIA beantwortet diese Frage in Sekunden — mit kausaler KI statt reiner Statistik.

## Hauptmerkmale

- Westgard-Regeln für QC (Standard in allen Laboren weltweit)
- Kausale KI mit DoWhy (Microsoft/PyWhy)
- Kontrafaktische Simulation: "Was wäre gewesen, wenn X anders gewesen wäre?"
- FastAPI REST-Schnittstelle für LIMS-Integration
- MCP-Server für KI-Assistenten (Claude und andere)
- Web-Dashboard mit 5 Seiten (FastAPI + Jinja2 + Plotly.js)

## Schnellstart

```
make setup
make data
make run
```

Öffnen: http://localhost:8000

## Datenquellen

Die QC-Zeitreihendaten sind synthetisch generiert. Echte Westgard-Kalibrierungsprotokolle
sind in klinischen Einrichtungen vertraulich — synthetische Daten sind der Industriestandard
für diesen Typ von MLOps-Projekten.
Der synthetische Generator wurde anhand echter MIMIC-IV-Demo-Laborverteilungen
(PhysioNet, 2023) kalibriert, um physiologisch korrekte Wertebereiche für alle
8 Testtypen sicherzustellen.

- Synthetisch: 180 Tage realistische QC-Daten (8 Tests, 3 Geräte, 3 QC-Stufen)
- Referenzdaten: MIMIC-IV Clinical Database Demo (PhysioNet, kostenloser Zugang)

## Zielbranchen

- Kliniken: Universitätsklinikum Heidelberg (UKHD)
- Forschung: DKFZ, EMBL Heidelberg
- Pharma: Roche Diagnostics, Bayer, Merck KGaA
- Jedes Labor mit QC-Prozessen

## Technologie

Python 3.11, DoWhy, pgmpy, FastAPI, Jinja2, Plotly.js, MCP, SQLite, Docker

## Kernaussage

"Die meisten QC-Systeme sagen Ihnen, DASS ein Experiment fehlgeschlagen ist.
ARIA sagt Ihnen, WARUM — und was beim nächsten Mal geändert werden muss."
