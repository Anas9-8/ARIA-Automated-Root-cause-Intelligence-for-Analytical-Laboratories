# Explainer module: answers the question "what if?"
# Example: "If the temperature had been 21C instead of 25C, would QC have passed?"
# This makes AI decisions understandable to lab managers.

import pandas as pd
import numpy as np
from typing import Dict, List


CAUSE_LABELS = {
    "lab_temp_c": "Lab temperature (°C)",
    "humidity_pct": "Relative humidity (%)",
    "reagent_lot_id": "Reagent lot quality",
    "hours_since_cal": "Hours since last calibration",
}

# Normal operating ranges for clinical labs
CAUSE_NORMAL_RANGES = {
    "lab_temp_c":      (18.0, 23.0),   # °C
    "humidity_pct":    (40.0, 60.0),   # %
    "hours_since_cal": (0.0,  24.0),   # h
}

# Recommendation when the value is ELEVATED / outside normal range
CAUSE_SUGGESTIONS = {
    "lab_temp_c":      "Lab temperature exceeds 23 °C — high heat degrades enzyme activity. Check HVAC and cool the lab.",
    "humidity_pct":    "Humidity is outside 40–60 % range. Store reagents in sealed containers and inspect air conditioning.",
    "reagent_lot_id":  "Switch to a different reagent lot. Check lot-specific QC performance histograms.",
    "hours_since_cal": "Recalibrate the instrument. More than 24 h since last calibration — drift is accumulating.",
}

# Recommendation when value is within normal range (not the actual driver)
CAUSE_SUGGESTIONS_NORMAL = {
    "lab_temp_c":      (
        "Lab temperature is within normal range (< 23 °C) and is NOT the active driver here. "
        "This is the strongest statistical predictor across all data, but the current value is acceptable. "
        "Likely cause: reagent lot variability or borderline random measurement noise. Repeat the QC run."
    ),
    "humidity_pct":    (
        "Humidity is within normal range (40–60 %). This factor is not actively elevated. "
        "Check reagent lot quality or repeat the run."
    ),
    "hours_since_cal": (
        "Calibration is recent (< 24 h). Instrument drift is minimal. "
        "Check reagent lot quality or repeat the run."
    ),
}


def _to_py(v):
    """Convert numpy scalar to native Python type."""
    if isinstance(v, np.floating):
        return float(v)
    if isinstance(v, np.integer):
        return int(v)
    return v


def get_lot_info(lot_name: str) -> dict:
    """
    Classify a reagent lot by its naming suffix.
    Matches the bias coefficients in data/synthetic/generate.py:
      -03 lots → −2% mean bias (strong_negative)
      -02 lots → −0.8% mean bias (known_negative)
      -01 lots → no bias (reference)
    """
    name = str(lot_name).strip()
    if not name or name in ("", "nan"):
        return {
            "label": "Reagent Lot — unknown",
            "bias":  "unknown",
            "suggestion": "Reagent lot information is missing. Verify lot tracking.",
        }
    if name.endswith("-03"):
        return {
            "label": f"Reagent Lot {name} — strong negative bias (−8%)",
            "bias":  "strong_negative",
            "suggestion": (
                f"Lot {name} has documented strong negative bias (−8% from reference). "
                f"Stop using this lot immediately. Switch to a -01 reference lot and repeat QC."
            ),
        }
    if name.endswith("-02"):
        return {
            "label": f"Reagent Lot {name} — known negative bias (−3%)",
            "bias":  "known_negative",
            "suggestion": (
                f"Lot {name} has a documented negative bias (−3% from reference). "
                f"Switch to a lot ending in -01, or run lot-specific verification before reporting patient results."
            ),
        }
    return {
        "label": f"Reagent Lot {name} — reference lot (stable)",
        "bias":  "reference",
        "suggestion": (
            f"Lot {name} is a reference lot with no documented bias. "
            f"This failure is likely random measurement variation. Repeat the QC run."
        ),
    }


def explain_failure(
    record: pd.Series,
    causal_ates: Dict[str, float],
) -> Dict:
    """
    Explain why a QC record failed.
    Priority logic:
      1. If any environmental value is outside normal range → that is the primary cause.
      2. Else if reagent lot has known bias → reagent lot is primary cause.
      3. Else → borderline/random variation, report statistical driver only.
    """
    ranked = sorted(
        causal_ates.items(), key=lambda x: abs(x[1]) if x[1] else 0, reverse=True
    )

    # ── z-score status ──────────────────────────────────────────────────────
    z_score = record.get("z_score", 0)
    abs_z   = abs(float(z_score)) if z_score is not None else 0.0
    if abs_z >= 3.0:
        status = "FAIL"
    elif abs_z >= 2.0:
        status = "WARNING"
    else:
        status = "PASS"

    # ── Reagent lot info from real lot name (not numeric id) ────────────────
    lot_name = str(record.get("reagent_lot", "")).strip()
    lot_info = get_lot_info(lot_name)

    # ── Build top_factors — show real lot name instead of numeric id ────────
    top_factors = []
    for cause, ate in ranked:
        if cause == "reagent_lot_id":
            top_factors.append([lot_info["label"], lot_name])
        else:
            label = CAUSE_LABELS.get(cause, cause)
            value = _to_py(record.get(cause, "N/A"))
            top_factors.append([label, value])

    # ── Check all continuous env variables against normal ranges ────────────
    env_violations = []
    for cause, _ in ranked:
        if cause not in CAUSE_NORMAL_RANGES:
            continue
        try:
            val  = float(record.get(cause, 0))
            lo, hi = CAUSE_NORMAL_RANGES[cause]
            if not (lo <= val <= hi):
                env_violations.append((cause, val))
        except (TypeError, ValueError):
            pass
    all_env_normal = len(env_violations) == 0

    # ── Determine primary cause ─────────────────────────────────────────────
    top_cause, top_ate = ranked[0] if ranked else ("unknown", 0)
    effect_size = float(top_ate) if top_ate else 0.0

    if env_violations:
        # An environmental variable is genuinely out of range — use ATE ranking
        top_cause_label = CAUSE_LABELS.get(top_cause, top_cause)
        top_cause_value = _to_py(record.get(top_cause, "N/A"))
        explanation_text = (
            f"Primary cause: {top_cause_label} = {float(top_cause_value):.2f}. "
            f"ATE = {effect_size:+.4f} per unit on QC z-score."
        )
        recommendation = CAUSE_SUGGESTIONS.get(top_cause, "Investigate manually.")

    elif lot_info["bias"] in ("known_negative", "strong_negative"):
        # All env conditions normal → reagent lot is the operative cause
        top_cause       = "reagent_lot_id"
        top_cause_label = lot_info["label"]
        top_cause_value = lot_name
        temp_s = f"{float(record.get('lab_temp_c', 0)):.1f}°C"
        hum_s  = f"{float(record.get('humidity_pct', 0)):.1f}%"
        cal_s  = f"{float(record.get('hours_since_cal', 0)):.0f}h"
        explanation_text = (
            f"Primary cause: {lot_info['label']}. "
            f"All environmental conditions are within normal range "
            f"(temp {temp_s}, humidity {hum_s}, calibration {cal_s})."
        )
        recommendation = lot_info["suggestion"]

    else:
        # All env normal, lot is stable → borderline random variation
        top_cause_label = CAUSE_LABELS.get(top_cause, top_cause)
        top_cause_value = _to_py(record.get(top_cause, "N/A"))
        explanation_text = (
            f"Statistical driver: {top_cause_label} (ATE = {effect_size:+.4f}/unit). "
            f"Current value {float(top_cause_value):.2f} is within normal operating range. "
            f"This is a borderline failure — likely random measurement variation."
        )
        recommendation = CAUSE_SUGGESTIONS_NORMAL.get(
            top_cause,
            f"{lot_info['suggestion']}. Repeat the QC run to confirm."
        )

    # ── all_causes list (for causal table in dashboard) ─────────────────────
    all_causes = [
        {
            "variable": cause,
            "label":    lot_info["label"] if cause == "reagent_lot_id" else CAUSE_LABELS.get(cause, cause),
            "ate":      round(float(ate), 4) if ate else 0.0,
            "value":    top_factors[i][1],
        }
        for i, (cause, ate) in enumerate(ranked)
    ]

    return {
        "status":          status,
        "top_factors":     top_factors,
        "explanation":     explanation_text,
        "recommendation":  recommendation,
        "top_cause":       top_cause,
        "top_cause_label": top_cause_label,
        "top_cause_value": top_cause_value,
        "effect_size":     round(effect_size, 4),
        "suggestion":      recommendation,
        "all_causes":      all_causes,
        "reagent_lot":     lot_name,
        "reagent_lot_bias": lot_info["bias"],
    }


def counterfactual_analysis(
    record: pd.Series,
    counterfactual_values: Dict[str, float],
    causal_ates: Dict[str, float] = None,
) -> Dict:
    """
    Simulate: if we change these variables, would QC pass?
    Uses actual ATE coefficients from the causal engine (linear approximation).
    delta = new_value - original_value; effect = delta * ATE; simulated_z += effect
    Cooling temp (negative delta) with positive ATE → negative effect → lower Z. ✓
    """
    original_z = record.get("z_score", 0)
    simulated_z = original_z
    changes = []

    ate_map = causal_ates or {
        "lab_temp_c": 0.0122,
        "hours_since_cal": 0.003,
    }

    for variable, new_value in counterfactual_values.items():
        original_value = record.get(variable)
        if original_value is None:
            continue
        ate = ate_map.get(variable, 0)
        delta = float(new_value) - float(original_value)
        effect = delta * float(ate)
        simulated_z = float(simulated_z) + effect
        changes.append(f"{variable}: {float(original_value):.4g} → {float(new_value):.4g}")

    orig_z_f = float(original_z)
    sim_z_f  = float(simulated_z)
    original_pass = abs(orig_z_f) < 2.0
    simulated_pass = abs(sim_z_f) < 2.0

    def get_status(z):
        if abs(z) >= 3.0:
            return "FAIL"
        if abs(z) >= 2.0:
            return "WARNING"
        return "PASS"

    return {
        "original_z": round(orig_z_f, 3),
        "simulated_z": round(sim_z_f, 3),
        "z_change": round(sim_z_f - orig_z_f, 3),
        "original_status": get_status(orig_z_f),
        "simulated_status": get_status(sim_z_f),
        "would_have_passed": bool(simulated_pass and not original_pass),
        "changes_applied": changes,
        "conclusion": (
            "Correcting these conditions would have prevented the failure."
            if (simulated_pass and not original_pass)
            else "The failure would persist even with these corrections."
        ),
    }
