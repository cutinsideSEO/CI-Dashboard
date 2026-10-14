# Weekly tool check in the browser

Most tools in the Tools Database have no API this project can reach. Once a week, Claude in Chrome opens each one in the owner's own signed-in browser and reads its plan, usage, credits and last activity. The Control Room shows the results under **Tools → Live checks** and in the **Usage** column, and raises alerts for low credits or failed logins.

This runs on the owner's computer, in the Claude desktop app with Claude in Chrome. The cloud session that refreshes the dashboard has no browser with those logins.

## Set it up once (about 3 minutes)

1. On your computer, open the Claude desktop app. Make sure Claude in Chrome is connected, and that Chrome is signed in to the tools.
2. Open the Control Room, go to **Tools → Weekly browser check** and click **Copy the task prompt**.
3. In the desktop app, create a scheduled task that runs weekly (for example Sunday 08:00) and paste the prompt.
4. Run it once now to check that it works. Results show up straight away in the same card and in the **Usage** column.

The list of tools to check lives in the dashboard database (`sources/toolchecks` → `plan`), built from the Tools Database sheet:
- **30 paid tools** to read;
- **5 tools to confirm cancelled:** Glimpse, V0, heygen, Ceyo and Canva are marked "not paying" in the sheet but still have auto-renew on.

The full procedure is in `.claude/skills/control-room-tool-check/SKILL.md`.

## Rules

- **Read only.** Never change a setting, plan or seat, never buy credits, never cancel anything, and never accept a prompt that does.
- **Never type a password or 2FA code.** If a tool isn't signed in, record `loginOk: false` and move on.
- **Write down only what the page shows.** Leave a field out rather than guess it.
- Take about 2 minutes per tool. If a page won't load, record that and move on.

## Tools to check

The list is the paid tools in the "💻 Tools Database" tab of the sheet ("Are we currently paying for it?" = TRUE). The account to use is in the **Admin** column. For each one, open its billing, subscription, usage or limits page.

| Tool | What to read |
|---|---|
| Ahrefs (seo@cutinside.com) | Plan, renewal date, credits or rows used and the limit for this period, users |
| SE Ranking | Is the subscription still active? (The sheet says it expired on 26 Nov 2025.) Plan, renewal date, checks used and the limit |
| peec.ai | Plan, prompts used of 100, renewal date |
| Claude (seo@, admin@, or@) | Plan per seat (Max x20), renewal date, usage limit status |
| ChatGPT, Figma, Slack, Monday, Miro, Apollo | Plan, seats, next charge date, last activity |
| Supabase, Render | Current month's usage and cost, plan, any usage warnings |
| ElevenLabs | Characters used and the limit, renewal date (the 11th of each month) |
| Supermetrics, SEOGets, Rank Tracker, Uptime Robot | Plan, renewal date, limits |
| OpenAI API, Gemini API | Credit balance, this month's spend, auto-recharge on or off |
| Timeless, Usercentrics Cookiebot, Twitter | Is it active or expired? (Timeless and Cookiebot are past their expiry date in the sheet.) |
| Google Workspace | Number of licences, next charge |

DataForSEO is already checked twice a day through its API, so skip it.

## Result format

Write one document, `sources/toolchecks`, in the artifact's database:

```json
{
  "checkedAt": "2026-10-18T06:00:00Z",
  "items": [
    {
      "tool": "Ahrefs",
      "checkedAt": "2026-10-18T06:02:00Z",
      "method": "browser",
      "loginOk": true,
      "plan": "Standard",
      "renewsOn": "2027-05-07",
      "lastUsed": "2026-10-17",
      "value": "412 / 500",
      "unit": "credits",
      "status": "ok",
      "headline": "412 of 500 credits used, renews 7 May 2027",
      "detail": "Anything unusual, in one or two sentences."
    }
  ]
}
```

- `tool` must equal the **Name** in the sheet exactly.
- `status` is `critical` when something will stop working within 14 days (credits running out, expired, payment failed). It is `low` when credits are under 25% or there's a renewal decision within 30 days. Otherwise it is `ok`.
- `lastUsed` is the most recent activity or login the tool shows. Leave it out if the tool doesn't show one.

**How to save it, in order of preference:**

1. **ArtifactData.** Read `sources/toolchecks` first (`get`). Then `set` the whole document with `if_version` equal to the version you read, or with no `if_version` if the document doesn't exist yet.
2. **Google Drive.** If ArtifactData isn't available, save the JSON as a Google Doc named `Control Room tool checks` in your Drive. The twice-daily refresh picks it up.

The dashboard shows the results as soon as they're written. The next refresh then adds the alerts.
