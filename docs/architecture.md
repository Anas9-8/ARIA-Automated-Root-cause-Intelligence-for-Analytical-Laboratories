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
        +-- GET /              -> templates/overview.html    (Jinja2 render)
        +-- GET /causal        -> templates/causal.html
        +-- GET /explainer     -> templates/explainer.html
        +-- GET /alerts        -> templates/alerts.html
        +-- GET /architecture  -> templates/architecture.html
        |
        +-- GET /qc/status     -> src/qc/rules.py           (Westgard engine)
        +-- GET /causal/analysis -> src/causal/engine.py    (DoWhy ATE)
        +-- GET /causal/explain/{id} -> src/explainer/explainer.py
        +-- POST /causal/counterfactual -> src/explainer/explainer.py
        |
        +-- GET /summary       -> src/ingestion/loader.py
        +-- GET /db/recent     -> src/storage/db.py
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
  Generates 116,640 synthetic QC records across:
    - 180 days
    - 3 instruments (INST-A, INST-B, INST-C)
    - 8 analytes (Glucose, Creatinine, Sodium, Potassium, ALT, Hemoglobin, Calcium, Bilirubin)
    - 3 QC levels per analyte
    - 19 reagent lots with injected bias offsets
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
Domain DAG (networkx DiGraph):

  lab_temp_c -------> z_score
  hours_since_cal --> z_score
  reagent_lot ------> z_score
  lab_temp_c -------> hours_since_cal

DoWhy CausalModel wraps the DAG.
Backdoor linear regression estimates ATE for each treatment variable.

ATE interpretation:
  lab_temp_c:       ~ +0.35 z per degree above baseline
  hours_since_cal:  negative drift per additional hour
  reagent_lot_bias: small but statistically detectable per-lot offset

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
  10x   -> last 10 records, all same sign           (Rejection)

Status hierarchy: FAIL > WARNING > PASS
```

---

## Explainer and Counterfactuals

```
src/explainer/explainer.py

explain_failure(record, ates):
  1. Check z-score against thresholds to assign status.
  2. Rank factors by |factor_value * ATE| to find the largest contributor.
  3. Build a natural language explanation string.
  4. Return: status, explanation, recommendation, top_factors list.

counterfactual_analysis(record, changes, causal_ates):
  1. For each changed variable, compute delta = new_value - original_value.
  2. Adjust z-score: new_z = original_z + sum(delta * ATE for each variable).
  3. Apply status thresholds to new_z.
  4. Return: original_z, simulated_z, original_status, simulated_status,
             z_change, conclusion.
```

---

## Storage

```
src/storage/db.py

SQLite file: data/aria.db
Schema:
  CREATE TABLE IF NOT EXISTS qc_results (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp    TEXT,
      instrument_id TEXT,
      test_name    TEXT,
      qc_level     TEXT,
      z_score      REAL,
      status       TEXT
  )

Three functions:
  init_db()        -- creates table if not exists, called at FastAPI startup
  save_result(row) -- inserts one QC evaluation row
  get_recent(limit)-- returns last N rows ordered by timestamp DESC
```

---

## MCP Server

```
src/mcp/server.py

Implements Anthropic's Model Context Protocol.
Exposes three tools to AI assistants:

  get_qc_status()           -- current QC status across all instruments
  get_causal_analysis()     -- ATE values from the causal model
  simulate_counterfactual() -- counterfactual simulation for a given record

Runs as a separate process (make mcp).
Communicates with AI clients via stdio transport.
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
  On server: git pull origin main -> docker-compose up --build -d --remove-orphans.
  Health check: curl http://localhost:8000/docs
```

---

## Dependency Notes

- **torch** is installed before requirements.txt to lock in CPU wheels. pgmpy would otherwise pull CUDA wheels (~2 GB).
- **DoWhy 0.11** requires networkx 3.x and pgmpy 0.1.25. Do not upgrade pgmpy without testing causal engine compatibility.
- **MCP 1.0** follows the Anthropic Model Context Protocol specification. The server uses stdio transport, not HTTP.
