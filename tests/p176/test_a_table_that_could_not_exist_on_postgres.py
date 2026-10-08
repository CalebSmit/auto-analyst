"""P176 - a table that could not exist on Postgres.

The first time the Postgres job ever ran to the point of touching a database, it found that
one of the eight tables cannot be created there. `precedent` carried

    CheckConstraint("masked = 1 OR masked = true")

which is somebody covering both backends and covering neither. SQLite stores a boolean as 0
or 1 and compares it to an integer without complaint, so the first half worked on the only
backend anybody ran; Postgres has no `boolean = integer` operator and rejects the expression
while planning the `CREATE TABLE`, taking the whole statement with it. 130 refusals in that
run. The store is documented as being one URL away from Postgres, and one eighth of it had
never existed there.

**Why no test caught it.** `tests/p04` is the store conformance suite and it is thorough -
but its Postgres half is opt-in, skips by default, and the only machine that ever ran it was
a developer's with SQLite. The suite's own summary says so every time, in words: *SQLite
passing is not evidence the Postgres path works. This suite is green on one backend of two.*

So these do not need a server. SQLAlchemy can compile the schema for a dialect without
connecting to anything, which turns "does this DDL parse on Postgres" into a question any
machine can answer in milliseconds - and that is the question that was going unasked.
"""

from __future__ import annotations

import re

import pytest
from sqlalchemy.schema import CreateTable

from ops.models import Base

DIALECTS = ("postgresql", "sqlite")


def dialect(name: str):
    if name == "postgresql":
        from sqlalchemy.dialects.postgresql import psycopg
        return psycopg.dialect()
    from sqlalchemy.dialects.sqlite import pysqlite
    return pysqlite.dialect()


def tables():
    return sorted(Base.metadata.tables.values(), key=lambda t: t.name)


def test_the_model_has_the_tables_this_is_about() -> None:
    """A sweep that passes because the metadata moved is a sweep that has stopped."""
    names = {t.name for t in tables()}
    assert "precedent" in names, "the table this phase is named for is gone"
    assert len(names) >= 8, names


@pytest.mark.parametrize("table", tables(), ids=lambda t: t.name)
def test_each_table_is_the_same_table_on_both_backends(table) -> None:
    """The DDL SQLAlchemy would send, compared between the two.

    *Does it compile* was the first version of this and it is almost a no-op - a `CHECK`
    is emitted as the text it was given, so even one naming a column that does not exist
    compiles happily. The revert harness said so by leaving it green on exactly that.

    What can be asked is whether the two backends are being sent the same schema. Every
    constraint this store declares has to appear in both, because a store that is *one URL
    away from Postgres* and quietly drops a check on one of them is not one store.
    """
    emitted = {}
    for name in DIALECTS:
        sql = str(CreateTable(table).compile(dialect=dialect(name)))
        assert sql.strip().upper().startswith("CREATE TABLE"), name
        emitted[name] = {
            found.group(1) for found in re.finditer(r"CONSTRAINT (\w+)", sql)
        }
    assert emitted["postgresql"] == emitted["sqlite"], (
        f"{table.name} is sent different constraints: "
        f"only on Postgres {sorted(emitted['postgresql'] - emitted['sqlite'])}, "
        f"only on SQLite {sorted(emitted['sqlite'] - emitted['postgresql'])}"
    )


@pytest.mark.parametrize("table", tables(), ids=lambda t: t.name)
def test_no_check_constraint_compares_a_boolean_to_a_number(table) -> None:
    """The defect itself, said as a property of the schema rather than of the one constraint.

    Postgres has no `boolean = integer` operator. Any column declared BOOLEAN and compared
    to `0` or `1` in a CHECK is a table that cannot be created there, and the error arrives
    as a DDL failure rather than as anything resembling the mistake.
    """
    booleans = {c.name for c in table.columns if c.type.__class__.__name__ == "Boolean"}
    if not booleans:
        pytest.skip(f"{table.name} has no boolean column, so it cannot make this mistake")
    sql = str(CreateTable(table).compile(dialect=dialect("postgresql")))
    for column in booleans:
        bad = re.search(rf"\b{re.escape(column)}\s*(=|<>|!=)\s*-?\d", sql)
        assert bad is None, (
            f"{table.name}.{column} is BOOLEAN and the DDL compares it to a number "
            f"({bad.group(0) if bad else ''}); Postgres will refuse the whole CREATE TABLE"
        )


def test_the_one_that_was_wrong_is_the_expression_both_backends_parse() -> None:
    """Named, because the sweep above would also pass if the constraint were deleted - and
    the constraint is the thing that says precedent is only ever stored masked, which is one
    of this build's non-negotiables."""
    precedent = Base.metadata.tables["precedent"]
    checks = {
        c.name: str(c.sqltext)
        for c in precedent.constraints
        if c.__class__.__name__ == "CheckConstraint"
    }
    assert "precedent_is_masked" in checks, "the constraint that keeps precedent masked is gone"
    said = checks["precedent_is_masked"]
    assert "= 1" not in said, "it compares a boolean to an integer again"
    assert "true" in said.lower(), f"it no longer asserts the column is true: {said}"


@pytest.mark.parametrize("name", DIALECTS)
def test_the_whole_schema_compiles_for_each_backend(name: str) -> None:
    """All of it at once, because the failure that happened was one table refusing and the
    rest never being reached."""
    compiled = [str(CreateTable(t).compile(dialect=dialect(name))) for t in tables()]
    assert len(compiled) == len(tables())
    assert all(sql.strip().upper().startswith("CREATE TABLE") for sql in compiled)


def test_the_sqlite_this_runs_on_understands_the_keyword() -> None:
    """The limit of the fix above, asked rather than assumed.

    `masked = true` is portable between the two backends and that is why it was chosen -
    but `true` is a keyword SQLite only gained in **3.23** (2018). On anything older it
    parses as a column name and the CREATE TABLE fails, which is the same failure this
    phase is about wearing the other backend's clothes. Nothing in reach is near that
    floor; what makes it worth a test is that the defect being fixed here was exactly an
    unstated assumption about what a backend would accept.

    Asked of the interpreter, and then of the engine, because the version string being new
    enough is not the same claim as the keyword working.
    """
    import sqlite3

    version = tuple(int(part) for part in sqlite3.sqlite_version.split("."))
    assert version >= (3, 23), (
        f"this SQLite is {sqlite3.sqlite_version} and does not know the keyword `true`; "
        f"the precedent table will not create here"
    )

    live = sqlite3.connect(":memory:")
    live.execute("CREATE TABLE t (masked BOOLEAN NOT NULL, CHECK (masked = true))")
    live.execute("INSERT INTO t VALUES (1)")
    with pytest.raises(sqlite3.IntegrityError):
        live.execute("INSERT INTO t VALUES (0)")
