"""Profitability metrics, segmentation, Pareto and diagnostics."""
from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_MARGIN_THRESHOLD = 0.60   # "healthy" gross margin
CRITICAL_MARGIN = 0.25            # below this a product is structurally unprofitable
MATERIAL_REVENUE_SHARE = 0.01     # >=1% of revenue counts as a "high-sales" product


def _safe_div(a, b):
    return np.where(b == 0, np.nan, a / np.where(b == 0, 1, b))


# --------------------------------------------------------------------------- #
# Product level
# --------------------------------------------------------------------------- #
def margin_volatility(df: pd.DataFrame, min_months: int = 3) -> pd.Series:
    """Std-dev (in percentage points) of the monthly gross margin of each product."""
    monthly = df.groupby(["Product Name", "Month"]).agg(s=("Sales", "sum"), g=("Gross Profit", "sum")).reset_index()
    monthly["m"] = monthly["g"] / monthly["s"]
    counts = monthly.groupby("Product Name")["m"].count()
    vol = monthly.groupby("Product Name")["m"].std() * 100
    return vol.where(counts >= min_months)


def product_metrics(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["Product Name", "Division", "Factory"], dropna=False).agg(
        Orders=("Order ID", "nunique"),
        Sales=("Sales", "sum"),
        Units=("Units", "sum"),
        Cost=("Cost", "sum"),
        GrossProfit=("Gross Profit", "sum"),
    ).reset_index()
    tot_s, tot_p = g["Sales"].sum(), g["GrossProfit"].sum()
    g["GrossMargin"] = _safe_div(g["GrossProfit"], g["Sales"])
    g["ProfitPerUnit"] = _safe_div(g["GrossProfit"], g["Units"])
    g["UnitPrice"] = _safe_div(g["Sales"], g["Units"])
    g["UnitCost"] = _safe_div(g["Cost"], g["Units"])
    g["RevenueContribution"] = g["Sales"] / tot_s if tot_s else np.nan
    g["ProfitContribution"] = g["GrossProfit"] / tot_p if tot_p else np.nan
    g["MarginVolatility"] = g["Product Name"].map(margin_volatility(df))
    g["RankByProfit"] = g["GrossProfit"].rank(ascending=False, method="min").astype(int)
    g["RankByMargin"] = g["GrossMargin"].rank(ascending=False, method="min").astype(int)
    return g.sort_values("GrossProfit", ascending=False).reset_index(drop=True)


def segment_products(pm: pd.DataFrame, margin_threshold: float = DEFAULT_MARGIN_THRESHOLD,
                     revenue_share: float = MATERIAL_REVENUE_SHARE) -> pd.DataFrame:
    """Four-way segmentation on revenue share (volume) vs gross margin."""
    out = pm.copy()
    hi_sales = out["RevenueContribution"] >= revenue_share
    hi_margin = out["GrossMargin"] >= margin_threshold
    out["Segment"] = np.select(
        [hi_sales & hi_margin, hi_sales & ~hi_margin, ~hi_sales & hi_margin],
        ["Star: high profit / high margin", "Volume trap: high sales / low margin", "Niche: low sales / high margin"],
        default="Low sales / low profit",
    )
    return out


def diagnose_products(pm: pd.DataFrame, margin_threshold: float = DEFAULT_MARGIN_THRESHOLD,
                      critical_margin: float = CRITICAL_MARGIN,
                      revenue_share: float = MATERIAL_REVENUE_SHARE) -> pd.DataFrame:
    """Rule-based action flags (repricing / cost renegotiation / discontinuation review)."""
    out = segment_products(pm, margin_threshold, revenue_share)
    material = out["RevenueContribution"] >= revenue_share
    crit = out["GrossMargin"] < critical_margin
    weak = (out["GrossMargin"] >= critical_margin) & (out["GrossMargin"] < margin_threshold)
    out["Flag"] = np.select(
        [crit & ~material, crit & material, weak & material, weak & ~material],
        ["Discontinuation review", "Cost renegotiation + repricing", "Cost renegotiation", "Repricing review"],
        default="Healthy",
    )
    out["RiskLevel"] = np.select([crit, weak], ["High", "Medium"], default="Low")
    # Margin gap vs best product in the same division (pricing / cost inefficiency)
    best = out.groupby("Division")["GrossMargin"].transform("max")
    out["MarginGapVsDivisionBest"] = best - out["GrossMargin"]
    # What it would take to reach the target margin (price lever vs cost lever)
    below = out["GrossMargin"] < margin_threshold
    req_price = out["UnitCost"] / (1 - margin_threshold)
    req_cost = out["UnitPrice"] * (1 - margin_threshold)
    out["PriceToReachTarget"] = np.where(below, req_price, np.nan)
    out["PriceIncreaseNeeded"] = np.where(below, req_price / out["UnitPrice"] - 1, np.nan)
    out["UnitCostToReachTarget"] = np.where(below, req_cost, np.nan)
    out["CostReductionNeeded"] = np.where(below, 1 - req_cost / out["UnitCost"], np.nan)
    return out


# --------------------------------------------------------------------------- #
# Division / factory / region
# --------------------------------------------------------------------------- #
def group_metrics(df: pd.DataFrame, by: str) -> pd.DataFrame:
    g = df.groupby(by).agg(
        Products=("Product Name", "nunique"),
        Orders=("Order ID", "nunique"),
        Sales=("Sales", "sum"),
        Units=("Units", "sum"),
        Cost=("Cost", "sum"),
        GrossProfit=("Gross Profit", "sum"),
        AvgOrderMargin=("Gross Margin", "mean"),
    ).reset_index()
    g["GrossMargin"] = _safe_div(g["GrossProfit"], g["Sales"])
    g["ProfitPerUnit"] = _safe_div(g["GrossProfit"], g["Units"])
    g["RevenueShare"] = g["Sales"] / g["Sales"].sum()
    g["ProfitShare"] = g["GrossProfit"] / g["GrossProfit"].sum()
    g["ProfitMinusRevenueShare"] = g["ProfitShare"] - g["RevenueShare"]  # <0: revenue outruns profit
    mon = df.groupby([by, "Month"]).agg(s=("Sales", "sum"), p=("Gross Profit", "sum"))
    mon["m"] = mon["p"] / mon["s"]
    g["MarginVolatility"] = g[by].map(mon.groupby(level=0)["m"].std() * 100)  # pp, driven by mix/sparsity
    return g.sort_values("GrossProfit", ascending=False).reset_index(drop=True)


def division_metrics(df: pd.DataFrame) -> pd.DataFrame:
    g = group_metrics(df, "Division")
    overall = df["Gross Profit"].sum() / df["Sales"].sum() if len(df) else np.nan
    g["Efficiency"] = np.where(g["GrossMargin"] >= overall, "Strong financial efficiency", "Structural margin issue")
    return g


# --------------------------------------------------------------------------- #
# Pareto / concentration
# --------------------------------------------------------------------------- #
def pareto(df: pd.DataFrame, by: str, value: str, cutoff: float = 0.80) -> tuple[pd.DataFrame, dict]:
    s = df.groupby(by)[value].sum().sort_values(ascending=False)
    cum = s.cumsum() / s.sum()
    t = pd.DataFrame({by: s.index, value: s.values, "Share": s.values / s.sum(), "CumShare": cum.values})
    t["Rank"] = np.arange(1, len(t) + 1)
    n_needed = int((t["CumShare"] < cutoff).sum() + 1)
    stats = {"items": len(t), "items_for_cutoff": n_needed, "pct_items_for_cutoff": n_needed / len(t)}
    return t, stats


def hhi(shares: pd.Series) -> float:
    """Herfindahl-Hirschman index on a 0-1 scale (1 = single item)."""
    sh = shares / shares.sum()
    return float((sh ** 2).sum())


def dependency_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Over-dependency risk on products, divisions, factories, states and regions."""
    rows = []
    for dim in ["Product Name", "Division", "Factory", "State/Province", "Region"]:
        gp = df.groupby(dim)["Gross Profit"].sum().sort_values(ascending=False)
        sales = df.groupby(dim)["Sales"].sum().sort_values(ascending=False)
        h = hhi(gp)
        rows.append({
            "Dimension": dim,
            "Items": len(gp),
            "TopItem": gp.index[0],
            "TopItemProfitShare": gp.iloc[0] / gp.sum(),
            "Top3ProfitShare": gp.iloc[:3].sum() / gp.sum(),
            "TopItemRevenueShare": sales.iloc[0] / sales.sum(),
            "ProfitHHI": h,
            # effective number of equal-sized contributors
            "EffectiveItems": 1 / h if h else np.nan,
        })
    out = pd.DataFrame(rows)
    out["Risk"] = np.select(
        [out["TopItemProfitShare"] >= 0.5, out["TopItemProfitShare"] >= 0.3],
        ["High", "Moderate"], default="Low")
    return out


# --------------------------------------------------------------------------- #
# Time
# --------------------------------------------------------------------------- #
def monthly_margin(df: pd.DataFrame, by: str | None = None) -> pd.DataFrame:
    keys = ["Month"] + ([by] if by else [])
    m = df.groupby(keys).agg(Sales=("Sales", "sum"), GrossProfit=("Gross Profit", "sum")).reset_index()
    m["GrossMargin"] = m["GrossProfit"] / m["Sales"]
    return m


# --------------------------------------------------------------------------- #
# Headline KPIs
# --------------------------------------------------------------------------- #
def headline_kpis(df: pd.DataFrame) -> dict:
    s, p, u = df["Sales"].sum(), df["Gross Profit"].sum(), df["Units"].sum()
    return {
        "Sales": s, "GrossProfit": p, "Cost": df["Cost"].sum(), "Units": int(u),
        "GrossMargin": p / s if s else np.nan,
        "ProfitPerUnit": p / u if u else np.nan,
        "Orders": df["Order ID"].nunique(),
    }
