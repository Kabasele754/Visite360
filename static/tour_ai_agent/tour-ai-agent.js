(() => {
  const root = document.getElementById("tourAiAgent");
  const cfg = window.TOUR_AI_CONFIG;
  if (!root || !cfg || window.__tourAiAgentLoaded) return;
  window.__tourAiAgentLoaded = true;

  const launcher = root.querySelector(".tour-ai-launcher");
  const panel = root.querySelector("#tourAiPanel");
  const nudge = root.querySelector(".tour-ai-nudge");
  const messages = root.querySelector("[data-ai-messages]");
  const form = root.querySelector("[data-ai-form]");
  const input = root.querySelector("[data-ai-input]");
  const sendButton = root.querySelector("[data-ai-send]");
  let visitorId = localStorage.getItem("tw_visitor_id") || "";
  let conversationId = null;
  let currentSceneId = root.dataset.initialSceneId || null;
  let bootstrapped = false;
  let isOpen = false;
  let busy = false;

  const csrfToken = (() => {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  })();

  function payload(extra = {}) {
    return {
      tour_id: cfg.tourId,
      scene_id: currentSceneId || null,
      visitor_id: visitorId || undefined,
      conversation_id: conversationId || undefined,
      locale: cfg.locale || document.documentElement.lang || "en",
      ...extra,
    };
  }

  async function post(url, body) {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-CSRFToken": csrfToken,
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Request failed");
    return data;
  }

  function escapeText(value) {
    return String(value || "");
  }

  function addMessage(text, role = "assistant", meta = {}) {
    if (!text) return null;
    const wrap = document.createElement("div");
    wrap.className = `tour-ai-message-wrap ${role}`;

    const item = document.createElement("div");
    item.className = `tour-ai-msg ${role}`;
    item.textContent = escapeText(text);
    wrap.appendChild(item);

    if (role === "assistant" && meta.provider) {
      const source = document.createElement("small");
      source.className = "tour-ai-source";
      source.textContent = meta.degraded ? "Local assistant" : `Powered by ${meta.provider}`;
      wrap.appendChild(source);
    }

    messages.appendChild(wrap);
    messages.scrollTop = messages.scrollHeight;
    return wrap;
  }

  function addProductCards(products = []) {
    const visible = products.filter((product) => product.verified || product.confidence >= 0.3).slice(0, 4);
    if (!visible.length) return;
    const rail = document.createElement("div");
    rail.className = "tour-ai-products";
    visible.forEach((product) => {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "tour-ai-product-card";
      card.innerHTML = `
        ${product.cover_image ? `<img src="${product.cover_image}" alt="">` : '<span class="tour-ai-product-placeholder">◎</span>'}
        <span class="tour-ai-product-copy">
          <strong>${escapeText(product.name)}</strong>
          <small>${escapeText(product.category || "Related item")}</small>
          <b>${escapeText(product.currency || "")} ${escapeText(product.price || "")}</b>
        </span>`;
      card.addEventListener("click", () => {
        window.TwinscopesAgent?.action("add_to_cart", { product_id: product.id, quantity: 1 });
        sendSignal("ai_product_clicked", { product_id: product.id, verified: product.verified });
      });
      rail.appendChild(card);
    });
    messages.appendChild(rail);
    messages.scrollTop = messages.scrollHeight;
  }

  function createThinkingIndicator() {
    const box = document.createElement("div");
    box.className = "tour-ai-thinking";
    box.setAttribute("role", "status");
    box.setAttribute("aria-live", "polite");
    box.innerHTML = `
      <div class="tour-ai-thinking-head">
        <span class="tour-ai-avatar">AI</span>
        <div><strong>Twinscopes AI is working</strong><small data-thinking-label>Understanding your request</small></div>
      </div>
      <div class="tour-ai-dots" aria-hidden="true"><i></i><i></i><i></i></div>
      <div class="tour-ai-thinking-steps" data-thinking-steps></div>`;
    messages.appendChild(box);
    messages.scrollTop = messages.scrollHeight;
    return box;
  }

  function animateThinking(box) {
    const labels = [
      "Understanding your request",
      "Analyzing the current 360° scene",
      "Checking organization and place context",
      "Comparing verified products",
      "Preparing a reliable answer",
    ];
    let index = 0;
    const label = box.querySelector("[data-thinking-label]");
    const timer = window.setInterval(() => {
      index = Math.min(index + 1, labels.length - 1);
      if (label) label.textContent = labels[index];
    }, 1100);
    return () => window.clearInterval(timer);
  }

  function renderReasoningSummary(box, steps = []) {
    const holder = box.querySelector("[data-thinking-steps]");
    if (!holder) return;
    holder.innerHTML = "";
    steps.slice(0, 4).forEach((step) => {
      const row = document.createElement("div");
      row.className = "tour-ai-step done";
      row.innerHTML = `<span>✓</span><small>${escapeText(step.label)}</small>`;
      holder.appendChild(row);
    });
  }

  function setBusy(value) {
    busy = value;
    input.disabled = value;
    if (sendButton) sendButton.disabled = value;
    root.classList.toggle("is-busy", value);
  }

  function updateMobileOffset() {
    if (!window.matchMedia("(max-width: 640px)").matches) {
      root.style.removeProperty("--tour-ai-mobile-offset");
      return;
    }
    const selectors = [
      "[data-tour-controls]",
      ".tour-controls",
      ".viewer-controls",
      ".panorama-controls",
      ".bottom-controls",
      ".control-bar",
      "#controls",
    ];
    let top = window.innerHeight;
    selectors.forEach((selector) => {
      document.querySelectorAll(selector).forEach((node) => {
        if (root.contains(node)) return;
        const style = getComputedStyle(node);
        if (style.display === "none" || style.visibility === "hidden") return;
        const rect = node.getBoundingClientRect();
        if (rect.width > 80 && rect.height > 20 && rect.bottom >= window.innerHeight - 100) {
          top = Math.min(top, rect.top);
        }
      });
    });
    const occupied = top < window.innerHeight ? Math.max(78, window.innerHeight - top + 16) : 92;
    root.style.setProperty("--tour-ai-mobile-offset", `${occupied}px`);
  }

  async function bootstrap() {
    if (bootstrapped) return;
    const data = await post(cfg.bootstrapUrl, payload());
    bootstrapped = true;
    conversationId = data.conversation_id;
    visitorId = data.visitor_id || visitorId;
    if (visitorId) localStorage.setItem("tw_visitor_id", visitorId);
    addMessage(data.opening_message || "Need help exploring this space?");
    const delay = Math.max(6, Number(data.auto_prompt_delay || 15)) * 1000;
    window.setTimeout(() => {
      if (!isOpen && sessionStorage.getItem("tw_ai_nudge_dismissed") !== "1") nudge.hidden = false;
    }, delay);
  }

  async function sendSignal(signalType, data = {}) {
    try { await post(cfg.signalUrl, payload({ signal_type: signalType, payload: data })); } catch (_) {}
  }

  async function openPanel() {
    await bootstrap().catch(() => {});
    isOpen = true;
    panel.hidden = false;
    nudge.hidden = true;
    launcher.setAttribute("aria-expanded", "true");
    updateMobileOffset();
    input?.focus();
    sendSignal("ai_agent_opened");
  }

  function closePanel() {
    isOpen = false;
    panel.hidden = true;
    launcher.setAttribute("aria-expanded", "false");
  }

  async function sendMessage(text) {
    const clean = String(text || "").trim();
    if (!clean || busy) return;
    addMessage(clean, "user");
    input.value = "";
    setBusy(true);
    const thinking = createThinkingIndicator();
    const stopThinking = animateThinking(thinking);
    try {
      const data = await post(cfg.messageUrl, payload({ message: clean }));
      conversationId = data.conversation_id || conversationId;
      stopThinking();
      renderReasoningSummary(thinking, data.reasoning_steps || []);
      await new Promise((resolve) => setTimeout(resolve, 320));
      thinking.remove();
      addMessage(data.text || "I’m here to help.", "assistant", data);
      addProductCards(data.products || []);
    } catch (error) {
      stopThinking();
      thinking.remove();
      addMessage("I could not answer right now. Please try again.", "assistant", { degraded: true, provider: "local" });
    } finally {
      setBusy(false);
      input.focus();
    }
  }

  launcher.addEventListener("click", () => isOpen ? closePanel() : openPanel());
  root.querySelector("[data-ai-open]")?.addEventListener("click", openPanel);
  root.querySelector("[data-ai-dismiss]")?.addEventListener("click", () => {
    nudge.hidden = true;
    sessionStorage.setItem("tw_ai_nudge_dismissed", "1");
    sendSignal("ai_agent_dismissed");
  });
  root.querySelector("[data-ai-close]")?.addEventListener("click", closePanel);
  form.addEventListener("submit", (event) => { event.preventDefault(); sendMessage(input.value); });
  root.querySelectorAll("[data-ai-prompt]").forEach((button) => button.addEventListener("click", () => sendMessage(button.dataset.aiPrompt)));

  function updateScene(sceneId, title = "") {
    if (!sceneId || String(sceneId) === String(currentSceneId)) return;
    currentSceneId = String(sceneId);
    sendSignal("scene_changed", { scene_title: title });
  }

  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-scene-id]");
    if (trigger) updateScene(trigger.dataset.sceneId, trigger.dataset.sceneTitle || trigger.textContent.trim());
  }, true);
  window.addEventListener("twinscopes:scene-changed", (event) => updateScene(event.detail?.sceneId, event.detail?.title || ""));
  window.addEventListener("resize", updateMobileOffset, { passive: true });
  window.addEventListener("orientationchange", () => setTimeout(updateMobileOffset, 250), { passive: true });

  window.TwinscopesAgent = {
    open: openPanel,
    close: closePanel,
    setScene: ({ sceneId, sceneTitle }) => updateScene(sceneId, sceneTitle),
    signal: sendSignal,
    action: (actionType, actionPayload = {}) => post(cfg.actionUrl, payload({ action_type: actionType, payload: actionPayload })),
  };

  updateMobileOffset();
  bootstrap().catch(() => {});
})();
