"""Nassau Candy - Product Line Profitability & Margin Performance dashboard.

Run:  streamlit run app.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from nassau import metrics as M
from nassau.data import load_clean

st.set_page_config(page_title="Nassau Candy | Profitability", page_icon="🍬", layout="wide")

COLORS = {"Chocolate": "#2a6fdb", "Other": "#e8833a", "Sugar": "#2e9c6a"}
FLAG_COLORS = {"Healthy": "#2e9c6a", "Repricing review": "#e8b13a", "Cost renegotiation": "#e8833a",
               "Cost renegotiation + repricing": "#d1495b", "Discontinuation review": "#8b1e3f"}


@st.cache_data(show_spinner="Loading and cleaning data...")
def get_data():
    return load_clean()


df_all, clean_report = get_data()

# ------------------------------------------------------------------ sidebar filters
st.sidebar.title("Filters")
dmin, dmax = df_all["Order Date"].min().date(), df_all["Order Date"].max().date()
date_range = st.sidebar.date_input("Order date range", (dmin, dmax), min_value=dmin, max_value=dmax)
if isinstance(date_range, tuple) and len(date_range) == 2:
    d0, d1 = date_range
else:
    d0, d1 = dmin, dmax
divisions = st.sidebar.multiselect("Division", sorted(df_all["Division"].unique()),
                                   default=sorted(df_all["Division"].unique()))
margin_thr = st.sidebar.slider("Margin threshold (%)", 0, 90, int(M.DEFAULT_MARGIN_THRESHOLD * 100), 1,
                               help="Products below this gross margin are treated as margin risks.") / 100
crit_thr = st.sidebar.slider("Critical margin (%)", 0, 50, int(M.CRITICAL_MARGIN * 100), 1,
                             help="Below this a product is flagged High risk.") / 100
rev_thr = st.sidebar.number_input("'High-sales' = revenue share of at least (%)", 0.0, 20.0,
                                  M.MATERIAL_REVENUE_SHARE * 100, 0.5) / 100
search = st.sidebar.text_input("Product search", placeholder="e.g. Wonka, Gum, Kazookles")

mask = (df_all["Order Date"].dt.date >= d0) & (df_all["Order Date"].dt.date <= d1) & df_all["Division"].isin(divisions)
df = df_all[mask]
if search:
    df = df[df["Product Name"].str.contains(search, case=False, regex=False)]

st.title("🍬 Nassau Candy - Product Profitability & Margin Performance")
st.caption("Sales volume alone is misleading. This dashboard shows which products and divisions actually earn profit, "
           "and where pricing, sourcing or rationalisation is needed.")

if df.empty:
    st.warning("No data for the selected filters.")
    st.stop()

# ------------------------------------------------------------------ KPI row
k = M.headline_kpis(df)
c = st.columns(6)
c[0].metric("Sales", f"${k['Sales']:,.0f}")
c[1].metric("Gross profit", f"${k['GrossProfit']:,.0f}")
c[2].metric("Gross margin", f"{k['GrossMargin']:.1%}")
c[3].metric("Profit / unit", f"${k['ProfitPerUnit']:.2f}")
c[4].metric("Units", f"{k['Units']:,}")
c[5].metric("Orders", f"{k['Orders']:,}")

pm = M.product_metrics(df)
diag = M.diagnose_products(pm, margin_thr, crit_thr, rev_thr)
div = M.division_metrics(df)

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Product profitability", "Division performance", "Cost vs margin diagnostics",
     "Profit concentration", "Data & method"])

# ------------------------------------------------------------------ tab 1
with tab1:
    st.subheader("Product margin leaderboard")
    rank_by = st.radio("Rank by", ["Gross profit", "Gross margin"], horizontal=True)
    col = "GrossProfit" if rank_by == "Gross profit" else "GrossMargin"
    lb = diag.sort_values(col, ascending=False)
    show = lb[["Product Name", "Division", "Sales", "Units", "GrossProfit", "GrossMargin", "ProfitPerUnit",
               "RevenueContribution", "ProfitContribution", "MarginVolatility", "Segment"]].copy()
    st.dataframe(
        show, hide_index=True, width="stretch",
        column_config={
            "Sales": st.column_config.NumberColumn(format="$%.0f"),
            "GrossProfit": st.column_config.NumberColumn("Gross profit", format="$%.0f"),
            "GrossMargin": st.column_config.NumberColumn("Gross margin", format="percent"),
            "ProfitPerUnit": st.column_config.NumberColumn("Profit / unit", format="$%.2f"),
            "RevenueContribution": st.column_config.NumberColumn("Revenue share", format="percent"),
            "ProfitContribution": st.column_config.NumberColumn("Profit share", format="percent"),
            "MarginVolatility": st.column_config.NumberColumn("Margin volatility (pp)", format="%.2f"),
        })
    a, b = st.columns(2)
    with a:
        fig = px.bar(lb.sort_values("GrossProfit"), x="GrossProfit", y="Product Name", orientation="h",
                     color="Division", color_discrete_map=COLORS, title="Profit contribution ($)")
        fig.update_layout(height=480, yaxis_title=None, xaxis_title="Gross profit ($)")
        st.plotly_chart(fig, width="stretch")
    with b:
        fig = px.scatter(diag, x="Sales", y="GrossMargin", size="Units", color="Segment", text="Product Name",
                         log_x=True, title="Sales vs margin: is volume profitable?",
                         hover_data={"GrossProfit": ":$,.0f", "Units": True})
        fig.add_hline(y=margin_thr, line_dash="dash", line_color="grey",
                      annotation_text=f"threshold {margin_thr:.0%}")
        fig.update_traces(textposition="top center", textfont_size=9)
        fig.update_layout(height=480, yaxis_tickformat=".0%", yaxis_title="Gross margin")
        st.plotly_chart(fig, width="stretch")
    seg = diag.groupby("Segment").agg(Products=("Product Name", "count"), Sales=("Sales", "sum"),
                                      GrossProfit=("GrossProfit", "sum")).reset_index()
    st.markdown("**Segments** (high sales = revenue share above the sidebar cut-off; high margin = above the threshold)")
    st.dataframe(seg, hide_index=True, width="stretch",
                 column_config={"Sales": st.column_config.NumberColumn(format="$%.0f"),
                                "GrossProfit": st.column_config.NumberColumn("Gross profit", format="$%.0f")})

# ------------------------------------------------------------------ tab 2
with tab2:
    st.subheader("Division performance")
    a, b = st.columns(2)
    with a:
        long = div.melt(id_vars="Division", value_vars=["RevenueShare", "ProfitShare"],
                        var_name="Metric", value_name="Share")
        long["Metric"] = long["Metric"].map({"RevenueShare": "Revenue share", "ProfitShare": "Profit share"})
        fig = px.bar(long, x="Division", y="Share", color="Metric", barmode="group",
                     color_discrete_sequence=["#8a8f98", "#2a6fdb"], title="Revenue vs profit share")
        fig.update_layout(yaxis_tickformat=".0%", height=400)
        st.plotly_chart(fig, width="stretch")
    with b:
        order_m = df.assign(MarginPct=df["Gross Margin"] * 100)
        fig = px.box(order_m, x="Division", y="MarginPct", color="Division", color_discrete_map=COLORS,
                     title="Order-level margin distribution", points=False)
        fig.update_layout(height=400, showlegend=False, yaxis_title="Gross margin (%)")
        st.plotly_chart(fig, width="stretch")
    st.dataframe(
        div[["Division", "Products", "Sales", "GrossProfit", "GrossMargin", "AvgOrderMargin", "ProfitPerUnit",
             "RevenueShare", "ProfitShare", "ProfitMinusRevenueShare", "MarginVolatility", "Efficiency"]],
        hide_index=True, width="stretch",
        column_config={
            "Sales": st.column_config.NumberColumn(format="$%.0f"),
            "GrossProfit": st.column_config.NumberColumn("Gross profit", format="$%.0f"),
            "GrossMargin": st.column_config.NumberColumn("Weighted margin", format="percent"),
            "AvgOrderMargin": st.column_config.NumberColumn("Avg order margin", format="percent"),
            "ProfitPerUnit": st.column_config.NumberColumn("Profit / unit", format="$%.2f"),
            "RevenueShare": st.column_config.NumberColumn("Revenue share", format="percent"),
            "ProfitShare": st.column_config.NumberColumn("Profit share", format="percent"),
            "ProfitMinusRevenueShare": st.column_config.NumberColumn("Profit share - revenue share", format="percent"),
            "MarginVolatility": st.column_config.NumberColumn("Monthly margin volatility (pp)", format="%.2f"),
        })
    st.caption("A negative 'profit share - revenue share' means the division takes more of the revenue than it returns in profit. "
               "'Weighted margin' = total profit / total sales; 'Avg order margin' is the simple mean of order margins.")
    mm = M.monthly_margin(df, "Division")
    fig = px.line(mm, x="Month", y="GrossMargin", color="Division", color_discrete_map=COLORS, markers=True,
                  title="Monthly gross margin by division")
    fig.update_layout(yaxis_tickformat=".0%", height=360)
    st.plotly_chart(fig, width="stretch")
    fac = M.group_metrics(df, "Factory")
    st.markdown("**By factory** (product-to-factory mapping from the project brief)")
    st.dataframe(fac[["Factory", "Products", "Sales", "GrossProfit", "GrossMargin", "ProfitPerUnit", "RevenueShare",
                      "ProfitShare"]], hide_index=True, width="stretch",
                 column_config={"Sales": st.column_config.NumberColumn(format="$%.0f"),
                                "GrossProfit": st.column_config.NumberColumn("Gross profit", format="$%.0f"),
                                "GrossMargin": st.column_config.NumberColumn("Margin", format="percent"),
                                "ProfitPerUnit": st.column_config.NumberColumn("Profit / unit", format="$%.2f"),
                                "RevenueShare": st.column_config.NumberColumn("Revenue share", format="percent"),
                                "ProfitShare": st.column_config.NumberColumn("Profit share", format="percent")})

# ------------------------------------------------------------------ tab 3
with tab3:
    st.subheader("Cost vs margin diagnostics")
    a, b = st.columns([3, 2])
    with a:
        fig = px.scatter(diag, x="Sales", y="Cost", color="Flag", color_discrete_map=FLAG_COLORS,
                         size="Units", text="Product Name", log_x=True, log_y=True,
                         title="Cost vs sales (log-log); points near the diagonal have almost no margin")
        lim = float(max(diag["Sales"].max(), diag["Cost"].max()))
        lo = float(min(diag["Sales"].min(), diag["Cost"].min()))
        fig.add_trace(go.Scatter(x=[lo, lim], y=[lo, lim], mode="lines", name="Break-even",
                                 line=dict(dash="dash", color="grey")))
        fig.update_traces(textposition="top center", textfont_size=9, selector=dict(mode="markers+text"))
        fig.update_layout(height=500)
        st.plotly_chart(fig, width="stretch")
    with b:
        counts = diag["Flag"].value_counts().reindex(list(FLAG_COLORS)).dropna().reset_index()
        counts.columns = ["Flag", "Products"]
        st.markdown("**Margin risk flags**")
        st.dataframe(counts, hide_index=True, width="stretch")
        st.caption(f"Healthy: margin >= {margin_thr:.0%}. Critical: < {crit_thr:.0%}. "
                   f"Material volume: >= {rev_thr:.1%} of revenue.")
        risk = diag[diag["Flag"] != "Healthy"]
        st.metric("Revenue in flagged products", f"{risk['RevenueContribution'].sum():.1%}")
        st.metric("Profit left on the table vs threshold",
                  f"${((margin_thr * risk['Sales']) - risk['GrossProfit']).clip(lower=0).sum():,.0f}",
                  help="Extra gross profit if every flagged product earned exactly the threshold margin on its current sales.")
    flagged = diag[diag["Flag"] != "Healthy"].sort_values("RevenueContribution", ascending=False)
    st.markdown("**Products needing action**")
    if flagged.empty:
        st.success("No products fall below the margin threshold for the current filters.")
    else:
        st.dataframe(
            flagged[["Product Name", "Flag", "RiskLevel", "Sales", "GrossProfit", "GrossMargin", "UnitPrice",
                     "UnitCost", "PriceToReachTarget", "PriceIncreaseNeeded", "CostReductionNeeded"]],
            hide_index=True, width="stretch",
            column_config={
                "Sales": st.column_config.NumberColumn(format="$%.0f"),
                "GrossProfit": st.column_config.NumberColumn("Gross profit", format="$%.0f"),
                "GrossMargin": st.column_config.NumberColumn("Margin", format="percent"),
                "UnitPrice": st.column_config.NumberColumn("Unit price", format="$%.2f"),
                "UnitCost": st.column_config.NumberColumn("Unit cost", format="$%.2f"),
                "PriceToReachTarget": st.column_config.NumberColumn("Price for target margin", format="$%.2f"),
                "PriceIncreaseNeeded": st.column_config.NumberColumn("Price increase needed", format="percent"),
                "CostReductionNeeded": st.column_config.NumberColumn("or cost cut needed", format="percent"),
            })
    st.caption("In this dataset every product sells at a single price and unit cost, so product margins are fixed and do not "
               "vary over time. Margin risk is therefore structural (price/cost) rather than volatile.")

# ------------------------------------------------------------------ tab 4
with tab4:
    st.subheader("Profit concentration (Pareto)")
    cutoff = st.slider("Concentration cut-off (%)", 50, 95, 80, 5) / 100
    pr, sr = M.pareto(df, "Product Name", "Sales", cutoff)
    pp, sp = M.pareto(df, "Product Name", "Gross Profit", cutoff)
    c = st.columns(3)
    c[0].metric(f"Products for {cutoff:.0%} of revenue", f"{sr['items_for_cutoff']} of {sr['items']}",
                f"{sr['pct_items_for_cutoff']:.0%} of products", delta_color="off")
    c[1].metric(f"Products for {cutoff:.0%} of profit", f"{sp['items_for_cutoff']} of {sp['items']}",
                f"{sp['pct_items_for_cutoff']:.0%} of products", delta_color="off")
    c[2].metric("Top product profit share", f"{pp['Share'].iloc[0]:.1%}", pp["Product Name"].iloc[0], delta_color="off")

    def pareto_chart(t, label, value_col):
        fig = go.Figure()
        fig.add_bar(x=t["Product Name"], y=t["Share"], name=f"{label} share", marker_color="#2a6fdb")
        fig.add_scatter(x=t["Product Name"], y=t["CumShare"], name="Cumulative", yaxis="y2", mode="lines+markers",
                        line=dict(color="#e8833a"))
        fig.add_hline(y=cutoff, line_dash="dash", line_color="grey", yref="y2")
        fig.update_layout(title=f"Pareto: {label} by product", height=420, yaxis=dict(tickformat=".0%"),
                          yaxis2=dict(overlaying="y", side="right", tickformat=".0%", range=[0, 1.05]),
                          legend=dict(orientation="h", y=-0.5), xaxis_tickangle=-45)
        return fig

    a, b = st.columns(2)
    a.plotly_chart(pareto_chart(pr, "Revenue", "Sales"), width="stretch")
    b.plotly_chart(pareto_chart(pp, "Gross profit", "Gross Profit"), width="stretch")

    st.markdown("**Dependency indicators**")
    dep = M.dependency_indicators(df)
    st.dataframe(dep, hide_index=True, width="stretch", column_config={
        "TopItemProfitShare": st.column_config.NumberColumn("Top item profit share", format="percent"),
        "Top3ProfitShare": st.column_config.NumberColumn("Top-3 profit share", format="percent"),
        "TopItemRevenueShare": st.column_config.NumberColumn("Top item revenue share", format="percent"),
        "ProfitHHI": st.column_config.NumberColumn("Profit HHI", format="%.3f"),
        "EffectiveItems": st.column_config.NumberColumn("Effective # of contributors", format="%.1f"),
    })
    st.caption("Risk: High if the top item earns >= 50% of profit, Moderate if >= 30%. HHI runs 0-1 (1 = one contributor); "
               "'effective contributors' = 1 / HHI.")
    dim = st.radio("Geographic concentration", ["State/Province", "Region"], horizontal=True)
    geo, gs = M.pareto(df, dim, "Gross Profit", cutoff)
    st.write(f"**{gs['items_for_cutoff']} of {gs['items']}** {dim.lower()}s generate {cutoff:.0%} of gross profit.")
    fig = px.bar(geo.head(15), x=dim, y="Share", title=f"Top {dim.lower()}s by profit share")
    fig.update_layout(yaxis_tickformat=".0%", height=360)
    st.plotly_chart(fig, width="stretch")

# ------------------------------------------------------------------ tab 5
with tab5:
    st.subheader("Data cleaning report")
    st.json(clean_report)
    st.markdown(
        "**Method.** Gross margin = gross profit / sales (computed on summed values, never an average of ratios). "
        "Profit per unit = gross profit / units. Revenue/profit contribution = product share of the total. "
        "Margin volatility = standard deviation (percentage points) of a product's monthly margin, shown only if it has "
        ">= 3 months of data.\n\n"
        "**Data caveat.** Ship Date values fall in 2026-2030, well after the 2024-2025 order dates, so shipping metrics were "
        "not used; profitability does not depend on them."
    )
    st.download_button("Download filtered product table (CSV)", diag.to_csv(index=False), "product_diagnostics.csv")
