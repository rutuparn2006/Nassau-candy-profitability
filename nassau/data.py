"""Data loading, cleaning and validation for the Nassau Candy dataset."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "nassau_candy_distributor.csv"

# Product -> factory mapping and factory coordinates (from the project brief).
PRODUCT_FACTORY = {
    "Wonka Bar - Nutty Crunch Surprise": "Lot's O' Nuts",
    "Wonka Bar - Fudge Mallows": "Lot's O' Nuts",
    "Wonka Bar - Scrumdiddlyumptious": "Lot's O' Nuts",
    "Wonka Bar - Milk Chocolate": "Wicked Choccy's",
    "Wonka Bar - Triple Dazzle Caramel": "Wicked Choccy's",
    "Laffy Taffy": "Sugar Shack",
    "SweeTARTS": "Sugar Shack",
    "Nerds": "Sugar Shack",
    "Fun Dip": "Sugar Shack",
    "Fizzy Lifting Drinks": "Sugar Shack",
    "Everlasting Gobstopper": "Secret Factory",
    "Hair Toffee": "The Other Factory",
    "Lickable Wallpaper": "Secret Factory",
    "Wonka Gum": "Secret Factory",
    "Kazookles": "The Other Factory",
}

FACTORY_COORDS = {
    "Lot's O' Nuts": (32.881893, -111.768036),
    "Wicked Choccy's": (32.076176, -81.088371),
    "Sugar Shack": (48.11914, -96.18115),
    "Secret Factory": (41.446333, -90.565487),
    "The Other Factory": (35.1175, -89.971107),
}


def standardize_product_name(name: str) -> str:
    """Normalise spacing around the dash, e.g. 'Wonka Bar -Scrum...' -> 'Wonka Bar - Scrum...'."""
    return re.sub(r"\s*-\s*", " - ", " ".join(str(name).split()))


def load_raw(path: Path | str = DATA_PATH) -> pd.DataFrame:
    return pd.read_csv(path)


def clean(df: pd.DataFrame, tol: float = 0.011) -> tuple[pd.DataFrame, dict]:
    """Apply the cleaning rules from the brief and return (clean_df, report).

    Rules
    -----
    1. Standardise product / division / region / ship-mode labels.
    2. Parse dates (dd-mm-yyyy).
    3. Drop rows with non-positive Sales or Cost (invalid values).
    4. Drop rows where Gross Profit != Sales - Cost (invalid profit record).
    5. Missing / non-positive Units are imputed from the product's median unit price
       (Sales / median price), and dropped if that is impossible.
    """
    report: dict = {"rows_raw": len(df)}
    d = df.copy()

    # 1. labels
    d["Product Name"] = d["Product Name"].map(standardize_product_name)
    for col in ["Division", "Region", "Ship Mode", "City", "State/Province", "Country/Region"]:
        d[col] = d[col].astype(str).str.strip()
    d["Division"] = d["Division"].str.title()
    d["Region"] = d["Region"].str.title()

    # 2. dates
    d["Order Date"] = pd.to_datetime(d["Order Date"], format="%d-%m-%Y", errors="coerce")
    d["Ship Date"] = pd.to_datetime(d["Ship Date"], format="%d-%m-%Y", errors="coerce")
    report["bad_order_dates"] = int(d["Order Date"].isna().sum())
    d = d.dropna(subset=["Order Date"])

    # 3. sales / cost validity
    for col in ["Sales", "Cost", "Gross Profit"]:
        d[col] = pd.to_numeric(d[col], errors="coerce")
    bad_vals = d["Sales"].isna() | d["Cost"].isna() | d["Gross Profit"].isna() | (d["Sales"] <= 0) | (d["Cost"] <= 0)
    report["invalid_sales_or_cost"] = int(bad_vals.sum())
    d = d[~bad_vals]

    # 4. profit consistency
    bad_profit = (d["Sales"] - d["Cost"] - d["Gross Profit"]).abs() > tol
    report["inconsistent_gross_profit"] = int(bad_profit.sum())
    d = d[~bad_profit]

    # 5. units
    d["Units"] = pd.to_numeric(d["Units"], errors="coerce")
    missing_units = d["Units"].isna() | (d["Units"] <= 0)
    report["missing_units"] = int(missing_units.sum())
    if missing_units.any():
        unit_price = (d["Sales"] / d["Units"]).where(~missing_units)
        median_price = unit_price.groupby(d["Product Name"]).transform("median")
        d.loc[missing_units, "Units"] = (d.loc[missing_units, "Sales"] / median_price[missing_units]).round()
        d = d[d["Units"].notna() & (d["Units"] > 0)]
    d["Units"] = d["Units"].astype(int)

    # derived columns
    d["Factory"] = d["Product Name"].map(PRODUCT_FACTORY)
    d["Gross Margin"] = d["Gross Profit"] / d["Sales"]
    d["Month"] = d["Order Date"].dt.to_period("M").dt.to_timestamp()
    report["rows_clean"] = len(d)
    report["rows_removed"] = report["rows_raw"] - report["rows_clean"]
    report["unmapped_factory_rows"] = int(d["Factory"].isna().sum())
    return d.reset_index(drop=True), report


def load_clean(path: Path | str = DATA_PATH) -> tuple[pd.DataFrame, dict]:
    return clean(load_raw(path))
