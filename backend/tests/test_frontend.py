"""Static checks on the frontend.

There is no bundler and no Node toolchain -- the whole site is plain ES modules
served straight by GitHub Pages, which is what lets a future commissioner open a
file, change a line, and see the result without installing anything.

The price of no bundler is that nothing catches a mistyped import path until a
browser silently fails to load a module. These checks pay that price back:
every import must resolve, every imported name must actually be exported, and
the palette must stay in tokens.css where the next commissioner can find it.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "frontend" / "public"
JS_FILES = sorted([p for p in PUBLIC.rglob("*.js") if "certamen" not in p.parts])

IMPORT_RE = re.compile(
    r'^\s*import\s+(?P<names>.+?)\s+from\s+["\'](?P<path>[^"\']+)["\']',
    re.MULTILINE)
EXPORT_RE = re.compile(
    r'^\s*export\s+(?:async\s+)?(?:function|const|let|class)\s+(\w+)', re.MULTILINE)
EXPORT_LIST_RE = re.compile(r'^\s*export\s*\{([^}]+)\}', re.MULTILINE)


def exported_names(path: pathlib.Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    names = set(EXPORT_RE.findall(source))
    for group in EXPORT_LIST_RE.findall(source):
        names.update(part.strip().split(" as ")[-1].strip()
                     for part in group.split(",") if part.strip())
    return names


def imported_names(clause: str) -> tuple[set[str], bool]:
    """(named imports, is_namespace_import)"""
    clause = clause.strip()
    if clause.startswith("*"):
        return set(), True
    match = re.search(r"\{([^}]*)\}", clause)
    if not match:
        return set(), False       # default import; we have none, but be lenient
    return {part.strip().split(" as ")[0].strip()
            for part in match.group(1).split(",") if part.strip()}, False


@pytest.mark.parametrize("path", JS_FILES, ids=lambda p: p.name)
def test_every_import_resolves(path):
    source = path.read_text(encoding="utf-8")
    for match in IMPORT_RE.finditer(source):
        target = match.group("path")
        assert target.startswith("."), \
            f"{path.name} imports {target!r} from the network; everything is local"
        resolved = (path.parent / target).resolve()
        assert resolved.exists(), f"{path.name} imports {target!r}, which does not exist"


@pytest.mark.parametrize("path", JS_FILES, ids=lambda p: p.name)
def test_every_imported_name_is_exported(path):
    source = path.read_text(encoding="utf-8")
    for match in IMPORT_RE.finditer(source):
        names, namespace = imported_names(match.group("names"))
        if namespace or not names:
            continue
        target = (path.parent / match.group("path")).resolve()
        available = exported_names(target)
        missing = names - available
        assert not missing, (
            f"{path.name} imports {sorted(missing)} from {target.name}, "
            f"which exports {sorted(available)}")


@pytest.mark.parametrize("path", JS_FILES, ids=lambda p: p.name)
def test_module_parses(path):
    """Every module must actually be valid JavaScript.

    There is no bundler and no Node toolchain here, so nothing else catches a
    syntax error until a browser silently refuses to load the module and the
    page renders as a blank white rectangle. This check found two unclosed
    function calls that reviewing the code by eye did not.

    esprima understands up to roughly ES2018, which is a useful ceiling rather
    than a limitation: delegates arrive on whatever phone they own, and
    `catch {}` (Safari 11.1), `??` (Safari 13.1) and `||=` (Safari 14) each cut
    off a slice of them for no benefit. Keeping inside what this parser accepts
    keeps the site working on an old handed-down iPhone.
    """
    esprima = pytest.importorskip("esprima")
    try:
        esprima.parseModule(path.read_text(encoding="utf-8"))
    except Exception as error:  # esprima raises its own Error type
        pytest.fail(f"{path.name} is not valid JavaScript: {error}")


# ---------------------------------------------------------------------------
# The design rules that are easy to break by accident
# ---------------------------------------------------------------------------

HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def test_colours_live_only_in_tokens_css():
    """docs/design.md: write the palette once as custom properties in a single
    tokens.css. No hex literals anywhere else.

    This is the file next year's commissioners re-skin from. A stray hex in
    app.css is a colour they will not find."""
    offenders = {}
    css_files = [p for p in PUBLIC.rglob("*.css") if "certamen" not in p.parts]
    for path in css_files + JS_FILES + [PUBLIC / "index.html"]:
        if path.name == "tokens.css":
            continue
        found = HEX.findall(path.read_text(encoding="utf-8"))
        if found:
            offenders[str(path.relative_to(ROOT))] = found
    assert offenders == {}, f"hex colours outside tokens.css: {offenders}"


def test_every_palette_token_is_defined():
    tokens = (PUBLIC / "tokens.css").read_text(encoding="utf-8")
    for name in ("--ink", "--purple", "--gold", "--blue", "--lavender",
                 "--ivory", "--slate", "--mist", "--white", "--focus"):
        assert f"{name}:" in tokens, f"{name} is missing from tokens.css"


def test_gold_is_never_a_focus_ring():
    """Gold on ivory is 2.06:1 and fails the 3:1 minimum for a non-text
    indicator. A gold focus ring is a ring some people cannot see."""
    css = (PUBLIC / "app.css").read_text(encoding="utf-8")
    for block in re.findall(r"outline[^;]*;", css):
        assert "--gold" not in block, f"gold used as an outline: {block}"
    tokens = (PUBLIC / "tokens.css").read_text(encoding="utf-8")
    focus_line = [l for l in tokens.splitlines() if l.strip().startswith("--focus:")][0]
    assert "gold" not in focus_line


def test_reduced_motion_is_respected():
    css = (PUBLIC / "app.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in css


def test_dark_mode_redefines_every_alias():
    """Dark mode works by swapping the semantic aliases and nothing else.

    Components name `--text` and `--page-bg`, never `--ink` or `--ivory`, so the
    whole site inverts by redefining one block. The failure that makes is silent
    and ugly: miss one alias and that single colour stays in light mode, which
    usually means black text on a navy panel.

    Both blocks are checked. `@media (prefers-color-scheme: dark)` serves
    somebody who has never touched the toggle; `[data-theme="dark"]` serves
    somebody who has, including on a system set to light.
    """
    tokens = (PUBLIC / "tokens.css").read_text(encoding="utf-8")

    light = tokens[tokens.index(":root {"):tokens.index("}\n\n/* ---")]
    aliases = set(re.findall(r"^  (--[\w-]+):\s*var\(", light, re.M))
    assert len(aliases) > 10, "the alias block moved; this is reading the wrong thing"

    for block in ('@media (prefers-color-scheme: dark)', ':root[data-theme="dark"]'):
        start = tokens.index(block)
        end = tokens.index("\n}\n", tokens.index("--status-pending", start))
        defined = set(re.findall(r"(--[\w-]+):\s*", tokens[start:end]))
        missing = sorted(aliases - defined)
        assert missing == [], f"{block} leaves these in light mode: {missing}"


def test_dark_mode_survives_an_explicit_choice_of_light():
    """Somebody on a dark-mode phone who presses the toggle for light must get
    light. Without the `:not([data-theme="light"])` guard the media query wins
    and the button appears to do nothing."""
    tokens = (PUBLIC / "tokens.css").read_text(encoding="utf-8")
    start = tokens.index("@media (prefers-color-scheme: dark)")
    end = tokens.index("\n}\n", tokens.index("--status-pending", start))
    assert ':root:not([data-theme="light"])' in tokens[start:end], (
        "the dark media query must exclude an explicit light choice")


def test_the_theme_is_applied_before_the_first_paint():
    """A dark-mode phone must not see a white page first.

    The stylesheet cannot do this alone: the attribute the toggle writes lives
    in localStorage, and reading it from a deferred module means one painted
    frame in the wrong colours. The script has to be inline, in the head, after
    the stylesheets.
    """
    html = (PUBLIC / "index.html").read_text(encoding="utf-8")
    head = html[:html.index("</head>")]
    assert 'localStorage.getItem("theme")' in head, (
        "nothing in <head> reads the stored theme")
    assert head.index("app.css") < head.index("localStorage"), (
        "the theme script must come after the stylesheets it overrides")


def test_the_dark_palette_was_measured():
    """Every colour pairing dark mode introduces clears 4.5:1.

    The light palette records a measured ratio beside each token because the
    rule there is "measured, not guessed". Dark mode does not get a weaker rule
    just because it arrived later, and it is the easier half: gold and Columbia
    blue were always marked "on dark ONLY" precisely because they work here.
    """
    tokens = (PUBLIC / "tokens.css").read_text(encoding="utf-8")

    def value(name):
        found = re.search(rf"{re.escape(name)}:\s*(#[0-9A-Fa-f]{{6}})", tokens)
        assert found, f"{name} is not a hex literal in tokens.css"
        return found.group(1)

    def contrast(one, two):
        def channel(hex_pair):
            v = int(hex_pair, 16) / 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

        def luminance(colour):
            h = colour.lstrip("#")
            r, g, b = (channel(h[i:i + 2]) for i in (0, 2, 4))
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        first, second = luminance(one), luminance(two)
        hi, lo = max(first, second), min(first, second)
        return (hi + 0.05) / (lo + 0.05)

    night, panel = value("--night"), value("--night-panel")
    readable = {
        "--ivory": "body text",
        "--haze": "metadata",
        "--lavender": "links",
        "--rose": "destructive actions",
        "--gold": "accents and the focus ring",
    }
    for token, role in readable.items():
        colour = value(token)
        for ground, where in ((night, "--night"), (panel, "--night-panel")):
            measured = contrast(colour, ground)
            assert measured >= 4.5, (
                f"{token} ({role}) is {measured:.2f}:1 on {where}, under 4.5:1")


def test_fonts_are_self_hosted():
    """No Google Fonts CDN, no third-party request, no external point of
    failure. The site has to work from a school network that blocks half the
    internet."""
    css = (PUBLIC / "app.css").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in css
    assert "fonts.gstatic.com" not in css
    assert css.count("@font-face") >= 7
    for name in ("literata-400", "literata-600", "literata-italic-400",
                 "plex-sans-400", "plex-sans-600", "plex-mono-400", "plex-mono-500"):
        assert (PUBLIC / "fonts" / f"{name}.woff2").exists(), f"{name}.woff2 missing"


def test_the_theme_macrons_render():
    """The single most likely way this site ships broken.

    The theme needs Latin Extended-A, which default subsetting silently drops,
    and the failure is tofu boxes on the one line the whole design is built
    around."""
    from fontTools.ttLib import TTFont

    for name in ("literata-400", "literata-italic-400", "plex-sans-400"):
        font = TTFont(PUBLIC / "fonts" / f"{name}.woff2")
        covered = set()
        for table in font["cmap"].tables:
            covered.update(table.cmap.keys())
        font.close()
        for character in "āēīōū":
            assert ord(character) in covered, \
                f"{name}.woff2 cannot render {character!r} (U+{ord(character):04X})"


def test_the_static_snapshot_is_populated():
    """A visitor arriving while Modal is cold must see a complete page."""
    html = (PUBLIC / "index.html").read_text(encoding="utf-8")
    for key in ("theme_latin", "dates", "schools_hs", "delegates"):
        match = re.search(
            rf'data-snapshot="{key}"[^>]*>(?P<value>[^<]*)', html)
        assert match, f"no snapshot slot for {key}"
        assert match.group("value").strip() not in ("", "—"), \
            f"snapshot for {key} is empty; run scripts/build_snapshot.py"
    assert "aequam mement" in html


def test_the_offline_announcement_file_is_valid():
    """The second layer: editable from the GitHub web UI with Modal down."""
    body = json.loads((PUBLIC / "announcement.json").read_text(encoding="utf-8"))
    assert set(body) >= {"active", "level", "body_md"}
    assert body["active"] is False, "an announcement is committed as live"


def test_semantic_html_essentials():
    html = (PUBLIC / "index.html").read_text(encoding="utf-8")
    assert html.count("<h1") == 1, "exactly one h1 per page"
    assert 'class="skip-link"' in html
    assert "<main" in html and "<header" in html and "<footer" in html
    assert 'lang="en"' in html


COMMENT_RE = re.compile(r"/\*.*?\*/|//.*?$|<!--.*?-->", re.DOTALL | re.MULTILINE)


def test_no_secret_leaks_into_the_frontend():
    """The frontend never holds a database credential and never talks to Turso.

    Comments are stripped before checking: several of them explain that very
    rule, and a test that fails on its own documentation teaches people to
    delete the documentation.
    """
    for path in JS_FILES + [PUBLIC / "config.js", PUBLIC / "index.html"]:
        source = COMMENT_RE.sub("", path.read_text(encoding="utf-8")).lower()
        for forbidden in ("turso", "auth_token", "authtoken", "libsql",
                          "code_pepper", "pepper", "modal_token"):
            assert forbidden not in source, \
                f"{path.name} contains {forbidden!r} outside a comment"


# ---------------------------------------------------------------------------
# The DOM's own append() is banned
# ---------------------------------------------------------------------------

def test_nothing_calls_the_dom_append_directly():
    """`node.append(x)` stringifies x, so a conditional child renders as "null".

    Written the ordinary way --

        host.append(error ? errorSummary(error) : null, field({...}))

    -- the page gets a text node reading "null" whenever there is no error.
    It survives review because the markup is correct; only the rendered page
    is wrong. This shipped above roughly half the headings on the site.

    ui.js exports `add(node, ...children)`, which filters null, undefined and
    false exactly as `el()` always has. ui.js itself is exempt: it is where the
    one real call lives.
    """
    offenders = []
    for path in JS_FILES:
        if path.name == "ui.js":
            continue
        source = path.read_text(encoding="utf-8")
        for number, line in enumerate(source.splitlines(), start=1):
            if re.search(r"\.append\(", line):
                offenders.append(f"{path.relative_to(ROOT).as_posix()}:{number}")

    assert offenders == [], (
        "use add(node, ...) from ui.js instead of node.append(...) at "
        + ", ".join(offenders))


def test_the_add_helper_drops_empty_children():
    """The three values a conditional child actually takes."""
    source = (PUBLIC / "js" / "ui.js").read_text(encoding="utf-8")
    assert re.search(r"export function add\(node, \.\.\.children\)", source)
    # add() and el() must go through the same filter, or they drift apart.
    assert re.search(r"function append\(node, children\)[\s\S]{0,200}?"
                     r"child === null \|\| child === undefined \|\| child === false",
                     source)


# The layout scale. `.span-9` has no user today, but a column scale with a hole
# in it is worse than an unused step, and the next page that needs nine columns
# would otherwise silently get twelve.
CSS_KEPT_ON_PURPOSE = {"span-9"}


def test_every_css_rule_has_a_user():
    """A stylesheet is where dead code hides best.

    Nothing fails when a rule stops being used -- the page still renders, the
    tests still pass -- so a class outlives its markup indefinitely and the
    next person has to read it to find out it does nothing. Five had: an
    epigraph variant, a fourth banner severity, a pill colour, an imagery
    placeholder, and a flush panel.

    Set the class on an element, or delete the rule.
    """
    css = (ROOT / "frontend/public/app.css").read_text(encoding="utf-8")
    markup = "\n".join(
        p.read_text(encoding="utf-8")
        for pattern in ("frontend/public/**/*.js", "frontend/public/*.html",
                        "backend/**/*.py")
        for p in ROOT.glob(pattern))

    defined = set(re.findall(r"\.([a-zA-Z][\w-]+)", css)) - CSS_KEPT_ON_PURPOSE
    unused = sorted(c for c in defined
                    if not re.search(r"\b" + re.escape(c) + r"\b", markup))
    assert unused == [], "no markup uses these classes: " + ", ".join(unused)


def test_pages_do_not_use_the_browsers_own_dialogs():
    """`alert()` and `confirm()` are the browser's furniture, not this site's.

    Projected in a room they read as something having gone wrong, they cannot
    be styled, and `confirm()` focuses OK -- so the dangerous answer is the one
    you get by pressing Return. `ui.js` provides `check()` and `tell()`, which
    are `<dialog>`s that look like the rest of the site and default to the safe
    answer.

    `guardUnsaved` in ui.js is the single exception: it must answer inside a
    click handler, synchronously, or the navigation it is trying to cancel has
    already happened. It is allowed here and explains itself in place.
    """
    offenders = []
    for path in sorted(ROOT.glob("frontend/public/js/**/*.js")):
        if path.name == "ui.js":
            continue
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith(("*", "//", "/*")):
                continue
            if re.search(r"(?<![.\w])(alert|confirm|prompt)\s*\(", line):
                offenders.append(f"{path.name}:{number}: {line.strip()}")
    assert offenders == [], (
        "use check() or tell() from ui.js instead:\n  " + "\n  ".join(offenders))


# The raw palette. A component naming one of these has opted out of dark mode,
# because these are the colours dark mode does NOT redefine -- the aliases are.
RAW_PALETTE = ("--ink", "--purple", "--gold", "--blue", "--lavender", "--ivory",
               "--slate", "--mist", "--white", "--crimson",
               "--night", "--night-panel", "--haze", "--rose")


def test_components_never_name_a_raw_palette_colour():
    """app.css must reach for `--text`, never `--ink`.

    This is the rule that makes dark mode one block of overrides, and breaking
    it is silent: the page still renders, in light mode it looks right, and
    only a viewer in dark mode sees the damage. It went wrong in eighteen
    places at once -- a nav bar with navy text on a navy tint, and filled
    buttons with white text on lavender.

    The print block is exempt. Paper is white in both modes.
    """
    css = (PUBLIC / "app.css").read_text(encoding="utf-8")
    # Anything from @media print onwards is exempt: paper is white either way.
    last_line = css[:css.index("@media print")].count(chr(10)) + 1

    offenders = [
        f"{number}: {line.strip()}"
        for number, line in enumerate(css.splitlines(), 1)
        if number < last_line
        and any(f"var({token})" in line for token in RAW_PALETTE)
    ]

    assert offenders == [], (
        "these use a raw palette colour instead of a semantic alias, so they "
        "will not follow the theme:\n  " + "\n  ".join(offenders))


def test_the_router_cannot_be_overtaken_by_a_slower_page():
    """Two clicks in quick succession must not leave one tab's contents under
    another tab's highlight.

    Every page fetches, so `route()` sits at an await for as long as the
    network takes, and whichever call finishes LAST wins the screen. The
    highlight comes from `location.hash` and is always right, which is what
    makes the mismatch so confusing to look at.

    Two mechanisms, and the second is what actually saves it: a ticket that
    stops an overtaken navigation writing anything more, and a fresh container
    per navigation so a page still fetching when a newer one arrives paints
    into a detached node.
    """
    main = (PUBLIC / "js/main.js").read_text(encoding="utf-8")
    body = main[main.index("async function route()"):]
    body = body[:body.index("\nasync function ensureSession")]

    assert "const ticket = ++navigation" in body, "no per-navigation ticket"
    assert body.count("if (stale()) return;") >= 2, (
        "every await in route() must be followed by a staleness check")
    assert 'const host = el("div");' in body, (
        "the page must render into its own container, not into #app directly")
    assert "await page(host," in body, "the page is handed #app, not its own node"


def test_buttons_show_their_own_wait():
    """A button that fires a request must disable itself and say so.

    The two failure modes it replaces are both real. Doing nothing invites a
    second click, and "Record payment" pressed twice is two payments against
    one cheque. Replacing the screen with a loading bar is worse: the button
    you just pressed vanishes, so you cannot tell whether the press landed, and
    the page you were reading goes with it.

    `button()` in ui.js does this for every caller whose `onclick` returns a
    promise, which an `async` handler does by definition.
    """
    ui = (PUBLIC / "js/ui.js").read_text(encoding="utf-8")
    body = ui[ui.index("export function button("):]
    body = body[:body.index("\n/* ---")]

    assert "typeof result.then" in body, "the helper must detect a promise"
    assert "node.disabled = true" in body, "a busy button must not accept a second click"
    assert 'aria-busy' in body, "the wait has to be announced, not only drawn"
    assert "btn__spinner" in body, "there is no visible sign of the wait"
    assert "finally" in body, "a failed request must give the button back"


def test_the_sheets_do_not_blank_the_screen_to_save():
    """Saving is the moment a delegate most wants the page to stay put.

    `statusHost` hands the wait to the cold-start ladder, which CLEARS whatever
    host it is given before drawing itself -- so pressing Save wiped the form,
    showed a bar, and then flashed empty. The button carries the wait instead.
    """
    for name in ("activity.js", "adult.js"):
        page = (PUBLIC / "js/pages" / name).read_text(encoding="utf-8")
        save = page[page.index("async function save()"):]
        # The literal option, not the word: the code says in a comment why it
        # is absent, and that comment must not satisfy this test.
        assert "statusHost:" not in save, (
            f"{name}: saving must not hand the whole screen to a loading state")


def test_a_sponsor_is_assumed_to_know_latin():
    """A sponsor is the chapter's Latin teacher.

    Defaulting them to "None" meant every one of them had to correct the form,
    and the ones who did not were quietly shut out of the roles that need Latin
    -- Certamen reading above all. A chaperone is a parent, and None is right
    for them.
    """
    page = (PUBLIC / "js/pages/adult.js").read_text(encoding="utf-8")
    assert page.count('person.adult_type === "sponsor" ? "advanced" : "none"') == 2, (
        "both the initial value and the post-save reset must apply the default")


def test_the_check_in_dialog_does_not_discard_a_note_silently():
    """A note typed and dismissed is a chapter somebody believes they checked
    in.

    Refusing to close at all was worse -- the one modal on the site with no way
    out reads as a trap. The way out before anything is saved is "Cancel", in
    red so it cannot be mistaken for a save, and it asks first only when there
    is something to lose. Warning about an empty box teaches people to dismiss
    warnings.
    """
    page = (PUBLIC / "js/pages/checkin.js").read_text(encoding="utf-8")

    desk = page[page.index("function deskView()"):page.index("function settledView()")]
    assert '"Cancel"' in desk and "btn--danger" in desk, (
        "leaving without saving must be offered, and must not look like a save")
    assert '"Close"' not in desk, (
        '"Close" reads as "done"; before anything is saved the honest word is '
        '"Cancel"')

    settled = page[page.index("function settledView()"):page.index("function codeList()")]
    assert '"Close"' in settled, "there must be a plain way out once saved"

    assert "unsavedNote()" in page and "confirmDiscard()" in page, (
        "a typed note must not be discarded silently")
    assert 'addEventListener("cancel"' in page, (
        "Escape and the backdrop must go through the same question")


def test_opening_the_roster_from_check_in_closes_the_dialog_first():
    """A modal left open keeps its backdrop over whatever it navigated to, so
    the roster rendered perfectly and could not be clicked."""
    page = (PUBLIC / "js/pages/checkin.js").read_text(encoding="utf-8")
    handler = page[page.index('button("Open the roster"'):]
    handler = handler[:handler.index("})")]
    assert handler.index("dialog.close()") < handler.index("location.hash"), (
        "close the dialog before navigating, not after")


def test_a_delegate_added_at_the_desk_needs_all_four_answers():
    """Grade and Latin level are questions only the person at the desk can
    answer, and chasing them afterwards means chasing somebody who has gone
    home."""
    page = (PUBLIC / "js/pages/checkin.js").read_text(encoding="utf-8")
    add_view = page[page.index("function addView()"):]
    for wanted in ("a first name", "a last name", "a grade", "a Latin level"):
        assert f'missing.push("{wanted}")' in add_view, f"{wanted} is not required"
    assert "waive-activity-sheet" in add_view, (
        "a delegate added at the desk must have their sheet waived")
