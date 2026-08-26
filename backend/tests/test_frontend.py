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
JS_FILES = sorted(PUBLIC.rglob("*.js"))

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
    for path in list(PUBLIC.rglob("*.css")) + JS_FILES + [PUBLIC / "index.html"]:
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


def test_no_dark_mode():
    """docs/design.md: out of scope, and it would double the contrast-audit
    surface for no benefit to this audience."""
    css = (PUBLIC / "app.css").read_text(encoding="utf-8")
    assert "prefers-color-scheme" not in css


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
