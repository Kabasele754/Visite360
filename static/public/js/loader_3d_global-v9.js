(() => {
  "use strict";

  window.TWINSCOPE_LOADER_VERSION = "stable-loader-v9-20260717";

  const loader = document.getElementById("globalPageLoader");
  if (!loader || loader.dataset.loaderInitialized === "true") return;
  loader.dataset.loaderInitialized = "true";

  const statusEl = loader.querySelector("#globalLoaderStatusText");
  const statuses = [
    "Loading content...",
    "Preparing immersive navigation...",
    "Optimizing visual experience...",
    "Almost ready..."
  ];

  let statusIndex = 0;
  let statusTimer = null;
  let hideTimer = null;
  let safetyTimer = null;
  let hidden = false;

  const startStatusRotation = () => {
    if (!statusEl || statusTimer || hidden) return;
    statusTimer = window.setInterval(() => {
      statusIndex = (statusIndex + 1) % statuses.length;
      statusEl.textContent = statuses[statusIndex];
    }, 1150);
  };

  const stopStatusRotation = () => {
    if (statusTimer) {
      clearInterval(statusTimer);
      statusTimer = null;
    }
  };

  const hide = (delay = 260) => {
    if (hidden) return;
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => {
      if (hidden) return;
      hidden = true;
      loader.classList.add("is-hidden");
      loader.setAttribute("aria-hidden", "true");
      loader.style.pointerEvents = "none";
      stopStatusRotation();

      setTimeout(() => {
        loader.hidden = true;
        loader.style.display = "none";
      }, 520);
    }, delay);
  };

  const show = () => {
    hidden = false;
    loader.hidden = false;
    loader.style.display = "flex";
    loader.style.pointerEvents = "auto";
    loader.setAttribute("aria-hidden", "false");
    requestAnimationFrame(() => loader.classList.remove("is-hidden"));
    startStatusRotation();
  };

  window.VirtualTourLoader = { show, hide };

  show();

  const pageReady = () => {
    requestAnimationFrame(() => requestAnimationFrame(() => hide(180)));
  };

  // Important: the script may be loaded after window.load already fired.
  if (document.readyState === "complete") {
    pageReady();
  } else {
    window.addEventListener("load", pageReady, { once: true });
    document.addEventListener("DOMContentLoaded", () => hide(900), { once: true });
  }

  // Never block the interface indefinitely, even if one asset hangs.
  safetyTimer = setTimeout(() => hide(0), 5000);

  window.addEventListener("pageshow", event => {
    if (event.persisted) hide(0);
  });

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && !hidden) startStatusRotation();
  });
})();
