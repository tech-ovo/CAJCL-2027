"""Checks that read the source, and therefore need nothing installed.

WHY THIS FILE IS SEPARATE
    `test_db_drivers.py` begins with `pytest.importorskip("libsql")`, so the
    whole module is skipped wherever that driver is absent -- which is every
    ARM machine, because libsql publishes no wheel for one. Two source-text
    checks lived in there and were therefore skipped on exactly the machines
    that most needed them.

    Nothing here imports the application. These run everywhere, always.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]

PYTHON_FILES = sorted(
    path for path in ROOT.rglob("*.py")
    if not any(part in {".venv", "venv", "__pycache__", ".git", "node_modules"}
               for part in path.parts)
)


@pytest.mark.parametrize("path", PYTHON_FILES,
                         ids=[str(p.relative_to(ROOT)) for p in PYTHON_FILES])
def test_every_python_file_compiles(path):
    """Parse, do not import.

    `backend/app.py` imports `modal` at module level, so no test ever loaded
    it -- and a broken string literal in it therefore reached production and
    failed at `modal run`, in front of the person trying to use it.

    Compiling catches that without needing modal, or Turso, or credentials, or
    a network. It is the cheapest check in this suite and it covers the files
    nothing else touches: app.py, the scripts, the workers.
    """
    source = path.read_text(encoding="utf-8")
    try:
        ast.parse(source, filename=str(path))
    except SyntaxError as error:
        line = source.splitlines()[error.lineno - 1] if error.lineno else ""
        pytest.fail(f"{path.relative_to(ROOT)}:{error.lineno} "
                    f"{error.msg}\n    {line.strip()}")


# ---------------------------------------------------------------------------
# Turso decides which statements it will run
# ---------------------------------------------------------------------------

# What a hosted Turso database accepts. Anything else is refused outright:
#
#     SQL not allowed statement: PRAGMA busy_timeout = 5000
#
# and because these run at CONNECTION time, a refused one takes the whole API
# down rather than one query.
TURSO_ALLOWED_PRAGMAS = {"foreign_keys"}


def _section(source: str, start: str, end: str) -> str:
    """The text between two markers.

    `end` is searched for AFTER `start`. Searching from the beginning finds an
    earlier occurrence and silently returns a backwards slice -- which is empty,
    matches nothing, and makes the assertion below pass no matter what the code
    says. That is worse than no test.
    """
    begin = source.index(start)
    return source[begin:source.index(end, begin + len(start))]


def test_the_remote_handle_sends_only_pragmas_turso_permits():
    """A local file is opened. A hosted database is ASKED.

    `PRAGMA busy_timeout` was added to the remote path to match the local one,
    on the correct reasoning that lock contention is a hosted database's
    problem rather than a laptop's. The reasoning was right and the mechanism
    was wrong: Turso allows a short list of pragmas and refuses the rest, so
    every connection failed and the site was down until it came out.

    The wait is done in Python instead -- `_run_with_retry` in db.py -- where
    nobody's permission is required.
    """
    source = (ROOT / "backend" / "lib" / "db.py").read_text(encoding="utf-8")
    remote = _section(source, "def _open_remote", "\n# ------")

    sent = set(re.findall(r'execute\("PRAGMA (\w+)', remote))
    assert sent <= TURSO_ALLOWED_PRAGMAS, (
        f"{sorted(sent - TURSO_ALLOWED_PRAGMAS)} will be refused by Turso at "
        f"connection time, taking the whole API with it. Do it in Python.")


def test_the_local_handle_still_uses_the_pragmas_a_file_supports():
    """The point is not that pragmas are bad. A local file is ours to
    configure, and WAL and busy_timeout genuinely help there."""
    source = (ROOT / "backend" / "lib" / "db.py").read_text(encoding="utf-8")
    local = _section(source, "def _open_local", "def _clean_credential")
    assert "busy_timeout" in local
    assert "journal_mode" in local


# ---------------------------------------------------------------------------
# The seed promises to contain no real names
# ---------------------------------------------------------------------------

# Adults running the convention who may be named in the seed, because the
# seeded audit log is an illustration of a real convention and is read as one.
# They have agreed to it. `scripts/add_board.py` matches these rather than
# creating duplicates.
SEED_ADULTS_ALLOWED = ("Michalak", "Carl", "Liu", "Timothy", "Chen")

# Real people who must NEVER appear in demonstration data. Everyone else on the
# board, and — the whole point — every student, parent and guardian.
#
# Add a name here when somebody real joins. It costs nothing and it is the only
# thing between a good intention and a public commit.
REAL_NAMES = (
    "Conant", "Corrigan",
    "Chenyue", "Zhou", "Sriya", "Kushwaha",
    "Brian Jing", "Yun Jen", "Aurelian Shen",
    "Danny Yoo", "Isa Baucum",
    "Woodbridge",
)


def test_no_unexpected_real_person_is_named_in_the_seed():
    """`scripts/seed.py` invents every delegate, parent and chapter.

    A handful of named adults are allowed and listed above; the board decided
    that an illustrative audit entry naming a real commissioner is fine. What
    is not fine, ever, is a real student — and the fastest way to end up with
    one is for this list to go unmaintained.
    """
    source = (ROOT / "scripts" / "seed.py").read_text(encoding="utf-8")
    found = sorted(name for name in REAL_NAMES if name in source)
    assert found == [], (
        f"{found} appear in scripts/seed.py. Real people belong in board.json, "
        f"which is gitignored - see docs/DEPLOY.md step 4b.")


def test_the_seed_promises_only_what_it_delivers():
    """The docstring used to claim no real name appeared anywhere, while three
    did. A promise nobody checks is worse than no promise."""
    source = (ROOT / "scripts" / "seed.py").read_text(encoding="utf-8")
    head = source[:source.index('"""', 3)]

    assert "EVERY NAME IN HERE IS FABRICATED" not in head, (
        "that claim is not true and has not been for a long time")
    assert "No student. No parent." in head, (
        "the docstring should say plainly what IS guaranteed")


def test_board_json_is_not_committed():
    """The file holding real names must never be tracked by git."""
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").split("\n")
    ignored = {line.strip() for line in gitignore}
    for name in ("board.json", "board-codes.txt", "demo-codes.txt"):
        assert name in ignored, f"{name} must be in .gitignore"
    assert not (ROOT / "board.example.json").exists(), (
        "board.example.json was removed; docs/DEPLOY.md step 4b shows the shape")
