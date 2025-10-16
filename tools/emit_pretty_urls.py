#!/usr/bin/env python3
# tools/emit_pretty_urls.py
import os, re
from pathlib import Path
from urllib.parse import urljoin, urlparse

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
    # about.html -> about/index.html ; books/foo.html -> books/foo/index.html
    return p.parent / p.stem / "index.html"

def pretty_url_for_index(pretty_index: Path) -> str:
    rel = pretty_index.relative_to(ROOT).as_posix()
    if rel == "index.html":
        return SITE + "/"
    if rel.endswith("/index.html"):
        return SITE + "/" + rel[:-len("index.html")]
    return SITE + "/" + rel

# --- helpers to normalize attributes in the pretty copy ---

def _absolutize_assets(html: str) -> str:
    # Convert href/src that point to assets/... into root-absolute /assets/...
    # Matches href="assets/..."; href="./assets/..."; href="../assets/..."
    def repl(m):
        attr = m.group('attr')
        q = m.group('q')
        url = m.group('url')
        # Strip leading ./ or ../ segments until we reach assets/
        idx = url.lower().find("assets/")
        if idx == -1:
            return m.group(0)
        fixed = "/" + url[idx:]  # ensure root-absolute /assets/...
        return f'{attr}={q}{fixed}{q}'

    pattern = r'(?P<attr>(?:href|src))=(?P<q>["\'])(?P<url>(?:\./|\.\./)*assets/[^"\']+)(?P=q)'
    return re.sub(pattern, repl, html, flags=re.IGNORECASE)

def _rewrite_absolute_html_links(html: str) -> str:
    # /foo.html -> /foo/   and  /index.html#x -> /#x
    html = re.sub(
        r'href=(["\"])/index\.html(#[^"\']*)?\1',
        lambda m: f'href={m.group(1)}/{m.group(2) or ""}{m.group(1)}',
        html, flags=re.IGNORECASE)
    html = re.sub(
        r'href=(["\"])/([^"\']+?)\.html(#[^"\']*)?\1',
        lambda m: f'href={m.group(1)}/{m.group(2)}/{m.group(3) or ""}{m.group(1)}',
        html, flags=re.IGNORECASE)
    return html

def _rewrite_relative_html_links(html: str, page_web_path: str) -> str:
    """
    Convert relative .html links (e.g., "about.html", "../about.html",
    "qda-with-xxx.html") into absolute slash URLs by resolving against
    the original page directory (NOT the pretty subfolder).
    """
    base_dir = page_web_path.rsplit("/", 1)[0] + "/"  # e.g., "/books/"
    # Match href="<relative>.html" that does NOT start with http(s), mailto, tel, #, or /
    pattern = r'href=(["\'])(?!https?:|mailto:|tel:|#|/)([^"\']+?\.html)(#[^"\']*)?\1'

    def repl(m):
        q, rel_url, anchor = m.group(1), m.group(2), m.group(3) or ""
        # Resolve relative against the original page directory (under the site root)
        resolved = urljoin(SITE + base_dir, rel_url)
        path = urlparse(resolved).path  # "/books/qda-with-xx.html" or "/about.html" etc.

        # Normalize index.html and .html -> slash
        if path.endswith("/index.html"):
            pretty_path = path[:-len("index.html")]
        elif path.endswith(".html"):
            pretty_path = path[:-len(".html")] + "/"
        else:
            pretty_path = path

        return f'href={q}{pretty_path}{anchor}{q}'

    return re.sub(pattern, repl, html, flags=re.IGNORECASE)

def _fix_canonical_and_og(html: str, pretty_url: str) -> str:
    # canonical
    html = re.sub(
        r'(<link\s+rel=["\']canonical["\']\s+href=["\'])([^"\']+)(["\'])',
        lambda m: m.group(1) + pretty_url + m.group(3),
        html, flags=re.IGNORECASE)
    # og:url
    html = re.sub(
        r'(<meta\s+property=["\']og:url["\']\s+content=["\'])([^"\']+)(["\'])',
        lambda m: m.group(1) + pretty_url + m.group(3),
        html, flags=re.IGNORECASE)
    # Any absolute content=.../something.html -> .../something/
    dom = re.escape(SITE)
    html = re.sub(
        r'content=(["\"])'+dom+r'/([^"\']+?)\.html(#[^"\']*)?(\1)',
        lambda m: f'content={m.group(1)}{SITE}/{m.group(2)}/{m.group(3) or ""}{m.group(4)}',
        html, flags=re.IGNORECASE)
    return html

def rewrite_document_for_pretty(html: str, pretty_url: str, page_web_path: str) -> str:
    html = _fix_canonical_and_og(html, pretty_url)
    html = _absolutize_assets(html)             # make assets root-absolute
    html = _rewrite_absolute_html_links(html)   # /foo.html -> /foo/
    html = _rewrite_relative_html_links(html, page_web_path)  # ../foo.html -> /foo/
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
        page_web_path = "/" + p.relative_to(ROOT).as_posix()  # e.g., "/about.html"

        pretty_html = rewrite_document_for_pretty(raw, pretty_url, page_web_path)
        pretty_index.write_text(pretty_html, encoding="utf-8")

        # Overwrite the original .html with an instant redirect stub
        p.write_text(REDIRECT_STUB.format(to=pretty_url), encoding="utf-8")

        changed.append((p.relative_to(ROOT).as_posix(), pretty_index.relative_to(ROOT).as_posix()))

    print(f"Emitted {len(changed)} pretty pages and redirect stubs:")
    for old, new in changed:
        print(f"  {old} -> {new}")

if __name__ == "__main__":
    main()
