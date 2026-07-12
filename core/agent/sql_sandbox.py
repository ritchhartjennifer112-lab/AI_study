"""SQL sandbox: three-level protection for LLM-generated queries — AST whitelist → Cost Guard → Row Guard."""
from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlalchemy import text

ROWS_SOFT_LIMIT = 200
ROWS_HARD_LIMIT = 5000
COST_HARD_LIMIT = 50000.0
STATEMENT_TIMEOUT_MS = 3000

FORBIDDEN_CLAUSES = ["FOR UPDATE", "FOR SHARE", "NOWAIT", "SKIP LOCKED"]


class QueryRejectedError(ValueError):
    """SQL rejected by sandbox."""


# ── Level 1: AST whitelist ──

def validate_sql(sql: str) -> None:
    """Check that `sql` is a safe SELECT-only query.

    Rejects:
      - Non-SELECT/CTE statements (INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE)
      - SELECT INTO
      - FOR UPDATE / FOR SHARE / NOWAIT / SKIP LOCKED clauses
      - Custom (anonymous) functions
      - Unparseable SQL
    """
    sql_upper = sql.upper()
    for kw in FORBIDDEN_CLAUSES:
        if kw in sql_upper:
            raise QueryRejectedError(f"SQL contains forbidden clause: {kw}")

    try:
        tree = sqlglot.parse_one(sql)
    except Exception as e:
        raise QueryRejectedError(f"SQL parse error: {e}")

    if tree is None:
        raise QueryRejectedError("SQL parsed to empty tree")

    root_type = type(tree).__name__
    if root_type not in ("Select", "CTE"):
        raise QueryRejectedError(
            f"Forbidden SQL type: {root_type}. Only SELECT / WITH allowed."
        )

    # SELECT INTO check — sqlglot stores INTO in tree.args["into"]
    if tree.args.get("into"):
        raise QueryRejectedError("Forbidden: SELECT INTO")

    # Walk entire AST for nested DML/DDL
    for node in tree.walk():
        ntype = type(node).__name__
        if ntype in ("Insert", "Update", "Delete", "Drop", "Create", "Alter", "Truncate"):
            raise QueryRejectedError(f"Forbidden: {ntype}")

    # Reject anonymous / custom functions (anything not in sqlglot's built-in set)
    for node in tree.find_all(exp.Anonymous):
        name = node.name.upper() if node.name else "unknown"
        raise QueryRejectedError(f"Forbidden custom function: {name}()")


# ── Level 2: Cost Guard ──

def check_cost(plan: dict, cost_limit: float = COST_HARD_LIMIT) -> None:
    """Reject query if the PostgreSQL planner projects total cost above `cost_limit`.

    `plan` is the raw list/dict returned by ``EXPLAIN (FORMAT JSON) sql``.
    """
    try:
        total_cost = float(plan[0]["Plan"]["Total Cost"])
    except (KeyError, IndexError, TypeError):
        return  # plan malformed — let it through (DB will catch real errors)
    if total_cost > cost_limit:
        raise QueryRejectedError(
            f"Query cost too high ({total_cost:.0f} > {cost_limit:.0f}). "
            f"Add WHERE conditions or use aggregate_data first."
        )


# ── Level 3: Row Guard ──

def check_row_count(
    row_count: int,
    soft_limit: int = ROWS_SOFT_LIMIT,
    hard_limit: int = ROWS_HARD_LIMIT,
) -> None:
    """Reject query if estimated rows exceed the hard limit."""
    if row_count > hard_limit:
        raise QueryRejectedError(
            f"Estimated {row_count} rows exceeds hard limit {hard_limit}. "
            f"Narrow query scope."
        )


# ── Integrated: execute_with_guard ──

def execute_with_guard(
    sql: str,
    conn=None,
    soft_limit: int = ROWS_SOFT_LIMIT,
    hard_limit: int = ROWS_HARD_LIMIT,
    cost_limit: float = COST_HARD_LIMIT,
    timeout_ms: int = STATEMENT_TIMEOUT_MS,
    fetch_data: bool = True,
) -> dict:
    """Run a SQL query through all three safety levels and return results.

    Levels:
      1. AST whitelist — reject non-SELECT, custom functions, write clauses
      2. Cost Guard   — run EXPLAIN, reject if planner cost exceeds limit
      3. Row Guard    — COUNT the result set; soft limit truncates with guidance,
                         hard limit rejects

    Returns a dict:
      {'truncated': bool, 'total_rows': int, 'data': [...]}      — under soft limit
      {'truncated': True, 'total_rows': int, 'sample': [...],
       'columns': [...], 'guidance': str}                         — over soft limit
    """
    # Level 1
    validate_sql(sql)

    if conn is None:
        from core.db import get_engine

        conn = get_engine().connect()
        _own_conn = True
    else:
        _own_conn = False

    try:
        conn.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
        conn.execute(text("SET LOCAL max_parallel_workers = 0"))

        # Level 2
        plan = conn.execute(text(f"EXPLAIN (FORMAT JSON) {sql}")).scalar()
        check_cost(plan, cost_limit)

        if not fetch_data:
            return {"truncated": False, "total_rows": 0, "data": []}

        # Level 3
        count = conn.execute(text(f"SELECT COUNT(*) FROM ({sql}) _sub")).scalar()
        check_row_count(int(count), soft_limit, hard_limit)

        if count > soft_limit:
            sample = conn.execute(text(f"SELECT * FROM ({sql}) _sub LIMIT 5")).fetchall()
            columns = list(sample[0]._mapping.keys()) if sample else []
            return {
                "truncated": True,
                "total_rows": count,
                "sample": [dict(r._mapping) for r in sample],
                "columns": columns,
                "guidance": (
                    f"Query returned {count} rows (exceeds display limit {soft_limit}). "
                    f"Options:\n"
                    f"1. Use aggregate_data for grouping/aggregation\n"
                    f"2. Add more specific WHERE conditions (date, order_id, employee)\n"
                    f"3. Paginate ({soft_limit} rows per page)"
                ),
            }

        rows = conn.execute(text(sql)).fetchall()
        return {
            "truncated": False,
            "total_rows": int(count),
            "data": [dict(r._mapping) for r in rows],
        }
    finally:
        if _own_conn:
            conn.close()
