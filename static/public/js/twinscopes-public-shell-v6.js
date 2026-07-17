(() => {
  "use strict";

  window.TWINSCOPE_PUBLIC_SHELL_VERSION = "marketplace-shell-v6-20260717";

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


  const csrfToken = () =>
    document.querySelector("[name=csrfmiddlewaretoken]")?.value ||
    document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] ||
    "";

  const miniCart = () => document.getElementById("tsMiniCart");

  const renderMiniCart = (data) => {
    const panel = miniCart();
    if (!panel) return;
    panel.querySelector("[data-mini-cart-product-count]").textContent = data.product_count || 0;
    panel.querySelector("[data-mini-cart-item-count]").textContent = data.item_count || 0;
    panel.querySelector("[data-mini-cart-subtotal]").textContent =
      data.items?.length ? `${data.items[0].currency} ${data.subtotal}` : "—";

    document.querySelectorAll("[data-cart-count]").forEach((badge) => {
      badge.textContent = data.product_count || 0;
      badge.hidden = Number(data.product_count || 0) <= 0;
    });

    const host = panel.querySelector("[data-mini-cart-items]");
    if (!data.items?.length) {
      host.innerHTML = '<div class="ts-mini-cart__empty"><strong>Your cart is empty</strong><small>Add a product to see it here.</small></div>';
      return;
    }

    host.innerHTML = data.items.map((item) => `
      <article class="ts-mini-cart-item" data-mini-cart-row="${item.id}">
        <a href="/products/${item.organization_slug}/${item.slug}/" class="ts-mini-cart-item__media">
          ${item.image ? `<img src="${item.image}" alt="">` : '<span>▣</span>'}
        </a>
        <div class="ts-mini-cart-item__copy">
          <small>${item.organization}</small>
          <strong>${item.name}</strong>
          <div class="ts-mini-cart-item__controls">
            <button type="button" data-mini-minus aria-label="Decrease">−</button>
            <input type="number" min="1" max="${item.max_quantity}" value="${item.quantity}"
                   data-mini-quantity data-update-url="${item.update_url}">
            <button type="button" data-mini-plus aria-label="Increase">＋</button>
            <button type="button" data-mini-remove data-remove-url="${item.remove_url}" aria-label="Remove">×</button>
          </div>
        </div>
        <b>${item.currency} ${item.line_total}</b>
      </article>
    `).join("");
  };

  const refreshMiniCart = async () => {
    const response = await fetch("/cart/summary/", {
      headers: {"X-Requested-With": "XMLHttpRequest"},
      credentials: "same-origin",
    });
    if (!response.ok) throw new Error("Unable to load cart.");
    const data = await response.json();
    renderMiniCart(data);
    return data;
  };

  const openMiniCart = async () => {
    closeMore();
    const panel = miniCart();
    if (!panel) return;
    panel.removeAttribute("inert");
    panel.setAttribute("aria-hidden", "false");
    panel.classList.add("is-open");
    document.body.classList.add("ts-mini-cart-open");
    try { await refreshMiniCart(); } catch (_) {}
  };

  const closeMiniCart = () => {
    const panel = miniCart();
    if (!panel) return;
    panel.classList.remove("is-open");
    panel.setAttribute("aria-hidden", "true");
    panel.setAttribute("inert", "");
    document.body.classList.remove("ts-mini-cart-open");
  };

  const updateMiniCartItem = async (input, quantity) => {
    const safe = Math.max(0, Math.min(Number(input.max || 99), Number(quantity || 0)));
    const body = new URLSearchParams({quantity: String(safe)});
    const response = await fetch(input.dataset.updateUrl, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken(),
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
      },
      credentials: "same-origin",
      body,
    });
    if (!response.ok) throw new Error("Unable to update cart.");
    await refreshMiniCart();
  };


  const init = () => {
    if (initialized) return;
    initialized = true;

    applyTheme(readTheme());

    document.addEventListener("click", (event) => {
      const miniOpen = event.target.closest("[data-mini-cart-open]");
      if (miniOpen) {
        event.preventDefault();
        openMiniCart();
        return;
      }

      const miniClose = event.target.closest("[data-mini-cart-close]");
      if (miniClose) {
        event.preventDefault();
        closeMiniCart();
        return;
      }

      const miniPlus = event.target.closest("[data-mini-plus]");
      const miniMinus = event.target.closest("[data-mini-minus]");
      const miniRemove = event.target.closest("[data-mini-remove]");
      if (miniPlus || miniMinus) {
        event.preventDefault();
        const row = event.target.closest("[data-mini-cart-row]");
        const input = row?.querySelector("[data-mini-quantity]");
        if (input) updateMiniCartItem(input, Number(input.value || 1) + (miniPlus ? 1 : -1));
        return;
      }
      if (miniRemove) {
        event.preventDefault();
        fetch(miniRemove.dataset.removeUrl, {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken(),
            "X-Requested-With": "XMLHttpRequest",
          },
          credentials: "same-origin",
        }).then(refreshMiniCart);
        return;
      }

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
      if (event.key === "Escape") { closeMore({ restoreFocus: true }); closeMiniCart(); }
    });

    initSmartScroll();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
