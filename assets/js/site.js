// Only one <details> open per FAQ
(function () {
  function closeSiblings(current) {
    // Prefer .faq; fall back to the nearest section or parent node
    const scope =
      current.closest('.faq') ||
      current.closest('section') ||
      current.parentElement ||
      document;
    scope.querySelectorAll('details[open]').forEach((d) => {
      if (d !== current) d.open = false;
    });
  }

  // Fires after the open/close state changes
  document.addEventListener(
    'toggle',
    (e) => {
      const el = e.target;
      if (el && el.tagName === 'DETAILS' && el.open) closeSiblings(el);
    },
    true
  );
})();
