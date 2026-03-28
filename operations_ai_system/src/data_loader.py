"""Data loading and normalization for Rappi operational metrics."""

import re
from pathlib import Path

import pandas as pd

DATA_PATH = Path(__file__).parent.parent / "data" / "rappi_data.xlsx"


def get_metric_column(df: pd.DataFrame) -> str:
    """Find the metric column name in a DataFrame (case-insensitive)."""
    metric_col = next((c for c in df.columns if str(c).upper() == "METRIC"), None)
    if not metric_col:
        # Fallback to the first column with "metric" in the name
        metric_col = next((c for c in df.columns if "METRIC" in str(c).upper()), "METRIC")
    return metric_col


def _get_week_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Identify and sort week columns (L#W, L#W_ROLL, L#W_VALUE) from a DataFrame.

    Returns:
        (raw_cols, clean_labels) — sorted from oldest (e.g., L8W) to newest (L0W).
    """
    # Pattern matches L0W, L0W_ROLL, L0W_VALUE, etc.
    pattern = re.compile(r"^L(\d+)W(_ROLL|_VALUE)?$")
    week_cols = []
    
    for col in df.columns:
        match = pattern.match(str(col))
        if match:
            week_num = int(match.group(1))
            week_cols.append((week_num, col))
            
    # Sort by week number descending (L8W, L7W... L0W)
    week_cols.sort(key=lambda x: x[0], reverse=True)
    
    raw_cols = [c[1] for c in week_cols]
    # Standardize to L#W
    clean_labels = [f"L{c[0]}W" for c in week_cols]
    
    return raw_cols, clean_labels


def get_dimension_columns(df: pd.DataFrame, week_labels: list[str]) -> list[str]:
    """Identify dimension columns (anything not a metric or week label)."""
    metric_col = get_metric_column(df)
    exclude = set([metric_col] + week_labels)
    # Also exclude common variants just in case
    for w in week_labels:
        exclude.add(f"{w}_ROLL")
        exclude.add(f"{w}_VALUE")
    
    return [c for c in df.columns if c not in exclude]


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
    """Load RAW_ORDERS sheet and normalize week columns.

    Returns:
        DataFrame with standardized columns: COUNTRY, CITY, ZONE, METRIC, L8W..L0W.
    """
    df = pd.read_excel(path, sheet_name="RAW_ORDERS")
    raw_cols, labels = _get_week_columns(df)
    
    rename_map = dict(zip(raw_cols, labels))
    df = df.rename(columns=rename_map)
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
    metric_col = get_metric_column(df_metrics)
    return sorted(df_metrics[metric_col].unique().tolist())


def get_schema_summary(df_metrics: pd.DataFrame, df_orders: pd.DataFrame, week_labels: list[str]) -> str:
    """Generate a text summary of the data schema for LLM context injection.

    Includes column descriptions from RAW_SUMMARY when available.

    Returns:
        Human-readable string describing available columns, metrics,
        dimensions, and row counts.
    """
    metrics = get_valid_metrics(df_metrics)
    dimensions = get_dimension_columns(df_metrics, week_labels)
    metric_col_name = get_metric_column(df_metrics)

    # Example values for dimensions to help the LLM understand what they contain
    dim_examples = []
    for dim in dimensions:
        examples = df_metrics[dim].dropna().unique()[:5].tolist()
        dim_examples.append(f"{dim}: {', '.join(map(str, examples))}...")

    # Load data dictionary for column descriptions
    try:
        df_summary = load_summary()
        
        metric_desc_col = next((c for c in df_summary.columns if "metric" in str(c).lower() or "column" in str(c).lower()), None)
        desc_col = next((c for c in df_summary.columns if "description" in str(c).lower()), None)
        
        if metric_desc_col and desc_col:
            df_summary = df_summary.dropna(subset=[metric_desc_col])
            col_descriptions = "\n".join(
                f"- {row[metric_desc_col]}: {row[desc_col]}"
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
        f"Dimensions Available for Filtering/Grouping:\n"
        f"{chr(10).join(['- ' + ex for ex in dim_examples])}\n\n"
        f"Metric column name: {metric_col_name}\n"
        f"Metrics: {', '.join(metrics)}\n"
        f"Weeks: {week_range}\n\n"
        f"## Dataset: RAW_ORDERS ({len(df_orders):,} rows)\n"
        f"Metric: Always 'Orders'\n"
        f"Values are raw order counts (not ratios)."
        f"{dict_section}"
    )
