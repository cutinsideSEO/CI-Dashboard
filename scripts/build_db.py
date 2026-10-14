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
            "brainFullRead": bool(b.get("fullRead")),
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

    tcl = load("toolchecks.json", {})
    last_tc = iso((tcl or {}).get("checkedAt")) if isinstance(tcl, dict) else None
    if not last_tc or (TODAY - last_tc).days > 9:
        alert("agency-weekly-tool-check", "low", "agency", "Agency: weekly browser check of the tools is " + ("overdue" if last_tc else "not set up yet"),
              "Usage, credits and last-login data for tools without an API come from a weekly Claude in Chrome check on the owner's computer (BROWSER-CHECK.md in the repo).",
              due=last_tc, source="Weekly browser check")
        a = alerts["agency-weekly-tool-check"]
        a["he"] = {"title": he(a["title"]), "detail": he(a["detail"])}

    order = {"high": 0, "medium": 1, "low": 2}
    sev_counts = {s: sum(1 for a in alerts.values() if a["severity"] == s) for s in order}
    meta = {
        "updatedAt": NOW, "today": TODAY.isoformat(), "dataThrough": perf.get("dataThrough"),
        "counts": {"clients": len(client_docs), "contracts": len(contract_docs), "tools": len(tools), "alerts": sev_counts},
        "spend": spend, "portfolio": perf.get("portfolio"), "revenue": revenue,
        "sourceStatus": load("source_status.json", {}),
        "agency": {k2: (agency_brain or {}).get(k2) for k2 in ("summary", "keyFacts", "upcoming", "brainFolderUrl", "lastBrainUpdate")},
        "sources": {
            "toolsSheet": "https://docs.google.com/spreadsheets/d/1NhlhJMoLFvQws1Bzim9iDHCJghsQUEhcXBngqj2FnBU/edit",
            "surgeos": "SurgeOS (Search Console BigQuery mirror, GA4, Peec)", "drive": "Google Drive client folders",
        },
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
        if col in ("snapshot", "sources") and key not in live and ((col == "snapshot" and did != "favicons") or did.startswith("tm-")):
            writes.append({"op": "delete", "collection": col, "doc_id": did, "if_version": int(ver)})
    with open(os.path.join(OUT, "writes.json"), "w") as f:
        json.dump(writes, f, indent=1)
    print(json.dumps({"untranslated": len(MISSING), "writes": len(writes), "shards": shards, "alerts": sev_counts, "clients": len(client_docs),
                      "contracts": len(contract_docs), "tools": len(tools), "spend": spend}))


if __name__ == "__main__":
    build()
