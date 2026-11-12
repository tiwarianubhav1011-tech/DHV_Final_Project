"""
NIRF Analytics AI Chatbot - Modern Streamlit Interface

Features:
- ChatGPT / Perplexity inspired minimal analytics interface
- Persistent multi-conversation history with New Chat & Clear Chat
- Welcome screen with clickable prompt suggestions
- 5-part organized response: Answer, Results Table, Interactive Chart, Generated SQL, Chart Code
- Interactive Plotly visualizations (Bar, Line, Area, Scatter, India Choropleth map)
- Dynamic axis controls, row limiting, and grouping
- CSV download & Python chart code export
- Contextual follow-up memory support
"""

import re
import uuid
from datetime import datetime

import pandas as pd
import streamlit as st

from nirf.maps import show_map_attribution
from nirf_chatbot.analytics_catalog import ANALYTICS_CATALOG
from nirf_chatbot.sql_executor import execute_sql
from nirf_chatbot.visualization import (
    CHART_TYPES,
    HOVER_FIELDS,
    build_plotly_figure,
    compute_bivariate_stats,
    infer_chart_spec,
    validate_chart_spec,
)


SUGGESTED_QUESTIONS = [
    "Top 10 institutions in Overall rankings",
    "Engineering rankings in 2025",
    "Compare IIT Bombay and IIT Delhi over the years",
    "Plot the ranking trend of IIT Madras from 2017 to 2025",
    "Which states have the most institutions in the top 100?",
    "How are NIRF scores and percentiles calculated across institutes?",
]

RANKING_CATEGORIES = [
    "Overall", "Engineering", "University", "College",
    "Management", "Pharmacy", "Medical", "Law",
    "Architecture", "Dental", "Research", "Innovation",
    "Agriculture", "Open University", "Skill University",
    "State Public University", "SDG Institutions",
]

_VISUALIZATION_MARKER = re.compile(
    r"(?im)^\s*Visualization:\s*(CHART|TEXT)\s*$"
)
_PYTHON_CODE_BLOCK = re.compile(
    r"```python\s*(.*?)```", flags=re.IGNORECASE | re.DOTALL
)


def inject_custom_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Main Container Padding */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 4rem;
        max-width: 950px;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #0f172a;
        border-right: 1px solid #1e293b;
    }
    section[data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    section[data-testid="stSidebar"] .stButton > button {
        background-color: #1e293b;
        color: #f8fafc !important;
        border: 1px solid #334155;
        border-radius: 8px;
        font-weight: 500;
        text-align: left;
        justify-content: flex-start;
        padding: 0.5rem 0.75rem;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background-color: #334155;
        border-color: #64748b;
    }

    /* Brand Header in Sidebar */
    .brand-container {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.5rem 0 1.25rem 0;
        border-bottom: 1px solid #1e293b;
        margin-bottom: 1.25rem;
    }
    .brand-badge {
        background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
        color: white !important;
        font-size: 1.25rem;
        font-weight: 700;
        width: 38px;
        height: 38px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 10px;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    }
    .brand-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #ffffff !important;
        letter-spacing: -0.01em;
        line-height: 1.2;
    }
    .brand-sub {
        font-size: 0.75rem;
        color: #94a3b8 !important;
    }

    /* Welcome Hero Card */
    .hero-card {
        background: radial-gradient(circle at top right, rgba(59, 130, 246, 0.08), transparent 70%),
                    linear-gradient(180deg, rgba(30, 41, 59, 0.4) 0%, rgba(15, 23, 42, 0.2) 100%);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 16px;
        padding: 2.25rem 2rem;
        text-align: center;
        margin: 1.5rem 0 2rem 0;
        backdrop-filter: blur(8px);
    }
    .hero-title {
        font-size: 1.85rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        margin-bottom: 0.6rem;
    }
    .hero-subtitle {
        font-size: 0.95rem;
        color: #64748b;
        max-width: 620px;
        margin: 0 auto;
        line-height: 1.55;
    }

    /* Suggestion Pills */
    .suggestion-header {
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b;
        margin-bottom: 0.75rem;
    }

    /* Message Bubbles */
    .stChatMessage {
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
        border: 1px solid rgba(148, 163, 184, 0.12);
    }

    /* Custom response tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.2);
        margin-top: 1rem;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 6px 14px;
        border-radius: 8px 8px 0 0;
        font-weight: 500;
        font-size: 0.85rem;
    }

    /* Cards in Sidebar */
    .info-box {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 0.85rem;
        margin-top: 1rem;
        font-size: 0.82rem;
    }

    /* Hide standard header & footer */
    #MainMenu, footer { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)


def parse_answer(answer: str) -> tuple[bool, str, str | None]:
    marker = _VISUALIZATION_MARKER.search(answer)
    wants_chart = bool(marker and marker.group(1).upper() == "CHART")
    answer_body = answer[marker.end() :] if marker else answer
    code_match = _PYTHON_CODE_BLOCK.search(answer_body)
    chart_code = (
        code_match.group(1).strip() if wants_chart and code_match else None
    )
    if code_match:
        answer_body = answer_body[: code_match.start()]
    answer_body = re.sub(
        r"(?m)^\s*##\s*(Answer|Chart code)\s*$", "", answer_body
    )
    return wants_chart, answer_body.strip(), chart_code


def results_frame(results: dict) -> pd.DataFrame:
    columns = results.get("columns") or None
    rows = results.get("rows") or []
    return pd.DataFrame(rows, columns=columns)


def render_results_chart(
    frame: pd.DataFrame,
    key_prefix: str,
    question: str = "",
) -> str | None:
    spec = validate_chart_spec(frame, infer_chart_spec(frame, question))
    numeric_columns = [
        column
        for column in frame.columns
        if pd.to_numeric(frame[column], errors="coerce").notna().any()
    ]
    if not numeric_columns:
        st.info("These results do not contain numeric values to chart.")
        return None

    chart_types = (
        CHART_TYPES
        if "State" in frame.columns
        else [chart for chart in CHART_TYPES if chart != "India map"]
    )
    controls = st.columns(4)
    with controls[0]:
        chart_type = st.selectbox(
            "Chart type",
            chart_types,
            index=chart_types.index(spec["chart_type"]) if spec["chart_type"] in chart_types else 0,
            key=f"{key_prefix}_chart_type",
        )
    x_options = ["State"] if chart_type == "India map" else list(frame.columns)
    y_options = (
        numeric_columns
        if chart_type == "India map"
        or chart_type != "Bar"
        or spec["orientation"] != "h"
        else list(frame.columns)
    )

    default_x = spec["x"] if spec["x"] in x_options else x_options[0]
    default_y = spec["y"] if spec["y"] in y_options else (y_options[0] if y_options else default_x)

    with controls[1]:
        x_axis = st.selectbox(
            "Value / X axis"
            if chart_type == "Bar" and spec["orientation"] == "h"
            else "Category / X axis",
            x_options,
            index=x_options.index(default_x),
            key=f"{key_prefix}_x_axis",
        )
    with controls[2]:
        y_axis = st.selectbox(
            "Category / Y axis"
            if chart_type == "Bar" and spec["orientation"] == "h"
            else "Value / Y axis",
            y_options,
            index=y_options.index(default_y) if default_y in y_options else 0,
            key=f"{key_prefix}_y_axis",
        )
    group_options = ["None"] + [
        column
        for column in frame.columns
        if column not in numeric_columns and column not in {x_axis, y_axis}
    ]
    default_group = spec.get("color")
    if default_group not in group_options:
        default_group = "None"
    with controls[3]:
        group_by = st.selectbox(
            "Color / group by",
            group_options,
            index=group_options.index(default_group),
            key=f"{key_prefix}_color_group",
        )

    map_frame = frame
    if chart_type == "India map" and "Year" in frame.columns:
        years = sorted(
            pd.to_numeric(frame["Year"], errors="coerce").dropna().astype(int).unique()
        )
        if len(years) > 1:
            selected_year = st.selectbox(
                "Map year",
                years,
                index=len(years) - 1,
                key=f"{key_prefix}_map_year",
            )
            map_frame = frame[
                pd.to_numeric(frame["Year"], errors="coerce").eq(selected_year)
            ]

    orientation = "v"
    if chart_type == "Bar":
        x_is_numeric = x_axis in numeric_columns
        y_is_numeric = y_axis in numeric_columns
        if x_is_numeric and not y_is_numeric:
            orientation = "h"
        elif not x_is_numeric and y_is_numeric:
            orientation = "v"
        else:
            orientation = spec["orientation"]
    color = None if group_by == "None" else group_by
    spec = validate_chart_spec(
        map_frame,
        {
            **spec,
            "chart_type": chart_type,
            "x": x_axis,
            "y": y_axis,
            "color": color,
            "orientation": orientation,
        },
    )

    columns = list(dict.fromkeys(
        [
            x_axis,
            y_axis,
            *([color] if color else []),
            *[column for column in HOVER_FIELDS if column in map_frame.columns],
        ]
    ))
    chart_data = map_frame[columns].copy()
    for column in columns:
        if column in numeric_columns or column in {"Year", "Score", "Rank_Numeric"}:
            chart_data[column] = pd.to_numeric(chart_data[column], errors="coerce")
    chart_data = chart_data.dropna(subset=[x_axis, y_axis])
    if chart_type == "Bar" and orientation == "h" and x_axis in numeric_columns:
        chart_data = chart_data.sort_values(x_axis, ascending=False)
    elif chart_type in {"Line", "Area"} and x_axis == "Year":
        chart_data = chart_data.sort_values(x_axis)
    if chart_data.empty:
        st.info("There are no numeric values available for this chart.")
        return None

    if len(chart_data) > 1:
        default_limit = (
            len(chart_data)
            if chart_type in {"India map", "Line", "Area", "Scatter"}
            else min(25, len(chart_data))
        )
        row_limit = st.slider(
            "Rows to display",
            min_value=1,
            max_value=len(chart_data),
            value=default_limit,
            key=f"{key_prefix}_row_limit",
        )
        chart_data = chart_data.head(row_limit)

    if chart_type == "Scatter":
        show_trendline = st.checkbox(
            "Show OLS Trend Line",
            value=bool(spec.get("trendline", True)),
            key=f"{key_prefix}_trendline",
        )
        spec["trendline"] = show_trendline
        biv = compute_bivariate_stats(chart_data, x_axis, y_axis)
        if biv:
            mcols = st.columns(4)
            mcols[0].metric("Pearson r", f"{biv['r']:+.4f}")
            mcols[1].metric("R² (Variance Explained)", f"{biv['r2'] * 100:.1f}%")
            mcols[2].metric("OLS Slope", f"{biv['slope']:+.4f}")
            mcols[3].metric("Institutions (N)", f"{biv['n']:,}")

    figure, plot_code = build_plotly_figure(chart_data, spec)
    figure.update_layout(xaxis_title=x_axis, yaxis_title=y_axis)
    st.plotly_chart(
        figure,
        use_container_width=True,
        theme="streamlit",
        key=f"{key_prefix}_chart",
    )
    if chart_type == "India map":
        show_map_attribution()
    return plot_code


def _render_turn(turn: dict, index: int) -> None:
    with st.chat_message("user", avatar="👤"):
        st.markdown(f"**{turn['question']}**")

    response = turn["response"]
    with st.chat_message("assistant", avatar="🎓"):
        if response.get("answer_warning"):
            st.warning(response["answer_warning"])
        wants_chart, answer_text, _ = parse_answer(response["answer"])
        wants_chart = (
            wants_chart
            or response.get("is_chart_request", False)
        )
        frame = results_frame(response.get("results", {}))
        if not answer_text:
            answer_text = (
                f"Found **{len(frame)}** matching records. See the Results and "
                "Chart tabs for the returned data."
                if not frame.empty
                else "No matching records were found."
            )
        st.markdown(answer_text)
        tabs = st.tabs(["📊 Visualization", "📋 Results Table", "🔍 Generated SQL", "💻 Chart Code"])
        plot_code = None

        with tabs[0]:
            if response.get("is_general_knowledge"):
                st.info("💡 General NIRF analytical & framework response. See the **Results Table** tab for overall percentile benchmarks and score distribution statistics.")
            elif not wants_chart:
                st.info("💡 Ask for a graph, chart, plot, or ranking trend to visualize these results.")
            elif frame.empty:
                st.info("No matching database rows were returned to plot.")
            else:
                plot_code = render_results_chart(
                    frame,
                    f"chat_{index}",
                    turn["question"],
                )

        with tabs[1]:
            if frame.empty:
                st.info("No matching database rows were returned.")
            else:
                st.dataframe(
                    frame,
                    use_container_width=True,
                    hide_index=True,
                    height=min(380, len(frame) * 35 + 38),
                )
                st.download_button(
                    "📥 Download Results (CSV)",
                    data=frame.to_csv(index=False),
                    file_name="nirf_results.csv",
                    mime="text/csv",
                    key=f"chat_csv_{index}",
                )

        with tabs[2]:
            st.code(response.get("generated_sql", "-- No SQL query generated"), language="sql")

        with tabs[3]:
            if plot_code:
                st.code(plot_code, language="python")
                st.download_button(
                    "📥 Download Chart Code (.py)",
                    data=plot_code,
                    file_name="nirf_chart.py",
                    mime="text/x-python",
                    key=f"chat_code_{index}",
                )
                st.caption("Plotly script used to generate this visualization.")
            else:
                st.info("No plotting code is active for this response.")


def init_session():
    if "conversations" not in st.session_state:
        st.session_state.conversations = {}
    if "current_convo_id" not in st.session_state:
        cid = str(uuid.uuid4())[:8]
        st.session_state.current_convo_id = cid
        st.session_state.conversations[cid] = {
            "title": "New Chat",
            "history": [],
            "created_at": datetime.now(),
        }
    if "user_query_input" not in st.session_state:
        st.session_state.user_query_input = ""


def get_current_history() -> list[dict]:
    cid = st.session_state.current_convo_id
    if cid not in st.session_state.conversations:
        st.session_state.conversations[cid] = {
            "title": "New Chat",
            "history": [],
            "created_at": datetime.now(),
        }
    return st.session_state.conversations[cid]["history"]


def render_sidebar():
    with st.sidebar:
        st.markdown("""
        <div class="brand-container">
            <div class="brand-badge">NIRF</div>
            <div>
                <div class="brand-title">NIRF Analytics</div>
                <div class="brand-sub">AI Research & Ranking Engine</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("➕ New Chat", use_container_width=True):
            cid = str(uuid.uuid4())[:8]
            st.session_state.current_convo_id = cid
            st.session_state.conversations[cid] = {
                "title": "New Chat",
                "history": [],
                "created_at": datetime.now(),
            }
            st.rerun()

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        st.markdown("**Conversations**")

        for cid, convo in list(st.session_state.conversations.items())[::-1]:
            is_active = cid == st.session_state.current_convo_id
            title_disp = ("▸ " if is_active else "  ") + convo["title"]
            if len(title_disp) > 28:
                title_disp = title_disp[:26] + "…"
            if st.button(title_disp, key=f"convo_btn_{cid}", use_container_width=True):
                st.session_state.current_convo_id = cid
                st.rerun()

        st.markdown("<hr style='border-color: #1e293b; margin: 1.5rem 0;'>", unsafe_allow_html=True)

        history = get_current_history()
        if history:
            if st.button("🗑️ Clear Current Chat", use_container_width=True):
                history.clear()
                st.session_state.conversations[st.session_state.current_convo_id]["title"] = "New Chat"
                st.rerun()

        with st.expander("📊 40 Analytical Questions"):
            domain_names = list(ANALYTICS_CATALOG.keys())
            selected_domain = st.selectbox(
                "Analysis Domain",
                domain_names,
                key="sidebar_domain_select",
            )
            for idx, q_text in enumerate(ANALYTICS_CATALOG[selected_domain]):
                if st.button(
                    f"{idx + 1}. {q_text}",
                    key=f"sb_q_{selected_domain[:2]}_{idx}",
                    use_container_width=True,
                ):
                    process_and_append_question(q_text)
                    st.rerun()

        with st.expander("📚 Dataset Information"):
            st.markdown("""
            **Coverage:** 2017 – 2025 (6,966 records)  
            **Database:** PostgreSQL `public."NIRF"`  
            **Ranking Categories (17):**
            - Overall, Engineering, University, College
            - Management, Pharmacy, Medical, Law
            - Architecture, Dental, Research, Innovation
            - Agriculture, Open University, Skill University
            - State Public University, SDG Institutions
            **Parameters:** TLR, RPC, GO, OI, Perception
            """)

        with st.expander("ℹ️ About & Security"):
            st.markdown("""
            - **Model:** Sarvam AI (`sarvam-105b`)
            - **Security:** Read-Only PostgreSQL transactions, query timeout limit, strict SQL AST validation.
            - **Visualizations:** Plotly Express & India GeoJSON state maps.
            """)


BIVARIATE_VARIABLES = {
    "RPC": "Research & Professional Practice (RPC)",
    "TLR": "Teaching, Learning & Resources (TLR)",
    "GO": "Graduation Outcomes (GO)",
    "OI": "Outreach & Inclusivity (OI)",
    "Perception": "Peer Perception (PR)",
    "Score": "Overall NIRF Score",
    "Rank_Numeric": "Numeric Rank (1 = Best)",
}


@st.cache_data(ttl=300, show_spinner=False)
def _load_bivariate_slice(category: str, year_choice: str) -> pd.DataFrame:
    where_clauses = ['"Score" IS NOT NULL']
    if category != "All Categories":
        safe_cat = category.replace("'", "''")
        where_clauses.append(f"\"Category\" = '{safe_cat}'")
    if year_choice != "All Years (2017–2025)":
        where_clauses.append(f'"Year" = {int(year_choice)}')
    where_sql = " AND ".join(where_clauses)
    sql = f"""
        SELECT "Institution_ID", "Institution_Name", "Year", "Category",
               "State", "City", "Score", "Rank_Numeric",
               "TLR", "RPC", "GO", "OI", "Perception"
        FROM public."NIRF"
        WHERE {where_sql}
        ORDER BY "Rank_Numeric" ASC NULLS LAST
        LIMIT 500
    """
    res = execute_sql(sql)
    return results_frame(res)


def render_bivariate_explorer() -> None:
    with st.expander("🔬 Select-Two-Variables Bivariate & Correlation Explorer", expanded=False):
        st.caption(
            "Select any two numerical NIRF attributes to generate an interactive scatter plot, "
            "Pearson correlation coefficient (r), R², and optional OLS trend line."
        )
        c1, c2, c3, c4 = st.columns(4)
        var_keys = list(BIVARIATE_VARIABLES.keys())
        with c1:
            x_var = st.selectbox(
                "X Variable",
                var_keys,
                index=var_keys.index("RPC"),
                format_func=lambda k: f"{k} — {BIVARIATE_VARIABLES[k]}",
                key="biv_x_var",
            )
        with c2:
            y_var = st.selectbox(
                "Y Variable",
                var_keys,
                index=var_keys.index("Score"),
                format_func=lambda k: f"{k} — {BIVARIATE_VARIABLES[k]}",
                key="biv_y_var",
            )
        with c3:
            biv_cat = st.selectbox(
                "Category",
                ["Overall", *[c for c in RANKING_CATEGORIES if c != "Overall"], "All Categories"],
                index=0,
                key="biv_cat",
            )
        with c4:
            biv_year = st.selectbox(
                "Year",
                [str(y) for y in range(2025, 2016, -1)] + ["All Years (2017–2025)"],
                index=0,
                key="biv_year",
            )

        opt1, opt2 = st.columns([1, 2])
        with opt1:
            show_ols = st.checkbox("Show OLS Trend Line", value=True, key="biv_show_ols")
        with opt2:
            color_by = st.selectbox(
                "Color points by",
                ["None", "State", "Category", "Year"],
                index=0,
                key="biv_color_by",
            )

        if x_var == y_var:
            st.warning("Please select two different numerical attributes for X and Y.")
            return

        try:
            df = _load_bivariate_slice(biv_cat, biv_year)
        except Exception as exc:
            st.error(f"Could not load bivariate data: {exc}")
            return

        if df.empty:
            st.info("No records found for that Category / Year combination.")
            return

        biv_stats = compute_bivariate_stats(df, x_var, y_var)
        if biv_stats:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Pearson r", f"{biv_stats['r']:+.4f}")
            m2.metric("R² (Explained Variance)", f"{biv_stats['r2'] * 100:.1f}%")
            m3.metric("OLS Equation", f"{y_var} = {biv_stats['slope']:+.2f}·{x_var} {biv_stats['intercept']:+.2f}")
            m4.metric("Sample Size (N)", f"{biv_stats['n']:,}")

        spec = {
            "chart_type": "Scatter",
            "x": x_var,
            "y": y_var,
            "color": None if color_by == "None" else color_by,
            "orientation": "v",
            "title": f"{BIVARIATE_VARIABLES[y_var]} vs {BIVARIATE_VARIABLES[x_var]} ({biv_cat}, {biv_year})",
            "hover_name": "Institution_Name",
            "trendline": show_ols,
        }
        fig, _ = build_plotly_figure(df, spec)
        fig.update_layout(
            xaxis_title=BIVARIATE_VARIABLES[x_var],
            yaxis_title=BIVARIATE_VARIABLES[y_var],
        )
        st.plotly_chart(fig, use_container_width=True, theme="streamlit", key="biv_explorer_plot")


def render_chat_page(
    title: str = "NIRF Analytics Chatbot",
    subtitle: str = "Ask natural-language questions about India's National Institutional Ranking Framework (2017–2025).",
) -> None:
    inject_custom_css()
    init_session()
    render_sidebar()

    history = get_current_history()

    if st.session_state.get("last_error"):
        st.error(st.session_state.pop("last_error"))

    render_bivariate_explorer()

    if not history:
        st.markdown(f"""
        <div class="hero-card">
            <div class="hero-title">🎓 {title}</div>
            <div class="hero-subtitle">{subtitle}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="suggestion-header">Quick Start Questions</div>', unsafe_allow_html=True)
        cols = st.columns(2)
        for i, q in enumerate(SUGGESTED_QUESTIONS):
            with cols[i % 2]:
                if st.button(f"💬 {q}", key=f"sugg_{i}", use_container_width=True):
                    process_and_append_question(q)
                    st.rerun()

        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
        st.markdown('<div class="suggestion-header">📊 40-Question Research & Analytics Suite (8 Domains)</div>', unsafe_allow_html=True)
        domain_tabs = st.tabs([d.split(". ", 1)[1] for d in ANALYTICS_CATALOG.keys()])
        for d_idx, (domain_title, questions) in enumerate(ANALYTICS_CATALOG.items()):
            with domain_tabs[d_idx]:
                st.caption(f"**{domain_title}** — Click any question below to execute its SQL analysis and visualization:")
                q_cols = st.columns(2)
                for q_idx, q_text in enumerate(questions):
                    with q_cols[q_idx % 2]:
                        if st.button(
                            f"▶️ {q_idx + 1}. {q_text}",
                            key=f"hero_q_{d_idx}_{q_idx}",
                            use_container_width=True,
                        ):
                            process_and_append_question(q_text)
                            st.rerun()
    else:
        for index, turn in enumerate(history):
            _render_turn(turn, index)

    # Chat input
    question = st.chat_input("Ask about rankings, scores, colleges, states, or trends…")
    if question and question.strip():
        process_and_append_question(question.strip())
        st.rerun()


def process_and_append_question(question: str):
    history = get_current_history()
    try:
        with st.spinner("Analyzing question & querying PostgreSQL database…"):
            from nirf_chatbot.chat_service import process_question
            response = process_question(question, history=history)

        history.append({"question": question, "response": response})

        # Update conversation title from first question
        cid = st.session_state.current_convo_id
        if len(history) == 1:
            title = question
            if len(title) > 30:
                title = title[:28] + "…"
            st.session_state.conversations[cid]["title"] = title

    except Exception as exc:
        st.session_state["last_error"] = f"⚠️ {exc}"


def main():
    st.set_page_config(
        page_title="NIRF Analytics Chatbot",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    render_chat_page()


if __name__ == "__main__":
    main()

