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
import { state, route } from "../main.js";

export async function signInPage(host) {
  let error = null;

  function render() {
    clear(host);

    const codeInput = input({
      class: "mono",
      autocomplete: "one-time-code",
      spellcheck: "false",
      autocapitalize: "characters",
      // Not "DEL-XXXXX-XXXXX": a sponsor or a chair whose code starts SPO or
      // ADM should not be left wondering whether they are on the right screen.
      placeholder: "XXX-XXXXX-XXXXX",
      maxlength: 15,
      oninput: (event) => {
        const atEnd = event.target.selectionStart === event.target.value.length;
        event.target.value = formatCode(event.target.value);
        if (atEnd) {
          const end = event.target.value.length;
          event.target.setSelectionRange(end, end);
        }
      },
    });

    const status = el("div");
    const submit = button("Sign in", { variant: "btn--primary", type: "submit" });

    const form = el("form", {
      novalidate: true,
      onsubmit: async (event) => {
        event.preventDefault();
        const code = codeInput.value.trim();

        if (!checkSymbolOk(code)) {
          error = "Check that code again — one of the characters does not look " +
                  "right. It is printed on your registration sheet.";
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
          state.me = null;
          location.hash = "#/";
          await route();
        } catch (problem) {
          error = problem.message;
          render();
        }
      },
    });

    add(form, 
      error ? errorSummary([error]) : null,
      field({
        id: "code",
        label: "Your access code",
        help: "Fifteen characters, printed on your registration sheet. " +
              "It is not case sensitive.",
        required: true,
        control: codeInput,
      }),
      el("div", { class: "btn-row" }, submit),
      status,
    );

    add(host, el("section", { class: "with-rail" },
      el("div", { class: "rail" },
        el("p", { class: "label" }, "Signing in"),
        el("p", { class: "small muted" },
          "Scan the square code on your sheet with your phone camera and you " +
          "will not need to type anything at all."),
        el("hr", { class: "hair" }),
        // Everyone signs in the same way, but "ask your sponsor" is wrong
        // advice for the sponsor, and worse advice for a convention chair.
        // Say who issues a code to whom, once, plainly.
        el("p", { class: "label" }, "Where codes come from"),
        el("dl", { class: "detail small" },
          el("dt", {}, "Delegates"), el("dd", {}, "Your sponsor"),
          el("dt", {}, "Chaperones"), el("dd", {}, "The chapter's sponsor"),
          el("dt", {}, "Sponsors"), el("dd", {}, "A convention chair"),
          el("dt", {}, "Board"), el("dd", {}, "A convention president"))),
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
