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
    const previewSceneLoadingOverlay = $("previewSceneLoadingOverlay");
    const previewSceneLoadingImage = $("previewSceneLoadingImage");
    const previewSceneLoadingText = $("previewSceneLoadingText");

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
    let autorotateSuppressedByUser = false;
    let autorotateFrame = null;
    let autorotateLastTs = 0;
    let focusMode = false;
    let toastTimer = null;

    /* Progressive 360 loading state */
    let progressiveGeneration = 0;
    let progressiveUpgradeTimer = null;
    const QUALITY_CACHE_NAME = "ziarama-360-quality-v1";

    async function isPersistentQualityCached(url) {
        if (!url) return false;
        try {
            if ("caches" in window) {
                const cached = await caches.match(url, { ignoreSearch: false });
                if (cached) return true;
            }
        } catch (_) {}
        try {
            return localStorage.getItem(`ziarama360:${url}`) === "1";
        } catch (_) {
            return false;
        }
    }

    async function persistQualityAsset(url) {
        if (!url) return;
        try {
            localStorage.setItem(`ziarama360:${url}`, "1");
        } catch (_) {}
        if (!("caches" in window)) return;
        try {
            const cache = await caches.open(QUALITY_CACHE_NAME);
            const existing = await cache.match(url);
            if (existing) return;
            const response = await fetch(url, {
                credentials: "same-origin",
                cache: "force-cache",
            });
            if (response.ok || response.type === "opaque") {
                await cache.put(url, response.clone());
            }
        } catch (_) {}
    }

    async function getBestInitialEntry(sceneData) {
        const plan = getProgressiveLoadPlan(sceneData);
        const clearEntry = plan.compatible || plan.light;
        if (clearEntry?.url && await isPersistentQualityCached(clearEntry.url)) {
            console.info("[360 progressive] cached clear image selected", {
                sceneId: sceneData?.id,
                quality: clearEntry.quality,
                url: clearEntry.url,
            });
            return clearEntry;
        }
        return plan.light || clearEntry;
    }
    const decodedImageCache = new Map();
    const decodedImageMetaCache = new Map();
    const preloadPromises = new Map();
    const layerQuality = { A: "none", B: "none" };
    const layerSceneId = { A: null, B: null };

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
        const userAgent = String(navigator.userAgent || navigator.vendor || "").toLowerCase();
        const mobileUserAgent = /android|iphone|ipad|ipod|mobile|webos|blackberry|iemobile|opera mini/.test(userAgent);
        const coarsePointer = window.matchMedia?.("(pointer: coarse)")?.matches === true;
        const touchDevice = navigator.maxTouchPoints > 0 || "ontouchstart" in window;
        const compactScreen = window.matchMedia?.("(max-width: 900px)")?.matches === true;
        return Boolean(mobileUserAgent || (coarsePointer && touchDevice && compactScreen));
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

    function blurFocusedElementInside(element) {
        const focused = document.activeElement;
        if (!element || !focused || !element.contains(focused)) return;
        try { focused.blur?.(); } catch (_) {}
    }

    function restoreFocusSafely(element) {
        requestAnimationFrame(() => {
            if (!element || !document.contains(element) || typeof element.focus !== "function") return;
            try { element.focus({ preventScroll: true }); }
            catch (_) { try { element.focus(); } catch (_) {} }
        });
    }

    function setLayerAccessibility(layerKey, isActive) {
        const layer = getLayerEl(layerKey);
        if (!layer) return;

        if (isActive) {
            layer.removeAttribute("inert");
            try { layer.inert = false; } catch (_) {}
            layer.setAttribute("aria-hidden", "false");
            return;
        }

        // Focus must leave the layer before it becomes hidden/inert.
        blurFocusedElementInside(layer);
        layer.setAttribute("aria-hidden", "true");
        layer.setAttribute("inert", "");
        try { layer.inert = true; } catch (_) {}
    }

    function prepareLayersForTransition(outgoingKey, incomingKey) {
        // Both layers are visible during the cinematic crossfade.
        [outgoingKey, incomingKey].forEach((key) => {
            const layer = getLayerEl(key);
            if (!layer) return;
            layer.removeAttribute("inert");
            try { layer.inert = false; } catch (_) {}
            layer.setAttribute("aria-hidden", "false");
        });
    }

    function syncLayerAccessibility(activeKey = activeLayerKey) {
        setLayerAccessibility("A", activeKey === "A");
        setLayerAccessibility("B", activeKey === "B");
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

        // Mobile reste strictement sur la version mobile.
        const mobile =
            assets.viewer_mobile ||
            assets.mobile ||
            sceneData?.image_360_mobile_url ||
            sceneData?.mobile_image_url ||
            "";

        // Desktop reste strictement sur la version desktop.
        const desktop =
            assets.viewer_desktop ||
            assets.desktop ||
            sceneData?.image_360_desktop_url ||
            sceneData?.desktop_image_url ||
            sceneData?.image_360_url ||
            "";

        const original =
            assets.original ||
            sceneData?.image_360_original_url ||
            "";

        return {
            preview,
            thumbnail,
            mobile,
            desktop,
            original,
            mobileFallback: mobile || preview || thumbnail || "",
            desktopFallback: desktop || original || preview || thumbnail || "",
        };
    }

    function getPreferredImageUrl(sceneData) {
        const assets = getSceneAssets(sceneData);
        if (isMobileViewport()) {
            return assets.mobile || assets.preview || assets.thumbnail || "";
        }
        return assets.desktop || assets.original || assets.preview || assets.thumbnail || "";
    }

    function getConnectionProfile() {
        const connection =
            navigator.connection ||
            navigator.mozConnection ||
            navigator.webkitConnection ||
            null;

        const effectiveType = String(connection?.effectiveType || "").toLowerCase();
        const saveData = Boolean(connection?.saveData);
        const memory = Number(navigator.deviceMemory || 0);
        const cores = Number(navigator.hardwareConcurrency || 0);
        const slowNetwork = saveData || effectiveType === "slow-2g" || effectiveType === "2g";
        const mediumNetwork = effectiveType === "3g";
        const lowMemory = memory > 0 && memory <= 2;
        const modestDevice = (memory > 0 && memory <= 4) || (cores > 0 && cores <= 4);

        return {
            saveData,
            effectiveType,
            slowNetwork,
            mediumNetwork,
            lowMemory,
            modestDevice,
            online: navigator.onLine !== false
        };
    }

    function getProgressiveLoadPlan(sceneData) {
        const assets = getSceneAssets(sceneData);
        const profile = getConnectionProfile();
        const mobileDevice = isMobileViewport();

        if (mobileDevice) {
            const light = assets.preview || assets.thumbnail || assets.mobile || "";
            const compatible = assets.mobile || light || "";
            const sequence = [];
            [
                { quality: "light", url: light },
                { quality: "mobile", url: compatible },
            ].forEach((entry) => {
                if (entry.url && !sequence.some((item) => item.url === entry.url)) sequence.push(entry);
            });
            return {
                deviceMode: "mobile",
                light: sequence[0] || null,
                compatible: sequence[1] || sequence[0] || null,
                ultra: null,
                sequence,
                profile,
            };
        }

        const light = assets.preview || assets.thumbnail || assets.desktop || assets.original || "";
        const compatible = assets.desktop || assets.original || light || "";
        const sequence = [];
        [
            { quality: "light", url: light },
            { quality: "desktop", url: compatible },
        ].forEach((entry) => {
            if (entry.url && !sequence.some((item) => item.url === entry.url)) sequence.push(entry);
        });
        return {
            deviceMode: "desktop",
            light: sequence[0] || null,
            compatible: sequence[1] || sequence[0] || null,
            ultra: null,
            sequence,
            profile,
        };
    }

    function preloadDecodedImage(url, { priority = "auto", timeoutMs = 30000 } = {}) {
        if (!url) return Promise.resolve(false);
        if (decodedImageCache.has(url)) return Promise.resolve(true);
        if (preloadPromises.has(url)) return preloadPromises.get(url);

        const promise = new Promise((resolve) => {
            const image = new Image();
            let settled = false;
            let timeoutId = null;

            image.decoding = "async";

            /*
             * IMPORTANT : une image créée uniquement pour le préchargement n'est
             * pas insérée dans le DOM. Avec loading="lazy", plusieurs navigateurs
             * peuvent reporter indéfiniment son téléchargement. Elle doit donc
             * toujours être eager. fetchPriority garde la priorité réseau voulue.
             */
            image.loading = "eager";
            try { image.fetchPriority = priority; } catch (_) {}

            const finish = async (ok, reason = "") => {
                if (settled) return;
                settled = true;
                if (timeoutId) clearTimeout(timeoutId);

                if (ok) {
                    try {
                        if (typeof image.decode === "function") await image.decode();
                    } catch (_) {
                        /* Le fichier est déjà chargé ; decode() peut échouer sur Safari. */
                    }

                    decodedImageCache.set(url, true);
                    decodedImageMetaCache.set(url, {
                        width: Number(image.naturalWidth || 0),
                        height: Number(image.naturalHeight || 0),
                    });

                    console.info("[360 progressive] image ready", {
                        url,
                        priority,
                        width: image.naturalWidth,
                        height: image.naturalHeight,
                    });
                } else {
                    console.warn("[360 progressive] image preload failed", {
                        url,
                        priority,
                        reason,
                    });
                }

                preloadPromises.delete(url);
                resolve(ok);
            };

            image.onload = () => finish(true, "load");
            image.onerror = () => finish(false, "error");

            timeoutId = setTimeout(() => {
                finish(false, "timeout");
            }, timeoutMs);

            image.src = url;

            if (image.complete && image.naturalWidth > 0) {
                finish(true, "memory-cache");
            }
        });

        preloadPromises.set(url, promise);
        return promise;
    }

    function setSceneLoadingPreview(sceneData, visible = true, message = "Loading panorama") {
        if (!previewSceneLoadingOverlay) return;

        if (!visible) {
            previewSceneLoadingOverlay.classList.remove("is-visible", "is-progressive-visible");
            previewSceneLoadingOverlay.setAttribute("aria-hidden", "true");
            return;
        }

        const plan = getProgressiveLoadPlan(sceneData);
        const previewUrl = plan.light?.url || getSceneThumbnailUrl(sceneData);

        if (previewSceneLoadingImage) {
            if (previewUrl) {
                previewSceneLoadingImage.src = previewUrl;
                previewSceneLoadingImage.classList.remove("hidden");
            } else {
                previewSceneLoadingImage.removeAttribute("src");
                previewSceneLoadingImage.classList.add("hidden");
            }
        }

        if (previewSceneLoadingText) previewSceneLoadingText.textContent = message;
        previewSceneLoadingOverlay.classList.add("is-visible", "is-progressive-visible");
        previewSceneLoadingOverlay.setAttribute("aria-hidden", "false");
    }

    function copyViewParameters(fromView, toView) {
        if (!fromView || !toView) return;
        try {
            toView.setParameters({
                yaw: fromView.yaw(),
                pitch: fromView.pitch(),
                fov: fromView.fov()
            });
        } catch (_) {}
    }

    function cancelProgressiveWork() {
        progressiveGeneration += 1;
        clearTimeout(progressiveUpgradeTimer);
        progressiveUpgradeTimer = null;
    }

    function runWhenIdle(callback, timeout = 1400) {
        if (typeof window.requestIdleCallback === "function") {
            window.requestIdleCallback(callback, { timeout });
        } else {
            setTimeout(callback, Math.min(timeout, 650));
        }
    }

    function preloadNeighbourScenes(sceneData, generation) {
        const list = getNavigationSceneList();
        if (!list.length || generation !== progressiveGeneration) return;

        let index = findSceneListIndex(sceneData?.id);
        if (index < 0) index = 0;

        const candidates = [
            list[(index + 1) % list.length],
            list[(index - 1 + list.length) % list.length]
        ].filter(Boolean);

        runWhenIdle(() => {
            if (generation !== progressiveGeneration || document.hidden) return;
            candidates.forEach((entry) => {
                const neighbour = findScene(entry?.id) || findScene(entry?.scene_id) || entry;
                const plan = getProgressiveLoadPlan(neighbour);
                const target = plan.compatible || plan.light;
                if (target?.url) preloadDecodedImage(target.url, { priority: "low" });
            });
        }, 1800);
    }

    async function silentlyUpgradeCurrentScene(sceneData, generation, preferredEntry = null) {
        if (!sceneData || generation !== progressiveGeneration || isTransitioning) return false;

        const plan = getProgressiveLoadPlan(sceneData);
        const currentQuality = layerQuality[activeLayerKey];
        const upgradeEntry =
            preferredEntry ||
            (currentQuality === "light" ? plan.compatible : plan.ultra);

        if (!upgradeEntry?.url) {
            preloadNeighbourScenes(sceneData, generation);
            return false;
        }

        const currentPlanEntry = plan.sequence.find((item) => item.quality === currentQuality);
        if (currentPlanEntry?.url === upgradeEntry.url) {
            preloadNeighbourScenes(sceneData, generation);
            return false;
        }

        const loaded = await preloadDecodedImage(upgradeEntry.url, { priority: "low" });
        if (loaded) persistQualityAsset(upgradeEntry.url);
        if (!loaded || generation !== progressiveGeneration || isTransitioning) return false;
        if (!sceneMatchesId(sceneData, currentSceneId)) return false;

        const outgoingKey = activeLayerKey;
        const incomingKey = standbyLayerKey();
        const outgoingView = views[outgoingKey];

        const built = buildSceneOnLayer(incomingKey, sceneData, {
            imageUrl: upgradeEntry.url,
            quality: upgradeEntry.quality,
            preserveHotspots: true
        });
        if (!built || generation !== progressiveGeneration) return false;

        copyViewParameters(outgoingView, views[incomingKey]);

        const outgoingEl = getLayerEl(outgoingKey);
        const incomingEl = getLayerEl(incomingKey);
        if (!outgoingEl || !incomingEl) return false;

        closeAllFloorPopovers(null, { restoreFocus: false });
        prepareLayersForTransition(outgoingKey, incomingKey);

        incomingEl.classList.remove("standby-layer", "layer-incoming", "layer-outgoing");
        outgoingEl.classList.remove("layer-incoming", "layer-outgoing");
        incomingEl.classList.add("quality-upgrade-incoming");
        outgoingEl.classList.add("quality-upgrade-outgoing");
        incomingEl.style.opacity = "1";

        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        incomingEl.classList.add("quality-upgrade-visible");

        await new Promise((resolve) => setTimeout(resolve, 520));
        if (generation !== progressiveGeneration || isTransitioning) return false;

        outgoingEl.classList.remove("active-layer", "quality-upgrade-outgoing");
        outgoingEl.classList.add("standby-layer");
        outgoingEl.style.opacity = "0";

        incomingEl.classList.remove(
            "standby-layer",
            "quality-upgrade-incoming",
            "quality-upgrade-visible"
        );
        incomingEl.classList.add("active-layer");
        incomingEl.style.opacity = "1";

        activeLayerKey = incomingKey;
        syncLayerAccessibility(activeLayerKey);
        updateAllViewerSizes();
        syncZoomButtonsState();

        progressiveUpgradeTimer = setTimeout(() => {
            silentlyUpgradeCurrentScene(sceneData, generation);
        }, 700);

        preloadNeighbourScenes(sceneData, generation);
        return true;
    }

    function scheduleProgressiveUpgrade(sceneData, generation = progressiveGeneration) {
        clearTimeout(progressiveUpgradeTimer);

        const plan = getProgressiveLoadPlan(sceneData);
        console.info("[360 progressive] upgrade scheduled", {
            sceneId: sceneData?.id,
            deviceMode: plan.deviceMode,
            currentQuality: layerQuality[activeLayerKey],
            light: plan.light?.url || "",
            compatible: plan.compatible?.url || "",
        });

        progressiveUpgradeTimer = setTimeout(() => {
            silentlyUpgradeCurrentScene(sceneData, generation).then((upgraded) => {
                console.info("[360 progressive] upgrade finished", {
                    sceneId: sceneData?.id,
                    upgraded,
                    activeQuality: layerQuality[activeLayerKey],
                });
            });
        }, getConnectionProfile().mediumNetwork ? 1400 : 760);
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

    function stopAutorotate({ suppress = false } = {}) {
        if (suppress) autorotateSuppressedByUser = true;
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

    function startAutorotate({ force = false } = {}) {
        if (autorotateEnabled) return;
        if (autorotateSuppressedByUser && !force) return;
        if (force) autorotateSuppressedByUser = false;
        autorotateEnabled = true;
        autorotateBtn?.classList.add("active");
        autorotateFrame = requestAnimationFrame(autorotateLoop);
    }

    function toggleAutorotate() {
        if (autorotateEnabled) {
            stopAutorotate({ suppress: true });
        } else {
            startAutorotate({ force: true });
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

    const previewMediaModal = $("previewMediaModal");
    const previewMediaBody = $("previewMediaBody");
    const previewMediaTitle = $("previewMediaTitle");
    const previewMediaKicker = $("previewMediaKicker");
    const previewMediaFooter = $("previewMediaFooter");
    const previewFloorNavigator = $("previewFloorNavigator");
    let mediaModalPreviousFocus = null;
    let activePdfRenderToken = 0;
    let activePdfLoadingTask = null;
    let activePdfDocument = null;
    let activePdfObserver = null;

    function escapeAttr(value) { return String(value || "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }

    async function stopMediaPlayback() {
        activePdfRenderToken += 1;

        try { activePdfObserver?.disconnect?.(); } catch (_) {}
        activePdfObserver = null;

        try { await activePdfLoadingTask?.destroy?.(); } catch (_) {}
        activePdfLoadingTask = null;

        try { await activePdfDocument?.destroy?.(); } catch (_) {}
        activePdfDocument = null;

        previewMediaBody?.querySelectorAll("video").forEach(v => {
            try { v.pause(); v.removeAttribute("src"); v.load(); } catch (_) {}
        });
        previewMediaBody?.querySelectorAll("iframe").forEach(f => {
            try { f.src = "about:blank"; } catch (_) {}
        });
    }

    function closeMediaHotspot() {
        const focused = document.activeElement;
        if (focused && previewMediaModal?.contains(focused) && typeof focused.blur === "function") {
            focused.blur();
        }
        stopMediaPlayback();
        previewMediaModal?.classList.remove("open");
        previewMediaModal?.setAttribute("inert", "");
        previewMediaModal?.setAttribute("aria-hidden", "true");
        const focusTarget = mediaModalPreviousFocus;
        mediaModalPreviousFocus = null;
        restoreFocusSafely(focusTarget);
    }

    document.querySelectorAll("[data-media-close]").forEach(el => {
        el.addEventListener("click", closeMediaHotspot);
    });

    function extractYouTubeId(url) {
        try {
            const u = new URL(url, location.href);
            const host = u.hostname.replace(/^www\./, "").toLowerCase();
            if (host === "youtu.be") return u.pathname.split("/").filter(Boolean)[0] || "";
            if (host.endsWith("youtube.com") || host.endsWith("youtube-nocookie.com")) {
                if (u.searchParams.get("v")) return u.searchParams.get("v");
                const parts = u.pathname.split("/").filter(Boolean);
                const marker = parts.findIndex((part) => ["embed", "shorts", "live"].includes(part));
                if (marker >= 0 && parts[marker + 1]) return parts[marker + 1];
            }
        } catch (_) {}
        return "";
    }

    function toEmbedUrl(url, autoplay=false, muted=false) {
        try {
            const u = new URL(url, location.href);
            const youtubeId = extractYouTubeId(url);
            if (youtubeId) {
                const params = new URLSearchParams({
                    playsinline: "1",
                    autoplay: autoplay ? "1" : "0",
                    mute: muted ? "1" : "0",
                    rel: "0",
                    modestbranding: "1",
                    enablejsapi: "1",
                    origin: location.origin,
                });
                return `https://www.youtube-nocookie.com/embed/${encodeURIComponent(youtubeId)}?${params.toString()}`;
            }
            if (u.hostname.includes("vimeo.com")) {
                const id = u.pathname.split("/").filter(Boolean).pop();
                return id ? `https://player.vimeo.com/video/${encodeURIComponent(id)}?autoplay=${autoplay?1:0}&muted=${muted?1:0}` : "";
            }
        } catch (_) {}
        return "";
    }

    function isSamsungInternet() {
        const ua = String(navigator.userAgent || "").toLowerCase();
        return ua.includes("samsungbrowser");
    }

    function isIOSWebKit() {
        const ua = String(navigator.userAgent || "");
        const platform = String(navigator.platform || "");
        const touchMac = platform === "MacIntel" && Number(navigator.maxTouchPoints || 0) > 1;
        return /iPad|iPhone|iPod/i.test(ua) || touchMac;
    }

    function shouldDisablePdfWorker() {
        // Physical iPhone/iPad and Samsung Internet are more reliable
        // when PDF.js parses the document on the main thread.
        return isIOSWebKit() || isSamsungInternet() || isMobileViewport();
    }

    async function importPdfJsModule(primaryUrl) {
        const legacyUrl = String(
            config.pdfJsLegacyModuleUrl ||
            "/static/public/vendor/pdfjs/legacy/build/pdf.mjs"
        ).trim();

        const candidates = isIOSWebKit()
            ? [legacyUrl, primaryUrl]
            : [primaryUrl, legacyUrl];

        let lastError = null;

        for (const candidate of candidates.filter(Boolean)) {
            try {
                console.info("[PDF.js] importing module", {
                    candidate,
                    ios: isIOSWebKit(),
                    samsung: isSamsungInternet(),
                });
                const module = await import(candidate);
                console.info("[PDF.js] module imported", {
                    candidate,
                    version: module?.version || "unknown",
                });
                return { module, moduleUrl: candidate };
            } catch (error) {
                lastError = error;
                console.warn("[PDF.js] module import failed", {
                    candidate,
                    message: error?.message || String(error),
                });
            }
        }

        throw lastError || new Error("Unable to load the PDF reader module.");
    }

    function waitForPdfContainer(element, timeoutMs = 3000) {
        return new Promise((resolve, reject) => {
            const startedAt = performance.now();

            const inspect = () => {
                if (!element || !document.body.contains(element)) {
                    reject(new Error("The PDF container was removed."));
                    return;
                }

                const rect = element.getBoundingClientRect();
                const style = window.getComputedStyle(element);
                const visible =
                    rect.width >= 240 &&
                    rect.height >= 180 &&
                    style.display !== "none" &&
                    style.visibility !== "hidden";

                if (visible) {
                    resolve(rect);
                    return;
                }

                if (performance.now() - startedAt >= timeoutMs) {
                    reject(new Error("The PDF reader did not receive a visible size."));
                    return;
                }

                requestAnimationFrame(inspect);
            };

            requestAnimationFrame(inspect);
        });
    }

    function getPdfOutputScale() {
        const ratio = Number(window.devicePixelRatio || 1);
        // Un téléphone physique ne doit pas créer des dizaines de canvas 2x/3x.
        return isMobileViewport()
            ? 1
            : Math.min(Math.max(ratio, 1), 1.5);
    }

    async function renderPdfPage({ pdf, pageNumber, shell, pagesRoot, token }) {
        if (token !== activePdfRenderToken || shell.dataset.rendered === "1") return;
        shell.dataset.rendering = "1";

        try {
            const page = await pdf.getPage(pageNumber);
            if (token !== activePdfRenderToken) return;

            const baseViewport = page.getViewport({ scale: 1 });
            const rootRect = pagesRoot.getBoundingClientRect();
            const availableWidth = Math.max(
                260,
                Math.min(
                    rootRect.width - (isMobileViewport() ? 12 : 30),
                    isMobileViewport() ? Math.min(window.innerWidth - 20, 720) : 920
                )
            );
            const cssScale = clamp(availableWidth / baseViewport.width, 0.55, 2.2);
            const viewport = page.getViewport({ scale: cssScale });
            const outputScale = getPdfOutputScale();

            const canvas = document.createElement("canvas");
            canvas.className = "preview-pdf-canvas";
            canvas.width = Math.max(1, Math.floor(viewport.width * outputScale));
            canvas.height = Math.max(1, Math.floor(viewport.height * outputScale));
            canvas.style.width = `${Math.floor(viewport.width)}px`;
            canvas.style.height = `${Math.floor(viewport.height)}px`;

            const context = canvas.getContext("2d", {
                alpha: false,
                willReadFrequently: false,
            });
            if (!context) throw new Error("Canvas 2D is unavailable");

            shell.innerHTML = "";
            shell.appendChild(canvas);

            await page.render({
                canvasContext: context,
                viewport,
                transform: outputScale !== 1
                    ? [outputScale, 0, 0, outputScale, 0, 0]
                    : null,
                background: "#ffffff",
            }).promise;

            page.cleanup?.();
            shell.dataset.rendered = "1";
            delete shell.dataset.rendering;
        } catch (error) {
            delete shell.dataset.rendering;
            shell.innerHTML = `<div class="preview-pdf-page-error">Page ${pageNumber} unavailable</div>`;
            console.error("PDF_PAGE_RENDER_FAILED", { pageNumber, error });
        }
    }

    async function renderPdfInsideDialog(url) {
        const token = ++activePdfRenderToken;

        try { activePdfObserver?.disconnect?.(); } catch (_) {}
        activePdfObserver = null;
        try { await activePdfLoadingTask?.destroy?.(); } catch (_) {}
        activePdfLoadingTask = null;
        try { await activePdfDocument?.destroy?.(); } catch (_) {}
        activePdfDocument = null;

        const moduleUrl = String(
            config.pdfJsModuleUrl ||
            "/static/public/vendor/pdfjs/build/pdf.mjs"
        ).trim();

        const workerUrl = String(
            config.pdfJsWorkerUrl ||
            "/static/public/vendor/pdfjs/build/pdf.worker.mjs"
        ).trim();

        previewMediaBody.innerHTML = `
            <div class="preview-pdf-reader is-rendering" data-pdf-reader>
                <div class="preview-pdf-loading">
                    <span></span>
                    <strong>Loading document…</strong>
                    <small>Preparing the first page</small>
                </div>
                <div class="preview-pdf-pages" data-pdf-pages></div>
            </div>`;

        const reader = previewMediaBody.querySelector("[data-pdf-reader]");
        const pagesRoot = previewMediaBody.querySelector("[data-pdf-pages]");

        try {
            await waitForPdfContainer(reader);
            if (token !== activePdfRenderToken) return;

            console.info("[PDF.js] loading module", { moduleUrl, workerUrl, url });
            const importedPdfJs = await importPdfJsModule(moduleUrl);
            const pdfjsLib = importedPdfJs.module;
            const effectiveWorkerUrl = importedPdfJs.moduleUrl.includes("/legacy/")
                ? String(
                    config.pdfJsLegacyWorkerUrl ||
                    "/static/public/vendor/pdfjs/legacy/build/pdf.worker.mjs"
                ).trim()
                : workerUrl;

            if (pdfjsLib?.GlobalWorkerOptions) {
                pdfjsLib.GlobalWorkerOptions.workerSrc = effectiveWorkerUrl;
            }

            const response = await fetch(url, {
                method: "GET",
                credentials: "same-origin",
                cache: "force-cache",
                headers: {
                    Accept: "application/pdf",
                    "X-Requested-With": "XMLHttpRequest",
                },
            });

            if (!response.ok) throw new Error(`PDF HTTP ${response.status}`);

            const contentType = String(response.headers.get("content-type") || "").toLowerCase();
            if (contentType && !contentType.includes("application/pdf") && !contentType.includes("octet-stream")) {
                throw new Error(`Invalid PDF response: ${contentType}`);
            }

            const pdfBytes = new Uint8Array(await response.arrayBuffer());
            if (!pdfBytes.length) throw new Error("The PDF file is empty.");

            const signature = String.fromCharCode(...pdfBytes.slice(0, 5));
            if (signature !== "%PDF-") {
                throw new Error("The server response is not a valid PDF file.");
            }
            if (token !== activePdfRenderToken) return;

            const disableWorker = shouldDisablePdfWorker();

            activePdfLoadingTask = pdfjsLib.getDocument({
                data: pdfBytes,
                isEvalSupported: false,
                disableWorker,
                disableAutoFetch: isMobileViewport(),
                disableStream: true,
                useWorkerFetch: false,
                verbosity: 0,
            });

            console.info("[PDF.js] document task created", {
                disableWorker,
                samsungInternet: isSamsungInternet(),
                mobile: isMobileViewport(),
                bytes: pdfBytes.length,
            });

            const pdf = await activePdfLoadingTask.promise;
            activePdfDocument = pdf;
            if (token !== activePdfRenderToken) return;

            // Crée des emplacements légers. On ne crée pas tous les canvas à la fois.
            const shells = [];
            for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
                const shell = document.createElement("article");
                shell.className = "preview-pdf-page preview-pdf-page-placeholder";
                shell.dataset.pageNumber = String(pageNumber);
                shell.innerHTML = `<div class="preview-pdf-page-placeholder-label">Page ${pageNumber}</div>`;
                pagesRoot.appendChild(shell);
                shells.push(shell);
            }

            // La première page est rendue avant de retirer le loader.
            await renderPdfPage({
                pdf,
                pageNumber: 1,
                shell: shells[0],
                pagesRoot,
                token,
            });
            if (token !== activePdfRenderToken) return;

            reader.classList.remove("is-rendering");
            reader.classList.add("is-ready");

            // Les autres pages sont rendues seulement quand elles approchent de l'écran.
            activePdfObserver = new IntersectionObserver((entries) => {
                entries.forEach((entry) => {
                    if (!entry.isIntersecting) return;
                    const shell = entry.target;
                    const pageNumber = Number(shell.dataset.pageNumber || 0);
                    if (!pageNumber || shell.dataset.rendered === "1" || shell.dataset.rendering === "1") return;
                    renderPdfPage({ pdf, pageNumber, shell, pagesRoot, token });
                });
            }, {
                root: reader,
                rootMargin: "700px 0px",
                threshold: 0.01,
            });

            shells.slice(1).forEach(shell => activePdfObserver.observe(shell));
            console.info("[PDF.js] first page ready", { pages: pdf.numPages, url });
        } catch (error) {
            console.error("PDF_RENDER_FAILED", error);
            if (token !== activePdfRenderToken) return;

            previewMediaBody.innerHTML = `
                <div class="preview-pdf-fallback">
                    <strong>Unable to display this PDF inside the tour.</strong>
                    <p>${escapeAttr(
                        error?.message ||
                        (isIOSWebKit()
                            ? "The iPhone PDF reader could not start. Please try again."
                            : "The PDF reader could not start.")
                    )}</p>
                    <button type="button" class="preview-media-action preview-media-action-primary" data-pdf-retry>
                        Try again
                    </button>
                </div>`;

            previewMediaBody.querySelector("[data-pdf-retry]")?.addEventListener("click", () => {
                renderPdfInsideDialog(url);
            });
        }
    }

    async function openMediaHotspot(hotspot) {
        if (!previewMediaModal || !previewMediaBody) return;

        mediaModalPreviousFocus = document.activeElement;
        previewMediaModal.removeAttribute("inert");
        previewMediaModal.setAttribute("aria-hidden", "false");
        previewMediaModal.classList.add("open");

        const c = hotspot.payload?.content || {};
        previewMediaTitle.textContent = hotspot.title || hotspot.label || (hotspot.type === "pdf" ? "Document" : "Video");
        previewMediaKicker.textContent = hotspot.type === "pdf" ? "PDF DOCUMENT" : "VIDEO";
        previewMediaBody.innerHTML = "";
        previewMediaFooter.innerHTML = "";

        if (hotspot.type === "pdf") {
            const url = c.document_url || hotspot.media_file_url || "";
            if (!url) {
                previewMediaBody.innerHTML = `<div class="preview-media-empty">PDF unavailable</div>`;
            } else {
                previewMediaFooter.innerHTML = `
                    <button type="button" class="preview-media-action preview-media-action-secondary" data-pdf-reload>Reload</button>
                    <a class="preview-media-action preview-media-action-secondary" href="${escapeAttr(url)}" target="_blank" rel="noopener">Full screen</a>
                    ${c.allow_download === false ? "" : `<a class="preview-media-action preview-media-action-primary" href="${escapeAttr(url)}" download>Download</a>`}`;

                previewMediaFooter.querySelector("[data-pdf-reload]")?.addEventListener("click", () => {
                    renderPdfInsideDialog(url);
                });

                // Laisse deux frames au dialog mobile pour recevoir sa vraie taille.
                requestAnimationFrame(() => {
                    requestAnimationFrame(() => renderPdfInsideDialog(url));
                });
            }
        } else {
            const url = c.video_url || hotspot.media_file_url || "";
            const embed = toEmbedUrl(url, !!c.autoplay, !!c.muted);
            if (embed) {
                previewMediaBody.innerHTML = `<iframe class="preview-video-frame" src="${escapeAttr(embed)}" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen></iframe>`;
            } else if (url) {
                previewMediaBody.innerHTML = `<video class="preview-video-player" controls playsinline preload="metadata" ${c.autoplay ? "autoplay" : ""} ${c.muted ? "muted" : ""} ${c.loop ? "loop" : ""} poster="${escapeAttr(c.poster_url || hotspot.poster_image_url || "")}"><source src="${escapeAttr(url)}"></video>`;
            } else {
                previewMediaBody.innerHTML = `<div class="preview-media-empty">Video unavailable</div>`;
            }
        }

        stopAutorotate({ suppress: true });
        requestAnimationFrame(() => {
            const closeButton = previewMediaModal.querySelector("[data-media-close]");
            closeButton?.focus({ preventScroll: true });
        });
    }

    function showFloorTransitionLabel(hotspot) {
        const c = hotspot.payload?.content || {}; const el = document.createElement("div");
        el.className = `preview-floor-transition ${c.direction || "up"}`;
        el.innerHTML = `<strong>${c.direction === "down" ? "↓" : c.direction === "same" ? "→" : "↑"} ${escapeAttr(c.floor_name || hotspot.title || hotspot.label || "Floor")}</strong><span>${escapeAttr(c.destination_label || "")}</span>`;
        previewViewer.appendChild(el); requestAnimationFrame(()=>el.classList.add("show")); setTimeout(()=>{el.classList.remove("show"); setTimeout(()=>el.remove(),350)},1400);
    }

    function ensureFloorDockControl() {
        const dockRow = document.querySelector("#previewControlDock .dock-row");
        if (!dockRow || document.getElementById("floorDockToggle")) return;
        const floors = collectFloorDestinations();
        if (!floors.length) return;
        const divider = document.createElement("div"); divider.className = "dock-divider floor-dock-divider";
        const wrap = document.createElement("div"); wrap.className = "floor-dock-wrap";
        wrap.innerHTML = `<button id="floorDockToggle" type="button" class="control-btn" title="Floors" aria-label="Floors">⌂</button><div id="floorDockPanel" class="floor-dock-panel"></div>`;
        dockRow.appendChild(divider); dockRow.appendChild(wrap);
        const panel = wrap.querySelector("#floorDockPanel");
        floors.forEach((floor) => {
            const b=document.createElement("button"); b.type="button"; b.innerHTML=`<span>${escapeAttr(floor.number)}</span><div><strong>${escapeAttr(floor.name)}</strong><small>${escapeAttr(floor.description)}</small></div>`;
            b.addEventListener("click", (e)=>{e.stopPropagation(); panel.classList.remove("open"); const t=findScene(floor.target); if(t){showFloorTransitionLabel(floor.hotspot); goToSceneWithWalk(t);}}); panel.appendChild(b);
        });
        const floorToggle = wrap.querySelector("#floorDockToggle");
        floorToggle.setAttribute("aria-expanded", "false");
        floorToggle.addEventListener("click", (e) => {
            e.stopPropagation();
            const opened = panel.classList.toggle("open");
            floorToggle.setAttribute("aria-expanded", opened ? "true" : "false");
        });

        document.addEventListener("click", (event) => {
            if (!wrap.contains(event.target)) {
                panel.classList.remove("open");
                floorToggle.setAttribute("aria-expanded", "false");
            }
        });
        document.addEventListener("click", ()=>panel.classList.remove("open"));
    }

    function renderFloorNavigator() {
        if (!previewFloorNavigator) return;
        const floorHotspots = scenes.flatMap(scene => (scene.hotspots || []).filter(h => h.type === "floor").map(h => ({...h, owner_scene_id: scene.id})));
        const map = new Map(); floorHotspots.forEach(h => { const c=h.payload?.content||{}; const key=String(c.floor_number ?? c.floor_name ?? h.target_scene); if(!map.has(key)) map.set(key,h); });
        previewFloorNavigator.innerHTML = "";
        [...map.values()].sort((a,b)=>Number(b.payload?.content?.floor_number||0)-Number(a.payload?.content?.floor_number||0)).forEach(h=>{ const c=h.payload?.content||{}; const b=document.createElement("button"); b.type="button"; b.innerHTML=`<span>${escapeAttr(c.floor_number ?? "•")}</span><strong>${escapeAttr(c.floor_name || h.label || "Floor")}</strong>`; b.addEventListener("click",()=>{ const t=findScene(h.target_scene); if(t) goToSceneWithWalk(t); }); previewFloorNavigator.appendChild(b); });
        previewFloorNavigator.classList.remove("has-floors");
        ensureFloorDockControl();
    }

    function collectFloorDestinations() {
        const result = [];
        const seen = new Set();

        scenes.forEach((scene) => {
            (scene.hotspots || [])
                .filter((hotspot) => hotspot.type === "floor")
                .forEach((hotspot) => {
                    const content = hotspot.payload?.content || {};
                    const groupedItems = Array.isArray(content.floor_items)
                        ? content.floor_items
                        : [];

                    const items = groupedItems.length
                        ? groupedItems
                        : [{
                            floor_name: content.floor_name,
                            floor_number: content.floor_number,
                            direction: content.direction,
                            destination_label: content.destination_label,
                            target_scene: hotspot.target_scene,
                            order: 0,
                        }];

                    items.forEach((item, itemIndex) => {
                        const target = item.target_scene || hotspot.target_scene;
                        if (!target) return;
                        const number = item.floor_number ?? item.number ?? "•";
                        const name = item.floor_name || item.name || hotspot.title || hotspot.label || "Floor";
                        const key = String(item.uid || `${number}:${target}`);
                        if (seen.has(key)) return;
                        seen.add(key);
                        result.push({
                            hotspot: {
                                ...hotspot,
                                target_scene: target,
                                payload: {
                                    ...(hotspot.payload || {}),
                                    content: {
                                        ...content,
                                        ...item,
                                    },
                                },
                            },
                            number,
                            name,
                            description: item.destination_label || item.description || "",
                            direction: item.direction || "same",
                            target,
                            order: Number(item.order ?? itemIndex),
                        });
                    });
                });
        });

        return result.sort((a, b) => {
            const numberDiff = Number(b.number || 0) - Number(a.number || 0);
            return numberDiff || Number(a.order || 0) - Number(b.order || 0);
        });
    }

    function getSurfacePerspectiveScale(view, referenceFovDeg = 100) {
        if (!view || typeof view.fov !== "function") return 1;
        const currentFov = clamp(Number(view.fov() || degToRad(referenceFovDeg)), MIN_FOV, MAX_FOV);
        const referenceFov = clamp(degToRad(referenceFovDeg), MIN_FOV, MAX_FOV);
        const denominator = Math.tan(currentFov / 2);
        if (!Number.isFinite(denominator) || denominator <= 0) return 1;
        const scale = Math.tan(referenceFov / 2) / denominator;
        return clamp(scale, 0.28, 2.5);
    }

    function updateSurfaceHotspots(layerKey) {
        const view = views[layerKey];
        const mount = getMountEl(layerKey);
        if (!view || !mount) return;
        mount.querySelectorAll(".preview-surface-hotspot").forEach((node) => {
            const referenceFov = Number(node.dataset.referenceFov || 100);
            const scale = getSurfacePerspectiveScale(view, referenceFov);
            node.style.setProperty("--surface-perspective-scale", scale.toFixed(4));
        });
    }

    function bindSurfaceScaling(layerKey) {
        const view = views[layerKey];
        if (!view || view.__surfaceScalingBound) return;
        view.__surfaceScalingBound = true;
        const refresh = () => updateSurfaceHotspots(layerKey);
        try { view.addEventListener?.("change", refresh); } catch (_) {}
        requestAnimationFrame(refresh);
    }

    function getFloorPortalForNode(node) {
        const owner = String(node?.dataset?.floorOwner || "");
        if (!owner) return null;
        return [...document.querySelectorAll(".preview-floor-portal-popover[data-floor-owner]")]
            .find((item) => String(item.dataset.floorOwner || "") === owner) || null;
    }

    function getFloorBackdropForNode(node) {
        const owner = String(node?.dataset?.floorOwner || "");
        if (!owner) return null;
        return [...document.querySelectorAll(".preview-floor-modal-backdrop[data-floor-owner]")]
            .find((item) => String(item.dataset.floorOwner || "") === owner) || null;
    }

    function stopFloorPortalTracking(node) {
        if (!node) return;
        if (node.__floorPortalFrame) {
            cancelAnimationFrame(node.__floorPortalFrame);
            node.__floorPortalFrame = null;
        }
    }

    function positionFloorPortal(node) {
        const popover = getFloorPortalForNode(node);
        const trigger = node?.querySelector?.(".preview-floor-portal-trigger");
        if (!popover || !trigger || !previewViewer) return;

        // On mobile the CSS pins the panel above the control dock.
        if (isMobileViewport()) {
            popover.classList.remove("opens-left", "opens-above");
            popover.style.removeProperty("left");
            popover.style.removeProperty("top");
            return;
        }

        const viewerRect = previewViewer.getBoundingClientRect();
        const triggerRect = trigger.getBoundingClientRect();
        const panelRect = popover.getBoundingClientRect();
        const margin = 16;
        const dockSpace = 82;

        const triggerLeft = triggerRect.left - viewerRect.left;
        const triggerRight = triggerRect.right - viewerRect.left;
        const triggerCenterY = triggerRect.top - viewerRect.top + triggerRect.height / 2;

        let left = triggerRight + margin;
        let top = triggerCenterY - panelRect.height / 2;
        let opensLeft = false;

        const availableRight = viewerRect.width - triggerRight;
        const availableLeft = triggerLeft;
        if (availableRight < panelRect.width + margin && availableLeft >= panelRect.width + margin) {
            left = triggerLeft - panelRect.width - margin;
            opensLeft = true;
        }

        const maxLeft = Math.max(margin, viewerRect.width - panelRect.width - margin);
        const maxTop = Math.max(margin, viewerRect.height - panelRect.height - dockSpace);
        left = Math.max(margin, Math.min(left, maxLeft));
        top = Math.max(margin, Math.min(top, maxTop));

        popover.classList.toggle("opens-left", opensLeft);
        popover.classList.toggle("opens-above", top < triggerCenterY - panelRect.height / 2);
        popover.style.left = `${left}px`;
        popover.style.top = `${top}px`;
    }

    function startFloorPortalTracking(node) {
        stopFloorPortalTracking(node);
        const tick = () => {
            if (!node?.classList?.contains("is-open") || !document.contains(node)) {
                stopFloorPortalTracking(node);
                return;
            }
            positionFloorPortal(node);
            node.__floorPortalFrame = requestAnimationFrame(tick);
        };
        node.__floorPortalFrame = requestAnimationFrame(tick);
    }

    function closeFloorPortalNode(node, { restoreFocus = false } = {}) {
        if (!node) return;
        const trigger = node.querySelector(".preview-floor-portal-trigger");
        const popover = getFloorPortalForNode(node);
        const backdrop = getFloorBackdropForNode(node);
        const focused = document.activeElement;
        const hadFocus = !!(
            focused &&
            (node.contains(focused) || popover?.contains(focused))
        );

        if (hadFocus) {
            try { focused.blur?.(); } catch (_) {}
        }

        stopFloorPortalTracking(node);
        node.classList.remove("is-open");
        trigger?.setAttribute("aria-expanded", "false");
        popover?.classList.remove("is-open");
        popover?.setAttribute("aria-hidden", "true");
        popover?.setAttribute("inert", "");
        backdrop?.classList.remove("is-open");
        backdrop?.setAttribute("aria-hidden", "true");
        try { if (popover) popover.inert = true; } catch (_) {}

        if (restoreFocus && hadFocus) restoreFocusSafely(trigger);
    }

    function closeAllFloorPopovers(exceptNode = null, { restoreFocus = false } = {}) {
        document.querySelectorAll(".preview-floor-portal-hotspot.is-open").forEach((node) => {
            if (node === exceptNode) return;
            closeFloorPortalNode(node, { restoreFocus });
        });
    }

    function buildFloorCardNode(hotspot, sceneData) {
        const display = hotspot.payload?.display || {};
        const floorHotspots = (sceneData?.hotspots || []).filter((item) => item.type === "floor");

        // A single premium floor hotspot groups every available destination.
        if (floorHotspots[0] && String(floorHotspots[0].id) !== String(hotspot.id)) {
            const hidden = document.createElement("div");
            hidden.style.display = "none";
            return hidden;
        }

        const floors = collectFloorDestinations();
        const content = hotspot.payload?.content || {};
        const node = document.createElement("div");

        // Old versions stored a 310px card width. Convert those values to a compact marker.
        const storedWidth = Number(display.width || display.size || 94);
        const markerWidth = storedWidth > 160 ? 94 : clamp(storedWidth, 76, 124);
        const markerHeight = clamp(Number(display.height || markerWidth), 76, 124);
        const referenceFov = Number(display.reference_fov || sceneData?.hfov_default || 100);
        const direction = String(content.direction || "up").toLowerCase();
        const directionArrow = direction === "down" ? "↓" : direction === "same" ? "→" : "↑";
        const floorIconUrl =
            hotspot.icon_url ||
            hotspot.selected_icon_url ||
            resolveIcon(hotspot.selected_icon || hotspot.icon || "floor") ||
            "";
        const currentFloorName = content.floor_name || hotspot.title || hotspot.label || "Floors";
        const floorsCount = floors.length;

        node.className = "preview-hotspot preview-surface-hotspot preview-floor-portal-hotspot";
        node.style.width = `${markerWidth}px`;
        node.style.height = `${markerHeight}px`;
        node.dataset.referenceFov = String(referenceFov);
        node.dataset.hotspotType = "floor";

        node.innerHTML = `
            <div class="preview-surface-scale-wrap">
                <button type="button"
                        class="preview-floor-portal-trigger"
                        aria-expanded="false"
                        aria-label="Open floor navigation">
                    <span class="preview-floor-portal-ring" aria-hidden="true"></span>
                    <span class="preview-floor-portal-icon" aria-hidden="true">
                        ${floorIconUrl ? `<img src="${escapeAttr(floorIconUrl)}" alt="" draggable="false">` : `
                        <svg viewBox="0 0 64 64" focusable="false" aria-hidden="true">
                            <path d="M12 52h40M17 52V22l15-9 15 9v30M24 29h5M35 29h5M24 38h5M35 38h5M29 52V44h6v8"/>
                        </svg>`}
                    </span>
                    <span class="preview-floor-portal-direction" aria-hidden="true">${directionArrow}</span>
                    <strong>${escapeAttr(currentFloorName)}</strong>
                    <small>${floorsCount} level${floorsCount === 1 ? "" : "s"}</small>
                </button>

                <section class="preview-floor-portal-popover"
                         role="dialog"
                         aria-modal="false"
                         aria-label="Property floors"
                         aria-hidden="true"
                         inert>
                    <header class="preview-floor-portal-header">
                        <div class="preview-floor-portal-heading-icon" aria-hidden="true">
                            <svg viewBox="0 0 64 64" focusable="false"><path d="M12 52h40M17 52V22l15-9 15 9v30M24 29h5M35 29h5M24 38h5M35 38h5M29 52V44h6v8"/></svg>
                        </div>
                        <div class="preview-floor-portal-heading-copy">
                            <small>PROPERTY DIRECTORY</small>
                            <strong>Explore every level</strong>
                            <span>${floorsCount} available level${floorsCount === 1 ? "" : "s"}</span>
                        </div>
                        <button type="button" class="preview-floor-portal-close" aria-label="Close floor navigation">×</button>
                    </header>
                    <div class="preview-floor-portal-current">
                        <span>Current location</span>
                        <strong>${escapeAttr(currentFloorName)}</strong>
                    </div>
                    <div class="preview-floor-portal-list"></div>
                    <footer class="preview-floor-portal-footer">
                        <span>Tap a level to continue the virtual tour</span>
                    </footer>
                </section>
            </div>`;

        const trigger = node.querySelector(".preview-floor-portal-trigger");
        const popover = node.querySelector(".preview-floor-portal-popover");
        const closeButton = popover?.querySelector(".preview-floor-portal-close");
        const list = popover?.querySelector(".preview-floor-portal-list");
        const ownerId = `floor-${String(hotspot.id || sceneData?.id || Date.now())}`;
        node.dataset.floorOwner = ownerId;

        // Keep the directory visually inside the 360 viewer, but outside the
        // Marzipano hotspot transform so it remains sharp and readable.
        document.querySelectorAll(`.preview-floor-portal-popover[data-floor-owner="${ownerId}"], .preview-floor-modal-backdrop[data-floor-owner="${ownerId}"]`).forEach((item) => item.remove());
        const backdrop = document.createElement("div");
        backdrop.className = "preview-floor-modal-backdrop";
        backdrop.dataset.floorOwner = ownerId;
        backdrop.setAttribute("aria-hidden", "true");
        popover.dataset.floorOwner = ownerId;
        previewViewer.appendChild(backdrop);
        previewViewer.appendChild(popover);

        floors.forEach((floor) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "preview-floor-portal-item";
            const floorDirection = String(floor.hotspot?.payload?.content?.direction || "same").toLowerCase();
            const floorArrow = floorDirection === "up" ? "↑" : floorDirection === "down" ? "↓" : "→";
            button.innerHTML = `
                <span class="preview-floor-level-number">${escapeAttr(floor.number)}</span>
                <div>
                    <strong>${escapeAttr(floor.name)}</strong>
                    <small>${escapeAttr(floor.description || "Open this level")}</small>
                </div>
                <b class="preview-floor-level-action" aria-hidden="true">${floorArrow}</b>`;

            button.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                const target = findScene(floor.target);
                if (!target || isTransitioning) return;
                try { document.activeElement?.blur?.(); } catch (_) {}
                closeFloorPortalNode(node);
                showFloorTransitionLabel(floor.hotspot);
                stopAutorotate({ suppress: true });
                goToSceneWithWalk(target);
            });
            list.appendChild(button);
        });

        trigger?.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            const willOpen = !node.classList.contains("is-open");
            closeAllFloorPopovers(willOpen ? node : null);
            node.classList.toggle("is-open", willOpen);
            trigger.setAttribute("aria-expanded", willOpen ? "true" : "false");
            if (willOpen) {
                popover?.removeAttribute("inert");
                popover?.setAttribute("aria-hidden", "false");
                popover?.classList.add("is-open");
                backdrop?.classList.add("is-open");
                backdrop?.setAttribute("aria-hidden", "false");
                try { if (popover) popover.inert = false; } catch (_) {}
                stopAutorotate({ suppress: true });
                requestAnimationFrame(() => {
                    positionFloorPortal(node);
                    startFloorPortalTracking(node);
                    popover?.querySelector(".preview-floor-portal-item, .preview-floor-portal-close")?.focus?.({ preventScroll: true });
                });
            } else {
                closeFloorPortalNode(node, { restoreFocus: true });
            }
        });

        closeButton?.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            try { document.activeElement?.blur?.(); } catch (_) {}
            closeFloorPortalNode(node, { restoreFocus: true });
        });

        backdrop.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            closeFloorPortalNode(node, { restoreFocus: true });
        });

        stopTouchAndScrollEventPropagation(node);
        stopTouchAndScrollEventPropagation(popover);
        return node;
    }

    document.addEventListener("click", (event) => {
        if (!event.target?.closest?.(".preview-floor-portal-hotspot, .preview-floor-portal-popover")) {
            closeAllFloorPopovers();
        }
    });

    function renderWallVideo(node, hotspot, display) {
        const c = hotspot.payload?.content || {};
        const url = c.video_url || hotspot.media_file_url || "";
        const width = Math.max(120, Math.min(900, Number(display.width || 360)));
        const height = Math.max(80, Math.min(600, Number(display.height || 210)));
        const referenceFov = Number(display.reference_fov || 100);
        node.className = "preview-hotspot preview-surface-hotspot preview-wall-video-hotspot";
        node.style.width = `${width}px`;
        node.style.height = `${height}px`;
        node.dataset.referenceFov = String(referenceFov);
        const embed = toEmbedUrl(url, !!c.autoplay, c.muted !== false);
        if (embed) node.innerHTML = `<div class="preview-surface-scale-wrap"><div class="preview-wall-video-frame"><iframe src="${escapeAttr(embed)}" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen></iframe><button type="button" aria-label="Open video">⤢</button></div></div>`;
        else node.innerHTML = `<div class="preview-surface-scale-wrap"><div class="preview-wall-video-frame"><video playsinline ${c.autoplay ? "autoplay" : ""} ${c.muted !== false ? "muted" : ""} ${c.loop ? "loop" : ""} preload="metadata" poster="${escapeAttr(c.poster_url || hotspot.poster_image_url || "")}"><source src="${escapeAttr(url)}"></video><button type="button" aria-label="Open video">⤢</button></div></div>`;
        node.querySelector("button")?.addEventListener("click", (event) => { event.stopPropagation(); openMediaHotspot(hotspot); });
        stopTouchAndScrollEventPropagation(node);
        return node;
    }

    function buildDoorNode(hotspot, display) {
        const c = hotspot.payload?.content || {};
        const node = document.createElement("div");
        const width = Math.max(80, Math.min(500, Number(display.width || 180)));
        const height = Math.max(140, Math.min(800, Number(display.height || 320)));
        const referenceFov = Number(display.reference_fov || 100);
        node.className = `preview-hotspot preview-surface-hotspot preview-door-hotspot door-open-${c.opening_direction || "left"}`;
        node.style.width = `${width}px`;
        node.style.height = `${height}px`;
        node.dataset.referenceFov = String(referenceFov);
        node.innerHTML = `<div class="preview-surface-scale-wrap"><div class="preview-door-outline"><div class="preview-door-panel"><span class="preview-door-handle"></span></div><div class="preview-door-label">${escapeAttr(hotspot.title || hotspot.label || "Open")}</div></div></div>`;
        stopTouchAndScrollEventPropagation(node);
        node.addEventListener("click", (event) => {
            event.stopPropagation();
            if (isTransitioning || !hotspot.target_scene) return;
            node.classList.add("is-opening");
            stopAutorotate();
            setTimeout(() => {
                const target = findScene(hotspot.target_scene);
                if (target) goToSceneWithWalk(target);
            }, 520);
        });
        return node;
    }

    function buildHotspotNode(hotspot, sceneData) {
        const display = hotspot.payload?.display || {};
        const variant = display.variant || "pin";
        const size = Number(display.size || 58);
        const rotation = Number(display.rotation || 0);
        const offsetX = Number(display.offset_x || 0);
        const offsetY = Number(display.offset_y || 0);
        const anchor = display.anchor || "bottom";

        if (hotspot.type === "floor") return buildFloorCardNode(hotspot, sceneData);
        if (hotspot.type === "video" && display.variant === "screen") return renderWallVideo(document.createElement("div"), hotspot, display);
        if (hotspot.type === "door") return buildDoorNode(hotspot, display);

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
            `hotspot-type-${hotspot.type || "custom"}`,
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
            if (hotspot.type === "pdf" || hotspot.type === "video") {
                openMediaHotspot(hotspot);
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

    function getSceneSourceGeometryAndLimiter(sceneData, imageUrlOverride = "") {
        const mobile = isMobileViewport();

        if (sceneData?.tiles_url && !imageUrlOverride) {
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

        const selectedImageUrl = imageUrlOverride || getPreferredImageUrl(sceneData);
        const decodedMeta = decodedImageMetaCache.get(selectedImageUrl) || {};
        const declaredWidth = mobile
            ? Number(sceneData?.mobile_width || sceneData?.image_360_mobile_width || 0)
            : Number(sceneData?.desktop_width || sceneData?.image_360_desktop_width || sceneData?.image_width || 0);
        const logicalResolution = Math.max(
            Number(decodedMeta.width || 0),
            declaredWidth,
            Number(sceneData?.face_size || 0),
            Number(sceneData?.max_resolution || 0),
            mobile ? 2048 : 4096
        );

        return {
            source: Marzipano.ImageUrlSource.fromString(selectedImageUrl),
            geometry: new Marzipano.EquirectGeometry([{ width: logicalResolution }]),
            limiter: Marzipano.RectilinearView.limit.traditional(logicalResolution, MAX_FOV)
        };
    }

    function buildSceneOnLayer(layerKey, sceneData, options = {}) {
        const viewer = ensureViewer(layerKey);
        const selectedImageUrl = options.imageUrl || getPreferredImageUrl(sceneData);
        const useTiles = Boolean(sceneData?.tiles_url && !options.imageUrl);

        if (!viewer || (!selectedImageUrl && !useTiles)) return null;

        const { source, geometry, limiter } = getSceneSourceGeometryAndLimiter(
            sceneData,
            options.imageUrl || ""
        );
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

        layerQuality[layerKey] = options.quality || (useTiles ? "tiles" : "preferred");
        layerSceneId[layerKey] = sceneData?.id ?? null;

        (sceneData.hotspots || []).forEach((hotspot) => {
            const node = buildHotspotNode(hotspot, sceneData);
            if (!node) return;
            marzipanoScenes[layerKey].hotspotContainer().createHotspot(node, {
                yaw: Number(hotspot.yaw || 0),
                pitch: Number(hotspot.pitch || 0)
            });
        });

        bindSurfaceScaling(layerKey);
        updateSurfaceHotspots(layerKey);

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
                startAutorotate({ force: false });
            }
        }, 650);
    }

    async function cinematicSwitchScene(targetScene) {
        if (!targetScene) {
            isTransitioning = false;
            return;
        }

        cancelProgressiveWork();
        const generation = progressiveGeneration;
        const outgoingKey = activeLayerKey;
        const incomingKey = standbyLayerKey();
        const cinematicMs = getCinematicTransitionMs();
        const plan = getProgressiveLoadPlan(targetScene);
        const firstEntry = await getBestInitialEntry(targetScene);

        previewViewer?.style?.setProperty("--preview-cinematic-ms", `${cinematicMs}ms`);
        setSceneLoadingPreview(targetScene, true, "Loading scene");

        if (firstEntry?.url) {
            await preloadDecodedImage(firstEntry.url, { priority: "high" });
        }

        if (generation !== progressiveGeneration) return;

        const built = buildSceneOnLayer(incomingKey, targetScene, {
            imageUrl: firstEntry?.url || "",
            quality: firstEntry?.quality || "preferred"
        });

        if (!built) {
            setSceneLoadingPreview(targetScene, false);
            isTransitioning = false;
            return;
        }

        const incomingView = views[incomingKey];
        const outgoingEl = getLayerEl(outgoingKey);
        const incomingEl = getLayerEl(incomingKey);

        if (!outgoingEl || !incomingEl) {
            activeLayerKey = incomingKey;
            syncLayerAccessibility(activeLayerKey);
            currentSceneId = targetScene.id;
            setSceneLoadingPreview(targetScene, false);
            isTransitioning = false;
            scheduleProgressiveUpgrade(targetScene, generation);
            return;
        }

        const endYaw = degToRad(targetScene.yaw_default || 0);
        const endPitch = degToRad(targetScene.pitch_default || 0);
        const finalFov = getSceneFinalFov(targetScene);

        if (incomingView) {
            incomingView.setParameters({
                yaw: endYaw,
                pitch: endPitch,
                fov: finalFov
            });
        }

        outgoingEl.classList.remove(
            "standby-layer",
            "layer-incoming",
            "layer-outgoing",
            "quality-upgrade-incoming",
            "quality-upgrade-outgoing",
            "quality-upgrade-visible"
        );
        incomingEl.classList.remove(
            "active-layer",
            "standby-layer",
            "layer-incoming",
            "layer-outgoing",
            "quality-upgrade-incoming",
            "quality-upgrade-outgoing",
            "quality-upgrade-visible"
        );

        outgoingEl.classList.add("active-layer");
        incomingEl.classList.add("layer-incoming");

        closeAllFloorPopovers(null, { restoreFocus: false });
        prepareLayersForTransition(outgoingKey, incomingKey);

        outgoingEl.style.opacity = "1";
        incomingEl.style.opacity = "1";

        previewViewer?.classList.remove("is-walk-transition");
        previewViewer?.classList.add("is-cinematic-transition", "transitioning");

        currentSceneId = targetScene.id;
        updateSceneMeta(targetScene);
        syncSceneInUrl(targetScene);
        setSceneLoadingPreview(targetScene, false);

        requestAnimationFrame(() => {
            outgoingEl.classList.add("layer-outgoing");
            incomingEl.classList.add("layer-incoming");
        });

        setTimeout(() => {
            if (generation !== progressiveGeneration) return;

            outgoingEl.classList.remove("active-layer", "layer-outgoing", "layer-incoming");
            outgoingEl.classList.add("standby-layer");
            outgoingEl.style.opacity = "0";

            incomingEl.classList.remove("layer-incoming", "layer-outgoing", "standby-layer");
            incomingEl.classList.add("active-layer");
            incomingEl.style.opacity = "1";

            previewViewer?.classList.remove("is-cinematic-transition", "transitioning", "is-walk-transition");
            closeMediaHotspot();
            activeLayerKey = incomingKey;
            syncLayerAccessibility(activeLayerKey);
            isTransitioning = false;
            updateAllViewerSizes();
            syncZoomButtonsState();

            scheduleProgressiveUpgrade(targetScene, generation);

            // Ne pas redémarrer automatiquement après une navigation.
            // L'utilisateur peut le réactiver avec le bouton dédié.
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
        stopAutorotate({ suppress: true });

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
        stopAutorotate({ suppress: true });

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
                stopAutorotate({ suppress: true });
                localPinch.active = true;
                localPinch.startDistance = getTouchDistance(event.touches);
                localPinch.startFov = view.fov();
                return;
            }

            if (!isInsidePreview(event.target) || shouldIgnoreZoomTarget(event.target)) return;
            stopAutorotate({ suppress: true });
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
            if ("ontouchstart" in window) return;
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
            if ("ontouchstart" in window) return;
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
            stopAutorotate({ suppress: true });
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
        stopAutorotate({ suppress: true });
        zoomBy(isMobileViewport() ? 8 : 10, 120);
    });

    bindZoomButton(zoomInBtn, () => {
        stopAutorotate({ suppress: true });
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
    previewViewer?.addEventListener("pointerdown", () => {
        stopAutorotate({ suppress: true });
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
    renderFloorNavigator();
    setupMobileZoomGestures();

    const initialScene = getInitialSceneFromUrl() || scenes[0];
    currentSceneId = initialScene.id;

    async function bootProgressivePreview() {
        cancelProgressiveWork();
        const generation = progressiveGeneration;
        const plan = getProgressiveLoadPlan(initialScene);
        const firstEntry = await getBestInitialEntry(initialScene);

        // Au premier affichage, l'intro couvre déjà le viewer.
        // Ne pas ajouter une deuxième image de chargement par-dessus le panorama,
        // sinon l'utilisateur a l'impression de voir plusieurs images superposées.
        setSceneLoadingPreview(initialScene, false);

        if (firstEntry?.url) {
            await preloadDecodedImage(firstEntry.url, { priority: "high" });
        }

        if (generation !== progressiveGeneration) return;

        buildSceneOnLayer(activeLayerKey, initialScene, {
            imageUrl: firstEntry?.url || "",
            quality: firstEntry?.quality || "preferred"
        });
        syncLayerAccessibility(activeLayerKey);
        updateSceneMeta(initialScene);
        syncSceneInUrl(initialScene);

        requestAnimationFrame(() => {
            updateAllViewerSizes();
            syncZoomButtonsState();
            runInitialReveal(initialScene);

            // Attendre la fin complète de l'introduction avant la montée en qualité.
            // Ainsi, la preview légère ne se mélange jamais avec l'animation d'ouverture.
            setTimeout(() => {
                previewViewer?.classList.remove(
                    "is-opening",
                    "is-cinematic-transition",
                    "transitioning",
                    "is-walk-transition"
                );
                setSceneLoadingPreview(initialScene, false);
                scheduleProgressiveUpgrade(initialScene, generation);
            }, 920);
        });
    }

    bootProgressivePreview();
});
