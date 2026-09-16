"""The only code that talks to the Drive puppet (apps-script/Code.gs).

Contest entries are filed under the AUTOMATED Drive root: one folder per
contest, then one per chapter. This module never reads, lists or writes the
per-school packet folders that hold medical forms and waivers -- those are
uploaded by sponsors by hand, and no code here knows where they are.

TWO IMPLEMENTATIONS, CHOSEN BY THE ENVIRONMENT
    APPS_SCRIPT_URL + APPS_SCRIPT_KEY   the real puppet
    DRIVE_LOCAL_DIR                     a folder on this machine, for local
                                        work and the test suite

In production neither fallback applies: with CAJCL_ENV=production and no
puppet configured, uploads fail with a sentence rather than landing on a
container's disk that disappears at the next scale-down.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import pathlib
import time
import urllib.error
import urllib.request


class DriveUnavailable(Exception):
    """Drive could not be reached, or is not configured. Nothing was saved."""


class Drive:
    def mkdir(self, parent_id: str, name: str) -> str:
        raise NotImplementedError

    def upload(self, folder_id: str, name: str, mime_type: str, data: bytes) -> str:
        raise NotImplementedError

    def fetch(self, file_id: str) -> bytes:
        raise NotImplementedError

    def trash(self, file_id: str) -> None:
        raise NotImplementedError


class AppsScriptDrive(Drive):
    """Signed requests to the puppet's /exec URL.

    Apps Script answers a POST with a 302 to googleusercontent.com, which must
    be followed with a GET. urllib does exactly that for a 302, which is why
    this uses urllib rather than anything cleverer.
    """

    TIMEOUT_SECONDS = 90

    def __init__(self, url: str, key: str):
        self.url = url
        self.key = key.encode()

    def _call(self, op: str, **fields) -> dict:
        ts = str(int(time.time()))
        # Must match verify() in Code.gs, field for field.
        material = ".".join([ts, op, fields.get("folderId", ""),
                             fields.get("name", ""), fields.get("fileId", "")])
        sig = hmac.new(self.key, material.encode(), hashlib.sha256).hexdigest()
        body = json.dumps({"op": op, "ts": ts, "sig": sig, **fields}).encode()
        request = urllib.request.Request(
            self.url, data=body, method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            raise DriveUnavailable(f"Drive did not answer ({error}).") from None
        if not payload.get("ok"):
            raise DriveUnavailable(f"Drive refused the request: {payload.get('error')}")
        return payload

    def mkdir(self, parent_id: str, name: str) -> str:
        return self._call("mkdir", folderId=parent_id, name=name)["folderId"]

    def upload(self, folder_id: str, name: str, mime_type: str, data: bytes) -> str:
        return self._call("upload", folderId=folder_id, name=name, mimeType=mime_type,
                          contentBase64=base64.b64encode(data).decode())["fileId"]

    def fetch(self, file_id: str) -> bytes:
        return base64.b64decode(self._call("fetch", fileId=file_id)["contentBase64"])

    def trash(self, file_id: str) -> None:
        self._call("trash", fileId=file_id)


class LocalDrive(Drive):
    """Folders on disk, with paths as ids. For development and tests only.

    Ids are paths relative to the root, and every one is resolved and checked
    to stay inside it, so a crafted id cannot read a file elsewhere.
    """

    def __init__(self, root: str):
        self.root = pathlib.Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, ident: str) -> pathlib.Path:
        path = (self.root / ident).resolve()
        if path != self.root and self.root not in path.parents:
            raise DriveUnavailable("that is not a file in the local Drive")
        return path

    @staticmethod
    def _safe(name: str) -> str:
        return "".join(c if c.isalnum() or c in " .,-_()" else "_" for c in name).strip() or "_"

    def mkdir(self, parent_id: str, name: str) -> str:
        path = self._path(parent_id) / self._safe(name)
        path.mkdir(parents=True, exist_ok=True)
        return str(path.relative_to(self.root))

    def upload(self, folder_id: str, name: str, mime_type: str, data: bytes) -> str:
        folder = self._path(folder_id)
        folder.mkdir(parents=True, exist_ok=True)
        stem = self._safe(name)
        path = folder / stem
        counter = 1
        while path.exists():        # Drive keeps both; so does this
            counter += 1
            path = folder / f"{counter} {stem}"
        path.write_bytes(data)
        return str(path.relative_to(self.root))

    def fetch(self, file_id: str) -> bytes:
        path = self._path(file_id)
        if not path.is_file():
            raise DriveUnavailable("that file is no longer in the local Drive")
        return path.read_bytes()

    def trash(self, file_id: str) -> None:
        path = self._path(file_id)
        if path.is_file():
            trash = self.root / ".trash"
            trash.mkdir(exist_ok=True)
            path.replace(trash / f"{int(time.time() * 1000)} {path.name}")


_override: Drive | None = None


def use(drive: Drive | None) -> None:
    """Install a Drive for the test suite, or None to go back to the environment."""
    global _override
    _override = drive


def client() -> Drive:
    if _override is not None:
        return _override
    url = os.environ.get("APPS_SCRIPT_URL")
    key = os.environ.get("APPS_SCRIPT_KEY")
    if url and key:
        return AppsScriptDrive(url, key)
    local = os.environ.get("DRIVE_LOCAL_DIR")
    if local and os.environ.get("CAJCL_ENV") != "production":
        return LocalDrive(local)
    raise DriveUnavailable(
        "Contest uploads are not switched on yet: the Drive connection is not "
        "configured. Nothing was saved. Please tell state@uhsjcl.org.")


def root_folder(configured: str) -> str:
    """The contests root. A local Drive needs no folder id and uses its own root."""
    if configured:
        return configured
    if isinstance(client(), LocalDrive):
        return "."
    raise DriveUnavailable(
        "Contest uploads are not switched on yet: no Drive folder is set for "
        "them in Settings. Nothing was saved. Please tell state@uhsjcl.org.")
