# REST API for ARIA.
# Other systems (LIMS, dashboards, other tools) can talk to ARIA through this API.
# This file also serves the HTML dashboard using Jinja2 templates.

import io
import logging
import os
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from src.causal.engine import run_causal_analysis
from src.explainer.explainer import counterfactual_analysis, explain_failure
from src.ingestion.loader import get_summary, load_qc_data
from src.qc.rules import evaluate_qc_dataframe
from src.storage.db import get_recent, init_db, save_result

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aria.api")

app = FastAPI(
    title="ARIA API",
    description="Automated Root-cause Intelligence for Analytical Laboratories",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_static_path = os.path.join(os.path.dirname(__file__), "..", "..", "dashboard", "static")
app.mount("/static", StaticFiles(directory=_static_path), name="static")

_templates_path = os.path.join(os.path.dirname(__file__), "..", "..", "dashboard", "templates")
templates = Jinja2Templates(directory=_templates_path)

init_db()

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


# ── HTML pages ──────────────────────────────────────────────────────────────

@app.get("/")
def page_overview(request: Request):
    return templates.TemplateResponse("overview.html", {"request": request, "page": "overview"})


@app.get("/causal")
def page_causal(request: Request):
    return templates.TemplateResponse("causal.html", {"request": request, "page": "causal"})


@app.get("/explainer")
def page_explainer(request: Request):
    return templates.TemplateResponse("explainer.html", {"request": request, "page": "explainer"})


@app.get("/alerts")
def page_alerts(request: Request):
    return templates.TemplateResponse("alerts.html", {"request": request, "page": "alerts"})


@app.get("/architecture")
def page_architecture(request: Request):
    return templates.TemplateResponse("architecture.html", {"request": request, "page": "architecture"})


@app.get("/mcp")
def page_mcp(request: Request):
    return templates.TemplateResponse("mcp.html", {"request": request, "page": "mcp"})


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Data endpoints ──────────────────────────────────────────────────────────

@app.get("/summary")
def summary():
    return get_summary(get_data())


@app.get("/api/failures")
def api_failures_list(
    limit:    int   = 200,
    severity: str   = "all",   # "warn" → |z|>2, "fail" → |z|>3, "all" → both
):
    """
    List of out-of-control QC observations for the explainer slider.

    Westgard 1-2s (|z|>2) is a *warning*; 1-3s (|z|>3) is a *rejection*.
    `severity=all` returns both — the explainer treats every entry as
    "investigate"-worthy. `severity=fail` restricts to rejections only.
    """
    df = get_data()
    z_abs = df["z_score"].abs()
    if severity == "fail":
        mask = z_abs > 3.0
    elif severity == "warn":
        mask = (z_abs > 2.0) & (z_abs <= 3.0)
    else:
        mask = z_abs > 2.0

    rows = df[mask].copy()
    total = int(len(rows))
    rows["original_index"] = rows.index
    rows["severity"] = z_abs[mask].apply(lambda v: "fail" if v > 3.0 else "warn")
    rows = rows.head(limit)

    cols = [
        "original_index", "severity", "test_name", "qc_level", "instrument_id",
        "reagent_lot", "z_score", "lab_temp_c", "hours_since_cal", "humidity_pct",
        "measured_value", "unit",
    ]
    payload = rows[cols].copy()
    # Keep numeric rounding only for actual numeric columns.
    num_cols = payload.select_dtypes(include="number").columns
    payload[num_cols] = payload[num_cols].round(4)

    return {
        "total":   total,
        "limit":   limit,
        "shown":   int(len(payload)),
        "records": payload.to_dict(orient="records"),
    }


@app.get("/qc/status")
def qc_status(instrument: Optional[str] = None, test: Optional[str] = None):
    df = get_data()
    if instrument:
        df = df[df["instrument_id"] == instrument]
    if test:
        df = df[df["test_name"] == test]
    result = evaluate_qc_dataframe(df)

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


@app.get("/qc/failures")
def qc_failures():
    df = get_data()
    result = evaluate_qc_dataframe(df)
    failures = result[result["status"] == "FAIL"]
    return failures.to_dict(orient="records")


@app.get("/db/recent")
def db_recent(limit: int = 100):
    return get_recent(limit=limit)


# ── Trend (z-score time series) ─────────────────────────────────────────────

@app.get("/api/trend/options")
def trend_options():
    """Available instruments + tests for the trend chart dropdowns."""
    df = get_data()
    return {
        "instruments": sorted(df["instrument_id"].dropna().unique().tolist()),
        "tests":       sorted(df["test_name"].dropna().unique().tolist()),
        "qc_levels":   sorted(df["qc_level"].dropna().unique().tolist()),
    }


@app.get("/api/trend")
def api_trend(
    instrument: Optional[str] = None,
    test:       Optional[str] = None,
    qc_level:   Optional[str] = None,
    days:       int = 180,
    limit:      int = 1500,
):
    """Time-series of z-scores for the trend chart on the Overview page.
    Returns one record per QC observation: timestamp, z_score, status, instrument, test, qc_level."""
    df = get_data()
    if instrument:
        df = df[df["instrument_id"] == instrument]
    if test:
        df = df[df["test_name"] == test]
    if qc_level:
        df = df[df["qc_level"] == qc_level]

    if "timestamp" in df.columns and len(df):
        cutoff = df["timestamp"].max() - pd.Timedelta(days=days)
        df = df[df["timestamp"] >= cutoff]

    df = df.sort_values("timestamp")
    if len(df) > limit:
        # downsample evenly to keep payload small but visually faithful
        step = max(1, len(df) // limit)
        df = df.iloc[::step]

    def status_of(z: float) -> str:
        a = abs(z)
        if a >= 3.0:
            return "FAIL"
        if a >= 2.0:
            return "WARNING"
        return "PASS"

    rows = []
    for _, r in df.iterrows():
        z = float(r["z_score"])
        rows.append({
            "timestamp":     r["timestamp"].isoformat() if hasattr(r["timestamp"], "isoformat") else str(r["timestamp"]),
            "z_score":       round(z, 4),
            "status":        status_of(z),
            "instrument_id": r.get("instrument_id"),
            "test_name":     r.get("test_name"),
            "qc_level":      r.get("qc_level"),
        })
    return {"count": len(rows), "points": rows}


# ── CSV export ──────────────────────────────────────────────────────────────

def _stream_csv(df: pd.DataFrame, filename: str) -> StreamingResponse:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/export.csv")
def api_export_csv(
    view:       str = "qc",
    instrument: Optional[str] = None,
    test:       Optional[str] = None,
    qc_level:   Optional[str] = None,
):
    """Download the current dashboard view as CSV.
    view = 'qc' | 'failures' | 'trend' | 'raw'."""
    df = get_data()
    if instrument:
        df = df[df["instrument_id"] == instrument]
    if test:
        df = df[df["test_name"] == test]
    if qc_level:
        df = df[df["qc_level"] == qc_level]

    if view == "qc":
        out = evaluate_qc_dataframe(df)
        return _stream_csv(out, "aria_qc_status.csv")
    if view == "failures":
        out = evaluate_qc_dataframe(df)
        out = out[out["status"] == "FAIL"]
        return _stream_csv(out, "aria_qc_failures.csv")
    if view == "trend":
        cols = [c for c in [
            "timestamp", "instrument_id", "test_name", "qc_level",
            "reagent_lot", "z_score", "lab_temp_c", "hours_since_cal",
            "humidity_pct", "measured_value", "unit",
        ] if c in df.columns]
        return _stream_csv(df[cols].sort_values("timestamp"), "aria_qc_trend.csv")
    if view == "raw":
        return _stream_csv(df, "aria_qc_raw.csv")
    raise HTTPException(status_code=400, detail=f"Unknown view '{view}'. Use qc|failures|trend|raw.")


# ── Causal endpoints ────────────────────────────────────────────────────────

@app.get("/causal/analysis")
def causal_analysis():
    return get_causal()


@app.get("/causal/explain/{row_index}")
def explain(row_index: int):
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
    row_index:       int   = Field(ge=0, description="Row index in the loaded QC dataset")
    lab_temp_c:      Optional[float] = Field(default=None, ge=10, le=40, description="Counterfactual lab temperature (°C)")
    hours_since_cal: Optional[float] = Field(default=None, ge=0, le=72, description="Counterfactual hours since calibration")


@app.post("/causal/counterfactual")
def counterfactual(req: CounterfactualRequest):
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
    """Curl-friendly counterfactual GET endpoint."""
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
