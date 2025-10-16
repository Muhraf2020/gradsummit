#!/usr/bin/env python3
"""
Generate sitemap.xml with pretty slash URLs only.
- Includes home (/), /about/, and /books/<slug>/, etc. — NO .html entries.
- lastmod uses the git timestamp of the ORIGINAL source page (about.html, books/<slug>.html),
  falling back to the current index.html mtime when needed.
- Adds <image:image> entries from <meta property="og:image"> and the first <img> tags.
"""

from __future__ import annotations
import os, re, subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
SITE = os.environ.get("SITE_DOMAIN", "https://www.gradsummit.com").rstrip("/")

# -------- helpers --------

def is_index(p: Path) -> bool:
    rel = p.relative_to(ROOT).as_posix()
    if rel == "404.html":               # never include 404 in sitemap
        return False
    return p.name == "index.html"

def pretty_url_for_index(p: Path) -> str:
    rel = p.relative_to(ROOT).as_posix()
    if rel == "index.html":
        return SITE + "/"
    # /dir/index.html -> /dir/
    return SITE + "/" + rel[:-len("index.html")]

def source_html_for_index(pretty_index: Path) -> Path | None:
    """
    Map /about/index.html -> /about.html
        /books/foo/index.html -> /books/foo.html
    """
    try:
        parent = pretty_index.parent
        src = parent.with_suffix(".html")  # replaces last folder with .html
        # e.g., Path('.../about/index.html').parent = '.../about'
        #       -> '.../about.html'
        if (src.exists()):
            return src
        # fallback: try root if mapping failed
        return None
    except Exception:
        return None

def git_last_commit_iso(p: Path) -> str | None:
    """Return last commit date in ISO-8601 from git; None if not tracked."""
    try:
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%cI", "--", str(p)],
            cwd=str(ROOT),
            text=True
        ).strip()
        return out or None
    except Exception:
        return None

def fs_mtime_iso(p: Path) -> str:
    t = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    return t.isoformat(timespec="seconds")

# very light HTML sniffers (fast, regex-based)
META_OG_IMAGE = re.compile(
    r'<meta\s+(?:property|name)=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
    re.IGNORECASE)
IMG_SRC = re.compile(
    r'<img\b[^>]*\s+src=["\']([^"\']+)["\']',
    re.IGNORECASE)

def to_abs_url(u: str) -> str:
    if re.match(r'^(?:https?:|data:|blob:)', u, re.I):
        return u
    # make root-absolute into full URL
    if u.startswith("/"):
        return SITE + u
    # otherwise treat as relative to root
    return SITE + "/" + u.lstrip("./")

def find_images_in(pretty_html_path: Path, limit: int = 3) -> list[str]:
    try:
        html = pretty_html_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    imgs: list[str] = []

    # 1) og:image (preferred)
    for m in META_OG_IMAGE.finditer(html):
        imgs.append(m.group(1))
    # 2) first few <img src=...>
    for m in IMG_SRC.finditer(html):
        imgs.append(m.group(1))
        if len(imgs) >= limit:
            break

    # normalize to absolute full URLs
    out: list[str] = []
    for u in imgs:
        out.append(to_abs_url(u))
    # de-dup preserving order
    seen = set()
    uniq = []
    for u in out:
        if u not in seen:
            uniq.append(u)
            seen.add(u)
    return uniq[:limit]

# -------- main build --------

def main():
    indexes = [p for p in ROOT.rglob("index.html") if is_index(p)]
    entries = []

    for idx in sorted(indexes):
        loc = pretty_url_for_index(idx)

        # Prefer git time of the SOURCE html (about.html, books/foo.html)
        src = source_html_for_index(idx)
        lastmod = (git_last_commit_iso(src) if src else None) or fs_mtime_iso(idx)

        images = find_images_in(idx, limit=3)

        entries.append({
            "loc": loc,
            "lastmod": lastmod,
            "images": images,
        })

    # Write XML
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">'
    ]
    for e in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{e['loc']}</loc>")
        lines.append(f"    <lastmod>{e['lastmod']}</lastmod>")
        # optional: light heuristics
        # homepage gets a touch higher priority/changefreq
        if e['loc'].rstrip("/") == SITE:
            lines.append("    <changefreq>weekly</changefreq>")
            lines.append("    <priority>0.9</priority>")
        else:
            lines.append("    <changefreq>monthly</changefreq>")
            lines.append("    <priority>0.6</priority>")
        # images
        for img in e["images"]:
            lines.append("    <image:image>")
            lines.append(f"      <image:loc>{img}</image:loc>")
            lines.append("    </image:image>")
        lines.append("  </url>")
    lines.append("</urlset>\n")

    (ROOT / "sitemap.xml").write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated sitemap.xml with {len(entries)} URLs")

if __name__ == "__main__":
    main()
