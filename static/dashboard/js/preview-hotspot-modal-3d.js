/* =====================================================================
   PREVIEW HOTSPOT 3D MODAL ADDON
   À charger APRÈS dashboard/js/preview-tailwind.js
   Exemple :
   <script src="{% static 'dashboard/js/preview-hotspot-modal-3d.js' %}?v=3d-hotspot-modal-20260603"></script>
===================================================================== */
(function () {
    document.addEventListener("DOMContentLoaded", () => {
        const panel = document.getElementById("previewInfoPanel");
        const backdrop = document.getElementById("previewInfoBackdrop");
        const frontClose = document.getElementById("previewInfoClose");

        if (!panel) return;

        let flipTimer = null;
        let wasOpen = panel.classList.contains("open");

        function resetToFront() {
            window.clearTimeout(flipTimer);
            panel.classList.remove("is-flipped", "flip-settled");
        }

        function closePanel3D() {
            resetToFront();
            panel.classList.remove("open");
            panel.setAttribute("aria-hidden", "true");
            backdrop?.classList.remove("open");
            document.body.classList.remove("info-panel-open");
        }

        function flipPanel() {
            window.clearTimeout(flipTimer);
            panel.classList.remove("flip-settled");
            panel.classList.toggle("is-flipped");

            flipTimer = window.setTimeout(() => {
                panel.classList.add("flip-settled");
            }, 720);
        }

        panel.addEventListener("click", (event) => {
            const flipButton = event.target.closest("[data-preview-info-flip]");
            if (flipButton) {
                event.preventDefault();
                event.stopPropagation();
                flipPanel();
                return;
            }

            const closeButton = event.target.closest("[data-preview-info-close]");
            if (closeButton) {
                event.preventDefault();
                event.stopPropagation();
                closePanel3D();
            }
        });

        // Le bouton close de la face avant est déjà géré par preview-tailwind.js.
        // Ici on ajoute seulement le reset du flip pour éviter de rouvrir le modal au dos.
        frontClose?.addEventListener("click", () => {
            resetToFront();
            panel.setAttribute("aria-hidden", "true");
        }, true);

        backdrop?.addEventListener("click", () => {
            resetToFront();
            panel.setAttribute("aria-hidden", "true");
        }, true);

        // Quand preview-tailwind.js ouvre le panneau avec .open,
        // on force toujours le démarrage sur la face image.
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
