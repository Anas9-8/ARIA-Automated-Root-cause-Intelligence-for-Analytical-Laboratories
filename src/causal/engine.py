# Causal AI engine for ARIA.
# This module learns WHY QC failures happen, not just that they happen.
# It uses DoWhy to build a causal model from historical data.
#
# Outcome is the continuous z_score (in σ units), not a binary fail flag.
# That keeps ATEs in the same units the explainer and counterfactual use,
# so a 1°C ATE of +0.012 means "+0.012 σ of z-score per °C above ambient".

import pandas as pd
import numpy as np
import networkx as nx
from dowhy import CausalModel
import warnings
warnings.filterwarnings("ignore")


# The causal graph as a DOT string - kept for reference and documentation.
# Each arrow means "this variable causes that variable."
#
# lab_temp_c     -> z_score   (high temp degrades enzymes → biased measurement)
# humidity_pct   -> z_score   (humidity affects reagent concentration)
# reagent_lot_id -> z_score   (some lots run lower than reference)
# hours_since_cal -> z_score  (instruments drift after calibration)

CAUSAL_GRAPH_DOT = """
digraph {
    lab_temp_c       -> z_score;
    humidity_pct     -> z_score;
    reagent_lot_id   -> z_score;
    hours_since_cal  -> z_score;
}
"""


def _build_nx_graph() -> nx.DiGraph:
    """
    Build the causal graph as a NetworkX DiGraph.
    DoWhy works best with a networkx graph object.
    Edges encode domain knowledge of clinical-lab QC drift.
    """
    G = nx.DiGraph()
    edges = [
        ("lab_temp_c",      "z_score"),
        ("humidity_pct",    "z_score"),
        ("reagent_lot_id",  "z_score"),
        ("hours_since_cal", "z_score"),
    ]
    G.add_edges_from(edges)
    return G


def prepare_causal_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert raw QC data into a format ready for causal analysis.
    Encodes reagent_lot as numeric id; outcome is the raw z_score in σ units.
    """
    causal_df = df.copy()

    # Numeric reagent lot id (DoWhy needs numeric treatments).
    lot_map = {lot: i for i, lot in enumerate(causal_df["reagent_lot"].unique())}
    causal_df["reagent_lot_id"] = causal_df["reagent_lot"].map(lot_map)

    keep = [
        "lab_temp_c", "humidity_pct", "reagent_lot_id",
        "hours_since_cal", "z_score",
    ]
    return causal_df[keep].dropna()


def get_ate(causal_data: pd.DataFrame, treatment: str, outcome: str = "z_score") -> float:
    """
    Average Treatment Effect of `treatment` on the QC `outcome` (z-score, σ units).
    Positive ATE → that variable pushes the z-score up (toward +failure).
    Negative ATE → pushes the z-score down (toward −failure).
    """
    G = _build_nx_graph()
    model = CausalModel(
        data=causal_data,
        treatment=treatment,
        outcome=outcome,
        graph=G,
    )
    identified = model.identify_effect(proceed_when_unidentifiable=True)
    estimate   = model.estimate_effect(
        identified,
        method_name="backdoor.linear_regression",
    )
    return round(float(estimate.value), 6)


def run_causal_analysis(df: pd.DataFrame) -> dict:
    """
    Run full causal analysis on the QC dataset.
    Returns one ATE (z-score per unit) for each upstream variable.
    """
    causal_data = prepare_causal_data(df)

    causes = ["lab_temp_c", "humidity_pct", "reagent_lot_id", "hours_since_cal"]
    results: dict = {}
    for cause in causes:
        try:
            results[cause] = get_ate(causal_data, treatment=cause)
        except Exception:
            results[cause] = None

    sorted_results = dict(
        sorted(results.items(), key=lambda kv: abs(kv[1]) if kv[1] else 0, reverse=True)
    )
    top = max(sorted_results, key=lambda k: abs(sorted_results[k]) if sorted_results[k] else 0)

    failure_rate = float((df["z_score"].abs() > 2.0).mean())

    return {
        "ates":          sorted_results,
        "top_cause":     top,
        "outcome":       "z_score",
        "outcome_unit":  "σ (z-score)",
        "causal_graph":  CAUSAL_GRAPH_DOT,
        "n_records":     len(causal_data),
        "failure_rate":  round(failure_rate, 4),
    }


def get_causal_graph_for_plot() -> nx.DiGraph:
    """
    Return the causal graph as a NetworkX object for visualization.
    Used by the dashboard to draw the causal diagram.
    """
    return _build_nx_graph()
