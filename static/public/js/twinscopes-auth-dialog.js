(() => {
  const root = document.getElementById('tsAuthDialog');
  if (!root) return;
  const config = window.TWINSCOPE_AUTH || {};
  const csrf = () => (document.cookie.match(/(?:^|; )csrftoken=([^;]*)/) || [])[1] || '';
  let lastFocus = null;

  function view(name) {
    root.querySelectorAll('[data-auth-view]').forEach(el => el.classList.toggle('is-active', el.dataset.authView === name));
    const first = root.querySelector(`[data-auth-view="${name}"] input`);
    setTimeout(() => first?.focus(), 50);
  }
  function open(name='welcome') {
    lastFocus = document.activeElement;
    root.inert = false;
    root.setAttribute('aria-hidden', 'false');
    root.classList.add('is-open');
    document.documentElement.style.overflow = 'hidden';
    view(name);
  }
  function close() {
    root.classList.remove('is-open');
    root.setAttribute('aria-hidden', 'true');
    root.inert = true;
    document.documentElement.style.overflow = '';
    lastFocus?.focus?.();
  }
  document.addEventListener('click', e => {
    const trigger = e.target.closest('[data-auth-open]');
    if (trigger) { e.preventDefault(); open(trigger.dataset.authOpen || 'welcome'); }
    if (e.target.closest('[data-auth-close]')) close();
    const switcher = e.target.closest('[data-auth-open-view]');
    if (switcher) view(switcher.dataset.authOpenView);
    const toggle = e.target.closest('[data-password-toggle]');
    if (toggle) {
      const input = toggle.parentElement.querySelector('input');
      input.type = input.type === 'password' ? 'text' : 'password';
      toggle.textContent = input.type === 'password' ? 'Show' : 'Hide';
    }
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && root.classList.contains('is-open')) close(); });

  function clearErrors(form) {
    form.querySelectorAll('[data-field-error]').forEach(el => el.textContent = '');
    const notice = form.querySelector('[data-auth-notice]');
    notice.hidden = true; notice.textContent = '';
  }
  function showErrors(form, errors) {
    const notice = form.querySelector('[data-auth-notice]');
    Object.entries(errors || {}).forEach(([field, messages]) => {
      const target = form.querySelector(`[data-field-error="${field}"]`);
      if (target) target.textContent = messages.join(' ');
      else { notice.hidden = false; notice.textContent = messages.join(' '); }
    });
    if (!Object.keys(errors || {}).length) { notice.hidden = false; notice.textContent = 'Unable to continue. Please try again.'; }
  }
  root.querySelectorAll('[data-auth-form]').forEach(form => form.addEventListener('submit', async e => {
    e.preventDefault(); clearErrors(form);
    const kind = form.dataset.authForm;
    const data = Object.fromEntries(new FormData(form).entries());
    data.remember = form.querySelector('[name=remember]')?.checked || false;
    data.next = config.next || '/';
    const button = form.querySelector('[type=submit]');
    button.disabled = true; const previous = button.textContent; button.textContent = kind === 'register' ? 'Creating account…' : 'Signing in…';
    try {
      const response = await fetch(kind === 'register' ? config.registerUrl : config.loginUrl, {
        method: 'POST', credentials: 'same-origin', headers: {'Content-Type':'application/json','X-CSRFToken':csrf(),'X-Requested-With':'XMLHttpRequest'}, body: JSON.stringify(data)
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) { showErrors(form, payload.errors); return; }
      window.location.assign(payload.redirect_url || '/');
    } catch (_) { showErrors(form, {__all__: ['Network error. Please try again.']}); }
    finally { button.disabled = false; button.textContent = previous; }
  }));

  const params = new URLSearchParams(location.search);
  if (params.get('auth') === 'signin') open('welcome');
  if (params.get('auth_error')) open('welcome');
  window.TwinscopesAuth = {open, close};
})();
