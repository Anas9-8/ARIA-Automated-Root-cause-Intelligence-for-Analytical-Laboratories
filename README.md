# ARIA

**Automated Root-cause Intelligence for Analytical Laboratories**

[![Live on AWS](https://img.shields.io/badge/Live%20on-AWS%20EC2-FF9900?style=flat&logo=amazon-aws)](http://3.78.247.13:8000/causal)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF?style=flat&logo=github-actions)](https://github.com/Anas9-8/ARIA-Automated-Root-cause-Intelligence-for-Analytical-Laboratories/actions)
[![Docker](https://img.shields.io/badge/Deployed%20with-Docker-2496ED?style=flat&logo=docker)](http://3.78.247.13:8000/health)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116-009688?style=flat&logo=fastapi)](http://3.78.247.13:8000/docs)
[![MCP](https://img.shields.io/badge/MCP-server-7c3aed?style=flat)](http://3.78.247.13:8000/mcp)

ARIA reads daily clinical-lab QC runs, applies the six standard Westgard rules,
and uses a DoWhy causal model to answer **why** a run failed — not just that it did.
A counterfactual simulator on the dashboard lets you replay any failed run with
different lab conditions and see whether it would have passed.

---

## Live deployment — no installation required

| | Link |
|---|---|
| QC Overview | http://3.78.247.13:8000/ |
| Causal Analysis | http://3.78.247.13:8000/causal |
| Counterfactual / Root Cause | http://3.78.247.13:8000/explainer |
| Active Alerts | http://3.78.247.13:8000/alerts |
| AI Integration (MCP) | http://3.78.247.13:8000/mcp |
| Architecture | http://3.78.247.13:8000/architecture |
| API Docs (Swagger) | http://3.78.247.13:8000/docs |
| Health Check | http://3.78.247.13:8000/health |

No account, no setup. The full causal AI analysis and every interactive chart are live.

---

## The problem

Every clinical lab runs daily quality-control checks. When a QC run fails, the
technician knows the result is wrong — but not why. Was it the reagent lot? The
instrument? Temperature drift? A calibration that ran too long?

In most labs that investigation takes hours and relies on tribal knowledge. ARIA
answers the question in seconds using **causal inference, not correlation**.

---

## What's in the box

- **Westgard multi-rule QC engine** — six rules (1-2s, 1-3s, 2-2s, R-4s, 4-1s, 10x)
  with clinically appropriate tiered time windows so old violations do not
  inflate today's status.
- **Causal graph + DoWhy ATE estimator** — the outcome is the continuous QC
  z-score (σ units), so every coefficient is "σ change in z-score per unit
  change in this variable". That keeps the counterfactual math in the same
  units as the chart and the explanation.
- **Counterfactual simulator (the showcase feature)** — a hero card on the
  Explainer page with paired before/after gauges. Pick any out-of-control
  run, dial temperature and calibration sliders, click Run Simulation, and
  watch the simulated z-score move.
- **Z-score trend with Westgard control limits** on the Overview page —
  filterable per instrument / test / QC level, ±2σ and ±3σ guides drawn in.
- **PNG export** on every chart (Plotly camera button) and **CSV export** on
  every table (one click per view: status / failures / trend / raw).
- **Root-cause natural-language explainer** — for each failure: ranked
  contributing factors, a recommendation, and a reagent-lot bias hint.
- **MCP server** — same analysis exposed as tools to Claude Desktop / Cursor /
  any MCP client. Three resources, three tools, stdio transport.
- **FastAPI REST backend** — every analysis is also reachable over HTTP.
  Suitable for LIMS integration.
- **SQLite history** with a UNIQUE index — repeated polls do not duplicate rows.
- **Docker + GitHub Actions CI/CD** — push to `main` deploys to AWS EC2.

---

## Counterfactual simulator (the showcase)

The Explainer page (`/explainer`) is built around a single hero card so the
counterfactual is the first thing you see, not buried under a table:

- **Failure selector** — slider over every QC observation with `|z| > 2σ`
  (warnings *and* rejections; severity is shown per row).
- **Paired gauges** — Original z-score on the left, Simulated z-score on the
  right, with an arrow that turns green when the simulation improves the run.
- **Two sliders** — Lab temperature (°C) and Hours-since-calibration. Both
  pre-fill to the failed run's actual values so the starting state is honest.
- **Run Simulation** posts to `/causal/counterfactual`; the simulator applies
  the engine's ATEs to the deltas and returns the new z-score.
- **Reset** snaps both sliders back to the original conditions.

Math:

```
simulated_z = original_z + Σ (new_value − original_value) * ATE_var
```

Because the engine outcome is the z-score itself, ATEs are in σ units, so this
is dimensionally consistent.

---

## CI/CD pipeline

```
git push origin main
       |
       v
GitHub Actions (.github/workflows/deploy.yml)
       |
       v
SSH into AWS EC2 (appleboy/ssh-action)
       |
       +-- git pull origin main
       +-- docker-compose down --remove-orphans
       +-- docker-compose up --build -d
       +-- health-check loop: polls /health every 5s for 60s
       +-- verify /causal and /docs respond
       |
       v
Live at http://3.78.247.13:8000
```

Secrets (EC2 host, private SSH key) are stored in GitHub Actions and never
appear in the repository.

---

## Causal model

Domain-informed DAG with one outcome and four upstream causes:

```
lab_temp_c       -> z_score
humidity_pct     -> z_score
reagent_lot_id   -> z_score
hours_since_cal  -> z_score
```

DoWhy's backdoor linear regression is run once per cause; each estimate is the
σ-change in the QC z-score per unit change in that cause. An ATE of `+0.012` on
`lab_temp_c` means "every °C raises the z-score by 0.012 σ on average".

Counterfactuals reuse those same coefficients, so the simulated z-score and the
chart label are in the same units.

---

## QC engine

| Rule | Type | Trigger |
|------|------|---------|
| 1-2s | Warning | `|z| > 2.0` (most recent value) |
| 1-3s | Rejection | `|z| > 3.0` (most recent value) |
| 2-2s | Rejection | Two consecutive values > 2.0 σ in same direction |
| R-4s | Rejection | Range between two consecutive values > 4 σ |
| 4-1s | Rejection | Four consecutive values all > 1.0 σ in same direction |
| 10x  | Rejection | Ten consecutive values on the same side of the mean |

Tiered time windows per rule type stop stale violations from inflating today's
status.

---

## Data

The QC time-series is **synthetic by design**. Real Westgard logs are
confidential. The synthetic generator is calibrated against the public
**MIMIC-IV Demo** dataset (PhysioNet, 2023) so that value ranges, units, and
instrument variation are physiologically realistic.

| | |
|---|---|
| Records | 38,880 |
| Days | 180 |
| Instruments | COBAS-C311-01, COBAS-C311-02, COBAS-C501-03 |
| Tests | Glucose, Creatinine, Sodium, Potassium, ALT, Hemoglobin, Calcium, Bilirubin |
| QC levels | L1, L2, L3 |
| Reagent lots | 19 (`-01` reference, `-02` ≈ −0.8 % bias, `-03` ≈ −2 % bias) |
| z-score range | clipped to `[−4, +4]` (anything beyond is broken instrument, not drift) |

---

## MCP server

ARIA is also an **MCP server** — every analysis on the dashboard is reachable
as a tool from Claude Desktop, Cursor, Cline, or any custom MCP client.

Start it locally:

```bash
make mcp
```

What it exposes (matches `src/mcp/server.py` exactly):

**Resources**
- `lab://qc-status` — Westgard status per instrument-test-level.
- `lab://causal-model` — DoWhy ATE results (σ per unit on the QC z-score).
- `lab://summary` — record count, instruments, tests, reagent lots, date range.

**Tools**
- `get_qc_failures()` — active failures + which Westgard rule fired.
- `get_root_cause()` — top causal factor and full ATE table.
- `get_instrument_status({ instrument_id })` — per-instrument summary, e.g.
  `instrument_id = "COBAS-C311-01"`.

Wire into Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "aria": {
      "command": "python",
      "args": ["-m", "src.mcp.server"],
      "cwd": "/absolute/path/to/ARIA"
    }
  }
}
```

After restarting Claude Desktop you can ask things like *"Which Glucose runs
on COBAS-C311-01 are failing today?"* and Claude will call ARIA's tools.

---

## Technology stack

| Tool | Version | Role |
|------|---------|------|
| Python | 3.11 | All backend logic |
| FastAPI | 0.116 | REST API + HTML page serving |
| Uvicorn | 0.30 | ASGI server |
| Jinja2 | 3.1 | HTML template engine |
| Plotly.js | 2.32 | Every interactive chart (PNG export built in) |
| DoWhy | 0.11 | Causal model + ATE estimation |
| pgmpy | 0.1.25 | DAG backend for DoWhy |
| scikit-learn | 1.5 | Linear regression estimator |
| pandas | 2.2 | Data loading and transformation |
| numpy | 1.26 | z-score computation |
| SQLite | stdlib | QC result history (idempotent inserts) |
| MCP | 1.0 | AI assistant integration |
| Docker | — | Container packaging |
| GitHub Actions | — | CI/CD pipeline |
| AWS EC2 | — | Production hosting |

---

## REST API

Live interactive docs: http://3.78.247.13:8000/docs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/summary` | Dataset summary statistics |
| GET | `/qc/status` | QC status for all instrument-test-level combinations (idempotent) |
| GET | `/qc/failures` | Only FAIL-status records |
| GET | `/api/failures` | Out-of-control rows for the explainer (`severity=warn` or `fail`); returns `{total, shown, records}` |
| GET | `/api/trend/options` | Available instruments / tests / QC levels for the trend dropdowns |
| GET | `/api/trend` | z-score time series with optional filters and downsampling |
| GET | `/api/export.csv` | Download a view as CSV (`view=qc|failures|trend|raw`) |
| GET | `/causal/analysis` | ATE values from the causal model |
| GET | `/causal/explain/{row_index}` | Root cause + recommendation for a row |
| POST | `/causal/counterfactual` | Counterfactual simulation |
| GET | `/causal/simulate/{row_index}` | curl-friendly counterfactual variant |
| GET | `/db/recent` | Last N results from SQLite history |

---

## Local development

The app is already live on AWS. Local setup is only needed if you want to
modify the code.

**Requirements:** Python 3.11+, make.

```bash
git clone https://github.com/Anas9-8/ARIA-Automated-Root-cause-Intelligence-for-Analytical-Laboratories.git
cd ARIA-Automated-Root-cause-Intelligence-for-Analytical-Laboratories

make setup     # creates .venv and installs dependencies
make data      # generates synthetic QC dataset (38,880 records)
make run       # starts FastAPI on http://localhost:8000
```

### Docker (local)

```bash
docker-compose up --build -d
```

The container builds, generates synthetic data, and starts the FastAPI server
on port 8000. The `data/` directory is mounted as a volume so the SQLite
database persists across restarts.

### Tests

```bash
make test
```

- `tests/test_qc.py` — unit tests for all six Westgard rules.
- `tests/test_causal.py` — covers `prepare_causal_data`, the DAG shape, and the
  fact that every edge terminates at the `z_score` outcome.
- `tests/test_api.py` — FastAPI endpoint tests via httpx TestClient.

---

## Deployment on AWS EC2

The deploy workflow (`.github/workflows/deploy.yml`) runs on every push to `main`:

1. GitHub Actions SSHs into the EC2 instance using a stored private key.
2. `git pull origin main` fetches the latest code.
3. `docker-compose down --remove-orphans` stops the existing container cleanly.
4. `docker-compose up --build -d` rebuilds and starts.
5. A retry loop polls `/health` every 5 s for up to 60 s.
6. Final checks confirm `/causal` and `/docs` both respond before marking the
   deploy successful.

**Secrets**

| Secret | Value |
|--------|-------|
| `EC2_HOST` | Public IP of the EC2 instance |
| `EC2_SSH_KEY` | Contents of the private `.pem` key file |

---

## Limitations & honest notes

- **Synthetic data.** Distributions are MIMIC-IV-calibrated, but every record
  was generated by `data/synthetic/generate.py`. The bias coefficients in the
  generator (`lot_bias`, `temperature_effect`, `calibration_drift`) are
  deliberately small so the resulting z-scores stay in the realistic
  `[−4, +4]` range.
- **Lot bias semantics.** `-03` lots carry roughly **−2 %** mean bias, `-02`
  roughly **−0.8 %**, `-01` is the reference. The explainer labels in the UI
  match these coefficients exactly. (Earlier revisions of the project showed
  larger numbers — those have been corrected.)
- **Mediator nodes.** Earlier revisions had `reagent_activity` and `drift` as
  mediators in the DAG, but those were *constructed* deterministically from
  the inputs, which conflated a synthetic feature with a measured one. The
  current DAG models direct effects only and uses the continuous z-score as
  the outcome, so each ATE is a real σ-per-unit estimate.
- **Westgard "warnings" vs "failures".** `|z| > 2σ` is a Westgard *warning*
  (1-2s); rejection requires `|z| > 3σ` (1-3s) or a multi-point rule. The API
  surfaces both: `/api/failures?severity=warn` for warnings, `severity=fail`
  for rejections, default returns both with a per-row severity tag.
- **Authentication.** The live deployment is intentionally open for demo
  purposes — there is no auth, no rate limiting. Do not point anything you
  care about at it.

---

## Project structure

```
ARIA/
├── Makefile
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── README.md
├── README_DE.md
│
├── .github/workflows/deploy.yml      <- GitHub Actions CI/CD
│
├── data/
│   ├── raw/mimic_demo/               <- MIMIC-IV reference data
│   ├── processed/
│   └── synthetic/
│       ├── generate.py               <- 38,880 synthetic QC records
│       └── qc_data.csv
│
├── src/
│   ├── ingestion/loader.py           <- CSV parsing + summary stats
│   ├── qc/rules.py                   <- Westgard rules + tiered windows
│   ├── causal/engine.py              <- DoWhy DAG + ATE on z-score
│   ├── explainer/explainer.py        <- Root cause + counterfactual
│   ├── storage/db.py                 <- SQLite, idempotent inserts
│   ├── api/main.py                   <- FastAPI backend (port 8000)
│   └── mcp/server.py                 <- MCP server for AI assistants
│
├── dashboard/
│   ├── static/style.css              <- Dark design system
│   ├── static/charts.js              <- Plotly chart functions
│   └── templates/
│       ├── base.html
│       ├── overview.html             <- KPI + trend + donut + bar + table
│       ├── causal.html               <- ATE chart, DAG, results table
│       ├── explainer.html            <- Counterfactual hero card
│       ├── alerts.html               <- Active failures + Westgard cards
│       ├── mcp.html                  <- MCP integration page
│       └── architecture.html         <- Data flow + tool stack + tree
│
├── scripts/generate_demo.py          <- Playwright → GIF pipeline
└── tests/
    ├── test_qc.py
    ├── test_causal.py
    └── test_api.py
```

---

## Author

Built by a Biotechnologischer Assistent (BTA) with machine-learning engineering
training. Domain knowledge from real lab QC practice combined with causal AI
methods from the PyWhy ecosystem.
