/* Sign in with a code.
 *
 * The check symbol is validated HERE, before any request is sent, so a typo
 * produces immediate feedback rather than an attempt against the rate limiter.
 * A delegate who fumbles their code five times would otherwise lock themselves
 * out of their own account for an hour.
 */

import * as api from "../api.js";
import { add, el, clear, field, input, button, errorSummary } from "../ui.js";
import { checkSymbolOk, formatCode } from "../codes.js";
import { state, route, adopt, landingFor } from "../main.js";

export async function signInPage(host) {
  let error = null;

  function render() {
    clear(host);

    /* THIRTEEN BOXES, GROUPED 3-5-5, WITH THE DASHES DRAWN IN.
     *
     * A single field looked like it wanted the dashes typed, and people typed
     * them — into a field that stripped and re-inserted them, so the caret
     * jumped and characters appeared to vanish. The boxes remove the question:
     * the dashes are printed between the groups and are not typed at all.
     *
     * It also shows the shape of the thing. A code is 3 + 5 + 5 and the sheet
     * prints it that way, so somebody transcribing from paper can see where
     * they are without counting.
     *
     * Everything the old field forgave, these still forgive: lower case, the
     * confusable letters, and a pasted code with its dashes in.
     */
    const boxes = [];

    function codeValue() {
      const raw = boxes.map((box) => box.value).join("");
      return formatCode(raw);
    }

    function focusBox(index) {
      const box = boxes[Math.max(0, Math.min(boxes.length - 1, index))];
      if (box) { box.focus(); box.select(); }
    }

    function fill(from, text) {
      // A paste, or a code typed faster than one box at a time. Dashes and
      // spaces are dropped; everything else lands one character per box.
      const characters = String(text).replace(/[^A-Za-z0-9]/g, "").toUpperCase();
      let index = from;
      for (const character of characters) {
        if (index >= boxes.length) break;
        boxes[index].value = character;
        index += 1;
      }
      focusBox(index);
    }

    for (let position = 0; position < 13; position += 1) {
      const box = el("input", {
        type: "text",
        class: "code-box mono",
        inputmode: position < 3 ? "text" : "latin",
        maxlength: "1",
        spellcheck: "false",
        autocapitalize: "characters",
        autocomplete: position === 0 ? "one-time-code" : "off",
        "aria-label": `Character ${position + 1} of 13`,
        onfocus: (event) => event.target.select(),
        oninput: (event) => {
          const typed = event.target.value;
          if (typed.length > 1) {          // a paste landed in one box
            event.target.value = "";
            fill(position, typed);
            return;
          }
          event.target.value = typed.toUpperCase();
          if (typed) focusBox(position + 1);
        },
        onkeydown: (event) => {
          if (event.key === "Backspace" && !event.target.value) {
            event.preventDefault();
            const previous = boxes[position - 1];
            if (previous) { previous.value = ""; focusBox(position - 1); }
          } else if (event.key === "ArrowLeft") {
            event.preventDefault(); focusBox(position - 1);
          } else if (event.key === "ArrowRight") {
            event.preventDefault(); focusBox(position + 1);
          }
        },
        onpaste: (event) => {
          event.preventDefault();
          fill(position, (event.clipboardData || window.clipboardData)
                           .getData("text"));
        },
      });
      boxes.push(box);
    }

    const codeInput = el("div",
      { class: "code-boxes", role: "group",
        "aria-label": "Your access code, thirteen characters" },
      ...boxes.slice(0, 3),
      el("span", { class: "code-boxes__dash", "aria-hidden": "true" }, "–"),
      ...boxes.slice(3, 8),
      el("span", { class: "code-boxes__dash", "aria-hidden": "true" }, "–"),
      ...boxes.slice(8, 13));

    const status = el("div");
    const submit = button("Sign in", { variant: "btn--primary", type: "submit" });

    const form = el("form", {
      novalidate: true,
      onsubmit: async (event) => {
        event.preventDefault();
        const code = codeValue();

        if (!checkSymbolOk(code)) {
          error = "Check that code again. It is printed on your registration sheet.";
          render();
          return;
        }

        error = null;
        submit.disabled = true;
        submit.textContent = "Signing in…";
        try {
          const result = await api.post("/auth/redeem", { code },
                                        { statusHost: status });
          api.token.set(result.token);
          // The response already says who this is, so the next page renders
          // from it instead of asking again.
          adopt(result.person);
          // Not the welcome page: somebody who has just typed a code has an
          // intention, and the welcome page answers none of them.
          location.hash = landingFor(result.person);
          await route();
        } catch (problem) {
          error = problem.message;
          render();
        }
      },
    });

    add(form, 
      error ? errorSummary([error]) : null,
      el("div", { class: "field field--wide" },
        el("p", { class: "field__label label label--ink" }, "Your access code"),
        codeInput,
        el("p", { class: "field__help" },
          "Printed on your registration sheet. Case does not matter, and you "
          + "can paste the whole thing into the first box.")),
      el("div", { class: "btn-row" }, submit),
      status,
    );

    add(host, el("section", { class: "with-rail" },
      // Each heading and its text are ONE element. On a phone the rail becomes
      // a wrapping row, and loose children wrapped wherever they fitted — so
      // "Where codes come from" ended up indented beside the block above it.
      el("div", { class: "rail" },
        el("div", { class: "rail__item" },
          el("p", { class: "label label--ink" }, "Signing in"),
          el("p", { class: "small muted" },
            "Scan the square code on your sheet with your phone camera and you "
            + "will not need to type anything at all.")),
        // Everyone signs in the same way, but "ask your sponsor" is wrong
        // advice for the sponsor, and worse advice for a convention chair.
        // Say who issues a code to whom, once, plainly.
        // A two-column list put the term and the answer in the same small
        // capitals, so neither led — and squeezed the answers into a column
        // narrow enough to wrap three words onto two lines. A heading with a
        // line under it has the hierarchy the content already had.
        // `label--ink`, not plain `label`: this one is a HEADING over the list
        // beneath it, and the muted default made the heading fainter than the
        // content it introduces.
        el("div", { class: "rail__item" },
          el("p", { class: "label label--ink" }, "Where codes come from"),
          el("div", { class: "rail-list" },
            ...[["Delegates", "Your sponsor"],
                ["Chaperones", "Your chapter's sponsor"],
                ["Sponsors", "A convention chair"],
                ["Board", "A convention president"]].map(([who, source]) =>
              el("p", { class: "small muted" },
                el("strong", {}, who), el("br"), source))))),
      el("div", {},
        el("h1", {}, "Sign in"),
        el("p", { class: "lede" },
          "Enter the code from your registration sheet. You will stay signed " +
          "in on this device."),
        form,
        el("hr", { class: "hair" }),
        el("p", { class: "small muted" },
          "Lost your code? Whoever issued it can issue another. The old one " +
          "stops working the moment they do."),
        el("p", { class: "small muted" },
          "Using a shared computer? Sign out when you are finished — the button " +
          "is in the bar at the top of every page."))));
  }

  render();
}
