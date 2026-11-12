"""
Chat service — central orchestrator for the NIRF Analytics Chatbot.

Pipeline:
1. Pure methodology questions (e.g. "What is NIRF?", "Explain NIRF parameter
   weights") are answered by ``general_engine`` using NIRF framework notes
   and live database statistics.
2. Pure dataset-overview questions (e.g. "Describe the dataset") run a single
   summary SELECT over ``public."NIRF"``.
3. All other questions go to the Sarvam SQL generator (with follow-up context
   only when the question actually refers to the previous turn), are cleaned,
   validated with ``sqlglot``, and executed in a READ ONLY transaction with a
   5-second timeout. If validation or execution fails, one automatic repair
   attempt is made with the error message.
"""

import logging
import re

from langchain_core.output_parsers import StrOutputParser

from nirf_chatbot.analytics_catalog import resolve_analytical_question
from nirf_chatbot.answer_engine import (
    AnswerGenerationTimeout,
    _fallback_answer,
    generate_answer,
)
from nirf_chatbot.general_engine import (
    answer_general_question,
    is_general_question,
)
from nirf_chatbot.llm import fast_llm, llm
from nirf_chatbot.llm_utils import clean_llm_text, extract_sql, is_unsupported
from nirf_chatbot.sql_engine import SQL_REPAIR_PROMPT, sql_prompt
from nirf_chatbot.sql_executor import (
    DatabaseUnavailableError,
    QueryExecutionError,
    execute_sql,
)
from nirf_chatbot.sql_validator import SQLValidationError, normalize_sql
from nirf_chatbot.visualization import ensure_chart_columns, is_chart_request

log = logging.getLogger("nirf_chatbot.service")

sql_chain = sql_prompt | llm | StrOutputParser()
fast_sql_chain = sql_prompt | fast_llm | StrOutputParser()
sql_repair_chain = SQL_REPAIR_PROMPT | fast_llm | StrOutputParser()

RANKING_CATEGORIES = (
    "Overall",
    "Engineering",
    "University",
    "College",
    "Management",
    "Pharmacy",
    "Medical",
    "Law",
    "Architecture",
    "Dental",
    "Research",
    "Innovation",
    "Agriculture",
    "Open University",
    "Skill University",
    "State Public University",
    "SDG Institutions",
)

_PURE_DATASET_OVERVIEW = re.compile(
    r"^\s*(?:what\s+is\s+(?:in\s+)?(?:this|the)\s+(?:nirf\s+)?(?:dataset|data|database|table)"
    r"|describe\s+(?:this|the)\s+(?:nirf\s+)?(?:dataset|data|database|table)"
    r"|(?:nirf\s+)?dataset\s+(?:overview|summary|info|information|details)"
    r"|(?:overview|summary)\s+of\s+(?:this|the)\s+(?:nirf\s+)?(?:dataset|data|database))\s*\??\s*$",
    re.IGNORECASE,
)

_FOLLOWUP_START = re.compile(
    r"^\s*(?:now\b|also\b|and\s+(?:in|for|what|how|show|only)\b|but\b|"
    r"what\s+about\b|how\s+about\b|same\s+(?:for|in|but)\b|instead\b|"
    r"only\s+(?:in|for|from|show|top)\b|just\s+(?:in|for|from|show)\b|"
    r"filter\s+(?:by|to|for)\b|narrow\s+(?:to|by)\b|restrict\s+to\b|"
    r"exclude\b|include\s+only\b)",
    re.IGNORECASE,
)

_FOLLOWUP_PRONOUN = re.compile(
    r"\b(?:among\s+them|of\s+them|of\s+those|of\s+these|from\s+those|"
    r"from\s+these|those\s+institutions|these\s+institutions|"
    r"their\s+ranks?|their\s+scores?|its\s+rank|its\s+score|"
    r"that\s+state|that\s+category|that\s+year|same\s+category|"
    r"same\s+year|same\s+state|previous\s+(?:query|question|results?))\b",
    re.IGNORECASE,
)

_FRAGMENT_START = re.compile(
    r"^\s*(?:in|for|from|within|by|without)\s+\w+",
    re.IGNORECASE,
)

_STANDALONE_ANCHORS = re.compile(
    r"\b(?:top|bottom|best|worst|highest|lowest|rank(?:s|ed|ing|ings)?|"
    r"scores?|institutions?|institutes?|colleges?|universit(?:y|ies)|"
    r"schools?|states?|cit(?:y|ies)|iit|nit|iim|iisc|aiims|iiit|"
    r"compare|plot|chart|graph|map|show|list|which|what|how\s+many|"
    r"count|total|average|mean|median|percent(?:age|ile)?|trend)\b",
    re.IGNORECASE,
)


def _dataset_overview_query(question: str) -> str | None:
    if not _PURE_DATASET_OVERVIEW.match(question):
        return None
    return """
        SELECT COUNT(*) AS row_count,
               COUNT(DISTINCT "Year") AS year_count,
               MIN("Year") AS first_year,
               MAX("Year") AS last_year,
               COUNT(DISTINCT "Category") AS category_count,
               COUNT(DISTINCT "Institution_ID") AS institution_count,
               COUNT(DISTINCT "State") AS state_count
        FROM public."NIRF"
        LIMIT 1
    """


def _dataset_overview_answer(results: dict) -> str:
    rows = results.get("rows") or []
    if not rows:
        return "The NIRF dataset did not return any summary information."

    summary = rows[0]
    row_count = int(summary.get("row_count") or 0)
    year_count = int(summary.get("year_count") or 0)
    category_count = int(summary.get("category_count") or 0)
    institution_count = int(summary.get("institution_count") or 0)
    state_count = int(summary.get("state_count") or 0)
    first_year = summary.get("first_year")
    last_year = summary.get("last_year")

    if not row_count:
        return "The NIRF dataset is currently empty."

    year_coverage = (
        f"{year_count} distinct years ({first_year}–{last_year})"
        if first_year is not None and last_year is not None
        else f"{year_count} distinct years"
    )
    return (
        f"The NIRF dataset contains **{row_count:,}** ranking records covering "
        f"**{year_coverage}** across **{category_count}** categories, with "
        f"**{institution_count:,}** distinct institutions in **{state_count}** "
        "states and union territories. Each record includes the institution "
        "name, category, year, overall score, numeric rank, location, and the "
        "five NIRF parameter scores (TLR, RPC, GO, OI, Perception)."
    )


def _is_followup_question(question: str) -> bool:
    """Return True only when the question clearly depends on the previous turn."""
    if _FOLLOWUP_START.search(question) or _FOLLOWUP_PRONOUN.search(question):
        return True
    words = question.strip().split()
    if len(words) <= 5 and _FRAGMENT_START.search(question) and not _STANDALONE_ANCHORS.search(question):
        return True
    return False


def _build_followup_context(question: str, history: list[dict]) -> str:
    """Build a context block for the SQL prompt only when `question` is a follow-up."""
    if not history or not _is_followup_question(question):
        return ""
    prev = history[-1]
    prev_q = prev.get("question", "")
    prev_sql = (prev.get("response") or {}).get("generated_sql", "")
    if not prev_q:
        return ""
    lines = [
        "Conversation context (the user is asking a follow-up to the previous turn; "
        "keep the previous filters unless the follow-up replaces them):",
        f"Previous question: {prev_q}",
    ]
    if prev_sql and not prev_sql.lstrip().startswith("--"):
        lines.append(f"Previous SQL: {prev_sql}")
    return "\n".join(lines) + "\n\n"


def _prepare_sql(raw_output: str, question: str) -> str:
    sql = extract_sql(raw_output)
    if not sql:
        raise SQLValidationError("The model did not return a SQL query.")
    sql = ensure_chart_columns(sql, question)
    sql = normalize_sql(sql)
    return sql


def process_question(question: str, history: list[dict] | None = None) -> dict:
    """Process a user question and return a structured response dict."""
    question = (question or "").strip()
    if not question:
        raise ValueError("Please enter a question.")

    chart_requested = is_chart_request(question)

    # 1. Pure conceptual / methodology questions about NIRF itself
    if is_general_question(question):
        return answer_general_question(question, history=history, reason="methodology")

    # 2. Pure dataset-overview request (no filters)
    dataset_overview_query = _dataset_overview_query(question)
    if dataset_overview_query:
        generated_sql = normalize_sql(dataset_overview_query)
        results = execute_sql(generated_sql)
        answer = _dataset_overview_answer(results)
        return {
            "question": question,
            "generated_sql": generated_sql,
            "results": results,
            "answer": f"Visualization: TEXT\n## Answer\n{answer}",
            "is_chart_request": False,
        }

    # 3. Parameterized analytical catalog (8 domains / 40 analytical templates,
    #    preserving any category, year/range, state, or institution filter)
    context = _build_followup_context(question, history or [])
    if not context:
        resolved = resolve_analytical_question(question)
        if resolved is not None:
            raw_sql, catalog_chart = resolved
            generated_sql = normalize_sql(raw_sql)
            results = execute_sql(generated_sql)
            answer_warning = None
            try:
                answer = generate_answer(question=question, results=results, sql=generated_sql)
            except AnswerGenerationTimeout as exc:
                answer = _fallback_answer("", results, question)
                answer_warning = str(exc)
            response = {
                "question": question,
                "generated_sql": generated_sql,
                "results": results,
                "answer": answer,
                "is_chart_request": bool(catalog_chart or chart_requested),
            }
            if answer_warning:
                response["answer_warning"] = answer_warning
            return response

    # 4. LLM-powered SQL generation (with follow-up context only when applicable)
    try:
        raw_sql = sql_chain.invoke({"question": question, "context": context})
        if not clean_llm_text(raw_sql):
            log.info("Primary model returned empty output; falling back to fast_sql_chain")
            raw_sql = fast_sql_chain.invoke({"question": question, "context": context})
    except Exception as exc:
        log.exception("Sarvam SQL generation call failed")
        raise RuntimeError(
            "Sarvam AI timed out or failed while converting your question to SQL. "
            "Please try again."
        ) from exc

    if is_unsupported(raw_sql):
        return answer_general_question(question, history=history, reason="unsupported")

    # 4. Validate + execute, with one automatic self-repair attempt on failure
    try:
        generated_sql = _prepare_sql(raw_sql, question)
        results = execute_sql(generated_sql)
    except DatabaseUnavailableError:
        raise
    except (SQLValidationError, QueryExecutionError) as first_err:
        log.info("First SQL attempt failed (%s); attempting repair. Raw: %s", first_err, raw_sql)
        try:
            repaired_raw = sql_repair_chain.invoke({
                "question": question,
                "context": context,
                "bad_sql": clean_llm_text(raw_sql),
                "error": str(first_err),
            })
        except Exception as repair_exc:
            log.exception("SQL repair call failed")
            raise ValueError(f"Could not generate a valid query: {first_err}") from repair_exc

        if is_unsupported(repaired_raw):
            return answer_general_question(question, history=history, reason="unsupported")

        try:
            generated_sql = _prepare_sql(repaired_raw, question)
            results = execute_sql(generated_sql)
        except (SQLValidationError, QueryExecutionError) as second_err:
            log.warning("Repaired SQL also failed (%s): %s", second_err, repaired_raw)
            raise ValueError(
                f"Could not run a valid SQL query for that question ({second_err}). "
                "Try rephrasing with a specific category, state, institution, or year."
            ) from second_err

    # 5. Compose grounded answer from the actual rows
    answer_warning = None
    try:
        answer = generate_answer(question=question, results=results, sql=generated_sql)
    except AnswerGenerationTimeout as exc:
        answer = _fallback_answer("", results, question)
        answer_warning = str(exc)

    response = {
        "question": question,
        "generated_sql": generated_sql,
        "results": results,
        "answer": answer,
        "is_chart_request": chart_requested,
    }
    if answer_warning:
        response["answer_warning"] = answer_warning
    return response
