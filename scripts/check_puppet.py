"""Ask the deployed Drive puppet (apps-script/Code.gs) which version it runs.

    APPS_SCRIPT_URL='https://script.google.com/macros/s/.../exec' \
    APPS_SCRIPT_KEY='...' python scripts/check_puppet.py

Both values are in the Modal secrets (`apps-script`); copy them from the Modal
dashboard. This is for the moment "I deployed it and I still get the old
error": the URL Modal calls may belong to a different deployment from the one
that was updated, and this shows what THAT URL is running.

    version <date>        the new script. Anything else was not deployed to
                          this URL.
    unknown op: ping      an older script is running at this URL.
    signature rejected    the key does not match Script Properties SHARED_KEY.
"""

from __future__ import annotations

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from backend.lib import drive  # noqa: E402


def main() -> int:
    url, key = os.environ.get("APPS_SCRIPT_URL"), os.environ.get("APPS_SCRIPT_KEY")
    if not (url and key):
        print("Set APPS_SCRIPT_URL and APPS_SCRIPT_KEY (see the top of this file).",
              file=sys.stderr)
        return 2
    puppet = drive.AppsScriptDrive(url, key)
    print(f"URL ends …{url[-12:]}")

    try:
        print("version", puppet._call("ping")["version"])
    except drive.DriveUnavailable as error:
        print(error)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
