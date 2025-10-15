// v3 — robust Amazon click tracking for GA4
(function () {
  function getAnchorFromEvent(ev) {
    // Prefer composedPath (works through nested elements/shadow DOM)
    if (typeof ev.composedPath === 'function') {
      const path = ev.composedPath();
      for (const n of path) {
        if (n && n.tagName === 'A' && n.href) return n;
      }
    }
    // Fallback to closest
    const t = ev.target;
    if (t && t.closest) {
      const a = t.closest('a[href]');
      if (a) return a;
    }
    return null;
  }

  function isAmazonUrl(href) {
    try {
      const u = new URL(href, location.href);
      // match *.amazon.<tld>
      return /(^|\.)amazon\./i.test(u.hostname);
    } catch {
      return false;
    }
  }

  function track(ev) {
    const a = getAnchorFromEvent(ev);
    if (!a) return;
    const href = a.getAttribute('href') || a.href || '';
    if (!isAmazonUrl(href)) return;

    // Send GA4 event
    if (typeof gtag === 'function') {
      gtag('event', 'amazon_click', {
        link_url: a.href || href,
        link_text: (a.textContent || '').trim(),
        page_location: location.href,
        transport_type: 'beacon'
      });
    }
  }

  // Capture phase so we run before navigation
  document.addEventListener('click', track, true);
  // Middle-click (new tab)
  document.addEventListener('auxclick', function (e) {
    if (e.button === 1) track(e);
  }, true);

  // Optional: quick console signal that the file loaded
  // console.log('[amazon-track] loaded');
})();
