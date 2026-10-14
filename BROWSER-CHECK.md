# Weekly tool check in the browser

Most tools in the Tools Database have no API this project can reach. Once a week, Claude in Chrome opens each one in the owner's own signed-in browser and reads its plan, usage, credits and last activity. The Control Room shows the results under **Tools → Live checks** and in the **Usage** column, and raises alerts for low credits or failed logins.

This runs on the owner's computer, in the Claude desktop app with Claude in Chrome. The cloud session that refreshes the dashboard has no browser with those logins.

## How it runs

A scheduled task in the Claude desktop app, **"בדיקת כלים שבועית – Control Room"**, runs every Sunday at 08:00 on the owner's computer. It reads `.claude/skills/control-room-tool-check/SKILL.md` from this folder and follows it. The app must be open, with Claude in Chrome connected; if the app is closed at 08:00, the task runs the next time it opens.

Besides the billing pages, it checks the billing emails:
- **seo@cutinside.com**, in Chrome. Most tool receipts arrive here. Gmail filters label them `Receipts/<Vendor>` and `Receipts/Payment problems`.
- **or@cutinside.com**, through the Gmail connector (Anthropic, Google Cloud, Timeless).

Each run ends with a list of the tools that need signing in, grouped by account, so the owner can sign in to all of them in one go. Sessions with "stay signed in" usually last for weeks.

To run it by hand, open the task in the desktop app and click **Run now**.

The list of tools to check lives in the dashboard database (`sources/toolchecks` → `plan`), built from the Tools Database sheet:
- **30 paid tools** to read;
- **5 tools to confirm cancelled:** Glimpse, V0, heygen, Ceyo and Canva are marked "not paying" in the sheet but still have auto-renew on.

The full procedure is in `.claude/skills/control-room-tool-check/SKILL.md`.

## Rules

- **Read only.** Never change a setting, plan or seat, never buy credits, never cancel anything, and never accept a prompt that does.
- **Never type a password or 2FA code**, and never approve a Google or GitHub sign-in consent. If a tool isn't signed in, record `loginOk: false` and move on.
- **Report what is really charged.** Read the invoices or receipts, not just the plan name, and write any difference from the sheet in `gap`.
- **Write down only what the page or email shows.** Leave a field out rather than guess it.
- Take about 2 minutes per tool. If a page won't load, record that and move on.
- Work in one browser tab. Background tabs freeze.

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
      "method": "browser+email",
      "loginOk": true,
      "plan": "Standard",
      "renewsOn": "2027-05-07",
      "lastUsed": "2026-10-17",
      "lastCharge": {"amount": "$2,490.00", "date": "2026-05-07"},
      "value": "412 / 500",
      "unit": "credits",
      "status": "ok",
      "headline": "412 of 500 credits used, renews 7 May 2027",
      "detail": "Anything unusual, in one or two sentences.",
      "gap": "Difference from the sheet, if any."
    }
  ]
}
```

- `tool` must equal the **Name** in the sheet exactly. A charge from a tool that isn't in the sheet gets its own item, named after the vendor, with `method: "email"`.
- One item per tool: the dashboard keeps only the last item with a given name.
- `status` is `critical` when a payment failed or is past due, an account is locked, or something will stop working within 14 days. It is `low` when credits are under 25%, there's a renewal decision within 30 days, or a tool that isn't in the sheet is charging. Otherwise it is `ok`.
- `lastUsed` is the most recent activity or login the tool shows. Leave it out if the tool doesn't show one.

**How to save it, in order of preference:**

1. **ArtifactData.** Read `sources/toolchecks` first (`get`). Then `set` the whole document with `if_version` equal to the version you read, or with no `if_version` if the document doesn't exist yet.
2. **Google Drive.** If ArtifactData isn't available, save the JSON as a Google Doc named `Control Room tool checks` in your Drive. The twice-daily refresh picks it up.

The dashboard shows the results as soon as they're written. The next refresh then adds the alerts.
