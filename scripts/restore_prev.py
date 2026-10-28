#!/usr/bin/env python3
"""Step 0 of REFRESH.md: rebuild data/ from the dashboard database copy in prev/.

List each collection with ArtifactData (out_dir=prev) first, then run:
    python3 scripts/restore_prev.py [--force]
It fills data/ only where a file is missing (or everything with --force), so a container that still has its
data/ keeps it, and a fresh container gets back everything the refresh needs.
"""
import json, os, sys

PREV, DATA = os.environ.get("PREV_DIR", "prev"), os.environ.get("DATA_DIR", "data")
FORCE = "--force" in sys.argv
done = []


def rd(path):
    p = os.path.join(PREV, path)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def wr(name, obj, text=False):
    p = os.path.join(DATA, name)
    if os.path.exists(p) and not FORCE:
        return
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(obj) if text else json.dump(obj, f, ensure_ascii=False)
    done.append(name)


def rd_items(name, key="items"):
    """A sharded sources/ document (name, name-1, ...) joined back into one list; None if it is missing."""
    out, found = [], False
    for k in range(0, 50):
        d = rd(f"sources/{name}.json" if k == 0 else f"sources/{name}-{k}.json")
        if d is None:
            continue
        found = True
        out += d.get(key, []) if isinstance(d, dict) else d
    return out if found else None


os.makedirs(DATA, exist_ok=True)
for name in ("brains", "contracts"):
    d = rd_items(name)
    if d is not None:
        wr(f"{name}.json", d)
d = rd("sources/performance.json")
if d is not None:
    wr("performance.json", d)
tm = {x["en"]: x["he"] for x in rd_items("tm") or []}
if tm:
    p = os.path.join(DATA, "tm.json")
    old = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    old.update({k: v for k, v in tm.items() if k not in old})
    json.dump(old, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    done.append("tm.json (merged)")
for m in rd_items("meetings") or []:
    key = m.get("client")
    if key:
        wr(f"meetings/{key}.json", m)
d = rd("sources/toolchecks.json")
if d is not None:
    wr("toolchecks.json", d)
d = rd("sources/slack.json")
if d is not None:
    d["channels"] = rd_items("slack", "channels")
    wr("slack.json", d)
d = rd("snapshot/favicons.json")
if d and d.get("icons"):
    wr("favicons.json", d["icons"])
d = rd("snapshot/dataforseo.json")
if d:
    wr("dfs_prev.json", d)
    wr("dfs_balance.json", d.get("balanceHistory") or [])
d = rd("briefing/latest.json")
if d:
    wr("briefing.json", d)
d = rd("meta/state.json")
if d and d.get("sourceStatus"):
    wr("source_status.json", d["sourceStatus"])
d = rd("sources/inputs.json")  # small inputs that are not their own document: tools sheet CSV, one-off alerts, calendar
if d:
    if d.get("toolsCsv"):
        wr("tools.csv", d["toolsCsv"], text=True)
    for key, fn in (("extraAlerts", "extra_alerts.json"), ("calendar", "calendar.json"), ("livechecks", "livechecks.json")):
        if d.get(key) is not None:
            wr(fn, d[key])
print(json.dumps({"restored": done, "force": FORCE}))
