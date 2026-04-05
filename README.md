# ARIA

Automated Root-cause Intelligence for Analytical Laboratories

ARIA is a causal AI system for clinical, research, and industrial laboratories.
It monitors QC (Quality Control) data from lab instruments and identifies
the root cause of failures - not just that a failure occurred, but WHY.

## The Problem ARIA Solves

Every lab runs daily QC checks. When a QC run fails, the technician knows
the result is wrong. But they often spend hours investigating: was it the
reagent lot? the instrument? the temperature? a calibration issue?

ARIA answers this question in seconds using causal AI, not just statistics.

## Key Features

- Westgard QC rule engine (1-2s, 1-3s, 2-2s, R-4s, 4-1s, 10x)
- Causal graph learning with DoWhy
- Counterfactual simulation: "what if we had changed X?"
- FastAPI REST backend for LIMS integration
- MCP server for AI assistant integration
- Streamlit dashboard with architecture diagrams

## Quick Start

```
make setup
make data
make run
```

Open http://localhost:8501

## Data Sources

The QC time-series data is synthetic by design. Real Westgard calibration logs
are confidential in clinical settings — synthetic data is the industry standard
for this type of MLOps project.
The synthetic generator is calibrated against real MIMIC-IV Demo lab distributions
(PhysioNet, 2023) to ensure physiologically accurate value ranges for all 8 test types.

- Synthetic: 180 days of realistic QC data (8 tests, 3 instruments, 3 QC levels)
- Real reference: MIMIC-IV Clinical Database Demo (PhysioNet, free access)

## Target Institutions

- Clinical hospitals: Uniklinik Heidelberg (UKHD)
- Research: DKFZ, EMBL Heidelberg
- Pharma: Roche Diagnostics, Bayer, Merck
- Any laboratory using QC methods

## Tech Stack

Python 3.11, DoWhy, pgmpy, FastAPI, MCP, Streamlit, Docker

## Author

Built by a Biotechnologischer Assistent (BTA) + Machine Learning Engineer.
Domain knowledge from real lab training combined with modern causal AI methods.
