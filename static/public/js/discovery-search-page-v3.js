(() => {
  const root = document.querySelector("[data-discovery-search-page]");
  if (!root) return;

  const form = root.querySelector("[data-discovery-form]");
  const queryInput = root.querySelector("[data-discovery-query]");
  const cityInput = root.querySelector("[data-discovery-city]");
  const locateButton = root.querySelector("[data-discovery-locate]");
  const locateLabel = root.querySelector("[data-locate-label]");
  const clearButton = root.querySelector("[data-discovery-clear]");
  const submitButton = root.querySelector("[data-discovery-submit]");
  const submitLabel = root.querySelector("[data-discovery-submit-label]");
  const status = root.querySelector("[data-discovery-status]");
  const suggestions = root.querySelector("[data-discovery-suggestions]");
  const resultsRoot = root.querySelector("[data-discovery-results]");
  const backButton = root.querySelector("[data-search-back]");
  const themeButton = root.querySelector("[data-search-theme-toggle]");
  const endpoint = root.dataset.searchUrl || "/api/public/discovery/search/";
  const appointmentEndpoint = root.dataset.appointmentUrl || "/api/public/discovery/healthcare/appointments/";
  const homeUrl = root.dataset.homeUrl || "/";
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
  let appointmentPreviousFocus = null;

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  }[char]));

  function setTheme(theme) {
    const value = theme === "dark" ? "dark" : "light";
    document.documentElement.dataset.marketTheme = value;
    document.documentElement.style.colorScheme = value;
    try {
      localStorage.setItem("twinscopes-market-theme", value);
      localStorage.setItem("twinscopesTheme", value);
      localStorage.setItem("virtualToursTheme", value);
    } catch (_) {}
  }

  function setStatus(message, kind = "info") {
    if (!status) return;
    status.hidden = !message;
    status.textContent = message || "";
    status.dataset.kind = kind;
  }

  function showSkeletons() {
    resultsRoot.innerHTML = Array.from({ length: 6 }, () => (
      '<div class="ts-result__skeleton" aria-hidden="true"><span></span><span></span></div>'
    )).join("");
  }

  function contactUrl(item) {
    const appointment = item.appointment || {};
    if (appointment.url) return appointment.url;
    if (appointment.phone) return `tel:${String(appointment.phone).replace(/\s+/g, "")}`;
    if (appointment.email) return `mailto:${appointment.email}`;
    return item.organization?.booking_url || "";
  }

  function renderResult(item) {
    const place = item.place || {};
    const organization = item.organization || {};
    const facts = [];
    if (item.bedrooms) facts.push(`${item.bedrooms} bedrooms`);
    if (item.bathrooms) facts.push(`${item.bathrooms} bathrooms`);
    if (item.distance_km != null) facts.push(`${item.distance_km} km away`);
    if (place.category_label) facts.push(place.category_label);
    const price = item.price ? `<p class="ts-result__price">${escapeHtml(item.price)} ${escapeHtml(item.currency || "")}</p>` : "";
    const practitioners = (item.practitioners || []).slice(0, 3);
    const practitionerBlock = practitioners.length ? `
      <div class="ts-result__doctors">
        <strong>Available specialists</strong>
        ${practitioners.map((doctor) => {
          const slot = Array.isArray(doctor.availability) ? doctor.availability[0] : null;
          const availability = slot ? ` · ${escapeHtml(slot.weekday_label)} ${escapeHtml(slot.starts_at)}–${escapeHtml(slot.ends_at)}` : "";
          return `<span>${escapeHtml(doctor.name)}${doctor.specialty ? ` · ${escapeHtml(doctor.specialty)}` : ""}${availability}</span>`;
        }).join("")}
      </div>` : "";
    const contact = contactUrl(item);
    return `
      <article class="ts-result">
        <div class="ts-result__image">
          ${item.cover_url ? `<img src="${escapeHtml(item.cover_url)}" alt="${escapeHtml(item.title)}" loading="lazy" decoding="async">` : ""}
          <span class="ts-result__badge">360° available</span>
        </div>
        <div class="ts-result__body">
          <p class="ts-result__org">${escapeHtml(organization.name || "Twinscopes")}</p>
          <h2>${escapeHtml(item.title)}</h2>
          <p class="ts-result__location">${escapeHtml([place.address, place.city, place.country].filter(Boolean).join(", "))}</p>
          ${price}
          <div class="ts-result__facts">${facts.map((fact) => `<span>${escapeHtml(fact)}</span>`).join("")}</div>
          <div class="ts-result__reasons">${(item.reasons || []).map((reason) => `<span>${escapeHtml(reason)}</span>`).join("")}</div>
          ${practitionerBlock}
          <div class="ts-result__actions">
            <a class="ts-result__visit" href="${escapeHtml(item.preview_url)}">Open virtual tour</a>
            ${item.appointment?.available
              ? `<button type="button" class="ts-result__contact" data-appointment-tour="${escapeHtml(item.tour_id)}">Request appointment</button>`
              : (contact ? `<a class="ts-result__contact" href="${escapeHtml(contact)}" ${contact.startsWith("http") ? 'target="_blank" rel="noopener"' : ""}>Contact / book</a>` : "")}
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
      resultsRoot.innerHTML = `<div class="ts-result__empty"><strong>No matching tour found</strong>${escapeHtml(data.message || "Try a broader search, another city or fewer filters.")}</div>`;
      return;
    }
    resultsRoot.innerHTML = items.map(renderResult).join("");
  }

  function updateAddressBar(query, city) {
    const url = new URL(window.location.href);
    if (query) url.searchParams.set("q", query); else url.searchParams.delete("q");
    if (city) url.searchParams.set("city", city); else url.searchParams.delete("city");
    window.history.replaceState({}, "", url);
  }

  async function search({ committed = false } = {}) {
    const query = queryInput.value.trim();
    const city = cityInput.value.trim();
    clearButton.hidden = !query;
    if (query.length < 2) {
      controller?.abort();
      lastQueryKey = "";
      setStatus("");
      resultsRoot.innerHTML = "";
      suggestions.hidden = false;
      updateAddressBar(query, city);
      return;
    }

    const key = `${query.toLowerCase()}|${city.toLowerCase()}|${coordinates?.latitude || ""}|${coordinates?.longitude || ""}`;
    if (!committed && key === lastQueryKey) return;
    lastQueryKey = key;
    controller?.abort();
    controller = new AbortController();
    submitButton.disabled = true;
    submitLabel.textContent = "Searching…";
    setStatus("Searching available virtual tours…");
    showSkeletons();
    updateAddressBar(query, city);

    const url = new URL(endpoint, window.location.origin);
    url.searchParams.set("q", query);
    url.searchParams.set("limit", "18");
    url.searchParams.set("live", committed ? "0" : "1");
    if (city) url.searchParams.set("city", city);
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
      resultsRoot.innerHTML = '<div class="ts-result__empty"><strong>Search is temporarily unavailable</strong>Please try again in a moment.</div>';
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
    document.documentElement.classList.remove("ts-appointment-open");
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
    document.documentElement.classList.add("ts-appointment-open");
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
    } catch (_) {
      setAppointmentStatus(publicMessage, "error");
    } finally {
      appointmentSubmit.disabled = false;
      appointmentSubmit.textContent = "Send request";
    }
  }

  backButton?.addEventListener("click", () => {
    if (window.history.length > 1 && document.referrer && new URL(document.referrer).origin === window.location.origin) {
      window.history.back();
    } else {
      window.location.assign(homeUrl);
    }
  });
  themeButton?.addEventListener("click", () => setTheme(document.documentElement.dataset.marketTheme === "dark" ? "light" : "dark"));
  form?.addEventListener("submit", (event) => { event.preventDefault(); search({ committed: true }); });
  queryInput?.addEventListener("input", scheduleSearch);
  cityInput?.addEventListener("input", scheduleSearch);
  clearButton?.addEventListener("click", () => {
    queryInput.value = "";
    clearButton.hidden = true;
    lastQueryKey = "";
    resultsRoot.innerHTML = "";
    setStatus("");
    suggestions.hidden = false;
    updateAddressBar("", cityInput.value.trim());
    queryInput.focus();
  });
  root.querySelectorAll("[data-discovery-example]").forEach((button) => button.addEventListener("click", () => {
    queryInput.value = button.dataset.discoveryExample || "";
    queryInput.focus();
    search({ committed: true });
  }));
  resultsRoot?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-appointment-tour]");
    if (button) openAppointment(resultCache.get(String(button.dataset.appointmentTour || "")));
  });
  appointmentForm?.addEventListener("submit", submitAppointment);
  root.querySelectorAll("[data-appointment-close]").forEach((button) => button.addEventListener("click", closeAppointment));
  locateButton?.addEventListener("click", () => {
    if (!navigator.geolocation) {
      setStatus("Location is not available on this device.", "error");
      return;
    }
    locateButton.disabled = true;
    locateLabel.textContent = "Locating…";
    navigator.geolocation.getCurrentPosition(
      (position) => {
        coordinates = { latitude: position.coords.latitude, longitude: position.coords.longitude };
        locateLabel.textContent = "Location added ✓";
        locateButton.disabled = false;
        setStatus("Your location is used only to rank nearby results.");
        if (queryInput.value.trim().length >= 2) search({ committed: true });
      },
      () => {
        locateLabel.textContent = "Use my location";
        locateButton.disabled = false;
        setStatus("We could not access your location. You can enter a city instead.", "error");
      },
      { enableHighAccuracy: false, timeout: 9000, maximumAge: 300000 },
    );
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && appointmentModal && !appointmentModal.hidden) closeAppointment();
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      queryInput.focus();
    }
  });

  clearButton.hidden = !queryInput.value.trim();
  if (queryInput.value.trim().length >= 2) search({ committed: false });
})();
