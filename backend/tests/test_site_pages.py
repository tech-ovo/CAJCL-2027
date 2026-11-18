"""Site pages: Google Docs turned into static pages (migration 015).

Drive is a folder under the test's tmp_path (drive.LocalDrive). Its `convert`
reads a file standing in for the Doc's HTML export, cleans it with the same
module the site build uses, and writes the copy, so the whole path from "paste a
link" to "the page's HTML is in Drive" runs for real. GitHub is a stub.
"""

from __future__ import annotations

import base64
import json
import pathlib
import struct
import shutil
import subprocess

import pytest

from backend import api
from backend.lib import drive, htmlclean, pages
from backend.lib.catalog import ValidationError

from .helpers import Fixture

DOC_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
DOC_URL = f"https://docs.google.com/document/d/{DOC_ID}/edit?usp=sharing"

EXPORT = """<html><head><style>.c1{font-weight:700}</style></head><body class="c0">
<h1 class="c2">Hotel list</h1>
<p class="c3"><span class="c1">Hilton</span> — <a href="https://www.google.com/url?q=https://example.com/hilton&amp;sa=D">book</a></p>
<script>alert(1)</script></body></html>"""


@pytest.fixture
def fx(tmp_path, monkeypatch):
    with Fixture(tmp_path) as f:
        monkeypatch.setattr(api, "_db", f.db)
        local = drive.LocalDrive(str(tmp_path / "drive"))
        drive.use(local)
        f.drive_root = local.root
        f.rebuilds = []
        pages.use_dispatcher(lambda: f.rebuilds.append(1))
        (local.root / DOC_ID).write_text(EXPORT, encoding="utf-8")
        try:
            yield f
        finally:
            drive.use(None)
            pages.use_dispatcher(None)


@pytest.fixture
def client(fx):
    from fastapi.testclient import TestClient
    with TestClient(api.app, raise_server_exceptions=False) as client:
        yield client


def as_(fx, who="admin"):
    return {"Authorization": f"Bearer {fx.sign_in(who)}"}


def add(client, fx, **extra):
    body = {"title": "Hotel list", "doc_url": DOC_URL, **extra}
    response = client.post("/admin/pages", json=body, headers=as_(fx))
    assert response.status_code == 200, response.text
    return response.json()["page"]


def publish(client, fx, who="admin"):
    """What the Site pages screen does: convert each page, then rebuild.

    Returns {"pages", "converted", "failed", "rebuild"} like the screen's summary.
    """
    listing = client.get("/admin/pages", headers=as_(fx, who)).json()["pages"]
    converted = failed = 0
    for page in listing:
        response = client.post(f"/admin/pages/{page['id']}/convert", json={},
                               headers=as_(fx, who))
        assert response.status_code == 200, response.text
        if response.json()["ok"]:
            converted += 1
        else:
            failed += 1
    rebuild = client.post("/admin/pages/rebuild", json={}, headers=as_(fx, who))
    assert rebuild.status_code == 200, rebuild.text
    return {"pages": client.get("/admin/pages", headers=as_(fx, who)).json()["pages"],
            "converted": converted, "failed": failed,
            "rebuild": rebuild.json()["rebuild"]}


# ---------------------------------------------------------------------------
# The rules
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("link", [
    f"https://docs.google.com/document/d/{DOC_ID}/edit",
    f"https://docs.google.com/document/d/{DOC_ID}",
    f"https://docs.google.com/document/u/1/d/{DOC_ID}/edit?tab=t.0",
    f"https://docs.google.com/open?id={DOC_ID}",
])
def test_every_way_of_copying_a_docs_link_is_understood(link):
    assert pages.doc_id_from(link) == DOC_ID


@pytest.mark.parametrize("link", [
    "", "hotels",
    f"https://docs.google.com/spreadsheets/d/{DOC_ID}/edit",
    f"https://docs.google.com/presentation/d/{DOC_ID}/edit",
    f"https://drive.google.com/file/d/{DOC_ID}/view",
    f"http://docs.google.com/document/d/{DOC_ID}/edit",
    f"https://evil.example/docs.google.com/document/d/{DOC_ID}/edit",
    "https://docs.google.com/document/d/short/edit",
])
def test_anything_that_is_not_a_google_doc_is_refused(link):
    with pytest.raises(ValidationError):
        pages.check_page({"title": "x", "doc_url": link})


def test_the_address_defaults_to_the_title():
    fields = pages.check_page({"title": "White Book — 2027!", "doc_url": DOC_URL})
    assert fields["slug"] == "white-book-2027"
    assert fields["doc_id"] == DOC_ID and fields["show_in_nav"] == 1


@pytest.mark.parametrize("slug", ["Has Spaces", "a--b", "-a", "a/b", "..", "index",
                                  "x" * 61])
def test_an_address_cannot_be_anything_but_a_plain_slug(slug):
    with pytest.raises(ValidationError):
        pages.check_page({"title": "x", "slug": slug, "doc_url": DOC_URL})


def test_an_edit_keeps_what_it_does_not_mention():
    current = {"slug": "hotels", "title": "Hotels", "nav_label": "", "show_in_nav": 0,
               "sort_order": 30, "doc_url": DOC_URL, "doc_id": DOC_ID}
    fields = pages.check_page({"title": "Hotel list"}, current)
    assert fields["slug"] == "hotels" and fields["show_in_nav"] == 0
    assert fields["sort_order"] == 30 and fields["doc_id"] == DOC_ID


# ---------------------------------------------------------------------------
# The cleaner
# ---------------------------------------------------------------------------

def test_code_and_styles_do_not_survive():
    out = htmlclean.clean(EXPORT)
    assert "<script" not in out and "alert" not in out and "<style" not in out
    assert "class=" not in out and "font-weight" not in out


def test_google_link_redirects_are_unwrapped():
    out = htmlclean.clean(EXPORT)
    assert '<a href="https://example.com/hilton">book</a>' in out


@pytest.mark.parametrize("href", ["javascript:alert(1)", "JaVaScRiPt:alert(1)",
                                  "data:text/html,<b>x", "vbscript:x", "//evil.example/x",
                                  "file:///etc/passwd"])
def test_a_link_cannot_run_code_or_leave_for_somewhere_odd(href):
    out = htmlclean.clean(f'<p><a href="{href}">x</a></p>')
    assert "href" not in out and "<a" not in out and ">x<" in out


def test_attributes_are_dropped_except_the_two_cells_need():
    out = htmlclean.clean('<table onclick="x()"><tr><td style="color:red" colspan="2" '
                          'onmouseover="y()">a</td></tr></table>')
    assert out == '<table><tr><td colspan="2">a</td></tr></table>'


def test_headings_move_down_one_level_under_the_pages_own_title():
    assert htmlclean.clean("<h1>A</h1><h2>B</h2><h3>C</h3><h6>D</h6>") == \
        "<h2>A</h2><h3>B</h3><h4>C</h4><h4>D</h4>"


def test_output_is_always_well_formed():
    assert htmlclean.clean("<ul><li>one<li>two</ul><p>x<p>y") == \
        "<ul><li>one</li><li>two</li></ul><p>x</p><p>y</p>"
    assert htmlclean.clean("<b><i>x</b>") == "<strong><em>x</em></strong>"


def test_text_is_escaped_not_reparsed():
    assert htmlclean.clean("<p>1 &lt; 2 &amp; <b>3</b></p>") == \
        "<p>1 &lt; 2 &amp; <strong>3</strong></p>"
    assert "<img" not in htmlclean.clean('<p>&lt;img src=x onerror=alert(1)&gt;</p>')


def test_empty_paragraphs_go():
    assert htmlclean.clean("<p>a</p><p><br></p><p> </p><p><span></span></p><p>b</p>") == \
        "<p>a</p><p>b</p>"


def test_a_leading_heading_that_repeats_the_title_is_dropped():
    body = htmlclean.clean("<h1>Hotel list</h1><p>x</p>")
    assert htmlclean.drop_leading_title(body, "Hotel List") == "<p>x</p>"
    assert htmlclean.drop_leading_title(body, "Something else") == body


def test_an_enormous_document_is_refused():
    with pytest.raises(ValueError):
        htmlclean.clean("<p>" + "x" * (htmlclean.MAX_BYTES + 1) + "</p>")


# ---------------------------------------------------------------------------
# Pictures
# ---------------------------------------------------------------------------

def _chunk(kind, body):
    return struct.pack(">I", len(body)) + kind + body + b"\x00\x00\x00\x00"


def png_bytes(secret=b"Location\x00Irvine"):
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", b"\x00" * 13)
            + _chunk(b"tEXt", secret) + _chunk(b"IDAT", b"\x00\x01\x02")
            + _chunk(b"IEND", b""))


def data_uri(data, kind="png"):
    return f"data:image/{kind};base64," + base64.b64encode(data).decode()


def test_an_embedded_picture_is_kept_with_its_description():
    out = htmlclean.clean(f'<p>a</p><img src="{data_uri(png_bytes())}" alt="  A  \'rose\' ">')
    assert out.startswith("<p>a</p><img src=\"data:image/png;base64,")
    assert 'alt="A &#x27;rose&#x27;"' in out


@pytest.mark.parametrize("src", [
    "https://example.com/x.png", "//evil.example/x.png", "images/image1.png",
    "javascript:alert(1)", data_uri(b"<svg onload=alert(1)>", "svg+xml"),
    "data:text/html;base64,PHNjcmlwdD4=", "data:image/png;base64,AA AA",
    'data:image/png;base64,AAAA" onerror="alert(1)',
])
def test_a_picture_that_is_not_embedded_png_jpeg_or_gif_is_dropped(src):
    out = htmlclean.clean(f'<p>a</p><img src=\'{src}\'>')
    assert "<img" not in out and out == "<p>a</p>"


def test_an_alt_cannot_break_out_of_its_attribute():
    out = htmlclean.clean(
        f'<img src="{data_uri(png_bytes())}" alt="x&quot; onerror=&quot;alert(1)">')
    assert 'onerror="' not in out and "&quot;" in out


def test_pictures_become_files_with_their_location_removed(tmp_path):
    body = htmlclean.clean(f'<p><img src="{data_uri(png_bytes())}" alt="Rose"></p>')
    out = htmlclean.extract_images(body, tmp_path / "img", "/p/img")
    files = list((tmp_path / "img").iterdir())
    assert len(files) == 1 and files[0].suffix == ".png"
    assert f'<img src="/p/img/{files[0].name}" alt="Rose">' in out
    assert b"Irvine" not in files[0].read_bytes()
    assert "base64" not in out


def test_the_same_picture_twice_is_one_file(tmp_path):
    tag = f'<img src="{data_uri(png_bytes())}" alt="">'
    htmlclean.extract_images(htmlclean.clean(tag + tag), tmp_path, "/p/img")
    assert len(list(tmp_path.iterdir())) == 1


def test_a_picture_that_is_not_what_it_claims_fails(tmp_path):
    body = htmlclean.clean(f'<img src="{data_uri(b"<script>alert(1)</script>")}">')
    with pytest.raises(ValueError, match="not a PNG"):
        htmlclean.extract_images(body, tmp_path, "/p/img")


def test_a_huge_picture_or_too_many_fail(tmp_path):
    big = png_bytes() + b"\x00" * (htmlclean.MAX_IMAGE_BYTES + 1)
    with pytest.raises(ValueError, match="MB"):
        htmlclean.extract_images(htmlclean.clean(f'<img src="{data_uri(big)}">'),
                                 tmp_path, "/p/img")
    many = f'<img src="{data_uri(png_bytes())}">' * (htmlclean.MAX_IMAGES + 1)
    with pytest.raises(ValueError, match="most is"):
        htmlclean.extract_images(htmlclean.clean(many), tmp_path, "/p/img")


def test_pictures_do_not_count_toward_the_text_limit():
    body = f'<img src="{data_uri(png_bytes() + b"x" * 3_000_000)}">' * 2
    assert "<img" in htmlclean.clean(body)


# ---------------------------------------------------------------------------
# The screen's endpoints
# ---------------------------------------------------------------------------

def test_adding_a_page_does_not_publish_it(client, fx):
    page = add(client, fx)
    assert page["slug"] == "hotel-list" and page["converted"] is False
    assert client.get("/public/pages").json() == {"pages": []}
    assert fx.rebuilds == []


def test_two_pages_cannot_share_an_address(client, fx):
    add(client, fx)
    response = client.post("/admin/pages", headers=as_(fx), json={
        "title": "Other", "slug": "HOTEL-LIST", "doc_url": DOC_URL})
    assert response.status_code == 422 and "/p/hotel-list.html" in response.json()["error"]


def test_publishing_converts_every_doc_and_asks_for_a_rebuild(client, fx):
    add(client, fx)
    body = publish(client, fx)
    assert body["converted"] == 1 and body["failed"] == 0
    assert body["rebuild"]["ok"] and fx.rebuilds == [1]
    assert body["pages"][0]["converted"] is True and body["pages"][0]["synced_at"]

    public = client.get("/public/pages").json()["pages"]
    assert [p["slug"] for p in public] == ["hotel-list"]
    assert public[0]["html_url"].startswith("local:")
    assert set(public[0]) == {"slug", "title", "nav_label", "show_in_nav",
                              "html_url", "synced_at"}, "nothing private leaves"

    copy = next(fx.drive_root.rglob("page-1.html")).read_text(encoding="utf-8")
    assert "<script" not in copy and "<h2>Hotel list</h2>" in copy
    assert "site_page.publish" in fx.audit_actions()


def test_publishing_again_rewrites_the_same_file(client, fx):
    add(client, fx)
    publish(client, fx)
    first = client.get("/public/pages").json()["pages"][0]["html_url"]
    (fx.drive_root / DOC_ID).write_text("<p>Changed</p>", encoding="utf-8")
    publish(client, fx)
    again = client.get("/public/pages").json()["pages"][0]["html_url"]
    assert again == first, "the link is stable, so nothing in the database moves"
    assert len(list(fx.drive_root.rglob("page-1.html"))) == 1
    assert next(fx.drive_root.rglob("page-1.html")).read_text() == "<p>Changed</p>"


def test_a_doc_that_fails_keeps_its_last_good_copy_and_says_why(client, fx):
    add(client, fx)
    publish(client, fx)
    (fx.drive_root / DOC_ID).unlink()            # the Doc is no longer readable
    body = publish(client, fx)
    assert body["failed"] == 1
    page = body["pages"][0]
    assert page["sync_error"] and page["converted"] is True
    assert len(client.get("/public/pages").json()["pages"]) == 1
    assert body["rebuild"]["ok"], "a rebuild is still asked for"


def test_one_bad_doc_does_not_stop_the_others(client, fx):
    add(client, fx)
    other = "1ZyXwVuTsRqPoNmLkJiHgFeDcBa9876543210"
    (fx.drive_root / other).write_text("<p>Second</p>", encoding="utf-8")
    client.post("/admin/pages", headers=as_(fx), json={
        "title": "Missing", "doc_url": f"https://docs.google.com/document/d/{'Q' * 30}/edit"})
    client.post("/admin/pages", headers=as_(fx), json={
        "title": "Second", "doc_url": f"https://docs.google.com/document/d/{other}/edit"})
    body = publish(client, fx)
    assert (body["converted"], body["failed"]) == (2, 1)
    assert sorted(p["slug"] for p in client.get("/public/pages").json()["pages"]) == \
        ["hotel-list", "second"]


def test_the_rebuild_not_being_set_up_is_reported_not_hidden(client, fx):
    add(client, fx)

    def refuse():
        raise pages.RebuildUnavailable("The site rebuild is not switched on yet.")
    pages.use_dispatcher(refuse)
    body = publish(client, fx)
    assert body["converted"] == 1
    assert body["rebuild"]["ok"] is False and "not switched on" in body["rebuild"]["error"]


def test_publishing_with_no_pages_still_rebuilds(client, fx):
    """Removing the last page has to reach the site too."""
    body = publish(client, fx)
    assert body["converted"] == 0 and fx.rebuilds == [1]


def test_pointing_a_page_at_another_doc_forgets_the_old_copy(client, fx):
    page = add(client, fx)
    publish(client, fx)
    other = "1ZyXwVuTsRqPoNmLkJiHgFeDcBa9876543210"
    response = client.patch(f"/admin/pages/{page['id']}", headers=as_(fx), json={
        "doc_url": f"https://docs.google.com/document/d/{other}/edit"})
    assert response.status_code == 200 and response.json()["page"]["converted"] is False
    assert client.get("/public/pages").json() == {"pages": []}


def test_retitling_keeps_the_converted_copy(client, fx):
    page = add(client, fx)
    publish(client, fx)
    response = client.patch(f"/admin/pages/{page['id']}", json={"title": "Hotels"},
                            headers=as_(fx))
    assert response.json()["page"]["converted"] is True


def test_removing_a_page_trashes_the_copy_and_leaves_the_doc(client, fx):
    page = add(client, fx)
    publish(client, fx)
    assert client.delete(f"/admin/pages/{page['id']}", headers=as_(fx)).status_code == 200
    assert client.get("/public/pages").json() == {"pages": []}
    assert not list(fx.drive_root.rglob("page-1.html"))
    assert (fx.drive_root / DOC_ID).exists(), "the Doc itself is never touched"


def test_a_registration_chair_can_keep_site_pages(client, fx):
    headers = as_(fx, "chair")
    response = client.post("/admin/pages", headers=headers, json={
        "title": "Instructions", "doc_url": DOC_URL})
    assert response.status_code == 200, response.text
    assert client.post("/admin/pages/1/convert", json={}, headers=headers).status_code == 200
    assert client.post("/admin/pages/rebuild", json={}, headers=headers).status_code == 200


@pytest.mark.parametrize("who", ["uni_sponsor", "delegate"])
def test_nobody_else_can_keep_site_pages(client, fx, who):
    """What is published here is public, so identity scopes do not reach it."""
    headers = as_(fx, who)
    assert client.get("/admin/pages", headers=headers).status_code == 403
    assert client.post("/admin/pages", headers=headers, json={
        "title": "x", "doc_url": DOC_URL}).status_code == 403
    assert client.patch("/admin/pages/1", headers=headers, json={}).status_code == 403
    assert client.delete("/admin/pages/1", headers=headers).status_code == 403
    assert client.post("/admin/pages/1/convert", json={}, headers=headers).status_code == 403
    assert client.post("/admin/pages/rebuild", json={}, headers=headers).status_code == 403
    assert fx.rebuilds == []


def test_the_public_list_needs_no_credential(client, fx):
    assert client.get("/public/pages").status_code == 200
    assert api.GUARDS.get("public.pages") is None, "no guard: it is deliberately open"


# ---------------------------------------------------------------------------
# The Apps Script cleaner agrees with this one
# ---------------------------------------------------------------------------

PARITY = [
    "<h1>A</h1><h2>B</h2><p>x <b>bold</b> <i>it</i></p>",
    '<p><a href="https://www.google.com/url?q=https://example.com/a&amp;sa=D">l</a></p>',
    '<p><a href="javascript:alert(1)">x</a> text</p>',
    '<ul><li>one</li><li>two</li></ul>',
    '<table><tr><td colspan="2" style="x" onclick="y()">a</td><th>b</th></tr></table>',
    '<p>1 &lt; 2 &amp; 3</p><script>alert(1)</script><style>p{}</style>',
    '<p>a</p><p><br></p><p><span> </span></p><p>b</p>',
    '<p onclick="x()" class="c1" style="color:red"><span class="c2">kept</span></p>',
    '<p>an image <img src="https://example.com/x.png"> goes</p>',
    '<p>kept <img src="data:image/png;base64,iVBORw0KGgo=" alt="A rose"> here</p>',
    '<img src="data:image/gif;base64,R0lGODlhAQABAA==" alt="">',
    '<img src="data:image/svg+xml;base64,AAAA" alt="no">',
]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_apps_script_cleaner_agrees_with_the_python_one():
    """Code.gs is the first pass and htmlclean the guard; if they drifted, the
    page would change shape between the Drive copy and the site."""
    source = pathlib.Path(api.__file__).resolve().parents[1] / "apps-script" / "Code.gs"
    script = ("const fs=require('fs');"
              "const f=new Function(fs.readFileSync(process.argv[1],'utf8')"
              "+'; return cleanDocHtml;')();"
              "const cases=JSON.parse(fs.readFileSync(0,'utf8'));"
              "console.log(JSON.stringify(cases.map(c=>f(c, s=>s.startsWith('data:')?s:''))));")
    run = subprocess.run(["node", "-e", script, str(source)], input=json.dumps(PARITY),
                         capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    for case, got in zip(PARITY, json.loads(run.stdout)):
        assert got == htmlclean.clean(case), case


# ---------------------------------------------------------------------------
# The site build
# ---------------------------------------------------------------------------

ROOT = pathlib.Path(api.__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def builder():
    import importlib.util
    import sys
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location("build_pages", ROOT / "scripts" / "build_pages.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PAGES = [
    {"slug": "hotel-list", "title": "Hotel list", "nav_label": "Hotels",
     "show_in_nav": True, "html_url": "https://drive.example/hotels"},
    {"slug": "white-book", "title": "White Book", "nav_label": "White Book",
     "show_in_nav": False, "html_url": "https://drive.example/white"},
]
DRIVE = {
    "https://drive.example/hotels":
        "<h2>Hotel list</h2><p>Hilton <a href=\"javascript:alert(1)\">x</a></p><script>x</script>",
    "https://drive.example/white": "<h2>Rules</h2><p>Be kind.</p>",
}


def run_build(builder, tmp_path, pages=PAGES, drive_map=DRIVE):
    return builder.build(
        pages, lambda url: drive_map[url], tmp_path,
        index_html=(ROOT / "frontend/public/index.html").read_text(encoding="utf-8"),
        template=(ROOT / "frontend/page.template.html").read_text(encoding="utf-8"))


def test_the_build_writes_each_page_and_the_navigation_list(builder, tmp_path):
    entries = run_build(builder, tmp_path)
    hotels = (tmp_path / "p" / "hotel-list.html").read_text(encoding="utf-8")
    assert "<h1>Hotel list</h1>" in hotels
    assert hotels.count("Hotel list</h1>") == 1, "the Doc's repeated title is dropped"
    assert "Hilton" in hotels and "javascript" not in hotels and "<script>x" not in hotels
    assert 'aria-current="page">Hotels</a>' in hotels
    assert "White Book" not in hotels, "a page hidden from the menu is not in it"
    assert "{{" not in hotels
    assert json.loads((tmp_path / "pages.json").read_text()) == entries
    assert entries[0]["path"] == "/p/hotel-list.html" and entries[1]["show_in_nav"] is False


def test_each_page_allows_exactly_its_own_theme_script(builder, tmp_path):
    """The same hash rule as the welcome page, or the theme would flash white."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "check_csp_hash", ROOT / "scripts" / "check_csp_hash.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    run_build(builder, tmp_path)
    page = (tmp_path / "p" / "white-book.html").read_text(encoding="utf-8")
    assert checker.wanted(page) == checker.recorded(page) != []
    assert "unsafe" not in page and "connect-src" not in page


def test_text_in_a_doc_that_looks_like_a_placeholder_is_left_alone(builder, tmp_path):
    run_build(builder, tmp_path, drive_map={**DRIVE,
              "https://drive.example/white": "<p>Type {{TITLE}} here</p>"})
    assert "{{TITLE}}" in (tmp_path / "p" / "white-book.html").read_text(encoding="utf-8")


def test_a_page_that_comes_back_empty_fails_the_build(builder, tmp_path):
    with pytest.raises(builder.BuildError) as caught:
        run_build(builder, tmp_path, drive_map={**DRIVE,
                  "https://drive.example/white": "<html><body></body></html>"})
    assert "white-book" in str(caught.value) and "empty" in str(caught.value)


def test_a_bad_address_from_the_api_fails_the_build(builder, tmp_path):
    for slug in ("../evil", "A", "a/b", ""):
        with pytest.raises(builder.BuildError):
            run_build(builder, tmp_path, pages=[{**PAGES[0], "slug": slug}])
    with pytest.raises(builder.BuildError):
        run_build(builder, tmp_path, pages=[PAGES[0], PAGES[0]])


def test_removed_pages_do_not_linger_in_the_output(builder, tmp_path):
    run_build(builder, tmp_path)
    run_build(builder, tmp_path, pages=[PAGES[0]])
    assert [p.name for p in (tmp_path / "p").glob("*.html")] == ["hotel-list.html"]
    run_build(builder, tmp_path, pages=[])
    assert json.loads((tmp_path / "pages.json").read_text()) == []


def test_a_page_with_a_picture_is_built_with_the_picture_as_a_file(builder, tmp_path):
    pic = data_uri(png_bytes())
    entries = run_build(builder, tmp_path, pages=[PAGES[1]], drive_map={
        **DRIVE, "https://drive.example/white": f'<h2>Rules</h2><img src="{pic}" alt="Map">'})
    page = (tmp_path / "p" / "white-book.html").read_text(encoding="utf-8")
    name = next((tmp_path / "p" / "img").iterdir()).name
    assert f'<img src="/p/img/{name}" alt="Map">' in page and "base64" not in page
    assert "img-src 'self' data:" in page
    assert entries[0]["slug"] == "white-book"


def test_a_page_that_is_only_a_picture_is_not_empty(builder, tmp_path):
    run_build(builder, tmp_path, pages=[PAGES[1]], drive_map={
        **DRIVE, "https://drive.example/white": f'<img src="{data_uri(png_bytes())}">'})
    assert (tmp_path / "p" / "white-book.html").exists()


def test_pictures_of_a_removed_page_do_not_linger(builder, tmp_path):
    run_build(builder, tmp_path, pages=[PAGES[1]], drive_map={
        **DRIVE, "https://drive.example/white":
            f'<p>x</p><img src="{data_uri(png_bytes())}">'})
    assert list((tmp_path / "p" / "img").iterdir())
    run_build(builder, tmp_path, pages=[PAGES[0]])
    assert not list((tmp_path / "p" / "img").iterdir())


def test_a_local_drive_conversion_keeps_the_pictures(client, fx):
    (fx.drive_root / DOC_ID).write_text(
        f'<h1>Hotel list</h1><img src="{data_uri(png_bytes())}" alt="Lobby">', encoding="utf-8")
    add(client, fx)
    publish(client, fx)
    assert 'alt="Lobby"' in next(fx.drive_root.rglob("page-1.html")).read_text(encoding="utf-8")
