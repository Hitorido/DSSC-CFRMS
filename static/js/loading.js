(function () {
  'use strict';

  var root = document.documentElement;
  var queuedRegions = window.CFRMSLoading ? window.CFRMSLoading.pending || [] : [];
  var regions = new Map();
  var pendingRegions = new Set();
  var submissions = new Map();
  var pageTarget;
  var targetState;
  var recoveryTimer;
  var lastKind = 'table';

  function announce(label) {
    var status = document.getElementById('cfrmsLoadingStatus');
    if (status) status.textContent = label || '';
  }

  function getTarget() {
    return document.querySelector('[data-loading-root]') || document.getElementById('content-start') || document.querySelector('main');
  }

  function currentKind() {
    var target = getTarget();
    if (!target) return 'detail';
    var pages = { home: 'dashboard', profile: 'profile', login: 'login', register: 'register', settings: 'settings' };
    if (pages[target.dataset.loadingPage]) return pages[target.dataset.loadingPage];
    if (target.querySelector('.cfrms-form, .password-form, .submit-row')) return 'form';
    if (target.querySelector('.dashboard-overview')) return 'dashboard';
    if (target.querySelector('.facility-calendar-card')) return 'calendar';
    if (target.querySelector('.table, #result_list, #changelist, table')) return 'table';
    if (target.querySelector('form:not([method="get"])')) return 'form';
    return 'detail';
  }

  function destinationKind(url) {
    var path = url.pathname.replace(/\/$/, '');
    if (!path) return 'dashboard';
    if (/^\/profile$/.test(path)) return 'profile';
    if (/^\/login$/.test(path)) return 'login';
    if (/^\/register$/.test(path)) return 'register';
    if (/\/(create|edit|appeal|add|change)$/.test(path)) return 'form';
    if (/^\/facilities\/\d+$/.test(path)) return 'calendar';
    if (/\/settings$/.test(path)) return 'settings';
    if (/\/done$/.test(path)) return 'detail';
    if (/\/(\d+|detail)$/.test(path)) return 'detail';
    if (/\/(facilities|maintenance|my|pending|report|notifications|admin-console|admin)$/.test(path)) return 'table';
    if (path.indexOf('/admin/') === 0) return 'table';
    return currentKind();
  }

  function positionLoader() {
    var loader = document.getElementById('cfrmsPageLoader');
    var target = getTarget();
    if (!loader || !target) return;
    if (loader.dataset.loadingView === 'login' || loader.dataset.loadingView === 'register') {
      loader.style.removeProperty('padding');
      return;
    }
    var bounds = target.getBoundingClientRect();
    if (target.id === 'cfrmsMain') loader.style.padding = window.getComputedStyle(target).padding;
    else loader.style.removeProperty('padding');
    var bar = document.querySelector('.cfrms-topbar');
    loader.style.setProperty('--cfrms-loading-top', Math.max(0, bounds.top, bar ? bar.getBoundingClientRect().bottom : 0) + 'px');
    loader.style.setProperty('--cfrms-loading-left', Math.max(0, bounds.left) + 'px');
    loader.style.setProperty('--cfrms-loading-right', Math.max(0, document.documentElement.clientWidth - bounds.right) + 'px');
  }

  function showPage(label, kind, initial) {
    var loader = document.getElementById('cfrmsPageLoader');
    if (!loader) return;
    if (!initial) {
      document.querySelectorAll('dialog[open]').forEach(function (dialog) { dialog.close(); });
    }
    lastKind = kind || currentKind();
    loader.hidden = false;
    loader.dataset.loadingView = lastKind;
    loader.querySelector('[data-loading-caption]').textContent = label || 'Loading page…';
    loader.querySelector('[data-loading-recovery]').hidden = true;
    if (!pageTarget) {
      pageTarget = getTarget();
      if (pageTarget) {
        targetState = { busy: pageTarget.getAttribute('aria-busy'), inert: pageTarget.hasAttribute('inert') };
        pageTarget.setAttribute('aria-busy', 'true');
        pageTarget.setAttribute('inert', '');
      }
    }
    positionLoader();
    root.dataset.cfrmsPageLoading = initial ? 'initial' : 'navigation';
    announce(label || 'Loading page…');
    window.clearTimeout(recoveryTimer);
    recoveryTimer = window.setTimeout(function () {
      loader.querySelector('[data-loading-recovery]').hidden = false;
    }, 15000);
  }

  function hidePage() {
    delete root.dataset.cfrmsPageLoading;
    var loader = document.getElementById('cfrmsPageLoader');
    if (loader) loader.hidden = true;
    window.clearTimeout(recoveryTimer);
    if (pageTarget && targetState) {
      if (targetState.busy === null) pageTarget.removeAttribute('aria-busy');
      else pageTarget.setAttribute('aria-busy', targetState.busy);
      pageTarget.toggleAttribute('inert', targetState.inert);
    }
    pageTarget = null;
    targetState = null;
    if (submissions.size) announce('Your request is still being submitted.');
    else announce(pendingRegions.size ? 'Loading data…' : '');
  }

  function beginRegion(element, label) {
    if (!element) return function () {};
    var token = {};
    var state = regions.get(element);
    if (!state) {
      var skeleton = document.createElement('div');
      skeleton.className = 'cfrms-region-skeleton';
      skeleton.setAttribute('aria-hidden', 'true');
      for (var index = 0; index < 3; index += 1) {
        var bone = document.createElement('span');
        bone.className = 'cfrms-skeleton-bone';
        skeleton.appendChild(bone);
      }
      state = { skeleton: skeleton, busy: element.getAttribute('aria-busy') };
      element.appendChild(skeleton);
      element.setAttribute('aria-busy', 'true');
      element.dataset.cfrmsRegionLoading = 'true';
      regions.set(element, state);
    }
    state.token = token;
    pendingRegions.add(token);
    root.dataset.cfrmsNetworkLoading = 'true';
    announce(label || 'Loading data…');
    var finished = false;
    return function () {
      if (finished) return;
      finished = true;
      pendingRegions.delete(token);
      if (regions.get(element) === state && state.token === token) {
        state.skeleton.remove();
        delete element.dataset.cfrmsRegionLoading;
        if (state.busy === null) element.removeAttribute('aria-busy');
        else element.setAttribute('aria-busy', state.busy);
        regions.delete(element);
      }
      if (!pendingRegions.size) {
        delete root.dataset.cfrmsNetworkLoading;
        if (!root.dataset.cfrmsPageLoading) announce('');
      }
    };
  }

  function restoreSubmissions() {
    submissions.forEach(function (state, form) {
      if (state.button) {
        state.button.classList.remove('cfrms-button-loading', 'cfrms-icon-loading');
        ['aria-busy', 'aria-disabled'].forEach(function (name) {
          if (state[name] === null) state.button.removeAttribute(name);
          else state.button.setAttribute(name, state[name]);
        });
      }
    });
    submissions.clear();
  }

  function navigableUrl(value) {
    try {
      var url = new URL(value, window.location.href);
      if (url.origin !== window.location.origin || !/^https?:$/.test(url.protocol)) return null;
      if (/\.(pdf|csv|xlsx?|zip|png|jpe?g|webp)$/i.test(url.pathname)) return null;
      return url;
    } catch (error) { return null; }
  }

  function navigate(value) {
    var url = navigableUrl(value);
    if (url) showPage('Loading page…', destinationKind(url));
    window.location.assign(value);
  }

  document.addEventListener('click', function (event) {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    var link = event.target.closest('a[href]');
    if (!link || link.closest('[data-loading-skip]') || link.hasAttribute('download') || (link.target && link.target !== '_self')) return;
    if (link.classList.contains('related-widget-wrapper-link')) return;
    var url = navigableUrl(link.href);
    if (!url || (url.pathname === window.location.pathname && url.search === window.location.search && url.hash)) return;
    Promise.resolve().then(function () {
      if (!event.defaultPrevented) showPage('Loading page…', destinationKind(url));
    });
  });

  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (event.defaultPrevented || form.closest('[data-loading-skip]') || form.method === 'dialog') return;
    var button = event.submitter || form.querySelector('button[type="submit"]:not(:disabled), input[type="submit"]:not(:disabled)');
    var target = button && button.formTarget || form.target;
    if (target && target !== '_self') return;
    if (!navigableUrl(button && button.formAction || form.action || window.location.href)) return;
    if (submissions.has(form)) {
      event.preventDefault();
      return;
    }
    Promise.resolve().then(function () {
      if (event.defaultPrevented) return;
      var state = { button: button };
      if (button) {
        state['aria-busy'] = button.getAttribute('aria-busy');
        state['aria-disabled'] = button.getAttribute('aria-disabled');
        button.classList.add('cfrms-button-loading');
        button.classList.toggle('cfrms-icon-loading', !button.textContent.trim());
        button.setAttribute('aria-busy', 'true');
        button.setAttribute('aria-disabled', 'true');
      }
      submissions.set(form, state);
      var url = navigableUrl(button && button.formAction || form.action || window.location.href);
      var isGet = (button && button.formMethod || form.method).toLowerCase() === 'get';
      var kind = currentKind();
      var label = isGet ? 'Loading results…' : kind === 'login' ? 'Signing in…' : kind === 'register' ? 'Creating account…' : 'Submitting…';
      showPage(label, isGet && url ? destinationKind(url) : kind);
    });
  });

  window.addEventListener('beforeunload', function () {
    if (!root.dataset.cfrmsPageLoading) showPage('Loading page…', lastKind);
  });
  window.addEventListener('resize', positionLoader);
  window.addEventListener('pageshow', function (event) {
    if (event.persisted) {
      restoreSubmissions();
      regions.forEach(function (state, element) {
        state.skeleton.remove();
        delete element.dataset.cfrmsRegionLoading;
        if (state.busy === null) element.removeAttribute('aria-busy');
        else element.setAttribute('aria-busy', state.busy);
      });
      regions.clear();
      pendingRegions.clear();
      delete root.dataset.cfrmsNetworkLoading;
      hidePage();
    }
  });

  window.CFRMSLoading = { showPage: showPage, hidePage: hidePage, beginRegion: beginRegion, navigate: navigate };
  queuedRegions.forEach(function (task) {
    if (!task.done) task.finish = beginRegion(task.element, task.label);
  });

  function ready() {
    var loader = document.getElementById('cfrmsPageLoader');
    if (!loader) return;
    window.clearTimeout(window.cfrmsLoadingFallback);
    loader.querySelector('[data-loading-recovery]').addEventListener('click', function () {
      hidePage();
      var heading = getTarget() && getTarget().querySelector('h1');
      if (heading) {
        var hadTabindex = heading.hasAttribute('tabindex');
        if (!hadTabindex) heading.setAttribute('tabindex', '-1');
        heading.focus({ preventScroll: true });
        if (!hadTabindex) heading.addEventListener('blur', function () { heading.removeAttribute('tabindex'); }, { once: true });
      }
    });
    if (root.dataset.cfrmsPageLoading === 'initial') {
      showPage('Loading page…', loader.dataset.loadingView, true);
      window.requestAnimationFrame(function () {
        if (root.dataset.cfrmsPageLoading === 'initial') hidePage();
      });
    }
  }
  if (document.readyState !== 'complete') document.addEventListener('DOMContentLoaded', ready, { once: true });
  else ready();
}());
