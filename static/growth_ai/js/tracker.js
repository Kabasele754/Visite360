(function () {
    "use strict";

    if (window.__twinscopesGrowthTrackerLoaded) return;
    window.__twinscopesGrowthTrackerLoaded = true;

    const endpoint = "/api/growth/events/";
    const sent = new Set();

    function cleanId(value) {
        const parsed = Number.parseInt(String(value || ""), 10);
        return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
    }

    function buildPayload(eventName, data) {
        const extra = data && typeof data === "object" ? data : {};
        return {
            event_name: String(eventName || "").trim(),
            page_path: window.location.pathname + window.location.search,
            referrer: document.referrer || "",
            source: new URLSearchParams(window.location.search).get("utm_source") || "direct",
            ...extra,
            organization_id: cleanId(extra.organization_id),
            tour_id: cleanId(extra.tour_id),
            product_id: cleanId(extra.product_id),
        };
    }

    function send(eventName, data, options) {
        const payload = buildPayload(eventName, data);
        if (!payload.event_name) return;

        const settings = options || {};
        const dedupeKey = settings.dedupeKey || "";
        if (dedupeKey && sent.has(dedupeKey)) return;
        if (dedupeKey) sent.add(dedupeKey);

        const body = JSON.stringify(payload);

        if (navigator.sendBeacon && !settings.forceFetch) {
            const accepted = navigator.sendBeacon(
                endpoint,
                new Blob([body], { type: "application/json;charset=UTF-8" })
            );
            if (accepted) return;
        }

        fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json", "Accept": "application/json" },
            credentials: "same-origin",
            body,
            keepalive: true,
        }).catch(function () {});
    }

    window.TwinscopesGrowth = { track: send };

    document.addEventListener("DOMContentLoaded", function () {
        const bodyData = document.body ? document.body.dataset || {} : {};
        const base = {
            organization_id: bodyData.organizationId || null,
            tour_id: bodyData.tourId || null,
            product_id: bodyData.productId || null,
        };

        send("page_view", base, {
            dedupeKey: "page_view:" + window.location.pathname + window.location.search,
        });

        if (bodyData.growthPageEvent && bodyData.growthPageEvent !== "page_view") {
            send(bodyData.growthPageEvent, base, {
                dedupeKey: "page_event:" + bodyData.growthPageEvent + ":" + window.location.pathname,
            });
        }

        document.addEventListener("click", function (event) {
            const element = event.target.closest("[data-growth-event]");
            if (!element) return;

            send(element.dataset.growthEvent, {
                organization_id: element.dataset.organizationId || base.organization_id,
                tour_id: element.dataset.tourId || base.tour_id,
                product_id: element.dataset.productId || base.product_id,
                metadata: {
                    label: (element.getAttribute("aria-label") || element.textContent || "")
                        .trim()
                        .slice(0, 80),
                },
            });
        });
    }, { once: true });
})();
