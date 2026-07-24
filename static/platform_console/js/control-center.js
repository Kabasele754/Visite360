(() => {
  const charts = [];

  const parseData = (id) => {
    const node = document.getElementById(id);
    if (!node) return null;
    try { return JSON.parse(node.textContent); } catch (_) { return null; }
  };

  const isDark = () => document.documentElement.dataset.dashboardTheme === "dark";

  function themeColors() {
    return isDark()
      ? {
          text: "#cbd5e1",
          muted: "#94a3b8",
          grid: "rgba(148,163,184,.16)",
          tooltip: "#020617",
          tooltipText: "#f8fafc",
          tooltipBorder: "rgba(34,211,238,.24)",
          doughnutBorder: "#0b1220",
        }
      : {
          text: "#475569",
          muted: "#64748b",
          grid: "rgba(15,23,42,.08)",
          tooltip: "#0f172a",
          tooltipText: "#f8fafc",
          tooltipBorder: "rgba(255,255,255,.12)",
          doughnutBorder: "#ffffff",
        };
  }

  function tooltipOptions() {
    const colors = themeColors();
    return {
      backgroundColor: colors.tooltip,
      titleColor: colors.tooltipText,
      bodyColor: colors.tooltipText,
      borderColor: colors.tooltipBorder,
      borderWidth: 1,
      padding: 12,
      cornerRadius: 12,
      displayColors: true,
      boxPadding: 5,
    };
  }

  function sharedOptions() {
    const colors = themeColors();
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 450 },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          labels: {
            color: colors.text,
            usePointStyle: true,
            boxWidth: 8,
            padding: 18,
            font: { weight: 700, family: "Inter, system-ui, sans-serif" },
          },
        },
        tooltip: tooltipOptions(),
      },
      scales: {
        x: {
          ticks: { color: colors.muted, maxRotation: 0, autoSkip: true },
          grid: { display: false },
          border: { display: false },
        },
        y: {
          beginAtZero: true,
          ticks: { color: colors.muted, precision: 0 },
          grid: { color: colors.grid, drawBorder: false },
          border: { display: false },
        },
      },
    };
  }

  function destroyCharts() {
    while (charts.length) {
      try { charts.pop().destroy(); } catch (_) {}
    }
  }

  function renderCharts() {
    if (!window.Chart) return;
    destroyCharts();

    const traffic = parseData("traffic-chart-data");
    const ai = parseData("ai-chart-data");
    const vision = parseData("vision-chart-data");
    const appointments = parseData("appointment-chart-data");
    const colors = themeColors();

    const trafficCanvas = document.getElementById("trafficChart");
    if (trafficCanvas && traffic) {
      charts.push(new Chart(trafficCanvas, {
        type: "line",
        data: {
          labels: traffic.labels,
          datasets: [
            {
              label: "Events",
              data: traffic.events,
              borderColor: "#06b6d4",
              backgroundColor: isDark() ? "rgba(6,182,212,.18)" : "rgba(6,182,212,.10)",
              fill: true,
              tension: .36,
              pointRadius: 2,
              pointHoverRadius: 5,
              borderWidth: 2.2,
            },
            {
              label: "Sessions",
              data: traffic.sessions,
              borderColor: "#3b82f6",
              backgroundColor: "rgba(59,130,246,.08)",
              fill: false,
              tension: .36,
              pointRadius: 2,
              pointHoverRadius: 5,
              borderWidth: 2.2,
            },
          ],
        },
        options: sharedOptions(),
      }));
    }

    const aiCanvas = document.getElementById("aiChart");
    if (aiCanvas && ai) {
      const palette = { Succeeded: "#10b981", Failed: "#ef4444", Running: "#3b82f6", Pending: "#f59e0b" };
      const options = sharedOptions();
      options.scales.x.stacked = true;
      options.scales.y.stacked = true;
      charts.push(new Chart(aiCanvas, {
        type: "bar",
        data: {
          labels: ai.labels,
          datasets: ai.datasets.map((dataset) => ({
            ...dataset,
            backgroundColor: palette[dataset.label] || "#94a3b8",
            borderRadius: 8,
            borderSkipped: false,
            maxBarThickness: 34,
          })),
        },
        options,
      }));
    }

    const doughnutOptions = {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "70%",
      animation: { duration: 450 },
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            color: colors.text,
            usePointStyle: true,
            boxWidth: 8,
            padding: 16,
            font: { weight: 700, family: "Inter, system-ui, sans-serif" },
          },
        },
        tooltip: tooltipOptions(),
      },
    };

    const visionCanvas = document.getElementById("visionChart");
    if (visionCanvas && vision) {
      charts.push(new Chart(visionCanvas, {
        type: "doughnut",
        data: {
          labels: vision.labels,
          datasets: [{
            data: vision.data,
            backgroundColor: ["#f59e0b", "#3b82f6", "#10b981", "#06b6d4", "#ef4444", "#94a3b8"],
            borderColor: colors.doughnutBorder,
            borderWidth: 3,
            hoverOffset: 6,
          }],
        },
        options: doughnutOptions,
      }));
    }

    const appointmentCanvas = document.getElementById("appointmentChart");
    if (appointmentCanvas && appointments) {
      charts.push(new Chart(appointmentCanvas, {
        type: "doughnut",
        data: {
          labels: appointments.labels,
          datasets: [{
            data: appointments.data,
            backgroundColor: ["#f59e0b", "#2563eb", "#10b981", "#ef4444", "#94a3b8"],
            borderColor: colors.doughnutBorder,
            borderWidth: 3,
            hoverOffset: 6,
          }],
        },
        options: doughnutOptions,
      }));
    }
  }

  function waitForChart(attempt = 0) {
    if (window.Chart) {
      renderCharts();
      return;
    }
    if (attempt < 50) {
      window.setTimeout(() => waitForChart(attempt + 1), 100);
      return;
    }
    document.querySelectorAll(".ts-chart-wrap").forEach((node) => {
      node.innerHTML = '<p class="ts-control-empty">Charts are temporarily unavailable.</p>';
    });
  }

  function bindResourceFilter() {
    const input = document.querySelector("[data-control-resource-filter]");
    const resources = [...document.querySelectorAll("[data-control-resource]")];
    const groups = [...document.querySelectorAll("[data-resource-group]")];
    const empty = document.querySelector("[data-control-resource-empty]");
    if (!input || !resources.length) return;

    const apply = () => {
      const query = input.value.trim().toLocaleLowerCase();
      let visibleCount = 0;
      resources.forEach((resource) => {
        const haystack = (resource.dataset.resourceSearch || resource.textContent || "").toLocaleLowerCase();
        const visible = !query || haystack.includes(query);
        resource.hidden = !visible;
        if (visible) visibleCount += 1;
      });
      groups.forEach((group) => {
        group.hidden = !group.querySelector("[data-control-resource]:not([hidden])");
      });
      if (empty) empty.hidden = visibleCount > 0;
    };

    input.addEventListener("input", apply);
    document.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        input.focus({ preventScroll: false });
        input.select();
      }
      if (event.key === "Escape" && document.activeElement === input && input.value) {
        input.value = "";
        apply();
      }
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindResourceFilter();
    waitForChart();

    let themeTimer = null;
    const observer = new MutationObserver((changes) => {
      if (!changes.some((change) => change.attributeName === "data-dashboard-theme")) return;
      window.clearTimeout(themeTimer);
      themeTimer = window.setTimeout(() => window.requestAnimationFrame(renderCharts), 80);
    });
    observer.observe(document.documentElement, { attributes: true });
  });
})();
