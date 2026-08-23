/* config.js — the API base URL. NOT a secret.
 *
 * The frontend never holds a database credential and never talks to Turso.
 * Everything routes through Modal, including basic reads, because Modal is
 * where authentication and authorization happen.
 *
 * A future commissioner changes this one line when the Modal app is redeployed
 * under a new name. Nothing else in the frontend knows the URL.
 */
window.CAJCL_CONFIG = {
  apiBase: location.hostname === "localhost" || location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:8000"
    : "https://techuhsjcl--cajcl-2027-web.modal.run",
};
