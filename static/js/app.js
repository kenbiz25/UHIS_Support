// ── Safe localStorage wrapper — survives Edge Tracking Prevention ─────────────
function _lsGet(k, def) { try { return localStorage.getItem(k) ?? def; } catch(e) { return def; } }
function _lsSet(k, v)   { try { localStorage.setItem(k, v); } catch(e) {} }

// ── Dark mode ─────────────────────────────────────────────────────────────────
(function () {
  const root = document.documentElement;
  const icon = document.getElementById('themeIcon');
  function applyTheme(t) {
    root.setAttribute('data-bs-theme', t);
    if (icon) icon.className = t === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
  }
  applyTheme(_lsGet('theme', 'light'));
  const btn = document.getElementById('themeToggle');
  if (btn) btn.addEventListener('click', function() {
    const next = root.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
    _lsSet('theme', next);
    applyTheme(next);
  });
})();

// ── Keyboard shortcuts ────────────────────────────────────────────────────────
document.addEventListener('keydown', function (e) {
  const tag = document.activeElement.tagName.toUpperCase();
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || document.activeElement.isContentEditable) return;
  if (e.altKey && e.key.toLowerCase() === 't') {
    document.getElementById('themeToggle')?.click(); return;
  }
  const urls = window.APP_URLS || {};
  const map = {
    'n': urls.createTicket,
    'i': urls.unifiedInbox,
    'd': urls.dashboard,
    'r': urls.reports,
  };
  if (map[e.key.toLowerCase()]) { window.location.href = map[e.key.toLowerCase()]; return; }
  if (e.key === '/') {
    e.preventDefault();
    document.querySelector('input[name=search], input[type=search]')?.focus();
    return;
  }
  if (e.key === '?') {
    bootstrap.Modal.getOrCreateInstance(document.getElementById('shortcutsModal')).toggle();
  }
});

// ── Drag-and-drop file zones ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.drop-zone').forEach(function (zone) {
    const input = zone.querySelector('input[type=file]');
    zone.addEventListener('click', function () { if (input) input.click(); });
    zone.addEventListener('dragover', function (e) { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', function () { zone.classList.remove('drag-over'); });
    zone.addEventListener('drop', function (e) {
      e.preventDefault();
      zone.classList.remove('drag-over');
      if (input && e.dataTransfer.files.length) {
        try {
          const dt = new DataTransfer();
          Array.from(e.dataTransfer.files).forEach(function(f) { dt.items.add(f); });
          input.files = dt.files;
          const label = zone.querySelector('.drop-label');
          if (label) label.textContent = Array.from(dt.files).map(function(f) { return f.name; }).join(', ');
        } catch(err) {}
      }
    });
  });
});

// ── Mobile-collapsible sections ────────────────────────────────────────────────
// <details class="mobile-collapsible" open> stays open on tablet/desktop but
// starts collapsed on phones, so secondary content doesn't push the essentials
// (e.g. the actual form fields) below the fold.
document.addEventListener('DOMContentLoaded', function () {
  if (window.innerWidth < 768) {
    document.querySelectorAll('details.mobile-collapsible').forEach(function (d) {
      d.removeAttribute('open');
    });
  }
});

// ── Notification polling ──────────────────────────────────────────────────────
(function pollNotifications() {
  const apiUrl = (window.APP_URLS || {}).notifCount;
  if (!apiUrl) return;
  function update() {
    fetch(apiUrl)
      .then(function(r) { return r.json(); })
      .then(function(data) {
        document.querySelectorAll('.notif-count').forEach(function(el) {
          if (data.count > 0) {
            el.textContent = data.count > 99 ? '99+' : data.count;
            el.style.display = '';
          } else {
            el.style.display = 'none';
          }
        });
      }).catch(function() {});
  }
  update();
  setInterval(update, 30000);
})();
