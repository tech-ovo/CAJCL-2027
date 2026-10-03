/* Join a chapter with its join code.
 *
 * WHO THIS IS FOR
 *   A student holding a handout from their sponsor. No account, no code of
 *   their own yet: they type the chapter's join code with their name, grade
 *   and Latin level, and are signed in and given an access code of their own.
 *   The QR on the handout opens this page with the join code filled in.
 *
 * THE ACCESS CODE IS SHOWN ONCE
 *   It is stored scrambled and nothing can read it back, so the screen that
 *   shows it asks to be told it has been saved before it lets them go on. A
 *   student who loses it is not stuck -- their sponsor can issue another -- but
 *   it is a trip to the sponsor that one tick here prevents.
 *
 * THEY ARE PENDING, AND CAN CARRY ON
 *   Nothing here waits for the sponsor. Until the sponsor approves them their
 *   registration is "preliminary" -- it is in no total and no invoice -- but
 *   they fill in their forms straight away.
 */

import * as api from "../api.js";
import { add, el, clear, field, input, button, errorSummary } from "../ui.js";
import { route, adopt } from "../main.js";
import { formatJoinCode } from "./joincode.js";

/* Matches latin_level in the schema and backend/lib/joining.py. */
const LEVELS = [
  ["Middle school", [["MS-1", "Latin I"], ["MS-2", "Latin II"],
                     ["MS-3", "Latin III"]]],
  ["High school", [["HS-1", "Latin I"], ["HS-2", "Latin II"],
                   ["HS-3", "Latin III"], ["HS-Adv", "Advanced"]]],
];

export async function joinPage(host, params = []) {
  const preset = params[0] ? decodeURIComponent(params[0]) : "";
  let errors = [];

  const code = input({
    autocomplete: "off", autocapitalize: "characters", spellcheck: "false",
    maxlength: "9", class: "mono", placeholder: "ABCD-EFGH",
    value: formatJoinCode(preset),
    oninput: (event) => {
      // The dash is drawn for them, the way the sign-in boxes draw theirs.
      event.target.value = formatJoinCode(event.target.value);
    },
  });
  const first = input({ autocomplete: "given-name" });
  const last = input({ autocomplete: "family-name" });
  const grade = el("select", {},
    el("option", { value: "" }, "Choose one"),
    ...[6, 7, 8, 9, 10, 11, 12].map((g) => el("option", { value: g }, String(g))));
  const level = el("select", {},
    el("option", { value: "" }, "Choose one"),
    ...LEVELS.map(([group, options]) => el("optgroup", { label: group },
      ...options.map(([value, text]) => el("option", { value }, text)))));

  const submit = button("Join", {
    variant: "btn--primary", type: "submit",
  });

  function render() {
    clear(host);
    const form = el("form", {
      novalidate: true,
      onsubmit: async (event) => {
        event.preventDefault();
        errors = [];
        if (!code.value.trim()) errors.push("Enter your chapter's join code.");
        if (!first.value.trim()) errors.push("Enter your first name.");
        if (!last.value.trim()) errors.push("Enter your last name.");
        if (!grade.value) errors.push("Choose your grade.");
        if (!level.value) errors.push("Choose your Latin level.");
        if (errors.length) { render(); return; }

        submit.disabled = true;
        try {
          const result = await api.post("/auth/join", {
            join_code: code.value,
            first_name: first.value,
            last_name: last.value,
            grade: Number(grade.value),
            latin_level: level.value,
          });
          api.token.set(result.token);
          adopt(result.person);
          showCode(result);
        } catch (problem) {
          submit.disabled = false;
          errors = problem.errors && problem.errors.length
            ? problem.errors : [problem.message];
          render();
        }
      },
    });

    add(form,
      errors.length ? errorSummary(errors) : null,
      field({ id: "join-code", label: "Join code", required: true, control: code,
              help: "On the handout from your sponsor.", wide: true }),
      el("div", { class: "grid" },
        el("div", { class: "span-6" },
          field({ id: "join-first", label: "First name", required: true,
                  control: first })),
        el("div", { class: "span-6" },
          field({ id: "join-last", label: "Last name", required: true,
                  control: last })),
        el("div", { class: "span-6" },
          field({ id: "join-grade", label: "Grade", required: true,
                  control: grade })),
        el("div", { class: "span-6" },
          field({ id: "join-level", label: "Latin level", required: true,
                  control: level }))),
      el("div", { class: "btn-row" }, submit));

    add(host, el("section", { class: "with-rail" },
      el("div", { class: "rail" },
        el("div", { class: "rail__item" },
          el("p", { class: "label label--ink" }, "What happens next"),
          el("p", { class: "small muted" },
            "You get an access code of your own, and can fill in your forms "
            + "straight away. Your sponsor then approves you.")),
        el("div", { class: "rail__item" },
          el("p", { class: "label label--ink" }, "Already registered?"),
          el("p", { class: "small muted" },
            el("a", { href: "#/sign-in" }, "Sign in with your access code"),
            "."))),
      el("div", {},
        el("h1", {}, "Join your chapter"),
        el("p", { class: "lede" },
          "Type the join code from your sponsor's handout, then tell us who "
          + "you are."),
        form)));
  }

  /* The one screen where the access code can be read. */
  function showCode(result) {
    clear(host);
    const saved = el("input", { type: "checkbox", id: "join-saved" });
    const go = button("Continue to my forms", {
      variant: "btn--primary",
      disabled: true,
      onclick: async () => {
        location.hash = "#/activity-sheet";
        await route();
      },
    });
    saved.onchange = () => { go.disabled = !saved.checked; };

    add(host, el("section", { class: "panel", role: "status" },
      el("h1", {}, `Welcome, ${result.person.first_name}`),
      el("p", { class: "lede" },
        `You have joined ${result.school.name}.`),
      el("p", { class: "label" }, "Your access code"),
      el("p", { class: "tabula__code mono", style: "font-size:1.75rem" },
        result.code),
      el("p", {},
        "This is the only time this code is shown, and it is how you sign in "
        + "again. Write it down or take a screenshot now. If you lose it, "
        + "your sponsor can issue you a new one."),
      el("div", { class: "banner banner--info", style: "margin:1.5rem 0" },
        el("span", { class: "banner__label" }, "Preliminary"),
        el("span", {},
          "Your sponsor still has to approve you. Until then you can fill in "
          + "your forms, but you are not yet counted in your chapter's total.")),
      el("label", { class: "choice" }, saved,
        el("span", {},
          el("span", { class: "choice__name" },
            "I have saved my access code"))),
      el("div", { class: "btn-row" },
        button("Copy my code", {
          onclick: async () => {
            try { await navigator.clipboard.writeText(result.code); }
            catch (ignored) { /* they can still read it above */ }
          },
        }),
        go)));
  }

  render();
}
