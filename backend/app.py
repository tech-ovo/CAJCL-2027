"""The Modal app: two images, the crons, and nothing else.

All the business logic is in api.py, which imports no Modal at all. That split
is what lets the whole API be exercised by the test suite and run locally with
`uvicorn backend.api:app`.

TWO IMAGES, ONE WRITER
    The web server is a SLIM image -- fastapi, libsql, segno, openpyxl -- and must
    cold-start in a couple of seconds, because a delegate on a phone is waiting
    for it. Anything CPU-heavy or dependency-heavy runs as a separate function
    on its own FAT image and is `.spawn()`ed. WeasyPrint needs Pango and Cairo
    apt-installed; the fat image only ever cold-starts when someone actually
    asks for a PDF, so the interactive path never pays for it.

DO NOT PIN THE WEB FUNCTION TO ONE CONTAINER
    Turso handles durability, so there is no reason to. Modal notes that pinning
    to a single container prevents it bringing up a replacement to shift traffic
    during a rolling redeployment, which would turn every hotfix into an outage.
    Leave `target_concurrency` unset and do not set `max_containers=1`.

    Deploy:  modal deploy backend/app.py
"""

from __future__ import annotations

import modal

app = modal.App("cajcl-2027")

# Secrets live ONLY here and in GitHub Actions. Never in the repository, never
# in the frontend. See docs/RUNBOOK.md for what each one is and what breaks when
# it is rotated.
secrets = [modal.Secret.from_name("cajcl-2027")]

# ---------------------------------------------------------------------------
# TURN THIS ON BEFORE CONVENTION WEEKEND, AND OFF AFTERWARDS
# ---------------------------------------------------------------------------
# Auto-export writes a full backup every ten minutes. It exists for live
# grading, where losing ten minutes of scores is the difference between a smooth
# awards ceremony and a disaster.
#
# For the other fifty weeks of the year it is a container starting up 144 times
# a day to read one setting, find it switched off, and stop. That costs real
# credit and protects nothing, because there is nothing being typed in.
#
# With this False the function still EXISTS and can be run by hand
# (`modal run backend/app.py::autoexport`) -- it simply is not scheduled. The
# in-database switch, Settings > Operations, still has to be on as well: this
# controls whether the alarm clock rings, that controls what happens when it
# does.
#
#     Friday of convention:          set True, `modal deploy`, then turn
#                                    auto-export on in Settings > Operations
#     Monday after:                  set False, `modal deploy`
LIVE_GRADING = False

slim_image = (
    modal.Image.debian_slim(python_version="3.12")
    # openpyxl is pure Python and adds nothing measurable to a cold start, and
    # having it here means an export downloads immediately instead of waiting
    # for the fat image to boot. WeasyPrint is the only thing heavy enough to
    # justify the split.
    .pip_install("fastapi[standard]", "libsql", "segno", "openpyxl", "tzdata")
    .add_local_dir(".", remote_path="/root/cajcl", ignore=[
        "**/.git/**", "**/__pycache__/**", "**/.pytest_cache/**",
        "*.db", "*.db-wal", "*.db-shm", "codes.txt", "demo-codes.txt",
    ])
)

# WeasyPrint is an HTML/CSS renderer, which is the entire reason the print
# stylesheet IS the PDF stylesheet. It needs the Pango and Cairo system
# libraries, which is why this image exists separately from the slim one.
fat_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(
        "libpango-1.0-0", "libpangoft2-1.0-0", "libcairo2",
        "libgdk-pixbuf-2.0-0", "libffi-dev", "shared-mime-info", "fonts-dejavu-core",
    )
    .pip_install("weasyprint", "openpyxl", "libsql", "segno", "tzdata")
    .add_local_dir(".", remote_path="/root/cajcl", ignore=[
        "**/.git/**", "**/__pycache__/**", "**/.pytest_cache/**",
        "*.db", "*.db-wal", "*.db-shm", "codes.txt", "demo-codes.txt",
    ])
)


@app.function(
    image=slim_image,
    secrets=secrets,
    # The reconciler below manages min_containers. Whatever is written here is
    # what a deploy resets it to, which is exactly why the database -- not this
    # line -- is the source of truth for warmth.
    min_containers=0,
    scaledown_window=300,
    timeout=60,
)
@modal.asgi_app()
def web():
    import sys
    sys.path.insert(0, "/root/cajcl")
    from backend.api import app as fastapi_app
    return fastapi_app


# ---------------------------------------------------------------------------
# Workers -- fat image, spawned, never in the request path
# ---------------------------------------------------------------------------

@app.function(image=fat_image, secrets=secrets, timeout=600)
def render_pdf(document: str, school_id: int, person_id: int | None = None,
               codes: dict | None = None) -> bytes:
    """Render the packet or the invoice to PDF.

    Takes the SAME HTML the browser print view is served. There is one layout,
    not two. See backend/workers/pdf.py -- which also runs standalone in a
    Colab, given a .db file.
    """
    import sys
    sys.path.insert(0, "/root/cajcl")
    from backend.workers.pdf import render

    # Keys arrive over the wire as strings; render_packet looks them up by the
    # integer person id.
    by_id = {int(k): str(v) for k, v in (codes or {}).items()}
    return render(document=document, school_id=school_id, person_id=person_id,
                  codes=by_id or None)


@app.function(image=fat_image, secrets=secrets, timeout=900)
def run_export(fmt: str = "xlsx", anonymized: bool = False) -> dict:
    """Export the database. Four files per export: Excel and SQL, each in a full
    version and an anonymised one.

    The anonymised versions exist so they can be handed to an AI or an outside
    helper without exposing minors' data.
    """
    import sys
    sys.path.insert(0, "/root/cajcl")
    from backend.workers.export import run

    return run(fmt=fmt, anonymized=anonymized)


# ---------------------------------------------------------------------------
# Setting up the database, from Modal rather than from a laptop
# ---------------------------------------------------------------------------
#
# WHY THESE EXIST
#     Talking to Turso needs the `libsql` driver, which ships wheels for x86_64
#     Linux, both macOS architectures, and Windows -- but NOT for ARM64 Linux.
#     On an ARM machine (a Snapdragon laptop, a Mac running Linux in a VM) pip
#     falls back to compiling it from Rust source, which needs cmake and a full
#     toolchain and takes ten minutes when it works at all.
#
#     Modal's image is x86_64, so the wheel is simply there. Running migrations
#     from inside Modal sidesteps the whole problem, and it is better practice
#     regardless: the migration runs in the same environment as the code that
#     will use it.
#
#     Local development never needs `libsql` -- a local .db file uses `sqlite3`
#     from the standard library.
#
#         modal run backend/app.py::setup            # migrate, then seed
#         modal run backend/app.py::setup --reset    # wipe first
#         modal run backend/app.py::setup --no-seed  # migrate only

@app.function(image=slim_image, secrets=secrets, timeout=900)
def migrate_database(reset: bool = False) -> str:
    """Bring the database up to date, optionally from empty.

    `reset` DROPS EVERY TABLE FIRST, and it has to happen here rather than
    later in the run. Migrating an existing database compares each file against
    the hash recorded when it first ran, so a database that has applied
    migrations which no longer exist -- after a deliberate consolidation, say
    -- refuses to migrate at all. The wipe used to live in `seed_database`,
    which meant `setup --reset` failed on the migrate step before ever reaching
    the thing that would have fixed it. The only way out was a console.
    """
    import sys
    sys.path.insert(0, "/root/cajcl")
    from backend.lib import migrate
    from backend.lib.db import connect

    db = connect()
    try:
        if reset:
            import scripts.seed as seed_script
            print("dropping all tables")
            seed_script.wipe(db)
        applied = migrate.run(db, verbose=True)
    finally:
        db.close()
    return (f"{applied} migration(s) applied" if applied
            else "database already up to date")


@app.function(image=slim_image, secrets=secrets, timeout=1800)
def seed_database(reset: bool = False) -> dict:
    """Load the demonstration data. Returns the access codes.

    The codes come back to the caller rather than being written to a file,
    because a file written inside a Modal container disappears with it.
    """
    import sys
    sys.path.insert(0, "/root/cajcl")
    import scripts.seed as seed_script
    from backend.lib import catalog, settings
    from backend.lib.db import connect

    db = connect()
    try:
        if reset:
            print("dropping all tables")
            seed_script.wipe(db)
        seed_script.migrate(db)
        settings.invalidate()
        catalog.invalidate()
        print("seeding demonstration data")
        return seed_script.Seeder(db).run()
    finally:
        db.close()


@app.function(image=slim_image, secrets=secrets, timeout=120)
def inspect_secret() -> str:
    """Describe the configuration without revealing it.

    The driver reports a malformed token as
    `Hrana: http error: http::Error(InvalidHeaderValue)`, which names neither
    the setting nor the character at fault. This reports the shape of each
    value -- length, first and last few characters, anything that cannot go in
    an HTTP header -- and then tries the connection for real.
    """
    import os
    import sys
    sys.path.insert(0, "/root/cajcl")

    lines = []
    for name in ("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN", "CODE_PEPPER",
                 "CAJCL_ENV", "TURSO_PLATFORM_TOKEN", "TURSO_ORG", "TURSO_DB_NAME"):
        raw = os.environ.get(name)
        if raw is None:
            lines.append(f"{name:<22} not set")
            continue

        odd = sorted({c for c in raw if not (" " <= c <= "~")})
        described = ", ".join(f"U+{ord(c):04X}" for c in odd) or "none"
        # The URL is not a secret and is useful in full. The rest are shown
        # only at the ends, which is enough to spot a truncated paste.
        if name == "TURSO_DATABASE_URL" or not raw:
            shown = repr(raw)
        else:
            shown = f"{raw[:6]}...{raw[-4:]}"
        lines.append(
            f"{name:<22} {len(raw):>4} chars  {shown}  odd characters: {described}")

    from backend.lib.db import connect
    try:
        db = connect()
        try:
            with db.read() as tx:
                rows = tx.all("settings.all")
        finally:
            db.close()
        lines.append(f"\nconnection OK - {len(rows)} setting(s) read back")
    except Exception as error:
        text = str(error)
        if "no such table" in text:
            # Reaching the database and finding it bare is a success, not a
            # failure. It is what a brand new Turso database looks like.
            lines.append("\nconnection OK - database is empty, so run "
                         "`modal run backend/app.py::setup` next")
        else:
            lines.append(f"\nconnection FAILED - {type(error).__name__}: {error}")

    return "\n".join(lines)


@app.function(image=slim_image, secrets=secrets, timeout=900)
def add_board_members(people: list, new_codes: bool = False,
                      create_schools: bool = False) -> dict:
    """Give the real board their accounts. Returns their codes.

    The names arrive as an argument rather than from a file in the image,
    because the file they come from is gitignored and must stay that way -- see
    scripts/add_board.py.
    """
    import sys
    sys.path.insert(0, "/root/cajcl")
    import scripts.add_board as add_board
    from backend.lib.db import connect

    db = connect()
    try:
        return add_board.run(db, people, new_codes=new_codes,
                             create_schools=create_schools)
    finally:
        db.close()


@app.local_entrypoint()
def board(file: str = "board.json", new_codes: bool = False,
          create_schools: bool = False):
    """Provision real people from a local, gitignored file.

        modal run backend/app.py::board
        modal run backend/app.py::board --new-codes

    Safe to run repeatedly: an existing person keeps their account and their
    code, and only their roles are brought into line with the file.
    """
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import scripts.add_board as add_board

    try:
        people = add_board.load(pathlib.Path(file))
    except add_board.BoardError as error:
        print(error)
        return

    result = add_board_members.remote(people, new_codes=new_codes,
                                      create_schools=create_schools)
    text = add_board.report(result)
    print()
    print(text)
    print()
    print(add_board.summarise(result))

    # Written every time, not only when a code was issued. The file is the
    # list of who is on the board; one that appears only sometimes is one
    # nobody trusts. People whose code did not change read "(unchanged)"
    # rather than being left out — which is what made the file look as though
    # it were missing members.
    pathlib.Path("board-codes.txt").write_text(text + "\n", encoding="utf-8")
    print("also written to board-codes.txt")


@app.function(image=slim_image, secrets=secrets, timeout=900)
def reissue_retired_prefix(old_prefix: str = "ADM") -> dict:
    import sys
    sys.path.insert(0, "/root/cajcl")
    import scripts.add_board as add_board
    from backend.lib.db import connect

    db = connect()
    try:
        return add_board.retire_prefix(db, old_prefix)
    finally:
        db.close()


@app.function(image=slim_image, secrets=secrets, timeout=300)
def export_board() -> list:
    import sys
    sys.path.insert(0, "/root/cajcl")
    import scripts.add_board as add_board
    from backend.lib.db import connect

    db = connect()
    try:
        return add_board.export(db)
    finally:
        db.close()


@app.local_entrypoint()
def recover_board(file: str = "board.json"):
    """Rebuild board.json from the live database, when the file has been lost.

        modal run backend/app.py::recover_board

    The names are in the database; the file is what goes missing, and it is the
    only route into provisioning. Codes are NOT recovered and cannot be -- only
    their HMAC is stored. Anyone who needs one gets a new one.
    """
    import json
    import pathlib

    target = pathlib.Path(file)
    if target.exists():
        print(f"{target.name} already exists. Move it aside first -- this "
              f"would overwrite it.")
        return

    people = export_board.remote()
    target.write_text(
        json.dumps(people, indent=2, ensure_ascii=False) + '\n',
        encoding="utf-8")
    print(f"wrote {len(people)} person/people to {target.name}")
    for entry in people:
        print(f"  {entry['first']} {entry['last']} - {entry['title']}"
              f" - {', '.join(entry['roles'])}")


@app.local_entrypoint()
def retire_adm_codes():
    """Reissue for everyone still holding an ADM code.

        modal run backend/app.py::retire_adm_codes

    `ADM` no longer exists, so those codes no longer sign anybody in. The
    prefix is part of the hashed string, so there is no way to convert one --
    each person gets a new code and needs a new sheet.
    """
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import scripts.add_board as add_board

    result = reissue_retired_prefix.remote("ADM")
    if not result["people"]:
        print("Nobody is holding an ADM code. Nothing to do.")
        return

    text = add_board.report(result)
    print(text)
    pathlib.Path("board-codes.txt").write_text(
        "Access codes reissued when the ADM prefix was retired.\n"
        "REAL PEOPLE. Do not commit this file; it is gitignored.\n"
        "Each code is shown once. Everyone here needs a new sheet.\n\n" + text,
        encoding="utf-8")
    print(f"{len(result['people'])} code(s) also written to board-codes.txt")


@app.local_entrypoint()
def doctor():
    """Check the Modal secret before running anything that depends on it.

        modal run backend/app.py::doctor
    """
    print(inspect_secret.remote())


@app.local_entrypoint()
def setup(reset: bool = False, seed: bool = True):
    """Prepare the production database without installing anything locally.

    USE --detach IF THE CONNECTION IS AT ALL UNRELIABLE:

        modal run --detach backend/app.py::setup --reset

    Seeding is about 1,600 statements. Against a local file that is under a
    second; against a hosted database it is one network round trip each, so
    one to two minutes. `modal run` ties the app's life to the client
    connection, and a laptop that drops for sixty seconds in the middle takes
    the whole run down with it -- half-seeded, which is what an interrupted
    reset leaves behind.

    `--detach` cuts that tie. The run continues on Modal whether or not the
    laptop is still listening, and `modal app logs cajcl-2027` shows how it
    went. The codes are then printed by that log rather than returned here, so
    read them there.
    """
    import pathlib

    # The wipe belongs HERE, before the migrate, not inside the seed. A
    # database holding migrations that no longer exist cannot be migrated, so
    # doing it the other way round meant `--reset` failed at the first step and
    # never reached the wipe that was the point of asking for it.
    print(migrate_database.remote(reset=reset))
    if not seed:
        return

    # Already empty and freshly migrated if `reset` was asked for.
    codes = seed_database.remote(reset=False)

    # One line each, code first, and nothing else on the page.
    #
    # This gets printed and read off in a hurry. A preamble is something to
    # scroll past; a label on the line above its code is a place to lose. Code
    # first because that is the column being read out. Sorted by PERSON,
    # not by code: somebody looking at this sheet is looking for a name.
    lines = [f"{code:16} — {label}"
             for label, code in sorted(codes.items())]
    pathlib.Path("codes.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")

    print()
    for line in lines:
        print("  " + line)
    print()
    print(f"{len(lines)} codes, also written to codes.txt")


# ---------------------------------------------------------------------------
# Crons
# ---------------------------------------------------------------------------

@app.function(image=slim_image, secrets=secrets, schedule=modal.Period(minutes=5))
def warm_reconciler():
    """Reconcile actual warmth to what the database asks for.

    THE DATABASE IS THE SOURCE OF TRUTH, NOT THE MODAL API. Deploying the app
    resets the autoscaler to the static configuration in code, so a one-shot
    button press would be silently undone by the first hotfix during convention.
    This runs every five minutes, so it re-applies within five minutes of any
    deploy and also survives the container dying with a change pending.
    """
    import sys
    sys.path.insert(0, "/root/cajcl")
    from backend.lib import clock, settings
    from backend.lib.db import connect

    db = connect()
    try:
        with db.read() as tx:
            warm_until = settings.get_datetime(tx, "ops.warm_until")
    finally:
        db.close()

    wanted = 1 if (warm_until and not clock.is_past(warm_until)) else 0

    function = modal.Function.from_name("cajcl-2027", "web")
    function.update_autoscaler(min_containers=wanted)
    print(f"warm_until={warm_until or '(unset)'} -> min_containers={wanted}")


@app.function(image=slim_image, secrets=secrets,
              schedule=modal.Period(minutes=10) if LIVE_GRADING else None)
def autoexport():
    """A no-op unless auto-export is enabled and inside its window.

    TWO SWITCHES, DELIBERATELY.
        `LIVE_GRADING` at the top of this file decides whether this is on a
        schedule at all, and changing it needs a deploy. `ops.autoexport_enabled`
        in the database decides what happens when it fires, and changes from the
        dashboard in a second.

        The first exists so this is not costing credit all year for nothing. The
        second exists so a chair can stop it mid-convention without a deploy.

    It has a SHUT-OFF time as well as a start, so nobody has to remember to turn
    it off.
    """
    import sys
    sys.path.insert(0, "/root/cajcl")
    from backend.lib import clock, settings
    from backend.lib.db import connect

    db = connect()
    try:
        with db.read() as tx:
            enabled = settings.get_bool(tx, "ops.autoexport_enabled")
            until = settings.get_datetime(tx, "ops.autoexport_until")
    finally:
        db.close()

    if not enabled:
        # Said out loud on purpose. A scheduled function that runs every ten
        # minutes and logs nothing looks, from the Modal dashboard, exactly
        # like one that is quietly doing something.
        print("auto-export is off (Settings > Operations); nothing to do")
        return
    if until and clock.is_past(until):
        print("auto-export window has closed")
        return

    run_export.spawn(fmt="sql", anonymized=False)
    run_export.spawn(fmt="xlsx", anonymized=False)
    print("auto-export spawned")


@app.function(image=slim_image, secrets=secrets, schedule=modal.Cron("17 9 * * *"))
def prune_login_attempts():
    """Keep login_attempts to seven days.

    Not merely tidiness: both rate-limit queries are indexed range scans, and
    they stay cheap only while the table stays small.
    """
    import sys
    sys.path.insert(0, "/root/cajcl")
    from backend.lib import clock
    from backend.lib.db import connect

    db = connect()
    try:
        with db.tx() as tx:
            removed = tx.run("auth.attempts_prune", (clock.plus_days(-7),))
            tx.mark_silent("login_attempt.record")
    finally:
        db.close()
    print(f"pruned {removed} login attempt(s)")
