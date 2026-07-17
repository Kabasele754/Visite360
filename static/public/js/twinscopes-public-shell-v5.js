(() => {
  "use strict";

  window.TWINSCOPE_PUBLIC_SHELL_VERSION = "mobile-more-v5-20260717";

  const THEME_KEY = "twinscopes-market-theme";
  const legacyThemeKeys = ["twinscopesTheme", "virtualToursTheme"];
  const root = document.documentElement;
  let initialized = false;
  let chromeHidden = false;

  const readTheme = () =>
    localStorage.getItem(THEME_KEY) ||
    legacyThemeKeys.map((key) => localStorage.getItem(key)).find(Boolean) ||
    (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");

  const applyTheme = (theme) => {
    const resolved = theme === "dark" ? "dark" : "light";
    const dark = resolved === "dark";
    root.dataset.marketTheme = resolved;
    root.style.colorScheme = resolved;
    document.body?.classList.toggle("theme-dark", dark);
    document.querySelectorAll("[data-ts-theme-toggle]").forEach((button) => {
      button.setAttribute("aria-pressed", String(dark));
    });
    localStorage.setItem(THEME_KEY, resolved);
    localStorage.setItem("twinscopesTheme", resolved);
  };

  const getChrome = () => ({
    desktop: document.getElementById("desktopHeader"),
    mobileTop: document.getElementById("mobileTopActions"),
    mobileBottom: document.getElementById("mobileBottomNav"),
  });

  const setChromeHidden = (hidden, { force = false } = {}) => {
    if (!force && chromeHidden === hidden) return;
    chromeHidden = hidden;
    const { desktop, mobileTop, mobileBottom } = getChrome();
    [desktop, mobileTop, mobileBottom].forEach((element) => {
      if (!element) return;
      element.classList.toggle("is-scroll-hidden", hidden);
      element.classList.toggle("is-scroll-visible", !hidden);
      element.setAttribute("data-scroll-state", hidden ? "hidden" : "visible");
    });
    document.body?.classList.toggle("ts-public-chrome-hidden", hidden);
  };

  const getMoreElements = () => ({
    sheet: document.getElementById("tsMobileMoreSheet"),
    trigger: document.querySelector("[data-ts-more-toggle]"),
  });

  const closeMore = ({ restoreFocus = false } = {}) => {
    const { sheet, trigger } = getMoreElements();
    if (!sheet) return;

    const focused = document.activeElement;
    if (focused && sheet.contains(focused) && typeof focused.blur === "function") {
      focused.blur();
    }

    sheet.classList.remove("is-open");
    sheet.setAttribute("aria-hidden", "true");
    sheet.setAttribute("inert", "");
    trigger?.setAttribute("aria-expanded", "false");
    document.body?.classList.remove("ts-more-open");

    if (restoreFocus && trigger && document.contains(trigger)) {
      requestAnimationFrame(() => {
        try {
          trigger.focus({ preventScroll: true });
        } catch (_) {}
      });
    }
  };

  const openMore = () => {
    const { sheet, trigger } = getMoreElements();
    if (!sheet || !trigger) return;

    setChromeHidden(false, { force: true });
    sheet.removeAttribute("inert");
    sheet.setAttribute("aria-hidden", "false");
    sheet.classList.add("is-open");
    trigger.setAttribute("aria-expanded", "true");
    document.body?.classList.add("ts-more-open");

    requestAnimationFrame(() => {
      sheet.querySelector(".ts-more-card [data-ts-more-close]")?.focus({
        preventScroll: true,
      });
    });
  };

  const toggleMore = () => {
    const { sheet } = getMoreElements();
    if (!sheet) return;
    sheet.classList.contains("is-open")
      ? closeMore({ restoreFocus: true })
      : openMore();
  };

  const initSmartScroll = () => {
    let lastY = Math.max(0, window.scrollY || 0);
    let accumulated = 0;
    let ticking = false;
    let ignoreUntil = 0;

    const shouldKeepVisible = () => {
      const { sheet } = getMoreElements();
      const active = document.activeElement;
      return Boolean(
        sheet?.classList.contains("is-open") ||
        document.body?.classList.contains("modal-open") ||
        document.body?.classList.contains("search-open") ||
        active?.matches?.("input,textarea,select,[contenteditable='true']")
      );
    };

    const update = () => {
      ticking = false;
      const y = Math.max(0, window.scrollY || document.documentElement.scrollTop || 0);
      const delta = y - lastY;
      document.getElementById("desktopHeader")?.classList.toggle("is-scrolled", y > 18);

      if (Date.now() < ignoreUntil || shouldKeepVisible() || y <= 88) {
        accumulated = 0;
        setChromeHidden(false);
        lastY = y;
        return;
      }

      if (Math.sign(delta) !== Math.sign(accumulated)) accumulated = 0;
      accumulated += delta;

      if (accumulated >= 18) {
        setChromeHidden(true);
        accumulated = 0;
      } else if (accumulated <= -8) {
        setChromeHidden(false);
        accumulated = 0;
      }
      lastY = y;
    };

    addEventListener(
      "scroll",
      () => {
        if (!ticking) {
          ticking = true;
          requestAnimationFrame(update);
        }
      },
      { passive: true }
    );

    addEventListener(
      "resize",
      () => {
        ignoreUntil = Date.now() + 220;
        setChromeHidden(false, { force: true });
        lastY = Math.max(0, scrollY || 0);
      },
      { passive: true }
    );

    addEventListener("pageshow", () => setChromeHidden(false, { force: true }));
    setChromeHidden(false, { force: true });
  };

  const init = () => {
    if (initialized) return;
    initialized = true;

    applyTheme(readTheme());

    document.addEventListener("click", (event) => {
      const themeButton = event.target.closest("[data-ts-theme-toggle]");
      if (themeButton) {
        applyTheme(root.dataset.marketTheme === "dark" ? "light" : "dark");
        return;
      }

      const moreTrigger = event.target.closest("[data-ts-more-toggle]");
      if (moreTrigger) {
        event.preventDefault();
        event.stopPropagation();
        toggleMore();
        return;
      }

      const closeButton = event.target.closest("[data-ts-more-close]");
      if (closeButton) {
        event.preventDefault();
        closeMore({ restoreFocus: true });
        return;
      }

      const sheetLink = event.target.closest("#tsMobileMoreSheet a");
      if (sheetLink) closeMore();
    });

    addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeMore({ restoreFocus: true });
    });

    initSmartScroll();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
