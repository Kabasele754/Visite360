(() => {
  const root = document.querySelector("[data-discovery-agent]");
  if (!root) return;
  const form = root.querySelector("[data-discovery-form]");
  const queryInput = root.querySelector("[data-discovery-query]");
  const cityInput = root.querySelector("[data-discovery-city]");
  const locateButton = root.querySelector("[data-discovery-locate]");
  const submitButton = root.querySelector(".discovery-agent__submit");
  const submitLabel = root.querySelector("[data-discovery-submit-label]");
  const status = root.querySelector("[data-discovery-status]");
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
  const fr = String(document.documentElement.lang || "en").toLowerCase().startsWith("fr");
  const resultCache = new Map();
  let coordinates = null;
  let controller = null;
  let appointmentPreviousFocus = null;

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  }[char]));

  function setStatus(message, kind = "info") {
    status.hidden = !message;
    status.textContent = message || "";
    status.dataset.kind = kind;
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
    if (item.bedrooms) facts.push(`${item.bedrooms} ${fr ? "chambres" : "bedrooms"}`);
    if (item.bathrooms) facts.push(`${item.bathrooms} ${fr ? "salles de bain" : "bathrooms"}`);
    if (item.distance_km != null) facts.push(`${item.distance_km} km`);
    if (place.category_label) facts.push(place.category_label);
    const price = item.price ? `<p class="discovery-result__price">${escapeHtml(item.price)} ${escapeHtml(item.currency || "")}</p>` : "";
    const practitioners = (item.practitioners || []).slice(0, 3);
    const practitionerBlock = practitioners.length ? `
      <div class="discovery-result__practitioners">
        <strong>${fr ? "Spécialistes disponibles" : "Available specialists"}</strong>
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
          <span class="discovery-result__badge">360° ${fr ? "disponible" : "available"}</span>
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
            <a class="discovery-result__visit" href="${escapeHtml(item.preview_url)}">${fr ? "Visite virtuelle" : "Virtual visit"}</a>
            ${item.appointment?.available ? `<button type="button" class="discovery-result__contact" data-appointment-tour="${escapeHtml(item.tour_id)}">${fr ? "Demander un rendez-vous" : "Request appointment"}</button>` : (contact ? `<a class="discovery-result__contact" href="${escapeHtml(contact)}" ${contact.startsWith("http") ? 'target="_blank" rel="noopener"' : ""}>${fr ? "Contacter / réserver" : "Contact / book"}</a>` : "")}
          </div>
        </div>
      </article>`;
  }

  function renderResults(data) {
    const items = Array.isArray(data.results) ? data.results : [];
    if (!items.length) {
      resultsRoot.innerHTML = `<div class="discovery-result__empty">${escapeHtml(data.message || (fr ? "Aucun résultat exact. Essayez une recherche plus large." : "No exact match. Try a broader search."))}</div>`;
      return;
    }
    resultCache.clear();
    items.forEach((item) => resultCache.set(String(item.tour_id), item));
    resultsRoot.innerHTML = items.map(renderResult).join("");
    resultsRoot.scrollIntoView({ behavior: "smooth", block: "nearest" });
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
    appointmentTitle.textContent = fr ? `Rendez-vous — ${item.organization?.name || item.title}` : `Appointment — ${item.organization?.name || item.title}`;
    appointmentDescription.textContent = fr
      ? "Choisissez un docteur si disponible. L’établissement confirmera ensuite la date et l’heure."
      : "Choose a doctor when available. The facility will confirm the date and time.";
    if (appointmentSpecialty) {
      const specialties = Array.isArray(item.specialties) ? item.specialties : [];
      appointmentSpecialty.innerHTML = `<option value="">${fr ? "Toutes les spécialités" : "All specialties"}</option>` + specialties.map((specialty) => (
        `<option value="${escapeHtml(specialty.id)}">${escapeHtml(specialty.name)}</option>`
      )).join("");
    }
    if (appointmentPractitioner) {
      const doctors = Array.isArray(item.practitioners) ? item.practitioners : [];
      appointmentPractitioner.innerHTML = `<option value="">${fr ? "Premier spécialiste disponible" : "First available specialist"}</option>` + doctors.map((doctor) => (
        `<option value="${escapeHtml(doctor.id)}">${escapeHtml(doctor.name)}${doctor.specialty ? ` — ${escapeHtml(doctor.specialty)}` : ""}</option>`
      )).join("");
    }
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
    const formData = new FormData(appointmentForm);
    const payload = Object.fromEntries(formData.entries());
    appointmentSubmit.disabled = true;
    appointmentSubmit.textContent = fr ? "Envoi…" : "Sending…";
    setAppointmentStatus(fr ? "Enregistrement sécurisé de votre demande…" : "Securely saving your request…");
    let publicErrorMessage = fr
      ? "La demande n’a pas pu être envoyée. Vérifiez les informations puis réessayez."
      : "The request could not be sent. Check the information and try again.";
    try {
      const response = await fetch(appointmentEndpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        if (typeof data.message === "string" && data.message.trim()) publicErrorMessage = data.message.trim();
        throw new Error("appointment_submit_failed");
      }
      setAppointmentStatus(data.message || (fr ? "Votre demande a bien été envoyée." : "Your request was sent."), "success");
      appointmentForm.querySelectorAll("input:not([type=hidden]), textarea, select").forEach((field) => { field.disabled = true; });
      appointmentSubmit.hidden = true;
    } catch (error) {
      console.error("[Twinscopes appointment]", error);
      setAppointmentStatus(publicErrorMessage, "error");
    } finally {
      appointmentSubmit.disabled = false;
      appointmentSubmit.textContent = fr ? "Envoyer la demande" : "Send request";
    }
  }

  async function search() {
    const query = queryInput.value.trim();
    if (!query) return;
    controller?.abort();
    controller = new AbortController();
    submitButton.disabled = true;
    submitLabel.textContent = fr ? "Recherche…" : "Searching…";
    setStatus(fr ? "Analyse de votre demande et recherche des visites disponibles…" : "Understanding your request and searching available visits…");
    const url = new URL(endpoint, window.location.origin);
    url.searchParams.set("q", query);
    if (cityInput.value.trim()) url.searchParams.set("city", cityInput.value.trim());
    if (coordinates) {
      url.searchParams.set("latitude", String(coordinates.latitude));
      url.searchParams.set("longitude", String(coordinates.longitude));
    }
    try {
      const response = await fetch(url, { headers: { Accept: "application/json" }, signal: controller.signal });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.message || `HTTP ${response.status}`);
      setStatus(`${data.count || 0} ${fr ? "résultat(s) correspondant à votre demande" : "matching result(s)"}`, "success");
      renderResults(data);
    } catch (error) {
      if (error.name === "AbortError") return;
      console.error("[Twinscopes discovery]", error);
      setStatus(fr ? "La recherche est temporairement indisponible. Réessayez dans un instant." : "Search is temporarily unavailable. Please try again shortly.", "error");
    } finally {
      submitButton.disabled = false;
      submitLabel.textContent = fr ? "Rechercher" : "Search";
    }
  }

  form?.addEventListener("submit", (event) => { event.preventDefault(); search(); });
  appointmentForm?.addEventListener("submit", submitAppointment);
  root.querySelectorAll("[data-appointment-close]").forEach((button) => button.addEventListener("click", closeAppointment));
  resultsRoot?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-appointment-tour]");
    if (!button) return;
    openAppointment(resultCache.get(String(button.dataset.appointmentTour || "")));
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && appointmentModal && !appointmentModal.hidden) closeAppointment();
  });
  root.querySelectorAll("[data-discovery-example]").forEach((button) => {
    button.addEventListener("click", () => {
      queryInput.value = button.dataset.discoveryExample || "";
      queryInput.focus();
      search();
    });
  });
  locateButton?.addEventListener("click", () => {
    if (!navigator.geolocation) {
      setStatus(fr ? "La géolocalisation n’est pas disponible sur cet appareil." : "Location is not available on this device.", "error");
      return;
    }
    locateButton.disabled = true;
    locateButton.textContent = fr ? "Localisation…" : "Locating…";
    navigator.geolocation.getCurrentPosition(
      (position) => {
        coordinates = { latitude: position.coords.latitude, longitude: position.coords.longitude };
        locateButton.textContent = fr ? "Position ajoutée ✓" : "Location added ✓";
        locateButton.disabled = false;
        setStatus(fr ? "Votre position sera utilisée uniquement pour classer les résultats proches." : "Your location will only be used to rank nearby results.");
      },
      () => {
        locateButton.textContent = fr ? "Utiliser ma position" : "Use my location";
        locateButton.disabled = false;
        setStatus(fr ? "Impossible d’obtenir votre position. Vous pouvez saisir une ville." : "We could not access your location. You can enter a city instead.", "error");
      },
      { enableHighAccuracy: false, timeout: 9000, maximumAge: 300000 },
    );
  });
})();
