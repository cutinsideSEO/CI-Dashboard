---
name: control-room-tool-check
description: Weekly read-only check of Cut Inside's paid tools in the owner's signed-in Chrome (Claude in Chrome), cross-checked against the billing emails in seo@ and or@. It reads plan, real charges, usage, renewal and payment problems for each tool, compares them with the Tools Database sheet, and writes the results to the Control Room dashboard. Use it when asked to run the weekly tool check, or when the scheduled weekly task fires.
---

# Control Room weekly tool check

The Control Room dashboard (https://claude.ai/artifact/5AxMQ4gPXYVmeQWk1Kzq45) tracks Cut Inside's tool subscriptions. Most tools have no API, so once a week this check opens each one in the owner's Chrome, where they are already signed in, reads what the billing page shows, and checks the billing emails. The point is to report what is **really** charged and what is failing, not what the sheet says.

## Before you start

1. Load the Claude in Chrome tools in one ToolSearch call (tabs_context_mcp, tabs_create_mcp, tabs_close_mcp, navigate, computer, find, get_page_text, javascript_tool, browser_batch). Call `tabs_context_mcp` with `createIfEmpty: true` and work in **one** tab. Leave the person's own tabs alone.
2. Read the plan: ArtifactData `get`, url=https://claude.ai/artifact/5AxMQ4gPXYVmeQWk1Kzq45, collection=`sources`, doc_id=`toolchecks`. Note its `version`. `plan` is `{tool, group, account, look}`; `group` is "paid" or "verify-cancelled". Keep the previous `items` in mind: last week's findings are the baseline.
3. Read the sheet values to compare against: ArtifactData `get`, collection=`snapshot`, doc_id=`tools`, with `out_dir` set to a folder inside the repo (not the scratchpad, which is refused), then read the JSON. Each item has `name`, `paying`, `plan`, `yearlyCost`, `monthlyCost`, `frequency`, `nextRenewal`, `autoRenew`, `admin`. Delete that folder when you're done.

## Rules (no exceptions)

- **Read only.** Never change a setting, plan, seat, billing email or payment method. Never buy credits, upgrade, downgrade, cancel or renew. Never accept a dialog that would.
- **Never type a password, 2FA code or card number**, and never approve a "Sign in with Google/GitHub" consent screen. If a tool isn't signed in, record `loginOk: false` and move on.
- Don't switch accounts. If the account shown isn't the one in `account`, say so in `detail`.
- Record only what the page or email shows. Leave a field out rather than guess.
- About 2 minutes per tool. If a page hangs twice, record that and move on.
- Gmail: only read and add labels. Never archive, delete, send, forward or create filters. Opening an email marks it read; if it was unread, click "Mark as unread" afterwards.

## Working in Chrome (what works)

- **One tab, sequentially.** Background tabs freeze (pages never reach idle, scripts time out). Navigate the same tab from tool to tool.
- Read pages with `javascript_tool`: `location.href + '\n' + document.body.innerText.slice(0, 3000)` after `navigate` + a 5-8 second `wait`. Don't put `await new Promise(setTimeout…)` inside the script; wait with the `computer` wait action instead.
- If a click by `ref` times out, take a screenshot and click by coordinate, or click the element from `javascript_tool`.
- Accounts in this Chrome: Google `authuser=0` is or@cutinside.com and `authuser=1` is seo@cutinside.com (use `/u/1/` or `?authuser=seo@cutinside.com`). claude.ai is signed in as or@ only.

## Where to look

| Tool | Page | Notes |
|---|---|---|
| Ahrefs | app.ahrefs.com/account/limits-and-usage/web, then /account/billing (Invoices tab) | Brand Radar prompt checks can exceed the base 300 |
| SE Ranking | online.seranking.com/admin.subscription.html | Sheet says expired Nov 2025, but it still sends reports |
| peec.ai | app.peec.ai/billing | Custom plan; no invoices on the page |
| Claude (or@) | claude.ai/settings/billing, then the Usage tab in the dialog | seo@ and admin@ can't be read here (record loginOk false) |
| ChatGPT | chatgpt.com/settings/billing, /settings/usage, /settings/account | Also check the ChatGPT **Business** workspace (2 seats) in seo@ mail |
| OpenAI API | platform.openai.com/settings/organization/billing/overview (choose "Cut Inside"), /usage | Balance, auto-reload, month's spend |
| Gemini API | aistudio.google.com/u/1/spend and /u/1/billing | Billing account 011FCA-6E1595-BD05B0 |
| Google Workspace | admin.google.com/u/1/ac/billing/subscriptions | Usually asks for the password: record loginOk false, use the emails |
| Slack | cut-inside.slack.com/admin/billing | Price only visible to the owner (Michael) |
| SEOGets | app.seogets.com/account/team/billing; Stripe portal at app.seogets.com/api/team/billing/portal | $50/month from 15 Oct 2026 |
| ElevenLabs | elevenlabs.io/app/subscription; "Billing" → "Manage billing information" opens Stripe | |
| Supabase | supabase.com/dashboard/organizations → org → Billing | Watch the "Outstanding invoices" banner |
| Render | dashboard.render.com/billing | |
| Figma | figma.com/files/team/1456647381995217261/team-admin-console/billing | Watch the "team is locked" banner |
| Miro | miro.com/app/settings/company/3458764611237238483/billing/ | 7 licences; card on file |
| Supermetrics | hub.supermetrics.com | The licence is on the "SEO Department" team; the hub often freezes |
| Nord Account / NordPass | my.nordaccount.com/billing/my-subscriptions/ and /billing/billing-history/ | seo@ has NordVPN Basic only |
| V0 (Vercel) | v0.app/settings/billing | Free plan, but AI credits get bought |
| heygen | app.heygen.com/settings?nav=Plan%20%26%20Billing | |
| Ceyo | platform.ceyo.ai | Stuck in onboarding; don't complete it |
| Glimpse | meetglimpse.com/sign-in/ | |
| Twitter Verification badge | x.com/settings/manage_subscriptions | |
| Canva | canva.com/settings/billing-and-teams | |
| Timeless | my.timeless.day | |
| Screaming Frog | screamingfrog.co.uk/my-account/ | |
| Uptime Robot | dashboard.uptimerobot.com | |
| Monday | auth.monday.com/login | |
| Apollo | app.apollo.io/#/settings/plans | |
| Usercentrics Cookibot | manage.cookiebot.com/en/manage, admin.usercentrics.eu | |
| Rank Tracker (New) | app.ranktracker.com | Product not confirmed with the owner yet |
| Ben Collins / Snagit | courses.benlcollins.com, techsmith.com/signin | One-time purchases: confirm nothing recurs |

## For each tool in the plan

1. Open the billing page. Read the plan, **the actual charges or invoices** (date, amount, currency, card last 4), the next charge, usage against limits, seats, and any warning banner.
2. Compare with the sheet: plan name, cost (yearly or monthly), renewal date, paying / auto-renew. Write every difference in `gap` (one line, e.g. "Pays €890/mo; sheet: $997/mo Pro Workspace").
3. Fill the item:
   - `plan`, `renewsOn` (YYYY-MM-DD), `value` + `unit` (e.g. "412 / 500", "credits"), `lastUsed` (YYYY-MM-DD) if shown;
   - `lastCharge`: `{amount, date}` when an invoice or receipt shows one;
   - `loginOk`, `headline` (one line a manager can scan), `detail` (what you saw, and where), `gap`.
4. `status`:
   - `critical`: a payment failed or is past due, an account is locked or will shut down, something stops within 14 days, or a "verify-cancelled" tool is still charging;
   - `low`: under 25% of credits left, a renewal decision within 30 days, a charge from a tool that isn't in the sheet, or a card on file that is failing elsewhere;
   - `ok`: anything else. Leave `status` out when the tool wasn't signed in.

## Email pass (after the browser pass)

1. **seo@ Gmail**, in the same tab: mail.google.com/mail/u/1/. Labels `Receipts`, `Receipts/<Vendor>` and `Receipts/Payment problems` are kept up to date by Gmail filters.
   - Search `label:receipts-payment-problems newer_than:8d`. Every hit is a payment problem: note the vendor, date, amount and card.
   - Search `label:receipts newer_than:8d` for new charges. To read an amount, open the email, read `div.a3s` text, then mark it unread again if it was unread.
   - A charge from a vendor that isn't in the plan gets its own item with `method: "email"` (examples so far: ChatGPT Business, TypeSafe AI, AWS, GoDaddy).
   - If a vendor sends receipts that no label caught, say so in the summary (don't create filters).
2. **or@ Gmail** through the Gmail connector (it is or@'s mailbox): search receipts and payment problems from the last 8 days (Anthropic, Google Cloud, Timeless) and add the matching `Receipts/<Vendor>` label to new threads.
3. **Cards:** list every card that failed anywhere this week (last 4 digits) and the tools still charging it.

Put email evidence into the tool's item (`detail`, `lastCharge`, `status`) and set `method` to `"browser+email"`. The dashboard keeps only the last item per tool name, so write one item per tool.

## Write the results

ArtifactData `set`, collection=`sources`, doc_id=`toolchecks`, `if_version` = the version you read (build the JSON in a file and pass `file_path`). Keep `plan` exactly as it was, and keep `emailCheckedAt` and `note` if present.

```json
{
  "checkedAt": "<now, ISO 8601>",
  "plan": [ "...unchanged..." ],
  "items": [
    {
      "tool": "<exact name from the plan, or the vendor name for tools not in the plan>",
      "checkedAt": "...",
      "method": "browser | email | browser+email",
      "loginOk": true,
      "plan": "...",
      "renewsOn": "YYYY-MM-DD",
      "lastUsed": "YYYY-MM-DD",
      "lastCharge": {"amount": "$20.88", "date": "YYYY-MM-DD"},
      "value": "...",
      "unit": "...",
      "status": "ok | low | critical",
      "headline": "...",
      "detail": "...",
      "gap": "difference from the sheet, if any"
    }
  ]
}
```

If ArtifactData isn't available, save the same JSON as a Google Doc named `Control Room tool checks` in the owner's Drive.

## Finish

Close the tab you opened. Then give a short summary in Hebrew:
1. Payment problems first (vendor, amount, card), then other critical and low items.
2. Gaps between the sheet and reality, as a table.
3. **Sign-ins needed**, grouped by account (seo@, michael@, yuval@, Aviv, Shalom…), so the owner can sign in to all of them in one go. Offer to open those login pages in one tab group.
