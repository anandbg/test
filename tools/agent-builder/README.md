# Agent Builder templates

Two agents, used in sequence. The pattern is map then reduce: summarise each search on its own, then combine.

| File | Agent | Knowledge to attach | Run |
|---|---|---|---|
| `1-map-agent-instructions.md` | Map | The CSVs from **one** search | Once per search. Save each answer as a file |
| `2-reduce-agent-instructions.md` | Reduce | The ten saved map answers **plus the ranked tables from the analysis tool** | Once |

## The rule that makes this work

The agent never produces a number it worked out itself.

Counting, deduplicating, overlap and ranking are done by code, because those answers must be exact and must be the same every time you ask. Knowledge sources are retrieval, not computation. An agent asked to count across two hundred CSVs returns a confident, plausible, wrong answer with no sign that it is wrong.

The agent does the language work: harvesting new search vocabulary from file names, explaining why a site is on the list, and drafting the notes to site owners and users. That is genuinely what it is good at, and the vocabulary harvesting is what turns one round of searching into a better next round.

## Limits worth knowing

- Up to 500 uploaded files as knowledge, up to 100 SharePoint files, folders or sites, each holding up to 1,000 files, up to 50 OneDrive files.
- Ten searches at about twenty CSVs each is two hundred files. Comfortably inside the limits.
- Agents keep nothing between runs. Each map answer must be saved as a file and fed back in for the reduce step.
- The CSVs hold sensitive project metadata. Confirm whichever model you use sits inside your tenant boundary before uploading anything.

Full reasoning is in `docs/keyword-strategy-and-business-actions.md`.
