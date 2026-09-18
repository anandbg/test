# Loading the eDiscovery analysis into Dataverse

A practical route from Purview CSV exports to a Power Platform environment that the business can actually work in.

Metadata only throughout. No document content is loaded at any stage.

---

## 1. Decide what belongs in Dataverse, and what does not

Dataverse is not a cheaper SQLite. It is a place where people do work. Put things there that need a person, a permission or an audit trail.

| Layer | Where it belongs | Why |
|---|---|---|
| Raw CSV rows, exactly as exported | **Outside Dataverse**, in the local SQLite store | Bulky, never read by a person, and it is the evidence trail. Keep it cheap and keep it whole |
| Deduplication, keyword linking, scoring | **Outside Dataverse** | Heavy set-based work. Fast and free locally, slow and metered in Dataverse |
| Item register, location rankings, keyword table, score factors | **In Dataverse** | People read these, filter them, and argue with them |
| Review tasks, verdicts, remediation decisions | **In Dataverse, and nowhere else** | This is the part that needs named users, security roles, approval and an audit trail |

The tool already produces the middle layer. Run:

```
python edisc.py dataverse --db itar.db --out dataverse_load
```

That writes one CSV per Dataverse table plus `_dataverse_schema.csv`, which lists every column, its type, its length and whether it is an alternate key.

**If you would rather put everything in Dataverse**, that is possible. Section 5 covers the cost and the design change it forces.

---

## 2. Table design

### Standard tables for the curated layer

Standard tables sit on Azure SQL. They support relationships, transactions and the SQL endpoint that Power BI and reporting tools like. Use them for:

`led_search`, `led_keyword`, `led_location`, `led_locationscore`, `led_item`, `led_scorefactor`, `led_dataqualityissue`, and the three review tables.

### Elastic tables, only if the hit table gets very large

`led_hit` is the one table that grows without limit. Every keyword match on every item is a row, so twenty keywords across a large tenant runs into millions.

Elastic tables sit on Cosmos DB and are built for exactly this. Microsoft states they scale to ingest tens of millions of rows an hour. But they come with real restrictions:

- No many-to-many relationships.
- No rollup columns.
- **No filtering on related tables**, in views, advanced find or any query. This is the big one.
- The SQL (TDS) endpoint does not work with elastic tables. Fabric Link does, provided change tracking is on.
- Cascading must be set to none on any one-to-many relationship.

Because you cannot filter on a related table, an elastic `led_hit` must carry its own copy of the columns you want to filter by. The export already does this: every hit row repeats the keyword text, the category code, the site URL and the mailbox. Denormalising is not sloppiness here, it is the required design.

**Rule of thumb.** Under about a million hit rows, keep `led_hit` standard and keep your life simple. Above that, make it elastic and analyse it through Fabric rather than the SQL endpoint.

---

## 3. Three things that will bite you

### Alternate keys reject the characters every URL contains

Dataverse alternate keys do not work when the value contains `/ < > * % & : \ ?`. A SharePoint URL contains four of those before you reach the site name. Retrieve, update and upsert all fail.

**So every key column in the export is a hex hash.** `led_itemkey`, `led_locationkey`, `led_hitkey` and the rest are SHA-1 values. URLs travel as ordinary text columns, where they are perfectly safe. Do not be tempted to make the site URL an alternate key.

Also: a null in an alternate key column means uniqueness is not enforced. Every key column in the export is always populated.

### One payload cannot contain the same key twice

`UpsertMultiple` fails if two rows in the same request resolve to the same key, and Data Factory upsert behaves the same way. The export deduplicates each file on its key before writing, and reports how many duplicates it removed.

### Load order matters

Load parents before children, or the lookups have nothing to point at:

1. `led_search`
2. `led_keyword`
3. `led_location`
4. `led_locationscore`
5. `led_item`
6. `led_hit`
7. `led_scorefactor`
8. `led_dataqualityissue`

---

## 4. How to load it

Three options, easiest first.

### Option A: dataflows (recommended to start)

A standard dataflow reads the CSV and writes to the table. Choosing a key column tells the dataflow to upsert rather than insert, which is what makes re-running safe.

- Good for tens of thousands to low hundreds of thousands of rows.
- No code, no app registration, no developer.
- Map `led_itemkey` (and equivalents) as the key column on every table.

### Option B: Fabric or Azure Data Factory pipeline

Same idea, more throughput, scheduling and retry built in. Worth it once the load runs regularly or the row counts climb.

### Option C: bulk API

`CreateMultiple`, `UpdateMultiple` and `UpsertMultiple` send many rows per request instead of one at a time. This is the fastest route and the one to use for an elastic `led_hit`. It needs an app registration and someone comfortable with the Dataverse SDK. Watch the request size ceiling of roughly 116 MB and batch well below it.

Whichever you choose, **run it twice on purpose during testing.** The second run must change nothing. If row counts double, your key mapping is wrong.

---

## 5. Capacity and cost, before you commit

Dataverse database capacity is entitlement-based and the entitlements are small. The default environment starts with 3 GB. Per-user and per-app licences add megabytes, not gigabytes. Beyond that you buy capacity in 1 GB blocks, and it is not cheap.

**Size it before you load it**, not after:

1. Load one keyword's worth of data into a test environment.
2. Check what it consumed in the capacity report.
3. Multiply by the number of keywords you expect, then by your expected growth.

A rough guide: an item row with thirty text columns lands somewhere around 1 to 2 KB. A million item rows is therefore 1 to 2 GB before indexes. Hit rows are smaller but far more numerous.

This is the strongest argument for the split in section 1. The curated layer is thousands of rows for the shortlist, not millions. The millions stay in SQLite, where they cost nothing.

---

## 6. Analysis, once it is loaded

| Tool | Use it for | Note |
|---|---|---|
| **Power BI, Dataverse connector** | The site, mailbox and Teams rankings. The two-axis view from appendix A | Simplest route. Works against standard tables |
| **SQL endpoint (TDS)** | Ad hoc queries, validation, joining tables | Standard tables only. Not available for elastic tables |
| **Link to Microsoft Fabric** | Anything large, and anything involving an elastic `led_hit` | Creates a lakehouse, a SQL endpoint and a semantic model, kept in sync. Elastic tables need change tracking enabled |
| **Model-driven app** | The reviewer experience. Assign a location, record a verdict, see the evidence | This is the real reason to use Dataverse |
| **Power Automate** | Assignment, reminders, escalation, approval routing | Keep remediation behind a human approval step |

### What the reviewer should see

A model-driven app with three views is enough to start:

1. **My review tasks.** Locations assigned to me, highest score first.
2. **Location detail.** The score with its four components shown separately, the indicator classes found, the raw match count marked as context only, and the list of items beneath.
3. **Record a verdict.** Confirmed, not ITAR, needs a specialist, cannot determine. Free text for the rationale.

Verdicts flowing back are what let you measure which keywords are actually earning their place, and recalibrate the weights with evidence instead of opinion.

---

## 7. Security, which is not optional here

The data is metadata, but it is sensitive metadata: programme names, engineer names, email subjects, recipient addresses and file paths that reveal what is being built and with whom.

- Use a **dedicated environment**, not the default one. The default environment is open to everyone in the tenant.
- Restrict with security roles from day one. Most people should see the location rankings, not the item register.
- Consider masking recipient addresses to domain only in any view shared beyond the core team.
- Decide who may export from the app, and turn it off for everyone else.
- Record the environment and its access decision alongside the method document.

---

## 8. Suggested order of work

1. Run the local pipeline end to end on the searches you already have. Confirm the ranking looks sane to someone who knows the business.
2. Create a dedicated Dataverse environment and the tables from `_dataverse_schema.csv`. Add the alternate keys.
3. Create the three review tables empty. Nothing loads into them.
4. Load one search only, using a dataflow. Check the capacity report.
5. Run the same load again. Confirm nothing duplicates.
6. Load the rest. Build the Power BI report against the ranking tables.
7. Build the model-driven app for reviewers. Start with three views.
8. Only then wire up Power Automate for assignment and approval.

Do not skip step 5.

---

## Sources

- [Elastic tables for developers](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/elastic-tables)
- [Create and edit elastic tables](https://learn.microsoft.com/en-us/power-apps/maker/data-platform/create-edit-elastic-tables)
- [Use bulk operation messages](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/bulk-operations)
- [Optimize performance for bulk operations](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/optimize-performance-create-update)
- [Work with alternate keys](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/define-alternate-keys-entity)
- [Use upsert to create or update a record](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/use-upsert-insert-update-record)
- [Field mapping considerations for standard dataflows](https://learn.microsoft.com/en-us/power-query/dataflows/get-best-of-standard-dataflows)
- [Dataverse capacity-based storage details](https://learn.microsoft.com/en-us/power-platform/admin/capacity-storage)
- [Link your Dataverse environment to Microsoft Fabric](https://learn.microsoft.com/en-us/power-apps/maker/data-platform/azure-synapse-link-view-in-fabric)
- [Use SQL to query data](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/dataverse-sql-query)

---

*Analytical triage only. No labelling, access change or deletion should follow from this data without authorised human review.*
