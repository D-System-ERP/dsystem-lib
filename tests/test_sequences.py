from uuid import UUID

from sqlalchemy import Insert, Select, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError, NoResultFound

from dsystem.sequences import START_NUMBER, TENANT_SCOPE, SequenceBase, format_code, next_number

KEY = ("organization_id", "legal_entity_id", "kind", "prefix")
ORG = UUID("11111111-1111-1111-1111-111111111111")
ENTITY = UUID("22222222-2222-2222-2222-222222222222")


class CounterSequence(SequenceBase):
    __tablename__ = "counter_sequences"
    __table_args__ = (UniqueConstraint(*KEY),)


class _Result:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row

    def scalar_one(self):
        if self._row is None:
            raise NoResultFound("no sequence row")
        return self._row


class PostgresLikeSession:
    def __init__(self, *, stored=None, racer=None):
        self.stored = stored
        self.racer = racer
        self.statements: list = []
        self._unflushed: list = []

    def _sql(self, stmt) -> str:
        return str(stmt.compile(dialect=postgresql.dialect()))

    def _write_attempt(self) -> bool:
        if self.racer is not None:
            self.stored, self.racer = self.racer, None
        return self.stored is not None

    async def execute(self, stmt):
        self.statements.append(stmt)
        if isinstance(stmt, Select):
            return _Result(self.stored)
        if isinstance(stmt, Insert):
            if self._write_attempt():
                if f"ON CONFLICT ({', '.join(KEY)}) DO NOTHING" not in self._sql(stmt):
                    raise IntegrityError(self._sql(stmt), {}, Exception("duplicate key value"))
                return _Result(None)
            params = stmt.compile(dialect=postgresql.dialect()).params
            self.stored = CounterSequence(**{column: params[column] for column in (*KEY, "last_number")})
            return _Result(None)
        raise AssertionError(f"unexpected statement {stmt!r}")

    def add(self, obj):
        self._unflushed.append(obj)

    async def flush(self):
        pending, self._unflushed = self._unflushed, []
        for obj in pending:
            if self._write_attempt():
                raise IntegrityError("INSERT INTO counter_sequences", {}, Exception("duplicate key value"))
            self.stored = obj


def _row(last_number: int, legal_entity_id: UUID = TENANT_SCOPE) -> CounterSequence:
    return CounterSequence(
        organization_id=ORG, legal_entity_id=legal_entity_id, kind="invoice", prefix="SA", last_number=last_number
    )


def test_format_code_with_and_without_entity_prefix():
    assert format_code("SA", 10001) == "SA10001"
    assert format_code("SA", 10001, "ABC") == "ABC-SA10001"
    assert format_code("P", START_NUMBER + 1, None) == "P10001"


def test_tenant_scope_is_the_nil_uuid():
    assert str(TENANT_SCOPE) == "00000000-0000-0000-0000-000000000000"


async def test_concurrent_first_call_takes_the_next_number_instead_of_failing():
    db = PostgresLikeSession(racer=_row(START_NUMBER + 1))
    assert await next_number(db, CounterSequence, ORG, "invoice", "SA") == START_NUMBER + 2


async def test_first_call_creates_the_row_in_the_requested_scope():
    db = PostgresLikeSession()
    assert await next_number(db, CounterSequence, ORG, "invoice", "SA", legal_entity_id=ENTITY) == START_NUMBER + 1
    assert (db.stored.organization_id, db.stored.legal_entity_id, db.stored.kind, db.stored.prefix) == (
        ORG,
        ENTITY,
        "invoice",
        "SA",
    )
    assert isinstance(db.statements[-1], Select)
    assert "FOR UPDATE" in db._sql(db.statements[-1])


async def test_existing_row_is_locked_and_incremented_without_an_insert():
    db = PostgresLikeSession(stored=_row(START_NUMBER + 41))
    assert await next_number(db, CounterSequence, ORG, "invoice", "SA") == START_NUMBER + 42
    assert len(db.statements) == 1
    assert isinstance(db.statements[0], Select)
    assert "FOR UPDATE" in db._sql(db.statements[0])
