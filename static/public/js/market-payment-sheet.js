(() => {
  "use strict";

  const body = document.body;
  const sheet = document.getElementById("marketPaymentSheet");
  const backdrop = document.getElementById("marketPaymentBackdrop");
  if (!sheet || !backdrop) return;

  const stripeRoot = document.getElementById("marketStripeEmbedded");
  const paypalRoot = document.getElementById("marketPayPalButtons");
  const status = document.getElementById("marketPaymentStatus");
  const title = document.getElementById("marketPaymentSheetTitle");
  const csrf = document.querySelector("input[name='csrfmiddlewaretoken']")?.value
    || document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)?.[1]
    || "";

  let embeddedCheckout = null;
  let paypalRendered = false;
  let lastTrigger = null;

  const setStatus = (message = "", type = "") => {
    status.textContent = message;
    status.dataset.type = type;
    status.hidden = !message;
  };

  const openSheet = (provider, trigger) => {
    lastTrigger = trigger || document.activeElement;
    backdrop.hidden = false;
    sheet.dataset.provider = provider;
    stripeRoot.hidden = provider !== "stripe";
    paypalRoot.hidden = provider !== "paypal";
    title.textContent = provider === "stripe" ? "Pay securely by card" : "Pay with PayPal";

    requestAnimationFrame(() => {
      backdrop.classList.add("is-open");
      sheet.removeAttribute("inert");
      sheet.setAttribute("aria-hidden", "false");
      sheet.classList.add("is-open");
      document.body.classList.add("market-payment-sheet-open");
    });

    if (provider === "stripe") initStripe();
    if (provider === "paypal") initPayPal();
  };

  const closeSheet = () => {
    const focused = document.activeElement;
    if (focused && sheet.contains(focused) && typeof focused.blur === "function") focused.blur();
    sheet.classList.remove("is-open");
    backdrop.classList.remove("is-open");
    sheet.setAttribute("aria-hidden", "true");
    sheet.setAttribute("inert", "");
    document.body.classList.remove("market-payment-sheet-open");
    setTimeout(() => {
      backdrop.hidden = true;
      if (lastTrigger && document.contains(lastTrigger)) {
        try { lastTrigger.focus({ preventScroll: true }); } catch (_) {}
      }
    }, 260);
  };

  async function initStripe() {
    if (embeddedCheckout || !window.Stripe) return;
    const key = body.dataset.stripePublicKey;
    const endpoint = body.dataset.stripeSessionUrl;
    if (!key || !endpoint) {
      setStatus("Stripe configuration is unavailable.", "error");
      return;
    }

    setStatus("Preparing the secure card form…", "loading");
    try {
      const stripe = window.Stripe(key);
      embeddedCheckout = await stripe.initEmbeddedCheckout({
        fetchClientSecret: async () => {
          const response = await fetch(endpoint, {
            method: "POST",
            credentials: "same-origin",
            headers: {
              "X-CSRFToken": csrf,
              "X-Requested-With": "XMLHttpRequest",
            },
          });
          const data = await response.json();
          if (!response.ok || !data.ok) throw new Error(data.error || "Stripe session could not be created.");
          if (data.paid && data.redirect_url) {
            window.location.assign(data.redirect_url);
            return "";
          }
          return data.client_secret;
        },
      });
      embeddedCheckout.mount("#marketStripeEmbedded");
      setStatus("");
    } catch (error) {
      console.error("STRIPE_EMBEDDED_INIT_FAILED", error);
      setStatus(error.message || "Stripe could not load.", "error");
    }
  }

  function initPayPal() {
    if (paypalRendered) return;
    if (!window.paypal) {
      setStatus("PayPal could not load. Check the content security policy and client ID.", "error");
      return;
    }
    paypalRendered = true;
    setStatus("Loading PayPal…", "loading");

    window.paypal.Buttons({
      style: {
        layout: "vertical",
        color: document.documentElement.dataset.marketTheme === "dark" ? "black" : "gold",
        shape: "rect",
        label: "paypal",
        height: 48,
      },
      createOrder: async () => {
        const response = await fetch(body.dataset.paypalCreateUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "X-CSRFToken": csrf,
            "X-Requested-With": "XMLHttpRequest",
          },
        });
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || "PayPal order could not be created.");
        if (data.paid && data.redirect_url) {
          window.location.assign(data.redirect_url);
          return "";
        }
        return data.id;
      },
      onApprove: async (data) => {
        setStatus("Confirming your PayPal payment…", "loading");
        const response = await fetch(body.dataset.paypalCaptureUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrf,
            "X-Requested-With": "XMLHttpRequest",
          },
          body: JSON.stringify({ order_id: data.orderID }),
        });
        const result = await response.json();
        if (!response.ok || !result.ok) throw new Error(result.error || "PayPal payment could not be confirmed.");
        window.location.assign(result.redirect_url);
      },
      onCancel: () => setStatus("Payment cancelled. You can try again.", "info"),
      onError: (error) => {
        console.error("PAYPAL_BUTTON_FAILED", error);
        setStatus(error.message || "PayPal could not complete the payment.", "error");
      },
    }).render("#marketPayPalButtons").then(() => setStatus(""));
  }

  document.querySelectorAll("[data-open-payment-sheet]").forEach((button) => {
    button.addEventListener("click", () => openSheet(button.dataset.openPaymentSheet, button));
  });
  document.querySelectorAll("[data-payment-sheet-close]").forEach((button) => {
    button.addEventListener("click", closeSheet);
  });
  addEventListener("keydown", (event) => {
    if (event.key === "Escape" && sheet.classList.contains("is-open")) closeSheet();
  });

  const selected = body.dataset.selectedProvider;
  if (selected === "stripe" || selected === "paypal") {
    const trigger = document.querySelector(`[data-open-payment-sheet="${selected}"]`);
    if (trigger) requestAnimationFrame(() => openSheet(selected, trigger));
  }
})();
