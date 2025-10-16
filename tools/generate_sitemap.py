#!/usr/bin/env python3
"""
Generate sitemap.xml with pretty URLs only (/, /about/, /books/<slug>/...).
- Reads SITE_DOMAIN from env or defaults to https://www.gradsummit.com
- Includes only index.html files (root and subfolders), skips /404.html
- Uses last git commit time if available; falls back to mtime
"""
import os, subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = os.environ.get("SITE_DOMAIN", "https://www.gradsummit.com").rstrip("/")

def is_index(p: Path) -> bool:
    rel = p.relative_to(ROOT).as_posix()
    if rel == "404.html":
        return False
    if p.name != "index.html":
        return False
    return True

def url_for_index(p: Path) -> str:
    rel = p.relative_to(ROOT).as_posix()
    if rel == "index.html":
        return SITE + "/"
    # /foo/index.html -> /foo/
    return SITE + "/" + rel[:-len("index.html")]

def git_lastmod(p: Path) -> str | None:
    try:
        ts = subprocess.check_output(
            ["git", "log", "-1", "--format=%cI", "--", str(p)],
            cwd=ROOT, text=True).strip()
        return ts or None
    except Exception:
        return None

def fs_lastmod(p: Path) -> str:
    t = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    return t.isoformat(timespec="seconds")

indexes = [p for p in ROOT.rglob("index.html") if is_index(p)]
entries = []
for p in sorted(indexes):
    lastmod = git_lastmod(p) or fs_lastmod(p)
    entries.append((url_for_index(p), lastmod))

xml = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
]
for url, lastmod in entries:
    xml += [ "  <url>",
             f"    <loc>{url}</loc>",
             f"    <lastmod>{lastmod}</lastmod>",
             "  </url>" ]
xml.append("</urlset>\n")

(ROOT / "sitemap.xml").write_text("\n".join(xml), encoding="utf-8")
print("Generated sitemap.xml with", len(entries), "URLs")
