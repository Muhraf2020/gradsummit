#!/usr/bin/env python3
"""
Generate sitemap.xml listing all .html files with <loc> and <lastmod>.
- Domain taken from env SITE_DOMAIN (e.g., https://www.mastermytheses.com), or default below.
- lastmod prefers last Git commit time; falls back to filesystem mtime.
- Skips hidden folders, .github, node_modules. Skips root 404.html.
"""
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent.parent

# Change default if you want, or set SITE_DOMAIN in the GitHub Action
DOMAIN = os.environ.get("SITE_DOMAIN", "https://www.mastermytheses.com").rstrip("/") + "/"

def is_ignored(p: Path) -> bool:
    parts = p.parts
    if ".github" in parts or "node_modules" in parts:
        return True
    return False

def last_commit_dt(path: Path):
    """Return last commit datetime (UTC) for file, or None if git not available."""
    try:
        ts = subprocess.check_output(
            ["git", "log", "-1", "--format=%cI", "--", str(path)],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        if ts:
            # %cI returns ISO 8601, possibly ending with 'Z'
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None
    return None

def file_mtime_dt(path: Path):
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

def iso8601(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def loc_for(relpath: str) -> str:
    # index.html -> /
    return DOMAIN if relpath == "index.html" else urljoin(DOMAIN, relpath)

# Collect pages
pages = []
for p in ROOT.rglob("*.html"):
    if is_ignored(p):
        continue
    rel = p.relative_to(ROOT).as_posix()
    # optionally skip root 404.html from sitemap
    if rel == "404.html":
        continue
    pages.append((p, rel))

# Build entries with lastmod
entries = []
for abs_path, rel in pages:
    dt = last_commit_dt(abs_path) or file_mtime_dt(abs_path)
    entries.append((loc_for(rel), iso8601(dt)))

# Write XML
entries.sort(key=lambda x: x[0])

xml = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
]
for url, lastmod in entries:
    xml.append("  <url>")
    xml.append(f"    <loc>{url}</loc>")
    xml.append(f"    <lastmod>{lastmod}</lastmod>")
    xml.append("  </url>")
xml.append("</urlset>\n")

(ROOT / "sitemap.xml").write_text("\n".join(xml), encoding="utf-8")
print("Generated sitemap.xml with", len(entries), "URLs")
