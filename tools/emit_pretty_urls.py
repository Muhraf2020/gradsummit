#!/usr/bin/env python3
# tools/emit_pretty_urls.py
import os, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = os.environ.get("SITE_DOMAIN", "https://www.gradsummit.com").rstrip("/")

def ignore(p: Path) -> bool:
    rel = p.relative_to(ROOT).as_posix()
    # keep 404.html and any existing index.html files as-is
    if rel == "404.html":
        return True
    if p.name == "index.html":
        return True
    return False

def to_pretty_index(p: Path) -> Path:
    # about.html -> about/index.html
    stem = p.stem
    return p.parent / stem / "index.html"

def pretty_url_for_index(pretty_index: Path) -> str:
    rel = pretty_index.relative_to(ROOT).as_posix()
    if rel == "index.html":
        return SITE + "/"
    if rel.endswith("/index.html"):
        return SITE + "/" + rel[:-len("index.html")]
    return SITE + "/" + rel

def rewrite_document_for_pretty(html: str, pretty_url: str) -> str:
    # Update canonical & og:url if present
    html = re.sub(
        r'(<link\s+rel=["\']canonical["\']\s+href=["\'])([^"\']+)(["\'])',
        lambda m: m.group(1) + pretty_url + m.group(3),
        html, flags=re.I)
    html = re.sub(
        r'(<meta\s+property=["\']og:url["\']\s+content=["\'])([^"\']+)(["\'])',
        lambda m: m.group(1) + pretty_url + m.group(3),
        html, flags=re.I)

    # Convert internal .html links → slash versions (root-absolute and same-domain)
    dom = re.escape(SITE)
    # /foo.html -> /foo/
    html = re.sub(r'href=([\'"])/([^"\']+?)\.html(#[^"\']*)?([\'"])',
                  lambda m: f'href={m.group(1)}/{m.group(2)}/{m.group(3) or ""}{m.group(4)}',
                  html)
    # https://site/foo.html -> https://site/foo/
    html = re.sub(r'href=([\'"])'+dom+r'/([^"\']+?)\.html(#[^"\']*)?([\'"])',
                  lambda m: f'href={m.group(1)}{SITE}/{m.group(2)}/{m.group(3) or ""}{m.group(4)}',
                  html)
    # Also fix og:url or other content attributes with absolute .html
    html = re.sub(r'content=([\'"])'+dom+r'/([^"\']+?)\.html(#[^"\']*)?([\'"])',
                  lambda m: f'content={m.group(1)}{SITE}/{m.group(2)}/{m.group(3) or ""}{m.group(4)}',
                  html)
    return html

REDIRECT_STUB = """<!doctype html><meta charset="utf-8">
<title>Redirecting...</title>
<link rel="canonical" href="{to}">
<meta http-equiv="refresh" content="0; url={to}">
<script>location.replace("{to}");</script>
"""

def main():
    html_files = [p for p in ROOT.rglob("*.html")]
    changed = []
    for p in html_files:
        if ignore(p):  # skip root 404.html and any index.html
            continue

        pretty_index = to_pretty_index(p)
        pretty_index.parent.mkdir(parents=True, exist_ok=True)

        raw = p.read_text(encoding="utf-8", errors="ignore")
        pretty_url = pretty_url_for_index(pretty_index)

        # Write pretty copy with updated canonical/og/url + internal links
        pretty_html = rewrite_document_for_pretty(raw, pretty_url)
        pretty_index.write_text(pretty_html, encoding="utf-8")

        # Overwrite the original .html with an instant redirect stub
        p.write_text(REDIRECT_STUB.format(to=pretty_url), encoding="utf-8")

        changed.append((p.relative_to(ROOT).as_posix(), pretty_index.relative_to(ROOT).as_posix()))

    print(f"Emitted {len(changed)} pretty pages and redirect stubs:")
    for old, new in changed:
        print(f"  {old} -> {new}")

if __name__ == "__main__":
    main()
