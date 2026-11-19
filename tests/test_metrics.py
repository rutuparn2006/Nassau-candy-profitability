import numpy as np
import pandas as pd
import pytest

from nassau import metrics as M
from nassau.data import clean, load_clean, standardize_product_name


@pytest.fixture(scope="module")
def df():
    d, _ = load_clean()
    return d


def test_label_standardisation():
    assert standardize_product_name("Wonka Bar -Scrumdiddlyumptious") == "Wonka Bar - Scrumdiddlyumptious"
    assert standardize_product_name("Wonka Bar - Milk Chocolate") == "Wonka Bar - Milk Chocolate"


def test_cleaning_drops_invalid_rows(df):
    raw = pd.DataFrame({
        "Order ID": ["a", "b", "c", "d"], "Order Date": ["01-01-2024"] * 4, "Ship Date": ["01-02-2024"] * 4,
        "Ship Mode": ["Standard Class"] * 4, "Country/Region": ["United States"] * 4, "City": ["X"] * 4,
        "State/Province": ["Y"] * 4, "Division": ["chocolate"] * 4, "Region": ["pacific"] * 4,
        "Product Name": ["Wonka Gum"] * 4,
        "Sales": [10.0, 0.0, 10.0, 10.0], "Cost": [4.0, 4.0, 4.0, 4.0],
        "Gross Profit": [6.0, -4.0, 9.0, 6.0], "Units": [2, 2, 2, np.nan]})
    out, rep = clean(raw)
    assert rep["invalid_sales_or_cost"] == 1      # zero sales
    assert rep["inconsistent_gross_profit"] == 1  # 10 - 4 != 9
    assert rep["missing_units"] == 1              # imputed, not dropped
    assert len(out) == 2 and out["Units"].tolist() == [2, 2]
    assert set(out["Division"]) == {"Chocolate"}


def test_totals_reconcile(df):
    pm = M.product_metrics(df)
    assert pm["Sales"].sum() == pytest.approx(df["Sales"].sum())
    assert pm["GrossProfit"].sum() == pytest.approx(df["Gross Profit"].sum())
    assert pm["RevenueContribution"].sum() == pytest.approx(1)
    assert pm["ProfitContribution"].sum() == pytest.approx(1)
    assert (pm["GrossMargin"] == pm["GrossProfit"] / pm["Sales"]).all()


def test_gross_profit_equals_sales_minus_cost(df):
    assert ((df["Sales"] - df["Cost"] - df["Gross Profit"]).abs() < 0.011).all()


def test_division_shares_sum_to_one(df):
    div = M.division_metrics(df)
    assert div["RevenueShare"].sum() == pytest.approx(1)
    assert div["ProfitShare"].sum() == pytest.approx(1)


def test_pareto_monotonic_and_cutoff(df):
    t, s = M.pareto(df, "Product Name", "Gross Profit")
    assert t["CumShare"].is_monotonic_increasing
    assert t["CumShare"].iloc[-1] == pytest.approx(1)
    assert t["CumShare"].iloc[s["items_for_cutoff"] - 1] >= 0.8
    if s["items_for_cutoff"] > 1:
        assert t["CumShare"].iloc[s["items_for_cutoff"] - 2] < 0.8


def test_flags_and_repricing_math(df):
    d = M.diagnose_products(M.product_metrics(df))
    kz = d[d["Product Name"] == "Kazookles"].iloc[0]
    assert kz["Flag"] == "Discontinuation review"
    # price needed for a 60% margin: cost / (1 - 0.6)
    assert kz["PriceToReachTarget"] == pytest.approx(kz["UnitCost"] / 0.4)
    healthy = d[d["GrossMargin"] >= M.DEFAULT_MARGIN_THRESHOLD]
    assert (healthy["Flag"] == "Healthy").all()


def test_hhi_bounds():
    assert M.hhi(pd.Series([1, 0, 0])) == 1
    assert M.hhi(pd.Series([1, 1, 1, 1])) == pytest.approx(0.25)
