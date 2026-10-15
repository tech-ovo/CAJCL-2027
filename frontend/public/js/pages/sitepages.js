/* Site pages — long text written in Google Docs, published as pages on the site.
 *
 *   #/site-pages    the list of pages, the form to add or change one, and the
 *                   Publish button
 *
 * HOW IT WORKS FOR WHOEVER IS USING IT
 *   1. Write the page in a Google Doc and share it with the CAJCL Drive account.
 *   2. Add it here: a title, and the Doc's link. That is done once.
 *   3. Press Publish. Every Doc is read again, cleaned of its fonts and colours,
 *      and the site is rebuilt. It takes a few minutes to appear.
 *
 * To change a page later, edit the Doc and press Publish. The link does not
 * change and nothing else needs doing.
 */

import * as api from "../api.js";
import { add, el, clear, table, field, input, button, errorSummary,
         emptyState, loadingRows, check, tell, localDate } from "../ui.js";

function errorsOf(error) {
  return error.errors && error.errors.length ? error.errors : [error.message];
}

function statusOf(page) {
  if (page.sync_error) {
    return el("span", {},
      el("span", { class: "pill" }, page.converted ? "Out of date" : "Failed"),
      el("span", { class: "small muted", style: "display:block" }, page.sync_error));
  }
  if (!page.converted) {
    return el("span", { class: "pill" }, "Not published yet");
  }
  return el("span", {},
    el("span", { class: "pill pill--done" }, "✓ Converted"),
    el("span", { class: "small muted", style: "display:block" },
      localDate(page.synced_at, { withTime: true })));
}

export async function sitePagesPage(host) {
  add(host, loadingRows(5, "Loading the site pages"));
  const data = await api.get("/admin/pages", { statusHost: host });
  clear(host);

  let editing = null;      // page id being edited
  let pending = null;      // what was typed into a form that was refused
  let errors = [];
  let outcome = null;      // the last Publish's answer
  let progress = null;     // while Publish is walking the list, where it is up to

  add(host,
    el("h1", {}, "Site pages"),
    el("p", { class: "lede" },
      "Long pages — the hotel list, the white book, instructions — are written "
      + "in Google Docs and shown on this site. Add a Doc's link here once. "
      + "After that, edit the Doc and press Publish."));
  const body = el("div", {});
  add(host, body);
  draw();

  function draw() {
    clear(body);
    add(body, publishPanel());

    if (data.pages.length) {
      add(body, table([
        { key: "title", label: "Page",
          render: (row) => el("span", {},
            el("strong", {}, row.title),
            el("span", { class: "small muted", style: "display:block" },
              row.converted
                ? el("a", { href: row.path }, row.path)
                : row.path)) },
        { key: "status", label: "Status", render: statusOf },
        { key: "nav", label: "Menu",
          render: (row) => row.show_in_nav
            ? (row.nav_label || row.title)
            : el("span", { class: "muted" }, "Not in the menu") },
        { key: "actions", label: "",
          render: (row) => el("div", { class: "btn-row" },
            el("a", { class: "btn btn--small btn--quiet", href: row.doc_url,
                      target: "_blank", rel: "noopener noreferrer" }, "Open Doc"),
            button("Edit", {
              variant: "btn--small btn--quiet",
              onclick: () => { editing = row.id; pending = null; errors = []; draw();
                               scrollToForm(); },
            }),
            button("Remove", {
              variant: "btn--small btn--quiet btn--danger",
              onclick: () => remove(row),
            })) },
      ], data.pages, { caption: "Site pages" }));
    } else {
      add(body, emptyState("No pages yet",
        "Add the first one below. It appears on the site after you press "
        + "Publish."));
    }

    const current = data.pages.find((p) => p.id === editing) || null;
    add(body, form(current));
  }

  /* ---------------------------------------------------------------------- */

  function publishPanel() {
    const waiting = data.pages.filter((p) => !p.converted).length;
    return el("section", { class: "panel", style: "margin-bottom:var(--space-5)" },
      el("h2", {}, "Publish"),
      el("p", {},
        "Reads every Doc again (pictures included) and rebuilds the site. Do "
        + "this after editing a Doc, or after adding, hiding or removing a "
        + "page. Reading a Doc takes a few seconds, more with pictures. The "
        + "change reaches the site a few minutes after that."),
      waiting
        ? el("p", { class: "small muted" },
            `${waiting} ${waiting === 1 ? "page has" : "pages have"} not been `
            + "published yet.")
        : null,
      el("div", { class: "btn-row" },
        button("Publish the site", {
          variant: "btn--primary", onclick: publish,
          disabled: progress ? true : null })),
      progress ? el("p", { role: "status", class: "small" }, progress) : null,
      outcome ? outcomeNote() : null);
  }

  function outcomeNote() {
    const lines = [];
    if (outcome.failed) {
      lines.push(el("p", { class: "field__error" },
        `${outcome.failed} ${outcome.failed === 1 ? "Doc" : "Docs"} could not be `
        + "converted. The last good copy stays on the site. See Status below."));
    } else if (outcome.converted) {
      lines.push(el("p", {}, `${outcome.converted} `
        + `${outcome.converted === 1 ? "Doc" : "Docs"} converted.`));
    }
    if (outcome.rebuild.ok) {
      lines.push(el("p", {},
        "The site is rebuilding. ",
        el("a", { href: outcome.rebuild.url, target: "_blank",
                  rel: "noopener noreferrer" }, "Watch the build"),
        " — when it shows a green tick the change is live."));
    } else {
      lines.push(el("p", { class: "field__error" }, outcome.rebuild.error));
    }
    return el("div", { role: "status" }, ...lines);
  }

  /* ONE REQUEST PER PAGE. A Doc with pictures can take half a minute to read,
   * and the server allows a request a minute, so this walks the list itself,
   * shows each page as it finishes, and only then asks for the rebuild. A page
   * that fails is a result like any other: the rest carry on. */
  async function publish() {
    const queue = data.pages.slice();
    let converted = 0;
    let failed = 0;
    outcome = null;
    try {
      for (let i = 0; i < queue.length; i++) {
        progress = `Reading Doc ${i + 1} of ${queue.length}: ${queue[i].title}`;
        draw();
        let result;
        try {
          result = await api.post(`/admin/pages/${queue[i].id}/convert`, {});
        } catch (error) {
          if (error.status === 422) continue;     // removed meanwhile
          throw error;
        }
        const at = data.pages.findIndex((p) => p.id === result.page.id);
        if (at >= 0) data.pages[at] = result.page;
        if (result.ok) converted++; else failed++;
      }
      progress = "Starting the rebuild…";
      draw();
      const rebuilt = await api.post("/admin/pages/rebuild", {});
      outcome = { converted, failed, rebuild: rebuilt.rebuild };
    } catch (error) {
      await tell({ title: "Publishing did not finish", body: error.message });
    } finally {
      progress = null;
      draw();
    }
  }

  /* ---------------------------------------------------------------------- */

  function scrollToForm() {
    const target = document.getElementById("site-page-form");
    if (target) target.scrollIntoView({ block: "start" });
  }

  function form(current) {
    const shown = pending || (current ? {
      title: current.title, slug: current.slug, doc_url: current.doc_url,
      nav_label: current.nav_label, show_in_nav: current.show_in_nav,
      sort_order: String(current.sort_order),
    } : { title: "", slug: "", doc_url: "", nav_label: "", show_in_nav: true,
          sort_order: "" });

    const title = input({ value: shown.title, maxlength: data.max_title,
                          placeholder: "Hotel list" });
    const docUrl = input({ type: "url", value: shown.doc_url,
                           placeholder: "https://docs.google.com/document/d/…",
                           spellcheck: "false" });
    const slug = input({ value: shown.slug, maxlength: 60, spellcheck: "false",
                         autocapitalize: "none", placeholder: "hotel-list" });
    const navLabel = input({ value: shown.nav_label, maxlength: data.max_name,
                             placeholder: "Hotels" });
    const inNav = el("input", { type: "checkbox", checked: shown.show_in_nav || null });
    const order = input({ type: "number", value: shown.sort_order, step: "1",
                          inputmode: "numeric" });

    const values = () => {
      const out = { title: title.value, doc_url: docUrl.value.trim(),
                    nav_label: navLabel.value, show_in_nav: inNav.checked };
      // Left empty on a new page, the address is made from the title.
      if (slug.value.trim() || current) out.slug = slug.value.trim();
      // Left empty on a new page, it goes last.
      if (order.value !== "") out.sort_order = Number(order.value);
      return out;
    };

    return el("section", { class: "form-section", id: "site-page-form" },
      el("h2", {}, current ? `Edit “${current.title}”` : "Add a page"),
      el("div", { class: "panel" },
        errorSummary(errors),
        field({ id: "site-page-title", label: "Title", required: true,
                help: "Shown as the page's heading. The Doc does not need to repeat it.",
                control: title, wide: true }),
        field({ id: "site-page-doc", label: "Google Doc link", required: true,
                help: "Open the Doc, click Share, and copy the link. Share the "
                  + "Doc with the CAJCL Drive account first (Viewer is enough); "
                  + "if it is not, Publish will say which address to share it with.",
                control: docUrl, wide: true }),
        field({ id: "site-page-slug", label: "Address",
                help: current
                  ? "Changing this breaks any link to the old address."
                  : "Leave empty to make it from the title. Lower-case letters, "
                    + "numbers and hyphens: the page will be at /p/this-name.html.",
                control: slug, wide: true }),
        el("label", { class: "choice" }, inNav,
          el("span", {},
            el("span", { class: "choice__name" }, "Show in the menu"),
            el("span", { class: "choice__why" },
              "Untick to leave it out of the menu bar. It is still reachable "
              + "from Resources and by its address."))),
        field({ id: "site-page-nav", label: "Menu name",
                help: "A shorter name for the menu bar. Empty uses the title.",
                control: navLabel }),
        field({ id: "site-page-order", label: "Order",
                help: "Smaller numbers come first in the menu and on this list. "
                  + "Empty puts a new page last.",
                control: order }),
        el("div", { class: "btn-row" },
          button(current ? "Save changes" : "Add page", {
            variant: "btn--primary",
            onclick: () => (current ? save(current, values()) : create(values())),
          }),
          current ? button("Cancel", {
            variant: "btn--quiet",
            onclick: () => { editing = null; pending = null; errors = []; draw(); },
          }) : null)));
  }

  async function create(values) {
    try {
      const result = await api.post("/admin/pages", values);
      data.pages.push(result.page);
      data.pages.sort(compare);
      pending = null;
      errors = [];
      draw();
    } catch (error) {
      pending = { title: values.title, slug: values.slug || "",
                  doc_url: values.doc_url, nav_label: values.nav_label,
                  show_in_nav: values.show_in_nav,
                  sort_order: values.sort_order === undefined ? ""
                                                              : String(values.sort_order) };
      errors = errorsOf(error);
      draw();
    }
  }

  async function save(row, values) {
    try {
      const result = await api.patch(`/admin/pages/${row.id}`, values);
      Object.assign(row, result.page);
      data.pages.sort(compare);
      editing = null;
      pending = null;
      errors = [];
      draw();
    } catch (error) {
      pending = { title: values.title, slug: values.slug || "",
                  doc_url: values.doc_url, nav_label: values.nav_label,
                  show_in_nav: values.show_in_nav,
                  sort_order: values.sort_order === undefined ? ""
                                                              : String(values.sort_order) };
      errors = errorsOf(error);
      draw();
    }
  }

  async function remove(row) {
    const sure = await check({
      title: `Remove “${row.title}”?`,
      body: "It leaves the site the next time you press Publish. The Google Doc "
        + "itself is not touched.",
      confirmLabel: "Remove page",
      danger: true,
    });
    if (!sure) return;
    try {
      await api.del(`/admin/pages/${row.id}`);
      data.pages = data.pages.filter((p) => p.id !== row.id);
      if (editing === row.id) editing = null;
      draw();
    } catch (error) {
      await tell({ body: error.message });
    }
  }

  /* The server's order: sort order, then title. */
  function compare(a, b) {
    return (a.sort_order - b.sort_order)
      || String(a.title).toLowerCase().localeCompare(String(b.title).toLowerCase());
  }
}
