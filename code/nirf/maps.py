"""
India choropleth map utilities for NIRF Analytics.

Provides GeoJSON loading, state name mapping, and Plotly choropleth
generation for state-level NIRF metrics.
"""

import json
import os
from functools import lru_cache

import pandas as pd
import plotly.express as px
import streamlit as st


# Canonical Indian state/UT names → GeoJSON feature names.
# The India GeoJSON uses these property names; we map DB values to them.
STATE_NAME_MAP = {
    "Andaman and Nicobar Islands": "Andaman & Nicobar Island",
    "Andhra Pradesh": "Andhra Pradesh",
    "Arunachal Pradesh": "Arunachal Pradesh",
    "Assam": "Assam",
    "Bihar": "Bihar",
    "Chandigarh": "Chandigarh",
    "Chhattisgarh": "Chhattisgarh",
    "Dadra and Nagar Haveli and Daman and Diu": "Dadara & Nagar Havelli",
    "Delhi": "NCT of Delhi",
    "Goa": "Goa",
    "Gujarat": "Gujarat",
    "Haryana": "Haryana",
    "Himachal Pradesh": "Himachal Pradesh",
    "Jammu and Kashmir": "Jammu & Kashmir",
    "Jharkhand": "Jharkhand",
    "Karnataka": "Karnataka",
    "Kerala": "Kerala",
    "Ladakh": "Ladakh",
    "Lakshadweep": "Lakshadweep",
    "Madhya Pradesh": "Madhya Pradesh",
    "Maharashtra": "Maharashtra",
    "Manipur": "Manipur",
    "Meghalaya": "Meghalaya",
    "Mizoram": "Mizoram",
    "Nagaland": "Nagaland",
    "Odisha": "Odisha",
    "Puducherry": "Puducherry",
    "Punjab": "Punjab",
    "Rajasthan": "Rajasthan",
    "Sikkim": "Sikkim",
    "Tamil Nadu": "Tamil Nadu",
    "Telangana": "Telangana",
    "Tripura": "Tripura",
    "Uttar Pradesh": "Uttar Pradesh",
    "Uttarakhand": "Uttarakhand",
    "West Bengal": "West Bengal",
}

_GEOJSON_URL = (
    "https://gist.githubusercontent.com/jbrobst/56c13bbbf9d97d187fea01ca62ea5112"
    "/raw/e388c4cae20aa53cb5090210a42ebb9b765c0a36/india_states.geojson"
)

_GEOJSON_CACHE_PATH = os.path.join(
    os.path.dirname(__file__), "india_states.geojson"
)


@lru_cache(maxsize=1)
def load_geojson():
    """Load India states GeoJSON, preferring a local cache."""
    if os.path.exists(_GEOJSON_CACHE_PATH):
        with open(_GEOJSON_CACHE_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)

    # Try downloading and caching
    try:
        import urllib.request

        with urllib.request.urlopen(_GEOJSON_URL, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        # Cache for future use
        try:
            with open(_GEOJSON_CACHE_PATH, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
        except OSError:
            pass
        return data
    except Exception:
        # Return a minimal empty FeatureCollection so the app doesn't crash
        return {"type": "FeatureCollection", "features": []}


def make_choropleth(
    frame: pd.DataFrame,
    value_col: str,
    title: str,
    colorscale: str = "YlGnBu",
    metric_label: str | None = None,
) -> object:
    """Build a Plotly choropleth figure for Indian states.

    Parameters
    ----------
    frame : pd.DataFrame
        Must contain a ``State`` column with canonical state names and
        a numeric column identified by *value_col*.
    value_col : str
        Column in *frame* to use as the choropleth colour value.
    title : str
        Figure title.
    colorscale : str
        Plotly colour scale name.
    metric_label : str or None
        Label for the colour bar.  Defaults to *value_col*.
    """
    geojson = load_geojson()
    if metric_label is None:
        metric_label = value_col.replace("_", " ").title()

    plot_frame = frame.copy()
    plot_frame["_geo_state"] = plot_frame["State"].map(STATE_NAME_MAP).fillna(
        plot_frame["State"]
    )

    fig = px.choropleth(
        plot_frame,
        geojson=geojson,
        featureidkey="properties.ST_NM",
        locations="_geo_state",
        color=value_col,
        color_continuous_scale=colorscale,
        hover_name="State",
        hover_data={value_col: True, "_geo_state": False},
        labels={value_col: metric_label},
        title=title,
    )
    fig.update_geos(
        fitbounds="locations",
        visible=False,
    )
    fig.update_layout(
        margin={"r": 0, "t": 50, "l": 0, "b": 0},
        height=550,
    )
    return fig


def show_map_attribution():
    """Display GeoJSON attribution in Streamlit."""
    st.caption(
        "India state boundaries: "
        "[india_states.geojson](https://gist.github.com/jbrobst/56c13bbbf9d97d187fea01ca62ea5112) "
        "by jbrobst (public domain)."
    )
