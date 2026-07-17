(function () {
  "use strict";
  function initFloatingContacts() {
    document.querySelectorAll("[data-floating-contact-stack]").forEach(function (stack) {
      if (stack.dataset.ready === "true") return;
      stack.dataset.ready = "true";
      const toggle = stack.querySelector("[data-floating-contact-toggle]");
      if (!toggle) return;
      toggle.addEventListener("click", function () {
        const collapsed = stack.classList.toggle("is-collapsed");
        toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
      });
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initFloatingContacts, { once: true });
  } else {
    initFloatingContacts();
  }
})();
