"""
General NIRF knowledge engine.

Used only for questions that are about the NIRF framework itself
(methodology, parameters, weights, how ranks/scores are computed, what NIRF
is) or that the SQL generator declares unanswerable from the data.

Live dataset statistics are computed with real, validated, read-only SQL
(shown to the user). Nothing is hard-coded: if the database cannot be
reached, the answer is given from the methodology notes only and says so.
"""

import logging
import re
import time

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from nirf_chatbot.llm import fast_llm, llm
from nirf_chatbot.llm_utils import clean_llm_text
from nirf_chatbot.sql_executor import execute_sql

log = logging.getLogger("nirf_chatbot.general")

NIRF_KNOWLEDGE_BASE = """
- NIRF (National Institutional Ranking Framework) was launched in September
  2015 by the Ministry of Education, Government of India; the first rankings
  were published in 2016.
- Institutions are scored out of 100 on five parameter groups. The weights
  below are those used for the Overall / University / Engineering style
  rankings; NIRF varies weights by category (e.g. Medical, Management, Law
  and College use different weights):
  1. Teaching, Learning & Resources (TLR) - ~30%: student strength incl.
     doctoral students, faculty-student ratio, faculty with PhD and
     experience, financial resources and utilisation.
  2. Research & Professional Practice (RPC) - ~30%: publications, quality of
     publications (citations), IPR and patents, sponsored research and
     consultancy footprint.
  3. Graduation Outcomes (GO) - ~20%: university examination results, PhD
     graduates, placement / higher studies and median salary.
  4. Outreach & Inclusivity (OI) - ~10%: students from other states and
     countries, women, economically and socially challenged students,
     facilities for physically challenged students.
  5. Perception (PR) - ~10%: surveys of academic peers and employers.
- Final score = weighted sum of the five parameter scores; institutions are
  ranked by score within each category. Exact ranks are published for the top
  institutions (typically top 100-200, varies by category); beyond that NIRF
  publishes rank bands.
- Participation is voluntary: institutions submit data to NIRF, so the set of
  ranked institutions is a subset of all Indian higher-education institutions.
  Percentile of a rank R among N ranked institutions in a category:
  percentile = 100 * (N - R) / N.
- Categories have been added over time (e.g. Research, Innovation,
  Agriculture, Open University, Skill University, State Public University,
  SDG Institutions in later years).
"""

_CONCEPTUAL = re.compile(
    r"\bwhat\s+(is|are|does)\s+(the\s+)?nirf\b"
    r"|\bnirf\s+(methodology|framework|parameters?|criteria|weight(age|s)?)\b"
    r"|\bmethodology\b"
    r"|\bhow\s+(is|are|does|do)\b.*\b(scores?|ranks?|rankings?|nirf|percentiles?)\b.*\b(calculated|computed|determined|decided|assigned|work|derived|given)\b"
    r"|\bweight(age|s|ing)?\s+of\b"
    r"|\bwhat\s+(is|are|does)\s+(tlr|rpc|go|oi|perception|pr)\b"
    r"|\b(stand|stands)\s+for\b"
    r"|\beligib(le|ility)\b"
    r"|\bexplain\s+(the\s+)?(nirf|ranking|framework|parameters?|scoring)\b",
    re.IGNORECASE,
)
_DATA_REQUEST = re.compile(
    r"\b(which|list|top\s*\d*|show\s+me|compare|plot|chart|graph|map|"
    r"rank\s+of|score\s+of|highest|lowest|best|worst)\b",
    re.IGNORECASE,
)
_STATS_WORDS = re.compile(
    r"\b(percent(age)?|percentiles?|distribution|statistics?|stats|median|"
    r"average|mean|how\s+many|share|proportion|coverage)\b",
    re.IGNORECASE,
)

STATS_SQL = """
SELECT COUNT(*) AS total_records,
       COUNT(DISTINCT "Institution_ID") AS distinct_institutions,
       COUNT(*) FILTER (WHERE "Rank_Numeric" IS NOT NULL) AS ranked_records,
       COUNT(*) FILTER (WHERE "Score" IS NOT NULL) AS scored_records,
       MIN("Year") AS first_year,
       MAX("Year") AS last_year,
       COUNT(DISTINCT "Category") AS categories,
       COUNT(DISTINCT "State") AS states,
       ROUND(AVG("Score")::numeric, 2) AS avg_score,
       ROUND((percentile_cont(0.25) WITHIN GROUP (ORDER BY "Score"))::numeric, 2) AS p25_score,
       ROUND((percentile_cont(0.50) WITHIN GROUP (ORDER BY "Score"))::numeric, 2) AS median_score,
       ROUND((percentile_cont(0.75) WITHIN GROUP (ORDER BY "Score"))::numeric, 2) AS p75_score,
       ROUND((percentile_cont(0.90) WITHIN GROUP (ORDER BY "Score"))::numeric, 2) AS p90_score,
       ROUND((percentile_cont(0.99) WITHIN GROUP (ORDER BY "Score"))::numeric, 2) AS p99_score
FROM public."NIRF"
LIMIT 1
"""

_STATS_LABELS = {
    "total_records": "Total records (institution x year x category)",
    "distinct_institutions": "Distinct institutions",
    "ranked_records": "Records with a numeric rank",
    "scored_records": "Records with a score",
    "first_year": "First year",
    "last_year": "Last year",
    "categories": "Categories",
    "states": "States / UTs",
    "avg_score": "Average score",
    "p25_score": "25th percentile score",
    "median_score": "Median (50th percentile) score",
    "p75_score": "75th percentile score",
    "p90_score": "90th percentile score",
    "p99_score": "99th percentile score",
}

_STATS_TTL_SECONDS = 600
_stats_cache: dict = {"at": 0.0, "value": None}


def is_general_question(question: str) -> bool:
    """True only for questions about the framework itself, not data lookups."""
    return bool(_CONCEPTUAL.search(question)) and not _DATA_REQUEST.search(question)


def fetch_dataset_stats() -> dict | None:
    """Live statistics from the database (cached for 10 minutes on success).
    Returns None if the database is unavailable - never fabricated values."""
    now = time.time()
    if _stats_cache["value"] is not None and now - _stats_cache["at"] < _STATS_TTL_SECONDS:
        return _stats_cache["value"]
    try:
        result = execute_sql(STATS_SQL)
        row = result["rows"][0] if result["rows"] else None
    except Exception:
        log.exception("Could not compute live dataset statistics")
        return None
    if row:
        _stats_cache.update(at=now, value=dict(row))
    return row and dict(row)


general_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are an expert on India's National Institutional Ranking
Framework (NIRF). Answer the user's question about NIRF's framework,
methodology or the dataset.

Reference notes on NIRF methodology:
{knowledge_base}

Live statistics computed from the user's NIRF database (2017-2025):
{stats}

Rules:
- Start with exactly these two lines:
Visualization: TEXT
## Answer
- Then give a clear, well-structured answer (markdown bullets allowed).
- Any dataset number you state must come from the live statistics above.
  If they are unavailable, say that live statistics could not be loaded.
- If the question needs specific institution/state/year data that is not in
  the statistics, say so and suggest how to ask it (e.g. "Top 10 Engineering
  institutions in 2025").
- Do not output SQL or code.""",
    ),
    ("human", "{question}"),
])

general_chain = general_prompt | llm | StrOutputParser()
fast_general_chain = general_prompt | fast_llm | StrOutputParser()


def _stats_text(stats: dict | None) -> str:
    if not stats:
        return "UNAVAILABLE (database could not be reached)"
    return "\n".join(f"- {_STATS_LABELS.get(k, k)}: {v}" for k, v in stats.items())


def _deterministic_answer(stats: dict | None) -> str:
    lines = [
        "NIRF scores institutions out of 100 on five parameters — Teaching, "
        "Learning & Resources (TLR), Research & Professional Practice (RPC), "
        "Graduation Outcomes (GO), Outreach & Inclusivity (OI) and Perception "
        "(PR) — and ranks them by total score within each category.",
    ]
    if stats:
        lines.append("")
        lines.append("Live statistics from your database:")
        for key in ("total_records", "distinct_institutions", "first_year",
                    "last_year", "median_score", "p90_score", "p99_score"):
            if key in stats:
                lines.append(f"- {_STATS_LABELS[key]}: {stats[key]}")
    else:
        lines.append("\n_Live dataset statistics could not be loaded._")
    return "\n".join(lines)


def answer_general_question(question: str, history: list[dict] | None = None,
                            reason: str = "methodology") -> dict:
    stats = fetch_dataset_stats()
    chain_input = {
        "knowledge_base": NIRF_KNOWLEDGE_BASE,
        "stats": _stats_text(stats),
        "question": question,
    }
    try:
        raw = general_chain.invoke(chain_input)
        if not clean_llm_text(raw):
            raw = fast_general_chain.invoke(chain_input)
        answer = clean_llm_text(raw)
    except Exception:
        log.exception("General answer generation failed")
        answer = ""

    body = re.sub(r"(?im)^\s*Visualization:\s*(CHART|TEXT)\s*$", "", answer)
    body = re.sub(r"(?m)^\s*##\s*Answer\s*$", "", body).strip()
    if not body:
        body = _deterministic_answer(stats)

    note = (
        "\n\n_This answer comes from NIRF methodology notes"
        + (" plus live dataset statistics" if stats else "")
        + (", because the question could not be answered with a database query._"
           if reason == "unsupported" else "._")
    )
    answer = f"Visualization: TEXT\n## Answer\n{body}{note}"

    show_stats = bool(stats) and bool(_STATS_WORDS.search(question))
    results = {
        "columns": ["Metric", "Value"] if show_stats else [],
        "rows": (
            [{"Metric": _STATS_LABELS.get(k, k), "Value": v} for k, v in stats.items()]
            if show_stats else []
        ),
    }
    return {
        "question": question,
        "generated_sql": STATS_SQL.strip() if stats else "-- No query: answered from NIRF methodology notes.",
        "results": results,
        "answer": answer,
        "is_chart_request": False,
        "is_general_knowledge": True,
        "source": "knowledge",
    }
