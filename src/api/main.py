# REST API for ARIA.
# Other systems (LIMS, dashboards, other tools) can talk to ARIA through this API.
# This file also serves the HTML dashboard using Jinja2 templates.

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
import pandas as pd
import os

from src.ingestion.loader import load_qc_data, get_summary
from src.qc.rules import evaluate_qc_dataframe
from src.causal.engine import run_causal_analysis
from src.explainer.explainer import explain_failure, counterfactual_analysis
from src.storage.db import init_db, save_result, get_recent

app = FastAPI(
    title="ARIA API",
    description="Automated Root-cause Intelligence for Analytical Laboratories",
    version="1.0.0",
)

# Allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (CSS, JS) from dashboard/static
_static_path = os.path.join(os.path.dirname(__file__), "..", "..", "dashboard", "static")
app.mount("/static", StaticFiles(directory=_static_path), name="static")

# Load HTML templates from dashboard/templates
_templates_path = os.path.join(os.path.dirname(__file__), "..", "..", "dashboard", "templates")
templates = Jinja2Templates(directory=_templates_path)

# Set up the database when the app starts
init_db()

# Load data once at startup
_df: Optional[pd.DataFrame] = None
_causal_result: Optional[dict] = None


def get_data() -> pd.DataFrame:
    global _df
    if _df is None:
        _df = load_qc_data()
    return _df


def get_causal() -> dict:
    global _causal_result
    if _causal_result is None:
        df = get_data()
        _causal_result = run_causal_analysis(df.head(1000))
    return _causal_result


# --- Each route below serves one HTML page of the dashboard ---

@app.get("/")
def page_overview(request: Request):
    """Serve the QC Overview page."""
    return templates.TemplateResponse("overview.html", {"request": request, "page": "overview"})


@app.get("/causal")
def page_causal(request: Request):
    """Serve the Causal Analysis page."""
    return templates.TemplateResponse("causal.html", {"request": request, "page": "causal"})


@app.get("/explainer")
def page_explainer(request: Request):
    """Serve the Root Cause Explainer page."""
    return templates.TemplateResponse("explainer.html", {"request": request, "page": "explainer"})


@app.get("/alerts")
def page_alerts(request: Request):
    """Serve the Active Alerts page."""
    return templates.TemplateResponse("alerts.html", {"request": request, "page": "alerts"})


@app.get("/architecture")
def page_architecture(request: Request):
    """Serve the System Architecture page."""
    return templates.TemplateResponse("architecture.html", {"request": request, "page": "architecture"})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/failures")
def api_failures_list(limit: int = 51):
    """Return the first N failed QC records with their original row indices.
    Used by the Explainer page so JavaScript can populate the slider."""
    df = get_data()
    # Find rows where the z-score shows a failure
    mask = df["z_score"].abs() > 2.0
    failures = df[mask].copy()
    failures["original_index"] = failures.index
    failures = failures.head(limit)
    cols = ["original_index", "test_name", "qc_level", "instrument_id",
            "reagent_lot", "z_score", "lab_temp_c", "hours_since_cal", "humidity_pct",
            "measured_value", "unit"]
    return failures[cols].round(4).to_dict(orient="records")


@app.get("/summary")
def summary():
    """Return dataset summary statistics."""
    df = get_data()
    return get_summary(df)


@app.get("/qc/status")
def qc_status(instrument: Optional[str] = None, test: Optional[str] = None):
    """Return current QC status for all or filtered instrument/test combinations."""
    df = get_data()
    if instrument:
        df = df[df["instrument_id"] == instrument]
    if test:
        df = df[df["test_name"] == test]
    result = evaluate_qc_dataframe(df)

    # Save each result row to the database for history tracking
    for _, row in result.iterrows():
        save_result({
            "instrument_id": row["instrument_id"],
            "test_name":     row["test_name"],
            "qc_level":      row["qc_level"],
            "z_score":       row["latest_z"] if row["latest_z"] is not None else 0.0,
            "status":        row["status"],
            "timestamp":     row["last_timestamp"],
        })

    return result.to_dict(orient="records")


@app.get("/db/recent")
def db_recent(limit: int = 100):
    """Return the last N QC results stored in the database."""
    return get_recent(limit=limit)


@app.get("/qc/failures")
def qc_failures():
    """Return all current QC failures (FAIL status only)."""
    df = get_data()
    result = evaluate_qc_dataframe(df)
    failures = result[result["status"] == "FAIL"]
    return failures.to_dict(orient="records")


@app.get("/causal/analysis")
def causal_analysis():
    """Return causal analysis: which variable most affects QC failure."""
    return get_causal()


@app.get("/causal/explain/{row_index}")
def explain(row_index: int):
    """Explain why a specific QC record failed."""
    df = get_data()
    if row_index >= len(df):
        raise HTTPException(status_code=404, detail="Row not found")
    record = df.iloc[row_index]
    causal = get_causal()
    result = explain_failure(record, causal["ates"])
    result["unit"] = str(record.get("unit", ""))
    result["measured_value"] = float(record.get("measured_value", 0))
    return result


class CounterfactualRequest(BaseModel):
    row_index:    int
    lab_temp_c:   Optional[float] = None
    hours_since_cal: Optional[float] = None


@app.post("/causal/counterfactual")
def counterfactual(req: CounterfactualRequest):
    """Simulate: if we had changed these conditions, would QC have passed?"""
    df = get_data()
    if req.row_index >= len(df):
        raise HTTPException(status_code=404, detail="Row not found")
    record = df.iloc[req.row_index]
    changes = {}
    if req.lab_temp_c is not None:
        changes["lab_temp_c"] = req.lab_temp_c
    if req.hours_since_cal is not None:
        changes["hours_since_cal"] = req.hours_since_cal
    causal = get_causal()
    return counterfactual_analysis(record, changes, causal_ates=causal["ates"])


@app.get("/causal/simulate/{row_index}")
def simulate(row_index: int, new_temp: Optional[float] = None, new_hours: Optional[float] = None):
    """GET endpoint for counterfactual simulation (curl-friendly).
    Example: /causal/simulate/1?new_temp=19&new_hours=1
    """
    df = get_data()
    if row_index >= len(df):
        raise HTTPException(status_code=404, detail="Row not found")
    record = df.iloc[row_index]
    changes = {}
    if new_temp is not None:
        changes["lab_temp_c"] = new_temp
    if new_hours is not None:
        changes["hours_since_cal"] = new_hours
    causal = get_causal()
    return counterfactual_analysis(record, changes, causal_ates=causal["ates"])
