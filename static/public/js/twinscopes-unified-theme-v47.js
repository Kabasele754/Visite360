(() => {
  const STORAGE_KEY = 'twinscopes-market-theme';
  const resolve = () => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) || localStorage.getItem('twinscopes-dashboard-theme') || localStorage.getItem('studio-builder-theme');
      if (saved === 'light' || saved === 'dark') return saved;
      return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    } catch (_) { return 'dark'; }
  };
  const apply = (theme, persist = true) => {
    const value = theme === 'light' ? 'light' : 'dark';
    document.documentElement.dataset.marketTheme = value;
    document.documentElement.dataset.dashboardTheme = value;
    document.documentElement.style.colorScheme = value;
    document.body?.classList.toggle('builder-dark', value === 'dark');
    document.body?.classList.toggle('builder-light', value === 'light');
    if (persist) {
      try {
        localStorage.setItem(STORAGE_KEY, value);
        localStorage.setItem('twinscopes-dashboard-theme', value);
        localStorage.setItem('studio-builder-theme', value);
      } catch (_) {}
    }
    document.querySelectorAll('[data-global-theme-toggle]').forEach(button => {
      button.textContent = value === 'dark' ? '☀' : '◐';
      button.setAttribute('aria-pressed', value === 'dark' ? 'true' : 'false');
    });
    window.dispatchEvent(new CustomEvent('twinscopes:theme', { detail: { theme: value } }));
  };
  const bind = () => {
    apply(resolve(), false);
    document.querySelectorAll('[data-global-theme-toggle]').forEach(button => {
      button.addEventListener('click', () => apply(document.documentElement.dataset.marketTheme === 'dark' ? 'light' : 'dark'));
    });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind, { once: true });
  else bind();
  window.addEventListener('storage', event => {
    if (['twinscopes-market-theme','twinscopes-dashboard-theme','studio-builder-theme'].includes(event.key)) apply(resolve(), false);
  });
  window.TwinscopesTheme = { apply, resolve };
})();
