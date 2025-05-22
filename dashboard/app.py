"""Finance Decoder Dashboard — PDF‑styled Dash app (v3)
====================================================

🏷 **Key change in v3** – Filtering logic
---------------------------------------
* **No filters selected**  → plot *all* cities (unchanged).
* **Any filter widget used**
  * City dropdown picks ⇒ plot *only* those cities (unchanged).
  * State dropdown changed **without** picking a city ⇒ **show nothing** until the
    user explicitly chooses cities.  This honours the request: *“once the
    filtering functionality is used I want to only see the cities that are
    added with the filter.”*

Everything else (vertical sustainability/flexibility bar, styling) is
identical to v2.

Quick start
-----------
```bash
pip install dash plotly pandas
python app.py
```

---------------------------------------------------------------------------
Code
---------------------------------------------------------------------------
"""
from __future__ import annotations

import os
import pathlib
from typing import List

import dash
from dash import Input, Output, State, dcc, html
import pandas as pd
import plotly.express as px

# -------------------------------------------------------------------
# Locate CSV (env‑var → data/ → current folder)
# -------------------------------------------------------------------
ROOT = pathlib.Path(__file__).parent
CANDIDATES = [
    pathlib.Path(os.getenv("FIN_CSV_PATH", "___no_file___")),  # user‑specified
    ROOT / "data" / "financials_tidy.csv",                     # repo default
    ROOT / "financials_tidy.csv",                              # fall‑back
]
CSV_PATH = next((p for p in CANDIDATES if p.is_file()), None)
if CSV_PATH is None:
    raise FileNotFoundError(
        "Cannot locate financials_tidy.csv. Set FIN_CSV_PATH or place the file "
        "in ./data/ or alongside app.py."
    )

# -------------------------------------------------------------------
# Data & indicator meta
# -------------------------------------------------------------------
INDICATORS: List[str] = [
    "Net Financial Position",
    "Financial Assets-to-Liabilities",
    "Assets-to-Liabilities",
    "Net Debt-to-Total Revenues",
    "Interest-to-Total Revenues",
    "Net Book-to-Cost of TCA",
    "Govt Transfers-to-Total Revenues"
]

ARROW_META = {
    "Net Financial Position":          dict(bottom="Less sustainable", top="More sustainable", invert=False),
    "Financial Assets-to-Liabilities": dict(bottom="Less sustainable", top="More sustainable", invert=False),
    "Assets-to-Liabilities":           dict(bottom="Less sustainable", top="More sustainable", invert=False),
    "Net Debt-to-Total Revenues":      dict(bottom="More sustainable", top="Less sustainable", invert=True),
    "Interest-to-Total Revenues":      dict(bottom="More flexible",    top="Less flexible",    invert=True),
    "Net Book-to-Cost of TCA":         dict(bottom="More flexible",    top="Less flexible",    invert=True),
    "Govt Transfers-to-Total Revenues":dict(bottom="Less vulnerable",  top="More Vulnerable",  invert=False),
}

COLOR_RED = "#BF1E2E"   # undesirable end (bottom)
COLOR_GREEN = "#2AA876" # desirable end (top)

# Read tidy CSV
_df_raw = pd.read_csv(CSV_PATH)
df = _df_raw[_df_raw["variable"].isin(INDICATORS)].copy()

# -------------------------------------------------------------------
# Dash app
# -------------------------------------------------------------------
external_stylesheets = [
    "https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600&display=swap",
]
app = dash.Dash(
    __name__,
    external_stylesheets=external_stylesheets,
    title="Finance Decoder Dashboard",
)

app.layout = html.Div(
    [
        dcc.Store(id="filters-store"),
        html.H1("Finance Decoder Dashboard", className="main-title"),
        # -------------------- Filter bar ---------------------------
        html.Div(
            [
                dcc.Dropdown(
                    id="state-dd",
                    options=[{"label": s, "value": s} for s in sorted(df["state"].unique())],
                    multi=True,
                    placeholder="Filter by state(s)…",
                    className="state-dd",
                ),
                dcc.Dropdown(
                    id="city-dd",
                    options=[{"label": c, "value": c} for c in sorted(df["city"].unique())],
                    multi=True,
                    placeholder="Select city/cities…",
                    className="city-dd",
                ),
            ],
            className="filter-bar",
        ),
        # -------------------- Tabs -------------------------------
        dcc.Tabs(
            id="indicator-tabs",
            value=INDICATORS[0],
            children=[dcc.Tab(label=ind, value=ind) for ind in INDICATORS],
            className="indicator-tabs",
        ),
        html.Div(id="page-content"),
    ]
)

# -------------------------------------------------------------------
# Callbacks
# -------------------------------------------------------------------
@app.callback(Output("city-dd", "options"), Input("state-dd", "value"))
def update_city_options(states):
    """Re‑order cities so those in selected states appear first, but keep all."""
    all_cities = sorted(df["city"].unique())
    if not states:
        return [{"label": c, "value": c} for c in all_cities]
    top = sorted(df.loc[df["state"].isin(states), "city"].unique())
    ordered = top + [c for c in all_cities if c not in top]
    return [{"label": (c + " *" if c in top else c), "value": c} for c in ordered]


@app.callback(Output("filters-store", "data"), Input("state-dd", "value"), Input("city-dd", "value"))
def sync_filter_state(state_sel, city_sel):
    return {"states": state_sel or [], "cities": city_sel or []}


@app.callback(
    Output("page-content", "children"),
    Input("indicator-tabs", "value"),
    Input("filters-store", "data")
)
def render_page(indicator, filters):
    states = filters.get("states") if filters else []
    cities = filters.get("cities") if filters else []

    # ---------------- Filtering logic v3 ---------------------
    if not states and not cities:
        # No filters at all → show **all** cities
        city_subset = sorted(df["city"].unique())
    elif cities:
        # City filter in use → show those cities only
        city_subset = cities
    else:
        # States selected but no explicit cities → show nothing until city picked
        city_subset = []

    sub = df[(df["variable"] == indicator) & (df["city"].isin(city_subset))]

    if sub.empty:
        fig = px.line()
        fig.add_annotation(
            text="No data for selected filters", showarrow=False, x=0.5, y=0.5,
            xref="paper", yref="paper", font_size=20
        )
    else:
        fig = px.line(sub, x="year", y="value", color="city", markers=True)
        fig.update_layout(
            margin=dict(t=40),
            xaxis_title="Year",
            yaxis_title=indicator,
            legend_title_text="City",
        )

    # ------------ Vertical sustainability / flexibility bar ----------
    meta = ARROW_META[indicator]
    spectrum = html.Div(
        [
            html.Span(meta["top"], className="top-label"),
            html.Div(className="bar-vert"),
            html.Span(meta["bottom"], className="bottom-label"),
        ],
        className="spectrum-vert" + (" invert" if meta["invert"] else ""),
    )

    return html.Div(
        [
            html.Div(dcc.Graph(figure=fig, config={"displaylogo": False}), className="graph-wrapper"),
            html.Div(spectrum, className="arrow-wrapper"),
        ],
        className="metric-page",
    )


# -------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)

app = dash.Dash(__name__, suppress_callback_exceptions=True)
# ... all your callbacks ...
server = app.server    # ← THIS is what Gunicorn needs