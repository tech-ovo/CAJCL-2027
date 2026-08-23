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

slim_image = (
    modal.Image.debian_slim(python_version="3.12")
    # openpyxl is pure Python and adds nothing measurable to a cold start, and
    # having it here means an export downloads immediately instead of waiting
    # for the fat image to boot. WeasyPrint is the only thing heavy enough to
    # justify the split.
    .pip_install("fastapi[standard]", "libsql", "segno", "openpyxl")
    .add_local_dir(".", remote_path="/root/cajcl", ignore=[
        "**/.git/**", "**/__pycache__/**", "**/.pytest_cache/**",
        "*.db", "*.db-wal", "*.db-shm", "demo-codes.txt",
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
    .pip_install("weasyprint", "openpyxl", "libsql", "segno")
    .add_local_dir(".", remote_path="/root/cajcl", ignore=[
        "**/.git/**", "**/__pycache__/**", "**/.pytest_cache/**",
        "*.db", "*.db-wal", "*.db-shm", "demo-codes.txt",
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
def render_pdf(document: str, school_id: int, person_id: int | None = None) -> bytes:
    """Render the packet or the invoice to PDF.

    Takes the SAME HTML the browser print view is served. There is one layout,
    not two. See backend/workers/pdf.py -- which also runs standalone in a
    Colab, given a .db file.
    """
    import sys
    sys.path.insert(0, "/root/cajcl")
    from backend.workers.pdf import render

    return render(document=document, school_id=school_id, person_id=person_id)


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


@app.function(image=slim_image, secrets=secrets, schedule=modal.Period(minutes=10))
def autoexport():
    """A no-op unless auto-export is enabled and inside its window.

    This matters most during live grading, when losing ten minutes of scores is
    the difference between a smooth awards ceremony and a disaster. It has a
    SHUT-OFF time as well as a start, so nobody has to remember to turn it off.
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
