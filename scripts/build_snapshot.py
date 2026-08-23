"""Bake the convention facts into index.html as a build-time snapshot.

WHY
    Modal scales to zero, so the first request after an idle period takes
    several seconds. A visitor arriving at a cold site must see a COMPLETE page
    immediately -- the theme, the dates, the venue, and the latest published
    statistics -- with the live values replacing them quietly once the API
    answers. Never a loading screen, never a blank page.

    Baking the values into the HTML rather than fetching a JSON file means zero
    requests and zero flash of empty content. `announcement.json` stays a
    separate file because it is edited by hand from the GitHub web UI during an
    emergency, when nobody is running a build.

HOW
    Reads a local .db (or Turso, via the usual environment variables) and
    rewrites the `data-snapshot` elements in place. Run it in CI before
    publishing to Pages, on a schedule, so the numbers stay roughly current.

    python scripts/build_snapshot.py --db dev.db
"""

from __future__ import annotations

import argparse
import html
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from backend.lib import clock, settings  # noqa: E402
from backend.lib.db import connect  # noqa: E402
from backend.lib.printing import convention_dates_roman  # noqa: E402

INDEX = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "public" / "index.html"


def gather(db) -> dict[str, str]:
    with db.read() as tx:
        convention = settings.public_convention(tx)
        stats = tx.one("stats.public")
        welcome = tx.one("documents.get", ("welcome_body",))

        start = convention.get("convention.start_date", "")
        end = convention.get("convention.end_date", "")
        dates = ""
        if start and end:
            first = clock.render_local(clock.start_of_day_utc(start), with_time=False)
            last = clock.render_local(clock.start_of_day_utc(end), with_time=False)
            # "March 12–13, 2027" rather than repeating the month and year.
            if first.split()[0] == last.split()[0]:
                dates = f"{first.rsplit(',', 1)[0]}–{last.split()[1].rstrip(',')}, " \
                        f"{last.rsplit(', ', 1)[1]}"
            else:
                dates = f"{first} – {last}"

        ordinal = convention.get("convention.ordinal", "")
        body = (welcome["body_md"].split("\n\n")[0] if welcome else "")

        return {
            "theme_latin": convention.get("convention.theme_latin", ""),
            "theme_english": convention.get("convention.theme_english", ""),
            "theme_citation": convention.get("convention.theme_citation", ""),
            "dates": dates,
            "dates_roman": convention_dates_roman(tx),
            "masthead_line":
                f"{ordinal} State Convention &middot; "
                f"{convention.get('convention.venue_name', '')}, "
                f"{convention.get('convention.venue_address', '').split(',')[-2].strip()}"
                if convention.get("convention.venue_address", "").count(",") >= 2
                else f"{ordinal} State Convention",
            "heading": f"The {ordinal} California Junior Classical League "
                       f"State Convention",
            "welcome_body": body,
            "venue": f"{convention.get('convention.venue_name', '')}<br>"
                     f"{convention.get('convention.venue_address', '')}",
            "footer": f"California Junior Classical League &middot; "
                      f"{convention.get('convention.contact_email', '')}",
            "schools_hs": f"{stats['schools_hs']:,}" if stats else "—",
            "schools_ms": f"{stats['schools_ms']:,}" if stats else "—",
            "delegates": f"{stats['delegates']:,}" if stats else "—",
            "adults": f"{stats['adults']:,}" if stats else "—",
        }


def apply(source: str, values: dict[str, str]) -> tuple[str, int]:
    """Replace the inner text of every element carrying a data-snapshot key."""
    replaced = 0

    def substitute(match: re.Match) -> str:
        nonlocal replaced
        key = match.group("key")
        if key not in values:
            return match.group(0)
        replaced += 1
        value = values[key]
        # `venue` and the masthead line carry a deliberate <br> / entity; every
        # other value is escaped, because it came out of a database.
        if key not in ("venue", "masthead_line", "footer"):
            value = html.escape(value)
        return f"{match.group('open')}{value}{match.group('close')}"

    pattern = re.compile(
        r'(?P<open><(?P<tag>\w+)[^>]*data-snapshot="(?P<key>[^"]+)"[^>]*>)'
        r'.*?'
        r'(?P<close></(?P=tag)>)',
        re.DOTALL)
    return pattern.sub(substitute, source), replaced


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=None)
    args = ap.parse_args()

    db = connect(args.db)
    values = gather(db)
    db.close()

    source = INDEX.read_text(encoding="utf-8")
    updated, replaced = apply(source, values)
    INDEX.write_text(updated, encoding="utf-8")

    print(f"baked {replaced} values into {INDEX.name}")
    print(f"  theme     {values['theme_latin']}")
    print(f"  dates     {values['dates']}  ({values['dates_roman']})")
    print(f"  chapters  {values['schools_hs']} high school, "
          f"{values['schools_ms']} middle school")
    print(f"  people    {values['delegates']} delegates, {values['adults']} adults")
    return 0


if __name__ == "__main__":
    sys.exit(main())
