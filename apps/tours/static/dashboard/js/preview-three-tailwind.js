
import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.164.1/build/three.module.js";

(function () {
    "use strict";

    const config = window.PREVIEW_CONFIG || {};
    const scenesDataEl = document.getElementById("preview-scenes-data");
    const scenes = scenesDataEl ? JSON.parse(scenesDataEl.textContent) : [];

    const mountA = document.getElementById("previewMountA");
    const mountB = document.getElementById("previewMountB");
    const layerB = document.getElementById("previewLayerB");
    const sceneRail = document.getElementById("previewSceneRail");
    const scenesList = document.getElementById("previewScenesList");
    const sceneStackToggle = document.getElementById("sceneStackToggle");
    const sceneStackMiniPreview = document.getElementById("sceneStackMiniPreview");
    const sceneCountBadge = document.getElementById("sceneCountBadge");

    const prevSceneBtn = document.getElementById("prevSceneBtn");
    const nextSceneBtn = document.getElementById("nextSceneBtn");
    const zoomOutBtn = document.getElementById("zoomOutBtn");
    const zoomInBtn = document.getElementById("zoomInBtn");
    const resetViewBtn = document.getElementById("resetViewBtn");
    const autorotateBtn = document.getElementById("autorotateBtn");
    const focusModeBtn = document.getElementById("focusModeBtn");
    const shareBtn = document.getElementById("shareBtn");
    const fullscreenBtn = document.getElementById("fullscreenBtn");
    const previewToast = document.getElementById("previewToast");

    const infoBackdrop = document.getElementById("previewInfoBackdrop");
    const infoPanel = document.getElementById("previewInfoPanel");
    const infoCloseBtn = document.getElementById("previewInfoClose");
    const infoMedia = document.getElementById("previewInfoMedia");
    const infoBadge = document.getElementById("previewInfoBadge");
    const infoTitle = document.getElementById("previewInfoTitle");
    const infoDescription = document.getElementById("previewInfoDescription");
    const infoPrice = document.getElementById("previewInfoPrice");
    const infoSite = document.getElementById("previewInfoSite");
    const infoAction = document.getElementById("previewInfoAction");
    const infoWhatsapp = document.getElementById("previewInfoWhatsapp");
    const infoContact = document.getElementById("previewInfoContact");
    const brandOverlay = document.getElementById("brandOverlay");
    const controlDock = document.getElementById("previewControlDock");

    const MAX_FOV = 90;
    const MIN_FOV = 40;
    const DEFAULT_FOV = 75;
    const SPHERE_RADIUS = 500;

    const viewerState = {
        renderer: null,
        scene3D: null,
        camera: null,
        sphere: null,
        texture: null,
        hotspotOverlay: null,
        hotspotEntries: [],
        animationFrame: null,
        isPointerDown: false,
        pointerStartX: 0,
        pointerStartY: 0,
        yawStart: 0,
        pitchStart: 0,
        yaw: 0,
        pitch: 0,
        fov: DEFAULT_FOV,
        autorotateEnabled: false,
        focusModeEnabled: false,
        currentSceneId: null,
        currentSceneIndex: 0,
        lastTimestamp: 0
    };

    function isMobileViewport() {
        return window.matchMedia("(max-width: 768px), (max-height: 700px)").matches;
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

    function sanitizeText(value) {
        return String(value == null ? "" : value);
    }

    function degToRad(deg) {
        return (deg || 0) * Math.PI / 180;
    }

    function radToDeg(rad) {
        return (rad || 0) * 180 / Math.PI;
    }

    function clamp(value, min, max) {
        return Math.max(min, Math.min(max, value));
    }

    function getInitialSceneFromUrl() {
        const params = new URLSearchParams(window.location.search);
        const requested = params.get("s");
        if (!requested) return scenes[0] || null;
        return scenes.find((scene) =>
            String(scene.id) === requested || String(scene.scene_id) === requested
        ) || scenes[0] || null;
    }

    function updateSceneQuery(sceneData) {
        const url = new URL(window.location.href);
        url.searchParams.set("s", String(sceneData.id || sceneData.scene_id));
        window.history.replaceState({}, "", url.toString());
    }

    function showToast(message) {
        if (!previewToast) return;
        previewToast.textContent = message;
        previewToast.classList.remove("opacity-0");
        previewToast.classList.add("opacity-100");
        clearTimeout(showToast._timer);
        showToast._timer = setTimeout(() => {
            previewToast.classList.remove("opacity-100");
            previewToast.classList.add("opacity-0");
        }, 1800);
    }

    function getCurrentScene() {
        return scenes[viewerState.currentSceneIndex] || null;
    }

    function getSceneById(targetId) {
        return scenes.find((scene) => String(scene.id) === String(targetId) || String(scene.scene_id) === String(targetId)) || null;
    }

    function getSceneFinalFov(sceneData) {
        const hfov = Number(sceneData?.hfov_default || DEFAULT_FOV);
        return clamp(hfov, MIN_FOV, MAX_FOV);
    }

    function createRenderer() {
        const renderer = new THREE.WebGLRenderer({
            antialias: false,
            alpha: true,
            powerPreference: "high-performance"
        });
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
        renderer.domElement.className = "preview-webgl-canvas";
        mountA.appendChild(renderer.domElement);
        return renderer;
    }

    function createHotspotOverlay() {
        const overlay = document.createElement("div");
        overlay.className = "preview-hotspot-overlay";
        mountA.appendChild(overlay);
        return overlay;
    }

    function createViewer() {
        if (!mountA) return;

        viewerState.renderer = createRenderer();
        viewerState.scene3D = new THREE.Scene();
        viewerState.camera = new THREE.PerspectiveCamera(
            DEFAULT_FOV,
            1,
            1,
            2000
        );
        viewerState.hotspotOverlay = createHotspotOverlay();

        if (layerB) layerB.classList.add("preview-hidden-layer");
        if (mountB) mountB.innerHTML = "";

        attachPointerControls(viewerState.renderer.domElement);
        resizeRenderer();
        startRenderLoop();
    }

    function destroyCurrentSphere() {
        if (viewerState.sphere) {
            viewerState.scene3D.remove(viewerState.sphere);
            viewerState.sphere.geometry.dispose();
            viewerState.sphere.material.dispose();
            viewerState.sphere = null;
        }
        if (viewerState.texture) {
            viewerState.texture.dispose();
            viewerState.texture = null;
        }
    }

    function vectorFromYawPitch(yaw, pitch, radius = SPHERE_RADIUS) {
        const x = radius * Math.sin(yaw) * Math.cos(pitch);
        const y = radius * Math.sin(pitch);
        const z = radius * Math.cos(yaw) * Math.cos(pitch);
        return new THREE.Vector3(x, y, z);
    }

    function attachPointerControls(element) {
        element.addEventListener("pointerdown", (event) => {
            viewerState.isPointerDown = true;
            viewerState.pointerStartX = event.clientX;
            viewerState.pointerStartY = event.clientY;
            viewerState.yawStart = viewerState.yaw;
            viewerState.pitchStart = viewerState.pitch;
            element.setPointerCapture?.(event.pointerId);
        });

        element.addEventListener("pointermove", (event) => {
            if (!viewerState.isPointerDown) return;
            const dx = event.clientX - viewerState.pointerStartX;
            const dy = event.clientY - viewerState.pointerStartY;
            const sensitivity = isMobileViewport() ? 0.0038 : 0.0032;
            viewerState.yaw = viewerState.yawStart - dx * sensitivity;
            viewerState.pitch = clamp(
                viewerState.pitchStart + dy * sensitivity,
                -Math.PI / 2 + 0.03,
                Math.PI / 2 - 0.03
            );
            viewerState.autorotateEnabled = false;
            syncAutorotateButton();
        });

        function releasePointer() {
            viewerState.isPointerDown = false;
        }

        element.addEventListener("pointerup", releasePointer);
        element.addEventListener("pointercancel", releasePointer);
        element.addEventListener("pointerleave", releasePointer);

        element.addEventListener("wheel", (event) => {
            const delta = event.deltaY > 0 ? 3 : -3;
            viewerState.fov = clamp(viewerState.fov + delta, MIN_FOV, MAX_FOV);
            syncCamera();
            syncZoomButtonsState();
        }, { passive: true });
    }

    async function loadImage(url) {
        return await new Promise((resolve, reject) => {
            const image = new Image();
            image.crossOrigin = "anonymous";
            image.onload = () => resolve(image);
            image.onerror = reject;
            image.src = url;
        });
    }

    async function createPanoramaTexture(url) {
        const image = await loadImage(url);
        const rendererMaxTexture = viewerState.renderer?.capabilities?.maxTextureSize || 2048;
        const requestedMax = isMobileViewport() ? 2048 : 4096;
        const maxSize = Math.min(rendererMaxTexture, requestedMax);

        let width = image.naturalWidth;
        let height = image.naturalHeight;

        if (Math.max(width, height) > maxSize) {
            const scale = maxSize / Math.max(width, height);
            width = Math.round(width * scale);
            height = Math.round(height * scale);
        }

        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;

        const ctx = canvas.getContext("2d", { alpha: false });
        ctx.drawImage(image, 0, 0, width, height);

        const texture = new THREE.CanvasTexture(canvas);
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.minFilter = THREE.LinearFilter;
        texture.magFilter = THREE.LinearFilter;
        texture.generateMipmaps = false;
        return texture;
    }

    async function applySceneTexture(sceneData) {
        if (!sceneData?.image_360_url) {
            throw new Error("Scene sans image_360_url");
        }

        const texture = await createPanoramaTexture(sceneData.image_360_url);
        const geometry = new THREE.SphereGeometry(SPHERE_RADIUS, 64, 40);
        geometry.scale(-1, 1, 1);

        const material = new THREE.MeshBasicMaterial({ map: texture });
        const sphere = new THREE.Mesh(geometry, material);

        destroyCurrentSphere();
        viewerState.texture = texture;
        viewerState.sphere = sphere;
        viewerState.scene3D.add(sphere);
    }

    function getSceneHotspots(sceneData) {
        return Array.isArray(sceneData?.hotspots) ? sceneData.hotspots : [];
    }

    function getHotspotIcon(hotspot) {
        const businessIconMap = config.businessIconMap || {};
        const iconMap = config.iconMap || {};
        return (
            businessIconMap[hotspot.type] ||
            businessIconMap[hotspot.selected_icon] ||
            iconMap[hotspot.selected_icon] ||
            iconMap.default ||
            ""
        );
    }

    function getHotspotVariant(hotspot) {
        if (hotspot.label || hotspot.tooltip_text) return "variant-label";
        if (["arrowdown", "tilted", "whitetilted"].includes(hotspot.selected_icon)) return "variant-floor";
        return "variant-flat";
    }

    function stopTouchAndScrollEventPropagation(element) {
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

    function openHotspotPanel(hotspot) {
        const payload = hotspot.payload || {};
        const title = hotspot.title || hotspot.label || "Hotspot";
        const description = hotspot.description || payload.description || "";

        infoTitle.textContent = title;
        infoDescription.textContent = description;

        const badgeText = hotspot.type ? hotspot.type.toUpperCase() : "INFO";
        infoBadge.textContent = badgeText;

        const price = payload.price || payload.amount || "";
        infoPrice.textContent = price;
        infoPrice.classList.toggle("hidden", !price);

        const site = payload.site || payload.site_name || "";
        infoSite.textContent = site;
        infoSite.classList.toggle("hidden", !site);

        infoMedia.innerHTML = "";
        const mediaUrl = hotspot.ad_image_url || payload.image || payload.image_url || "";
        if (mediaUrl) {
            const img = document.createElement("img");
            img.src = mediaUrl;
            img.alt = title;
            img.className = "h-full w-full object-cover";
            infoMedia.appendChild(img);
        } else {
            infoMedia.innerHTML = '<div class="flex h-full w-full items-center justify-center text-sm font-bold text-slate-300">No media</div>';
        }

        const actionUrl = payload.url || payload.link || payload.cta_url || "";
        if (actionUrl) {
            infoAction.href = actionUrl;
            infoAction.classList.remove("hidden");
        } else {
            infoAction.classList.add("hidden");
        }

        const whatsapp = payload.whatsapp || "";
        if (whatsapp) {
            infoWhatsapp.href = whatsapp.startsWith("http")
                ? whatsapp
                : `https://wa.me/${whatsapp.replace(/\D/g, "")}`;
            infoWhatsapp.classList.remove("hidden");
        } else {
            infoWhatsapp.classList.add("hidden");
        }

        const phone = payload.phone || payload.tel || "";
        if (phone) {
            infoContact.href = `tel:${phone}`;
            infoContact.classList.remove("hidden");
        } else {
            infoContact.classList.add("hidden");
        }

        infoBackdrop.classList.add("open");
        infoPanel.classList.add("open");
    }

    function closeHotspotPanel() {
        infoBackdrop.classList.remove("open");
        infoPanel.classList.remove("open");
    }

    function buildHotspotNode(hotspot) {
        const node = document.createElement("button");
        node.type = "button";
        node.className = `preview-hotspot ${getHotspotVariant(hotspot)}`;
        node.setAttribute("aria-label", hotspot.title || hotspot.label || "Hotspot");

        const icon = document.createElement("img");
        icon.src = getHotspotIcon(hotspot);
        icon.alt = hotspot.title || hotspot.label || "Hotspot";
        node.appendChild(icon);

        const label = hotspot.label || hotspot.tooltip_text || "";
        if (label) {
            const span = document.createElement("span");
            span.textContent = label;
            node.appendChild(span);
        }

        stopTouchAndScrollEventPropagation(node);

        node.addEventListener("click", () => {
            if (hotspot.target_scene) {
                const targetScene = getSceneById(hotspot.target_scene);
                if (targetScene) {
                    switchSceneById(targetScene.id);
                }
                return;
            }
            openHotspotPanel(hotspot);
        });

        return node;
    }

    function rebuildHotspots(sceneData) {
        viewerState.hotspotOverlay.innerHTML = "";
        viewerState.hotspotEntries = getSceneHotspots(sceneData).map((hotspot) => {
            const node = buildHotspotNode(hotspot);
            viewerState.hotspotOverlay.appendChild(node);
            return { hotspot, node };
        });
    }

    function updateHotspots() {
        if (!viewerState.camera || !viewerState.hotspotOverlay) return;

        const width = mountA.clientWidth;
        const height = mountA.clientHeight;

        viewerState.hotspotEntries.forEach(({ hotspot, node }) => {
            const point = vectorFromYawPitch(Number(hotspot.yaw || 0), Number(hotspot.pitch || 0), SPHERE_RADIUS);
            const projected = point.clone().project(viewerState.camera);

            const isVisible = projected.z < 1 && projected.z > -1;
            const x = (projected.x * 0.5 + 0.5) * width;
            const y = (-projected.y * 0.5 + 0.5) * height;

            if (!isVisible || x < -60 || x > width + 60 || y < -60 || y > height + 60) {
                node.style.display = "none";
                return;
            }

            node.style.display = "";
            node.style.left = `${x}px`;
            node.style.top = `${y}px`;
            node.style.opacity = projected.z > 0.99 ? "0" : "1";
        });
    }

    function syncCamera() {
        if (!viewerState.camera) return;
        viewerState.camera.fov = viewerState.fov;
        viewerState.camera.updateProjectionMatrix();

        const target = vectorFromYawPitch(viewerState.yaw, viewerState.pitch, SPHERE_RADIUS);
        viewerState.camera.lookAt(target);
    }

    function startRenderLoop() {
        function animate(timestamp) {
            viewerState.animationFrame = requestAnimationFrame(animate);

            const delta = viewerState.lastTimestamp
                ? (timestamp - viewerState.lastTimestamp) / 1000
                : 0.016;

            viewerState.lastTimestamp = timestamp;

            if (viewerState.autorotateEnabled && !viewerState.isPointerDown) {
                viewerState.yaw += delta * 0.26;
            }

            syncCamera();
            updateHotspots();
            viewerState.renderer.render(viewerState.scene3D, viewerState.camera);
        }

        animate(0);
    }

    function resizeRenderer() {
        if (!viewerState.renderer || !viewerState.camera) return;
        const width = Math.max(1, mountA.clientWidth);
        const height = Math.max(1, mountA.clientHeight);
        viewerState.renderer.setSize(width, height, false);
        viewerState.camera.aspect = width / height;
        viewerState.camera.updateProjectionMatrix();
    }

    async function switchScene(sceneData) {
        if (!sceneData) return;

        try {
            mountA.classList.add("opacity-80");
            await applySceneTexture(sceneData);

            viewerState.currentSceneId = sceneData.id;
            viewerState.currentSceneIndex = scenes.findIndex((scene) => scene.id === sceneData.id);

            viewerState.yaw = degToRad(sceneData.yaw_default || 0);
            viewerState.pitch = degToRad(sceneData.pitch_default || 0);
            viewerState.fov = getSceneFinalFov(sceneData);

            rebuildHotspots(sceneData);
            updateSceneRail(sceneData);
            updateSceneQuery(sceneData);
            closeHotspotPanel();
            syncZoomButtonsState();
        } catch (error) {
            console.error(error);
            showToast("Scene loading failed");
        } finally {
            mountA.classList.remove("opacity-80");
        }
    }

    function switchSceneById(sceneId) {
        const sceneData = getSceneById(sceneId);
        if (sceneData) {
            switchScene(sceneData);
        }
    }

    function updateSceneRail(currentScene) {
        if (sceneCountBadge) {
            sceneCountBadge.textContent = String(scenes.length);
        }

        if (sceneStackMiniPreview) {
            sceneStackMiniPreview.style.backgroundImage = currentScene?.thumbnail_url
                ? `url('${currentScene.thumbnail_url}')`
                : "none";
            sceneStackMiniPreview.style.backgroundSize = "cover";
            sceneStackMiniPreview.style.backgroundPosition = "center";
        }

        const cards = scenesList.querySelectorAll(".scene-card");
        cards.forEach((card) => {
            const active = String(card.dataset.sceneId) === String(currentScene.id);
            card.classList.toggle("active", active);
        });
    }

    function renderSceneRail() {
        if (!scenesList) return;

        scenesList.innerHTML = "";

        scenes.forEach((sceneData, index) => {
            const card = document.createElement("button");
            card.type = "button";
            card.className = "scene-card";
            card.dataset.sceneId = sceneData.id;
            card.style.setProperty("--stagger", String(index));

            const thumb = sceneData.thumbnail_url
                ? `<div class="scene-card-thumb"><img src="${sceneData.thumbnail_url}" alt="${sanitizeText(sceneData.title)}" class="h-full w-full object-cover rounded-[18px]"></div>`
                : `<div class="scene-card-thumb flex h-full items-center justify-center rounded-[18px] bg-white/5 text-sm font-bold text-white/80">360</div>`;

            card.innerHTML = `
                ${thumb}
                <div class="min-w-0">
                    <div class="text-sm font-black text-white truncate">${sanitizeText(sceneData.title || "Scene")}</div>
                    <div class="mt-2 text-xs text-slate-300">Scene ${index + 1}</div>
                </div>
            `;

            card.addEventListener("click", () => {
                switchScene(sceneData);
                sceneRail.classList.remove("open");
            });

            scenesList.appendChild(card);
        });
    }

    function syncZoomButtonsState() {
        if (zoomInBtn) zoomInBtn.disabled = viewerState.fov <= MIN_FOV + 0.5;
        if (zoomOutBtn) zoomOutBtn.disabled = viewerState.fov >= MAX_FOV - 0.5;
    }

    function syncAutorotateButton() {
        autorotateBtn?.classList.toggle("active", viewerState.autorotateEnabled);
    }

    function toggleFocusMode() {
        viewerState.focusModeEnabled = !viewerState.focusModeEnabled;

        [brandOverlay, controlDock].forEach((el) => {
            if (!el) return;
            el.style.opacity = viewerState.focusModeEnabled ? "0" : "1";
            el.style.pointerEvents = viewerState.focusModeEnabled ? "none" : "";
        });

        focusModeBtn?.classList.toggle("active", viewerState.focusModeEnabled);
    }

    function bindEvents() {
        sceneStackToggle?.addEventListener("click", () => {
            sceneRail.classList.toggle("open");
        });

        prevSceneBtn?.addEventListener("click", () => {
            viewerState.currentSceneIndex = (viewerState.currentSceneIndex - 1 + scenes.length) % scenes.length;
            switchScene(scenes[viewerState.currentSceneIndex]);
        });

        nextSceneBtn?.addEventListener("click", () => {
            viewerState.currentSceneIndex = (viewerState.currentSceneIndex + 1) % scenes.length;
            switchScene(scenes[viewerState.currentSceneIndex]);
        });

        zoomInBtn?.addEventListener("click", () => {
            viewerState.fov = clamp(viewerState.fov - 6, MIN_FOV, MAX_FOV);
            syncCamera();
            syncZoomButtonsState();
        });

        zoomOutBtn?.addEventListener("click", () => {
            viewerState.fov = clamp(viewerState.fov + 6, MIN_FOV, MAX_FOV);
            syncCamera();
            syncZoomButtonsState();
        });

        resetViewBtn?.addEventListener("click", () => {
            const sceneData = getCurrentScene();
            viewerState.yaw = degToRad(sceneData?.yaw_default || 0);
            viewerState.pitch = degToRad(sceneData?.pitch_default || 0);
            viewerState.fov = getSceneFinalFov(sceneData);
            syncCamera();
            syncZoomButtonsState();
        });

        autorotateBtn?.addEventListener("click", () => {
            viewerState.autorotateEnabled = !viewerState.autorotateEnabled;
            syncAutorotateButton();
        });

        focusModeBtn?.addEventListener("click", toggleFocusMode);

        shareBtn?.addEventListener("click", async () => {
            try {
                if (navigator.share) {
                    await navigator.share({
                        title: document.title,
                        url: window.location.href
                    });
                } else if (navigator.clipboard) {
                    await navigator.clipboard.writeText(window.location.href);
                    showToast("Link copied");
                }
            } catch (_) {
                showToast("Share cancelled");
            }
        });

        fullscreenBtn?.addEventListener("click", async () => {
            try {
                if (!document.fullscreenElement) {
                    await document.documentElement.requestFullscreen();
                } else {
                    await document.exitFullscreen();
                }
            } catch (_) {
                showToast("Fullscreen not available");
            }
        });

        infoCloseBtn?.addEventListener("click", closeHotspotPanel);
        infoBackdrop?.addEventListener("click", closeHotspotPanel);

        window.addEventListener("resize", () => {
            resizeRenderer();
        });

        window.addEventListener("orientationchange", () => {
            setTimeout(resizeRenderer, 280);
        });

        if (window.visualViewport) {
            window.visualViewport.addEventListener("resize", resizeRenderer);
        }
    }

    function init() {
        setupResponsiveMode();

        if (!scenes.length) {
            showToast("No scene found");
            return;
        }

        createViewer();
        renderSceneRail();
        bindEvents();
        syncAutorotateButton();

        const initialScene = getInitialSceneFromUrl();
        switchScene(initialScene || scenes[0]);
    }

    init();
})();
