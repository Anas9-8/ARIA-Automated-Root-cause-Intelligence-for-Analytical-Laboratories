# Tests for the Westgard QC rules engine.
# Run with: pytest tests/test_qc.py -v

import pytest
import pandas as pd
from src.qc.rules import check_1_3s, check_2_2s, check_R_4s, run_all_westgard_rules


def test_1_3s_detects_outlier():
    """A z-score above 3.0 must trigger a rejection."""
    z = pd.Series([0.1, -0.2, 0.3, 3.5, 0.1])
    violations = check_1_3s(z)
    assert len(violations) > 0
    assert violations[0].severity == "rejection"


def test_1_3s_clean_data():
    """Clean data (all z within 2 SD) must have no rejection."""
    z = pd.Series([0.1, -0.5, 0.3, 1.2, -0.8])
    violations = check_1_3s(z)
    assert len(violations) == 0


def test_2_2s_consecutive_positive():
    """Two consecutive z-scores above 2 SD must trigger rejection."""
    z = pd.Series([0.1, 2.5, 2.8, 0.2])
    violations = check_2_2s(z)
    assert any(v.rule == "2-2s" for v in violations)


def test_R_4s_large_range():
    """A range of more than 4 SD between two points must trigger rejection."""
    z = pd.Series([0.0, 3.0, -1.5])  # range = 3.0 - (-1.5) = 4.5
    violations = check_R_4s(z)
    assert any(v.rule == "R-4s" for v in violations)


def test_all_rules_run_without_error():
    """Running all rules on a short series must not raise any exception."""
    z = pd.Series([0.1, 2.3, -0.2, 1.5, -2.1, 0.8, 1.2, -0.5, 0.3, 2.7])
    violations = run_all_westgard_rules(z)
    assert isinstance(violations, list)
