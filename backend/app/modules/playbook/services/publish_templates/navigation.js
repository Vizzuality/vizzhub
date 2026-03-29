(function () {
  'use strict';

  var STORAGE_KEY = 'playbook-nav-state';

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
    var site = getSite();
    if (site) {
      site.classList.remove('sidebar-open');
    }
  }

  function toggleSidebar() {
    var site = getSite();
    if (site) {
      site.classList.toggle('sidebar-open');
    }
  }

  function getGroupKey(details) {
    var summary = details.querySelector('summary');
    return summary ? summary.textContent.trim() : null;
  }

  function loadNavState() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (e) {
      return {};
    }
  }

  function saveNavState() {
    var state = {};
    var groups = document.querySelectorAll('.nav-group');
    groups.forEach(function (details) {
      var key = getGroupKey(details);
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
    var state = loadNavState();
    var groups = document.querySelectorAll('.nav-group');

    groups.forEach(function (details) {
      var key = getGroupKey(details);
      if (!key) return;

      var hasActive = details.querySelector('.nav-item.active');
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
    var toggle = getToggle();
    var overlay = getOverlay();

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
