# ITAR eDiscovery Metadata Analysis: Proposed Method

**Purpose.** Turn many single-keyword Microsoft Purview eDiscovery exports into one queryable store, and from it produce a ranked, evidence-backed view of the SharePoint sites, OneDrive accounts, mailboxes and Teams that most likely hold ITAR-controlled technical data.

**Status.** Proposal for review. No code written yet. Nothing here is a Trade Compliance or legal determination.

**Scope rule carried through the whole design.** Metadata only. No extracted text, no content reconstruction, no inference about what a document says beyond the fields Purview exports. Email sender, recipient and subject fields are treated as sensitive project data at every stage, including in reports.

---

## 0. The core problem in one paragraph

Each keyword is searched separately, so the same item appears once per keyword it matches. Raw hit counts are therefore both inflated and misleading: a corporate policy library will out-score a small engineering project site every time. The method below fixes this by separating **identity** (one canonical record per item instance) from **evidence** (every keyword match preserved as a link), and by scoring locations on the *variety and strength* of independent signals rather than on volume.

---

## 1. Target SQLite data model

### 1.1 Design principles

1. **Land raw, then normalise.** Every CSV row is stored verbatim as JSON before any interpretation. Nothing is lost when Purview changes a column name.
2. **One canonical record per item instance per location.** The same file copied into three sites is three records, because the deliverable is *which sites to isolate*. A separate content group ID links the copies.
3. **Evidence is never collapsed.** The item-to-keyword link table keeps every match, with its search, its CSV file and its original row.
4. **Every score is itemised.** No score exists without a set of factor rows explaining it.
5. **Additive by design.** A new search inserts; it never rewrites history.

### 1.2 Tables

**Provenance and control**

| Table | Purpose | Key columns |
|---|---|---|
| `search_run` | One Purview search and export | `search_run_id`, `search_name`, `case_name`, `query_text`, `search_date`, `export_date`, `scope_note`, `settings_json`, `ingested_at` |
| `source_file` | One CSV file ingested | `source_file_id`, `search_run_id`, `file_name`, `file_type` (items/locations/summary/settings/derived), `file_sha256`, `row_count`, `header_signature`, `ingested_at` |
| `raw_item_row` | Verbatim landing rows | `raw_row_id`, `source_file_id`, `row_number`, `raw_json`, `load_status` |
| `column_map` | Source header to canonical field, with aliases | `source_header`, `file_type`, `canonical_field`, `first_seen_run`, `notes` |
| `ingest_log` | Audit of every load attempt | `ingest_id`, `source_file_id`, `started_at`, `finished_at`, `rows_in`, `rows_loaded`, `rows_rejected`, `status`, `message` |
| `schema_version` | Migration tracking | `version`, `applied_at`, `script_name` |

**Keywords and taxonomy**

| Table | Purpose | Key columns |
|---|---|---|
| `keyword_category` | Indicator classes (section 3) | `category_id`, `category_code`, `category_name`, `default_weight`, `is_negative` |
| `keyword` | One canonical term or phrase | `keyword_id`, `keyword_text`, `normalised_text`, `category_id`, `specificity` (1 to 3), `status` (candidate/approved/retired), `owner`, `guidance_note`, `active_from`, `active_to` |
| `keyword_alias` | Spelling and abbreviation variants mapped to one keyword | `alias_id`, `keyword_id`, `alias_text` |
| `search_run_keyword` | Which keyword(s) a run represents | `search_run_id`, `keyword_id`, `is_primary` |

**Items, locations, evidence**

| Table | Purpose | Key columns |
|---|---|---|
| `location` | Canonical container | `location_id`, `location_key` (hash), `workload`, `site_url`, `site_title`, `library_name`, `folder_path`, `folder_depth`, `mailbox_upn`, `mailbox_type`, `team_name`, `channel_name`, `owner_upn`, `repo_class`, `is_known_itar_repo`, `external_sharing_flag` |
| `item` | One canonical item instance | `item_id`, `item_key` (hash), `content_group_id`, `location_id`, `workload`, `source_item_id`, `family_id`, `conversation_id`, `file_name`, `file_extension`, `title_or_subject`, `author`, `created_utc`, `sent_utc`, `modified_utc`, `size_bytes`, `word_count`, `extracted_text_len`, `sensitivity_label`, `retention_label`, `has_attachments`, `index_status`, `is_encrypted`, `is_unsupported`, `version_id`, `first_seen_run`, `last_seen_run` |
| `item_participant` | People, one row each, not a comma blob | `item_id`, `role` (author/sender/to/cc/bcc/modifier/participant), `party_address`, `party_display`, `party_domain`, `is_internal` |
| `item_keyword_hit` | The evidence link table | `item_id`, `keyword_id`, `search_run_id`, `source_file_id`, `raw_row_id`, `matched_field_hint`, `first_seen_at` (PK: item, keyword, run) |
| `location_stats` | Counts straight from the Locations CSV | `search_run_id`, `keyword_id`, `location_id`, `item_count`, `total_size_bytes`, `partially_indexed_count` |
| `search_summary` | Figures straight from the Summary CSV | `search_run_id`, `indexed_items`, `unindexed_items`, `total_size_bytes`, `locations_searched` |

**Analysis layer**

| Table | Purpose | Key columns |
|---|---|---|
| `scoring_rule` | Versioned factor definitions and weights | `rule_id`, `score_version`, `factor_code`, `description`, `weight`, `cap`, `applies_to` (item/location) |
| `score` | One score per scope per version | `score_id`, `scope_type` (item/folder/library/site/onedrive/mailbox/team/channel/cluster), `scope_id`, `score_version`, `total_score`, `band`, `status_code`, `computed_at` |
| `score_factor` | Why the score is what it is | `score_id`, `factor_code`, `factor_value`, `weight`, `points`, `evidence_ref` |
| `analytical_status` | The six triage categories | `status_code`, `status_name`, `description` |
| `cluster` / `item_cluster` | Programme, project, contract and path clusters | `cluster_id`, `cluster_type`, `cluster_label`, `derivation_note` |
| `reference_programme` | Authorised list of known ITAR programmes, contracts and approved repositories | `ref_id`, `ref_type`, `ref_value`, `source`, `authorised_by`, `valid_from` |
| `review_verdict` | Feedback from authorised reviewers | `verdict_id`, `scope_type`, `scope_id`, `verdict`, `reviewer_role`, `reviewed_at`, `note` |
| `data_quality_issue` | Every anomaly found | `issue_id`, `issue_code`, `severity`, `scope_type`, `scope_id`, `source_file_id`, `detail`, `detected_at` |
| `report_snapshot` | Frozen report outputs, so any past position is reproducible | `snapshot_id`, `report_code`, `score_version`, `run_at`, `row_count`, `file_path` |

**Views** (read-only convenience, rebuilt cheaply): `v_item_full`, `v_item_signals`, `v_site_rollup`, `v_onedrive_rollup`, `v_mailbox_rollup`, `v_team_rollup`, `v_multi_signal`, `v_keyword_quality`, `v_unreadable_queue`.

**Indexes**: unique on `item.item_key`, `location.location_key`, `source_file.file_sha256`; plus `item(location_id)`, `item_keyword_hit(keyword_id)`, `item_keyword_hit(item_id)`, `item(content_group_id)`, `location(site_url)`, `score(scope_type, scope_id, score_version)`. SQLite in WAL mode handles this volume comfortably.

### 1.3 The two different kinds of "duplicate"

This distinction matters and is easy to get wrong:

- **`item_key`** identifies *one copy in one place*. Two copies of the same drawing in two sites are two items, because both sites may need isolating.
- **`content_group_id`** identifies *the same content wherever it lives*. It answers "how far has this spread" and "is this a widely circulated policy PDF rather than a controlled drawing".

Both are needed. Collapsing them would destroy the site-level answer the exercise is for.

---

## 2. Ingestion and deduplication approach

### 2.1 Pipeline stages

1. **Discover.** Walk the export folder tree. One folder per search run by convention; the run is registered from the Settings and Summary CSVs.
2. **Fingerprint.** SHA-256 each file. A file already loaded with the same hash is skipped, so re-running the loader is always safe.
3. **Classify.** Identify file type from its header signature, not its filename, since export naming varies.
4. **Land.** Insert every row verbatim into `raw_item_row` as JSON.
5. **Map.** Apply `column_map` to produce canonical fields. Any unmapped header is logged as a data-quality issue and left available in `raw_json`, so no field is silently dropped.
6. **Normalise.** Lowercase and de-parameterise URLs, strip trailing slashes, split site / library / folder path, derive folder depth, split participant lists into rows, extract domains, convert all dates to UTC ISO-8601, convert sizes to bytes, standardise label names.
7. **Resolve location.** Upsert `location` on `location_key`.
8. **Resolve item.** Upsert `item` on `item_key`. Existing rows update only `last_seen_run` and any previously null fields.
9. **Record evidence.** Insert `item_keyword_hit` rows. Never updated, only inserted.
10. **Reconcile.** Compare loaded counts against the Locations and Summary CSVs. Mismatches raise issues; they do not fail the load.
11. **Score.** Incremental rescoring of only the items and locations touched (section 6).

Each file loads inside one transaction. A failure rolls that file back and leaves the rest of the database intact.

### 2.2 Item key derivation

Tried in order, first available wins, and the method used is recorded in `item.key_method` so nothing is a black box:

1. Purview immutable ID or DocID, plus workload.
2. SharePoint and OneDrive: normalised document link plus version ID.
3. Exchange and Teams: internet message ID plus mailbox UPN.
4. Fallback: hash of workload, location key, file name, size and created date. Items resolved by fallback are flagged `key_confidence = low` and listed in the data-quality report.

`content_group_id` uses internet message ID for mail, and a hash of file name, size and created date for documents.

### 2.3 Keyword attribution

Because each keyword is searched separately, the keyword usually comes from the run, not from a column in the Items CSV. Attribution order: an explicit keyword column if present, otherwise the run's registered keyword, otherwise the query text parsed from the Summary CSV. A run with no resolvable keyword is rejected at load and raised as an issue, rather than loaded with a guess.

### 2.4 Practical CSV handling notes

Purview exports routinely contain a UTF-8 byte order mark, embedded newlines inside subject fields, commas inside recipient lists, occasional very long single fields, and chunked Items files (`Items_1.csv`, `Items_2.csv`). Chunks are separate `source_file` rows feeding the same run, and dedupe by `item_key` handles any overlap between chunks.

---

## 3. Keyword taxonomy

Every keyword gets one primary category, an optional secondary, and a specificity of 1 (broad) to 3 (highly specific). Category diversity, not keyword count, is what drives score.

| Code | Category | Examples | Specificity range | Role in scoring |
|---|---|---|---|---|
| **A** | Export control regulation | International Traffic in Arms Regulations, ITAR, USML, DDTC, DSP-5, TAA, MLA, ECCN, EAR | 2 to 3 | Positive, strong |
| **B** | Handling and distribution markings | Export Controlled, NOFORN, US Persons Only, Distribution Statement B to F, Third Party Transfer, Technical Data Package | 3 | Positive, strongest |
| **C** | Contract, programme and customer identifiers | Programme names, contract numbers, customer names, licence numbers | 3 | Positive, strong. Supplied by Trade Compliance |
| **D** | Technical data indicators | Drawing number patterns, part numbers, specification, interface control document, test report, source code, CAD extensions (.dwg, .step, .stp, .prt, .catpart, .slddrw) | 2 to 3 | Positive, strong. The difference between "talks about ITAR" and "may be ITAR" |
| **E** | Nationality and personnel control | Dual national, nationality check, citizenship verification, export-approved personnel | 2 | Positive, corroborating |
| **F** | Procedural and reference | ITAR training, awareness, policy, procedure, compliance manual, newsletter, induction | 1 to 2 | **Negative**, pushes towards deprioritisation |
| **G** | Known noise and collisions | Acronym collisions, surnames, foreign-language false friends, boilerplate footers | 1 | **Negative**, false-positive marker |

Every keyword carries an owner and a guidance note recording why it was chosen and what it is expected to catch. Retired keywords stay in the database with `active_to` set, so old results stay explainable.

**Keyword quality metrics**, computed per keyword and reported (section 5, report 11):

- Total hits, distinct items, distinct locations.
- **Unique contribution**: items found by this keyword and no other. Zero unique contribution over several runs means redundant.
- **Overlap**: Jaccard similarity against every other keyword. High overlap pairs are candidates for retirement.
- **Concentration**: share of hits in the top five locations. Near-total concentration in one policy site suggests a reference-only term.
- **Precision**, once reviewer verdicts exist: confirmed relevant divided by reviewed.
- **Breadth flag**: hits above a set percentile of all keywords, with low unique contribution, marks a term as overly broad.

---

## 4. Evidence and scoring framework

### 4.1 Rules

- Additive points, each from a named factor, each capped.
- Negative factors are allowed and are shown, not hidden.
- Weights live in `scoring_rule`, versioned. Changing a weight creates a new `score_version`; old scores are retained.
- No score is written without its `score_factor` rows. A score with no explanation is a bug.

### 4.2 Item-level factors (starting weights, to be calibrated)

| Code | Factor | Points |
|---|---|---|
| F01 | Distinct indicator categories matched, beyond the first | +4 each, cap +12 |
| F02 | Highest keyword specificity present | 3 to +5, 2 to +3, 1 to +1 |
| F03 | Category B handling marking in file name or title | +6 |
| F04 | Technical document type by extension or document-type term | +5 |
| F05 | Programme, contract or part-number pattern in path or file name | +5 |
| F06 | Located in an engineering or programme repository class | +3 |
| F07 | Located in a known, authorised ITAR repository | -4 and flagged separately as "expected location" |
| F08 | Unexpected location: personal OneDrive, general corporate site, externally shared | +4 |
| F09 | No sensitivity label where sibling items in the same library carry one | +3 |
| F10 | Label present but inconsistent with siblings | +2 |
| F11 | External or non-approved-jurisdiction recipient domains on mail | +4 |
| F12 | Only category F or G matched | -6 |
| F13 | Content group appears in many locations across M365 | +2, but if very widely spread and only F or G signals, routes to procedural instead |
| F14 | Modified within the last 24 months | +1 |
| F15 | Encrypted, unsupported or partially indexed | Not scored. Routed to the unreadable queue |

### 4.3 Location-level scoring, which is the actual deliverable

Location score is **not** the sum of item scores, because that reintroduces volume bias. It combines four normalised components plus modifiers:

```
location_score = 0.35 * norm(peak_item_score)
               + 0.25 * norm(category_diversity)
               + 0.20 * norm(match_density)
               + 0.20 * norm(distinct_high_specificity_keywords)
               + modifiers (repo class, known repository, external sharing, label gaps)
```

- **peak** rewards one genuinely strong item over a hundred weak ones.
- **diversity** is the count of distinct indicator categories seen in the location.
- **density** is matched items divided by total items in the location (see the open question in section 7 about the denominator).
- **breadth** counts distinct specificity-3 keywords.

Raw match count is carried as a context column in every report but is deliberately **not** an input. That is the direct answer to the principle that the biggest repository is not automatically the highest risk.

### 4.4 Mapping to the six analytical statuses

Rules first, thresholds second, so the category is explainable:

| Condition | Status |
|---|---|
| Encrypted, unsupported or partially indexed | Insufficient metadata to assess |
| Only category G matched | Likely false positive |
| Only category F, or F dominant with no D | Likely procedural or reference material |
| C present, D absent | Possible contractual or programme indicator |
| D present together with A or B | Possible ITAR technical data |
| Three or more categories, and score in the top band | High-priority business review |

Bands: 0 to 9 low, 10 to 19 medium, 20 to 29 high, 30 and above critical.

---

## 5. Reports and validation checks

### 5.1 The twelve required outputs

| # | Report | Source | Notes |
|---|---|---|---|
| 1 | Consolidated item register | `v_item_full` | One canonical record per item instance, with provenance columns |
| 2 | Keyword-to-item link table | `item_keyword_hit` | Every match preserved, joined to run and CSV |
| 3 | Ranked SharePoint site and library report | `v_site_rollup` | Score components shown as separate columns |
| 4 | Ranked OneDrive account report | `v_onedrive_rollup` | Personal sites separated from team sites |
| 5 | Ranked mailbox report | `v_mailbox_rollup` | Folder-level breakdown where available |
| 6 | Ranked Teams and channel report | `v_team_rollup` | Team mapped to its backing SharePoint site |
| 7 | Multiple high-value indicator list | `v_multi_signal` | Items and locations with three or more categories |
| 8 | Likely procedural repositories | status filter | Deprioritised, explicitly **not** excluded, with the reason shown |
| 9 | Unreadable and partially indexed items | `v_unreadable_queue` | Separate investigation track |
| 10 | Business review pack | generated per location | Location, metadata, matched indicator categories, reason for review. No extracted text. Recipient addresses reducible to domain only for wider circulation |
| 11 | Keyword quality report | `v_keyword_quality` | Metrics from section 3 |
| 12 | Data quality report | `data_quality_issue` | Missing fields, format drift, duplicates, scope limits |

Every row in every report carries: search run, keyword, source CSV file name, original row number and original item identifier. Traceability is a column requirement, not an appendix.

### 5.2 Validation checks, run automatically after each load

- **Reconciliation**: items loaded per run equals the Summary CSV count; items per location equals the Locations CSV count.
- **Orphans**: no hit without an item, no item without a location.
- **Key collisions**: no two different source identifiers resolving to one `item_key`.
- **Key confidence**: count and list of items resolved by the fallback hash.
- **Field null rates per run**, compared against the previous run. A sudden jump means Purview changed the export format.
- **Unmapped headers**: any header not in `column_map`.
- **Date sanity**: future dates, dates before 1990, sent after received.
- **Keyword coverage**: every run maps to at least one keyword.
- **Scoring determinism**: a fixed fixture set must produce byte-identical scores for a given `score_version`. Run as a unit test.
- **Sampling harness**: stratified random sample per band exported for authorised reviewer verdicts, which feed `review_verdict` and recalibrate keyword precision and factor weights.

---

## 6. Adding future searches without rebuilding

1. **Insert-only loading.** A new search creates a `search_run`, its `source_file` rows, its item upserts and its hits. Existing rows are never rewritten, only touched on `last_seen_run`.
2. **Hash-based idempotency.** Re-loading the same file does nothing. Re-exporting a search produces a new file hash and merges cleanly by `item_key`.
3. **Incremental rescoring.** Only items and locations touched by the new run are rescored. A full rescore is only triggered when `score_version` changes, and even then is a minutes-long job at this scale.
4. **New keyword, no rebuild.** Add the keyword and its category, load its CSVs, run the incremental score. The taxonomy is data, not code.
5. **Score history retained.** Rescoring writes a new `score` version row rather than overwriting, so "why did this site rank differently last month" is always answerable.
6. **Schema migrations.** Numbered migration scripts plus `schema_version`. No destructive migrations.
7. **Snapshots.** Each report run is frozen in `report_snapshot`, so the position as at any date can be reproduced exactly.

---

## 7. Limitations and open questions

### Limitations to state in every output

- Metadata cannot confirm that an item is ITAR-controlled. Only authorised business owners and Trade Compliance can.
- **Absence of hits is not absence of risk.** Partially indexed, encrypted, oversized and unsupported items never match any keyword, and ITAR technical data frequently contains no export-control wording at all. Drawings, CAD files and scanned documents are the most likely blind spot.
- Purview search scope defines the ceiling of what can be found. Locations excluded from the search cannot appear in the results.
- No remediation, labelling, access change or deletion should follow from this analysis alone.

### Open questions

1. **Density denominator.** Purview gives matched item counts, not total items per library or mailbox. Without a denominator, density is relative only. Can a separate SharePoint or Graph usage report supply library item counts, or should the first version rank on peak, diversity and breadth alone?
2. **Sample export.** A real Items, Locations, Summary and Settings CSV set from the completed "International Traffic in Arms Regulations" search would let the column mapping be built from fact rather than assumption.
3. **Reference list authorisation.** Is there an approved list of ITAR programmes, contracts and sanctioned repositories that can be loaded into `reference_programme`? Several factors depend on it.
4. **Repository classification.** Is there an existing site inventory giving each SharePoint site a class (engineering, programme, policy, corporate, personal)? If not, it can be inferred from URL and title patterns, with lower confidence.
5. **Teams scope.** Are Teams channel messages inside the eDiscovery scope, or only the files in the backing SharePoint sites? This changes report 6.
6. **Where the database lives.** SQLite is right for the analysis, but the file itself will contain sensitive project metadata and needs an agreed protected location and access control.

---

*Prepared as a method proposal. Triage categories are analytical only and carry no legal or Trade Compliance status.*
