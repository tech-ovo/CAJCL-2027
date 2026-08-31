"""Render the packet or the invoice to PDF. Runs on Modal, and in a Colab.

THERE IS ONE LAYOUT, NOT TWO.
    This takes the SAME HTML that backend/lib/printing.py serves to the browser
    as a print view and hands it to WeasyPrint, which is an HTML/CSS renderer.
    The print stylesheet IS the PDF stylesheet. Do not write a second layout,
    and do not treat the browser print view as a fallback for this: both need
    Modal because both need data only Modal can supply, so a second path would
    mean maintaining two things that fail together.

WHY THIS IS A SEPARATE FUNCTION ON A SEPARATE IMAGE
    WeasyPrint needs Pango and Cairo apt-installed. Putting it in the web image
    would add seconds to every cold start of the interactive path, which a
    delegate on a phone would pay for. The fat image only ever cold-starts when
    somebody actually asks for a PDF.

    In a Colab:
        !apt-get -qq install libpango-1.0-0 libpangoft2-1.0-0 libcairo2
        !pip install weasyprint segno
        !python pdf.py --db cajcl.db --document packet --school 2 --out packet.pdf
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from backend.lib import printing  # noqa: E402
from backend.lib.db import connect  # noqa: E402

FONTS = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "public" / "fonts"


def build_html(db, document: str, school_id: int,
               person_id: int | None = None,
               codes: dict[int, str] | None = None) -> str:
    """The same HTML the browser print view is served.

    `codes` maps person id to the plaintext access code, and is passed in by
    whoever just minted them. WITHOUT IT EVERY SHEET PRINTS BLOCKS, because the
    stored code is an HMAC and cannot be read back -- which is correct, and was
    silently making this whole path produce packets nobody could sign in with.
    """
    with db.read() as tx:
        school = tx.one("schools.get", (school_id,))
        if school is None:
            raise SystemExit(f"no school with id {school_id}")
        school = dict(school)

        if document == "packet":
            return printing.render_packet(tx, school, only_person=person_id,
                                          codes=codes)
        if document == "invoice":
            return printing.render_invoice(tx, school)
    raise SystemExit(f"unknown document {document!r}; expected packet or invoice")


def to_pdf(html: str, base_url: str | None = None) -> bytes:
    from weasyprint import HTML

    # `base_url` is where a relative URL in the document would resolve from.
    #
    # NOTHING IN THE DOCUMENT USES ONE TODAY. The print stylesheet declares no
    # @font-face -- it names "Literata" and falls back to Georgia, which is
    # what both the browser print view and this PDF actually render in -- and
    # the QR codes are inline SVG rather than images. This is here so that the
    # day somebody does reference a file, it resolves against the frontend
    # rather than against nothing.
    #
    # An earlier comment claimed this loaded the self-hosted fonts. It did not,
    # and never had: there were no @font-face rules for it to resolve.
    return HTML(string=html, base_url=base_url or str(FONTS.parent)).write_pdf()


def render(document: str, school_id: int, person_id: int | None = None,
           db_path: str | None = None,
           codes: dict[int, str] | None = None) -> bytes:
    """The entry point Modal calls."""
    db = connect(db_path)
    try:
        html = build_html(db, document, school_id, person_id, codes)
    finally:
        db.close()
    return to_pdf(html)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="path to a SQLite .db file")
    ap.add_argument("--document", choices=["packet", "invoice"], default="packet")
    ap.add_argument("--school", type=int, required=True)
    ap.add_argument("--person", type=int, default=None,
                    help="render one attendee's sheet only, for a reprint")
    ap.add_argument("--out", default=None)
    ap.add_argument("--html", action="store_true",
                    help="write the HTML instead of the PDF, for checking the "
                         "layout without installing Pango and Cairo")
    args = ap.parse_args()

    db = connect(args.db)
    try:
        html = build_html(db, args.document, args.school, args.person)
    finally:
        db.close()

    if args.html:
        out = pathlib.Path(args.out or f"{args.document}.html")
        out.write_text(html, encoding="utf-8")
        print(f"wrote {out} ({len(html) / 1024:.0f} KB of HTML)")
        return 0

    out = pathlib.Path(args.out or f"{args.document}.pdf")
    out.write_bytes(to_pdf(html))
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
