# Tests for the causal analysis engine.

import pytest
import pandas as pd
from src.ingestion.loader import load_qc_data
from src.causal.engine import prepare_causal_data, get_causal_graph_for_plot


def test_prepare_causal_data():
    """Causal data preparation must keep z_score (continuous outcome) and a numeric lot id."""
    df = load_qc_data()
    causal_df = prepare_causal_data(df.head(100))
    assert "z_score" in causal_df.columns
    assert "reagent_lot_id" in causal_df.columns
    assert pd.api.types.is_numeric_dtype(causal_df["reagent_lot_id"])


def test_causal_graph_has_nodes():
    """The causal graph must contain nodes and edges."""
    G = get_causal_graph_for_plot()
    assert len(G.nodes()) > 0
    assert len(G.edges()) > 0


def test_causal_graph_has_outcome_node():
    """z_score is the outcome node — every edge must terminate there."""
    G = get_causal_graph_for_plot()
    assert "z_score" in G.nodes()
    for _, target in G.edges():
        assert target == "z_score"
