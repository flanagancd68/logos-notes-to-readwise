#!/usr/bin/env python3
"""
logos_to_readwise.py
====================

Export Logos Bible Software notes & highlights to a Readwise-compatible
bulk-import CSV (https://readwise.io/import_bulk).

Inspired by agape-apps/Logos-Notes-Exporter, but instead of writing one
Markdown file per note it produces a single CSV with the columns Readwise
expects:  Highlight, Title, Author, URL, Note, Location, Date.

Design decisions (per project discussion):
  * Bible anchors are rendered as the human-readable reference (e.g.
    "John 3:16"), hyperlinked to the Logos app, and placed in the
    HIGHLIGHT column (not the Note column).
  * Book (non-Bible) highlights link to the exact position via ref.ly using
    the resource abbreviation and the AnchorsJson offset (e.g.
    "https://ref.ly/logosres/sotintro?off=143862").
  * When Logos stores a highlight (kind=1) and an annotation (kind=0) at the
    same book position, they are merged into one row: the annotation's prose
    and tags move onto the highlight, and the standalone note is dropped.
  * Multiple anchors on one note are concatenated, all links preserved.
  * The HIGHLIGHT field is guaranteed non-empty (Readwise requires it).
    A space placeholder is deliberately NOT used; instead a meaningful
    fallback is chosen, and any truly-empty row is skipped and reported.
  * Readwise has no Tags column. Tags + shortcodes go on the FIRST line of
    the NOTE field (each token prefixed with "."), and the user's note
    prose follows after a blank line. Anything beginning with "." on that
    first line is treated by Readwise as a tag.
  * URL and Author are held constant so Readwise groups every note in a
    notebook under one document keyed by Title.

Read-only: the notes and catalog databases are opened immutable; the live
ResourceManager database is opened mode=ro (honouring its -wal file). None
are modified.

Standard library only (sqlite3, csv, argparse, ...). Python 3.8+.
"""

import argparse
import csv
import glob
import json
import os
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# --------------------------------------------------------------------------
# Bible book mapping (ported from Logos-Notes-Exporter reference-decoder.ts)
# anchorId -> (English name, chapter count).  Single-chapter books format
# their reference as "Book N" rather than "Book 1:N".
# --------------------------------------------------------------------------
BOOK_MAP = {
    1: ("Genesis", 50), 2: ("Exodus", 40), 3: ("Leviticus", 27), 4: ("Numbers", 36),
    5: ("Deuteronomy", 34), 6: ("Joshua", 24), 7: ("Judges", 21), 8: ("Ruth", 4),
    9: ("1 Samuel", 31), 10: ("2 Samuel", 24), 11: ("1 Kings", 22), 12: ("2 Kings", 25),
    13: ("1 Chronicles", 29), 14: ("2 Chronicles", 36), 15: ("Ezra", 10), 16: ("Nehemiah", 13),
    17: ("Esther", 10), 18: ("Job", 42), 19: ("Psalms", 150), 20: ("Proverbs", 31),
    21: ("Ecclesiastes", 12), 22: ("Song of Solomon", 8), 23: ("Isaiah", 66), 24: ("Jeremiah", 52),
    25: ("Lamentations", 5), 26: ("Ezekiel", 48), 27: ("Daniel", 12), 28: ("Hosea", 14),
    29: ("Joel", 3), 30: ("Amos", 9), 31: ("Obadiah", 1), 32: ("Jonah", 4), 33: ("Micah", 7),
    34: ("Nahum", 3), 35: ("Habakkuk", 3), 36: ("Zephaniah", 3), 37: ("Haggai", 2),
    38: ("Zechariah", 14), 39: ("Malachi", 4),
    # Apocrypha (40-57, NRSV arrangement)
    40: ("Tobit", 14), 41: ("Judith", 16), 42: ("Esther (Greek)", 16),
    43: ("The Wisdom of Solomon", 19), 44: ("Ecclesiasticus (Sirach)", 51), 45: ("Baruch", 6),
    46: ("The Letter of Jeremiah", 1), 47: ("Song of the Three Young Men", 1), 48: ("Susanna", 1),
    49: ("Bel and the Dragon", 1), 50: ("1 Maccabees", 16), 51: ("2 Maccabees", 15),
    52: ("1 Esdras", 9), 53: ("Prayer of Manasseh", 1), 54: ("Psalm 151", 1),
    55: ("3 Maccabees", 7), 56: ("2 Esdras", 16), 57: ("4 Maccabees", 18),
    # New Testament (61-87)
    61: ("Matthew", 28), 62: ("Mark", 16), 63: ("Luke", 24), 64: ("John", 21), 65: ("Acts", 28),
    66: ("Romans", 16), 67: ("1 Corinthians", 16), 68: ("2 Corinthians", 13), 69: ("Galatians", 6),
    70: ("Ephesians", 6), 71: ("Philippians", 4), 72: ("Colossians", 4), 73: ("1 Thessalonians", 5),
    74: ("2 Thessalonians", 3), 75: ("1 Timothy", 6), 76: ("2 Timothy", 4), 77: ("Titus", 3),
    78: ("Philemon", 1), 79: ("Hebrews", 13), 80: ("James", 5), 81: ("1 Peter", 5),
    82: ("2 Peter", 3), 83: ("1 John", 5), 84: ("2 John", 1), 85: ("3 John", 1), 86: ("Jude", 1),
    87: ("Revelation", 22),
}

LOGOS_APP_BASE = "https://app.logos.com/books"

# Categories used for the include-filter
CAT_BOTH = "both"            # highlight (kind=1) that also has note text
CAT_HL_ONLY = "highlight_only"   # highlight (kind=1) with no note text
CAT_NOTE_ONLY = "note_only"      # text note (kind=0)
ALL_CATEGORIES = [CAT_BOTH, CAT_HL_ONLY, CAT_NOTE_ONLY]


# --------------------------------------------------------------------------
# Reference decoding
# --------------------------------------------------------------------------
def book_name(anchor_book_id):
    entry = BOOK_MAP.get(anchor_book_id)
    return entry[0] if entry else "Unknown Book {}".format(anchor_book_id)


def is_single_chapter(anchor_book_id):
    entry = BOOK_MAP.get(anchor_book_id)
    return bool(entry) and entry[1] == 1


_BIBLE_RE = re.compile(
    r"bible\+([^.]+)\.(\d+)\.(\d+)\.(\d+)(?:-(\d+)\.(\d+)\.(\d+))?"
)


def format_reference(reference, anchor_book_id):
    """Turn a Logos reference string into a human-readable label.

    `reference` example:  bible+nkjv.64.3.16   (book.chapter.verse)
    `anchor_book_id` comes from NoteAnchorFacetReferences.BibleBook and is the
    authoritative book id (1-87); we use it for the name but take the
    chapter/verse numbers from the reference string, mirroring the original
    exporter's logic.
    """
    m = _BIBLE_RE.search(reference or "")
    if not m:
        # Not a bible+ reference we recognise; show the book name if we have it.
        if anchor_book_id and anchor_book_id in BOOK_MAP:
            return book_name(anchor_book_id)
        return reference or ""

    _ver, _booknum, chap, verse, _endbook, end_chap, end_verse = m.groups()
    bid = anchor_book_id or int(_booknum or 0)
    name = book_name(bid)

    if is_single_chapter(bid):
        # For single-chapter books the trailing field is the verse number:
        # bible+x.86.1.24 -> "Jude 24"; a second value means a range.
        label = "{} {}".format(name, int(verse))
        if end_verse:
            label += "-{}".format(int(end_verse))
        return label

    chap_i = int(chap or 0)
    verse_i = int(verse or 0)
    label = "{} {}".format(name, chap_i)
    if verse_i:
        label += ":{}".format(verse_i)
        if end_chap and end_verse:
            if int(end_chap) == chap_i:
                label += "-{}".format(int(end_verse))
            else:
                label += "-{}:{}".format(int(end_chap), int(end_verse))
    return label


def encode_resource_id(resource_id):
    if not resource_id:
        return None
    return resource_id.replace(":", "%3A")


def bible_anchor_link(resource_id, reference):
    enc = encode_resource_id(resource_id)
    if not enc or not reference:
        return None
    return "{}/{}/references/{}".format(LOGOS_APP_BASE, enc, reference)


REFLY_BASE = "https://ref.ly/logosres"


def refly_offset_link(slug, offset):
    """ref.ly link to a precise position in a resource.

    `slug` is the resource abbreviation (e.g. "sotintro") when the book is
    downloaded locally, otherwise the raw resource id (e.g. "LLS:34.0.33").
    The offset is the resource-wide character offset Logos stores in
    AnchorsJson -> textRange.offset (same scale as the app.logos.com
    /offsets/ endpoint).
    """
    if not slug:
        return None
    if offset is not None and offset >= 0:
        return "{}/{}?off={}".format(REFLY_BASE, slug, offset)
    return "{}/{}".format(REFLY_BASE, slug)


# --------------------------------------------------------------------------
# XAML -> Markdown (pragmatic; covers the common Logos note elements)
# --------------------------------------------------------------------------
_NS_RE = re.compile(r'\sxmlns(:\w+)?="[^"]*"')
_PREFIX_RE = re.compile(r"(<\/?)(\w+):")

# Zero-width and invisible Unicode characters Logos embeds around Hebrew/Greek text
_ZERO_WIDTH_RE = re.compile(
    "[\u00ad\u200b\u200c\u200d\u200e\u200f"
    "\u2028\u2029\u202a\u202b\u202c\u202d\u202e"
    "\u2060\u2061\u2062\u2063\u2064\ufeff]"
)


def _clean_unicode(text):
    """Strip invisible/zero-width characters Logos may embed in Rich Text."""
    return _ZERO_WIDTH_RE.sub("", text) if text else text


def _normalize_inline_fmt(md):
    """Collapse adjacent ** or * markers produced by back-to-back same-style runs."""
    prev = None
    while prev != md:
        prev = md
        md = re.sub(r"\*\*(\s*)\*\*", r"\1", md)
    return md


def _strip_namespaces(xaml):
    xaml = _NS_RE.sub("", xaml)
    xaml = _PREFIX_RE.sub(r"\1", xaml)
    # also strip prefixed attributes like x:Name=
    xaml = re.sub(r'\s\w+:(\w+)=', r' \1=', xaml)
    return xaml


def _local(tag):
    return tag.split("}")[-1].lower() if tag else ""


def _runs_to_md(elem):
    """Recursively render an element's inline content to Markdown."""
    out = []
    tag = _local(elem.tag)

    if tag in ("run", "span"):
        text = _clean_unicode(elem.get("Text", ""))
        if not text and elem.text:
            text = _clean_unicode(elem.text)
        bold = (elem.get("FontBold", "").lower() == "true")
        italic = (elem.get("FontItalic", "").lower() == "true")
        if elem.get("FontWeight", "").lower() == "bold":
            bold = True
        if elem.get("FontStyle", "").lower() == "italic":
            italic = True
        inner = text or ""
        for child in list(elem):
            inner += _runs_to_md(child)
        if inner:
            if italic:
                inner = "*{}*".format(inner)
            if bold:
                inner = "**{}**".format(inner)
        out.append(inner)
        if elem.tail:
            out.append(elem.tail)
        return "".join(out)

    if tag in ("hyperlink", "urilink"):
        uri = elem.get("Uri") or elem.get("NavigateUri") or ""
        text = elem.get("Text", "") or (elem.text or "")
        for child in list(elem):
            text += _runs_to_md(child)
        text = text.strip() or uri
        link = "[{}]({})".format(text, uri) if uri else text
        if elem.tail:
            link += elem.tail
        return link

    # generic container: concatenate children
    buf = []
    if elem.text:
        buf.append(elem.text)
    for child in list(elem):
        buf.append(_runs_to_md(child))
    if elem.tail:
        buf.append(elem.tail)
    return "".join(buf)


def xaml_to_markdown(content):
    """Best-effort XAML -> Markdown. Falls back to plain text on parse error."""
    if not content:
        return ""
    content = content.strip()
    if not content:
        return ""

    # Logos notes may also be plain text / markdown passthrough.
    if not content.lstrip().startswith("<"):
        return _clean_unicode(content.strip())

    try:
        cleaned = _strip_namespaces(content)
        root = ET.fromstring("<root>{}</root>".format(cleaned))
    except ET.ParseError:
        # Strip tags and return whatever text remains.
        text = re.sub(r"<[^>]+>", "", content)
        return _clean_unicode(re.sub(r"[ \t]+", " ", text).strip())

    blocks = []

    def walk_blocks(node):
        for child in list(node):
            t = _local(child.tag)
            if t == "paragraph":
                blocks.append(_normalize_inline_fmt(_runs_to_md(child).strip()))
            elif t == "section":
                walk_blocks(child)
            elif t == "list":
                for item in list(child):
                    text = _normalize_inline_fmt(_runs_to_md(item).strip())
                    if text:
                        blocks.append("- {}".format(text))
            elif t in ("run", "span", "hyperlink", "urilink"):
                blocks.append(_normalize_inline_fmt(_runs_to_md(child).strip()))
            else:
                walk_blocks(child)

    walk_blocks(root)
    md = "\n\n".join(b for b in blocks if b)
    if not md:
        md = _normalize_inline_fmt(_runs_to_md(root).strip())
    # collapse excessive blank lines
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


# --------------------------------------------------------------------------
# Tag handling
# --------------------------------------------------------------------------
def parse_tags(tags_json):
    """Logos stores tags as JSON. Return a list of clean Readwise tag tokens."""
    if not tags_json:
        return []
    try:
        data = json.loads(tags_json)
    except (ValueError, TypeError):
        return []

    raw = []
    if isinstance(data, list):
        for item in data:
            text = _extract_tag_text(item)
            if text:
                raw.append(text)
    elif isinstance(data, str):
        raw.append(data)
    elif isinstance(data, dict):
        text = _extract_tag_text(data)
        if text:
            raw.append(text)

    tags = []
    for t in raw:
        # Spaces are removed (not underscored): "Survey of OT" -> "SurveyofOT".
        # Existing underscores/hyphens are kept: "book_notes" -> "book_notes".
        token = re.sub(r"\s+", "", t.strip())
        token = re.sub(r"[^\w\-]", "", token)
        if token:
            tags.append("." + token)
    return tags


def _extract_tag_text(item):
    """Pull a tag's display text from Logos' tag JSON.

    Logos stores tags as {"plain": {"text": "Survey of OT"}}; older/other shapes
    may put the string at the top level ({"text": ...}, {"name": ...}) or be a
    bare string.  Handle each, digging one level into nested dicts.
    """
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return None
    for key in ("tag", "name", "text", "Tag", "Name", "Text"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val
    # Nested shapes such as {"plain": {"text": ...}} or {"reference": {"text": ...}}
    for val in item.values():
        if isinstance(val, dict):
            nested = _extract_tag_text(val)
            if nested:
                return nested
    return None


def build_note_field(tags, prose):
    """First line = tags/shortcodes; note prose follows after a blank line."""
    tag_line = " ".join(tags).strip()
    prose = (prose or "").strip()
    if tag_line and prose:
        return tag_line + "\n\n" + prose
    if tag_line:
        return tag_line
    return prose


# --------------------------------------------------------------------------
# Date handling
# --------------------------------------------------------------------------
def parse_logos_date(value):
    """Parse a Logos date value into an aware UTC datetime, or None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Heuristic: large numbers are unix seconds/millis.
        try:
            v = float(value)
            if v > 1e12:
                v /= 1000.0
            return datetime.fromtimestamp(v, tz=timezone.utc)
        except (ValueError, OSError):
            return None
    s = str(value).strip()
    if not s:
        return None
    s2 = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(s.split("+")[0].rstrip("Z"), fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def readwise_date(dt):
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------------
# Database access
# --------------------------------------------------------------------------
def open_ro(path):
    uri = "file:{}?mode=ro&immutable=1".format(os.path.abspath(path).replace("?", "%3f"))
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def open_ro_wal(path):
    """Read-only open that still honours the -wal file.

    Logos' live databases (e.g. ResourceManager.db) keep recent writes in a
    WAL; immutable mode would hide them, so use plain mode=ro here.
    """
    uri = "file:{}?mode=ro".format(os.path.abspath(path).replace("?", "%3f"))
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def derive_catalog_path(notestool_path):
    p = notestool_path
    p = p.replace("/Documents/", "/Data/").replace("\\Documents\\", "\\Data\\")
    p = p.replace("/NotesToolManager/", "/LibraryCatalog/").replace(
        "\\NotesToolManager\\", "\\LibraryCatalog\\")
    p = p.replace("notestool.db", "catalog.db")
    return p if os.path.exists(p) else None


def derive_resourcemanager_path(notestool_path):
    p = notestool_path
    p = p.replace("/Documents/", "/Data/").replace("\\Documents\\", "\\Data\\")
    p = p.replace("/NotesToolManager/", "/ResourceManager/").replace(
        "\\NotesToolManager\\", "\\ResourceManager\\")
    p = p.replace("notestool.db", "ResourceManager.db")
    return p if os.path.exists(p) else None


def load_resource_abbreviations(resourcemanager_conn):
    """Map resourceId -> lowercase abbreviation slug (from the resource filename).

    ref.ly uses the resource's file basename as its slug, e.g.
    SOTINTRO.logos4 -> "sotintro".  Only books downloaded locally appear here;
    cloud-only resources fall back to the raw resource id at link-build time.
    """
    abbrevs = {}
    if resourcemanager_conn is None:
        return abbrevs
    try:
        for rid, loc in resourcemanager_conn.execute(
                "SELECT ResourceId, Location FROM Resources"):
            if rid and loc:
                base = os.path.splitext(os.path.basename(loc))[0]
                if base:
                    abbrevs[rid] = base.lower()
    except sqlite3.Error:
        pass
    return abbrevs


def find_default_db():
    candidates = []
    home = os.path.expanduser("~")
    mac = os.path.join(home, "Library", "Application Support", "Logos4", "Documents")
    candidates += glob.glob(os.path.join(mac, "*", "NotesToolManager", "notestool.db"))
    lad = os.environ.get("LOCALAPPDATA")
    if lad:
        win = os.path.join(lad, "Logos", "Documents")
        candidates += glob.glob(os.path.join(win, "*", "NotesToolManager", "notestool.db"))
    candidates = [c for c in candidates if os.path.exists(c)]
    candidates.sort(key=lambda c: os.path.getsize(c), reverse=True)
    return candidates[0] if candidates else None


# --------------------------------------------------------------------------
# Core extraction
# --------------------------------------------------------------------------
class Anchor:
    __slots__ = ("index", "display", "link")

    def __init__(self, index, display, link):
        self.index = index
        self.display = display
        self.link = link

    def render(self):
        if self.link and self.display:
            return "[{}]({})".format(self.display, self.link)
        if self.display:
            return self.display
        if self.link:
            return self.link
        return ""


def load_notes(conn, catalog_conn, resource_abbrevs=None):
    notes = {r["id"]: dict(r) for r in conn.execute("""
        SELECT NoteId AS id, ExternalId AS externalId,
               CreatedDate AS createdDate, ModifiedDate AS modifiedDate,
               Kind AS kind, ContentRichText AS contentRichText,
               NotebookExternalId AS notebookExternalId,
               AnchorResourceIdId AS anchorResourceIdId, TagsJson AS tagsJson,
               AnchorsJson AS anchorsJson
        FROM Notes
        WHERE IsDeleted = 0 AND IsTrashed = 0
    """)}

    notebooks = {}
    for r in conn.execute("""
        SELECT ExternalId AS externalId, Title AS title
        FROM Notebooks WHERE IsDeleted = 0 AND IsTrashed = 0
    """):
        notebooks[r["externalId"]] = r["title"]

    resource_ids = {r["resourceIdId"]: r["resourceId"] for r in conn.execute(
        "SELECT ResourceIdId AS resourceIdId, ResourceId AS resourceId FROM ResourceIds")}

    # Catalog titles (resourceId string -> title)
    catalog_titles = {}
    if catalog_conn is not None:
        try:
            for r in catalog_conn.execute("SELECT ResourceId AS rid, Title AS title FROM Records"):
                catalog_titles[r["rid"]] = r["title"]
        except sqlite3.Error:
            pass

    # Bible reference anchors
    bible_anchors = {}
    for r in conn.execute("""
        SELECT NoteId AS noteId, Reference AS reference,
               BibleBook AS bibleBook, AnchorIndex AS anchorIndex
        FROM NoteAnchorFacetReferences
        ORDER BY NoteId, AnchorIndex
    """):
        note = notes.get(r["noteId"])
        res_id = resource_ids.get(note["anchorResourceIdId"]) if note else None
        display = format_reference(r["reference"], r["bibleBook"])
        link = bible_anchor_link(res_id, r["reference"])
        bible_anchors.setdefault(r["noteId"], []).append(
            Anchor(r["anchorIndex"], display, link))

    # Resource (offset) anchors — built from AnchorsJson textRanges, which carry the
    # authoritative resource-wide offset.  (NoteAnchorTextRanges.Offset is -1 for many
    # synced highlights, so reading it there drops the position.)  Links use the ref.ly
    # abbreviation form (e.g. ".../sotintro?off=143124") when the book is local,
    # otherwise the raw resource id.  The same pass records (resourceId, offset) ->
    # note ids so highlight/annotation pairs sharing a position can be merged below.
    resource_abbrevs = resource_abbrevs or {}
    offset_anchors = {}
    offset_to_notes = {}  # (resourceId, offset) -> [note_id, ...]
    for note_id, note in notes.items():
        aj = note.get("anchorsJson")
        if not aj:
            continue
        try:
            anchors = json.loads(aj)
        except (ValueError, TypeError):
            continue
        if not isinstance(anchors, list):
            anchors = [anchors]
        for idx, anchor in enumerate(anchors):
            tr = anchor.get("textRange") if isinstance(anchor, dict) else None
            if not tr or "resourceId" not in tr:
                continue
            res_id = tr["resourceId"]
            offset = tr.get("offset")
            slug = resource_abbrevs.get(res_id) or res_id
            title = catalog_titles.get(res_id) or resource_abbrevs.get(res_id) or "Open in Logos"
            offset_anchors.setdefault(note_id, []).append(
                Anchor(idx, title, refly_offset_link(slug, offset)))
            if offset is not None:
                offset_to_notes.setdefault((res_id, offset), []).append(note_id)

    # Pair kind=0 annotation notes with their kind=1 highlight at the same book offset.
    # Logos creates a kind=1 highlight + a kind=0 note when a user highlights text and
    # types an annotation simultaneously.  The annotation's prose AND tags are merged
    # into the highlight, and the standalone kind=0 row is dropped.
    paired_prose = {}    # kind=1 note_id -> prose merged from paired kind=0 notes
    paired_tags = {}     # kind=1 note_id -> tag tokens merged from paired kind=0 notes
    absorbed_ids = set()  # kind=0 note_ids merged into a kind=1 sibling

    for note_ids in offset_to_notes.values():
        uniq_ids = list(dict.fromkeys(note_ids))  # drop dupes from multi-anchor notes
        k0_ids = [nid for nid in uniq_ids if notes[nid].get("kind") == 0]
        k1_ids = [nid for nid in uniq_ids if notes[nid].get("kind") == 1]
        if not k0_ids or not k1_ids:
            continue
        for k1_id in k1_ids:
            prose_parts = []
            tag_tokens = []
            for k0_id in k0_ids:
                k0_prose = xaml_to_markdown(notes[k0_id].get("contentRichText")).strip()
                if k0_prose:
                    prose_parts.append(k0_prose)
                for tok in parse_tags(notes[k0_id].get("tagsJson")):
                    if tok not in tag_tokens:
                        tag_tokens.append(tok)
            if prose_parts:
                paired_prose[k1_id] = "\n\n".join(prose_parts)
            if tag_tokens:
                paired_tags[k1_id] = tag_tokens
        for k0_id in k0_ids:
            absorbed_ids.add(k0_id)

    return {
        "notes": notes,
        "notebooks": notebooks,
        "resource_ids": resource_ids,
        "catalog_titles": catalog_titles,
        "bible_anchors": bible_anchors,
        "offset_anchors": offset_anchors,
        "paired_prose": paired_prose,
        "paired_tags": paired_tags,
        "absorbed_ids": absorbed_ids,
    }


def categorize(note, prose):
    kind = note.get("kind")
    has_note = bool(prose.strip())
    if kind == 1:
        return CAT_BOTH if has_note else CAT_HL_ONLY
    return CAT_NOTE_ONLY


def resource_title_for_note(note, data):
    res_id = data["resource_ids"].get(note.get("anchorResourceIdId"))
    if not res_id:
        return None
    return data["catalog_titles"].get(res_id)


def assemble_anchor_block(note_id, data):
    anchors = []
    anchors += data["bible_anchors"].get(note_id, [])
    # Only add offset anchors if there are no bible refs for the same index,
    # to avoid duplicate links for the same anchor.
    bible_indices = {a.index for a in data["bible_anchors"].get(note_id, [])}
    for a in data["offset_anchors"].get(note_id, []):
        if a.index not in bible_indices:
            anchors.append(a)
    anchors.sort(key=lambda a: (a.index if a.index is not None else 0))
    rendered = [a.render() for a in anchors if a.render()]
    return "\n".join(rendered)


def primary_note_link(note_id, data):
    """First available anchor link for the note (used for --url-mode note)."""
    anchors = list(data["bible_anchors"].get(note_id, []))
    bible_indices = {a.index for a in anchors}
    for a in data["offset_anchors"].get(note_id, []):
        if a.index not in bible_indices:
            anchors.append(a)
    anchors.sort(key=lambda a: (a.index if a.index is not None else 0))
    for a in anchors:
        if a.link:
            return a.link
    return ""


def default_output_path():
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    base = desktop if os.path.isdir(desktop) else os.path.expanduser("~")
    return os.path.join(base, "logos_readwise.csv")


def resolve_output_path(arg_output, interactive):
    """Determine where to write the CSV, prompting (default Desktop) when needed."""
    default = default_output_path()
    if arg_output:
        path = os.path.expanduser(arg_output)
    elif interactive:
        path = os.path.expanduser(prompt("\nSave CSV to [{}]: ".format(default), default))
    else:
        path = default

    if path.endswith(os.sep) or os.path.isdir(path):
        path = os.path.join(path, "logos_readwise.csv")
    elif not path.lower().endswith(".csv"):
        path += ".csv"

    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    return path


# --------------------------------------------------------------------------
# Interactive helpers
# --------------------------------------------------------------------------
def prompt(msg, default=""):
    try:
        val = input(msg).strip()
    except EOFError:
        return default
    return val or default


def interactive_include_tags():
    print("\nInclude Logos tags on the first line of each note? (e.g. '.SurveyofOT .book_notes')")
    choice = prompt("  Include tags? [Y/n]: ", "y")
    return not choice.strip().lower().startswith("n")


def interactive_notebook(notebook_rows, default_ext):
    """Pick exactly ONE notebook to export (one notebook per run)."""
    # Only offer notebooks that have a real title.  Orphaned/untitled notebooks
    # (left over from deleted notebooks, etc.) are noise the user can't meaningfully
    # pick, so they're hidden from the list.
    named = [nb for nb in notebook_rows if nb["title"]]
    if not named:
        named = notebook_rows
    if not any(nb["ext"] == default_ext for nb in named):
        default_ext = named[0]["ext"]
    print("\nSelect ONE notebook to export (type its number, or Enter for the default):")
    for i, nb in enumerate(named, 1):
        marker = "  <- most recently modified (default)" if nb["ext"] == default_ext else ""
        print("  {}) {} [{} notes]{}".format(i, nb["title"], nb["count"], marker))
    choice = prompt("  Choice [default]: ", "").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(named):
        return named[int(choice) - 1]["ext"]
    return default_ext


# --------------------------------------------------------------------------
# Highlight-text enrichment (optional, from a manual Logos export)
#
# The Logos note database stores only a byte offset into the (encrypted) book
# for each highlight, NOT the highlighted passage text.  A manual Logos export
# of the notebook DOES contain that passage.  Given such an export as plain
# text, sorted by Date Created (descending - Logos' only option), we recover
# each highlight's passage by:
#   1. text-matching every note that has prose to its unique export record
#      (order-independent, ~99% unique) -> high-confidence anchor pairs;
#   2. interpolating the note-less highlights in the gaps between anchors (the
#      export is a strict reverse of note-creation order, so the anchors pin
#      the sequence and it self-resyncs despite small count differences).
# Recovered passages are prepended to the Highlight column.
# --------------------------------------------------------------------------
_MATCH_RE = re.compile(r"[^0-9a-z]+")


def _norm_for_match(s):
    """Lowercase alphanumeric fingerprint used for fuzzy text matching."""
    if not s:
        return ""
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)  # markdown link -> label
    s = s.replace("*", "").replace("`", "")
    return _MATCH_RE.sub(" ", s.lower()).strip()


def _read_text_file(path):
    """Read a text export, tolerating common encodings (BOM, UTF-16, ...)."""
    for enc in ("utf-8-sig", "utf-16", "utf-8", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeError, UnicodeDecodeError):
            continue
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def parse_export_records(path, notebook_title=None):
    """Split a Logos plain-text export into per-note records (in file order).

    Records are separated by a line of 3+ dashes.  A leading notebook title on
    the first record (Logos prepends it) is stripped.
    """
    text = _read_text_file(path)
    parts = re.split(r"\n[ \t]*-{3,}[ \t]*\n", text)
    records = [p.strip() for p in parts]
    if records and notebook_title and records[0].startswith(notebook_title):
        records[0] = records[0][len(notebook_title):].strip()
    return [r for r in records if r.strip()]


def _passage_from_record(record, note_prose):
    """Return the highlighted-passage portion of an export record.

    Within a record the passage precedes the note text.  When the note has
    prose, the passage is everything before that prose begins; a note-less
    highlight record is entirely passage.
    """
    record = record.strip()
    if not note_prose or not note_prose.strip():
        return record
    probe = _norm_for_match(note_prose)[:50]
    if not probe:
        return record
    lines = record.split("\n")
    for li in range(len(lines)):
        if _norm_for_match("\n".join(lines[li:])).startswith(probe):
            return "\n".join(lines[:li]).strip()
    return ""  # the whole record is the note -> no passage


def build_passage_map(export_path, ordered_notes, notebook_title=None):
    """Map NoteId -> recovered highlighted passage text from a Logos export.

    `ordered_notes` is every note in the export's scope, sorted by creation
    order ascending (oldest first) - the reverse of the export's order.
    Returns (passage_map, stats).
    """
    records = parse_export_records(export_path, notebook_title)
    rec_norm = [_norm_for_match(r) for r in records]
    n_rec = len(records)

    # 1. Anchor: text-match notes that have prose to a single record.
    anchors = []          # (note_index, record_index), note_index ascending
    note_prose = {}
    for j, note in enumerate(ordered_notes):
        prose = xaml_to_markdown(note.get("contentRichText")).strip()
        note_prose[j] = prose
        probe = _norm_for_match(prose)[:50]
        if len(probe) < 8:            # too short to match reliably
            continue
        hits = [i for i, rn in enumerate(rec_norm) if probe in rn]
        if len(hits) == 1:
            anchors.append((j, hits[0]))

    # 2. Assign a record to each note: anchors directly, gaps by interpolation.
    #    The export runs newest->oldest, so record index DECREASES as note index
    #    increases.  Within a gap whose note-count == record-count, map in order.
    assigned = {j: i for j, i in anchors}
    bounds = [(-1, n_rec)] + anchors + [(len(ordered_notes), -1)]
    for (ja, ia), (jb, ib) in zip(bounds, bounds[1:]):
        gap_notes = list(range(ja + 1, jb))
        gap_recs = list(range(ib + 1, ia))   # ascending record indices in the gap
        if gap_notes and len(gap_notes) == len(gap_recs):
            for k, jn in enumerate(gap_notes):
                assigned[jn] = gap_recs[len(gap_recs) - 1 - k]  # note asc <-> rec desc

    # 3. Extract each assigned record's passage, keyed by NoteId.
    passage_map = {}
    for j, note in enumerate(ordered_notes):
        i = assigned.get(j)
        if i is None:
            continue
        passage = _passage_from_record(records[i], note_prose.get(j, ""))
        if passage and passage.strip():
            passage_map[note["id"]] = passage.strip()

    stats = {
        "records": n_rec,
        "notes": len(ordered_notes),
        "notes_with_text": sum(1 for p in note_prose.values() if p),
        "anchors": len(anchors),
        "assigned": len(assigned),
        "passages": len(passage_map),
    }
    return passage_map, stats


def interactive_highlight_file():
    print("\nRecover highlighted passage text from a manual Logos export? (optional)")
    print("  In Logos: open the SAME notebook you'll choose below, sort by Date Created,")
    print("  and export the whole notebook as plain text (.txt).  Press Enter to skip.")
    path = prompt("  Path to export .txt (or Enter to skip): ", "")
    return os.path.expanduser(path) if path.strip() else None


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Export Logos notes/highlights to a Readwise bulk-import CSV.")
    ap.add_argument("--db", help="Path to Logos notestool.db (auto-detected if omitted)")
    ap.add_argument("--catalog", help="Path to Logos catalog.db (auto-detected from --db)")
    ap.add_argument("-o", "--output", default=None,
                    help="Output CSV path (prompts, default ~/Desktop, if omitted)")
    ap.add_argument("--url-mode", choices=["none", "note"], default="none",
                    help="'none' (blank URL, notebook grouping preserved; per-note links "
                         "are still clickable inside each Highlight) or 'note' (put each "
                         "note's Logos link in the URL column - makes every note its own "
                         "Readwise document)")
    ap.add_argument("--title-source", choices=["notebook", "resource"],
                    help="Which value to use for the Readwise Title column")
    ap.add_argument("--from", dest="date_from", help="Include notes on/after YYYY-MM-DD")
    ap.add_argument("--to", dest="date_to", help="Include notes on/before YYYY-MM-DD")
    ap.add_argument("--date-field", choices=["created", "modified"], default="created",
                    help="Which date drives filtering and the Date column")
    ap.add_argument("--notebook", help="Title of the single Logos notebook to export "
                                       "(one notebook per run)")
    ap.add_argument("--include", help="Comma-separated of: both,highlight_only,note_only")
    ap.add_argument("--author", default="", help="Constant value for the Author column")
    ap.add_argument("--no-tags", action="store_true",
                    help="Do not add the Logos tags line (.tag .tag) to the Note field")
    ap.add_argument("--highlight-file",
                    help="Path to a manual Logos plain-text export of the notebook "
                         "(sorted by Date Created) used to recover highlighted passage "
                         "text and prepend it to the Highlight column")
    ap.add_argument("--no-interactive", action="store_true",
                    help="Never prompt; rely solely on flags/defaults")
    args = ap.parse_args()

    interactive = (not args.no_interactive) and sys.stdin.isatty()

    db_path = args.db or find_default_db()
    if not db_path or not os.path.exists(db_path):
        sys.exit("ERROR: Could not find notestool.db. Pass it with --db /path/to/notestool.db")
    catalog_path = args.catalog or derive_catalog_path(db_path)
    resourcemanager_path = derive_resourcemanager_path(db_path)

    print("NotesTool DB: {}".format(db_path))
    print("Catalog DB:   {}".format(catalog_path or "(not found - resource titles unavailable)"))
    print("Resource DB:  {}".format(
        resourcemanager_path or "(not found - ref.ly abbreviations unavailable)"))

    conn = open_ro(db_path)
    catalog_conn = open_ro(catalog_path) if catalog_path else None
    resourcemanager_conn = open_ro_wal(resourcemanager_path) if resourcemanager_path else None
    resource_abbrevs = load_resource_abbreviations(resourcemanager_conn)
    data = load_notes(conn, catalog_conn, resource_abbrevs)
    notes = data["notes"]
    if not notes:
        sys.exit("No active notes found in the database.")

    # ---- Notebook list with counts + most-recently-modified default ----
    nb_count = {}
    nb_latest = {}
    for n in notes.values():
        ext = n.get("notebookExternalId") or ""
        nb_count[ext] = nb_count.get(ext, 0) + 1
        dt = parse_logos_date(n.get("modifiedDate") or n.get("createdDate"))
        if dt and (ext not in nb_latest or dt > nb_latest[ext]):
            nb_latest[ext] = dt
    notebook_rows = []
    for ext, count in nb_count.items():
        notebook_rows.append({
            "ext": ext,
            "title": data["notebooks"].get(ext) or ("(No notebook)" if ext == "" else None),
            "count": count,
        })
    notebook_rows.sort(key=lambda r: r["count"], reverse=True)
    default_ext = max(nb_latest, key=lambda e: nb_latest[e]) if nb_latest else (
        notebook_rows[0]["ext"] if notebook_rows else "")

    # ---- Resolve options (flags first, then prompt, then default) ----
    highlight_file = args.highlight_file
    if highlight_file:
        highlight_file = os.path.expanduser(highlight_file)
    elif interactive:
        highlight_file = interactive_highlight_file()
    if highlight_file and not os.path.exists(highlight_file):
        print("WARNING: highlight export file not found: {} (skipping enrichment)".format(
            highlight_file))
        highlight_file = None

    if args.no_tags:
        include_tags = False
    elif interactive:
        include_tags = interactive_include_tags()
    else:
        include_tags = True

    title_source = args.title_source or "notebook"

    # Default to every note kind; --include is a command-line-only override.
    if args.include:
        categories = [c.strip() for c in args.include.split(",") if c.strip() in ALL_CATEGORIES]
        categories = categories or list(ALL_CATEGORIES)
    else:
        categories = list(ALL_CATEGORIES)

    # No date filter by default; --from/--to are command-line-only overrides.
    date_from, date_to = args.date_from, args.date_to
    dt_from = parse_logos_date(date_from) if date_from else None
    dt_to = parse_logos_date(date_to + " 23:59:59") if date_to else None

    # One notebook per run (keeps the optional highlight-export match reliable).
    if args.notebook:
        match = [r["ext"] for r in notebook_rows if (r["title"] or "") == args.notebook]
        if not match:
            sys.exit("No notebook titled {!r} was found.".format(args.notebook))
        selected_ext = {match[0]}
    elif interactive:
        selected_ext = {interactive_notebook(notebook_rows, default_ext)}
    else:
        selected_ext = {default_ext}

    selected_title = data["notebooks"].get(next(iter(selected_ext))) or "(notebook)"
    print("\nExporting | notebook={!r} | title={} | categories={} | tags={} | {}..{}".format(
        selected_title, title_source, ",".join(categories),
        "on" if include_tags else "off", date_from or "-", date_to or "-"))

    output_path = resolve_output_path(args.output, interactive)

    # ---- Optional: recover highlighted passage text from a manual Logos export ----
    passage_map = {}
    if highlight_file:
        # Scope must mirror the manual export so records line up: same notebook(s),
        # and the same Date-Created range if one was given (the export is sorted and
        # filtered by Date Created).  Categories are NOT applied here - the export
        # always contains every note kind.
        def _in_created_range(nt):
            d = parse_logos_date(nt.get("createdDate"))
            if dt_from and (d is None or d < dt_from):
                return False
            if dt_to and (d is None or d > dt_to):
                return False
            return True

        scope_notes = [nt for nt in notes.values()
                       if (nt.get("notebookExternalId") or "") in selected_ext
                       and _in_created_range(nt)]
        scope_notes.sort(key=lambda nt: (nt.get("createdDate") or "", nt.get("id")))
        nb_title = None
        if len(selected_ext) == 1:
            nb_title = data["notebooks"].get(next(iter(selected_ext)))
        passage_map, pstats = build_passage_map(highlight_file, scope_notes, nb_title)
        records_n = pstats["records"]
        notes_n = pstats["notes"]
        with_text = pstats["notes_with_text"]
        anchors_n = pstats["anchors"]
        print("\nHighlight enrichment | export records={} | notes in scope={} | "
              "anchors={} | passages recovered={}".format(
                  records_n, notes_n, anchors_n, pstats["passages"]))

        # Judge alignment by MATCH QUALITY, not a raw count difference (small gaps
        # are normal).  Flag only when the two clearly aren't the same notes: a big
        # count gap, or few of the text notes actually matched.
        gap_frac = abs(records_n - notes_n) / max(records_n, notes_n, 1)
        match_rate = (anchors_n / with_text) if with_text else 1.0
        looks_wrong = gap_frac > 0.20 or (with_text >= 5 and match_rate < 0.5)

        if looks_wrong:
            print("  " + "!" * 68)
            print("  WARNING: the export file and this notebook do NOT look like the")
            print("  same set of notes.  Only {:.0f}% of your text notes matched, and the".format(
                match_rate * 100))
            print("  counts differ a lot ({} records vs {} notes).".format(records_n, notes_n))
            print("  --> Did you export the WHOLE notebook?  In Logos, select EVERY note in")
            print("      this notebook, sort by Date Created, export to plain text, re-run.")
            print("  Recovered highlights are unreliable until these line up.")
            print("  " + "!" * 68)
        else:
            print("  OK: the export lines up with this notebook "
                  "({:.0f}% of text notes matched).".format(match_rate * 100))

    # ---- Build rows ----
    rows = []
    skipped_empty = 0
    for note in sorted(notes.values(),
                       key=lambda n: (n.get("createdDate") or "", n.get("id"))):
        ext = note.get("notebookExternalId") or ""
        if ext not in selected_ext:
            continue

        # Skip kind=0 notes that have been absorbed into a paired kind=1 highlight
        if note["id"] in data["absorbed_ids"]:
            continue

        prose = xaml_to_markdown(note.get("contentRichText"))
        cat = categorize(note, prose)
        if cat not in categories:
            continue

        date_val = note.get("modifiedDate") if args.date_field == "modified" else note.get("createdDate")
        dt = parse_logos_date(date_val)
        if dt_from and (dt is None or dt < dt_from):
            continue
        if dt_to and (dt is None or dt > dt_to):
            continue

        # Title
        if title_source == "resource":
            title = resource_title_for_note(note, data) or data["notebooks"].get(ext) \
                or ("(No notebook)" if ext == "" else "(Untitled)")
        else:
            title = data["notebooks"].get(ext) or ("(No notebook)" if ext == "" else "(Untitled)")

        # Highlight = anchor block for actual highlights / Bible refs.
        # For kind=0 text notes whose only anchor is an offset (book position link),
        # the prose is the real content — use its first line as the highlight instead.
        anchor_block = assemble_anchor_block(note["id"], data)  # Bible-ref links OR ref.ly book link
        has_bible_refs = bool(data["bible_anchors"].get(note["id"]))
        is_highlight = note.get("kind") == 1
        is_book = bool(data["offset_anchors"].get(note["id"])) and not has_bible_refs
        passage = passage_map.get(note["id"], "")
        link = anchor_block.strip()
        first_line = prose.strip().splitlines()[0][:300] if prose.strip() else ""

        if is_book:
            # Book highlight/annotation: recovered passage (if any) on top of the ref.ly
            # link back to Logos.  The note's own words live in the Note column, so the
            # link is ALWAYS shown here -- even when no passage was recovered.
            if passage and link:
                highlight = passage + "\n" + link
            elif passage:
                highlight = passage
            elif link:
                highlight = link
            else:
                highlight = first_line
        elif has_bible_refs:
            # Bible-anchored: the verse reference links are the highlight.
            highlight = link or first_line
        else:
            # Plain text note with no book/Bible anchor: the prose is the content.
            highlight = first_line or link

        if not highlight.strip():
            highlight = "Logos note - {}".format(
                readwise_date(dt) or note.get("externalId") or note["id"])

        # Note = tag line + prose.  For kind=1 highlights that have a paired kind=0
        # annotation, append that annotation's text and merge in its tags.
        tags = []
        if include_tags:
            tags = parse_tags(note.get("tagsJson"))
            for tok in data["paired_tags"].get(note["id"], []):
                if tok not in tags:
                    tags.append(tok)
        paired = data["paired_prose"].get(note["id"], "")
        effective_prose = paired if (is_highlight and not prose.strip() and paired) else prose
        if is_highlight and prose.strip() and paired:
            effective_prose = prose.strip() + "\n\n" + paired
        note_field = build_note_field(tags, effective_prose)

        rows.append({
            "Highlight": highlight,
            "Title": title,
            "Author": args.author,
            "URL": primary_note_link(note["id"], data) if args.url_mode == "note" else "",
            "Note": note_field,
            "Location": len(rows) + 1,  # preserve file order (Readwise requires an integer)
            "Date": readwise_date(dt),
        })

    if not rows:
        sys.exit("No notes matched the selected filters. Nothing written.")

    fieldnames = ["Highlight", "Title", "Author", "URL", "Note", "Location", "Date"]
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("\nWrote {} highlights to {}".format(len(rows), output_path))
    if skipped_empty:
        print("Skipped {} note(s) with no anchor and no text.".format(skipped_empty))
    print("Done.")


if __name__ == "__main__":
    main()
