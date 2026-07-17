(function () {
  "use strict";

  function initProductExperience() {
    if (document.documentElement.dataset.productExperienceReady === "true") return;
    document.documentElement.dataset.productExperienceReady = "true";

    const sheet = document.getElementById("marketTourBottomSheet");
    const openButton = document.querySelector("[data-market-tour-sheet-open]");

    if (sheet && openButton) {
      const panel = sheet.querySelector(".market-tour-sheet__panel");
      const closeButtons = sheet.querySelectorAll("[data-market-tour-sheet-close]");

      const openSheet = function () {
        sheet.removeAttribute("inert");
        sheet.setAttribute("aria-hidden", "false");
        sheet.classList.add("is-open");
        document.body.classList.add("market-sheet-open");
        openButton.setAttribute("aria-expanded", "true");
        window.setTimeout(function () {
          sheet.querySelector(".market-tour-sheet__close")?.focus();
        }, 180);
      };

      const closeSheet = function () {
        sheet.classList.remove("is-open");
        sheet.setAttribute("aria-hidden", "true");
        document.body.classList.remove("market-sheet-open");
        openButton.setAttribute("aria-expanded", "false");
        window.setTimeout(function () {
          sheet.setAttribute("inert", "");
        }, 360);
      };

      openButton.addEventListener("click", function (event) {
        event.preventDefault();
        openSheet();
      });

      closeButtons.forEach(function (button) {
        button.addEventListener("click", function (event) {
          event.preventDefault();
          closeSheet();
        });
      });

      panel?.addEventListener("click", function (event) {
        event.stopPropagation();
      });

      document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && sheet.classList.contains("is-open")) {
          closeSheet();
        }
      });
    }

    const flipCard = function (card) {
      if (!card) return;
      card.classList.add("is-flipping");
      const flipped = card.classList.toggle("is-flipped");
      card.setAttribute("aria-pressed", flipped ? "true" : "false");
      window.setTimeout(function () {
        card.classList.remove("is-flipping");
      }, 620);
    };

    document.querySelectorAll("[data-tour-flip-card]").forEach(function (card) {
      card.addEventListener("click", function (event) {
        if (event.target.closest("[data-tour-card-link], a, [data-tour-flip]")) return;
        flipCard(card);
      });

      card.addEventListener("keydown", function (event) {
        if (event.key !== "Enter" && event.key !== " ") return;
        if (event.target.closest("[data-tour-card-link], a")) return;
        event.preventDefault();
        flipCard(card);
      });
    });

    document.querySelectorAll("[data-tour-flip]").forEach(function (button) {
      button.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        flipCard(button.closest("[data-tour-flip-card]"));
      });
    });

    document.querySelectorAll("[data-tour-card-link]").forEach(function (link) {
      link.addEventListener("click", function (event) {
        event.stopPropagation();
      });
    });

    document.querySelectorAll("[data-tour-horizontal-rail]").forEach(function (rail) {
      let pointerDown = false;
      let startX = 0;
      let startScrollLeft = 0;
      let moved = false;

      rail.addEventListener("pointerdown", function (event) {
        if (event.target.closest("a, button")) return;
        pointerDown = true;
        moved = false;
        startX = event.clientX;
        startScrollLeft = rail.scrollLeft;
        rail.classList.add("is-dragging");
        rail.setPointerCapture?.(event.pointerId);
      });

      rail.addEventListener("pointermove", function (event) {
        if (!pointerDown) return;
        const delta = event.clientX - startX;
        if (Math.abs(delta) > 5) moved = true;
        rail.scrollLeft = startScrollLeft - delta;
      });

      const stopDrag = function (event) {
        if (!pointerDown) return;
        pointerDown = false;
        rail.classList.remove("is-dragging");
        try { rail.releasePointerCapture?.(event.pointerId); } catch (_) {}
      };

      rail.addEventListener("pointerup", stopDrag);
      rail.addEventListener("pointercancel", stopDrag);
      rail.addEventListener("pointerleave", function (event) {
        if (event.buttons === 0) stopDrag(event);
      });

      rail.addEventListener("click", function (event) {
        if (!moved) return;
        event.preventDefault();
        event.stopPropagation();
        moved = false;
      }, true);

      rail.addEventListener("wheel", function (event) {
        if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
        if (rail.scrollWidth <= rail.clientWidth) return;
        event.preventDefault();
        rail.scrollBy({ left: event.deltaY, behavior: "smooth" });
      }, { passive: false });
    });

    document.querySelectorAll("[data-floating-contact-stack]").forEach(function (stack) {
      const toggle = stack.querySelector("[data-floating-contact-toggle]");
      if (!toggle) return;

      toggle.addEventListener("click", function () {
        const collapsed = stack.classList.toggle("is-collapsed");
        toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initProductExperience, { once: true });
  } else {
    initProductExperience();
  }

  window.addEventListener("pageshow", initProductExperience);
})();
