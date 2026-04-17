document.addEventListener("DOMContentLoaded", () => {
    if (typeof Marzipano === "undefined") {
        debugLog("Marzipano not loaded");
        showDebugDialog("MARZIPANO_NOT_LOADED", "Le script Marzipano n'a pas été chargé sur cet appareil.");
        return;
    }

    const config = window.PREVIEW_CONFIG || {};
    const scenesDataEl = document.getElementById("preview-scenes-data");
    let scenes = scenesDataEl ? JSON.parse(scenesDataEl.textContent) : [];

    if (!Array.isArray(scenes)) scenes = [];

    scenes = scenes.slice().sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

    const DEBUG_PREVIEW = /Android|iPhone|iPad|Mobile/i.test(navigator.userAgent) || window.location.search.includes("debug=1");
    let debugBox = null;

    function ensureDebugBox() {
        if (!DEBUG_PREVIEW || debugBox) return debugBox;

        debugBox = document.createElement("pre");
        debugBox.id = "previewMobileDebug";
        debugBox.style.position = "fixed";
        debugBox.style.left = "10px";
        debugBox.style.right = "10px";
        debugBox.style.bottom = "10px";
        debugBox.style.zIndex = "999999";
        debugBox.style.maxHeight = "38vh";
        debugBox.style.overflow = "auto";
        debugBox.style.padding = "10px";
        debugBox.style.margin = "0";
        debugBox.style.borderRadius = "12px";
        debugBox.style.background = "rgba(0,0,0,0.86)";
        debugBox.style.color = "#4ade80";
        debugBox.style.font = "12px/1.4 monospace";
        debugBox.style.whiteSpace = "pre-wrap";
        debugBox.style.wordBreak = "break-word";
        debugBox.style.boxShadow = "0 8px 30px rgba(0,0,0,0.35)";
        debugBox.style.pointerEvents = "none";
        debugBox.textContent = "PREVIEW DEBUG\n";
        document.body.appendChild(debugBox);
        return debugBox;
    }

    function debugLog(...parts) {
        const line = parts.map((part) => {
            if (typeof part === "string") return part;
            try {
                return JSON.stringify(part);
            } catch (_) {
                return String(part);
            }
        }).join(" ");

        console.log("[PREVIEW DEBUG]", ...parts);

        if (DEBUG_PREVIEW) {
            const box = ensureDebugBox();
            if (box) {
                box.textContent += line + "\n";
                box.scrollTop = box.scrollHeight;
            }
        }
    }

    let debugDialogEl = null;
    let debugDialogBodyEl = null;

    function ensureDebugDialog() {
        if (debugDialogEl) return debugDialogEl;

        debugDialogEl = document.createElement("div");
        debugDialogEl.id = "previewDebugDialog";
        debugDialogEl.style.position = "fixed";
        debugDialogEl.style.inset = "0";
        debugDialogEl.style.zIndex = "1000000";
        debugDialogEl.style.display = "none";
        debugDialogEl.style.alignItems = "center";
        debugDialogEl.style.justifyContent = "center";
        debugDialogEl.style.padding = "18px";
        debugDialogEl.style.background = "rgba(0,0,0,0.72)";

        const card = document.createElement("div");
        card.style.width = "100%";
        card.style.maxWidth = "680px";
        card.style.maxHeight = "82vh";
        card.style.overflow = "hidden";
        card.style.borderRadius = "16px";
        card.style.background = "#08111f";
        card.style.color = "#e2e8f0";
        card.style.boxShadow = "0 20px 60px rgba(0,0,0,0.45)";
        card.style.display = "flex";
        card.style.flexDirection = "column";
        card.style.border = "1px solid rgba(255,255,255,0.08)";

        const header = document.createElement("div");
        header.style.display = "flex";
        header.style.alignItems = "center";
        header.style.justifyContent = "space-between";
        header.style.gap = "12px";
        header.style.padding = "14px 16px";
        header.style.borderBottom = "1px solid rgba(255,255,255,0.08)";
        header.innerHTML = '<strong style="font:600 15px system-ui;">Preview debug</strong>';

        const actions = document.createElement("div");
        actions.style.display = "flex";
        actions.style.gap = "8px";

        const copyBtn = document.createElement("button");
        copyBtn.type = "button";
        copyBtn.textContent = "Copy";
        copyBtn.style.padding = "8px 12px";
        copyBtn.style.borderRadius = "10px";
        copyBtn.style.border = "0";
        copyBtn.style.background = "#16a34a";
        copyBtn.style.color = "#fff";
        copyBtn.style.fontWeight = "600";
        copyBtn.addEventListener("click", async () => {
            try {
                await navigator.clipboard.writeText(debugDialogBodyEl?.textContent || "");
                copyBtn.textContent = "Copied";
                setTimeout(() => copyBtn.textContent = "Copy", 1200);
            } catch (_) {
                copyBtn.textContent = "Failed";
                setTimeout(() => copyBtn.textContent = "Copy", 1200);
            }
        });

        const closeBtn = document.createElement("button");
        closeBtn.type = "button";
        closeBtn.textContent = "Close";
        closeBtn.style.padding = "8px 12px";
        closeBtn.style.borderRadius = "10px";
        closeBtn.style.border = "0";
        closeBtn.style.background = "#334155";
        closeBtn.style.color = "#fff";
        closeBtn.style.fontWeight = "600";
        closeBtn.addEventListener("click", () => {
            debugDialogEl.style.display = "none";
        });

        actions.appendChild(copyBtn);
        actions.appendChild(closeBtn);
        header.appendChild(actions);

        debugDialogBodyEl = document.createElement("pre");
        debugDialogBodyEl.style.margin = "0";
        debugDialogBodyEl.style.padding = "16px";
        debugDialogBodyEl.style.overflow = "auto";
        debugDialogBodyEl.style.whiteSpace = "pre-wrap";
        debugDialogBodyEl.style.wordBreak = "break-word";
        debugDialogBodyEl.style.font = "12px/1.45 monospace";
        debugDialogBodyEl.style.color = "#86efac";

        card.appendChild(header);
        card.appendChild(debugDialogBodyEl);
        debugDialogEl.appendChild(card);
        document.body.appendChild(debugDialogEl);

        return debugDialogEl;
    }

    function showDebugDialog(title, payload) {
        const dialog = ensureDebugDialog();
        if (!dialog || !debugDialogBodyEl) return;

        const content = [
            title,
            "",
            typeof payload === "string"
                ? payload
                : JSON.stringify(payload, null, 2)
        ].join("\n");

        debugDialogBodyEl.textContent = content;
        dialog.style.display = "flex";
    }

    function getPreferredImageUrl(sceneData) {
        const mobile = isMobileViewport();
        return (
            (mobile && sceneData?.image_360_mobile_url) ||
            sceneData?.image_360_url ||
            ""
        );
    }

    function testImageUrl(url, label = "image") {
        return new Promise((resolve) => {
            if (!url) {
                resolve({ ok: false, label, reason: "empty-url", url });
                return;
            }

            const img = new Image();
            const startedAt = Date.now();
            let done = false;

            const finalize = (payload) => {
                if (done) return;
                done = true;
                resolve(payload);
            };

            const timer = setTimeout(() => {
                finalize({
                    ok: false,
                    label,
                    reason: "timeout",
                    url,
                    elapsedMs: Date.now() - startedAt
                });
            }, 8000);

            img.onload = () => {
                clearTimeout(timer);
                finalize({
                    ok: true,
                    label,
                    url,
                    width: img.naturalWidth,
                    height: img.naturalHeight,
                    elapsedMs: Date.now() - startedAt
                });
            };

            img.onerror = () => {
                clearTimeout(timer);
                finalize({
                    ok: false,
                    label,
                    reason: "load-error",
                    url,
                    elapsedMs: Date.now() - startedAt
                });
            };

            img.src = url + (url.includes("?") ? "&" : "?") + "_debug=" + Date.now();
        });
    }

    window.addEventListener("error", (event) => {
        const payload = {
            message: event.message,
            file: event.filename,
            line: event.lineno,
            col: event.colno
        };
        debugLog("JS_ERROR", payload);
        showDebugDialog("JS_ERROR", payload);
    });

    window.addEventListener("unhandledrejection", (event) => {
        const payload = String(event.reason?.stack || event.reason || "unknown");
        debugLog("PROMISE_REJECTION", payload);
        showDebugDialog("PROMISE_REJECTION", payload);
    });

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

    debugLog("INIT", {
        marzipanoLoaded: typeof Marzipano !== "undefined",
        scenesCount: scenes.length,
        innerWidth: window.innerWidth,
        innerHeight: window.innerHeight,
        devicePixelRatio: window.devicePixelRatio || 1,
        userAgent: navigator.userAgent
    });

    let activeLayerKey = "A";
    let currentSceneId = null;
    let isTransitioning = false;

    let autorotateEnabled = false;
    let autorotateFrame = null;
    let autorotateLastTs = 0;

    let focusMode = false;
    let toastTimer = null;

    const MIN_FOV = degToRad(28);
    const MAX_FOV = degToRad(118);

    const EXTRA_WIDE_OFFSET = degToRad(12);
    const INITIAL_START_OFFSET = degToRad(16);
    const SCENE_SWITCH_START_OFFSET = degToRad(14);

    const MOBILE_EXTRA_WIDE_OFFSET = degToRad(4);
    const MOBILE_PINCH_SENSITIVITY = 0.0045;

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

    function findScene(sceneId) {
        return scenes.find(scene => String(scene.id) === String(sceneId));
    }

    function findSceneIndex(sceneId) {
        return scenes.findIndex(scene => String(scene.id) === String(sceneId));
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
        return clamp(degToRad(scene?.hfov_default || 100), MIN_FOV, MAX_FOV);
    }

    function getSceneFinalFov(scene) {
        const mobileBoost = isMobileViewport() ? MOBILE_EXTRA_WIDE_OFFSET : 0;
        return clamp(
            getSceneBaseFov(scene) + EXTRA_WIDE_OFFSET + mobileBoost,
            MIN_FOV,
            MAX_FOV
        );
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
        const imageUrl = content.image_url || hotspot.ad_image_url || "";
        const ctaUrl = content.cta_url || "";
        const buttonText = content.button_text || "Open";
        const badge = content.badge || "";
        const price = content.price || "";
        const siteName = content.site_name || "";
        const phone = content.phone || "";
        const email = content.email || "";
        const whatsappNumber = content.whatsapp_number || "";
        const whatsappMessage = content.whatsapp_message || "Hello";

        previewInfoMedia.innerHTML = imageUrl
            ? `<img src="${imageUrl}" alt="${hotspot.title || hotspot.label || "Hotspot"}" class="info-media-image">`
            : `<div class="info-media-empty">Preview unavailable</div>`;

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

        const currentIndex = Math.max(findSceneIndex(currentSceneId), 0);
        const miniScenes = [
            scenes[currentIndex],
            scenes[currentIndex + 1] || scenes[0],
            scenes[currentIndex + 2] || scenes[1] || scenes[0]
        ].filter(Boolean);

        miniScenes.slice(0, 3).forEach((scene) => {
            const card = document.createElement("div");
            card.className = "scene-stack-mini-card";
            card.innerHTML = scene.thumbnail_url || scene.image_360_url
                ? `<img src="${scene.thumbnail_url || scene.image_360_url}" alt="${scene.title || 'Scene'}">`
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
            button.dataset.sceneId = scene.id;

            button.innerHTML = `
                <div class="scene-thumb">
                    ${
                        scene.thumbnail_url || scene.image_360_url
                            ? `<img src="${scene.thumbnail_url || scene.image_360_url}" alt="${scene.title}">`
                            : `<div class="scene-thumb-placeholder">360</div>`
                    }
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

                const targetScene = findScene(scene.id);
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
        const index = findSceneIndex(scene?.id);

        if (sceneCountBadge && index >= 0) {
            sceneCountBadge.textContent = `${index + 1}`;
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
            debugLog("ensureViewer: missing mount", key);
            return null;
        }

        mount.innerHTML = "";

        try {
            viewers[key] = new Marzipano.Viewer(mount, {
                controls: {
                    mouseViewMode: "drag"
                }
            });
            debugLog("Viewer created", key);
        } catch (error) {
            debugLog("Viewer creation failed", key, String(error?.message || error));
            return null;
        }

        return viewers[key];
    }


    function getSceneSourceGeometryAndLimiter(sceneData) {
        const mobile = isMobileViewport();

        debugLog("Scene source select", {
            sceneId: sceneData?.id,
            title: sceneData?.title,
            mobile,
            image_360_url: sceneData?.image_360_url || "",
            image_360_mobile_url: sceneData?.image_360_mobile_url || "",
            tiles_url: sceneData?.tiles_url || ""
        });

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
                    sceneData.face_size || (mobile ? 1024 : 2048),
                    MAX_FOV
                )
            };
        }

        const textureWidth = mobile ? 1536 : 3072;
        const faceSize = mobile ? 1536 : 3072;

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
        if (!viewer || (!sceneData?.image_360_url && !sceneData?.tiles_url)) {
            debugLog("buildSceneOnLayer skipped", {
                layerKey,
                hasViewer: !!viewer,
                hasImage: !!sceneData?.image_360_url,
                hasTiles: !!sceneData?.tiles_url
            });
            return null;
        }

        const selectedImageUrl = getPreferredImageUrl(sceneData);

        debugLog("buildSceneOnLayer start", {
            layerKey,
            sceneId: sceneData?.id,
            title: sceneData?.title,
            selectedImageUrl,
            tilesUrl: sceneData?.tiles_url || "",
            hfov_default: sceneData?.hfov_default
        });

        if (!sceneData?.tiles_url) {
            testImageUrl(selectedImageUrl, `scene-${sceneData?.id || "unknown"}`).then((result) => {
                debugLog("Image probe", result);

                if (!result.ok) {
                    showDebugDialog("IMAGE_PROBE_FAILED", result);
                    return;
                }

                if (isMobileViewport() && (result.width > 5000 || result.height > 2500)) {
                    showDebugDialog("IMAGE_TOO_LARGE_FOR_MOBILE", result);
                }
            });
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
            debugLog("Scene switched", {
                layerKey,
                sceneId: sceneData?.id,
                title: sceneData?.title
            });
        } catch (error) {
            const payload = {
                layerKey,
                sceneId: sceneData?.id,
                error: String(error?.message || error)
            };
            debugLog("createScene/switchTo failed", payload);
            showDebugDialog("CREATE_SCENE_FAILED", payload);
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
        const startFov = clamp(finalFov - INITIAL_START_OFFSET, MIN_FOV, MAX_FOV);

        const finalYaw = degToRad(scene.yaw_default || 0);
        const finalPitch = degToRad(scene.pitch_default || 0);

        previewViewer.classList.add("is-cinematic-transition");

        view.setParameters({
            yaw: finalYaw,
            pitch: finalPitch,
            fov: startFov
        });

        setTimeout(() => {
            view.setParameters(
                {
                    yaw: finalYaw,
                    pitch: finalPitch,
                    fov: finalFov
                },
                { transitionDuration: 1600 }
            );
            syncZoomButtonsState();
        }, 140);

        setTimeout(() => {
            previewIntroOverlay?.classList.add("is-hidden");
            document.body.classList.add("preview-has-loaded");
        }, 650);

        setTimeout(() => {
            previewViewer.classList.remove("is-cinematic-transition");
            syncZoomButtonsState();
        }, 1850);
    }

    function cinematicSwitchScene(targetScene, options = {}) {
        if (!targetScene) {
            isTransitioning = false;
            return;
        }

        const outgoingKey = activeLayerKey;
        const incomingKey = standbyLayerKey();

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
        const introFov = clamp(finalFov - SCENE_SWITCH_START_OFFSET, MIN_FOV, MAX_FOV);

        if (incomingView) {
            incomingView.setParameters({
                yaw: startYaw,
                pitch: startPitch,
                fov: introFov
            });
        }

        outgoingEl.classList.remove("standby-layer", "layer-incoming", "layer-outgoing");
        incomingEl.classList.remove("standby-layer", "layer-incoming", "layer-outgoing");

        outgoingEl.classList.add("active-layer");
        incomingEl.classList.add("layer-incoming");
        incomingEl.style.opacity = "0";

        previewViewer.classList.add("is-cinematic-transition");

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
                    { transitionDuration: 1250 }
                );
            }
        }, 100);

        setTimeout(() => {
            outgoingEl.classList.remove("active-layer", "layer-outgoing");
            outgoingEl.classList.add("standby-layer");
            outgoingEl.style.opacity = "0";

            incomingEl.classList.remove("layer-incoming", "standby-layer");
            incomingEl.classList.add("active-layer");
            incomingEl.style.opacity = "1";

            previewViewer.classList.remove("is-cinematic-transition");
            activeLayerKey = incomingKey;
            isTransitioning = false;
            updateAllViewerSizes();
            syncZoomButtonsState();
        }, 1550);
    }

    async function navigateToScene(targetSceneId, hotspot) {
        if (isTransitioning) return;

        const targetScene = findScene(targetSceneId);
        const currentView = getCurrentView();
        if (!targetScene || !currentView) return;

        isTransitioning = true;
        closeInfoPanel();
        stopAutorotate();

        const hotspotYaw = normalizeAngle(Number(hotspot.yaw ?? currentView.yaw()));
        const hotspotPitch = Number(hotspot.pitch ?? currentView.pitch());

        const currentFov = currentView.fov();
        const preSwitchFov = clamp(currentFov + degToRad(8), MIN_FOV, MAX_FOV);
        const preSwitchFov2 = clamp(currentFov + degToRad(14), MIN_FOV, MAX_FOV);

        currentView.setParameters(
            {
                yaw: hotspotYaw,
                pitch: hotspotPitch,
                fov: preSwitchFov
            },
            { transitionDuration: 280 }
        );

        setTimeout(() => {
            currentView.setParameters(
                {
                    yaw: hotspotYaw,
                    pitch: hotspotPitch,
                    fov: preSwitchFov2
                },
                { transitionDuration: 420 }
            );
            syncZoomButtonsState();
        }, 140);

        setTimeout(() => {
            cinematicSwitchScene(targetScene, {
                fromYaw: hotspotYaw,
                fromPitch: hotspotPitch
            });
        }, 460);
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
        if (isTransitioning || !scenes.length) return;

        const currentIndex = findSceneIndex(currentSceneId);
        const nextIndex = currentIndex < 0
            ? 0
            : (currentIndex + step + scenes.length) % scenes.length;

        const targetScene = scenes[nextIndex];
        if (!targetScene) return;

        closeInfoPanel();
        isTransitioning = true;
        stopAutorotate();

        const currentView = getCurrentView();
        if (currentView) {
            const widenedFov = clamp(currentView.fov() + degToRad(12), MIN_FOV, MAX_FOV);
            currentView.setParameters(
                { fov: widenedFov },
                { transitionDuration: 260 }
            );
            syncZoomButtonsState();

            setTimeout(() => {
                cinematicSwitchScene(targetScene);
            }, 180);
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

    function setupMobileZoomGestures() {
        if (!previewViewer) return;

        previewViewer.addEventListener("touchstart", (event) => {
            if (event.touches.length === 2) {
                const view = getCurrentView();
                if (!view) return;

                stopAutorotate();
                pinchState.active = true;
                pinchState.startDistance = getTouchDistance(event.touches);
                pinchState.startFov = view.fov();
            }
        }, { passive: false });

        previewViewer.addEventListener("touchmove", (event) => {
            if (!pinchState.active || event.touches.length !== 2) return;

            const view = getCurrentView();
            if (!view) return;

            event.preventDefault();

            const currentDistance = getTouchDistance(event.touches);
            const distanceDelta = pinchState.startDistance - currentDistance;

            const nextFov = clamp(
                pinchState.startFov + distanceDelta * MOBILE_PINCH_SENSITIVITY,
                MIN_FOV,
                MAX_FOV
            );

            view.setParameters({ fov: nextFov });
            syncZoomButtonsState();
        }, { passive: false });

        previewViewer.addEventListener("touchend", (event) => {
            if (event.touches.length < 2) {
                pinchState.active = false;
            }
            syncZoomButtonsState();
        }, { passive: true });

        previewViewer.addEventListener("touchcancel", () => {
            pinchState.active = false;
            syncZoomButtonsState();
        }, { passive: true });

        ["gesturestart", "gesturechange", "gestureend"].forEach((evt) => {
            previewViewer.addEventListener(evt, (event) => {
                event.preventDefault();
            }, { passive: false });
        });
    }

    sceneStackToggle?.addEventListener("click", toggleSceneStack);

    prevSceneBtn?.addEventListener("click", () => goToRelativeScene(-1));
    nextSceneBtn?.addEventListener("click", () => goToRelativeScene(1));

    zoomOutBtn?.addEventListener("click", () => {
        stopAutorotate();
        zoomBy(8);
    });

    zoomInBtn?.addEventListener("click", () => {
        stopAutorotate();
        zoomBy(-8);
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

    if (!scenes.length) {
        if (sceneCountBadge) sceneCountBadge.textContent = "0";
        return;
    }

    renderSceneRail();
    setupMobileZoomGestures();

    const initialScene = getInitialSceneFromUrl() || scenes[0];
    currentSceneId = initialScene.id;

    debugLog("Initial scene chosen", {
        id: initialScene?.id,
        title: initialScene?.title,
        preferredImageUrl: getPreferredImageUrl(initialScene),
        tilesUrl: initialScene?.tiles_url || ""
    });

    buildSceneOnLayer(activeLayerKey, initialScene);
    updateSceneMeta(initialScene);
    syncSceneInUrl(initialScene);

    requestAnimationFrame(() => {
        updateAllViewerSizes();
        syncZoomButtonsState();
        runInitialReveal(initialScene);
    });
});
