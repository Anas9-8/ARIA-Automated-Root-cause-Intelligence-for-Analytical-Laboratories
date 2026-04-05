# Causal AI engine for ARIA.
# This module learns WHY QC failures happen, not just that they happen.
# It uses DoWhy to build a causal model from historical data.

import pandas as pd
import numpy as np
import networkx as nx
from dowhy import CausalModel
import warnings
warnings.filterwarnings("ignore")


# The causal graph as a DOT string - kept for reference and documentation.
# Each arrow means "this variable causes that variable."
#
# Temperature  -> reagent_activity  (high temp degrades enzymes)
# humidity_pct -> reagent_activity  (high humidity changes reagent concentration)
# reagent_lot  -> reagent_activity  (some lots are less stable)
# hours_since_cal -> drift          (instruments drift after calibration)
# reagent_activity -> qc_fail       (poor reagents cause failures)
# drift           -> qc_fail        (drift causes failures)

CAUSAL_GRAPH_DOT = """
digraph {
    lab_temp_c     -> reagent_activity;
    humidity_pct   -> reagent_activity;
    reagent_lot_id -> reagent_activity;
    hours_since_cal -> drift;
    reagent_activity -> qc_fail;
    drift           -> qc_fail;
}
"""


def _build_nx_graph() -> nx.DiGraph:
    """
    Build the causal graph as a NetworkX DiGraph.
    DoWhy works best with a networkx graph object.
    """
    G = nx.DiGraph()
    edges = [
        ("lab_temp_c",       "reagent_activity"),
        ("humidity_pct",     "reagent_activity"),
        ("reagent_lot_id",   "reagent_activity"),
        ("hours_since_cal",  "drift"),
        ("reagent_activity", "qc_fail"),
        ("drift",            "qc_fail"),
    ]
    G.add_edges_from(edges)
    return G


def prepare_causal_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert raw QC data into a format ready for causal analysis.
    Creates binary columns for qc_fail and numeric lot ID.
    """
    causal_df = df.copy()

    # Target variable: did QC fail? (z-score outside 2 SD = failure)
    causal_df["qc_fail"] = (causal_df["z_score"].abs() > 2.0).astype(int)

    # Convert reagent lot to a numeric ID for the model
    lot_map = {lot: i for i, lot in enumerate(causal_df["reagent_lot"].unique())}
    causal_df["reagent_lot_id"] = causal_df["reagent_lot"].map(lot_map)

    max_lot = causal_df["reagent_lot_id"].max()
    if max_lot == 0:
        max_lot = 1

    # Create a proxy variable for reagent activity based on lot and temperature
    # This represents the combined effect of lot quality and environmental stress
    causal_df["reagent_activity"] = (
        1.0
        - 0.05 * (causal_df["lab_temp_c"] - 21.0).clip(lower=0)
        - 0.03 * causal_df["reagent_lot_id"] / max_lot
        + np.random.normal(0, 0.02, len(causal_df))
    )

    # Create instrument drift proxy
    causal_df["drift"] = (
        (causal_df["hours_since_cal"] / 48.0).clip(upper=1.0)
        + np.random.normal(0, 0.05, len(causal_df))
    ).clip(lower=0)

    # Keep only the columns needed for causal analysis
    keep = [
        "lab_temp_c", "humidity_pct", "reagent_lot_id",
        "hours_since_cal", "reagent_activity", "drift", "qc_fail"
    ]
    return causal_df[keep].dropna()


def get_ate(causal_data: pd.DataFrame, treatment: str, outcome: str = "qc_fail") -> float:
    """
    Calculate the Average Treatment Effect (ATE) of one variable on QC failure.
    ATE tells us: if we change this variable by 1 unit, how much does QC failure change?
    A positive ATE means the variable increases failure risk.
    A negative ATE means the variable reduces failure risk.
    """
    G = _build_nx_graph()
    model = CausalModel(
        data=causal_data,
        treatment=treatment,
        outcome=outcome,
        graph=G
    )
    identified = model.identify_effect(proceed_when_unidentifiable=True)
    estimate   = model.estimate_effect(
        identified,
        method_name="backdoor.linear_regression"
    )
    return round(float(estimate.value), 6)


def run_causal_analysis(df: pd.DataFrame) -> dict:
    """
    Run full causal analysis on the QC dataset.
    Returns ATE for each cause variable.
    This tells us which variable has the biggest effect on QC failures.
    """
    causal_data = prepare_causal_data(df)

    causes = ["lab_temp_c", "humidity_pct", "reagent_lot_id", "hours_since_cal"]
    results = {}

    for cause in causes:
        try:
            ate = get_ate(causal_data, treatment=cause)
            results[cause] = ate
        except Exception as e:
            results[cause] = None

    # Sort by absolute effect size (largest effect first)
    sorted_results = dict(
        sorted(results.items(), key=lambda x: abs(x[1]) if x[1] else 0, reverse=True)
    )

    # Pick the top cause that has a real value
    top = max(
        sorted_results,
        key=lambda x: abs(sorted_results[x]) if sorted_results[x] else 0
    )

    return {
        "ates":          sorted_results,
        "top_cause":     top,
        "causal_graph":  CAUSAL_GRAPH_DOT,
        "n_records":     len(causal_data),
        "failure_rate":  round(causal_data["qc_fail"].mean(), 4),
    }


def get_causal_graph_for_plot() -> nx.DiGraph:
    """
    Return the causal graph as a NetworkX object for visualization.
    Used by the dashboard to draw the causal diagram.
    """
    return _build_nx_graph()
