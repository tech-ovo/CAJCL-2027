/* The at-convention photo contest.
 *
 * TWO PAGES, ONE MODULE.
 *   #/photos                       a delegate's own photos, one per category
 *   #/photo-contest[/categories]   the Activities chair: every photo with its
 *                                  name and chapter, and the categories
 *
 * A PHOTO IS RE-DRAWN BEFORE IT IS SENT. A phone photo is several megabytes
 * and carries where it was taken. Drawing it onto a canvas and saving that as
 * a JPEG makes it a fraction of the size on convention Wi-Fi, applies the
 * phone's rotation to the pixels, and leaves the location behind. The same
 * pass makes the small thumbnail the chair's page shows.
 *
 * THUMBNAILS LOAD AS THEY SCROLL INTO VIEW, a few at a time. Each one is a
 * round trip through Apps Script, and a page asking for a hundred at once
 * would queue every other upload at convention behind it.
 */

import * as api from "../api.js";
import { add, el, clear, field, input, button, errorSummary, localDate,
         emptyState, loadingRows, table, check, tell, fullName, select,
         personNumber, chapterNumber } from "../ui.js";

const FULL_SIDE = 2400;      // pixels on the long side of the photo sent
const THUMB_SIDE = 480;      // and of its thumbnail

/* ------------------------------------------------------------------------ */
/* Shared pieces. Top-level functions, so nothing reaches into a sibling.    */
/* ------------------------------------------------------------------------ */

function megabytes(bytes) {
  return `${(bytes / 1048576).toFixed(bytes < 1048576 ? 2 : 1)} MB`;
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

function loadImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => { URL.revokeObjectURL(url); resolve(image); };
    image.onerror = () => { URL.revokeObjectURL(url); reject(new Error("unreadable")); };
    image.src = url;
  });
}

/* White underneath, so a transparent PNG does not turn black as a JPEG. */
function drawJpeg(image, side, quality) {
  const width = image.naturalWidth || image.width;
  const height = image.naturalHeight || image.height;
  const scale = Math.min(1, side / Math.max(width, height));
  const canvas = el("canvas", {});
  canvas.width = Math.max(1, Math.round(width * scale));
  canvas.height = Math.max(1, Math.round(height * scale));
  const context = canvas.getContext("2d");
  context.fillStyle = "white";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) => canvas.toBlob(
    (blob) => (blob ? resolve(blob) : reject(new Error("could not save"))),
    "image/jpeg", quality));
}

/* { photo: {name, data}, thumbnail, preview } ready to send, or throws a
 * sentence. A browser that cannot draw the photo sends a JPG or PNG as it is
 * (the server strips its metadata) and no thumbnail. */
async function preparePhoto(file, maxBytes) {
  let image = null;
  try { image = await loadImage(file); } catch (ignored) { image = null; }
  if (image) {
    const full = await drawJpeg(image, FULL_SIDE, 0.88);
    const thumb = await drawJpeg(image, THUMB_SIDE, 0.8);
    const name = file.name.replace(/\.[^.]*$/, "") + ".jpg";
    return { photo: { name, data: await blobToBase64(full) },
             thumbnail: await blobToBase64(thumb),
             preview: URL.createObjectURL(thumb) };
  }
  if (!/^image\/(jpeg|png)$/.test(file.type)) {
    throw new Error("This browser cannot read that kind of photo. Choose a "
      + "JPG or PNG, or pick it from your photo library instead of Files.");
  }
  if (file.size > maxBytes) {
    throw new Error(`That photo is ${megabytes(file.size)}. The limit is `
      + `${megabytes(maxBytes)}.`);
  }
  return { photo: { name: file.name, data: await blobToBase64(file) },
           thumbnail: null, preview: null };
}

/* Fetch thumbnails as their cards come into view, four at a time, and keep
 * each object URL for as long as the page is open so filtering does not
 * fetch them again. */
function thumbLoader() {
  const cache = new Map();
  const waiting = [];
  let running = 0;
  const observer = "IntersectionObserver" in window
    ? new IntersectionObserver((seen) => {
        for (const entry of seen) {
          if (!entry.isIntersecting) continue;
          observer.unobserve(entry.target);
          enqueue(entry.target);
        }
      }, { rootMargin: "300px" })
    : null;

  function enqueue(image) {
    waiting.push(image);
    pump();
  }

  function pump() {
    while (running < 4 && waiting.length) {
      const image = waiting.shift();
      running += 1;
      fetchInto(image).finally(() => { running -= 1; pump(); });
    }
  }

  async function fetchInto(image) {
    const path = image.dataset.src;
    try {
      if (!cache.has(path)) {
        const { blob } = await api.getBlob(path);
        cache.set(path, URL.createObjectURL(blob));
      }
      image.src = cache.get(path);
      image.removeAttribute("aria-busy");
    } catch (error) {
      image.alt = "The photo could not be loaded.";
      image.removeAttribute("aria-busy");
    }
  }

  return {
    watch(image, path) {
      image.dataset.src = path;
      if (cache.has(path)) { image.src = cache.get(path); return image; }
      image.setAttribute("aria-busy", "true");
      if (observer) observer.observe(image); else enqueue(image);
      return image;
    },
  };
}

function statusPill(category) {
  if (category.entry) return el("span", { class: "pill pill--done" }, "✓ Entered");
  return el("span", { class: "pill" },
    category.accepting ? "Not entered" : "Not taking photos");
}

/* Plain text with the chair's line breaks kept. */
function descriptionBlock(text) {
  return text ? el("p", { class: "photo-description" }, text) : null;
}

/* ------------------------------------------------------------------------ */
/* A delegate's photos                                                       */
/* ------------------------------------------------------------------------ */

export async function photosPage(host) {
  let data = null;
  let editing = null;          // category id whose form is open
  let errors = [];
  const loader = thumbLoader();
  const previews = new Map();  // category id -> object URL of what was just sent

  add(host, loadingRows(4, "Loading the photo contest"));
  data = await api.get("/me/photos", { statusHost: host });
  render();

  function render() {
    clear(host);
    add(host,
      el("h1", {}, "Photo contest"),
      el("p", { class: "lede" },
        "Take a photo at convention for any category below and upload it "
        + "here. One photo per category; sending another replaces it."),
      el("p", { class: "form-note" },
        "Send only photos you took yourself. Ask before photographing "
        + "anybody, and leave out anyone who says no."));

    if (!data.can_enter) {
      add(host, emptyState("This is for delegates",
        "The photo contest is entered by delegates."));
      return;
    }
    if (!data.categories.length) {
      add(host, emptyState("No categories yet",
        "The Activities chair has not set up the photo contest. Check back "
        + "at convention."));
      return;
    }
    for (const category of data.categories) add(host, section(category));
  }

  function section(category) {
    const entry = category.entry;
    const open = editing === category.id;
    const node = el("section", { class: "form-section", id: `photo-${category.id}` },
      el("h2", {}, category.name, " ", statusPill(category)),
      descriptionBlock(category.description));

    if (entry && !open) add(node, entrySummary(category, entry));

    if (open) {
      add(node, entryForm(category));
    } else if (category.accepting || entry) {
      add(node, el("div", { class: "btn-row" },
        category.accepting
          ? button(entry ? "Replace or re-caption" : "Upload a photo", {
              variant: entry ? "" : "btn--primary",
              onclick: () => { editing = category.id; errors = []; render(); focusSection(category); },
            })
          : null,
        entry ? button("Withdraw", {
          variant: "btn--quiet btn--danger",
          onclick: () => withdraw(category),
        }) : null));
    }
    return node;
  }

  function focusSection(category) {
    const target = document.getElementById(`photo-${category.id}`);
    if (target) target.scrollIntoView({ block: "start" });
  }

  function thumbnail(category, entry) {
    const image = el("img", { class: "photo-card__img",
                              alt: entry.caption || `Your photo for ${category.name}` });
    if (previews.has(category.id)) {
      image.src = previews.get(category.id);
      return image;
    }
    return loader.watch(image,
      `/me/photos/${category.id}/file?size=thumb&v=${encodeURIComponent(entry.updated_at)}`);
  }

  function entrySummary(category, entry) {
    return el("div", { class: "photo-mine" },
      el("div", { class: "photo-card__frame" }, thumbnail(category, entry)),
      el("dl", { class: "detail" },
        el("dt", {}, "Caption"), el("dd", {}, entry.caption || "—"),
        el("dt", {}, "Sent"), el("dd", {}, localDate(entry.updated_at, { withTime: true }))));
  }

  function entryForm(category) {
    const entry = category.entry;
    const form = el("div", { class: "panel" });
    add(form, errorSummary(errors));
    const preview = el("img", { class: "photo-card__img", alt: "The photo you chose" });
    const frame = el("div", { class: "photo-card__frame photo-preview", hidden: true }, preview);
    const file = el("input", { type: "file", accept: "image/*",
      onchange: () => {
        const chosen = file.files[0];
        if (!chosen) { frame.hidden = true; return; }
        preview.src = URL.createObjectURL(chosen);
        frame.hidden = false;
      } });
    const caption = input({ value: entry ? entry.caption || "" : "", maxlength: 200 });
    add(form,
      field({ id: `photo-${category.id}-file`,
              label: entry ? "A new photo (leave empty to keep yours)" : "Your photo",
              help: "Take one now or choose one from your phone.",
              required: !entry, control: file, wide: true }),
      frame,
      field({ id: `photo-${category.id}-caption`, label: "Caption",
              help: "Optional. A few words about it.", control: caption, wide: true }),
      el("div", { class: "btn-row" },
        button(entry ? "Save" : "Send my photo", {
          variant: "btn--primary",
          onclick: () => submit(category, file, caption),
        }),
        button("Cancel", {
          variant: "btn--quiet",
          onclick: () => { editing = null; errors = []; render(); },
        })));
    return form;
  }

  async function submit(category, file, caption) {
    const payload = { caption: caption.value };
    let preview = null;
    const chosen = file.files[0];
    if (!chosen && !category.entry) {
      errors = ["Choose the photo to upload."];
      render();
      return;
    }
    if (chosen) {
      try {
        const ready = await preparePhoto(chosen, data.max_photo_bytes);
        payload.photo = ready.photo;
        if (ready.thumbnail) payload.thumbnail = ready.thumbnail;
        preview = ready.preview;
      } catch (error) {
        errors = [error.message];
        render();
        return;
      }
    }
    // No statusHost: the cold-start ladder would sit over the form. The
    // button is already showing the wait.
    try {
      const result = await api.post(`/me/photos/${category.id}`, payload);
      category.entry = result.entry;
      if (preview) previews.set(category.id, preview);
      editing = null;
      errors = [];
      render();
      focusSection(category);
    } catch (error) {
      errors = error.errors && error.errors.length ? error.errors : [error.message];
      render();
    }
  }

  async function withdraw(category) {
    const sure = await check({
      title: `Withdraw your photo for ${category.name}?`,
      body: "It is deleted from the contest. "
        + (category.accepting ? "You can send another while the category is open."
                              : "This category is closed, so you cannot send another."),
      confirmLabel: "Withdraw photo",
      danger: true,
    });
    if (!sure) return;
    try {
      await api.del(`/me/photos/${category.id}`);
      category.entry = null;
      previews.delete(category.id);
      render();
    } catch (error) {
      await tell({ body: error.message });
    }
  }
}

/* ------------------------------------------------------------------------ */
/* The Activities chair                                                      */
/* ------------------------------------------------------------------------ */

function chairTabs(current) {
  const tabs = [["photos", "Photos", "#/photo-contest"],
                ["categories", "Categories", "#/photo-contest/categories"]];
  return el("nav", { class: "tabs", "aria-label": "Photo contest sections" },
    ...tabs.map(([key, label, href]) => {
      const anchor = el("a", { href,
        class: key === current ? "tabs__tab is-current" : "tabs__tab" }, label);
      if (key === current) anchor.setAttribute("aria-current", "page");
      return anchor;
    }));
}

export async function photoContestPage(host, params = []) {
  const tab = params[0] === "categories" ? "categories" : "photos";
  add(host, loadingRows(8, "Loading the photo contest"));
  const data = await api.get("/admin/photos", { statusHost: host });
  clear(host);
  add(host,
    el("h1", {}, "Photo contest"),
    el("p", { class: "lede" },
      "Photos delegates send from their phones during convention, with whose "
      + "they are. Open a category when it should start taking photos."),
    chairTabs(tab));
  const body = el("div", {});
  add(host, body);
  if (tab === "categories") categoriesTab(body, data);
  else photosTab(body, data);
}

/* EVERY PHOTO. Filtering is local -- everything is already here -- and only
 * the grid under the filters is redrawn, so the search box keeps its focus. */
function photosTab(host, data) {
  let categoryFilter = "";
  let chapterFilter = "";
  let needle = "";
  const loader = thumbLoader();

  const chapters = [];
  const seen = new Set();
  for (const row of data.entries) {
    if (seen.has(row.school_id)) continue;
    seen.add(row.school_id);
    chapters.push(row);
  }
  chapters.sort((a, b) => (a.school_number || 0) - (b.school_number || 0)
                          || a.school_name.localeCompare(b.school_name));

  const results = el("div", {});
  add(host, headline(), filters(), results);
  draw();

  function headline() {
    const stat = (label, value) => el("div", { class: "stat" },
      el("span", { class: "stat__value" }, String(value)),
      el("span", { class: "label" }, label));
    return el("div", { class: "stats" },
      stat("Photos", data.entries.length),
      stat("Delegates", new Set(data.entries.map((r) => r.person_id)).size),
      stat("Chapters", chapters.length),
      ...data.categories.map((c) => stat(c.name, c.photos)));
  }

  function filters() {
    const category = select(
      [["", "All categories"], ...data.categories.map((c) => [String(c.id), c.name])],
      { onchange: (event) => { categoryFilter = event.target.value; draw(); } });
    const chapter = select(
      [["", "All chapters"],
       ...chapters.map((c) => [String(c.school_id),
                               `${chapterNumber({ number: c.school_number })} ${c.school_name}`])],
      { onchange: (event) => { chapterFilter = event.target.value; draw(); } });
    const search = input({
      type: "search", placeholder: "Name or caption",
      oninput: (event) => { needle = event.target.value.trim().toLowerCase(); draw(); },
    });
    return el("div", { class: "btn-row", style: "margin-top:var(--space-6);align-items:flex-end" },
      field({ id: "photos-category", label: "Category", control: category }),
      field({ id: "photos-chapter", label: "Chapter", control: chapter }),
      field({ id: "photos-search", label: "Search", control: search }));
  }

  function matches(row) {
    if (categoryFilter && String(row.category_id) !== categoryFilter) return false;
    if (chapterFilter && String(row.school_id) !== chapterFilter) return false;
    if (!needle) return true;
    return [row.first_name, row.last_name, row.caption, row.school_name]
      .filter(Boolean).join(" ").toLowerCase().includes(needle);
  }

  function draw() {
    clear(results);
    if (!data.entries.length) {
      add(results, emptyState("No photos yet",
        data.categories.some((c) => c.accepting)
          ? "When delegates send photos, they appear here."
          : "No category is taking photos. Open one on the Categories tab."));
      return;
    }
    const rows = data.entries.filter(matches);
    add(results, el("p", { class: "small muted" },
      `Showing ${rows.length} of ${data.entries.length}.`));
    if (!rows.length) {
      add(results, emptyState("Nothing matches", "Try a different category, chapter or search."));
      return;
    }
    for (const category of data.categories) {
      const mine = rows.filter((r) => r.category_id === category.id);
      if (!mine.length) continue;
      add(results,
        el("h2", {}, category.name, " ",
           el("span", { class: "small muted" }, `${mine.length}`)),
        el("div", { class: "photo-grid" }, ...mine.map(card)));
    }
  }

  function card(row) {
    const image = loader.watch(
      el("img", { class: "photo-card__img", alt: row.caption || `Photo by ${fullName(row)}` }),
      `/admin/photos/entries/${row.id}/file?size=thumb`);
    return el("figure", { class: "photo-card" },
      el("button", { class: "photo-card__frame", type: "button",
                     title: "See it full size", onclick: () => showFull(row) }, image),
      el("figcaption", { class: "photo-card__body" },
        el("strong", {}, fullName(row)),
        el("span", { class: "small muted mono" },
           personNumber({ number: row.school_number }, row)),
        el("span", { class: "small" },
           `${chapterNumber({ number: row.school_number })} ${row.school_name}`),
        row.caption ? el("span", { class: "small" }, `“${row.caption}”`) : null,
        el("span", { class: "small muted" }, localDate(row.updated_at, { withTime: true })),
        row.approval === "pending"
          ? el("span", { class: "pill" }, "Not yet approved") : null,
        row.person_status !== "active"
          ? el("span", { class: "pill" }, "Not attending") : null,
        el("div", { class: "btn-row" },
          button("Take down", { variant: "btn--small btn--quiet btn--danger",
                                onclick: () => takeDown(row) }))));
  }

  async function showFull(row) {
    let url;
    try {
      const { blob } = await api.getBlob(`/admin/photos/entries/${row.id}/file`);
      url = URL.createObjectURL(blob);
    } catch (error) {
      await tell({ body: error.message });
      return;
    }
    const extension = row.original_name && /\.png$/i.test(row.original_name) ? "png" : "jpg";
    const saveAs = `${row.category} - ${row.last_name}, ${row.first_name}.${extension}`;
    await tell({
      title: `${fullName(row)} · ${row.category}`,
      body: [el("img", { class: "photo-full", src: url, alt: row.caption || "The photo" }),
             row.caption ? el("p", {}, row.caption) : null,
             el("p", {}, el("a", { href: url, download: saveAs }, "Download this photo"))],
    });
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }

  async function takeDown(row) {
    const sure = await check({
      title: `Take down ${fullName(row)}'s photo?`,
      body: `It is removed from ${row.category} and put in Drive's trash. `
        + "They can send another while the category is open.",
      confirmLabel: "Take it down",
      danger: true,
    });
    if (!sure) return;
    try {
      await api.del(`/admin/photos/entries/${row.id}`);
      data.entries = data.entries.filter((r) => r.id !== row.id);
      const category = data.categories.find((c) => c.id === row.category_id);
      if (category) category.photos -= 1;
      draw();
    } catch (error) {
      await tell({ body: error.message });
    }
  }
}

/* THE CATEGORIES. One form at a time: the one for a new category at the
 * bottom, or one row's in place of the row. */
function categoriesTab(host, data) {
  let editing = null;          // category id being edited
  let errors = [];

  draw();

  function draw() {
    clear(host);
    if (data.categories.length) {
      add(host, table([
        { key: "name", label: "Category",
          render: (row) => el("span", {}, el("strong", {}, row.name),
            row.description ? el("span", { class: "small muted photo-description" },
                                 row.description) : null) },
        { key: "accepting", label: "Taking photos",
          render: (row) => row.accepting
            ? el("span", { class: "pill pill--done" }, "✓ Open")
            : el("span", { class: "pill" }, "Closed") },
        { key: "photos", label: "Photos", render: (row) => String(row.photos) },
        { key: "actions", label: "",
          render: (row) => el("div", { class: "btn-row" },
            button(row.accepting ? "Close" : "Open", {
              variant: "btn--small",
              onclick: () => save(row, { accepting: !row.accepting }),
            }),
            button("Edit", {
              variant: "btn--small btn--quiet",
              onclick: () => { editing = row.id; errors = []; draw(); },
            }),
            button("Delete", {
              variant: "btn--small btn--quiet btn--danger",
              onclick: () => remove(row),
            })) },
      ], data.categories, { caption: "Photo contest categories" }));
    } else {
      add(host, emptyState("No categories",
        "Add the first one below, like “Best flower photo”."));
    }

    const current = data.categories.find((c) => c.id === editing);
    add(host,
      el("h2", {}, current ? `Edit “${current.name}”` : "Add a category"),
      form(current));
  }

  function form(current) {
    const name = input({ value: current ? current.name : "", maxlength: data.max_name,
                         placeholder: "Best stuffed animal photo" });
    const description = el("textarea", { rows: 3, maxlength: data.max_description,
      placeholder: "What counts, and any rules. Delegates see this above the upload." },
      current ? current.description || "" : "");
    const accepting = el("input", { type: "checkbox",
                                    checked: (current ? current.accepting : true) || null });
    return el("div", { class: "panel" },
      errorSummary(errors),
      field({ id: "photo-category-name", label: "Name", required: true,
              control: name, wide: true }),
      field({ id: "photo-category-description", label: "Description",
              control: description, wide: true }),
      el("label", { class: "choice" }, accepting,
        el("span", {},
          el("span", { class: "choice__name" }, "Taking photos"),
          el("span", { class: "choice__why" },
            "Delegates can upload only while this is ticked."))),
      el("div", { class: "btn-row" },
        button(current ? "Save changes" : "Add category", {
          variant: "btn--primary",
          onclick: () => (current
            ? save(current, { name: name.value, description: description.value,
                              accepting: accepting.checked })
            : create({ name: name.value, description: description.value,
                       accepting: accepting.checked })),
        }),
        current ? button("Cancel", {
          variant: "btn--quiet",
          onclick: () => { editing = null; errors = []; draw(); },
        }) : null));
  }

  async function create(payload) {
    try {
      const result = await api.post("/admin/photos/categories", payload);
      data.categories.push(result.category);
      errors = [];
      draw();
    } catch (error) {
      errors = error.errors && error.errors.length ? error.errors : [error.message];
      draw();
    }
  }

  async function save(row, payload) {
    try {
      const result = await api.patch(`/admin/photos/categories/${row.id}`, payload);
      Object.assign(row, result.category);
      for (const entry of data.entries) {
        if (entry.category_id === row.id) entry.category = row.name;
      }
      editing = null;
      errors = [];
      draw();
    } catch (error) {
      if (editing === row.id) {
        errors = error.errors && error.errors.length ? error.errors : [error.message];
        draw();
      } else {
        await tell({ body: error.message });
      }
    }
  }

  async function remove(row) {
    const sure = await check({
      title: `Delete “${row.name}”?`,
      body: row.photos
        ? `Its ${row.photos} photo${row.photos === 1 ? "" : "s"} are deleted with it `
          + "and put in Drive's trash, where they can be recovered for 30 days."
        : "It has no photos.",
      confirmLabel: "Delete category",
      danger: true,
    });
    if (!sure) return;
    try {
      await api.del(`/admin/photos/categories/${row.id}`);
      data.categories = data.categories.filter((c) => c.id !== row.id);
      data.entries = data.entries.filter((e) => e.category_id !== row.id);
      if (editing === row.id) editing = null;
      draw();
    } catch (error) {
      await tell({ body: error.message });
    }
  }
}
