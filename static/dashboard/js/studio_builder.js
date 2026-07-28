document.addEventListener("DOMContentLoaded", () => {
    const config = window.BUILDER_CONFIG || {};
    const scenesDataEl = document.getElementById("scenes-data");
    let scenesData = scenesDataEl ? JSON.parse(scenesDataEl.textContent) : [];

    function injectModalDesignStyles() {
        if (document.getElementById("studio-builder-modal-js-style")) return;

        const style = document.createElement("style");
        style.id = "studio-builder-modal-js-style";
        style.textContent = `
            body.modal-is-open {
                overflow: hidden;
            }

            .modal-backdrop {
                opacity: 1;
                transition: opacity 220ms ease;
                background:
                    radial-gradient(circle at top left, rgba(37, 99, 235, .32), transparent 34%),
                    radial-gradient(circle at bottom right, rgba(14, 165, 233, .22), transparent 34%),
                    rgba(2, 6, 23, .82) !important;
                backdrop-filter: blur(18px);
            }

            .modal-backdrop.is-opening {
                animation: modalBackdropIn 220ms ease forwards;
            }

            .modal-backdrop.is-closing {
                opacity: 0;
            }

            .modal-card {
                overflow: hidden;
                border-radius: 34px !important;
                border: 1px solid rgba(255, 255, 255, .14) !important;
                background:
                    radial-gradient(circle at top right, rgba(37, 99, 235, .14), transparent 36%),
                    linear-gradient(180deg, rgba(15, 23, 42, .98), rgba(15, 23, 42, .94)) !important;
                box-shadow:
                    0 40px 120px rgba(0, 0, 0, .45),
                    inset 0 1px 0 rgba(255, 255, 255, .08) !important;
                color: #e5e7eb;
                transform: translateY(0) scale(1);
                transition: transform 220ms ease, opacity 220ms ease;
            }

            .modal-backdrop.is-opening .modal-card {
                animation: modalCardIn 260ms cubic-bezier(.22,.9,.3,1) forwards;
            }

            .modal-backdrop.is-closing .modal-card {
                transform: translateY(16px) scale(.985);
                opacity: 0;
            }

            @keyframes modalBackdropIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }

            @keyframes modalCardIn {
                from {
                    opacity: 0;
                    transform: translateY(24px) scale(.97);
                }
                to {
                    opacity: 1;
                    transform: translateY(0) scale(1);
                }
            }

            .modal-header {
                border-bottom: 1px solid rgba(255, 255, 255, .10) !important;
                background:
                    radial-gradient(circle at top left, rgba(37, 99, 235, .30), transparent 36%),
                    rgba(2, 6, 23, .72) !important;
                color: #ffffff !important;
            }

            .modal-header h3 {
                color: #ffffff !important;
                font-weight: 950 !important;
                letter-spacing: -.025em;
            }

            .modal-header p {
                color: rgba(226, 232, 240, .68) !important;
            }

            .close-btn {
                background: rgba(255, 255, 255, .08) !important;
                color: #ffffff !important;
                border: 1px solid rgba(255, 255, 255, .10) !important;
                transition: all .16s ease;
            }

            .close-btn:hover {
                background: rgba(255, 255, 255, .14) !important;
                transform: scale(1.03);
            }

            .modal-body {
                background:
                    radial-gradient(circle at top right, rgba(37, 99, 235, .18), transparent 30%),
                    #0f172a !important;
                color: #e5e7eb !important;
            }

            .modal-body::-webkit-scrollbar {
                width: 8px;
            }

            .modal-body::-webkit-scrollbar-thumb {
                background: rgba(148, 163, 184, .35);
                border-radius: 999px;
            }

            .modal-actions {
                border-top: 1px solid rgba(255, 255, 255, .10) !important;
                background: rgba(2, 6, 23, .86) !important;
                backdrop-filter: blur(18px);
            }

            .modal-type-hero {
                position: relative;
                overflow: hidden;
                border-radius: 28px;
                border: 1px solid rgba(255, 255, 255, .12);
                background:
                    radial-gradient(circle at top right, rgba(59, 130, 246, .45), transparent 38%),
                    linear-gradient(135deg, rgba(30, 41, 59, .98), rgba(15, 23, 42, .98));
                color: white;
                padding: 20px;
                margin-bottom: 18px;
                box-shadow: 0 24px 70px rgba(0, 0, 0, .28);
            }

            .modal-type-hero::before {
                content: "";
                position: absolute;
                inset: 0;
                background:
                    linear-gradient(120deg, rgba(255,255,255,.10), transparent 26%, transparent 72%, rgba(255,255,255,.05));
                pointer-events: none;
            }

            .modal-type-hero-inner {
                position: relative;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 18px;
            }

            .modal-type-kicker {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                border-radius: 999px;
                background: rgba(255, 255, 255, .10);
                border: 1px solid rgba(255, 255, 255, .14);
                padding: 7px 11px;
                font-size: 10px;
                font-weight: 950;
                letter-spacing: .08em;
                text-transform: uppercase;
                color: rgba(255, 255, 255, .76);
                margin-bottom: 10px;
            }

            .modal-type-title {
                font-size: 22px;
                font-weight: 950;
                line-height: 1.1;
                letter-spacing: -.04em;
                color: #ffffff;
            }

            .modal-type-description {
                margin-top: 8px;
                font-size: 13px;
                line-height: 1.65;
                color: rgba(226, 232, 240, .72);
                max-width: 620px;
            }

            .modal-type-icon {
                width: 72px;
                height: 72px;
                border-radius: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
                background:
                    linear-gradient(180deg, rgba(255,255,255,.16), rgba(255,255,255,.07));
                border: 1px solid rgba(255, 255, 255, .18);
                box-shadow:
                    0 24px 60px rgba(0, 0, 0, .24),
                    inset 0 1px 0 rgba(255,255,255,.12);
                flex-shrink: 0;
            }

            .modal-type-icon img {
                width: 44px;
                height: 44px;
                object-fit: contain;
                filter: drop-shadow(0 12px 24px rgba(0,0,0,.35));
            }

            .hotspot-live-preview-card {
                overflow: hidden;
                border-radius: 28px;
                border: 1px solid rgba(255, 255, 255, .12);
                background:
                    linear-gradient(180deg, rgba(30, 41, 59, .96), rgba(15, 23, 42, .96));
                box-shadow: 0 22px 64px rgba(0, 0, 0, .24);
                margin-bottom: 18px;
            }

            .hotspot-live-preview-head {
                padding: 15px 18px;
                border-bottom: 1px solid rgba(255, 255, 255, .10);
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                background: rgba(2, 6, 23, .38);
            }

            .hotspot-live-preview-head strong {
                font-size: 11px;
                font-weight: 950;
                text-transform: uppercase;
                letter-spacing: .08em;
                color: rgba(226, 232, 240, .74);
            }

            .hotspot-live-preview-badge {
                border-radius: 999px;
                padding: 6px 10px;
                background: rgba(37, 99, 235, .18);
                color: #93c5fd;
                border: 1px solid rgba(59, 130, 246, .22);
                font-size: 10px;
                font-weight: 950;
                text-transform: uppercase;
                letter-spacing: .05em;
            }

            .hotspot-live-preview-body {
                display: grid;
                grid-template-columns: 170px minmax(0, 1fr);
                gap: 16px;
                padding: 16px;
            }

            .hotspot-live-preview-media {
                height: 134px;
                border-radius: 22px;
                background:
                    radial-gradient(circle at top left, rgba(59, 130, 246, .24), transparent 40%),
                    rgba(255, 255, 255, .06);
                border: 1px solid rgba(255, 255, 255, .10);
                overflow: hidden;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #93c5fd;
                font-size: 34px;
                font-weight: 950;
            }

            .hotspot-live-preview-media img {
                width: 100%;
                height: 100%;
                object-fit: contain;
                background: rgba(255, 255, 255, .04);
                display: block;
                padding: 10px;
            }

            .hotspot-live-preview-content {
                min-width: 0;
            }

            .hotspot-live-preview-title {
                font-size: 18px;
                font-weight: 950;
                color: #ffffff;
                line-height: 1.2;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                letter-spacing: -.02em;
            }

            .hotspot-live-preview-desc {
                margin-top: 7px;
                color: rgba(203, 213, 225, .78);
                font-size: 13px;
                line-height: 1.6;
                display: -webkit-box;
                -webkit-line-clamp: 3;
                -webkit-box-orient: vertical;
                overflow: hidden;
            }

            .hotspot-live-preview-meta {
                margin-top: 12px;
                display: flex;
                flex-wrap: wrap;
                gap: 7px;
            }

            .hotspot-live-preview-meta span {
                border-radius: 999px;
                background: rgba(255, 255, 255, .07);
                border: 1px solid rgba(255, 255, 255, .10);
                padding: 6px 10px;
                color: #e2e8f0;
                font-size: 11px;
                font-weight: 900;
            }

            .hotspot-live-preview-actions {
                margin-top: 13px;
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
            }

            .hotspot-live-preview-action {
                border-radius: 15px;
                background: linear-gradient(135deg, #2563eb, #1d4ed8);
                color: white;
                padding: 9px 12px;
                font-size: 11px;
                font-weight: 950;
                box-shadow: 0 14px 30px rgba(37, 99, 235, .24);
            }

            .hotspot-live-preview-action.dark {
                background: linear-gradient(135deg, #334155, #0f172a);
            }

            .hotspot-live-preview-action.green {
                background: linear-gradient(135deg, #22c55e, #16a34a);
            }

            .modal-body .form-group,
            .modal-body .hotspot-type-panel,
            .modal-body .rounded-\\[1\\.5rem\\] {
                background: rgba(255, 255, 255, .055) !important;
                border-color: rgba(255, 255, 255, .10) !important;
                color: #e5e7eb !important;
                backdrop-filter: blur(10px);
            }

            .modal-body label {
                color: rgba(226, 232, 240, .72) !important;
            }

            .modal-body input,
            .modal-body select,
            .modal-body textarea {
                background: rgba(2, 6, 23, .44) !important;
                border-color: rgba(255, 255, 255, .12) !important;
                color: #ffffff !important;
                box-shadow: none !important;
            }

            .modal-body input::placeholder,
            .modal-body textarea::placeholder {
                color: rgba(148, 163, 184, .68) !important;
            }

            .modal-body input:focus,
            .modal-body select:focus,
            .modal-body textarea:focus {
                border-color: rgba(96, 165, 250, .75) !important;
                box-shadow: 0 0 0 4px rgba(37, 99, 235, .18) !important;
                background: rgba(15, 23, 42, .86) !important;
            }

            .hotspot-icon-option {
                position: relative;
                min-height: 82px;
                display: flex !important;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                gap: 8px;
                border-radius: 22px !important;
                background: rgba(255, 255, 255, .06) !important;
                border: 1px solid rgba(255, 255, 255, .10) !important;
                color: rgba(226, 232, 240, .82) !important;
                transition: transform .16s ease, border-color .16s ease, background .16s ease, box-shadow .16s ease;
            }

            .hotspot-icon-option:hover {
                transform: translateY(-2px);
                background: rgba(59, 130, 246, .12) !important;
                border-color: rgba(96, 165, 250, .40) !important;
                box-shadow: 0 18px 40px rgba(0, 0, 0, .18);
            }

            .hotspot-icon-option.active {
                background: linear-gradient(135deg, rgba(37, 99, 235, .28), rgba(14, 165, 233, .14)) !important;
                border-color: rgba(96, 165, 250, .72) !important;
                color: #ffffff !important;
                box-shadow:
                    0 0 0 4px rgba(37, 99, 235, .16),
                    0 20px 44px rgba(37, 99, 235, .18);
            }

            .hotspot-icon-option img {
                width: 34px;
                height: 34px;
                object-fit: contain;
                filter: drop-shadow(0 10px 18px rgba(0,0,0,.25));
            }

            .hotspot-icon-option span {
                font-size: 10px;
                font-weight: 950;
                text-transform: uppercase;
                letter-spacing: .04em;
            }

            .btn-primary-modal {
                background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
                color: #ffffff !important;
                box-shadow: 0 18px 38px rgba(37, 99, 235, .26) !important;
                border: 1px solid rgba(96, 165, 250, .25) !important;
            }

            .btn-secondary-modal {
                background: rgba(255, 255, 255, .07) !important;
                color: #e5e7eb !important;
                border-color: rgba(255, 255, 255, .12) !important;
            }

            .btn-danger-modal {
                background: rgba(244, 63, 94, .12) !important;
                color: #fecdd3 !important;
                border: 1px solid rgba(244, 63, 94, .22) !important;
            }

            .btn-loading {
                pointer-events: none;
                opacity: .72;
                position: relative;
            }

            .btn-loading::after {
                content: "";
                width: 14px;
                height: 14px;
                margin-left: 8px;
                border-radius: 999px;
                border: 2px solid rgba(255, 255, 255, .50);
                border-top-color: white;
                display: inline-block;
                vertical-align: -2px;
                animation: spinLoader .7s linear infinite;
            }

            @keyframes spinLoader {
                to { transform: rotate(360deg); }
            }

            .builder-toast {
                position: fixed;
                right: 18px;
                top: 18px;
                z-index: 99999;
                max-width: min(360px, calc(100vw - 36px));
                border-radius: 18px;
                padding: 13px 15px;
                color: white;
                font-size: 13px;
                font-weight: 850;
                box-shadow: 0 20px 60px rgba(15, 23, 42, .25);
                animation: toastIn .22s ease forwards;
            }

            .builder-toast.success { background: #16a34a; }
            .builder-toast.error { background: #dc2626; }
            .builder-toast.info { background: #2563eb; }
            .builder-toast.warning { background: #d97706; }

            @keyframes toastIn {
                from {
                    opacity: 0;
                    transform: translateY(-8px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            .scene-card-wrap.dragging {
                opacity: .55;
                transform: scale(.98);
            }

            .scene-card-wrap.drag-over {
                border-color: #2563eb !important;
                background: #eff6ff !important;
                box-shadow: 0 0 0 4px rgba(37, 99, 235, .10);
            }

            .marzipano-hotspot,
            .marzipano-hotspot-marker {
                cursor: pointer;
                user-select: none;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                filter: drop-shadow(0 14px 22px rgba(15, 23, 42, .26));
                transition: transform .18s ease, filter .18s ease;
            }

            .marzipano-hotspot:hover,
            .marzipano-hotspot-marker:hover {
                filter: drop-shadow(0 18px 30px rgba(37, 99, 235, .40));
            }

            .marzipano-hotspot-marker.variant-label {
                gap: 8px;
                width: auto !important;
                min-width: max-content;
                background: rgba(255, 255, 255, .96);
                border: 1px solid rgba(226, 232, 240, .95);
                border-radius: 999px;
                padding: 7px 10px 7px 7px;
                box-shadow: 0 16px 38px rgba(15, 23, 42, .18);
                backdrop-filter: blur(10px);
            }

            .marzipano-hotspot-marker.variant-label img {
                width: 30px;
                height: 30px;
                flex-shrink: 0;
            }

            .marzipano-hotspot-marker.variant-label span {
                margin-left: 0 !important;
                box-shadow: none !important;
                background: transparent !important;
                padding: 0 !important;
                font-weight: 950;
                color: #0f172a;
                white-space: nowrap;
            }

            .marzipano-hotspot-marker.is-selected {
                filter: drop-shadow(0 0 14px rgba(37, 99, 235, .95));
            }

            @media (max-width: 640px) {
                .modal-card {
                    border-radius: 28px 28px 0 0 !important;
                }

                .modal-type-hero-inner {
                    align-items: flex-start;
                }

                .modal-type-icon {
                    width: 58px;
                    height: 58px;
                    border-radius: 20px;
                }

                .modal-type-icon img {
                    width: 36px;
                    height: 36px;
                }

                .hotspot-live-preview-body {
                    grid-template-columns: 1fr;
                }

                .hotspot-live-preview-media {
                    height: 180px;
                }
            }
        `;

        document.head.appendChild(style);
    }

    function notify(message, type = "info") {
        if (window.Swal && typeof window.Swal.fire === "function") {
            const icon = type === "error" ? "error" : type === "success" ? "success" : type === "warning" ? "warning" : "info";

            window.Swal.fire({
                toast: true,
                position: "top-end",
                icon,
                title: message,
                showConfirmButton: false,
                timer: 2400,
                timerProgressBar: true,
                background: "#0f172a",
                color: "#f8fafc",
            });
            return;
        }

        const toast = document.createElement("div");
        toast.className = `builder-toast ${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(-8px)";
            setTimeout(() => toast.remove(), 180);
        }, 2400);
    }

    async function confirmAction(message, title = "Confirmation") {
        if (window.Swal && typeof window.Swal.fire === "function") {
            const result = await window.Swal.fire({
                title,
                text: message,
                icon: "warning",
                showCancelButton: true,
                confirmButtonText: "Yes, continue",
                cancelButtonText: "Cancel",
                confirmButtonColor: "#dc2626",
                background: "#ffffff",
                color: "#0f172a",
            });

            return result.isConfirmed;
        }

        return window.confirm(message);
    }

    function setButtonLoading(button, loading, loadingText = "Saving...") {
        if (!button) return;

        if (loading) {
            if (!button.dataset.originalText) {
                button.dataset.originalText = button.textContent.trim();
            }

            button.textContent = loadingText;
            button.classList.add("btn-loading");
            button.disabled = true;
        } else {
            button.textContent = button.dataset.originalText || button.textContent;
            button.classList.remove("btn-loading");
            button.disabled = false;
        }
    }

    function escapeHtml(value) {
        return String(value || "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    function getIconSrc(iconName) {
        if (config.businessIconMap && config.businessIconMap[iconName]) {
            return config.businessIconMap[iconName];
        }

        if (config.iconMap && config.iconMap[iconName]) {
            return config.iconMap[iconName];
        }

        if (config.iconMap && config.iconMap.default) {
            return config.iconMap.default;
        }

        return "";
    }

    if (typeof Marzipano === "undefined") {
        console.error("Marzipano library is not loaded.");
        notify("Marzipano n'est pas chargé. Vérifie le script marzipano.js.", "error");
        return;
    }

    injectModalDesignStyles();

    const sceneList = document.getElementById("sceneList");
    const dropZone = document.getElementById("dropZone");
    const sceneFileInput = document.getElementById("sceneFileInput");
    const addSceneBtn = document.getElementById("addSceneBtn");

    const sceneTitleInput = document.getElementById("sceneTitle");
    const yawInput = document.getElementById("yawDefault");
    const pitchInput = document.getElementById("pitchDefault");
    const hfovInput = document.getElementById("hfovDefault");
    const scenePublicInput = document.getElementById("sceneIsPublic");
    const scenePublicStatus = document.getElementById("scenePublicStatus");
    const scenePublicHelp = document.getElementById("scenePublicHelp");
    const sceneVisibilityPreview = document.getElementById("sceneVisibilityPreview");
    const tripodLogoEnabled = document.getElementById("tripodLogoEnabled");
    const tripodLogoApplyAllScenes = document.getElementById("tripodLogoApplyAllScenes");
    const tripodLogoSize = document.getElementById("tripodLogoSize");
    const tripodLogoYaw = document.getElementById("tripodLogoYaw");
    const tripodLogoPitch = document.getElementById("tripodLogoPitch");
    const tripodLogoOffsetX = document.getElementById("tripodLogoOffsetX");
    const tripodLogoOffsetY = document.getElementById("tripodLogoOffsetY");
    const tripodLogoRotation = document.getElementById("tripodLogoRotation");
    const tripodLogoTiltX = document.getElementById("tripodLogoTiltX");
    const tripodLogoTiltY = document.getElementById("tripodLogoTiltY");
    const tripodLogoRadius = document.getElementById("tripodLogoRadius");
    const tripodLogoPlaceBtn = document.getElementById("tripodLogoPlaceBtn");
    const tripodLogoNadirBtn = document.getElementById("tripodLogoNadirBtn");

    const viewerSceneTitle = document.getElementById("viewerSceneTitle");
    const activeSceneLabel = document.getElementById("activeSceneLabel");

    const panoramaViewer = document.getElementById("panoramaViewer");
    const layerAEl = document.getElementById("marzipanoLayerA");
    const layerBEl = document.getElementById("marzipanoLayerB");
    const mountAEl = document.getElementById("marzipanoMountA");
    const mountBEl = document.getElementById("marzipanoMountB");

    const saveSceneBtn = document.getElementById("saveSceneBtn");
    const toolButtons = document.querySelectorAll(".tool-btn");

    const cameraLeftBtn = document.getElementById("cameraLeftBtn");
    const cameraRightBtn = document.getElementById("cameraRightBtn");
    const cameraUpBtn = document.getElementById("cameraUpBtn");
    const cameraDownBtn = document.getElementById("cameraDownBtn");
    const zoomInBtn = document.getElementById("zoomInBtn");
    const zoomOutBtn = document.getElementById("zoomOutBtn");
    const resetViewBtn = document.getElementById("resetViewBtn");
    const setCurrentViewBtn = document.getElementById("setCurrentViewBtn");
    const createCenterHotspotBtn = document.getElementById("createCenterHotspotBtn");
    const fullscreenBtn = document.getElementById("fullscreenBtn");

    const hotspotModal = document.getElementById("hotspotModal");
    const hotspotModalTitle = document.getElementById("hotspotModalTitle");
    const closeHotspotModal = document.getElementById("closeHotspotModal");
    const cancelHotspotBtn = document.getElementById("cancelHotspotBtn");
    const saveHotspotBtn = document.getElementById("saveHotspotBtn");
    const deleteHotspotBtn = document.getElementById("deleteHotspotBtn");

    const hotspotType = document.getElementById("hotspotType");
    const hotspotLabel = document.getElementById("hotspotLabel");
    const hotspotTooltip = document.getElementById("hotspotTooltip");
    const hotspotTitle = document.getElementById("hotspotTitle");
    const hotspotDescription = document.getElementById("hotspotDescription");
    const hotspotTargetScene = document.getElementById("hotspotTargetScene");
    const hotspotSelectedIconInput = document.getElementById("hotspotSelectedIcon");
    const hotspotVariant = document.getElementById("hotspotVariant");
    const hotspotSize = document.getElementById("hotspotSize");
    const hotspotRotation = document.getElementById("hotspotRotation");
    const hotspotAnchor = document.getElementById("hotspotAnchor");
    const hotspotOffsetX = document.getElementById("hotspotOffsetX");
    const hotspotOffsetY = document.getElementById("hotspotOffsetY");

    const hotspotPanels = document.querySelectorAll(".hotspot-type-panel");
    const hotspotIconOptions = document.querySelectorAll(".hotspot-icon-option");

    const hotspotImageUpload = document.getElementById("hotspotImageUpload");
    const hotspotImageUrl = document.getElementById("hotspotImageUrl");

    const hotspotProductTitle = document.getElementById("hotspotProductTitle");
    const hotspotProductDescription = document.getElementById("hotspotProductDescription");
    const hotspotImageUploadProduct = document.getElementById("hotspotImageUploadProduct");
    const hotspotImageUrlProduct = document.getElementById("hotspotImageUrlProduct");
    const hotspotPrice = document.getElementById("hotspotPrice");
    const hotspotBadge = document.getElementById("hotspotBadge");
    const hotspotButtonText = document.getElementById("hotspotButtonText");
    const hotspotCtaUrl = document.getElementById("hotspotCtaUrl");
    const hotspotSiteName = document.getElementById("hotspotSiteName");

    const hotspotWhatsapp = document.getElementById("hotspotWhatsapp");
    const hotspotWhatsappMessage = document.getElementById("hotspotWhatsappMessage");

    const hotspotPhone = document.getElementById("hotspotPhone");
    const hotspotEmail = document.getElementById("hotspotEmail");

    const hotspotWebsiteTitle = document.getElementById("hotspotWebsiteTitle");
    const hotspotWebsiteButtonText = document.getElementById("hotspotWebsiteButtonText");
    const hotspotWebsiteUrl = document.getElementById("hotspotWebsiteUrl");
    const hotspotFloorTargetScene = document.getElementById("hotspotFloorTargetScene");
    const hotspotFloorDirection = document.getElementById("hotspotFloorDirection");
    const hotspotFloorName = document.getElementById("hotspotFloorName");
    const hotspotFloorNumber = document.getElementById("hotspotFloorNumber");
    const hotspotFloorDestination = document.getElementById("hotspotFloorDestination");
    const hotspotPdfTitle = document.getElementById("hotspotPdfTitle");
    const hotspotPdfDescription = document.getElementById("hotspotPdfDescription");
    const hotspotPdfFile = document.getElementById("hotspotPdfFile");
    const hotspotPdfUrl = document.getElementById("hotspotPdfUrl");
    const hotspotPdfDownload = document.getElementById("hotspotPdfDownload");
    const hotspotVideoTitle = document.getElementById("hotspotVideoTitle");
    const hotspotVideoDisplayMode = document.getElementById("hotspotVideoDisplayMode");
    const hotspotVideoWidth = document.getElementById("hotspotVideoWidth");
    const hotspotVideoHeight = document.getElementById("hotspotVideoHeight");
    const hotspotDoorTargetScene = document.getElementById("hotspotDoorTargetScene");
    const hotspotDoorDirection = document.getElementById("hotspotDoorDirection");
    const hotspotDoorWidth = document.getElementById("hotspotDoorWidth");
    const hotspotDoorHeight = document.getElementById("hotspotDoorHeight");
    const hotspotDoorLabel = document.getElementById("hotspotDoorLabel");
    const hotspotVideoDescription = document.getElementById("hotspotVideoDescription");
    const hotspotVideoFile = document.getElementById("hotspotVideoFile");
    const hotspotVideoUrl = document.getElementById("hotspotVideoUrl");
    const hotspotVideoPoster = document.getElementById("hotspotVideoPoster");
    const hotspotVideoAutoplay = document.getElementById("hotspotVideoAutoplay");
    const hotspotVideoMuted = document.getElementById("hotspotVideoMuted");
    const hotspotVideoLoop = document.getElementById("hotspotVideoLoop");

    const hotspotEditHud = document.getElementById("hotspotEditHud");
    const hudMoveLeft = document.getElementById("hudMoveLeft");
    const hudMoveUp = document.getElementById("hudMoveUp");
    const hudMoveDown = document.getElementById("hudMoveDown");
    const hudMoveRight = document.getElementById("hudMoveRight");
    const hudSizeMinus = document.getElementById("hudSizeMinus");
    const hudSizePlus = document.getElementById("hudSizePlus");
    const hudRotateMinus = document.getElementById("hudRotateMinus");
    const hudRotatePlus = document.getElementById("hudRotatePlus");
    const hudSaveHotspot = document.getElementById("hudSaveHotspot");

    const hotspotInfoPopup = document.getElementById("hotspotInfoPopup");
    const hotspotPopupClose = document.getElementById("hotspotPopupClose");
    const hotspotPopupMedia = document.getElementById("hotspotPopupMedia");
    const hotspotPopupBadge = document.getElementById("hotspotPopupBadge");
    const hotspotPopupTitle = document.getElementById("hotspotPopupTitle");
    const hotspotPopupDescription = document.getElementById("hotspotPopupDescription");
    const hotspotPopupPrice = document.getElementById("hotspotPopupPrice");
    const hotspotPopupSiteName = document.getElementById("hotspotPopupSiteName");
    const hotspotPopupAction = document.getElementById("hotspotPopupAction");
    const hotspotPopupWhatsapp = document.getElementById("hotspotPopupWhatsapp");
    const hotspotPopupContact = document.getElementById("hotspotPopupContact");

    const tourTitleText = document.getElementById("tourTitleText");
    const tourTitleInput = document.getElementById("tourTitleInput");
    const tourTitleSaving = document.getElementById("tourTitleSaving");

    let currentSceneId = null;
    let currentTool = "move";
    let pendingHotspotPosition = null;
    let selectedLibraryIcon = "default";
    let isSceneTransitioning = false;
    let activeLayerKey = "A";
    let editingHotspotId = null;
    let floorGroupItems = [];
    let floorGroupEditorReady = false;
    let selectedHotspotId = null;
    let selectedHotspotDraft = null;
    let draggedSceneId = null;
    let tourTitleSaveTimeout = null;
    let lastSavedTourTitle = tourTitleInput?.value || "";
    let modalPreviewObjectUrl = "";

    const viewers = { A: null, B: null };
    const layerViews = { A: null, B: null };
    const layerScenes = { A: null, B: null };
    const tripodLogoHotspots = { A: null, B: null };

    function getLayerEl(key) {
        return key === "A" ? layerAEl : layerBEl;
    }

    function getMountEl(key) {
        return key === "A" ? mountAEl : mountBEl;
    }

    function getStandbyLayerKey() {
        return activeLayerKey === "A" ? "B" : "A";
    }

    function getCSRFToken() {
        const name = "csrftoken";
        const cookies = document.cookie.split(";").map(c => c.trim());

        for (const cookie of cookies) {
            if (cookie.startsWith(name + "=")) {
                return decodeURIComponent(cookie.substring(name.length + 1));
            }
        }

        return "";
    }

    function radiansToDegrees(rad) {
        return rad * 180 / Math.PI;
    }

    function getSurfaceReferenceFovDeg() {
        const view = layerViews[activeLayerKey];
        if (view && typeof view.fov === "function") {
            return Number(radiansToDegrees(view.fov()).toFixed(3));
        }
        return Number(activeScene?.hfov_default || 100);
    }

    function degreesToRadians(deg) {
        return deg * Math.PI / 180;
    }

    function normalizeAngle(rad) {
        while (rad > Math.PI) rad -= 2 * Math.PI;
        while (rad < -Math.PI) rad += 2 * Math.PI;
        return rad;
    }

    function sortScenesData() {
        scenesData = scenesData.slice().sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
    }

    function findScene(sceneId) {
        return scenesData.find(scene => String(scene.id) === String(sceneId));
    }

    function setActiveTool(toolName) {
        currentTool = toolName;

        toolButtons.forEach(btn => {
            btn.classList.toggle("active", btn.dataset.tool === toolName);
        });
    }

    function setActiveCard(sceneId) {
        document.querySelectorAll(".scene-card").forEach(card => {
            card.classList.toggle("active", String(card.dataset.sceneId) === String(sceneId));
        });
    }

    function isScenePublic(scene) {
        // Anciennes scènes sans champ is_public restent visibles par défaut.
        return scene?.is_public !== false;
    }

    function syncScenePublicUI(scene) {
        const visible = isScenePublic(scene);

        if (scenePublicInput) scenePublicInput.checked = visible;

        if (scenePublicStatus) {
            scenePublicStatus.textContent = visible ? "Visible dans le preview" : "Masquée dans le preview";
            scenePublicStatus.classList.toggle("is-public", visible);
            scenePublicStatus.classList.toggle("is-private", !visible);
        }

        if (scenePublicHelp) {
            scenePublicHelp.textContent = visible
                ? "Cette scène apparaîtra dans le preview public et dans la liste des scènes."
                : "Cette scène reste disponible dans le builder, mais elle sera cachée dans le preview public.";
        }

        if (sceneVisibilityPreview) {
            sceneVisibilityPreview.textContent = visible ? "Public" : "Privé";
            sceneVisibilityPreview.classList.toggle("is-public", visible);
            sceneVisibilityPreview.classList.toggle("is-private", !visible);
        }
    }

    function updateScenePublicDraft() {
        if (!currentSceneId || !scenePublicInput) return;

        const visible = Boolean(scenePublicInput.checked);

        scenesData = scenesData.map(scene =>
            String(scene.id) === String(currentSceneId)
                ? { ...scene, is_public: visible }
                : scene
        );

        syncScenePublicUI(findScene(currentSceneId));
        renderSceneList();
    }

    function syncInputsFromView() {
        const currentView = layerViews[activeLayerKey];
        if (!currentView) return;

        if (yawInput) yawInput.value = radiansToDegrees(currentView.yaw()).toFixed(2);
        if (pitchInput) pitchInput.value = radiansToDegrees(currentView.pitch()).toFixed(2);
        if (hfovInput) hfovInput.value = radiansToDegrees(currentView.fov()).toFixed(2);
    }

    function setCurrentViewToInputs() {
        const currentView = layerViews[activeLayerKey];
        if (!currentView) return;

        const yawDeg = radiansToDegrees(currentView.yaw());
        const pitchDeg = radiansToDegrees(currentView.pitch());
        const fovDeg = radiansToDegrees(currentView.fov());

        if (yawInput) yawInput.value = yawDeg.toFixed(2);
        if (pitchInput) pitchInput.value = pitchDeg.toFixed(2);
        if (hfovInput) hfovInput.value = fovDeg.toFixed(2);

        const activeScene = findScene(currentSceneId);
        if (activeScene) {
            activeScene.yaw_default = yawDeg;
            activeScene.pitch_default = pitchDeg;
            activeScene.hfov_default = fovDeg;
        }

        notify("Vue actuelle appliquée aux champs.", "success");
    }

    function applyInputsToCurrentView() {
        const currentView = layerViews[activeLayerKey];
        if (!currentView) return;

        const yaw = degreesToRadians(parseFloat(yawInput?.value || 0));
        const pitch = degreesToRadians(parseFloat(pitchInput?.value || 0));
        const fov = degreesToRadians(parseFloat(hfovInput?.value || 100));

        currentView.setParameters({ yaw, pitch, fov }, { transitionDuration: 400 });
    }

    function getCenterViewCoordinates() {
        const currentView = layerViews[activeLayerKey];
        if (!currentView) return null;

        return {
            yaw: currentView.yaw(),
            pitch: currentView.pitch(),
            fov: currentView.fov(),
        };
    }


    // ============================================================
    // FIX HOTSPOT OWNER SCENE
    // Objectif: créer/éditer un hotspot sur la vraie scène active,
    // même si currentSceneId est resté bloqué sur l'ancienne scène.
    // ============================================================
    function normalizeBuilderSceneId(value) {
        if (value === null || value === undefined) return "";
        return String(value).trim();
    }

    function findBuilderSceneById(sceneId) {
        const safeId = normalizeBuilderSceneId(sceneId);
        if (!safeId || !Array.isArray(scenesData)) return null;

        return scenesData.find(scene => {
            return normalizeBuilderSceneId(scene.id) === safeId ||
                normalizeBuilderSceneId(scene.scene_id) === safeId ||
                normalizeBuilderSceneId(scene.uuid) === safeId ||
                normalizeBuilderSceneId(scene.slug) === safeId;
        }) || null;
    }

    function findSceneIdOwningHotspot(hotspotId) {
        const safeHotspotId = normalizeBuilderSceneId(hotspotId);
        if (!safeHotspotId || !Array.isArray(scenesData)) return "";

        const ownerScene = scenesData.find(scene => {
            const hotspots = Array.isArray(scene.hotspots) ? scene.hotspots : [];
            return hotspots.some(hotspot => normalizeBuilderSceneId(hotspot.id) === safeHotspotId);
        });

        return ownerScene ? normalizeBuilderSceneId(ownerScene.id) : "";
    }

    function getActiveBuilderSceneIdFromDom() {
        const selectors = [
            ".scene-card.active[data-scene-id]",
            ".scene-card.is-active[data-scene-id]",
            ".scene-card.selected[data-scene-id]",
            ".scene-card.active[data-id]",
            ".scene-card.is-active[data-id]",
            ".scene-card.selected[data-id]",
            ".scene-card-wrap.active[data-scene-id]",
            ".scene-card-wrap.is-active[data-scene-id]",
            ".scene-card-wrap.selected[data-scene-id]",
            "[data-builder-scene-card].active[data-scene-id]",
            "[data-builder-scene-card].is-active[data-scene-id]",
            "[data-scene-id][aria-selected='true']",
            "[data-id][aria-selected='true']"
        ];

        for (const selector of selectors) {
            const element = document.querySelector(selector);
            if (!element) continue;

            const rawId =
                element.dataset.sceneId ||
                element.dataset.id ||
                element.getAttribute("data-scene-id") ||
                element.getAttribute("data-id");

            const safeId = normalizeBuilderSceneId(rawId);

            if (safeId && findBuilderSceneById(safeId)) {
                return safeId;
            }
        }

        return "";
    }

    function getHotspotOwnerSceneId() {
        const domSceneId = getActiveBuilderSceneIdFromDom();

        if (domSceneId && findBuilderSceneById(domSceneId)) {
            currentSceneId = domSceneId;
            document.documentElement.dataset.builderCurrentSceneId = domSceneId;
            return domSceneId;
        }

        const currentId = normalizeBuilderSceneId(currentSceneId);

        if (currentId && findBuilderSceneById(currentId)) {
            document.documentElement.dataset.builderCurrentSceneId = currentId;
            return currentId;
        }

        const firstSceneId = normalizeBuilderSceneId(scenesData?.[0]?.id);

        if (firstSceneId) {
            currentSceneId = firstSceneId;
            document.documentElement.dataset.builderCurrentSceneId = firstSceneId;
            return firstSceneId;
        }

        return "";
    }

    function setBuilderCurrentScene(sceneId, options = {}) {
        const scene = findBuilderSceneById(sceneId);
        if (!scene) return "";

        currentSceneId = normalizeBuilderSceneId(scene.id);
        document.documentElement.dataset.builderCurrentSceneId = currentSceneId;

        setActiveCard(scene.id);

        if (sceneTitleInput) sceneTitleInput.value = scene.title || "";
        if (yawInput) yawInput.value = scene.yaw_default ?? 0;
        if (pitchInput) pitchInput.value = scene.pitch_default ?? 0;
        if (hfovInput) hfovInput.value = scene.hfov_default ?? 100;
        syncTripodLogoInputs(scene);

        syncScenePublicUI(scene);

        if (viewerSceneTitle) viewerSceneTitle.textContent = scene.title || "Untitled Scene";
        if (activeSceneLabel) activeSceneLabel.textContent = scene.title || "Scene preview";

        if (!options.skipTargetRefresh && typeof refreshTargetSceneOptions === "function") {
            refreshTargetSceneOptions(hotspotTargetScene?.value || "");
        }

        return currentSceneId;
    }

    function installBuilderSceneCaptureOnce() {
        if (window.__builderSceneCaptureInstalled) return;
        window.__builderSceneCaptureInstalled = true;

        document.addEventListener("click", function (event) {
            const sceneElement = event.target.closest(
                ".scene-card[data-scene-id], .scene-card[data-id], .scene-card-wrap[data-scene-id], .scene-card-wrap[data-id], [data-builder-scene-card][data-scene-id], [data-builder-scene-card][data-id]"
            );

            if (!sceneElement) return;

            const rawId =
                sceneElement.dataset.sceneId ||
                sceneElement.dataset.id ||
                sceneElement.getAttribute("data-scene-id") ||
                sceneElement.getAttribute("data-id");

            const safeId = normalizeBuilderSceneId(rawId);

            if (safeId && findBuilderSceneById(safeId)) {
                setBuilderCurrentScene(safeId, { skipTargetRefresh: true });
            }
        }, true);
    }

    function refreshTargetSceneOptions(selectedValue = "") {
        if (!hotspotTargetScene) return;

        const ownerSceneId = getHotspotOwnerSceneId();
        const safeSelectedValue = normalizeBuilderSceneId(selectedValue || hotspotTargetScene.value || "");

        hotspotTargetScene.innerHTML = "";

        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "Select a destination scene";
        hotspotTargetScene.appendChild(placeholder);

        scenesData.forEach(scene => {
            const sceneId = normalizeBuilderSceneId(scene.id);
            const option = document.createElement("option");

            option.value = sceneId;

            if (sceneId === ownerSceneId) {
                option.textContent = `${scene.title || "Scene"} — current scene`;
                option.disabled = true;
            } else {
                option.textContent = scene.title || "Scene";
            }

            if (safeSelectedValue && safeSelectedValue === sceneId && sceneId !== ownerSceneId) {
                option.selected = true;
            }

            hotspotTargetScene.appendChild(option);
            if (hotspotFloorTargetScene) hotspotFloorTargetScene.appendChild(option.cloneNode(true));
            if (hotspotDoorTargetScene) hotspotDoorTargetScene.appendChild(option.cloneNode(true));
        });

        if (
            safeSelectedValue &&
            safeSelectedValue !== ownerSceneId &&
            findBuilderSceneById(safeSelectedValue)
        ) {
            hotspotTargetScene.value = safeSelectedValue;
        } else {
            hotspotTargetScene.value = "";
        }
    }

    function getHotspotDisplay(hotspot) {
        return hotspot?.payload?.display || {};
    }

    function resolveHotspotIconSrc(iconName) {
        return getIconSrc(iconName);
    }

    function getTypeMeta(type) {
        const meta = {
            floor: { kicker: "Property levels", title: "Floor Navigation", description: "Move beautifully between floors and levels." },
            pdf: { kicker: "Document", title: "PDF Hotspot", description: "Open a brochure or document inside the tour." },
            video: { kicker: "Media", title: "Video Hotspot", description: "Play as a classic hotspot or directly on a wall screen." },
            door: { kicker: "Immersive navigation", title: "Interactive Door", description: "Trace a clickable door and animate its opening." },
            navigate: {
                kicker: "Scene navigation",
                title: "Navigation Hotspot",
                description: "Use this hotspot to move from one panorama scene to another.",
                iconName: "arrowright",
            },
            info: {
                kicker: "Information point",
                title: "Info Hotspot",
                description: "Show useful information, description, photo or detail inside the virtual tour.",
                iconName: "info",
            },
            product: {
                kicker: "Product card",
                title: "Product Hotspot",
                description: "Display a product card with image, price, badge and action button.",
                iconName: "product",
            },
            whatsapp: {
                kicker: "Direct contact",
                title: "WhatsApp Hotspot",
                description: "Let visitors contact the business directly through WhatsApp.",
                iconName: "whatsapp",
            },
            phone: {
                kicker: "Call action",
                title: "Phone Hotspot",
                description: "Let visitors call the business directly from the virtual tour.",
                iconName: "phone",
            },
            email: {
                kicker: "Email action",
                title: "Email Hotspot",
                description: "Let visitors send an email from the virtual tour.",
                iconName: "info",
            },
            cta: {
                kicker: "External link",
                title: "Website / CTA Hotspot",
                description: "Send visitors to a website, booking page, catalog or external link.",
                iconName: "website",
            },
            custom: {
                kicker: "Custom action",
                title: "Custom Hotspot",
                description: "Create a custom hotspot using your own label and tooltip.",
                iconName: "cta",
            },
        };

        return meta[type] || meta.custom;
    }

    function decorateHotspotIconOptions() {
        hotspotIconOptions.forEach((btn) => {
            const iconName = btn.dataset.icon || "default";
            const label = btn.textContent.trim() || iconName;
            const iconSrc = getIconSrc(iconName);

            btn.innerHTML = "";

            if (iconSrc) {
                const img = document.createElement("img");
                img.src = iconSrc;
                img.alt = label;
                btn.appendChild(img);
            }

            const span = document.createElement("span");
            span.textContent = label;
            btn.appendChild(span);
        });
    }

    function ensureModalHero() {
        const modalBody = hotspotModal?.querySelector(".modal-body");
        if (!modalBody) return null;

        let hero = modalBody.querySelector("#hotspotModalHero");
        if (hero) return hero;

        hero = document.createElement("div");
        hero.id = "hotspotModalHero";
        hero.className = "modal-type-hero";

        hero.innerHTML = `
            <div class="modal-type-hero-inner">
                <div class="min-w-0">
                    <div class="modal-type-kicker" id="modalTypeKicker">Hotspot</div>
                    <div class="modal-type-title" id="modalTypeTitle">Hotspot</div>
                    <div class="modal-type-description" id="modalTypeDescription"></div>
                </div>
                <div class="modal-type-icon" id="modalTypeIcon"></div>
            </div>
        `;

        modalBody.prepend(hero);
        return hero;
    }

    function updateModalHero(type) {
        ensureModalHero();

        const meta = getTypeMeta(type);
        const kicker = document.getElementById("modalTypeKicker");
        const title = document.getElementById("modalTypeTitle");
        const description = document.getElementById("modalTypeDescription");
        const icon = document.getElementById("modalTypeIcon");

        if (kicker) kicker.textContent = meta.kicker;
        if (title) title.textContent = meta.title;
        if (description) description.textContent = meta.description;

        if (icon) {
            const iconSrc = getIconSrc(meta.iconName || "default");
            icon.innerHTML = "";

            if (iconSrc) {
                const img = document.createElement("img");
                img.src = iconSrc;
                img.alt = meta.title;
                icon.appendChild(img);
            }
        }
    }

    function updateHotspotTypePanels(type) {
        hotspotPanels.forEach(panel => {
            panel.classList.toggle("active", panel.dataset.panel === type);
        });

        updateModalHero(type);
        renderHotspotLivePreview();
    }

    function activateIconOption(iconName) {
        hotspotIconOptions.forEach(btn => {
            btn.classList.toggle("active", btn.dataset.icon === iconName);
        });

        if (hotspotSelectedIconInput) hotspotSelectedIconInput.value = iconName;
        selectedLibraryIcon = iconName;
        renderHotspotLivePreview();
    }

    function applyTypeDefaults(type) {
        if (!hotspotVariant) return;

        if (type === "navigate") {
            hotspotVariant.value = "pin";
            activateIconOption("default");
        } else if (type === "info") {
            hotspotVariant.value = "label";
            activateIconOption("info");
        } else if (type === "product") {
            hotspotVariant.value = "label";
            activateIconOption("product");
        } else if (type === "whatsapp") {
            hotspotVariant.value = "pin";
            activateIconOption("whatsapp");
        } else if (type === "phone") {
            hotspotVariant.value = "pin";
            activateIconOption("phone");
        } else if (type === "email") {
            hotspotVariant.value = "pin";
            activateIconOption("info");
        } else if (type === "cta") {
            hotspotVariant.value = "pin";
            activateIconOption("website");
        } else if (type === "custom") {
            hotspotVariant.value = "pin";
            activateIconOption("cta");
        }

        renderHotspotLivePreview();
    }

    function showHotspotHud() {
        hotspotEditHud?.classList.remove("hidden");
    }

    function hideHotspotHud() {
        hotspotEditHud?.classList.add("hidden");
    }

    function closeHotspotInfoPopup() {
        hotspotInfoPopup?.classList.add("hidden");
    }

    function cloneHotspotForDraft(hotspot) {
        return JSON.parse(JSON.stringify(hotspot));
    }

    function updateSelectedHotspotDraft(mutator) {
        if (!selectedHotspotDraft) return;

        mutator(selectedHotspotDraft);

        scenesData = scenesData.map(scene => ({
            ...scene,
            hotspots: (scene.hotspots || []).map(h =>
                String(h.id) === String(selectedHotspotDraft.id) ? selectedHotspotDraft : h
            ),
        }));

        const activeScene = findScene(currentSceneId);
        if (activeScene) buildLayerScene(activeLayerKey, activeScene);
    }

    function setPopupImage(imageUrl, title) {
        if (!hotspotPopupMedia) return;

        hotspotPopupMedia.innerHTML = "";

        if (imageUrl) {
            const img = document.createElement("img");
            img.src = imageUrl;
            img.alt = title || "Hotspot";
            hotspotPopupMedia.appendChild(img);
            return;
        }

        const placeholder = document.createElement("div");
        placeholder.style.cssText = `
            min-height: 190px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #f8fafc, #e0f2fe);
            color: #64748b;
            font-size: 13px;
            font-weight: 900;
        `;
        placeholder.textContent = "No image";
        hotspotPopupMedia.appendChild(placeholder);
    }

    function openHotspotInfoPopup(hotspot) {
        if (!hotspotInfoPopup) return;

        const content = hotspot.payload?.content || {};
        const imageUrl = content.image_url || hotspot.ad_image_url || "";
        const ctaUrl = content.cta_url || "";
        const buttonText = content.button_text || "Open";
        const price = content.price || "";
        const badge = content.badge || "";
        const siteName = content.site_name || "";
        const whatsappNumber = content.whatsapp_number || "";
        const whatsappMessage = content.whatsapp_message || "Bonjour, je veux commander ce produit";
        const phone = content.phone || "";
        const email = content.email || "";
        const title = hotspot.title || hotspot.label || "Hotspot";

        setPopupImage(imageUrl, title);

        if (hotspotPopupTitle) hotspotPopupTitle.textContent = title;
        if (hotspotPopupDescription) hotspotPopupDescription.textContent = hotspot.description || hotspot.tooltip_text || "";

        if (badge) {
            hotspotPopupBadge.textContent = badge;
            hotspotPopupBadge.classList.remove("hidden");
        } else {
            hotspotPopupBadge.textContent = "";
            hotspotPopupBadge.classList.add("hidden");
        }

        if (price) {
            hotspotPopupPrice.textContent = price;
            hotspotPopupPrice.classList.remove("hidden");
        } else {
            hotspotPopupPrice.textContent = "";
            hotspotPopupPrice.classList.add("hidden");
        }

        if (siteName) {
            hotspotPopupSiteName.textContent = siteName;
            hotspotPopupSiteName.classList.remove("hidden");
        } else {
            hotspotPopupSiteName.textContent = "";
            hotspotPopupSiteName.classList.add("hidden");
        }

        if (ctaUrl) {
            hotspotPopupAction.href = ctaUrl;
            hotspotPopupAction.textContent = buttonText || "Open";
            hotspotPopupAction.classList.remove("hidden");
        } else {
            hotspotPopupAction.removeAttribute("href");
            hotspotPopupAction.classList.add("hidden");
        }

        if (whatsappNumber) {
            const cleanNumber = whatsappNumber.replace(/[^\d]/g, "");
            hotspotPopupWhatsapp.href = `https://wa.me/${cleanNumber}?text=${encodeURIComponent(whatsappMessage)}`;
            hotspotPopupWhatsapp.textContent = "WhatsApp Order";
            hotspotPopupWhatsapp.classList.remove("hidden");
        } else {
            hotspotPopupWhatsapp.removeAttribute("href");
            hotspotPopupWhatsapp.classList.add("hidden");
        }

        if (phone) {
            hotspotPopupContact.href = `tel:${phone}`;
            hotspotPopupContact.textContent = "Call";
            hotspotPopupContact.classList.remove("hidden");
        } else if (email) {
            hotspotPopupContact.href = `mailto:${email}`;
            hotspotPopupContact.textContent = "Email";
            hotspotPopupContact.classList.remove("hidden");
        } else {
            hotspotPopupContact.removeAttribute("href");
            hotspotPopupContact.classList.add("hidden");
        }

        hotspotInfoPopup.classList.remove("hidden");
    }

    function buildHotspotElement(hotspot) {
        const display = getHotspotDisplay(hotspot);

        const variant = display.variant || "pin";
        const size = Number(display.size || 56);
        const rotation = Number(display.rotation || 0);
        const offsetX = Number(display.offset_x || 0);
        const offsetY = Number(display.offset_y || 0);
        const anchor = display.anchor || "bottom";

        const el = document.createElement("div");
        el.className = `marzipano-hotspot marzipano-hotspot-marker variant-${variant} hotspot-anchor-${anchor} hotspot-type-${hotspot.type || "custom"}`;
        el.title = hotspot.label || "Hotspot";
        el.dataset.hotspotId = hotspot.id;

        if (String(hotspot.id) === String(selectedHotspotId)) {
            el.classList.add("is-selected");
        }

        el.style.width = `${size}px`;
        el.style.height = variant === "label" ? "auto" : `${size}px`;
        el.style.transform = `translate(${offsetX}px, ${offsetY}px) rotate(${rotation}deg)`;

        const img = document.createElement("img");
        const iconName = hotspot.selected_icon || "default";
        img.src = resolveHotspotIconSrc(iconName);
        img.alt = hotspot.label || "Hotspot";
        img.className = "marzipano-hotspot-icon";

        if (variant === "label") {
            const text = document.createElement("span");
            text.textContent = hotspot.label || "Hotspot";
            el.appendChild(img);
            el.appendChild(text);
        } else {
            el.appendChild(img);
        }

        return el;
    }

    function ensureViewer(key) {
        const mount = getMountEl(key);
        if (!mount) return null;

        mount.innerHTML = "";

        viewers[key] = new Marzipano.Viewer(mount, {
            controls: { mouseViewMode: "drag" },
        });

        return viewers[key];
    }

    function createSceneHotspots(scene, layerKey) {
        if (!scene.hotspots || !layerScenes[layerKey]) return;

        scene.hotspots.forEach(hotspot => {
            const el = buildHotspotElement(hotspot);

            el.addEventListener("click", async (e) => {
                e.stopPropagation();

                selectedHotspotId = hotspot.id;
                selectedHotspotDraft = cloneHotspotForDraft(hotspot);
                showHotspotHud();

                if (hotspot.type === "navigate" && hotspot.target_scene && currentTool !== "move") {
                    if (!isSceneTransitioning) {
                        await navigateThroughHotspot(hotspot);
                    }
                    return;
                }

                if (["info", "product", "cta", "whatsapp", "phone", "email", "custom"].includes(hotspot.type)) {
                    openHotspotInfoPopup(hotspot);
                }

                if (currentTool === "move") {
                    openEditHotspotModal(hotspot);
                }
            });

            layerScenes[layerKey].hotspotContainer().createHotspot(el, {
                yaw: hotspot.yaw,
                pitch: hotspot.pitch,
            });
        });
    }

    function getTripodLogoSettings(scene) {
        const settings = scene?.tripod_logo || {};
        return {
            enabled: Boolean(settings.enabled),
            size: Math.max(72, Math.min(320, Number(settings.size || 132))),
            yaw: Math.max(-180, Math.min(180, Number(settings.yaw || 0))),
            pitch: Math.max(-89.5, Math.min(89.5, Number(settings.pitch ?? 88.5))),
            offsetX: Math.max(-250, Math.min(250, Number(settings.offset_x || 0))),
            offsetY: Math.max(-250, Math.min(250, Number(settings.offset_y || 0))),
            rotation: Math.max(-180, Math.min(180, Number(settings.rotation || 0))),
            tiltX: Math.max(-70, Math.min(70, Number(settings.tilt_x || 0))),
            tiltY: Math.max(-70, Math.min(70, Number(settings.tilt_y || 0))),
            radius: Math.max(350, Math.min(2400, Number(settings.radius || 900))),
        };
    }

    function tripodLogoExtraTransforms(settings) {
        return [
            `translateX(${settings.offsetX}px)`,
            `translateY(${settings.offsetY}px)`,
            `rotateZ(${settings.rotation}deg)`,
            `rotateX(${settings.tiltX}deg)`,
            `rotateY(${settings.tiltY}deg)`,
        ].join(" ");
    }

    function getTripodLogoRecord(layerKey) {
        return tripodLogoHotspots[layerKey] || null;
    }

    function destroyTripodLogo(layerKey) {
        const record = getTripodLogoRecord(layerKey);
        if (!record) return;
        try { record.hotspot?.destroy?.(); } catch (error) { console.debug("TRIPOD_LOGO_DESTROY", error); }
        tripodLogoHotspots[layerKey] = null;
    }

    function writeTripodInputs(settings) {
        if (tripodLogoEnabled) tripodLogoEnabled.checked = settings.enabled;
        if (tripodLogoSize) tripodLogoSize.value = String(Math.round(settings.size));
        if (tripodLogoYaw) tripodLogoYaw.value = settings.yaw.toFixed(2);
        if (tripodLogoPitch) tripodLogoPitch.value = settings.pitch.toFixed(2);
        if (tripodLogoOffsetX) tripodLogoOffsetX.value = String(Math.round(settings.offsetX));
        if (tripodLogoOffsetY) tripodLogoOffsetY.value = String(Math.round(settings.offsetY));
        if (tripodLogoRotation) tripodLogoRotation.value = settings.rotation.toFixed(1);
        if (tripodLogoTiltX) tripodLogoTiltX.value = settings.tiltX.toFixed(1);
        if (tripodLogoTiltY) tripodLogoTiltY.value = settings.tiltY.toFixed(1);
        if (tripodLogoRadius) tripodLogoRadius.value = String(Math.round(settings.radius));
    }

    function writeTripodSettingsToScene(scene, settings) {
        scene.tripod_logo = {
            enabled: Boolean(settings.enabled),
            size: Math.round(settings.size),
            yaw: settings.yaw,
            pitch: settings.pitch,
            offset_x: Math.round(settings.offsetX),
            offset_y: Math.round(settings.offsetY),
            rotation: settings.rotation,
            tilt_x: settings.tiltX,
            tilt_y: settings.tiltY,
            radius: Math.round(settings.radius),
        };
    }

    function settingsFromTripodInputs() {
        return {
            enabled: Boolean(tripodLogoEnabled?.checked),
            size: Math.max(72, Math.min(320, Number(tripodLogoSize?.value || 132))),
            yaw: Math.max(-180, Math.min(180, Number(tripodLogoYaw?.value || 0))),
            pitch: Math.max(-89.5, Math.min(89.5, Number(tripodLogoPitch?.value || 88.5))),
            offsetX: Math.max(-250, Math.min(250, Number(tripodLogoOffsetX?.value || 0))),
            offsetY: Math.max(-250, Math.min(250, Number(tripodLogoOffsetY?.value || 0))),
            rotation: Math.max(-180, Math.min(180, Number(tripodLogoRotation?.value || 0))),
            tiltX: Math.max(-70, Math.min(70, Number(tripodLogoTiltX?.value || 0))),
            tiltY: Math.max(-70, Math.min(70, Number(tripodLogoTiltY?.value || 0))),
            radius: Math.max(350, Math.min(2400, Number(tripodLogoRadius?.value || 900))),
        };
    }

    function tripodSettingsMatch(expected, persisted) {
        if (!expected || !persisted) return false;
        const close = (left, right, tolerance = 0.001) =>
            Number.isFinite(Number(left)) &&
            Number.isFinite(Number(right)) &&
            Math.abs(Number(left) - Number(right)) <= tolerance;

        return Boolean(expected.enabled) === Boolean(persisted.enabled)
            && Math.round(expected.size) === Math.round(persisted.size)
            && close(expected.yaw, persisted.yaw)
            && close(expected.pitch, persisted.pitch)
            && Math.round(expected.offsetX) === Math.round(persisted.offsetX)
            && Math.round(expected.offsetY) === Math.round(persisted.offsetY)
            && close(expected.rotation, persisted.rotation)
            && close(expected.tiltX, persisted.tiltX)
            && close(expected.tiltY, persisted.tiltY)
            && Math.round(expected.radius) === Math.round(persisted.radius);
    }

    function applyTripodRecordVisual(record, settings) {
        if (!record) return;
        record.node.style.setProperty("--builder-tripod-logo-size", `${settings.size}px`);
        record.hotspot.setPosition({
            yaw: degreesToRadians(settings.yaw),
            pitch: degreesToRadians(settings.pitch),
        });
        record.hotspot.setPerspective({
            radius: settings.radius,
            extraTransforms: tripodLogoExtraTransforms(settings),
        });
    }

    function bindTripodLogoEditor(node, layerKey) {
        const resizeHandle = node.querySelector(".builder-tripod-logo-resize");
        const rotateHandle = node.querySelector(".builder-tripod-logo-rotate");

        const stop = (event) => {
            event.preventDefault();
            event.stopPropagation();
        };

        node.addEventListener("click", stop);
        node.addEventListener("dblclick", stop);
        node.addEventListener("wheel", stop, { passive: false });

        node.addEventListener("pointerdown", (event) => {
            if (event.target === resizeHandle || event.target === rotateHandle) return;
            stop(event);
            const view = layerViews[layerKey];
            const layerEl = getLayerEl(layerKey);
            const record = getTripodLogoRecord(layerKey);
            const scene = findScene(currentSceneId);
            if (!view || !layerEl || !record || !scene) return;

            node.classList.add("is-dragging");
            try { node.setPointerCapture(event.pointerId); } catch (_) {}

            const move = (moveEvent) => {
                stop(moveEvent);
                const rect = layerEl.getBoundingClientRect();
                const x = Math.max(0, Math.min(rect.width, moveEvent.clientX - rect.left));
                const y = Math.max(0, Math.min(rect.height, moveEvent.clientY - rect.top));
                const coords = view.screenToCoordinates({ x, y });
                if (!coords) return;
                const settings = getTripodLogoSettings(scene);
                settings.enabled = true;
                settings.yaw = Math.max(-180, Math.min(180, radiansToDegrees(coords.yaw)));
                settings.pitch = Math.max(-89.5, Math.min(89.5, radiansToDegrees(coords.pitch)));
                settings.offsetX = 0;
                settings.offsetY = 0;
                writeTripodSettingsToScene(scene, settings);
                writeTripodInputs(settings);
                record.hotspot.setPosition({ yaw: coords.yaw, pitch: coords.pitch });
                record.hotspot.setPerspective({ radius: settings.radius, extraTransforms: tripodLogoExtraTransforms(settings) });
            };

            const finish = (upEvent) => {
                stop(upEvent);
                node.classList.remove("is-dragging");
                node.removeEventListener("pointermove", move);
                node.removeEventListener("pointerup", finish);
                node.removeEventListener("pointercancel", finish);
                notify("Position 360° du logo mise à jour. Sauvegarde la scène.", "success");
            };

            node.addEventListener("pointermove", move);
            node.addEventListener("pointerup", finish);
            node.addEventListener("pointercancel", finish);
        });

        resizeHandle?.addEventListener("pointerdown", (event) => {
            stop(event);
            const scene = findScene(currentSceneId);
            const record = getTripodLogoRecord(layerKey);
            if (!scene || !record) return;
            const rect = node.getBoundingClientRect();
            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;
            const startDistance = Math.max(1, Math.hypot(event.clientX - centerX, event.clientY - centerY));
            const startSize = getTripodLogoSettings(scene).size;
            node.classList.add("is-resizing");
            try { resizeHandle.setPointerCapture(event.pointerId); } catch (_) {}

            const move = (moveEvent) => {
                stop(moveEvent);
                const distance = Math.max(1, Math.hypot(moveEvent.clientX - centerX, moveEvent.clientY - centerY));
                const settings = getTripodLogoSettings(scene);
                settings.enabled = true;
                settings.size = Math.max(72, Math.min(320, startSize * (distance / startDistance)));
                writeTripodSettingsToScene(scene, settings);
                writeTripodInputs(settings);
                applyTripodRecordVisual(record, settings);
            };
            const finish = (upEvent) => {
                stop(upEvent);
                node.classList.remove("is-resizing");
                resizeHandle.removeEventListener("pointermove", move);
                resizeHandle.removeEventListener("pointerup", finish);
                resizeHandle.removeEventListener("pointercancel", finish);
            };
            resizeHandle.addEventListener("pointermove", move);
            resizeHandle.addEventListener("pointerup", finish);
            resizeHandle.addEventListener("pointercancel", finish);
        });

        rotateHandle?.addEventListener("pointerdown", (event) => {
            stop(event);
            const scene = findScene(currentSceneId);
            const record = getTripodLogoRecord(layerKey);
            if (!scene || !record) return;
            node.classList.add("is-rotating");
            try { rotateHandle.setPointerCapture(event.pointerId); } catch (_) {}

            const move = (moveEvent) => {
                stop(moveEvent);
                const rect = node.getBoundingClientRect();
                const angle = Math.atan2(
                    moveEvent.clientY - (rect.top + rect.height / 2),
                    moveEvent.clientX - (rect.left + rect.width / 2)
                ) * 180 / Math.PI + 90;
                const settings = getTripodLogoSettings(scene);
                settings.enabled = true;
                settings.rotation = Math.max(-180, Math.min(180, ((angle + 540) % 360) - 180));
                writeTripodSettingsToScene(scene, settings);
                writeTripodInputs(settings);
                applyTripodRecordVisual(record, settings);
            };
            const finish = (upEvent) => {
                stop(upEvent);
                node.classList.remove("is-rotating");
                rotateHandle.removeEventListener("pointermove", move);
                rotateHandle.removeEventListener("pointerup", finish);
                rotateHandle.removeEventListener("pointercancel", finish);
            };
            rotateHandle.addEventListener("pointermove", move);
            rotateHandle.addEventListener("pointerup", finish);
            rotateHandle.addEventListener("pointercancel", finish);
        });
    }

    function createSceneTripodLogo(scene, layerKey) {
        destroyTripodLogo(layerKey);
        const settings = getTripodLogoSettings(scene);
        const logoUrl = String(config.organizationLogoUrl || "").trim();
        if (!settings.enabled || !logoUrl || !layerScenes[layerKey]) return;

        const node = document.createElement("div");
        node.className = "builder-tripod-logo-hotspot";
        node.style.setProperty("--builder-tripod-logo-size", `${settings.size}px`);
        node.setAttribute("role", "button");
        node.setAttribute("aria-label", "Déplacer le logo du trépied");
        node.title = "Glisser pour déplacer le logo dans la sphère 360°";

        const image = document.createElement("img");
        image.src = logoUrl;
        image.alt = "";
        image.draggable = false;
        node.appendChild(image);

        const rotateHandle = document.createElement("button");
        rotateHandle.type = "button";
        rotateHandle.className = "builder-tripod-logo-handle builder-tripod-logo-rotate";
        rotateHandle.setAttribute("aria-label", "Tourner le logo");
        rotateHandle.textContent = "↻";
        node.appendChild(rotateHandle);

        const resizeHandle = document.createElement("button");
        resizeHandle.type = "button";
        resizeHandle.className = "builder-tripod-logo-handle builder-tripod-logo-resize";
        resizeHandle.setAttribute("aria-label", "Redimensionner le logo");
        resizeHandle.textContent = "↘";
        node.appendChild(resizeHandle);

        const hotspot = layerScenes[layerKey].hotspotContainer().createHotspot(
            node,
            {
                yaw: degreesToRadians(settings.yaw),
                pitch: degreesToRadians(settings.pitch),
            },
            {
                perspective: {
                    radius: settings.radius,
                    extraTransforms: tripodLogoExtraTransforms(settings),
                },
            }
        );
        tripodLogoHotspots[layerKey] = { hotspot, node };
        bindTripodLogoEditor(node, layerKey);
    }

    function syncTripodLogoInputs(scene) {
        writeTripodInputs(getTripodLogoSettings(scene));
    }

    function updateTripodLogoDraft({ refresh = true } = {}) {
        const scene = findScene(currentSceneId);
        if (!scene) return;
        const settings = settingsFromTripodInputs();
        writeTripodSettingsToScene(scene, settings);
        if (!refresh) return;
        if (!settings.enabled) {
            destroyTripodLogo(activeLayerKey);
            return;
        }
        const record = getTripodLogoRecord(activeLayerKey);
        if (record) applyTripodRecordVisual(record, settings);
        else createSceneTripodLogo(scene, activeLayerKey);
    }

    function placeTripodLogoAtCurrentView() {
        const view = layerViews[activeLayerKey];
        if (!view) return;
        if (tripodLogoEnabled) tripodLogoEnabled.checked = true;
        if (tripodLogoYaw) tripodLogoYaw.value = radiansToDegrees(view.yaw()).toFixed(2);
        if (tripodLogoPitch) tripodLogoPitch.value = radiansToDegrees(view.pitch()).toFixed(2);
        if (tripodLogoOffsetX) tripodLogoOffsetX.value = "0";
        if (tripodLogoOffsetY) tripodLogoOffsetY.value = "0";
        updateTripodLogoDraft();
        notify("Logo ancré au centre de la vue actuelle. Tu peux maintenant le glisser précisément.", "success");
    }

    function placeTripodLogoAtNadir() {
        if (tripodLogoEnabled) tripodLogoEnabled.checked = true;
        if (tripodLogoYaw) tripodLogoYaw.value = "0.00";
        if (tripodLogoPitch) tripodLogoPitch.value = "88.50";
        if (tripodLogoOffsetX) tripodLogoOffsetX.value = "0";
        if (tripodLogoOffsetY) tripodLogoOffsetY.value = "0";
        if (tripodLogoTiltX) tripodLogoTiltX.value = "0";
        if (tripodLogoTiltY) tripodLogoTiltY.value = "0";
        updateTripodLogoDraft();
        notify("Logo placé au nadir en perspective 3D. Glisse-le si le trépied est décentré.", "success");
    }

    function buildLayerScene(layerKey, sceneData) {
        if (!sceneData.image_360_url) {
            console.warn("No panorama URL for scene:", sceneData);
            notify("Cette scène n'a pas d'image 360.", "warning");
            return null;
        }

        const viewer = ensureViewer(layerKey);
        if (!viewer) return null;

        const source = Marzipano.ImageUrlSource.fromString(sceneData.image_360_url);
        const geometry = new Marzipano.EquirectGeometry([{ width: 4000 }]);
        const limiter = Marzipano.RectilinearView.limit.traditional(4096, degreesToRadians(100));

        const initialYaw = degreesToRadians(sceneData.yaw_default || 0);
        const initialPitch = degreesToRadians(sceneData.pitch_default || 0);
        const initialFov = degreesToRadians(sceneData.hfov_default || 100);

        layerViews[layerKey] = new Marzipano.RectilinearView(
            { yaw: initialYaw, pitch: initialPitch, fov: initialFov },
            limiter
        );

        layerScenes[layerKey] = viewer.createScene({
            source,
            geometry,
            view: layerViews[layerKey],
            pinFirstLevel: true,
        });

        layerScenes[layerKey].switchTo();
        createSceneHotspots(sceneData, layerKey);
        createSceneTripodLogo(sceneData, layerKey);

        requestAnimationFrame(() => {
            try {
                viewer.updateSize();
            } catch (e) {
                console.warn("updateSize failed:", e);
            }
        });

        return layerScenes[layerKey];
    }

    function markLayerClasses(outgoingKey, incomingKey) {
        const outgoingEl = getLayerEl(outgoingKey);
        const incomingEl = getLayerEl(incomingKey);

        outgoingEl.classList.remove("active-layer", "standby-layer", "layer-incoming", "layer-outgoing");
        incomingEl.classList.remove("active-layer", "standby-layer", "layer-incoming", "layer-outgoing");

        outgoingEl.classList.add("active-layer", "layer-outgoing");
        incomingEl.classList.add("standby-layer", "layer-incoming");
        incomingEl.style.opacity = "1";
    }

    function finalizeLayerSwap(newActiveKey, oldActiveKey) {
        const newActiveEl = getLayerEl(newActiveKey);
        const oldActiveEl = getLayerEl(oldActiveKey);

        oldActiveEl.classList.remove("layer-outgoing", "active-layer");
        oldActiveEl.classList.add("standby-layer");
        oldActiveEl.style.opacity = "0";

        newActiveEl.classList.remove("layer-incoming", "standby-layer");
        newActiveEl.classList.add("active-layer");
        newActiveEl.style.opacity = "1";

        activeLayerKey = newActiveKey;
        syncInputsFromView();
    }

    function animateActiveCameraTo(targetYaw, targetPitch, targetFov, duration = 500) {
        const currentView = layerViews[activeLayerKey];
        if (!currentView) return;

        currentView.setParameters(
            { yaw: targetYaw, pitch: targetPitch, fov: targetFov },
            { transitionDuration: duration }
        );

        setTimeout(syncInputsFromView, duration + 40);
    }

    function nudgeCamera(deltaYaw = 0, deltaPitch = 0, deltaFov = 0) {
        const currentView = layerViews[activeLayerKey];
        if (!currentView) return;

        animateActiveCameraTo(
            currentView.yaw() + deltaYaw,
            currentView.pitch() + deltaPitch,
            currentView.fov() + deltaFov,
            350
        );
    }

    function resetCurrentView() {
        const scene = findScene(currentSceneId);
        if (!scene) return;

        animateActiveCameraTo(
            degreesToRadians(scene.yaw_default || 0),
            degreesToRadians(scene.pitch_default || 0),
            degreesToRadians(scene.hfov_default || 100),
            700
        );
    }

    function loadInitialScene(sceneId) {
        const scene = findScene(sceneId);
        if (!scene) return;

        currentSceneId = normalizeBuilderSceneId(scene.id);
        document.documentElement.dataset.builderCurrentSceneId = currentSceneId;
        setActiveCard(scene.id);

        if (sceneTitleInput) sceneTitleInput.value = scene.title || "";
        if (yawInput) yawInput.value = scene.yaw_default ?? 0;
        if (pitchInput) pitchInput.value = scene.pitch_default ?? 0;
        if (hfovInput) hfovInput.value = scene.hfov_default ?? 100;

        syncScenePublicUI(scene);

        if (viewerSceneTitle) viewerSceneTitle.textContent = scene.title || "Untitled Scene";
        if (activeSceneLabel) activeSceneLabel.textContent = scene.title || "Scene preview";

        refreshTargetSceneOptions();
        buildLayerScene(activeLayerKey, scene);
        syncInputsFromView();
    }

    function crossfadeToScene(scene) {
        const outgoingKey = activeLayerKey;
        const incomingKey = getStandbyLayerKey();

        buildLayerScene(incomingKey, scene);
        markLayerClasses(outgoingKey, incomingKey);

        panoramaViewer.classList.add("transitioning");

        requestAnimationFrame(() => {
            getLayerEl(outgoingKey).classList.add("layer-outgoing");
            getLayerEl(incomingKey).classList.add("layer-incoming");
        });

        setTimeout(() => {
            panoramaViewer.classList.remove("transitioning");
            finalizeLayerSwap(incomingKey, outgoingKey);
            isSceneTransitioning = false;
        }, 1180);
    }

    async function navigateThroughHotspot(hotspot) {
        const currentView = layerViews[activeLayerKey];
        if (!currentView || !hotspot.target_scene || isSceneTransitioning) return;

        isSceneTransitioning = true;

        const targetScene = findScene(hotspot.target_scene);
        if (!targetScene) {
            isSceneTransitioning = false;
            return;
        }

        const targetYaw = normalizeAngle(hotspot.yaw);
        const currentPitch = currentView.pitch();

        animateActiveCameraTo(targetYaw, currentPitch, currentView.fov(), 260);

        setTimeout(() => {
            const tighterFov = Math.max(degreesToRadians(20), currentView.fov() - degreesToRadians(22));
            animateActiveCameraTo(targetYaw, currentPitch, tighterFov, 260);
        }, 180);

        setTimeout(() => {
            setBuilderCurrentScene(targetScene.id, { skipTargetRefresh: true });

            if (sceneTitleInput) sceneTitleInput.value = targetScene.title || "";
            if (yawInput) yawInput.value = targetScene.yaw_default ?? 0;
            if (pitchInput) pitchInput.value = targetScene.pitch_default ?? 0;
            if (hfovInput) hfovInput.value = targetScene.hfov_default ?? 100;
            syncTripodLogoInputs(targetScene);

            syncScenePublicUI(targetScene);

            if (viewerSceneTitle) viewerSceneTitle.textContent = targetScene.title || "Untitled Scene";
            if (activeSceneLabel) activeSceneLabel.textContent = targetScene.title || "Scene preview";

            refreshTargetSceneOptions();
            crossfadeToScene(targetScene);
        }, 420);
    }

    function bindSceneDragEvents(wrapper) {
        wrapper.addEventListener("dragstart", (e) => {
            draggedSceneId = wrapper.dataset.sceneId;
            wrapper.classList.add("dragging");

            if (e.dataTransfer) {
                e.dataTransfer.effectAllowed = "move";
                e.dataTransfer.setData("text/plain", draggedSceneId);
            }
        });

        wrapper.addEventListener("dragend", () => {
            wrapper.classList.remove("dragging");
            draggedSceneId = null;
            document.querySelectorAll(".scene-card-wrap").forEach(el => el.classList.remove("drag-over"));
        });

        wrapper.addEventListener("dragover", (e) => {
            e.preventDefault();

            if (!draggedSceneId || draggedSceneId === wrapper.dataset.sceneId) return;
            wrapper.classList.add("drag-over");
        });

        wrapper.addEventListener("dragleave", () => {
            wrapper.classList.remove("drag-over");
        });

        wrapper.addEventListener("drop", async (e) => {
            e.preventDefault();
            wrapper.classList.remove("drag-over");

            const targetSceneId = wrapper.dataset.sceneId;
            if (!draggedSceneId || draggedSceneId === targetSceneId) return;

            reorderScenesInMemory(draggedSceneId, targetSceneId);
            renderSceneList();
            await persistSceneOrder();
        });
    }

    function getSceneThumbUrl(scene) {
        return scene.thumbnail_url || scene.thumbnail_image_url || scene.image_360_preview_url || scene.image_360_mobile_url || scene.image_360_url || "";
    }

    function renderSceneBadges(scene) {
        const badges = [];

        if (isScenePublic(scene)) {
            badges.push(`<span class="scene-public-mini-badge is-public">Public</span>`);
        } else {
            badges.push(`<span class="scene-public-mini-badge is-private">Privé</span>`);
        }

        if (scene.assets_status) {
            const status = scene.assets_status;
            const klass = status === "ready"
                ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                : status === "failed"
                    ? "bg-rose-50 text-rose-700 ring-rose-200"
                    : "bg-amber-50 text-amber-700 ring-amber-200";

            badges.push(`<span class="rounded-full px-2 py-1 text-[10px] font-black ring-1 ${klass}">Assets ${escapeHtml(status)}</span>`);
        }

        if (scene.tiles_enabled || scene.tiles_status) {
            const status = scene.tiles_status || "pending";
            const klass = status === "ready"
                ? "bg-blue-50 text-blue-700 ring-blue-200"
                : status === "failed"
                    ? "bg-rose-50 text-rose-700 ring-rose-200"
                    : "bg-slate-100 text-slate-600 ring-slate-200";

            badges.push(`<span class="rounded-full px-2 py-1 text-[10px] font-black ring-1 ${klass}">Tiles ${escapeHtml(status)}</span>`);
        }

        return badges.join("");
    }

    function renderSceneList() {
        if (!sceneList) return;

        sceneList.innerHTML = "";

        if (!scenesData.length) {
            sceneList.innerHTML = `
                <div id="emptySceneState" class="rounded-[1.5rem] border border-dashed border-slate-300 bg-white p-6 text-center">
                    <div class="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-2xl">🌐</div>
                    <p class="text-sm font-black text-slate-800">No panorama yet.</p>
                    <p class="mt-1 text-xs leading-5 text-slate-500">
                        Drop your panorama file here or use <strong>Add</strong>.
                    </p>
                </div>
            `;
            return;
        }

        sortScenesData();

        scenesData.forEach(scene => {
            const thumbUrl = getSceneThumbUrl(scene);

            const wrapper = document.createElement("div");
            wrapper.className = "scene-card-wrap group relative rounded-[1.45rem] border border-slate-200 bg-white p-2 transition hover:border-blue-200 hover:bg-slate-50";
            wrapper.dataset.sceneId = scene.id;
            wrapper.setAttribute("draggable", "true");

            wrapper.innerHTML = `
                <button
                    class="scene-card flex w-full min-w-0 items-center gap-3 rounded-[1.25rem] p-2 text-left transition ${String(scene.id) === String(currentSceneId) ? "active bg-blue-50" : "hover:bg-white"}"
                    data-scene-id="${escapeHtml(scene.id)}"
                    type="button">

                    <div class="scene-thumb h-16 w-20 flex-shrink-0 overflow-hidden rounded-2xl bg-slate-100">
                        ${
                            thumbUrl
                                ? `<img src="${escapeHtml(thumbUrl)}" alt="${escapeHtml(scene.title)}">`
                                : `<div class="flex h-full w-full items-center justify-center text-xs font-black text-slate-400">360</div>`
                        }
                    </div>

                    <div class="scene-meta min-w-0 flex-1">
                        <strong class="block truncate text-sm font-black text-slate-950">${escapeHtml(scene.title || "Untitled Scene")}</strong>
                        <span class="mt-1 block truncate text-xs font-semibold text-slate-400">Order ${escapeHtml(scene.order || "-")}</span>
                        <span class="scene-card-visibility ${isScenePublic(scene) ? "is-public" : "is-private"}">
                            ${isScenePublic(scene) ? "Visible preview" : "Masquée preview"}
                        </span>
                        <div class="mt-2 flex flex-wrap gap-1.5">
                            ${renderSceneBadges(scene)}
                        </div>
                    </div>
                </button>

                <div
                    class="scene-drag-handle absolute right-3 top-3 cursor-grab rounded-xl bg-slate-100 px-2 py-1 text-xs font-black text-slate-400 opacity-0 transition group-hover:opacity-100"
                    title="Drag to reorder">
                    ⋮⋮
                </div>
            `;

            wrapper.querySelector(".scene-card")?.addEventListener("click", () => {
                if (isSceneTransitioning) return;

                const targetScene = findScene(scene.id);
                if (!targetScene) return;

                setBuilderCurrentScene(targetScene.id, { skipTargetRefresh: true });

                if (sceneTitleInput) sceneTitleInput.value = targetScene.title || "";
                if (yawInput) yawInput.value = targetScene.yaw_default ?? 0;
                if (pitchInput) pitchInput.value = targetScene.pitch_default ?? 0;
                if (hfovInput) hfovInput.value = targetScene.hfov_default ?? 100;

                if (viewerSceneTitle) viewerSceneTitle.textContent = targetScene.title || "Untitled Scene";
                if (activeSceneLabel) activeSceneLabel.textContent = targetScene.title || "Scene preview";

                refreshTargetSceneOptions();
                isSceneTransitioning = true;
                crossfadeToScene(targetScene);
            });

            bindSceneDragEvents(wrapper);
            sceneList.appendChild(wrapper);
        });
    }

    function reorderScenesInMemory(draggedId, targetId) {
        const ordered = scenesData.slice().sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
        const fromIndex = ordered.findIndex(scene => String(scene.id) === String(draggedId));
        const toIndex = ordered.findIndex(scene => String(scene.id) === String(targetId));

        if (fromIndex === -1 || toIndex === -1) return;

        const [moved] = ordered.splice(fromIndex, 1);
        ordered.splice(toIndex, 0, moved);

        scenesData = ordered.map((scene, index) => ({
            ...scene,
            order: index + 1,
        }));
    }

    async function persistSceneOrder() {
        if (!config.reorderScenesUrl) return false;

        try {
            const response = await fetch(config.reorderScenesUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCSRFToken(),
                },
                body: JSON.stringify({
                    scene_ids: scenesData
                        .slice()
                        .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
                        .map(scene => scene.id),
                }),
            });

            if (!response.ok) {
                notify("Unable to reorder scenes.", "error");
                return false;
            }

            const data = await response.json();
            scenesData = data.scenes || [];
            sortScenesData();
            renderSceneList();
            notify("Scenes reordered successfully.", "success");
            return true;
        } catch (error) {
            console.error(error);
            notify("Scene reorder failed.", "error");
            return false;
        }
    }

    async function uploadFiles(files) {
        if (!files || !files.length || !config.uploadScenesUrl) return;

        setButtonLoading(addSceneBtn, true, "Uploading...");

        try {
            const formData = new FormData();
            Array.from(files).forEach(file => formData.append("panos", file));

            const response = await fetch(config.uploadScenesUrl, {
                method: "POST",
                headers: { "X-CSRFToken": getCSRFToken() },
                body: formData,
            });

            if (!response.ok) {
                notify("Upload failed.", "error");
                return;
            }

            const data = await response.json();
            const newScenes = data.scenes || [];

            newScenes.forEach(scene => {
                scene.hotspots = scene.hotspots || [];
                scenesData.push(scene);
            });

            sortScenesData();
            renderSceneList();

            if (newScenes.length > 0 && !currentSceneId) {
                loadInitialScene(newScenes[0].id);
            }

            notify(`${newScenes.length} panorama(s) uploaded.`, "success");
        } catch (error) {
            console.error(error);
            notify("Upload failed.", "error");
        } finally {
            setButtonLoading(addSceneBtn, false);
        }
    }

    async function saveScene() {
        if (!currentSceneId) {
            notify("Select a scene first.", "warning");
            return;
        }

        setButtonLoading(saveSceneBtn, true, "Saving...");

        try {
            const currentView = layerViews[activeLayerKey];

            if (currentView) {
                if (yawInput) yawInput.value = radiansToDegrees(currentView.yaw()).toFixed(2);
                if (pitchInput) pitchInput.value = radiansToDegrees(currentView.pitch()).toFixed(2);
                if (hfovInput) hfovInput.value = radiansToDegrees(currentView.fov()).toFixed(2);
            }

            const tripodDraft = settingsFromTripodInputs();
            const currentScene = findScene(currentSceneId);
            if (currentScene) writeTripodSettingsToScene(currentScene, tripodDraft);

            const payload = {
                title: sceneTitleInput?.value || "",
                yaw_default: parseFloat(yawInput?.value || 0),
                pitch_default: parseFloat(pitchInput?.value || 0),
                hfov_default: parseFloat(hfovInput?.value || 100),
                is_public: scenePublicInput ? Boolean(scenePublicInput.checked) : true,
                tripod_logo_enabled: Boolean(tripodDraft.enabled),
                tripod_logo_size: Math.round(tripodDraft.size),
                tripod_logo_yaw: Number(tripodDraft.yaw),
                tripod_logo_pitch: Number(tripodDraft.pitch),
                tripod_logo_offset_x: Math.round(tripodDraft.offsetX),
                tripod_logo_offset_y: Math.round(tripodDraft.offsetY),
                tripod_logo_rotation: Number(tripodDraft.rotation),
                tripod_logo_tilt_x: Number(tripodDraft.tiltX),
                tripod_logo_tilt_y: Number(tripodDraft.tiltY),
                tripod_logo_radius: Math.round(tripodDraft.radius),
                tripod_logo_apply_all_scenes: Boolean(tripodLogoApplyAllScenes?.checked),
            };

            const response = await fetch(`${config.updateSceneBaseUrl}${currentSceneId}/update/`, {
                method: "POST",
                credentials: "same-origin",
                cache: "no-store",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCSRFToken(),
                    "X-Requested-With": "XMLHttpRequest",
                    "Cache-Control": "no-cache",
                },
                body: JSON.stringify(payload),
            });

            let data = null;
            try {
                data = await response.json();
            } catch (_) {
                data = null;
            }

            if (!response.ok || !data?.success || !data?.scene) {
                const detail = data?.detail || "Unable to save scene.";
                throw new Error(detail);
            }

            if (!data?.persistence?.database_verified || !data?.persistence?.tripod_logo_verified) {
                throw new Error("The server did not confirm the tripod logo database write.");
            }

            const updatedScene = data.scene;
            const persistedTripod = getTripodLogoSettings(updatedScene);
            if (!tripodSettingsMatch(tripodDraft, persistedTripod)) {
                console.error("TRIPOD_LOGO_PERSISTENCE_MISMATCH", {
                    expected: tripodDraft,
                    persisted: persistedTripod,
                    response: data,
                });
                throw new Error("The saved tripod position does not match the database response.");
            }

            const appliedSceneIds = new Set(
                (data?.persistence?.tripod_logo_applied_scene_ids || [updatedScene.id])
                    .map(value => String(value))
            );

            scenesData = scenesData.map(scene => {
                const sceneId = String(scene.id);
                let nextScene = sceneId === String(updatedScene.id)
                    ? { ...scene, ...updatedScene, hotspots: updatedScene.hotspots || scene.hotspots || [] }
                    : scene;

                if (appliedSceneIds.has(sceneId)) {
                    nextScene = { ...nextScene };
                    writeTripodSettingsToScene(nextScene, persistedTripod);
                }
                return nextScene;
            });

            const savedScene = findScene(updatedScene.id);
            if (savedScene) {
                writeTripodSettingsToScene(savedScene, persistedTripod);
                writeTripodInputs(persistedTripod);
                const record = getTripodLogoRecord(activeLayerKey);
                if (record) applyTripodRecordVisual(record, persistedTripod);
                else if (persistedTripod.enabled) createSceneTripodLogo(savedScene, activeLayerKey);
            }

            renderSceneList();
            const appliedCount = Number(data?.persistence?.tripod_logo_applied_scene_count || 1);
            notify(
                appliedCount > 1
                    ? `Logo enregistré sur ${appliedCount} scènes du tour.`
                    : "Scene and tripod logo saved in the database.",
                "success"
            );
        } catch (error) {
            console.error("SCENE_SAVE_FAILED", error);
            notify(error?.message || "Unable to save scene.", "error");
        } finally {
            setButtonLoading(saveSceneBtn, false);
        }
    }

    function ensureLivePreviewCard() {
        const modalBody = hotspotModal?.querySelector(".modal-body");
        if (!modalBody) return null;

        let preview = modalBody.querySelector("#hotspotLivePreview");
        if (preview) return preview;

        const hero = ensureModalHero();

        preview = document.createElement("div");
        preview.id = "hotspotLivePreview";
        preview.className = "hotspot-live-preview-card";

        preview.innerHTML = `
            <div class="hotspot-live-preview-head">
                <strong>Live preview</strong>
                <span class="hotspot-live-preview-badge" id="previewTypeBadge">Hotspot</span>
            </div>

            <div class="hotspot-live-preview-body">
                <div class="hotspot-live-preview-media" id="previewMedia">
                    Preview
                </div>

                <div class="hotspot-live-preview-content">
                    <div class="hotspot-live-preview-title" id="previewTitle">Hotspot title</div>
                    <div class="hotspot-live-preview-desc" id="previewDescription">
                        Fill in the form to preview how this hotspot will look.
                    </div>

                    <div class="hotspot-live-preview-meta" id="previewMeta"></div>
                    <div class="hotspot-live-preview-actions" id="previewActions"></div>
                </div>
            </div>
        `;

        if (hero && hero.nextSibling) {
            modalBody.insertBefore(preview, hero.nextSibling);
        } else if (hero) {
            hero.after(preview);
        } else {
            modalBody.prepend(preview);
        }

        return preview;
    }

    function getModalPreviewData() {
        const type = hotspotType?.value || "navigate";

        let title = hotspotLabel?.value || "Hotspot";
        let description = hotspotTooltip?.value || "Configure this hotspot";
        let imageUrl = "";
        let badge = "";
        let price = "";
        let siteName = "";
        let actionText = "";
        let whatsapp = "";
        let contact = "";
        let display = {};

        if (modalPreviewObjectUrl) {
            URL.revokeObjectURL(modalPreviewObjectUrl);
            modalPreviewObjectUrl = "";
        }

        if (type === "info") {
            title = hotspotTitle?.value || hotspotLabel?.value || "Info";
            description = hotspotDescription?.value || hotspotTooltip?.value || "Information details";
            imageUrl = hotspotImageUpload?.files?.[0]
                ? URL.createObjectURL(hotspotImageUpload.files[0])
                : hotspotImageUrl?.value || "";
            modalPreviewObjectUrl = hotspotImageUpload?.files?.[0] ? imageUrl : "";
            actionText = "Read more";
        }

        if (type === "product") {
            title = hotspotProductTitle?.value || hotspotLabel?.value || "Product";
            description = hotspotProductDescription?.value || hotspotTooltip?.value || "Product description";
            imageUrl = hotspotImageUploadProduct?.files?.[0]
                ? URL.createObjectURL(hotspotImageUploadProduct.files[0])
                : hotspotImageUrlProduct?.value || "";
            modalPreviewObjectUrl = hotspotImageUploadProduct?.files?.[0] ? imageUrl : "";
            badge = hotspotBadge?.value || "";
            price = hotspotPrice?.value || "";
            siteName = hotspotSiteName?.value || "";
            actionText = hotspotButtonText?.value || "Order now";
        }

        if (type === "navigate") {
            const targetOption = hotspotTargetScene?.selectedOptions?.[0];
            title = hotspotLabel?.value || "Go to scene";
            description = targetOption?.textContent && hotspotTargetScene?.value
                ? `Navigate to ${targetOption.textContent}`
                : "Choose a target scene.";
            actionText = "Navigate";
        }

        if (type === "whatsapp") {
            title = hotspotLabel?.value || "WhatsApp";
            description = hotspotWhatsappMessage?.value || "Contact us on WhatsApp";
            whatsapp = hotspotWhatsapp?.value || "";
            actionText = "WhatsApp";
        }

        if (type === "phone") {
            title = hotspotLabel?.value || "Call us";
            description = hotspotTooltip?.value || "Tap to call directly.";
            contact = hotspotPhone?.value || "";
            actionText = "Call";
        }

        if (type === "email") {
            title = hotspotLabel?.value || "Email us";
            description = hotspotTooltip?.value || "Tap to send an email.";
            contact = hotspotEmail?.value || "";
            actionText = "Email";
        }

        if (type === "cta") {
            title = hotspotWebsiteTitle?.value || hotspotLabel?.value || "Visit website";
            description = hotspotTooltip?.value || "Open external link.";
            actionText = hotspotWebsiteButtonText?.value || "Open";
        }

        if (type === "floor") {
            const floorItems = getAllFloorGroupItems();
            const primaryFloor = floorItems[0] || getPrimaryFloorItemFromFields();
            title = primaryFloor.floor_name || hotspotLabel?.value || "Floor navigation";
            content = {
                floor_name: primaryFloor.floor_name,
                floor_number: Number(primaryFloor.floor_number || 0),
                direction: primaryFloor.direction || "same",
                destination_label: primaryFloor.destination_label || "",
                floor_items: floorItems.map((item, index) => ({
                    uid: item.uid || `floor-${index + 1}`,
                    floor_name: item.floor_name,
                    floor_number: Number(item.floor_number || 0),
                    direction: item.direction || "same",
                    destination_label: item.destination_label || "",
                    target_scene: normalizeBuilderSceneId(item.target_scene),
                    order: index,
                })),
            };
        }
        if (type === "pdf") {
            title = hotspotPdfTitle?.value || hotspotLabel?.value || "Document";
            description = hotspotPdfDescription?.value || "";
            content = { document_url: hotspotPdfUrl?.value || "", allow_download: hotspotPdfDownload?.checked !== false, button_text: "Open PDF" };
        }
        if (type === "video") {
            title = hotspotVideoTitle?.value || hotspotLabel?.value || "Video";
            description = hotspotVideoDescription?.value || "";
            const url = hotspotVideoUrl?.value || "";
            content = { video_url: url, video_source: /youtu/.test(url) ? "youtube" : /vimeo/.test(url) ? "vimeo" : "upload", autoplay: !!hotspotVideoAutoplay?.checked, muted: !!hotspotVideoMuted?.checked, loop: !!hotspotVideoLoop?.checked };
            display = { ...(display || {}), variant: hotspotVideoDisplayMode?.value === "screen" ? "screen" : "pin", width: Number(hotspotVideoWidth?.value || 360), height: Number(hotspotVideoHeight?.value || 210), reference_fov: getSurfaceReferenceFovDeg() };
        }

        if (type === "door") {
            title = hotspotDoorLabel?.value || hotspotLabel?.value || "Open the door";
            description = "Interactive door navigation";
            content = { opening_direction: hotspotDoorDirection?.value || "left" };
            display = { ...(display || {}), variant: "door", width: Number(hotspotDoorWidth?.value || 180), height: Number(hotspotDoorHeight?.value || 320), reference_fov: getSurfaceReferenceFovDeg() };
        }

        if (type === "custom") {
            title = hotspotLabel?.value || "Custom hotspot";
            description = hotspotTooltip?.value || "Custom action.";
            actionText = "Custom";
        }

        return {
            type,
            title,
            description,
            imageUrl,
            badge,
            price,
            siteName,
            actionText,
            whatsapp,
            contact,
            display,
        };
    }

    function renderHotspotLivePreview() {
        const preview = ensureLivePreviewCard();
        if (!preview) return;

        const data = getModalPreviewData();
        const meta = getTypeMeta(data.type);

        const previewTypeBadge = document.getElementById("previewTypeBadge");
        const previewMedia = document.getElementById("previewMedia");
        const previewTitle = document.getElementById("previewTitle");
        const previewDescription = document.getElementById("previewDescription");
        const previewMeta = document.getElementById("previewMeta");
        const previewActions = document.getElementById("previewActions");

        if (previewTypeBadge) previewTypeBadge.textContent = data.type;
        if (previewTitle) previewTitle.textContent = data.title || meta.title;
        if (previewDescription) previewDescription.textContent = data.description || meta.description;

        if (previewMedia) {
            previewMedia.innerHTML = "";

            if (data.imageUrl) {
                const img = document.createElement("img");
                img.src = data.imageUrl;
                img.alt = data.title || "Preview";
                previewMedia.appendChild(img);
            } else {
                const iconSrc = getIconSrc(meta.iconName || "default");

                if (iconSrc) {
                    const img = document.createElement("img");
                    img.src = iconSrc;
                    img.alt = data.title || meta.title;
                    previewMedia.appendChild(img);
                } else {
                    previewMedia.textContent = data.type.toUpperCase();
                }
            }
        }

        if (previewMeta) {
            previewMeta.innerHTML = "";

            [data.badge, data.price, data.siteName, data.whatsapp, data.contact]
                .filter(Boolean)
                .forEach(value => {
                    const span = document.createElement("span");
                    span.textContent = value;
                    previewMeta.appendChild(span);
                });
        }

        if (previewActions) {
            previewActions.innerHTML = "";

            if (data.actionText) {
                const btn = document.createElement("span");
                btn.className = "hotspot-live-preview-action";

                if (data.type === "whatsapp") btn.classList.add("green");
                if (["phone", "email", "custom"].includes(data.type)) btn.classList.add("dark");

                btn.textContent = data.actionText;
                previewActions.appendChild(btn);
            }
        }
    }

    function resetHotspotModalFields() {
        if (hotspotLabel) hotspotLabel.value = "";
        if (hotspotTooltip) hotspotTooltip.value = "";
        if (hotspotTitle) hotspotTitle.value = "";
        if (hotspotDescription) hotspotDescription.value = "";
        if (hotspotTargetScene) hotspotTargetScene.value = "";
        if (hotspotType) hotspotType.value = "navigate";

        if (hotspotVariant) hotspotVariant.value = "pin";
        if (hotspotSize) hotspotSize.value = 56;
        if (hotspotRotation) hotspotRotation.value = 0;
        if (hotspotAnchor) hotspotAnchor.value = "bottom";
        if (hotspotOffsetX) hotspotOffsetX.value = 0;
        if (hotspotOffsetY) hotspotOffsetY.value = 0;

        if (hotspotImageUpload) hotspotImageUpload.value = "";
        if (hotspotImageUrl) hotspotImageUrl.value = "";

        if (hotspotProductTitle) hotspotProductTitle.value = "";
        if (hotspotProductDescription) hotspotProductDescription.value = "";
        if (hotspotImageUploadProduct) hotspotImageUploadProduct.value = "";
        if (hotspotImageUrlProduct) hotspotImageUrlProduct.value = "";
        if (hotspotPrice) hotspotPrice.value = "";
        if (hotspotBadge) hotspotBadge.value = "";
        if (hotspotButtonText) hotspotButtonText.value = "";
        if (hotspotCtaUrl) hotspotCtaUrl.value = "";
        if (hotspotSiteName) hotspotSiteName.value = "";

        if (hotspotWhatsapp) hotspotWhatsapp.value = "";
        if (hotspotWhatsappMessage) hotspotWhatsappMessage.value = "";

        if (hotspotPhone) hotspotPhone.value = "";
        if (hotspotEmail) hotspotEmail.value = "";

        if (hotspotWebsiteTitle) hotspotWebsiteTitle.value = "";
        if (hotspotWebsiteButtonText) hotspotWebsiteButtonText.value = "";
        if (hotspotWebsiteUrl) hotspotWebsiteUrl.value = "";

        updateHotspotTypePanels("navigate");
        applyTypeDefaults("navigate");
        renderHotspotLivePreview();
    }

    function openModalShell() {
        if (!hotspotModal) return;

        ensureModalHero();
        ensureLivePreviewCard();

        hotspotModal.classList.remove("hidden", "is-closing");
        hotspotModal.classList.add("is-opening");
        document.body.classList.add("modal-is-open");

        setTimeout(() => {
            hotspotModal.classList.remove("is-opening");
        }, 230);

        setTimeout(() => {
            const firstInput = hotspotModal.querySelector("input:not([type='hidden']), select, textarea, button");
            firstInput?.focus?.();
        }, 80);
    }

    function openHotspotModal(position) {
        const ownerSceneId = getHotspotOwnerSceneId();

        if (!ownerSceneId) {
            notify("No active scene.", "warning");
            return;
        }

        setBuilderCurrentScene(ownerSceneId, { skipTargetRefresh: true });

        editingHotspotId = null;
        pendingHotspotPosition = position;

        if (hotspotModalTitle) hotspotModalTitle.textContent = "Create Hotspot";
        if (saveHotspotBtn) {
            saveHotspotBtn.textContent = "Save Hotspot";
            saveHotspotBtn.dataset.originalText = "Save Hotspot";
        }
        if (deleteHotspotBtn) deleteHotspotBtn.style.display = "none";

        resetHotspotModalFields();
        refreshTargetSceneOptions("");
        floorGroupItems = [];
        loadFloorGroupEditor({}, null);

        if (hotspotTargetScene) {
            hotspotTargetScene.value = "";
        }

        openModalShell();
    }

    function openEditHotspotModal(hotspot) {
        editingHotspotId = hotspot.id;
        pendingHotspotPosition = {
            yaw: hotspot.yaw,
            pitch: hotspot.pitch,
        };

        const display = getHotspotDisplay(hotspot);
        const content = hotspot.payload?.content || {};
        const type = hotspot.type || "navigate";

        if (hotspotModalTitle) hotspotModalTitle.textContent = "Edit Hotspot";
        if (saveHotspotBtn) {
            saveHotspotBtn.textContent = "Update Hotspot";
            saveHotspotBtn.dataset.originalText = "Update Hotspot";
        }
        if (deleteHotspotBtn) deleteHotspotBtn.style.display = "inline-flex";

        if (hotspotType) hotspotType.value = type;
        if (hotspotLabel) hotspotLabel.value = hotspot.label || "";
        if (hotspotTooltip) hotspotTooltip.value = hotspot.tooltip_text || "";
        if (hotspotTitle) hotspotTitle.value = hotspot.title || "";
        if (hotspotDescription) hotspotDescription.value = hotspot.description || "";
        const hotspotOwnerSceneId = findSceneIdOwningHotspot(hotspot.id) || getHotspotOwnerSceneId();

        if (hotspotOwnerSceneId) {
            setBuilderCurrentScene(hotspotOwnerSceneId, { skipTargetRefresh: true });
        }

        refreshTargetSceneOptions(hotspot.target_scene || "");

        if (hotspotTargetScene) {
            hotspotTargetScene.value = normalizeBuilderSceneId(hotspot.target_scene || "");
        }

        if (hotspotVariant) hotspotVariant.value = display.variant || "pin";
        if (hotspotSize) hotspotSize.value = Number(display.size || 56);
        if (hotspotRotation) hotspotRotation.value = Number(display.rotation || 0);
        if (hotspotAnchor) hotspotAnchor.value = display.anchor || "bottom";
        if (hotspotOffsetX) hotspotOffsetX.value = Number(display.offset_x || 0);
        if (hotspotOffsetY) hotspotOffsetY.value = Number(display.offset_y || 0);

        if (hotspotImageUpload) hotspotImageUpload.value = "";
        if (hotspotImageUrl) hotspotImageUrl.value = content.image_url || hotspot.ad_image_url || "";

        if (hotspotProductTitle) hotspotProductTitle.value = hotspot.title || "";
        if (hotspotProductDescription) hotspotProductDescription.value = hotspot.description || "";
        if (hotspotImageUploadProduct) hotspotImageUploadProduct.value = "";
        if (hotspotImageUrlProduct) hotspotImageUrlProduct.value = content.image_url || hotspot.ad_image_url || "";
        if (hotspotPrice) hotspotPrice.value = content.price || "";
        if (hotspotBadge) hotspotBadge.value = content.badge || "";
        if (hotspotButtonText) hotspotButtonText.value = content.button_text || "";
        if (hotspotCtaUrl) hotspotCtaUrl.value = content.cta_url || "";
        if (hotspotSiteName) hotspotSiteName.value = content.site_name || "";

        if (hotspotWhatsapp) hotspotWhatsapp.value = content.whatsapp_number || "";
        if (hotspotWhatsappMessage) hotspotWhatsappMessage.value = content.whatsapp_message || "";

        if (hotspotPhone) hotspotPhone.value = content.phone || "";
        if (hotspotEmail) hotspotEmail.value = content.email || "";

        if (hotspotWebsiteTitle) hotspotWebsiteTitle.value = hotspot.title || "";
        if (hotspotWebsiteButtonText) hotspotWebsiteButtonText.value = content.button_text || "";
        if (hotspotWebsiteUrl) hotspotWebsiteUrl.value = content.cta_url || "";

        if (type === "floor") {
            loadFloorGroupEditor(content, hotspot);
        } else {
            floorGroupItems = [];
            renderFloorGroupEditor();
        }

        updateHotspotTypePanels(type);
        activateIconOption(hotspot.selected_icon || "default");
        renderHotspotLivePreview();

        openModalShell();
    }

    function closeHotspotModalFn() {
        if (!hotspotModal || hotspotModal.classList.contains("hidden")) return;

        hotspotModal.classList.remove("is-opening");
        hotspotModal.classList.add("is-closing");

        setTimeout(() => {
            hotspotModal.classList.add("hidden");
            hotspotModal.classList.remove("is-closing");
            document.body.classList.remove("modal-is-open");

            pendingHotspotPosition = null;
            editingHotspotId = null;
        }, 180);
    }

    function getImageFileForType(type) {
        if (type === "info") return hotspotImageUpload?.files?.[0] || null;
        if (type === "product") return hotspotImageUploadProduct?.files?.[0] || null;
        return null;
    }


    function normalizeFloorGroupItem(item = {}, index = 0) {
        return {
            uid: String(item.uid || item.id || `floor-${Date.now()}-${index}-${Math.random().toString(36).slice(2, 8)}`),
            floor_name: String(item.floor_name || item.name || `Floor ${index + 1}`),
            floor_number: Number.isFinite(Number(item.floor_number ?? item.number))
                ? Number(item.floor_number ?? item.number)
                : index,
            direction: String(item.direction || "up"),
            destination_label: String(item.destination_label || item.description || ""),
            target_scene: normalizeBuilderSceneId(item.target_scene || item.target || ""),
        };
    }

    function getPrimaryFloorItemFromFields() {
        return normalizeFloorGroupItem({
            uid: "primary-floor",
            floor_name: hotspotFloorName?.value || hotspotLabel?.value || "Ground floor",
            floor_number: Number(hotspotFloorNumber?.value || 0),
            direction: hotspotFloorDirection?.value || "same",
            destination_label: hotspotFloorDestination?.value || "",
            target_scene: hotspotFloorTargetScene?.value || "",
        }, 0);
    }

    function setPrimaryFloorFields(item) {
        const floor = normalizeFloorGroupItem(item || {}, 0);
        if (hotspotFloorName) hotspotFloorName.value = floor.floor_name;
        if (hotspotFloorNumber) hotspotFloorNumber.value = floor.floor_number;
        if (hotspotFloorDirection) hotspotFloorDirection.value = floor.direction;
        if (hotspotFloorDestination) hotspotFloorDestination.value = floor.destination_label;
        if (hotspotFloorTargetScene) hotspotFloorTargetScene.value = floor.target_scene;
    }

    function getAllFloorGroupItems() {
        const primary = getPrimaryFloorItemFromFields();
        return [primary, ...floorGroupItems.map(normalizeFloorGroupItem)]
            .filter((item) => item.floor_name || item.target_scene);
    }

    function createFloorSceneOptions(selectedValue = "") {
        const ownerSceneId = getHotspotOwnerSceneId();
        const normalizedSelected = normalizeBuilderSceneId(selectedValue || "");
        return [
            `<option value="">Select destination scene</option>`,
            ...scenesData.map((scene) => {
                const id = normalizeBuilderSceneId(scene.id);
                const disabled = id === ownerSceneId ? " disabled" : "";
                const selected = id === normalizedSelected ? " selected" : "";
                const current = disabled ? " — current scene" : "";
                return `<option value="${escapeHtml(id)}"${selected}${disabled}>${escapeHtml(scene.title || "Scene")}${current}</option>`;
            }),
        ].join("");
    }

    function ensureFloorGroupEditor() {
        if (floorGroupEditorReady) return document.getElementById("floorGroupEditor");
        const panel = document.querySelector('[data-panel="floor"]');
        if (!panel) return null;

        const editor = document.createElement("section");
        editor.id = "floorGroupEditor";
        editor.className = "floor-group-editor";
        editor.innerHTML = `
            <div class="floor-group-editor-head">
                <div class="floor-group-editor-icon" aria-hidden="true">
                    <svg viewBox="0 0 64 64"><path d="M11 53h42M16 53V20l16-9 16 9v33M23 29h6M35 29h6M23 39h6M35 39h6M29 53v-8h6v8"/></svg>
                </div>
                <div class="floor-group-editor-copy">
                    <small>FLOOR DIRECTORY</small>
                    <strong>Build all levels from one hotspot</strong>
                    <span>Add, edit, reorder or remove floor destinations.</span>
                </div>
                <button type="button" class="floor-group-add-btn" id="addFloorGroupItem">
                    <span>＋</span> Add floor
                </button>
            </div>
            <div class="floor-group-primary-note">
                <span class="floor-group-primary-dot"></span>
                The fields above define the primary level shown on the hotspot.
            </div>
            <div class="floor-group-list" id="floorGroupList"></div>
            <div class="floor-group-empty" id="floorGroupEmpty">
                <strong>No additional floors yet</strong>
                <span>Use “Add floor” to include another level in the same navigation hotspot.</span>
            </div>
        `;
        panel.appendChild(editor);

        editor.querySelector("#addFloorGroupItem")?.addEventListener("click", () => {
            const nextNumber = getAllFloorGroupItems().reduce((max, item) => Math.max(max, Number(item.floor_number || 0)), -1) + 1;
            floorGroupItems.push(normalizeFloorGroupItem({
                floor_name: `Floor ${nextNumber}`,
                floor_number: nextNumber,
                direction: "up",
                target_scene: "",
            }, floorGroupItems.length + 1));
            renderFloorGroupEditor();
        });

        floorGroupEditorReady = true;
        return editor;
    }

    function moveFloorGroupItem(index, delta) {
        const next = index + delta;
        if (next < 0 || next >= floorGroupItems.length) return;
        const copy = [...floorGroupItems];
        [copy[index], copy[next]] = [copy[next], copy[index]];
        floorGroupItems = copy;
        renderFloorGroupEditor();
    }

    function renderFloorGroupEditor() {
        const editor = ensureFloorGroupEditor();
        if (!editor) return;
        const list = editor.querySelector("#floorGroupList");
        const empty = editor.querySelector("#floorGroupEmpty");
        if (!list || !empty) return;
        list.innerHTML = "";
        empty.hidden = floorGroupItems.length > 0;

        floorGroupItems.forEach((rawItem, index) => {
            const item = normalizeFloorGroupItem(rawItem, index + 1);
            const card = document.createElement("article");
            card.className = "floor-group-item";
            card.dataset.floorUid = item.uid;
            card.innerHTML = `
                <div class="floor-group-item-index">${index + 2}</div>
                <div class="floor-group-item-body">
                    <div class="floor-group-item-top">
                        <div>
                            <small>ADDITIONAL LEVEL</small>
                            <strong>${escapeHtml(item.floor_name || `Floor ${index + 2}`)}</strong>
                        </div>
                        <div class="floor-group-item-actions">
                            <button type="button" data-move="up" aria-label="Move floor up" ${index === 0 ? "disabled" : ""}>↑</button>
                            <button type="button" data-move="down" aria-label="Move floor down" ${index === floorGroupItems.length - 1 ? "disabled" : ""}>↓</button>
                            <button type="button" data-remove aria-label="Remove floor">×</button>
                        </div>
                    </div>
                    <div class="floor-group-fields">
                        <label>
                            <span>Floor name</span>
                            <input type="text" data-field="floor_name" value="${escapeHtml(item.floor_name)}" placeholder="Second floor">
                        </label>
                        <label>
                            <span>Floor number</span>
                            <input type="number" data-field="floor_number" value="${escapeHtml(item.floor_number)}" step="1">
                        </label>
                        <label class="floor-group-field-wide">
                            <span>Destination scene</span>
                            <select data-field="target_scene">${createFloorSceneOptions(item.target_scene)}</select>
                        </label>
                        <label>
                            <span>Direction</span>
                            <select data-field="direction">
                                <option value="up" ${item.direction === "up" ? "selected" : ""}>Up</option>
                                <option value="down" ${item.direction === "down" ? "selected" : ""}>Down</option>
                                <option value="same" ${item.direction === "same" ? "selected" : ""}>Same level</option>
                            </select>
                        </label>
                        <label class="floor-group-field-wide">
                            <span>Short description</span>
                            <input type="text" data-field="destination_label" value="${escapeHtml(item.destination_label)}" placeholder="Bedrooms, balcony and lounge">
                        </label>
                    </div>
                </div>
            `;

            card.querySelectorAll("[data-field]").forEach((input) => {
                input.addEventListener("input", () => {
                    const field = input.dataset.field;
                    floorGroupItems[index] = {
                        ...floorGroupItems[index],
                        [field]: field === "floor_number" ? Number(input.value || 0) : input.value,
                    };
                    if (field === "floor_name") {
                        const title = card.querySelector(".floor-group-item-top strong");
                        if (title) title.textContent = input.value || `Floor ${index + 2}`;
                    }
                    renderHotspotLivePreview();
                });
                input.addEventListener("change", () => input.dispatchEvent(new Event("input")));
            });
            card.querySelector('[data-move="up"]')?.addEventListener("click", () => moveFloorGroupItem(index, -1));
            card.querySelector('[data-move="down"]')?.addEventListener("click", () => moveFloorGroupItem(index, 1));
            card.querySelector("[data-remove]")?.addEventListener("click", () => {
                floorGroupItems.splice(index, 1);
                renderFloorGroupEditor();
                renderHotspotLivePreview();
            });
            list.appendChild(card);
        });
    }

    function loadFloorGroupEditor(content = {}, hotspot = null) {
        const items = Array.isArray(content.floor_items) && content.floor_items.length
            ? content.floor_items.map(normalizeFloorGroupItem)
            : [normalizeFloorGroupItem({
                floor_name: content.floor_name || hotspot?.title || hotspot?.label || "Ground floor",
                floor_number: content.floor_number ?? 0,
                direction: content.direction || "same",
                destination_label: content.destination_label || "",
                target_scene: hotspot?.target_scene || "",
            }, 0)];
        setPrimaryFloorFields(items[0]);
        floorGroupItems = items.slice(1);
        renderFloorGroupEditor();
    }

    function validateHotspotPayload(type) {
        if (!pendingHotspotPosition) {
            notify("Aucune position hotspot n'est définie.", "warning");
            return false;
        }

        if (type === "navigate" && !hotspotTargetScene?.value) {
            notify("Choisis une scène cible pour ce hotspot de navigation.", "warning");
            hotspotTargetScene?.focus?.();
            return false;
        }


        if (type === "floor") {
            const floors = getAllFloorGroupItems();
            if (!floors.length || floors.some((floor) => !floor.target_scene)) {
                notify("Select a destination scene for every floor.", "warning");
                const missing = document.querySelector('#floorGroupEditor select[data-field="target_scene"]:invalid, #floorGroupEditor select[data-field="target_scene"]');
                (missing || hotspotFloorTargetScene)?.focus?.();
                return false;
            }
            const ownerSceneId = getHotspotOwnerSceneId();
            if (floors.some((floor) => normalizeBuilderSceneId(floor.target_scene) === ownerSceneId)) {
                notify("A floor destination cannot be the current scene.", "warning");
                return false;
            }
            const seenTargets = new Set();
            for (const floor of floors) {
                const target = normalizeBuilderSceneId(floor.target_scene);
                if (seenTargets.has(target)) {
                    notify("Each floor must point to a different scene.", "warning");
                    return false;
                }
                seenTargets.add(target);
            }
        }

        if (type === "door" && !hotspotDoorTargetScene?.value) {
            notify("Choisis la scène derrière la porte.", "warning");
            hotspotDoorTargetScene?.focus?.();
            return false;
        }

        if (type === "navigate") {
            const ownerSceneId = getHotspotOwnerSceneId();
            const targetSceneId = normalizeBuilderSceneId(hotspotTargetScene?.value || "");

            if (ownerSceneId && targetSceneId && ownerSceneId === targetSceneId) {
                notify("La scène de destination ne peut pas être la scène actuelle.", "warning");
                hotspotTargetScene?.focus?.();
                return false;
            }
        }

        if (type === "product" && !(hotspotProductTitle?.value || hotspotLabel?.value)) {
            notify("Ajoute au moins un nom de produit.", "warning");
            hotspotProductTitle?.focus?.();
            return false;
        }

        return true;
    }

    function buildHotspotRequestPayload() {
        const type = hotspotType?.value || "navigate";

        let title = hotspotLabel?.value || "Hotspot";
        let description = "";
        let content = {};
        let display = {};

        if (type === "navigate") {
            content = {};
        }

        if (type === "info") {
            title = hotspotTitle?.value || hotspotLabel?.value || "Info";
            description = hotspotDescription?.value || "";
            content = {
                image_url: hotspotImageUrl?.value || "",
            };
        }

        if (type === "product") {
            title = hotspotProductTitle?.value || hotspotLabel?.value || "Product";
            description = hotspotProductDescription?.value || "";
            content = {
                image_url: hotspotImageUrlProduct?.value || "",
                cta_url: hotspotCtaUrl?.value || "",
                button_text: hotspotButtonText?.value || "",
                price: hotspotPrice?.value || "",
                badge: hotspotBadge?.value || "",
                site_name: hotspotSiteName?.value || "",
            };
        }

        if (type === "whatsapp") {
            content = {
                whatsapp_number: hotspotWhatsapp?.value || "",
                whatsapp_message: hotspotWhatsappMessage?.value || "",
            };
        }

        if (type === "phone") {
            content = {
                phone: hotspotPhone?.value || "",
            };
        }

        if (type === "email") {
            content = {
                email: hotspotEmail?.value || "",
            };
        }

        if (type === "cta") {
            title = hotspotWebsiteTitle?.value || hotspotLabel?.value || "Website";
            content = {
                cta_url: hotspotWebsiteUrl?.value || "",
                button_text: hotspotWebsiteButtonText?.value || "",
            };
        }

        if (type === "floor") {
            const floorItems = getAllFloorGroupItems();
            const primaryFloor = floorItems[0] || getPrimaryFloorItemFromFields();
            title = primaryFloor.floor_name || hotspotLabel?.value || "Floor navigation";
            content = {
                floor_name: primaryFloor.floor_name,
                floor_number: Number(primaryFloor.floor_number || 0),
                direction: primaryFloor.direction || "same",
                destination_label: primaryFloor.destination_label || "",
                floor_items: floorItems.map((item, index) => ({
                    uid: item.uid || `floor-${index + 1}`,
                    floor_name: item.floor_name,
                    floor_number: Number(item.floor_number || 0),
                    direction: item.direction || "same",
                    destination_label: item.destination_label || "",
                    target_scene: normalizeBuilderSceneId(item.target_scene),
                    order: index,
                })),
            };
        }
        if (type === "pdf") {
            title = hotspotPdfTitle?.value || hotspotLabel?.value || "Document";
            description = hotspotPdfDescription?.value || "";
            content = { document_url: hotspotPdfUrl?.value || "", allow_download: hotspotPdfDownload?.checked !== false, button_text: "Open PDF" };
        }
        if (type === "video") {
            title = hotspotVideoTitle?.value || hotspotLabel?.value || "Video";
            description = hotspotVideoDescription?.value || "";
            const url = hotspotVideoUrl?.value || "";
            content = { video_url: url, video_source: /youtu/.test(url) ? "youtube" : /vimeo/.test(url) ? "vimeo" : "upload", autoplay: !!hotspotVideoAutoplay?.checked, muted: !!hotspotVideoMuted?.checked, loop: !!hotspotVideoLoop?.checked };
            display = { ...(display || {}), variant: hotspotVideoDisplayMode?.value === "screen" ? "screen" : "pin", width: Number(hotspotVideoWidth?.value || 360), height: Number(hotspotVideoHeight?.value || 210), reference_fov: getSurfaceReferenceFovDeg() };
        }

        if (type === "door") {
            title = hotspotDoorLabel?.value || hotspotLabel?.value || "Open the door";
            description = "Interactive door navigation";
            content = { opening_direction: hotspotDoorDirection?.value || "left" };
            display = { ...(display || {}), variant: "door", width: Number(hotspotDoorWidth?.value || 180), height: Number(hotspotDoorHeight?.value || 320), reference_fov: getSurfaceReferenceFovDeg() };
        }

        if (type === "custom") {
            content = {
                tooltip: hotspotTooltip?.value || "",
            };
        }

        return {
            type,
            label: hotspotLabel?.value || "Hotspot",
            tooltip_text: hotspotTooltip?.value || "",
            title,
            description,
            target_scene: type === "floor" ? (getAllFloorGroupItems()[0]?.target_scene || null) : type === "door" ? (hotspotDoorTargetScene?.value || null) : (hotspotTargetScene?.value || null),
            yaw: pendingHotspotPosition.yaw,
            pitch: pendingHotspotPosition.pitch,
            selected_icon: hotspotSelectedIconInput?.value || selectedLibraryIcon || "default",
            payload: {
                display: {
                    variant: type === "video" && hotspotVideoDisplayMode?.value === "screen" ? "screen" : type === "door" ? "door" : (hotspotVariant?.value || "pin"),
                    size: Number(hotspotSize?.value || 56),
                    width: type === "video" ? Number(hotspotVideoWidth?.value || 360) : type === "door" ? Number(hotspotDoorWidth?.value || 180) : type === "floor" ? 94 : undefined,
                    height: type === "video" ? Number(hotspotVideoHeight?.value || 210) : type === "door" ? Number(hotspotDoorHeight?.value || 320) : type === "floor" ? 94 : undefined,
                    reference_fov: ["video", "door", "floor"].includes(type) ? getSurfaceReferenceFovDeg() : undefined,
                    rotation: Number(hotspotRotation?.value || 0),
                    offset_x: Number(hotspotOffsetX?.value || 0),
                    offset_y: Number(hotspotOffsetY?.value || 0),
                    anchor: hotspotAnchor?.value || "bottom",
                },
                content,
            },
        };
    }

    async function uploadHotspotImage(hotspotId, file) {
        if (!file || !hotspotId || !config.uploadHotspotImageBaseUrl) return "";

        const formData = new FormData();
        formData.append("image", file);

        const response = await fetch(`${config.uploadHotspotImageBaseUrl}${hotspotId}/upload-image/`, {
            method: "POST",
            headers: { "X-CSRFToken": getCSRFToken() },
            body: formData,
        });

        if (!response.ok) {
            notify("Unable to upload hotspot image.", "error");
            return "";
        }

        const data = await response.json();
        return data?.hotspot?.ad_image_url || "";
    }

    async function uploadHotspotMedia(hotspotId, type) {
        if (!hotspotId || !config.uploadHotspotMediaBaseUrl) return null;
        const media = type === "pdf" ? hotspotPdfFile?.files?.[0] : type === "video" ? hotspotVideoFile?.files?.[0] : null;
        const poster = type === "video" ? hotspotVideoPoster?.files?.[0] : null;
        if (!media && !poster) return null;
        const fd = new FormData();
        if (media) fd.append("media", media);
        if (poster) fd.append("poster", poster);
        const response = await fetch(`${config.uploadHotspotMediaBaseUrl}${hotspotId}/upload-media/`, { method: "POST", headers: { "X-CSRFToken": getCSRFToken() }, body: fd });
        if (!response.ok) { const e = await response.json().catch(()=>({})); notify(e.detail || "Unable to upload media.", "error"); return null; }
        return (await response.json()).hotspot;
    }

    async function createHotspotRequest() {
        const ownerSceneId = getHotspotOwnerSceneId();

        if (!ownerSceneId || !pendingHotspotPosition) {
            notify("No active scene.", "warning");
            return;
        }

        currentSceneId = ownerSceneId;

        const payload = buildHotspotRequestPayload();
        const type = payload.type;

        if (!validateHotspotPayload(type)) return;

        setButtonLoading(saveHotspotBtn, true, "Creating...");

        try {
            const response = await fetch(`${config.createHotspotBaseUrl}${encodeURIComponent(ownerSceneId)}/create-hotspot/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCSRFToken(),
                },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                notify("Unable to create hotspot.", "error");
                return;
            }

            const data = await response.json();
            let hotspot = data.hotspot;
            if (type === "pdf" || type === "video") hotspot = (await uploadHotspotMedia(hotspot.id, type)) || hotspot;

            const imageFile = getImageFileForType(type);
            if (imageFile) {
                const uploadedImageUrl = await uploadHotspotImage(hotspot.id, imageFile);

                if (uploadedImageUrl) {
                    hotspot.ad_image_url = uploadedImageUrl;
                    hotspot.payload = hotspot.payload || {};
                    hotspot.payload.content = hotspot.payload.content || {};
                    hotspot.payload.content.image_url = uploadedImageUrl;
                }
            }

            scenesData = scenesData.map(scene => {
                if (normalizeBuilderSceneId(scene.id) === ownerSceneId) {
                    const hotspots = Array.isArray(scene.hotspots) ? scene.hotspots : [];
                    return { ...scene, hotspots: [...hotspots, hotspot] };
                }

                return scene;
            });

            const activeScene = typeof findScene === "function"
                ? findScene(ownerSceneId)
                : findBuilderSceneById(ownerSceneId);

            if (activeScene) buildLayerScene(activeLayerKey, activeScene);

            closeHotspotModalFn();
            notify("Hotspot created successfully.", "success");
        } catch (error) {
            console.error(error);
            notify("Unable to create hotspot.", "error");
        } finally {
            setButtonLoading(saveHotspotBtn, false);
        }
    }

    async function updateHotspotRequest() {
        if (!editingHotspotId || !pendingHotspotPosition) return;

        const payload = buildHotspotRequestPayload();
        const type = payload.type;

        if (!validateHotspotPayload(type)) return;

        setButtonLoading(saveHotspotBtn, true, "Updating...");

        try {
            const response = await fetch(`${config.updateHotspotBaseUrl}${editingHotspotId}/update/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCSRFToken(),
                },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                notify("Unable to update hotspot.", "error");
                return;
            }

            const data = await response.json();
            let updatedHotspot = data.hotspot;
            if (type === "pdf" || type === "video") updatedHotspot = (await uploadHotspotMedia(updatedHotspot.id, type)) || updatedHotspot;

            const imageFile = getImageFileForType(type);
            if (imageFile) {
                const uploadedImageUrl = await uploadHotspotImage(updatedHotspot.id, imageFile);

                if (uploadedImageUrl) {
                    updatedHotspot.ad_image_url = uploadedImageUrl;
                    updatedHotspot.payload = updatedHotspot.payload || {};
                    updatedHotspot.payload.content = updatedHotspot.payload.content || {};
                    updatedHotspot.payload.content.image_url = uploadedImageUrl;
                }
            }

            scenesData = scenesData.map(scene => ({
                ...scene,
                hotspots: (scene.hotspots || []).map(h =>
                    String(h.id) === String(updatedHotspot.id) ? updatedHotspot : h
                ),
            }));

            selectedHotspotId = updatedHotspot.id;
            selectedHotspotDraft = cloneHotspotForDraft(updatedHotspot);

            const activeScene = findScene(currentSceneId);
            if (activeScene) buildLayerScene(activeLayerKey, activeScene);

            closeHotspotModalFn();
            notify("Hotspot updated successfully.", "success");
        } catch (error) {
            console.error(error);
            notify("Unable to update hotspot.", "error");
        } finally {
            setButtonLoading(saveHotspotBtn, false);
        }
    }

    async function saveHotspotHandler() {
        if (editingHotspotId) {
            await updateHotspotRequest();
        } else {
            await createHotspotRequest();
        }
    }

    async function createHotspotAtCenter() {
        const ownerSceneId = getHotspotOwnerSceneId();

        if (!ownerSceneId) {
            notify("No active scene.", "warning");
            return;
        }

        setBuilderCurrentScene(ownerSceneId, { skipTargetRefresh: true });

        const center = getCenterViewCoordinates();

        if (!center) {
            notify("No active scene.", "warning");
            return;
        }

        openHotspotModal({
            yaw: center.yaw,
            pitch: center.pitch,
        });
    }

    async function deleteHotspot(hotspotId) {
        try {
            const response = await fetch(`${config.deleteHotspotBaseUrl}${hotspotId}/delete/`, {
                method: "POST",
                headers: { "X-CSRFToken": getCSRFToken() },
            });

            if (!response.ok) {
                notify("Unable to delete hotspot.", "error");
                return;
            }

            const ownerSceneId = findSceneIdOwningHotspot(hotspotId) || getHotspotOwnerSceneId();

            scenesData = scenesData.map(scene => {
                if (normalizeBuilderSceneId(scene.id) === normalizeBuilderSceneId(ownerSceneId)) {
                    return {
                        ...scene,
                        hotspots: (scene.hotspots || []).filter(h => String(h.id) !== String(hotspotId)),
                    };
                }

                return scene;
            });

            selectedHotspotId = null;
            selectedHotspotDraft = null;
            hideHotspotHud();
            closeHotspotInfoPopup();

            const activeScene = findScene(currentSceneId);
            if (activeScene) buildLayerScene(activeLayerKey, activeScene);

            notify("Hotspot deleted.", "success");
        } catch (error) {
            console.error(error);
            notify("Unable to delete hotspot.", "error");
        }
    }

    async function deleteEditingHotspot() {
        if (!editingHotspotId) return;

        const confirmed = await confirmAction("Delete this hotspot?", "Delete hotspot");
        if (!confirmed) return;

        setButtonLoading(deleteHotspotBtn, true, "Deleting...");
        await deleteHotspot(editingHotspotId);
        setButtonLoading(deleteHotspotBtn, false);
        closeHotspotModalFn();
    }

    function showTourSaving(isSaving) {
        if (!tourTitleSaving) return;
        tourTitleSaving.classList.toggle("hidden", !isSaving);
    }

    function enterTourTitleEditMode() {
        if (!tourTitleText || !tourTitleInput) return;

        tourTitleText.classList.add("hidden");
        tourTitleInput.classList.remove("hidden");
        tourTitleInput.focus();
        tourTitleInput.select();
    }

    function exitTourTitleEditMode() {
        if (!tourTitleText || !tourTitleInput) return;

        tourTitleInput.classList.add("hidden");
        tourTitleText.classList.remove("hidden");
    }

    async function saveTourTitleNow() {
        if (!tourTitleInput || !tourTitleText || !config.updateTourBaseUrl || !config.tourId) return;

        const newTitle = (tourTitleInput.value || "").trim() || "Untitled Tour";

        if (newTitle === lastSavedTourTitle) {
            tourTitleText.textContent = newTitle;
            exitTourTitleEditMode();
            showTourSaving(false);
            return;
        }

        showTourSaving(true);

        try {
            const response = await fetch(`${config.updateTourBaseUrl}${config.tourId}/update/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCSRFToken(),
                },
                body: JSON.stringify({ title: newTitle }),
            });

            if (!response.ok) throw new Error("Unable to save");

            const data = await response.json();
            const savedTitle = data?.tour?.title || newTitle;

            lastSavedTourTitle = savedTitle;
            tourTitleInput.value = savedTitle;
            tourTitleText.textContent = savedTitle;
            document.title = `${savedTitle} - Builder`;
            exitTourTitleEditMode();
        } catch (error) {
            console.error("Tour title save error:", error);
            notify("Unable to save tour title.", "error");
        } finally {
            showTourSaving(false);
        }
    }

    function scheduleTourTitleAutosave() {
        if (!tourTitleInput || !tourTitleText) return;

        const draftTitle = (tourTitleInput.value || "").trim() || "Untitled Tour";
        tourTitleText.textContent = draftTitle;

        if (tourTitleSaveTimeout) clearTimeout(tourTitleSaveTimeout);

        showTourSaving(true);
        tourTitleSaveTimeout = setTimeout(async () => {
            await saveTourTitleNow();
        }, 700);
    }

    function bindModalPreviewInputs() {
        const inputs = [
            hotspotType,
            hotspotLabel,
            hotspotTooltip,
            hotspotTitle,
            hotspotDescription,
            hotspotTargetScene,
            hotspotVariant,
            hotspotSize,
            hotspotRotation,
            hotspotAnchor,
            hotspotOffsetX,
            hotspotOffsetY,
            hotspotImageUpload,
            hotspotImageUrl,
            hotspotProductTitle,
            hotspotProductDescription,
            hotspotImageUploadProduct,
            hotspotImageUrlProduct,
            hotspotPrice,
            hotspotBadge,
            hotspotButtonText,
            hotspotCtaUrl,
            hotspotSiteName,
            hotspotWhatsapp,
            hotspotWhatsappMessage,
            hotspotPhone,
            hotspotEmail,
            hotspotWebsiteTitle,
            hotspotWebsiteButtonText,
            hotspotWebsiteUrl,
        ];

        inputs.forEach(input => {
            input?.addEventListener("input", renderHotspotLivePreview);
            input?.addEventListener("change", renderHotspotLivePreview);
        });
    }

    addSceneBtn?.addEventListener("click", () => sceneFileInput?.click());

    sceneFileInput?.addEventListener("change", async (e) => {
        await uploadFiles(e.target.files);
        e.target.value = "";
    });

    dropZone?.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });

    dropZone?.addEventListener("dragleave", () => {
        dropZone.classList.remove("dragover");
    });

    dropZone?.addEventListener("drop", async (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        await uploadFiles(e.dataTransfer.files);
    });

    saveSceneBtn?.addEventListener("click", saveScene);
    scenePublicInput?.addEventListener("change", updateScenePublicDraft);
    tripodLogoPlaceBtn?.addEventListener("click", placeTripodLogoAtCurrentView);
    tripodLogoNadirBtn?.addEventListener("click", placeTripodLogoAtNadir);
    [tripodLogoEnabled, tripodLogoSize, tripodLogoYaw, tripodLogoPitch, tripodLogoOffsetX, tripodLogoOffsetY, tripodLogoRotation, tripodLogoTiltX, tripodLogoTiltY, tripodLogoRadius].forEach(input => {
        input?.addEventListener("input", () => updateTripodLogoDraft());
        input?.addEventListener("change", () => updateTripodLogoDraft());
    });
    setCurrentViewBtn?.addEventListener("click", setCurrentViewToInputs);
    createCenterHotspotBtn?.addEventListener("click", createHotspotAtCenter);

    [yawInput, pitchInput, hfovInput].forEach(input => {
        input?.addEventListener("change", applyInputsToCurrentView);
    });

    toolButtons.forEach(btn => {
        btn.addEventListener("click", () => setActiveTool(btn.dataset.tool));
    });

    hotspotType?.addEventListener("change", () => {
        const type = hotspotType.value;
        updateHotspotTypePanels(type);
        applyTypeDefaults(type);
    });

    hotspotIconOptions.forEach(btn => {
        btn.addEventListener("click", () => {
            activateIconOption(btn.dataset.icon);
        });
    });

    cameraLeftBtn?.addEventListener("click", () => nudgeCamera(-degreesToRadians(12), 0, 0));
    cameraRightBtn?.addEventListener("click", () => nudgeCamera(degreesToRadians(12), 0, 0));
    cameraUpBtn?.addEventListener("click", () => nudgeCamera(0, degreesToRadians(8), 0));
    cameraDownBtn?.addEventListener("click", () => nudgeCamera(0, -degreesToRadians(8), 0));
    zoomInBtn?.addEventListener("click", () => nudgeCamera(0, 0, -degreesToRadians(8)));
    zoomOutBtn?.addEventListener("click", () => nudgeCamera(0, 0, degreesToRadians(8)));
    resetViewBtn?.addEventListener("click", resetCurrentView);

    fullscreenBtn?.addEventListener("click", () => {
        if (panoramaViewer.requestFullscreen) {
            panoramaViewer.requestFullscreen();
        }
    });

    panoramaViewer?.addEventListener("click", (e) => {
        if (!hotspotModal?.classList.contains("hidden")) return;

        if (currentTool !== "hotspot" && currentTool !== "navigate") {
            closeHotspotInfoPopup();
        }

        if (isSceneTransitioning) return;
        if (currentTool !== "hotspot" && currentTool !== "navigate") return;

        const activeLayerEl = getLayerEl(activeLayerKey);
        const activeView = layerViews[activeLayerKey];

        if (!activeLayerEl || !activeView) return;

        const rect = activeLayerEl.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const coords = activeView.screenToCoordinates({ x, y });
        if (!coords) return;

        openHotspotModal({
            yaw: coords.yaw,
            pitch: coords.pitch,
        });
    });

    hotspotPopupClose?.addEventListener("click", closeHotspotInfoPopup);

    hudMoveLeft?.addEventListener("click", () => {
        updateSelectedHotspotDraft(h => {
            h.payload = h.payload || {};
            h.payload.display = h.payload.display || {};
            h.payload.display.offset_x = Number(h.payload.display.offset_x || 0) - 4;
        });
    });

    hudMoveRight?.addEventListener("click", () => {
        updateSelectedHotspotDraft(h => {
            h.payload = h.payload || {};
            h.payload.display = h.payload.display || {};
            h.payload.display.offset_x = Number(h.payload.display.offset_x || 0) + 4;
        });
    });

    hudMoveUp?.addEventListener("click", () => {
        updateSelectedHotspotDraft(h => {
            h.payload = h.payload || {};
            h.payload.display = h.payload.display || {};
            h.payload.display.offset_y = Number(h.payload.display.offset_y || 0) - 4;
        });
    });

    hudMoveDown?.addEventListener("click", () => {
        updateSelectedHotspotDraft(h => {
            h.payload = h.payload || {};
            h.payload.display = h.payload.display || {};
            h.payload.display.offset_y = Number(h.payload.display.offset_y || 0) + 4;
        });
    });

    hudSizeMinus?.addEventListener("click", () => {
        updateSelectedHotspotDraft(h => {
            h.payload = h.payload || {};
            h.payload.display = h.payload.display || {};
            h.payload.display.size = Math.max(24, Number(h.payload.display.size || 56) - 4);
        });
    });

    hudSizePlus?.addEventListener("click", () => {
        updateSelectedHotspotDraft(h => {
            h.payload = h.payload || {};
            h.payload.display = h.payload.display || {};
            h.payload.display.size = Math.min(140, Number(h.payload.display.size || 56) + 4);
        });
    });

    hudRotateMinus?.addEventListener("click", () => {
        updateSelectedHotspotDraft(h => {
            h.payload = h.payload || {};
            h.payload.display = h.payload.display || {};
            h.payload.display.rotation = Number(h.payload.display.rotation || 0) - 5;
        });
    });

    hudRotatePlus?.addEventListener("click", () => {
        updateSelectedHotspotDraft(h => {
            h.payload = h.payload || {};
            h.payload.display = h.payload.display || {};
            h.payload.display.rotation = Number(h.payload.display.rotation || 0) + 5;
        });
    });

    hudSaveHotspot?.addEventListener("click", async () => {
        if (!selectedHotspotDraft) return;

        openEditHotspotModal(selectedHotspotDraft);
        await updateHotspotRequest();
        hideHotspotHud();
    });

    closeHotspotModal?.addEventListener("click", closeHotspotModalFn);
    cancelHotspotBtn?.addEventListener("click", closeHotspotModalFn);
    saveHotspotBtn?.addEventListener("click", saveHotspotHandler);
    deleteHotspotBtn?.addEventListener("click", deleteEditingHotspot);

    hotspotModal?.addEventListener("click", (e) => {
        if (e.target === hotspotModal) {
            closeHotspotModalFn();
        }
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && hotspotModal && !hotspotModal.classList.contains("hidden")) {
            closeHotspotModalFn();
        }
    });

    tourTitleText?.addEventListener("click", enterTourTitleEditMode);

    tourTitleInput?.addEventListener("input", () => {
        scheduleTourTitleAutosave();
    });

    tourTitleInput?.addEventListener("keydown", async (e) => {
        if (e.key === "Enter") {
            e.preventDefault();

            if (tourTitleSaveTimeout) {
                clearTimeout(tourTitleSaveTimeout);
                tourTitleSaveTimeout = null;
            }

            await saveTourTitleNow();
        }

        if (e.key === "Escape") {
            if (tourTitleSaveTimeout) {
                clearTimeout(tourTitleSaveTimeout);
                tourTitleSaveTimeout = null;
            }

            tourTitleInput.value = lastSavedTourTitle || "Untitled Tour";
            tourTitleText.textContent = lastSavedTourTitle || "Untitled Tour";
            showTourSaving(false);
            exitTourTitleEditMode();
        }
    });

    tourTitleInput?.addEventListener("blur", async () => {
        if (tourTitleSaveTimeout) {
            clearTimeout(tourTitleSaveTimeout);
            tourTitleSaveTimeout = null;
        }

        await saveTourTitleNow();
    });

    bindModalPreviewInputs();
    ensureFloorGroupEditor();
    renderFloorGroupEditor();
    decorateHotspotIconOptions();
    installBuilderSceneCaptureOnce();

    if (scenesData.length > 0) {
        sortScenesData();
        renderSceneList();
        loadInitialScene(scenesData[0].id);

        if (currentSceneId) {
            setBuilderCurrentScene(currentSceneId);
        } else if (scenesData?.length) {
            setBuilderCurrentScene(scenesData[0].id);
        }
    }
});
