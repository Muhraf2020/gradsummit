#!/usr/bin/env python3
# tools/inject_nav.py — replace header nav across all pages (no Jekyll)

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARTIAL = ROOT / "partials" / "nav.html"

NAV_RE = re.compile(
    r'<nav\b[^>]*aria-label=["\']Primary["\'][^>]*>.*?</nav>',
    re.IGNORECASE | re.DOTALL
)

# brand href normalizer: index.html / index / index/ -> /
BRAND_FIXES = [
    (re.compile(r'href=["\']/index\.html["\']', re.I), 'href="/"'),
    (re.compile(r'href=["\']/index/["\']', re.I),      'href="/"'),
    (re.compile(r'href=["\']/index["\']', re.I),        'href="/"'),
    (re.compile(r'href=["\']index\.html["\']', re.I),   'href="/"'),
    (re.compile(r'href=["\']index/["\']', re.I),        'href="/"'),
    (re.compile(r'href=["\']index["\']', re.I),         'href="/"'),
]

def main():
    if not PARTIAL.exists():
        raise SystemExit(f"Missing partial: {PARTIAL}")

    nav_html = PARTIAL.read_text(encoding="utf-8")
    updated = 0
    scanned = 0

    for p in ROOT.rglob("*.html"):
        # Skip the partials folder and CI metadata
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith("partials/") or rel.startswith(".github/"):
            continue

        raw = p.read_text(encoding="utf-8", errors="ignore")
        orig = raw

        # 1) Replace the <nav aria-label="Primary">...</nav> block with the partial
        if NAV_RE.search(raw):
            raw = NAV_RE.sub(nav_html, raw)

        # 2) Normalize brand hrefs to "/"
        for rx, replacement in BRAND_FIXES:
            raw = rx.sub(replacement, raw)

        if raw != orig:
            p.write_text(raw, encoding="utf-8")
            updated += 1
        scanned += 1

    print(f"inject_nav: scanned {scanned} html files, updated {updated}")

if __name__ == "__main__":
    main()
