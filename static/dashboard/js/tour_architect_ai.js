(() => {
  "use strict";
  const shell = document.querySelector(".ta-shell");
  if (!shell) return;
  const csrf = shell.querySelector("input[name=csrfmiddlewaretoken]")?.value || "";
  const toast = document.getElementById("architectToast");
  let pollTimer = null;

  function notify(message, error = false) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.toggle("is-error", error);
    toast.classList.add("is-visible");
    window.clearTimeout(toast._timer);
    toast._timer = window.setTimeout(() => toast.classList.remove("is-visible"), 3600);
  }

  async function postJSON(url, payload = {}) {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {"Content-Type": "application/json", "X-CSRFToken": csrf, "X-Requested-With": "XMLHttpRequest"},
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "The operation could not be completed.");
    return data;
  }

  document.querySelectorAll("[data-ta-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("[data-ta-tab]").forEach((item) => item.classList.toggle("is-active", item === button));
      document.querySelectorAll("[data-ta-panel]").forEach((panel) => panel.classList.toggle("is-active", panel.dataset.taPanel === button.dataset.taTab));
      if (button.dataset.taTab === "overview") drawGraph();
    });
  });

  const runButton = document.getElementById("runArchitectBtn");
  runButton?.addEventListener("click", async () => {
    runButton.disabled = true;
    runButton.textContent = "Preparing Gemini Architect…";
    try {
      const result = await postJSON(shell.dataset.runUrl, {force: true, mode: "auto"});
      shell.dataset.statusUrl = result.status_url;
      notify("Tour Architect started. Scene topology will update automatically.");
      startPolling(true);
    } catch (error) {
      notify(error.message, true);
      runButton.disabled = false;
      runButton.textContent = "✦ Analyze and connect scenes";
    }
  });

  document.getElementById("applySafeLinksBtn")?.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      const data = await postJSON(shell.dataset.applyUrl, {min_confidence: 0.84});
      notify(`${data.applied} navigation link(s) applied${data.conflicts ? `; ${data.conflicts} manual conflict(s) preserved` : ""}.`);
      window.setTimeout(() => window.location.reload(), 900);
    } catch (error) {
      notify(error.message, true);
      button.disabled = false;
    }
  });

  document.querySelectorAll("[data-object-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const card = button.closest(".ta-object-card");
      try {
        const data = await postJSON(button.dataset.url, {action: button.dataset.objectAction});
        card.classList.remove("is-suggested", "is-approved", "is-rejected", "is-hidden");
        card.classList.add(`is-${data.candidate.review_status}`);
        notify(data.candidate.review_status === "approved" ? "Object approved for client use." : "Object removed from client-ready information.");
      } catch (error) { notify(error.message, true); }
    });
  });

  document.querySelectorAll("[data-rerun-scene]").forEach((button) => {
    button.addEventListener("click", async () => {
      button.disabled = true;
      button.textContent = "Queued…";
      try {
        await postJSON(button.dataset.url, {});
        notify("Scene analysis queued. Object crops and quality guidance will refresh automatically.");
      } catch (error) {
        notify(error.message, true);
        button.disabled = false;
        button.textContent = "Re-run scene intelligence";
      }
    });
  });

  document.querySelectorAll("[data-link-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const card = button.closest(".ta-link-card");
      const payload = {action: button.dataset.linkAction};
      card.querySelectorAll("[data-field]").forEach((field) => {
        payload[field.dataset.field] = field.type === "checkbox" ? field.checked : field.value;
      });
      button.disabled = true;
      try {
        const data = await postJSON(card.dataset.url, payload);
        card.className = card.className.replace(/is-(suggested|approved|rejected|applied|conflict)/g, "").trim();
        card.classList.add(`is-${data.status}`);
        notify(data.status === "applied" ? "Navigation link applied without touching manual hotspots." : `Proposal ${data.status}.`);
        if (data.status === "applied") window.setTimeout(() => window.location.reload(), 700);
      } catch (error) {
        notify(error.message, true);
        button.disabled = false;
      }
    });
  });

  // Visual equirectangular editor. It lets an administrator fine-tune
  // Gemini's yaw/pitch without publishing or opening the public preview.
  const placementModal = document.getElementById("architectPlacementModal");
  const placementStage = document.getElementById("architectPlacementStage");
  const placementImage = document.getElementById("architectPlacementImage");
  const placementPin = document.getElementById("architectPlacementPin");
  const placementYaw = document.getElementById("architectPlacementYaw");
  const placementPitch = document.getElementById("architectPlacementPitch");
  let placementCard = null;
  let placementMode = "from";
  let pendingPlacement = {yaw: 0, pitch: 0};
  let placementDragging = false;

  function placementFields() {
    return placementMode === "from"
      ? {yaw: "from_yaw", pitch: "from_pitch"}
      : {yaw: "to_yaw", pitch: "to_pitch"};
  }

  function readPlacementFromCard() {
    if (!placementCard) return;
    const fields = placementFields();
    pendingPlacement.yaw = Number(placementCard.querySelector(`[data-field="${fields.yaw}"]`)?.value || 0);
    pendingPlacement.pitch = Number(placementCard.querySelector(`[data-field="${fields.pitch}"]`)?.value || 0);
    renderPlacementPin();
  }

  function renderPlacementPin() {
    if (!placementPin) return;
    const x = Math.max(0, Math.min(1, (pendingPlacement.yaw + Math.PI) / (Math.PI * 2)));
    const y = Math.max(0, Math.min(1, 0.5 - pendingPlacement.pitch / Math.PI));
    placementPin.style.left = `${x * 100}%`;
    placementPin.style.top = `${y * 100}%`;
    if (placementYaw) placementYaw.textContent = pendingPlacement.yaw.toFixed(3);
    if (placementPitch) placementPitch.textContent = pendingPlacement.pitch.toFixed(3);
  }

  function updatePlacementFromPointer(event) {
    if (!placementStage) return;
    const rect = placementStage.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (event.clientX - rect.left) / Math.max(rect.width, 1)));
    const y = Math.max(0, Math.min(1, (event.clientY - rect.top) / Math.max(rect.height, 1)));
    pendingPlacement.yaw = Math.max(-Math.PI, Math.min(Math.PI, x * Math.PI * 2 - Math.PI));
    pendingPlacement.pitch = Math.max(-1.2, Math.min(1.2, (0.5 - y) * Math.PI));
    renderPlacementPin();
  }

  function switchPlacementMode(mode) {
    placementMode = mode === "to" ? "to" : "from";
    placementModal?.querySelectorAll("[data-placement-mode]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.placementMode === placementMode);
    });
    const trigger = placementCard?.querySelector("[data-visual-editor]");
    if (placementImage && trigger) {
      placementImage.src = placementMode === "from" ? trigger.dataset.fromImage : trigger.dataset.toImage;
    }
    readPlacementFromCard();
  }

  function closePlacementModal() {
    if (!placementModal) return;
    placementModal.hidden = true;
    placementDragging = false;
  }

  document.querySelectorAll("[data-visual-editor]").forEach((button) => {
    button.addEventListener("click", () => {
      placementCard = button.closest(".ta-link-card");
      if (!placementCard || !placementModal) return;
      placementModal.hidden = false;
      switchPlacementMode("from");
    });
  });
  placementModal?.querySelectorAll("[data-placement-close]").forEach((button) => button.addEventListener("click", closePlacementModal));
  placementModal?.querySelectorAll("[data-placement-mode]").forEach((button) => {
    button.addEventListener("click", () => switchPlacementMode(button.dataset.placementMode));
  });
  placementStage?.addEventListener("pointerdown", (event) => {
    placementDragging = true;
    placementStage.setPointerCapture?.(event.pointerId);
    updatePlacementFromPointer(event);
  });
  placementStage?.addEventListener("pointermove", (event) => {
    if (placementDragging) updatePlacementFromPointer(event);
  });
  placementStage?.addEventListener("pointerup", (event) => {
    placementDragging = false;
    placementStage.releasePointerCapture?.(event.pointerId);
  });
  document.getElementById("architectPlacementSave")?.addEventListener("click", () => {
    if (!placementCard) return;
    const fields = placementFields();
    const yawInput = placementCard.querySelector(`[data-field="${fields.yaw}"]`);
    const pitchInput = placementCard.querySelector(`[data-field="${fields.pitch}"]`);
    if (yawInput) yawInput.value = pendingPlacement.yaw.toFixed(6);
    if (pitchInput) pitchInput.value = pendingPlacement.pitch.toFixed(6);
    closePlacementModal();
    notify("Visual position updated. Save the adjustment or apply the proposal when ready.");
  });
  placementModal?.addEventListener("click", (event) => {
    if (event.target === placementModal) closePlacementModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && placementModal && !placementModal.hidden) closePlacementModal();
  });

  const imageModal = document.getElementById("architectImageModal");
  document.querySelectorAll("[data-preview-image]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      imageModal.querySelector("img").src = link.href;
      imageModal.hidden = false;
    });
  });
  imageModal?.querySelector("button")?.addEventListener("click", () => { imageModal.hidden = true; });
  imageModal?.addEventListener("click", (event) => { if (event.target === imageModal) imageModal.hidden = true; });

  async function pollStatus() {
    if (!shell.dataset.statusUrl) return;
    try {
      const data = await fetch(shell.dataset.statusUrl, {credentials: "same-origin"}).then((response) => response.json());
      const run = data.run;
      document.getElementById("architectRunTitle").textContent = run.status.replaceAll("_", " ");
      document.getElementById("architectRunStage").textContent = run.stage.replaceAll("_", " ");
      document.getElementById("runSceneCount").textContent = run.scene_count;
      document.getElementById("runObjectCount").textContent = run.object_count;
      document.getElementById("runProposalCount").textContent = run.proposal_count;
      document.getElementById("runAppliedCount").textContent = run.applied_count;
      if (["review", "applied", "failed"].includes(run.status)) {
        window.clearInterval(pollTimer); pollTimer = null;
        if (run.status !== "failed") {
          notify("Gemini navigation proposals are ready for review.");
          window.setTimeout(() => window.location.reload(), 900);
        } else {
          notify("Tour Architect could not complete this run. Existing tour data was preserved.", true);
          runButton.disabled = false;
          runButton.textContent = "✦ Analyze and connect scenes";
        }
      }
    } catch (_) { /* transient polling failures remain invisible */ }
  }
  function startPolling(immediate = false) {
    window.clearInterval(pollTimer);
    if (immediate) pollStatus();
    pollTimer = window.setInterval(pollStatus, 3500);
  }
  const statusText = document.getElementById("architectRunTitle")?.textContent.toLowerCase() || "";
  if (statusText.includes("queued") || statusText.includes("running")) startPolling();

  function drawGraph() {
    const svg = document.getElementById("tourArchitectureGraph");
    const source = document.getElementById("tour-architect-graph-data");
    if (!svg || !source) return;
    let graph;
    try { graph = JSON.parse(source.textContent); } catch (_) { return; }
    const width = Math.max(640, svg.clientWidth || 900), height = Math.max(330, svg.clientHeight || 420);
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.replaceChildren();
    const nodes = graph.nodes || [], edges = graph.edges || [];
    if (!nodes.length) return;
    const centerX = width / 2, centerY = height / 2, radius = Math.min(width, height) * .34;
    const positions = new Map();
    nodes.forEach((node, index) => {
      const angle = -Math.PI / 2 + (index * Math.PI * 2 / nodes.length);
      positions.set(Number(node.id), {x: centerX + Math.cos(angle) * radius, y: centerY + Math.sin(angle) * radius});
    });
    const ns = "http://www.w3.org/2000/svg";
    edges.forEach((edge) => {
      const a = positions.get(Number(edge.from)), b = positions.get(Number(edge.to)); if (!a || !b) return;
      const line = document.createElementNS(ns, "line"); line.setAttribute("x1", a.x); line.setAttribute("y1", a.y); line.setAttribute("x2", b.x); line.setAttribute("y2", b.y);
      line.setAttribute("class", `ta-graph-edge is-${edge.status}`); svg.appendChild(line);
      const text = document.createElementNS(ns, "text"); text.setAttribute("x", (a.x+b.x)/2); text.setAttribute("y", (a.y+b.y)/2 - 5); text.setAttribute("class", "ta-graph-confidence"); text.textContent = Number(edge.confidence || 0).toFixed(2); svg.appendChild(text);
    });
    nodes.forEach((node) => {
      const point = positions.get(Number(node.id)); const group = document.createElementNS(ns, "g"); group.setAttribute("class", "ta-graph-node");
      const circle = document.createElementNS(ns, "circle"); circle.setAttribute("cx", point.x); circle.setAttribute("cy", point.y); circle.setAttribute("r", 23); group.appendChild(circle);
      const number = document.createElementNS(ns, "text"); number.setAttribute("x", point.x); number.setAttribute("y", point.y + 4); number.setAttribute("text-anchor", "middle"); number.textContent = node.order + 1; group.appendChild(number);
      const label = document.createElementNS(ns, "text"); label.setAttribute("x", point.x); label.setAttribute("y", point.y + 40); label.setAttribute("text-anchor", "middle"); label.textContent = String(node.title).slice(0, 22); group.appendChild(label); svg.appendChild(group);
    });
  }
  drawGraph();
  window.addEventListener("resize", () => window.requestAnimationFrame(drawGraph));
})();
