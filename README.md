# Nassau Candy - Product Line Profitability & Margin Performance

A data analytics project that shows which products and divisions of Nassau Candy Distributor actually drive profit, whether high-sales products are profitable, and where pricing, sourcing or product rationalisation is needed.

**Deliverables**

| Deliverable | Location |
|---|---|
| Research paper (EDA, insights, recommendations) | [`reports/research_report.md`](reports/research_report.md) |
| Executive summary | [`reports/executive_summary.md`](reports/executive_summary.md) |
| Streamlit dashboard | [`app.py`](app.py) |
| Analysis pipeline (tables + figures) | [`run_analysis.py`](run_analysis.py), output in [`outputs/`](outputs/) |

## Key findings

* Gross profit **$93,443** on **$141,784** sales (**65.9%** margin), 2024-25, 15 products.
* **5 Wonka Bars = 93% of revenue and 95% of profit**; no single product exceeds 21% of profit.
* **Kazookles**: 7.7% margin ($0.25 profit/unit): review for discontinuation. **Lickable Wallpaper**: 50% margin on 5.5% of revenue.
* **"Other" division** margin 44.8% vs Chocolate 67.4%.
* Product margins are **structural**: each product has a single price and unit cost, so the fix is pricing/cost, not volatility control.

## Quick start

```bash
git clone <your-repo-url>
cd nassau-candy-profitability
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python run_analysis.py      # regenerate outputs/tables/*.csv and outputs/figures/*.png
pytest                      # run the tests
python manage_users.py add yourname --role admin --name "Your Name"   # create the first account
streamlit run app.py        # launch the dashboard at http://localhost:8501 and sign in
```

## Dashboard

Sidebar: **date range**, **division filter**, **margin threshold slider** (plus critical-margin slider and high-sales cut-off), and **product search**.

| Tab | Contents |
|---|---|
| Product profitability | Margin leaderboard (rank by profit or margin), profit contribution chart, sales-vs-margin segmentation |
| Division performance | Revenue vs profit share, margin distribution by division, monthly margin, factory table |
| Cost vs margin diagnostics | Cost-sales scatter, margin risk flags, price / cost change needed to hit the target margin |
| Profit concentration | Pareto charts (adjustable cut-off), dependency indicators (HHI), geographic concentration |
| Data & method | Cleaning report, metric definitions, caveats, CSV download (analyst and admin) |
| Team & access | People, roles, audit log (admin only) |

## Sign-in and access

The dashboard sits behind a login page. Nothing (not even the data) loads until someone signs in.

| Role | Can do |
|---|---|
| Admin | Everything, plus add / disable / delete people, reset passwords, unlock accounts, read the audit log (Team & access tab) |
| Analyst | All dashboards, the Data & method tab, CSV export |
| Viewer | Dashboards only |

**Creating accounts.** There is no default password. Create the first admin with `python manage_users.py add <username> --role admin`
(passwords are prompted for, never typed on the command line). After that, admins add people from the **Team & access** tab.
`manage_users.py` also supports `list`, `passwd`, `role`, `enable`, `disable`, `unlock`, `delete` and `audit`.
On a hosted deployment where you can't run the CLI, set `NASSAU_ADMIN_USER` and `NASSAU_ADMIN_PASSWORD` (environment variables or
`.streamlit/secrets.toml`) and the first admin is created on first start; change that password after signing in.

**What is enforced**

* Passwords are stored only as salted PBKDF2-HMAC-SHA256 hashes (600,000 iterations), checked in constant time. Minimum 10 characters with a letter and a number.
* 5 wrong attempts lock a username for 15 minutes (also for names that don't exist, and the login error never says which part was wrong).
* Sessions end after 30 minutes of inactivity. Disabling or deleting a person takes effect on their next click.
* The last active admin can't be removed, disabled or demoted.
* Sign-ins, failures, lock-outs and account changes are written to `auth_data/audit.log`.
* Accounts live in `auth_data/users.json` (owner-only permissions, git-ignored).

**Limits.** Lock-out is per username, not per IP. Sessions are per browser tab and end on a full page refresh (there is no "remember me").
The user store is a JSON file, which suits a small team on one server; for many app instances or SSO, put the app behind your identity
provider or swap `UserStore` for a database. Serve the app over HTTPS in production so passwords are encrypted in transit.

## KPIs

| KPI | Definition |
|---|---|
| Gross margin (%) | Gross profit / sales |
| Profit per unit | Gross profit / units |
| Revenue contribution | Product sales / total sales |
| Profit contribution | Product gross profit / total gross profit |
| Margin volatility | Std-dev (pp) of monthly margin |

## Project structure

```
nassau-candy-profitability/
├── app.py                  # Streamlit dashboard (behind the login)
├── manage_users.py         # create / manage accounts from the command line
├── run_analysis.py         # end-to-end analysis -> outputs/
├── .streamlit/config.toml  # base theme colours
├── nassau/
│   ├── data.py             # loading, cleaning, validation, factory mapping
│   ├── metrics.py          # KPIs, segmentation, Pareto, HHI, diagnostics
│   ├── auth.py             # hashing, roles, lock-out, audit log (no Streamlit dependency)
│   ├── auth_ui.py          # login screen, session handling, admin panel
│   └── theme.py            # palette, CSS, animations, Plotly template
├── data/nassau_candy_distributor.csv
├── outputs/{tables,figures,summary.json}
├── reports/{research_report.md, executive_summary.md}
├── auth_data/              # created at runtime: users.json, audit.log (git-ignored)
├── tests/{test_metrics.py, test_auth.py, test_theme.py}
└── requirements.txt
```

## Methodology (summary)

1. **Clean & validate:** standardise labels, parse dates, drop invalid Sales/Cost/Profit records, impute missing units. (This dataset needed no row removal.)
2. **Metrics:** margin, profit per unit and contribution at product, division and factory level.
3. **Segment:** Star / Volume trap / Niche / Low sales-low profit.
4. **Concentration:** Pareto (80%) and HHI.
5. **Diagnose:** rule-based flags (repricing, cost renegotiation, discontinuation review) with the price or cost change required to reach the target margin.

## Notes on the data

* Ship Date values (2026-2030) are inconsistent with the 2024-25 order dates, so they are not used. Profitability does not depend on them.
* Figures are **gross** profit (sales minus manufacturing cost); shipping and overhead are not included.
* What-if dollar figures assume constant volume; the data has no price history to estimate elasticity.
