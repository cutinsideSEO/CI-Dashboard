# Cut Inside Control Room

The agency's operations dashboard, published as a Claude artifact:
https://claude.ai/artifact/5AxMQ4gPXYVmeQWk1Kzq45

## What it shows

| Area | Source | What it flags |
|---|---|---|
| Client brains | `00. AI Brain` / `02. Strategy & Brain` folders in each client's Drive folder | Risks, blockers, dissatisfaction, deadlines from the brain docs |
| Contracts | Client agreements, SOWs and quotes in Google Drive | Contracts ending within 30/90/120 days, expired contracts, notice deadlines, clients with no contract on file |
| Performance | SurgeOS (Search Console BigQuery mirror, GA4, Peec, tasks, OKRs) | Click/impression drops and their drivers, OKRs off track, overdue tasks |
| Tools | [Cut Inside's Tools Database](https://docs.google.com/spreadsheets/d/1NhlhJMoLFvQws1Bzim9iDHCJghsQUEhcXBngqj2FnBU/edit) sheet plus live API checks | Renewals within 45 days, lapsed subscriptions still marked as paying, cancelled tools with auto-renew still on, low credit balances |

The **Ask Opus** tab sends questions to Claude Opus along with the dashboard data. When it needs more, it can look things up live in SurgeOS and Google Drive, using the viewer's own connectors.

## How it updates

The "Control Room refresh" routine (`trig_01WDH93AGHQEqNsCiNghRytm`) runs twice a day at 06:56 and 14:56 Israel time and follows [REFRESH.md](REFRESH.md):

1. It re-reads the sources (the tools sheet, Drive brains and contracts, SurgeOS, live tool checks).
2. `scripts/build_db.py` merges them into documents and computes the alerts.
3. It writes those documents to the artifact's database, along with a fresh executive briefing.

The page itself never changes. Data lives in the artifact database: `meta/state`, `briefing/latest`, `snapshot/{clients,contracts,tools,alerts}` and `sources/*`. Acknowledgements live in `acks` and are kept across refreshes.

## Design and language

The page follows the [Cut Inside design system](https://claude.ai/artifact/KtDR5tusYbobTc3GPFATnN):
- dark brand ground with a light theme, one teal accent, Familjen Grotesk for headlines and numbers, and Montserrat for copy;
- pill buttons and tabs, and the official lockup logos in `assets/`.

The **עברית / English** button switches the whole interface, including right-to-left layout. Data content (briefing, alerts, client summaries and issues) comes from a Hebrew translation memory that the refresh routine keeps up to date (`sources/tm` in the database).

Edit `src/dashboard.src.html`, then run `python3 scripts/build_page.py`. That inlines the logos into `dashboard.html`, the published file.

## Local build

```bash
# put tools.csv, brains.json, contracts.json, performance.json, livechecks.json in data/
python3 scripts/build_db.py          # writes out/<collection>/<id>.json and out/batches/*.json
```

`data/` and `out/` are git-ignored because they contain client data.
