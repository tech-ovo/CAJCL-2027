/**
 * The Drive puppet.
 *
 * This exists for exactly one reason: only Apps Script can act as Timothy's
 * Google identity and write to his personal Drive under his 5 TB quota. Modal
 * cannot, absent domain-wide delegation. That is the whole justification, and
 * nothing else should ever be added here.
 *
 * IT HOLDS NO CONFIGURATION. Folder IDs, filenames, and retention rules all
 * travel in the request payload from Modal. The ONE secret in Script Properties
 * is a shared HMAC key, because this web app is deployed as "execute as me /
 * anyone with the link" and otherwise has no way to know the caller is actually
 * our backend.
 *
 * WHAT IT MUST NEVER TOUCH
 *   The scanned medical forms and waivers. Those live in a SEPARATE per-school
 *   folder that a sponsor uploads to with their own Google account and shares
 *   manually with the Convention Presidents. The database stores only a URL
 *   string. Keeping the two roots physically separate means no future change to
 *   this automated path can widen access to minors' medical data by accident.
 *   Do not merge them for convenience.
 *
 * SETUP
 *   1. Script Properties: set SHARED_KEY to a long random string, and set the
 *      same value as APPS_SCRIPT_KEY in Modal Secrets.
 *   2. Deploy > New deployment > Web app, execute as me, anyone with the link.
 *   3. Put the /exec URL in Modal Secrets as APPS_SCRIPT_URL.
 *
 *   Re-deploying can mint a NEW URL. If exports start failing silently, that is
 *   the first thing to check. See docs/RUNBOOK.md.
 */

/** Requests older than this are rejected, so a captured request cannot be
 *  replayed tomorrow. */
var MAX_AGE_SECONDS = 300;

function doPost(e) {
  try {
    var request = JSON.parse(e.postData.contents);

    if (!verify(request)) {
      return json({ ok: false, error: 'signature rejected' });
    }

    switch (request.op) {
      case 'upload': return json(upload(request));
      case 'list':   return json(list(request));
      case 'mkdir':  return json(mkdir(request));
      case 'trash':  return json(trash(request));
      default:       return json({ ok: false, error: 'unknown op: ' + request.op });
    }
  } catch (error) {
    return json({ ok: false, error: String(error) });
  }
}

/**
 * HMAC-SHA256 over the timestamp and the operation, with a freshness window.
 *
 * The timestamp is part of the signed material, so an attacker cannot take a
 * valid request and change its clock. Comparison is constant-time-ish: Apps
 * Script has no timingSafeEqual, and over the public internet against a
 * 256-bit key the difference is not the weak point.
 */
function verify(request) {
  var key = PropertiesService.getScriptProperties().getProperty('SHARED_KEY');
  if (!key) throw new Error('SHARED_KEY is not set in Script Properties');

  var age = Math.abs((Date.now() / 1000) - Number(request.ts || 0));
  if (!request.ts || age > MAX_AGE_SECONDS) return false;

  var material = String(request.ts) + '.' + String(request.op) + '.' +
                 String(request.folderId || '') + '.' + String(request.name || '');
  var computed = Utilities.computeHmacSha256Signature(material, key);

  var hex = computed.map(function (byte) {
    return ('0' + (byte & 0xFF).toString(16)).slice(-2);
  }).join('');

  var given = String(request.sig || '');
  if (given.length !== hex.length) return false;
  var mismatch = 0;
  for (var i = 0; i < hex.length; i++) {
    mismatch |= hex.charCodeAt(i) ^ given.charCodeAt(i);
  }
  return mismatch === 0;
}

/** Write a file. Modal sends the bytes base64-encoded and names the folder. */
function upload(request) {
  var folder = DriveApp.getFolderById(request.folderId);
  var bytes = Utilities.base64Decode(request.contentBase64);
  var blob = Utilities.newBlob(bytes, request.mimeType || 'application/octet-stream',
                               request.name);
  var file = folder.createFile(blob);
  return { ok: true, fileId: file.getId(), name: file.getName(),
           size: file.getSize(), url: file.getUrl() };
}

/**
 * List a folder, so Modal can cache the structure and file IDs in the database
 * and resolve them from there rather than crawling Drive on every request.
 */
function list(request) {
  var folder = DriveApp.getFolderById(request.folderId);
  var out = [];

  var folders = folder.getFolders();
  while (folders.hasNext()) {
    var sub = folders.next();
    out.push({ id: sub.getId(), name: sub.getName(), kind: 'folder' });
  }

  var files = folder.getFiles();
  while (files.hasNext()) {
    var file = files.next();
    out.push({ id: file.getId(), name: file.getName(), kind: 'file',
               size: file.getSize(), mimeType: file.getMimeType(),
               updated: file.getLastUpdated().toISOString() });
  }
  return { ok: true, entries: out };
}

/** Create a subfolder, or return the existing one. Idempotent on purpose:
 *  Modal calls this before every upload and must not accumulate duplicates. */
function mkdir(request) {
  var parent = DriveApp.getFolderById(request.folderId);
  var existing = parent.getFoldersByName(request.name);
  if (existing.hasNext()) {
    var found = existing.next();
    return { ok: true, folderId: found.getId(), created: false };
  }
  var made = parent.createFolder(request.name);
  return { ok: true, folderId: made.getId(), created: true };
}

/** Move a file to the trash. Never a permanent delete -- a mistake here is
 *  somebody's contest entry, and the trash is a thirty-day undo. */
function trash(request) {
  DriveApp.getFileById(request.fileId).setTrashed(true);
  return { ok: true, trashed: request.fileId };
}

function json(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}
