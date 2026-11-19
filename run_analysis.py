"""Run the full analysis: cleaning -> metrics -> CSV tables + PNG figures.

Usage:  python run_analysis.py
Outputs: outputs/tables/*.csv, outputs/figures/*.png, outputs/summary.json
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from nassau import metrics as M
from nassau.data import load_clean

ROOT = Path(__file__).resolve().parent
TABLES, FIGS = ROOT / "outputs" / "tables", ROOT / "outputs" / "figures"
TABLES.mkdir(parents=True, exist_ok=True)
FIGS.mkdir(parents=True, exist_ok=True)

BLUE, ORANGE, RED, GREY, GREEN = "#2a6fdb", "#e8833a", "#d1495b", "#8a8f98", "#2e9c6a"
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
                     "axes.titleweight": "bold", "figure.dpi": 130})

SHORT = lambda s: s.replace("Wonka Bar - ", "WB: ")


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIGS / name, bbox_inches="tight")
    plt.close(fig)


def main():
    df, report = load_clean()
    print("Cleaning report:", report)

    pm = M.product_metrics(df)
    diag = M.diagnose_products(pm)
    div = M.division_metrics(df)
    fac = M.group_metrics(df, "Factory")
    reg = M.group_metrics(df, "Region")
    state = M.group_metrics(df, "State/Province")
    dep = M.dependency_indicators(df)
    p_rev, s_rev = M.pareto(df, "Product Name", "Sales")
    p_pro, s_pro = M.pareto(df, "Product Name", "Gross Profit")
    st_pro, s_st = M.pareto(df, "State/Province", "Gross Profit")
    mm = M.monthly_margin(df)
    mm_div = M.monthly_margin(df, "Division")

    for name, t in {"product_metrics": pm, "product_diagnostics": diag, "division_metrics": div,
                    "factory_metrics": fac, "region_metrics": reg, "state_metrics": state,
                    "dependency_indicators": dep, "pareto_products_revenue": p_rev,
                    "pareto_products_profit": p_pro, "pareto_states_profit": st_pro,
                    "monthly_margin": mm, "monthly_margin_by_division": mm_div}.items():
        t.to_csv(TABLES / f"{name}.csv", index=False)

    k = M.headline_kpis(df)
    summary = {
        "cleaning": report, "kpis": k,
        "pareto": {"products_revenue_80": s_rev, "products_profit_80": s_pro, "states_profit_80": s_st},
    }
    (ROOT / "outputs" / "summary.json").write_text(json.dumps(summary, indent=2, default=float))

    # ---- Figure 1: profit and margin leaderboard -------------------------------------------
    d = pm.sort_values("GrossProfit")
    fig, ax = plt.subplots(1, 2, figsize=(11, 5.2), sharey=True)
    ax[0].barh(d["Product Name"].map(SHORT), d["GrossProfit"], color=BLUE)
    ax[0].set_title("Gross profit ($)")
    ax[1].barh(d["Product Name"].map(SHORT), d["GrossMargin"] * 100,
               color=[RED if m < 25 else ORANGE if m < 60 else GREEN for m in d["GrossMargin"] * 100])
    ax[1].axvline(k["GrossMargin"] * 100, color=GREY, ls="--", lw=1)
    ax[1].set_title("Gross margin (%)  -  dashed = company average")
    save(fig, "01_product_profit_margin.png")

    # ---- Figure 2: Sales vs margin (segmentation) ------------------------------------------
    fig, ax = plt.subplots(figsize=(8, 5.4))
    ax.scatter(diag["Sales"], diag["GrossMargin"] * 100, s=np.sqrt(diag["Units"]) * 8, color=BLUE, alpha=.7)
    bars = diag[diag["Product Name"].str.startswith("Wonka Bar")].sort_values("GrossMargin", ascending=False)
    stagger = {n: (-8, 14 - 15 * i) for i, n in enumerate(bars["Product Name"])}  # keep the 5 bars legible
    for _, r in diag.iterrows():
        off = stagger.get(r["Product Name"], (4, 4))
        ax.annotate(SHORT(r["Product Name"]), (r["Sales"], r["GrossMargin"] * 100), fontsize=7.5,
                    xytext=(off[0] - 120 if r["Product Name"] in stagger else off[0], off[1]),
                    textcoords="offset points", ha="left",
                    arrowprops=dict(arrowstyle="-", color=GREY, lw=.5) if r["Product Name"] in stagger else None)
    ax.set_xscale("log"); ax.axhline(60, color=GREY, ls="--", lw=1)
    ax.set_xlim(left=diag["Sales"].min() * 0.6, right=diag["Sales"].max() * 2.2)
    ax.set_xlabel("Total sales ($, log scale)"); ax.set_ylabel("Gross margin (%)")
    ax.set_title("Sales volume vs margin (bubble = units)")
    save(fig, "02_sales_vs_margin.png")

    # ---- Figure 3: Division revenue vs profit share ----------------------------------------
    x = np.arange(len(div)); w = .38
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    ax.bar(x - w / 2, div["RevenueShare"] * 100, w, label="Revenue share", color=GREY)
    ax.bar(x + w / 2, div["ProfitShare"] * 100, w, label="Profit share", color=BLUE)
    ax.set_xticks(x, div["Division"]); ax.set_ylabel("% of total"); ax.legend()
    ax.set_title("Division: revenue share vs profit share")
    save(fig, "03_division_share.png")

    # ---- Figure 4: Pareto ------------------------------------------------------------------
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.4))
    for a, t, col, ttl in [(ax[0], p_rev, "Sales", "Revenue"), (ax[1], p_pro, "Gross Profit", "Gross profit")]:
        a.bar(range(len(t)), t["Share"] * 100, color=BLUE)
        a2 = a.twinx(); a2.plot(range(len(t)), t["CumShare"] * 100, color=ORANGE, marker="o", ms=3)
        a2.axhline(80, color=GREY, ls="--", lw=1); a2.set_ylim(0, 105)
        a.set_xticks(range(len(t)), [SHORT(n) for n in t["Product Name"]], rotation=70, ha="right", fontsize=7)
        a.set_title(f"Pareto: {ttl} by product"); a.set_ylabel("% share"); a2.set_ylabel("Cumulative %")
        a2.spines["top"].set_visible(False)
    save(fig, "04_pareto.png")

    # ---- Figure 5: Cost vs sales -----------------------------------------------------------
    fig, ax = plt.subplots(figsize=(7, 5))
    colors = diag["Flag"].map({"Healthy": GREEN, "Repricing review": ORANGE, "Cost renegotiation": ORANGE,
                               "Cost renegotiation + repricing": RED, "Discontinuation review": RED})
    ax.scatter(diag["Sales"], diag["Cost"], color=colors, s=60)
    lim = max(diag["Sales"].max(), diag["Cost"].max()) * 1.1
    ax.plot([1, lim], [1, lim], color=GREY, ls="--", lw=1, label="Break-even (cost = sales)")
    for _, r in diag.iterrows():
        ax.annotate(SHORT(r["Product Name"]), (r["Sales"], r["Cost"]), fontsize=7, xytext=(4, 3), textcoords="offset points")
    ax.set_xscale("log"); ax.set_yscale("log"); ax.legend()
    ax.set_xlabel("Total sales ($)"); ax.set_ylabel("Total cost ($)"); ax.set_title("Cost vs sales (log-log)")
    save(fig, "05_cost_vs_sales.png")

    # ---- Figure 6: monthly margin by division ---------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 4))
    for dv, c in zip(["Chocolate", "Other", "Sugar"], [BLUE, ORANGE, GREEN]):
        t = mm_div[mm_div["Division"] == dv]
        ax.plot(t["Month"], t["GrossMargin"] * 100, label=dv, color=c, marker="o", ms=3)
    ax.set_ylabel("Gross margin (%)"); ax.legend(); ax.set_title("Monthly gross margin by division")
    save(fig, "06_monthly_margin.png")

    print(json.dumps(summary, indent=2, default=float))
    print(diag[["Product Name", "Sales", "GrossProfit", "GrossMargin", "ProfitPerUnit",
                "RevenueContribution", "ProfitContribution", "MarginVolatility", "Segment", "Flag"]].round(3).to_string())
    print(div.round(3).to_string())
    print(fac.round(3).to_string())
    print(reg.round(3).to_string())
    print(dep.round(3).to_string())
    print(state.head(8)[["State/Province", "Sales", "GrossProfit", "GrossMargin", "ProfitShare"]].round(3).to_string())


if __name__ == "__main__":
    main()
