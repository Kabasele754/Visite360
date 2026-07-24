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
  const vision = {
    backdrop: root.querySelector("[data-vision-backdrop]"),
    sheet: root.querySelector("[data-vision-sheet]"),
    loading: root.querySelector("[data-vision-loading]"),
    content: root.querySelector("[data-vision-content]"),
    figure: root.querySelector("[data-vision-figure]"),
    image: root.querySelector("[data-vision-image]"),
    kind: root.querySelector("[data-vision-kind]"),
    confidence: root.querySelector("[data-vision-confidence]"),
    title: root.querySelector("[data-vision-title]"),
    description: root.querySelector("[data-vision-description]"),
    exactText: root.querySelector("[data-vision-text]"),
    attributes: root.querySelector("[data-vision-attributes]"),
    sources: root.querySelector("[data-vision-sources]"),
    rescan: root.querySelector("[data-vision-rescan]"),
    ask: root.querySelector("[data-vision-ask]"),
  };

  let visitorId = localStorage.getItem("tw_visitor_id") || "";
  let conversationId = null;
  let currentSceneId = root.dataset.initialSceneId || null;
  let bootstrapped = false;
  let bootstrapPromise = null;
  let isOpen = false;
  let busy = false;
  let insightRequest = null;
  let activeInsight = null;
  let lastInspectionPoint = null;
  let longPressMs = Number(cfg.longPressMs || 650);

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

  async function post(url, body, signal) {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {"Content-Type": "application/json", Accept: "application/json", "X-CSRFToken": csrfToken, "X-Requested-With": "XMLHttpRequest"},
      body: JSON.stringify(body),
      signal,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Request failed");
    return data;
  }

  function text(value) { return String(value ?? ""); }
  function localeIsFrench() { return text(cfg.locale || document.documentElement.lang || "en").toLowerCase().startsWith("fr"); }
  function publicErrorReference(prefix = "AI") {
    const seed = globalThis.crypto?.randomUUID?.().replaceAll("-", "").slice(0, 8) || Math.random().toString(36).slice(2, 10);
    return `${prefix}-${String(seed).toUpperCase()}`;
  }
  function reportTechnicalError(prefix, error, context = {}) {
    const reference = publicErrorReference(prefix);
    console.error(`[Twinscopes ${reference}]`, {
      message: error?.message || text(error) || "Unknown error",
      name: error?.name || "Error",
      stack: error?.stack || "",
      context,
    });
    return reference;
  }
  function friendlyRequestFailure() {
    return localeIsFrench()
      ? "Nous n’avons pas pu terminer cette demande pour le moment. Réessayez dans quelques instants."
      : "We could not complete this request right now. Please try again in a moment.";
  }
  function cardText(value, maxLength = 360) {
    let valueText = text(value).replaceAll("```json", " ").replaceAll("```", " ").replace(/\s+/g, " ").trim();
    if (!valueText || valueText.startsWith("{") || valueText.startsWith("[")) return "";
    const jsonStarts = [valueText.indexOf(" {"), valueText.indexOf(" [")].filter((index) => index > 20);
    if (jsonStarts.length) valueText = valueText.slice(0, Math.min(...jsonStarts)).trim();
    if (valueText.length > maxLength) valueText = `${valueText.slice(0, maxLength).replace(/\s+\S*$/, "").trim()}…`;
    return valueText;
  }
  function clear(node) { while (node?.firstChild) node.removeChild(node.firstChild); }
  function element(tag, className, value) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined) node.textContent = text(value);
    return node;
  }

  function addMessage(value, role = "assistant", meta = {}) {
    if (!value) return null;
    const wrap = element("div", `tour-ai-message-wrap ${role}`);
    wrap.appendChild(element("div", `tour-ai-msg ${role}`, value));
    if (role === "assistant" && meta.provider) {
      wrap.appendChild(element("small", "tour-ai-source", meta.degraded ? "Twinscopes AI · Local mode" : "Twinscopes AI"));
    }
    messages.appendChild(wrap);
    messages.scrollTop = messages.scrollHeight;
    return wrap;
  }

  function addProductCards(products = []) {
    const visible = products.filter((p) => p.verified || Number(p.confidence || 0) >= 0.3).slice(0, 4);
    if (!visible.length) return;
    const rail = element("div", "tour-ai-products");
    visible.forEach((product) => {
      const card = element("button", "tour-ai-product-card");
      card.type = "button";
      if (product.cover_image) {
        const img = document.createElement("img"); img.src = product.cover_image; img.alt = ""; card.appendChild(img);
      } else card.appendChild(element("span", "tour-ai-product-placeholder", "◎"));
      const copy = element("span", "tour-ai-product-copy");
      copy.append(element("strong", "", product.name), element("small", "", product.category || "Related item"), element("b", "", `${product.currency || ""} ${product.price || ""}`.trim()));
      card.appendChild(copy);
      card.addEventListener("click", () => {
        window.TwinscopesAgent?.action("add_to_cart", {product_id: product.id, quantity: 1});
        sendSignal("ai_product_clicked", {product_id: product.id, verified: product.verified});
      });
      rail.appendChild(card);
    });
    messages.appendChild(rail);
    messages.scrollTop = messages.scrollHeight;
  }

  function createThinkingIndicator() {
    const box = element("div", "tour-ai-thinking");
    box.setAttribute("role", "status");
    box.innerHTML = `<div class="tour-ai-thinking-head"><span class="tour-ai-avatar">AI</span><div><strong>${localeIsFrench() ? "Twinscopes prépare votre réponse" : "Twinscopes is preparing your answer"}</strong><small data-thinking-label>${localeIsFrench() ? "Un instant…" : "Just a moment…"}</small></div></div><div class="tour-ai-dots" aria-hidden="true"><i></i><i></i><i></i></div><div class="tour-ai-thinking-steps" data-thinking-steps></div>`;
    messages.appendChild(box); messages.scrollTop = messages.scrollHeight; return box;
  }

  function animateThinking(box) {
    const labels = localeIsFrench()
      ? ["Un instant…", "Recherche des informations utiles", "Préparation d’une réponse claire"]
      : ["Just a moment…", "Finding useful information", "Preparing a clear answer"];
    let index = 0; const label = box.querySelector("[data-thinking-label]");
    const timer = setInterval(() => { index = Math.min(index + 1, labels.length - 1); if (label) label.textContent = labels[index]; }, 1300);
    return () => clearInterval(timer);
  }

  function renderReasoningSummary(box, steps = []) {
    const holder = box.querySelector("[data-thinking-steps]"); if (!holder) return; clear(holder);
    steps.slice(0, 4).forEach((step) => { const row = element("div", "tour-ai-step done"); row.append(element("span", "", "✓"), element("small", "", step.label)); holder.appendChild(row); });
  }

  function setBusy(value) {
    busy = value; input.disabled = value; if (sendButton) sendButton.disabled = value; root.classList.toggle("is-busy", value);
  }

  function updateMobileOffset() {
    if (!matchMedia("(max-width: 640px)").matches) { root.style.removeProperty("--tour-ai-mobile-offset"); return; }
    const selectors = ["[data-tour-controls]", ".tour-controls", ".viewer-controls", ".panorama-controls", ".bottom-controls", ".control-bar", "#controls"];
    let top = innerHeight;
    selectors.forEach((selector) => document.querySelectorAll(selector).forEach((node) => {
      if (root.contains(node)) return;
      const style = getComputedStyle(node); if (style.display === "none" || style.visibility === "hidden") return;
      const rect = node.getBoundingClientRect(); if (rect.width > 80 && rect.height > 20 && rect.bottom >= innerHeight - 100) top = Math.min(top, rect.top);
    }));
    root.style.setProperty("--tour-ai-mobile-offset", `${top < innerHeight ? Math.max(78, innerHeight - top + 16) : 92}px`);
  }

  async function bootstrap() {
    if (bootstrapped) return;
    if (bootstrapPromise) return bootstrapPromise;
    bootstrapPromise = (async () => {
      const data = await post(cfg.bootstrapUrl, payload());
      bootstrapped = true; conversationId = data.conversation_id; visitorId = data.visitor_id || visitorId;
      longPressMs = Number(data.vision_long_press_duration_ms || longPressMs);
      window.dispatchEvent(new CustomEvent("twinscopes:vision-config", {detail: {longPressMs, available: data.vision_available}}));
      if (visitorId) localStorage.setItem("tw_visitor_id", visitorId);
      addMessage(data.opening_message || "Need help exploring this space?");
      setTimeout(() => { if (!isOpen && sessionStorage.getItem("tw_ai_nudge_dismissed") !== "1") nudge.hidden = false; }, Math.max(6, Number(data.auto_prompt_delay || 15)) * 1000);
    })();
    try { return await bootstrapPromise; }
    finally { bootstrapPromise = null; }
  }

  async function sendSignal(signalType, data = {}) { try { await post(cfg.signalUrl, payload({signal_type: signalType, payload: data})); } catch (_) {} }
  async function openPanel() {
    try {
      await bootstrap();
    } catch (error) {
      const reference = reportTechnicalError("AI-START", error, {tourId: cfg.tourId, sceneId: currentSceneId});
      if (!messages.children.length) addMessage(friendlyRequestFailure(), "assistant", {degraded: true, provider: "local"});
    }
    isOpen = true; panel.hidden = false; nudge.hidden = true; launcher.setAttribute("aria-expanded", "true"); updateMobileOffset(); input?.focus(); sendSignal("ai_agent_opened");
  }
  function closePanel() { isOpen = false; panel.hidden = true; launcher.setAttribute("aria-expanded", "false"); }

  async function sendMessage(value, options = {}) {
    const clean = text(value).trim(); if (!clean || busy) return;
    addMessage(options.displayText || clean, "user"); input.value = ""; setBusy(true);
    const thinking = createThinkingIndicator(); const stopThinking = animateThinking(thinking);
    try {
      const requestId = crypto?.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
      const data = await post(cfg.messageUrl, payload({
        message: clean,
        request_id: requestId,
        vision_insight_id: options.visionInsightId || undefined,
      }));
      conversationId = data.conversation_id || conversationId; stopThinking(); renderReasoningSummary(thinking, data.reasoning_steps || []);
      await new Promise((resolve) => setTimeout(resolve, 320)); thinking.remove();
      addMessage(data.text || "I’m here to help.", "assistant", data); addProductCards(data.products || []);
    } catch (error) {
      stopThinking(); thinking.remove();
      const reference = reportTechnicalError("AI-MSG", error, {tourId: cfg.tourId, sceneId: currentSceneId});
      addMessage(friendlyRequestFailure(), "assistant", {degraded: true, provider: "local"});
    }
    finally { setBusy(false); input.focus(); }
  }

  function openVisionLoading() {
    vision.backdrop.hidden = false; vision.sheet.hidden = false; vision.loading.hidden = false; vision.content.hidden = true;
    requestAnimationFrame(() => root.classList.add("vision-open"));
  }
  function closeVision() {
    insightRequest?.abort(); insightRequest = null; activeInsight = null; root.classList.remove("vision-open");
    setTimeout(() => { vision.backdrop.hidden = true; vision.sheet.hidden = true; }, 180);
  }

  function renderVision(data) {
    vision.loading.hidden = true; vision.content.hidden = false; activeInsight = data.insight || null;
    const item = data.insight || data;
    const refineSelection = ["no_object", "refine_selection"].includes(data.status);
    vision.kind.textContent = refineSelection
      ? (localeIsFrench() ? "Zone sélectionnée" : "Selected area")
      : item.kind === "text"
        ? (localeIsFrench() ? "Texte visible" : "Visible text")
        : item.kind === "object"
          ? (localeIsFrench() ? "Élément identifié" : "Identified item")
          : (localeIsFrench() ? "Détail de la scène" : "Scene detail");
    const score = Number(item.confidence_percent ?? data.confidence_percent ?? 0);
    vision.confidence.textContent = score >= 80
      ? (localeIsFrench() ? "Confiance élevée" : "High confidence")
      : score > 0
        ? (localeIsFrench() ? "Résultat probable" : "Likely match")
        : "";
    vision.title.textContent = cardText(item.title, 180) || (localeIsFrench() ? "Détail de la scène" : "Scene detail");
    vision.description.textContent = cardText(item.description, 360) || (localeIsFrench()
      ? "Aucun détail précis n’a été confirmé à cet endroit."
      : "No specific detail was confirmed at this point.");
    if (vision.ask) vision.ask.hidden = refineSelection;
    if (vision.rescan) {
      vision.rescan.hidden = !refineSelection;
      vision.rescan.textContent = localeIsFrench() ? "Scanner à nouveau" : "Scan again";
    }

    if (item.crop_url) { vision.image.src = item.crop_url; vision.figure.hidden = false; }
    else { vision.image.removeAttribute("src"); vision.figure.hidden = true; }
    if (item.exact_text) { vision.exactText.textContent = `“${item.exact_text}”`; vision.exactText.hidden = false; }
    else { vision.exactText.textContent = ""; vision.exactText.hidden = true; }

    clear(vision.attributes);
    const publicAttributeLabels = {
      category: localeIsFrench() ? "Catégorie" : "Category",
      color: localeIsFrench() ? "Couleur" : "Color",
      material: localeIsFrench() ? "Matériau" : "Material",
      condition: localeIsFrench() ? "État" : "Condition",
    };
    Object.entries(item.attributes || {})
      .filter(([key, value]) => publicAttributeLabels[key] && typeof value !== "object" && value !== "")
      .slice(0, 4)
      .forEach(([key, value]) => {
        vision.attributes.appendChild(element("span", "", `${publicAttributeLabels[key]}: ${value}`));
      });
    clear(vision.sources);
    if (vision.sources) vision.sources.hidden = true;
  }

  async function inspectPoint(point) {
    if (!cfg.inspectUrl || !point?.sceneId) return;
    lastInspectionPoint = {
      sceneId: point.sceneId,
      yaw: Number(point.yaw),
      pitch: Number(point.pitch),
      clientX: Number(point.clientX),
      clientY: Number(point.clientY),
    };
    currentSceneId = String(point.sceneId);
    await bootstrap().catch(() => {});
    insightRequest?.abort();
    const controller = new AbortController();
    insightRequest = controller;
    openVisionLoading();
    try {
      const requestPayload = payload({
        yaw: Number(point.yaw),
        pitch: Number(point.pitch),
        selection: point.selection || null,
      });
      const maxAttempts = 80;
      for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
        const data = await post(cfg.inspectUrl, requestPayload, controller.signal);
        renderVision(data);
        if (data.status !== "analyzing") return;
        const waitMs = Math.max(1200, Math.min(Number(data.retry_after_ms || 3000), 10000));
        await new Promise((resolve, reject) => {
          const timer = window.setTimeout(resolve, waitMs);
          controller.signal.addEventListener("abort", () => {
            window.clearTimeout(timer);
            reject(new DOMException("Aborted", "AbortError"));
          }, {once: true});
        });
      }
      renderVision({
        title: localeIsFrench() ? "Préparation toujours en cours" : "Still preparing the details",
        description: localeIsFrench()
          ? "Cette scène contient beaucoup d’éléments. Fermez cette fiche et réessayez dans quelques instants."
          : "This scene contains many details. Close this card and try again in a moment.",
      });
    } catch (error) {
      if (error.name === "AbortError") return;
      reportTechnicalError("VISION", error, {
        tourId: cfg.tourId,
        sceneId: currentSceneId,
        point: {
          sceneId: point?.sceneId,
          yaw: point?.yaw,
          pitch: point?.pitch,
          selection: point?.selection ? {
            version: point.selection.version,
            bbox: point.selection.bbox,
            hasCapture: Boolean(point.selection.capture),
          } : null,
        },
      });
      renderVision({
        title: localeIsFrench() ? "Détails visuels temporairement indisponibles" : "Visual details temporarily unavailable",
        description: localeIsFrench()
          ? "Nous ne pouvons pas afficher ces informations maintenant. Réessayez dans un instant."
          : "We cannot display this information right now. Please try again shortly.",
      });
    } finally {
      if (insightRequest === controller) insightRequest = null;
    }
  }

  launcher.addEventListener("click", () => isOpen ? closePanel() : openPanel());
  root.querySelector("[data-ai-open]")?.addEventListener("click", openPanel);
  root.querySelector("[data-ai-dismiss]")?.addEventListener("click", () => { nudge.hidden = true; sessionStorage.setItem("tw_ai_nudge_dismissed", "1"); sendSignal("ai_agent_dismissed"); });
  root.querySelector("[data-ai-close]")?.addEventListener("click", closePanel);
  form.addEventListener("submit", (event) => { event.preventDefault(); sendMessage(input.value); });
  root.querySelectorAll("[data-ai-prompt]").forEach((button) => button.addEventListener("click", () => sendMessage(button.dataset.aiPrompt)));
  root.querySelectorAll("[data-vision-close],[data-vision-dismiss]").forEach((button) => button.addEventListener("click", closeVision));
  vision.backdrop?.addEventListener("click", closeVision);
  vision.rescan?.addEventListener("click", () => {
    const point = lastInspectionPoint || {};
    closeVision();
    window.setTimeout(() => {
      window.dispatchEvent(new CustomEvent("twinscopes:vision-reframe", {
        detail: {
          clientX: Number.isFinite(point.clientX) ? point.clientX : undefined,
          clientY: Number.isFinite(point.clientY) ? point.clientY : undefined,
        },
      }));
    }, 190);
  });
  vision.ask?.addEventListener("click", async () => {
    const target = activeInsight?.title || vision.title.textContent || "this visible detail";
    const exactText = activeInsight?.exact_text ? ` Visible text: ${activeInsight.exact_text}.` : "";
    closeVision(); await openPanel();
    sendMessage(
      `Explain only the exact visual item selected in the current scene: ${target}.${exactText} Use the selected visual insight and verified organization data; do not substitute another object or invent a catalogue match.`,
      {displayText: `Tell me more about ${target}`, visionInsightId: activeInsight?.id},
    );
  });

  function updateScene(sceneId, title = "") {
    if (!sceneId || String(sceneId) === String(currentSceneId)) return;
    currentSceneId = String(sceneId); closeVision(); sendSignal("scene_changed", {scene_title: title});
  }
  document.addEventListener("click", (event) => { const trigger = event.target.closest("[data-scene-id]"); if (trigger) updateScene(trigger.dataset.sceneId, trigger.dataset.sceneTitle || trigger.textContent.trim()); }, true);
  window.addEventListener("twinscopes:scene-changed", (event) => updateScene(event.detail?.sceneId, event.detail?.title || ""));
  window.addEventListener("twinscopes:vision-long-press", (event) => inspectPoint(event.detail));
  window.addEventListener("resize", updateMobileOffset, {passive: true});
  window.addEventListener("orientationchange", () => setTimeout(updateMobileOffset, 250), {passive: true});
  document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !vision.sheet.hidden) closeVision(); });

  window.TwinscopesAgent = {
    open: openPanel, close: closePanel,
    setScene: ({sceneId, sceneTitle}) => updateScene(sceneId, sceneTitle),
    inspectPoint, signal: sendSignal,
    action: (actionType, actionPayload = {}) => post(cfg.actionUrl, payload({action_type: actionType, payload: actionPayload})),
  };

  updateMobileOffset(); bootstrap().catch(() => {});
})();
