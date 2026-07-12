"""ActionExecutor: execute ActionPlans with Sagas compensation rollback + optimistic locking."""
from __future__ import annotations
import json
import logging
from datetime import datetime
from dataclasses import dataclass, field

from sqlalchemy import text

_log = logging.getLogger('action_executor')


@dataclass
class ExecutionResult:
    success: bool = False
    error: str = ""
    compensated_steps: int = 0
    outcome_id: str = ""
    is_replay: bool = False
    details: list[dict] = field(default_factory=list)


@dataclass
class CompensationRecord:
    step_index: int
    tool: str
    reverse_params: dict


class CompensationError(Exception):
    """Compensation itself failed (worst case)."""


class ActionExecutor:
    """Execute ActionPlan with Sagas compensation rollback.

    Flow:
        1. Execute steps sequentially
        2. Record compensation after each successful step
        3. On failure: reverse-execute compensations (LIFO)
        4. On rollback: check optimistic lock (updated_at), dead-letter on mismatch
    """

    def __init__(self, db=None):
        self.db = db
        self._compensations: list[CompensationRecord] = []

    def execute_plan(self, plan, im_chat_id: str = "") -> ExecutionResult:
        """Execute an ActionPlan. Auto-rollback on failure."""
        if not hasattr(plan, 'steps'):
            return ExecutionResult(success=False, error="Invalid plan: no steps attribute")

        self._compensations = []
        try:
            for i, step in enumerate(plan.steps):
                result = self._call_step(step)
                if isinstance(result, dict) and not result.get("success", True):
                    compensation_count = self._sagas_rollback()
                    return ExecutionResult(
                        success=False,
                        error=f"Step {i+1}/{len(plan.steps)} ({step.tool}): {result.get('error', 'unknown')}",
                        compensated_steps=compensation_count,
                        details=[{"step": i, "tool": step.tool, "result": result}],
                    )
                self._record_compensation(i, step, result)

            self._compensations.clear()
            return ExecutionResult(success=True)

        except Exception as e:
            self._sagas_rollback()
            return ExecutionResult(success=False, error=str(e), compensated_steps=len(self._compensations))

    def _call_step(self, step) -> dict:
        from core.agent.tool_registry import ToolRegistry
        from core.agent.tools.primitives import register
        reg = ToolRegistry()
        register(reg)
        return reg.call(step.tool, **step.params)

    def _record_compensation(self, step_index: int, step, result):
        """Record compensation info after a successful step."""
        params = step.params if hasattr(step, 'params') else step.get("params", {})
        reverse = params.get("reverse")
        if reverse:
            self._compensations.append(CompensationRecord(
                step_index=step_index,
                tool="execute_write",
                reverse_params=reverse,
            ))
        elif hasattr(step, 'tool') and step.tool == "call_api":
            self._compensations.append(CompensationRecord(
                step_index=step_index,
                tool="sync_queue_record",
                reverse_params={"api_call": params, "result": result},
            ))

    def _sagas_rollback(self) -> int:
        """Reverse compensation chain (LIFO). Returns count of compensated steps."""
        compensated = 0
        for rec in reversed(self._compensations):
            try:
                if rec.tool == "execute_write":
                    self._safe_reverse_write(rec.reverse_params)
                    compensated += 1
                elif rec.tool == "sync_queue_record":
                    self._write_dead_letter(rec.reverse_params)
            except CompensationError as e:
                _log.critical(f"CRITICAL ROLLBACK FAILURE step={rec.step_index}: {e}")
                self._write_dead_letter({"step_index": rec.step_index, "tool": rec.tool,
                                         "params": rec.reverse_params, "reason": str(e)})
                break  # Stop on compensation failure to prevent cascade
        return compensated

    def _safe_reverse_write(self, reverse_params: dict) -> bool:
        """Execute reverse write with optimistic lock check. Bypasses execute_write tool
        (compensation is terminal — the reverse of the reverse IS the original operation).

        If condition includes updated_at: verify it matches current DB value.
        Mismatch → dead-letter (someone else modified the record), no overwrite.
        """
        from core.db import get_engine
        from sqlalchemy import text

        condition = reverse_params.get("condition", {})
        table = reverse_params.get("table", "")
        if "updated_at" not in condition:
            condition = self._enrich_with_updated_at(table, condition)
            reverse_params["condition"] = condition

        if condition.get("updated_at"):
            engine = get_engine()
            with engine.connect() as conn:
                where = " AND ".join(f"{k} = :{k}" for k in condition.keys() if k != "updated_at")
                where += " AND updated_at = :updated_at"
                current = conn.execute(
                    text(f"SELECT updated_at FROM {table} WHERE {where} LIMIT 1"), condition
                ).fetchone()

                if not current:
                    reason = f"OLOCK: record missing {table}.{condition}"
                    self._write_dead_letter({"table": table, "condition": condition, "reason": reason})
                    raise CompensationError(reason)

        # Execute the reverse write directly against DB
        engine = get_engine()
        operation = reverse_params.get("operation", "delete")
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with engine.begin() as conn:
            if operation == "delete":
                where_clause = " AND ".join(f"{k} = :{k}" for k in condition.keys())
                conn.execute(text(f"DELETE FROM {table} WHERE {where_clause}"), condition)
            elif operation == "update":
                data = reverse_params.get("data", {})
                set_clause = ", ".join(f"{k} = :{k}" for k in data.keys())
                where_clause = " AND ".join(f"{k} = :c_{k}" for k in condition.keys())
                params = {**data, **{f"c_{k}": v for k, v in condition.items()}}
                conn.execute(text(f"UPDATE {table} SET {set_clause} WHERE {where_clause}"), params)
            elif operation == "insert":
                data = reverse_params.get("data", {})
                data_with_ts = {**data, "updated_at": now}
                columns = ", ".join(data_with_ts.keys())
                placeholders = ", ".join(f":{k}" for k in data_with_ts.keys())
                conn.execute(text(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"), data_with_ts)

        return True

    def _enrich_with_updated_at(self, table: str, condition: dict) -> dict:
        """Fetch current updated_at from DB and add to condition."""
        from core.db import get_engine
        engine = get_engine()
        with engine.connect() as conn:
            where = " AND ".join(f"{k} = :{k}" for k in condition.keys())
            row = conn.execute(
                text(f"SELECT updated_at FROM {table} WHERE {where} LIMIT 1"), condition
            ).fetchone()
            if row and row[0]:
                condition["updated_at"] = str(row[0])
        return condition

    def _write_dead_letter(self, data: dict):
        """Write to sync_dead_letter (existing table) + critical_rollback_failure."""
        from core.db import get_engine
        engine = get_engine()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO critical_rollback_failure (step_index, tool, params, error, logged_at)
                    VALUES (:si, :tool, :params, :error, :now)
                """), {
                    "si": data.get("step_index", 0),
                    "tool": data.get("tool", str(data.get("table", "unknown"))),
                    "params": json.dumps(data, ensure_ascii=False),
                    "error": data.get("reason", "rollback failure"),
                    "now": now,
                })
        except Exception as e:
            _log.error(f"Failed to write dead letter: {e}")
