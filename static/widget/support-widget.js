(function () {
  'use strict';

  // ── Config ──────────────────────────────────────────────────────────────────
  var scriptEl = document.currentScript ||
    (function () {
      var scripts = document.querySelectorAll('script[data-base-url]');
      return scripts[scripts.length - 1];
    })();

  var BASE_URL      = (scriptEl && scriptEl.getAttribute('data-base-url'))      || '';
  var APP           = (scriptEl && scriptEl.getAttribute('data-app'))           || '';
  var TOKEN         = (scriptEl && scriptEl.getAttribute('data-token'))         || '';
  var PRIMARY_COLOR = (scriptEl && scriptEl.getAttribute('data-primary-color')) || '#2514BE';
  var USER_NAME     = (scriptEl && scriptEl.getAttribute('data-name'))          || '';
  var USER_CONTACT  = (scriptEl && scriptEl.getAttribute('data-contact'))       || '';
  var DEFAULT_LANG  = (scriptEl && scriptEl.getAttribute('data-lang'))          || 'en';
  var WHATSAPP_NUM  = (scriptEl && scriptEl.getAttribute('data-whatsapp'))      || '';

  if (!BASE_URL) return; // nothing to do without a base URL

  // ── i18n ────────────────────────────────────────────────────────────────────
  var STRINGS = {
    en: {
      aria_support: 'Support', aria_widget: 'Support Widget',
      aria_close_panel: 'Close support panel', aria_close: 'Close',
      search_placeholder: 'Search for help...', aria_search_kb: 'Search knowledge base',
      btn_submit_request_secondary: 'Submit a Support Request', searching: 'Searching…',
      empty_no_results: "Can't find what you need?", btn_submit_request: 'Submit a Request',
      search_failed: 'Search failed. Please try again.', article_fallback: 'Article',
      back_to_search: 'Back to search', label_name: 'Name', placeholder_name: 'Your full name',
      label_contact: 'Phone or Email', placeholder_contact: 'Phone number or email address',
      label_issue: 'Issue Description', placeholder_issue: 'Describe your issue or question in detail…',
      err_required: 'Please fill in all required fields.', submitting: 'Submitting…',
      btn_submit_request_primary: 'Submit Request', err_submit_failed: 'Submission failed. Please try again.',
      title_ticket_status: 'Ticket Status', success_submitted: 'Your request has been submitted successfully.',
      label_ticket_ref: 'Ticket Reference', label_status: 'Status',
      status_open: 'Open', status_inprogress: 'In Progress', status_resolved: 'Resolved', status_closed: 'Closed',
      rate_experience: 'Rate your support experience', thanks_feedback: 'Thank you for your feedback!',
      btn_submit_another: 'Submit Another Request',
      touchpoints_label: 'Or get help another way',
      btn_chat_whatsapp: 'Chat on WhatsApp', btn_ask_ai: 'Ask AI Assistant',
      ai_chat_title: 'AI Assistant', ai_input_placeholder: 'Type your question...',
      ai_thinking: 'Thinking...', ai_contact_intro: "Great, let's get this logged. Please share your details:",
      btn_create_ticket: 'Create Ticket', ai_send: 'Send',
      ai_intake_intro: "Before we get started, it helps to have your details on file:",
      label_mobile: 'Mobile Number', placeholder_mobile: 'Your mobile number',
      label_email: 'Email', placeholder_email: 'Your email address',
      label_division: 'Division', btn_continue: 'Continue', btn_skip: 'Skip for now',
    },
    bn: {
      aria_support: 'সমর্থন', aria_widget: 'সমর্থন উইজেট',
      aria_close_panel: 'সমর্থন প্যানেল বন্ধ করুন', aria_close: 'বন্ধ',
      search_placeholder: 'সাহায্যের জন্য অনুসন্ধান করুন...', aria_search_kb: 'জ্ঞানের ভিত্তি অনুসন্ধান করুন',
      btn_submit_request_secondary: 'একটি সমর্থন অনুরোধ জমা দিন', searching: 'অনুসন্ধান করা হচ্ছে...',
      empty_no_results: 'আপনার যা প্রয়োজন তা খুঁজে পাচ্ছেন না?', btn_submit_request: 'একটি অনুরোধ জমা দিন',
      search_failed: 'অনুসন্ধান ব্যর্থ হয়েছে। আবার চেষ্টা করুন।', article_fallback: 'প্রবন্ধ',
      back_to_search: 'অনুসন্ধানে ফিরে যান', label_name: 'নাম', placeholder_name: 'আপনার পুরো নাম',
      label_contact: 'ফোন বা ইমেইল', placeholder_contact: 'ফোন নম্বর বা ইমেল ঠিকানা',
      label_issue: 'সমস্যার বিবরণ', placeholder_issue: 'আপনার সমস্যা বা প্রশ্ন বিস্তারিতভাবে বর্ণনা করুন…',
      err_required: 'সমস্ত প্রয়োজনীয় ক্ষেত্র পূরণ করুন।', submitting: 'জমা দেওয়া হচ্ছে...',
      btn_submit_request_primary: 'অনুরোধ জমা দিন', err_submit_failed: 'জমা দিতে ব্যর্থ হয়েছে। আবার চেষ্টা করুন।',
      title_ticket_status: 'টিকিটের অবস্থা', success_submitted: 'আপনার অনুরোধ সফলভাবে জমা দেওয়া হয়েছে।',
      label_ticket_ref: 'টিকিট রেফারেন্স', label_status: 'স্ট্যাটাস',
      status_open: 'খোলা', status_inprogress: 'চলছে', status_resolved: 'সমাধান করা হয়েছে', status_closed: 'বন্ধ',
      rate_experience: 'আপনার সমর্থন অভিজ্ঞতা রেট করুন', thanks_feedback: 'আপনার প্রতিক্রিয়ার জন্য ধন্যবাদ!',
      btn_submit_another: 'আরেকটি অনুরোধ জমা দিন',
      touchpoints_label: 'অথবা অন্যভাবে সাহায্য নিন',
      btn_chat_whatsapp: 'হোয়াটসঅ্যাপে চ্যাট করুন', btn_ask_ai: 'এআই সহায়ককে জিজ্ঞাসা করুন',
      ai_chat_title: 'এআই সহায়ক', ai_input_placeholder: 'আপনার প্রশ্ন লিখুন...',
      ai_thinking: 'ভাবছি...', ai_contact_intro: 'ঠিক আছে, এবার আপনার তথ্য দিন:',
      btn_create_ticket: 'টিকিট তৈরি করুন', ai_send: 'পাঠান',
      ai_intake_intro: 'শুরু করার আগে, আপনার তথ্য থাকলে সহায়ক হয়:',
      label_mobile: 'মোবাইল নম্বর', placeholder_mobile: 'আপনার মোবাইল নম্বর',
      label_email: 'ইমেইল', placeholder_email: 'আপনার ইমেইল ঠিকানা',
      label_division: 'বিভাগ', btn_continue: 'চালিয়ে যান', btn_skip: 'এখন এড়িয়ে যান',
    },
  };

  var LANG = (function () {
    try {
      var saved = localStorage.getItem('ml_widget_lang');
      if (saved && STRINGS[saved]) return saved;
    } catch (e) { /* ignore */ }
    return STRINGS[DEFAULT_LANG] ? DEFAULT_LANG : 'en';
  })();

  function t(key) {
    return (STRINGS[LANG] && STRINGS[LANG][key]) || STRINGS.en[key] || key;
  }

  function setLang(lang) {
    if (!STRINGS[lang] || lang === LANG) return;
    LANG = lang;
    try { localStorage.setItem('ml_widget_lang', lang); } catch (e) { /* ignore */ }
  }

  // ── CSS ─────────────────────────────────────────────────────────────────────
  var CSS = [
    '*{box-sizing:border-box;margin:0;padding:0;}',

    // FAB
    '#fab{',
    '  position:fixed;bottom:24px;right:24px;',
    '  width:56px;height:56px;border-radius:50%;',
    '  background:var(--primary);color:#fff;',
    '  border:none;cursor:pointer;',
    '  box-shadow:0 4px 16px rgba(0,0,0,.28);',
    '  font-size:28px;line-height:56px;text-align:center;',
    '  z-index:999999;transition:transform .2s ease,box-shadow .2s ease;',
    '  display:flex;align-items:center;justify-content:center;',
    '  user-select:none;',
    '}',
    '#fab:hover{transform:scale(1.08);box-shadow:0 6px 22px rgba(0,0,0,.34);}',
    '#fab:active{transform:scale(.96);}',

    // Panel
    '#panel{',
    '  position:fixed;bottom:92px;right:24px;',
    '  width:380px;height:520px;',
    '  background:#fff;border-radius:16px;',
    '  box-shadow:0 8px 32px rgba(0,0,0,.18);',
    '  display:flex;flex-direction:column;',
    '  overflow:hidden;',
    '  z-index:999999;',
    '  transform:translateY(24px) scale(.96);opacity:0;',
    '  transition:transform .25s ease,opacity .25s ease;',
    '  pointer-events:none;',
    '  font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;',
    '  font-size:14px;color:#1a1a1a;',
    '}',
    '#panel.open{transform:translateY(0) scale(1);opacity:1;pointer-events:all;}',

    // Mobile full-screen
    '@media(max-width:479px){',
    '  #panel{bottom:0;right:0;left:0;width:100vw;height:100vh;border-radius:0;}',
    '  #fab{bottom:20px;right:20px;}',
    '}',

    // Header
    '.w-header{',
    '  display:flex;align-items:center;justify-content:space-between;',
    '  padding:16px 16px 12px;',
    '  border-bottom:1px solid #f0f0f0;',
    '  background:var(--primary);color:#fff;',
    '  flex-shrink:0;',
    '}',
    '.w-header .logo{font-weight:700;font-size:15px;letter-spacing:.01em;}',
    '.w-header .logo span{font-weight:400;opacity:.85;}',
    '.w-btn-icon{',
    '  background:none;border:none;cursor:pointer;',
    '  color:#fff;font-size:20px;line-height:1;padding:4px;',
    '  border-radius:6px;display:flex;align-items:center;justify-content:center;',
    '  opacity:.85;transition:opacity .15s;',
    '}',
    '.w-btn-icon:hover{opacity:1;background:rgba(255,255,255,.15);}',

    // Language switch
    '.w-lang-switch{display:flex;gap:4px;align-items:center;}',
    '.w-lang-btn{',
    '  background:none;border:none;cursor:pointer;color:rgba(255,255,255,.75);',
    '  font-size:11px;font-weight:600;padding:2px 5px;border-radius:4px;font-family:inherit;',
    '}',
    '.w-lang-btn.active{color:#fff;background:rgba(255,255,255,.18);}',
    '.w-header-actions{display:flex;align-items:center;gap:8px;}',

    // Body
    '.w-body{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px;}',
    '.w-body::-webkit-scrollbar{width:4px;}',
    '.w-body::-webkit-scrollbar-thumb{background:#ddd;border-radius:4px;}',

    // Search
    '.w-search-wrap{position:relative;}',
    '.w-search-wrap svg{position:absolute;left:10px;top:50%;transform:translateY(-50%);opacity:.45;pointer-events:none;}',
    'input.w-input{',
    '  width:100%;padding:10px 12px 10px 36px;',
    '  border:1.5px solid #e0e0e0;border-radius:8px;',
    '  font-size:14px;outline:none;',
    '  transition:border-color .15s;',
    '  font-family:inherit;',
    '}',
    'input.w-input:focus{border-color:var(--primary);}',
    'textarea.w-input{padding:10px 12px;resize:vertical;min-height:88px;}',

    // Results
    '.w-results{list-style:none;display:flex;flex-direction:column;gap:4px;}',
    '.w-result-item{',
    '  padding:10px 12px;border-radius:8px;cursor:pointer;',
    '  border:1px solid #f0f0f0;transition:background .12s;',
    '}',
    '.w-result-item:hover{background:#f5f9ff;border-color:#c8dff5;}',
    '.w-result-title{font-weight:600;font-size:13px;margin-bottom:2px;color:#1a1a1a;}',
    '.w-result-desc{',
    '  font-size:12px;color:#666;',
    '  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;',
    '}',

    // Empty state
    '.w-empty{text-align:center;padding:16px 0 8px;color:#666;font-size:13px;}',

    // Primary button
    '.w-btn-primary{',
    '  width:100%;padding:11px 16px;',
    '  background:var(--primary);color:#fff;',
    '  border:none;border-radius:8px;',
    '  font-size:14px;font-weight:600;cursor:pointer;',
    '  font-family:inherit;letter-spacing:.01em;',
    '  transition:filter .15s;',
    '}',
    '.w-btn-primary:hover{filter:brightness(1.1);}',
    '.w-btn-primary:active{filter:brightness(.95);}',
    '.w-btn-primary:disabled{opacity:.6;cursor:default;filter:none;}',

    // Secondary / outline button
    '.w-btn-secondary{',
    '  width:100%;padding:10px 16px;',
    '  background:#fff;color:var(--primary);',
    '  border:1.5px solid var(--primary);border-radius:8px;',
    '  font-size:14px;font-weight:600;cursor:pointer;',
    '  font-family:inherit;',
    '  transition:background .15s;',
    '}',
    '.w-btn-secondary:hover{background:#f0f7ff;}',

    // Back button
    '.w-back{',
    '  display:inline-flex;align-items:center;gap:6px;',
    '  background:none;border:none;cursor:pointer;',
    '  color:var(--primary);font-size:13px;font-weight:600;',
    '  padding:0;font-family:inherit;',
    '}',
    '.w-back:hover{text-decoration:underline;}',

    // Form field
    '.w-field{display:flex;flex-direction:column;gap:5px;}',
    '.w-label{font-size:12px;font-weight:600;color:#444;letter-spacing:.02em;}',
    '.w-label .req{color:#e53e3e;}',

    // Error
    '.w-error{font-size:12px;color:#e53e3e;padding:8px 12px;background:#fff5f5;border-radius:6px;border:1px solid #fed7d7;}',

    // Divider
    '.w-divider{border:none;border-top:1px solid #f0f0f0;margin:4px 0;}',

    // Status view
    '.w-sl-no{text-align:center;padding:12px;background:#f8f8f8;border-radius:10px;margin-bottom:4px;}',
    '.w-sl-label{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#888;margin-bottom:4px;}',
    '.w-sl-value{font-size:20px;font-weight:700;color:#1a1a1a;letter-spacing:.03em;}',

    '.w-status-badge{',
    '  display:inline-block;padding:4px 12px;border-radius:20px;',
    '  font-size:12px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;',
    '}',
    '.status-open{background:#fff0f0;color:#c0392b;}',
    '.status-inprogress{background:#fff7e6;color:#b7770d;}',
    '.status-resolved{background:#eafaf1;color:#1e8449;}',
    '.status-default{background:#f0f0f0;color:#555;}',

    // Stars
    '.w-stars{display:flex;gap:6px;justify-content:center;margin:8px 0;}',
    '.w-star{',
    '  font-size:28px;cursor:pointer;color:#e0e0e0;',
    '  transition:color .12s,transform .1s;',
    '  user-select:none;',
    '}',
    '.w-star.active,.w-star.hover{color:#f6c90e;}',
    '.w-star:hover{transform:scale(1.15);}',
    '.w-csat-label{text-align:center;font-size:13px;color:#555;font-weight:500;}',
    '.w-csat-thanks{text-align:center;font-size:13px;color:#1e8449;font-weight:600;padding:6px;}',

    // Spinner
    '.w-spinner{',
    '  display:inline-block;width:18px;height:18px;',
    '  border:2.5px solid rgba(255,255,255,.4);',
    '  border-top-color:#fff;border-radius:50%;',
    '  animation:spin .7s linear infinite;vertical-align:middle;margin-right:6px;',
    '}',
    '@keyframes spin{to{transform:rotate(360deg)}}',

    '.w-loading{display:flex;align-items:center;justify-content:center;gap:8px;color:#888;font-size:13px;padding:12px;}',
    '.w-loading-ring{width:20px;height:20px;border:2.5px solid #e0e0e0;border-top-color:var(--primary);border-radius:50%;animation:spin .7s linear infinite;}',

    // Touchpoints row (WhatsApp / AI Assistant quick actions)
    '.w-touchpoints-label{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#999;text-align:center;}',
    '.w-touchpoints{display:flex;gap:8px;}',
    '.w-touchpoint-btn{',
    '  flex:1;display:flex;flex-direction:column;align-items:center;gap:6px;',
    '  padding:12px 8px;border:1.5px solid #e0e0e0;border-radius:10px;',
    '  background:#fff;cursor:pointer;font-family:inherit;font-size:11.5px;font-weight:600;color:#333;',
    '  transition:border-color .15s,background .15s;',
    '}',
    '.w-touchpoint-btn:hover{border-color:var(--primary);background:#f9faff;}',
    '.w-touchpoint-btn svg{width:22px;height:22px;}',

    // AI chat
    '.w-chat-log{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:10px;padding-bottom:4px;}',
    '.w-chat-msg{max-width:82%;padding:9px 12px;border-radius:14px;font-size:13.5px;line-height:1.4;white-space:pre-wrap;}',
    '.w-chat-msg.user{align-self:flex-end;background:var(--primary);color:#fff;border-bottom-right-radius:4px;}',
    '.w-chat-msg.assistant{align-self:flex-start;background:#f0f2f5;color:#1a1a1a;border-bottom-left-radius:4px;}',
    '.w-chat-input-row{display:flex;gap:8px;padding-top:8px;border-top:1px solid #f0f0f0;flex-shrink:0;}',
    '.w-chat-input-row input.w-input{flex:1;}',
    '.w-chat-send-btn{',
    '  width:40px;flex-shrink:0;border:none;border-radius:8px;background:var(--primary);color:#fff;',
    '  cursor:pointer;display:flex;align-items:center;justify-content:center;',
    '}',
    '.w-chat-send-btn:disabled{opacity:.5;cursor:default;}',
    '.w-chat-body{flex:1;display:flex;flex-direction:column;overflow:hidden;padding:16px;gap:0;}',
  ].join('\n');

  // ── Helpers ──────────────────────────────────────────────────────────────────
  function h(tag, attrs, children) {
    var el = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === 'className') el.className = attrs[k];
        else if (k === 'style') el.style.cssText = attrs[k];
        else if (k === 'textContent') el.textContent = attrs[k];
        else if (k === 'innerHTML') el.innerHTML = attrs[k];
        else el.setAttribute(k, attrs[k]);
      });
    }
    if (children) {
      children.forEach(function (c) {
        if (c) el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
      });
    }
    return el;
  }

  function debounce(fn, ms) {
    var t;
    return function () {
      var args = arguments;
      var ctx = this;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, ms);
    };
  }

  function apiPost(path, body) {
    return fetch(BASE_URL + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(function (r) {
      return r.json().then(function (d) {
        if (!r.ok) return Promise.reject(d);
        return d;
      });
    });
  }

  function apiGet(path) {
    return fetch(BASE_URL + path).then(function (r) { return r.json(); });
  }

  function makeLangSwitch(onSwitch) {
    var wrap = h('div', { className: 'w-lang-switch' });
    ['en', 'bn'].forEach(function (code) {
      var btn = h('button', {
        className: 'w-lang-btn' + (LANG === code ? ' active' : ''),
        textContent: code === 'bn' ? 'বাং' : 'EN',
        type: 'button',
        'aria-label': code === 'bn' ? 'বাংলা' : 'English',
      });
      btn.addEventListener('click', function () {
        if (LANG === code) return;
        setLang(code);
        onSwitch();
      });
      wrap.appendChild(btn);
    });
    return wrap;
  }

  // ── Widget Factory ───────────────────────────────────────────────────────────
  function createWidget() {
    // Host container (outside shadow)
    var host = document.createElement('div');
    host.id = 'ml-support-widget';
    host.style.cssText = 'position:fixed;bottom:0;right:0;z-index:999999;pointer-events:none;';
    document.body.appendChild(host);

    var shadow = host.attachShadow({ mode: 'open' });

    // Inject styles
    var style = document.createElement('style');
    style.textContent = CSS;
    shadow.appendChild(style);

    // CSS custom property shim (shadow vars)
    var themeStyle = document.createElement('style');
    themeStyle.textContent = ':host{--primary:' + PRIMARY_COLOR + ';}';
    shadow.appendChild(themeStyle);

    // ── FAB ──────────────────────────────────────────────────────────────────
    var fab = h('button', { id: 'fab', 'aria-label': t('aria_support'), 'aria-expanded': 'false' });
    fab.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
    shadow.appendChild(fab);

    // ── Panel ─────────────────────────────────────────────────────────────────
    var panel = h('div', { id: 'panel', role: 'dialog', 'aria-modal': 'true', 'aria-label': t('aria_widget') });
    shadow.appendChild(panel);

    var isOpen = false;

    function openPanel() {
      isOpen = true;
      panel.classList.add('open');
      fab.setAttribute('aria-expanded', 'true');
      fab.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
    }

    function closePanel() {
      isOpen = false;
      panel.classList.remove('open');
      fab.setAttribute('aria-expanded', 'false');
      fab.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
    }

    fab.addEventListener('click', function () {
      if (isOpen) closePanel(); else openPanel();
    });

    // Allow pointer events on panel itself
    panel.style.pointerEvents = 'all';
    host.style.pointerEvents = 'none';
    fab.style.pointerEvents = 'all';

    // ── State ─────────────────────────────────────────────────────────────────
    var state = {
      view: 'SEARCH', // SEARCH | TICKET_FORM | TICKET_STATUS | AI_CHAT
      ticket: null,   // { sl_no, status, csat_token, rated }
      csatToken: TOKEN || null,
      config: { divisions: [], division_label: 'Division' },
      ai: {
        phase: 'chat',   // intake | chat | contact | done
        history: [],     // [{ role, content }]
        summary: '',
        ticket: null,    // { sl_no, csat_token }
        contact: { name: '', phone: '', email: '', divisionId: '', divisionName: '' },
        intakeDone: false,
      },
    };

    // Best-effort - if this fails the intake form just shows no division options.
    apiGet('/widget/config').then(function (cfg) {
      state.config.divisions = cfg.divisions || [];
      state.config.division_label = cfg.division_label || 'Division';
    }).catch(function () { /* keep defaults */ });

    // ── Render Router ─────────────────────────────────────────────────────────
    function render() {
      // Clear panel
      while (panel.firstChild) panel.removeChild(panel.firstChild);
      if (state.view === 'SEARCH') renderSearch();
      else if (state.view === 'TICKET_FORM') renderTicketForm();
      else if (state.view === 'TICKET_STATUS') renderTicketStatus();
      else if (state.view === 'AI_CHAT') renderAiChat();
    }

    // ── SEARCH VIEW ───────────────────────────────────────────────────────────
    function renderSearch() {
      // Header
      var header = h('div', { className: 'w-header' }, [
        h('div', { className: 'logo' }, [
          'Medtronic ',
          h('span', { textContent: 'LABS Support' }),
        ]),
        h('div', { className: 'w-header-actions' }, [
          makeLangSwitch(render),
          h('button', { className: 'w-btn-icon', 'aria-label': t('aria_close_panel') }),
        ]),
      ]);
      header.querySelector('button').innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
      header.querySelector('button').addEventListener('click', closePanel);
      panel.appendChild(header);

      // Body
      var body = h('div', { className: 'w-body' });
      panel.appendChild(body);

      // Search input
      var searchWrap = h('div', { className: 'w-search-wrap' });
      searchWrap.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>';
      var searchInput = h('input', {
        className: 'w-input',
        type: 'search',
        placeholder: t('search_placeholder'),
        'aria-label': t('aria_search_kb'),
        autocomplete: 'off',
      });
      searchWrap.appendChild(searchInput);
      body.appendChild(searchWrap);

      // Results container
      var resultsWrap = h('div', {});
      body.appendChild(resultsWrap);

      // Divider
      body.appendChild(h('hr', { className: 'w-divider' }));

      // Touchpoints: WhatsApp + AI Assistant quick actions
      body.appendChild(h('div', { className: 'w-touchpoints-label', textContent: t('touchpoints_label') }));
      var touchpoints = h('div', { className: 'w-touchpoints' });

      if (WHATSAPP_NUM) {
        var waBtn = h('button', { className: 'w-touchpoint-btn', type: 'button' });
        waBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="#25D366"><path d="M12.04 2c-5.46 0-9.9 4.44-9.9 9.9 0 1.75.46 3.45 1.32 4.95L2 22l5.25-1.38a9.9 9.9 0 0 0 4.79 1.22h.01c5.46 0 9.9-4.44 9.9-9.9S17.5 2 12.04 2m0 18.1h-.01a8.2 8.2 0 0 1-4.18-1.14l-.3-.18-3.12.82.83-3.04-.2-.31a8.2 8.2 0 0 1-1.26-4.35c0-4.54 3.7-8.24 8.25-8.24 2.2 0 4.27.86 5.83 2.42a8.19 8.19 0 0 1 2.41 5.83c0 4.55-3.7 8.19-8.25 8.19"/></svg>';
        var waLabel = document.createElement('span');
        waLabel.textContent = t('btn_chat_whatsapp');
        waBtn.appendChild(waLabel);
        waBtn.addEventListener('click', function () {
          window.open('https://wa.me/' + WHATSAPP_NUM.replace(/[^0-9]/g, ''), '_blank', 'noopener');
        });
        touchpoints.appendChild(waBtn);
      }

      var aiBtn = h('button', { className: 'w-touchpoint-btn', type: 'button' });
      aiBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v3M12 18v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M3 12h3M18 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/><circle cx="12" cy="12" r="3"/></svg>';
      var aiLabel = document.createElement('span');
      aiLabel.textContent = t('btn_ask_ai');
      aiBtn.appendChild(aiLabel);
      aiBtn.addEventListener('click', function () {
        state.view = 'AI_CHAT';
        if (!state.ai.intakeDone) {
          state.ai.phase = 'intake';
        } else if (state.ai.phase === 'done' || state.ai.phase === 'contact') {
          // Starting a fresh conversation after a previous one finished/escalated.
          state.ai.phase = 'chat';
          state.ai.history = [];
          state.ai.summary = '';
          state.ai.ticket = null;
        }
        render();
      });
      touchpoints.appendChild(aiBtn);

      body.appendChild(touchpoints);
      body.appendChild(h('hr', { className: 'w-divider' }));

      // Always-visible submit button
      var submitBtn = h('button', { className: 'w-btn-secondary', textContent: t('btn_submit_request_secondary') });
      submitBtn.addEventListener('click', function () { state.view = 'TICKET_FORM'; render(); });
      body.appendChild(submitBtn);

      // Debounced search
      function doSearch(q) {
        while (resultsWrap.firstChild) resultsWrap.removeChild(resultsWrap.firstChild);
        q = (q || '').trim();
        if (!q) return;

        var loading = h('div', { className: 'w-loading' }, [
          h('div', { className: 'w-loading-ring' }),
          document.createTextNode(t('searching')),
        ]);
        resultsWrap.appendChild(loading);

        apiGet('/widget/search?q=' + encodeURIComponent(q))
          .then(function (data) {
            while (resultsWrap.firstChild) resultsWrap.removeChild(resultsWrap.firstChild);
            var items = Array.isArray(data) ? data : (data.results || []);
            if (!items.length) {
              var empty = h('div', { className: 'w-empty' }, [
                h('p', { textContent: t('empty_no_results') }),
                h('br'),
              ]);
              var suggestBtn = h('button', { className: 'w-btn-primary', textContent: t('btn_submit_request'), style: 'margin-top:8px;' });
              suggestBtn.addEventListener('click', function () { state.view = 'TICKET_FORM'; render(); });
              empty.appendChild(suggestBtn);
              resultsWrap.appendChild(empty);
              return;
            }
            var list = h('ul', { className: 'w-results' });
            items.forEach(function (item) {
              var li = h('li', { className: 'w-result-item' }, [
                h('div', { className: 'w-result-title', textContent: item.title || t('article_fallback') }),
                h('div', { className: 'w-result-desc', textContent: item.meta_description || item.description || '' }),
              ]);
              li.addEventListener('click', function () {
                var url = item.url || item.link || (BASE_URL + '/kb/' + (item.id || item.slug));
                window.open(url, '_blank', 'noopener');
              });
              list.appendChild(li);
            });
            resultsWrap.appendChild(list);
          })
          .catch(function () {
            while (resultsWrap.firstChild) resultsWrap.removeChild(resultsWrap.firstChild);
            resultsWrap.appendChild(h('div', { className: 'w-error', textContent: t('search_failed') }));
          });
      }

      var debouncedSearch = debounce(doSearch, 400);
      searchInput.addEventListener('input', function () { debouncedSearch(searchInput.value); });
      searchInput.focus();
    }

    // ── TICKET_FORM VIEW ──────────────────────────────────────────────────────
    function renderTicketForm() {
      // Header
      var header = h('div', { className: 'w-header' }, [
        h('div', { className: 'logo', textContent: t('btn_submit_request') }),
        h('div', { className: 'w-header-actions' }, [
          makeLangSwitch(render),
          h('button', { className: 'w-btn-icon', 'aria-label': t('aria_close') }),
        ]),
      ]);
      header.querySelector('button').innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
      header.querySelector('button').addEventListener('click', closePanel);
      panel.appendChild(header);

      var body = h('div', { className: 'w-body' });
      panel.appendChild(body);

      // Back
      var backBtn = h('button', { className: 'w-back' });
      backBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg> ' + t('back_to_search');
      backBtn.addEventListener('click', function () { state.view = 'SEARCH'; render(); });
      body.appendChild(backBtn);

      // Name
      var nameField = h('div', { className: 'w-field' }, [
        h('label', { className: 'w-label', innerHTML: t('label_name') + ' <span class="req">*</span>' }),
      ]);
      var nameInput = h('input', {
        className: 'w-input',
        type: 'text',
        placeholder: t('placeholder_name'),
        value: USER_NAME,
        autocomplete: 'name',
      });
      nameField.appendChild(nameInput);
      body.appendChild(nameField);

      // Contact
      var contactField = h('div', { className: 'w-field' }, [
        h('label', { className: 'w-label', innerHTML: t('label_contact') + ' <span class="req">*</span>' }),
      ]);
      var contactInput = h('input', {
        className: 'w-input',
        type: 'text',
        placeholder: t('placeholder_contact'),
        value: USER_CONTACT,
        autocomplete: 'email',
      });
      contactField.appendChild(contactInput);
      body.appendChild(contactField);

      // Issue
      var issueField = h('div', { className: 'w-field' }, [
        h('label', { className: 'w-label', innerHTML: t('label_issue') + ' <span class="req">*</span>' }),
      ]);
      var issueInput = h('textarea', {
        className: 'w-input',
        rows: '4',
        placeholder: t('placeholder_issue'),
      });
      issueField.appendChild(issueInput);
      body.appendChild(issueField);

      // Error placeholder
      var errDiv = h('div', { style: 'display:none;' });
      body.appendChild(errDiv);

      // Submit
      var submitBtn = h('button', { className: 'w-btn-primary', textContent: t('btn_submit_request_primary') });
      body.appendChild(submitBtn);

      submitBtn.addEventListener('click', function () {
        var name    = nameInput.value.trim();
        var contact = contactInput.value.trim();
        var issue   = issueInput.value.trim();

        // Validation
        if (!name || !contact || !issue) {
          errDiv.className = 'w-error';
          errDiv.textContent = t('err_required');
          errDiv.style.display = '';
          return;
        }
        errDiv.style.display = 'none';

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="w-spinner"></span> ' + t('submitting');

        apiPost('/widget/ticket', {
          name: name,
          contact: contact,
          issue: issue,
          app: APP,
          page: window.location.href,
        })
          .then(function (data) {
            state.ticket = {
              sl_no: data.sl_no || data.ticket_id || data.id || 'N/A',
              status: data.status || 'Open',
              csat_token: data.csat_token || data.token || null,
              rated: false,
            };
            if (state.ticket.csat_token) state.csatToken = state.ticket.csat_token;
            state.view = 'TICKET_STATUS';
            render();
          })
          .catch(function (err) {
            submitBtn.disabled = false;
            submitBtn.textContent = t('btn_submit_request_primary');
            var msg = (err && (err.detail || err.message || err.error)) || t('err_submit_failed');
            errDiv.className = 'w-error';
            errDiv.textContent = msg;
            errDiv.style.display = '';
          });
      });
    }

    // ── TICKET_STATUS VIEW ────────────────────────────────────────────────────
    function renderTicketStatus() {
      var ticket = state.ticket || { sl_no: 'N/A', status: 'Open' };

      // Header
      var header = h('div', { className: 'w-header' }, [
        h('div', { className: 'logo', textContent: t('title_ticket_status') }),
        h('div', { className: 'w-header-actions' }, [
          makeLangSwitch(render),
          h('button', { className: 'w-btn-icon', 'aria-label': t('aria_close') }),
        ]),
      ]);
      header.querySelector('button').innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
      header.querySelector('button').addEventListener('click', closePanel);
      panel.appendChild(header);

      var body = h('div', { className: 'w-body' });
      panel.appendChild(body);

      // Success notice
      body.appendChild(h('div', {
        style: 'background:#eafaf1;border:1px solid #b2dfdb;border-radius:8px;padding:10px 14px;font-size:13px;color:#1e8449;font-weight:500;',
        textContent: t('success_submitted'),
      }));

      // Sl No
      var slBox = h('div', { className: 'w-sl-no' }, [
        h('div', { className: 'w-sl-label', textContent: t('label_ticket_ref') }),
        h('div', { className: 'w-sl-value', textContent: ticket.sl_no }),
      ]);
      body.appendChild(slBox);

      // Status badge
      var statusClass = 'status-default';
      var st = (ticket.status || '').toLowerCase().replace(/\s+/g, '');
      var statusKey = 'status_open';
      if (st === 'open') { statusClass = 'status-open'; statusKey = 'status_open'; }
      else if (st === 'inprogress' || st === 'in_progress') { statusClass = 'status-inprogress'; statusKey = 'status_inprogress'; }
      else if (st === 'resolved') { statusClass = 'status-resolved'; statusKey = 'status_resolved'; }
      else if (st === 'closed') { statusClass = 'status-resolved'; statusKey = 'status_closed'; }

      var statusRow = h('div', { style: 'display:flex;align-items:center;justify-content:space-between;padding:4px 0;' }, [
        h('span', { style: 'font-size:13px;color:#555;font-weight:500;', textContent: t('label_status') }),
        h('span', { className: 'w-status-badge ' + statusClass, textContent: ticket.status ? t(statusKey) : t('status_open') }),
      ]);
      body.appendChild(statusRow);

      body.appendChild(h('hr', { className: 'w-divider' }));

      // CSAT (only if resolved and not yet rated)
      var isResolved = (st === 'resolved' || st === 'closed');
      if (isResolved && !ticket.rated) {
        var csatSection = h('div', { style: 'display:flex;flex-direction:column;gap:6px;' });
        csatSection.appendChild(h('div', { className: 'w-csat-label', textContent: t('rate_experience') }));

        var starsRow = h('div', { className: 'w-stars' });
        var currentHover = 0;
        var rated = false;

        for (var i = 1; i <= 5; i++) {
          (function (val) {
            var star = h('span', { className: 'w-star', textContent: '★', 'data-val': val });
            star.addEventListener('mouseenter', function () {
              if (rated) return;
              currentHover = val;
              updateStars(starsRow, 0, currentHover);
            });
            star.addEventListener('mouseleave', function () {
              if (rated) return;
              currentHover = 0;
              updateStars(starsRow, 0, 0);
            });
            star.addEventListener('click', function () {
              if (rated) return;
              rated = true;
              updateStars(starsRow, val, 0);
              submitCsat(val, starsRow, csatSection);
            });
            starsRow.appendChild(star);
          })(i);
        }
        csatSection.appendChild(starsRow);
        body.appendChild(csatSection);
        body.appendChild(h('hr', { className: 'w-divider' }));
      }

      // Submit another
      var newBtn = h('button', { className: 'w-btn-secondary', textContent: t('btn_submit_another') });
      newBtn.addEventListener('click', function () {
        state.ticket = null;
        state.view = 'SEARCH';
        render();
      });
      body.appendChild(newBtn);

      // Back to search
      var backBtn = h('button', { className: 'w-back', style: 'justify-content:center;width:100%;margin-top:4px;' });
      backBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg> ' + t('back_to_search');
      backBtn.addEventListener('click', function () { state.view = 'SEARCH'; render(); });
      body.appendChild(backBtn);
    }

    // ── AI_CHAT VIEW ──────────────────────────────────────────────────────────
    function renderAiChat() {
      var isChatPhase = state.ai.phase === 'chat';

      // Header
      var header = h('div', { className: 'w-header' }, [
        h('div', { className: 'logo', textContent: t('ai_chat_title') }),
        h('div', { className: 'w-header-actions' }, [
          makeLangSwitch(render),
          h('button', { className: 'w-btn-icon', 'aria-label': t('aria_close') }),
        ]),
      ]);
      header.querySelector('button').innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
      header.querySelector('button').addEventListener('click', closePanel);
      panel.appendChild(header);

      var body = h('div', { className: isChatPhase ? 'w-chat-body' : 'w-body' });
      panel.appendChild(body);

      var backBtn = h('button', { className: 'w-back', style: 'margin-bottom:8px;flex-shrink:0;' });
      backBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg> ' + t('back_to_search');
      backBtn.addEventListener('click', function () { state.view = 'SEARCH'; render(); });
      body.appendChild(backBtn);

      var log = h('div', { className: 'w-chat-log' });
      body.appendChild(log);

      function appendMsg(role, text) {
        log.appendChild(h('div', { className: 'w-chat-msg ' + role, textContent: text }));
        log.scrollTop = log.scrollHeight;
      }

      state.ai.history.forEach(function (m) { appendMsg(m.role, m.content); });

      if (isChatPhase) {
        var inputRow = h('div', { className: 'w-chat-input-row' });
        var input = h('input', { className: 'w-input', type: 'text', placeholder: t('ai_input_placeholder'), autocomplete: 'off' });
        var sendBtn = h('button', { className: 'w-chat-send-btn', type: 'button', 'aria-label': t('ai_send') });
        sendBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>';
        inputRow.appendChild(input);
        inputRow.appendChild(sendBtn);
        body.appendChild(inputRow);

        function send() {
          var text = input.value.trim();
          if (!text) return;
          var priorHistory = state.ai.history.slice(); // turns before this message
          input.value = '';
          input.disabled = true;
          sendBtn.disabled = true;
          appendMsg('user', text);
          state.ai.history.push({ role: 'user', content: text });

          var thinking = h('div', { className: 'w-chat-msg assistant', textContent: t('ai_thinking') });
          log.appendChild(thinking);
          log.scrollTop = log.scrollHeight;

          apiPost('/widget/ai-chat', { message: text, history: priorHistory })
            .then(function (data) {
              log.removeChild(thinking);
              appendMsg('assistant', data.reply);
              state.ai.history.push({ role: 'assistant', content: data.reply });
              if (data.escalate) {
                state.ai.summary = data.summary || text;
                state.ai.phase = 'contact';
                render();
                return;
              }
              input.disabled = false;
              sendBtn.disabled = false;
              input.focus();
            })
            .catch(function () {
              log.removeChild(thinking);
              appendMsg('assistant', t('search_failed'));
              input.disabled = false;
              sendBtn.disabled = false;
            });
        }

        sendBtn.addEventListener('click', send);
        input.addEventListener('keydown', function (e) { if (e.key === 'Enter') send(); });
        input.focus();
      } else if (state.ai.phase === 'intake') {
        renderAiIntakeForm(body);
      } else if (state.ai.phase === 'contact') {
        renderAiContactForm(body);
      } else if (state.ai.phase === 'done') {
        renderAiCsat(body);
      }
    }

    // Soft, skippable ask for name/mobile/email/region shown once before the
    // first AI reply, so any ticket this conversation ends up filing is
    // already attributable - see renderAiContactForm below for the fallback
    // ask if the user skips this and later escalates to a ticket anyway.
    function renderAiIntakeForm(body) {
      body.appendChild(h('hr', { className: 'w-divider' }));
      body.appendChild(h('div', { className: 'w-csat-label', textContent: t('ai_intake_intro') }));

      var c = state.ai.contact;

      var nameField = h('div', { className: 'w-field' }, [
        h('label', { className: 'w-label', textContent: t('label_name') }),
      ]);
      var nameInput = h('input', { className: 'w-input', type: 'text', placeholder: t('placeholder_name'), value: c.name || USER_NAME, autocomplete: 'name' });
      nameField.appendChild(nameInput);
      body.appendChild(nameField);

      var phoneField = h('div', { className: 'w-field' }, [
        h('label', { className: 'w-label', textContent: t('label_mobile') }),
      ]);
      var phoneInput = h('input', { className: 'w-input', type: 'text', placeholder: t('placeholder_mobile'), value: c.phone || USER_CONTACT, autocomplete: 'tel' });
      phoneField.appendChild(phoneInput);
      body.appendChild(phoneField);

      var emailField = h('div', { className: 'w-field' }, [
        h('label', { className: 'w-label', textContent: t('label_email') }),
      ]);
      var emailInput = h('input', { className: 'w-input', type: 'text', placeholder: t('placeholder_email'), value: c.email || '', autocomplete: 'email' });
      emailField.appendChild(emailInput);
      body.appendChild(emailField);

      var divisionField = h('div', { className: 'w-field' }, [
        h('label', { className: 'w-label', textContent: state.config.division_label || t('label_division') }),
      ]);
      var divisionSelect = h('select', { className: 'w-input' });
      divisionSelect.appendChild(h('option', { value: '', textContent: '—' }));
      (state.config.divisions || []).forEach(function (r) {
        var opt = h('option', { value: String(r.id), textContent: r.name });
        if (c.divisionId && String(c.divisionId) === String(r.id)) opt.selected = true;
        divisionSelect.appendChild(opt);
      });
      divisionField.appendChild(divisionSelect);
      body.appendChild(divisionField);

      function saveContact() {
        c.name = nameInput.value.trim();
        c.phone = phoneInput.value.trim();
        c.email = emailInput.value.trim();
        c.divisionId = divisionSelect.value || '';
        var opt = divisionSelect.options[divisionSelect.selectedIndex];
        c.divisionName = (opt && opt.value) ? opt.textContent : '';
        state.ai.intakeDone = true;
        state.ai.phase = 'chat';
        render();
      }

      var continueBtn = h('button', { className: 'w-btn-primary', textContent: t('btn_continue'), style: 'margin-top:4px;' });
      continueBtn.addEventListener('click', saveContact);
      body.appendChild(continueBtn);

      var skipBtn = h('button', { className: 'w-btn-secondary', textContent: t('btn_skip'), style: 'margin-top:8px;' });
      skipBtn.addEventListener('click', function () {
        state.ai.intakeDone = true;
        state.ai.phase = 'chat';
        render();
      });
      body.appendChild(skipBtn);
    }

    function renderAiContactForm(body) {
      body.appendChild(h('hr', { className: 'w-divider' }));
      body.appendChild(h('div', { className: 'w-csat-label', textContent: t('ai_contact_intro') }));

      var known = state.ai.contact || {};

      var nameField = h('div', { className: 'w-field' }, [
        h('label', { className: 'w-label', innerHTML: t('label_name') + ' <span class="req">*</span>' }),
      ]);
      var nameInput = h('input', { className: 'w-input', type: 'text', placeholder: t('placeholder_name'), value: known.name || USER_NAME });
      nameField.appendChild(nameInput);
      body.appendChild(nameField);

      var contactField = h('div', { className: 'w-field' }, [
        h('label', { className: 'w-label', innerHTML: t('label_contact') + ' <span class="req">*</span>' }),
      ]);
      var contactInput = h('input', { className: 'w-input', type: 'text', placeholder: t('placeholder_contact'), value: known.phone || known.email || USER_CONTACT });
      contactField.appendChild(contactInput);
      body.appendChild(contactField);

      var errDiv = h('div', { style: 'display:none;' });
      body.appendChild(errDiv);

      var submitBtn = h('button', { className: 'w-btn-primary', textContent: t('btn_create_ticket') });
      submitBtn.addEventListener('click', function () {
        var name = nameInput.value.trim();
        var contact = contactInput.value.trim();
        if (!name || !contact) {
          errDiv.className = 'w-error';
          errDiv.textContent = t('err_required');
          errDiv.style.display = '';
          return;
        }
        errDiv.style.display = 'none';
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="w-spinner"></span> ' + t('submitting');

        var transcript = state.ai.history.map(function (m) {
          return (m.role === 'user' ? 'User: ' : 'Assistant: ') + m.content;
        }).join('\n');
        var issue = state.ai.summary + '\n\n--- AI chat transcript ---\n' + transcript;

        apiPost('/widget/ticket', {
          name: name,
          contact: contact,
          email: known.email || undefined,
          admin1_id: known.divisionId || undefined,
          issue: issue,
          app: APP,
          page: window.location.href,
        })
          .then(function (data) {
            state.ai.ticket = { sl_no: data.sl_no || data.ticket_id, csat_token: data.csat_token };
            state.ai.phase = 'done';
            render();
          })
          .catch(function () {
            submitBtn.disabled = false;
            submitBtn.textContent = t('btn_create_ticket');
            errDiv.className = 'w-error';
            errDiv.textContent = t('err_submit_failed');
            errDiv.style.display = '';
          });
      });
      body.appendChild(submitBtn);
    }

    function renderAiCsat(body) {
      body.appendChild(h('hr', { className: 'w-divider' }));

      var slBox = h('div', { className: 'w-sl-no' }, [
        h('div', { className: 'w-sl-label', textContent: t('label_ticket_ref') }),
        h('div', { className: 'w-sl-value', textContent: state.ai.ticket.sl_no }),
      ]);
      body.appendChild(slBox);

      var csatSection = h('div', { style: 'display:flex;flex-direction:column;gap:6px;' });
      csatSection.appendChild(h('div', { className: 'w-csat-label', textContent: t('rate_experience') }));
      var starsRow = h('div', { className: 'w-stars' });
      var rated = false;
      for (var i = 1; i <= 5; i++) {
        (function (val) {
          var star = h('span', { className: 'w-star', textContent: '★', 'data-val': val });
          star.addEventListener('mouseenter', function () { if (!rated) updateStars(starsRow, 0, val); });
          star.addEventListener('mouseleave', function () { if (!rated) updateStars(starsRow, 0, 0); });
          star.addEventListener('click', function () {
            if (rated) return;
            rated = true;
            updateStars(starsRow, val, 0);
            if (state.ai.ticket.csat_token) {
              apiPost('/widget/csat/' + encodeURIComponent(state.ai.ticket.csat_token), { rating: val })
                .then(function () { showCsatThanks(csatSection); })
                .catch(function () { showCsatThanks(csatSection); });
            } else {
              showCsatThanks(csatSection);
            }
          });
          starsRow.appendChild(star);
        })(i);
      }
      csatSection.appendChild(starsRow);
      body.appendChild(csatSection);
      body.appendChild(h('hr', { className: 'w-divider' }));

      var newBtn = h('button', { className: 'w-btn-secondary', textContent: t('btn_submit_another') });
      newBtn.addEventListener('click', function () {
        // Keep the already-collected contact info - no need to ask again.
        state.ai = {
          phase: 'chat', history: [], summary: '', ticket: null,
          contact: state.ai.contact, intakeDone: state.ai.intakeDone,
        };
        state.view = 'SEARCH';
        render();
      });
      body.appendChild(newBtn);
    }

    function updateStars(starsRow, active, hov) {
      var stars = starsRow.querySelectorAll('.w-star');
      var threshold = hov || active;
      stars.forEach(function (s, idx) {
        var v = idx + 1;
        if (v <= threshold) {
          s.classList.add('active');
          s.classList.remove('hover');
        } else {
          s.classList.remove('active');
          s.classList.remove('hover');
        }
      });
    }

    function submitCsat(rating, starsRow, csatSection) {
      if (!state.csatToken) {
        // No token — just show thanks
        showCsatThanks(csatSection);
        if (state.ticket) state.ticket.rated = true;
        return;
      }
      apiPost('/widget/csat/' + encodeURIComponent(state.csatToken), { rating: rating })
        .then(function () {
          if (state.ticket) state.ticket.rated = true;
          showCsatThanks(csatSection);
        })
        .catch(function () {
          if (state.ticket) state.ticket.rated = true;
          showCsatThanks(csatSection);
        });
    }

    function showCsatThanks(csatSection) {
      while (csatSection.firstChild) csatSection.removeChild(csatSection.firstChild);
      csatSection.appendChild(h('div', { className: 'w-csat-thanks', textContent: t('thanks_feedback') }));
    }

    // Initial render
    render();
  }

  // ── Auto-init ─────────────────────────────────────────────────────────────
  function init() {
    if (document.getElementById('ml-support-widget')) return;
    createWidget();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
