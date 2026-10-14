---
name: control-room-tool-check
description: Weekly read-only check of Cut Inside's paid tools in the owner's signed-in Chrome (Claude in Chrome). It reads plan, usage, credits, renewal and last activity for each tool, and writes the results to the Control Room dashboard. Use it when asked to run the weekly tool check, or when the scheduled weekly task fires.
---

# Control Room weekly tool check

The Control Room dashboard (https://claude.ai/artifact/5AxMQ4gPXYVmeQWk1Kzq45) tracks Cut Inside's tool subscriptions. Most tools have no API, so once a week this check opens each one in the owner's own Chrome, where they are already signed in, and reads what the account page shows.

## Before you start

1. Load the Claude in Chrome tools. Work in a new tab, and leave the person's other tabs alone.
2. Read the plan from the dashboard database with ArtifactData:
   `get`, url=https://claude.ai/artifact/5AxMQ4gPXYVmeQWk1Kzq45, collection=sources, doc_id=toolchecks.
   - Note the document's `version`.
   - `plan` is the list to check: `{tool, group, account, look}`.
   - `group` is "paid" (read its status) or "verify-cancelled" (confirm nothing will charge again).
   If ArtifactData isn't available here, use the tool list in BROWSER-CHECK.md in the repo.

## Rules (no exceptions)

- **Read only.** Never change a setting, plan, seat or payment method. Never buy credits, upgrade, downgrade, cancel or renew. Never accept a dialog that would.
- **Never type a password, code or card number.** If a tool isn't signed in, or asks for 2FA, record `loginOk: false` and move on.
- If the account shown isn't the one in `account`, say so in `detail`, and don't switch accounts.
- Record only what the page shows. Leave a field out rather than guess it.
- Spend about 2 minutes per tool. If a page won't load, record that and move on.

## For each tool in the plan

1. Open the tool's account, billing, usage or limits page. `look` says what to read.
2. Capture:
   - `plan`;
   - `renewsOn` (YYYY-MM-DD);
   - usage against the limit, in `value` and `unit` (e.g. "412 / 500" credits);
   - seats, if relevant;
   - `lastUsed` (YYYY-MM-DD), the most recent activity or login the tool shows;
   - anything unusual, in `detail`.
3. Set `status`:
   - `critical`: something stops working within 14 days (credits out, expired, payment failed), or a "verify-cancelled" tool is still active and will charge.
   - `low`: under 25% of credits left, or a renewal decision is due within 30 days.
   - `ok`: anything else.
4. Write a one-line `headline` a manager can scan, e.g. "412 of 500 credits used, renews 7 May 2027".

## Write the results

Write the whole document back with ArtifactData `set` to collection=sources, doc_id=toolchecks, with `if_version` equal to the version you read. Keep `plan` as it was.

```json
{
  "checkedAt": "<now, ISO 8601>",
  "plan": [ ...unchanged... ],
  "items": [
    {
      "tool": "<exact Name from the plan>",
      "checkedAt": "...",
      "method": "browser",
      "loginOk": true,
      "plan": "...",
      "renewsOn": "...",
      "lastUsed": "...",
      "value": "...",
      "unit": "...",
      "status": "ok|low|critical",
      "headline": "...",
      "detail": "..."
    }
  ]
}
```

If ArtifactData isn't available, save the same JSON as a Google Doc named `Control Room tool checks` in the owner's Drive. The twice-daily refresh picks it up.

## Finish

Give a short summary: how many tools were checked, which are critical or low, and which failed to load or weren't signed in. The dashboard shows the results right away (Tools → Live checks, and the Usage column).
