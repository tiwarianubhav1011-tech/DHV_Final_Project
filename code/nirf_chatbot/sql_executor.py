import logging

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, DBAPIError

from nirf_chatbot.database import engine
from nirf_chatbot.sql_validator import MAX_LIMIT, normalize_sql, validate_sql

log = logging.getLogger("nirf_chatbot.sql")


class DatabaseUnavailableError(RuntimeError):
    """The database could not be reached."""


class QueryExecutionError(RuntimeError):
    """The database rejected or failed to run a (validated) query."""


def execute_sql(query: str) -> dict:
    """Normalize, validate and run a query in a READ ONLY transaction.

    Raises SQLValidationError (a ValueError) for unsafe SQL,
    DatabaseUnavailableError for connection problems and
    QueryExecutionError for SQL the database rejects.
    """
    query = normalize_sql(query)
    validate_sql(query)
    try:
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                connection.execute(text("SET LOCAL statement_timeout = '5s'"))
                result = connection.execute(text(query))
                columns = list(result.keys())
                rows = result.mappings().fetchmany(MAX_LIMIT + 1)
    except OperationalError as exc:
        log.exception("Database connection failed for query: %s", query)
        if "timeout" in str(exc).casefold() or "canceling statement" in str(exc).casefold():
            raise QueryExecutionError("The query took too long (5s limit).") from exc
        raise DatabaseUnavailableError(
            "Could not connect to the NIRF database. Check DATABASE_URL and your network."
        ) from exc
    except DBAPIError as exc:
        log.warning("Database rejected query: %s | %s", query, exc.orig)
        raise QueryExecutionError(str(getattr(exc, "orig", exc)).strip()) from exc

    truncated = len(rows) > MAX_LIMIT
    return {
        "columns": columns,
        "rows": [dict(row) for row in rows[:MAX_LIMIT]],
        "truncated": truncated,
        "sql": query,
    }
