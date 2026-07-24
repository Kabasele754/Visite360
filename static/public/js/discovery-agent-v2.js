(() => {
  const root = document.querySelector("[data-discovery-agent]");
  if (!root) return;

  const launcherForm = root.querySelector("[data-discovery-launcher-form]");
  const launcherInput = root.querySelector("[data-discovery-launcher-input]");
  const modal = root.querySelector("[data-discovery-search]");
  const form = root.querySelector("[data-discovery-form]");
  const queryInput = root.querySelector("[data-discovery-query]");
  const cityInput = root.querySelector("[data-discovery-city]");
  const locateButton = root.querySelector("[data-discovery-locate]");
  const clearButton = root.querySelector("[data-discovery-clear]");
  const submitButton = root.querySelector("[data-discovery-submit]");
  const submitLabel = root.querySelector("[data-discovery-submit-label]");
  const status = root.querySelector("[data-discovery-status]");
  const suggestions = root.querySelector("[data-discovery-suggestions]");
  const resultsRoot = root.querySelector("[data-discovery-results]");
  const endpoint = root.dataset.searchUrl || "/api/public/discovery/search/";
  const appointmentEndpoint = root.dataset.appointmentUrl || "/api/public/discovery/healthcare/appointments/";
  const appointmentModal = root.querySelector("[data-discovery-appointment]");
  const appointmentForm = root.querySelector("[data-appointment-form]");
  const appointmentTitle = root.querySelector("[data-appointment-title]");
  const appointmentDescription = root.querySelector("[data-appointment-description]");
  const appointmentSpecialty = root.querySelector("[data-appointment-specialty]");
  const appointmentPractitioner = root.querySelector("[data-appointment-practitioner]");
  const appointmentStatus = root.querySelector("[data-appointment-status]");
  const appointmentSubmit = root.querySelector("[data-appointment-submit]");
  const csrfToken = root.querySelector('input[name="csrfmiddlewaretoken"]')?.value || "";

  const resultCache = new Map();
  let coordinates = null;
  let controller = null;
  let debounceTimer = null;
  let lastQueryKey = "";
  let previousFocus = null;
  let appointmentPreviousFocus = null;

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  }[char]));

  function setStatus(message, kind = "info") {
    if (!status) return;
    status.hidden = !message;
    status.textContent = message || "";
    status.dataset.kind = kind;
  }

  function openSearch(seed = "") {
    if (!modal) return;
    previousFocus = document.activeElement;
    modal.hidden = false;
    modal.setAttribute("aria-hidden", "false");
    document.documentElement.classList.add("discovery-search-open");
    if (seed) {
      queryInput.value = seed;
      launcherInput.value = seed;
    }
    clearButton.hidden = !queryInput.value;
    requestAnimationFrame(() => {
      queryInput.focus({ preventScroll: true });
      queryInput.setSelectionRange(queryInput.value.length, queryInput.value.length);
    });
  }

  function closeSearch() {
    if (!modal) return;
    controller?.abort();
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
    document.documentElement.classList.remove("discovery-search-open");
    previousFocus?.focus?.({ preventScroll: true });
  }

  function contactUrl(item) {
    const appointment = item.appointment || {};
    if (appointment.url) return appointment.url;
    if (appointment.phone) return `tel:${appointment.phone.replace(/\s+/g, "")}`;
    if (appointment.email) return `mailto:${appointment.email}`;
    return item.organization?.booking_url || "";
  }

  function renderResult(item) {
    const place = item.place || {};
    const organization = item.organization || {};
    const facts = [];
    if (item.bedrooms) facts.push(`${item.bedrooms} bedrooms`);
    if (item.bathrooms) facts.push(`${item.bathrooms} bathrooms`);
    if (item.distance_km != null) facts.push(`${item.distance_km} km`);
    if (place.category_label) facts.push(place.category_label);
    const price = item.price ? `<p class="discovery-result__price">${escapeHtml(item.price)} ${escapeHtml(item.currency || "")}</p>` : "";
    const practitioners = (item.practitioners || []).slice(0, 3);
    const practitionerBlock = practitioners.length ? `
      <div class="discovery-result__practitioners">
        <strong>Available specialists</strong>
        ${practitioners.map((doctor) => {
          const slot = Array.isArray(doctor.availability) ? doctor.availability[0] : null;
          const availability = slot ? ` · ${escapeHtml(slot.weekday_label)} ${escapeHtml(slot.starts_at)}–${escapeHtml(slot.ends_at)}` : "";
          return `<span>${escapeHtml(doctor.name)}${doctor.specialty ? ` · ${escapeHtml(doctor.specialty)}` : ""}${availability}</span>`;
        }).join("")}
      </div>` : "";
    const contact = contactUrl(item);
    return `
      <article class="discovery-result">
        <div class="discovery-result__image">
          ${item.cover_url ? `<img src="${escapeHtml(item.cover_url)}" alt="${escapeHtml(item.title)}" loading="lazy" decoding="async">` : ""}
          <span class="discovery-result__badge">360° available</span>
        </div>
        <div class="discovery-result__body">
          <p class="discovery-result__org">${escapeHtml(organization.name || "Twinscopes")}</p>
          <h3>${escapeHtml(item.title)}</h3>
          <p class="discovery-result__location">${escapeHtml([place.address, place.city, place.country].filter(Boolean).join(", "))}</p>
          ${price}
          <div class="discovery-result__facts">${facts.map((fact) => `<span>${escapeHtml(fact)}</span>`).join("")}</div>
          <div class="discovery-result__reasons">${(item.reasons || []).map((reason) => `<span>${escapeHtml(reason)}</span>`).join("")}</div>
          ${practitionerBlock}
          <div class="discovery-result__actions">
            <a class="discovery-result__visit" href="${escapeHtml(item.preview_url)}">Open virtual tour</a>
            ${item.appointment?.available ? `<button type="button" class="discovery-result__contact" data-appointment-tour="${escapeHtml(item.tour_id)}">Request appointment</button>` : (contact ? `<a class="discovery-result__contact" href="${escapeHtml(contact)}" ${contact.startsWith("http") ? 'target="_blank" rel="noopener"' : ""}>Contact / book</a>` : "")}
          </div>
        </div>
      </article>`;
  }

  function renderResults(data) {
    const items = Array.isArray(data.results) ? data.results : [];
    resultCache.clear();
    items.forEach((item) => resultCache.set(String(item.tour_id), item));
    suggestions.hidden = Boolean(queryInput.value.trim());
    if (!items.length) {
      resultsRoot.innerHTML = `<div class="discovery-result__empty">${escapeHtml(data.message || "No exact match was found. Try a broader search.")}</div>`;
      return;
    }
    resultsRoot.innerHTML = items.map(renderResult).join("");
  }

  async function search({ immediate = false } = {}) {
    const query = queryInput.value.trim();
    launcherInput.value = query;
    clearButton.hidden = !query;
    if (query.length < 2) {
      controller?.abort();
      lastQueryKey = "";
      setStatus("");
      resultsRoot.innerHTML = "";
      suggestions.hidden = false;
      return;
    }

    const key = `${query.toLowerCase()}|${cityInput.value.trim().toLowerCase()}|${coordinates?.latitude || ""}|${coordinates?.longitude || ""}`;
    if (!immediate && key === lastQueryKey) return;
    lastQueryKey = key;
    controller?.abort();
    controller = new AbortController();
    submitButton.disabled = true;
    submitLabel.textContent = "Searching…";
    setStatus("Searching available virtual tours…");

    const url = new URL(endpoint, window.location.origin);
    url.searchParams.set("q", query);
    url.searchParams.set("limit", "18");
    url.searchParams.set("live", immediate ? "0" : "1");
    if (cityInput.value.trim()) url.searchParams.set("city", cityInput.value.trim());
    if (coordinates) {
      url.searchParams.set("latitude", String(coordinates.latitude));
      url.searchParams.set("longitude", String(coordinates.longitude));
    }

    try {
      const response = await fetch(url, {
        headers: { Accept: "application/json" },
        signal: controller.signal,
        credentials: "same-origin",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error("search_failed");
      setStatus(`${data.count || 0} matching virtual tour${Number(data.count) === 1 ? "" : "s"}`, "success");
      renderResults(data);
    } catch (error) {
      if (error.name === "AbortError") return;
      console.error("[Twinscopes search]", error);
      setStatus("Search is temporarily unavailable. Please try again shortly.", "error");
    } finally {
      submitButton.disabled = false;
      submitLabel.textContent = "Search";
    }
  }

  function scheduleSearch() {
    window.clearTimeout(debounceTimer);
    debounceTimer = window.setTimeout(() => search(), 360);
  }

  function setAppointmentStatus(message, kind = "info") {
    if (!appointmentStatus) return;
    appointmentStatus.hidden = !message;
    appointmentStatus.textContent = message || "";
    appointmentStatus.dataset.kind = kind;
  }

  function closeAppointment() {
    if (!appointmentModal) return;
    appointmentModal.hidden = true;
    appointmentModal.setAttribute("aria-hidden", "true");
    document.documentElement.classList.remove("discovery-appointment-open");
    appointmentPreviousFocus?.focus?.({ preventScroll: true });
  }

  function openAppointment(item) {
    if (!appointmentModal || !appointmentForm || !item) return;
    appointmentPreviousFocus = document.activeElement;
    appointmentForm.reset();
    appointmentForm.querySelectorAll("input, textarea, select").forEach((field) => { field.disabled = false; });
    appointmentSubmit.hidden = false;
    setAppointmentStatus("");
    appointmentForm.elements.organization_slug.value = item.organization?.slug || "";
    appointmentForm.elements.tour_id.value = item.tour_id || "";
    appointmentTitle.textContent = `Appointment — ${item.organization?.name || item.title}`;
    appointmentDescription.textContent = "Choose a doctor when available. The facility will confirm the date and time.";
    const specialties = Array.isArray(item.specialties) ? item.specialties : [];
    appointmentSpecialty.innerHTML = '<option value="">All specialties</option>' + specialties.map((specialty) => `<option value="${escapeHtml(specialty.id)}">${escapeHtml(specialty.name)}</option>`).join("");
    const doctors = Array.isArray(item.practitioners) ? item.practitioners : [];
    appointmentPractitioner.innerHTML = '<option value="">First available specialist</option>' + doctors.map((doctor) => `<option value="${escapeHtml(doctor.id)}">${escapeHtml(doctor.name)}${doctor.specialty ? ` — ${escapeHtml(doctor.specialty)}` : ""}</option>`).join("");
    const dateInput = appointmentForm.elements.preferred_date;
    if (dateInput) dateInput.min = new Date().toISOString().slice(0, 10);
    appointmentModal.hidden = false;
    appointmentModal.setAttribute("aria-hidden", "false");
    document.documentElement.classList.add("discovery-appointment-open");
    requestAnimationFrame(() => appointmentForm.elements.full_name?.focus?.());
  }

  async function submitAppointment(event) {
    event.preventDefault();
    if (!appointmentForm || !appointmentSubmit) return;
    const payload = Object.fromEntries(new FormData(appointmentForm).entries());
    appointmentSubmit.disabled = true;
    appointmentSubmit.textContent = "Sending…";
    setAppointmentStatus("Securely saving your request…");
    let publicMessage = "The request could not be sent. Check the information and try again.";
    try {
      const response = await fetch(appointmentEndpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        if (typeof data.message === "string" && data.message.trim()) publicMessage = data.message.trim();
        throw new Error("appointment_failed");
      }
      setAppointmentStatus(data.message || "Your request was sent.", "success");
      appointmentForm.querySelectorAll("input:not([type=hidden]), textarea, select").forEach((field) => { field.disabled = true; });
      appointmentSubmit.hidden = true;
    } catch (error) {
      console.error("[Twinscopes appointment]", error);
      setAppointmentStatus(publicMessage, "error");
    } finally {
      appointmentSubmit.disabled = false;
      appointmentSubmit.textContent = "Send request";
    }
  }

  launcherForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    openSearch(launcherInput.value.trim());
    if (launcherInput.value.trim().length >= 2) search({ immediate: true });
  });
  launcherInput?.addEventListener("focus", () => openSearch(launcherInput.value.trim()));
  form?.addEventListener("submit", (event) => { event.preventDefault(); search({ immediate: true }); });
  queryInput?.addEventListener("input", () => {
    launcherInput.value = queryInput.value;
    clearButton.hidden = !queryInput.value;
    scheduleSearch();
  });
  cityInput?.addEventListener("input", scheduleSearch);
  clearButton?.addEventListener("click", () => {
    queryInput.value = "";
    launcherInput.value = "";
    clearButton.hidden = true;
    lastQueryKey = "";
    resultsRoot.innerHTML = "";
    setStatus("");
    suggestions.hidden = false;
    queryInput.focus();
  });
  root.querySelectorAll("[data-discovery-close]").forEach((button) => button.addEventListener("click", closeSearch));
  root.querySelectorAll("[data-discovery-example]").forEach((button) => button.addEventListener("click", () => {
    openSearch(button.dataset.discoveryExample || "");
    search({ immediate: true });
  }));
  appointmentForm?.addEventListener("submit", submitAppointment);
  root.querySelectorAll("[data-appointment-close]").forEach((button) => button.addEventListener("click", closeAppointment));
  resultsRoot?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-appointment-tour]");
    if (button) openAppointment(resultCache.get(String(button.dataset.appointmentTour || "")));
  });
  document.addEventListener("keydown", (event) => {
    const shortcut = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k";
    if (shortcut) {
      event.preventDefault();
      openSearch(launcherInput.value.trim());
      return;
    }
    if (event.key === "Escape") {
      if (appointmentModal && !appointmentModal.hidden) closeAppointment();
      else if (modal && !modal.hidden) closeSearch();
    }
  });
  locateButton?.addEventListener("click", () => {
    if (!navigator.geolocation) {
      setStatus("Location is not available on this device.", "error");
      return;
    }
    locateButton.disabled = true;
    locateButton.textContent = "Locating…";
    navigator.geolocation.getCurrentPosition(
      (position) => {
        coordinates = { latitude: position.coords.latitude, longitude: position.coords.longitude };
        locateButton.textContent = "Location added ✓";
        locateButton.disabled = false;
        setStatus("Your location is used only to rank nearby results.");
        if (queryInput.value.trim().length >= 2) search({ immediate: true });
      },
      () => {
        locateButton.textContent = "Use my location";
        locateButton.disabled = false;
        setStatus("We could not access your location. You can enter a city instead.", "error");
      },
      { enableHighAccuracy: false, timeout: 9000, maximumAge: 300000 },
    );
  });
})();
