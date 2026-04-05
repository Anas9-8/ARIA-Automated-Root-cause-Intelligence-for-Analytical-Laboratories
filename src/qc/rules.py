# Westgard rules for laboratory QC.
# These rules detect when an instrument is out of control.
# Reference: Westgard JO, Barry PL, Hunt MR. A multi-rule Shewhart chart. 1981.

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List


@dataclass
class QCViolation:
    """
    Represents one QC rule violation.
    A violation means the instrument may not be working correctly.
    """
    rule:       str    # name of the rule that failed (e.g. "1-3s")
    severity:   str    # "warning" or "rejection"
    message:    str    # human-readable explanation
    indices:    list = field(default_factory=list)  # which rows triggered this rule


def check_1_2s(z_scores: pd.Series) -> List[QCViolation]:
    """
    1-2s warning rule: one result is more than 2 SD from the mean.
    This is a warning only. Do not reject the run yet.
    """
    violations = []
    for i, z in enumerate(z_scores):
        if abs(z) > 2.0:
            violations.append(QCViolation(
                rule="1-2s",
                severity="warning",
                message=f"One result exceeded 2 SD (z={z:.2f}). Check instrument.",
                indices=[i]
            ))
    return violations


def check_1_3s(z_scores: pd.Series) -> List[QCViolation]:
    """
    1-3s rejection rule: one result is more than 3 SD from the mean.
    Reject the run. Do not report patient results.
    """
    violations = []
    for i, z in enumerate(z_scores):
        if abs(z) > 3.0:
            violations.append(QCViolation(
                rule="1-3s",
                severity="rejection",
                message=f"REJECT: One result exceeded 3 SD (z={z:.2f}). Run is invalid.",
                indices=[i]
            ))
    return violations


def check_2_2s(z_scores: pd.Series) -> List[QCViolation]:
    """
    2-2s rejection rule: two consecutive results both exceed 2 SD in the same direction.
    This indicates systematic error (bias), not random error.
    """
    violations = []
    for i in range(1, len(z_scores)):
        z_prev = z_scores.iloc[i - 1]
        z_curr = z_scores.iloc[i]
        # Both positive or both negative, and both > 2 SD
        if z_prev > 2.0 and z_curr > 2.0:
            violations.append(QCViolation(
                rule="2-2s",
                severity="rejection",
                message="REJECT: Two consecutive results above +2 SD. Systematic positive bias.",
                indices=[i - 1, i]
            ))
        elif z_prev < -2.0 and z_curr < -2.0:
            violations.append(QCViolation(
                rule="2-2s",
                severity="rejection",
                message="REJECT: Two consecutive results below -2 SD. Systematic negative bias.",
                indices=[i - 1, i]
            ))
    return violations


def check_R_4s(z_scores: pd.Series) -> List[QCViolation]:
    """
    R-4s rejection rule: range between two consecutive results exceeds 4 SD.
    This indicates random error. One result is high, the next is low (or opposite).
    """
    violations = []
    for i in range(1, len(z_scores)):
        z_range = abs(z_scores.iloc[i] - z_scores.iloc[i - 1])
        if z_range > 4.0:
            violations.append(QCViolation(
                rule="R-4s",
                severity="rejection",
                message=f"REJECT: Range between two results is {z_range:.2f} SD. High random error.",
                indices=[i - 1, i]
            ))
    return violations


def check_4_1s(z_scores: pd.Series) -> List[QCViolation]:
    """
    4-1s rejection rule: four consecutive results all exceed 1 SD in the same direction.
    This indicates a trend or drift in the instrument.
    """
    violations = []
    for i in range(3, len(z_scores)):
        window = z_scores.iloc[i - 3: i + 1]
        if all(z > 1.0 for z in window):
            violations.append(QCViolation(
                rule="4-1s",
                severity="rejection",
                message="REJECT: Four consecutive results above +1 SD. Instrument is drifting up.",
                indices=list(range(i - 3, i + 1))
            ))
        elif all(z < -1.0 for z in window):
            violations.append(QCViolation(
                rule="4-1s",
                severity="rejection",
                message="REJECT: Four consecutive results below -1 SD. Instrument is drifting down.",
                indices=list(range(i - 3, i + 1))
            ))
    return violations


def check_10x(z_scores: pd.Series) -> List[QCViolation]:
    """
    10x rejection rule: ten consecutive results are all on the same side of the mean.
    This is a very strong sign of systematic bias.
    """
    violations = []
    for i in range(9, len(z_scores)):
        window = z_scores.iloc[i - 9: i + 1]
        if all(z > 0 for z in window):
            violations.append(QCViolation(
                rule="10x",
                severity="rejection",
                message="REJECT: Ten consecutive results above mean. Strong systematic positive bias.",
                indices=list(range(i - 9, i + 1))
            ))
        elif all(z < 0 for z in window):
            violations.append(QCViolation(
                rule="10x",
                severity="rejection",
                message="REJECT: Ten consecutive results below mean. Strong systematic negative bias.",
                indices=list(range(i - 9, i + 1))
            ))
    return violations


def run_all_westgard_rules(z_scores: pd.Series) -> List[QCViolation]:
    """
    Run all six Westgard rules on a series of z-scores.
    Returns a list of all violations found.
    Call this once per test per instrument per QC level per day.
    """
    all_violations = []
    all_violations.extend(check_1_2s(z_scores))
    all_violations.extend(check_1_3s(z_scores))
    all_violations.extend(check_2_2s(z_scores))
    all_violations.extend(check_R_4s(z_scores))
    all_violations.extend(check_4_1s(z_scores))
    all_violations.extend(check_10x(z_scores))
    return all_violations


def evaluate_qc_dataframe(df: pd.DataFrame, window_days: int = 30) -> pd.DataFrame:
    """
    Run Westgard rules on all instrument/test/level combinations.
    Groups data by instrument, test, and QC level, then applies rules.
    Returns a summary DataFrame with pass/fail status and violation details.

    Westgard rules use different time windows in clinical practice:
    - Single-measurement rules (1-2s, 1-3s): only the most recent 3 runs (today)
    - Consecutive-result rules (2-2s, R-4s): last 6 runs (two days)
    - Trend rules (4-1s): last 12 runs (four days)
    - Long-trend rule (10x): last 30 runs (ten days)
    This avoids accumulating old violations into the current status.
    """
    results = []

    # Only look at the last 30 days, not all history.
    # Westgard rules are meant for recent data, not 6 months of accumulated runs.
    if "timestamp" in df.columns:
        cutoff = df["timestamp"].max() - pd.Timedelta(days=window_days)
        df = df[df["timestamp"] >= cutoff]

    groups = df.groupby(["instrument_id", "test_name", "qc_level"])

    for (instrument, test, level), group in groups:
        group = group.sort_values("timestamp")
        z_all = group["z_score"].reset_index(drop=True)

        # Short window: today's runs (last 3 measurements).
        # Used for single-measurement and two-point rules.
        z_short  = z_all.tail(3)
        z_medium = z_all.tail(6)
        z_trend  = z_all.tail(12)
        z_long   = z_all.tail(30)

        violations = []
        violations.extend(check_1_2s(z_short))
        violations.extend(check_1_3s(z_short))
        violations.extend(check_2_2s(z_medium))
        violations.extend(check_R_4s(z_medium))
        violations.extend(check_4_1s(z_trend))
        violations.extend(check_10x(z_long))

        rejections = [v for v in violations if v.severity == "rejection"]
        warnings    = [v for v in violations if v.severity == "warning"]

        results.append({
            "instrument_id":     instrument,
            "test_name":         test,
            "qc_level":          level,
            "status":            "FAIL" if rejections else ("WARNING" if warnings else "PASS"),
            "n_rejections":      len(rejections),
            "n_warnings":        len(warnings),
            "rejection_rules":   list({v.rule for v in rejections}),
            "latest_z":          round(z_all.iloc[-1], 3) if len(z_all) > 0 else None,
            "mean_z_last_10":    round(z_all.tail(10).mean(), 3) if len(z_all) >= 10 else None,
            "last_timestamp":    group["timestamp"].max().isoformat(),
        })

    return pd.DataFrame(results)
