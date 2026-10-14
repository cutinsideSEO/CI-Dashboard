# DataForSEO spend analysis

Rebuilds `data/dataforseo_usage.json`: what Cut Inside spent on DataForSEO, by day, month, API, endpoint, client and tag. The Control Room shows it under **Tools → DataForSEO spend**. Use **only free endpoints**:

- `GET /v3/appendix/user_data`: balance (`money.balance`), total deposited (`money.total`), today's spend (`money.statistics.day.total`).
- `POST /v3/<api>/id_list` for each API (serp, keywords_data, dataforseo_labs, ai_optimization, on_page, business_data, backlinks, content_analysis, merchant, app_data, domain_analytics): one row per task with `datetime_posted`, `cost` and `url`. It reaches back 6 months; `include_metadata: true` (keyword, location, tag) only works for the last month. Each call is limited to 1,000 rows, so page with `offset` inside time windows small enough to stay under the offset limit (busy SERP days need windows of an hour or less). Keep to about 10 calls a minute.

## How the scripts fit together

Run them from this folder with `DFS_DIR` set to a work directory (raw pages go to `$DFS_DIR/raw`) and `DFS_TOOL_RESULTS` set to the folder where the session saves large tool outputs.

1. Call `id_list` through the DataForSEO connector; each result lands in `DFS_TOOL_RESULTS`. `ingest_all.py` copies new `id_list` results into `$DFS_DIR/raw` with a name that encodes api, window and offset, and paces the calls.
2. `load.py` merges all raw pages and dedupes rows by `(api, id, datetime_posted)`.
3. `analyze.py` builds daily and monthly totals (net of refunds), the last-30-day breakdowns, duplicates (the same request on the same day), spikes (days above twice the 30-day median) and client attribution (`seeds.py` holds the client domains, brand terms and SurgeOS project tags).
4. `write.py` checks the total against `user_data` (today's id_list charges must equal `money.statistics.day.total`) and writes the JSON. Its findings text was written for the 14 Oct 2026 run: update the numbers and wording each time.

Output shape (read by `scripts/build_db.py`): `asOf`, `account`, `coverage`, `daily[]`, `monthly[]`, `runRate {avg7, avg30, projectedMonth, octoberToDate}`, `last30 {total, byEndpoint, byClient, byTag, byLocation, topTargets, duplicates}`, `spikes[]`, `findings[]`.
