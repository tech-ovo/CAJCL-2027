"""The printed packet and the invoice.

THERE IS ONE IMPLEMENTATION, NOT TWO.
    The server renders a single HTML document. That same HTML is served to the
    browser as a print view AND fed to WeasyPrint to produce the PDF, because
    WeasyPrint is an HTML/CSS renderer -- the print stylesheet IS the PDF
    stylesheet. Do not write a separate PDF layout. Do not treat the browser
    print view as a fallback for the PDF: both need Modal, because both need
    data only Modal can supply, so building a second path would mean
    maintaining two things that fail together.

WEASYPRINT DOES NOT SUPPORT CSS GRID.
    Everything here lays out with normal flow, tables, and simple flex. If you
    reach for `display: grid` in this file, the browser print view and the PDF
    will disagree, which defeats the entire point of one template.

GRAYSCALE
    Everything must be legible on a school printer. Navy and purple map to
    black, slate to mid grey, `--mist` to light grey; gold and Columbia blue are
    dropped entirely, and hierarchy comes from rule weight and type weight.
"""

from __future__ import annotations

import html
import io

import segno

from . import clock, settings, stats
from .db import Tx


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def money(cents: int | None) -> str:
    cents = cents or 0
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(cents) / 100:,.2f}"


def roman(n: int) -> str:
    """Roman numerals for METADATA CONTEXTS ONLY.

    Convention dates in the masthead rail and on printed sheets. Never for a
    date a person has to act on -- deadlines and payment dates stay Arabic,
    because a parent reading a due date should not have to decode it. This is
    the entire budget for classical flourish on the printed page.
    """
    table = ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
             (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
             (5, "V"), (4, "IV"), (1, "I"))
    out = []
    for value, numeral in table:
        while n >= value:
            out.append(numeral)
            n -= value
    return "".join(out)


def convention_dates(tx: Tx) -> str:
    """March 12-13, 2027.

    This used to render as XII-XIII MARTII MMXXVII. It looked like a classics
    convention, and it also meant a sponsor checking a packet against a calendar
    had to translate first. The dates are the one thing on the page nobody
    should have to decode.
    """
    months = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
    try:
        start = settings.get(tx, "convention.start_date")
        end = settings.get(tx, "convention.end_date")
        year, month, first = (int(part) for part in start.split("-"))
        end_year, end_month, last = (int(part) for part in end.split("-"))

        if (year, month) == (end_year, end_month):
            return f"{months[month - 1]} {first}–{last}, {year}"
        if year == end_year:
            return (f"{months[month - 1]} {first} – "
                    f"{months[end_month - 1]} {last}, {year}")
        return (f"{months[month - 1]} {first}, {year} – "
                f"{months[end_month - 1]} {last}, {end_year}")
    except Exception:
        # A malformed date must not take the packet down; a sponsor needs the
        # codes far more than the dateline.
        return ""


def qr_svg(payload: str) -> str:
    """An inline SVG QR. Scales cleanly to print and needs no image file.

    The code travels in the URL FRAGMENT, never the query string, so it is never
    sent to a server, never lands in an access log, and never leaks through a
    Referer header.
    """
    buffer = io.BytesIO()          # segno's SVG writer emits bytes, not text
    segno.make(payload, error="m").save(
        buffer, kind="svg",
        xmldecl=False,             # this is going inline into an HTML document
        svgns=True,
        scale=1, border=0,
        omitsize=True,             # let CSS size it; keeps the viewBox intact
        svgclass=None, lineclass=None,
        dark="#000000",            # black, so it survives a grayscale printer
    )
    return buffer.getvalue().decode("utf-8")


# ---------------------------------------------------------------------------
# Shared chrome
# ---------------------------------------------------------------------------

PRINT_CSS = """
@page { size: Letter; margin: 0.75in; }

/* The print palette. Navy and purple become black, slate mid grey, mist light
   grey; gold and Columbia blue are dropped. Hierarchy is rule weight and type
   weight, so everything survives a grayscale school printer. */
:root {
  --ink: #000; --slate: #444; --mist: #bbb; --paper: #fff;
}

* { box-sizing: border-box; }
body {
  margin: 0; background: var(--paper); color: var(--ink);
  font-family: "Literata", Georgia, "Times New Roman", serif;
  font-size: 11pt; line-height: 1.45;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
h1, h2, h3 { font-weight: 600; margin: 0 0 0.4em; line-height: 1.2; }
h1 { font-size: 20pt; letter-spacing: -0.01em; }
h2 { font-size: 13pt; }
p { margin: 0 0 0.7em; }
strong { font-weight: 700; }

.meta, th, .label, .rail {
  font-family: "IBM Plex Sans", -apple-system, "Segoe UI", sans-serif;
}
.mono, .code, td.num, .num {
  font-family: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
  font-variant-numeric: tabular-nums;
}
.label {
  font-size: 7.5pt; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--slate); font-weight: 600;
}

/* THE TABULA. A 1px rule box with a second hairline inset 3px on the top and
   bottom edges only -- a restrained echo of inscriptional double-ruling. This
   is the one place to spend boldness; everything around it stays quiet. It is
   the signature element and there is deliberately no second one. */
.tabula {
  border: 1px solid var(--ink);
  padding: 10pt 12pt;
  margin: 0 0 14pt;
  position: relative;
}
.tabula::before, .tabula::after {
  content: ""; position: absolute; left: 0; right: 0;
  border-top: 0.5pt solid var(--ink);
}
.tabula::before { top: 3px; }
.tabula::after { bottom: 3px; }
/* overflow-wrap keeps a very long surname inside the box instead of pushing it
   through the right-hand rule. The parser accepts names of any length -- there
   is no limit in the schema and there should not be one -- so the layout has to
   cope rather than the data being trimmed to fit it. */
.tabula .name {
  font-size: 19pt; font-weight: 600; margin: 2pt 0 6pt;
  overflow-wrap: anywhere; word-wrap: break-word;
}
/* A very long name is set smaller rather than allowed to run to four lines.
 *
 * `overflow-wrap: anywhere` already stops it overflowing the sheet -- it wraps
 * -- but at 19pt an 82-character name takes four lines and pushes the QR and
 * the instructions down the page. Two steps down keeps the longest real name
 * to two lines and is still far larger than anything else on the sheet, which
 * is the point: a sponsor sorting a stack must not hand the wrong page to the
 * wrong student.
 *
 * The threshold is applied in Python, not in CSS, because CSS cannot count
 * characters. See _packet_sheet. */
.tabula .name--long { font-size: 15pt; }
.tabula .name--verylong { font-size: 12.5pt; }
.tabula .row {
  display: flex; justify-content: space-between; align-items: baseline;
  gap: 12pt;
}
.tabula .code { font-size: 14pt; letter-spacing: 0.06em; font-weight: 500; }

hr.rule { border: 0; border-top: 1px solid var(--ink); margin: 14pt 0; }
hr.hair { border: 0; border-top: 1px solid var(--mist); margin: 10pt 0; }

table { width: 100%; border-collapse: collapse; }
th {
  text-align: left; font-size: 7.5pt; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--slate);
  border-bottom: 1px solid var(--ink); padding: 4pt 6pt 4pt 0;
}
td { padding: 5pt 6pt 5pt 0; border-bottom: 1px solid var(--mist); }
td.num, th.num { text-align: right; padding-right: 0; }

.footer {
  margin-top: 16pt; padding-top: 6pt; border-top: 1px solid var(--mist);
  font-size: 8pt; color: var(--slate);
}
.sheet { break-after: page; }
.sheet:last-child { break-after: auto; }
/* Nobody's credential may split across two pages. */
.tabula, .keep { break-inside: avoid; }

.warn {
  border: 1px solid var(--ink); padding: 8pt 10pt; margin: 12pt 0;
  font-size: 9.5pt;
}
/* The theme, set as an epigraph. Latin in Literata italic at display size,
   the translation beneath in Plex Sans, the citation as letterspaced small
   capitals -- the same treatment as the masthead on screen. */
.epigraph { margin: 14pt 0; max-width: 26em; }
.epigraph .latin { font-style: italic; font-size: 15pt; line-height: 1.25;
                   margin: 0 0 4pt; }
.epigraph .english { font-family: "IBM Plex Sans", sans-serif; font-size: 9.5pt;
                     margin: 0 0 2pt; color: var(--slate); }

.qr { width: 108pt; height: 108pt; }
.qr svg { width: 100%; height: 100%; display: block; }
.split { display: flex; gap: 18pt; align-items: flex-start; }
.split > .body { flex: 1 1 auto; }
.split > .aside { flex: 0 0 auto; text-align: center; }

@media screen {
  body { padding: 0.75in; max-width: 8.5in; margin: 0 auto; }
  .screen-note {
    background: #F8F5EE; border: 1px solid #B9BEC6; padding: 10pt 12pt;
    margin-bottom: 16pt; font-size: 9.5pt;
    font-family: "IBM Plex Sans", sans-serif;
  }
}
@media print { .screen-note { display: none; } }
"""


def _document(title: str, body: str, footer: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>{PRINT_CSS}</style>
</head><body>
{body}
<div class="footer">{footer}</div>
</body></html>"""


def _footer(tx: Tx) -> str:
    """The convention contact address, on the footer of every printed page."""
    return (f"{_esc(settings.get(tx, 'convention.ordinal'))} California Junior "
            f"Classical League State Convention &middot; "
            f"{_esc(settings.get(tx, 'convention.venue_name'))} &middot; "
            f"{_esc(settings.get(tx, 'convention.venue_address'))} &middot; "
            f"{_esc(settings.get(tx, 'convention.contact_email'))}")


def _markdown_ish(text: str) -> str:
    """The small subset of Markdown the editable documents actually use.

    Bold, bullet lists, and paragraphs. Deliberately not a Markdown library: the
    slim image has to cold-start in a couple of seconds, and this is three
    hundred bytes of prose in a printed packet.
    """
    import re

    out, in_list = [], False
    for raw in (text or "").split("\n"):
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(stripped[2:])}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if stripped:
            out.append(f"<p>{_inline(stripped)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def _inline(text: str) -> str:
    import re
    escaped = _esc(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def _document_body(tx: Tx, key: str) -> str:
    row = tx.one("documents.get", (key,))
    return _markdown_ish(row["body_md"]) if row else ""


# ---------------------------------------------------------------------------
# The packet
# ---------------------------------------------------------------------------

def render_packet(tx: Tx, school: dict, *, only_person: int | None = None,
                  only_people: list[int] | None = None,
                  base_url: str = "https://state.uhsjcl.org") -> str:
    """One sheet per attendee, plus a chapter cover and the paper-form checklist.

    `only_person` renders a single sheet, which is what the reprint after a code
    regeneration uses.

    THE SHEET IS A BEARER CREDENTIAL. It says so, and it shows the attendee's
    name large enough that a sponsor cannot hand the wrong page to the wrong
    student.
    """
    people = [dict(r) for r in tx.all("roster.list", (school["id"],))]
    people = [p for p in people if p["status"] == "active"]
    if only_person is not None:
        people = [p for p in people if p["id"] == only_person]
    elif only_people:
        # Keep the caller's order, so the printed stack matches the list the
        # sponsor just ticked rather than alphabetical order.
        wanted = {p["id"]: p for p in people}
        people = [wanted[i] for i in only_people if i in wanted]

    # A subset is a handful of replacement sheets, not a packet. The cover
    # ("this packet contains one sheet per attendee") and the paper-forms page
    # would both be lies on a three-page reprint.
    whole_packet = only_person is None and not only_people

    parts = []
    if whole_packet:
        parts.append(_packet_cover(tx, school, people))

    for person in people:
        parts.append(_packet_sheet(tx, school, person, base_url))

    if whole_packet:
        parts.append(_paper_forms_page(tx))

    note = (
        '<div class="screen-note"><strong>Print view.</strong> '
        'Use your browser&rsquo;s print command, or download the PDF. '
        'Each attendee&rsquo;s sheet starts on its own page.</div>'
    )
    title = (f"Packet - {school['name']}" if whole_packet
             else f"Access sheets - {school['name']}")
    return _document(title, note + "\n".join(parts), _footer(tx))


def _packet_cover(tx: Tx, school: dict, people: list[dict]) -> str:
    delegates = sum(1 for p in people if p["person_type"] == "delegate")
    adults = len(people) - delegates

    # The theme's one privileged placement in this document. It appears on the
    # cover and nowhere else in the packet -- an epigraph on thirty consecutive
    # credential sheets would be ornament, and ornament is what this design has
    # a budget of zero for.
    theme = f"""
  <div class="epigraph">
    <p class="latin">{_esc(settings.get(tx, 'convention.theme_latin'))}</p>
    <p class="english">{_esc(settings.get(tx, 'convention.theme_english'))}</p>
    <p class="label">{_esc(settings.get(tx, 'convention.theme_citation'))}</p>
  </div>"""

    return f"""
<section class="sheet">
  <div class="label rail">{_esc(convention_dates(tx))}</div>
  <h1>{_esc(settings.get(tx, 'convention.ordinal'))} CAJCL State Convention</h1>
  <div class="meta label">Chapter packet</div>
{theme}
  <hr class="rule">

  <div class="tabula">
    <div class="label">Chapter</div>
    <div class="name">{_esc(school['name'])}</div>
    <div class="row">
      <span class="mono">{_esc(school['level'])} &middot; {_esc(school['city'] or '')}</span>
      <span class="mono">{delegates} delegates &middot; {adults} adults</span>
    </div>
  </div>

  {_document_body(tx, 'packet_cover')}
</section>"""


def _name_size(name: str) -> str:
    """Which size class a name needs, if any.

    Counted here because CSS cannot count characters. The thresholds are where
    a name stops fitting on two lines at the size above, measured against the
    printed sheet's text column rather than guessed.
    """
    length = len(name)
    if length > 60:
        return " name--verylong"
    if length > 38:
        return " name--long"
    return ""


def _packet_sheet(tx: Tx, school: dict, person: dict, base_url: str) -> str:
    """One attendee's sheet.

    The access code itself is NOT available here -- only its HMAC is stored, and
    that is the point. The QR therefore carries a sign-in link and the code is
    filled in at print time only when the caller has just minted it. In normal
    packet printing the sponsor prints from the code they were shown once; see
    the reprint flow after a regeneration.
    """
    name = " ".join(filter(None, [
        person["first_name"], person["middle_name"], person["last_name"],
        person["suffix"]]))
    if person["person_type"] == "delegate":
        kind, instructions = "Delegate", "packet_instructions"
    elif person.get("adult_type") == "sponsor":
        kind, instructions = "Sponsor", "packet_instructions_sponsor"
    elif person.get("adult_type") == "chaperone":
        kind, instructions = "Chaperone", "packet_instructions_adult"
    else:
        kind, instructions = "Adult", "packet_instructions_adult"
    magic = f"{base_url}/#/enter/{person['code_prefix']}-XXXXX-XXXXX"

    return f"""
<section class="sheet">
  <div class="label rail">{_esc(convention_dates(tx))} &middot; {_esc(school['name'])}</div>

  <div class="tabula keep">
    <div class="label">{_esc(kind.upper())}</div>
    <div class="name{_name_size(name)}">{_esc(name)}</div>
    <div class="row">
      <span class="code mono">{_esc(person['code_prefix'])}-&#9608;&#9608;&#9608;&#9608;&#9608;-&#9608;&#9608;&#9608;&#9608;&#9608;</span>
      <span class="mono label">&#8470;&nbsp; {person['id']:04d}</span>
    </div>
  </div>

  <div class="split">
    <div class="body">
      <h2>{'Finish your registration' if kind == 'Delegate'
           else 'What to do next'}</h2>
      {_document_body(tx, instructions)}
    </div>
    <div class="aside">
      <div class="qr">{qr_svg(magic)}</div>
      <div class="label" style="margin-top:6pt">Scan to sign in</div>
    </div>
  </div>

  <div class="warn keep">
    <strong>This sheet is your key.</strong> Anyone holding it can sign in as
    {_esc(person['first_name'])}. Keep it somewhere safe, and do not photograph
    it or post it. If it is lost, ask
    {'a convention chair' if kind == 'Sponsor' else 'your sponsor'}
    for a new code &mdash; the old one stops working straight away.
  </div>
</section>"""


def _paper_forms_page(tx: Tx) -> str:
    return f"""
<section class="sheet">
  <div class="label rail">{_esc(convention_dates(tx))}</div>
  <h1>Required paper forms</h1>
  <hr class="rule">
  {_document_body(tx, 'packet_paper_forms')}
</section>"""


# ---------------------------------------------------------------------------
# The invoice
# ---------------------------------------------------------------------------

def invoice_context(tx: Tx, school: dict) -> dict:
    """The numbers behind an invoice, as data. Used by the API and the template.

    Every line the sponsor is charged for is returned separately, including the
    free-adult allowance, so the arithmetic is visible rather than magic. A
    sponsor who cancels a delegate and sees the bill fall by $65 instead of $140
    can find the reason on this page instead of sending an email.
    """
    counters = dict(tx.one("stats.for_school", (school["id"],)) or {})
    fees = settings.fee_settings(tx)
    payments = [dict(r) for r in tx.all("payments.for_school", (school["id"],))]

    delegates, adults = stats.billable_counts({
        "delegates_active": counters.get("delegates_active", 0),
        "delegates_cancelled_paid": counters.get("delegates_cancelled_paid", 0),
        "adults_active": counters.get("adults_active", 0),
        "adults_cancelled_paid": counters.get("adults_cancelled_paid", 0),
    })

    ratio = fees["fee.adult_ratio"] or 10
    free_adults = -(-delegates // ratio)          # ceil, without importing math
    chargeable_adults = max(0, adults - free_adults)
    owed = counters.get("amount_owed_cents", 0)
    paid = counters.get("amount_paid_cents", 0)

    return {
        "school": {k: v for k, v in school.items() if k != "drive_folder_id"},
        "exempt": bool(school["billing_exempt"]),
        "lines": [
            {"label": "Delegates", "count": delegates,
             "unit_cents": fees["fee.delegate_cents"],
             "amount_cents": delegates * fees["fee.delegate_cents"]},
            {"label": "Adults included at no charge",
             "count": min(free_adults, adults), "unit_cents": 0,
             "amount_cents": 0,
             "note": f"one per {ratio} delegates"},
            {"label": "Additional adults", "count": chargeable_adults,
             "unit_cents": fees["fee.extra_adult_cents"],
             "amount_cents": chargeable_adults * fees["fee.extra_adult_cents"]},
        ],
        "discount_cents": counters.get("discount_cents", 0),
        "discount_reason": school.get("discount_reason"),
        "amount_owed_cents": owed,
        "amount_paid_cents": paid,
        "balance_cents": owed - paid,
        "payments": payments,
        "counts": {"delegates_billable": delegates, "adults_billable": adults,
                   "delegates_cancelled_paid": counters.get("delegates_cancelled_paid", 0)},
        "remit_to": settings.get(tx, "invoice.remit_to"),
        "remit_address": settings.get(tx, "invoice.remit_address"),
        "due": clock.render_local(settings.get_datetime(tx, "deadline.payment"),
                                  with_time=False)
        if settings.get_datetime(tx, "deadline.payment") else "",
    }


def render_invoice(tx: Tx, school: dict) -> str:
    ctx = invoice_context(tx, school)

    if ctx["exempt"]:
        # A blank invoice reads as a bug. Say why, in words.
        body = f"""
<div class="label rail">{_esc(convention_dates(tx))}</div>
<h1>Invoice</h1>
<hr class="rule">
<div class="tabula">
  <div class="label">Chapter</div>
  <div class="name">{_esc(school['name'])}</div>
  <div class="row"><span class="mono">Nothing due</span>
  <span class="mono label">&#8470;&nbsp; {school['id']:04d}</span></div>
</div>
{_document_body(tx, 'invoice_exempt_note')}"""
        return _document(f"Invoice - {school['name']}", body, _footer(tx))

    rows = []
    for line in ctx["lines"]:
        if not line["count"] and not line["amount_cents"]:
            continue
        unit = money(line["unit_cents"]) if line["unit_cents"] else "&mdash;"
        # Parenthesised. Without the brackets the line read
        # "Adults included at no charge ONE PER 10 DELEGATES" -- body type
        # running straight into small capitals with no mark to say the voice
        # had changed, which looked like a rendering fault rather than an aside.
        note = (f' <span class="label">({_esc(line["note"])})</span>'
                if line.get("note") else "")
        rows.append(
            f'<tr><td>{_esc(line["label"])}{note}</td>'
            f'<td class="num mono">{line["count"]}</td>'
            f'<td class="num mono">{unit}</td>'
            f'<td class="num mono">{money(line["amount_cents"])}</td></tr>')

    if ctx["discount_cents"]:
        reason = f' <span class="label">{_esc(ctx["discount_reason"] or "")}</span>' \
            if ctx["discount_reason"] else ""
        rows.append(
            f'<tr><td>Discount{reason}</td><td class="num mono"></td>'
            f'<td class="num mono"></td>'
            f'<td class="num mono">-{money(ctx["discount_cents"])}</td></tr>')

    payment_rows = "".join(
        f'<tr><td class="mono">{_esc(p["received_on"] or p["created_at"][:10])}</td>'
        f'<td>{_esc(p["method"] or "")} {_esc(p["reference"] or "")}</td>'
        f'<td class="num mono">{money(p["amount_cents"])}</td></tr>'
        for p in ctx["payments"]) or \
        '<tr><td colspan="3" class="label">No payments recorded yet.</td></tr>'

    cancelled_note = ""
    if ctx["counts"]["delegates_cancelled_paid"]:
        n = ctx["counts"]["delegates_cancelled_paid"]
        cancelled_note = (
            f'<p class="label">Includes {n} attendee{"" if n == 1 else "s"} who '
            f'withdrew after payment was received. There are no refunds, so they '
            f'remain on this invoice.</p>')

    body = f"""
<div class="label rail">{_esc(convention_dates(tx))}</div>
<h1>Invoice</h1>
<hr class="rule">

<div class="tabula">
  <div class="label">Chapter</div>
  <div class="name">{_esc(school['name'])}</div>
  <div class="row">
    <span class="mono">{_esc(school['level'])} &middot; {_esc(school['city'] or '')}</span>
    <span class="mono label">&#8470;&nbsp; {school['id']:04d}</span>
  </div>
</div>

<table>
  <thead><tr><th>Item</th><th class="num">Count</th>
  <th class="num">Each</th><th class="num">Amount</th></tr></thead>
  <tbody>{''.join(rows)}</tbody>
  <tfoot>
    <tr><td colspan="3" class="num"><strong>Total due</strong></td>
        <td class="num mono"><strong>{money(ctx['amount_owed_cents'])}</strong></td></tr>
    <tr><td colspan="3" class="num">Received</td>
        <td class="num mono">{money(ctx['amount_paid_cents'])}</td></tr>
    <tr><td colspan="3" class="num"><strong>Balance</strong></td>
        <td class="num mono"><strong>{money(ctx['balance_cents'])}</strong></td></tr>
  </tfoot>
</table>
{cancelled_note}

<hr class="hair">
<h2>Payments received</h2>
<table>
  <thead><tr><th>Date</th><th>Method</th><th class="num">Amount</th></tr></thead>
  <tbody>{payment_rows}</tbody>
</table>

<hr class="hair">
<div class="keep">
  <div class="label">Payment due</div>
  <p class="mono">{_esc(ctx['due'])}</p>
  <div class="label">Remit to</div>
  <p>{_esc(ctx['remit_to'])}<br>{_esc(ctx['remit_address'])}</p>
  {_document_body(tx, 'invoice_terms')}
</div>"""
    return _document(f"Invoice - {school['name']}", body, _footer(tx))
