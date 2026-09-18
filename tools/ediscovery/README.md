# Running the eDiscovery analysis on a Windows laptop

This turns a pile of Purview eDiscovery metadata CSVs into one local SQLite database, scores it, and writes the ranked reports.

Everything runs on your machine. Nothing is uploaded. The tool reads metadata only. It never opens a native file and never reads document content.

---

## 1. What you need

**Python 3.9 or newer.** Check by opening Command Prompt and typing:

```
python --version
```

If that fails, install Python from the Microsoft Store or from python.org. Tick "Add Python to PATH" during setup. Your IT team may need to approve it.

Nothing else. No pip install, no libraries, no internet.

**Optional, for browsing the database by hand:** DB Browser for SQLite (sqlitebrowser.org). Not required. The reports are plain CSVs that open in Excel.

---

## 2. Lay out the export folders

One folder per search. Put the four CSVs from that search inside it. Folder names are how the tool tells searches apart, so name them clearly.

```
C:\ediscovery\exports\
    search_itar_phrase\
        Items.csv
        Locations.csv
        Summary.csv
        Settings.csv
    search_export_controlled\
        Items.csv
        ...
    search_sweep_dwg\
        ...
```

Chunked exports are fine. `Items_1.csv`, `Items_2.csv` and so on all load into the same search.

---

## 3. Tell it what each search was looking for

Copy `keywords.example.csv` to `keywords.csv` and edit it. One row per search:

| column | meaning |
|---|---|
| `run_name` | the folder name |
| `keyword` | the term that was searched |
| `category` | A to G, or X for a file type sweep. See the method document |
| `specificity` | 1 broad, 2 medium, 3 highly specific |
| `owner` | who chose the term |
| `note` | why it is on the list |

This file is the difference between a useful ranking and a meaningless one. The categories are what stop a policy library outranking an engineering site.

---

## 4. Run it

Open Command Prompt in this folder and run these three, or just edit the paths in `run.bat` and double click it.

**Check what it can read, before loading anything:**

```
python edisc.py inspect --exports "C:\ediscovery\exports"
```

This lists every CSV, what it thinks each one is, and any column it does not recognise. Unrecognised columns are still stored, but they will not be scored. If something important is on that list, tell me the column name and I will add it.

**Load, score and report in one go:**

```
python edisc.py all --db "C:\ediscovery\itar.db" --exports "C:\ediscovery\exports" --keywords keywords.csv --out "C:\ediscovery\reports"
```

Or run the three stages separately if you prefer:

```
python edisc.py load   --db itar.db --exports "C:\ediscovery\exports" --keywords keywords.csv
python edisc.py score  --db itar.db --config config.json
python edisc.py report --db itar.db --out reports
```

**Adding a new search later:** drop the new folder into `exports` and run the same command again. Files already loaded are skipped. Nothing is rebuilt.

**Prove it works before you trust it:**

```
python edisc.py selftest
```

This builds invented data, runs the whole pipeline, and checks that an engineering site outranks a policy site and that a file matched by three searches stays one item with three pieces of evidence.

---

## 5. What comes out

| File | What it is |
|---|---|
| `01_item_register.csv` | One row per item, with its score, its matched classes and where it came from |
| `02_keyword_item_links.csv` | Every keyword match, traceable back to the CSV and row |
| `03_sharepoint_sites.csv` | **The main answer.** Sites ranked, with the score broken into its parts |
| `03b_folders_and_libraries.csv` | Same, at folder level |
| `04_onedrive_accounts.csv` | OneDrive ranked |
| `05_mailboxes.csv` | Mailboxes ranked |
| `06_teams_channels.csv` | Teams and channels ranked |
| `07_multi_signal.csv` | Items matching three or more independent classes |
| `08_procedural_deprioritised.csv` | Likely reference material. Lower priority, not excluded |
| `09_unreadable_items.csv` | Encrypted, unsupported or partly indexed. Needs separate investigation |
| `10_business_review_pack.csv` | For the business owners. Location, metadata, reason for review, no content |
| `11_keyword_quality.csv` | Which terms are earning their place |
| `12_data_quality.csv` | Everything that looked wrong during loading |
| `12b_unmapped_columns.csv` | Columns the tool did not recognise |
| `13_provenance.csv` | Every file loaded, with its checksum |

### Reading the site ranking

`score` is built from four parts, all shown as their own columns:

- `pts_peak` the strongest single item, so one serious file beats a hundred weak ones
- `pts_diversity` how many different classes of indicator appear
- `pts_density` distinct documents after versions and copies are collapsed
- `pts_breadth` how many highly specific terms appear

`raw_matches_context_only` is exactly that. It is shown so you can see it, and it is deliberately not part of the score.

---

## 6. Things to know before you rely on it

- The weights in `config.json` are a starting point. They need calibrating once real reviewers have looked at a sample. Every point is itemised in the review pack so you can see what drove any result.
- A site with no hits is not a clean site. CAD files, scans and protected archives never match keywords. Run the file type sweeps as well.
- Counts will not tie back exactly to Purview. That is expected, and the reasons are recorded in the data quality report.
- The database holds sensitive project metadata, including email subjects and recipients. Keep it somewhere protected and agree who may open it.
- Nothing here is a Trade Compliance or legal determination. It prioritises what people should look at, nothing more.
