/* =====================================================================
   PREVIEW HOTSPOT 3D MODAL ADDON — SHARP IMAGE + MOBILE FLIP FIX
   À charger APRÈS dashboard/js/preview-tailwind.js
===================================================================== */
(function () {
    document.addEventListener("DOMContentLoaded", () => {
        const panel = document.getElementById("previewInfoPanel");
        const backdrop = document.getElementById("previewInfoBackdrop");
        const frontClose = document.getElementById("previewInfoClose");

        if (!panel) return;

        let flipTimer = null;
        let wasOpen = panel.classList.contains("open");
        let isAnimating = false;
        let lastFlipAt = 0;
        let targetFlipped = panel.classList.contains("is-flipped");

        function isMobile() {
            return window.matchMedia("(max-width: 768px)").matches;
        }

        function settleFace(flipped) {
            window.clearTimeout(flipTimer);
            targetFlipped = Boolean(flipped);
            isAnimating = false;
            panel.classList.remove("flip-animating");
            panel.classList.toggle("is-flipped", targetFlipped);
            panel.classList.add("flip-settled");
            panel.setAttribute("data-flip-state", targetFlipped ? "back" : "front");
        }

        function resetToFront() {
            window.clearTimeout(flipTimer);
            targetFlipped = false;
            isAnimating = false;
            panel.classList.remove("is-flipped", "flip-animating");
            panel.classList.add("flip-settled");
            panel.setAttribute("data-flip-state", "front");
        }

        function closePanel3D() {
            resetToFront();
            panel.classList.remove("open");
            panel.setAttribute("aria-hidden", "true");
            backdrop?.classList.remove("open");
            document.body.classList.remove("info-panel-open");
        }

        function setFlipped(nextValue) {
            const next = Boolean(nextValue);
            const now = Date.now();

            // Protection mobile contre le double tap / ghost click qui relance la rotation.
            if (isAnimating || now - lastFlipAt < 520) return;
            if (targetFlipped === next && panel.classList.contains("flip-settled")) return;

            lastFlipAt = now;
            targetFlipped = next;
            isAnimating = true;

            window.clearTimeout(flipTimer);
            panel.classList.remove("flip-settled");
            panel.classList.add("flip-animating");

            // Prépare l'état de départ, puis déclenche la rotation au frame suivant.
            if (next) {
                panel.classList.remove("is-flipped");
            } else {
                panel.classList.add("is-flipped");
            }

            const card = document.getElementById("previewInfoCard3D") || panel.querySelector(".hotspot-info-3d-card");
            if (card) void card.offsetWidth;

            window.requestAnimationFrame(() => {
                panel.classList.toggle("is-flipped", next);
            });

            flipTimer = window.setTimeout(() => settleFace(next), isMobile() ? 760 : 720);
        }

        function flipPanel() {
            setFlipped(!targetFlipped);
        }

        panel.addEventListener("pointerdown", (event) => {
            if (event.target.closest("[data-preview-info-flip], [data-preview-info-close]")) {
                event.stopPropagation();
            }
        }, { capture: true });

        panel.addEventListener("click", (event) => {
            const flipButton = event.target.closest("[data-preview-info-flip]");
            if (flipButton) {
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();
                flipPanel();
                return;
            }

            const closeButton = event.target.closest("[data-preview-info-close]");
            if (closeButton) {
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();
                closePanel3D();
            }
        }, { capture: true });

        frontClose?.addEventListener("click", () => {
            resetToFront();
            panel.setAttribute("aria-hidden", "true");
        }, true);

        backdrop?.addEventListener("click", () => {
            resetToFront();
            panel.setAttribute("aria-hidden", "true");
        }, true);

        const observer = new MutationObserver(() => {
            const isOpen = panel.classList.contains("open");

            if (isOpen && !wasOpen) {
                resetToFront();
                panel.setAttribute("aria-hidden", "false");
            }

            if (!isOpen && wasOpen) {
                resetToFront();
                panel.setAttribute("aria-hidden", "true");
            }

            wasOpen = isOpen;
        });

        observer.observe(panel, {
            attributes: true,
            attributeFilter: ["class"],
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                resetToFront();
                panel.setAttribute("aria-hidden", "true");
            }
        });
    });
})();
