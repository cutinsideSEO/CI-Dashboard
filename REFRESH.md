# Control Room refresh runbook

This is what the twice-daily routine does. A person can follow it too. It is read-only towards every source (Drive, SurgeOS, the tools sheet). The only thing it writes is the dashboard's own artifact database.

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

Write each check as `{tool, metric, value, unit, status, headline, detail, checkedAt, method}`. `tool` must equal the Name in the sheet, for example "DataForSEO API".

Tools with no API or connector (Ahrefs, SE Ranking, Screaming Frog, Claude seats and the rest) are not checked live. Don't guess their usage.

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

## 5. Contracts → `data/contracts.json` (incremental)

1. Search Drive for new or changed agreements since the last run. Search titles and full text for: contract, agreement, SOW, הסכם, חוזה, הצעת מחיר, signed.
2. Read each one and extract:

```
{client, displayName, title, url, type, startDate, endDate, termMonths, autoRenew, noticeDays, monthlyFee, totalValue, currency, hoursPerMonth, scope, signed, confidence, notes}
```

3. Compute `endDate` from start + term when only the term is given, and say so in `notes`.

## 6. Build

```bash
python3 scripts/build_db.py --versions=prev/versions.json     # TODAY defaults to the current date
```

- The build writes `out/writes.json`: ArtifactData batch entries pinned with `if_version` from `prev/versions.json`.
- It also writes a delete for any snapshot shard that is no longer needed.
- It never touches `acks/*`, where viewers record which alerts they've acknowledged. Alert ids are stable from run to run, so acknowledgements carry over.

## 7. Briefing → `briefing/latest`

Read `out/alerts/*.json` and the client headlines. Write `data/briefing.json` as:

```
{title, text, by: "Claude (refresh routine)", generatedAt}
```

- `title` is a short headline of the day.
- `text` is 120–220 words of markdown: the 3–6 things the agency owner must act on today (contracts, client risk, tools and spend), and what changed since the last briefing.

Then run the build again so the briefing is included (it is written to `briefing/latest`).

## 8. Write

1. Send everything in `out/writes.json` in one `ArtifactData batch` call, as `writes`. Split it if it has more than 50 entries.
2. If an entry fails because its version changed, re-list that collection, update `prev/versions.json`, rebuild and resend. Never force a write.

## 9. Report

Finish with a 5-line summary of what changed. If a source failed (a connector needing re-auth, a SurgeOS outage), say which one. The previous data stays in place.
