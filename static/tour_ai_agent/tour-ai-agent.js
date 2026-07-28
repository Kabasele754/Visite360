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
  const resource = {
    backdrop: root.querySelector("[data-resource-backdrop]"),
    modal: root.querySelector("[data-resource-modal]"),
    icon: root.querySelector("[data-resource-icon]"),
    eyebrow: root.querySelector("[data-resource-eyebrow]"),
    title: root.querySelector("[data-resource-title]"),
    body: root.querySelector("[data-resource-body]"),
    external: root.querySelector("[data-resource-external]"),
    embed: root.querySelector("[data-resource-embed]"),
    embedStatus: root.querySelector("[data-resource-embed-status]"),
    frame: root.querySelector("[data-resource-frame]"),
    closeButtons: root.querySelectorAll("[data-resource-close]"),
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
  let activeResource = null;
  let resourcePreviousFocus = null;
  let resourceFrameTimer = null;
  let activeMessageController = null;
  let stopActiveThinking = null;
  let sceneSignalTimer = null;
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

  function sourceMap(meta = {}) {
    return new Map((meta.sources || []).filter((item) => item?.citation).map((item) => [String(item.citation), item]));
  }

  function safeResourceUrl(value) {
    const raw = text(value).trim();
    if (!raw) return "";
    if (/^(mailto:|tel:)/i.test(raw)) return raw;
    try {
      const parsed = new URL(raw, window.location.origin);
      return ["http:", "https:"].includes(parsed.protocol) ? parsed.href : "";
    } catch (_) {
      return "";
    }
  }

  function resourceKindFromUrl(url) {
    if (/^mailto:/i.test(url)) return "email";
    if (/^tel:/i.test(url)) return "phone";
    return "url";
  }

  function createInlineResource(label, info, className = "tour-ai-inline-link") {
    const button = element("button", className, label);
    button.type = "button";
    button.addEventListener("click", () => openResourceModal(info));
    return button;
  }

  function appendPlainWithResources(parent, value, meta = {}) {
    const map = sourceMap(meta);
    const pattern = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\[[^\]\n]+\]\((?:https?:\/\/|mailto:|tel:)[^)\s]+\)|\[K\d+\]|https?:\/\/[^\s<]+|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|\+?\d[\d\s().-]{7,}\d|\*[^*\n]+\*)/gi;
    let cursor = 0;
    let match;
    while ((match = pattern.exec(value)) !== null) {
      if (match.index > cursor) parent.appendChild(document.createTextNode(value.slice(cursor, match.index).replace(/\*+/g, "")));
      const token = match[0];
      if (token.startsWith("**") && token.endsWith("**")) {
        const strong = element("strong");
        appendPlainWithResources(strong, token.slice(2, -2), meta);
        parent.appendChild(strong);
      } else if (token.startsWith("`") && token.endsWith("`")) {
        parent.appendChild(element("code", "", token.slice(1, -1)));
      } else if (/^\[K\d+\]$/.test(token)) {
        const citation = token.slice(1, -1);
        const item = map.get(citation);
        if (item) {
          parent.appendChild(createInlineResource(citation.replace("K", ""), {
            kind: "source",
            eyebrow: "Verified source",
            title: item.title || `Source ${citation}`,
            source: item.source || "Official organization source",
            summary: item.summary || "",
            url: item.url || "",
            citation,
            copyValue: item.url || item.title || "",
          }, "tour-ai-citation"));
        }
      } else if (token.startsWith("[") && token.includes("](")) {
        const parsed = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
        const url = safeResourceUrl(parsed?.[2]);
        const label = parsed?.[1] || "View information";
        if (url) parent.appendChild(createInlineResource(label, {
          kind: resourceKindFromUrl(url), title: label, url,
          value: url.replace(/^(mailto:|tel:)/i, ""), copyValue: url.replace(/^(mailto:|tel:)/i, ""),
        }));
        else parent.appendChild(document.createTextNode(label));
      } else if (/^https?:\/\//i.test(token)) {
        let clean = token;
        let suffix = "";
        while (/[.,;:!?)]$/.test(clean)) { suffix = clean.slice(-1) + suffix; clean = clean.slice(0, -1); }
        const url = safeResourceUrl(clean);
        if (url) parent.appendChild(createInlineResource(new URL(url).hostname.replace(/^www\./, ""), {
          kind: "url", title: "Official web address", url, value: url, copyValue: url,
        }));
        if (suffix) parent.appendChild(document.createTextNode(suffix));
      } else if (/^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i.test(token)) {
        parent.appendChild(createInlineResource(token, {kind: "email", title: "Public email", value: token, copyValue: token}));
      } else if ((token.match(/\d/g) || []).length >= 8) {
        parent.appendChild(createInlineResource(token.trim(), {kind: "phone", title: "Public phone", value: token.trim(), copyValue: token.trim()}));
      } else if (token.startsWith("*") && token.endsWith("*")) {
        const em = element("em");
        appendPlainWithResources(em, token.slice(1, -1), meta);
        parent.appendChild(em);
      } else {
        parent.appendChild(document.createTextNode(token.replace(/\*+/g, "")));
      }
      cursor = pattern.lastIndex;
    }
    if (cursor < value.length) parent.appendChild(document.createTextNode(value.slice(cursor).replace(/\*+/g, "")));
  }

  function renderMarkdown(container, value, meta = {}) {
    clear(container);
    const lines = text(value).replace(/```(?:markdown|md|text)?/gi, "").replace(/```/g, "").replace(/\r\n?/g, "\n").split("\n");
    let paragraph = [];
    let list = null;
    let listType = "";

    const flushParagraph = () => {
      const content = paragraph.join(" ").trim();
      paragraph = [];
      if (!content) return;
      const p = element("p");
      appendPlainWithResources(p, content, meta);
      container.appendChild(p);
    };
    const closeList = () => { list = null; listType = ""; };

    lines.forEach((rawLine) => {
      const line = rawLine.trim();
      if (!line) { flushParagraph(); closeList(); return; }
      const heading = line.match(/^(#{1,3})\s+(.+)$/);
      if (heading) {
        flushParagraph(); closeList();
        const h = element(`h${Math.min(heading[1].length + 2, 5)}`);
        appendPlainWithResources(h, heading[2], meta);
        container.appendChild(h);
        return;
      }
      const bullet = line.match(/^[-*•]\s+(.+)$/);
      const numbered = line.match(/^\d+[.)]\s+(.+)$/);
      if (bullet || numbered) {
        flushParagraph();
        const type = numbered ? "ol" : "ul";
        if (!list || listType !== type) { closeList(); list = element(type); listType = type; container.appendChild(list); }
        const li = element("li"); appendPlainWithResources(li, (bullet || numbered)[1], meta); list.appendChild(li);
        return;
      }
      const quote = line.match(/^>\s*(.+)$/);
      if (quote) {
        flushParagraph(); closeList();
        const blockquote = element("blockquote"); appendPlainWithResources(blockquote, quote[1], meta); container.appendChild(blockquote);
        return;
      }
      closeList(); paragraph.push(line);
    });
    flushParagraph();
    if (!container.children.length) container.textContent = text(value).replace(/\*+/g, "");
  }

  function citedSources(value, meta = {}) {
    const cited = new Set(text(value).match(/K\d+/g) || []);
    return (meta.sources || []).filter((item) => cited.has(String(item.citation))).slice(0, 5);
  }

  function appendSourceStrip(wrap, value, meta = {}) {
    const sources = citedSources(value, meta);
    if (!sources.length) return;
    const strip = element("div", "tour-ai-message-sources");
    strip.appendChild(element("small", "", "Sources"));
    sources.forEach((item) => strip.appendChild(createInlineResource(item.citation, {
      kind: "source", eyebrow: "Verified source", title: item.title || item.citation,
      source: item.source || "Official organization source", summary: item.summary || "",
      url: item.url || "", citation: item.citation, copyValue: item.url || item.title || "",
    }, "tour-ai-source-chip")));
    wrap.appendChild(strip);
  }

  function contactItems(contact = {}) {
    const rows = [];
    if (contact.phone) rows.push({label: "Phone", kind: "phone", value: contact.phone});
    if (contact.email) rows.push({label: "Email", kind: "email", value: contact.email});
    if (contact.website) rows.push({label: "Official website", kind: "url", value: contact.website, url: contact.website, embed_mode: "auto", embed_allowed: contact.allow_embedded_resources !== false});
    if (contact.booking_url) rows.push({label: "Appointments", kind: "booking", value: contact.booking_url, url: contact.booking_url, embed_mode: "auto", embed_allowed: contact.allow_embedded_resources !== false, native_fallback: "booking"});
    Object.entries(contact.social_links || {}).forEach(([network, url]) => rows.push({label: network.charAt(0).toUpperCase() + network.slice(1), kind: "url", value: url, url, embed_mode: "summary"}));
    (contact.resources || []).forEach((item) => rows.push({
      label: item.label || item.button_label || "Connected service",
      title: item.label || "Connected service",
      kind: item.kind || "url",
      value: item.url,
      url: item.url,
      description: item.description || "",
      embed_mode: item.embed_mode || "auto",
      embed_allowed: item.verified !== false && contact.allow_embedded_resources !== false,
      native_fallback: ["booking", "crm"].includes(item.kind) ? "booking" : ["contact", "form"].includes(item.kind) ? "contact" : "",
      sandbox_permissions: item.sandbox_permissions || [],
      verified: item.verified !== false,
      resource_id: item.id,
    }));
    const seen = new Set();
    return rows.filter((item) => {
      const key = `${item.kind}:${item.url || item.value || item.label}`.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function appendContactCard(wrap, contact = {}, force = false) {
    const rows = contactItems(contact);
    if (!rows.length || !force) return;
    const card = element("div", "tour-ai-contact-card");
    const heading = element("div", "tour-ai-contact-card-heading");
    heading.append(element("strong", "", contact.organization_name || "Public contact information"), element("small", "", "Verified organization details"));
    card.appendChild(heading);
    rows.slice(0, 5).forEach((item) => {
      const button = element("button", "tour-ai-contact-row"); button.type = "button";
      const copy = element("span", "tour-ai-contact-copy"); copy.append(element("small", "", item.label), element("strong", "", item.value));
      button.append(copy, element("span", "tour-ai-contact-chevron", "›"));
      button.addEventListener("click", () => openResourceModal({...item, title: item.label, copyValue: item.value}));
      card.appendChild(button);
    });
    wrap.appendChild(card);
  }

  function addMessage(value, role = "assistant", meta = {}) {
    if (!value) return null;
    const wrap = element("div", `tour-ai-message-wrap ${role}`);
    const bubble = element("div", `tour-ai-msg ${role}`);
    if (role === "assistant") renderMarkdown(bubble, value, meta);
    else bubble.textContent = text(value);
    wrap.appendChild(bubble);
    if (role === "assistant") {
      appendSourceStrip(wrap, value, meta);
      appendContactCard(wrap, meta.contact || {}, meta.intent === "contact" || meta.showContact === true);
    }
    if (role === "assistant" && meta.provider) {
      const assistantLabel = text(cfg.assistantName || "Assistant");
      wrap.appendChild(element("small", "tour-ai-source", meta.degraded ? `${assistantLabel} · Local mode` : assistantLabel));
    }
    messages.appendChild(wrap);
    messages.scrollTop = messages.scrollHeight;
    return wrap;
  }

  function iconForResource(kind) {
    return ({
      phone: "☎", email: "@", source: "✓", contact_collection: "i", url: "↗",
      website: "◎", booking: "▣", crm: "◇", form: "✎", contact: "✉", social: "◌",
    })[kind] || "i";
  }

  function resourceRow(label, value, info) {
    const button = element("button", "tour-ai-resource-row"); button.type = "button";
    const copy = element("span", "tour-ai-resource-row-copy"); copy.append(element("small", "", label), element("strong", "", value));
    button.append(copy, element("span", "tour-ai-resource-row-arrow", "›"));
    button.addEventListener("click", () => openResourceModal(info));
    return button;
  }

  function normalizeResourceInfo(raw = {}) {
    const info = raw && typeof raw === "object" ? {...raw} : {};
    info.kind = text(info.kind || "text").toLowerCase().replace(/[^a-z0-9_-]/g, "").slice(0, 32) || "text";
    info.title = cardText(info.title || info.label || "Information", 180) || "Information";
    info.value = cardText(info.value || info.url || "", 1200);
    info.url = safeResourceUrl(info.url || (info.kind === "url" || info.kind === "booking" || info.kind === "crm" || info.kind === "form" ? info.value : ""));
    info.copyValue = text(info.copyValue || info.value || info.url).trim().slice(0, 2000);
    info.embed_mode = text(info.embed_mode || "auto").toLowerCase();
    info.embed_allowed = info.embed_allowed !== false && cfg.allowEmbeddedResources !== false;
    info.native_fallback = text(info.native_fallback || (["booking", "crm"].includes(info.kind) ? "booking" : ["contact", "form"].includes(info.kind) ? "contact" : ""));
    info.sandbox_permissions = Array.isArray(info.sandbox_permissions) ? info.sandbox_permissions : [];
    return info;
  }

  function resetEmbeddedResource() {
    if (resourceFrameTimer) window.clearTimeout(resourceFrameTimer);
    resourceFrameTimer = null;
    if (resource.frame) {
      resource.frame.removeAttribute("src");
      resource.frame.onload = null;
    }
    if (resource.embed) {
      resource.embed.hidden = true;
      resource.embed.classList.remove("is-loaded");
    }
    if (resource.body) resource.body.hidden = false;
    if (resource.embedStatus) resource.embedStatus.textContent = "Preparing secure preview…";
  }

  function resourceSandbox(info) {
    const allowed = new Set(["allow-forms", "allow-scripts", "allow-same-origin", "allow-downloads", "allow-popups", "allow-popups-to-escape-sandbox"]);
    const requested = info.sandbox_permissions.filter((value) => allowed.has(value));
    const defaults = ["allow-forms", "allow-scripts", "allow-same-origin", "allow-popups-to-escape-sandbox"];
    return [...new Set(requested.length ? requested : defaults)].join(" ");
  }

  function openEmbeddedResource() {
    const info = normalizeResourceInfo(activeResource || {});
    if (!resource.frame || !resource.embed || !info.url || !info.embed_allowed) return;
    resource.body.hidden = true;
    resource.embed.hidden = false;
    resource.embed.classList.remove("is-loaded");
    resource.embedStatus.textContent = "Loading the verified provider…";
    resource.frame.setAttribute("sandbox", resourceSandbox(info));
    resource.frame.setAttribute("allow", "payment 'none'; geolocation 'none'; camera 'none'; microphone 'none'; clipboard-write 'self'");
    resource.frame.onload = () => {
      if (resourceFrameTimer) window.clearTimeout(resourceFrameTimer);
      resourceFrameTimer = null;
      resource.embedStatus.textContent = "Connected provider preview";
      resource.embed.classList.add("is-loaded");
    };
    resource.frame.src = info.url;
    resourceFrameTimer = window.setTimeout(() => {
      if (resource.embedStatus) {
        resource.embedStatus.textContent = "This provider may block embedded views. Use the open icon in the header to continue in full size.";
      }
    }, Math.max(2500, Number(cfg.externalEmbedTimeoutMs || 7000)));
    sendSignal("ai_resource_embedded", {kind: info.kind, resource_id: info.resource_id || ""});
  }


  function renderResourceBody(info) {
    clear(resource.body);
    if (info.kind === "contact_collection") {
      const intro = element("p", "tour-ai-resource-intro", "Select a verified contact detail.");
      resource.body.appendChild(intro);
      const rows = element("div", "tour-ai-resource-list");
      contactItems(info.contact || {}).forEach((item) => rows.appendChild(resourceRow(item.label, item.value, {...item, title: item.label, copyValue: item.value})));
      resource.body.appendChild(rows);
      if (!rows.children.length) resource.body.appendChild(element("div", "tour-ai-resource-empty", "No public contact details are currently available."));
      return;
    }

    if (info.kind === "source") {
      const trust = element("div", "tour-ai-resource-trust"); trust.append(element("span", "", "✓"), element("strong", "", info.citation ? `${info.citation} · Verified source` : "Verified source"));
      resource.body.appendChild(trust);
      if (info.summary) { const summary = element("p", "tour-ai-resource-summary"); summary.textContent = info.summary; resource.body.appendChild(summary); }
      if (info.source) resource.body.appendChild(resourceRow("Source", info.source, {kind: "text", title: "Source", value: info.source, copyValue: info.source}));
      if (info.url) resource.body.appendChild(resourceRow("Web address", info.url, {kind: "url", title: info.title || "Web address", url: info.url, value: info.url, copyValue: info.url, embed_mode: "auto", embed_allowed: true}));
      return;
    }

    const value = info.value || info.url || "";
    const panel = element("div", "tour-ai-resource-value-card");
    const webKinds = ["url", "website", "booking", "crm", "form", "contact", "social"];
    const kindLabel = info.kind === "phone" ? "PUBLIC PHONE"
      : info.kind === "email" ? "PUBLIC EMAIL"
      : info.kind === "booking" ? "VERIFIED BOOKING RESOURCE"
      : info.kind === "crm" ? "CONNECTED CLIENT PORTAL"
      : info.kind === "form" || info.kind === "contact" ? "VERIFIED FORM"
      : webKinds.includes(info.kind) ? "CONNECTED WEB ADDRESS"
      : "INFORMATION";
    panel.append(element("small", "", kindLabel), element("strong", "", value));
    resource.body.appendChild(panel);
    if (webKinds.includes(info.kind)) {
      let host = "Official connected source";
      try { host = new URL(info.url).hostname.replace(/^www\./, ""); } catch (_) {}
      resource.body.appendChild(element("p", "tour-ai-resource-note", `This address belongs to ${host}. It is displayed here without sending you away from the virtual tour.`));
    } else if (info.kind === "phone" || info.kind === "email") {
      resource.body.appendChild(element("p", "tour-ai-resource-note", "This public contact detail is displayed securely. Use the action icon in the header to continue."));
    }
  }

  function portalizeResourceModal() {
    if (resource.modal?.dataset.portalized === "1") return;
    document.body.append(resource.backdrop, resource.modal);
    resource.modal.dataset.portalized = "1";
  }

  function openResourceModal(rawInfo = {}) {
    if (!resource.modal || !resource.backdrop || !resource.body) {
      reportTechnicalError("AI-RESOURCE-UI", new Error("Resource modal is unavailable"), {tourId: cfg.tourId});
      return;
    }
    const info = normalizeResourceInfo(rawInfo);
    try {
      portalizeResourceModal();
      resetEmbeddedResource();
      activeResource = info;
      resourcePreviousFocus = document.activeElement;
      resource.icon.textContent = iconForResource(info.kind);
      resource.eyebrow.textContent = info.eyebrow || (info.kind === "source" ? "Verified source" : info.kind === "contact_collection" ? "Organization contact" : "Verified information");
      resource.title.textContent = info.title;
      renderResourceBody(info);

      let externalUrl = info.url || "";
      if (!externalUrl && info.kind === "phone" && info.value) externalUrl = `tel:${info.value}`;
      if (!externalUrl && info.kind === "email" && info.value) externalUrl = `mailto:${info.value}`;
      if (resource.external) {
        if (externalUrl) {
          resource.external.href = externalUrl;
          resource.external.hidden = false;
          resource.external.textContent = info.kind === "phone" ? "☎" : info.kind === "email" ? "@" : "↗";
          resource.external.setAttribute("aria-label", info.kind === "phone" ? "Call" : info.kind === "email" ? "Send email" : "Open in full size");
          resource.external.setAttribute("title", info.kind === "phone" ? "Call" : info.kind === "email" ? "Send email" : "Open in full size");
        } else {
          resource.external.hidden = true;
          resource.external.removeAttribute("href");
        }
      }

      const previewable = Boolean(
        info.url &&
        /^https?:/i.test(info.url) &&
        info.embed_allowed &&
        !["summary", "native_booking", "native_contact"].includes(info.embed_mode)
      );

      resource.backdrop.hidden = false;
      resource.modal.hidden = false;
      document.documentElement.classList.add("tour-ai-resource-open");
      requestAnimationFrame(() => {
        resource.backdrop.classList.add("is-open");
        resource.modal.classList.add("is-open");
        resource.modal.querySelector("[data-resource-close]")?.focus();
        if (previewable) requestAnimationFrame(openEmbeddedResource);
      });
      sendSignal("ai_resource_opened", {kind: info.kind || "information", citation: info.citation || "", resource_id: info.resource_id || ""});
    } catch (error) {
      const reference = reportTechnicalError("AI-RESOURCE", error, {tourId: cfg.tourId, kind: info.kind, citation: info.citation || ""});
      resetEmbeddedResource();
      clear(resource.body);
      resource.body.appendChild(element("div", "tour-ai-resource-empty", `This information could not be displayed. Reference: ${reference}`));
      if (resource.external) {
        resource.external.hidden = true;
        resource.external.removeAttribute("href");
      }
      resource.backdrop.hidden = false;
      resource.modal.hidden = false;
      document.documentElement.classList.add("tour-ai-resource-open");
      requestAnimationFrame(() => { resource.backdrop.classList.add("is-open"); resource.modal.classList.add("is-open"); });
    }
  }

  function closeResourceModal() {
    if (!resource.modal || resource.modal.hidden) return;
    resetEmbeddedResource();
    resource.backdrop.classList.remove("is-open"); resource.modal.classList.remove("is-open");
    document.documentElement.classList.remove("tour-ai-resource-open");
    window.setTimeout(() => { resource.backdrop.hidden = true; resource.modal.hidden = true; }, 170);
    if (resource.external) {
      resource.external.hidden = true;
      resource.external.removeAttribute("href");
    }
    const focusTarget = resourcePreviousFocus; activeResource = null; resourcePreviousFocus = null;
    if (focusTarget?.focus && isOpen()) window.setTimeout(() => focusTarget.focus({preventScroll: true}), 180);
  }


  async function showContactInformation() {
    try {
      await bootstrap();
      const data = await post(cfg.actionUrl, payload({action_type: "contact_business", payload: {}}));
      openResourceModal({kind: "contact_collection", title: data.contact?.organization_name || "Contact information", contact: data.contact || {}});
    } catch (error) {
      reportTechnicalError("AI-CONTACT", error, {tourId: cfg.tourId});
      addMessage(friendlyRequestFailure(), "assistant", {degraded: true, provider: "local"});
    }
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
    const assistantLabel = text(cfg.assistantName || "Assistant");
    const avatarLabel = assistantLabel.trim().slice(0, 2).toUpperCase() || "•";
    box.innerHTML = `<div class="tour-ai-thinking-head"><span class="tour-ai-avatar">${avatarLabel}</span><div><strong>${localeIsFrench() ? `${assistantLabel} prépare votre réponse` : `${assistantLabel} is preparing your answer`}</strong><small data-thinking-label>${localeIsFrench() ? "Un instant…" : "Just a moment…"}</small></div></div><div class="tour-ai-dots" aria-hidden="true"><i></i><i></i><i></i></div><div class="tour-ai-thinking-steps" data-thinking-steps></div>`;
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

  async function sendSignal(signalType, data = {}) {
    if (!bootstrapped && signalType !== "ai_agent_opened") return;
    try { await post(cfg.signalUrl, payload({signal_type: signalType, payload: data})); } catch (_) {}
  }

  async function openPanel() {
    if (isOpen) return;
    isOpen = true;
    panel.hidden = false;
    root.classList.add("is-open");
    nudge.hidden = true;
    launcher.setAttribute("aria-expanded", "true");
    updateMobileOffset();
    try {
      await bootstrap();
    } catch (error) {
      reportTechnicalError("AI-START", error, {tourId: cfg.tourId, sceneId: currentSceneId});
      if (!messages.children.length) addMessage(friendlyRequestFailure(), "assistant", {degraded: true, provider: "local"});
    }
    if (isOpen) {
      try { input?.focus?.({preventScroll: true}); } catch (_) { input?.focus?.(); }
      sendSignal("ai_agent_opened");
    }
  }

  function closePanel() {
    isOpen = false;
    try { input?.blur?.(); } catch (_) {}
    activeMessageController?.abort();
    activeMessageController = null;
    stopActiveThinking?.();
    stopActiveThinking = null;
    closeVision();
    if (resource.modal && !resource.modal.hidden) closeResourceModal();
    panel.hidden = true;
    root.classList.remove("is-open", "is-busy");
    launcher.setAttribute("aria-expanded", "false");
    setBusy(false);
    window.setTimeout(() => window.dispatchEvent(new Event("resize")), 190);
  }

  async function sendMessage(value, options = {}) {
    const clean = text(value).trim(); if (!clean || busy) return;
    await bootstrap().catch(() => {});
    addMessage(options.displayText || clean, "user"); input.value = ""; setBusy(true);
    const thinking = createThinkingIndicator();
    const stopThinking = animateThinking(thinking);
    stopActiveThinking = stopThinking;
    activeMessageController?.abort();
    const controller = new AbortController();
    activeMessageController = controller;
    try {
      const requestId = crypto?.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
      const data = await post(cfg.messageUrl, payload({
        message: clean,
        request_id: requestId,
        vision_insight_id: options.visionInsightId || undefined,
      }), controller.signal);
      conversationId = data.conversation_id || conversationId;
      stopThinking();
      stopActiveThinking = null;
      renderReasoningSummary(thinking, data.reasoning_steps || []);
      await new Promise((resolve) => setTimeout(resolve, 220));
      thinking.remove();
      if (isOpen) {
        addMessage(data.text || "I’m here to help.", "assistant", data);
        addProductCards(data.products || []);
      }
    } catch (error) {
      stopThinking();
      stopActiveThinking = null;
      thinking.remove();
      if (error?.name !== "AbortError" && isOpen) {
        reportTechnicalError("AI-MSG", error, {tourId: cfg.tourId, sceneId: currentSceneId});
        addMessage(friendlyRequestFailure(), "assistant", {degraded: true, provider: "local"});
      }
    } finally {
      if (activeMessageController === controller) activeMessageController = null;
      setBusy(false);
      if (isOpen && !panel.hidden) {
        try { input?.focus?.({preventScroll: true}); } catch (_) { input?.focus?.(); }
      }
    }
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
      const maxAttempts = 10;
      for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
        const data = await post(cfg.inspectUrl, requestPayload, controller.signal);
        renderVision(data);
        if (data.status !== "analyzing") return;
        const serverWait = Number(data.retry_after_ms || 2200);
        const waitMs = Math.max(1200, Math.min(serverWait + attempt * 700, 9000));
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
  root.querySelector("[data-ai-contact]")?.addEventListener("click", showContactInformation);
  resource.closeButtons?.forEach((button) => button.addEventListener("click", closeResourceModal));
  resource.backdrop?.addEventListener("click", closeResourceModal);
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
    currentSceneId = String(sceneId);
    closeVision();
    if (sceneSignalTimer) window.clearTimeout(sceneSignalTimer);
    sceneSignalTimer = window.setTimeout(() => {
      sceneSignalTimer = null;
      sendSignal("scene_changed", {scene_title: title});
    }, 1200);
  }
  document.addEventListener("click", (event) => { const trigger = event.target.closest("[data-scene-id]"); if (trigger) updateScene(trigger.dataset.sceneId, trigger.dataset.sceneTitle || trigger.textContent.trim()); }, true);
  window.addEventListener("twinscopes:scene-changed", (event) => updateScene(event.detail?.sceneId, event.detail?.title || ""));
  window.addEventListener("twinscopes:vision-long-press", (event) => inspectPoint(event.detail));
  window.addEventListener("resize", updateMobileOffset, {passive: true});
  window.addEventListener("orientationchange", () => setTimeout(updateMobileOffset, 250), {passive: true});
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (resource.modal && !resource.modal.hidden) closeResourceModal();
    else if (!vision.sheet.hidden) closeVision();
    else if (isOpen) closePanel();
  });

  window.TwinscopesAgent = {
    open: openPanel, close: closePanel,
    setScene: ({sceneId, sceneTitle}) => updateScene(sceneId, sceneTitle),
    inspectPoint, signal: sendSignal,
    action: (actionType, actionPayload = {}) => post(cfg.actionUrl, payload({action_type: actionType, payload: actionPayload})),
  };

  updateMobileOffset();
  window.addEventListener("pagehide", () => {
    activeMessageController?.abort();
    insightRequest?.abort();
    stopActiveThinking?.();
    if (sceneSignalTimer) window.clearTimeout(sceneSignalTimer);
    sceneSignalTimer = null;
  }, {once: true});
})();
