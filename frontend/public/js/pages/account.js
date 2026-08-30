/* A person's own account: where they are signed in, and how to end a session.
 *
 * Assume shared devices. A school Chromebook accumulates a dozen sessions over
 * a weekend, and a delegate who signed in on a friend's phone needs a way to
 * undo that from their own.
 */

import * as api from "../api.js";
import { add, el, clear, tabula, button, table, localDate, emptyState, personNumber } from "../ui.js";
import { state } from "../main.js";

export async function accountPage(host) {
  async function render() {
    clear(host);
    const me = await api.get("/auth/me", { statusHost: host });
    state.me = me;
    const sessions = me.sessions || [];

    add(host, 
      tabula({
        label: me.person_type === "delegate" ? "Delegate" : "Adult",
        name: `${me.first_name} ${me.last_name}`,
        left: me.school.name,
        right: personNumber(me.school || {}, me),
      }),

      el("section", { class: "grid" },
        el("div", { class: "span-7" },
          el("h2", {}, "Where you are signed in"),
          el("p", { class: "muted" },
            "One row per device. If you see something you do not recognise, or " +
            "you used a shared computer, sign that device out."),
          sessions.length
            ? table([
                { key: "device", label: "Device",
                  render: (row) => describeDevice(row.user_agent) },
                { key: "last_seen_at", label: "Last used",
                  render: (row) => localDate(row.last_seen_at, { withTime: true }) },
                { key: "actions", label: "Action",
                  render: (row) => button("Sign out", {
                    variant: "btn--small",
                    onclick: async () => {
                      await api.post(`/auth/sessions/${row.id}/revoke`, {});
                      await render();
                    },
                  }) },
              ], sessions, { caption: "Your active sessions" })
            : emptyState("No other devices",
                "This is the only device signed in to your account.")),

        el("div", { class: "span-4" },
          el("h2", {}, "Your access"),
          el("dl", { class: "detail" },
            el("dt", {}, "Chapter"), el("dd", {}, me.school.name),
            el("dt", {}, "Roles"),
            // Roles are stored as slugs -- "delegate", "sponsor". The chapter
            // beside them is a proper name, and a lowercase word next to it
            // reads as a mistake.
            el("dd", {}, (me.roles || []).map(titleCase).join(", ") || "—")),
          el("hr", { class: "hair" }),
          el("p", { class: "small muted" },
            "Your name and chapter are set by your sponsor. If either is wrong, " +
            "ask them to correct it — you cannot change them here."))));
  }

  await render();
}

/** "chapter_leader" -> "Chapter leader". */
function titleCase(slug) {
  const words = String(slug || "").replace(/[_-]+/g, " ").trim();
  return words ? words[0].toUpperCase() + words.slice(1) : "";
}

function describeDevice(userAgent) {
  const ua = String(userAgent || "");
  if (!ua) return "Unknown device";
  if (/CrOS/.test(ua)) return "Chromebook";
  if (/iPhone/.test(ua)) return "iPhone";
  if (/iPad/.test(ua)) return "iPad";
  if (/Android/.test(ua)) return "Android phone";
  if (/Macintosh/.test(ua)) return "Mac";
  if (/Windows/.test(ua)) return "Windows PC";
  return "Web browser";
}
