"""Visual identity for the dashboard: palette, CSS, HTML fragments and the Plotly template.

Kept free of Streamlit imports so the markup can be rendered and checked in a plain browser.
"""
from __future__ import annotations

import re
from html import escape

# ---------------------------------------------------------------------------- palette
INK = "#2A1245"          # deep plum: text, login panel
RASPBERRY = "#D6336C"    # primary accent
BUTTERSCOTCH = "#F2A93B"
MINT = "#1FA88A"
COCOA = "#7B4B2A"
SLATE = "#4F7CAC"
PAPER = "#FAF8FC"
LILAC = "#F1ECF7"
LINE = "#E4DCEE"
MUTED = "#6E6483"

DIVISION_COLORS = {"Chocolate": COCOA, "Sugar": RASPBERRY, "Other": SLATE}
FLAG_COLORS = {"Healthy": MINT, "Repricing review": BUTTERSCOTCH, "Cost renegotiation": "#E8743B",
               "Cost renegotiation + repricing": RASPBERRY, "Discontinuation review": "#7A1F4B"}
COLORWAY = [RASPBERRY, INK, BUTTERSCOTCH, MINT, SLATE, COCOA, "#9B72CF", "#E8743B"]

HEADING_FONT = "Fraunces"
BODY_FONT = "Figtree"


def _flat(html: str) -> str:
    """Collapse markup to one line. Streamlit's markdown turns indented or blank-line-separated HTML into code."""
    return re.sub(r">\s+<", "><", re.sub(r"\s*\n\s*", " ", html)).strip()


# ---------------------------------------------------------------------------- CSS
CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Figtree:wght@400;500;600;700&display=swap');

:root {{
  --ink:{INK}; --raspberry:{RASPBERRY}; --butterscotch:{BUTTERSCOTCH}; --mint:{MINT};
  --paper:{PAPER}; --lilac:{LILAC}; --line:{LINE}; --muted:{MUTED};
  --display:'{HEADING_FONT}', Georgia, 'Times New Roman', serif;
  --body:'{BODY_FONT}', system-ui, -apple-system, 'Segoe UI', sans-serif;
}}

html, body, .stApp, [data-testid="stAppViewContainer"] {{ font-family: var(--body); color: var(--ink); }}
.stApp {{
  background:
    radial-gradient(900px 420px at 92% -8%, rgba(214,51,108,.07), transparent 70%),
    radial-gradient(700px 380px at -5% 0%, rgba(242,169,59,.08), transparent 70%),
    var(--paper);
}}
[data-testid="stHeader"] {{ background: transparent; }}
#MainMenu, footer {{ visibility: hidden; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1320px; }}

h1, h2, h3, [data-testid="stHeading"] h1, [data-testid="stHeading"] h2, [data-testid="stHeading"] h3 {{
  font-family: var(--display); color: var(--ink); letter-spacing: -0.01em; font-weight: 600;
}}
h2, [data-testid="stHeading"] h2 {{ font-size: 1.55rem; }}
p, li, label, .stMarkdown {{ font-family: var(--body); }}
[data-testid="stCaptionContainer"] {{ color: var(--muted); }}

/* ---- sidebar */
[data-testid="stSidebar"] {{ background: var(--lilac); border-right: 1px solid var(--line); }}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ font-size: 1.15rem; }}

/* ---- inputs */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] {{
  border-radius: 10px !important; transition: box-shadow .2s ease, border-color .2s ease;
}}
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within {{
  box-shadow: 0 0 0 3px rgba(214,51,108,.18); border-color: var(--raspberry) !important;
}}

/* ---- buttons */
.stButton > button, [data-testid="stFormSubmitButton"] > button, .stDownloadButton > button {{
  font-family: var(--body); font-weight: 600; border-radius: 10px; border: 1px solid var(--line);
  transition: transform .15s ease, box-shadow .2s ease, background .2s ease, border-color .2s ease;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{ border-color: var(--raspberry); color: var(--raspberry); }}
[data-testid="stFormSubmitButton"] > button, .stButton > button[kind="primary"] {{
  background: var(--raspberry); color: #fff; border-color: var(--raspberry);
  box-shadow: 0 6px 16px -6px rgba(214,51,108,.55);
}}
[data-testid="stFormSubmitButton"] > button:hover, .stButton > button[kind="primary"]:hover {{
  background: #BF2B5E; color: #fff; border-color: #BF2B5E; transform: translateY(-1px);
}}
[data-testid="stFormSubmitButton"] > button:active, .stButton > button:active {{ transform: translateY(0); }}
button:focus-visible {{ outline: 3px solid rgba(214,51,108,.35) !important; outline-offset: 2px; }}

/* ---- tabs */
[data-baseweb="tab-list"] {{ gap: .25rem; border-bottom: 1px solid var(--line); }}
button[data-baseweb="tab"] {{
  font-family: var(--body); font-weight: 600; color: var(--muted); border-radius: 10px 10px 0 0; padding: .6rem 1rem;
  transition: color .2s ease, background .2s ease;
}}
button[data-baseweb="tab"]:hover {{ color: var(--ink); background: rgba(214,51,108,.06); }}
button[data-baseweb="tab"][aria-selected="true"] {{ color: var(--raspberry); }}
[data-baseweb="tab-highlight"] {{ background: var(--raspberry) !important; height: 3px !important; border-radius: 3px; }}
[data-baseweb="tab-border"] {{ display: none; }}
[data-baseweb="tab-panel"] {{ animation: nc-fade .35s ease both; padding-top: 1.1rem; }}

/* ---- data + charts */
[data-testid="stDataFrame"] {{ border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: #fff; }}
.stPlotlyChart {{ background: #fff; border: 1px solid var(--line); border-radius: 14px; padding: .35rem .5rem; }}
[data-testid="stMetric"] {{ background: #fff; border: 1px solid var(--line); border-radius: 12px; padding: .8rem 1rem; }}
[data-testid="stMetricValue"] {{ font-family: var(--display); font-weight: 600; }}
[data-testid="stAlert"] {{ border-radius: 12px; }}
[data-testid="stExpander"] {{ border: 1px solid var(--line); border-radius: 12px; background: #fff; }}

/* ---- brand lockup + page hero */
.nc-hero {{ display:flex; align-items:center; justify-content:space-between; gap:1.5rem; margin: 0 0 1.4rem; flex-wrap:wrap; }}
.nc-hero-left {{ display:flex; align-items:center; gap:1rem; min-width:0; }}
.nc-logo {{ width:52px; height:52px; flex:none; animation: nc-wobble 1.1s cubic-bezier(.3,1.6,.5,1) .15s both; }}
.nc-hero h1 {{ margin:0; font-size:2.3rem; line-height:1.1; padding:0; }}
.nc-hero p {{ margin:.3rem 0 0; color:var(--muted); max-width:62ch; line-height:1.5; }}
.nc-user {{ display:flex; align-items:center; gap:.7rem; background:#fff; border:1px solid var(--line);
  border-radius:999px; padding:.35rem .9rem .35rem .4rem; }}
.nc-avatar {{ width:34px; height:34px; border-radius:50%; background:var(--ink); color:#fff; display:grid; place-items:center;
  font-weight:700; font-size:.9rem; }}
.nc-user b {{ display:block; font-size:.9rem; line-height:1.1; }}
.nc-user span {{ font-size:.78rem; color:var(--muted); }}

/* ---- KPI strip: one panel, six cells */
.nc-kpis {{ display:grid; grid-template-columns: repeat(6, minmax(0,1fr)); background:#fff; border:1px solid var(--line);
  border-radius:18px; margin: 0 0 1.6rem; overflow:hidden; animation: nc-rise .6s cubic-bezier(.2,.7,.2,1) both; }}
.nc-kpi {{ padding:1.05rem 1.2rem 1.15rem; border-left:1px solid var(--line); min-width:0; }}
.nc-kpi:first-child {{ border-left:0; }}
.nc-kpi-label {{ color:var(--muted); font-size:.85rem; font-weight:500; }}
.nc-kpi-value {{ font-family:var(--display); font-weight:600; font-size:1.85rem; line-height:1.25; letter-spacing:-.01em;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.nc-kpi-bar {{ height:6px; border-radius:6px; background:var(--lilac); margin-top:.45rem; overflow:hidden; }}
.nc-kpi-bar i {{ display:block; height:100%; width:var(--w); border-radius:6px;
  background:linear-gradient(90deg, var(--raspberry), var(--butterscotch)); transform-origin:left;
  animation: nc-fill 1.1s cubic-bezier(.2,.7,.2,1) .35s both; }}
@media (max-width: 1100px) {{
  .nc-kpis {{ grid-template-columns: repeat(3, minmax(0,1fr)); }}
  .nc-kpi:nth-child(4) {{ border-left:0; }}
  .nc-kpi:nth-child(n+4) {{ border-top:1px solid var(--line); }}
}}
@media (max-width: 600px) {{
  .nc-kpis {{ grid-template-columns: repeat(2, minmax(0,1fr)); }}
  .nc-kpi {{ border-left:0 !important; border-top:1px solid var(--line); }}
  .nc-kpi:nth-child(-n+2) {{ border-top:0; }}
  .nc-kpi:nth-child(even) {{ border-left:1px solid var(--line) !important; }}
  .nc-hero h1 {{ font-size:1.8rem; }}
}}

/* ---- sidebar brand */
.nc-side-brand {{ display:flex; align-items:center; gap:.6rem; font-family:var(--display); font-weight:700; font-size:1.2rem; margin:.2rem 0 1rem; }}
.nc-side-brand svg {{ width:30px; height:30px; }}

/* ---- login screen */
.nc-brand {{ position:relative; overflow:hidden; min-height:600px; border-radius:26px; color:#fff; padding:2.6rem;
  display:flex; flex-direction:column; justify-content:space-between;
  background: linear-gradient(155deg,#3F1C63 0%, #2A1245 52%, #5B1D58 100%); }}
.nc-brand-top {{ display:flex; align-items:center; gap:.7rem; font-family:var(--display); font-size:1.45rem; font-weight:700; position:relative; z-index:2; }}
.nc-brand-top svg {{ width:38px; height:38px; }}
.nc-brand-copy {{ position:relative; z-index:2; max-width:22rem; }}
.nc-brand-copy h2 {{ font-family:var(--display); color:#fff; font-size:2.35rem; line-height:1.12; margin:0 0 .9rem; font-weight:600; }}
.nc-brand-copy p {{ margin:0; color:rgba(255,255,255,.78); line-height:1.55; }}
.nc-ball {{ position:absolute; border-radius:50%; width:var(--s); height:var(--s); left:var(--x); top:var(--y);
  background: radial-gradient(circle at 30% 26%, rgba(255,255,255,.85) 0 7%, var(--c) 8% 100%);
  box-shadow: inset -8px -10px 18px rgba(0,0,0,.22), 0 18px 30px -18px rgba(0,0,0,.6);
  animation: nc-float var(--d) ease-in-out var(--delay, 0s) infinite alternate; z-index:1; }}
.nc-mint {{ position:absolute; right:-70px; top:-70px; width:250px; height:250px; border-radius:50%; z-index:1;
  background: repeating-conic-gradient(from 0deg, #fff 0 12deg, {RASPBERRY} 12deg 24deg);
  -webkit-mask: radial-gradient(circle, transparent 0 24%, #000 25% 100%); mask: radial-gradient(circle, transparent 0 24%, #000 25% 100%);
  opacity:.92; animation: nc-spin 38s linear infinite; }}
.nc-login-head h2 {{ font-size:2rem; margin:0 0 .35rem; }}
.nc-login-head p {{ color:var(--muted); margin:0 0 1.2rem; line-height:1.5; }}
.nc-login-note {{ color:var(--muted); font-size:.85rem; margin-top:.9rem; }}
.nc-login-pane {{ animation: nc-rise .7s cubic-bezier(.2,.7,.2,1) .1s both; }}
.nc-brand {{ animation: nc-rise .7s cubic-bezier(.2,.7,.2,1) both; }}
.nc-setup code {{ background:var(--lilac); padding:.15rem .4rem; border-radius:6px; }}
[data-testid="stForm"] {{ border: 1px solid var(--line); border-radius: 18px; padding: 1.4rem 1.4rem .6rem; background:#fff; }}

/* ---- motion */
@keyframes nc-rise {{ from {{ opacity:0; transform: translateY(14px); }} to {{ opacity:1; transform:none; }} }}
@keyframes nc-fade {{ from {{ opacity:0; }} to {{ opacity:1; }} }}
@keyframes nc-fill {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
@keyframes nc-float {{ from {{ transform: translateY(0) rotate(0deg); }} to {{ transform: translateY(-22px) rotate(8deg); }} }}
@keyframes nc-spin {{ to {{ transform: rotate(360deg); }} }}
@keyframes nc-wobble {{ 0% {{ transform: scale(.4) rotate(-40deg); opacity:0; }} 100% {{ transform: none; opacity:1; }} }}
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ animation-duration: .001ms !important; animation-iteration-count: 1 !important; transition-duration: .001ms !important; }}
}}
"""

HIDE_SIDEBAR_CSS = """
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] { display: none !important; }
.block-container { max-width: 1100px; padding-top: 4vh; }
@media (max-width: 800px) {
  .nc-brand { min-height: 0; padding: 1.6rem; gap: 2.2rem; border-radius: 20px; }
  .nc-brand-copy h2 { font-size: 1.6rem; }
  .nc-brand-copy { max-width: none; }
  .nc-mint { width: 150px; height: 150px; right: -50px; top: -50px; }
  .nc-ball { display: none; }
}
"""


def style_tag(extra: str = "") -> str:
    return f"<style>{CSS}{extra}</style>"


# ---------------------------------------------------------------------------- HTML fragments
LOGO_SVG = (
    '<svg class="nc-logo" viewBox="0 0 52 52" aria-hidden="true">'
    f'<path d="M5 15 L18 26 L5 37 Z" fill="{BUTTERSCOTCH}"/><path d="M47 15 L34 26 L47 37 Z" fill="{BUTTERSCOTCH}"/>'
    f'<circle cx="26" cy="26" r="14" fill="{RASPBERRY}"/>'
    '<path d="M15.5 21.5 Q26 14 36.5 21.5" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round" opacity=".85"/>'
    '<path d="M16 31 Q26 37 36 31" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round" opacity=".45"/></svg>'
)


def initials(name: str) -> str:
    parts = [p for p in re.split(r"[\s._-]+", name.strip()) if p]
    return (parts[0][0] + (parts[1][0] if len(parts) > 1 else "")).upper() if parts else "?"


def login_brand_html() -> str:
    balls = [
        ("#F2A93B", 74, "8%", "28%", "7s", "0s"), ("#1FA88A", 46, "70%", "20%", "5.5s", ".6s"),
        ("#9B72CF", 98, "62%", "38%", "8s", "1.2s"), ("#E8743B", 38, "24%", "52%", "6s", ".3s"),
        ("#FF7BAA", 58, "82%", "62%", "7.5s", ".9s"),
    ]
    ball_html = "".join(
        f'<span class="nc-ball" style="--c:{c};--s:{s}px;--x:{x};--y:{y};--d:{d};--delay:{dl}"></span>'
        for c, s, x, y, d, dl in balls)
    return _flat(f"""
    <div class="nc-brand">
      <span class="nc-mint" aria-hidden="true"></span>{ball_html}
      <div class="nc-brand-top">{LOGO_SVG.replace('class="nc-logo"', '')}<span>Nassau Candy</span></div>
      <div class="nc-brand-copy">
        <h2>Which candy actually earns its shelf space?</h2>
        <p>Margin, product mix and pricing for the whole line. Because the best-selling product is not always the most profitable one.</p>
      </div>
    </div>""")


def login_head_html(title: str, subtitle: str) -> str:
    return _flat(f'<div class="nc-login-pane nc-login-head"><h2>{escape(title)}</h2><p>{escape(subtitle)}</p></div>')


def hero_html(display_name: str, role_label: str) -> str:
    return _flat(f"""
    <div class="nc-hero">
      <div class="nc-hero-left">{LOGO_SVG}
        <div><h1>Product profitability</h1>
        <p>Sales volume alone is misleading. See which products and divisions actually earn profit, and where pricing,
        sourcing or range decisions are needed.</p></div>
      </div>
      <div class="nc-user"><div class="nc-avatar">{escape(initials(display_name))}</div>
        <div><b>{escape(display_name)}</b><span>{escape(role_label)}</span></div></div>
    </div>""")


def kpi_strip_html(k: dict) -> str:
    margin = max(0.0, min(1.0, float(k["GrossMargin"])))
    cells = [
        ("Sales", f"${k['Sales']:,.0f}", ""),
        ("Gross profit", f"${k['GrossProfit']:,.0f}", ""),
        ("Gross margin", f"{k['GrossMargin']:.1%}", f'<div class="nc-kpi-bar"><i style="--w:{margin:.1%}"></i></div>'),
        ("Profit per unit", f"${k['ProfitPerUnit']:.2f}", ""),
        ("Units sold", f"{k['Units']:,}", ""),
        ("Orders", f"{k['Orders']:,}", ""),
    ]
    inner = "".join(f'<div class="nc-kpi"><div class="nc-kpi-label">{l}</div><div class="nc-kpi-value">{v}</div>{extra}</div>'
                    for l, v, extra in cells)
    return f'<div class="nc-kpis">{inner}</div>'


def sidebar_brand_html() -> str:
    return _flat(f'<div class="nc-side-brand">{LOGO_SVG.replace("nc-logo", "")}<span>Nassau Candy</span></div>')


# ---------------------------------------------------------------------------- Plotly
def register_plotly_template() -> None:
    import plotly.graph_objects as go
    import plotly.io as pio

    axis = dict(gridcolor="#EEE8F5", linecolor=LINE, zeroline=False, ticks="", title=dict(font=dict(size=12, color=MUTED)))
    pio.templates["nassau"] = go.layout.Template(layout=dict(
        font=dict(family=f"{BODY_FONT}, system-ui, sans-serif", color=INK, size=13),
        title=dict(font=dict(family=f"{HEADING_FONT}, Georgia, serif", size=19, color=INK), x=0.01, xanchor="left"),
        colorway=COLORWAY,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=axis, yaxis=axis,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=12)),
        hoverlabel=dict(bgcolor=INK, font=dict(color="#fff", family=BODY_FONT), bordercolor=INK),
        margin=dict(l=48, r=24, t=64, b=48),
    ))
    pio.templates.default = "nassau"
