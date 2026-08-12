(function () {
  'use strict';

  const STORAGE_KEY = 'playbook-nav-state';

  function getToggle() {
    return document.querySelector('.sidebar-toggle');
  }

  function getSite() {
    return document.querySelector('.site');
  }

  function getOverlay() {
    return document.querySelector('.sidebar-overlay');
  }

  function isMobile() {
    return window.innerWidth <= 768;
  }

  function closeSidebar() {
    const site = getSite();
    if (site) {
      site.classList.remove('sidebar-open');
    }
  }

  function toggleSidebar() {
    const site = getSite();
    if (site) {
      site.classList.toggle('sidebar-open');
    }
  }

  function getGroupKey(details) {
    const summary = details.querySelector('summary');
    return summary ? summary.textContent.trim() : null;
  }

  function loadNavState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (e) {
      // Corrupt JSON or unavailable localStorage: fall back to default state.
      console.warn('playbook-nav: could not restore nav state', e);
      return {};
    }
  }

  function saveNavState() {
    const state = {};
    const groups = document.querySelectorAll('.nav-group');
    groups.forEach(function (details) {
      const key = getGroupKey(details);
      if (key) {
        state[key] = details.open;
      }
    });
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (e) {
      // localStorage unavailable
    }
  }

  function restoreNavState() {
    const state = loadNavState();
    const groups = document.querySelectorAll('.nav-group');

    groups.forEach(function (details) {
      const key = getGroupKey(details);
      if (!key) return;

      const hasActive = details.querySelector('.nav-item.active');
      if (hasActive) {
        details.open = true;
        return;
      }

      if (state.hasOwnProperty(key)) {
        details.open = state[key];
      }
    });
  }

  function init() {
    const toggle = getToggle();
    const overlay = getOverlay();

    if (toggle) {
      toggle.addEventListener('click', function (e) {
        e.preventDefault();
        toggleSidebar();
      });
    }

    if (overlay) {
      overlay.addEventListener('click', closeSidebar);
    }

    restoreNavState();

    document.querySelectorAll('.nav-group').forEach(function (details) {
      details.addEventListener('toggle', saveNavState);
    });

    if (isMobile()) {
      document.querySelectorAll('.nav-item').forEach(function (link) {
        link.addEventListener('click', closeSidebar);
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
