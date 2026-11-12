"""
SQL normalization and validation for LLM-generated or template SQL.

Safety model (defence in depth):
1. Only a single read-only query is accepted: SELECT, WITH ... SELECT, or a
   UNION/INTERSECT/EXCEPT of SELECTs.
2. Only public."NIRF" may be read (CTE names defined inside the query are
   allowed as references, their bodies are validated like everything else).
3. Only whitelisted columns (or aliases defined in the query) may be used.
4. SELECT *, DML/DDL nodes anywhere in the tree, and dangerous server
   functions are rejected.
5. A LIMIT (max 500) is always enforced.
The executor additionally runs every query in a READ ONLY transaction with a
statement timeout.
"""

import sqlglot
from sqlglot import exp


ALLOWED_TABLE = "NIRF"
ALLOWED_SCHEMA = "public"
MAX_LIMIT = 500
ALLOWED_COLUMNS = {
    "Year",
    "Category",
    "Institution_ID",
    "Institution_Name",
    "City",
    "State",
    "Score",
    "Score_Status",
    "Rank_Numeric",
    "Rank_Status",
    "Band",
    # NIRF parameter scores (0-100, may be NULL)
    "TLR",
    "RPC",
    "GO",
    "OI",
    "Perception",
}

_QUERY_TYPES = (exp.Select, exp.Union, exp.Intersect, exp.Except)

_FORBIDDEN_NODES = tuple(
    getattr(exp, name)
    for name in (
        "Insert", "Update", "Delete", "Drop", "Create", "Alter", "Merge",
        "Command", "Into", "Copy", "Grant", "TruncateTable", "Set", "Lock",
    )
    if hasattr(exp, name)
)

_FORBIDDEN_FUNCTIONS = {
    "pg_sleep", "pg_sleep_for", "pg_sleep_until", "pg_read_file",
    "pg_read_binary_file", "pg_ls_dir", "pg_stat_file", "lo_import",
    "lo_export", "lo_get", "dblink", "dblink_exec", "set_config",
    "current_setting", "pg_terminate_backend", "pg_cancel_backend",
    "pg_reload_conf", "query_to_xml", "query_to_json", "pg_advisory_lock",
}


class SQLValidationError(ValueError):
    """Raised when a query violates the read-only safety rules."""


def _parse_single(query: str) -> exp.Expression:
    try:
        parsed = [p for p in sqlglot.parse(query, read="postgres") if p is not None]
    except sqlglot.errors.ParseError as exc:
        raise SQLValidationError(f"SQL could not be parsed: {exc}") from exc
    if len(parsed) != 1:
        raise SQLValidationError("Only one SQL statement is allowed")
    return parsed[0]


def _cte_names(statement: exp.Expression) -> set[str]:
    return {cte.alias_or_name for cte in statement.find_all(exp.CTE)}


def _aliases(statement: exp.Expression) -> set[str]:
    names = set()
    for node in statement.find_all(exp.Alias):
        if node.alias:
            names.add(node.alias.casefold())
    for node in statement.find_all(exp.TableAlias):
        for col in node.columns or []:
            names.add(col.name.casefold())
    return names


def normalize_sql(query: str) -> str:
    """Canonicalise identifiers and enforce a LIMIT. Returns the input unchanged
    if it cannot be parsed (validation will then reject it)."""
    try:
        statement = _parse_single(query)
    except SQLValidationError:
        return query
    if not isinstance(statement, _QUERY_TYPES):
        return query

    canonical_columns = {column.casefold(): column for column in ALLOWED_COLUMNS}
    aliases = _aliases(statement)

    for column in statement.find_all(exp.Column):
        canonical_name = canonical_columns.get(column.name.casefold())
        if canonical_name is not None and column.name.casefold() not in aliases:
            column.set("this", exp.to_identifier(canonical_name, quoted=True))

    for table in statement.find_all(exp.Table):
        if table.name.casefold() == ALLOWED_TABLE.casefold():
            table.set("this", exp.to_identifier(ALLOWED_TABLE, quoted=True))

    limit = statement.args.get("limit")
    if limit is None:
        statement.set("limit", exp.Limit(expression=exp.Literal.number(MAX_LIMIT)))
    else:
        limit_value = limit.args.get("expression")
        if not isinstance(limit_value, exp.Literal) or not limit_value.is_int:
            statement.set("limit", exp.Limit(expression=exp.Literal.number(MAX_LIMIT)))
        elif int(limit_value.this) > MAX_LIMIT:
            limit_value.replace(exp.Literal.number(MAX_LIMIT))

    return statement.sql(dialect="postgres")


def validate_sql(query: str) -> bool:
    statement = _parse_single(query)
    if not isinstance(statement, _QUERY_TYPES):
        raise SQLValidationError("Only SELECT queries are allowed")

    for node in statement.walk():
        if _FORBIDDEN_NODES and isinstance(node, _FORBIDDEN_NODES):
            raise SQLValidationError(
                f"Statement type not allowed: {type(node).__name__}"
            )
        if isinstance(node, (exp.Anonymous, exp.Func)):
            name = (
                node.name if isinstance(node, exp.Anonymous) else node.sql_name()
            ).casefold()
            if name in _FORBIDDEN_FUNCTIONS:
                raise SQLValidationError(f"Function not allowed: {name}")

    for select in statement.find_all(exp.Select):
        if any(isinstance(p, exp.Star) for p in select.expressions):
            raise SQLValidationError("SELECT * is not allowed")
        if any(
            isinstance(p, exp.Column) and isinstance(p.this, exp.Star)
            for p in select.expressions
        ):
            raise SQLValidationError("SELECT table.* is not allowed")

    ctes = _cte_names(statement)
    tables = list(statement.find_all(exp.Table))
    if not tables:
        raise SQLValidationError("Query must read from the NIRF table")
    reads_nirf = False
    for table in tables:
        if table.name in ctes and not table.db:
            continue
        if table.name != ALLOWED_TABLE:
            raise SQLValidationError(f"Access to table '{table.name}' is not allowed")
        if table.db and table.db != ALLOWED_SCHEMA:
            raise SQLValidationError(f"Access to schema '{table.db}' is not allowed")
        if table.catalog:
            raise SQLValidationError("Cross-database references are not allowed")
        reads_nirf = True
    if not reads_nirf:
        raise SQLValidationError("Query must read from the NIRF table")

    aliases = _aliases(statement)
    for column in statement.find_all(exp.Column):
        if isinstance(column.this, exp.Star):
            continue
        if column.name not in ALLOWED_COLUMNS and column.name.casefold() not in aliases:
            raise SQLValidationError(f"Column is not available: {column.name}")

    return True
