/* =====================================================================
   PREVIEW HOTSPOT 3D MODAL ADDON — IMAGE-ONLY FRONT + STABLE MOBILE FLIP
   À charger APRÈS dashboard/js/preview-tailwind.js
===================================================================== */
(function () {
    document.addEventListener("DOMContentLoaded", () => {
        const panel = document.getElementById("previewInfoPanel");
        const backdrop = document.getElementById("previewInfoBackdrop");
        const frontClose = document.getElementById("previewInfoClose");
        const card = document.getElementById("previewInfoCard3D");

        if (!panel) return;

        let flipTimer = null;
        let wasOpen = panel.classList.contains("open");
        let isAnimating = false;
        let targetFlipped = panel.classList.contains("is-flipped");
        let lastFlipAt = 0;
        let lastPointerAt = 0;

        function isMobile() {
            return window.matchMedia("(max-width: 768px)").matches;
        }

        function clearFlipTimer() {
            window.clearTimeout(flipTimer);
            flipTimer = null;
        }

        function settleFace(flipped) {
            clearFlipTimer();
            isAnimating = false;
            targetFlipped = Boolean(flipped);

            panel.classList.remove("flip-animating");
            panel.classList.toggle("is-flipped", targetFlipped);
            panel.classList.add("flip-settled");
            panel.setAttribute("data-flip-state", targetFlipped ? "back" : "front");
        }

        function resetToFront() {
            clearFlipTimer();
            isAnimating = false;
            targetFlipped = false;
            lastFlipAt = 0;
            lastPointerAt = 0;

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

            // Évite double tap, ghost click mobile, ou deuxième rotation pendant la stabilisation.
            if (isAnimating) return;
            if (now - lastFlipAt < 650) return;
            if (now - lastPointerAt < 80 && isMobile()) return;
            if (targetFlipped === next && panel.classList.contains("flip-settled")) return;

            lastFlipAt = now;
            isAnimating = true;
            targetFlipped = next;
            clearFlipTimer();

            panel.classList.remove("flip-settled");
            panel.classList.add("flip-animating");

            // Préparer état de départ : indispensable pour une vraie rotation visible.
            if (next) {
                panel.classList.remove("is-flipped");
            } else {
                panel.classList.add("is-flipped");
            }

            if (card) void card.offsetWidth;

            window.requestAnimationFrame(() => {
                panel.classList.toggle("is-flipped", next);
            });

            flipTimer = window.setTimeout(() => {
                settleFace(next);
            }, isMobile() ? 740 : 720);
        }

        function flipPanel() {
            setFlipped(!targetFlipped);
        }

        panel.addEventListener("pointerdown", (event) => {
            if (event.target.closest("[data-preview-info-flip], [data-preview-info-close], #previewInfoClose")) {
                lastPointerAt = Date.now();
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

            const closeButton = event.target.closest("[data-preview-info-close], #previewInfoClose");
            if (closeButton) {
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();
                closePanel3D();
                return;
            }

            // Face avant = image uniquement. On tape n'importe où sur l'image
            // pour lancer le flip vers la description, sans bouton visible.
            const frontFace = event.target.closest(".hotspot-info-front");
            if (frontFace && !targetFlipped) {
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();
                setFlipped(true);
                return;
            }
        }, { capture: true });

        frontClose?.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            closePanel3D();
        }, true);

        backdrop?.addEventListener("click", () => {
            closePanel3D();
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
                closePanel3D();
            }
        });
    });
})();
