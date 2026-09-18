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
2. **Evidence is never collapsed.** The item-to-keyword link table keeps every match, with its search, its CSV file and its original row.
3. **Every score is itemised.** No score exists without a set of factor rows explaining it.
4. **Additive by design.** A new search inserts; it never rewrites history.

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
| `label_lookup` | Sensitivity label GUID to display name | `label_guid`, `label_name`, `label_priority`, `sourced_from`, `refreshed_at` |

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
| `location` | Canonical container | `location_id`, `location_key` (hash), `workload`, `location_subtype` (PrimaryMailbox / ArchiveMailbox / SystemMailbox / OneDriveSite / TeamSite / PrivateChannelSite), `site_url`, `site_title`, `library_name`, `folder_path`, `folder_depth`, `mailbox_upn`, `mailbox_type`, `team_name`, `channel_name`, `channel_type` (standard/private/shared), `parent_team_site_url`, `owner_upn`, `repo_class`, `is_known_itar_repo`, `external_sharing_flag` |
| `item` | One canonical item instance | `item_id`, `item_key` (hash), `key_method`, `key_confidence`, `content_group_id`, `doc_group_id` (all versions of one document), `is_current_version`, `location_id`, `workload`, `source_item_id`, `family_id`, `conversation_id`, `file_name`, `file_extension`, `title_or_subject`, `author`, `created_utc`, `sent_utc`, `modified_utc`, `size_bytes`, `word_count`, `extracted_text_len`, `sensitivity_label_guid`, `sensitivity_label_name`, `retention_label`, `has_attachments`, `index_status`, `is_encrypted`, `is_unsupported`, `is_list_item`, `version_id`, `first_seen_run`, `last_seen_run` |
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

- **`doc_group_id`** identifies *all versions of one SharePoint or OneDrive document*. Microsoft's own documentation confirms that document versions are not counted in search estimates but **are** returned on export. A library with versioning switched on will therefore look far busier than one without it, purely as an artefact. Versions collapse to one document for ranking, and the version count is carried as a separate column.

All three are needed. Collapsing them would destroy the site-level answer the exercise is for.

---

## 2. Ingestion and deduplication approach

### 2.1 Pipeline stages

1. **Discover.** Walk the export folder tree. One folder per search run by convention; the run is registered from the Settings and Summary CSVs.
2. **Fingerprint.** SHA-256 each file. A file already loaded with the same hash is skipped, so re-running the loader is always safe.
3. **Classify.** Identify file type from its header signature, not its filename, since export naming varies.
4. **Land.** Insert every row verbatim into `raw_item_row` as JSON.
5. **Map.** Apply `column_map` to produce canonical fields. Any unmapped header is logged as a data-quality issue and left available in `raw_json`, so no field is silently dropped.
5. **Normalise.** Lowercase and de-parameterise URLs, strip trailing slashes, split site / library / folder path, derive folder depth, split participant lists into rows, extract domains, convert all dates to UTC ISO-8601, convert sizes to bytes, standardise label names.
6. **Resolve location.** Upsert `location` on `location_key`.
7. **Resolve item.** Upsert `item` on `item_key`. Existing rows update only `last_seen_run` and any previously null fields.
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

`content_group_id` uses internet message ID for mail, and a hash of file name, size and created date for documents. `doc_group_id` uses the document link with version parameters stripped, so every version of a drawing rolls up to one document.

**SharePoint list trap.** If the *name* of a SharePoint list matches a search term, Purview counts every item in that list as a hit, but exports the whole list as a single CSV. A site holding a list called something like "Export Control Register" will therefore show thousands of hits that are really one object. Items resolved as list items are flagged `is_list_item` and counted once at location level, with the raw count kept as context.

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

- **Reconciliation, tolerance based**: Microsoft states that estimated and actual result counts legitimately differ, because the search is re-run at export, versions and unindexed items are added, and lists collapse. So the check is not equality. It flags a variance outside an agreed band and records the expected reasons (version expansion, list collapse, unindexed inclusion, content changed between estimate and export) so a real load failure is not hidden inside normal drift.
- **Location row expansion**: one SMTP address can produce several Locations CSV rows, one per mailbox subtype (primary, archive, system). These must stay as separate locations and must not be summed into one mailbox figure without saying so.
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

## 6.5 Confirmed export route: metadata only

Leonardo is taking what eDiscovery produces directly from search, in metadata form only. No native files, no content. The whole design assumes this and depends on it.

**What this gives.** Summary, Locations, Items and Settings CSVs per keyword search. Enough for every location-level report in section 5.

**What this costs.** Fields that only populate after analytics runs in a review set stay empty: near-duplicate grouping, email threading, some family and conversation fields, and Purview's own duplicate detection. The database derives its own equivalents, as set out in 7.1, so the method still works. The derived versions are just less precise, and every one is flagged with its confidence.

**The upgrade path, which keeps content out of scope.** Adding a search result to a review set and running analytics enriches the metadata. Exporting from that review set with the **Reports only** option produces the summary and metadata load file **without any native files**. So the richer fields are available without content ever leaving the tenant boundary in a document.

**Recommended two-tier operating model:**

| Tier | Route | Applies to | Purpose |
|---|---|---|---|
| 1 | Direct export from search, metadata only | Every keyword, every sweep | Broad coverage, location ranking, keyword tuning |
| 2 | Add to review set, run analytics, export Reports only | Top-ranked locations from tier 1 | Sharper duplicate, family and threading data to confirm a location before business review |

Tier 2 is optional and only ever applied to a shortlist. Tier 1 alone still produces all twelve required outputs.

---

## 7. Checked against Microsoft's documentation

The design above was reviewed against Microsoft Learn before being finalised. Five points changed as a result. Each one would have distorted the site ranking if left as first drafted.

### 7.1 Many metadata fields are empty on a direct export from search

Microsoft's metadata field reference marks which fields populate for a **direct export from search** and which only populate once items are **added to a review set and analytics has run**. Duplicate detection, near-duplicate grouping, email threading and several family fields fall in the second group.

**Consequence.** If Leonardo is exporting straight from search, the duplicate and family columns will largely be blank, and any design leaning on them fails silently.

**What changed.** Deduplication no longer depends on Purview's duplicate fields. The database derives its own `content_group_id` and `doc_group_id`, and records `key_method` and `key_confidence` for every item so the weaker derivations are visible. Recommended operating model: keep direct export for broad sweeps, and add only the high-scoring locations to a review set with analytics enabled, where the richer fields become available.

### 7.2 The partially indexed blind spot is worse than stated, and it sits exactly where ITAR data lives

Microsoft states that statistics on partially indexed items **do not include SharePoint sites or OneDrive accounts**, and that unindexed items are only exported from locations that already produced a match. Common causes are unsupported file types, encrypted or password-protected files, and oversized attachments.

**Consequence.** CAD files, scanned drawings, large technical data packages and password-protected archives, which is precisely the ITAR technical data population, are the least likely content to appear in any keyword result, and a site containing nothing but those files can return a clean sheet.

**What changed.** This is promoted from a footnote to a headline limitation, and it now carries an action: adding data sources to an eDiscovery (Premium) case triggers advanced indexing, which reindexes content that failed first time. A separate, non-keyword sweep by file extension and location is needed to cover what keyword search structurally cannot reach.

### 7.3 Teams multiplies the same message across many mailboxes

Microsoft's Teams eDiscovery guidance sets out where each kind of message lands:

- Standard channel messages are journaled to the **team's group mailbox**.
- Private channel messages place a compliance copy in the mailbox of **every private channel member**.
- Shared channel messages go to a **system mailbox** of the parent team, searchable only through the parent team.
- Private and shared channels each have **their own SharePoint site**, separate from the parent team site.

**Consequence.** One sensitive private-channel message about an ITAR programme appears as twenty hits across twenty mailboxes. Ranked naively, twenty innocent mailboxes rise to the top and the actual channel is missed. Equally, isolating a team's main site leaves its private channel sites untouched.

**What changed.** `location` now carries `location_subtype`, `channel_type` and `parent_team_site_url`. Compliance copies collapse to one message by `content_group_id` for ranking, with the spread shown as a separate column. Private and shared channel sites are surfaced as their own locations in the site report, linked to the parent team.

### 7.4 SharePoint versions and list names inflate counts

Versions are excluded from estimates but included in exports, and a matching list *name* counts every item in that list. Both inflate a site's apparent hit count without any extra risk.

**What changed.** `doc_group_id` collapses versions, `is_list_item` isolates the list artefact, and both raw and collapsed counts appear side by side so nobody has to trust an adjustment they cannot see.

### 7.5 Count reconciliation cannot be an equality check

Microsoft documents several legitimate reasons estimated and actual counts differ. A strict equality check would fire constantly and be switched off, which is how real load failures get missed.

**What changed.** Reconciliation is now tolerance based, with the known causes recorded against each variance.

**One thing the research confirmed rather than changed.** The Locations CSV gives a matched-item count per location but no total item count for that location, which is why the density denominator remains an open question rather than an oversight.

---

## 8. Limitations and open questions

### Limitations to state in every output

- Metadata cannot confirm that an item is ITAR-controlled. Only authorised business owners and Trade Compliance can.
- **Absence of hits is not absence of risk, and this is the single biggest weakness of the exercise.** Partially indexed, encrypted, oversized and unsupported items never match any keyword. SharePoint and OneDrive partially indexed items are not even counted in the statistics. ITAR technical data also frequently contains no export-control wording at all.
- Keyword search reaches text. It does not reach drawings, scans, CAD geometry or the contents of protected archives.
- Purview search scope sets the ceiling. Locations excluded from the search cannot appear in the results.
- Counts are approximate by design, for the reasons in section 7.5.
- No remediation, labelling, access change or deletion should follow from this analysis alone.

### Open questions

1. **Density denominator.** Purview gives matched counts, not totals per library or mailbox. Can a SharePoint or Graph usage report supply library item counts, or does version one rank on peak, diversity and breadth alone?
2. **Sample export.** A real Items, Locations, Summary and Settings set from the completed "International Traffic in Arms Regulations" search would replace assumption with fact in the column map.
3. **Reference list authorisation.** Is there an approved list of ITAR programmes, contracts and sanctioned repositories to load into `reference_programme`? Several scoring factors depend on it.
4. **Repository classification.** Is there a site inventory classing each site as engineering, programme, policy, corporate or personal? If not it can be inferred from URL and title patterns, at lower confidence.
5. **Teams scope.** Are channel messages inside the eDiscovery scope, or only the files in the backing sites? Private and shared channels need explicit confirmation.
6. **Non-keyword sweep.** Is there appetite for a parallel file-type and location sweep to cover the blind spot in 7.2? Without it the exercise cannot claim coverage of technical data.
7. **Where the database lives.** The SQLite file will hold sensitive project metadata and needs an agreed protected location and access control.

---

## Sources

- [Document metadata fields in eDiscovery](https://learn.microsoft.com/en-us/purview/edisc-ref-document-metadata-fields)
- [Export reference for eDiscovery](https://learn.microsoft.com/en-us/purview/edisc-ref-export)
- [Export search results in eDiscovery](https://learn.microsoft.com/en-us/purview/edisc-search-export)
- [Export items from a review set in eDiscovery](https://learn.microsoft.com/en-us/purview/edisc-review-set-export)
- [Partially indexed items in eDiscovery](https://learn.microsoft.com/en-us/purview/edisc-ref-partially-indexed-items)
- [Investigating partially indexed items in eDiscovery](https://learn.microsoft.com/en-us/purview/ediscovery-investigating-partially-indexed-items)
- [Advanced indexing in eDiscovery](https://learn.microsoft.com/en-us/purview/edisc-ref-advanced-indexing)
- [Finding content in Microsoft Teams in eDiscovery](https://learn.microsoft.com/en-us/purview/edisc-search-teams)
- [eDiscovery (Premium) workflow for content in Microsoft Teams](https://learn.microsoft.com/en-us/purview/ediscovery-teams-workflow)
- [Process reports in eDiscovery](https://learn.microsoft.com/en-us/purview/edisc-process-report)
- [Collection statistics and reports](https://learn.microsoft.com/en-us/purview/ediscovery-collection-statistics-reports)
- [Estimated and actual eDiscovery search results](https://learn.microsoft.com/en-us/purview/ediscovery-differences-between-estimated-and-actual-search-results)
- [Evaluate and refine search results in eDiscovery](https://learn.microsoft.com/en-us/purview/edisc-search-results)
- [Keyword queries and search conditions for eDiscovery](https://learn.microsoft.com/en-us/purview/ediscovery-keyword-queries-and-search-conditions)
- [Use Keyword Query Language to create search queries in eDiscovery](https://learn.microsoft.com/en-us/purview/edisc-keyword-query-language)

---

## Appendix A. The file-type sweep, and why keyword search alone is not enough

### The problem in plain terms

Keyword search reads the words inside a file. A great deal of ITAR technical data has no readable words inside it:

- A CAD model is geometry, not text.
- A scanned drawing is a picture of a drawing.
- A password-protected archive cannot be opened at all.
- An oversized technical data package is skipped.

None of these will ever match "ITAR", or any other term, no matter how good the keyword list is. A site holding nothing but engineering drawings returns zero hits and looks clean. It is not clean. It is invisible to this method.

That is why keyword results alone cannot support a statement about coverage of technical data. They support a statement about coverage of *documents that talk about* technical data.

### The fix, which needs no new tool

Stop asking "which files mention export control" and start asking "which places hold engineering material at all". Microsoft supports `FileExtension` as a searchable property in eDiscovery KeyQL, with wildcards. The file name and extension are indexed even when the content inside is not, so this reaches files that keyword search cannot.

**Sweep design:**

1. Run a second family of searches carrying **no keyword at all**, only file type. For example `FileExtension:dwg OR FileExtension:step OR FileExtension:stp OR FileExtension:catpart OR FileExtension:slddrw OR FileExtension:prt OR FileExtension:igs`.
2. Group them into classes: CAD and drawing, simulation and analysis, source code and firmware, technical publication, archive and container.
3. Export the Locations CSV exactly as for the keyword searches. Load into the same database with a keyword category of its own, so the plumbing does not change.
4. Rank locations by **engineering material density**, entirely separately from keyword hits.

### How the two views combine

The site report gains a second axis. Keyword evidence on one, engineering material on the other:

| | Few engineering files | Many engineering files |
|---|---|---|
| **Many keyword hits** | Likely a policy or reference site. Deprioritise, do not exclude | Highest priority. Talks about control and holds the material |
| **Few or no keyword hits** | Low interest | **The blind spot.** Holds the material, says nothing about it. Invisible to keyword search alone |

The bottom-right cell is the whole point. Those locations cannot be found any other way, and on a first-principles view of ITAR risk they may matter more than a site full of policy documents.

### What it still cannot do

A file-type sweep finds *containers of technical material*. It does not say whether any given drawing is ITAR-controlled. That remains a business owner and Trade Compliance judgement, as everywhere else in this method.

---

*Prepared as a method proposal. Triage categories are analytical only and carry no legal or Trade Compliance status.*
