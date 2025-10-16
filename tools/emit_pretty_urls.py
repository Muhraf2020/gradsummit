#!/usr/bin/env python3
# tools/emit_pretty_urls.py — image-safe pretty URLs

import os, re
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parent.parent
SITE = os.environ.get("SITE_DOMAIN", "https://www.gradsummit.com").rstrip("/")

def ignore(p: Path) -> bool:
    rel = p.relative_to(ROOT).as_posix()
    if rel == "404.html":                      # keep GitHub Pages 404 at /404.html
        return True
    if rel.startswith(("partials/", ".github/")):  # NEW: never emit partials or CI
        return True
    if p.name == "index.html":                 # skip any existing index.html
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

# ---------- URL helpers ----------

PROTO_RE = re.compile(r'^(?:https?:|mailto:|tel:|data:|blob:|#|/)', re.I)

def _resolve_to_root_absolute(rel_url: str, base_dir: str) -> str:
    """
    Resolve rel_url against site root + base_dir, return a root-absolute path /...
    """
    absolute = urljoin(SITE + base_dir, rel_url)
    path = urlparse(absolute).path
    return path if path.startswith("/") else "/" + path

# ---------- Rewriters for the pretty copy ----------

def _fix_canonical_og_and_meta_images(html: str, pretty_url: str) -> str:
    # canonical
    html = re.sub(
        r'(<link\s+rel=["\']canonical["\']\s+href=["\'])([^"\']+)(["\'])',
        lambda m: m.group(1) + pretty_url + m.group(3),
        html, flags=re.I)
    # og:url
    html = re.sub(
        r'(<meta\s+property=["\']og:url["\']\s+content=["\'])([^"\']+)(["\'])',
        lambda m: m.group(1) + pretty_url + m.group(3),
        html, flags=re.I)
    # og:image / twitter:image -> absolute FULL URL
    def _imgmeta(attr):
        return re.sub(
            rf'(<meta\s+(?:property|name)=["\']{attr}["\']\s+content=["\'])([^"\']+)(["\'])',
            lambda m: m.group(1) + (
                m.group(2) if PROTO_RE.match(m.group(2))
                else SITE + _resolve_to_root_absolute(m.group(2), "/")
            ) + m.group(3),
            html, flags=re.I)
    html = _imgmeta(r'(?:og:image|twitter:image)')
    return html

def _rewrite_absolute_html_links(html: str) -> str:
    # /index or /index/ -> /
    html = re.sub(
        r'href=(["\'])/index/?(#[^"\']*)?\1',
        lambda m: f'href={m.group(1)}/{m.group(2) or ""}{m.group(1)}',
        html, flags=re.I
    )
    # /index.html -> /
    html = re.sub(
        r'href=(["\'])/index\.html(#[^"\']*)?\1',
        lambda m: f'href={m.group(1)}/{m.group(2) or ""}{m.group(1)}',
        html, flags=re.I)
    # /foo.html -> /foo/
    html = re.sub(
        r'href=(["\'])/([^"\']+?)\.html(#[^"\']*)?\1',
        lambda m: f'href={m.group(1)}/{m.group(2)}/{m.group(3) or ""}{m.group(1)}',
        html, flags=re.I)
    return html

def _rewrite_relative_html_links(html: str, base_dir: str) -> str:
    """
    Turn relative HREFs ending with .html into pretty absolute slash URLs,
    resolved against the ORIGINAL PAGE directory (e.g., /books/).
    """
    pattern = r'href=(["\'])(?!https?:|mailto:|tel:|#|/)([^"\']+?\.html)(#[^"\']*)?\1'
    def repl(m):
        q, rel_url, anchor = m.group(1), m.group(2), m.group(3) or ""
        resolved_path = _resolve_to_root_absolute(rel_url, base_dir)
        # /x/index.html -> /x/ ; /x.html -> /x/
        if resolved_path.endswith("/index.html"):
            pretty_path = resolved_path[:-len("index.html")]
        elif resolved_path.endswith(".html"):
            pretty_path = resolved_path[:-len(".html")] + "/"
        else:
            pretty_path = resolved_path
        return f'href={q}{pretty_path}{anchor}{q}'
    return re.sub(pattern, repl, html, flags=re.I)

def _rewrite_relative_assets(html: str, base_dir: str) -> str:
    """
    Resolve relative asset URLs (img/video/link/etc) to root-absolute:
    - src, data-src, poster, href (non-HTML targets), preload as, etc.
    Excludes protocols, data:, blob:, #, and '/'-rooted.
    """
    # 1) src/href/poster/data-src (single URL)
    pattern = r'(?P<attr>src|href|poster|data-src)=(?P<q>["\'])(?P<url>(?!https?:|mailto:|tel:|data:|blob:|#|/)[^"\']+)(?P=q)'
    def repl(m):
        attr, q, url = m.group('attr'), m.group('q'), m.group('url')
        # skip .html here; those were (or will be) handled elsewhere
        if url.lower().endswith('.html'):
            return m.group(0)
        fixed = _resolve_to_root_absolute(url, base_dir)
        return f'{attr}={q}{fixed}{q}'
    html = re.sub(pattern, repl, html, flags=re.I)

    # 2) srcset/data-srcset (multiple URLs with descriptors)
    def fix_srcset_val(val: str) -> str:
        parts = [p.strip() for p in val.split(",") if p.strip()]
        fixed_parts = []
        for p in parts:
            # split first whitespace into url + rest (descriptor)
            if " " in p:
                url, desc = p.split(" ", 1)
            else:
                url, desc = p, ""
            if not PROTO_RE.match(url):
                url = _resolve_to_root_absolute(url, base_dir)
            fixed_parts.append((url + (" " + desc if desc else "")).strip())
        return ", ".join(fixed_parts)

    pattern_set = r'(?P<attr>srcset|data-srcset)=(?P<q>["\'])(?P<val>[^"\']+)(?P=q)'
    def repl_set(m):
        return f'{m.group("attr")}={m.group("q")}{fix_srcset_val(m.group("val"))}{m.group("q")}'
    html = re.sub(pattern_set, repl_set, html, flags=re.I)

    # 3) Inline CSS url(...) inside style=""
    def fix_style(style_val: str) -> str:
        def repl_url(m):
            q = m.group('q') or ''
            url = m.group('url')
            if PROTO_RE.match(url):
                return m.group(0)
            fixed = _resolve_to_root_absolute(url, base_dir)
            return f'url({q}{fixed}{q})'
        return re.sub(r'url\((?P<q>["\']?)(?P<url>[^)\'"]+)(?P=q)\)', repl_url, style_val, flags=re.I)

    def style_repl(m):
        q, val = m.group(1), m.group(2)
        return f'style={q}{fix_style(val)}{q}'

    html = re.sub(r'style=(["\'])([^"\']*)(\1)', style_repl, html, flags=re.I)
    return html

def rewrite_document_for_pretty(html: str, pretty_url: str, page_web_path: str) -> str:
    # base_dir like "/books/" for "/books/slug.html"
    base_dir = page_web_path.rsplit("/", 1)[0] + "/"
    html = _fix_canonical_og_and_meta_images(html, pretty_url)
    html = _rewrite_absolute_html_links(html)             # /foo.html -> /foo/
    html = _rewrite_relative_html_links(html, base_dir)   # ../foo.html -> /foo/
    html = _rewrite_relative_assets(html, base_dir)       # fix img/srcset/style urls
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
        if ignore(p):
            continue

        pretty_index = to_pretty_index(p)
        pretty_index.parent.mkdir(parents=True, exist_ok=True)

        raw = p.read_text(encoding="utf-8", errors="ignore")
        pretty_url = pretty_url_for_index(pretty_index)
        page_web_path = "/" + p.relative_to(ROOT).as_posix()  # e.g., "/books/slug.html"

        pretty_html = rewrite_document_for_pretty(raw, pretty_url, page_web_path)
        pretty_index.write_text(pretty_html, encoding="utf-8")

        # Overwrite original .html with an instant redirect stub
        p.write_text(REDIRECT_STUB.format(to=pretty_url), encoding="utf-8")

        changed.append((p.relative_to(ROOT).as_posix(), pretty_index.relative_to(ROOT).as_posix()))

    # >>> NEW: make root index.html links pretty (no client redirects needed)
    root_index = ROOT / "index.html"
    if root_index.exists():
        s = root_index.read_text(encoding="utf-8", errors="ignore")
        # /index.html -> /
        s = re.sub(
            r'href=(["\'])/index\.html(#[^"\']*)?\1',
            lambda m: f'href={m.group(1)}/{m.group(2) or ""}{m.group(1)}',
            s, flags=re.I
        )
        # /index or /index/ -> /
        s = re.sub(
            r'href=(["\'])/index/?(#[^"\']*)?\1',
            lambda m: f'href={m.group(1)}/{m.group(2) or ""}{m.group(1)}',
            s, flags=re.I
        )
        # /foo.html -> /foo/
        s = re.sub(
            r'href=(["\'])/([^"\']+?)\.html(#[^"\']*)?\1',
            lambda m: f'href={m.group(1)}/{m.group(2)}/{m.group(3) or ""}{m.group(1)}',
            s, flags=re.I
        )
        # relative .html on the homepage -> pretty (optional)
        s = re.sub(
            r'href=(["\'])(?!https?:|mailto:|tel:|#|/)([^"\']+?)\.html(#[^"\']*)?\1',
            lambda m: f'href={m.group(1)}/{m.group(2)}/{m.group(3) or ""}{m.group(1)}',
            s, flags=re.I
        )
        root_index.write_text(s, encoding="utf-8")
    # <<< END NEW

    print(f"Emitted {len(changed)} pretty pages and redirect stubs:")
    for old, new in changed:
        print(f"  {old} -> {new}")

if __name__ == "__main__":
    main()
