"""
Analytical Query Catalog & Pattern Resolver for the 40 NIRF Analytics Questions.

Covers all 8 analytical domains:
1. Time-series and trend analysis (Q1.1 – Q1.5)
2. Geospatial and regional analysis (Q2.1 – Q2.5)
3. Univariate analysis (Q3.1 – Q3.5)
4. Bivariate analysis and correlation (Q4.1 – Q4.5)
5. Multivariate analysis (Q5.1 – Q5.5)
6. Distribution and statistical comparison (Q6.1 – Q6.5)
7. Ranking transitions and institutional mobility (Q7.1 – Q7.5)
8. Outlier detection and performance gaps (Q8.1 – Q8.5)

Important design rules:
- Only matches when a question clearly asks one of these 40 analytical
  questions.
- Always extracts any category, year (or year pair), state, or institution
  mentioned in the question so user filters are never dropped.
- If a question mentions states/cities/institutions that do not fit the
  template's parameters, returns None so the LLM SQL generator handles it.
"""

import re

CATEGORY_PATTERNS = [
    ("State Public University", r"\bstate\s+public\s+universit(?:y|ies)\b"),
    ("Open University", r"\bopen\s+universit(?:y|ies)\b"),
    ("Skill University", r"\bskill\s+universit(?:y|ies)\b"),
    ("SDG Institutions", r"\bsdg(?:\s+institutions?)?\b"),
    ("Engineering", r"\bengineering\b"),
    ("University", r"\buniversit(?:y|ies)\b"),
    ("College", r"\bcolleges?\b"),
    ("Management", r"\bmanagement\b|\bbusiness\s+schools?\b"),
    ("Pharmacy", r"\bpharmac(?:y|ies)\b"),
    ("Medical", r"\bmedical\b"),
    ("Law", r"\blaw\b"),
    ("Architecture", r"\barchitecture\b"),
    ("Dental", r"\bdental\b"),
    ("Research", r"\bresearch\s+(?:category|rankings?|institutions?)\b"),
    ("Innovation", r"\binnovation\b"),
    ("Agriculture", r"\bagricultur(?:e|al)\b"),
    ("Overall", r"\boverall\b"),
]

INDIAN_STATES = (
    "Andaman and Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh",
    "Assam", "Bihar", "Chandigarh", "Chhattisgarh", "Delhi", "Goa",
    "Gujarat", "Haryana", "Himachal Pradesh", "Jammu and Kashmir",
    "Jharkhand", "Karnataka", "Kerala", "Ladakh", "Madhya Pradesh",
    "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
    "Odisha", "Puducherry", "Punjab", "Rajasthan", "Sikkim",
    "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh",
    "Uttarakhand", "West Bengal",
)

INSTITUTION_ALIASES = {
    "IIT Madras": "Indian Institute of Technology Madras",
    "IIT Bombay": "Indian Institute of Technology Bombay",
    "IIT Delhi": "Indian Institute of Technology Delhi",
    "IIT Kanpur": "Indian Institute of Technology Kanpur",
    "IIT Kharagpur": "Indian Institute of Technology Kharagpur",
    "IIT Roorkee": "Indian Institute of Technology Roorkee",
    "IIT Guwahati": "Indian Institute of Technology Guwahati",
    "IIT Hyderabad": "Indian Institute of Technology Hyderabad",
    "IISc": "Indian Institute of Science",
    "IISc Bangalore": "Indian Institute of Science",
    "JNU": "Jawaharlal Nehru University",
    "BHU": "Banaras Hindu University",
    "Anna University": "Anna University",
    "Amrita": "Amrita Vishwa Vidyapeetham",
    "NIT Trichy": "National Institute of Technology Tiruchirappalli",
    "NIT Surathkal": "National Institute of Technology Karnataka",
}

ANALYTICS_CATALOG: dict[str, list[str]] = {
    "1. Time-Series & Trend Analysis": [
        "How has the overall NIRF ranking of a selected institution changed from 2017 to 2025?",
        "Which institutions have shown the greatest improvement in rank over the nine years?",
        "Which institutions have experienced the largest decline in ranking?",
        "How has the average score of institutions changed over time?",
        "Which institutions have remained consistently in the top 10 across multiple years?",
    ],
    "2. Geospatial & Regional Analysis": [
        "Which states have the highest number of institutions in the top 100?",
        "How is the geographical distribution of top-ranked institutions changing from 2017 to 2025?",
        "Which states have improved their representation in the top 100 over time?",
        "How do the rankings of institutions in Karnataka compare with those in Tamil Nadu?",
        "Which states have produced the largest number of newly appearing institutions in the rankings?",
    ],
    "3. Univariate Analysis": [
        "What is the distribution of NIRF scores for a selected year?",
        "What is the distribution of overall ranks across all institutions?",
        "What is the average, median, minimum, and maximum score in a given year?",
        "What percentage of ranked institutions fall into each score quartile?",
        "How does the spread of scores differ across NIRF categories?",
    ],
    "4. Bivariate Analysis & Correlation": [
        "How strongly are Research and Professional Practice (RPC) scores associated with overall scores?",
        "How does Perception (PR) relate to overall scores?",
        "Which NIRF parameter has the strongest correlation with the overall score?",
        "How are TLR and RPC scores related across institutions?",
        "Has the correlation between research scores and overall scores changed from 2017 to 2025?",
    ],
    "5. Multivariate Analysis": [
        "How do the top five institutions compare across all five NIRF parameters?",
        "Which institutions have high research scores but relatively low teaching scores?",
        "Which institutions have high teaching scores but relatively low perception scores?",
        "Which institutions have improved their overall scores despite declining scores in one or more parameters?",
        "Which institutions have the largest difference between their strongest and weakest parameters?",
    ],
    "6. Distribution & Statistical Comparison": [
        "How does the score distribution differ between the top 10 and the remaining institutions?",
        "Are NIRF scores more dispersed in one year than another?",
        "Which NIRF parameter exhibits the greatest variability across institutions?",
        "How do the median and interquartile range of scores change over time?",
        "How does the score distribution differ across states?",
    ],
    "7. Ranking Transitions & Mobility": [
        "How many institutions moved from the 51–100 band into the top 50 between two selected years?",
        "Which institutions entered or exited the top 10 between consecutive years?",
        "What percentage of institutions remained in the same rank band from one year to the next?",
        "Which institutions experienced the largest upward and downward rank movements?",
        "How many institutions moved up, moved down, or retained their positions each year?",
    ],
    "8. Outlier Detection & Performance Gaps": [
        "Which institutions have unusually high research scores relative to their overall scores?",
        "Which institutions perform substantially better in research than in teaching?",
        "Which institutions experienced an unusually large year-to-year score change?",
        "Which institutions have a strong parameter score but a relatively poor overall rank?",
        "Which institutions have unusually high ranking volatility compared with similar institutions?",
    ],
}


def _extract_category(question: str, default: str = "Overall") -> str:
    for cat, pattern in CATEGORY_PATTERNS:
        if re.search(pattern, question, re.IGNORECASE):
            return cat
    return default


def _extract_years(question: str) -> list[int]:
    return [int(y) for y in re.findall(r"\b(20(?:1[7-9]|2[0-5]))\b", question)]


def _extract_states(question: str) -> list[str]:
    found = []
    for state in INDIAN_STATES:
        if re.search(rf"\b{re.escape(state)}\b", question, re.IGNORECASE):
            found.append(state)
    return found


def _extract_institution(question: str) -> str | None:
    q_fold = question.casefold()
    for alias, canonical in INSTITUTION_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", question, re.IGNORECASE) or canonical.casefold() in q_fold:
            return canonical
    return None


def _latest_year_sql(category: str) -> str:
    return f'(SELECT MAX("Year") FROM public."NIRF" WHERE "Category" = \'{category}\')'


def resolve_analytical_question(question: str) -> tuple[str, bool] | None:
    """If `question` matches one of the 40 analytical patterns, return
    `(sql_query, is_chart_request)`. Otherwise return `None`."""
    q = question.strip()
    cat = _extract_category(q, "Overall")
    years = _extract_years(q)
    states = _extract_states(q)
    inst = _extract_institution(q)
    year_sql = str(years[0]) if len(years) == 1 else _latest_year_sql(cat)
    state_clause = f' AND "State" = \'{states[0]}\'' if len(states) == 1 else ""

    # ── 1. Time-Series & Trend Analysis ──────────────────────────────────────

    # Q1.1: How has the overall NIRF ranking of a selected institution changed from 2017 to 2025?
    if re.search(
        r"how\s+has\s+the\s+(?:\w+\s+)*(?:nirf\s+)?ranking\s+of\s+(?:a\s+selected\s+institution|.+?)\s+changed",
        q, re.IGNORECASE,
    ):
        if inst:
            esc = inst.replace("'", "''")
            return (
                f"""SELECT "Institution_ID", "Institution_Name", "Year", "Category", "Rank_Numeric", "Score", "TLR", "RPC", "GO", "OI", "Perception", "State", "City"
                FROM public."NIRF"
                WHERE "Category" = '{cat}' AND "Institution_Name" ILIKE '%{esc}%' AND "Year" BETWEEN 2017 AND 2025
                ORDER BY "Year" ASC""",
                True,
            )
        if re.search(r"\bselected\s+institution\b", q, re.IGNORECASE):
            return (
                f"""SELECT "Institution_ID", "Institution_Name", "Year", "Category", "Rank_Numeric", "Score", "State", "City"
                FROM public."NIRF"
                WHERE "Category" = '{cat}'
                  AND "Institution_ID" IN (
                      SELECT "Institution_ID" FROM public."NIRF"
                      WHERE "Category" = '{cat}' AND "Year" = {_latest_year_sql(cat)} AND "Rank_Numeric" BETWEEN 1 AND 5
                  )
                ORDER BY "Institution_ID", "Year" ASC""",
                True,
            )

    # Q1.2: Which institutions have shown the greatest improvement in rank over the nine years?
    if re.search(
        r"(?:greatest|largest|most|biggest)\s+improvement\s+in\s+rank(?:ing)?\s+(?:over\s+the\s+(?:nine|9|\d+)\s+years|from\s+2017\s+to\s+2025|over\s+(?:time|the\s+years))",
        q, re.IGNORECASE,
    ):
        y_filter = f' AND "Year" BETWEEN {years[0]} AND {years[-1]}' if len(years) >= 2 else ""
        return (
            f"""WITH bounds AS (
                SELECT "Institution_ID", MIN("Year") AS first_year, MAX("Year") AS last_year
                FROM public."NIRF"
                WHERE "Category" = '{cat}' AND "Rank_Numeric" IS NOT NULL{state_clause}{y_filter}
                GROUP BY "Institution_ID"
                HAVING MIN("Year") < MAX("Year")
            )
            SELECT b."Institution_ID",
                   l."Institution_Name",
                   l."State",
                   b.first_year,
                   e."Rank_Numeric" AS start_rank,
                   b.last_year,
                   l."Rank_Numeric" AS end_rank,
                   (e."Rank_Numeric" - l."Rank_Numeric") AS rank_improvement,
                   ROUND((l."Score" - e."Score")::numeric, 2) AS score_change
            FROM bounds b
            JOIN public."NIRF" e ON e."Institution_ID" = b."Institution_ID" AND e."Category" = '{cat}' AND e."Year" = b.first_year
            JOIN public."NIRF" l ON l."Institution_ID" = b."Institution_ID" AND l."Category" = '{cat}' AND l."Year" = b.last_year
            WHERE e."Rank_Numeric" > l."Rank_Numeric"
            ORDER BY rank_improvement DESC, l."Rank_Numeric" ASC
            LIMIT 25""",
            True,
        )

    # Q1.3: Which institutions have experienced the largest decline in ranking?
    if re.search(
        r"(?:largest|greatest|most|biggest|worst)\s+(?:decline|drop|fall)\s+in\s+rank(?:ing)?",
        q, re.IGNORECASE,
    ):
        y_filter = f' AND "Year" BETWEEN {years[0]} AND {years[-1]}' if len(years) >= 2 else ""
        return (
            f"""WITH bounds AS (
                SELECT "Institution_ID", MIN("Year") AS first_year, MAX("Year") AS last_year
                FROM public."NIRF"
                WHERE "Category" = '{cat}' AND "Rank_Numeric" IS NOT NULL{state_clause}{y_filter}
                GROUP BY "Institution_ID"
                HAVING MIN("Year") < MAX("Year")
            )
            SELECT b."Institution_ID",
                   l."Institution_Name",
                   l."State",
                   b.first_year,
                   e."Rank_Numeric" AS start_rank,
                   b.last_year,
                   l."Rank_Numeric" AS end_rank,
                   (l."Rank_Numeric" - e."Rank_Numeric") AS rank_decline,
                   ROUND((l."Score" - e."Score")::numeric, 2) AS score_change
            FROM bounds b
            JOIN public."NIRF" e ON e."Institution_ID" = b."Institution_ID" AND e."Category" = '{cat}' AND e."Year" = b.first_year
            JOIN public."NIRF" l ON l."Institution_ID" = b."Institution_ID" AND l."Category" = '{cat}' AND l."Year" = b.last_year
            WHERE l."Rank_Numeric" > e."Rank_Numeric"
            ORDER BY rank_decline DESC, l."Rank_Numeric" DESC
            LIMIT 25""",
            True,
        )

    # Q1.4: How has the average score of institutions changed over time?
    if re.search(
        r"how\s+has\s+the\s+(?:average|mean)\s+score\s+(?:of\s+institutions\s+)?changed\s+over\s+(?:time|the\s+years)",
        q, re.IGNORECASE,
    ):
        return (
            f"""SELECT "Year",
                   "Category",
                   COUNT(DISTINCT "Institution_ID") AS institutions_evaluated,
                   ROUND(AVG("Score")::numeric, 2) AS avg_score,
                   ROUND((percentile_cont(0.50) WITHIN GROUP (ORDER BY "Score"))::numeric, 2) AS median_score,
                   ROUND(MIN("Score")::numeric, 2) AS min_score,
                   ROUND(MAX("Score")::numeric, 2) AS max_score
            FROM public."NIRF"
            WHERE "Category" = '{cat}' AND "Score" IS NOT NULL{state_clause}
            GROUP BY "Year", "Category"
            ORDER BY "Year" ASC""",
            True,
        )

    # Q1.5: Which institutions have remained consistently in the top 10 across multiple years?
    if re.search(
        r"consistently\s+in\s+the\s+top\s*(\d+)\s+across\s+(?:multiple\s+)?years",
        q, re.IGNORECASE,
    ):
        m = re.search(r"top\s*(\d+)", q, re.IGNORECASE)
        top_n = int(m.group(1)) if m else 10
        return (
            f"""SELECT "Institution_ID",
                   MAX("Institution_Name") AS "Institution_Name",
                   MAX("State") AS "State",
                   COUNT(DISTINCT "Year") AS years_in_top_{top_n},
                   MIN("Year") AS first_year,
                   MAX("Year") AS last_year,
                   MIN("Rank_Numeric") AS best_rank,
                   ROUND(AVG("Rank_Numeric")::numeric, 2) AS avg_rank,
                   ROUND(AVG("Score")::numeric, 2) AS avg_score
            FROM public."NIRF"
            WHERE "Category" = '{cat}' AND "Rank_Numeric" BETWEEN 1 AND {top_n}{state_clause}
            GROUP BY "Institution_ID"
            HAVING COUNT(DISTINCT "Year") >= 2
            ORDER BY years_in_top_{top_n} DESC, avg_rank ASC
            LIMIT 25""",
            True,
        )

    # ── 2. Geospatial & Regional Analysis ────────────────────────────────────

    # Q2.1: Which states have the highest number of institutions in the top 100?
    if re.search(
        r"which\s+states?\s+have\s+the\s+(?:highest\s+number\s+of|most)\s+(?:\w+\s+)*institutions?\s+in\s+the\s+top\s*(\d+)",
        q, re.IGNORECASE,
    ) and not states:
        m = re.search(r"top\s*(\d+)", q, re.IGNORECASE)
        top_n = int(m.group(1)) if m else 100
        return (
            f"""SELECT "State",
                   COUNT(DISTINCT "Institution_ID") AS institution_count,
                   ROUND(AVG("Score")::numeric, 2) AS avg_score,
                   MIN("Rank_Numeric") AS best_rank
            FROM public."NIRF"
            WHERE "Category" = '{cat}'
              AND "Year" = {year_sql}
              AND "Rank_Numeric" BETWEEN 1 AND {top_n}
              AND "State" IS NOT NULL
            GROUP BY "State"
            ORDER BY institution_count DESC, "State" ASC""",
            True,
        )

    # Q2.2: How is the geographical distribution of top-ranked institutions changing from 2017 to 2025?
    if re.search(
        r"geographical\s+distribution\s+of\s+top[- ]ranked\s+institutions\s+changing",
        q, re.IGNORECASE,
    ):
        return (
            f"""SELECT "Year",
                   "State",
                   COUNT(DISTINCT "Institution_ID") AS institution_count,
                   ROUND(AVG("Score")::numeric, 2) AS avg_score
            FROM public."NIRF"
            WHERE "Category" = '{cat}'
              AND "Rank_Numeric" BETWEEN 1 AND 100
              AND "State" IS NOT NULL
            GROUP BY "Year", "State"
            ORDER BY "Year" ASC, institution_count DESC""",
            True,
        )

    # Q2.3: Which states have improved their representation in the top 100 over time?
    if re.search(
        r"which\s+states?\s+have\s+improved\s+their\s+representation\s+in\s+the\s+top\s*(\d+)",
        q, re.IGNORECASE,
    ):
        m = re.search(r"top\s*(\d+)", q, re.IGNORECASE)
        top_n = int(m.group(1)) if m else 100
        y1 = years[0] if len(years) >= 2 else 2017
        y2 = years[-1] if len(years) >= 2 else 2025
        return (
            f"""WITH s_start AS (
                SELECT "State", COUNT(DISTINCT "Institution_ID") AS count_{y1}
                FROM public."NIRF"
                WHERE "Category" = '{cat}' AND "Year" = {y1} AND "Rank_Numeric" BETWEEN 1 AND {top_n} AND "State" IS NOT NULL
                GROUP BY "State"
            ),
            s_end AS (
                SELECT "State", COUNT(DISTINCT "Institution_ID") AS count_{y2}
                FROM public."NIRF"
                WHERE "Category" = '{cat}' AND "Year" = {y2} AND "Rank_Numeric" BETWEEN 1 AND {top_n} AND "State" IS NOT NULL
                GROUP BY "State"
            )
            SELECT COALESCE(s_end."State", s_start."State") AS "State",
                   COALESCE(s_start.count_{y1}, 0) AS count_{y1},
                   COALESCE(s_end.count_{y2}, 0) AS count_{y2},
                   (COALESCE(s_end.count_{y2}, 0) - COALESCE(s_start.count_{y1}, 0)) AS net_gain
            FROM s_end
            FULL OUTER JOIN s_start ON s_end."State" = s_start."State"
            ORDER BY net_gain DESC, count_{y2} DESC""",
            True,
        )

    # Q2.4: How do the rankings of institutions in Karnataka compare with those in Tamil Nadu?
    if re.search(
        r"how\s+do\s+the\s+rankings\s+of\s+(?:\w+\s+)*institutions\s+in\s+.+?\s+compare\s+with\s+(?:those\s+in\s+)?.+",
        q, re.IGNORECASE,
    ) and len(states) == 2:
        s1, s2 = states[0], states[1]
        return (
            f"""SELECT "Institution_ID", "Institution_Name", "State", "City", "Year", "Category", "Rank_Numeric", "Score", "TLR", "RPC", "GO", "OI", "Perception"
            FROM public."NIRF"
            WHERE "Category" = '{cat}'
              AND "Year" = {year_sql}
              AND "State" IN ('{s1}', '{s2}')
              AND "Rank_Numeric" IS NOT NULL
            ORDER BY "Rank_Numeric" ASC""",
            True,
        )

    # Q2.5: Which states have produced the largest number of newly appearing institutions in the rankings?
    if re.search(
        r"which\s+states?\s+have\s+produced\s+the\s+(?:largest|highest|most)\s+number\s+of\s+newly\s+appearing\s+institutions",
        q, re.IGNORECASE,
    ):
        return (
            """WITH first_appearance AS (
                SELECT "Institution_ID",
                       MAX("State") AS "State",
                       MIN("Year") AS debut_year
                FROM public."NIRF"
                WHERE "State" IS NOT NULL
                GROUP BY "Institution_ID"
            )
            SELECT "State",
                   COUNT(*) FILTER (WHERE debut_year > 2017) AS newly_appearing_institutions,
                   COUNT(*) FILTER (WHERE debut_year = 2025) AS new_in_2025,
                   COUNT(*) AS total_distinct_institutions
            FROM first_appearance
            GROUP BY "State"
            HAVING COUNT(*) FILTER (WHERE debut_year > 2017) > 0
            ORDER BY newly_appearing_institutions DESC, "State" ASC""",
            True,
        )

    # ── 3. Univariate Analysis ───────────────────────────────────────────────

    # Q3.1: What is the distribution of NIRF scores for a selected year?
    if re.search(
        r"distribution\s+of\s+(?:\w+\s+)*scores\s+(?:for|in)\b",
        q, re.IGNORECASE,
    ):
        return (
            f"""SELECT (FLOOR("Score" / 5) * 5)::int || '–' || (FLOOR("Score" / 5) * 5 + 5)::int AS score_band,
                   (FLOOR("Score" / 5) * 5)::int AS band_start,
                   COUNT(*) AS institution_count,
                   ROUND(AVG("Score")::numeric, 2) AS avg_score_in_band,
                   MIN("Rank_Numeric") AS best_rank_in_band,
                   MAX("Rank_Numeric") AS worst_rank_in_band
            FROM public."NIRF"
            WHERE "Category" = '{cat}' AND "Year" = {year_sql} AND "Score" IS NOT NULL{state_clause}
            GROUP BY FLOOR("Score" / 5)
            ORDER BY band_start ASC""",
            True,
        )

    # Q3.2: What is the distribution of overall ranks across all institutions?
    if re.search(
        r"distribution\s+of\s+(?:overall\s+)?ranks?\s+across\s+all\s+institutions",
        q, re.IGNORECASE,
    ):
        return (
            f"""SELECT CASE
                       WHEN "Rank_Numeric" BETWEEN 1 AND 10 THEN '1. Top 10 (1–10)'
                       WHEN "Rank_Numeric" BETWEEN 11 AND 25 THEN '2. Ranks 11–25'
                       WHEN "Rank_Numeric" BETWEEN 26 AND 50 THEN '3. Ranks 26–50'
                       WHEN "Rank_Numeric" BETWEEN 51 AND 75 THEN '4. Ranks 51–75'
                       WHEN "Rank_Numeric" BETWEEN 76 AND 100 THEN '5. Ranks 76–100'
                       ELSE '6. Ranks 101–200'
                   END AS rank_tier,
                   COUNT(*) AS total_records,
                   COUNT(DISTINCT "Institution_ID") AS distinct_institutions,
                   ROUND(AVG("Score")::numeric, 2) AS avg_score,
                   ROUND(MIN("Score")::numeric, 2) AS min_score,
                   ROUND(MAX("Score")::numeric, 2) AS max_score
            FROM public."NIRF"
            WHERE "Category" = '{cat}' AND "Rank_Numeric" IS NOT NULL{state_clause}
            GROUP BY rank_tier
            ORDER BY rank_tier ASC""",
            True,
        )

    # Q3.3: What is the average, median, minimum, and maximum score in a given year?
    if re.search(
        r"average,\s*median,\s*minimum,\s*(?:and\s+)?maximum\s+score",
        q, re.IGNORECASE,
    ):
        y_clause = f' AND "Year" = {years[0]}' if len(years) == 1 else ""
        return (
            f"""SELECT "Year",
                   "Category",
                   COUNT(*) AS scored_institutions,
                   ROUND(AVG("Score")::numeric, 2) AS avg_score,
                   ROUND((percentile_cont(0.50) WITHIN GROUP (ORDER BY "Score"))::numeric, 2) AS median_score,
                   ROUND(MIN("Score")::numeric, 2) AS min_score,
                   ROUND(MAX("Score")::numeric, 2) AS max_score,
                   ROUND(STDDEV("Score")::numeric, 2) AS std_dev
            FROM public."NIRF"
            WHERE "Category" = '{cat}' AND "Score" IS NOT NULL{y_clause}{state_clause}
            GROUP BY "Year", "Category"
            ORDER BY "Year" DESC""",
            True,
        )

    # Q3.4: What percentage of ranked institutions fall into each score quartile?
    if re.search(
        r"percentage\s+of\s+(?:ranked\s+)?institutions\s+fall\s+into\s+each\s+score\s+quartile"
        r"|percentage\s+of\s+ranked\s+institute.*percentile",
        q, re.IGNORECASE,
    ):
        return (
            f"""WITH bounds AS (
                SELECT MIN("Score") AS min_s,
                       MAX("Score") AS max_s,
                       (MAX("Score") - MIN("Score")) / 4.0 AS step,
                       COUNT(*) AS total_cnt
                FROM public."NIRF"
                WHERE "Category" = '{cat}' AND "Year" = {year_sql} AND "Score" IS NOT NULL AND "Rank_Numeric" IS NOT NULL
            ),
            banded AS (
                SELECT n."Institution_ID",
                       n."Score",
                       LEAST(4, GREATEST(1, WIDTH_BUCKET(n."Score", b.min_s, b.max_s + 0.001, 4))) AS score_range_quartile,
                       NTILE(4) OVER (ORDER BY n."Score" ASC) AS equal_count_quartile
                FROM public."NIRF" n
                CROSS JOIN bounds b
                WHERE n."Category" = '{cat}' AND n."Year" = {year_sql} AND n."Score" IS NOT NULL AND n."Rank_Numeric" IS NOT NULL
            )
            SELECT 'Q' || score_range_quartile AS score_quartile,
                   CASE score_range_quartile
                       WHEN 1 THEN 'Q1 (Lowest 25% of Score Range)'
                       WHEN 2 THEN 'Q2 (25%–50% of Score Range)'
                       WHEN 3 THEN 'Q3 (50%–75% of Score Range)'
                       WHEN 4 THEN 'Q4 (Top 25% of Score Range)'
                   END AS quartile_description,
                   COUNT(*) AS institution_count,
                   ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_ranked_institutions,
                   ROUND(MIN("Score")::numeric, 2) AS min_score,
                   ROUND(AVG("Score")::numeric, 2) AS avg_score,
                   ROUND(MAX("Score")::numeric, 2) AS max_score
            FROM banded
            GROUP BY score_range_quartile
            ORDER BY score_range_quartile ASC""",
            True,
        )

    # Q3.5: How does the spread of scores differ across NIRF categories?
    if re.search(
        r"spread\s+of\s+scores\s+differ\s+across\s+(?:nirf\s+)?categories",
        q, re.IGNORECASE,
    ):
        y_clause = f' AND "Year" = {years[0]}' if len(years) == 1 else ' AND "Year" = 2025'
        return (
            f"""SELECT "Category",
                   COUNT(*) AS institutions,
                   ROUND(AVG("Score")::numeric, 2) AS avg_score,
                   ROUND(STDDEV("Score")::numeric, 2) AS std_dev,
                   ROUND(((percentile_cont(0.75) WITHIN GROUP (ORDER BY "Score")) - (percentile_cont(0.25) WITHIN GROUP (ORDER BY "Score")))::numeric, 2) AS iqr_spread,
                   ROUND(MIN("Score")::numeric, 2) AS min_score,
                   ROUND((percentile_cont(0.50) WITHIN GROUP (ORDER BY "Score"))::numeric, 2) AS median_score,
                   ROUND(MAX("Score")::numeric, 2) AS max_score,
                   ROUND((MAX("Score") - MIN("Score"))::numeric, 2) AS total_range
            FROM public."NIRF"
            WHERE "Score" IS NOT NULL{y_clause}
            GROUP BY "Category"
            ORDER BY std_dev DESC NULLS LAST""",
            True,
        )

    # ── 4. Bivariate Analysis & Correlation ──────────────────────────────────

    # Q4.1: How strongly are Research and Professional Practice (RPC) scores associated with overall scores?
    if re.search(
        r"how\s+strongly\s+are\s+(?:research\s+and\s+professional\s+practice|rpc).*associated\s+with\s+overall\s+scores",
        q, re.IGNORECASE,
    ):
        return (
            f"""SELECT "Institution_ID", "Institution_Name", "Year", "Category", "RPC", "Score", "Rank_Numeric", "State", "City"
            FROM public."NIRF"
            WHERE "Category" = '{cat}' AND "Year" = {year_sql} AND "RPC" IS NOT NULL AND "Score" IS NOT NULL
            ORDER BY "Score" DESC""",
            True,
        )

    # Q4.2: How does Perception (PR) relate to overall scores?
    if re.search(
        r"how\s+does\s+perception.*relate\s+to\s+overall\s+scores",
        q, re.IGNORECASE,
    ):
        return (
            f"""SELECT "Institution_ID", "Institution_Name", "Year", "Category", "Perception", "Score", "Rank_Numeric", "State", "City"
            FROM public."NIRF"
            WHERE "Category" = '{cat}' AND "Year" = {year_sql} AND "Perception" IS NOT NULL AND "Score" IS NOT NULL
            ORDER BY "Score" DESC""",
            True,
        )

    # Q4.3: Which NIRF parameter has the strongest correlation with the overall score?
    if re.search(
        r"which\s+(?:nirf\s+)?parameter\s+has\s+the\s+strongest\s+correlation\s+with\s+(?:the\s+)?overall\s+score",
        q, re.IGNORECASE,
    ):
        y_clause = f' AND "Year" = {years[0]}' if len(years) == 1 else ""
        return (
            f"""SELECT parameter, correlation_r, r_squared, avg_parameter_score, sample_size FROM (
                SELECT 'TLR (Teaching, Learning & Resources)' AS parameter,
                       ROUND(CORR("TLR", "Score")::numeric, 4) AS correlation_r,
                       ROUND(POWER(CORR("TLR", "Score"), 2)::numeric, 4) AS r_squared,
                       ROUND(AVG("TLR")::numeric, 2) AS avg_parameter_score,
                       COUNT(*) AS sample_size
                FROM public."NIRF" WHERE "Category" = '{cat}' AND "Score" IS NOT NULL AND "TLR" IS NOT NULL{y_clause}
                UNION ALL
                SELECT 'RPC (Research & Professional Practice)',
                       ROUND(CORR("RPC", "Score")::numeric, 4),
                       ROUND(POWER(CORR("RPC", "Score"), 2)::numeric, 4),
                       ROUND(AVG("RPC")::numeric, 2),
                       COUNT(*)
                FROM public."NIRF" WHERE "Category" = '{cat}' AND "Score" IS NOT NULL AND "RPC" IS NOT NULL{y_clause}
                UNION ALL
                SELECT 'GO (Graduation Outcomes)',
                       ROUND(CORR("GO", "Score")::numeric, 4),
                       ROUND(POWER(CORR("GO", "Score"), 2)::numeric, 4),
                       ROUND(AVG("GO")::numeric, 2),
                       COUNT(*)
                FROM public."NIRF" WHERE "Category" = '{cat}' AND "Score" IS NOT NULL AND "GO" IS NOT NULL{y_clause}
                UNION ALL
                SELECT 'OI (Outreach & Inclusivity)',
                       ROUND(CORR("OI", "Score")::numeric, 4),
                       ROUND(POWER(CORR("OI", "Score"), 2)::numeric, 4),
                       ROUND(AVG("OI")::numeric, 2),
                       COUNT(*)
                FROM public."NIRF" WHERE "Category" = '{cat}' AND "Score" IS NOT NULL AND "OI" IS NOT NULL{y_clause}
                UNION ALL
                SELECT 'Perception (PR)',
                       ROUND(CORR("Perception", "Score")::numeric, 4),
                       ROUND(POWER(CORR("Perception", "Score"), 2)::numeric, 4),
                       ROUND(AVG("Perception")::numeric, 2),
                       COUNT(*)
                FROM public."NIRF" WHERE "Category" = '{cat}' AND "Score" IS NOT NULL AND "Perception" IS NOT NULL{y_clause}
            ) AS corr_table
            ORDER BY correlation_r DESC""",
            True,
        )

    # Q4.4: How are TLR and RPC scores related across institutions?
    if re.search(
        r"how\s+are\s+tlr\s+and\s+rpc\s+scores\s+related",
        q, re.IGNORECASE,
    ):
        return (
            f"""SELECT "Institution_ID", "Institution_Name", "Year", "Category", "TLR", "RPC", "Score", "Rank_Numeric", "State", "City"
            FROM public."NIRF"
            WHERE "Category" = '{cat}' AND "Year" = {year_sql} AND "TLR" IS NOT NULL AND "RPC" IS NOT NULL
            ORDER BY "Score" DESC""",
            True,
        )

    # Q4.5: Has the correlation between research scores and overall scores changed from 2017 to 2025?
    if re.search(
        r"correlation\s+between\s+(?:research\s+scores?|rpc)\s+and\s+overall\s+scores?\s+changed",
        q, re.IGNORECASE,
    ):
        return (
            f"""SELECT "Year",
                   "Category",
                   COUNT(*) AS institutions,
                   ROUND(CORR("RPC", "Score")::numeric, 4) AS rpc_score_correlation,
                   ROUND(CORR("TLR", "Score")::numeric, 4) AS tlr_score_correlation,
                   ROUND(CORR("Perception", "Score")::numeric, 4) AS perception_score_correlation,
                   ROUND(AVG("RPC")::numeric, 2) AS avg_rpc,
                   ROUND(AVG("Score")::numeric, 2) AS avg_score
            FROM public."NIRF"
            WHERE "Category" = '{cat}' AND "RPC" IS NOT NULL AND "Score" IS NOT NULL
            GROUP BY "Year", "Category"
            ORDER BY "Year" ASC""",
            True,
        )

    # ── 5. Multivariate Analysis ─────────────────────────────────────────────

    # Q5.1: How do the top five institutions compare across all five NIRF parameters?
    if re.search(
        r"top\s+(?:five|5|\d+)\s+(?:\w+\s+)*institutions\s+compare\s+across\s+all\s+five\s+(?:nirf\s+)?parameters",
        q, re.IGNORECASE,
    ):
        m = re.search(r"top\s+(\d+)", q, re.IGNORECASE)
        top_n = int(m.group(1)) if m else 5
        return (
            f"""SELECT "Rank_Numeric", "Institution_Name", "Year", "Category", "Score", "TLR", "RPC", "GO", "OI", "Perception", "State", "City"
            FROM public."NIRF"
            WHERE "Category" = '{cat}' AND "Year" = {year_sql} AND "Rank_Numeric" BETWEEN 1 AND {top_n}
            ORDER BY "Rank_Numeric" ASC""",
            True,
        )

    # Q5.2 & Q8.2: High research scores but relatively low teaching scores / perform substantially better in research than in teaching
    if re.search(
        r"high\s+research\s+scores?\s+but\s+(?:relatively\s+)?low\s+teaching\s+scores?"
        r"|perform\s+substantially\s+better\s+in\s+research\s+than\s+in\s+teaching",
        q, re.IGNORECASE,
    ):
        return (
            f"""SELECT "Institution_ID", "Institution_Name", "Year", "Category", "Rank_Numeric", "Score",
                   "RPC", "TLR", ROUND(("RPC" - "TLR")::numeric, 2) AS rpc_minus_tlr, "State", "City"
            FROM public."NIRF"
            WHERE "Category" = '{cat}' AND "Year" = {year_sql}
              AND "RPC" IS NOT NULL AND "TLR" IS NOT NULL AND "RPC" > "TLR"
            ORDER BY rpc_minus_tlr DESC
            LIMIT 25""",
            True,
        )

    # Q5.3: High teaching scores but relatively low perception scores
    if re.search(
        r"high\s+teaching\s+scores?\s+but\s+(?:relatively\s+)?low\s+perception\s+scores?",
        q, re.IGNORECASE,
    ):
        return (
            f"""SELECT "Institution_ID", "Institution_Name", "Year", "Category", "Rank_Numeric", "Score",
                   "TLR", "Perception", ROUND(("TLR" - "Perception")::numeric, 2) AS tlr_minus_perception, "State", "City"
            FROM public."NIRF"
            WHERE "Category" = '{cat}' AND "Year" = {year_sql}
              AND "TLR" IS NOT NULL AND "Perception" IS NOT NULL AND "TLR" > "Perception"
            ORDER BY tlr_minus_perception DESC
            LIMIT 25""",
            True,
        )

    # Q5.4: Improved their overall scores despite declining scores in one or more parameters
    if re.search(
        r"improved\s+their\s+overall\s+scores?\s+despite\s+declining\s+scores?\s+in\s+one\s+or\s+more\s+parameters",
        q, re.IGNORECASE,
    ):
        y1 = years[0] if len(years) >= 2 else 2024
        y2 = years[-1] if len(years) >= 2 else 2025
        return (
            f"""SELECT n."Institution_ID",
                   n."Institution_Name",
                   n."State",
                   o."Year" AS prev_year,
                   n."Year" AS curr_year,
                   ROUND(o."Score"::numeric, 2) AS prev_score,
                   ROUND(n."Score"::numeric, 2) AS curr_score,
                   ROUND((n."Score" - o."Score")::numeric, 2) AS overall_score_gain,
                   ROUND((n."TLR" - o."TLR")::numeric, 2) AS tlr_change,
                   ROUND((n."RPC" - o."RPC")::numeric, 2) AS rpc_change,
                   ROUND((n."GO" - o."GO")::numeric, 2) AS go_change,
                   ROUND((n."OI" - o."OI")::numeric, 2) AS oi_change,
                   ROUND((n."Perception" - o."Perception")::numeric, 2) AS perception_change
            FROM public."NIRF" n
            JOIN public."NIRF" o
              ON n."Institution_ID" = o."Institution_ID"
             AND n."Category" = o."Category"
             AND o."Year" = {y1} AND n."Year" = {y2}
            WHERE n."Category" = '{cat}'
              AND n."Score" > o."Score"
              AND (n."TLR" < o."TLR" OR n."RPC" < o."RPC" OR n."GO" < o."GO" OR n."OI" < o."OI" OR n."Perception" < o."Perception")
            ORDER BY overall_score_gain DESC
            LIMIT 25""",
            True,
        )

    # Q5.5: Largest difference between their strongest and weakest parameters
    if re.search(
        r"largest\s+difference\s+between\s+(?:their\s+)?strongest\s+and\s+weakest\s+parameters",
        q, re.IGNORECASE,
    ):
        return (
            f"""SELECT "Institution_ID", "Institution_Name", "Year", "Category", "Rank_Numeric", "Score",
                   ROUND(GREATEST("TLR", "RPC", "GO", "OI", "Perception")::numeric, 2) AS strongest_param_score,
                   ROUND(LEAST("TLR", "RPC", "GO", "OI", "Perception")::numeric, 2) AS weakest_param_score,
                   ROUND((GREATEST("TLR", "RPC", "GO", "OI", "Perception") - LEAST("TLR", "RPC", "GO", "OI", "Perception"))::numeric, 2) AS parameter_gap,
                   "TLR", "RPC", "GO", "OI", "Perception", "State"
            FROM public."NIRF"
            WHERE "Category" = '{cat}' AND "Year" = {year_sql}
              AND "TLR" IS NOT NULL AND "RPC" IS NOT NULL AND "GO" IS NOT NULL AND "OI" IS NOT NULL AND "Perception" IS NOT NULL
            ORDER BY parameter_gap DESC
            LIMIT 25""",
            True,
        )

    # ── 6. Distribution & Statistical Comparison ─────────────────────────────

    # Q6.1: How does the score distribution differ between the top 10 and the remaining institutions?
    if re.search(
        r"score\s+distribution\s+differ\s+between\s+the\s+top\s*(\d+)\s+and\s+the\s+remaining",
        q, re.IGNORECASE,
    ):
        m = re.search(r"top\s*(\d+)", q, re.IGNORECASE)
        top_n = int(m.group(1)) if m else 10
        return (
            f"""SELECT CASE WHEN "Rank_Numeric" <= {top_n} THEN 'Top {top_n} Institutions' ELSE 'Remaining Institutions (Rank {top_n + 1}+)' END AS institution_group,
                   COUNT(*) AS institution_count,
                   ROUND(AVG("Score")::numeric, 2) AS avg_score,
                   ROUND((percentile_cont(0.50) WITHIN GROUP (ORDER BY "Score"))::numeric, 2) AS median_score,
                   ROUND(STDDEV("Score")::numeric, 2) AS std_dev,
                   ROUND(((percentile_cont(0.75) WITHIN GROUP (ORDER BY "Score")) - (percentile_cont(0.25) WITHIN GROUP (ORDER BY "Score")))::numeric, 2) AS iqr,
                   ROUND(MIN("Score")::numeric, 2) AS min_score,
                   ROUND(MAX("Score")::numeric, 2) AS max_score,
                   ROUND(AVG("TLR")::numeric, 2) AS avg_tlr,
                   ROUND(AVG("RPC")::numeric, 2) AS avg_rpc,
                   ROUND(AVG("Perception")::numeric, 2) AS avg_perception
            FROM public."NIRF"
            WHERE "Category" = '{cat}' AND "Year" = {year_sql} AND "Rank_Numeric" IS NOT NULL AND "Score" IS NOT NULL
            GROUP BY institution_group
            ORDER BY avg_score DESC""",
            True,
        )

    # Q6.2: Are NIRF scores more dispersed in one year than another?
    if re.search(
        r"scores?\s+more\s+dispersed\s+in\s+one\s+year\s+than\s+another",
        q, re.IGNORECASE,
    ):
        return (
            f"""SELECT "Year",
                   "Category",
                   COUNT(*) AS institutions,
                   ROUND(STDDEV("Score")::numeric, 2) AS std_dev,
                   ROUND(VARIANCE("Score")::numeric, 2) AS variance,
                   ROUND(((percentile_cont(0.75) WITHIN GROUP (ORDER BY "Score")) - (percentile_cont(0.25) WITHIN GROUP (ORDER BY "Score")))::numeric, 2) AS iqr,
                   ROUND((MAX("Score") - MIN("Score"))::numeric, 2) AS score_range,
                   ROUND(AVG("Score")::numeric, 2) AS avg_score
            FROM public."NIRF"
            WHERE "Category" = '{cat}' AND "Score" IS NOT NULL
            GROUP BY "Year", "Category"
            ORDER BY "Year" ASC""",
            True,
        )

    # Q6.3: Which NIRF parameter exhibits the greatest variability across institutions?
    if re.search(
        r"which\s+(?:nirf\s+)?parameter\s+exhibits\s+the\s+(?:greatest|highest|most)\s+variability",
        q, re.IGNORECASE,
    ):
        y_clause = f' AND "Year" = {years[0]}' if len(years) == 1 else f' AND "Year" = {_latest_year_sql(cat)}'
        return (
            f"""SELECT parameter, std_dev, variance, iqr, min_score, median_score, max_score, avg_score FROM (
                SELECT 'Perception (PR)' AS parameter, ROUND(STDDEV("Perception")::numeric, 2) AS std_dev, ROUND(VARIANCE("Perception")::numeric, 2) AS variance, ROUND(((percentile_cont(0.75) WITHIN GROUP (ORDER BY "Perception")) - (percentile_cont(0.25) WITHIN GROUP (ORDER BY "Perception")))::numeric, 2) AS iqr, ROUND(MIN("Perception")::numeric, 2) AS min_score, ROUND((percentile_cont(0.50) WITHIN GROUP (ORDER BY "Perception"))::numeric, 2) AS median_score, ROUND(MAX("Perception")::numeric, 2) AS max_score, ROUND(AVG("Perception")::numeric, 2) AS avg_score FROM public."NIRF" WHERE "Category" = '{cat}' AND "Perception" IS NOT NULL{y_clause}
                UNION ALL
                SELECT 'RPC (Research & Professional Practice)', ROUND(STDDEV("RPC")::numeric, 2), ROUND(VARIANCE("RPC")::numeric, 2), ROUND(((percentile_cont(0.75) WITHIN GROUP (ORDER BY "RPC")) - (percentile_cont(0.25) WITHIN GROUP (ORDER BY "RPC")))::numeric, 2), ROUND(MIN("RPC")::numeric, 2), ROUND((percentile_cont(0.50) WITHIN GROUP (ORDER BY "RPC"))::numeric, 2), ROUND(MAX("RPC")::numeric, 2), ROUND(AVG("RPC")::numeric, 2) FROM public."NIRF" WHERE "Category" = '{cat}' AND "RPC" IS NOT NULL{y_clause}
                UNION ALL
                SELECT 'TLR (Teaching, Learning & Resources)', ROUND(STDDEV("TLR")::numeric, 2), ROUND(VARIANCE("TLR")::numeric, 2), ROUND(((percentile_cont(0.75) WITHIN GROUP (ORDER BY "TLR")) - (percentile_cont(0.25) WITHIN GROUP (ORDER BY "TLR")))::numeric, 2), ROUND(MIN("TLR")::numeric, 2), ROUND((percentile_cont(0.50) WITHIN GROUP (ORDER BY "TLR"))::numeric, 2), ROUND(MAX("TLR")::numeric, 2), ROUND(AVG("TLR")::numeric, 2) FROM public."NIRF" WHERE "Category" = '{cat}' AND "TLR" IS NOT NULL{y_clause}
                UNION ALL
                SELECT 'GO (Graduation Outcomes)', ROUND(STDDEV("GO")::numeric, 2), ROUND(VARIANCE("GO")::numeric, 2), ROUND(((percentile_cont(0.75) WITHIN GROUP (ORDER BY "GO")) - (percentile_cont(0.25) WITHIN GROUP (ORDER BY "GO")))::numeric, 2), ROUND(MIN("GO")::numeric, 2), ROUND((percentile_cont(0.50) WITHIN GROUP (ORDER BY "GO"))::numeric, 2), ROUND(MAX("GO")::numeric, 2), ROUND(AVG("GO")::numeric, 2) FROM public."NIRF" WHERE "Category" = '{cat}' AND "GO" IS NOT NULL{y_clause}
                UNION ALL
                SELECT 'OI (Outreach & Inclusivity)', ROUND(STDDEV("OI")::numeric, 2), ROUND(VARIANCE("OI")::numeric, 2), ROUND(((percentile_cont(0.75) WITHIN GROUP (ORDER BY "OI")) - (percentile_cont(0.25) WITHIN GROUP (ORDER BY "OI")))::numeric, 2), ROUND(MIN("OI")::numeric, 2), ROUND((percentile_cont(0.50) WITHIN GROUP (ORDER BY "OI"))::numeric, 2), ROUND(MAX("OI")::numeric, 2), ROUND(AVG("OI")::numeric, 2) FROM public."NIRF" WHERE "Category" = '{cat}' AND "OI" IS NOT NULL{y_clause}
            ) AS v
            ORDER BY std_dev DESC""",
            True,
        )

    # Q6.4: How do the median and interquartile range of scores change over time?
    if re.search(
        r"median\s+and\s+interquartile\s+range\s+(?:of\s+scores\s+)?change\s+over\s+time",
        q, re.IGNORECASE,
    ):
        return (
            f"""SELECT "Year",
                   "Category",
                   COUNT(*) AS institutions,
                   ROUND((percentile_cont(0.25) WITHIN GROUP (ORDER BY "Score"))::numeric, 2) AS p25_score,
                   ROUND((percentile_cont(0.50) WITHIN GROUP (ORDER BY "Score"))::numeric, 2) AS median_score,
                   ROUND((percentile_cont(0.75) WITHIN GROUP (ORDER BY "Score"))::numeric, 2) AS p75_score,
                   ROUND(((percentile_cont(0.75) WITHIN GROUP (ORDER BY "Score")) - (percentile_cont(0.25) WITHIN GROUP (ORDER BY "Score")))::numeric, 2) AS iqr,
                   ROUND(AVG("Score")::numeric, 2) AS mean_score
            FROM public."NIRF"
            WHERE "Category" = '{cat}' AND "Score" IS NOT NULL
            GROUP BY "Year", "Category"
            ORDER BY "Year" ASC""",
            True,
        )

    # Q6.5: How does the score distribution differ across states?
    if re.search(
        r"score\s+distribution\s+differ\s+across\s+states",
        q, re.IGNORECASE,
    ):
        return (
            f"""SELECT "State",
                   COUNT(*) AS institutions,
                   ROUND(AVG("Score")::numeric, 2) AS avg_score,
                   ROUND((percentile_cont(0.50) WITHIN GROUP (ORDER BY "Score"))::numeric, 2) AS median_score,
                   ROUND(((percentile_cont(0.75) WITHIN GROUP (ORDER BY "Score")) - (percentile_cont(0.25) WITHIN GROUP (ORDER BY "Score")))::numeric, 2) AS iqr,
                   ROUND(STDDEV("Score")::numeric, 2) AS std_dev,
                   ROUND(MIN("Score")::numeric, 2) AS min_score,
                   ROUND(MAX("Score")::numeric, 2) AS max_score
            FROM public."NIRF"
            WHERE "Category" = '{cat}' AND "Year" = {year_sql} AND "Score" IS NOT NULL AND "State" IS NOT NULL
            GROUP BY "State"
            ORDER BY median_score DESC, avg_score DESC""",
            True,
        )

    # ── 7. Ranking Transitions & Institutional Mobility ──────────────────────

    # Q7.1: How many institutions moved from the 51–100 band into the top 50 between two selected years?
    if re.search(
        r"moved\s+from\s+the\s+51[–\-]100\s+band\s+into\s+the\s+top\s+50",
        q, re.IGNORECASE,
    ):
        y1 = years[0] if len(years) >= 2 else 2024
        y2 = years[-1] if len(years) >= 2 else 2025
        return (
            f"""SELECT n."Institution_ID",
                   n."Institution_Name",
                   n."State",
                   n."Category",
                   o."Year" AS from_year,
                   o."Rank_Numeric" AS previous_rank,
                   n."Year" AS to_year,
                   n."Rank_Numeric" AS new_rank,
                   (o."Rank_Numeric" - n."Rank_Numeric") AS places_gained,
                   ROUND((n."Score" - o."Score")::numeric, 2) AS score_gain
            FROM public."NIRF" n
            JOIN public."NIRF" o
              ON n."Institution_ID" = o."Institution_ID"
             AND n."Category" = o."Category"
            WHERE n."Category" = '{cat}'
              AND o."Year" = {y1} AND n."Year" = {y2}
              AND o."Rank_Numeric" BETWEEN 51 AND 100
              AND n."Rank_Numeric" BETWEEN 1 AND 50
            ORDER BY n."Rank_Numeric" ASC""",
            True,
        )

    # Q7.2: Which institutions entered or exited the top 10 between consecutive years?
    if re.search(
        r"entered\s+or\s+exited\s+the\s+top\s*(\d+)\s+between\s+consecutive\s+years",
        q, re.IGNORECASE,
    ):
        m = re.search(r"top\s*(\d+)", q, re.IGNORECASE)
        top_n = int(m.group(1)) if m else 10
        return (
            f"""WITH paired AS (
                SELECT n."Institution_ID",
                       n."Institution_Name",
                       n."Category",
                       o."Year" AS prev_year,
                       n."Year" AS curr_year,
                       o."Rank_Numeric" AS prev_rank,
                       n."Rank_Numeric" AS curr_rank,
                       CASE
                           WHEN o."Rank_Numeric" > {top_n} AND n."Rank_Numeric" <= {top_n} THEN 'Entered Top {top_n}'
                           WHEN o."Rank_Numeric" <= {top_n} AND n."Rank_Numeric" > {top_n} THEN 'Exited Top {top_n}'
                       END AS transition
                FROM public."NIRF" n
                JOIN public."NIRF" o
                  ON n."Institution_ID" = o."Institution_ID"
                 AND n."Category" = o."Category"
                 AND n."Year" = o."Year" + 1
                WHERE n."Category" = '{cat}'
                  AND ((o."Rank_Numeric" > {top_n} AND n."Rank_Numeric" <= {top_n})
                       OR (o."Rank_Numeric" <= {top_n} AND n."Rank_Numeric" > {top_n}))
            )
            SELECT "Institution_Name", "Category", prev_year, curr_year, prev_rank, curr_rank, transition
            FROM paired
            ORDER BY curr_year DESC, transition ASC, curr_rank ASC""",
            True,
        )

    # Q7.3: What percentage of institutions remained in the same rank band from one year to the next?
    if re.search(
        r"percentage\s+of\s+institutions\s+remained\s+in\s+the\s+same\s+rank\s+band",
        q, re.IGNORECASE,
    ):
        return (
            f"""WITH banded AS (
                SELECT "Institution_ID",
                       "Category",
                       "Year",
                       CASE
                           WHEN "Rank_Numeric" BETWEEN 1 AND 10 THEN '1–10'
                           WHEN "Rank_Numeric" BETWEEN 11 AND 25 THEN '11–25'
                           WHEN "Rank_Numeric" BETWEEN 26 AND 50 THEN '26–50'
                           WHEN "Rank_Numeric" BETWEEN 51 AND 100 THEN '51–100'
                           ELSE '101+'
                       END AS rank_band
                FROM public."NIRF"
                WHERE "Category" = '{cat}' AND "Rank_Numeric" IS NOT NULL
            )
            SELECT o."Year" || ' → ' || n."Year" AS year_transition,
                   n."Year" AS "Year",
                   COUNT(*) AS returning_institutions,
                   COUNT(*) FILTER (WHERE o.rank_band = n.rank_band) AS same_band_count,
                   ROUND(100.0 * COUNT(*) FILTER (WHERE o.rank_band = n.rank_band) / NULLIF(COUNT(*), 0), 2) AS pct_same_band,
                   ROUND(100.0 * COUNT(*) FILTER (WHERE o.rank_band <> n.rank_band) / NULLIF(COUNT(*), 0), 2) AS pct_changed_band
            FROM banded n
            JOIN banded o
              ON n."Institution_ID" = o."Institution_ID"
             AND n."Category" = o."Category"
             AND n."Year" = o."Year" + 1
            GROUP BY o."Year", n."Year"
            ORDER BY "Year" ASC""",
            True,
        )

    # Q7.4: Which institutions experienced the largest upward and downward rank movements?
    if re.search(
        r"largest\s+upward\s+and\s+downward\s+rank\s+movements?",
        q, re.IGNORECASE,
    ):
        return (
            f"""WITH yoy AS (
                SELECT n."Institution_ID",
                       n."Institution_Name",
                       n."State",
                       o."Year" AS prev_year,
                       n."Year" AS curr_year,
                       o."Rank_Numeric" AS prev_rank,
                       n."Rank_Numeric" AS curr_rank,
                       (o."Rank_Numeric" - n."Rank_Numeric") AS rank_change
                FROM public."NIRF" n
                JOIN public."NIRF" o
                  ON n."Institution_ID" = o."Institution_ID"
                 AND n."Category" = o."Category"
                 AND n."Year" = o."Year" + 1
                WHERE n."Category" = '{cat}'
                  AND o."Rank_Numeric" IS NOT NULL AND n."Rank_Numeric" IS NOT NULL
            )
            SELECT "Institution_Name", "State", prev_year, curr_year, prev_rank, curr_rank, rank_change,
                   ABS(rank_change) AS abs_movement,
                   CASE WHEN rank_change > 0 THEN 'Upward (Improved)' ELSE 'Downward (Declined)' END AS direction
            FROM yoy
            WHERE rank_change <> 0
            ORDER BY abs_movement DESC
            LIMIT 30""",
            True,
        )

    # Q7.5: How many institutions moved up, moved down, or retained their positions each year?
    if re.search(
        r"moved\s+up,\s*moved\s+down,\s*or\s+retained\s+their\s+positions",
        q, re.IGNORECASE,
    ):
        return (
            f"""SELECT o."Year" || ' → ' || n."Year" AS year_transition,
                   n."Year" AS "Year",
                   COUNT(*) FILTER (WHERE n."Rank_Numeric" < o."Rank_Numeric") AS moved_up,
                   COUNT(*) FILTER (WHERE n."Rank_Numeric" > o."Rank_Numeric") AS moved_down,
                   COUNT(*) FILTER (WHERE n."Rank_Numeric" = o."Rank_Numeric") AS retained_position,
                   COUNT(*) AS total_returning
            FROM public."NIRF" n
            JOIN public."NIRF" o
              ON n."Institution_ID" = o."Institution_ID"
             AND n."Category" = o."Category"
             AND n."Year" = o."Year" + 1
            WHERE n."Category" = '{cat}'
              AND o."Rank_Numeric" IS NOT NULL AND n."Rank_Numeric" IS NOT NULL
            GROUP BY o."Year", n."Year"
            ORDER BY "Year" ASC""",
            True,
        )

    # ── 8. Outlier Detection & Performance Gaps ──────────────────────────────

    # Q8.1: Which institutions have unusually high research scores relative to their overall scores?
    if re.search(
        r"unusually\s+high\s+research\s+scores?\s+relative\s+to\s+(?:their\s+)?overall\s+scores?",
        q, re.IGNORECASE,
    ):
        return (
            f"""SELECT "Institution_ID", "Institution_Name", "Year", "Category", "Rank_Numeric",
                   "RPC", "Score", ROUND(("RPC" - "Score")::numeric, 2) AS rpc_over_overall_gap, "State", "City"
            FROM public."NIRF"
            WHERE "Category" = '{cat}' AND "Year" = {year_sql}
              AND "RPC" IS NOT NULL AND "Score" IS NOT NULL AND "RPC" > "Score"
            ORDER BY rpc_over_overall_gap DESC
            LIMIT 25""",
            True,
        )

    # Q8.3: Which institutions experienced an unusually large year-to-year score change?
    if re.search(
        r"unusually\s+large\s+year[- ]to[- ]year\s+score\s+change",
        q, re.IGNORECASE,
    ):
        return (
            f"""WITH yoy AS (
                SELECT n."Institution_ID",
                       n."Institution_Name",
                       n."Category",
                       o."Year" AS prev_year,
                       n."Year" AS curr_year,
                       ROUND(o."Score"::numeric, 2) AS prev_score,
                       ROUND(n."Score"::numeric, 2) AS curr_score,
                       ROUND((n."Score" - o."Score")::numeric, 2) AS score_change,
                       ROUND(ABS(n."Score" - o."Score")::numeric, 2) AS abs_score_change
                FROM public."NIRF" n
                JOIN public."NIRF" o
                  ON n."Institution_ID" = o."Institution_ID"
                 AND n."Category" = o."Category"
                 AND n."Year" = o."Year" + 1
                WHERE n."Category" = '{cat}'
                  AND o."Score" IS NOT NULL AND n."Score" IS NOT NULL
            )
            SELECT "Institution_Name", "Category", prev_year, curr_year, prev_score, curr_score, score_change, abs_score_change
            FROM yoy
            ORDER BY abs_score_change DESC
            LIMIT 25""",
            True,
        )

    # Q8.4: Which institutions have a strong parameter score but a relatively poor overall rank?
    if re.search(
        r"strong\s+parameter\s+score\s+but\s+a\s+(?:relatively\s+)?poor\s+overall\s+rank",
        q, re.IGNORECASE,
    ):
        return (
            f"""SELECT "Institution_ID", "Institution_Name", "Year", "Category", "Rank_Numeric", "Score",
                   ROUND(GREATEST("TLR", "RPC", "GO", "OI", "Perception")::numeric, 2) AS best_parameter_score,
                   "TLR", "RPC", "GO", "OI", "Perception", "State"
            FROM public."NIRF"
            WHERE "Category" = '{cat}' AND "Year" = {year_sql}
              AND "Rank_Numeric" > 50
              AND GREATEST("TLR", "RPC", "GO", "OI", "Perception") >= 70
            ORDER BY best_parameter_score DESC, "Rank_Numeric" DESC
            LIMIT 25""",
            True,
        )

    # Q8.5: Which institutions have unusually high ranking volatility compared with similar institutions?
    if re.search(
        r"unusually\s+high\s+ranking\s+volatility",
        q, re.IGNORECASE,
    ):
        return (
            f"""SELECT "Institution_ID",
                   MAX("Institution_Name") AS "Institution_Name",
                   MAX("State") AS "State",
                   COUNT(DISTINCT "Year") AS years_ranked,
                   MIN("Rank_Numeric") AS best_rank,
                   MAX("Rank_Numeric") AS worst_rank,
                   (MAX("Rank_Numeric") - MIN("Rank_Numeric")) AS rank_span,
                   ROUND(STDDEV("Rank_Numeric")::numeric, 2) AS rank_volatility_stddev,
                   ROUND(AVG("Rank_Numeric")::numeric, 1) AS avg_rank
            FROM public."NIRF"
            WHERE "Category" = '{cat}' AND "Rank_Numeric" IS NOT NULL
            GROUP BY "Institution_ID"
            HAVING COUNT(DISTINCT "Year") >= 4
            ORDER BY rank_volatility_stddev DESC, rank_span DESC
            LIMIT 25""",
            True,
        )

    return None
