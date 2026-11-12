"""
Answer generation.

Produces 100% grounded natural-language summaries directly from the SQL
result rows:
- Bivariate correlation queries: computes exact Pearson r, R^2, OLS slope,
  and sample size N from the returned rows, plus top institution examples.
- Institution-level queries (single-year, multi-year trends, rank mobility,
  parameter gaps, outliers, 5-parameter comparisons): preserves the exact
  SQL row order and includes all derived analytical columns.
- Aggregate / statistical tables (by year, state, category, parameter,
  quartile, rank band): formats a structured summary highlighting the key
  findings and listing the returned rows.
"""

import json
import logging
import re
from decimal import Decimal

import pandas as pd
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from nirf_chatbot.llm import fast_llm, llm
from nirf_chatbot.llm_utils import clean_llm_text
from nirf_chatbot.prompts import system_prompt
from nirf_chatbot.visualization import (
    _detect_bivariate_pair,
    _numeric_columns,
    compute_bivariate_stats,
    is_chart_request,
)

log = logging.getLogger("nirf_chatbot.answer")

MAX_ROWS_FOR_LLM = 60
MAX_LINES = 10

PARAMETER_COLUMNS = {
    "perception": "Perception",
    "tlr": "TLR",
    "teaching": "TLR",
    "rpc": "RPC",
    "research and professional": "RPC",
    "graduation": "GO",
    "go score": "GO",
    "outreach": "OI",
    "inclusivity": "OI",
    "oi score": "OI",
}

FIVE_PARAMS = ("TLR", "RPC", "GO", "OI", "Perception")

BOILERPLATE_COLS = {
    "Institution_ID",
    "Institution_Name",
    "City",
    "State",
    "Year",
    "Category",
    "Score",
    "Rank_Numeric",
    "Band",
    "Rank_Status",
    "Score_Status",
    *FIVE_PARAMS,
}

answer_prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    (
        "human",
        """User question:
{question}

SQL that was executed:
{sql}

Result rows ({row_count} total{truncated_note}), as JSON:
{results}

Write the answer now, using only these rows. Start with the
Visualization line, then '## Answer'.""",
    ),
])

answer_chain = answer_prompt | llm | StrOutputParser()
fast_answer_chain = answer_prompt | fast_llm | StrOutputParser()


class AnswerGenerationTimeout(RuntimeError):
    """Raised when the model times out while composing a natural-language answer."""


def _is_timeout_error(error: BaseException) -> bool:
    current: BaseException | None = error
    while current is not None:
        if isinstance(current, TimeoutError):
            return True
        if "timeout" in type(current).__name__.casefold():
            return True
        if "timed out" in str(current).casefold():
            return True
        current = current.__cause__ or current.__context__
    return False


def _fmt(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, (float, Decimal)):
        text = f"{float(value):,.2f}".rstrip("0").rstrip(".")
        return text
    return str(value)


def _json_default(value):
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _has_answer_body(answer: str) -> bool:
    body = re.sub(r"(?im)^\s*Visualization:\s*(?:CHART|TEXT)\s*$", "", answer)
    body = re.sub(r"(?m)^\s*##\s*(?:Answer|Chart code)\s*$", "", body)
    body = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    return bool(body.strip())


def _wrap(question: str, body: str) -> str:
    visualization = "CHART" if is_chart_request(question) else "TEXT"
    return f"Visualization: {visualization}\n## Answer\n{body.strip()}"


def _corr_strength(r: float) -> str:
    ar = abs(r)
    direction = "positive" if r >= 0 else "negative"
    if ar >= 0.85:
        return f"very strong {direction}"
    if ar >= 0.65:
        return f"strong {direction}"
    if ar >= 0.40:
        return f"moderate {direction}"
    if ar >= 0.20:
        return f"weak {direction}"
    return "negligible"


def _bivariate_answer(question: str, results: dict) -> str | None:
    rows = results.get("rows") or []
    if len(rows) < 3:
        return None
    df = pd.DataFrame(rows)
    columns = list(df.columns)
    numeric = _numeric_columns(df)
    pair = _detect_bivariate_pair(columns, numeric, question)
    if not pair:
        return None
    x_col, y_col = pair
    stats = compute_bivariate_stats(df, x_col, y_col)
    if not stats:
        return None

    r = stats["r"]
    r2_pct = round(stats["r2"] * 100, 1)
    strength = _corr_strength(r)
    x_mean = pd.to_numeric(df[x_col], errors="coerce").mean()
    y_mean = pd.to_numeric(df[y_col], errors="coerce").mean()
    cat = df["Category"].iloc[0] if "Category" in df.columns else "Overall"
    yr = df["Year"].iloc[0] if "Year" in df.columns else ""

    lines = [
        f"Across **{stats['n']}** ranked institutions in **NIRF {cat} {yr}**, "
        f"**{x_col}** and **{y_col}** show a **{strength} correlation**:",
        f"- **Pearson correlation ($r$):** `{r:.4f}`",
        f"- **Variance explained ($R^2$):** `{stats['r2']:.4f}` ({r2_pct}% of variance in {y_col} is explained by {x_col})",
        f"- **Linear trend (OLS slope):** `{stats['slope']:+.3f}` {y_col} points per 1-point increase in {x_col}",
        f"- **Sample averages:** mean {x_col} = `{x_mean:.2f}`, mean {y_col} = `{y_mean:.2f}`",
    ]
    if "Institution_Name" in df.columns:
        lines.append("\n**Top institutions in this sample:**")
        for i, row in enumerate(rows[:5], start=1):
            lines.append(
                f"{i}. **{row['Institution_Name']}** — {x_col}: {_fmt(row.get(x_col))}, "
                f"{y_col}: {_fmt(row.get(y_col))}"
                + (f", rank #{row['Rank_Numeric']}" if row.get("Rank_Numeric") is not None else "")
            )
    return "\n".join(lines)


def _metric_for(question: str, fields) -> str | None:
    q = question.casefold()
    for keyword, column in PARAMETER_COLUMNS.items():
        if keyword in q and column in fields:
            return column
    return None


def _institution_answer(question: str, results: dict) -> str | None:
    rows = results.get("rows") or []
    columns = results.get("columns") or list(rows[0].keys())
    fields = set(columns)
    if "Institution_Name" not in fields:
        return None

    # Check if this is a bivariate correlation question first
    biv = _bivariate_answer(question, results)
    if biv is not None:
        return biv

    derived_cols = [c for c in columns if c not in BOILERPLATE_COLS]
    all_five_present = all(p in fields for p in FIVE_PARAMS)
    parameter = _metric_for(question, fields)
    years = sorted({r.get("Year") for r in rows if r.get("Year") is not None})
    names_in_order = list(dict.fromkeys(r["Institution_Name"] for r in rows))
    truncated = " (result limit reached)" if results.get("truncated") else ""

    def describe(row) -> str:
        bits = []
        if "Rank_Numeric" in fields and row.get("Rank_Numeric") is not None:
            bits.append(f"rank #{row['Rank_Numeric']}")
        if "Score" in fields and row.get("Score") is not None:
            bits.append(f"score {_fmt(row.get('Score'))}")
        for dc in derived_cols:
            if row.get(dc) is not None:
                bits.append(f"{dc.replace('_', ' ')}: **{_fmt(row.get(dc))}**")
        if all_five_present:
            param_str = ", ".join(
                f"{p} {_fmt(row.get(p))}" for p in FIVE_PARAMS if row.get(p) is not None
            )
            if param_str:
                bits.append(f"[{param_str}]")
        elif parameter and parameter not in derived_cols:
            bits.append(f"{parameter} {_fmt(row.get(parameter))}")
        else:
            for p in FIVE_PARAMS:
                if p in fields and row.get(p) is not None and not all_five_present:
                    bits.append(f"{p} {_fmt(row.get(p))}")
        return ", ".join(bits) if bits else "—"

    # Two-state comparison summary header (e.g. Karnataka vs Tamil Nadu)
    states_present = sorted({r.get("State") for r in rows if r.get("State")})
    state_comparison_header = []
    if len(states_present) == 2 and "compare" in question.casefold() and len(years) <= 1:
        df = pd.DataFrame(rows)
        state_comparison_header.append(
            f"**State Comparison ({states_present[0]} vs {states_present[1]}):**"
        )
        for st_name in states_present:
            sub = df[df["State"] == st_name]
            cnt = len(sub)
            avg_s = pd.to_numeric(sub["Score"], errors="coerce").mean() if "Score" in sub else None
            best_r = pd.to_numeric(sub["Rank_Numeric"], errors="coerce").min() if "Rank_Numeric" in sub else None
            state_comparison_header.append(
                f"- **{st_name}:** **{cnt}** ranked institutions"
                + (f", best rank **#{int(best_r)}**" if pd.notna(best_r) else "")
                + (f", average score **{_fmt(avg_s)}**" if pd.notna(avg_s) else "")
            )
        state_comparison_header.append("")

    # Multi-year time-series per institution (when Year column has multiple years and no yoy derived columns)
    if len(years) > 1 and "Year" in fields and not derived_cols:
        categories = sorted({r.get("Category") for r in rows if r.get("Category")})
        header = (
            f"Year-by-year results for **{', '.join(categories) or 'the selected category'}** "
            f"({years[0]}–{years[-1]}){truncated}:"
        )
        lines = [header]
        for name in names_in_order[:MAX_LINES]:
            inst_rows = sorted(
                (r for r in rows if r["Institution_Name"] == name),
                key=lambda r: (r.get("Year") or 0, r.get("Category") or ""),
            )
            multi_cat = len({r.get("Category") for r in inst_rows}) > 1
            points = "; ".join(
                f"{r.get('Year')}{' ' + r.get('Category') if multi_cat else ''}: "
                + (f"rank #{r['Rank_Numeric']}" if r.get("Rank_Numeric") is not None else "unranked")
                + (f" ({_fmt(r.get('Score'))})" if r.get("Score") is not None else "")
                for r in inst_rows
            )
            lines.append(f"- **{name}** — {points}")
        if len(names_in_order) > MAX_LINES:
            lines.append(f"\n…and {len(names_in_order) - MAX_LINES} more institutions (see Results Table).")
        return "\n".join(lines)

    # Single row
    if len(rows) == 1:
        r = rows[0]
        where = ", ".join(x for x in (r.get("City"), r.get("State")) if x)
        context = " ".join(
            str(x) for x in (r.get("Category"), r.get("Year")) if x is not None
        )
        prefix = ""
        if re.search(r"\bhow\s+many\b", question, re.IGNORECASE):
            prefix = "**1** institution matched this criterion:\n- "
        return (
            f"{prefix}**{r['Institution_Name']}**{f' ({where})' if where else ''}"
            f"{f' in NIRF {context}' if context else ''}: {describe(r)}."
        )

    category = next((r.get("Category") for r in rows if r.get("Category")), None)
    year = years[0] if len(years) == 1 else None
    title_bits = " ".join(str(x) for x in (category, year) if x is not None)
    if re.search(r"\bhow\s+many\b", question, re.IGNORECASE):
        lead = f"**{len(rows)}** institutions matched{f' in NIRF {title_bits}' if title_bits else ''}{truncated}:"
    else:
        lead = f"**{len(rows)}** results{f' for NIRF {title_bits}' if title_bits else ''}{truncated}:"

    lines = [*state_comparison_header, lead]
    for i, r in enumerate(rows[:MAX_LINES], start=1):
        where = r.get("State") or ""
        lines.append(f"{i}. **{r['Institution_Name']}**{f' ({where})' if where else ''} — {describe(r)}")
    if len(rows) > MAX_LINES:
        lines.append(f"\nShowing the first {MAX_LINES} of {len(rows)} rows (see Results Table).")
    return "\n".join(lines)


def _aggregate_table_answer(question: str, results: dict) -> str | None:
    """Format multi-row aggregate / statistical tables deterministically."""
    rows = results.get("rows") or []
    columns = results.get("columns") or (list(rows[0].keys()) if rows else [])
    if not rows or "Institution_Name" in columns:
        return None

    if len(rows) == 1:
        parts = [f"**{c.replace('_', ' ')}**: {_fmt(rows[0].get(c))}" for c in columns]
        return "Result: " + "; ".join(parts) + "."

    key_col = columns[0]
    val_cols = [c for c in columns[1:] if c != "band_start"]
    lines = [f"Summary across **{len(rows)}** groups (ordered by query ranking):"]
    for row in rows[:12]:
        key_val = _fmt(row.get(key_col))
        metrics = ", ".join(
            f"{c.replace('_', ' ')}: **{_fmt(row.get(c))}**"
            for c in val_cols[:6]
            if row.get(c) is not None
        )
        lines.append(f"- **{key_val}** — {metrics}")
    if len(rows) > 12:
        lines.append(f"\nShowing the first 12 of {len(rows)} rows (see Results Table and Visualization tabs).")
    return "\n".join(lines)


def _generic_summary(results: dict) -> str:
    rows = results.get("rows") or []
    columns = results.get("columns") or (list(rows[0].keys()) if rows else [])
    if not rows:
        return "The query ran successfully but returned no rows."
    if len(rows) == 1:
        parts = [f"**{c.replace('_', ' ')}**: {_fmt(rows[0].get(c))}" for c in columns]
        return "Result: " + "; ".join(parts) + "."
    lines = [f"The query returned **{len(rows)}** rows. First rows:"]
    for row in rows[:MAX_LINES]:
        lines.append("- " + ", ".join(f"{c.replace('_', ' ')}: {_fmt(row.get(c))}" for c in columns[:5]))
    return "\n".join(lines)


def _fallback_answer(answer: str, results: dict, question: str = "") -> str:
    if answer and _has_answer_body(answer):
        return answer
    return _wrap(question, _generic_summary(results))


def generate_answer(question: str, results: dict, sql: str = "") -> str:
    rows = results.get("rows") or []
    if not rows:
        return _wrap(
            question,
            "The query ran successfully but **no matching records** were found. "
            "Check the filters in the Generated SQL tab — for example the "
            "category, state spelling, institution name or year (data covers 2017–2025).",
        )

    grounded = _institution_answer(question, results)
    if grounded is not None:
        return _wrap(question, grounded)

    agg_summary = _aggregate_table_answer(question, results)
    if agg_summary is not None:
        return _wrap(question, agg_summary)

    payload = json.dumps(rows[:MAX_ROWS_FOR_LLM], default=_json_default, ensure_ascii=False)
    chain_input = {
        "question": question,
        "sql": sql or results.get("sql", ""),
        "row_count": len(rows),
        "truncated_note": ", truncated" if results.get("truncated") else "",
        "results": payload,
    }
    try:
        raw = answer_chain.invoke(chain_input)
        if not clean_llm_text(raw):
            raw = fast_answer_chain.invoke(chain_input)
    except Exception as exc:
        if _is_timeout_error(exc):
            raise AnswerGenerationTimeout(
                "The database query succeeded, but Sarvam timed out while "
                "writing the answer. The results and chart are still available."
            ) from exc
        log.exception("Answer generation failed")
        return _wrap(question, _generic_summary(results))

    answer = clean_llm_text(raw)
    if not answer.lstrip().lower().startswith("visualization:"):
        answer = _wrap(question, answer)
    return _fallback_answer(answer, results, question)
