(() => {
  "use strict";
  window.TWINSCOPE_PUBLIC_SHELL_VERSION = "brand-filter-sheet-v8-20260717";

  const root = document.documentElement;
  const body = document.body;
  const THEME_KEY = "twinscopes-market-theme";

  const setInert = (element, inert) => {
    if (!element) return;
    if (inert) element.setAttribute("inert", "");
    else element.removeAttribute("inert");
  };

  const applyTheme = (theme) => {
    const value = theme === "dark" ? "dark" : "light";
    root.dataset.marketTheme = value;
    root.style.colorScheme = value;
    body?.classList.toggle("theme-dark", value === "dark");
    localStorage.setItem(THEME_KEY, value);
    document.querySelectorAll("[data-ts-theme-toggle]").forEach(button => {
      button.setAttribute("aria-pressed", String(value === "dark"));
    });
  };

  applyTheme(
    localStorage.getItem(THEME_KEY) ||
    (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
  );

  const moreSheet = () => document.getElementById("tsMobileMoreSheet");
  const moreTrigger = () => document.querySelector("[data-ts-more-toggle]");
  const miniCart = () => document.getElementById("tsMiniCart");
  const filterSheet = () => document.getElementById("marketProductFilterSheet");
  const filterBackdrop = () => document.getElementById("marketProductFilterBackdrop");

  const openMore = () => {
    const sheet = moreSheet();
    if (!sheet) return;
    closeMiniCart();
    closeFilter();
    setInert(sheet, false);
    sheet.setAttribute("aria-hidden", "false");
    sheet.classList.add("is-open");
    moreTrigger()?.setAttribute("aria-expanded", "true");
    body.classList.add("ts-more-open");
  };

  const closeMore = () => {
    const sheet = moreSheet();
    if (!sheet) return;
    sheet.classList.remove("is-open");
    sheet.setAttribute("aria-hidden", "true");
    setInert(sheet, true);
    moreTrigger()?.setAttribute("aria-expanded", "false");
    body.classList.remove("ts-more-open");
  };

  const openFilter = () => {
    const sheet = filterSheet();
    const backdrop = filterBackdrop();
    if (!sheet) return;
    closeMore();
    closeMiniCart();
    setInert(sheet, false);
    sheet.setAttribute("aria-hidden", "false");
    sheet.classList.add("is-open");
    if (backdrop) {
      backdrop.hidden = false;
      requestAnimationFrame(() => backdrop.classList.add("is-open"));
    }
    body.classList.add("market-filter-open");
    requestAnimationFrame(() => sheet.querySelector("input,select")?.focus({preventScroll:true}));
  };

  const closeFilter = () => {
    const sheet = filterSheet();
    const backdrop = filterBackdrop();
    if (!sheet) return;
    sheet.classList.remove("is-open");
    sheet.setAttribute("aria-hidden", "true");
    setInert(sheet, true);
    backdrop?.classList.remove("is-open");
    setTimeout(() => { if (backdrop) backdrop.hidden = true; }, 220);
    body.classList.remove("market-filter-open");
  };

  const csrf = () =>
    document.querySelector("[name=csrfmiddlewaretoken]")?.value ||
    document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || "";

  const renderMiniCart = data => {
    const panel = miniCart();
    if (!panel) return;
    panel.querySelector("[data-mini-cart-product-count]").textContent = data.product_count || 0;
    panel.querySelector("[data-mini-cart-item-count]").textContent = data.item_count || 0;
    panel.querySelector("[data-mini-cart-subtotal]").textContent =
      data.items?.length ? `${data.items[0].currency} ${data.subtotal}` : "—";
    document.querySelectorAll("[data-cart-count]").forEach(badge => {
      badge.textContent = data.product_count || 0;
      badge.hidden = Number(data.product_count || 0) <= 0;
    });
    const host = panel.querySelector("[data-mini-cart-items]");
    if (!host) return;
    if (!data.items?.length) {
      host.innerHTML = '<div class="ts-mini-cart__empty"><strong>Your cart is empty</strong><small>Add a product to see it here.</small></div>';
      return;
    }
    host.innerHTML = data.items.map(item => `
      <article class="ts-mini-cart-item" data-mini-cart-row="${item.id}">
        <a href="/products/${item.organization_slug}/${item.slug}/" class="ts-mini-cart-item__media">
          ${item.image ? `<img src="${item.image}" alt="" loading="lazy" decoding="async">` : "<span>▣</span>"}
        </a>
        <div class="ts-mini-cart-item__copy">
          <small>${item.organization}</small>
          <strong>${item.name}</strong>
          <div class="ts-mini-cart-item__controls">
            <button type="button" data-mini-minus>−</button>
            <input type="number" min="1" max="${item.max_quantity}" value="${item.quantity}"
                   data-mini-quantity data-update-url="${item.update_url}">
            <button type="button" data-mini-plus>＋</button>
            <button type="button" data-mini-remove data-remove-url="${item.remove_url}">×</button>
          </div>
        </div>
        <b>${item.currency} ${item.line_total}</b>
      </article>`).join("");
  };

  const refreshMiniCart = async () => {
    const response = await fetch("/cart/summary/", {
      headers: {"X-Requested-With":"XMLHttpRequest"},
      credentials: "same-origin",
      cache: "no-store",
    });
    if (!response.ok) throw new Error("Unable to load cart");
    const data = await response.json();
    renderMiniCart(data);
    return data;
  };

  const openMiniCart = async () => {
    const panel = miniCart();
    if (!panel) return;
    closeMore();
    closeFilter();
    setInert(panel, false);
    panel.setAttribute("aria-hidden", "false");
    panel.classList.add("is-open");
    body.classList.add("ts-mini-cart-open");
    try { await refreshMiniCart(); } catch (_) {}
  };

  function closeMiniCart() {
    const panel = miniCart();
    if (!panel) return;
    panel.classList.remove("is-open");
    panel.setAttribute("aria-hidden", "true");
    setInert(panel, true);
    body.classList.remove("ts-mini-cart-open");
  }

  const updateMiniItem = async (input, quantity) => {
    const safe = Math.max(0, Math.min(Number(input.max || 99), Number(quantity || 0)));
    const response = await fetch(input.dataset.updateUrl, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrf(),
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
      },
      credentials: "same-origin",
      body: new URLSearchParams({quantity:String(safe)}),
    });
    if (response.ok) await refreshMiniCart();
  };

  document.addEventListener("click", event => {
    const target = event.target;

    if (target.closest("[data-ts-more-toggle]")) {
      event.preventDefault();
      const sheet = moreSheet();
      sheet?.classList.contains("is-open") ? closeMore() : openMore();
      return;
    }
    if (target.closest("[data-ts-more-close]")) {
      event.preventDefault();
      closeMore();
      return;
    }
    if (target.closest("[data-market-filter-open]")) {
      event.preventDefault();
      openFilter();
      return;
    }
    if (target.closest("[data-market-filter-close]")) {
      event.preventDefault();
      closeFilter();
      return;
    }
    if (target.closest("[data-mini-cart-open]")) {
      event.preventDefault();
      openMiniCart();
      return;
    }
    if (target.closest("[data-mini-cart-close]")) {
      event.preventDefault();
      closeMiniCart();
      return;
    }
    const plus = target.closest("[data-mini-plus]");
    const minus = target.closest("[data-mini-minus]");
    if (plus || minus) {
      event.preventDefault();
      const input = target.closest("[data-mini-cart-row]")?.querySelector("[data-mini-quantity]");
      if (input) updateMiniItem(input, Number(input.value || 1) + (plus ? 1 : -1));
      return;
    }
    const remove = target.closest("[data-mini-remove]");
    if (remove) {
      event.preventDefault();
      fetch(remove.dataset.removeUrl, {
        method: "POST",
        headers: {"X-CSRFToken":csrf(),"X-Requested-With":"XMLHttpRequest"},
        credentials: "same-origin",
      }).then(refreshMiniCart);
      return;
    }
    const theme = target.closest("[data-ts-theme-toggle]");
    if (theme) {
      event.preventDefault();
      applyTheme(root.dataset.marketTheme === "dark" ? "light" : "dark");
    }
  }, true);

  addEventListener("keydown", event => {
    if (event.key === "Escape") {
      closeMore();
      closeFilter();
      closeMiniCart();
    }
  });

  document.addEventListener("twinscopes:cart-updated", () => {
    refreshMiniCart().catch(() => {});
  });

  // Simple smart scroll without hiding active overlays.
  let lastY = scrollY;
  addEventListener("scroll", () => {
    const current = scrollY;
    const overlayOpen = body.classList.contains("ts-more-open") ||
      body.classList.contains("ts-mini-cart-open") ||
      body.classList.contains("market-filter-open");
    const hide = !overlayOpen && current > 110 && current > lastY + 6;
    document.querySelectorAll("#desktopHeader,#mobileTopActions,#mobileBottomNav").forEach(el => {
      el.classList.toggle("is-scroll-hidden", hide);
      el.classList.toggle("is-scroll-visible", !hide);
    });
    lastY = current;
  }, {passive:true});
})();
