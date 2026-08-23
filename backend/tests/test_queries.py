"""The SQL registry itself.

The registry is not just a place to keep SQL. Two guarantees depend on it being
correct about what each statement DOES:

  * `Query.mutating` is what makes the audit invariant real. A transaction that
    ran a mutating statement and wrote no audit entry refuses to commit, and a
    read-only transaction refuses to mutate at all -- but only for statements
    the registry recognises as mutating.

  * CI runs EXPLAIN QUERY PLAN over every entry. A query the registry cannot
    see is a query nobody checked.

An earlier version tested the first physical line for INSERT/UPDATE/DELETE.
Every query here is documented, so the keyword is almost never on the first
line, and 14 of 91 -- `payments.create` among them -- were classified read-only.
The enforcement mechanism had a hole exactly where the code was best explained.
"""

from __future__ import annotations

import re

from backend.lib.queries import REGISTRY

# The keyword that opens a statement, ignoring comments and blank lines.
OPENING_KEYWORD = re.compile(r"^\s*(\w+)", re.MULTILINE)

MUTATING_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "REPLACE"}


def first_keyword(sql: str) -> str:
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        match = OPENING_KEYWORD.match(stripped)
        return match.group(1).upper() if match else ""
    return ""


def test_every_query_knows_whether_it_mutates():
    """The check that would have caught the hole.

    Compares the registry's flag against the statement's real opening keyword,
    for all of them, every run.
    """
    wrong = []
    for name, query in sorted(REGISTRY.items()):
        expected = first_keyword(query.sql) in MUTATING_KEYWORDS
        if query.mutating != expected:
            wrong.append(f"{name} ({query.source}): flagged mutating="
                         f"{query.mutating}, actually {expected}")
    assert wrong == [], "\n".join(wrong)


def test_the_statements_that_must_be_mutating():
    """Named individually, because these are the ones where a wrong flag means
    money or a person changed with nothing in the log to show for it."""
    for name in ("payments.create", "people.cancel", "people.set_code",
                 "people.update_details", "roster.import_create",
                 "forms.mark_paper", "stats.upsert_school",
                 "auth.session_revoke_all_for_person", "audit.insert"):
        assert REGISTRY[name].mutating, f"{name} is not flagged as mutating"


def test_the_statements_that_must_not_be():
    for name in ("roster.list", "stats.dashboard", "auth.person_by_code_hmac",
                 "audit.recent", "settings.all", "catalog.items"):
        assert not REGISTRY[name].mutating, f"{name} is wrongly flagged mutating"


def test_the_non_obvious_queries_are_documented():
    """Comment the WHY, never the WHAT.

    `SELECT * FROM school_stats WHERE school_id = ?` needs no comment, and
    demanding one produces exactly the noise this project is trying to avoid.
    A query with a JOIN, a subquery, an aggregate, or an ON CONFLICT is
    different: its shape was a decision -- which index it leans on, why it is
    one query and not a loop -- and that reasoning cannot be recovered from the
    SQL by someone reading it three years later.
    """
    interesting = re.compile(
        r"(JOIN|GROUP BY|ON CONFLICT|EXISTS|SUM\(|COUNT\(|CASE WHEN)",
        re.IGNORECASE)

    undocumented = [
        f"{name} ({query.source})"
        for name, query in sorted(REGISTRY.items())
        if interesting.search(query.sql)
        and not any(line.strip().startswith("--")
                    for line in query.sql.splitlines())
    ]
    assert undocumented == [], (
        "these queries do something non-obvious and explain nothing: "
        + ", ".join(undocumented))


def test_no_query_builds_sql_by_concatenation():
    """All SQL lives in backend/queries/*.sql precisely so CI can see it. A
    format placeholder here means a statement assembled at runtime, which is
    both an injection risk and a query the plan check never sees."""
    # Arithmetic is fine -- `COALESCE(MAX(id), 0) + 1` is a real expression.
    # A FORMAT PLACEHOLDER is the thing that means a statement was assembled.
    suspicious = [
        name for name, query in REGISTRY.items()
        if "{" in query.sql or "%s" in query.sql or "' +" in query.sql
    ]
    assert suspicious == [], f"queries look interpolated: {suspicious}"


def test_placeholders_are_qmark_only():
    """Both drivers use qmark parameters. A named placeholder would work on one
    and fail on the other."""
    for name, query in REGISTRY.items():
        body = re.sub(r"--[^\n]*", "", query.sql)
        assert ":" not in re.sub(r"'[^']*'", "", body).replace("::", ""), \
            f"{name} appears to use named placeholders"
