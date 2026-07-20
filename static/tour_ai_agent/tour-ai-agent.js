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
  let visitorId = localStorage.getItem("tw_visitor_id") || "";
  let conversationId = null;
  let currentSceneId = root.dataset.initialSceneId || null;
  let bootstrapped = false;
  let isOpen = false;

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
        "Accept": "application/json",
        "X-CSRFToken": csrfToken,
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Request failed");
    return data;
  }

  function addMessage(text, role = "assistant") {
    if (!text) return;
    const item = document.createElement("div");
    item.className = `tour-ai-msg ${role}`;
    item.textContent = text;
    messages.appendChild(item);
    messages.scrollTop = messages.scrollHeight;
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
    try {
      await post(cfg.signalUrl, payload({ signal_type: signalType, payload: data }));
    } catch (_) {}
  }

  async function openPanel() {
    await bootstrap().catch(() => {});
    isOpen = true;
    panel.hidden = false;
    nudge.hidden = true;
    launcher.setAttribute("aria-expanded", "true");
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
    if (!clean) return;
    addMessage(clean, "user");
    input.value = "";
    input.disabled = true;
    try {
      const data = await post(cfg.messageUrl, payload({ message: clean }));
      conversationId = data.conversation_id || conversationId;
      addMessage(data.text || "I’m here to help.");
    } catch (error) {
      addMessage("I could not answer right now. Please try again.");
    } finally {
      input.disabled = false;
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
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage(input.value);
  });
  root.querySelectorAll("[data-ai-prompt]").forEach((button) => {
    button.addEventListener("click", () => sendMessage(button.dataset.aiPrompt));
  });

  function updateScene(sceneId, title = "") {
    if (!sceneId || String(sceneId) === String(currentSceneId)) return;
    currentSceneId = String(sceneId);
    sendSignal("scene_changed", { scene_title: title });
  }

  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-scene-id]");
    if (trigger) updateScene(trigger.dataset.sceneId, trigger.dataset.sceneTitle || trigger.textContent.trim());
  }, true);

  window.addEventListener("twinscopes:scene-changed", (event) => {
    updateScene(event.detail?.sceneId, event.detail?.title || "");
  });

  window.TwinscopesAgent = {
    open: openPanel,
    close: closePanel,
    setScene: ({ sceneId, sceneTitle }) => updateScene(sceneId, sceneTitle),
    signal: sendSignal,
    action: (actionType, actionPayload = {}) => post(cfg.actionUrl, payload({ action_type: actionType, payload: actionPayload })),
  };

  bootstrap().catch(() => {});
})();
