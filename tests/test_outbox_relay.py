from datetime import timedelta

import pytest
from sqlalchemy import Select
from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import BinaryExpression, BindParameter, BooleanClauseList, Grouping
from sqlalchemy.sql.schema import Column

from dsystem.events import outbox
from dsystem.events.outbox import RECLAIM_AFTER_SECONDS, RELAY_GRACE_SECONDS, RELAY_MAX_ATTEMPTS
from dsystem.utils.timezone import utc_now


class _Result:
    rowcount = 0

    def all(self):
        return []


class RecordingSession:
    def __init__(self, statements: list):
        self.statements = statements

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _Result()

    async def commit(self):
        pass


def _evaluate(clause, row: dict):
    if isinstance(clause, Grouping):
        return _evaluate(clause.element, row)
    if isinstance(clause, BooleanClauseList):
        values = [_evaluate(child, row) for child in clause.clauses]
        return all(values) if clause.operator is operators.and_ else any(values)
    if isinstance(clause, BinaryExpression):
        return clause.operator(_evaluate(clause.left, row), _evaluate(clause.right, row))
    if isinstance(clause, Column):
        return row[clause.key]
    if isinstance(clause, BindParameter):
        return clause.value
    raise TypeError(f"unsupported clause {clause!r}")


async def _claim_filter(monkeypatch):
    monkeypatch.setattr(outbox, "_publisher_ready", lambda: True)
    statements: list = []
    await outbox.relay_once(lambda: RecordingSession(statements))
    (claim,) = [stmt for stmt in statements if isinstance(stmt, Select)]
    return claim.whereclause


def _row(*, status="pending", attempts=0, created_ago=3600, updated_ago=3600):
    now = utc_now()
    return {
        "status": status,
        "attempts": attempts,
        "created_at": now - timedelta(seconds=created_ago),
        "updated_at": now - timedelta(seconds=updated_ago),
    }


@pytest.mark.parametrize(
    ("row", "due"),
    [
        (_row(), True),
        (_row(attempts=RELAY_MAX_ATTEMPTS - 1, updated_ago=1), True),
        (_row(created_ago=RELAY_GRACE_SECONDS // 2, updated_ago=1), False),
        (_row(status="published"), False),
        (_row(status="publishing"), False),
        (_row(attempts=RELAY_MAX_ATTEMPTS, updated_ago=RECLAIM_AFTER_SECONDS + 60), True),
        (_row(attempts=RELAY_MAX_ATTEMPTS + 5, updated_ago=RECLAIM_AFTER_SECONDS + 60), True),
        (_row(attempts=RELAY_MAX_ATTEMPTS, updated_ago=RECLAIM_AFTER_SECONDS - 60), False),
    ],
    ids=[
        "fresh-pending",
        "retrying-below-cap",
        "inside-grace",
        "published",
        "publishing",
        "exhausted-after-backoff",
        "long-exhausted-after-backoff",
        "exhausted-during-backoff",
    ],
)
async def test_relay_claims_due_rows_and_retries_exhausted_ones_slowly(monkeypatch, row, due):
    claim_filter = await _claim_filter(monkeypatch)
    assert _evaluate(claim_filter, row) is due
