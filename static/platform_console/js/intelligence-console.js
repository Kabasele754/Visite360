(() => {
  const charts = [];
  const parseData = (id) => {
    const node = document.getElementById(id);
    if (!node) return null;
    try { return JSON.parse(node.textContent); } catch (_) { return null; }
  };
  const isDark = () => document.documentElement.dataset.dashboardTheme === "dark";
  const colors = () => isDark()
    ? { text: "#cbd5e1", border: "#0d1726", grid: "rgba(148,163,184,.15)" }
    : { text: "#475569", border: "#ffffff", grid: "rgba(15,23,42,.08)" };

  function destroyCharts() {
    while (charts.length) {
      try { charts.pop().destroy(); } catch (_) {}
    }
  }

  function renderCharts() {
    if (!window.Chart) return;
    destroyCharts();
    const theme = colors();
    const readiness = parseData("intelligence-readiness-data");
    const domain = parseData("intelligence-domain-data");
    const shared = {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 420 },
      plugins: {
        legend: { position: "bottom", labels: { color: theme.text, usePointStyle: true, padding: 16, boxWidth: 8, font: { weight: 700 } } },
        tooltip: { backgroundColor: "#020617", titleColor: "#f8fafc", bodyColor: "#f8fafc", padding: 11, cornerRadius: 11 },
      },
    };
    const readinessCanvas = document.getElementById("intelligenceReadinessChart");
    if (readinessCanvas && readiness) {
      charts.push(new Chart(readinessCanvas, {
        type: "doughnut",
        data: { labels: readiness.labels, datasets: [{ data: readiness.data, backgroundColor: ["#64748b", "#3b82f6", "#f59e0b", "#10b981"], borderColor: theme.border, borderWidth: 3, hoverOffset: 6 }] },
        options: { ...shared, cutout: "70%" },
      }));
    }
    const domainCanvas = document.getElementById("intelligenceDomainChart");
    if (domainCanvas && domain) {
      charts.push(new Chart(domainCanvas, {
        type: "bar",
        data: { labels: domain.labels, datasets: [{ label: "Organizations", data: domain.data, backgroundColor: ["#06b6d4", "#2563eb", "#8b5cf6", "#10b981", "#f59e0b"], borderRadius: 9, borderSkipped: false, maxBarThickness: 42 }] },
        options: { ...shared, plugins: { ...shared.plugins, legend: { display: false } }, scales: { x: { ticks: { color: theme.text }, grid: { display: false }, border: { display: false } }, y: { beginAtZero: true, ticks: { color: theme.text, precision: 0 }, grid: { color: theme.grid }, border: { display: false } } } },
      }));
    }
  }

  function waitForChart(attempt = 0) {
    if (window.Chart) return renderCharts();
    if (attempt < 50) window.setTimeout(() => waitForChart(attempt + 1), 100);
  }

  function watchTheme() {
    const observer = new MutationObserver((mutations) => {
      if (mutations.some((mutation) => mutation.attributeName === "data-dashboard-theme")) renderCharts();
    });
    observer.observe(document.documentElement, { attributes: true });
  }

  function bindRunPolling() {
    const root = document.querySelector("[data-intelligence-run]");
    if (!root) return;
    const url = root.dataset.statusUrl;
    if (!url) return;
    let timer = null;
    const update = (payload) => {
      const status = root.querySelector("[data-run-status]");
      if (status) status.textContent = payload.status_label;
      const message = root.querySelector("[data-run-message]");
      if (message && payload.message) message.textContent = payload.message;
      const heading = root.querySelector("[data-run-heading]");
      if (heading) {
        const headings = {
          queued: payload.stalled ? "The collection is waiting too long" : "Waiting for the background runner",
          running: "Collecting and preparing client data",
          succeeded: "Collection completed successfully",
          partial: "Collection completed with warnings",
          failed: "Collection could not be completed",
          cancelled: "Collection was cancelled",
        };
        heading.textContent = headings[payload.status] || payload.status_label;
      }
      const recovery = root.querySelector("[data-run-recovery]");
      if (recovery) recovery.hidden = !payload.can_retry;
      root.querySelectorAll("[data-run-value]").forEach((node) => {
        const key = node.dataset.runValue;
        if (Object.prototype.hasOwnProperty.call(payload, key)) node.textContent = payload[key];
      });
      const state = root.querySelector(".ts-intel-run-state .ts-status-dot");
      if (state) state.className = `ts-status-dot ts-status-dot--${payload.status}`;
      if (payload.finished && timer) {
        window.clearInterval(timer);
        timer = null;
        window.setTimeout(() => window.location.reload(), 700);
      }
    };
    let failedPolls = 0;
    const poll = async () => {
      try {
        const response = await fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin", cache: "no-store" });
        if (!response.ok) throw new Error(`Status request failed: ${response.status}`);
        failedPolls = 0;
        update(await response.json());
      } catch (_) {
        failedPolls += 1;
        if (failedPolls >= 3) {
          const message = root.querySelector("[data-run-message]");
          if (message) message.textContent = "The dashboard cannot refresh the run status right now. Check the local server connection.";
        }
      }
    };
    poll();
    timer = window.setInterval(poll, 4000);
  }

  document.addEventListener("DOMContentLoaded", () => {
    waitForChart();
    watchTheme();
    bindRunPolling();
  });
})();
