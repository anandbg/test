#!/usr/bin/env python3
"""
edisc.py - load Microsoft Purview eDiscovery metadata exports into a local
SQLite database, score them, and write the analysis reports.

Standard library only. No pip install, no internet, nothing leaves the machine.

Usage (Windows PowerShell or Command Prompt):

    python edisc.py inspect --exports "C:\\ediscovery\\exports"
    python edisc.py load    --db itar.db --exports "C:\\ediscovery\\exports" --keywords keywords.csv
    python edisc.py score   --db itar.db --config config.json
    python edisc.py report  --db itar.db --out reports
    python edisc.py all     --db itar.db --exports "C:\\ediscovery\\exports" --keywords keywords.csv --out reports
    python edisc.py selftest

Metadata only. This tool never opens native files and never reads document content.
"""

import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

SCHEMA_VERSION = 1
SCORE_VERSION = "v1"

try:
    csv.field_size_limit(2 ** 31 - 1)
except OverflowError:
    csv.field_size_limit(2 ** 27)


# --------------------------------------------------------------------------
# schema
# --------------------------------------------------------------------------

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_version(
  version INTEGER PRIMARY KEY, applied_at TEXT, note TEXT);

CREATE TABLE IF NOT EXISTS search_run(
  search_run_id INTEGER PRIMARY KEY,
  run_name TEXT UNIQUE, case_name TEXT, query_text TEXT, search_date TEXT,
  export_folder TEXT, settings_json TEXT, ingested_at TEXT);

CREATE TABLE IF NOT EXISTS source_file(
  source_file_id INTEGER PRIMARY KEY,
  search_run_id INTEGER REFERENCES search_run(search_run_id),
  file_name TEXT, rel_path TEXT, file_type TEXT,
  file_sha256 TEXT, row_count INTEGER,
  header_signature TEXT, ingested_at TEXT,
  UNIQUE(search_run_id, file_sha256));

CREATE TABLE IF NOT EXISTS raw_row(
  raw_row_id INTEGER PRIMARY KEY,
  source_file_id INTEGER REFERENCES source_file(source_file_id),
  row_number INTEGER, raw_json TEXT);

CREATE TABLE IF NOT EXISTS keyword_category(
  category_code TEXT PRIMARY KEY, category_name TEXT,
  polarity INTEGER DEFAULT 1, description TEXT);

CREATE TABLE IF NOT EXISTS keyword(
  keyword_id INTEGER PRIMARY KEY,
  keyword_text TEXT UNIQUE, normalised_text TEXT,
  category_code TEXT REFERENCES keyword_category(category_code),
  specificity INTEGER DEFAULT 2, status TEXT DEFAULT 'approved',
  owner TEXT, guidance_note TEXT);

CREATE TABLE IF NOT EXISTS search_run_keyword(
  search_run_id INTEGER, keyword_id INTEGER,
  PRIMARY KEY(search_run_id, keyword_id));

CREATE TABLE IF NOT EXISTS location(
  location_id INTEGER PRIMARY KEY, location_key TEXT UNIQUE,
  workload TEXT, location_subtype TEXT, raw_location TEXT,
  site_url TEXT, site_title TEXT, library_name TEXT,
  folder_path TEXT, folder_depth INTEGER,
  mailbox_upn TEXT, team_name TEXT, channel_name TEXT,
  repo_class TEXT, is_known_itar_repo INTEGER DEFAULT 0);

CREATE TABLE IF NOT EXISTS item(
  item_id INTEGER PRIMARY KEY, item_key TEXT UNIQUE,
  key_method TEXT, key_confidence TEXT,
  content_group_id TEXT, doc_group_id TEXT,
  location_id INTEGER REFERENCES location(location_id), workload TEXT,
  source_item_id TEXT, family_id TEXT, conversation_id TEXT, message_id TEXT,
  file_name TEXT, file_extension TEXT, title_or_subject TEXT,
  author TEXT, sender TEXT,
  created_utc TEXT, sent_utc TEXT, modified_utc TEXT,
  size_bytes INTEGER, word_count INTEGER, extracted_text_len INTEGER,
  sensitivity_label TEXT, retention_label TEXT,
  has_attachments INTEGER, index_status TEXT,
  is_unreadable INTEGER DEFAULT 0, is_list_item INTEGER DEFAULT 0,
  version_id TEXT, item_path TEXT,
  first_seen_run INTEGER, last_seen_run INTEGER);

CREATE TABLE IF NOT EXISTS item_participant(
  item_id INTEGER, role TEXT, party_address TEXT, party_domain TEXT, is_internal INTEGER);

CREATE TABLE IF NOT EXISTS item_keyword_hit(
  item_id INTEGER, keyword_id INTEGER, search_run_id INTEGER,
  source_file_id INTEGER, raw_row_id INTEGER, first_seen_at TEXT,
  PRIMARY KEY(item_id, keyword_id, search_run_id));

CREATE TABLE IF NOT EXISTS location_stats(
  search_run_id INTEGER, keyword_id INTEGER, location_id INTEGER,
  item_count INTEGER, total_size_bytes INTEGER,
  PRIMARY KEY(search_run_id, keyword_id, location_id));

CREATE TABLE IF NOT EXISTS score(
  score_id INTEGER PRIMARY KEY,
  scope_type TEXT, scope_ref TEXT, score_version TEXT,
  total_score REAL, band TEXT, status_code TEXT, computed_at TEXT,
  UNIQUE(scope_type, scope_ref, score_version));

CREATE TABLE IF NOT EXISTS score_factor(
  score_id INTEGER REFERENCES score(score_id),
  factor_code TEXT, factor_value TEXT, points REAL, note TEXT);

CREATE TABLE IF NOT EXISTS data_quality_issue(
  issue_id INTEGER PRIMARY KEY, issue_code TEXT, severity TEXT,
  scope_type TEXT, scope_ref TEXT, source_file_id INTEGER,
  detail TEXT, detected_at TEXT);

CREATE TABLE IF NOT EXISTS unmapped_header(
  header TEXT, file_type TEXT, example_file TEXT, PRIMARY KEY(header, file_type));

CREATE TABLE IF NOT EXISTS ingest_log(
  ingest_id INTEGER PRIMARY KEY, source_file_id INTEGER, started_at TEXT,
  finished_at TEXT, rows_in INTEGER, rows_loaded INTEGER, status TEXT, message TEXT);

CREATE TABLE IF NOT EXISTS reference_programme(
  ref_id INTEGER PRIMARY KEY, ref_type TEXT, ref_value TEXT, note TEXT);

CREATE TABLE IF NOT EXISTS label_lookup(label_guid TEXT PRIMARY KEY, label_name TEXT);

CREATE INDEX IF NOT EXISTS ix_item_location ON item(location_id);
CREATE INDEX IF NOT EXISTS ix_item_content_group ON item(content_group_id);
CREATE INDEX IF NOT EXISTS ix_item_doc_group ON item(doc_group_id);
CREATE INDEX IF NOT EXISTS ix_hit_keyword ON item_keyword_hit(keyword_id);
CREATE INDEX IF NOT EXISTS ix_hit_item ON item_keyword_hit(item_id);
CREATE INDEX IF NOT EXISTS ix_location_site ON location(site_url);
CREATE INDEX IF NOT EXISTS ix_score_scope ON score(scope_type, scope_ref);

CREATE VIEW IF NOT EXISTS v_item_signals AS
SELECT i.item_id,
       COUNT(DISTINCT k.category_code) AS n_categories,
       COUNT(DISTINCT k.keyword_id)    AS n_keywords,
       MAX(k.specificity)              AS max_specificity,
       GROUP_CONCAT(DISTINCT k.category_code) AS categories,
       GROUP_CONCAT(DISTINCT k.keyword_text)  AS keywords
FROM item i
JOIN item_keyword_hit h ON h.item_id = i.item_id
JOIN keyword k          ON k.keyword_id = h.keyword_id
GROUP BY i.item_id;
"""

DEFAULT_CATEGORIES = [
    ("A", "Export control regulation", 1, "ITAR, USML, DDTC, EAR, ECCN, TAA, DSP-5"),
    ("B", "Handling and distribution marking", 1, "Export Controlled, NOFORN, US Persons Only, Distribution Statement"),
    ("C", "Contract, programme or customer identifier", 1, "Programme names, contract and licence numbers"),
    ("D", "Technical data indicator", 1, "Drawing, specification, ICD, test report, CAD file types"),
    ("E", "Nationality and personnel control", 1, "Dual national, nationality check, citizenship"),
    ("F", "Procedural or reference", -1, "Training, policy, awareness, procedure"),
    ("G", "Known noise or collision", -1, "Acronym collisions, boilerplate, false friends"),
    ("X", "File type sweep", 1, "No keyword. Engineering material presence by file extension"),
]


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def nkey(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def sha1s(*parts):
    h = hashlib.sha1()
    for p in parts:
        h.update((str(p) if p is not None else "").encode("utf-8", "replace"))
        h.update(b"\x1f")
    return h.hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_int(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if not s:
        return None
    m = re.match(r"^-?\d+", s)
    return int(m.group(0)) if m else None


DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y",
    "%m/%d/%Y %H:%M:%S", "%m/%d/%Y", "%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M",
]


def parse_date(v):
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    s = s.replace("+00:00", "Z")
    for fmt in DATE_FORMATS:
        try:
            return datetime.datetime.strptime(s, fmt).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return "%s-%s-%sT00:00:00Z" % m.groups()
    return None


def truthy(v):
    return 1 if str(v).strip().lower() in ("1", "true", "yes", "y") else 0


# --------------------------------------------------------------------------
# column aliases
# --------------------------------------------------------------------------

ITEM_ALIASES = {
    "source_item_id": ["itemid", "id", "docid", "documentid", "identifier", "uniqueid", "nativeitemid"],
    "immutable_id": ["immutableid", "immutablemessageid"],
    "message_id": ["internetmessageid", "messageid"],
    "workload": ["workload", "source", "service", "datasourcetype", "locationtype", "itemtype"],
    "raw_location": ["location", "datasource", "sourcelocation", "locationname", "custodian", "mailbox", "site", "sitename"],
    "item_path": ["documentlink", "originalpath", "itempath", "filepath", "path", "url", "originalurl", "webur", "weburl", "sitepath", "parentfolder"],
    "site_url": ["siteurl", "sitecollectionurl", "spsiteurl", "sourcesiteurl"],
    "site_title": ["sitetitle", "sitename", "webtitle"],
    "file_name": ["filename", "nativefilename", "name", "documentname", "originalfilename"],
    "title_or_subject": ["subject", "title", "itemsubject", "messagesubject"],
    "file_extension": ["fileextension", "extension", "filetype", "nativeextension"],
    "author": ["author", "createdby", "documentauthor", "owner"],
    "sender": ["sender", "from", "senderemail", "senderaddress", "sendersmtp"],
    "recipients_to": ["to", "torecipients", "recipients", "recipient"],
    "recipients_cc": ["cc", "ccrecipients"],
    "recipients_bcc": ["bcc", "bccrecipients"],
    "participants": ["participants", "participantdomains", "conversationparticipants"],
    "created_utc": ["createdtime", "created", "createddate", "datecreated", "createdutc", "creationtime"],
    "sent_utc": ["sent", "senttime", "datesent", "sentdate"],
    "received_utc": ["received", "receivedtime", "datereceived"],
    "modified_utc": ["lastmodifiedtime", "modified", "modifieddate", "datemodified", "lastmodifieddate"],
    "size_bytes": ["size", "filesize", "itemsize", "sizeinbytes", "nativesize"],
    "word_count": ["wordcount"],
    "extracted_text_len": ["extractedtextlength", "textlength", "extractedtextsize"],
    "sensitivity_label": ["sensitivitylabel", "sensitivitylabelid", "sensitivitylabels", "label", "labels", "informationprotectionlabel"],
    "retention_label": ["retentionlabel", "compliancetag", "retentiontag"],
    "has_attachments": ["hasattachment", "hasattachments", "attachmentcount"],
    "index_status": ["indexingstatus", "indexstatus", "isindexed", "partiallyindexed", "indexingerror", "processingstatus", "errorcode", "error"],
    "family_id": ["familyid", "parentid", "emailfamilyid"],
    "conversation_id": ["conversationid", "threadid", "conversationtopicid"],
    "version_id": ["version", "versionid", "documentversion", "versionnumber"],
    "team_name": ["teamname", "team", "groupname"],
    "channel_name": ["channelname", "channel"],
    "mailbox_upn": ["mailbox", "custodianupn", "userprincipalname", "upn", "primarysmtpaddress", "emailaddress", "custodianemail"],
    "keyword": ["keyword", "searchterm", "matchedkeyword", "term", "query"],
}

LOCATION_ALIASES = {
    "raw_location": ["location", "locationname", "datasource", "custodian", "mailbox", "site", "sitename", "sourcelocation", "displayname"],
    "location_subtype": ["locationsubtype", "subtype", "locationtype", "type", "sourcetype"],
    "workload": ["workload", "service", "source", "datasourcetype"],
    "item_count": ["count", "itemcount", "items", "resultcount", "matchcount", "totalitems"],
    "total_size_bytes": ["size", "totalsize", "sizeinbytes", "totalsizeinbytes", "bytes"],
    "site_url": ["siteurl", "url", "weburl", "path"],
    "mailbox_upn": ["upn", "userprincipalname", "primarysmtpaddress", "emailaddress", "smtpaddress"],
}

SUMMARY_ALIASES = {
    "query_text": ["query", "searchquery", "keyword", "keyqlquery", "contentquery", "condition"],
    "search_name": ["searchname", "name", "search", "collectionname"],
    "case_name": ["casename", "case"],
    "search_date": ["date", "createdtime", "searchdate", "runtime", "starttime", "completedtime"],
    "item_count": ["items", "itemcount", "totalitems", "indexeditems", "count", "estimateditems"],
    "unindexed_count": ["unindexeditems", "partiallyindexeditems", "unindexed", "partiallyindexed"],
}


def build_lookup(aliases):
    out = {}
    for canon, names in aliases.items():
        out[nkey(canon)] = canon
        for n in names:
            out[nkey(n)] = canon
    return out


ITEM_LOOKUP = build_lookup(ITEM_ALIASES)
LOCATION_LOOKUP = build_lookup(LOCATION_ALIASES)
SUMMARY_LOOKUP = build_lookup(SUMMARY_ALIASES)


def map_row(row, lookup):
    """Return {canonical_field: value} plus the list of headers we could not map."""
    mapped, unmapped = {}, []
    for header, value in row.items():
        if header is None:
            continue
        canon = lookup.get(nkey(header))
        if canon:
            if canon not in mapped or (not mapped[canon] and value):
                mapped[canon] = value
        else:
            unmapped.append(header)
    return mapped, unmapped


# --------------------------------------------------------------------------
# file classification and location parsing
# --------------------------------------------------------------------------

def sniff_headers(path, limit=1):
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            for row in reader:
                return [c.strip() for c in row]
    except (UnicodeDecodeError, OSError):
        try:
            with open(path, "r", encoding="latin-1", newline="") as fh:
                for row in csv.reader(fh):
                    return [c.strip() for c in row]
        except OSError:
            return []
    return []


def detect_file_type(path, headers):
    name = nkey(path.name)
    hset = {nkey(h) for h in headers}
    if "location" in name or "locations" in name:
        return "locations"
    if "setting" in name or "config" in name:
        return "settings"
    if "summary" in name:
        return "summary"
    if "item" in name or "loadfile" in name or "result" in name:
        return "items"
    # header based fallback
    loc_hits = sum(1 for h in hset if LOCATION_LOOKUP.get(h) in ("item_count", "location_subtype"))
    item_hits = sum(1 for h in hset if ITEM_LOOKUP.get(h) in ("file_name", "title_or_subject", "size_bytes", "item_path"))
    if item_hits >= 2:
        return "items"
    if loc_hits >= 1 and len(hset) <= 12:
        return "locations"
    if len(hset) <= 4:
        return "summary"
    return "unknown"


def iter_csv(path):
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(path, "r", encoding=enc, newline="") as fh:
                for n, row in enumerate(csv.DictReader(fh), start=1):
                    yield n, row
            return
        except UnicodeDecodeError:
            continue


ONEDRIVE_RE = re.compile(r"^(https?://[^/]*-my\.sharepoint\.com)/personal/([^/]+)(/.*)?$", re.I)
SITE_RE = re.compile(r"^(https?://[^/]+/(?:sites|teams)/[^/]+)(/.*)?$", re.I)
ROOT_RE = re.compile(r"^(https?://[^/]+)(/.*)?$", re.I)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def personal_segment_to_upn(seg):
    """john_smith_leonardo_com -> john.smith@leonardo.com. Heuristic, flagged as such."""
    parts = seg.split("_")
    if len(parts) < 3:
        return None
    if len(parts) >= 4 and parts[-1] in ("uk", "us", "it", "au") and len(parts[-2]) <= 3:
        domain = ".".join(parts[-3:])
        user = ".".join(parts[:-3])
    else:
        domain = ".".join(parts[-2:])
        user = ".".join(parts[:-2])
    return "%s@%s" % (user, domain) if user else None


def classify_repo(site_url, site_title, rules):
    hay = ("%s %s" % (site_url or "", site_title or "")).lower()
    for rule in rules:
        if re.search(rule["match"], hay, re.I):
            return rule["class"]
    return "corporate"


def parse_location(fields, config):
    """Work out one canonical container from whatever the export gave us."""
    raw = (fields.get("raw_location") or "").strip()
    path = (fields.get("item_path") or "").strip()
    site_url = (fields.get("site_url") or "").strip()
    workload = (fields.get("workload") or "").strip()
    team = (fields.get("team_name") or "").strip()
    channel = (fields.get("channel_name") or "").strip()
    mailbox = (fields.get("mailbox_upn") or "").strip()

    url = path or site_url or raw
    url_nq = url.split("?")[0].rstrip("/")

    loc = {
        "workload": None, "location_subtype": None, "raw_location": raw or url or mailbox,
        "site_url": None, "site_title": fields.get("site_title"), "library_name": None,
        "folder_path": None, "folder_depth": 0, "mailbox_upn": None,
        "team_name": team or None, "channel_name": channel or None,
    }

    m = ONEDRIVE_RE.match(url_nq)
    if m:
        loc["workload"] = "OneDrive"
        loc["location_subtype"] = "OneDriveSite"
        loc["site_url"] = "%s/personal/%s" % (m.group(1), m.group(2))
        loc["mailbox_upn"] = personal_segment_to_upn(m.group(2))
        rest = (m.group(3) or "").strip("/")
    else:
        m = SITE_RE.match(url_nq)
        if m:
            loc["workload"] = "Teams" if "/teams/" in m.group(1).lower() or team else "SharePoint"
            loc["location_subtype"] = "TeamSite" if loc["workload"] == "Teams" else "SharePointSite"
            loc["site_url"] = m.group(1)
            rest = (m.group(2) or "").strip("/")
        elif EMAIL_RE.match(raw) or EMAIL_RE.match(mailbox):
            loc["workload"] = "Exchange"
            loc["location_subtype"] = fields.get("location_subtype") or "PrimaryMailbox"
            loc["mailbox_upn"] = (mailbox or raw).lower()
            rest = ""
        elif url_nq.lower().startswith("http"):
            m = ROOT_RE.match(url_nq)
            loc["workload"] = "SharePoint"
            loc["location_subtype"] = "SharePointSite"
            loc["site_url"] = m.group(1) if m else url_nq
            rest = (m.group(2) or "").strip("/") if m else ""
        else:
            loc["workload"] = workload or ("Teams" if team else "Unknown")
            loc["location_subtype"] = fields.get("location_subtype") or "Unknown"
            rest = ""

    if rest:
        segs = [s for s in rest.split("/") if s]
        if segs and ("." in segs[-1]):  # looks like a file name, drop it
            segs = segs[:-1]
        if segs:
            loc["library_name"] = segs[0]
            loc["folder_path"] = "/".join(segs[1:]) or None
            loc["folder_depth"] = len(segs) - 1

    if fields.get("location_subtype"):
        loc["location_subtype"] = fields["location_subtype"]
    if workload and not loc["workload"]:
        loc["workload"] = workload

    loc["repo_class"] = classify_repo(loc["site_url"] or loc["mailbox_upn"], loc["site_title"], config["repo_class_rules"])
    if loc["location_subtype"] == "OneDriveSite":
        loc["repo_class"] = "personal"

    loc["location_key"] = sha1s(loc["workload"], loc["location_subtype"], (loc["site_url"] or "").lower(),
                                (loc["mailbox_upn"] or "").lower(), (loc["library_name"] or "").lower(),
                                (loc["folder_path"] or "").lower(), (loc["team_name"] or "").lower(),
                                (loc["channel_name"] or "").lower())
    return loc


# --------------------------------------------------------------------------
# configuration
# --------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "internal_domains": [],
    "technical_extensions": ["dwg", "dxf", "step", "stp", "iges", "igs", "catpart", "catproduct",
                             "prt", "asm", "sldprt", "slddrw", "sldasm", "ipt", "iam", "idw",
                             "nc", "cnc", "gerber", "brd", "sch", "vhd", "vhdl", "v", "c", "h", "cpp",
                             "m", "mdl", "slx", "cdb", "inp", "unv"],
    "archive_extensions": ["zip", "7z", "rar", "tar", "gz", "cab"],
    "document_type_terms": ["drawing", "specification", "spec", "interface control", "icd",
                            "test report", "analysis", "datasheet", "manual", "technical data package", "tdp"],
    "programme_patterns": [r"\b[A-Z]{2,5}-\d{3,6}\b", r"\b\d{3}-\d{4,6}(?:-\d+)?\b",
                           r"\bP/?N[ :-]?\s*[A-Z0-9-]{4,}\b", r"\bDWG[ -]?\d+\b"],
    "repo_class_rules": [
        {"match": r"/personal/", "class": "personal"},
        {"match": r"(policy|policies|hr\b|quality|bms|businessmanagement|intranet|comms|training|induction|handbook)", "class": "policy"},
        {"match": r"(engineer|\beng[-_]|design|\bcad\b|drawing|technical|\btech[-_]|r&d|rnd|\blab[-_]|test)", "class": "engineering"},
        {"match": r"(programme|program|\bprog[-_]|project|\bproj[-_]|bid|tender|contract|campaign)", "class": "programme"},
    ],
    "bands": [[30, "critical"], [20, "high"], [10, "medium"], [0, "low"]],
    "location_bands": [[70, "critical"], [50, "high"], [30, "medium"], [0, "low"]],
    "weights": {
        "F01_category_diversity": 4, "F01_cap": 12,
        "F02_specificity_3": 5, "F02_specificity_2": 3, "F02_specificity_1": 1,
        "F03_marking_in_name": 6,
        "F04_technical_type": 5,
        "F05_programme_pattern": 5,
        "F06_engineering_repo": 3,
        "F07_known_itar_repo": -4,
        "F08_unexpected_location": 4,
        "F09_missing_label": 3,
        "F11_external_recipient": 4,
        "F12_procedural_only": -6,
        "F13_widely_duplicated": 2,
        "F14_recent": 1,
    },
    "location_weights": {"peak": 0.35, "diversity": 0.25, "density": 0.20, "breadth": 0.20},
    "widely_duplicated_threshold": 5,
    "recent_months": 24,
}


def load_config(path):
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if path and Path(path).exists():
        user = json.loads(Path(path).read_text(encoding="utf-8"))
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    return cfg


# --------------------------------------------------------------------------
# database
# --------------------------------------------------------------------------

def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    conn.execute("INSERT OR IGNORE INTO schema_version(version, applied_at, note) VALUES (?,?,?)",
                 (SCHEMA_VERSION, now_iso(), "initial"))
    for code, name, pol, desc in DEFAULT_CATEGORIES:
        conn.execute("INSERT OR IGNORE INTO keyword_category(category_code, category_name, polarity, description) "
                     "VALUES (?,?,?,?)", (code, name, pol, desc))
    conn.commit()
    return conn


def issue(conn, code, severity, scope_type, scope_ref, detail, source_file_id=None):
    conn.execute("INSERT INTO data_quality_issue(issue_code, severity, scope_type, scope_ref, "
                 "source_file_id, detail, detected_at) VALUES (?,?,?,?,?,?,?)",
                 (code, severity, scope_type, str(scope_ref), source_file_id, detail, now_iso()))


def load_keywords(conn, path):
    """keywords.csv: run_name,keyword,category,specificity,owner,note"""
    if not path:
        return
    p = Path(path)
    if not p.exists():
        print("  keyword file not found: %s" % p)
        return
    n = 0
    for _, row in iter_csv(p):
        row = {nkey(k): (v or "").strip() for k, v in row.items() if k}
        kw = row.get("keyword")
        if not kw:
            continue
        conn.execute(
            "INSERT INTO keyword(keyword_text, normalised_text, category_code, specificity, owner, guidance_note) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(keyword_text) DO UPDATE SET "
            "category_code=excluded.category_code, specificity=excluded.specificity, "
            "owner=excluded.owner, guidance_note=excluded.guidance_note",
            (kw, nkey(kw), (row.get("category") or "A").upper()[:1],
             parse_int(row.get("specificity")) or 2, row.get("owner"), row.get("note")))
        n += 1
    conn.commit()
    print("  keywords defined: %d" % n)


def keyword_for_run(conn, run_name, query_text, keyword_map):
    """Resolve which keyword a run represents. Refuses to guess blindly."""
    if run_name in keyword_map:
        return keyword_map[run_name]
    for stored_run, kw in keyword_map.items():
        if stored_run and nkey(stored_run) and nkey(stored_run) in nkey(run_name):
            return kw
    if query_text:
        q = query_text.strip().strip('"')
        m = re.match(r'^[\w ]*?["“]?([^"”]+)["”]?$', q)
        cand = (m.group(1) if m else q).strip()
        if cand and len(cand) < 120:
            return cand
    return None


def read_keyword_map(path):
    """run_name -> keyword, from the same keywords.csv."""
    out = {}
    if not path or not Path(path).exists():
        return out
    for _, row in iter_csv(Path(path)):
        row = {nkey(k): (v or "").strip() for k, v in row.items() if k}
        if row.get("run_name") and row.get("keyword"):
            out[row["run_name"]] = row["keyword"]
    return out


def get_keyword_id(conn, text):
    if not text:
        return None
    cur = conn.execute("SELECT keyword_id FROM keyword WHERE keyword_text = ?", (text,))
    r = cur.fetchone()
    if r:
        return r["keyword_id"]
    cur = conn.execute("INSERT INTO keyword(keyword_text, normalised_text, category_code, specificity, status) "
                       "VALUES (?,?,?,?,?)", (text, nkey(text), "A", 2, "unclassified"))
    issue(conn, "KEYWORD_UNCLASSIFIED", "medium", "keyword", text,
          "Keyword seen in an export but not present in keywords.csv. Defaulted to category A, specificity 2.")
    return cur.lastrowid


def upsert_location(conn, loc):
    cur = conn.execute("SELECT location_id FROM location WHERE location_key = ?", (loc["location_key"],))
    r = cur.fetchone()
    if r:
        return r["location_id"]
    cur = conn.execute(
        "INSERT INTO location(location_key, workload, location_subtype, raw_location, site_url, site_title, "
        "library_name, folder_path, folder_depth, mailbox_upn, team_name, channel_name, repo_class) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (loc["location_key"], loc["workload"], loc["location_subtype"], loc["raw_location"], loc["site_url"],
         loc["site_title"], loc["library_name"], loc["folder_path"], loc["folder_depth"], loc["mailbox_upn"],
         loc["team_name"], loc["channel_name"], loc["repo_class"]))
    return cur.lastrowid


def derive_item_key(f, loc):
    if f.get("immutable_id"):
        return sha1s("imm", f["immutable_id"]), "immutable_id", "high"
    if f.get("message_id") and loc.get("mailbox_upn"):
        return sha1s("msg", f["message_id"], loc["mailbox_upn"].lower()), "message_id+mailbox", "high"
    if f.get("item_path"):
        p = f["item_path"].split("?")[0].rstrip("/").lower()
        return sha1s("path", p, f.get("version_id") or ""), "path+version", "medium"
    if f.get("source_item_id"):
        return sha1s("src", f["source_item_id"], loc["location_key"]), "source_item_id", "medium"
    return sha1s("fallback", loc["location_key"], (f.get("file_name") or f.get("title_or_subject") or "").lower(),
                 f.get("size_bytes") or "", f.get("created_utc") or ""), "fallback_hash", "low"


UNREADABLE_HINTS = ("unsupported", "encrypt", "password", "partially indexed", "indexing error",
                    "error", "notindexed", "unindexed", "failed", "toolarge")


def ingest_export_folder(conn, root, keyword_file, config):
    root = Path(root)
    if not root.exists():
        print("Export folder not found: %s" % root)
        return
    keyword_map = read_keyword_map(keyword_file)

    kw_path = Path(keyword_file).resolve() if keyword_file else None
    csv_files = sorted(p for p in root.rglob("*.csv")
                       if p.is_file() and p.resolve() != kw_path and nkey(p.stem) != "keywords")
    if not csv_files:
        print("No CSV files found under %s" % root)
        return

    by_run = {}
    for p in csv_files:
        rel = p.relative_to(root)
        run_name = rel.parts[0] if len(rel.parts) > 1 else p.stem
        by_run.setdefault(run_name, []).append(p)

    for run_name, files in sorted(by_run.items()):
        print("\nRun: %s  (%d files)" % (run_name, len(files)))
        classified = []
        for p in files:
            headers = sniff_headers(p)
            classified.append((p, headers, detect_file_type(p, headers)))

        query_text, case_name, search_date = None, None, None
        for p, headers, ftype in classified:
            if ftype in ("summary", "settings"):
                for _, row in iter_csv(p):
                    mapped, _ = map_row(row, SUMMARY_LOOKUP)
                    query_text = query_text or mapped.get("query_text")
                    case_name = case_name or mapped.get("case_name")
                    search_date = search_date or parse_date(mapped.get("search_date"))
                    # key/value shaped summary files
                    vals = [v for v in row.values() if v]
                    if len(row) == 2 and vals:
                        k, v = list(row.items())[0][1], list(row.items())[1][1]
                        if nkey(k or "") in SUMMARY_LOOKUP and SUMMARY_LOOKUP[nkey(k or "")] == "query_text":
                            query_text = query_text or v

        conn.execute("INSERT OR IGNORE INTO search_run(run_name, case_name, query_text, search_date, "
                     "export_folder, ingested_at) VALUES (?,?,?,?,?,?)",
                     (run_name, case_name, query_text, search_date, str(root), now_iso()))
        run_id = conn.execute("SELECT search_run_id FROM search_run WHERE run_name = ?", (run_name,)).fetchone()[0]

        kw_text = keyword_for_run(conn, run_name, query_text, keyword_map)
        kw_id = get_keyword_id(conn, kw_text) if kw_text else None
        if kw_id:
            conn.execute("INSERT OR IGNORE INTO search_run_keyword(search_run_id, keyword_id) VALUES (?,?)",
                         (run_id, kw_id))
            print("  keyword: %s" % kw_text)
        else:
            issue(conn, "RUN_NO_KEYWORD", "high", "search_run", run_name,
                  "No keyword could be resolved for this run. Items loaded without keyword evidence.")
            print("  keyword: NOT RESOLVED (add a row to keywords.csv with run_name=%s)" % run_name)

        for p, headers, ftype in classified:
            ingest_file(conn, run_id, kw_id, root, p, headers, ftype, config)
        conn.commit()


def ingest_file(conn, run_id, kw_id, root, path, headers, ftype, config):
    digest = sha256_file(path)
    if conn.execute("SELECT 1 FROM source_file WHERE file_sha256 = ? AND search_run_id = ?",
                    (digest, run_id)).fetchone():
        print("  skip (already loaded): %s" % path.name)
        return
    cur = conn.execute(
        "INSERT INTO source_file(search_run_id, file_name, rel_path, file_type, file_sha256, row_count, "
        "header_signature, ingested_at) VALUES (?,?,?,?,?,?,?,?)",
        (run_id, path.name, str(path.relative_to(root)), ftype, digest, 0, "|".join(headers), now_iso()))
    sf_id = cur.lastrowid

    if ftype == "items":
        n = ingest_items(conn, run_id, kw_id, sf_id, path, config)
    elif ftype == "locations":
        n = ingest_locations(conn, run_id, kw_id, sf_id, path, config)
    else:
        n = 0
        for rn, row in iter_csv(path):
            conn.execute("INSERT INTO raw_row(source_file_id, row_number, raw_json) VALUES (?,?,?)",
                         (sf_id, rn, json.dumps(row, ensure_ascii=False)))
            n += 1
    conn.execute("UPDATE source_file SET row_count = ? WHERE source_file_id = ?", (n, sf_id))
    print("  loaded %-10s %-40s %6d rows" % (ftype, path.name, n))


def ingest_items(conn, run_id, kw_id, sf_id, path, config):
    count = 0
    internal = [d.lower() for d in config["internal_domains"]]
    for rn, row in iter_csv(path):
        conn.execute("INSERT INTO raw_row(source_file_id, row_number, raw_json) VALUES (?,?,?)",
                     (sf_id, rn, json.dumps(row, ensure_ascii=False)))
        raw_id = conn.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]
        f, unmapped = map_row(row, ITEM_LOOKUP)
        for h in unmapped:
            conn.execute("INSERT OR IGNORE INTO unmapped_header(header, file_type, example_file) VALUES (?,?,?)",
                         (h, "items", path.name))

        loc = parse_location(f, config)
        loc_id = upsert_location(conn, loc)

        f["size_bytes"] = parse_int(f.get("size_bytes"))
        for d in ("created_utc", "sent_utc", "modified_utc", "received_utc"):
            f[d] = parse_date(f.get(d))
        item_key, method, confidence = derive_item_key(f, loc)

        name = f.get("file_name") or ""
        ext = (f.get("file_extension") or "").lstrip(".").lower()
        if not ext and "." in name:
            ext = name.rsplit(".", 1)[1].lower()

        idx = (f.get("index_status") or "").lower()
        unreadable = 1 if any(h in idx for h in UNREADABLE_HINTS) else 0

        path_l = (f.get("item_path") or "").lower()
        doc_group = sha1s("doc", re.sub(r"[?&]versionid=[^&]*", "", path_l)) if path_l else None
        if f.get("message_id"):
            content_group = sha1s("cg", f["message_id"])
        else:
            content_group = sha1s("cg", name.lower(), f.get("size_bytes") or "", f.get("created_utc") or "")

        conn.execute("""
            INSERT INTO item(item_key, key_method, key_confidence, content_group_id, doc_group_id, location_id,
                workload, source_item_id, family_id, conversation_id, message_id, file_name, file_extension,
                title_or_subject, author, sender, created_utc, sent_utc, modified_utc, size_bytes, word_count,
                extracted_text_len, sensitivity_label, retention_label, has_attachments, index_status,
                is_unreadable, is_list_item, version_id, item_path, first_seen_run, last_seen_run)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(item_key) DO UPDATE SET last_seen_run = excluded.last_seen_run""",
            (item_key, method, confidence, content_group, doc_group, loc_id, loc["workload"],
             f.get("source_item_id"), f.get("family_id"), f.get("conversation_id"), f.get("message_id"),
             name or None, ext or None, f.get("title_or_subject"), f.get("author"), f.get("sender"),
             f.get("created_utc"), f.get("sent_utc") or f.get("received_utc"), f.get("modified_utc"),
             f.get("size_bytes"), parse_int(f.get("word_count")), parse_int(f.get("extracted_text_len")),
             f.get("sensitivity_label") or None, f.get("retention_label") or None,
             truthy(f.get("has_attachments")), f.get("index_status"), unreadable,
             1 if "/lists/" in path_l else 0, f.get("version_id"), f.get("item_path"), run_id, run_id))

        item_id = conn.execute("SELECT item_id FROM item WHERE item_key = ?", (item_key,)).fetchone()["item_id"]

        for role, key in (("sender", "sender"), ("to", "recipients_to"), ("cc", "recipients_cc"),
                          ("bcc", "recipients_bcc"), ("participant", "participants")):
            blob = f.get(key)
            if not blob:
                continue
            for addr in re.split(r"[;,]", str(blob)):
                addr = addr.strip().strip("<>").lower()
                if not addr or "@" not in addr:
                    continue
                dom = addr.rsplit("@", 1)[1]
                conn.execute("INSERT INTO item_participant(item_id, role, party_address, party_domain, is_internal) "
                             "VALUES (?,?,?,?,?)",
                             (item_id, role, addr, dom, 1 if dom in internal else 0))

        row_kw = f.get("keyword")
        this_kw = get_keyword_id(conn, row_kw) if row_kw else kw_id
        if this_kw:
            conn.execute("INSERT OR IGNORE INTO item_keyword_hit(item_id, keyword_id, search_run_id, "
                         "source_file_id, raw_row_id, first_seen_at) VALUES (?,?,?,?,?,?)",
                         (item_id, this_kw, run_id, sf_id, raw_id, now_iso()))
        count += 1
    return count


def ingest_locations(conn, run_id, kw_id, sf_id, path, config):
    count = 0
    for rn, row in iter_csv(path):
        conn.execute("INSERT INTO raw_row(source_file_id, row_number, raw_json) VALUES (?,?,?)",
                     (sf_id, rn, json.dumps(row, ensure_ascii=False)))
        f, unmapped = map_row(row, LOCATION_LOOKUP)
        for h in unmapped:
            conn.execute("INSERT OR IGNORE INTO unmapped_header(header, file_type, example_file) VALUES (?,?,?)",
                         (h, "locations", path.name))
        loc = parse_location(f, config)
        loc_id = upsert_location(conn, loc)
        if kw_id:
            conn.execute("INSERT OR REPLACE INTO location_stats(search_run_id, keyword_id, location_id, "
                         "item_count, total_size_bytes) VALUES (?,?,?,?,?)",
                         (run_id, kw_id, loc_id, parse_int(f.get("item_count")) or 0,
                          parse_int(f.get("total_size_bytes")) or 0))
        count += 1
    return count


# --------------------------------------------------------------------------
# scoring
# --------------------------------------------------------------------------

def band_for(score, bands):
    for threshold, name in bands:
        if score >= threshold:
            return name
    return "low"


def status_for(cats, has_technical, unreadable, score, band):
    if unreadable:
        return "insufficient_metadata"
    if cats and cats <= {"G"}:
        return "likely_false_positive"
    if cats and cats <= {"F", "G"}:
        return "procedural_or_reference"
    if len(cats) >= 3 and band in ("high", "critical"):
        return "high_priority_business_review"
    if has_technical and (cats & {"A", "B"}):
        return "possible_itar_technical_data"
    if "C" in cats and not has_technical:
        return "possible_contract_or_programme"
    if not cats:
        return "insufficient_metadata"
    return "procedural_or_reference" if "F" in cats else "possible_contract_or_programme"


def score_items(conn, config):
    w = config["weights"]
    tech_ext = set(config["technical_extensions"])
    doc_terms = [t.lower() for t in config["document_type_terms"]]
    patterns = [re.compile(p) for p in config["programme_patterns"]]
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=30 * config["recent_months"])).strftime("%Y-%m-%dT%H:%M:%SZ")

    conn.execute("DELETE FROM score_factor WHERE score_id IN (SELECT score_id FROM score WHERE score_version = ? "
                 "AND scope_type = 'item')", (SCORE_VERSION,))
    conn.execute("DELETE FROM score WHERE score_version = ? AND scope_type = 'item'", (SCORE_VERSION,))

    label_counts = {}
    for r in conn.execute("SELECT location_id, SUM(CASE WHEN sensitivity_label IS NOT NULL AND "
                          "sensitivity_label <> '' THEN 1 ELSE 0 END) AS labelled, COUNT(*) AS total "
                          "FROM item GROUP BY location_id"):
        label_counts[r["location_id"]] = (r["labelled"], r["total"])

    spread = {}
    for r in conn.execute("SELECT content_group_id, COUNT(DISTINCT location_id) AS n FROM item "
                          "WHERE content_group_id IS NOT NULL GROUP BY content_group_id"):
        spread[r["content_group_id"]] = r["n"]

    ext_ref = {r["ref_value"].lower() for r in conn.execute(
        "SELECT ref_value FROM reference_programme WHERE ref_type = 'approved_repository'")}

    rows = conn.execute("""
        SELECT i.*, l.repo_class, l.site_url, l.location_subtype,
               s.n_categories, s.n_keywords, s.max_specificity, s.categories, s.keywords
        FROM item i
        JOIN location l ON l.location_id = i.location_id
        LEFT JOIN v_item_signals s ON s.item_id = i.item_id""").fetchall()

    for it in rows:
        cats = set((it["categories"] or "").split(",")) - {""}
        factors, total = [], 0.0

        n_extra = max(0, len(cats) - 1)
        pts = min(n_extra * w["F01_category_diversity"], w["F01_cap"])
        if pts:
            factors.append(("F01", "categories=%s" % ",".join(sorted(cats)), pts, "independent indicator classes"))
            total += pts

        spec = it["max_specificity"] or 0
        pts = w.get("F02_specificity_%d" % spec, 0)
        if pts:
            factors.append(("F02", "specificity=%d" % spec, pts, "strength of strongest matched term"))
            total += pts

        name_blob = ("%s %s" % (it["file_name"] or "", it["title_or_subject"] or "")).lower()
        if "B" in cats:
            for kw in (it["keywords"] or "").split(","):
                if kw and kw.lower() in name_blob:
                    factors.append(("F03", kw, w["F03_marking_in_name"], "handling marking in the name itself"))
                    total += w["F03_marking_in_name"]
                    break

        ext = (it["file_extension"] or "").lower()
        is_tech = ext in tech_ext or any(t in name_blob for t in doc_terms) or "D" in cats
        if is_tech:
            factors.append(("F04", ext or "doc-type term", w["F04_technical_type"], "technical document type"))
            total += w["F04_technical_type"]

        hay = "%s %s" % (name_blob, (it["item_path"] or "").lower())
        for pat in patterns:
            m = pat.search(hay.upper())
            if m:
                factors.append(("F05", m.group(0), w["F05_programme_pattern"], "programme or part number pattern"))
                total += w["F05_programme_pattern"]
                break

        if it["repo_class"] in ("engineering", "programme"):
            factors.append(("F06", it["repo_class"], w["F06_engineering_repo"], "engineering or programme repository"))
            total += w["F06_engineering_repo"]

        if (it["site_url"] or "").lower() in ext_ref:
            factors.append(("F07", "approved repository", w["F07_known_itar_repo"], "expected location for controlled data"))
            total += w["F07_known_itar_repo"]
        elif it["repo_class"] in ("personal", "corporate") and cats & {"A", "B", "C", "D"}:
            factors.append(("F08", it["repo_class"], w["F08_unexpected_location"], "controlled signals outside a controlled repository"))
            total += w["F08_unexpected_location"]

        labelled, total_items = label_counts.get(it["location_id"], (0, 0))
        if not (it["sensitivity_label"] or "") and total_items >= 5 and labelled >= total_items * 0.5:
            factors.append(("F09", "%d of %d peers labelled" % (labelled, total_items),
                            w["F09_missing_label"], "no label where the library normally labels"))
            total += w["F09_missing_label"]

        ext_party = conn.execute("SELECT COUNT(*) AS n FROM item_participant WHERE item_id = ? AND is_internal = 0 "
                                 "AND role <> 'sender'", (it["item_id"],)).fetchone()["n"]
        if ext_party and config["internal_domains"]:
            factors.append(("F11", "%d external recipients" % ext_party, w["F11_external_recipient"], "sent outside the organisation"))
            total += w["F11_external_recipient"]

        if cats and cats <= {"F", "G"}:
            factors.append(("F12", ",".join(sorted(cats)), w["F12_procedural_only"], "only procedural or noise terms matched"))
            total += w["F12_procedural_only"]

        n_loc = spread.get(it["content_group_id"], 1)
        if n_loc >= config["widely_duplicated_threshold"]:
            pts = w["F13_widely_duplicated"] if not (cats <= {"F", "G"}) else 0
            if pts:
                factors.append(("F13", "in %d locations" % n_loc, pts, "content has spread widely"))
                total += pts

        newest = max([d for d in (it["modified_utc"], it["created_utc"], it["sent_utc"]) if d] or [""])
        if newest and newest >= cutoff:
            factors.append(("F14", newest[:10], w["F14_recent"], "recently active"))
            total += w["F14_recent"]

        total = max(0.0, total)
        bnd = band_for(total, config["bands"])
        st = status_for(cats, is_tech, it["is_unreadable"], total, bnd)
        cur = conn.execute("INSERT INTO score(scope_type, scope_ref, score_version, total_score, band, "
                           "status_code, computed_at) VALUES ('item',?,?,?,?,?,?)",
                           (str(it["item_id"]), SCORE_VERSION, total, bnd, st, now_iso()))
        sid = cur.lastrowid
        for code, val, pts, note in factors:
            conn.execute("INSERT INTO score_factor(score_id, factor_code, factor_value, points, note) "
                         "VALUES (?,?,?,?,?)", (sid, code, str(val), pts, note))
    conn.commit()
    print("  scored items: %d" % len(rows))


def norm(value, maximum):
    return 0.0 if not maximum else float(value) / float(maximum)


def score_locations(conn, config):
    lw = config["location_weights"]
    conn.execute("DELETE FROM score_factor WHERE score_id IN (SELECT score_id FROM score WHERE score_version = ? "
                 "AND scope_type <> 'item')", (SCORE_VERSION,))
    conn.execute("DELETE FROM score WHERE score_version = ? AND scope_type <> 'item'", (SCORE_VERSION,))

    scopes = {
        "site": "CASE WHEN l.workload IN ('SharePoint','Teams') THEN l.site_url END",
        "onedrive": "CASE WHEN l.workload = 'OneDrive' THEN l.site_url END",
        "mailbox": "CASE WHEN l.workload = 'Exchange' THEN l.mailbox_upn END",
        "team": "CASE WHEN l.workload = 'Teams' THEN COALESCE(l.team_name, l.site_url) || ' / ' || COALESCE(l.channel_name,'(all)') END",
        "folder": "CAST(l.location_id AS TEXT)",
    }

    for scope_type, expr in scopes.items():
        rows = conn.execute("""
            SELECT %s AS scope_ref,
                   COUNT(DISTINCT i.item_id)                          AS raw_items,
                   COUNT(DISTINCT i.doc_group_id)                     AS distinct_docs,
                   COUNT(DISTINCT i.content_group_id)                 AS distinct_content,
                   MAX(sc.total_score)                                AS peak,
                   AVG(sc.total_score)                                AS mean,
                   SUM(CASE WHEN i.is_unreadable = 1 THEN 1 ELSE 0 END) AS unreadable,
                   SUM(CASE WHEN i.is_list_item = 1 THEN 1 ELSE 0 END)  AS list_items,
                   MIN(l.repo_class)                                  AS repo_class,
                   MIN(l.workload)                                    AS workload
            FROM item i
            JOIN location l ON l.location_id = i.location_id
            LEFT JOIN score sc ON sc.scope_type='item' AND sc.scope_ref = CAST(i.item_id AS TEXT)
                              AND sc.score_version = ?
            WHERE %s IS NOT NULL
            GROUP BY 1""" % (expr, expr), (SCORE_VERSION,)).fetchall()
        if not rows:
            continue

        detail = {}
        for r in rows:
            ref = r["scope_ref"]
            d = conn.execute("""
                SELECT COUNT(DISTINCT k.category_code) AS cats,
                       COUNT(DISTINCT CASE WHEN k.specificity >= 3 THEN k.keyword_id END) AS strong,
                       GROUP_CONCAT(DISTINCT k.category_code) AS catlist
                FROM item i JOIN location l ON l.location_id = i.location_id
                JOIN item_keyword_hit h ON h.item_id = i.item_id
                JOIN keyword k ON k.keyword_id = h.keyword_id
                WHERE %s = ?""" % expr, (ref,)).fetchone()
            detail[ref] = d

        max_peak = max([r["peak"] or 0 for r in rows]) or 1
        max_cats = max([detail[r["scope_ref"]]["cats"] or 0 for r in rows]) or 1
        max_docs = max([r["distinct_docs"] or 0 for r in rows]) or 1
        max_strong = max([detail[r["scope_ref"]]["strong"] or 0 for r in rows]) or 1

        for r in rows:
            ref = r["scope_ref"]
            d = detail[ref]
            comps = [
                ("L01", "peak=%.1f" % (r["peak"] or 0), lw["peak"] * norm(r["peak"] or 0, max_peak) * 100,
                 "strongest single item, not volume"),
                ("L02", (d["catlist"] or "none"), lw["diversity"] * norm(d["cats"] or 0, max_cats) * 100,
                 "distinct indicator classes seen here: %s" % (d["catlist"] or "none")),
                ("L03", "%d docs" % (r["distinct_docs"] or 0), lw["density"] * norm(r["distinct_docs"] or 0, max_docs) * 100,
                 "distinct documents after collapsing versions and copies"),
                ("L04", "%d strong terms" % (d["strong"] or 0), lw["breadth"] * norm(d["strong"] or 0, max_strong) * 100,
                 "distinct high specificity terms"),
            ]
            total = sum(c[2] for c in comps)
            factors = list(comps)
            if r["repo_class"] == "policy":
                factors.append(("L05", "policy repository", -10.0, "reference site, deprioritised not excluded"))
                total -= 10.0
            if r["repo_class"] in ("engineering", "programme"):
                factors.append(("L06", r["repo_class"], 8.0, "engineering or programme repository"))
                total += 8.0
            if r["list_items"]:
                factors.append(("L07", "%d list items" % r["list_items"], 0.0,
                                "SharePoint list artefact, counted once, see appendix A"))
            # context only, deliberately zero points: volume must not drive the ranking
            factors.append(("C01", str(r["raw_items"] or 0), 0.0, "raw matched items, context only"))
            factors.append(("C02", str(r["distinct_docs"] or 0), 0.0, "distinct documents after collapsing versions"))
            factors.append(("C03", str(r["unreadable"] or 0), 0.0, "unreadable items needing separate investigation"))
            factors.append(("C04", r["workload"] or "", 0.0, "workload"))
            factors.append(("C05", r["repo_class"] or "", 0.0, "repository class"))
            total = max(0.0, total)
            bnd = band_for(total, config["location_bands"])
            cur = conn.execute("INSERT INTO score(scope_type, scope_ref, score_version, total_score, band, "
                               "status_code, computed_at) VALUES (?,?,?,?,?,?,?)",
                               (scope_type, str(ref), SCORE_VERSION, total, bnd, "ranked", now_iso()))
            sid = cur.lastrowid
            for code, val, pts, note in factors:
                conn.execute("INSERT INTO score_factor(score_id, factor_code, factor_value, points, note) "
                             "VALUES (?,?,?,?,?)", (sid, code, str(val), round(pts, 2), note))
        print("  scored %-9s scopes: %d" % (scope_type, len(rows)))
    conn.commit()


# --------------------------------------------------------------------------
# reports
# --------------------------------------------------------------------------

def write_report(out_dir, name, conn, sql, params=()):
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    path = Path(out_dir) / ("%s.csv" % name)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(cols)
        n = 0
        for row in cur:
            wr.writerow(["" if v is None else v for v in row])
            n += 1
    print("  %-38s %6d rows -> %s" % (name, n, path.name))
    return n


LOC_RANK_SQL = """
SELECT s.scope_ref                         AS location,
       ROUND(s.total_score, 1)             AS score,
       s.band,
       (SELECT factor_value FROM score_factor f WHERE f.score_id = s.score_id AND f.factor_code='L02') AS indicator_classes,
       (SELECT ROUND(points,1) FROM score_factor f WHERE f.score_id = s.score_id AND f.factor_code='L01') AS pts_peak,
       (SELECT ROUND(points,1) FROM score_factor f WHERE f.score_id = s.score_id AND f.factor_code='L02') AS pts_diversity,
       (SELECT ROUND(points,1) FROM score_factor f WHERE f.score_id = s.score_id AND f.factor_code='L03') AS pts_density,
       (SELECT ROUND(points,1) FROM score_factor f WHERE f.score_id = s.score_id AND f.factor_code='L04') AS pts_breadth,
       (SELECT note FROM score_factor f WHERE f.score_id = s.score_id AND f.factor_code='L02') AS diversity_note,
       (SELECT GROUP_CONCAT(factor_value || ' (' || points || ')', ' | ') FROM score_factor f
          WHERE f.score_id = s.score_id AND f.factor_code IN ('L05','L06','L07')) AS modifiers,
       (SELECT factor_value FROM score_factor f WHERE f.score_id = s.score_id AND f.factor_code='C04') AS workload,
       (SELECT factor_value FROM score_factor f WHERE f.score_id = s.score_id AND f.factor_code='C05') AS repo_class,
       (SELECT factor_value FROM score_factor f WHERE f.score_id = s.score_id AND f.factor_code='C01') AS raw_matches_context_only,
       (SELECT factor_value FROM score_factor f WHERE f.score_id = s.score_id AND f.factor_code='C02') AS distinct_documents,
       (SELECT factor_value FROM score_factor f WHERE f.score_id = s.score_id AND f.factor_code='C03') AS unreadable_items
FROM score s
WHERE s.scope_type = ? AND s.score_version = ?
ORDER BY s.total_score DESC"""


def build_reports(conn, out_dir, config):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    v = SCORE_VERSION

    write_report(out, "01_item_register", conn, """
        SELECT i.item_id, i.item_key, i.key_method, i.key_confidence, i.workload, l.location_subtype,
               l.site_url, l.mailbox_upn, l.team_name, l.channel_name, l.library_name, l.folder_path,
               l.repo_class, i.file_name, i.file_extension, i.title_or_subject, i.author, i.sender,
               i.created_utc, i.sent_utc, i.modified_utc, i.size_bytes, i.sensitivity_label,
               i.retention_label, i.index_status, i.is_unreadable, i.is_list_item,
               sg.n_keywords, sg.n_categories, sg.categories, sg.keywords,
               ROUND(sc.total_score,1) AS score, sc.band, sc.status_code,
               r.run_name AS first_search, sf.file_name AS source_csv
        FROM item i
        JOIN location l ON l.location_id = i.location_id
        LEFT JOIN v_item_signals sg ON sg.item_id = i.item_id
        LEFT JOIN score sc ON sc.scope_type='item' AND sc.scope_ref=CAST(i.item_id AS TEXT) AND sc.score_version=?
        LEFT JOIN search_run r ON r.search_run_id = i.first_seen_run
        LEFT JOIN (SELECT item_id, MIN(source_file_id) AS source_file_id FROM item_keyword_hit GROUP BY item_id) h
               ON h.item_id = i.item_id
        LEFT JOIN source_file sf ON sf.source_file_id = h.source_file_id
        ORDER BY sc.total_score DESC""", (v,))

    write_report(out, "02_keyword_item_links", conn, """
        SELECT h.item_id, k.keyword_text, k.category_code, k.specificity, r.run_name, r.search_date,
               sf.file_name AS source_csv, h.raw_row_id AS source_row, i.item_key, i.file_name,
               l.site_url, l.mailbox_upn
        FROM item_keyword_hit h
        JOIN keyword k ON k.keyword_id = h.keyword_id
        JOIN search_run r ON r.search_run_id = h.search_run_id
        JOIN item i ON i.item_id = h.item_id
        JOIN location l ON l.location_id = i.location_id
        LEFT JOIN source_file sf ON sf.source_file_id = h.source_file_id
        ORDER BY h.item_id""")

    for name, scope in (("03_sharepoint_sites", "site"), ("04_onedrive_accounts", "onedrive"),
                        ("05_mailboxes", "mailbox"), ("06_teams_channels", "team"),
                        ("03b_folders_and_libraries", "folder")):
        write_report(out, name, conn, LOC_RANK_SQL, (scope, v))

    write_report(out, "07_multi_signal", conn, """
        SELECT i.item_id, l.site_url, l.mailbox_upn, l.team_name, i.file_name, i.title_or_subject,
               sg.n_categories, sg.categories, sg.keywords, ROUND(sc.total_score,1) AS score, sc.status_code
        FROM item i
        JOIN location l ON l.location_id = i.location_id
        JOIN v_item_signals sg ON sg.item_id = i.item_id
        LEFT JOIN score sc ON sc.scope_type='item' AND sc.scope_ref=CAST(i.item_id AS TEXT) AND sc.score_version=?
        WHERE sg.n_categories >= 3
        ORDER BY sc.total_score DESC""", (v,))

    write_report(out, "08_procedural_deprioritised", conn, """
        SELECT l.site_url, l.mailbox_upn, l.repo_class, COUNT(*) AS items,
               GROUP_CONCAT(DISTINCT sc.status_code) AS statuses,
               'Deprioritised, not excluded. Reference material may still sit beside controlled data.' AS note
        FROM item i
        JOIN location l ON l.location_id = i.location_id
        JOIN score sc ON sc.scope_type='item' AND sc.scope_ref=CAST(i.item_id AS TEXT) AND sc.score_version=?
        WHERE sc.status_code IN ('procedural_or_reference','likely_false_positive')
        GROUP BY l.site_url, l.mailbox_upn, l.repo_class
        ORDER BY items DESC""", (v,))

    write_report(out, "09_unreadable_items", conn, """
        SELECT i.item_id, l.site_url, l.mailbox_upn, i.file_name, i.file_extension, i.size_bytes,
               i.index_status, i.key_method, i.key_confidence,
               'Cannot be assessed from metadata. Needs separate investigation.' AS reason
        FROM item i JOIN location l ON l.location_id = i.location_id
        WHERE i.is_unreadable = 1
        ORDER BY i.size_bytes DESC""")

    write_report(out, "10_business_review_pack", conn, """
        SELECT sc.band, ROUND(sc.total_score,1) AS score, sc.status_code,
               l.workload, l.site_url, l.mailbox_upn, l.team_name, l.channel_name,
               l.library_name, l.folder_path, l.repo_class,
               i.file_name, i.file_extension, i.created_utc, i.modified_utc, i.sensitivity_label,
               sg.categories AS indicator_classes, sg.n_keywords,
               (SELECT GROUP_CONCAT(f.factor_code || ': ' || f.factor_value || ' (' || f.points || ')', ' | ')
                  FROM score_factor f WHERE f.score_id = sc.score_id) AS reason_for_review
        FROM item i
        JOIN location l ON l.location_id = i.location_id
        JOIN score sc ON sc.scope_type='item' AND sc.scope_ref=CAST(i.item_id AS TEXT) AND sc.score_version=?
        LEFT JOIN v_item_signals sg ON sg.item_id = i.item_id
        WHERE sc.band IN ('high','critical')
        ORDER BY sc.total_score DESC""", (v,))

    write_report(out, "11_keyword_quality", conn, """
        SELECT k.keyword_text, k.category_code, k.specificity, k.status,
               COUNT(DISTINCT h.item_id) AS items,
               COUNT(DISTINCT i.location_id) AS locations,
               (SELECT COUNT(*) FROM (
                   SELECT h2.item_id FROM item_keyword_hit h2 WHERE h2.keyword_id = k.keyword_id
                   GROUP BY h2.item_id
                   HAVING (SELECT COUNT(DISTINCT h3.keyword_id) FROM item_keyword_hit h3
                             WHERE h3.item_id = h2.item_id) = 1)) AS unique_contribution,
               ROUND(100.0 * COUNT(DISTINCT CASE WHEN l.repo_class='policy' THEN h.item_id END)
                     / NULLIF(COUNT(DISTINCT h.item_id),0), 1) AS pct_in_policy_sites,
               CASE WHEN COUNT(DISTINCT h.item_id) = 0 THEN 'no hits, review or retire'
                    WHEN COUNT(DISTINCT i.location_id) = 1 THEN 'single location, very specific'
                    ELSE 'in use' END AS assessment
        FROM keyword k
        LEFT JOIN item_keyword_hit h ON h.keyword_id = k.keyword_id
        LEFT JOIN item i ON i.item_id = h.item_id
        LEFT JOIN location l ON l.location_id = i.location_id
        GROUP BY k.keyword_id ORDER BY items DESC""")

    write_report(out, "12_data_quality", conn, """
        SELECT issue_code, severity, scope_type, scope_ref, detail, detected_at
        FROM data_quality_issue ORDER BY
          CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, issue_code""")

    write_report(out, "12b_unmapped_columns", conn, """
        SELECT header, file_type, example_file,
               'Not recognised. Kept in raw_row. Add an alias in edisc.py if it matters.' AS note
        FROM unmapped_header ORDER BY file_type, header""")

    write_report(out, "13_provenance", conn, """
        SELECT r.run_name, r.search_date, r.query_text,
               (SELECT GROUP_CONCAT(k.keyword_text) FROM search_run_keyword sk
                  JOIN keyword k ON k.keyword_id = sk.keyword_id
                 WHERE sk.search_run_id = r.search_run_id) AS keywords,
               sf.file_name, sf.file_type, sf.row_count, sf.file_sha256, sf.ingested_at
        FROM search_run r LEFT JOIN source_file sf ON sf.search_run_id = r.search_run_id
        ORDER BY r.run_name, sf.file_type""")


def run_quality_checks(conn):
    n = conn.execute("SELECT COUNT(*) c FROM item WHERE key_confidence = 'low'").fetchone()["c"]
    if n:
        issue(conn, "LOW_CONFIDENCE_KEY", "medium", "item", "-",
              "%d items identified by fallback hash. Cross-run matching for these is weaker." % n)
    for r in conn.execute("""
        SELECT ls.location_id, ls.item_count AS stated,
               (SELECT COUNT(*) FROM item i WHERE i.location_id = ls.location_id) AS loaded,
               l.raw_location
        FROM location_stats ls JOIN location l ON l.location_id = ls.location_id"""):
        if r["stated"] and r["loaded"] and abs(r["stated"] - r["loaded"]) > max(5, r["stated"] * 0.2):
            issue(conn, "COUNT_VARIANCE", "medium", "location", r["raw_location"],
                  "Locations CSV states %d, items loaded %d. Expected causes: versions, list collapse, "
                  "unindexed items, content changed between estimate and export." % (r["stated"], r["loaded"]))
    n = conn.execute("SELECT COUNT(*) c FROM item WHERE item_id NOT IN "
                     "(SELECT item_id FROM item_keyword_hit)").fetchone()["c"]
    if n:
        issue(conn, "ITEM_WITHOUT_KEYWORD", "high", "item", "-",
              "%d items carry no keyword evidence. Usually a run with no keyword mapped." % n)
    n = conn.execute("SELECT COUNT(*) c FROM item WHERE is_unreadable = 1").fetchone()["c"]
    if n:
        issue(conn, "UNREADABLE_PRESENT", "high", "item", "-",
              "%d items are unreadable. Note that SharePoint and OneDrive partially indexed items are not "
              "counted in Purview statistics at all, so the true figure is higher." % n)
    conn.commit()


# --------------------------------------------------------------------------
# Dataverse export
# --------------------------------------------------------------------------
#
# Dataverse alternate keys must not contain / < > * % & : \ ? and every
# SharePoint URL contains several of those. So every key column written here
# is a hex hash. URLs are carried as ordinary text columns, never as keys.
#
# UpsertMultiple and dataflow upserts both fail when one payload contains two
# rows with the same key, so each file is deduplicated on its key before it is
# written.

DV_SCHEMA = [
    # table, column, type, length, required, is_alternate_key
    ("led_search", "led_searchkey", "Text", 64, "Yes", "Yes"),
    ("led_search", "led_name", "Text", 200, "Yes", "No"),
    ("led_search", "led_query", "Text", 4000, "No", "No"),
    ("led_search", "led_searchdate", "DateOnly", "", "No", "No"),
    ("led_search", "led_casename", "Text", 200, "No", "No"),

    ("led_keyword", "led_keywordkey", "Text", 64, "Yes", "Yes"),
    ("led_keyword", "led_name", "Text", 400, "Yes", "No"),
    ("led_keyword", "led_categorycode", "Text", 4, "Yes", "No"),
    ("led_keyword", "led_categoryname", "Text", 100, "No", "No"),
    ("led_keyword", "led_specificity", "WholeNumber", "", "No", "No"),
    ("led_keyword", "led_status", "Text", 50, "No", "No"),
    ("led_keyword", "led_owner", "Text", 100, "No", "No"),
    ("led_keyword", "led_note", "Text", 2000, "No", "No"),

    ("led_location", "led_locationkey", "Text", 64, "Yes", "Yes"),
    ("led_location", "led_name", "Text", 400, "Yes", "No"),
    ("led_location", "led_workload", "Choice", "", "No", "No"),
    ("led_location", "led_subtype", "Text", 60, "No", "No"),
    ("led_location", "led_siteurl", "Text", 1000, "No", "No"),
    ("led_location", "led_sitetitle", "Text", 400, "No", "No"),
    ("led_location", "led_library", "Text", 400, "No", "No"),
    ("led_location", "led_folderpath", "Text", 2000, "No", "No"),
    ("led_location", "led_folderdepth", "WholeNumber", "", "No", "No"),
    ("led_location", "led_mailbox", "Text", 320, "No", "No"),
    ("led_location", "led_team", "Text", 200, "No", "No"),
    ("led_location", "led_channel", "Text", 200, "No", "No"),
    ("led_location", "led_repoclass", "Choice", "", "No", "No"),

    ("led_locationscore", "led_locationscorekey", "Text", 64, "Yes", "Yes"),
    ("led_locationscore", "led_name", "Text", 400, "Yes", "No"),
    ("led_locationscore", "led_scopetype", "Choice", "", "Yes", "No"),
    ("led_locationscore", "led_score", "Decimal", "", "No", "No"),
    ("led_locationscore", "led_band", "Choice", "", "No", "No"),
    ("led_locationscore", "led_ptspeak", "Decimal", "", "No", "No"),
    ("led_locationscore", "led_ptsdiversity", "Decimal", "", "No", "No"),
    ("led_locationscore", "led_ptsdensity", "Decimal", "", "No", "No"),
    ("led_locationscore", "led_ptsbreadth", "Decimal", "", "No", "No"),
    ("led_locationscore", "led_indicatorclasses", "Text", 200, "No", "No"),
    ("led_locationscore", "led_rawmatches", "WholeNumber", "", "No", "No"),
    ("led_locationscore", "led_distinctdocuments", "WholeNumber", "", "No", "No"),
    ("led_locationscore", "led_unreadableitems", "WholeNumber", "", "No", "No"),
    ("led_locationscore", "led_modifiers", "Text", 1000, "No", "No"),

    ("led_item", "led_itemkey", "Text", 64, "Yes", "Yes"),
    ("led_item", "led_name", "Text", 400, "Yes", "No"),
    ("led_item", "led_locationkey", "Text", 64, "No", "No"),
    ("led_item", "led_workload", "Choice", "", "No", "No"),
    ("led_item", "led_siteurl", "Text", 1000, "No", "No"),
    ("led_item", "led_mailbox", "Text", 320, "No", "No"),
    ("led_item", "led_team", "Text", 200, "No", "No"),
    ("led_item", "led_channel", "Text", 200, "No", "No"),
    ("led_item", "led_library", "Text", 400, "No", "No"),
    ("led_item", "led_folderpath", "Text", 2000, "No", "No"),
    ("led_item", "led_repoclass", "Choice", "", "No", "No"),
    ("led_item", "led_filename", "Text", 400, "No", "No"),
    ("led_item", "led_fileextension", "Text", 30, "No", "No"),
    ("led_item", "led_subject", "Text", 1000, "No", "No"),
    ("led_item", "led_author", "Text", 200, "No", "No"),
    ("led_item", "led_sender", "Text", 320, "No", "No"),
    ("led_item", "led_createdon_source", "DateTime", "", "No", "No"),
    ("led_item", "led_modifiedon_source", "DateTime", "", "No", "No"),
    ("led_item", "led_sizebytes", "WholeNumber", "", "No", "No"),
    ("led_item", "led_sensitivitylabel", "Text", 200, "No", "No"),
    ("led_item", "led_retentionlabel", "Text", 200, "No", "No"),
    ("led_item", "led_indexstatus", "Text", 200, "No", "No"),
    ("led_item", "led_isunreadable", "YesNo", "", "No", "No"),
    ("led_item", "led_keycconfidence", "Choice", "", "No", "No"),
    ("led_item", "led_keywordcount", "WholeNumber", "", "No", "No"),
    ("led_item", "led_categorycount", "WholeNumber", "", "No", "No"),
    ("led_item", "led_categories", "Text", 100, "No", "No"),
    ("led_item", "led_keywords", "Text", 4000, "No", "No"),
    ("led_item", "led_score", "Decimal", "", "No", "No"),
    ("led_item", "led_band", "Choice", "", "No", "No"),
    ("led_item", "led_status", "Choice", "", "No", "No"),
    ("led_item", "led_reasonforreview", "Multiline", 4000, "No", "No"),

    ("led_hit", "led_hitkey", "Text", 64, "Yes", "Yes"),
    ("led_hit", "led_name", "Text", 400, "Yes", "No"),
    ("led_hit", "led_itemkey", "Text", 64, "Yes", "No"),
    ("led_hit", "led_keywordkey", "Text", 64, "Yes", "No"),
    ("led_hit", "led_searchkey", "Text", 64, "Yes", "No"),
    ("led_hit", "led_keywordtext", "Text", 400, "No", "No"),
    ("led_hit", "led_categorycode", "Text", 4, "No", "No"),
    ("led_hit", "led_siteurl", "Text", 1000, "No", "No"),
    ("led_hit", "led_mailbox", "Text", 320, "No", "No"),
    ("led_hit", "led_sourcecsv", "Text", 260, "No", "No"),
    ("led_hit", "led_sourcerow", "WholeNumber", "", "No", "No"),

    ("led_scorefactor", "led_scorefactorkey", "Text", 64, "Yes", "Yes"),
    ("led_scorefactor", "led_name", "Text", 200, "Yes", "No"),
    ("led_scorefactor", "led_itemkey", "Text", 64, "Yes", "No"),
    ("led_scorefactor", "led_factorcode", "Text", 10, "Yes", "No"),
    ("led_scorefactor", "led_factorvalue", "Text", 400, "No", "No"),
    ("led_scorefactor", "led_points", "Decimal", "", "No", "No"),
    ("led_scorefactor", "led_explanation", "Text", 400, "No", "No"),

    ("led_dataqualityissue", "led_issuekey", "Text", 64, "Yes", "Yes"),
    ("led_dataqualityissue", "led_name", "Text", 200, "Yes", "No"),
    ("led_dataqualityissue", "led_issuecode", "Text", 60, "Yes", "No"),
    ("led_dataqualityissue", "led_severity", "Choice", "", "No", "No"),
    ("led_dataqualityissue", "led_detail", "Multiline", 4000, "No", "No"),
]

# Tables a reviewer fills in. Created empty in Dataverse, never loaded from the
# analysis, because the whole point is that people write to them.
DV_REVIEW_TABLES = """
led_reviewtask   - one per location or item sent for business review
                   led_taskkey (alt key), led_scopetype, led_scopekey, led_assignedto (user
                   lookup), led_duedate, led_state, led_priority
led_reviewverdict- what the reviewer decided
                   led_verdictkey (alt key), led_taskkey, led_verdict (choice: confirmed ITAR,
                   not ITAR, needs specialist, cannot determine), led_reviewer, led_reviewedon,
                   led_rationale, led_evidencenote
led_remediation  - what was agreed, subject to authorisation
                   led_actionkey (alt key), led_scopekey, led_proposedaction, led_approvedby,
                   led_approvedon, led_state
"""


def clip(value, n):
    if value is None:
        return ""
    s = str(value)
    return s if len(s) <= n else s[: n - 1] + "\u2026"


def dv_write(out_dir, name, header, rows, key_index=0):
    """Write one Dataverse-ready CSV, deduplicated on its key column."""
    path = Path(out_dir) / ("%s.csv" % name)
    seen, written, dropped = set(), 0, 0
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(header)
        for row in rows:
            k = row[key_index]
            if not k or k in seen:
                dropped += 1
                continue
            seen.add(k)
            wr.writerow(row)
            written += 1
    note = "  (%d duplicate keys removed)" % dropped if dropped else ""
    print("  %-22s %6d rows -> %s%s" % (name, written, path.name, note))
    return written


def export_dataverse(conn, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    v = SCORE_VERSION

    dv_write(out, "led_search", ["led_searchkey", "led_name", "led_query", "led_searchdate", "led_casename"],
             [(sha1s("search", r["run_name"]), clip(r["run_name"], 200), clip(r["query_text"], 4000),
               (r["search_date"] or "")[:10], clip(r["case_name"], 200))
              for r in conn.execute("SELECT * FROM search_run")])

    dv_write(out, "led_keyword",
             ["led_keywordkey", "led_name", "led_categorycode", "led_categoryname", "led_specificity",
              "led_status", "led_owner", "led_note"],
             [(sha1s("kw", r["keyword_text"]), clip(r["keyword_text"], 400), r["category_code"] or "",
               clip(r["category_name"], 100), r["specificity"] or 0, clip(r["status"], 50),
               clip(r["owner"], 100), clip(r["guidance_note"], 2000))
              for r in conn.execute("SELECT k.*, c.category_name FROM keyword k "
                                    "LEFT JOIN keyword_category c ON c.category_code = k.category_code")])

    dv_write(out, "led_location",
             ["led_locationkey", "led_name", "led_workload", "led_subtype", "led_siteurl", "led_sitetitle",
              "led_library", "led_folderpath", "led_folderdepth", "led_mailbox", "led_team", "led_channel",
              "led_repoclass"],
             [(r["location_key"], clip(r["raw_location"] or r["site_url"] or r["mailbox_upn"] or "unknown", 400),
               r["workload"] or "", clip(r["location_subtype"], 60), clip(r["site_url"], 1000),
               clip(r["site_title"], 400), clip(r["library_name"], 400), clip(r["folder_path"], 2000),
               r["folder_depth"] or 0, clip(r["mailbox_upn"], 320), clip(r["team_name"], 200),
               clip(r["channel_name"], 200), r["repo_class"] or "")
              for r in conn.execute("SELECT * FROM location")])

    loc_rows = []
    for r in conn.execute("""
        SELECT s.score_id, s.scope_type, s.scope_ref, s.total_score, s.band,
               (SELECT points FROM score_factor f WHERE f.score_id=s.score_id AND f.factor_code='L01') AS p1,
               (SELECT points FROM score_factor f WHERE f.score_id=s.score_id AND f.factor_code='L02') AS p2,
               (SELECT points FROM score_factor f WHERE f.score_id=s.score_id AND f.factor_code='L03') AS p3,
               (SELECT points FROM score_factor f WHERE f.score_id=s.score_id AND f.factor_code='L04') AS p4,
               (SELECT factor_value FROM score_factor f WHERE f.score_id=s.score_id AND f.factor_code='L02') AS cls,
               (SELECT factor_value FROM score_factor f WHERE f.score_id=s.score_id AND f.factor_code='C01') AS raw,
               (SELECT factor_value FROM score_factor f WHERE f.score_id=s.score_id AND f.factor_code='C02') AS docs,
               (SELECT factor_value FROM score_factor f WHERE f.score_id=s.score_id AND f.factor_code='C03') AS unread,
               (SELECT GROUP_CONCAT(factor_value || ' (' || points || ')', ' | ') FROM score_factor f
                  WHERE f.score_id=s.score_id AND f.factor_code IN ('L05','L06','L07')) AS mods
        FROM score s WHERE s.scope_type <> 'item' AND s.score_version = ?""", (v,)):
        loc_rows.append((sha1s("locscore", r["scope_type"], r["scope_ref"]),
                         clip(r["scope_ref"], 400), r["scope_type"], round(r["total_score"], 2), r["band"],
                         round(r["p1"] or 0, 2), round(r["p2"] or 0, 2), round(r["p3"] or 0, 2),
                         round(r["p4"] or 0, 2), clip(r["cls"], 200), parse_int(r["raw"]) or 0,
                         parse_int(r["docs"]) or 0, parse_int(r["unread"]) or 0, clip(r["mods"], 1000)))
    dv_write(out, "led_locationscore",
             ["led_locationscorekey", "led_name", "led_scopetype", "led_score", "led_band", "led_ptspeak",
              "led_ptsdiversity", "led_ptsdensity", "led_ptsbreadth", "led_indicatorclasses", "led_rawmatches",
              "led_distinctdocuments", "led_unreadableitems", "led_modifiers"], loc_rows)

    item_rows = []
    for r in conn.execute("""
        SELECT i.*, l.location_key, l.site_url, l.mailbox_upn, l.team_name, l.channel_name,
               l.library_name, l.folder_path, l.repo_class,
               sg.n_keywords, sg.n_categories, sg.categories, sg.keywords,
               sc.total_score, sc.band, sc.status_code, sc.score_id
        FROM item i
        JOIN location l ON l.location_id = i.location_id
        LEFT JOIN v_item_signals sg ON sg.item_id = i.item_id
        LEFT JOIN score sc ON sc.scope_type='item' AND sc.scope_ref=CAST(i.item_id AS TEXT) AND sc.score_version=?""",
        (v,)):
        reason = conn.execute(
            "SELECT GROUP_CONCAT(factor_code || ': ' || factor_value || ' (' || points || ')', ' | ') AS r "
            "FROM score_factor WHERE score_id = ?", (r["score_id"],)).fetchone()["r"] if r["score_id"] else ""
        item_rows.append((
            r["item_key"], clip(r["file_name"] or r["title_or_subject"] or r["item_key"], 400),
            r["location_key"], r["workload"] or "", clip(r["site_url"], 1000), clip(r["mailbox_upn"], 320),
            clip(r["team_name"], 200), clip(r["channel_name"], 200), clip(r["library_name"], 400),
            clip(r["folder_path"], 2000), r["repo_class"] or "", clip(r["file_name"], 400),
            clip(r["file_extension"], 30), clip(r["title_or_subject"], 1000), clip(r["author"], 200),
            clip(r["sender"], 320), r["created_utc"] or "", r["modified_utc"] or "", r["size_bytes"] or 0,
            clip(r["sensitivity_label"], 200), clip(r["retention_label"], 200), clip(r["index_status"], 200),
            "true" if r["is_unreadable"] else "false", r["key_confidence"] or "",
            r["n_keywords"] or 0, r["n_categories"] or 0, clip(r["categories"], 100), clip(r["keywords"], 4000),
            round(r["total_score"] or 0, 2), r["band"] or "", r["status_code"] or "", clip(reason, 4000)))
    dv_write(out, "led_item",
             ["led_itemkey", "led_name", "led_locationkey", "led_workload", "led_siteurl", "led_mailbox",
              "led_team", "led_channel", "led_library", "led_folderpath", "led_repoclass", "led_filename",
              "led_fileextension", "led_subject", "led_author", "led_sender", "led_createdon_source",
              "led_modifiedon_source", "led_sizebytes", "led_sensitivitylabel", "led_retentionlabel",
              "led_indexstatus", "led_isunreadable", "led_keycconfidence", "led_keywordcount",
              "led_categorycount", "led_categories", "led_keywords", "led_score", "led_band", "led_status",
              "led_reasonforreview"], item_rows)

    hit_rows = []
    for r in conn.execute("""
        SELECT i.item_key, k.keyword_text, k.category_code, sr.run_name, l.site_url, l.mailbox_upn,
               sf.file_name AS source_csv, h.raw_row_id
        FROM item_keyword_hit h
        JOIN item i ON i.item_id = h.item_id
        JOIN keyword k ON k.keyword_id = h.keyword_id
        JOIN search_run sr ON sr.search_run_id = h.search_run_id
        JOIN location l ON l.location_id = i.location_id
        LEFT JOIN source_file sf ON sf.source_file_id = h.source_file_id"""):
        kk, sk = sha1s("kw", r["keyword_text"]), sha1s("search", r["run_name"])
        hit_rows.append((sha1s("hit", r["item_key"], kk, sk),
                         clip("%s / %s" % (r["keyword_text"], r["run_name"]), 400),
                         r["item_key"], kk, sk, clip(r["keyword_text"], 400), r["category_code"] or "",
                         clip(r["site_url"], 1000), clip(r["mailbox_upn"], 320),
                         clip(r["source_csv"], 260), r["raw_row_id"] or 0))
    dv_write(out, "led_hit",
             ["led_hitkey", "led_name", "led_itemkey", "led_keywordkey", "led_searchkey", "led_keywordtext",
              "led_categorycode", "led_siteurl", "led_mailbox", "led_sourcecsv", "led_sourcerow"], hit_rows)

    fac_rows = []
    for r in conn.execute("""
        SELECT i.item_key, f.factor_code, f.factor_value, f.points, f.note
        FROM score_factor f JOIN score s ON s.score_id = f.score_id
        JOIN item i ON CAST(i.item_id AS TEXT) = s.scope_ref
        WHERE s.scope_type = 'item' AND s.score_version = ?""", (v,)):
        fac_rows.append((sha1s("fac", r["item_key"], r["factor_code"], r["factor_value"]),
                         clip("%s %s" % (r["factor_code"], r["factor_value"]), 200), r["item_key"],
                         r["factor_code"], clip(r["factor_value"], 400), r["points"], clip(r["note"], 400)))
    dv_write(out, "led_scorefactor",
             ["led_scorefactorkey", "led_name", "led_itemkey", "led_factorcode", "led_factorvalue",
              "led_points", "led_explanation"], fac_rows)

    dv_write(out, "led_dataqualityissue",
             ["led_issuekey", "led_name", "led_issuecode", "led_severity", "led_detail"],
             [(sha1s("dq", r["issue_code"], r["scope_ref"], r["detail"]),
               clip("%s %s" % (r["issue_code"], r["scope_ref"]), 200), r["issue_code"],
               r["severity"], clip(r["detail"], 4000))
              for r in conn.execute("SELECT * FROM data_quality_issue")])

    with open(out / "_dataverse_schema.csv", "w", encoding="utf-8-sig", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["table", "column", "type", "max_length", "required", "alternate_key"])
        for row in DV_SCHEMA:
            wr.writerow(row)
    print("  %-22s %6d rows -> _dataverse_schema.csv" % ("(table definitions)", len(DV_SCHEMA)))

    with open(out / "_review_tables.txt", "w", encoding="utf-8") as fh:
        fh.write("Tables to create empty in Dataverse. Reviewers write to these, the loader never does.\n")
        fh.write(DV_REVIEW_TABLES)

    print("\nEvery key column is a hex hash, because Dataverse alternate keys reject / : ? & and")
    print("every SharePoint URL contains them. URLs are carried as ordinary text columns.")


def cmd_dataverse(args):
    conn = connect(args.db)
    print("Dataverse export")
    export_dataverse(conn, args.out)
    print("\nFiles written to: %s" % args.out)


# --------------------------------------------------------------------------
# inspect and selftest
# --------------------------------------------------------------------------

def cmd_inspect(args):
    root = Path(args.exports)
    files = sorted(p for p in root.rglob("*.csv") if p.is_file())
    if not files:
        print("No CSV files found under %s" % root)
        return
    print("Found %d CSV files under %s\n" % (len(files), root))
    unmapped = {}
    for p in files:
        headers = sniff_headers(p)
        ftype = detect_file_type(p, headers)
        lookup = {"items": ITEM_LOOKUP, "locations": LOCATION_LOOKUP}.get(ftype, SUMMARY_LOOKUP)
        known = [h for h in headers if nkey(h) in lookup]
        unk = [h for h in headers if nkey(h) not in lookup]
        print("%-50s %-10s  %d columns, %d recognised" % (str(p.relative_to(root)), ftype, len(headers), len(known)))
        for h in unk:
            unmapped.setdefault(h, ftype)
    if unmapped:
        print("\nColumns not recognised (kept in the database as raw JSON either way):")
        for h, ft in sorted(unmapped.items()):
            print("  [%s] %s" % (ft, h))
        print("\nIf any of these matter, add the name to the alias lists near the top of edisc.py.")
    else:
        print("\nEvery column was recognised.")


SAMPLE_ITEM_HEADERS = ["Item ID", "Workload", "Location", "Document Link", "File Name", "Subject",
                       "File Extension", "Author", "Sender", "To", "Created Time", "Sent",
                       "Last Modified Time", "Size", "Sensitivity Label", "Indexing Status",
                       "Internet Message Id", "Team Name", "Channel Name"]


def make_sample(root):
    """Synthetic data only. Invented sites, invented names. Used to prove the pipeline runs."""
    root = Path(root)
    runs = [
        ("search_itar_phrase", "International Traffic in Arms Regulations"),
        ("search_export_controlled", "Export Controlled"),
        ("search_dwg_sweep", "FileExtension:dwg"),
    ]
    sp = "https://contoso.sharepoint.com/sites"
    od = "https://contoso-my.sharepoint.com/personal"
    rows_by_run = {
        "search_itar_phrase": [
            ("SP1", "SharePoint", sp + "/Policy-BMS", sp + "/Policy-BMS/Shared Documents/Compliance/ITAR Awareness Briefing.pptx",
             "ITAR Awareness Briefing.pptx", "", "pptx", "A Trainer", "", "", "2021-02-03", "", "2021-02-03", "204800", "Internal", "Indexed", "", "", ""),
            ("SP2", "SharePoint", sp + "/Policy-BMS", sp + "/Policy-BMS/Shared Documents/Compliance/Export Control Policy.docx",
             "Export Control Policy.docx", "", "docx", "A Trainer", "", "", "2020-06-01", "", "2023-01-09", "88000", "Internal", "Indexed", "", "", ""),
            ("SP3", "SharePoint", sp + "/Eng-ProjectFalcon", sp + "/Eng-ProjectFalcon/Shared Documents/Drawings/FAL-10422 Assembly.dwg",
             "FAL-10422 Assembly.dwg", "", "dwg", "J Engineer", "", "", "2024-03-11", "", "2025-07-02", "4400000", "", "Indexed", "", "", ""),
            ("EX1", "Exchange", "j.engineer@contoso.com", "", "", "RE: FAL-10422 export licence question", "msg",
             "", "j.engineer@contoso.com", "trade.compliance@contoso.com;partner@overseas-corp.com",
             "2025-06-30", "2025-06-30", "2025-06-30", "34000", "", "Indexed", "<msg-001@contoso.com>", "", ""),
            ("OD1", "OneDrive", od + "/j_engineer_contoso_com", od + "/j_engineer_contoso_com/Documents/Working/FAL-10422 stress notes.xlsx",
             "FAL-10422 stress notes.xlsx", "", "xlsx", "J Engineer", "", "", "2025-05-02", "", "2025-05-02", "120000", "", "Indexed", "", "", ""),
            ("TM1", "Teams", sp + "/Eng-ProjectFalcon", "", "", "Falcon drawing pack shared with supplier", "msg",
             "", "j.engineer@contoso.com", "team@contoso.com", "2025-04-04", "2025-04-04", "2025-04-04", "2000", "", "Indexed",
             "<msg-002@contoso.com>", "Project Falcon", "Design Private"),
        ],
        "search_export_controlled": [
            ("SP3", "SharePoint", sp + "/Eng-ProjectFalcon", sp + "/Eng-ProjectFalcon/Shared Documents/Drawings/FAL-10422 Assembly.dwg",
             "FAL-10422 Assembly.dwg", "", "dwg", "J Engineer", "", "", "2024-03-11", "", "2025-07-02", "4400000", "", "Indexed", "", "", ""),
            ("SP4", "SharePoint", sp + "/Eng-ProjectFalcon", sp + "/Eng-ProjectFalcon/Shared Documents/Drawings/EXPORT CONTROLLED FAL-10500 ICD.pdf",
             "EXPORT CONTROLLED FAL-10500 ICD.pdf", "", "pdf", "J Engineer", "", "", "2025-01-15", "", "2025-06-01", "900000", "", "Indexed", "", "", ""),
            ("SP2", "SharePoint", sp + "/Policy-BMS", sp + "/Policy-BMS/Shared Documents/Compliance/Export Control Policy.docx",
             "Export Control Policy.docx", "", "docx", "A Trainer", "", "", "2020-06-01", "", "2023-01-09", "88000", "Internal", "Indexed", "", "", ""),
            ("SP9", "SharePoint", sp + "/Bid-Skylark", sp + "/Bid-Skylark/Shared Documents/Contracts/SKY-2291 TAA draft.docx",
             "SKY-2291 TAA draft.docx", "", "docx", "C Manager", "", "", "2025-02-02", "", "2025-02-20", "150000", "", "Indexed", "", "", ""),
        ],
        "search_dwg_sweep": [
            ("SP3", "SharePoint", sp + "/Eng-ProjectFalcon", sp + "/Eng-ProjectFalcon/Shared Documents/Drawings/FAL-10422 Assembly.dwg",
             "FAL-10422 Assembly.dwg", "", "dwg", "J Engineer", "", "", "2024-03-11", "", "2025-07-02", "4400000", "", "Indexed", "", "", ""),
            ("SP5", "SharePoint", sp + "/Eng-Hangar7", sp + "/Eng-Hangar7/Shared Documents/CAD/H7-3301 wing rib.dwg",
             "H7-3301 wing rib.dwg", "", "dwg", "K Designer", "", "", "2023-09-01", "", "2025-03-03", "7100000", "", "Partially indexed", "", "", ""),
            ("SP6", "SharePoint", sp + "/Eng-Hangar7", sp + "/Eng-Hangar7/Shared Documents/CAD/H7-3302 spar.catpart",
             "H7-3302 spar.catpart", "", "catpart", "K Designer", "", "", "2023-09-02", "", "2025-03-04", "9900000", "", "Unsupported file type", "", "", ""),
        ],
    }
    for run_name, query in runs:
        d = root / run_name
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "Items.csv", "w", encoding="utf-8-sig", newline="") as fh:
            wr = csv.writer(fh)
            wr.writerow(SAMPLE_ITEM_HEADERS)
            for r in rows_by_run[run_name]:
                wr.writerow(r)
        locs = {}
        for r in rows_by_run[run_name]:
            key = r[2]
            locs[key] = locs.get(key, 0) + 1
        with open(d / "Locations.csv", "w", encoding="utf-8-sig", newline="") as fh:
            wr = csv.writer(fh)
            wr.writerow(["Location", "Location Subtype", "Count", "Size"])
            for k, c in locs.items():
                sub = "OneDriveSite" if "/personal/" in k else ("PrimaryMailbox" if "@" in k else "SharePointSite")
                wr.writerow([k, sub, c, c * 100000])
        with open(d / "Summary.csv", "w", encoding="utf-8-sig", newline="") as fh:
            wr = csv.writer(fh)
            wr.writerow(["Search Name", "Query", "Date", "Items"])
            wr.writerow([run_name, query, "2026-09-01", len(rows_by_run[run_name])])
        with open(d / "Settings.csv", "w", encoding="utf-8-sig", newline="") as fh:
            wr = csv.writer(fh)
            wr.writerow(["Setting", "Value"])
            wr.writerow(["Export type", "Reports only (metadata)"])
            wr.writerow(["Include unindexed", "Yes"])

    with open(root / "keywords.csv", "w", encoding="utf-8-sig", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["run_name", "keyword", "category", "specificity", "owner", "note"])
        wr.writerow(["search_itar_phrase", "International Traffic in Arms Regulations", "A", 3, "Trade Compliance", "seed term"])
        wr.writerow(["search_export_controlled", "Export Controlled", "B", 3, "Trade Compliance", "handling marking"])
        wr.writerow(["search_dwg_sweep", "FileExtension:dwg", "X", 3, "Analyst", "file type sweep, no keyword"])
    return root / "keywords.csv"


def cmd_selftest(args):
    tmp = Path(tempfile.mkdtemp(prefix="edisc_selftest_"))
    try:
        exports = tmp / "exports"
        kw = make_sample(exports)
        db = tmp / "test.db"
        conn = connect(str(db))
        config = load_config(None)
        config["internal_domains"] = ["contoso.com"]
        load_keywords(conn, kw)
        ingest_export_folder(conn, exports, kw, config)
        run_quality_checks(conn)
        print("\nScoring")
        score_items(conn, config)
        score_locations(conn, config)
        out = tmp / "reports"
        print("\nReports")
        build_reports(conn, out, config)

        items = conn.execute("SELECT COUNT(*) c FROM item").fetchone()["c"]
        hits = conn.execute("SELECT COUNT(*) c FROM item_keyword_hit").fetchone()["c"]
        assert items > 0, "no items loaded"
        assert hits >= items, "hits should be at least one per item"
        dup = conn.execute("SELECT COUNT(*) c FROM item i JOIN item_keyword_hit h ON h.item_id=i.item_id "
                           "WHERE i.file_name='FAL-10422 Assembly.dwg'").fetchone()["c"]
        assert dup >= 3, "the file matched by three searches should carry three hits, got %d" % dup
        one = conn.execute("SELECT COUNT(*) c FROM item WHERE file_name='FAL-10422 Assembly.dwg'").fetchone()["c"]
        assert one == 1, "that file should be ONE item, got %d" % one

        ranked = conn.execute("SELECT scope_ref, total_score FROM score WHERE scope_type='site' "
                              "AND score_version=? ORDER BY total_score DESC", (SCORE_VERSION,)).fetchall()
        print("\nSite ranking from the synthetic data:")
        for r in ranked:
            print("  %8.1f  %s" % (r["total_score"], r["scope_ref"]))
        top = ranked[0]["scope_ref"]
        policy = [r for r in ranked if "Policy-BMS" in r["scope_ref"]]
        assert "Eng-" in top, "an engineering site should rank top, got %s" % top
        assert policy and policy[0]["total_score"] < ranked[0]["total_score"], "policy site must not lead"

        unread = conn.execute("SELECT COUNT(*) c FROM item WHERE is_unreadable=1").fetchone()["c"]
        assert unread >= 2, "unreadable items should be detected, got %d" % unread

        dv = tmp / "dataverse"
        print("\nDataverse export")
        export_dataverse(conn, dv)
        bad = re.compile(r"[/<>*%&:\\?]")
        for f in sorted(dv.glob("led_*.csv")):
            with open(f, encoding="utf-8-sig", newline="") as fh:
                rdr = csv.reader(fh)
                header = next(rdr)
                keycols = [i for i, h in enumerate(header) if h.endswith("key")]
                seen = set()
                for row in rdr:
                    k = row[0]
                    assert k not in seen, "%s has a duplicate key, upsert would fail" % f.name
                    seen.add(k)
                    for i in keycols:
                        assert not bad.search(row[i]), \
                            "%s column %s holds a character Dataverse keys reject: %r" % (f.name, header[i], row[i])
        assert (dv / "_dataverse_schema.csv").exists(), "table definitions not written"

        print("\nSELFTEST PASSED")
        print("  items: %d   keyword hits: %d   unreadable: %d" % (items, hits, unread))
        if args.keep:
            print("  files kept at: %s" % tmp)
            return
    finally:
        if not args.keep:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------

def cmd_load(args):
    conn = connect(args.db)
    config = load_config(args.config)
    load_keywords(conn, args.keywords)
    ingest_export_folder(conn, args.exports, args.keywords, config)
    run_quality_checks(conn)
    print("\nDatabase written: %s" % args.db)


def cmd_score(args):
    conn = connect(args.db)
    config = load_config(args.config)
    print("Scoring")
    score_items(conn, config)
    score_locations(conn, config)


def cmd_report(args):
    conn = connect(args.db)
    config = load_config(args.config)
    print("Reports")
    build_reports(conn, args.out, config)
    print("\nAll reports written to: %s" % args.out)


def cmd_all(args):
    cmd_load(args)
    cmd_score(args)
    cmd_report(args)
    if getattr(args, "dataverse_out", None):
        conn = connect(args.db)
        print("\nDataverse export")
        export_dataverse(conn, args.dataverse_out)


def main():
    ap = argparse.ArgumentParser(description="Load Purview eDiscovery metadata exports into SQLite and analyse them.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("inspect", help="list the CSVs found and which columns are recognised")
    p.add_argument("--exports", required=True)
    p.set_defaults(func=cmd_inspect)

    for name, fn, needs_out in (("load", cmd_load, False), ("all", cmd_all, True)):
        p = sub.add_parser(name)
        p.add_argument("--db", required=True)
        p.add_argument("--exports", required=True)
        p.add_argument("--keywords", default="keywords.csv")
        p.add_argument("--config", default="config.json")
        if needs_out:
            p.add_argument("--out", default="reports")
            p.add_argument("--dataverse-out", dest="dataverse_out", default=None,
                           help="also write Dataverse-ready CSVs to this folder")
        p.set_defaults(func=fn)

    p = sub.add_parser("score")
    p.add_argument("--db", required=True)
    p.add_argument("--config", default="config.json")
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("report")
    p.add_argument("--db", required=True)
    p.add_argument("--out", default="reports")
    p.add_argument("--config", default="config.json")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("dataverse", help="write Dataverse-ready CSVs and the table definitions")
    p.add_argument("--db", required=True)
    p.add_argument("--out", default="dataverse")
    p.set_defaults(func=cmd_dataverse)

    p = sub.add_parser("selftest", help="run the whole pipeline on invented data and check the result")
    p.add_argument("--keep", action="store_true")
    p.set_defaults(func=cmd_selftest)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
