# This module loads QC data from CSV files (instrument exports or LIMS).
# It cleans the data and prepares it for QC rules and causal analysis.

import pandas as pd
import numpy as np
import os


def load_qc_data(path="data/synthetic/qc_data.csv") -> pd.DataFrame:
    """
    Load QC data from a CSV file.
    The CSV must have columns: timestamp, instrument_id, test_name,
    qc_level, reagent_lot, z_score, lab_temp_c, hours_since_cal.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Data file not found: {path}")

    df = pd.read_csv(path, parse_dates=["timestamp"])

    # Remove rows with missing critical values
    required = ["z_score", "test_name", "qc_level", "instrument_id", "reagent_lot"]
    df = df.dropna(subset=required)

    # Add a date column for grouping by day
    df["date"] = df["timestamp"].dt.date

    # Sort by time
    df = df.sort_values("timestamp").reset_index(drop=True)

    return df


def load_mimic_demo(path="data/raw/mimic_demo/labevents.csv") -> pd.DataFrame:
    """
    Load real hospital lab data from MIMIC-IV demo.
    We use this to show that ARIA works on real data, not just synthetic data.
    """
    if not os.path.exists(path):
        print("MIMIC demo file not found. Run data/synthetic/generate.py first.")
        return pd.DataFrame()

    df = pd.read_csv(path, parse_dates=["charttime"])

    # Keep only rows with a numeric result
    df = df.dropna(subset=["valuenum"])
    df = df[df["valuenum"] > 0]

    # Add instrument placeholder (MIMIC does not have instrument IDs)
    df["instrument_id"] = "HOSPITAL-LAB-01"

    return df


def get_summary(df: pd.DataFrame) -> dict:
    """
    Get basic statistics about the loaded dataset.
    Useful for the dashboard overview page.
    """
    return {
        "total_records":  len(df),
        "date_range":     f"{df['timestamp'].min().date()} to {df['timestamp'].max().date()}" if "timestamp" in df.columns else "N/A",
        "instruments":    df["instrument_id"].nunique() if "instrument_id" in df.columns else 0,
        "tests":          df["test_name"].nunique() if "test_name" in df.columns else 0,
        "reagent_lots":   df["reagent_lot"].nunique() if "reagent_lot" in df.columns else 0,
    }
