#!/usr/bin/env python3
"""Merge the dashboard's sources into Artifact database documents.

Inputs (in DATA_DIR, default ./data):
  tools.csv         CSV export of the "Tools Database" tab of Cut Inside's Tools Database sheet
  brains.json       client brain extracts from Google Drive (see REFRESH.md for the shape)
  contracts.json    client contracts found in Google Drive
  performance.json  SurgeOS performance snapshot + per-client alerts
  livechecks.json   live tool checks (DataForSEO balance, etc.)
  briefing.json     optional executive briefing {text, highlights}

Output (in OUT_DIR, default ./out): docs/<collection>__<doc_id>.json and
writes.json, a list of ArtifactData "batch" entries (op, collection, doc_id,
file_path, if_version). Pass --versions=<file.json | "col/doc:3,col/doc:1">
with the versions read just before writing so existing documents are pinned.

Database layout: meta/state, briefing/latest, snapshot/{clients,contracts,
tools,alerts}[-N] as {items: [...]}, sources/{brains,contracts,performance}.
acks/* belongs to viewers and is never written here.
"""
import csv
import datetime as dt
import json
import os
import re
import sys

DATA = os.environ.get("DATA_DIR", "data")
OUT = os.environ.get("OUT_DIR", "out")
TODAY = dt.date.fromisoformat(os.environ.get("TODAY", dt.date.today().isoformat()))
NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

# SurgeOS projects that are not clients.
NOT_CLIENTS = {"Sole & Stride", "Training - Maya", "Yarden Training", "CI"}

DISPLAY = {
    "BOG": "Bits of Gold", "MO": "Moroccanoil", "WD": "Western Digital", "NLI": "National Library of Israel",
    "drushim-il": "Drushim", "Pro": "Pro.co.il", "SANDISK": "SanDisk", "IDI": "Israel Democracy Institute",
    "PAC": "PAC", "babli": "Babli", "bestie": "Bestie", "Sapir": "Sapir College",
}


def load(name, default):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def slug(s):
    s = re.sub(r"[^A-Za-z0-9]+", "-", str(s).strip().lower()).strip("-")
    return s[:80] or "x"


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def money(s):
    s = str(s or "").replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def ddmmyyyy(s):
    s = str(s or "").strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if not m:
        return None
    try:
        return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def iso(s):
    try:
        return dt.date.fromisoformat(str(s)[:10]) if s else None
    except ValueError:
        return None


def add_months(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    y += d.year
    m += 1
    last = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return dt.date(y, m, min(d.day, last))


def truthy(s):
    return str(s).strip().upper() == "TRUE"


alerts = {}

# Hebrew: a translation memory {english: hebrew} kept in data/tm.json. Strings missing from it are
# written to out/untranslated.json for the refresh routine to translate; the pruned memory is stored
# back in the database (sources/tm*) so the next run starts from it.
TM = {}
TM_USED = {}
MISSING = set()


def he(s):
    if not s or not isinstance(s, str):
        return s
    if s in TM:
        TM_USED[s] = TM[s]
        return TM[s]
    MISSING.add(s)
    return None


def he_list(xs):
    out = [he(x) for x in (xs or [])]
    return out if all(out) else None


def alert(aid, severity, category, title, detail, client=None, due=None, source=None, source_url=None):
    aid = slug(aid)
    alerts[aid] = {
        "severity": severity, "category": category, "title": title, "detail": detail,
        "client": client, "dueDate": due.isoformat() if isinstance(due, dt.date) else due,
        "source": source, "sourceUrl": source_url, "createdAt": NOW,
    }


# ---------------------------------------------------------------- tools
def build_tools():
    path = os.path.join(DATA, "tools.csv")
    tools = {}
    if not os.path.exists(path):
        return tools
    rows = list(csv.reader(open(path, encoding="utf-8")))
    hdr_i = next(i for i, r in enumerate(rows) if r and r[0].strip() == "Name")
    hdr = rows[hdr_i]
    live = {slug(x.get("tool")): x for x in load("livechecks.json", [])}
    # weekly browser checks (Claude in Chrome on the owner's machine) write sources/toolchecks
    tc = load("toolchecks.json", {})
    browser = {slug(x.get("tool")): x for x in (tc.get("items", []) if isinstance(tc, dict) else tc)}
    for r in rows[hdr_i + 1:]:
        if not r or not r[0].strip():
            continue
        d = dict(zip(hdr, r))
        name = d["Name"].strip()
        tid = slug(name)
        paying = truthy(d.get("Are we currently paying for it?"))
        auto = truthy(d.get("Auto Renewal?"))
        freq = d.get("Payment Frequency", "").strip()
        expires = ddmmyyyy(d.get("Expires On"))
        yearly, monthly = money(d.get("Yearly Cost")), money(d.get("Monthly Cost"))
        notes = d.get("Notes / Desc.", "").strip()
        nxt, stale = expires, False
        if paying and expires and expires < TODAY and auto:
            step = 1 if freq.startswith("Monthly") else 12
            while nxt < TODAY:
                nxt = add_months(nxt, step)
            stale = True
        days = (nxt - TODAY).days if nxt else None
        t = {
            "name": name, "vendor": d.get("Company / Developer", "").strip() or None,
            "group": d.get("Group", "").strip() or None, "function": d.get("Main Function", "").strip() or None,
            "paying": paying, "yearlyCost": yearly, "monthlyCost": monthly, "frequency": freq or None,
            "model": d.get("Payment Model", "").strip() or None, "usedBy": d.get("Used By", "").strip() or None,
            "admin": d.get("Admin", "").strip() or None, "sheetExpires": expires.isoformat() if expires else None,
            "nextRenewal": nxt.isoformat() if nxt else None, "daysToRenewal": days, "renewalDateStale": stale,
            "autoRenew": auto, "plan": d.get("Plan Name", "").strip() or None, "notes": notes or None,
            "learningHub": d.get("Tool Learning Hub", "").strip() or None,
            "live": live.get(tid), "browserCheck": browser.get(tid),
        }
        tools[tid] = t
        cost = f"${yearly:,.0f}/yr" if yearly else "cost not set"
        src = "Tools Database sheet"
        if paying and expires and expires < TODAY and not auto:
            alert(f"tool-{tid}-expired", "high" if yearly else "low", "tools", f"{name}: expired {expires:%d %b %Y} but still marked as paying",
                  f"Auto-renew is off, so the subscription has lapsed or the sheet is out of date. Confirm with {t['admin'] or 'the admin'} and update the sheet ({cost}).",
                  due=expires, source=src)
        elif paying and days is not None and days <= 45:
            sev = "high" if days <= 7 or not auto else "medium"
            what = "renews automatically" if auto else "expires (auto-renew OFF)"
            alert(f"tool-{tid}-renewal", sev, "tools", f"{name} {what} on {nxt:%d %b %Y}",
                  f"{cost} · admin {t['admin'] or 'n/a'}. Decide: renew, downgrade or cancel.", due=nxt, source=src)
        if paying and stale and freq.startswith("Yearly"):
            alert(f"tool-{tid}-stale", "low", "tools", f"{name}: sheet still shows the {expires:%d %b %Y} expiry",
                  f"It auto-renews yearly, so the next renewal should be {nxt:%d %b %Y}. Update the sheet so renewals stay accurate.", due=nxt, source=src)
        if not paying and auto and (yearly or monthly):
            alert(f"tool-{tid}-autorenew-on", "medium", "tools", f"{name}: marked not paying, but auto-renew is still ON",
                  f"Notes: {notes or 'none'}. Confirm the subscription is cancelled at the vendor so it does not charge again.", source=src)
        if "not clear" in notes.lower() or "will be charged" in notes.lower():
            alert(f"tool-{tid}-billing-unclear", "low", "tools", f"{name}: billing behaviour unclear", notes, source=src)
        bc = t["browserCheck"] or {}
        if bc.get("status") in ("low", "critical") or bc.get("loginOk") is False:
            alert(f"tool-{tid}-browser", "high" if bc.get("status") == "critical" else "medium", "tools",
                  f"{name}: {bc.get('headline') or ('login failed' if bc.get('loginOk') is False else 'needs attention')}",
                  bc.get("detail") or "", source="Weekly browser check")
        lv = t["live"] or {}
        if lv.get("status") in ("low", "critical"):
            alert(f"tool-{tid}-live", "high" if lv["status"] == "critical" else "medium", "tools",
                  f"{name}: {lv.get('headline') or 'low balance'}", lv.get("detail") or "", source="Live check")
    return tools


# ---------------------------------------------------------------- clients
def match_key(name, keys):
    n = norm(name)
    for k in keys:
        if norm(k) == n:
            return k
    for k in keys:
        nk = norm(k)
        if nk and (nk in n or n in nk) and min(len(nk), len(n)) >= 3:
            return k
    for k, disp in DISPLAY.items():
        if k in keys and (norm(disp) == n or norm(disp) in n):
            return k
    return None


def build():
    os.makedirs(OUT, exist_ok=True)
    tm = load("tm.json", {})
    TM.update(tm.get("items", tm) if isinstance(tm, dict) else {})
    # client intelligence: recent meetings, themes, highlights (data/meetings/<key>.json, one per client)
    intel = {}
    mdir = os.path.join(DATA, "meetings")
    if os.path.isdir(mdir):
        for fn in sorted(os.listdir(mdir)):
            if fn.endswith(".json"):
                m = json.load(open(os.path.join(mdir, fn), encoding="utf-8"))
                TM.update(m.pop("tm", {}) or {})
                # "last meeting" counts client-facing meetings only
                cm = [x.get("date") for x in m.get("meetings") or [] if x.get("type") != "internal" and x.get("date")]
                m["lastMeeting"] = max(cm) if cm else None
                intel[m.get("client") or fn[:-5]] = m
    # Slack (read-only): per-client channel activity, open client asks, mood; team news (data/slack.json)
    slack = load("slack.json", {}) or {}
    TM.update(slack.pop("tm", {}) or {})
    disp_of = {b.get("client"): b.get("displayName") for b in (load("brains.json", []) or []) if isinstance(b, dict)}
    slack_by_client = {}
    for ch in slack.get("channels") or []:
        k = ch.get("client")
        if not k:
            continue
        roll = slack_by_client.setdefault(k, dict((slack.get("clients") or {}).get(k) or {}, channels=[]))
        roll["channels"].append({x: ch.get(x) for x in ("id", "name", "kind", "lastMessageAt", "lastClientMessageAt", "messages30d", "summary", "highlights", "openAsks", "mood", "moodWhy")})
        for ask in ch.get("openAsks") or []:
            d0 = iso(ask.get("date"))
            age = (TODAY - d0).days if d0 else 0
            nm = disp_of.get(k) or k
            short = ask["ask"] if len(ask["ask"]) <= 90 else ask["ask"][:88].rsplit(" ", 1)[0] + "…"
            st = {"answered-no-delivery": ("acknowledged, not delivered", "אושר, טרם נמסר"), "unanswered": ("no reply yet", "עדיין אין תשובה"),
                  "in progress": ("in progress", "בטיפול")}.get(ask.get("status"), (ask.get("status") or "open", ask.get("status") or "פתוח"))
            title = f"{nm}: Slack ask from {ask.get('from', 'the client')}: {short}"
            detail = f"Asked in {ch.get('name')} on {d0:%d %b %Y}. Status in Slack: {st[0]}." if d0 else ask["ask"]
            ask_he = TM.get(ask["ask"])
            if ask_he:
                sh = ask_he if len(ask_he) <= 90 else ask_he[:88].rsplit(" ", 1)[0] + "…"
                TM.setdefault(title, f"{TM.get(nm, nm)}: בקשה ב-Slack מ-{ask.get('from', 'הלקוח')}: {sh}")
            if d0:
                TM.setdefault(detail, f"נשאל ב-{ch.get('name')} ב-{d0.day} ב{['ינואר','פברואר','מרץ','אפריל','מאי','יוני','יולי','אוגוסט','ספטמבר','אוקטובר','נובמבר','דצמבר'][d0.month-1]} {d0.year}. סטטוס ב-Slack: {st[1]}.")
            alert(f"slack-{k}-{ask.get('date')}-{slug(ask['ask'])[:24]}", "medium" if age > 5 or ask.get("status") == "unanswered" else "low", "clients",
                  title, detail, client=k, due=d0, source=f"Slack {ch.get('name')}", source_url=ask.get("url"))
    for c in slack_by_client.values():
        c["he"] = {"summary": he(c.get("summary"))}
        for ch in c["channels"]:
            ch["he"] = {"summary": he(ch.get("summary")), "highlights": he_list(ch.get("highlights")), "moodWhy": he(ch.get("moodWhy")),
                        "asks": [he(a.get("ask")) for a in ch.get("openAsks") or []]}
    team = slack.get("team") or None
    if team:
        team = dict(team, checkedAt=slack.get("checkedAt"))
        team["he"] = {"summary": he(team.get("summary")), "announcements": [he(x.get("text")) for x in team.get("announcements") or []],
                      "kudos": [he(x.get("text")) for x in team.get("kudos") or []]}
    # one-off findings from the refresh routine (e.g. a security issue spotted in Slack): data/extra_alerts.json
    for x in load("extra_alerts.json", []) or []:
        alert(x["id"], x.get("severity", "medium"), x.get("category", "agency"), x["title"], x.get("detail", ""), client=x.get("client"),
              due=x.get("due"), source=x.get("source"), source_url=x.get("sourceUrl"))
        if x.get("he"):
            TM.update({x["title"]: x["he"].get("title"), x.get("detail", ""): x["he"].get("detail")})
    tools = build_tools()
    perf = load("performance.json", {})
    brains = load("brains.json", [])
    contracts = load("contracts.json", [])
    briefing = load("briefing.json", None)

    clients = {}
    for p in perf.get("clients", []):
        if p.get("client") in NOT_CLIENTS:
            continue
        clients[p["client"]] = {"client": p["client"], "performance": p}
    agency_brain = None
    for b in brains:
        key = match_key(b.get("client"), clients.keys()) or b.get("client")
        if key == "CI":
            agency_brain = b
            continue
        if key in NOT_CLIENTS:
            continue
        c = clients.setdefault(key, {"client": key})
        c["brain"] = b
        # one brain can cover several SurgeOS projects (e.g. Kikar Group -> Kikar, Srugim, babli)
        for extra in (b.get("surgeosClients") or [])[1:] + (b.get("relatedSurgeosClients") or []):
            ek = match_key(extra, clients.keys())
            if ek and ek != key and "brain" not in clients[ek]:
                clients[ek]["brain"] = dict(b, issues=[], displayName=None, sharedBrainOf=b.get("displayName") or key, primaryKey=key,
                                            summary=f"Covered by the {b.get('displayName') or key} brain. " + (b.get("summary") or ""))
    for i, a in enumerate((agency_brain or {}).get("issues") or []):
        alert(f"agency-{slug(a.get('title', i))[:40]}", a.get("severity", "medium"), "agency", f"Agency: {a.get('title')}",
              a.get("detail", ""), source=a.get("source") or "Company brain", source_url=(agency_brain or {}).get("brainFolderUrl"))
    # contracts: group per client
    cmap = {}
    for k in contracts:
        if k.get("type") == "vendor":
            continue
        key = match_key(k.get("client") or k.get("displayName"), clients.keys()) or k.get("client")
        if not key or key in NOT_CLIENTS:  # unmatched entries with no client are finished one-off projects
            continue
        if k.get("type") == "other" and not k.get("url") and not k.get("monthlyFee"):
            continue  # audit stubs such as "No agreement found" are not contracts
        cmap.setdefault(key, []).append(k)
        clients.setdefault(key, {"client": key})

    contract_docs = {}
    for key, lst in cmap.items():
        # governing agreement: not ended, a real agreement (not a PO/quote/email), not pipeline, most recent start.
        # A client can hold several at once (Yad2 SEO + GEO); the rest are listed as supporting documents.
        def rank(k):
            active = k.get("relationship") == "active"
            start = k.get("startDate") or k.get("endDate") or ("9999" if active else "")  # an undated active arrangement is the current one
            return (k.get("relationship") not in ("ended", "notice_given"), active, k.get("type") not in ("PO", "quote", "other"),
                    k.get("relationship") != "pipeline", start, k.get("endDate") or "9999")
        lst.sort(key=rank, reverse=True)
        for i, k in enumerate(lst):
            cid = slug(f"{key}-{k.get('title') or i}")
            if cid in contract_docs:
                cid = slug(f"{cid[:190]}-{i}")
            end = iso(k.get("endDate"))
            nd = k.get("noticeDays")
            notice = end - dt.timedelta(days=int(nd)) if end and nd else None
            days = (end - TODAY).days if end else None
            doc = dict(k)
            doc.update({"client": key, "isLatest": i == 0, "daysLeft": days,
                        "noticeDeadline": notice.isoformat() if notice else None})
            if end is None:
                doc["status"] = "unknown"
            elif days < 0:
                doc["status"] = "renewed" if (k.get("autoRenew") and i == 0) else "expired"
            elif days <= 30:
                doc["status"] = "critical"
            elif days <= 90:
                doc["status"] = "soon"
            else:
                doc["status"] = "ok"
            contract_docs[cid] = doc
        latest = next(d for d in contract_docs.values() if d["client"] == key and d["isLatest"])
        for d in contract_docs.values():
            if d["client"] == key and not d["isLatest"] and d.get("relationship") in ("ended", "notice_given") \
                    and d.get("type") not in ("other", "PO", "quote") and latest.get("relationship") not in ("ended", "notice_given") \
                    and (iso(d.get("endDate")) is None or (TODAY - iso(d.get("endDate"))).days < 120) and (d.get("startDate") or "") >= "2026":
                alert(f"contract-{key}-{slug(d.get('title') or 'side')[:30]}-ended", "medium", "contracts",
                      f"{DISPLAY.get(key, key)}: part of the engagement ended",
                      f"\"{(d.get('title') or '').split(' (')[0].split(' - ')[0]}\" has ended. The main agreement continues.", client=key, source=d.get("title"), source_url=d.get("url"))
        clients[key]["contract"] = {k2: latest.get(k2) for k2 in (
            "title", "url", "type", "startDate", "endDate", "daysLeft", "status", "autoRenew", "noticeDays",
            "noticeDeadline", "monthlyFee", "totalValue", "currency", "hoursPerMonth", "confidence", "relationship", "signed")}
        disp = DISPLAY.get(key, key)
        end, days, url = iso(latest.get("endDate")), latest.get("daysLeft"), latest.get("url")
        fee = latest.get("monthlyFee")
        fee_s = f" · {latest.get('currency') or ''} {fee:,.0f}/mo".replace("  ", " ") if fee else ""
        if latest["status"] == "expired":
            alert(f"contract-{key}-expired", "high", "contracts", f"{disp}: contract ended {end:%d %b %Y}",
                  f"No newer signed agreement found in Drive{fee_s}. Renew, or confirm the engagement continues on what terms.",
                  client=key, due=end, source=latest.get("title"), source_url=url)
        elif latest["status"] == "renewed":
            alert(f"contract-{key}-autorenewed", "low", "contracts", f"{disp}: contract term passed {end:%d %b %Y} and auto-renews",
                  "Check the renewal terms and whether a price update is due.", client=key, due=end, source=latest.get("title"), source_url=url)
        elif days is not None and days <= 120:
            sev = "high" if days <= 30 else "medium" if days <= 90 else "low"
            alert(f"contract-{key}-ending", sev, "contracts", f"{disp}: contract ends {end:%d %b %Y}",
                  f"{fee_s.lstrip(' ·')}{'. ' if fee_s else ''}" + ("Auto-renews unless notice is given." if latest.get("autoRenew") else "Does not auto-renew: start the renewal conversation."),
                  client=key, due=end, source=latest.get("title"), source_url=url)
        rel = latest.get("relationship")
        if rel in ("notice_given", "ended"):
            alert(f"contract-{key}-{rel}", "high", "contracts",
                  f"{disp}: " + ("client gave notice" if rel == "notice_given" else "engagement ended"),
                  (latest.get("notes") or "See the source document.") + (f" ({fee_s.lstrip(' ·')})" if fee_s else ""),
                  client=key, due=end, source=latest.get("title"), source_url=url)
        elif rel == "paused":
            alert(f"contract-{key}-paused", "medium", "contracts", f"{disp}: engagement paused",
                  latest.get("notes") or "See the source document.", client=key, source=latest.get("title"), source_url=url)
        if latest.get("signed") is None and latest.get("relationship") == "active":
            alert(f"contract-{key}-unverified", "low", "contracts", f"{disp}: no signed agreement on file",
                  f"Work runs on \"{latest.get('title')}\"{fee_s}, but no signed copy was found in Drive or Gmail. Get one on file.",
                  client=key, source=latest.get("title"), source_url=url)
        if latest.get("signed") is False:
            alert(f"contract-{key}-unsigned", "medium", "contracts", f"{disp}: latest agreement not signed",
                  f"\"{latest.get('title')}\"{fee_s} is still unsigned. Get it signed or confirm which terms apply.",
                  client=key, due=iso(latest.get("startDate")), source=latest.get("title"), source_url=url)
        nd = iso(latest.get("noticeDeadline"))
        if nd and end and end >= TODAY and (nd - TODAY).days <= 30:
            alert(f"contract-{key}-notice", "high", "contracts", f"{disp}: notice deadline {nd:%d %b %Y}",
                  f"{latest.get('noticeDays')} days' notice before the {end:%d %b %Y} end date. After this the contract terms lock in.",
                  client=key, due=nd, source=latest.get("title"), source_url=url)

    for key, c in clients.items():
        pk = (c.get("brain") or {}).get("primaryKey")
        if not c.get("contract") and pk and clients.get(pk, {}).get("contract"):
            c["contract"] = dict(clients[pk]["contract"], sharedFrom=pk)

    client_docs = {}
    for key, c in clients.items():
        p = c.get("performance") or {}
        b = c.get("brain") or {}
        disp = (b.get("displayName") or DISPLAY.get(key) or key)
        for i, a in enumerate(p.get("alerts") or []):
            alert(f"perf-{key}-{a.get('metric', 'x')}-{i}", a.get("severity", "medium"), "performance",
                  f"{disp}: {a.get('title')}", a.get("detail", ""), client=key, source="SurgeOS")
        for i, a in enumerate(b.get("issues") or []):
            alert(f"brain-{key}-{slug(a.get('title', i))[:40]}", a.get("severity", "medium"), "clients",
                  f"{disp}: {a.get('title')}", a.get("detail", ""), client=key, source=a.get("source") or "Client brain",
                  source_url=b.get("brainFolderUrl"))
        if p and not b:
            alert(f"brain-{key}-missing", "low", "clients", f"{disp}: no client brain yet",
                  "Active in SurgeOS but there is no 00. AI Brain folder for this client in Drive, so the dashboard has no relationship context for it.",
                  client=key, source="Drive search")
        lbu = iso(b.get("lastBrainUpdate"))
        if b and not b.get("sharedBrainOf") and lbu and (TODAY - lbu).days > 14:
            alert(f"brain-{key}-stale", "medium", "clients", f"{disp}: client brain not updated since {lbu:%d %b %Y}",
                  "The brain's harvest routine has not written anything for over two weeks, so its context here may be out of date. Check the routine on the owner's laptop.",
                  client=key, due=lbu, source="Client brain", source_url=b.get("brainFolderUrl"))
        if not c.get("contract") and key not in NOT_CLIENTS and p:
            alert(f"contract-{key}-missing", "medium", "contracts", f"{disp}: no contract found in Drive",
                  "Active in SurgeOS but no signed agreement was found. Add the contract to the client folder so its end date can be tracked.",
                  client=key, source="Drive search")
        it = intel.get(match_key(key, intel.keys()) or key) or intel.get((b or {}).get("primaryKey") or "")
        shared_intel = bool(it) and it.get("client") != key and match_key(key, intel.keys()) is None
        if it and not shared_intel and (it.get("relationship") or {}).get("mood") == "strained":
            alert(f"intel-{key}-strained", "medium", "clients", f"{disp}: relationship strained",
                  (it.get("relationship") or {}).get("why") or "", client=key, source="Recent meetings")
        sev = [a["severity"] for a in alerts.values() if a.get("client") == key]
        health = p.get("health")
        kst = (c.get("contract") or {}).get("status")
        # at risk = performance at risk, contract expired/ending within 30 days, or several urgent alerts
        if health == "risk" or kst in ("expired", "critical") or (c.get("contract") or {}).get("relationship") in ("notice_given", "ended") or sev.count("high") >= 2:
            status = "risk"
        elif "high" in sev or "medium" in sev or health == "watch":
            status = "watch"
        else:
            status = "good"
        client_docs[slug(key)] = {
            "key": key, "name": disp, "domain": p.get("domain") or b.get("domain"), "status": status,
            "headline": p.get("headline"), "summary": b.get("summary"), "services": b.get("services") or [],
            "keyFacts": b.get("keyFacts") or [], "issues": b.get("issues") or [], "upcoming": b.get("upcoming") or [],
            "contacts": b.get("contacts") or [], "brainFolderUrl": b.get("brainFolderUrl"),
            "driveFolderUrl": b.get("driveFolderUrl"), "brainDocs": (b.get("brainDocs") or [])[:12],
            "lastBrainUpdate": b.get("lastBrainUpdate"), "sharedBrainOf": b.get("sharedBrainOf"),
            "strategyFolderUrl": b.get("strategyFolderUrl"),
            "perf": {k2: p.get(k2) for k2 in ("w7", "w28", "w90", "spark28", "health", "wins", "okrs", "openTasks",
                                               "overdueTasks", "hoursUsed", "hoursBudget", "surgeosId")},
            "contract": c.get("contract"), "alertCount": len(sev), "updatedAt": NOW,
            "slack": slack_by_client.get(key),
            "brainFullRead": bool(b.get("fullRead")),
            "intel": ({k2: it.get(k2) for k2 in ("lastMeeting", "relationship", "meetings", "themes", "highlights", "updatedAt")}
                      | ({"sharedFrom": it.get("client")} if shared_intel else {})) if it else None,
        }

    # Hebrew fields (UI falls back to English where a string is not translated yet)
    for a in alerts.values():
        a["he"] = {"title": he(a["title"]), "detail": he(a["detail"])}
    for c in client_docs.values():
        c["he"] = {
            "name": he(c["name"]) if c["name"] != c["key"] else None,
            "headline": he(c["headline"]), "summary": he(c["summary"]),
            "keyFacts": he_list(c["keyFacts"]), "upcoming": he_list(c["upcoming"]),
            "wins": he_list((c["perf"] or {}).get("wins")),
            "issues": [{"title": he(i.get("title")), "detail": he(i.get("detail"))} for i in c["issues"]],
        }
        it = c.get("intel")
        if it:
            c["he"]["intel"] = {
                "why": he((it.get("relationship") or {}).get("why")),
                "highlights": he_list(it.get("highlights")),
                "themes": [{"title": he(x.get("title")), "detail": he(x.get("detail"))} for x in it.get("themes") or []],
                "meetings": [{"title": he(x.get("title")), "summary": he(x.get("summary")), "decisions": he_list(x.get("decisions")),
                              "followUps": he_list(x.get("followUps"))} for x in it.get("meetings") or []],
            }
    if briefing and not briefing.get("he"):
        bt, bx = he(briefing.get("title")), he(briefing.get("text"))
        if bt and bx:
            briefing["he"] = {"title": bt, "text": bx}

    # spend summary
    paying = [t for t in tools.values() if t["paying"]]
    spend = {
        "yearly": round(sum(t["yearlyCost"] or 0 for t in paying)),
        "monthly": round(sum(t["monthlyCost"] or 0 for t in paying)),
        "paying": len(paying), "total": len(tools),
    }
    # contracted revenue: each latest agreement counted once (one contract can cover several SurgeOS
    # projects, e.g. Kikar Group -> Kikar, Srugim, babli), per currency; unsigned ones are pipeline
    seen, revenue = set(), {"active": {}, "pipeline": {}, "atRisk": {}, "clientsAtRisk": 0}
    for cd in client_docs.values():
        k = cd.get("contract") or {}
        fee, cur = k.get("monthlyFee"), k.get("currency") or "ILS"
        ident = (k.get("url"), k.get("title"))  # several agreements can cite the same source doc (e.g. a handover summary)
        if not fee or k.get("sharedFrom") or ident in seen or k.get("status") == "expired" or k.get("relationship") in ("ended", "notice_given"):
            continue
        seen.add(ident)
        signed = k.get("signed")
        bucket = "pipeline" if k.get("relationship") == "pipeline" or (signed is False and not k.get("relationship")) else "active"
        revenue[bucket][cur] = revenue[bucket].get(cur, 0) + fee
        if bucket == "active" and cd["status"] == "risk":
            revenue["atRisk"][cur] = revenue["atRisk"].get(cur, 0) + fee
            revenue["clientsAtRisk"] += 1

    # tool checks that don't match a sheet row (e.g. a Google Cloud billing account found in email) still raise alerts
    for x in (load("toolchecks.json", {}) or {}).get("items", []) if isinstance(load("toolchecks.json", {}), dict) else []:
        if slug(x.get("tool") or "") not in tools and x.get("status") in ("low", "critical"):
            alert(f"tool-{slug(x.get('tool'))}-check", "high" if x["status"] == "critical" else "medium", "tools",
                  f"{x.get('tool')}: {x.get('headline')}", x.get("detail") or "", source=x.get("source") or x.get("method"))
            a = alerts[slug(f"tool-{slug(x.get('tool'))}-check")]
            a["he"] = {"title": he(a["title"]), "detail": he(a["detail"])}
    tcl = load("toolchecks.json", {})
    last_tc = iso((tcl or {}).get("checkedAt")) if isinstance(tcl, dict) else None
    if not last_tc or (TODAY - last_tc).days > 9:
        alert("agency-weekly-tool-check", "low", "agency", "Agency: weekly browser check of the tools is " + ("overdue" if last_tc else "not set up yet"),
              "Usage, credits and last-login data for tools without an API come from a weekly Claude in Chrome check on the owner's computer (BROWSER-CHECK.md in the repo).",
              due=last_tc, source="Weekly browser check")
        a = alerts["agency-weekly-tool-check"]
        a["he"] = {"title": he(a["title"]), "detail": he(a["detail"])}

    # Client meetings in the next 7 days: Google Calendar (data/calendar.json, saved by the refresh) plus dated
    # meeting items in the client brains' "upcoming" lists. Calendar wins when both name the same client and day.
    MEET_RE = re.compile(r"\b(meeting|sync|QBR|call|training)\b", re.I)
    UP_RE = re.compile(r"^(Week of\s+)?(\d{4}-\d{2}-\d{2})(?:\s*\(\w+\))?(?:\s+(\d{1,2}:\d{2}))?\s*[–:-]\s*(.+)$")
    ahead, seen_md = [], set()
    def find_client(title, emails):
        doms = {e.split("@")[-1].lower() for e in emails if not e.lower().endswith("@cutinside.com") and "@resource." not in e}
        for k, c in client_docs.items():
            d = (c.get("domain") or "").lower().replace("www.", "")
            if d and any(x == d or x.endswith("." + d) for x in doms):
                return c["key"], bool(doms)
        tl = title.lower()
        for k, c in client_docs.items():
            names = {c["key"].lower(), (c.get("name") or "").split(" (")[0].lower()}
            if any(n and len(n) > 2 and re.search(r"\b" + re.escape(n) + r"\b", tl) for n in names):
                return c["key"], bool(doms)
        return None, bool(doms)
    for e in load("calendar.json", []) or []:
        st = e.get("start") or ""
        d0 = iso(st[:10])
        if not d0 or not (0 <= (d0 - TODAY).days <= 7):
            continue
        key, external = find_client(e.get("title") or "", e.get("attendees") or [])
        if not key:
            continue
        ahead.append({"date": st[:10], "time": st[11:16] or None, "client": key, "title": e.get("title"), "internal": not external,
                      "source": "Google Calendar", "url": e.get("url") or None, "attendees": len(e.get("attendees") or [])})
        seen_md.add((key, st[:10]))
    for k, c in client_docs.items():
        if c.get("sharedBrainOf"):
            continue
        for u in c.get("upcoming") or []:
            m = UP_RE.match(u.strip())
            if not m or not MEET_RE.search(m.group(4)):
                continue
            d0 = iso(m.group(2))
            if not d0 or not (0 <= (d0 - TODAY).days <= 7) or (c["key"], m.group(2)) in seen_md:
                continue
            h = he(u)
            hm = UP_RE.match(h.strip()) if h else None
            ahead.append({"date": m.group(2), "time": m.group(3), "approx": bool(m.group(1)), "client": c["key"], "title": m.group(4),
                          "he": {"title": hm.group(4) if hm else h}, "internal": False, "source": "Client brain"})
            seen_md.add((c["key"], m.group(2)))
    ahead.sort(key=lambda x: (x["date"], x.get("time") or "99"))

    # DataForSEO spend: compact history for the page (from data/dataforseo_usage.json, rebuilt weekly from the free
    # id_list endpoint) plus a balance series that grows by one point per refresh (data/dfs_balance.json).
    dfs_doc = None
    usage = load("dataforseo_usage.json", None)
    lc = {slug(x.get("tool")): x for x in load("livechecks.json", [])}.get("dataforseo-api")
    hist = load("dfs_balance.json", []) or []
    if lc and lc.get("value") is not None and not any(h.get("at") == lc.get("checkedAt") for h in hist):
        hist.append({"at": lc.get("checkedAt"), "balance": lc.get("value"), "deposited": lc.get("deposited"), "spentToday": lc.get("spentToday")})
    hist = sorted(hist, key=lambda h: h.get("at") or "")[-400:]
    with open(os.path.join(DATA, "dfs_balance.json"), "w") as f:
        json.dump(hist, f)
    prev_dfs = load("dfs_prev.json", None)  # the stored snapshot/dataforseo, used when no new usage file was built this run
    if not usage and prev_dfs:
        bal = (lc or {}).get("value", prev_dfs.get("balance"))
        dep = (lc or {}).get("deposited", prev_dfs.get("deposited"))
        dfs_doc = dict(prev_dfs, balance=bal, deposited=dep, lifetimeSpent=round((dep or 0) - (bal or 0), 2), balanceHistory=hist, updatedAt=NOW)
        rr = prev_dfs.get("runRate") or {}
        for f in dfs_doc.get("findings") or []:
            he(f.get("en"))
        for c in (dfs_doc.get("last30") or {}).get("byClient") or []:
            if c["client"].startswith("("):
                he(c["client"])
        avg30, avg7 = rr.get("avg30") or 0, rr.get("avg7") or 0
        if bal is not None and avg30 and bal / avg30 < 14:
            alert("tool-dataforseo-runway", "high" if bal / avg30 < 7 else "medium", "tools",
                  f"DataForSEO: the ${bal:,.2f} balance covers about {bal/avg30:.0f}-{(bal/avg7 if avg7 else bal/avg30):.0f} days",
                  f"Spend averaged ${avg30:.2f}/day over 30 days and ${avg7:.2f}/day over 7 (as of the last spend analysis, {str(prev_dfs.get('asOf'))[:10]}). Top up before the rank trackers stop, and decide which jobs should keep running (Tools → DataForSEO spend).",
                  source="DataForSEO API (user_data + id_list)")
            alerts["tool-dataforseo-runway"]["he"] = {"title": he(alerts["tool-dataforseo-runway"]["title"]), "detail": he(alerts["tool-dataforseo-runway"]["detail"])}
        top = ((prev_dfs.get("last30") or {}).get("byClient") or [{}])[0]
        if top.get("client", "").startswith("(unattributed") and (top.get("share") or 0) >= 0.3:
            alert("tool-dataforseo-unowned", "medium", "tools",
                  f"DataForSEO: {top['share']*100:.0f}% of the last 30 days' spend has no owner",
                  f"{top['client'][1:].split(')')[0].capitalize()}: {top['client'].split(') ', 1)[-1]}, ${top['cost']:,.2f} over 30 days ({top.get('tasks', 0):,} tasks). Its keywords match no client. Find out who runs it and whether it still needs to run.",
                  source="DataForSEO id_list")
            alerts["tool-dataforseo-unowned"]["he"] = {"title": he(alerts["tool-dataforseo-unowned"]["title"]), "detail": he(alerts["tool-dataforseo-unowned"]["detail"])}
    if usage:
        l30, rr, acc = usage.get("last30") or {}, usage.get("runRate") or {}, usage.get("account") or {}
        bal = (lc or {}).get("value", acc.get("balance"))
        dep = (lc or {}).get("deposited", acc.get("deposited"))
        clients_ = [dict(c, he=he(c["client"]) if c["client"].startswith("(") else None) for c in (l30.get("byClient") or [])[:12]]
        dfs_doc = {
            "asOf": usage.get("asOf"), "balance": bal, "deposited": dep, "lifetimeSpent": round((dep or 0) - (bal or 0), 2) if dep else acc.get("lifetimeSpent"),
            "coverage": {k: (usage.get("coverage") or {}).get(k) for k in ("from", "to", "tasks", "netCost", "note")},
            "daily": [[d["date"], d["cost"], (d.get("byApi") or {}).get("serp", 0)] for d in usage.get("daily", [])],
            "monthly": [{"month": m["month"], "cost": m["cost"], "tasks": m.get("tasks"), "byApi": m.get("byApi")} for m in usage.get("monthly", [])],
            "runRate": {k: rr.get(k) for k in ("avg7", "avg30", "projectedMonth", "octoberToDate", "method")},
            "last30": {"total": l30.get("total"), "window": l30.get("window"), "byEndpoint": (l30.get("byEndpoint") or [])[:10], "byClient": clients_,
                       "byLocation": (l30.get("byLocation") or [])[:8], "topTargets": (l30.get("topTargets") or [])[:10],
                       "duplicates": {k: (l30.get("duplicates") or {}).get(k) for k in ("cost", "tasks")}},
            "spikes": usage.get("spikes", []), "spikeRule": usage.get("spikeRule"),
            "findings": [{"en": f, "he": he(f)} for f in usage.get("findings", [])],
            "balanceHistory": hist, "updatedAt": NOW,
        }
        avg30, avg7 = rr.get("avg30") or 0, rr.get("avg7") or 0
        if bal is not None and avg30:
            run30, run7 = bal / avg30, (bal / avg7 if avg7 else None)
            if run30 < 14:
                alert("tool-dataforseo-runway", "high" if run30 < 7 else "medium", "tools",
                      f"DataForSEO: the ${bal:,.2f} balance covers about {run30:.0f}-{(run7 or run30):.0f} days",
                      f"Spend averaged ${avg30:.2f}/day over 30 days and ${avg7:.2f}/day over 7. One weekly SERP batch costs more than the balance. Top up before the rank trackers stop, and decide which jobs should keep running (Tools → DataForSEO spend).",
                      source="DataForSEO API (user_data + id_list)")
        top = (l30.get("byClient") or [{}])[0]
        if top.get("client", "").startswith("(unattributed") and (top.get("share") or 0) >= 0.3:
            alert("tool-dataforseo-unowned", "medium", "tools",
                  f"DataForSEO: {top['share']*100:.0f}% of the last 30 days' spend has no owner",
                  f"{top['client'][1:].split(')')[0].capitalize()}: {top['client'].split(') ', 1)[-1]}, ${top['cost']:,.2f} over 30 days ({top.get('tasks', 0):,} tasks). Its keywords match no client. Find out who runs it and whether it still needs to run.",
                  source="DataForSEO id_list")
        recent = [x for x in usage.get("spikes", []) if x.get("date") and (TODAY - dt.date.fromisoformat(x["date"])).days <= 7]
        if recent:
            x = max(recent, key=lambda x: x["cost"])
            alert("tool-dataforseo-spike", "low", "tools", f"DataForSEO: ${x['cost']:,.2f} spent on {dt.date.fromisoformat(x["date"]):%d %b %Y}",
                  f"More than twice the 30-day median. Driver: {x.get('driver', '')[:220]}", due=x["date"], source="DataForSEO id_list")
        for aid in ("tool-dataforseo-runway", "tool-dataforseo-unowned", "tool-dataforseo-spike"):
            if aid in alerts:
                alerts[aid]["he"] = {"title": he(alerts[aid]["title"]), "detail": he(alerts[aid]["detail"])}

    # Alert lifecycle: keep each alert's first-seen time across runs, and list what is new and what disappeared
    # since the previous snapshot (prev/snapshot/alerts.json, loaded in step 0 of the refresh).
    prev_dir = os.environ.get("PREV_DIR", "prev")
    pa_path = os.path.join(prev_dir, "snapshot", "alerts.json")
    prev_alerts, prev_at = {}, None
    if os.path.exists(pa_path):
        pd_ = json.load(open(pa_path))
        pd_ = pd_.get("data", pd_)
        prev_at = pd_.get("updatedAt")
        prev_alerts = {a["id"]: a for a in pd_.get("items", [])}
        for k in range(1, 6):
            extra = os.path.join(prev_dir, "snapshot", f"alerts-{k}.json")
            if os.path.exists(extra):
                e2 = json.load(open(extra)); prev_alerts.update({a["id"]: a for a in e2.get("data", e2).get("items", [])})
    for aid, a in alerts.items():
        pa = prev_alerts.get(aid)
        a["firstSeen"] = (pa.get("firstSeen") or pa.get("createdAt")) if pa else NOW
        a["isNew"] = bool(prev_alerts) and not pa
    changes = {"since": prev_at, "new": [aid for aid, a in alerts.items() if a.get("isNew")],
               "resolved": [{"id": aid, "title": pa.get("title"), "he": pa.get("he"), "client": pa.get("client"), "severity": pa.get("severity"), "category": pa.get("category")}
                            for aid, pa in prev_alerts.items() if aid not in alerts]} if prev_alerts else None

    order = {"high": 0, "medium": 1, "low": 2}
    sev_counts = {s: sum(1 for a in alerts.values() if a["severity"] == s) for s in order}
    # refresh history: last 12 runs with the sources that succeeded or failed (source_status.json "failed")
    prev_meta = {}
    for a in sys.argv[1:]:
        if a.startswith("--prev-meta=") and os.path.exists(a.split("=", 1)[1]):
            prev_meta = json.load(open(a.split("=", 1)[1]))
    ss = load("source_status.json", {})
    runs = (prev_meta.get("runs") or [])[-11:] + [{
        "at": NOW, "by": os.environ.get("RUN_BY", "refresh"), "failed": ss.get("failed") or [],
        "ok": [k for k in ("sheet", "drive", "gmail", "surgeos", "dataforseo", "meetings") if ss.get(k) and k not in (ss.get("failed") or [])],
        "alerts": None}]
    meta = {
        "updatedAt": NOW, "today": TODAY.isoformat(), "dataThrough": perf.get("dataThrough"),
        "counts": {"clients": len(client_docs), "contracts": len(contract_docs), "tools": len(tools), "alerts": sev_counts},
        "spend": spend, "portfolio": perf.get("portfolio"), "revenue": revenue,
        "sourceStatus": load("source_status.json", {}),
        "runs": [dict(r, alerts=r.get("alerts") or sev_counts) for r in runs],
        "agency": {k2: (agency_brain or {}).get(k2) for k2 in ("summary", "keyFacts", "upcoming", "brainFolderUrl", "lastBrainUpdate")},
        "sources": {
            "toolsSheet": "https://docs.google.com/spreadsheets/d/1NhlhJMoLFvQws1Bzim9iDHCJghsQUEhcXBngqj2FnBU/edit",
            "surgeos": "SurgeOS (Search Console BigQuery mirror, GA4, Peec)", "drive": "Google Drive client folders",
        },
        "meetingsAhead": ahead,
        "team": team,
        "changes": changes,
        "schedule": os.environ.get("SCHEDULE", "Twice a day, ~07:00 and ~15:00 Israel time"),
        "triggerId": os.environ.get("TRIGGER_ID", "trig_01WDH93AGHQEqNsCiNghRytm"),
    }

    # ---- write: a handful of snapshot documents (each well under the 256 KiB doc cap)
    shards = {}
    writes = []
    os.makedirs(os.path.join(OUT, "docs"), exist_ok=True)

    def put(col, did, data):
        fp = os.path.join(OUT, "docs", f"{col}__{did}.json")
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        writes.append({"op": "set", "collection": col, "doc_id": did, "file_path": os.path.abspath(fp)})

    def put_items(name, items, limit=180_000):
        parts, cur, size = [], [], 0
        for it in items:
            n = len(json.dumps(it, ensure_ascii=False).encode())
            if cur and size + n > limit:
                parts.append(cur); cur, size = [], 0
            cur.append(it); size += n
        parts.append(cur)
        ids = [name if k == 0 else f"{name}-{k}" for k in range(len(parts))]
        for did, part in zip(ids, parts):
            put("snapshot", did, {"items": part, "updatedAt": NOW})
        shards[name] = ids

    put_items("clients", [dict(v, id=k) for k, v in sorted(client_docs.items())])
    put_items("contracts", [dict(v, id=k) for k, v in sorted(contract_docs.items())])
    put_items("tools", [dict(v, id=k) for k, v in sorted(tools.items())])
    put_items("alerts", [dict(v, id=k) for k, v in sorted(alerts.items())])
    fav = load("favicons.json", {})
    if fav:
        put("snapshot", "favicons", {"icons": fav, "updatedAt": NOW})
    if dfs_doc:
        put("snapshot", "dataforseo", dfs_doc)
    meta["shards"] = shards

    put("meta", "state", meta)
    if briefing:
        put("briefing", "latest", dict(briefing, generatedAt=briefing.get("generatedAt") or NOW))
    tm_items = [{"en": k, "he": v} for k, v in sorted(TM_USED.items())]
    parts, cur, size = [], [], 0
    for it in tm_items:
        n = len(json.dumps(it, ensure_ascii=False).encode())
        if cur and size + n > 180_000:
            parts.append(cur); cur, size = [], 0
        cur.append(it); size += n
    parts.append(cur)
    for k, part in enumerate(parts):
        put("sources", "tm" if k == 0 else f"tm-{k}", {"items": part, "updatedAt": NOW})
    with open(os.path.join(OUT, "untranslated.json"), "w", encoding="utf-8") as f:
        json.dump(sorted(MISSING), f, ensure_ascii=False, indent=1)
    if intel:
        put("sources", "meetings", {"items": list(intel.values()), "updatedAt": NOW})
    if os.path.exists(os.path.join(DATA, "slack.json")):
        put("sources", "slack", json.load(open(os.path.join(DATA, "slack.json"), encoding="utf-8")))
    for name in ("brains", "contracts", "performance"):
        raw = load(f"{name}.json", None)
        if raw is not None:
            put("sources", name, raw if isinstance(raw, dict) else {"items": raw})

    # pin writes to the versions the caller read (ArtifactData requires if_version on existing docs)
    versions = {}
    for a in sys.argv[1:]:
        if a.startswith("--versions="):
            v = a.split("=", 1)[1]
            versions = json.load(open(v)) if os.path.exists(v) else dict(x.split(":") for x in v.split(",") if x)
    for w in writes:
        ver = versions.get(f"{w['collection']}/{w['doc_id']}")
        if ver:
            w["if_version"] = int(ver)
    live = {f"{w['collection']}/{w['doc_id']}" for w in writes}
    for key, ver in versions.items():  # shards that no longer exist
        col, did = key.split("/", 1)
        if col in ("snapshot", "sources") and key not in live and ((col == "snapshot" and did not in ("favicons", "dataforseo")) or did.startswith("tm-")):
            writes.append({"op": "delete", "collection": col, "doc_id": did, "if_version": int(ver)})
    with open(os.path.join(OUT, "writes.json"), "w") as f:
        json.dump(writes, f, indent=1)
    # ArtifactData batch requests are capped at 1 MiB: split into ordered parts (snapshots first, meta last,
    # so the page never points at a shard that isn't written yet)
    order = {"snapshot": 0, "sources": 1, "briefing": 2, "meta": 3}
    parts, cur, size = [], [], 0
    for w in sorted(writes, key=lambda w: order.get(w["collection"], 1)):
        n = os.path.getsize(w["file_path"]) if w.get("file_path") else 200
        if cur and (size + n > 850_000 or len(cur) >= 50):
            parts.append(cur); cur, size = [], 0
        cur.append(w); size += n
    if cur:
        parts.append(cur)
    for old_part in [f for f in os.listdir(OUT) if f.startswith("writes-")]:
        os.remove(os.path.join(OUT, old_part))
    for i, part in enumerate(parts, 1):
        with open(os.path.join(OUT, f"writes-{i}.json"), "w") as f:
            json.dump(part, f, indent=1)
    print(json.dumps({"untranslated": len(MISSING), "writes": len(writes), "shards": shards, "alerts": sev_counts, "clients": len(client_docs),
                      "contracts": len(contract_docs), "tools": len(tools), "spend": spend}))


if __name__ == "__main__":
    build()
