document.addEventListener("DOMContentLoaded", () => {
    function removeLegacyDebugOverlays() {
        ["previewDebugDialog", "previewMobileDebug"].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.remove();
        });
    }

    removeLegacyDebugOverlays();
    window.addEventListener("pageshow", removeLegacyDebugOverlays);
    if (typeof Marzipano === "undefined") {
        return;
    }

    const config = window.PREVIEW_CONFIG || {};

    function parseJsonScript(id, fallback = []) {
        const el = document.getElementById(id);
        if (!el) return fallback;

        try {
            const parsed = JSON.parse(el.textContent || "[]");
            return Array.isArray(parsed) ? parsed : fallback;
        } catch (_) {
            return fallback;
        }
    }

    let scenes = parseJsonScript("preview-scenes-data", []);
    let sceneList = parseJsonScript("preview-scene-list-data", []);

    scenes = scenes.slice().sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

    // sceneList vient de la view Django: uniquement les scènes publiques.
    // Fallback de sécurité: si le template n'a pas encore scene_list_json,
    // on filtre côté JS avec is_public.
    sceneList = sceneList.length
        ? sceneList.slice().sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
        : scenes.filter((scene) => scene?.is_public !== false);

    const sceneLookup = new Map();
    scenes.forEach((scene) => {
        [scene?.id, scene?.scene_id, scene?.uuid, scene?.slug]
            .filter((value) => value !== undefined && value !== null && value !== "")
            .forEach((value) => sceneLookup.set(String(value), scene));
    });

    function getSceneAssets(sceneData) {
        const assets = sceneData?.assets || {};

        const preview =
            assets.preview ||
            assets.light ||
            sceneData?.image_360_preview_url ||
            sceneData?.thumbnail_url ||
            sceneData?.thumbnail_image_url ||
            "";

        const thumbnail =
            assets.thumbnail ||
            sceneData?.thumbnail_url ||
            sceneData?.thumbnail_image_url ||
            preview ||
            "";

        const mobile =
            assets.viewer_mobile ||
            assets.mobile ||
            sceneData?.image_360_mobile_url ||
            sceneData?.mobile_image_url ||
            sceneData?.image_360_url ||
            assets.viewer_desktop ||
            assets.desktop ||
            preview ||
            thumbnail ||
            "";

        const desktop =
            assets.viewer_desktop ||
            assets.desktop ||
            sceneData?.image_360_url ||
            sceneData?.image_360_desktop_url ||
            assets.original ||
            sceneData?.image_360_original_url ||
            mobile ||
            preview ||
            thumbnail ||
            "";

        const original = assets.original || sceneData?.image_360_original_url || "";
        const fallback = assets.fallback || desktop || mobile || preview || thumbnail || original || "";

        return { preview, thumbnail, mobile, desktop, original, fallback };
    }

    function getPreferredImageUrl(sceneData) {
        const assets = getSceneAssets(sceneData);

        if (isMobileViewport()) {
            return assets.mobile || assets.desktop || assets.original || assets.preview || assets.thumbnail || assets.fallback || "";
        }

        return assets.desktop || assets.original || assets.mobile || assets.preview || assets.thumbnail || assets.fallback || "";
    }

    function getSceneThumbnailUrl(sceneData) {
        const assets = getSceneAssets(sceneData);
        return assets.thumbnail || assets.preview || assets.mobile || assets.desktop || assets.fallback || "";
    }

    const $ = (id) => document.getElementById(id);

    const previewViewer = $("previewViewer");
    const previewLayerA = $("previewLayerA");
    const previewLayerB = $("previewLayerB");
    const previewMountA = $("previewMountA");
    const previewMountB = $("previewMountB");

    const previewIntroOverlay = $("previewIntroOverlay");

    const previewScenesList = $("previewScenesList");
    const sceneCountBadge = $("sceneCountBadge");
    const sceneStackToggle = $("sceneStackToggle");
    const previewSceneRail = $("previewSceneRail");
    const sceneStackMiniPreview = $("sceneStackMiniPreview");

    const prevSceneBtn = $("prevSceneBtn");
    const nextSceneBtn = $("nextSceneBtn");
    const zoomOutBtn = $("zoomOutBtn");
    const zoomInBtn = $("zoomInBtn");
    const resetViewBtn = $("resetViewBtn");
    const autorotateBtn = $("autorotateBtn");
    const focusModeBtn = $("focusModeBtn");
    const shareBtn = $("shareBtn");
    const fullscreenBtn = $("fullscreenBtn");

    const previewToast = $("previewToast");

    const previewInfoBackdrop = $("previewInfoBackdrop");
    const previewInfoPanel = $("previewInfoPanel");
    const previewInfoClose = $("previewInfoClose");
    const previewInfoMedia = $("previewInfoMedia");
    const previewInfoBadge = $("previewInfoBadge");
    const previewInfoTitle = $("previewInfoTitle");
    const previewInfoDescription = $("previewInfoDescription");
    const previewInfoPrice = $("previewInfoPrice");
    const previewInfoSite = $("previewInfoSite");
    const previewInfoAction = $("previewInfoAction");
    const previewInfoWhatsapp = $("previewInfoWhatsapp");
    const previewInfoContact = $("previewInfoContact");

    const viewers = { A: null, B: null };
    const views = { A: null, B: null };
    const marzipanoScenes = { A: null, B: null };


    let activeLayerKey = "A";
    let currentSceneId = null;
    let isTransitioning = false;

    let autorotateEnabled = false;
    let autorotateFrame = null;
    let autorotateLastTs = 0;

    let focusMode = false;
    let toastTimer = null;

    // Zoom Marzipano:
    // - FOV grand  = image dézoomée
    // - FOV petit  = image zoomée
    // Donc zoom 0 = FOV maximum.
    const MIN_FOV = degToRad(6);
    const MAX_FOV = degToRad(132);
    const ZERO_ZOOM_FOV = MAX_FOV;

    // On ne laisse plus hfov_default forcer un zoom initial.
    // Toutes les scènes commencent à zoom 0, surtout sur mobile.
    const EXTRA_WIDE_OFFSET = degToRad(0);
    const INITIAL_OPEN_ZOOM_OFFSET = degToRad(0);
    const NAVIGATION_ZOOM_IN_OFFSET_1 = degToRad(7);
    const NAVIGATION_ZOOM_IN_OFFSET_2 = degToRad(13);
    const SCENE_INCOMING_DEZOOM_OFFSET = degToRad(0);

    const MOBILE_EXTRA_WIDE_OFFSET = degToRad(0);
    const MOBILE_PINCH_SENSITIVITY = 2.15;

    const pinchState = {
        active: false,
        startDistance: 0,
        startFov: 0
    };

    function degToRad(deg) {
        return deg * Math.PI / 180;
    }

    function clamp(value, min, max) {
        return Math.min(Math.max(value, min), max);
    }

    function normalizeAngle(rad) {
        while (rad > Math.PI) rad -= 2 * Math.PI;
        while (rad < -Math.PI) rad += 2 * Math.PI;
        return rad;
    }

    function isMobileViewport() {
        return window.matchMedia("(max-width: 768px)").matches;
    }
    function setupResponsiveMode() {
        if (!window.matchMedia) return;

        const mql = window.matchMedia("(max-width: 768px), (max-height: 700px)");

        function applyMode() {
            document.body.classList.toggle("mobile", mql.matches);
            document.body.classList.toggle("desktop", !mql.matches);
        }

        applyMode();

        if (mql.addEventListener) {
            mql.addEventListener("change", applyMode);
        } else if (mql.addListener) {
            mql.addListener(applyMode);
        }

        document.body.classList.add("no-touch");

        window.addEventListener("touchstart", function onFirstTouch() {
            document.body.classList.remove("no-touch");
            document.body.classList.add("touch");
            window.removeEventListener("touchstart", onFirstTouch);
        }, { passive: true });
    }



    function injectPreviewCinematicStyles() {
        if (document.getElementById("preview-cinematic-js-style")) return;

        const style = document.createElement("style");
        style.id = "preview-cinematic-js-style";
        style.textContent = `
            .preview-viewer {
                position: relative;
                overflow: hidden;
                isolation: isolate;
                perspective: 1200px;
                transform-style: preserve-3d;
                background: #020617;
            }

            .preview-viewer canvas {
                width: 100% !important;
                height: 100% !important;
                display: block;
            }

            .preview-layer {
                position: absolute;
                inset: 0;
                z-index: 0;
                opacity: 0;
                pointer-events: none;
                transform: translate3d(0, 0, 0) scale(1);
                transform-origin: center center;
                filter: none;
                will-change: opacity, transform, filter;
                backface-visibility: hidden;
                transition:
                    opacity var(--preview-cinematic-ms, 1180ms) cubic-bezier(.22,.9,.25,1),
                    transform var(--preview-cinematic-ms, 1180ms) cubic-bezier(.22,.9,.25,1),
                    filter var(--preview-cinematic-ms, 1180ms) cubic-bezier(.22,.9,.25,1);
            }

            .preview-layer.active-layer {
                z-index: 1;
                opacity: 1;
                pointer-events: auto;
            }

            .preview-layer.standby-layer {
                z-index: 0;
                opacity: 0;
                pointer-events: none;
            }

            .preview-mount {
                width: 100%;
                height: 100%;
            }

            .preview-layer.layer-incoming {
                z-index: 2;
                opacity: 0;
                pointer-events: none;
                transform: translate3d(0, 0, 0) scale(1.035);
                filter: blur(8px) brightness(.78) saturate(.94);
            }

            .preview-viewer.is-cinematic-transition .preview-layer.layer-incoming {
                opacity: 1;
                transform: translate3d(0, 0, 0) scale(1);
                filter: blur(0) brightness(1) saturate(1);
            }

            .preview-viewer.is-cinematic-transition .preview-layer.layer-outgoing {
                z-index: 1;
                opacity: 0;
                pointer-events: none;
                transform: translate3d(0, 0, 0) scale(1.075);
                filter: blur(7px) brightness(.62) saturate(.82);
            }

            .preview-viewer::before {
                content: "";
                position: absolute;
                inset: 0;
                z-index: 8;
                pointer-events: none;
                opacity: 0;
                background:
                    radial-gradient(circle at 50% 48%, rgba(255,255,255,.18), transparent 18%),
                    radial-gradient(circle at center, transparent 32%, rgba(2,6,23,.48) 72%, rgba(2,6,23,.72) 100%),
                    linear-gradient(90deg, rgba(2,6,23,.36), transparent 24%, transparent 76%, rgba(2,6,23,.36));
            }

            .preview-viewer::after {
                content: "";
                position: absolute;
                inset: 0;
                z-index: 9;
                pointer-events: none;
                opacity: 0;
                box-shadow:
                    inset 0 10vh 0 rgba(2, 6, 23, .46),
                    inset 0 -10vh 0 rgba(2, 6, 23, .46);
            }

            .preview-viewer.is-cinematic-transition::before {
                animation: previewCinematicFlash var(--preview-cinematic-ms, 1180ms) cubic-bezier(.22,.9,.25,1) both;
            }

            .preview-viewer.is-cinematic-transition::after {
                animation: previewCinematicBars var(--preview-cinematic-ms, 1180ms) cubic-bezier(.22,.9,.25,1) both;
            }

            .preview-viewer.is-opening::before {
                animation: previewOpeningVignette 520ms ease both;
            }

            @keyframes previewCinematicFlash {
                0% { opacity: 0; }
                14% { opacity: .50; }
                42% { opacity: .28; }
                72% { opacity: .18; }
                100% { opacity: 0; }
            }

            @keyframes previewCinematicBars {
                0% { opacity: 0; }
                16% { opacity: .95; }
                58% { opacity: .78; }
                100% { opacity: 0; }
            }

            @keyframes previewOpeningVignette {
                0% { opacity: .72; }
                100% { opacity: 0; }
            }

            @media (max-width: 768px) {
                .preview-layer {
                    transition:
                        opacity var(--preview-cinematic-ms, 980ms) cubic-bezier(.22,.9,.25,1),
                        transform var(--preview-cinematic-ms, 980ms) cubic-bezier(.22,.9,.25,1),
                        filter var(--preview-cinematic-ms, 980ms) cubic-bezier(.22,.9,.25,1);
                }

                .preview-layer.layer-incoming {
                    transform: translate3d(0, 0, 0) scale(1.025);
                    filter: blur(5px) brightness(.82) saturate(.95);
                }

                .preview-viewer.is-cinematic-transition .preview-layer.layer-outgoing {
                    transform: translate3d(0, 0, 0) scale(1.045);
                    filter: blur(5px) brightness(.66) saturate(.86);
                }

                .preview-viewer::after {
                    box-shadow:
                        inset 0 7vh 0 rgba(2, 6, 23, .42),
                        inset 0 -7vh 0 rgba(2, 6, 23, .42);
                }
            }

            @media (prefers-reduced-motion: reduce) {
                .preview-layer {
                    transition: opacity 180ms ease !important;
                    transform: none !important;
                    filter: none !important;
                }

                .preview-viewer::before,
                .preview-viewer::after {
                    animation: none !important;
                    opacity: 0 !important;
                }
            }
        `;

        document.head.appendChild(style);
    }

    function getCinematicTransitionMs() {
        return isMobileViewport() ? 980 : 1180;
    }

    function getCinematicCameraMs() {
        return isMobileViewport() ? 620 : 760;
    }

    function getLayerEl(key) {
        return key === "A" ? previewLayerA : previewLayerB;
    }

    function getMountEl(key) {
        return key === "A" ? previewMountA : previewMountB;
    }

    function standbyLayerKey() {
        return activeLayerKey === "A" ? "B" : "A";
    }

    function getSceneIdentifier(scene) {
        return String(scene.slug || scene.uuid || scene.id);
    }

    function getSceneShareUrl(scene) {
        const url = new URL(window.location.href);
        url.searchParams.set("s", getSceneIdentifier(scene));
        return url.toString();
    }

    function syncSceneInUrl(scene) {
        const url = new URL(window.location.href);
        url.searchParams.set("s", getSceneIdentifier(scene));
        window.history.replaceState({}, "", url.toString());
    }

    function getInitialSceneFromUrl() {
        const url = new URL(window.location.href);
        const sceneParam = url.searchParams.get("s");
        if (!sceneParam) return null;

        return scenes.find(scene =>
            String(scene.id) === String(sceneParam) ||
            String(scene.slug) === String(sceneParam) ||
            String(scene.uuid) === String(sceneParam)
        ) || null;
    }

    function getSceneKeys(scene) {
        return [scene?.id, scene?.scene_id, scene?.uuid, scene?.slug]
            .filter((value) => value !== undefined && value !== null && value !== "")
            .map((value) => String(value));
    }

    function sceneMatchesId(scene, sceneId) {
        if (sceneId === undefined || sceneId === null) return false;
        return getSceneKeys(scene).includes(String(sceneId));
    }

    function findScene(sceneId) {
        if (sceneId === undefined || sceneId === null) return null;
        return sceneLookup.get(String(sceneId)) || scenes.find(scene => sceneMatchesId(scene, sceneId)) || null;
    }

    function findSceneIndex(sceneId) {
        return scenes.findIndex(scene => sceneMatchesId(scene, sceneId));
    }

    function findSceneListIndex(sceneId) {
        return sceneList.findIndex(scene => sceneMatchesId(scene, sceneId));
    }

    function getPublicSceneEntry(sceneId) {
        return sceneList.find(scene => sceneMatchesId(scene, sceneId)) || null;
    }

    function getNavigationSceneList() {
        return sceneList.length ? sceneList : scenes;
    }

    function resolveIcon(iconName) {
        if (config.businessIconMap && config.businessIconMap[iconName]) {
            return config.businessIconMap[iconName];
        }
        if (config.iconMap && config.iconMap[iconName]) {
            return config.iconMap[iconName];
        }
        return config.iconMap?.default || "";
    }

    function getSceneBaseFov(scene) {
        // Zoom 0: on ignore hfov_default pour ne pas commencer déjà zoomé.
        return ZERO_ZOOM_FOV;
    }

    function getSceneFinalFov(scene) {
        // Vue maximale au chargement et après chaque changement de scène.
        return clamp(ZERO_ZOOM_FOV, MIN_FOV, MAX_FOV);
    }

    function getCurrentView() {
        return views[activeLayerKey];
    }

    function updateAllViewerSizes() {
        try {
            Object.values(viewers).forEach((viewer) => {
                if (viewer && typeof viewer.updateSize === "function") {
                    viewer.updateSize();
                }
            });
        } catch (_) {}
    }

    function showToast(message) {
        if (!previewToast) return;
        previewToast.textContent = message;
        clearTimeout(toastTimer);
        previewToast.classList.add("toast-show");
        toastTimer = setTimeout(() => {
            previewToast.classList.remove("toast-show");
        }, 1700);
    }

    const imageZoomState = {
        overlay: null,
        image: null,
        scale: 1,
        translateX: 0,
        translateY: 0,
        isDragging: false,
        dragStartX: 0,
        dragStartY: 0,
        startTranslateX: 0,
        startTranslateY: 0,
        pointers: new Map(),
        pinchStartDistance: 0,
        pinchStartScale: 1
    };

    function injectImageZoomStyles() {
        if (document.getElementById("previewImageZoomStyles")) return;

        const style = document.createElement("style");
        style.id = "previewImageZoomStyles";
        style.textContent = `
            .info-media-image-zoomable {
                cursor: zoom-in;
                transition: transform .22s ease, filter .22s ease;
            }

            .info-media-image-zoomable:hover {
                transform: scale(1.018);
                filter: saturate(1.06) contrast(1.03);
            }

            .preview-image-zoom-overlay {
                position: fixed;
                inset: 0;
                z-index: 99999;
                display: none;
                align-items: center;
                justify-content: center;
                background: rgba(2, 6, 23, .88);
                backdrop-filter: blur(14px);
                -webkit-backdrop-filter: blur(14px);
                opacity: 0;
                transition: opacity .18s ease;
                touch-action: none;
            }

            .preview-image-zoom-overlay.open {
                display: flex;
                opacity: 1;
            }

            .preview-image-zoom-stage {
                position: absolute;
                inset: 0;
                display: flex;
                align-items: center;
                justify-content: center;
                overflow: hidden;
                touch-action: none;
                user-select: none;
                -webkit-user-select: none;
            }

            .preview-image-zoom-img {
                max-width: 94vw;
                max-height: 86vh;
                object-fit: contain;
                border-radius: 22px;
                box-shadow: 0 30px 90px rgba(0,0,0,.55);
                transform-origin: center center;
                will-change: transform;
                transition: transform .12s ease;
                cursor: zoom-in;
                user-select: none;
                -webkit-user-drag: none;
            }

            .preview-image-zoom-overlay.zoomed .preview-image-zoom-img {
                cursor: grab;
            }

            .preview-image-zoom-overlay.dragging .preview-image-zoom-img {
                cursor: grabbing;
                transition: none;
            }

            .preview-image-zoom-toolbar {
                position: absolute;
                top: max(18px, env(safe-area-inset-top));
                right: max(18px, env(safe-area-inset-right));
                z-index: 2;
                display: flex;
                gap: 10px;
                padding: 8px;
                border: 1px solid rgba(255,255,255,.16);
                border-radius: 999px;
                background: rgba(15, 23, 42, .68);
                box-shadow: 0 18px 50px rgba(0,0,0,.3);
            }

            .preview-image-zoom-btn {
                width: 42px;
                height: 42px;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                border: 0;
                border-radius: 999px;
                color: #fff;
                background: rgba(255,255,255,.14);
                font-size: 19px;
                font-weight: 900;
                line-height: 1;
                cursor: pointer;
                transition: transform .18s ease, background .18s ease;
            }

            .preview-image-zoom-btn:hover {
                transform: translateY(-1px);
                background: rgba(255,255,255,.24);
            }

            .preview-image-zoom-hint {
                position: absolute;
                left: 50%;
                bottom: max(20px, env(safe-area-inset-bottom));
                transform: translateX(-50%);
                z-index: 2;
                max-width: calc(100vw - 36px);
                padding: 9px 14px;
                border-radius: 999px;
                color: rgba(255,255,255,.86);
                background: rgba(15, 23, 42, .64);
                font-size: 12px;
                font-weight: 700;
                text-align: center;
                pointer-events: none;
            }

            @media (max-width: 768px) {
                .preview-image-zoom-img {
                    max-width: 96vw;
                    max-height: 78vh;
                    border-radius: 18px;
                }

                .preview-image-zoom-toolbar {
                    top: max(12px, env(safe-area-inset-top));
                    right: max(12px, env(safe-area-inset-right));
                    gap: 7px;
                    padding: 6px;
                }

                .preview-image-zoom-btn {
                    width: 38px;
                    height: 38px;
                    font-size: 17px;
                }
            }
        `;

        document.head.appendChild(style);
    }

    function clampImageTranslate() {
        if (imageZoomState.scale <= 1.02) {
            imageZoomState.translateX = 0;
            imageZoomState.translateY = 0;
            return;
        }

        const maxX = Math.min(window.innerWidth * 0.55 * imageZoomState.scale, window.innerWidth * 1.2);
        const maxY = Math.min(window.innerHeight * 0.55 * imageZoomState.scale, window.innerHeight * 1.2);

        imageZoomState.translateX = clamp(imageZoomState.translateX, -maxX, maxX);
        imageZoomState.translateY = clamp(imageZoomState.translateY, -maxY, maxY);
    }

    function applyImageZoomTransform() {
        if (!imageZoomState.image || !imageZoomState.overlay) return;

        clampImageTranslate();

        imageZoomState.image.style.transform = `translate3d(${imageZoomState.translateX}px, ${imageZoomState.translateY}px, 0) scale(${imageZoomState.scale})`;
        imageZoomState.overlay.classList.toggle("zoomed", imageZoomState.scale > 1.02);
    }

    function resetImageZoom() {
        imageZoomState.scale = 1;
        imageZoomState.translateX = 0;
        imageZoomState.translateY = 0;
        imageZoomState.pointers.clear();
        imageZoomState.pinchStartDistance = 0;
        imageZoomState.pinchStartScale = 1;
        applyImageZoomTransform();
    }

    function setImageZoomScale(nextScale) {
        imageZoomState.scale = clamp(nextScale, 1, 5);
        applyImageZoomTransform();
    }

    function getImagePointerDistance() {
        const points = Array.from(imageZoomState.pointers.values());
        if (points.length < 2) return 0;

        const dx = points[0].clientX - points[1].clientX;
        const dy = points[0].clientY - points[1].clientY;
        return Math.sqrt(dx * dx + dy * dy);
    }

    function closeImageZoomViewer() {
        if (!imageZoomState.overlay) return;

        imageZoomState.overlay.classList.remove("open", "dragging", "zoomed");
        document.body.classList.remove("image-zoom-open");
        imageZoomState.pointers.clear();
        imageZoomState.isDragging = false;
    }

    function ensureImageZoomViewer() {
        injectImageZoomStyles();

        if (imageZoomState.overlay && imageZoomState.image) {
            return imageZoomState.overlay;
        }

        const overlay = document.createElement("div");
        overlay.id = "previewImageZoomOverlay";
        overlay.className = "preview-image-zoom-overlay";
        overlay.innerHTML = `
            <div class="preview-image-zoom-toolbar" data-image-zoom-toolbar>
                <button type="button" class="preview-image-zoom-btn" data-image-zoom="out" aria-label="Zoom out">−</button>
                <button type="button" class="preview-image-zoom-btn" data-image-zoom="reset" aria-label="Reset zoom">1×</button>
                <button type="button" class="preview-image-zoom-btn" data-image-zoom="in" aria-label="Zoom in">+</button>
                <button type="button" class="preview-image-zoom-btn" data-image-zoom="close" aria-label="Close">×</button>
            </div>
            <div class="preview-image-zoom-stage" data-image-zoom-stage>
                <img class="preview-image-zoom-img" alt="Zoomed image" draggable="false">
            </div>
            <div class="preview-image-zoom-hint">Scroll / pinch to zoom • drag to move • double click to reset</div>
        `;

        document.body.appendChild(overlay);

        const stage = overlay.querySelector("[data-image-zoom-stage]");
        const image = overlay.querySelector(".preview-image-zoom-img");

        imageZoomState.overlay = overlay;
        imageZoomState.image = image;

        overlay.addEventListener("click", (event) => {
            if (event.target === overlay || event.target === stage) {
                closeImageZoomViewer();
            }
        });

        overlay.querySelectorAll("[data-image-zoom]").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();

                const action = button.dataset.imageZoom;
                if (action === "close") closeImageZoomViewer();
                if (action === "reset") resetImageZoom();
                if (action === "in") setImageZoomScale(imageZoomState.scale + 0.35);
                if (action === "out") setImageZoomScale(imageZoomState.scale - 0.35);
            });
        });

        overlay.addEventListener("wheel", (event) => {
            event.preventDefault();
            event.stopPropagation();

            const direction = event.deltaY > 0 ? -1 : 1;
            setImageZoomScale(imageZoomState.scale + direction * 0.25);
        }, { passive: false });

        image.addEventListener("dblclick", (event) => {
            event.preventDefault();
            event.stopPropagation();

            if (imageZoomState.scale > 1.02) {
                resetImageZoom();
            } else {
                setImageZoomScale(2.2);
            }
        });

        stage.addEventListener("pointerdown", (event) => {
            event.preventDefault();
            event.stopPropagation();

            imageZoomState.pointers.set(event.pointerId, {
                clientX: event.clientX,
                clientY: event.clientY
            });

            if (imageZoomState.pointers.size === 2) {
                imageZoomState.pinchStartDistance = getImagePointerDistance();
                imageZoomState.pinchStartScale = imageZoomState.scale;
                return;
            }

            if (imageZoomState.scale <= 1.02) return;

            imageZoomState.isDragging = true;
            imageZoomState.dragStartX = event.clientX;
            imageZoomState.dragStartY = event.clientY;
            imageZoomState.startTranslateX = imageZoomState.translateX;
            imageZoomState.startTranslateY = imageZoomState.translateY;
            overlay.classList.add("dragging");

            try { stage.setPointerCapture?.(event.pointerId); } catch (_) {}
        }, { passive: false });

        stage.addEventListener("pointermove", (event) => {
            if (!imageZoomState.pointers.has(event.pointerId)) return;

            event.preventDefault();
            event.stopPropagation();

            imageZoomState.pointers.set(event.pointerId, {
                clientX: event.clientX,
                clientY: event.clientY
            });

            if (imageZoomState.pointers.size >= 2 && imageZoomState.pinchStartDistance) {
                const currentDistance = getImagePointerDistance();
                if (currentDistance) {
                    const ratio = currentDistance / imageZoomState.pinchStartDistance;
                    setImageZoomScale(imageZoomState.pinchStartScale * ratio);
                }
                return;
            }

            if (!imageZoomState.isDragging) return;

            imageZoomState.translateX = imageZoomState.startTranslateX + (event.clientX - imageZoomState.dragStartX);
            imageZoomState.translateY = imageZoomState.startTranslateY + (event.clientY - imageZoomState.dragStartY);
            applyImageZoomTransform();
        }, { passive: false });

        function endImagePointer(event) {
            imageZoomState.pointers.delete(event.pointerId);

            if (imageZoomState.pointers.size < 2) {
                imageZoomState.pinchStartDistance = 0;
                imageZoomState.pinchStartScale = imageZoomState.scale;
            }

            if (imageZoomState.pointers.size === 0) {
                imageZoomState.isDragging = false;
                overlay.classList.remove("dragging");
            }
        }

        stage.addEventListener("pointerup", endImagePointer);
        stage.addEventListener("pointercancel", endImagePointer);
        stage.addEventListener("pointerleave", endImagePointer);

        return overlay;
    }

    function openImageZoomViewer(imageUrl, imageAlt = "Image") {
        if (!imageUrl) return;

        const overlay = ensureImageZoomViewer();
        const image = imageZoomState.image;

        image.src = imageUrl;
        image.alt = imageAlt || "Image";

        resetImageZoom();
        overlay.classList.add("open");
        document.body.classList.add("image-zoom-open");
    }

    function syncZoomButtonsState() {
        const view = getCurrentView();
        if (!view) return;

        const currentFov = view.fov();

        if (zoomInBtn) {
            zoomInBtn.disabled = currentFov <= MIN_FOV + 0.01;
            zoomInBtn.classList.toggle("opacity-40", zoomInBtn.disabled);
        }

        if (zoomOutBtn) {
            zoomOutBtn.disabled = currentFov >= MAX_FOV - 0.01;
            zoomOutBtn.classList.toggle("opacity-40", zoomOutBtn.disabled);
        }
    }

    function openSceneStack() {
        previewSceneRail?.classList.add("open");
        sceneStackToggle?.classList.add("open");
        document.body.classList.add("scene-rail-open");
    }

    function closeSceneStack() {
        previewSceneRail?.classList.remove("open");
        sceneStackToggle?.classList.remove("open");
        document.body.classList.remove("scene-rail-open");
    }

    function toggleSceneStack(event) {
        event?.stopPropagation();
        if (previewSceneRail?.classList.contains("open")) {
            closeSceneStack();
        } else {
            openSceneStack();
        }
    }

    function closeInfoPanel() {
        previewInfoPanel?.classList.remove("open");
        previewInfoBackdrop?.classList.remove("open");
        document.body.classList.remove("info-panel-open");
    }

    function openInfoPanel(hotspot) {
        if (!previewInfoPanel) return;

        const content = hotspot.payload?.content || {};
        const imageUrl =
            content.image_url ||
            content.product_image_url ||
            content.photo_url ||
            hotspot.image_url ||
            hotspot.ad_image_url ||
            "";
        const ctaUrl = content.cta_url || "";
        const buttonText = content.button_text || "Open";
        const badge = content.badge || "";
        const price = content.price || "";
        const siteName = content.site_name || "";
        const phone = content.phone || "";
        const email = content.email || "";
        const whatsappNumber = content.whatsapp_number || "";
        const whatsappMessage = content.whatsapp_message || "Hello";

        previewInfoMedia.innerHTML = "";

        if (imageUrl) {
            const infoImage = document.createElement("img");
            infoImage.src = imageUrl;
            infoImage.alt = hotspot.title || hotspot.label || "Hotspot";
            infoImage.className = "info-media-image info-media-image-zoomable";
            infoImage.loading = "lazy";
            infoImage.decoding = "async";
            infoImage.title = "Click to zoom";
            infoImage.setAttribute("role", "button");
            infoImage.setAttribute("tabindex", "0");

            infoImage.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                openImageZoomViewer(imageUrl, infoImage.alt);
            });

            infoImage.addEventListener("keydown", (event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    event.stopPropagation();
                    openImageZoomViewer(imageUrl, infoImage.alt);
                }
            });

            infoImage.onerror = () => {
                previewInfoMedia.innerHTML = `<div class="info-media-empty">Image unavailable</div>`;
            };

            previewInfoMedia.appendChild(infoImage);
        } else {
            previewInfoMedia.innerHTML = `<div class="info-media-empty">Preview unavailable</div>`;
        }

        previewInfoTitle.textContent = hotspot.title || hotspot.label || "Hotspot";
        previewInfoDescription.textContent = hotspot.description || hotspot.tooltip_text || "";

        if (badge) {
            previewInfoBadge.textContent = badge;
            previewInfoBadge.classList.remove("hidden");
        } else {
            previewInfoBadge.classList.add("hidden");
            previewInfoBadge.textContent = "";
        }

        if (price) {
            previewInfoPrice.textContent = price;
            previewInfoPrice.classList.remove("hidden");
        } else {
            previewInfoPrice.classList.add("hidden");
            previewInfoPrice.textContent = "";
        }

        if (siteName) {
            previewInfoSite.textContent = siteName;
            previewInfoSite.classList.remove("hidden");
        } else {
            previewInfoSite.classList.add("hidden");
            previewInfoSite.textContent = "";
        }

        if (ctaUrl) {
            previewInfoAction.href = ctaUrl;
            previewInfoAction.textContent = buttonText;
            previewInfoAction.classList.remove("hidden");
        } else {
            previewInfoAction.classList.add("hidden");
            previewInfoAction.removeAttribute("href");
        }

        if (whatsappNumber) {
            const cleanNumber = String(whatsappNumber).replace(/[^\d]/g, "");
            previewInfoWhatsapp.href = `https://wa.me/${cleanNumber}?text=${encodeURIComponent(whatsappMessage)}`;
            previewInfoWhatsapp.classList.remove("hidden");
        } else {
            previewInfoWhatsapp.classList.add("hidden");
            previewInfoWhatsapp.removeAttribute("href");
        }

        if (phone) {
            previewInfoContact.href = `tel:${phone}`;
            previewInfoContact.textContent = "Call";
            previewInfoContact.classList.remove("hidden");
        } else if (email) {
            previewInfoContact.href = `mailto:${email}`;
            previewInfoContact.textContent = "Email";
            previewInfoContact.classList.remove("hidden");
        } else {
            previewInfoContact.classList.add("hidden");
            previewInfoContact.removeAttribute("href");
        }

        previewInfoPanel.classList.add("open");
        previewInfoBackdrop?.classList.add("open");
        document.body.classList.add("info-panel-open");
    }

    function stopAutorotate() {
        autorotateEnabled = false;
        autorotateLastTs = 0;

        if (autorotateFrame) {
            cancelAnimationFrame(autorotateFrame);
            autorotateFrame = null;
        }

        autorotateBtn?.classList.remove("active");
    }

    function autorotateLoop(ts) {
        if (!autorotateEnabled) {
            autorotateFrame = null;
            autorotateLastTs = 0;
            return;
        }

        const view = getCurrentView();
        if (view) {
            if (!autorotateLastTs) autorotateLastTs = ts;
            const delta = (ts - autorotateLastTs) / 1000;
            autorotateLastTs = ts;

            const nextYaw = normalizeAngle(view.yaw() + degToRad(8) * delta);
            view.setParameters({ yaw: nextYaw });
        }

        autorotateFrame = requestAnimationFrame(autorotateLoop);
    }

    function startAutorotate() {
        if (autorotateEnabled) return;
        autorotateEnabled = true;
        autorotateBtn?.classList.add("active");
        autorotateFrame = requestAnimationFrame(autorotateLoop);
    }

    function toggleAutorotate() {
        if (autorotateEnabled) {
            stopAutorotate();
        } else {
            startAutorotate();
        }
    }

    function setFocusMode(enabled) {
        focusMode = !!enabled;
        document.body.classList.toggle("ui-hidden", focusMode);
        document.body.classList.toggle("preview-focus-mode", focusMode);
        focusModeBtn?.classList.toggle("active", focusMode);
    }

    function toggleFocusMode() {
        setFocusMode(!focusMode);
    }

    function renderSceneStackMini() {
        if (!sceneStackMiniPreview) return;

        sceneStackMiniPreview.innerHTML = "";

        const list = getNavigationSceneList();
        if (!list.length) return;

        let currentIndex = findSceneListIndex(currentSceneId);
        if (currentIndex < 0) currentIndex = 0;

        const miniScenes = [
            list[currentIndex],
            list[(currentIndex + 1) % list.length],
            list[(currentIndex + 2) % list.length]
        ].filter(Boolean);

        miniScenes.slice(0, 3).forEach((scene) => {
            const card = document.createElement("div");
            card.className = "scene-stack-mini-card";
            const thumb = getSceneThumbnailUrl(scene);
            card.innerHTML = thumb
                ? `<img src="${thumb}" alt="${scene.title || 'Scene'}">`
                : `<div class="scene-thumb-placeholder">360</div>`;
            sceneStackMiniPreview.appendChild(card);
        });
    }

    function renderSceneRail() {
        if (!previewScenesList) return;
        previewScenesList.innerHTML = "";

        const list = getNavigationSceneList();

        list.forEach((scene, index) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "scene-card";
            button.dataset.sceneId = scene.id;

            const thumb = getSceneThumbnailUrl(scene);

            button.innerHTML = `
                <div class="scene-thumb">
                    ${thumb ? `<img src="${thumb}" alt="${scene.title || 'Scene'}">` : `<div class="scene-thumb-placeholder">360</div>`}
                </div>
                <div class="scene-body">
                    <strong class="scene-title">${scene.title || "Untitled Scene"}</strong>
                    <span class="scene-subtitle">
                        <span class="scene-dot"></span>
                        Scene ${index + 1}
                    </span>
                </div>
            `;

            button.addEventListener("click", (event) => {
                event.stopPropagation();
                if (isTransitioning) return;

                const targetScene = findScene(scene.id) || findScene(scene.scene_id) || scene;
                if (!targetScene) return;

                closeInfoPanel();
                isTransitioning = true;
                cinematicSwitchScene(targetScene);
                closeSceneStack();
            });

            previewScenesList.appendChild(button);
        });
    }

    function markActiveSceneCard(sceneId) {
        document.querySelectorAll(".scene-card").forEach((card) => {
            card.classList.toggle("active", String(card.dataset.sceneId) === String(sceneId));
        });
        renderSceneStackMini();
    }

    function updateSceneMeta(scene) {
        if (sceneCountBadge) {
            // Affiche le nombre de scènes publiques disponibles dans le stack.
            sceneCountBadge.textContent = `${getNavigationSceneList().length}`;
        }

        markActiveSceneCard(scene?.id);
    }


    function stopTouchAndScrollEventPropagation(element) {
        if (!element) return;

        [
            "touchstart",
            "touchmove",
            "touchend",
            "touchcancel",
            "pointerdown",
            "pointermove",
            "pointerup",
            "pointercancel",
            "wheel"
        ].forEach((eventName) => {
            element.addEventListener(eventName, (event) => {
                event.stopPropagation();
            }, { passive: true });
        });
    }

    function buildHotspotNode(hotspot) {
        const display = hotspot.payload?.display || {};
        const variant = display.variant || "pin";
        const size = Number(display.size || 58);
        const rotation = Number(display.rotation || 0);
        const offsetX = Number(display.offset_x || 0);
        const offsetY = Number(display.offset_y || 0);
        const anchor = display.anchor || "bottom";

        const node = document.createElement("div");
        node.className = `preview-hotspot variant-${variant} anchor-${anchor}`;
        node.style.width = `${size}px`;
        node.style.height = variant === "label" ? "auto" : `${size}px`;
        node.style.transform = `translate(${offsetX}px, ${offsetY}px) rotate(${rotation}deg)`;

        const img = document.createElement("img");
        img.src = resolveIcon(hotspot.selected_icon || hotspot.icon || "default");
        img.alt = hotspot.label || hotspot.title || "Hotspot";

        if (variant === "label") {
            const span = document.createElement("span");
            span.textContent = hotspot.label || hotspot.title || "Hotspot";
            node.appendChild(img);
            node.appendChild(span);
        } else {
            node.appendChild(img);
        }

        stopTouchAndScrollEventPropagation(node);

        node.addEventListener("click", async (event) => {
            event.stopPropagation();

            if (hotspot.type === "navigate" && hotspot.target_scene) {
                await navigateToScene(hotspot.target_scene, hotspot);
                return;
            }

            openInfoPanel(hotspot);
        });

        return node;
    }

    function ensureViewer(key) {
        const mount = getMountEl(key);
        if (!mount) {
            return null;
        }

        mount.innerHTML = "";

        try {
            viewers[key] = new Marzipano.Viewer(mount, {
                controls: {
                    mouseViewMode: "drag"
                }
            });
        } catch (_) {
            return null;
        }

        return viewers[key];
    }


    function getSceneSourceGeometryAndLimiter(sceneData) {
        const mobile = isMobileViewport();


        if (sceneData?.tiles_url) {
            return {
                source: Marzipano.ImageUrlSource.fromString(
                    `${sceneData.tiles_url}/{z}/{f}/{y}/{x}.jpg`,
                    {
                        cubeMapPreviewUrl: `${sceneData.tiles_url}/preview.jpg`
                    }
                ),
                geometry: new Marzipano.CubeGeometry(
                    sceneData.levels || [
                        { tileSize: 256, size: 256, fallbackOnly: true },
                        { tileSize: 512, size: 512 },
                        { tileSize: 512, size: 1024 },
                        { tileSize: 512, size: 2048 }
                    ]
                ),
                limiter: Marzipano.RectilinearView.limit.traditional(
                    Math.max(
                        Number(sceneData.face_size || 0),
                        Number(sceneData.max_resolution || 0),
                        mobile ? 2048 : 4096
                    ),
                    MAX_FOV
                )
            };
        }

        // Résolution logique plus élevée pour permettre un vrai zoom avant,
        // surtout sur mobile où Marzipano bride vite le zoom si la largeur est trop basse.
        const logicalResolution = Math.max(
            Number(sceneData?.face_size || 0),
            Number(sceneData?.max_resolution || 0),
            mobile ? 3072 : 4096
        );
        const textureWidth = logicalResolution;
        const faceSize = logicalResolution;

        const preferredImageUrl = getPreferredImageUrl(sceneData);

        return {
            source: Marzipano.ImageUrlSource.fromString(preferredImageUrl),
            geometry: new Marzipano.EquirectGeometry([
                { width: textureWidth }
            ]),
            limiter: Marzipano.RectilinearView.limit.traditional(
                faceSize,
                MAX_FOV
            )
        };
    }

    function buildSceneOnLayer(layerKey, sceneData) {
        const viewer = ensureViewer(layerKey);
        const selectedImageUrl = getPreferredImageUrl(sceneData);

        if (!viewer || (!selectedImageUrl && !sceneData?.tiles_url)) {
            return null;
        }



        const { source, geometry, limiter } = getSceneSourceGeometryAndLimiter(sceneData);

        const yaw = degToRad(sceneData.yaw_default || 0);
        const pitch = degToRad(sceneData.pitch_default || 0);
        const fov = getSceneFinalFov(sceneData);

        views[layerKey] = new Marzipano.RectilinearView({ yaw, pitch, fov }, limiter);

        try {
            marzipanoScenes[layerKey] = viewer.createScene({
                source,
                geometry,
                view: views[layerKey],
                pinFirstLevel: true
            });

            marzipanoScenes[layerKey].switchTo();
        } catch (_) {
            return null;
        }

        (sceneData.hotspots || []).forEach((hotspot) => {
            const node = buildHotspotNode(hotspot);
            marzipanoScenes[layerKey].hotspotContainer().createHotspot(node, {
                yaw: hotspot.yaw,
                pitch: hotspot.pitch
            });
        });

        requestAnimationFrame(() => {
            updateAllViewerSizes();
            syncZoomButtonsState();
        });

        return marzipanoScenes[layerKey];
    }

    function runInitialReveal(scene) {
        const view = getCurrentView();
        if (!view || !scene) return;

        const finalFov = getSceneFinalFov(scene);
        const finalYaw = degToRad(scene.yaw_default || 0);
        const finalPitch = degToRad(scene.pitch_default || 0);

        // Démarrage direct à zoom 0, même sur mobile.
        // Pas de zoom automatique au chargement: l'utilisateur contrôle le zoom lui-même.
        previewViewer.classList.add("is-opening");

        view.setParameters({
            yaw: finalYaw,
            pitch: finalPitch,
            fov: clamp(finalFov - INITIAL_OPEN_ZOOM_OFFSET, MIN_FOV, MAX_FOV)
        });

        setTimeout(() => {
            previewIntroOverlay?.classList.add("is-hidden");
            document.body.classList.add("preview-has-loaded");
            syncZoomButtonsState();
        }, 220);

        setTimeout(() => {
            previewViewer.classList.remove("is-cinematic-transition", "transitioning", "is-opening");
            syncZoomButtonsState();
        }, 520);
    }

    function cinematicSwitchScene(targetScene, options = {}) {
        if (!targetScene) {
            isTransitioning = false;
            return;
        }

        const outgoingKey = activeLayerKey;
        const incomingKey = standbyLayerKey();
        const cinematicMs = getCinematicTransitionMs();
        const cameraMs = getCinematicCameraMs();

        previewViewer?.style?.setProperty("--preview-cinematic-ms", `${cinematicMs}ms`);

        buildSceneOnLayer(incomingKey, targetScene);

        const incomingView = views[incomingKey];
        const outgoingEl = getLayerEl(outgoingKey);
        const incomingEl = getLayerEl(incomingKey);

        const startYaw = options.fromYaw !== undefined
            ? options.fromYaw
            : degToRad(targetScene.yaw_default || 0);

        const startPitch = options.fromPitch !== undefined
            ? options.fromPitch
            : degToRad(targetScene.pitch_default || 0);

        const endYaw = degToRad(targetScene.yaw_default || 0);
        const endPitch = degToRad(targetScene.pitch_default || 0);

        const finalFov = getSceneFinalFov(targetScene);
        const incomingStartFov = clamp(
            finalFov - SCENE_INCOMING_DEZOOM_OFFSET,
            MIN_FOV,
            MAX_FOV
        );

        if (incomingView) {
            incomingView.setParameters({
                yaw: startYaw,
                pitch: startPitch,
                fov: incomingStartFov
            });
        }

        outgoingEl.classList.remove("standby-layer", "layer-incoming", "layer-outgoing");
        incomingEl.classList.remove("standby-layer", "layer-incoming", "layer-outgoing");

        outgoingEl.classList.add("active-layer");
        incomingEl.classList.add("layer-incoming");
        incomingEl.style.opacity = "0";

        previewViewer.classList.add("is-cinematic-transition", "transitioning");

        currentSceneId = targetScene.id;
        updateSceneMeta(targetScene);
        syncSceneInUrl(targetScene);

        requestAnimationFrame(() => {
            incomingEl.style.opacity = "1";
            outgoingEl.classList.add("layer-outgoing");
        });

        setTimeout(() => {
            if (incomingView) {
                incomingView.setParameters(
                    {
                        yaw: endYaw,
                        pitch: endPitch,
                        fov: finalFov
                    },
                    { transitionDuration: cameraMs }
                );
            }
        }, 70);

        setTimeout(() => {
            outgoingEl.classList.remove("active-layer", "layer-outgoing");
            outgoingEl.classList.add("standby-layer");
            outgoingEl.style.opacity = "0";

            incomingEl.classList.remove("layer-incoming", "standby-layer");
            incomingEl.classList.add("active-layer");
            incomingEl.style.opacity = "1";

            previewViewer.classList.remove("is-cinematic-transition", "transitioning");
            activeLayerKey = incomingKey;
            isTransitioning = false;
            updateAllViewerSizes();
            syncZoomButtonsState();
        }, cinematicMs);
    }

    async function navigateToScene(targetSceneId, hotspot) {
        if (isTransitioning) return;

        const targetScene = findScene(targetSceneId);
        const currentView = getCurrentView();
        if (!targetScene || !currentView) return;

        isTransitioning = true;
        closeInfoPanel();
        closeSceneStack();
        stopAutorotate();

        const hotspotYaw = normalizeAngle(Number(hotspot.yaw ?? currentView.yaw()));
        const hotspotPitch = Number(hotspot.pitch ?? currentView.pitch());

        const currentFov = currentView.fov();

        // Petit zoom cinéma vers le hotspot avant le changement.
        // On diminue le FOV pour zoomer, puis la nouvelle scène revient à zoom 0.
        const firstZoomOffset = isMobileViewport() ? degToRad(10) : degToRad(12);
        const secondZoomOffset = isMobileViewport() ? degToRad(20) : degToRad(24);

        const preSwitchFov = clamp(
            currentFov - firstZoomOffset,
            MIN_FOV,
            MAX_FOV
        );
        const preSwitchFov2 = clamp(
            currentFov - secondZoomOffset,
            MIN_FOV,
            MAX_FOV
        );

        currentView.setParameters(
            {
                yaw: hotspotYaw,
                pitch: hotspotPitch,
                fov: preSwitchFov
            },
            { transitionDuration: 260 }
        );

        setTimeout(() => {
            currentView.setParameters(
                {
                    yaw: hotspotYaw,
                    pitch: hotspotPitch,
                    fov: preSwitchFov2
                },
                { transitionDuration: 260 }
            );
            syncZoomButtonsState();
        }, 180);

        setTimeout(() => {
            cinematicSwitchScene(targetScene, {
                fromYaw: hotspotYaw,
                fromPitch: hotspotPitch
            });
        }, 420);
    }

    function zoomToFov(nextFov, duration = 220) {
        const view = getCurrentView();
        if (!view) return;

        view.setParameters(
            { fov: clamp(nextFov, MIN_FOV, MAX_FOV) },
            { transitionDuration: duration }
        );

        syncZoomButtonsState();
    }

    function zoomBy(deltaDeg, duration = 220) {
        const view = getCurrentView();
        if (!view) return;

        const nextFov = clamp(view.fov() + degToRad(deltaDeg), MIN_FOV, MAX_FOV);
        zoomToFov(nextFov, duration);
    }

    function resetCurrentView() {
        const scene = findScene(currentSceneId);
        const view = getCurrentView();
        if (!scene || !view) return;

        stopAutorotate();

        view.setParameters(
            {
                yaw: degToRad(scene.yaw_default || 0),
                pitch: degToRad(scene.pitch_default || 0),
                fov: getSceneFinalFov(scene)
            },
            { transitionDuration: 480 }
        );

        syncZoomButtonsState();
    }

    function goToRelativeScene(step) {
        const list = getNavigationSceneList();
        if (isTransitioning || !list.length) return;

        let currentIndex = findSceneListIndex(currentSceneId);
        if (currentIndex < 0) currentIndex = 0;

        const nextIndex = (currentIndex + step + list.length) % list.length;
        const sceneEntry = list[nextIndex];
        const targetScene = findScene(sceneEntry?.id) || findScene(sceneEntry?.scene_id) || sceneEntry;
        if (!targetScene) return;

        closeInfoPanel();
        closeSceneStack();
        isTransitioning = true;
        stopAutorotate();

        const currentView = getCurrentView();
        if (currentView) {
            const relativeZoomOffset = isMobileViewport() ? degToRad(12) : degToRad(16);
            const zoomInFov = clamp(
                currentView.fov() - relativeZoomOffset,
                MIN_FOV,
                MAX_FOV
            );

            currentView.setParameters(
                { fov: zoomInFov },
                { transitionDuration: 260 }
            );
            syncZoomButtonsState();

            setTimeout(() => {
                cinematicSwitchScene(targetScene);
            }, 300);
        } else {
            cinematicSwitchScene(targetScene);
        }
    }

    async function shareCurrentScene() {
        const scene = findScene(currentSceneId) || scenes[0];
        if (!scene) return;

        const shareUrl = getSceneShareUrl(scene);

        try {
            if (navigator.share) {
                await navigator.share({
                    title: document.title,
                    text: "Virtual Tour",
                    url: shareUrl
                });
                return;
            }

            await navigator.clipboard.writeText(shareUrl);
            showToast("Link copied");
        } catch (_) {
            showToast("Share unavailable");
        }
    }

    async function enterFullscreen() {
        try {
            if (previewViewer.requestFullscreen) {
                await previewViewer.requestFullscreen();
            }
        } catch (_) {}
    }

    function getTouchDistance(touches) {
        if (!touches || touches.length < 2) return 0;

        const dx = touches[0].clientX - touches[1].clientX;
        const dy = touches[0].clientY - touches[1].clientY;
        return Math.sqrt(dx * dx + dy * dy);
    }

    function setZoomInstant(nextFov) {
        const view = getCurrentView();
        if (!view) return;

        view.setParameters({ fov: clamp(nextFov, MIN_FOV, MAX_FOV) });
        syncZoomButtonsState();
    }

    function setupMobileZoomGestures() {
        if (!previewViewer) return;

        // MOBILE ZOOM FIX:
        // - 1 doigt: Marzipano garde le drag normal.
        // - 2 doigts: on force nous-mêmes le zoom en changeant le FOV.
        // - Pas de stopPropagation: Marzipano continue de recevoir les events.
        // - preventDefault seulement pendant le pinch pour empêcher le navigateur de zoomer la page.
        [previewViewer, previewLayerA, previewLayerB, previewMountA, previewMountB].forEach((el) => {
            if (!el) return;
            el.style.touchAction = "none";
            el.style.webkitUserSelect = "none";
            el.style.userSelect = "none";
        });

        let lastTapTs = 0;
        const activePointers = new Map();

        const localPinch = {
            active: false,
            startDistance: 0,
            startFov: 0
        };

        const pointerPinch = {
            active: false,
            startDistance: 0,
            startFov: 0
        };

        function shouldIgnoreZoomTarget(target) {
            return !!(
                target?.closest?.("#previewControlDock") ||
                target?.closest?.("#previewInfoPanel") ||
                target?.closest?.("#previewSceneRail") ||
                target?.closest?.("#previewImageZoomOverlay") ||
                target?.closest?.(".preview-hotspot") ||
                target?.closest?.("[data-ui='chrome']")
            );
        }

        function isInsidePreview(target) {
            return !!(previewViewer && target && previewViewer.contains(target));
        }

        function resetTouchPinch() {
            localPinch.active = false;
            localPinch.startDistance = 0;
            localPinch.startFov = 0;
            syncZoomButtonsState();
        }

        function resetPointerPinch() {
            pointerPinch.active = false;
            pointerPinch.startDistance = 0;
            pointerPinch.startFov = 0;
            syncZoomButtonsState();
        }

        function applyPinchZoom(startDistance, currentDistance, startFov, strength = 72) {
            const view = getCurrentView();
            if (!view || !startDistance || !currentDistance) return;

            // distance augmente => zoom avant => FOV diminue.
            // distance diminue => zoom arrière => FOV augmente.
            const ratio = currentDistance / startDistance;
            const zoomDelta = Math.log2(ratio) * degToRad(strength);
            const nextFov = clamp(startFov - zoomDelta, MIN_FOV, MAX_FOV);

            view.setParameters({ fov: nextFov });
            syncZoomButtonsState();
        }

        function startTouchPinch(event) {
            if (!event.touches || event.touches.length !== 2) return;
            if (!isInsidePreview(event.target) || shouldIgnoreZoomTarget(event.target)) return;

            const view = getCurrentView();
            if (!view) return;

            event.preventDefault();
            stopAutorotate();

            localPinch.active = true;
            localPinch.startDistance = getTouchDistance(event.touches);
            localPinch.startFov = view.fov();
        }

        function moveTouchPinch(event) {
            if (!localPinch.active || !event.touches || event.touches.length !== 2) return;
            if (!isInsidePreview(event.target) || shouldIgnoreZoomTarget(event.target)) return;

            event.preventDefault();
            const currentDistance = getTouchDistance(event.touches);
            applyPinchZoom(localPinch.startDistance, currentDistance, localPinch.startFov, isMobileViewport() ? 78 : 66);
        }

        function endTouchPinch(event) {
            if (!localPinch.active) return;

            if (!event.touches || event.touches.length < 2) {
                resetTouchPinch();
            }
        }

        // Capture = on reçoit le pinch même si le vrai target est le canvas WebGL.
        // Pas de stopPropagation = Marzipano continue de gérer le drag / inertie.
        previewViewer.addEventListener("touchstart", (event) => {
            if (event.touches && event.touches.length === 2) {
                startTouchPinch(event);
                return;
            }

            if (!isInsidePreview(event.target) || shouldIgnoreZoomTarget(event.target)) return;

            stopAutorotate();
        }, { passive: false, capture: true });

        previewViewer.addEventListener("touchmove", (event) => {
            if (event.touches && event.touches.length === 2) {
                moveTouchPinch(event);
            }
        }, { passive: false, capture: true });

        previewViewer.addEventListener("touchend", (event) => {
            if (localPinch.active) {
                endTouchPinch(event);
                return;
            }

            if (!isInsidePreview(event.target) || shouldIgnoreZoomTarget(event.target)) return;

            // Double tap mobile: zoom avant / retour zoom 0.
            const now = Date.now();
            if (now - lastTapTs < 300) {
                event.preventDefault();
                stopAutorotate();

                const view = getCurrentView();
                if (view) {
                    const currentFov = view.fov();
                    const zeroZoomFov = getSceneFinalFov(findScene(currentSceneId) || scenes[0]);
                    const targetFov = currentFov > degToRad(58)
                        ? clamp(currentFov - degToRad(34), MIN_FOV, MAX_FOV)
                        : zeroZoomFov;

                    view.setParameters({ fov: targetFov }, { transitionDuration: 160 });
                    setTimeout(syncZoomButtonsState, 180);
                }
            }

            lastTapTs = now;
        }, { passive: false, capture: true });

        previewViewer.addEventListener("touchcancel", resetTouchPinch, { passive: false, capture: true });

        // Document fallback: certains navigateurs envoient le move au document pendant le pinch.
        document.addEventListener("touchmove", (event) => {
            if (localPinch.active && event.touches && event.touches.length === 2) {
                moveTouchPinch(event);
            }
        }, { passive: false, capture: true });

        document.addEventListener("touchend", endTouchPinch, { passive: false, capture: true });
        document.addEventListener("touchcancel", resetTouchPinch, { passive: false, capture: true });

        // Pointer Events fallback pour Android/Chrome.
        function getPointerDistance() {
            const points = Array.from(activePointers.values());
            if (points.length < 2) return 0;
            const dx = points[0].clientX - points[1].clientX;
            const dy = points[0].clientY - points[1].clientY;
            return Math.sqrt(dx * dx + dy * dy);
        }

        previewViewer.addEventListener("pointerdown", (event) => {
            if (event.pointerType !== "touch") return;
            if (!isInsidePreview(event.target) || shouldIgnoreZoomTarget(event.target)) return;

            stopAutorotate();
            activePointers.set(event.pointerId, {
                clientX: event.clientX,
                clientY: event.clientY
            });

            if (activePointers.size === 2) {
                const view = getCurrentView();
                if (!view) return;

                event.preventDefault();
                pointerPinch.active = true;
                pointerPinch.startDistance = getPointerDistance();
                pointerPinch.startFov = view.fov();
            }
        }, { passive: false, capture: true });

        previewViewer.addEventListener("pointermove", (event) => {
            if (event.pointerType !== "touch" || !activePointers.has(event.pointerId)) return;
            if (!isInsidePreview(event.target) || shouldIgnoreZoomTarget(event.target)) return;

            activePointers.set(event.pointerId, {
                clientX: event.clientX,
                clientY: event.clientY
            });

            if (!pointerPinch.active || activePointers.size < 2) return;

            event.preventDefault();
            applyPinchZoom(pointerPinch.startDistance, getPointerDistance(), pointerPinch.startFov, isMobileViewport() ? 78 : 66);
        }, { passive: false, capture: true });

        function endPointer(event) {
            if (event.pointerType !== "touch") return;
            activePointers.delete(event.pointerId);
            if (activePointers.size < 2) resetPointerPinch();
        }

        previewViewer.addEventListener("pointerup", endPointer, { passive: false, capture: true });
        previewViewer.addEventListener("pointercancel", endPointer, { passive: false, capture: true });
        previewViewer.addEventListener("pointerleave", endPointer, { passive: false, capture: true });

        // iOS Safari native gesture fallback.
        let gestureStartFov = 0;

        previewViewer.addEventListener("gesturestart", (event) => {
            const view = getCurrentView();
            if (!view || shouldIgnoreZoomTarget(event.target)) return;

            event.preventDefault();
            stopAutorotate();
            gestureStartFov = view.fov();
        }, { passive: false, capture: true });

        previewViewer.addEventListener("gesturechange", (event) => {
            const view = getCurrentView();
            if (!view || !gestureStartFov || shouldIgnoreZoomTarget(event.target)) return;

            event.preventDefault();
            const scale = event.scale || 1;
            const zoomDelta = Math.log2(scale) * degToRad(76);
            const nextFov = clamp(gestureStartFov - zoomDelta, MIN_FOV, MAX_FOV);
            view.setParameters({ fov: nextFov });
            syncZoomButtonsState();
        }, { passive: false, capture: true });

        previewViewer.addEventListener("gestureend", (event) => {
            event.preventDefault();
            gestureStartFov = 0;
            syncZoomButtonsState();
        }, { passive: false, capture: true });

        // Desktop / trackpad: molette pour zoomer le panorama.
        previewViewer.addEventListener("wheel", (event) => {
            const target = event.target;
            if (shouldIgnoreZoomTarget(target)) return;

            const view = getCurrentView();
            if (!view) return;

            event.preventDefault();
            stopAutorotate();

            const direction = event.deltaY > 0 ? 1 : -1;
            const nextFov = clamp(view.fov() + degToRad(direction * 7), MIN_FOV, MAX_FOV);
            setZoomInstant(nextFov);
        }, { passive: false, capture: true });
    }


    sceneStackToggle?.addEventListener("click", toggleSceneStack);

    prevSceneBtn?.addEventListener("click", () => goToRelativeScene(-1));
    nextSceneBtn?.addEventListener("click", () => goToRelativeScene(1));

    function bindZoomButton(button, handler) {
        if (!button) return;

        button.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            handler();
        }, { passive: false });
    }

    bindZoomButton(zoomOutBtn, () => {
        stopAutorotate();
        zoomBy(isMobileViewport() ? 8 : 10, 120);
    });

    bindZoomButton(zoomInBtn, () => {
        stopAutorotate();
        zoomBy(isMobileViewport() ? -8 : -10, 120);
    });

    resetViewBtn?.addEventListener("click", resetCurrentView);
    autorotateBtn?.addEventListener("click", toggleAutorotate);
    focusModeBtn?.addEventListener("click", toggleFocusMode);
    shareBtn?.addEventListener("click", shareCurrentScene);
    fullscreenBtn?.addEventListener("click", enterFullscreen);

    previewInfoClose?.addEventListener("click", (event) => {
        event.stopPropagation();
        closeInfoPanel();
    });

    previewInfoBackdrop?.addEventListener("click", closeInfoPanel);

    previewViewer?.addEventListener("click", () => {
        closeInfoPanel();
    });

    previewViewer?.addEventListener("pointerdown", () => {
        stopAutorotate();
    });

    window.addEventListener("resize", () => {
        updateAllViewerSizes();
        syncZoomButtonsState();
    });

    window.addEventListener("orientationchange", () => {
        setTimeout(() => {
            updateAllViewerSizes();
            syncZoomButtonsState();
        }, 260);
    });

    if (window.visualViewport) {
        window.visualViewport.addEventListener("resize", () => {
            updateAllViewerSizes();
            syncZoomButtonsState();
        });
    }

    document.addEventListener("fullscreenchange", () => {
        setTimeout(() => {
            updateAllViewerSizes();
            syncZoomButtonsState();
        }, 180);
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeImageZoomViewer();
            closeInfoPanel();
            closeSceneStack();
        }

        if (event.key === "ArrowLeft") {
            goToRelativeScene(-1);
        }

        if (event.key === "ArrowRight") {
            goToRelativeScene(1);
        }

        if (event.key === "+") {
            zoomBy(-8);
        }

        if (event.key === "-") {
            zoomBy(8);
        }
    });

    setupResponsiveMode();
    injectPreviewCinematicStyles();

    if (!scenes.length) {
        if (sceneCountBadge) sceneCountBadge.textContent = "0";
        return;
    }

    if (sceneCountBadge) {
        sceneCountBadge.textContent = `${getNavigationSceneList().length}`;
    }

    renderSceneRail();
    setupMobileZoomGestures();

    const initialScene = getInitialSceneFromUrl() || scenes[0];
    currentSceneId = initialScene.id;


    buildSceneOnLayer(activeLayerKey, initialScene);
    updateSceneMeta(initialScene);
    syncSceneInUrl(initialScene);

    requestAnimationFrame(() => {
        updateAllViewerSizes();
        syncZoomButtonsState();
        runInitialReveal(initialScene);
    });
});
