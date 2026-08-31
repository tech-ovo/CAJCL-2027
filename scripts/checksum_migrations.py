"""Record the sha256 of every migration.

    python scripts/checksum_migrations.py

WHEN TO RUN IT
    After ADDING a migration, and at no other time. Commit the updated
    CHECKSUMS.txt alongside the new file.

    If it wants to change a line for a migration you did not just add, stop:
    you have edited one that has already run somewhere, and the next deploy
    will refuse to start. Revert that file and write a new migration instead.

WHY THE FILE EXISTS
    `migrate.py` already refuses to run when an applied migration's contents
    have changed -- it compares against the hash recorded in
    `schema_migrations` when the file first ran. That check is correct and it
    is the one that protects the data.

    But it lives in the DEPLOYED DATABASE. It fires in CI, against production,
    after a push, which is a long way from the person who changed a comment.
    This brings the same check to the laptop, where the answer is `git
    checkout` rather than a failed deploy.
"""

from __future__ import annotations

import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "backend" / "migrations"
MANIFEST = MIGRATIONS / "CHECKSUMS.txt"

HEADER = """\
# sha256 of every migration, as applied.
#
# MIGRATIONS ARE FORWARD-ONLY. Once one has run against a database it can
# never change again -- not a statement, not a comment, not a space. The
# hash is recorded in schema_migrations when it runs, and migrate.py refuses
# to start if a file no longer matches what it applied.
#
# That check lives in the DEPLOYED DATABASE, which means it fires in CI,
# against production, after a push. This file brings the same check back to
# the laptop: edit an applied migration and the test suite fails before the
# commit, which is where you want to find out.
#
# Adding a migration? Run `python scripts/checksum_migrations.py` and commit
# the result with it. Changing an applied one is what this exists to stop --
# write a new migration instead.
"""


def digest(path: pathlib.Path) -> str:
    # read_text normalises line endings, exactly as migrate.py does, so a
    # Windows checkout and a Linux one agree.
    return hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()


def current() -> dict[str, str]:
    return {path.name: digest(path) for path in sorted(MIGRATIONS.glob("*.sql"))}


def recorded() -> dict[str, str]:
    if not MANIFEST.exists():
        return {}
    out = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            value, name = line.split(maxsplit=1)
            out[name.strip()] = value
    return out


REWRITTEN_MARKER = "# rewritten-after: "


def rewritten_after() -> str | None:
    """The date of the last accepted rewrite, from the manifest.

    Written by `--accept`. Without it the drift check below compares every
    migration against the FIRST commit it ever had -- which is right until the
    files are deliberately rewritten, and wrong forever afterwards: it would
    report drift against a version that was intentionally replaced, on every
    run, for the rest of the project.
    """
    if not MANIFEST.exists():
        return None
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.startswith(REWRITTEN_MARKER):
            return line[len(REWRITTEN_MARKER):].strip()
    return None


def first_committed() -> dict[str, str]:
    """Each migration's sha256 AS FIRST COMMITTED, from git.

    THE MANIFEST MUST NOT RECORD DRIFT THAT IS ALREADY THERE. The first version
    of this script hashed the working tree and wrote whatever it found, so a
    file that had already been edited after being applied was recorded in its
    edited state -- and the local check then passed while production still
    refused the deploy. The guard agreed with the mistake.

    Comparing against the version git first saw catches that. It is advisory:
    git may be absent, the checkout may be shallow, and a legitimately
    uncommitted new migration has no history at all.
    """
    import subprocess

    # After an accepted rewrite, "first committed" means first committed SINCE
    # then. Anything older is a version that was deliberately replaced.
    since = rewritten_after()
    window = ["--since", since] if since else []

    out: dict[str, str] = {}
    for path in sorted(MIGRATIONS.glob("*.sql")):
        rel = path.relative_to(ROOT).as_posix()
        try:
            commits = subprocess.run(
                ["git", "log", "--format=%h", "--reverse", *window, "--", rel],
                capture_output=True, text=True, cwd=ROOT, timeout=30).stdout.split()
            if not commits:
                continue                      # never committed: nothing to compare
            blob = subprocess.run(
                ["git", "show", f"{commits[0]}:{rel}"],
                capture_output=True, cwd=ROOT, timeout=30).stdout
            text = blob.decode("utf-8").replace('\r\n', '\n')
            out[path.name] = hashlib.sha256(text.encode()).hexdigest()
        except Exception:
            return {}                         # no git, or no history; skip the check
    return out


def main() -> int:
    accept = "--accept" in sys.argv[1:]
    have, want = recorded(), current()

    if accept:
        # DELIBERATELY REWRITING THE MIGRATIONS. The only time this is
        # legitimate, and it is not a small claim: every database that has run
        # the old files is now on a history that no longer exists, and the only
        # way back into step is to drop it and migrate from empty.
        #
        # Offered because the alternative was worse. Corrections were piling up
        # as new files -- a comment fix here, a wording change there -- until
        # seventeen migrations described a schema that six could have. Between
        # conventions, when the database is going to be rebuilt anyway, folding
        # them back in is the right move and this is how it is recorded.
        import datetime as _dt
        stamp = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        MANIFEST.write_text(
            HEADER + chr(10)
            + REWRITTEN_MARKER + stamp + chr(10)
            + chr(10).join(f"{want[n]}  {n}" for n in sorted(want))
            + chr(10),
            encoding="utf-8")
        print(f"recorded {len(want)} migration(s), accepting every edit")
        print()
        print("EVERY DEPLOYED DATABASE MUST NOW BE REBUILT. It has run files "
              "that no longer exist and its schema_migrations table will not "
              "match. See docs/RUNBOOK.md 5b, and run:")
        print("    modal run backend/app.py::setup --reset")
        return 0

    # Refuse to record a file that has drifted since git first saw it, even if
    # the manifest has never mentioned it. That is the case this exists for.
    original = first_committed()
    drifted = sorted(n for n in original if n in want and original[n] != want[n])
    if drifted:
        for name in drifted:
            print(f"  DRIFTED  {name}  <- changed since it was first committed")
        print()
        print("Those files have been edited after being committed, and at least "
              "one database has already run them. Restore them with `git "
              "checkout` and put the change in a NEW migration; recording them "
              "as they are would make this check agree with the mistake.",
              file=sys.stderr)
        print()
        print("If you MEANT to rewrite them -- between conventions, when the "
              "database is going to be rebuilt anyway -- run this again with "
              "--accept. Every deployed database then has to be reset.",
              file=sys.stderr)
        return 1

    changed = sorted(n for n in have if n in want and have[n] != want[n])
    added = sorted(n for n in want if n not in have)
    removed = sorted(n for n in have if n not in want)

    # KEEP THE BASELINE. An ordinary run must not quietly drop the marker an
    # earlier `--accept` wrote: doing so re-points the drift check at commits
    # that were deliberately replaced, and every run afterwards reports drift
    # against a version nobody wants back.
    baseline = rewritten_after()
    marker = (REWRITTEN_MARKER + baseline + chr(10)) if baseline else ''
    MANIFEST.write_text(
        HEADER + chr(10) + marker
        + chr(10).join(f"{want[n]}  {n}" for n in sorted(want)) + chr(10),
        encoding="utf-8")

    for name in added:
        print(f"  added    {name}")
    for name in removed:
        print(f"  REMOVED  {name}  <- a migration that has run cannot be deleted")
    for name in changed:
        print(f"  CHANGED  {name}  <- this has already run somewhere")

    if changed or removed:
        print()
        print("Those files have already been applied. Revert them and write a "
              "new migration; the next deploy will refuse to start otherwise.",
              file=sys.stderr)
        return 1

    print(f"recorded {len(want)} migration(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
