# ARIA — System Architecture

## Overview

ARIA is a single-service application. One FastAPI process handles everything: it serves the HTML dashboard, responds to REST API calls, runs the QC engine and causal model, and persists results to SQLite. There is no message queue, no separate frontend server, and no external database.

---

## Request Path

```
Browser or LIMS client
        |
        | HTTP request
        v
FastAPI (uvicorn, port 8000)
  src/api/main.py
        |
        +-- GET /              -> templates/overview.html        (Jinja2)
        +-- GET /causal        -> templates/causal.html
        +-- GET /explainer     -> templates/explainer.html       (counterfactual hero)
        +-- GET /alerts        -> templates/alerts.html
        +-- GET /mcp           -> templates/mcp.html              (MCP integration page)
        +-- GET /architecture  -> templates/architecture.html
        |
        +-- GET /qc/status               -> src/qc/rules.py        (Westgard engine)
        +-- GET /qc/failures             -> src/qc/rules.py
        +-- GET /api/failures            -> filtered DataFrame view (severity tag)
        +-- GET /api/trend, /api/trend/options -> z-score time series
        +-- GET /api/export.csv          -> StreamingResponse
        +-- GET /causal/analysis         -> src/causal/engine.py   (DoWhy ATE)
        +-- GET /causal/explain/{id}     -> src/explainer/explainer.py
        +-- POST /causal/counterfactual  -> src/explainer/explainer.py
        +-- GET /causal/simulate/{id}    -> curl-friendly counterfactual GET
        |
        +-- GET /summary                 -> src/ingestion/loader.py
        +-- GET /db/recent               -> src/storage/db.py
```

HTML pages are rendered on the server. Charts are rendered on the client by Plotly.js using data fetched asynchronously from the JSON API endpoints.

---

## Data Pipeline

```
PhysioNet MIMIC-IV Demo
  data/raw/mimic_demo/labevents.csv
        |
        v
data/synthetic/generate.py
  Reads MIMIC-IV value distributions (mean, SD per test).
  Generates 38,880 synthetic QC records across:
    - 180 days
    - 3 instruments (COBAS-C311-01, COBAS-C311-02, COBAS-C501-03)
    - 3 daily QC runs per instrument (07:00 / 12:00 / 18:00)
    - 8 analytes (Glucose, Creatinine, Sodium, Potassium, ALT, Hemoglobin, Calcium, Bilirubin)
    - 3 QC levels per analyte (L1 / L2 / L3)
    - 19 reagent lots with injected bias offsets
  Z-scores clipped to ±4 σ.
  Writes: data/synthetic/qc_data.csv
        |
        v
src/ingestion/loader.py
  Reads qc_data.csv at FastAPI startup.
  Parses timestamps, coerces types, sorts by instrument+test+level+timestamp.
  Returns a pandas DataFrame cached in memory for the process lifetime.
```

---

## Causal Model

```
Domain DAG (networkx DiGraph) — outcome is the continuous z-score (σ units):

  lab_temp_c       -> z_score
  humidity_pct     -> z_score
  reagent_lot_id   -> z_score
  hours_since_cal  -> z_score

DoWhy CausalModel wraps the DAG.
Backdoor linear regression estimates ATE for each treatment variable.

ATE interpretation (σ change in z-score per unit change in treatment):
  lab_temp_c:       small positive σ-effect per °C above ambient
  hours_since_cal:  small negative σ-drift per additional hour
  reagent_lot_id:   small but statistically detectable per-lot offset
  humidity_pct:     near zero in the calibrated synthetic data

ATEs are computed lazily on the first /causal/analysis request and cached.
```

---

## QC Engine

```
src/qc/rules.py

Input:  full DataFrame grouped by (instrument_id, test_name, qc_level)
Output: one row per group with columns:
          status, latest_z, mean_z_last_10, n_rejections,
          rejection_rules, last_timestamp

Rules applied per group (tiered time windows):
  1-2s  -> last 1 record,  |z| > 2.0              (Warning)
  1-3s  -> last 1 record,  |z| > 3.0              (Rejection)
  2-2s  -> last 2 records, both z > +2 or both < -2  (Rejection)
  R-4s  -> last 2 records, range > 4               (Rejection)
  4-1s  -> last 4 records, all |z| > 1, same sign  (Rejection)
  10x   -> last 10 records, all same sign          (Rejection)

Status hierarchy: FAIL > WARNING > PASS
```

---

## Explainer and Counterfactuals

```
src/explainer/explainer.py

explain_failure(record, ates):
  1. Check |z| against thresholds → status (PASS / WARNING / FAIL).
  2. Check whether any environmental variable is outside its normal range.
     If yes → that variable is the operative cause.
     Else if the reagent lot has documented bias (-02 ≈ −0.8 %, -03 ≈ −2 %) →
     reagent lot is the operative cause.
     Else → borderline / random variation; report the statistical driver.
  3. Build a natural-language explanation and a recommendation.
  4. Return: status, explanation, recommendation, top_factors, all_causes,
             reagent_lot_bias.

counterfactual_analysis(record, changes, causal_ates):
  ATEs are σ-per-unit on the z-score, so the math is dimensionally consistent:
    simulated_z = original_z + Σ (new_value − original_value) * ATE_var
  Apply status thresholds to simulated_z and return the verdict.
```

---

## Storage

```
src/storage/db.py

SQLite file: data/aria.db
Schema:
  CREATE TABLE IF NOT EXISTS qc_results (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      instrument_id TEXT NOT NULL,
      test_name     TEXT NOT NULL,
      qc_level      TEXT NOT NULL,
      z_score       REAL NOT NULL,
      status        TEXT NOT NULL,
      timestamp     TEXT NOT NULL,
      created_at    TEXT DEFAULT (datetime('now'))
  )
  CREATE UNIQUE INDEX uq_qc_results_group_ts
    ON qc_results (instrument_id, test_name, qc_level, timestamp)

The unique index makes save_result() idempotent — repeated /qc/status polls
silently no-op via INSERT OR IGNORE instead of duplicating history rows.

Three functions:
  init_db()        -- creates table + index, dedupes any pre-existing rows
  save_result(row) -- INSERT OR IGNORE one QC evaluation row
  get_recent(limit)-- returns last N rows ordered by id DESC
```

---

## MCP Server

```
src/mcp/server.py

Implements Anthropic's Model Context Protocol over stdio transport.

Resources (read-only data):
  lab://qc-status      -- current Westgard status per instrument-test-level
  lab://causal-model   -- DoWhy ATE results (σ per unit on the QC z-score)
  lab://summary        -- record count, instruments, tests, lots, date range

Tools (callable actions):
  get_qc_failures()                          -- active failures + Westgard rules
  get_root_cause()                           -- top causal factor + full ATE table
  get_instrument_status(instrument_id: str)  -- per-instrument summary

Runs as a separate process (make mcp).
The /mcp dashboard page documents this visually with a copy-paste
claude_desktop_config.json snippet.
```

---

## Deployment

```
Docker:
  Dockerfile builds python:3.11-slim image.
  Installs CPU-only torch (avoids 2 GB CUDA download).
  Copies src/, dashboard/, data/.
  Runs generate.py inside the build to embed synthetic data in the image.
  Starts: uvicorn src.api.main:app --host 0.0.0.0 --port 8000

docker-compose.yml:
  Single service "aria".
  Mounts ./data:/app/data so SQLite persists across container restarts.
  Exposes port 8000.

GitHub Actions (.github/workflows/deploy.yml):
  Trigger: push to main.
  Uses appleboy/ssh-action to SSH into EC2.
  On server (set -euxo pipefail so silent failures are impossible):
    git fetch origin main && git reset --hard origin/main
    docker-compose down --remove-orphans
    docker-compose build --no-cache aria       # defeat layer cache
    docker-compose up -d --force-recreate
  Health check loop: curl /health every 5 s for up to 60 s.
  Final smoke checks: /causal and /docs both 200.
```

---

## Dependency Notes

- **torch** is installed before requirements.txt to lock in CPU wheels. pgmpy would otherwise pull CUDA wheels (~2 GB).
- **DoWhy 0.11** requires networkx 3.x and pgmpy 0.1.25. Do not upgrade pgmpy without testing causal engine compatibility.
- **MCP 1.0** follows the Anthropic Model Context Protocol specification. The server uses stdio transport, not HTTP.
