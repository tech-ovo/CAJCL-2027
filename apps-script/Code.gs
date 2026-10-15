/**
 * The Drive puppet.
 *
 * This exists for exactly one reason: only Apps Script can act as Timothy's
 * Google identity and write to his personal Drive under his 5 TB quota. Modal
 * cannot, absent domain-wide delegation. That is the whole justification, and
 * nothing else should ever be added here.
 *
 * `convert` is the same justification applied to Google Docs: reading a Doc
 * that is shared only with that account, and writing the converted copy to its
 * Drive, are things only this script can do. It reads a Doc and writes ONE
 * public HTML file into the folder it is told; it never lists or changes
 * anything else.
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

/** Pictures embedded in a converted page. Keep in step with htmlclean.py. */
var MAX_IMAGE_BYTES = 4 * 1024 * 1024;
var MAX_IMAGES = 40;
var MAX_IMAGE_TOTAL = 16 * 1024 * 1024;

function doPost(e) {
  try {
    var request = JSON.parse(e.postData.contents);

    if (!verify(request)) {
      return json({ ok: false, error: 'signature rejected' });
    }

    switch (request.op) {
      case 'upload': return json(upload(request));
      case 'fetch':  return json(fetch(request));
      case 'list':   return json(list(request));
      case 'mkdir':  return json(mkdir(request));
      case 'trash':  return json(trash(request));
      case 'convert': return json(convert(request));
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

  // fileId is signed too: without it, a captured `fetch` or `trash` could be
  // pointed at a different file inside the freshness window.
  // backend/lib/drive.py builds the same string; change both or neither.
  var material = String(request.ts) + '.' + String(request.op) + '.' +
                 String(request.folderId || '') + '.' + String(request.name || '') + '.' +
                 String(request.fileId || '');
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

/** Read a file back, so a judge can see an entry without being given access
 *  to the Drive folder -- whose chapter subfolders would say whose it is. */
function fetch(request) {
  var file = DriveApp.getFileById(request.fileId);
  return { ok: true, mimeType: file.getMimeType(),
           contentBase64: Utilities.base64Encode(file.getBlob().getBytes()) };
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

/**
 * Turn a Google Doc into a cleaned HTML file that anyone with the link can read.
 *
 * request.fileId   the Doc (signed, so a captured request cannot be aimed at
 *                  another Doc)
 * request.folderId where the HTML file lives; request.name what it is called
 *
 * The SAME file is rewritten on every call, found by name, so the link Modal
 * stores stays valid forever. If anything fails the previous copy is untouched.
 * Cleaning is cleanDocHtml below; the site build cleans again regardless.
 */
function convert(request) {
  var doc;
  try {
    doc = DriveApp.getFileById(request.fileId);
  } catch (error) {
    throw new Error('This script cannot open that Google Doc. Share the Doc with ' +
                    Session.getEffectiveUser().getEmail() + ' (Viewer is enough).');
  }
  if (doc.getMimeType() !== MimeType.GOOGLE_DOCS) {
    throw new Error('That link is not a Google Doc.');
  }

  // The zipped export: the HTML plus an images/ folder, which is the only
  // reliable way to get a Doc's pictures (the plain export links to Google
  // servers, and those links are not ours to depend on).
  var response = UrlFetchApp.fetch(
    'https://www.googleapis.com/drive/v3/files/' + encodeURIComponent(request.fileId) +
      '/export?mimeType=' + encodeURIComponent('application/zip'),
    { headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() },
      muteHttpExceptions: true });
  if (response.getResponseCode() !== 200) {
    throw new Error('Google could not export the Doc (' + response.getResponseCode() + ').');
  }
  var files = Utilities.unzip(response.getBlob().setContentType('application/zip'));
  var htmlBlob = null, pictures = {};
  files.forEach(function (blob) {
    var name = blob.getName();
    if (/\.html?$/i.test(name)) { if (!htmlBlob) htmlBlob = blob; }
    else pictures[name.replace(/^.*\//, '')] = blob;
  });
  if (!htmlBlob) throw new Error('Google\'s export of the Doc had no page in it.');

  var budget = { count: 0, bytes: 0 };
  var html = cleanDocHtml(htmlBlob.getDataAsString('UTF-8'), function (src) {
    var blob = pictures[String(src).replace(/^.*\//, '').split(/[?#]/)[0]];
    if (!blob) return '';
    var type = String(blob.getContentType() || '').toLowerCase();
    if (type === 'image/jpg') type = 'image/jpeg';
    if (type !== 'image/png' && type !== 'image/jpeg' && type !== 'image/gif') return '';
    var bytes = blob.getBytes();
    // The same ceilings the site build enforces (backend/lib/htmlclean.py);
    // a picture over them is left out here rather than failing the page.
    if (bytes.length > MAX_IMAGE_BYTES || budget.count >= MAX_IMAGES ||
        budget.bytes + bytes.length > MAX_IMAGE_TOTAL) return '';
    budget.count++;
    budget.bytes += bytes.length;
    return 'data:' + type + ';base64,' + Utilities.base64Encode(bytes);
  });

  var folder = DriveApp.getFolderById(request.folderId);
  var existing = folder.getFilesByName(request.name);
  var file;
  if (existing.hasNext()) {
    file = existing.next();
    file.setContent(html);
  } else {
    file = folder.createFile(request.name, html, MimeType.HTML);
  }
  file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
  return { ok: true, fileId: file.getId(), name: file.getName(),
           url: 'https://drive.google.com/uc?export=download&id=' + file.getId() };
}

/**
 * Reduce the HTML Google exports for a Doc to plain tags, with no styles.
 *
 * Google writes bold, italic and so on as CLASSES on <span>s, defined in a
 * <style> block, so deleting the styles would delete the emphasis. This reads
 * the style block first, turns those spans into <strong>/<em>/<u>/<sup>/<sub>,
 * and then drops every attribute except a link's href and a cell's
 * colspan/rowspan. Scripts go. Google's link redirects (google.com/url?q=...)
 * are unwrapped. A picture stays only if `resolveImage(src)` returns a
 * `data:image/...;base64,...` address for it (convert() supplies pictures from
 * the Doc's own export); with no resolver, pictures are dropped.
 *
 * It uses no Apps Script services, so it can be tried in any JavaScript
 * runtime. backend/lib/htmlclean.py is the same allowlist in Python; the site
 * build runs that one on every page, so this is the first pass, not the guard.
 */
function cleanDocHtml(source, resolveImage) {
  var KEEP = { p: 1, br: 1, hr: 1, ul: 1, ol: 1, li: 1, strong: 1, em: 1, u: 1,
               sub: 1, sup: 1, a: 1, table: 1, thead: 1, tbody: 1, tr: 1,
               th: 1, td: 1, blockquote: 1, code: 1, pre: 1, h2: 1, h3: 1, h4: 1 };
  var RENAME = { h1: 'h2', h2: 'h3', h3: 'h4', h4: 'h4', h5: 'h4', h6: 'h4',
                 b: 'strong', i: 'em' };

  var css = (source.match(/<style[^>]*>([\s\S]*?)<\/style>/i) || [0, ''])[1];
  var rules = {};
  css.replace(/\.([A-Za-z0-9_-]+)\s*\{([^}]*)\}/g, function (all, name, body) {
    rules[name] = (rules[name] || '') + ';' + body;
    return '';
  });
  function decorations(classAttr, inLink) {
    var open = '', close = '';
    var text = String(classAttr || '').split(/\s+/).map(function (c) { return rules[c] || ''; }).join(';');
    function wrap(tag) { open += '<' + tag + '>'; close = '</' + tag + '>' + close; }
    if (/font-weight\s*:\s*(700|bold)/i.test(text)) wrap('strong');
    if (/font-style\s*:\s*italic/i.test(text)) wrap('em');
    if (!inLink && /text-decoration\s*:[^;]*underline/i.test(text)) wrap('u');
    if (/vertical-align\s*:\s*super/i.test(text)) wrap('sup');
    if (/vertical-align\s*:\s*sub/i.test(text)) wrap('sub');
    return { open: open, close: close };
  }
  function attr(attrs, name) {
    var m = new RegExp('\\b' + name + '\\s*=\\s*(?:"([^"]*)"|\'([^\']*)\')', 'i').exec(attrs);
    return m ? (m[1] !== undefined ? m[1] : m[2]) : '';
  }
  function safeHref(raw) {
    var value = String(raw || '').replace(/&amp;/g, '&').trim();
    var wrapped = /^https?:\/\/(?:www\.)?google\.com\/url\?(.*)$/i.exec(value);
    if (wrapped) {
      var q = /(?:^|&)q=([^&]*)/.exec(wrapped[1]);
      try { value = q ? decodeURIComponent(q[1].replace(/\+/g, ' ')) : ''; } catch (e) { value = ''; }
    }
    if (!/^(https?:\/\/|mailto:|tel:|#.)/i.test(value)) return '';
    return value.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  }

  var body = (source.match(/<body[^>]*>([\s\S]*)<\/body>/i) || [0, source])[1];
  body = body.replace(/<!--[\s\S]*?-->/g, '')
             .replace(/<(script|style|head|iframe|object|embed|svg|form|noscript|template|title)\b[\s\S]*?<\/\1\s*>/gi, '');

  var out = [], stack = [], re = /<(\/?)([a-zA-Z][a-zA-Z0-9]*)([^>]*)>/g, last = 0, m;
  var linkDepth = 0;
  function closeTop() {
    var top = stack.pop();
    if (top.tag === 'a') linkDepth--;
    out.push(top.close);
  }
  while ((m = re.exec(body)) !== null) {
    out.push(body.substring(last, m.index));
    last = re.lastIndex;
    var closing = m[1] === '/', tag = m[2].toLowerCase(), attrs = m[3];
    tag = RENAME[tag] || tag;

    if (closing) {
      var at = -1;
      for (var i = stack.length - 1; i >= 0; i--) {
        if (stack[i].tag === tag || (tag === 'a' && stack[i].tag === 'a-dead')) { at = i; break; }
      }
      if (at >= 0) { while (stack.length > at) closeTop(); }
      continue;
    }
    if (tag === 'br' || tag === 'hr') { out.push('<' + tag + '>'); continue; }
    if (tag === 'img') {
      var uri = resolveImage ? String(resolveImage(attr(attrs, 'src')) || '') : '';
      if (/^data:image\/(png|jpeg|gif);base64,[A-Za-z0-9+\/]+=*$/.test(uri)) {
        var alt = attr(attrs, 'alt').replace(/\s+/g, ' ').trim().substring(0, 300);
        out.push('<img src="' + uri + '" alt="' + alt.replace(/"/g, '&quot;') + '">');
      }
      continue;
    }
    if (tag === 'span') {
      var d = decorations(attr(attrs, 'class'), linkDepth > 0);
      out.push(d.open);
      stack.push({ tag: 'span', close: d.close });
      continue;
    }
    if (tag === 'a') {
      var href = safeHref(attr(attrs, 'href'));
      if (!href) { stack.push({ tag: 'a-dead', close: '' }); continue; }
      out.push('<a href="' + href + '">');
      stack.push({ tag: 'a', close: '</a>' });
      linkDepth++;
      continue;
    }
    if (!KEEP[tag]) { stack.push({ tag: tag, close: '' }); continue; }
    var extra = '';
    if (tag === 'td' || tag === 'th') {
      ['colspan', 'rowspan'].forEach(function (name) {
        var v = parseInt(attr(attrs, name), 10);
        if (v > 1 && v <= 50) extra += ' ' + name + '="' + v + '"';
      });
    }
    out.push('<' + tag + extra + '>');
    stack.push({ tag: tag, close: '</' + tag + '>' });
  }
  out.push(body.substring(last));
  while (stack.length) closeTop();

  var html = out.join('');
  for (var pass = 0; pass < 3; pass++) {
    html = html.replace(/<(p|li|strong|em|u|sub|sup|a|blockquote|h[2-4])>(?:\s|<br>|&nbsp;)*<\/\1>/g, '');
  }
  return html.trim();
}

function json(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}
