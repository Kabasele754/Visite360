/* =====================================================================
   PREVIEW TAILWIND JS — VERSION COMPLETE WALK TRANSITION
   Remplace entièrement : dashboard/js/preview-tailwind.js

   Fonctionnalités :
   - Marzipano A/B layers
   - changement de scène avec effet marche / zoom vers hotspot
   - scène entrante zoomée puis dézoom vers zoom 0
   - hotspots navigation + business icons
   - scene stack, zoom, reset, autorotate, focus, share, fullscreen
   - panneau info produit/advertising/contact
   - zoom image dans le panneau info
   - pinch zoom mobile + molette desktop
===================================================================== */

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
        console.warn("Marzipano is not loaded.");
        return;
    }

    const config = window.PREVIEW_CONFIG || {};
    const $ = (id) => document.getElementById(id);

    function parseJsonScript(id, fallback = []) {
        const el = $(id);
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
    sceneList = sceneList.length
        ? sceneList.slice().sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
        : scenes.filter((scene) => scene?.is_public !== false);

    const sceneLookup = new Map();
    scenes.forEach((scene) => {
        [scene?.id, scene?.scene_id, scene?.uuid, scene?.slug]
            .filter((value) => value !== undefined && value !== null && value !== "")
            .forEach((value) => sceneLookup.set(String(value), scene));
    });

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

    const MIN_FOV = degToRad(6);
    const MAX_FOV = degToRad(132);
    const ZERO_ZOOM_FOV = MAX_FOV;

    function degToRad(deg) {
        return Number(deg || 0) * Math.PI / 180;
    }

    function clamp(value, min, max) {
        return Math.min(Math.max(value, min), max);
    }

    function normalizeAngle(rad) {
        let value = Number(rad || 0);
        while (value > Math.PI) value -= 2 * Math.PI;
        while (value < -Math.PI) value += 2 * Math.PI;
        return value;
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
        if (mql.addEventListener) mql.addEventListener("change", applyMode);
        else if (mql.addListener) mql.addListener(applyMode);

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
            /* =========================================================
               PREVIEW — TRANSITION CINÉMATIQUE TYPE BUILDER
               Objectif : effet déplacement propre, sans écran noir,
               sans sweep, sans overlay qui reste après la transition.
            ========================================================= */
            #previewViewer,
            .preview-viewer {
                position: relative !important;
                overflow: hidden !important;
                isolation: isolate !important;
                background: #020617 !important;
            }

            #previewViewer::before,
            #previewViewer::after,
            .preview-viewer::before,
            .preview-viewer::after {
                pointer-events: none !important;
            }

            #previewViewer.is-cinematic-transition::before,
            #previewViewer.transitioning::before,
            #previewViewer.is-cinematic-transition::after,
            #previewViewer.transitioning::after,
            .preview-viewer.is-cinematic-transition::before,
            .preview-viewer.transitioning::before,
            .preview-viewer.is-cinematic-transition::after,
            .preview-viewer.transitioning::after {
                content: none !important;
                display: none !important;
                opacity: 0 !important;
                background: transparent !important;
                animation: none !important;
            }

            #previewViewer canvas,
            .preview-viewer canvas {
                width: 100% !important;
                height: 100% !important;
                display: block !important;
            }

            #previewLayerA,
            #previewLayerB,
            .preview-layer {
                position: absolute !important;
                inset: 0 !important;
                opacity: 0;
                z-index: 1;
                pointer-events: none;
                transform: translate3d(0, 0, 0) scale(1);
                transform-origin: center center !important;
                backface-visibility: hidden !important;
                -webkit-backface-visibility: hidden !important;
                will-change: transform, opacity, filter !important;
                filter: blur(0) brightness(1) saturate(1);
            }

            #previewMountA,
            #previewMountB,
            .preview-mount {
                position: absolute !important;
                inset: 0 !important;
                width: 100% !important;
                height: 100% !important;
                touch-action: none !important;
                -ms-touch-action: none !important;
            }

            .preview-layer.active-layer {
                opacity: 1 !important;
                z-index: 2 !important;
                pointer-events: auto !important;
                transform: translate3d(0, 0, 0) scale(1) !important;
                filter: blur(0) brightness(1) saturate(1) !important;
            }

            .preview-layer.standby-layer {
                opacity: 0 !important;
                z-index: 1 !important;
                pointer-events: none !important;
                transform: translate3d(0, 0, 0) scale(1) !important;
                filter: blur(0) brightness(1) saturate(1) !important;
            }

            .preview-viewer.is-cinematic-transition .preview-layer,
            .preview-viewer.transitioning .preview-layer,
            #previewViewer.is-cinematic-transition .preview-layer,
            #previewViewer.transitioning .preview-layer {
                transition: none !important;
            }

            .preview-layer.layer-outgoing,
            .preview-viewer.is-cinematic-transition .layer-outgoing,
            .preview-viewer.transitioning .layer-outgoing,
            #previewViewer.is-cinematic-transition .layer-outgoing,
            #previewViewer.transitioning .layer-outgoing {
                z-index: 2 !important;
                pointer-events: none !important;
                animation: previewBuilderOutgoingClean 1100ms cubic-bezier(0.22, 1, 0.36, 1) forwards !important;
            }

            .preview-layer.layer-incoming,
            .preview-viewer.is-cinematic-transition .layer-incoming,
            .preview-viewer.transitioning .layer-incoming,
            #previewViewer.is-cinematic-transition .layer-incoming,
            #previewViewer.transitioning .layer-incoming {
                z-index: 3 !important;
                pointer-events: auto !important;
                animation: previewBuilderIncomingClean 1150ms cubic-bezier(0.22, 1, 0.36, 1) forwards !important;
            }

            .preview-layer.layer-incoming::after,
            .preview-viewer.is-cinematic-transition .layer-incoming::after,
            .preview-viewer.transitioning .layer-incoming::after,
            #previewViewer.is-cinematic-transition .layer-incoming::after,
            #previewViewer.transitioning .layer-incoming::after {
                content: none !important;
                display: none !important;
                opacity: 0 !important;
                background: transparent !important;
                animation: none !important;
            }

            @keyframes previewBuilderOutgoingClean {
                0% {
                    transform: translate3d(0, 0, 0) scale(1);
                    opacity: 1;
                    filter: blur(0px) brightness(1) saturate(1);
                }
                32% {
                    transform: translate3d(0, 0, 0) scale(1.10);
                    opacity: 1;
                    filter: blur(0.15px) brightness(1) saturate(1);
                }
                52% {
                    transform: translate3d(0, 0, 0) scale(1.16);
                    opacity: 0.92;
                    filter: blur(0.65px) brightness(1) saturate(1);
                }
                72% {
                    transform: translate3d(0, 0, 0) scale(1.20);
                    opacity: 0.62;
                    filter: blur(1.4px) brightness(1) saturate(1);
                }
                100% {
                    transform: translate3d(0, 0, 0) scale(1.24);
                    opacity: 0;
                    filter: blur(2.4px) brightness(1) saturate(1);
                }
            }

            @keyframes previewBuilderIncomingClean {
                0% {
                    transform: translate3d(0, 0, 0) scale(1.18);
                    opacity: 0;
                    filter: blur(3px) brightness(1) saturate(1);
                }
                25% {
                    transform: translate3d(0, 0, 0) scale(1.15);
                    opacity: 0.16;
                    filter: blur(2.5px) brightness(1) saturate(1);
                }
                48% {
                    transform: translate3d(0, 0, 0) scale(1.10);
                    opacity: 0.48;
                    filter: blur(1.7px) brightness(1) saturate(1);
                }
                68% {
                    transform: translate3d(0, 0, 0) scale(1.06);
                    opacity: 0.78;
                    filter: blur(0.8px) brightness(1) saturate(1);
                }
                100% {
                    transform: translate3d(0, 0, 0) scale(1);
                    opacity: 1;
                    filter: blur(0px) brightness(1) saturate(1);
                }
            }

            @media (prefers-reduced-motion: reduce) {
                .preview-layer.layer-outgoing,
                .preview-layer.layer-incoming {
                    animation: none !important;
                    transform: translate3d(0, 0, 0) scale(1) !important;
                    filter: none !important;
                }
            }
        `;

        document.head.appendChild(style);
    }

    function injectWalkTransitionStyles() {
        if (document.getElementById("preview-walk-transition-style")) return;

        const oldOverlay = document.getElementById("previewWalkOverlay");
        if (oldOverlay) oldOverlay.remove();

        const style = document.createElement("style");
        style.id = "preview-walk-transition-style";
        style.textContent = `
            /* Ancien overlay tunnel désactivé : il créait l'effet noir/voile après transition. */
            .preview-walk-overlay,
            #previewWalkOverlay {
                display: none !important;
                opacity: 0 !important;
                visibility: hidden !important;
                pointer-events: none !important;
                animation: none !important;
            }

            .preview-viewer.is-walk-transition::before,
            .preview-viewer.is-walk-transition::after,
            #previewViewer.is-walk-transition::before,
            #previewViewer.is-walk-transition::after {
                content: none !important;
                display: none !important;
                opacity: 0 !important;
                background: transparent !important;
                animation: none !important;
            }
        `;

        document.head.appendChild(style);
    }

    function ensureWalkTransitionOverlay() {
        const oldOverlay = document.getElementById("previewWalkOverlay");
        if (oldOverlay) oldOverlay.remove();
        return null;
    }

    function getCinematicTransitionMs() {
        // Durée Builder : outgoing 1100ms, incoming 1150ms, finalisation 1180ms.
        return 1180;
    }

    function getCinematicCameraMs() {
        // Gardé pour compatibilité si une ancienne partie du code l'appelle.
        return 0;
    }

    function getWalkTargetFov(currentFov) {
        // FOV plus petit = zoom avant. Valeurs proches de la logique Builder :
        // on avance vers le hotspot sans zoom trop agressif.
        const desiredTarget = isMobileViewport() ? degToRad(88) : degToRad(82);
        const extraIfAlreadyZoomed = isMobileViewport() ? degToRad(12) : degToRad(22);

        if (currentFov > desiredTarget) {
            return clamp(desiredTarget, MIN_FOV, MAX_FOV);
        }

        return clamp(currentFov - extraIfAlreadyZoomed, MIN_FOV, MAX_FOV);
    }

    function getIncomingWalkStartFov(finalFov) {
        // En mode Builder-like, la scène entrante est déjà à son zoom final.
        return clamp(finalFov, MIN_FOV, MAX_FOV);
    }

    function getShortestYawTarget(currentYaw, targetYaw) {
        return currentYaw + normalizeAngle(targetYaw - currentYaw);
    }

    function getWalkPitchTarget(currentPitch, targetPitch, extraBob = 0) {
        const direction = targetPitch >= currentPitch ? 1 : -1;
        return clamp(targetPitch + direction * extraBob, degToRad(-82), degToRad(82));
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

    function findSceneListIndex(sceneId) {
        return sceneList.findIndex(scene => sceneMatchesId(scene, sceneId));
    }

    function getNavigationSceneList() {
        return sceneList.length ? sceneList : scenes;
    }

    function getSceneIdentifier(scene) {
        return String(scene?.slug || scene?.uuid || scene?.id || "");
    }

    function getSceneShareUrl(scene) {
        const url = new URL(window.location.href);
        url.searchParams.set("s", getSceneIdentifier(scene));
        return url.toString();
    }

    function syncSceneInUrl(scene) {
        if (!scene) return;
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

    function resolveIcon(iconName) {
        if (config.businessIconMap && config.businessIconMap[iconName]) return config.businessIconMap[iconName];
        if (config.iconMap && config.iconMap[iconName]) return config.iconMap[iconName];
        return config.iconMap?.default || "";
    }

    function getSceneFinalFov() {
        return clamp(ZERO_ZOOM_FOV, MIN_FOV, MAX_FOV);
    }

    function getCurrentView() {
        return views[activeLayerKey];
    }

    function updateAllViewerSizes() {
        try {
            Object.values(viewers).forEach((viewer) => {
                if (viewer && typeof viewer.updateSize === "function") viewer.updateSize();
            });
        } catch (_) {}
    }

    function showToast(message) {
        if (!previewToast) return;
        previewToast.textContent = message;
        clearTimeout(toastTimer);
        previewToast.classList.add("toast-show");
        toastTimer = setTimeout(() => previewToast.classList.remove("toast-show"), 1700);
    }

    function stopTouchAndScrollEventPropagation(element) {
        if (!element) return;
        ["touchstart", "touchmove", "touchend", "touchcancel", "pointerdown", "pointermove", "pointerup", "pointercancel", "wheel"].forEach((eventName) => {
            element.addEventListener(eventName, (event) => event.stopPropagation(), { passive: true });
        });
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
            .info-media-image-zoomable { cursor: zoom-in; transition: transform .22s ease, filter .22s ease; }
            .info-media-image-zoomable:hover { transform: scale(1.018); filter: saturate(1.06) contrast(1.03); }
            .preview-image-zoom-overlay {
                position: fixed; inset: 0; z-index: 99999; display: none; align-items: center; justify-content: center;
                background: rgba(2, 6, 23, .88); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
                opacity: 0; transition: opacity .18s ease; touch-action: none;
            }
            .preview-image-zoom-overlay.open { display: flex; opacity: 1; }
            .preview-image-zoom-stage { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; overflow: hidden; touch-action: none; user-select: none; -webkit-user-select: none; }
            .preview-image-zoom-img {
                max-width: 94vw; max-height: 86vh; object-fit: contain; border-radius: 22px; box-shadow: 0 30px 90px rgba(0,0,0,.55);
                transform-origin: center center; will-change: transform; transition: transform .12s ease; cursor: zoom-in; user-select: none; -webkit-user-drag: none;
            }
            .preview-image-zoom-overlay.zoomed .preview-image-zoom-img { cursor: grab; }
            .preview-image-zoom-overlay.dragging .preview-image-zoom-img { cursor: grabbing; transition: none; }
            .preview-image-zoom-toolbar {
                position: absolute; top: max(18px, env(safe-area-inset-top)); right: max(18px, env(safe-area-inset-right)); z-index: 2;
                display: flex; gap: 10px; padding: 8px; border: 1px solid rgba(255,255,255,.16); border-radius: 999px;
                background: rgba(15, 23, 42, .68); box-shadow: 0 18px 50px rgba(0,0,0,.3);
            }
            .preview-image-zoom-btn {
                width: 42px; height: 42px; display: inline-flex; align-items: center; justify-content: center; border: 0; border-radius: 999px;
                color: #fff; background: rgba(255,255,255,.14); font-size: 19px; font-weight: 900; line-height: 1; cursor: pointer;
                transition: transform .18s ease, background .18s ease;
            }
            .preview-image-zoom-btn:hover { transform: translateY(-1px); background: rgba(255,255,255,.24); }
            .preview-image-zoom-hint {
                position: absolute; left: 50%; bottom: max(20px, env(safe-area-inset-bottom)); transform: translateX(-50%); z-index: 2;
                max-width: calc(100vw - 36px); padding: 9px 14px; border-radius: 999px; color: rgba(255,255,255,.86);
                background: rgba(15, 23, 42, .64); font-size: 12px; font-weight: 700; text-align: center; pointer-events: none;
            }
            @media (max-width: 768px) {
                .preview-image-zoom-img { max-width: 96vw; max-height: 78vh; border-radius: 18px; }
                .preview-image-zoom-toolbar { top: max(12px, env(safe-area-inset-top)); right: max(12px, env(safe-area-inset-right)); gap: 7px; padding: 6px; }
                .preview-image-zoom-btn { width: 38px; height: 38px; font-size: 17px; }
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
        if (imageZoomState.overlay && imageZoomState.image) return imageZoomState.overlay;

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
            if (event.target === overlay || event.target === stage) closeImageZoomViewer();
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
            if (imageZoomState.scale > 1.02) resetImageZoom();
            else setImageZoomScale(2.2);
        });

        stage.addEventListener("pointerdown", (event) => {
            event.preventDefault();
            event.stopPropagation();
            imageZoomState.pointers.set(event.pointerId, { clientX: event.clientX, clientY: event.clientY });

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
            imageZoomState.pointers.set(event.pointerId, { clientX: event.clientX, clientY: event.clientY });

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
        if (previewSceneRail?.classList.contains("open")) closeSceneStack();
        else openSceneStack();
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

        const ctaUrl = content.cta_url || hotspot.cta_url || "";
        const buttonText = content.button_text || hotspot.button_text || "Open";
        const badge = content.badge || hotspot.badge || "";
        const price = content.price || hotspot.price || "";
        const siteName = content.site_name || hotspot.site_name || "";
        const phone = content.phone || hotspot.phone || "";
        const email = content.email || hotspot.email || "";
        const whatsappNumber = content.whatsapp_number || hotspot.whatsapp_number || "";
        const whatsappMessage = content.whatsapp_message || hotspot.whatsapp_message || "Hello";

        if (previewInfoMedia) {
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
                infoImage.onerror = () => { previewInfoMedia.innerHTML = `<div class="info-media-empty">Image unavailable</div>`; };
                previewInfoMedia.appendChild(infoImage);
            } else {
                previewInfoMedia.innerHTML = `<div class="info-media-empty">Preview unavailable</div>`;
            }
        }

        if (previewInfoTitle) previewInfoTitle.textContent = hotspot.title || hotspot.label || "Hotspot";
        if (previewInfoDescription) previewInfoDescription.textContent = hotspot.description || hotspot.tooltip_text || "";

        function setOptionalText(el, value) {
            if (!el) return;
            if (value) {
                el.textContent = value;
                el.classList.remove("hidden");
            } else {
                el.textContent = "";
                el.classList.add("hidden");
            }
        }

        setOptionalText(previewInfoBadge, badge);
        setOptionalText(previewInfoPrice, price);
        setOptionalText(previewInfoSite, siteName);

        if (previewInfoAction) {
            if (ctaUrl) {
                previewInfoAction.href = ctaUrl;
                previewInfoAction.textContent = buttonText;
                previewInfoAction.classList.remove("hidden");
            } else {
                previewInfoAction.classList.add("hidden");
                previewInfoAction.removeAttribute("href");
            }
        }

        if (previewInfoWhatsapp) {
            if (whatsappNumber) {
                const cleanNumber = String(whatsappNumber).replace(/[^\d]/g, "");
                previewInfoWhatsapp.href = `https://wa.me/${cleanNumber}?text=${encodeURIComponent(whatsappMessage)}`;
                previewInfoWhatsapp.classList.remove("hidden");
            } else {
                previewInfoWhatsapp.classList.add("hidden");
                previewInfoWhatsapp.removeAttribute("href");
            }
        }

        if (previewInfoContact) {
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
        if (autorotateEnabled) stopAutorotate();
        else startAutorotate();
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
            button.style.setProperty("--stagger", String(index));

            const thumb = getSceneThumbnailUrl(scene);
            button.innerHTML = `
                <div class="scene-thumb">
                    ${thumb ? `<img src="${thumb}" alt="${scene.title || 'Scene'}">` : `<div class="scene-thumb-placeholder">360</div>`}
                </div>
                <div class="scene-body">
                    <strong class="scene-title">${scene.title || "Untitled Scene"}</strong>
                    <span class="scene-subtitle"><span class="scene-dot"></span>Scene ${index + 1}</span>
                </div>
            `;

            button.addEventListener("click", (event) => {
                event.stopPropagation();
                if (isTransitioning) return;
                const targetScene = findScene(scene.id) || findScene(scene.scene_id) || scene;
                if (!targetScene) return;
                closeInfoPanel();
                closeSceneStack();
                goToSceneWithWalk(targetScene);
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
        if (sceneCountBadge) sceneCountBadge.textContent = `${getNavigationSceneList().length}`;
        markActiveSceneCard(scene?.id);
    }

    function buildHotspotNode(hotspot) {
        const display = hotspot.payload?.display || {};
        const variant = display.variant || "pin";
        const size = Number(display.size || 58);
        const rotation = Number(display.rotation || 0);
        const offsetX = Number(display.offset_x || 0);
        const offsetY = Number(display.offset_y || 0);
        const anchor = display.anchor || "bottom";

        const businessIconKeys = new Set(Object.keys(config.businessIconMap || {}).map((key) => String(key).toLowerCase()));

        function normalizeHotspotKey(value) {
            return String(value || "")
                .trim()
                .toLowerCase()
                .replace(/^business[-_/]/, "")
                .replace(/\.(png|jpg|jpeg|svg|webp)$/i, "")
                .replace(/[^a-z0-9_-]/g, "");
        }

        const rawIconKey = hotspot.selected_icon || hotspot.icon || hotspot.type || "default";
        const iconKey = normalizeHotspotKey(rawIconKey);
        const typeKey = normalizeHotspotKey(hotspot.type);

        const isNavigate = hotspot.type === "navigate";
        const isBusinessIcon = !isNavigate && (businessIconKeys.has(iconKey) || businessIconKeys.has(typeKey));
        const hotspotKind = isNavigate
            ? "navigate"
            : businessIconKeys.has(iconKey)
                ? iconKey
                : businessIconKeys.has(typeKey)
                    ? typeKey
                    : typeKey || iconKey || "custom";

        const iconUrl = resolveIcon(iconKey) || resolveIcon(typeKey) || resolveIcon("default");
        const node = document.createElement("div");
        node.className = [
            "preview-hotspot",
            `variant-${variant}`,
            `anchor-${anchor}`,
            `hotspot-kind-${hotspotKind}`,
            isNavigate ? "hotspot-kind-navigate" : "",
            isBusinessIcon ? "hotspot-business-premium" : "hotspot-standard-premium"
        ].filter(Boolean).join(" ");

        node.dataset.hotspotType = hotspot.type || "";
        node.dataset.hotspotIcon = iconKey || "";
        node.dataset.hotspotKind = hotspotKind || "";
        node.style.width = `${size}px`;
        node.style.height = isBusinessIcon || variant !== "label" ? `${size}px` : "auto";
        node.style.transform = `translate(${offsetX}px, ${offsetY}px) rotate(${rotation}deg)`;

        const delay = Math.abs(Number(hotspot.id || hotspot.pk || 0)) % 7;
        node.style.setProperty("--hotspot-loader-delay", `${delay * 110}ms`);

        const wrap = document.createElement("span");
        wrap.className = "hotspot-grow-wrap";
        wrap.setAttribute("aria-hidden", "true");

        const img = document.createElement("img");
        img.src = iconUrl;
        img.alt = hotspot.label || hotspot.title || "Hotspot";
        img.loading = "lazy";
        img.decoding = "async";
        img.draggable = false;

        wrap.appendChild(img);
        node.appendChild(wrap);

        if (variant === "label") {
            const label = document.createElement("span");
            label.className = "hotspot-label-text";
            label.textContent = hotspot.label || hotspot.title || "Hotspot";
            node.appendChild(label);
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
        if (!mount) return null;
        mount.innerHTML = "";

        try {
            viewers[key] = new Marzipano.Viewer(mount, {
                controls: { mouseViewMode: "drag" }
            });
        } catch (error) {
            console.warn("VIEWER_CREATE_FAILED", error);
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
                    { cubeMapPreviewUrl: `${sceneData.tiles_url}/preview.jpg` }
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
                    Math.max(Number(sceneData.face_size || 0), Number(sceneData.max_resolution || 0), mobile ? 2048 : 4096),
                    MAX_FOV
                )
            };
        }

        const logicalResolution = Math.max(
            Number(sceneData?.face_size || 0),
            Number(sceneData?.max_resolution || 0),
            mobile ? 3072 : 4096
        );
        const selectedImageUrl = getPreferredImageUrl(sceneData);

        return {
            source: Marzipano.ImageUrlSource.fromString(selectedImageUrl),
            geometry: new Marzipano.EquirectGeometry([{ width: logicalResolution }]),
            limiter: Marzipano.RectilinearView.limit.traditional(logicalResolution, MAX_FOV)
        };
    }

    function buildSceneOnLayer(layerKey, sceneData) {
        const viewer = ensureViewer(layerKey);
        const selectedImageUrl = getPreferredImageUrl(sceneData);
        if (!viewer || (!selectedImageUrl && !sceneData?.tiles_url)) return null;

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
        } catch (error) {
            console.warn("SCENE_CREATE_FAILED", error);
            return null;
        }

        (sceneData.hotspots || []).forEach((hotspot) => {
            const node = buildHotspotNode(hotspot);
            marzipanoScenes[layerKey].hotspotContainer().createHotspot(node, {
                yaw: Number(hotspot.yaw || 0),
                pitch: Number(hotspot.pitch || 0)
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

        previewViewer?.classList.add("is-opening");
        view.setParameters({
            yaw: degToRad(scene.yaw_default || 0),
            pitch: degToRad(scene.pitch_default || 0),
            fov: getSceneFinalFov(scene)
        });

        setTimeout(() => {
            previewIntroOverlay?.classList.add("is-hidden");
            document.body.classList.add("preview-has-loaded");
            syncZoomButtonsState();
        }, 220);

        setTimeout(() => {
            previewViewer?.classList.remove("is-cinematic-transition", "transitioning", "is-opening", "is-walk-transition");
            syncZoomButtonsState();

            // Auto rotation au démarrage : le panorama commence à bouger automatiquement.
            if (!autorotateEnabled && !document.hidden) {
                startAutorotate();
            }
        }, 650);
    }

    function cinematicSwitchScene(targetScene) {
        if (!targetScene) {
            isTransitioning = false;
            return;
        }

        const outgoingKey = activeLayerKey;
        const incomingKey = standbyLayerKey();
        const cinematicMs = getCinematicTransitionMs();

        previewViewer?.style?.setProperty("--preview-cinematic-ms", `${cinematicMs}ms`);
        buildSceneOnLayer(incomingKey, targetScene);

        const incomingView = views[incomingKey];
        const outgoingEl = getLayerEl(outgoingKey);
        const incomingEl = getLayerEl(incomingKey);

        if (!outgoingEl || !incomingEl) {
            activeLayerKey = incomingKey;
            currentSceneId = targetScene.id;
            isTransitioning = false;
            return;
        }

        const endYaw = degToRad(targetScene.yaw_default || 0);
        const endPitch = degToRad(targetScene.pitch_default || 0);
        const finalFov = getSceneFinalFov(targetScene);

        // Même principe que le Builder : la nouvelle scène démarre directement
        // dans sa direction par défaut. Le mouvement est porté par l'animation A/B,
        // pas par un voile noir ni un écran de loading.
        if (incomingView) {
            incomingView.setParameters({
                yaw: endYaw,
                pitch: endPitch,
                fov: finalFov
            });
        }

        outgoingEl.classList.remove("standby-layer", "layer-incoming", "layer-outgoing");
        incomingEl.classList.remove("active-layer", "standby-layer", "layer-incoming", "layer-outgoing");

        outgoingEl.classList.add("active-layer");
        incomingEl.classList.add("layer-incoming");

        outgoingEl.style.opacity = "1";
        incomingEl.style.opacity = "1";

        previewViewer?.classList.remove("is-walk-transition");
        previewViewer?.classList.add("is-cinematic-transition", "transitioning");

        currentSceneId = targetScene.id;
        updateSceneMeta(targetScene);
        syncSceneInUrl(targetScene);

        requestAnimationFrame(() => {
            // Force la même sensation que crossfadeToScene() du Builder.
            outgoingEl.classList.add("layer-outgoing");
            incomingEl.classList.add("layer-incoming");
        });

        setTimeout(() => {
            outgoingEl.classList.remove("active-layer", "layer-outgoing", "layer-incoming");
            outgoingEl.classList.add("standby-layer");
            outgoingEl.style.opacity = "0";

            incomingEl.classList.remove("layer-incoming", "layer-outgoing", "standby-layer");
            incomingEl.classList.add("active-layer");
            incomingEl.style.opacity = "1";

            previewViewer?.classList.remove("is-cinematic-transition", "transitioning", "is-walk-transition");
            activeLayerKey = incomingKey;
            isTransitioning = false;
            updateAllViewerSizes();
            syncZoomButtonsState();

            // Relance douce après changement de scène, sauf si l'onglet est caché.
            if (!document.hidden) {
                startAutorotate();
            }
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

        previewViewer?.classList.remove("is-walk-transition");
        previewViewer?.style?.setProperty("--preview-cinematic-ms", `${getCinematicTransitionMs()}ms`);

        const rawHotspotYaw = normalizeAngle(Number(hotspot.yaw ?? currentView.yaw()));
        const targetYaw = getShortestYawTarget(currentView.yaw(), rawHotspotYaw);
        const currentPitch = currentView.pitch();
        const currentFov = currentView.fov();

        // Même logique que navigateThroughHotspot() du Builder :
        // 1) la caméra regarde vers le hotspot,
        // 2) petit zoom avant pour donner l'impression de marcher,
        // 3) crossfade A/B propre vers la scène cible.
        currentView.setParameters(
            {
                yaw: targetYaw,
                pitch: currentPitch,
                fov: currentFov
            },
            { transitionDuration: isMobileViewport() ? 240 : 260 }
        );

        setTimeout(() => {
            const tighterFov = getWalkTargetFov(currentFov);
            currentView.setParameters(
                {
                    yaw: targetYaw,
                    pitch: currentPitch,
                    fov: tighterFov
                },
                { transitionDuration: isMobileViewport() ? 250 : 260 }
            );
            syncZoomButtonsState();
        }, isMobileViewport() ? 160 : 180);

        setTimeout(() => {
            cinematicSwitchScene(targetScene);
        }, isMobileViewport() ? 380 : 420);
    }

    function goToSceneWithWalk(targetScene) {
        if (!targetScene || isTransitioning) return;
        isTransitioning = true;
        closeInfoPanel();
        closeSceneStack();
        stopAutorotate();

        previewViewer?.classList.remove("is-walk-transition");
        previewViewer?.style?.setProperty("--preview-cinematic-ms", `${getCinematicTransitionMs()}ms`);

        const currentView = getCurrentView();
        if (!currentView) {
            cinematicSwitchScene(targetScene);
            return;
        }

        const currentFov = currentView.fov();
        const walkTargetFov = getWalkTargetFov(currentFov);

        currentView.setParameters(
            { fov: walkTargetFov },
            { transitionDuration: isMobileViewport() ? 260 : 300 }
        );
        syncZoomButtonsState();

        setTimeout(() => cinematicSwitchScene(targetScene), isMobileViewport() ? 380 : 420);
    }

    function zoomToFov(nextFov, duration = 220) {
        const view = getCurrentView();
        if (!view) return;
        view.setParameters({ fov: clamp(nextFov, MIN_FOV, MAX_FOV) }, { transitionDuration: duration });
        syncZoomButtonsState();
    }

    function zoomBy(deltaDeg, duration = 220) {
        const view = getCurrentView();
        if (!view) return;
        zoomToFov(view.fov() + degToRad(deltaDeg), duration);
    }

    function setZoomInstant(nextFov) {
        const view = getCurrentView();
        if (!view) return;
        view.setParameters({ fov: clamp(nextFov, MIN_FOV, MAX_FOV) });
        syncZoomButtonsState();
    }

    function resetCurrentView() {
        const scene = findScene(currentSceneId);
        const view = getCurrentView();
        if (!scene || !view) return;
        stopAutorotate();
        view.setParameters({
            yaw: degToRad(scene.yaw_default || 0),
            pitch: degToRad(scene.pitch_default || 0),
            fov: getSceneFinalFov(scene)
        }, { transitionDuration: 480 });
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
        goToSceneWithWalk(targetScene);
    }

    function updatePreviewEngagementBadgesFromPayload(data) {
        if (!data || typeof data !== "object") return;
        if (typeof window.updatePreviewTourEngagementBadges === "function") {
            window.updatePreviewTourEngagementBadges(data);
        }
    }

    async function trackTourShare(channel = "web_share") {
        const engagementUrl = config.engagementUrl || window.PREVIEW_TOUR_ENGAGEMENT_URL || "";
        if (!engagementUrl) return null;

        try {
            const response = await fetch(engagementUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
                credentials: "same-origin",
                keepalive: true,
                body: JSON.stringify({ action: "share", channel }),
            });

            if (!response.ok) return null;
            const data = await response.json();
            updatePreviewEngagementBadgesFromPayload(data);
            return data;
        } catch (_) {
            return null;
        }
    }

    async function shareCurrentScene() {
        const scene = findScene(currentSceneId) || scenes[0];
        if (!scene) return;
        const shareUrl = getSceneShareUrl(scene);

        try {
            if (navigator.share) {
                await navigator.share({ title: document.title, text: "Virtual Tour", url: shareUrl });
                await trackTourShare("web_share");
                showToast("Shared");
                return;
            }

            await navigator.clipboard.writeText(shareUrl);
            await trackTourShare("copy_link");
            showToast("Link copied");
        } catch (_) {
            try {
                window.prompt("Copy this link", shareUrl);
                await trackTourShare("other");
            } catch (_) {}
            showToast("Share unavailable");
        }
    }

    async function enterFullscreen() {
        try {
            if (!document.fullscreenElement && previewViewer?.requestFullscreen) await previewViewer.requestFullscreen();
            else if (document.exitFullscreen) await document.exitFullscreen();
        } catch (_) {}
    }

    function getTouchDistance(touches) {
        if (!touches || touches.length < 2) return 0;
        const dx = touches[0].clientX - touches[1].clientX;
        const dy = touches[0].clientY - touches[1].clientY;
        return Math.sqrt(dx * dx + dy * dy);
    }

    function setupMobileZoomGestures() {
        if (!previewViewer) return;

        [previewViewer, previewLayerA, previewLayerB, previewMountA, previewMountB].forEach((el) => {
            if (!el) return;
            el.style.touchAction = "none";
            el.style.webkitUserSelect = "none";
            el.style.userSelect = "none";
        });

        let lastTapTs = 0;
        const activePointers = new Map();
        const localPinch = { active: false, startDistance: 0, startFov: 0 };
        const pointerPinch = { active: false, startDistance: 0, startFov: 0 };

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

        function applyPinchZoom(startDistance, currentDistance, startFov, strength = 72) {
            const view = getCurrentView();
            if (!view || !startDistance || !currentDistance) return;
            const ratio = currentDistance / startDistance;
            const zoomDelta = Math.log2(ratio) * degToRad(strength);
            const nextFov = clamp(startFov - zoomDelta, MIN_FOV, MAX_FOV);
            view.setParameters({ fov: nextFov });
            syncZoomButtonsState();
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

        previewViewer.addEventListener("touchstart", (event) => {
            if (event.touches && event.touches.length === 2) {
                if (!isInsidePreview(event.target) || shouldIgnoreZoomTarget(event.target)) return;
                const view = getCurrentView();
                if (!view) return;
                event.preventDefault();
                stopAutorotate();
                localPinch.active = true;
                localPinch.startDistance = getTouchDistance(event.touches);
                localPinch.startFov = view.fov();
                return;
            }

            if (!isInsidePreview(event.target) || shouldIgnoreZoomTarget(event.target)) return;
            stopAutorotate();
        }, { passive: false, capture: true });

        previewViewer.addEventListener("touchmove", (event) => {
            if (!localPinch.active || !event.touches || event.touches.length !== 2) return;
            if (!isInsidePreview(event.target) || shouldIgnoreZoomTarget(event.target)) return;
            event.preventDefault();
            applyPinchZoom(localPinch.startDistance, getTouchDistance(event.touches), localPinch.startFov, isMobileViewport() ? 78 : 66);
        }, { passive: false, capture: true });

        previewViewer.addEventListener("touchend", (event) => {
            if (localPinch.active) {
                if (!event.touches || event.touches.length < 2) resetTouchPinch();
                return;
            }

            if (!isInsidePreview(event.target) || shouldIgnoreZoomTarget(event.target)) return;
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

        document.addEventListener("touchmove", (event) => {
            if (localPinch.active && event.touches && event.touches.length === 2) {
                event.preventDefault();
                applyPinchZoom(localPinch.startDistance, getTouchDistance(event.touches), localPinch.startFov, isMobileViewport() ? 78 : 66);
            }
        }, { passive: false, capture: true });
        document.addEventListener("touchend", (event) => {
            if (localPinch.active && (!event.touches || event.touches.length < 2)) resetTouchPinch();
        }, { passive: false, capture: true });
        document.addEventListener("touchcancel", resetTouchPinch, { passive: false, capture: true });

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
            activePointers.set(event.pointerId, { clientX: event.clientX, clientY: event.clientY });
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
            activePointers.set(event.pointerId, { clientX: event.clientX, clientY: event.clientY });
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
            view.setParameters({ fov: clamp(gestureStartFov - zoomDelta, MIN_FOV, MAX_FOV) });
            syncZoomButtonsState();
        }, { passive: false, capture: true });

        previewViewer.addEventListener("gestureend", (event) => {
            event.preventDefault();
            gestureStartFov = 0;
            syncZoomButtonsState();
        }, { passive: false, capture: true });

        previewViewer.addEventListener("wheel", (event) => {
            if (shouldIgnoreZoomTarget(event.target)) return;
            const view = getCurrentView();
            if (!view) return;
            event.preventDefault();
            stopAutorotate();
            const direction = event.deltaY > 0 ? 1 : -1;
            setZoomInstant(view.fov() + degToRad(direction * 7));
        }, { passive: false, capture: true });
    }

    function bindZoomButton(button, handler) {
        if (!button) return;
        button.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            handler();
        }, { passive: false });
    }

    sceneStackToggle?.addEventListener("click", toggleSceneStack);
    prevSceneBtn?.addEventListener("click", () => goToRelativeScene(-1));
    nextSceneBtn?.addEventListener("click", () => goToRelativeScene(1));

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
    previewViewer?.addEventListener("click", () => closeInfoPanel());
    previewViewer?.addEventListener("pointerdown", () => stopAutorotate());

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
        if (event.key === "ArrowLeft") goToRelativeScene(-1);
        if (event.key === "ArrowRight") goToRelativeScene(1);
        if (event.key === "+") zoomBy(-8);
        if (event.key === "-") zoomBy(8);
    });

    setupResponsiveMode();
    injectPreviewCinematicStyles();
    injectWalkTransitionStyles();
    ensureWalkTransitionOverlay();

    if (!scenes.length) {
        if (sceneCountBadge) sceneCountBadge.textContent = "0";
        return;
    }

    if (sceneCountBadge) sceneCountBadge.textContent = `${getNavigationSceneList().length}`;

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
