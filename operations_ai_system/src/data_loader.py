"""Data loading and normalization for Rappi operational metrics."""

import re
from pathlib import Path

import pandas as pd

DATA_PATH = Path(__file__).parent.parent / "data" / "rappi_data.xlsx"


def _get_metric_column(df: pd.DataFrame) -> str:
    """Find the metric column name in a DataFrame (case-insensitive)."""
    metric_col = next((c for c in df.columns if str(c).upper() == "METRIC"), None)
    if not metric_col:
        # Fallback to the first column with "metric" in the name if "METRIC" not found exactly
        metric_col = next((c for c in df.columns if "METRIC" in str(c).upper()), "METRIC")
    return metric_col


def _get_week_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Identify and sort week columns (L#W or L#W_ROLL) from a DataFrame.

    Returns:
        (raw_cols, clean_labels) — sorted from oldest (e.g., L8W) to newest (L0W).
    """
    pattern = re.compile(r"^L(\d+)W(_ROLL)?$")
    week_cols = []
    
    for col in df.columns:
        match = pattern.match(str(col))
        if match:
            week_num = int(match.group(1))
            week_cols.append((week_num, col))
            
    # Sort by week number descending (L8W, L7W... L0W)
    week_cols.sort(key=lambda x: x[0], reverse=True)
    
    raw_cols = [c[1] for c in week_cols]
    clean_labels = [str(c[1]).replace("_ROLL", "") for c in week_cols]
    
    return raw_cols, clean_labels


def load_metrics(path: Path = DATA_PATH) -> tuple[pd.DataFrame, list[str]]:
    """Load RAW_INPUT_METRICS sheet and normalize week columns.

    Returns:
        (df_metrics, week_labels)
    """
    df = pd.read_excel(path, sheet_name="RAW_INPUT_METRICS")
    raw_cols, labels = _get_week_columns(df)
    
    rename_map = dict(zip(raw_cols, labels))
    df = df.rename(columns=rename_map)
    return df, labels


def load_orders(path: Path = DATA_PATH) -> pd.DataFrame:
    """Load RAW_ORDERS sheet.

    Returns:
        DataFrame with columns: COUNTRY, CITY, ZONE, METRIC, L8W..L0W.
    """
    df = pd.read_excel(path, sheet_name="RAW_ORDERS")
    return df


def load_summary(path: Path = DATA_PATH) -> pd.DataFrame:
    """Load RAW_SUMMARY sheet (data dictionary).

    Returns:
        DataFrame with columns containing metric names and descriptions.
    """
    df = pd.read_excel(path, sheet_name="RAW_SUMMARY")
    df.columns = df.columns.astype(str).str.strip()
    return df


def load_all(path: Path = DATA_PATH) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Load both datasets, normalized.

    Returns:
        (df_metrics, df_orders, week_labels)
    """
    df_metrics, week_labels = load_metrics(path)
    df_orders = load_orders(path)
    return df_metrics, df_orders, week_labels


def get_valid_metrics(df_metrics: pd.DataFrame) -> list[str]:
    """Return sorted list of unique metric names from the data."""
    metric_col = _get_metric_column(df_metrics)
    return sorted(df_metrics[metric_col].unique().tolist())


def get_valid_countries(df_metrics: pd.DataFrame) -> list[str]:
    """Return sorted list of unique country codes."""
    return sorted(df_metrics["COUNTRY"].unique().tolist())


def get_valid_zones(df_metrics: pd.DataFrame) -> list[str]:
    """Return sorted list of unique zone names."""
    return sorted(df_metrics["ZONE"].unique().tolist())


def get_valid_cities(df_metrics: pd.DataFrame) -> list[str]:
    """Return sorted list of unique city names."""
    return sorted(df_metrics["CITY"].unique().tolist())


def get_valid_zone_types(df_metrics: pd.DataFrame) -> list[str]:
    """Return sorted list of unique zone types."""
    return sorted(df_metrics["ZONE_TYPE"].unique().tolist())


def get_schema_summary(df_metrics: pd.DataFrame, df_orders: pd.DataFrame, week_labels: list[str]) -> str:
    """Generate a text summary of the data schema for LLM context injection.

    Includes column descriptions from RAW_SUMMARY when available.

    Returns:
        Human-readable string describing available columns, metrics,
        countries, zone types, and row counts.
    """
    metrics = get_valid_metrics(df_metrics)
    countries = get_valid_countries(df_metrics)
    zone_types = get_valid_zone_types(df_metrics)
    cities = get_valid_cities(df_metrics)

    # Load data dictionary for column descriptions
    try:
        df_summary = load_summary()
        
        # Dynamically find the best column names for metrics and descriptions
        metric_col = next((c for c in df_summary.columns if "metric" in str(c).lower() or "column" in str(c).lower()), None)
        desc_col = next((c for c in df_summary.columns if "description" in str(c).lower()), None)
        
        if metric_col and desc_col:
            df_summary = df_summary.dropna(subset=[metric_col])
            col_descriptions = "\n".join(
                f"- {row[metric_col]}: {row[desc_col]}"
                for _, row in df_summary.iterrows()
            )
            dict_section = f"\n\n## Metrics Dictionary\n{col_descriptions}"
        else:
            dict_section = ""
    except Exception:
        dict_section = ""

    week_range = f"{week_labels[0]}..{week_labels[-1]}" if week_labels else "No weeks found"

    return (
        f"## Dataset: RAW_INPUT_METRICS ({len(df_metrics):,} rows)\n"
        f"Columns: COUNTRY, CITY, ZONE, ZONE_TYPE, ZONE_PRIORITIZATION, METRIC, {week_range}\n"
        f"Metrics: {', '.join(metrics)}\n"
        f"Countries: {', '.join(countries)}\n"
        f"Zone Types: {', '.join(zone_types)}\n"
        f"Cities ({len(cities)}): {', '.join(cities[:10])}...\n\n"
        f"## Dataset: RAW_ORDERS ({len(df_orders):,} rows)\n"
        f"Columns: COUNTRY, CITY, ZONE, METRIC (always 'Orders'), {week_range}\n"
        f"Values are raw order counts (not ratios)."
        f"{dict_section}"
    )
