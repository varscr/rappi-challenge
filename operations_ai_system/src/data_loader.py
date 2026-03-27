"""Data loading and normalization for Rappi operational metrics."""

from pathlib import Path

import pandas as pd

DATA_PATH = Path(__file__).parent.parent / "data" / "rappi_data.xlsx"

WEEK_COLUMNS_ROLL = [f"L{i}W_ROLL" for i in range(8, -1, -1)]
WEEK_COLUMNS_RAW = [f"L{i}W" for i in range(8, -1, -1)]
WEEK_LABELS = [f"L{i}W" for i in range(8, -1, -1)]

GEO_COLUMNS = ["COUNTRY", "CITY", "ZONE"]
METRIC_COLUMN = "METRIC"

VALID_METRICS = [
    "% PRO Users Who Breakeven",
    "% Restaurants Sessions With Optimal Assortment",
    "Gross Profit UE",
    "Lead Penetration",
    "MLTV Top Verticals Adoption",
    "Non-Pro PTC > OP",
    "Perfect Orders",
    "Pro Adoption (Last Week Status)",
    "Restaurants Markdowns / GMV",
    "Restaurants SS > ATC CVR",
    "Restaurants SST > SS CVR",
    "Retail SST > SS CVR",
    "Turbo Adoption",
]


def load_metrics(path: Path = DATA_PATH) -> pd.DataFrame:
    """Load RAW_INPUT_METRICS sheet and normalize week columns.

    Returns:
        DataFrame with columns: COUNTRY, CITY, ZONE, ZONE_TYPE,
        ZONE_PRIORITIZATION, METRIC, L8W..L0W (renamed from _ROLL suffix).
    """
    df = pd.read_excel(path, sheet_name="RAW_INPUT_METRICS")
    rename_map = dict(zip(WEEK_COLUMNS_ROLL, WEEK_LABELS))
    df = df.rename(columns=rename_map)
    return df


def load_orders(path: Path = DATA_PATH) -> pd.DataFrame:
    """Load RAW_ORDERS sheet.

    Returns:
        DataFrame with columns: COUNTRY, CITY, ZONE, METRIC, L8W..L0W.
    """
    df = pd.read_excel(path, sheet_name="RAW_ORDERS")
    return df


def load_all(path: Path = DATA_PATH) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load both datasets, normalized.

    Returns:
        (df_metrics, df_orders) — both with L8W..L0W week columns.
    """
    return load_metrics(path), load_orders(path)


def get_valid_metrics(df_metrics: pd.DataFrame) -> list[str]:
    """Return sorted list of unique metric names from the data."""
    return sorted(df_metrics[METRIC_COLUMN].unique().tolist())


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


def get_schema_summary(df_metrics: pd.DataFrame, df_orders: pd.DataFrame) -> str:
    """Generate a text summary of the data schema for LLM context injection.

    Returns:
        Human-readable string describing available columns, metrics,
        countries, zone types, and row counts.
    """
    metrics = get_valid_metrics(df_metrics)
    countries = get_valid_countries(df_metrics)
    zone_types = get_valid_zone_types(df_metrics)
    cities = get_valid_cities(df_metrics)

    return (
        f"## Dataset: RAW_INPUT_METRICS ({len(df_metrics):,} rows)\n"
        f"Columns: COUNTRY, CITY, ZONE, ZONE_TYPE, ZONE_PRIORITIZATION, METRIC, L8W..L0W\n"
        f"Metrics: {', '.join(metrics)}\n"
        f"Countries: {', '.join(countries)}\n"
        f"Zone Types: {', '.join(zone_types)}\n"
        f"Cities ({len(cities)}): {', '.join(cities[:10])}...\n\n"
        f"## Dataset: RAW_ORDERS ({len(df_orders):,} rows)\n"
        f"Columns: COUNTRY, CITY, ZONE, METRIC (always 'Orders'), L8W..L0W\n"
        f"Values are raw order counts (not ratios)."
    )
