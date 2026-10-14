#!/usr/bin/env python3
"""Inline the Cut Inside logo lockups into src/dashboard.src.html -> dashboard.html (the published page)."""
import base64
import pathlib

root = pathlib.Path(__file__).resolve().parent.parent
page = (root / "src" / "dashboard.src.html").read_text(encoding="utf-8")
for key, name in (("%%LOGO_WHITE%%", "logo-lockup-white.png"), ("%%LOGO_BLACK%%", "logo-lockup-black.png")):
    page = page.replace(key, "data:image/png;base64," + base64.b64encode((root / "assets" / name).read_bytes()).decode())
(root / "dashboard.html").write_text(page, encoding="utf-8")
print("dashboard.html", len(page), "bytes")
