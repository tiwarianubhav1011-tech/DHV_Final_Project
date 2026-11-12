import re
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlglot
from sqlglot import exp
from nirf.maps import STATE_NAME_MAP, load_geojson, make_choropleth


_CHART_INTENT = re.compile(
    r"\b(?:graphs?|charts?|plot|plots|visuali[sz](?:e|ation)|draw|compare|comparison|"
    r"trends?|maps?|choropleth|vs|versus|distribution|spread|correlat(?:e|ion)|"
    r"relat(?:e|ed|ionship)|associat(?:ed|ion)|variability|dispersed|quartiles?|"
    r"mobility|movements?|volatility|outliers?)\b"
    r"|\bover\s+(?:time|the\s+years|the\s+nine\s+years)\b"
    r"|\bfrom\s+20\d{2}\s+to\s+20\d{2}\b",
    re.IGNORECASE,
)
_RANK_WORD = re.compile(r"\brank(?:s|ing|ings|ed)?\b", re.IGNORECASE)
_BIVARIATE_WORD = re.compile(
    r"\b(?:correlat(?:e|ed|ion)|relat(?:e|ed|ionship)|associat(?:ed|ion)|scatter|vs\.?|versus)\b",
    re.IGNORECASE,
)

DERIVED_INSTITUTION_METRICS = (
    "rank_improvement",
    "rank_decline",
    "places_gained",
    "rank_change",
    "abs_movement",
    "curr_rank",
    "prev_rank",
    "rpc_minus_tlr",
    "research_vs_teaching_gap",
    "tlr_minus_perception",
    "overall_score_gain",
    "score_gain",
    "score_change",
    "abs_score_change",
    "parameter_gap",
    "rpc_over_overall_gap",
    "best_parameter_score",
    "rank_volatility_stddev",
    "rank_span",
)


def is_chart_request(question: str) -> bool:
    return bool(_CHART_INTENT.search(question))


def ensure_chart_columns(query: str, question: str) -> str:
    if not is_chart_request(question):
        return query

    try:
        statement = sqlglot.parse_one(query, read="postgres")
    except sqlglot.errors.ParseError:
        return query
    if not isinstance(statement, exp.Select):
        return query
    if statement.args.get("group") or statement.args.get("distinct"):
        return query
    if statement.find(exp.AggFunc):
        return query
    if statement.args.get("joins") or statement.args.get("with"):
        return query
    if len(list(statement.find_all(exp.Select))) > 1:
        return query

    projections = statement.expressions
    if any(isinstance(item, exp.Star) for item in projections):
        return query

    selected_columns = {
        item.name.casefold()
        for item in projections
        if isinstance(item, exp.Column)
    }
    required_columns = ["Institution_Name", "Score", "Rank_Numeric"]
    for column in required_columns:
        if column.casefold() not in selected_columns:
            projections.append(exp.column(column, quoted=True))

    return statement.sql(dialect="postgres")


CHART_TYPES = ["Bar", "Line", "Area", "Scatter", "India map"]
STATE_TO_GEOJSON = STATE_NAME_MAP
HOVER_FIELDS = [
    "Institution_Name",
    "Year",
    "Category",
    "Score",
    "Rank_Numeric",
    "State",
    "City",
    "TLR",
    "RPC",
    "GO",
    "OI",
    "Perception",
]


_load_india_geojson = load_geojson


def _india_state_map(
    frame: pd.DataFrame, spec: dict
) -> tuple[object, str]:
    metric = spec["y"]
    title = spec.get("title", f"{metric.replace('_', ' ').title()} by State")
    metric_label = spec.get("metric_label", metric.replace("_", " ").title())
    figure = make_choropleth(
        frame,
        metric,
        title,
        colorscale="YlGnBu",
        metric_label=metric_label,
    )
    code = (
        "from nirf.maps import make_choropleth\n\n"
        "fig = make_choropleth(\n"
        "    chart_data,\n"
        f"    value_col={metric!r},\n"
        f"    title={title!r},\n"
        "    colorscale='YlGnBu',\n"
        f"    metric_label={metric_label!r},\n"
        ")\n"
    )
    return figure, code


def _numeric_columns(frame: pd.DataFrame) -> list[str]:
    return [
        column
        for column in frame.columns
        if pd.to_numeric(frame[column], errors="coerce").notna().any()
    ]


def _detect_bivariate_pair(columns: list[str], numeric: list[str], question: str) -> tuple[str, str] | None:
    """If the question asks about the relationship/correlation between two
    numeric columns present in `frame`, return `(x_col, y_col)`."""
    if not _BIVARIATE_WORD.search(question) or len(numeric) < 2:
        return None
    q = question.casefold()
    candidates = []
    aliases = [
        ("TLR", ("tlr", "teaching")),
        ("RPC", ("rpc", "research")),
        ("GO", ("go", "graduation")),
        ("OI", ("oi", "outreach", "inclusivity")),
        ("Perception", ("perception", "pr")),
        ("Score", ("overall score", "overall scores", "score", "scores")),
        ("Rank_Numeric", ("rank", "ranking")),
    ]
    for col, words in aliases:
        if col in numeric and any(re.search(rf"\b{re.escape(w)}\b", q) for w in words):
            candidates.append(col)
    if len(candidates) >= 2:
        return candidates[0], candidates[1]
    return None


def infer_chart_spec(frame: pd.DataFrame, question: str = "") -> dict:
    columns = list(frame.columns)
    numeric = _numeric_columns(frame)
    categories = [
        column for column in ("Category", "Category_Group") if column in columns
    ]
    color = categories[0] if categories and frame[categories[0]].nunique() > 1 else None
    question_mentions_rank = bool(_RANK_WORD.search(question))

    # 1. Bivariate scatter plot when the question asks how two numeric variables relate
    biv_pair = _detect_bivariate_pair(columns, numeric, question)
    if biv_pair and ("Year" not in columns or pd.to_numeric(frame["Year"], errors="coerce").nunique() <= 1):
        x_col, y_col = biv_pair
        return {
            "chart_type": "Scatter",
            "x": x_col,
            "y": y_col,
            "color": "State" if "State" in columns and frame["State"].nunique() <= 12 else color,
            "orientation": "v",
            "title": f"{y_col} vs {x_col}",
            "markers": True,
            "hover_name": "Institution_Name" if "Institution_Name" in columns else None,
            "trendline": True,
        }

    # 2. Institution-level results
    if "Institution_Name" in columns:
        derived_col = next(
            (
                c for c in DERIVED_INSTITUTION_METRICS
                if c in numeric
            ),
            next(
                (c for c in columns if c in numeric and c.startswith("years_in_top_")),
                None,
            ),
        )
        param_col = next(
            (
                p for p in ("Perception", "TLR", "RPC", "GO", "OI")
                if p in numeric and p.casefold() in question.casefold()
            ),
            None,
        )
        measure = (
            derived_col
            or param_col
            or (
                "Rank_Numeric"
                if question_mentions_rank and "Rank_Numeric" in numeric and "score" not in question.casefold()
                else "Score"
                if "Score" in numeric
                else "avg_score"
                if "avg_score" in numeric
                else "Rank_Numeric"
                if "Rank_Numeric" in numeric
                else (numeric[0] if numeric else None)
            )
        )
        if measure:
            years = (
                pd.to_numeric(frame["Year"], errors="coerce").nunique()
                if "Year" in columns
                else 1
            )
            if years > 1 and "Year" in columns and not derived_col:
                return {
                    "chart_type": "Line",
                    "x": "Year",
                    "y": measure,
                    "color": "Institution_Name",
                    "orientation": "v",
                    "title": f"{measure} by institution over time",
                    "markers": True,
                }
            bar_measure = (
                derived_col
                or param_col
                or ("Score" if "Score" in numeric else measure)
            )
            group_col = (
                "State"
                if "State" in columns and 1 < frame["State"].nunique() <= 4 and "compare" in question.casefold()
                else color
            )
            return {
                "chart_type": "Bar",
                "x": bar_measure,
                "y": "Institution_Name",
                "color": group_col,
                "orientation": "h",
                "title": f"{bar_measure.replace('_', ' ').title()} by Institution",
                "markers": False,
            }

    # 3. Multi-year aggregate time series (Year present, no Institution_Name)
    if "Year" in columns and pd.to_numeric(frame["Year"], errors="coerce").nunique() > 1:
        non_year_numeric = [c for c in numeric if c not in {"Year", "to_year", "from_year", "prev_year", "curr_year"}]
        priority_order = (
            "rpc_score_correlation",
            "std_dev" if ("dispers" in question.casefold() or "spread" in question.casefold() or "variab" in question.casefold()) else None,
            "iqr_score" if ("interquartile" in question.casefold() or "iqr" in question.casefold()) else None,
            "median_score" if "median" in question.casefold() else None,
            "pct_same_band",
            "moved_up",
            "avg_score",
            "median_score",
            "std_dev",
        )
        priority_hit = next((c for c in priority_order if c and c in non_year_numeric), None)
        preferred_metrics = [
            c for c in non_year_numeric
            if not c.endswith("_count") and c not in {"institutions", "institutions_evaluated", "scored_institutions", "returning_institutions", "total_returning"}
        ]
        metric = priority_hit or (preferred_metrics or non_year_numeric or [None])[0]
        if metric:
            state_group = "State" if "State" in columns and frame["State"].nunique() > 1 else color
            return {
                "chart_type": "Line",
                "x": "Year",
                "y": metric,
                "color": state_group,
                "orientation": "v",
                "title": f"{metric.replace('_', ' ').title()} over time",
                "markers": True,
            }

    # 4. State-level aggregate table
    if "State" in columns and "Institution_Name" not in columns:
        non_year = [c for c in numeric if c not in {"Year"} and not c.startswith("count_2017")]
        preferred = next(
            (c for c in ("net_gain", "newly_appearing_institutions", "institution_count", "avg_score", "median_score", "best_rank") if c in non_year),
            non_year[0] if non_year else None,
        )
        if preferred:
            metric_label = preferred.replace("_", " ").title()
            return {
                "chart_type": "India map",
                "x": "State",
                "y": preferred,
                "color": None,
                "orientation": "v",
                "title": f"{metric_label} by State",
                "metric_label": metric_label,
                "markers": False,
            }

    # 5. Category / Parameter / Band / Quartile breakdown tables
    if numeric:
        non_numeric = [c for c in columns if c not in numeric]
        category_col = non_numeric[0] if non_numeric else None
        preferred_val = next(
            (
                c for c in (
                    "correlation_r", "correlation_with_score", "std_dev",
                    "pct_of_ranked_institutions", "institution_count",
                    "total_records", "avg_score", "median_score", "iqr",
                )
                if c in numeric
            ),
            next((c for c in numeric if c != "Year"), numeric[0]),
        )
        if category_col:
            return {
                "chart_type": "Bar",
                "x": category_col,
                "y": preferred_val,
                "color": color if color != category_col else None,
                "orientation": "v",
                "title": f"{preferred_val.replace('_', ' ').title()} by {category_col.replace('_', ' ').title()}",
                "markers": False,
            }
        return {
            "chart_type": "Bar",
            "x": columns[0],
            "y": preferred_val,
            "color": None,
            "orientation": "v",
            "title": preferred_val.replace("_", " ").title(),
            "markers": False,
        }

    return {
        "chart_type": "Bar",
        "x": columns[0] if columns else "",
        "y": columns[0] if columns else "",
        "color": None,
        "orientation": "v",
        "title": "Query results",
        "markers": False,
    }


def validate_chart_spec(frame: pd.DataFrame, spec: dict) -> dict:
    columns = set(frame.columns)
    valid = (
        spec.get("chart_type") in CHART_TYPES
        and (
            spec.get("chart_type") != "India map"
            or "State" in columns
        )
        and spec.get("x") in columns
        and spec.get("y") in columns
        and spec.get("orientation") in {"h", "v"}
        and (spec.get("color") is None or spec.get("color") in columns)
    )
    return spec if valid else infer_chart_spec(frame)


def compute_bivariate_stats(frame: pd.DataFrame, x_col: str, y_col: str) -> dict | None:
    """Compute Pearson r, R^2, OLS slope/intercept, and sample size N for two numeric columns."""
    if x_col not in frame.columns or y_col not in frame.columns or x_col == y_col:
        return None
    x = pd.to_numeric(frame[x_col], errors="coerce")
    y = pd.to_numeric(frame[y_col], errors="coerce")
    valid = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(valid) < 3 or valid["x"].nunique() < 2 or valid["y"].nunique() < 2:
        return None
    r = float(valid["x"].corr(valid["y"]))
    if np.isnan(r):
        return None
    slope, intercept = np.polyfit(valid["x"].to_numpy(), valid["y"].to_numpy(), 1)
    return {
        "n": int(len(valid)),
        "r": round(r, 4),
        "r2": round(r * r, 4),
        "slope": round(float(slope), 4),
        "intercept": round(float(intercept), 4),
        "x_min": float(valid["x"].min()),
        "x_max": float(valid["x"].max()),
    }


def build_plotly_figure(frame: pd.DataFrame, spec: dict) -> tuple[object, str]:
    spec = validate_chart_spec(frame, spec)
    chart_type = spec["chart_type"]
    x_axis = spec["x"]
    y_axis = spec["y"]
    color = spec.get("color")
    orientation = spec.get("orientation", "v")
    title = spec.get("title", "Query results")
    show_trendline = bool(spec.get("trendline", False))

    if chart_type == "India map":
        return _india_state_map(frame, spec)

    hover_fields = [
        column
        for column in HOVER_FIELDS
        if column in frame.columns and column not in {x_axis, y_axis, color}
    ]
    included = list(dict.fromkeys([x_axis, y_axis, *([color] if color else []), *hover_fields]))
    chart_data = frame[included].copy()

    numeric_cols = _numeric_columns(frame)
    for column in included:
        if column in numeric_cols:
            chart_data[column] = pd.to_numeric(chart_data[column], errors="coerce")
    chart_data = chart_data.dropna(subset=[x_axis, y_axis])

    if chart_type == "Bar" and orientation == "h":
        sort_column = x_axis
        chart_data = chart_data.sort_values(sort_column, ascending=False)
    elif chart_type in {"Line", "Area"} and x_axis == "Year":
        chart_data = chart_data.sort_values(x_axis)

    kwargs = {
        "x": x_axis,
        "y": y_axis,
        "color": color,
        "title": title,
        "hover_data": hover_fields,
    }
    if chart_type == "Bar":
        kwargs["orientation"] = orientation
        figure = px.bar(chart_data, **kwargs)
        figure.update_layout(barmode="group")
        if orientation == "h" and y_axis == "Institution_Name":
            figure.update_yaxes(autorange="reversed")
    elif chart_type == "Line":
        figure = px.line(chart_data, markers=True, **kwargs)
        if y_axis == "Rank_Numeric":
            figure.update_yaxes(autorange="reversed")
    elif chart_type == "Area":
        figure = px.area(chart_data, **kwargs)
    else:
        hover_name = (
            spec.get("hover_name")
            if spec.get("hover_name") in chart_data.columns
            else ("Institution_Name" if "Institution_Name" in chart_data.columns else None)
        )
        figure = px.scatter(
            chart_data,
            hover_name=hover_name,
            **kwargs,
        )
        if show_trendline:
            biv = compute_bivariate_stats(chart_data, x_axis, y_axis)
            if biv:
                xs = np.array([biv["x_min"], biv["x_max"]])
                ys = biv["slope"] * xs + biv["intercept"]
                figure.add_trace(
                    go.Scatter(
                        x=xs,
                        y=ys,
                        mode="lines",
                        name=f"OLS Trend (r = {biv['r']:.3f})",
                        line={"dash": "dash", "width": 2},
                    )
                )

    code = (
        "import plotly.express as px\n\n"
        "# chart_data contains the selected result rows after sorting and row limiting.\n"
        f"fig = px.{chart_type.casefold()}(chart_data, x={x_axis!r}, y={y_axis!r}, "
        f"color={color!r}, title={title!r}, hover_data={hover_fields!r}"
    )
    if chart_type == "Bar":
        code += f", orientation={orientation!r})\nfig.update_layout(barmode='group')"
        if orientation == "h" and y_axis == "Institution_Name":
            code += "\nfig.update_yaxes(autorange='reversed')"
    elif chart_type == "Line":
        code += ", markers=True)"
        if y_axis == "Rank_Numeric":
            code += "\nfig.update_yaxes(autorange='reversed')"
    elif chart_type == "Scatter":
        hover_name = (
            spec.get("hover_name")
            if spec.get("hover_name") in chart_data.columns
            else ("Institution_Name" if "Institution_Name" in chart_data.columns else None)
        )
        if hover_name:
            code += f", hover_name={hover_name!r})"
        else:
            code += ")"
    else:
        code += ")"
    return figure, code
