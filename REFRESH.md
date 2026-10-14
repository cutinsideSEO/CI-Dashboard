# Control Room refresh runbook

This is what the twice-daily routine (`trig_01WDH93AGHQEqNsCiNghRytm`, which runs inside the session that holds the Google Drive, SurgeOS and DataForSEO connectors) does. A person can follow it too. It is read-only towards every source (Drive, SurgeOS, the tools sheet). The only thing it writes is the dashboard's own artifact database.

- Artifact: https://claude.ai/artifact/5AxMQ4gPXYVmeQWk1Kzq45
- Repo: `cutinsideSEO/CI-Dashboard`
- Work directory: the repo root. Put inputs in `data/`. The build writes to `out/`.

## 0. Load the previous state

The database holds a few documents: `meta/state`, `briefing/latest`, `snapshot/{clients,contracts,tools,alerts}` (plus `-1`, `-2`, … shards if one grows past ~180 KB) and `sources/{brains,contracts,performance}`. List each collection with `out_dir=prev`:

```
ArtifactData list  url=<artifact>  collection=meta      out_dir=prev
ArtifactData list  url=<artifact>  collection=briefing  out_dir=prev
ArtifactData list  url=<artifact>  collection=snapshot  out_dir=prev
ArtifactData list  url=<artifact>  collection=sources   out_dir=prev
```

1. The tool result prints each document's `version`. Write them to `prev/versions.json`, for example `{"meta/state": 4, "snapshot/clients": 4, ...}`.
2. Copy `prev/sources/brains.json`, `prev/sources/contracts.json` and `prev/sources/performance.json` into `data/` as the starting points. For brains and contracts, unwrap `{items: [...]}` into the plain array.
3. Merge `prev/sources/tm.json` and any `tm-N.json` shards (each `{items: [{en, he}]}`) into `data/tm.json` as one `{english: hebrew}` object. This is the Hebrew translation memory.
4. Copy `prev/sources/toolchecks.json` (the weekly browser check, see BROWSER-CHECK.md) to `data/toolchecks.json` if it exists.
5. Copy `prev/snapshot/favicons.json`, taking its `icons` object, to `data/favicons.json` if it exists.
6. Copy `prev/snapshot/dataforseo.json` to `data/dfs_prev.json` and its `balanceHistory` array to `data/dfs_balance.json`, if it exists. The build adds this run's balance to the series and keeps the spend analysis in place.

## 1. Tools sheet → `data/tools.csv`

1. Call `Google_Drive.download_file_content` with fileId `1NhlhJMoLFvQws1Bzim9iDHCJghsQUEhcXBngqj2FnBU` and exportMimeType `text/csv`. This exports the first tab, "💻 Tools Database".
2. Base64-decode `content` and save it as `data/tools.csv`.
3. Also read the "Changes Done (Log)" tab with `read_file_content`. Mention any new log entry in the briefing.

## 2. Live tool checks → `data/livechecks.json`

**DataForSEO.** Call `DataForSEO.api_request` with GET `/v3/appendix/user_data` and `noAiMode: true`. The output is large, so save it to a file and parse it.

- `money.balance` is what's left and `money.total` is the total deposited.
- `money.statistics.day.total` is today's spend.
- Runway in days = balance / max(today's spend, 1).
- status: `critical` if runway < 14 days or balance < 25; `low` if runway < 30 days; otherwise `ok`.

**Peec.** Usage is shown through SurgeOS (`get_peec_trend` for a Peec-connected client). Note it only if a sync stopped.

Also record `deposited` (`money.total`), `spentToday` and `runwayDays` on the DataForSEO check. The build appends each run's balance to the balance series on the Tools tab and raises the runway alert (high under 7 days, medium under 14, using the 30-day average from the spend analysis). The budget is not capped, so a low balance means "top up and check what is running", not "stop".

**DataForSEO spend analysis (weekly, Sunday's first run).** Rebuild `data/dataforseo_usage.json` from the free `GET /v3/<api>/id_list` endpoints, following `scripts/dataforseo/README.md`. It takes a long time (hundreds of paged calls), so hand it to a background agent and carry on with the refresh; if it hasn't finished, the build reuses the previous analysis (`data/dfs_prev.json`). Never call a paid endpoint for this.

Write each check as `{tool, metric, value, unit, status, headline, detail, checkedAt, method}`. `tool` must equal the Name in the sheet, for example "DataForSEO API".

Tools with no API or connector (Ahrefs, SE Ranking, Claude seats and the rest) are covered by the weekly browser check on the owner's computer (BROWSER-CHECK.md). It writes `sources/toolchecks` itself. If that document is missing or older than `meta/state.updatedAt`, also look in Drive for a Doc titled `Control Room tool checks`, and use its JSON as `data/toolchecks.json`. Don't guess usage.

**Favicons.** Run `python3 scripts/fetch_favicons.py`. It fetches only domains that are missing. It needs network access to www.google.com; if that is blocked it reports the failures, and the page keeps showing letter tiles.

## 3. Performance → `data/performance.json`

SurgeOS, read-only:

1. Get `portfolio_overview` for w7, w28 and w90.
2. For each client whose w28 clicks fell 10% or more, or whose position worsened by 1.5 or more, find the driver. Use `gsc_timeseries` with `compare: previous_year`, then `gsc_breakdown` or `search_gsc_pages` sorted by `clicksDelta`. Check `get_annotations` for known causes.
3. Get `get_okrs`, plus `get_tasks` for the current sprint and its overdue items.
4. For each client, record `spark28`, the last 28 daily clicks from `gsc_timeseries` with granularity daily.

Shape of each client entry:

```
{client, surgeosId, domain, w7, w28, w90, spark28, health, headline, alerts[], wins[], okrs[], openTasks, overdueTasks, hoursUsed, hoursBudget}
```

- `w7`, `w28` and `w90` are `{clicks, clicksChangePct, impressions, impressionsChangePct, position, prevPosition}`.
- `health` is `good`, `watch` or `risk`.
- Each alert is `{severity: high|medium|low, title, detail, metric}`.

Check year over year before calling an Israeli client's drop real, because of Jewish-holiday dips. Respect the `dataNotes` each result carries.

## 4. Client brains → `data/brains.json` (incremental)

Brains are markdown files in each client's `00. AI Brain` folder: the `AGENTS.md` hub, `context/active-workstreams`, `context/decisions-log`, `daily-log/` and `OPEN-ITEMS`. The company brain registry, `context/clients.md` in the Cut Inside brain, lists every client brain.

1. Search Drive for brain files modified since `meta/state.updatedAt`, with the query `modifiedTime > '<updatedAt>' and (title contains 'AGENTS' or title contains 'daily-log' or title contains 'decisions' or title contains 'workstreams' or title contains 'OPEN-ITEMS')`. Re-read only the brains that changed.
2. Look for new `00. AI Brain` folders, which mean a new client brain.
3. Per client, keep:

```
{client, displayName, surgeosClients[], driveFolderUrl, brainFolderUrl, brainDocs[], summary, services[], keyFacts[], issues[{severity,title,detail,source}], upcoming[], contacts[], lastBrainUpdate}
```

4. Drop issues the brain marks as resolved. Write everything in English.

## 4b. Client meetings → `data/meetings/<key>.json` (incremental)

Each client has a file holding these fields:
- `lastMeeting`
- `relationship {mood, why}`
- `meetings[]`, newest first, at most 6 from the last ~45 days; each is `{date, title, type, attendees, summary, decisions, followUps, sentiment, source, url}`
- `themes[]`, `highlights[]`
- `tm`, a map from each English string to its Hebrew

The previous state is in `sources/meetings`. Copy it to `data/meetings/` in step 0.

1. Look for new meetings since the last run:
   - Drive meeting transcripts and notes: "Transcript:", Gemini notes, Timeless notes, "סיכום", "פגישה", searched with `modifiedTime > last run`;
   - new daily-log entries in the client brains;
   - Google Calendar events from the last 2 days.
   Also save the next 7 days of calendar events as `data/calendar.json`, a list of `{start, end, title, attendees: [emails], url}` (`url` is the event's `htmlLink`). The build matches them to clients by attendee domain or client name, adds the dated meeting items from each brain's `upcoming` list, and shows the result as **Client meetings this week** on the overview.
2. For each client that had a meeting, add it to `meetings` and drop the oldest past 6. Refresh `themes`, `highlights` and `relationship` if the meeting changed them.
3. Add Hebrew for every new string to `tm`. Read only: never edit Drive, Calendar or Gmail.

## 5. Contracts → `data/contracts.json` (incremental)

1. **Drive.** Search for new or changed agreements since the last run. Search titles and full text for: contract, agreement, SOW, addendum, renewal, PO, הסכם, חוזה, תוספת, הצעת מחיר, signed.
2. **Gmail (read only).** Search messages since the last run for:
   - signature completions: "PandaDoc" "completed", "DocuSign" "Completed", "signed", "נחתם";
   - purchase orders and renewals;
   - notice or termination: "terminate", "notice", "הפסקת התקשרות", "סיום".
   Signed versions often exist only as email attachments or links.
3. Read each new item and extract `{client, displayName, title, url, type, startDate, endDate, termMonths, autoRenew, noticeDays, monthlyFee, totalValue, currency, hoursPerMonth, scope, signed, confidence, notes, relationship}`. `relationship` is `active`, `notice_given`, `ended`, `paused` or `pipeline`, and is set only when there is evidence for it.
4. Compute `endDate` from start + term when only the term is given, and say so in `notes`.
5. Keep superseded agreements, and note what replaced them.

## 5b. Source freshness

Write `data/source_status.json` as `{"sheet": "<ISO>", "drive": "<ISO>", "gmail": "<ISO>", "surgeos": "<ISO>", "dataforseo": "<ISO>", "meetings": "<ISO>", "failed": ["<source>", ...]}`. Each value is the time that source was last read successfully. `failed` lists the sources that errored this run. The build appends this run to `meta/state.runs`, which keeps the last 12, and the page shows that history. Use only the sources that actually succeeded this run, and keep the previous value for any that failed. The page shows these times at the bottom of the overview.

## 6. Build

```bash
python3 scripts/build_db.py --versions=prev/versions.json --prev-meta=prev/meta/state.json     # TODAY defaults to the current date
```

- The build writes `out/writes.json`: ArtifactData batch entries pinned with `if_version` from `prev/versions.json`.
- It also writes a delete for any snapshot shard that is no longer needed.
- It never touches `acks/*`, where viewers record which alerts they've acknowledged. Alert ids are stable from run to run, so acknowledgements carry over.

## 6b. Hebrew

The page has an English/Hebrew switch. Content from data (alerts, client headlines, summaries, issues, key facts) shows in Hebrew when its translation is in the memory.

1. After the build, `out/untranslated.json` lists the English strings that have no Hebrew yet. Usually a few per run.
2. Translate them into natural, concise Israeli business Hebrew. Keep names, tools, URLs, file names, numbers and currency exactly as they are, and write dates as "31 בדצמבר 2026".
3. Add them to `data/tm.json` and run the build again. The build keeps only the entries in use and stores them in `sources/tm*`.

## 7. Briefing → `briefing/latest`

Read `out/alerts/*.json` and the client headlines. Write `data/briefing.json` as:

```
{title, text, he: {title, text}, by: "Claude (refresh routine)", generatedAt}
```

- `title` is a short headline of the day.
- `text` is 120–220 words of markdown: the 3–6 things the agency owner must act on today (contracts, client risk, tools and spend), and what changed since the last briefing.
- `he` is the same briefing written in Hebrew.

Then run the build again so the briefing is included (it is written to `briefing/latest`).

## 8. Write

1. Send `out/writes-1.json`, `out/writes-2.json` and so on in order, one `ArtifactData batch` call each, as `writes`. They are already split under the 1 MiB request limit, with snapshot shards first and `meta/state` last.
2. If an entry fails because its version changed, re-list that collection, update `prev/versions.json`, rebuild and resend. Never force a write.

## 9. Report

Finish with a 5-line summary of what changed. If a source failed (a connector needing re-auth, a SurgeOS outage), say which one. The previous data stays in place.
