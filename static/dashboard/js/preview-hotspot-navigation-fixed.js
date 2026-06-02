/* preview-hotspot-navigation-fixed.js
 * Version complète corrigée pour preview.html
 * - Fix SyntaxError zoomToFov
 * - Hotspots Marzipano stables: aucun transform sur le parent .preview-hotspot
 * - Navigation entre scènes via target_scene_id / target_scene / payload.navigation
 * - Desktop/mobile image fallback, tiles désactivées par défaut pour éviter écran vide desktop
 * - Zoom boutons + wheel desktop + pinch mobile/iOS
 */

(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", () => {
        if (typeof Marzipano === "undefined") {
            console.error("Marzipano not loaded");
            return;
        }

        const config = window.PREVIEW_CONFIG || {};
        const scenesDataEl = document.getElementById("preview-scenes-data");
        let allScenes = scenesDataEl ? JSON.parse(scenesDataEl.textContent || "[]") : [];

        if (!Array.isArray(allScenes)) allScenes = [];
        allScenes = allScenes.slice().sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

        // Important pour ton cas: le backend envoie parfois toutes les scènes.
        // Pour le preview public et la liste, on garde uniquement les scènes publiques.
        const publicScenes = allScenes.filter((scene) => scene?.is_public !== false);
        const scenes = publicScenes.length ? publicScenes : allScenes;

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

        const previewSceneLoadingOverlay = $("previewSceneLoadingOverlay");
        const previewSceneLoadingImage = $("previewSceneLoadingImage");
        const previewSceneLoadingText = $("previewSceneLoadingText");

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

        if (!previewViewer || !previewLayerA || !previewLayerB || !previewMountA || !previewMountB) {
            console.error("Preview DOM nodes missing: previewViewer/Layer/Mount not found");
            return;
        }

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
        let sceneLoadingHideTimer = null;

        const MIN_FOV = degToRad(6);
        const MAX_FOV = degToRad(132);
        const ZERO_ZOOM_FOV = MAX_FOV;
        const NAVIGATION_ZOOM_IN_OFFSET_1 = degToRad(7);
        const NAVIGATION_ZOOM_IN_OFFSET_2 = degToRad(13);
        const SCENE_INCOMING_DEZOOM_OFFSET = degToRad(0);
        const MOBILE_PINCH_SENSITIVITY = 2.15;

        // Mets true plus tard si tes tiles desktop sont bien générées.
        // Pour corriger l'écran vide desktop rapidement, on force l'image equirectangulaire.
        const USE_DESKTOP_TILES = false;

        const assetPrefetchCache = new Set();

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

        function getLayerEl(key) {
            return key === "A" ? previewLayerA : previewLayerB;
        }

        function getMountEl(key) {
            return key === "A" ? previewMountA : previewMountB;
        }

        function standbyLayerKey() {
            return activeLayerKey === "A" ? "B" : "A";
        }

        function getSceneLookupValue(value) {
            if (value && typeof value === "object") {
                return value.id ?? value.scene_id ?? value.uuid ?? value.slug ?? null;
            }
            return value;
        }

        function getSceneIdentifier(scene) {
            return String(scene?.slug || scene?.uuid || scene?.scene_id || scene?.id || "");
        }

        function findScene(sceneId) {
            const lookup = getSceneLookupValue(sceneId);
            if (lookup === undefined || lookup === null || String(lookup).trim() === "") return null;

            return scenes.find((scene) =>
                String(scene.id) === String(lookup) ||
                String(scene.scene_id) === String(lookup) ||
                String(scene.uuid) === String(lookup) ||
                String(scene.slug) === String(lookup)
            ) || null;
        }

        function findSceneIndex(sceneId) {
            const lookup = getSceneLookupValue(sceneId);
            return scenes.findIndex((scene) =>
                String(scene.id) === String(lookup) ||
                String(scene.scene_id) === String(lookup) ||
                String(scene.uuid) === String(lookup) ||
                String(scene.slug) === String(lookup)
            );
        }

        function getInitialSceneFromUrl() {
            const url = new URL(window.location.href);
            const sceneParam = url.searchParams.get("s");
            if (!sceneParam) return null;
            return findScene(sceneParam);
        }

        function syncSceneInUrl(scene) {
            if (!scene) return;
            const url = new URL(window.location.href);
            url.searchParams.set("s", getSceneIdentifier(scene));
            window.history.replaceState({}, "", url.toString());
        }

        function getSceneShareUrl(scene) {
            const url = new URL(window.location.href);
            url.searchParams.set("s", getSceneIdentifier(scene));
            return url.toString();
        }

        function getSceneAssets(sceneData) {
            const assets = sceneData?.assets || {};
            return {
                preview: assets.preview || sceneData?.image_360_preview_url || "",
                thumbnail: assets.thumbnail || sceneData?.thumbnail_url || "",
                mobile: assets.mobile || sceneData?.image_360_mobile_url || "",
                desktop: assets.desktop || sceneData?.image_360_url || "",
                fallback: assets.fallback || sceneData?.image_360_url || sceneData?.image_360_mobile_url || sceneData?.image_360_preview_url || sceneData?.thumbnail_url || "",
                original: assets.original || sceneData?.image_360_original_url || ""
            };
        }

        function getTilesPreviewUrl(sceneData) {
            const tilesUrl = sceneData?.tiles_url || "";
            if (tilesUrl) return `${String(tilesUrl).replace(/\/$/, "")}/preview.jpg`;

            const template = sceneData?.tiles?.manifest?.urlTemplate || sceneData?.tiles_manifest?.urlTemplate || "";
            if (!template) return "";

            return String(template)
                .replace(/\{z\}/g, "0")
                .replace(/\{f\}/g, "f")
                .replace(/\{x\}/g, "0")
                .replace(/\{y\}/g, "0");
        }

        function getSceneLightImageUrl(sceneData) {
            const assets = getSceneAssets(sceneData);
            return assets.preview || assets.thumbnail || getTilesPreviewUrl(sceneData) || (isMobileViewport() ? assets.mobile : "") || assets.fallback || "";
        }

        function getPreferredImageUrl(sceneData) {
            const assets = getSceneAssets(sceneData);
            if (isMobileViewport()) {
                return assets.mobile || assets.desktop || assets.original || assets.preview || assets.thumbnail || assets.fallback || "";
            }
            return assets.desktop || assets.original || assets.mobile || assets.preview || assets.thumbnail || assets.fallback || "";
        }

        function getScenePreviewThumb(sceneData) {
            return getSceneLightImageUrl(sceneData);
        }

        function getSceneTilesData(sceneData) {
            const mobile = isMobileViewport();
            const tiles = sceneData?.tiles || {};
            const manifest = tiles.manifest || sceneData?.tiles_manifest || {};
            const legacyTilesUrl = sceneData?.tiles_url || "";
            const canUseTiles = !mobile && USE_DESKTOP_TILES;

            if (legacyTilesUrl) {
                return {
                    ready: true,
                    useTiles: canUseTiles,
                    urlTemplate: `${String(legacyTilesUrl).replace(/\/$/, "")}/{z}/{f}/{y}/{x}.jpg`,
                    previewUrl: `${String(legacyTilesUrl).replace(/\/$/, "")}/preview.jpg`,
                    levels: sceneData.levels || [
                        { tileSize: 256, size: 256, fallbackOnly: true },
                        { tileSize: 512, size: 512 },
                        { tileSize: 512, size: 1024 },
                        { tileSize: 512, size: 2048 },
                        { tileSize: 512, size: 4096 }
                    ],
                    faceSize: sceneData.face_size || 4096
                };
            }

            if ((tiles.ready || manifest.urlTemplate) && manifest.urlTemplate) {
                return {
                    ready: true,
                    useTiles: canUseTiles,
                    urlTemplate: manifest.urlTemplate,
                    previewUrl: getTilesPreviewUrl(sceneData),
                    levels: manifest.levels || [
                        { tileSize: 256, size: 256, fallbackOnly: true },
                        { tileSize: 512, size: 512 },
                        { tileSize: 512, size: 1024 },
                        { tileSize: 512, size: 2048 },
                        { tileSize: 512, size: 4096 }
                    ],
                    faceSize: manifest.faceSize || manifest.face_size || 4096
                };
            }

            return { ready: false, useTiles: false };
        }

        function getSceneSourceGeometryAndLimiter(sceneData) {
            const selectedImageUrl = getPreferredImageUrl(sceneData);
            const tilesData = getSceneTilesData(sceneData);

            const logicalMaxResolution = Math.max(
                Number(sceneData?.face_size || 0),
                Number(sceneData?.max_resolution || 0),
                Number(tilesData?.faceSize || 0),
                4096
            );

            // On utilise les tiles seulement si elles sont activées et prêtes.
            // Si USE_DESKTOP_TILES=false, desktop utilise image_360_url pour éviter l'écran noir.
            if (tilesData.ready && tilesData.useTiles) {
                return {
                    source: Marzipano.ImageUrlSource.fromString(
                        tilesData.urlTemplate,
                        { cubeMapPreviewUrl: tilesData.previewUrl || undefined }
                    ),
                    geometry: new Marzipano.CubeGeometry(tilesData.levels),
                    limiter: Marzipano.RectilinearView.limit.traditional(logicalMaxResolution, MAX_FOV)
                };
            }

            if (!selectedImageUrl && tilesData.ready) {
                return {
                    source: Marzipano.ImageUrlSource.fromString(
                        tilesData.urlTemplate,
                        { cubeMapPreviewUrl: tilesData.previewUrl || undefined }
                    ),
                    geometry: new Marzipano.CubeGeometry(tilesData.levels),
                    limiter: Marzipano.RectilinearView.limit.traditional(logicalMaxResolution, MAX_FOV)
                };
            }

            return {
                source: Marzipano.ImageUrlSource.fromString(selectedImageUrl),
                geometry: new Marzipano.EquirectGeometry([{ width: logicalMaxResolution }]),
                limiter: Marzipano.RectilinearView.limit.traditional(logicalMaxResolution, MAX_FOV)
            };
        }

        function getHotspotKind(hotspot) {
            const raw = String(
                hotspot?.type ||
                hotspot?.kind ||
                hotspot?.action ||
                hotspot?.selected_icon ||
                hotspot?.icon ||
                "default"
            ).trim().toLowerCase();

            if (["navigation", "nav", "scene", "go_to_scene", "goto", "link_scene", "navigate"].includes(raw)) {
                return "navigate";
            }

            return raw || "default";
        }

        function getTargetSceneId(hotspot) {
            const candidates = [
                hotspot?.target_scene_id,
                hotspot?.targetSceneId,
                hotspot?.target_scene,
                hotspot?.targetScene,
                hotspot?.scene_target,
                hotspot?.sceneTarget,
                hotspot?.payload?.target_scene_id,
                hotspot?.payload?.targetSceneId,
                hotspot?.payload?.target_scene,
                hotspot?.payload?.targetScene,
                hotspot?.payload?.navigation?.target_scene_id,
                hotspot?.payload?.navigation?.targetSceneId,
                hotspot?.payload?.navigation?.target_scene,
                hotspot?.payload?.navigation?.targetScene
            ];

            for (const candidate of candidates) {
                const value = getSceneLookupValue(candidate);
                if (value !== undefined && value !== null && String(value).trim() !== "") {
                    return value;
                }
            }

            return null;
        }

        function isNavigationHotspot(hotspot) {
            return getHotspotKind(hotspot) === "navigate" || !!getTargetSceneId(hotspot);
        }

        function toMarzipanoAngle(value, fallback = 0, type = "yaw") {
            const numberValue = Number(value);
            if (!Number.isFinite(numberValue)) return fallback;

            // Marzipano attend des radians. Si le backend renvoie des degrés, conversion automatique.
            if (type === "yaw" && Math.abs(numberValue) > Math.PI * 2 + 0.15) return degToRad(numberValue);
            if (type === "pitch" && Math.abs(numberValue) > Math.PI / 2 + 0.15) return degToRad(numberValue);
            return numberValue;
        }

        function getHotspotYaw(hotspot, fallback = 0) {
            return normalizeAngle(toMarzipanoAngle(hotspot?.yaw ?? hotspot?.longitude ?? hotspot?.x, fallback, "yaw"));
        }

        function getHotspotPitch(hotspot, fallback = 0) {
            return clamp(
                toMarzipanoAngle(hotspot?.pitch ?? hotspot?.latitude ?? hotspot?.y, fallback, "pitch"),
                -Math.PI / 2,
                Math.PI / 2
            );
        }

        function resolveIcon(iconName) {
            const key = String(iconName || "default").trim().toLowerCase();
            if (config.businessIconMap && config.businessIconMap[key]) return config.businessIconMap[key];
            if (config.iconMap && config.iconMap[key]) return config.iconMap[key];
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
            } catch (error) {
                console.warn("updateSize failed", error);
            }
        }

        function showToast(message) {
            if (!previewToast) return;
            previewToast.textContent = message;
            clearTimeout(toastTimer);
            previewToast.classList.add("toast-show");
            toastTimer = setTimeout(() => previewToast.classList.remove("toast-show"), 1700);
        }

        function showSceneLoadingPreview(scene, label = "Loading panorama") {
            if (!previewSceneLoadingOverlay || !previewSceneLoadingImage) return;

            const thumbUrl = getScenePreviewThumb(scene);
            if (previewSceneLoadingText) previewSceneLoadingText.textContent = label;

            if (thumbUrl) {
                previewSceneLoadingImage.src = thumbUrl;
                previewSceneLoadingImage.classList.remove("hidden");
            } else {
                previewSceneLoadingImage.removeAttribute("src");
                previewSceneLoadingImage.classList.add("hidden");
            }

            clearTimeout(sceneLoadingHideTimer);
            previewSceneLoadingOverlay.classList.add("is-visible");
        }

        function hideSceneLoadingPreview(delay = 220) {
            if (!previewSceneLoadingOverlay) return;
            clearTimeout(sceneLoadingHideTimer);
            sceneLoadingHideTimer = setTimeout(() => {
                previewSceneLoadingOverlay.classList.remove("is-visible");
            }, delay);
        }

        function prefetchUrl(url) {
            if (!url || assetPrefetchCache.has(url)) return;
            assetPrefetchCache.add(url);
            const img = new Image();
            img.decoding = "async";
            img.loading = "eager";
            img.src = url;
        }

        function prefetchSceneAssets(scene) {
            if (!scene) return;
            prefetchUrl(getSceneLightImageUrl(scene));
            prefetchUrl(getPreferredImageUrl(scene));
            if (!isMobileViewport() && USE_DESKTOP_TILES) prefetchUrl(getTilesPreviewUrl(scene));
        }

        function waitForPanoramaFirstPaint(layerKey, timeout = 900) {
            return new Promise((resolve) => {
                let done = false;
                const scene = marzipanoScenes[layerKey];

                const finish = () => {
                    if (done) return;
                    done = true;
                    resolve(true);
                };

                try {
                    if (scene && typeof scene.addEventListener === "function") {
                        scene.addEventListener("renderComplete", finish);
                    }
                } catch (_) {}

                requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(finish, timeout)));
            });
        }

        function scheduleSmartPrefetch(sceneId) {
            if (!scenes.length) return;
            const index = findSceneIndex(sceneId);
            if (index < 0) return;

            const next = scenes[(index + 1) % scenes.length];
            const previous = scenes[(index - 1 + scenes.length) % scenes.length];

            const run = () => {
                prefetchSceneAssets(next);
                prefetchSceneAssets(previous);
            };

            if ("requestIdleCallback" in window) {
                window.requestIdleCallback(run, { timeout: 1200 });
            } else {
                setTimeout(run, 350);
            }
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

        function setZoomInstant(nextFov) {
            const view = getCurrentView();
            if (!view) return;
            view.setParameters({ fov: clamp(nextFov, MIN_FOV, MAX_FOV) });
            syncZoomButtonsState();
        }

        function zoomToFov(nextFov, duration = 220) {
            const view = getCurrentView();
            if (!view) return;
            view.setParameters({ fov: clamp(nextFov, MIN_FOV, MAX_FOV) }, { transitionDuration: duration });
            syncZoomButtonsState();
        }

        function zoomBy(deltaDeg, duration = 120) {
            const view = getCurrentView();
            if (!view) return;
            zoomToFov(view.fov() + degToRad(deltaDeg), duration);
        }

        function setupResponsiveMode() {
            if (!window.matchMedia) return;
            const mql = window.matchMedia("(max-width: 768px), (max-height: 700px)");

            const applyMode = () => {
                document.body.classList.toggle("mobile", mql.matches);
                document.body.classList.toggle("desktop", !mql.matches);
            };

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

            const content = hotspot?.payload?.content || {};
            const imageUrl = content.image_url || content.product_image_url || content.photo_url || hotspot?.image_url || hotspot?.ad_image_url || "";
            const ctaUrl = content.cta_url || hotspot?.cta_url || "";
            const buttonText = content.button_text || "Open";
            const badge = content.badge || "";
            const price = content.price || "";
            const siteName = content.site_name || "";
            const phone = content.phone || "";
            const email = content.email || "";
            const whatsappNumber = content.whatsapp_number || "";
            const whatsappMessage = content.whatsapp_message || "Hello";
            const hotspotKind = getHotspotKind(hotspot);

            previewInfoPanel.classList.remove("is-product", "is-info", "is-ad", "is-cta", "is-cart", "is-whatsapp", "is-phone", "is-website");
            previewInfoPanel.classList.add(`is-${hotspotKind}`);
            previewInfoPanel.dataset.hotspotKind = hotspotKind;

            if (previewInfoMedia) {
                previewInfoMedia.innerHTML = "";
                if (imageUrl) {
                    const img = document.createElement("img");
                    img.src = imageUrl;
                    img.alt = hotspot?.title || hotspot?.label || "Hotspot";
                    img.className = "info-media-image";
                    img.loading = "lazy";
                    img.decoding = "async";
                    img.onerror = () => {
                        previewInfoMedia.innerHTML = `<div class="info-media-empty">Image unavailable</div>`;
                    };
                    previewInfoMedia.appendChild(img);
                } else {
                    previewInfoMedia.innerHTML = `<div class="info-media-empty">Preview unavailable</div>`;
                }
            }

            if (previewInfoTitle) previewInfoTitle.textContent = hotspot?.title || hotspot?.label || "Hotspot";
            if (previewInfoDescription) previewInfoDescription.textContent = hotspot?.description || hotspot?.tooltip_text || content.description || "";

            toggleTextEl(previewInfoBadge, badge);
            toggleTextEl(previewInfoPrice, price);
            toggleTextEl(previewInfoSite, siteName);

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

            closeSceneStack();
            previewInfoPanel.classList.add("open");
            previewInfoBackdrop?.classList.add("open");
            document.body.classList.add("info-panel-open");
        }

        function toggleTextEl(el, value) {
            if (!el) return;
            if (value) {
                el.textContent = value;
                el.classList.remove("hidden");
            } else {
                el.textContent = "";
                el.classList.add("hidden");
            }
        }

        function stopAutorotate() {
            autorotateEnabled = false;
            autorotateLastTs = 0;
            if (autorotateFrame) cancelAnimationFrame(autorotateFrame);
            autorotateFrame = null;
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
                view.setParameters({ yaw: normalizeAngle(view.yaw() + degToRad(8) * delta) });
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

            const currentIndex = Math.max(findSceneIndex(currentSceneId), 0);
            const miniScenes = [
                scenes[currentIndex],
                scenes[(currentIndex + 1) % scenes.length],
                scenes[(currentIndex + 2) % scenes.length]
            ].filter(Boolean);

            miniScenes.slice(0, 3).forEach((scene) => {
                const card = document.createElement("div");
                card.className = "scene-stack-mini-card";
                const thumbUrl = getScenePreviewThumb(scene);
                card.innerHTML = thumbUrl
                    ? `<img src="${escapeAttr(thumbUrl)}" alt="${escapeAttr(scene.title || "Scene")}">`
                    : `<div class="scene-thumb-placeholder">360</div>`;
                sceneStackMiniPreview.appendChild(card);
            });
        }

        function renderSceneRail() {
            if (!previewScenesList) return;
            previewScenesList.innerHTML = "";

            scenes.forEach((scene, index) => {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "scene-card";
                button.dataset.sceneId = String(scene.id);

                const thumbUrl = getScenePreviewThumb(scene);
                button.innerHTML = `
                    <div class="scene-thumb">
                        ${thumbUrl ? `<img src="${escapeAttr(thumbUrl)}" alt="${escapeAttr(scene.title || "Scene")}">` : `<div class="scene-thumb-placeholder">360</div>`}
                    </div>
                    <div class="scene-body">
                        <strong class="scene-title">${escapeHtml(scene.title || "Untitled Scene")}</strong>
                        <span class="scene-subtitle"><span class="scene-dot"></span>Scene ${index + 1}</span>
                    </div>
                `;

                button.addEventListener("click", (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    if (isTransitioning) return;

                    const targetScene = findScene(scene.id);
                    if (!targetScene || String(targetScene.id) === String(currentSceneId)) {
                        closeSceneStack();
                        return;
                    }

                    closeInfoPanel();
                    closeSceneStack();
                    stopAutorotate();
                    isTransitioning = true;
                    cinematicSwitchScene(targetScene);
                }, { passive: false });

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
            const index = findSceneIndex(scene?.id);
            if (sceneCountBadge && index >= 0) sceneCountBadge.textContent = `${index + 1}`;
            markActiveSceneCard(scene?.id);
        }

        function stopTouchAndScrollEventPropagation(element) {
            if (!element) return;
            ["touchstart", "touchmove", "touchend", "touchcancel", "pointerdown", "pointermove", "pointerup", "pointercancel", "wheel"].forEach((eventName) => {
                element.addEventListener(eventName, (event) => event.stopPropagation(), { passive: true });
            });
        }

        function buildHotspotNode(hotspot, hotspotIndex = 0) {
            const payload = hotspot?.payload || {};
            const display = payload.display || {};
            const hotspotKind = getHotspotKind(hotspot);
            const isNav = isNavigationHotspot(hotspot);

            const rawVariant = display.variant || hotspot?.variant || "pin";
            const variant = isNav ? "pin" : rawVariant;
            const anchor = display.anchor || "bottom";
            const isMobile = isMobileViewport();

            const defaultSize = isNav ? 54 : hotspotKind === "product" ? 66 : hotspotKind === "info" ? 60 : 58;
            const rawSize = Number(display.size || hotspot?.size || defaultSize);
            const size = clamp(rawSize, 36, isMobile ? 66 : 92);
            const rotation = Number(display.rotation || hotspot?.rotation || 0);
            const offsetX = Number(display.offset_x ?? display.offsetX ?? hotspot?.offset_x ?? hotspot?.offsetX ?? 0);
            const offsetY = Number(display.offset_y ?? display.offsetY ?? hotspot?.offset_y ?? hotspot?.offsetY ?? 0);

            const node = document.createElement("button");
            node.type = "button";
            node.className = `preview-hotspot variant-${variant} anchor-${anchor} hotspot-kind-${hotspotKind}`;
            node.dataset.hotspotType = hotspotKind;
            node.dataset.hotspotKind = hotspotKind;

            const targetSceneId = getTargetSceneId(hotspot);
            if (targetSceneId) node.dataset.targetSceneId = String(targetSceneId);

            node.style.width = `${size}px`;
            node.style.height = `${size}px`;
            node.style.minWidth = `${size}px`;
            node.style.minHeight = `${size}px`;

            // CRITIQUE: ne jamais faire node.style.transform ici.
            // Marzipano injecte transform inline sur ce parent pour positionner yaw/pitch.
            node.style.setProperty("--hotspot-grow-delay", `${Math.min(hotspotIndex * 70, 420)}ms`);

            const wrap = document.createElement("span");
            wrap.className = "hotspot-grow-wrap";
            wrap.style.setProperty("--hotspot-base-transform", `translate(${offsetX}px, ${offsetY}px) rotate(${rotation}deg)`);
            wrap.style.transform = "var(--hotspot-base-transform)";

            const img = document.createElement("img");
            img.src = resolveIcon(hotspot?.selected_icon || hotspot?.icon || hotspotKind || hotspot?.type || "default");
            img.alt = hotspot?.label || hotspot?.title || (isNav ? "Open scene" : "Hotspot");
            img.loading = "lazy";
            img.decoding = "async";
            img.draggable = false;
            img.onerror = () => {
                const fallback = resolveIcon("default");
                if (fallback && img.src !== fallback) img.src = fallback;
            };

            const srText = document.createElement("span");
            srText.className = "hotspot-label-text";
            srText.textContent = hotspot?.label || hotspot?.title || (isNav ? "Open scene" : "Hotspot");

            wrap.appendChild(img);
            wrap.appendChild(srText);
            node.appendChild(wrap);
            node.setAttribute("aria-label", srText.textContent);

            let lastActivateTs = 0;
            let pointerDownAt = null;

            async function activateHotspot(event) {
                event.preventDefault();
                event.stopPropagation();

                const nowTs = Date.now();
                if (nowTs - lastActivateTs < 280) return;
                lastActivateTs = nowTs;

                if (isTransitioning) return;

                const finalTargetSceneId = getTargetSceneId(hotspot);
                if (isNavigationHotspot(hotspot) && finalTargetSceneId) {
                    await navigateToScene(finalTargetSceneId, hotspot);
                    return;
                }

                openInfoPanel(hotspot);
            }

            node.addEventListener("pointerdown", (event) => {
                pointerDownAt = { x: event.clientX, y: event.clientY, t: Date.now() };
            }, { passive: true });

            node.addEventListener("pointerup", (event) => {
                if (event.pointerType === "mouse" && event.button !== 0) return;

                if (pointerDownAt) {
                    const dx = Math.abs(event.clientX - pointerDownAt.x);
                    const dy = Math.abs(event.clientY - pointerDownAt.y);
                    if (dx > 12 || dy > 12) return;
                }

                activateHotspot(event);
            }, { passive: false });

            node.addEventListener("click", activateHotspot, { passive: false });
            node.addEventListener("keydown", (event) => {
                if (event.key === "Enter" || event.key === " ") activateHotspot(event);
            }, { passive: false });

            stopTouchAndScrollEventPropagation(node);
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
                console.error("VIEWER_CREATE_FAILED", error);
                showToast("Viewer unavailable");
                return null;
            }

            return viewers[key];
        }

        function buildSceneOnLayer(layerKey, sceneData) {
            const viewer = ensureViewer(layerKey);
            const selectedImageUrl = getPreferredImageUrl(sceneData);
            const tilesData = getSceneTilesData(sceneData);

            if (!viewer || (!selectedImageUrl && !tilesData.ready)) {
                console.warn("buildSceneOnLayer skipped", {
                    layerKey,
                    sceneId: sceneData?.id,
                    selectedImageUrl,
                    tilesReady: !!tilesData.ready
                });
                showToast("Panorama unavailable");
                return null;
            }

            const { source, geometry, limiter } = getSceneSourceGeometryAndLimiter(sceneData);
            const yaw = degToRad(sceneData?.yaw_default || 0);
            const pitch = degToRad(sceneData?.pitch_default || 0);
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
                console.error("CREATE_SCENE_FAILED", {
                    layerKey,
                    sceneId: sceneData?.id,
                    error
                });
                showToast("Scene unavailable");
                return null;
            }

            (sceneData?.hotspots || []).forEach((hotspot, hotspotIndex) => {
                const node = buildHotspotNode(hotspot, hotspotIndex);
                const hotspotYaw = getHotspotYaw(hotspot, 0);
                const hotspotPitch = getHotspotPitch(hotspot, 0);

                try {
                    marzipanoScenes[layerKey].hotspotContainer().createHotspot(node, {
                        yaw: hotspotYaw,
                        pitch: hotspotPitch
                    });
                } catch (error) {
                    console.warn("HOTSPOT_CREATE_FAILED", { hotspot, error });
                }
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

            previewViewer.classList.add("is-opening");
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
                previewViewer.classList.remove("is-cinematic-transition", "transitioning", "is-opening");
                syncZoomButtonsState();
            }, 620);
        }

        function cinematicSwitchScene(targetScene, options = {}) {
            if (!targetScene) {
                isTransitioning = false;
                return;
            }

            showSceneLoadingPreview(targetScene, "Loading panorama");

            const outgoingKey = activeLayerKey;
            const incomingKey = standbyLayerKey();
            const outgoingEl = getLayerEl(outgoingKey);
            const incomingEl = getLayerEl(incomingKey);

            const builtScene = buildSceneOnLayer(incomingKey, targetScene);
            if (!builtScene) {
                isTransitioning = false;
                hideSceneLoadingPreview(120);
                return;
            }

            waitForPanoramaFirstPaint(incomingKey, isMobileViewport() ? 760 : 520)
                .then(() => hideSceneLoadingPreview(isMobileViewport() ? 110 : 80));

            const incomingView = views[incomingKey];
            const startYaw = options.fromYaw !== undefined ? options.fromYaw : degToRad(targetScene.yaw_default || 0);
            const startPitch = options.fromPitch !== undefined ? options.fromPitch : degToRad(targetScene.pitch_default || 0);
            const endYaw = degToRad(targetScene.yaw_default || 0);
            const endPitch = degToRad(targetScene.pitch_default || 0);
            const finalFov = getSceneFinalFov(targetScene);
            const incomingStartFov = clamp(finalFov - SCENE_INCOMING_DEZOOM_OFFSET, MIN_FOV, MAX_FOV);

            if (incomingView) {
                incomingView.setParameters({ yaw: startYaw, pitch: startPitch, fov: incomingStartFov });
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
                    incomingView.setParameters({ yaw: endYaw, pitch: endPitch, fov: finalFov }, { transitionDuration: 650 });
                }
            }, 35);

            setTimeout(() => {
                outgoingEl.classList.remove("active-layer", "layer-outgoing");
                outgoingEl.classList.add("standby-layer");
                outgoingEl.style.opacity = "0";

                incomingEl.classList.remove("layer-incoming", "standby-layer");
                incomingEl.classList.add("active-layer");
                incomingEl.style.opacity = "1";

                activeLayerKey = incomingKey;
                isTransitioning = false;
                previewViewer.classList.remove("is-cinematic-transition", "transitioning");
                updateAllViewerSizes();
                syncZoomButtonsState();
                hideSceneLoadingPreview(160);
                scheduleSmartPrefetch(targetScene.id);
            }, isMobileViewport() ? 760 : 860);
        }

        async function navigateToScene(targetSceneId, hotspot = {}) {
            if (isTransitioning) return;

            const finalTargetSceneId = getTargetSceneId(hotspot) || targetSceneId;
            const targetScene = findScene(finalTargetSceneId);
            const currentView = getCurrentView();

            if (!targetScene || !currentView) {
                console.warn("Navigation hotspot target not found", { finalTargetSceneId, hotspot });
                showToast("Scene unavailable");
                return;
            }

            if (String(targetScene.id) === String(currentSceneId)) return;

            isTransitioning = true;
            closeInfoPanel();
            closeSceneStack();
            stopAutorotate();

            const hotspotYaw = getHotspotYaw(hotspot, currentView.yaw());
            const hotspotPitch = getHotspotPitch(hotspot, currentView.pitch());
            const currentFov = currentView.fov();

            const preSwitchFov = clamp(currentFov - NAVIGATION_ZOOM_IN_OFFSET_1, MIN_FOV, MAX_FOV);
            const preSwitchFov2 = clamp(currentFov - NAVIGATION_ZOOM_IN_OFFSET_2, MIN_FOV, MAX_FOV);

            currentView.setParameters({ yaw: hotspotYaw, pitch: hotspotPitch, fov: preSwitchFov }, { transitionDuration: 150 });

            setTimeout(() => {
                currentView.setParameters({ yaw: hotspotYaw, pitch: hotspotPitch, fov: preSwitchFov2 }, { transitionDuration: 170 });
                syncZoomButtonsState();
            }, 55);

            setTimeout(() => {
                cinematicSwitchScene(targetScene, { fromYaw: hotspotYaw, fromPitch: hotspotPitch });
            }, 195);
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
            if (isTransitioning || !scenes.length) return;

            const currentIndex = findSceneIndex(currentSceneId);
            const nextIndex = currentIndex < 0 ? 0 : (currentIndex + step + scenes.length) % scenes.length;
            const targetScene = scenes[nextIndex];
            if (!targetScene) return;

            closeInfoPanel();
            closeSceneStack();
            stopAutorotate();
            isTransitioning = true;

            const currentView = getCurrentView();
            if (currentView) {
                currentView.setParameters({
                    fov: clamp(currentView.fov() - NAVIGATION_ZOOM_IN_OFFSET_1, MIN_FOV, MAX_FOV)
                }, { transitionDuration: 140 });
                syncZoomButtonsState();
                setTimeout(() => cinematicSwitchScene(targetScene), 170);
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
                    await navigator.share({ title: document.title, text: "Virtual Tour", url: shareUrl });
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
                if (previewViewer.requestFullscreen) await previewViewer.requestFullscreen();
            } catch (_) {}
        }

        function getTouchDistance(touches) {
            if (!touches || touches.length < 2) return 0;
            const dx = touches[0].clientX - touches[1].clientX;
            const dy = touches[0].clientY - touches[1].clientY;
            return Math.sqrt(dx * dx + dy * dy);
        }

        function setupMobileZoomGestures() {
            previewViewer.style.touchAction = "none";
            previewViewer.style.webkitUserSelect = "none";
            previewViewer.style.userSelect = "none";

            [previewLayerA, previewLayerB, previewMountA, previewMountB].forEach((el) => {
                if (!el) return;
                el.style.touchAction = "none";
                el.style.webkitUserSelect = "none";
                el.style.userSelect = "none";
            });

            const pinchState = { active: false, startDistance: 0, startFov: 0 };

            previewViewer.addEventListener("touchstart", (event) => {
                if (event.touches.length !== 2) return;
                const view = getCurrentView();
                if (!view) return;

                event.preventDefault();
                event.stopPropagation();
                stopAutorotate();

                pinchState.active = true;
                pinchState.startDistance = getTouchDistance(event.touches);
                pinchState.startFov = view.fov();
            }, { passive: false, capture: true });

            previewViewer.addEventListener("touchmove", (event) => {
                if (!pinchState.active || event.touches.length !== 2) return;
                const view = getCurrentView();
                if (!view) return;

                event.preventDefault();
                event.stopPropagation();

                const currentDistance = getTouchDistance(event.touches);
                if (!pinchState.startDistance || !currentDistance) return;

                const ratio = currentDistance / pinchState.startDistance;
                const zoomDelta = Math.log2(ratio) * degToRad(58) * MOBILE_PINCH_SENSITIVITY;
                setZoomInstant(pinchState.startFov - zoomDelta);
            }, { passive: false, capture: true });

            function endTouch() {
                pinchState.active = false;
                pinchState.startDistance = 0;
                pinchState.startFov = 0;
                syncZoomButtonsState();
            }

            previewViewer.addEventListener("touchend", endTouch, { passive: false, capture: true });
            previewViewer.addEventListener("touchcancel", endTouch, { passive: false, capture: true });

            // Pointer Events fallback.
            const activePointers = new Map();
            const pointerPinch = { active: false, startDistance: 0, startFov: 0 };

            function getPointerDistance() {
                const values = Array.from(activePointers.values());
                if (values.length < 2) return 0;
                const dx = values[0].clientX - values[1].clientX;
                const dy = values[0].clientY - values[1].clientY;
                return Math.sqrt(dx * dx + dy * dy);
            }

            previewViewer.addEventListener("pointerdown", (event) => {
                if (event.pointerType !== "touch") return;
                activePointers.set(event.pointerId, event);

                if (activePointers.size === 2) {
                    const view = getCurrentView();
                    if (!view) return;
                    event.preventDefault();
                    stopAutorotate();
                    pointerPinch.active = true;
                    pointerPinch.startDistance = getPointerDistance();
                    pointerPinch.startFov = view.fov();
                }
            }, { passive: false, capture: true });

            previewViewer.addEventListener("pointermove", (event) => {
                if (event.pointerType !== "touch") return;
                if (!activePointers.has(event.pointerId)) return;
                activePointers.set(event.pointerId, event);
                if (!pointerPinch.active || activePointers.size < 2) return;

                const view = getCurrentView();
                if (!view) return;

                event.preventDefault();
                event.stopPropagation();

                const currentDistance = getPointerDistance();
                if (!pointerPinch.startDistance || !currentDistance) return;

                const ratio = currentDistance / pointerPinch.startDistance;
                const zoomDelta = Math.log2(ratio) * degToRad(58) * MOBILE_PINCH_SENSITIVITY;
                setZoomInstant(pointerPinch.startFov - zoomDelta);
            }, { passive: false, capture: true });

            function endPointer(event) {
                if (event.pointerType !== "touch") return;
                activePointers.delete(event.pointerId);
                if (activePointers.size < 2) {
                    pointerPinch.active = false;
                    pointerPinch.startDistance = 0;
                    pointerPinch.startFov = 0;
                }
                syncZoomButtonsState();
            }

            previewViewer.addEventListener("pointerup", endPointer, { passive: false, capture: true });
            previewViewer.addEventListener("pointercancel", endPointer, { passive: false, capture: true });
            previewViewer.addEventListener("pointerleave", endPointer, { passive: false, capture: true });

            // iOS Safari gesture events.
            let gestureStartFov = 0;

            previewViewer.addEventListener("gesturestart", (event) => {
                const view = getCurrentView();
                if (!view) return;
                event.preventDefault();
                event.stopPropagation();
                stopAutorotate();
                gestureStartFov = view.fov();
            }, { passive: false, capture: true });

            previewViewer.addEventListener("gesturechange", (event) => {
                const view = getCurrentView();
                if (!view || !gestureStartFov) return;
                event.preventDefault();
                event.stopPropagation();
                const scale = event.scale || 1;
                const zoomDelta = Math.log2(scale) * degToRad(60) * MOBILE_PINCH_SENSITIVITY;
                setZoomInstant(gestureStartFov - zoomDelta);
            }, { passive: false, capture: true });

            previewViewer.addEventListener("gestureend", (event) => {
                event.preventDefault();
                gestureStartFov = 0;
                syncZoomButtonsState();
            }, { passive: false, capture: true });

            // Desktop / trackpad zoom.
            previewViewer.addEventListener("wheel", (event) => {
                const target = event.target;
                if (target?.closest?.("#previewControlDock") || target?.closest?.("#previewInfoPanel") || target?.closest?.("#previewSceneRail")) return;

                const view = getCurrentView();
                if (!view) return;

                event.preventDefault();
                stopAutorotate();

                const direction = event.deltaY > 0 ? 1 : -1;
                setZoomInstant(view.fov() + degToRad(direction * 7));
            }, { passive: false, capture: true });
        }

        function escapeHtml(value) {
            return String(value ?? "")
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        function escapeAttr(value) {
            return escapeHtml(value);
        }

        function bindZoomButton(button, handler) {
            if (!button) return;
            button.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                handler();
            }, { passive: false });
        }

        // =========================
        // Events
        // =========================
        sceneStackToggle?.addEventListener("click", toggleSceneStack);
        prevSceneBtn?.addEventListener("click", () => goToRelativeScene(-1));
        nextSceneBtn?.addEventListener("click", () => goToRelativeScene(1));

        bindZoomButton(zoomOutBtn, () => {
            stopAutorotate();
            zoomBy(isMobileViewport() ? 8 : 10);
        });

        bindZoomButton(zoomInBtn, () => {
            stopAutorotate();
            zoomBy(isMobileViewport() ? -8 : -10);
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

        previewViewer.addEventListener("click", () => closeInfoPanel());
        previewViewer.addEventListener("pointerdown", () => stopAutorotate());

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
                closeInfoPanel();
                closeSceneStack();
            }
            if (event.key === "ArrowLeft") goToRelativeScene(-1);
            if (event.key === "ArrowRight") goToRelativeScene(1);
            if (event.key === "+" || event.key === "=") zoomBy(-8);
            if (event.key === "-") zoomBy(8);
        });

        // =========================
        // Init
        // =========================
        setupResponsiveMode();

        if (!scenes.length) {
            if (sceneCountBadge) sceneCountBadge.textContent = "0";
            console.warn("No public scenes available for preview");
            return;
        }

        renderSceneRail();
        setupMobileZoomGestures();

        const initialScene = getInitialSceneFromUrl() || scenes[0];
        currentSceneId = initialScene.id;

        showSceneLoadingPreview(initialScene, "Loading first panorama");
        prefetchSceneAssets(initialScene);

        const initialBuilt = buildSceneOnLayer(activeLayerKey, initialScene);
        updateSceneMeta(initialScene);
        syncSceneInUrl(initialScene);
        scheduleSmartPrefetch(initialScene.id);

        if (!initialBuilt) {
            hideSceneLoadingPreview(200);
            return;
        }

        requestAnimationFrame(() => {
            updateAllViewerSizes();
            syncZoomButtonsState();
            runInitialReveal(initialScene);
        });

        waitForPanoramaFirstPaint(activeLayerKey, isMobileViewport() ? 1250 : 850)
            .then(() => hideSceneLoadingPreview(isMobileViewport() ? 180 : 120));
    });
})();
