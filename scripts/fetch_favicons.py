#!/usr/bin/env python3
"""Fetch each client domain's favicon into data/favicons.json as {domain: data-URI}.

The page cannot load external images (artifact CSP), so icons are fetched here and stored in the
database (snapshot/favicons). Existing icons are kept; only missing domains are fetched. Needs
outbound access to www.google.com (the s2 favicon service); if the network policy blocks it the
script reports the failures and leaves the file as it was, and the page shows letter tiles.
"""
import base64
import json
import os
import subprocess
import sys

DATA = os.environ.get("DATA_DIR", "data")
path = os.path.join(DATA, "favicons.json")
icons = json.load(open(path)) if os.path.exists(path) else {}
perf = json.load(open(os.path.join(DATA, "performance.json")))
domains = sorted({c["domain"] for c in perf.get("clients", []) if c.get("domain")})
failed = []
for d in domains:
    if d in icons and "--force" not in sys.argv:
        continue
    url = f"https://www.google.com/s2/favicons?domain={d}&sz=64"
    r = subprocess.run(["curl", "-sS", "-L", "--max-time", "20", "-w", "\n%{http_code} %{content_type}", url], capture_output=True)
    body, _, status = r.stdout.rpartition(b"\n")
    code, _, ctype = status.decode(errors="replace").partition(" ")
    if r.returncode != 0 or code != "200" or not ctype.startswith("image/") or len(body) < 100:
        failed.append(f"{d} ({r.stderr.decode(errors='replace').strip() or code})")
        continue
    icons[d] = f"data:{ctype.split(';')[0]};base64," + base64.b64encode(body).decode()
json.dump(icons, open(path, "w"))
print(json.dumps({"icons": len(icons), "domains": len(domains), "failed": failed[:5], "failedCount": len(failed)}))
