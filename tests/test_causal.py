# Tests for the causal analysis engine.

import pytest
import pandas as pd
from src.ingestion.loader import load_qc_data
from src.causal.engine import prepare_causal_data, get_causal_graph_for_plot


def test_prepare_causal_data():
    """Causal data preparation must add qc_fail column."""
    df = load_qc_data()
    causal_df = prepare_causal_data(df.head(100))
    assert "qc_fail" in causal_df.columns
    assert causal_df["qc_fail"].isin([0, 1]).all()


def test_causal_graph_has_nodes():
    """The causal graph must contain nodes and edges."""
    G = get_causal_graph_for_plot()
    assert len(G.nodes()) > 0
    assert len(G.edges()) > 0


def test_causal_graph_has_qc_fail_node():
    """qc_fail must be in the causal graph as the outcome node."""
    G = get_causal_graph_for_plot()
    assert "qc_fail" in G.nodes()
