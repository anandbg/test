# Running the ten searches, and what to hand the business

Three questions answered here: how to sequence the searches so each one teaches you something, what can actually be done to SharePoint, OneDrive, email and Teams, and how to use Agent Builder without it quietly inventing numbers.

Metadata only. Nothing here is a Trade Compliance determination.

---

## Part 1. How to run the ten searches

### Do not run all ten and then analyse

Run them in waves. Each wave changes what you search for next. Ten searches run blind give you ten piles. Ten searches run in waves give you a position.

**Wave 1, three searches, run together:**

1. `International Traffic in Arms Regulations` (the phrase, already done)
2. `Export Controlled` (the handling marking, the strongest single signal)
3. **The file type sweep.** `FileExtension:dwg OR FileExtension:step OR FileExtension:catpart` and so on. No keyword at all.

The file type sweep goes in wave 1, not at the end. It is the denominator. Without it you have no idea whether a site with three hits is a site with three documents or a site with thirty thousand drawings.

**Wave 2, three or four searches:** driven by what wave 1 tells you. Programme names, contract numbers and part number formats harvested from wave 1 file names and paths.

**Wave 3, the rest:** the gaps wave 2 exposes.

### The four numbers to record after every single search

| Number | What it is | What it tells you |
|---|---|---|
| **New locations** | Sites, mailboxes and teams not seen in any earlier search | The only real measure of progress |
| **New items** | Items not seen before | Volume, far less useful than new locations |
| **Overlap** | Share of this search's hits already found by earlier searches | High overlap means the term is redundant |
| **Concentration** | Share of hits sitting in policy or reference sites | High means the term finds talk about ITAR, not ITAR |

### The decision rules

Read them after each search and act:

- **New locations still rising after every search.** You are nowhere near the end. Ten searches will not be enough. Keep going and say so early, because it changes the plan.
- **New locations falling towards zero.** You have exhausted this vocabulary. Adding more synonyms will not help. Switch to pattern-based searching: file types, part number formats, path patterns, author names from the sites you already found.
- **Over roughly 70 percent of a term's hits in policy or reference sites.** It is a reference term. Keep it for context, stop chasing it, and do not let it drive any site ranking.
- **A term finds mostly new locations.** It is productive, and more importantly it is telling you the vocabulary you are missing. Mine its file names and folder paths for programme names, customer names and part number formats, and those become wave 2.
- **A term returns almost nothing.** Either it is genuinely absent, or it is spelled differently here. Check the spelling with Trade Compliance before retiring it.

### The trap to name out loud

Saturating the vocabulary is not the same as covering the risk. You can reach the point where no new keyword finds anything new, and still have found none of the CAD, none of the scans, and none of the protected archives, because those files contain no words to match. Keyword saturation tells you that you have found everything that *talks about* export control. It says nothing about the drawings.

That is why the file type sweep runs from wave 1 and is reported separately, never blended into the keyword ranking.

---

## Part 2. What can actually be done, per workload

### SharePoint sites: Restricted Content Discovery

This is the right first control and it is genuinely easy.

**What it does.** Stops the site's content appearing in organisation-wide search results and in Copilot responses. Also removes the AI entry points from the site: the Copilot button, the AI actions menus, agent creation, create pages with AI.

**What it does not do.** It does not change who can access the site. Nobody loses access. Nobody is locked out.

That combination is why it is the right first move. It is reversible, it disrupts nobody, and it buys time while the business does the real review.

**How.** SharePoint admin centre, Active sites, pick the site, Settings tab, turn on Restrict content from Microsoft Copilot. Or PowerShell:

```
Set-SPOSite -Identity <site-url> -RestrictContentOrgWideSearch $true
```

**The one caveat that matters.** On sites with more than 500,000 items, the change can take more than a week to work through search and Copilot. Apply it to your large sites first, not last.

**Say this to the business plainly:** this is a holding control, not remediation. It stops Copilot reading the site. It does not stop a person emailing a drawing out.

### SharePoint files: can you label an exact list of file names?

**Not with an auto-labelling policy.** This is the correction that matters most.

Auto-labelling policies match on **content**: sensitive information types, trainable classifiers, and keyword or regular expression patterns wrapped in a custom sensitive information type. They do not accept a list of file paths or file names. Handing the policy your list of 400 exact files is not a thing the product does.

You have two real routes.

**Route A, the scalable one: build a custom sensitive information type.**

Turn your strongest findings into a pattern: the part number formats you harvested, the handling markings such as "Export Controlled" and "Distribution Statement", programme names. Then auto-label on that.

- It catches files you never found, which is the whole point.
- It keeps working on new files without anyone doing anything.
- Auto-labelling policies run in **simulation mode** by default. Use it. Look at what it would have labelled before you turn it on. This is free and there is no excuse for skipping it.

**Route B, the exact list: the Graph API.**

`driveItem: assignSensitivityLabel` applies a label to one specific file, in SharePoint or OneDrive. So yes, an exact list is possible. But know what you are signing up for:

- It is a protected and **metered** API. You must enable metered APIs and services, which means an Azure subscription linked to the calling app. There is a per-call charge.
- It needs app permissions such as `Files.ReadWrite.All` or `Sites.ReadWrite.All`.
- It is asynchronous, one item at a time, and needs error handling and an audit record of every change.

In other words it is a small project, not a click. Worth it for a defined high-value list. Not worth it as the general mechanism.

**Recommendation.** Route A as the mechanism, Route B for a short list of confirmed high-risk files that the pattern misses.

**One more caveat.** Auto-labelling will not relabel files already encrypted with older Azure Information Protection labels, and some file formats are simply not supported. Expect a failure list and plan to work it.

### OneDrive: yes, you can label it

Your instinct here was wrong, and that is good news.

- OneDrive is an **included location in auto-labelling policies**. By default all SharePoint, OneDrive and Exchange locations are in scope when you create one.
- The Graph API route also works on OneDrive drive items.

So the technical ability exists. The question is whether you should use it silently.

**Recommendation: tell people first, then label.** A file in someone's OneDrive is their working copy. Labelling it without warning breaks their day and burns your credibility for the rest of the programme. Run the policy in simulation, send the affected people a short note with what is changing and when, give them a window to move anything that genuinely belongs elsewhere, then turn the policy on.

The note should say what to do, not list their files back at them.

### Email: the honest answer

**You cannot retroactively label existing email.** Auto-labelling for Exchange works on mail **in transit**, as it is sent or received. It does not apply to mail already sitting in mailboxes. There is no supported way to sweep the existing mailbox and label it.

What that leaves you:

| Want | Possible? | How |
|---|---|---|
| Label existing mail | No | Not supported |
| Label new mail carrying the markings | Yes | Auto-labelling policy, Exchange location, in transit |
| Stop Copilot using sensitive mail | Partly | DLP policy on the Microsoft 365 Copilot location, condition Content contains, Sensitivity labels. Only works on mail that carries a label, so only new mail, and only mail sent on or after 1 January 2025 |
| Apply a retention label to existing mail at rest | Yes | Auto-apply retention label policies can scan mailboxes at rest. This is the closest built-in mechanism, but it retains, it does not protect |
| Stop the behaviour | Yes | People |

So for existing email, the control is behavioural. That is not a cop-out, it is the actual state of the product.

### Teams: split it in two

This distinction is worth making clearly, because they are two different problems wearing one name.

**Teams files** live in SharePoint. They are fully in scope for Restricted Content Discovery and for auto-labelling. Treat them exactly as SharePoint. Remember that private and shared channels have their **own SharePoint sites**, separate from the parent team, so restricting the main team site leaves those untouched.

**Teams messages** are a different matter. They cannot be individually sensitivity-labelled. Copilot surfaces the highest priority label from the data it used, which does not help you with a chat message carrying a part number in plain text. And private channel messages sit as compliance copies in **every member's mailbox**, so there is no single place to clean up.

Teams messages are a training and behaviour finding. What you can do with them: identify which teams and channels it is happening in, brief those teams, and fix the backing SharePoint sites, which you can control.

---

## Part 3. The decision you have to make about people

For email and Teams chat, pick a posture. This is a business decision, not a technical one, and it should be made once and written down.

| Posture | What it means | When it fits |
|---|---|---|
| **A. Inform and educate** | General communication. No individual named, no evidence shared. Training refresh, reminder of the rules | The default for the general population |
| **B. Targeted ask** | Named individuals contacted, told what to do, given a deadline and asked to confirm | Mailboxes and OneDrive accounts that score high with multiple independent signals |
| **C. Formal escalation** | Treated as a potential unauthorised disclosure. Routed to Trade Compliance and legal before anyone contacts the individual | Only where technical data appears alongside a non-approved external recipient |

**Recommended split:** A for everyone, B for the named high-scoring accounts, C only on the external recipient trigger.

**Three rules for the comms, whichever posture:**

1. **Never send people their own email subjects or file lists as evidence.** That is itself a disclosure, it is inflammatory, and it invites argument about individual files instead of action. Send the ask.
2. **Say what to do, not what they did.** "Move any drawings or technical data out of your OneDrive and into the programme site by the 30th" beats "we found 14 files in your OneDrive".
3. **Get a confirmation.** A checkbox, a reply, a form. Without it you have no record that you asked, which matters if this is ever examined.

**One flag to raise before you start.** Reading and acting on named individuals' email and chat has employment law and, depending on the country, works council and notification implications. Get that cleared before posture B or C goes out, not after.

---

## Part 4. Using Agent Builder properly

### Your plan, assessed

Your plan was: one agent, feed it one search's output, get a succinct summary, run it ten times, then combine the ten summaries into the answer.

**The shape is right.** That is a map-reduce, and it is the correct pattern here. Ten small comparable summaries are far easier to reason over than two hundred CSVs.

**The volume is fine.** An agent can take up to 500 uploaded files as knowledge, up to 100 SharePoint files, folders or sites, and each of those sources can hold up to 1,000 files. Ten searches at twenty CSVs each is two hundred files. Comfortably inside the limits.

**But there is one flaw that will bite you**, and it matters because the output decides which sites get locked down.

### The flaw: what you are asking for is counting

Deduplicating an item that turns up in six of ten searches. Counting distinct sites. Working out overlap between keywords. Ranking. Measuring whether new locations are still rising.

These are counting operations over hundreds of thousands of rows. Knowledge sources are **retrieval**, not computation. The agent searches the files for relevant passages and reasons over what it finds. It does not load every row and tally them. Ask it for a count and you will get a confident, plausible, wrong number, with no signal that it is wrong.

For an ITAR exercise that is not acceptable. A site that should have been restricted and was not is the failure mode.

### The split that works

| Job | Who does it | Why |
|---|---|---|
| Deduplicate, count, overlap, rank, saturation curve | **Code.** The SQLite tool, or Power Query in Excel, or a Fabric query | Must be exact and repeatable. A different answer on Tuesday is worthless |
| Read file names and paths and propose **new search terms** | **Agent** | Language work. Genuinely what the model is good at |
| Explain why a site is on the list, in business language | **Agent** | Language work |
| Draft the note to each site owner and to OneDrive users | **Agent** | Language work |
| Answer a site owner asking "why is my site on this list" | **Agent** | Language work, grounded in the ranked table |

If you truly cannot run any code, use Power Query in Excel for the counting. It is deterministic, it is on every machine, and it needs no approval. Do not hand the counting to the model.

### The map step, done properly

The agent must return the **same shape every time** or the reduce step is meaningless. Give it a fixed template and tell it to leave a field blank rather than guess.

Ask it for, per search:

- The search name and term
- The top locations by hit count, as a plain list, taken from the Locations CSV which is already aggregated for you
- **Candidate new search terms** seen in file names and folder paths: programme names, customer names, part number formats, document type words, project code names
- **Observed patterns**, such as a recurring part number format written out as a pattern
- Anything that looks like a handling marking in a file name
- Which locations look like policy or reference material, and why
- What it could not tell from the metadata

Note what is **not** on that list. No counts it derived itself. No cross-search comparison. No ranking. Those come from the code.

The high value item there is candidate new search terms. That is the thing that turns wave 1 into wave 2, and it is exactly the task a language model earns its place on.

### The reduce step

Save each of the ten map outputs as a file. Agents have no memory between runs, so the ten summaries must be stored and then fed back in as a fresh input for the reduce step.

The reduce agent gets: the ten summaries, plus **the ranked tables produced by the code**. It writes the business-facing pack. It does not recompute the ranking, it narrates it.

### One thing to check before you start

The CSVs contain sensitive project metadata: programme names, engineer names, email subjects and recipients. Whichever model you use must sit inside your tenant boundary. Microsoft 365 Copilot and Agent Builder do. Confirm the same for the GPT deployment before anything is uploaded to it.

Ready-made instruction templates for both steps are in `tools/agent-builder/`.

---

## Part 5. The sequence, end to end

1. Run wave 1: two keywords plus the file type sweep.
2. Load into the tool. Record the four numbers.
3. Run the map agent over wave 1 to harvest new vocabulary.
4. Take the harvested terms to Trade Compliance to approve or reject. Do not search on unapproved terms.
5. Run wave 2. Record the four numbers again. Check whether new locations are still rising.
6. Repeat until new locations flatten, or you run out of budget. Say which one it was.
7. Rank the sites. Apply Restricted Content Discovery to the top sites as a holding control. This is reversible and needs no business sign-off to be safe.
8. Build the custom sensitive information type from the confirmed patterns. Run the auto-labelling policy in **simulation mode**.
9. Review what simulation would have labelled. Adjust. Only then turn it on.
10. Communicate to OneDrive users before labelling their files.
11. Email and Teams: apply the posture decision from part 3.
12. Report the blind spot honestly. Keyword search cannot cover technical data with no readable text, and no amount of keyword work changes that.

---

## Sources

- [Restrict discovery of SharePoint sites and content](https://learn.microsoft.com/en-us/sharepoint/restricted-content-discovery)
- [Manage access to agents in SharePoint](https://learn.microsoft.com/en-us/sharepoint/manage-access-agents-in-sharepoint)
- [Automatically apply a sensitivity label to Microsoft 365 data](https://learn.microsoft.com/en-us/purview/apply-sensitivity-label-automatically)
- [Enable sensitivity labels for files in SharePoint and OneDrive](https://learn.microsoft.com/en-us/purview/sensitivity-labels-sharepoint-onedrive-files)
- [Resolve auto-labeling failures in SharePoint and OneDrive files](https://learn.microsoft.com/en-us/troubleshoot/microsoft-365/purview/sensitivity-labels/auto-labeling-failures-sharepoint-onedrive)
- [driveItem: assignSensitivityLabel](https://learn.microsoft.com/en-us/graph/api/driveitem-assignsensitivitylabel?view=graph-rest-1.0)
- [Automatically apply a retention label to Microsoft 365 items](https://learn.microsoft.com/en-us/purview/apply-retention-labels-automatically)
- [Microsoft Purview DLP for Microsoft 365 Copilot and Copilot Chat](https://learn.microsoft.com/en-us/purview/dlp-microsoft365-copilot-location-learn-about)
- [Use Microsoft Purview to manage data security and compliance for Microsoft 365 Copilot](https://learn.microsoft.com/en-us/purview/ai-m365-copilot)
- [Considerations for Microsoft Purview to manage Microsoft 365 Copilot and Channel Agent in Teams](https://learn.microsoft.com/en-us/purview/ai-m365-copilot-considerations)
- [Finding content in Microsoft Teams in eDiscovery](https://learn.microsoft.com/en-us/purview/edisc-search-teams)
- [Agent Builder in Microsoft 365 Copilot](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/agent-builder)
- [Add knowledge sources to your declarative agent](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/agent-builder-add-knowledge)

---

*Analytical triage only. No labelling, access change or deletion should follow from this without authorised human review.*
