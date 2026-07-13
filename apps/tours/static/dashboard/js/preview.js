document.addEventListener("DOMContentLoaded", () => {
    if (typeof Marzipano === "undefined") {
        console.error("Marzipano not loaded");
        return;
    }

    const config = window.PREVIEW_CONFIG || {};
    const scenesDataEl = document.getElementById("preview-scenes-data");
    let scenes = scenesDataEl ? JSON.parse(scenesDataEl.textContent) : [];

    const previewViewer = document.getElementById("previewViewer");
    const previewLayerA = document.getElementById("previewLayerA");
    const previewLayerB = document.getElementById("previewLayerB");
    const previewMountA = document.getElementById("previewMountA");
    const previewMountB = document.getElementById("previewMountB");

    const previewSceneTitle = document.getElementById("previewSceneTitle");
    const previewScenesList = document.getElementById("previewScenesList");
    const toggleSceneDrawerBtn = document.getElementById("toggleSceneDrawerBtn");
    const previewScenesDrawer = document.getElementById("previewScenesDrawer");
    const previewFullscreenBtn = document.getElementById("previewFullscreenBtn");

    const previewDeviceFrame = document.getElementById("previewDeviceFrame");
    const deviceButtons = document.querySelectorAll(".device-btn");

    const previewPopup = document.getElementById("previewHotspotPopup");
    const previewPopupClose = document.getElementById("previewPopupClose");
    const previewPopupMedia = document.getElementById("previewPopupMedia");
    const previewPopupBadge = document.getElementById("previewPopupBadge");
    const previewPopupTitle = document.getElementById("previewPopupTitle");
    const previewPopupDescription = document.getElementById("previewPopupDescription");
    const previewPopupPrice = document.getElementById("previewPopupPrice");
    const previewPopupSite = document.getElementById("previewPopupSite");
    const previewPopupAction = document.getElementById("previewPopupAction");
    const previewPopupWhatsapp = document.getElementById("previewPopupWhatsapp");
    const previewPopupContact = document.getElementById("previewPopupContact");

    let activeLayerKey = "A";
    let currentSceneId = null;
    let isTransitioning = false;

    const viewers = { A: null, B: null };
    const views = { A: null, B: null };
    const marzipanoScenes = { A: null, B: null };

    function getLayerEl(key) {
        return key === "A" ? previewLayerA : previewLayerB;
    }

    function getMountEl(key) {
        return key === "A" ? previewMountA : previewMountB;
    }

    function standbyLayerKey() {
        return activeLayerKey === "A" ? "B" : "A";
    }

    function degToRad(deg) {
        return deg * Math.PI / 180;
    }

    function normalizeAngle(rad) {
        while (rad > Math.PI) rad -= 2 * Math.PI;
        while (rad < -Math.PI) rad += 2 * Math.PI;
        return rad;
    }

    function findScene(sceneId) {
        return scenes.find(scene => String(scene.id) === String(sceneId));
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

    function updateAllViewerSizes() {
        try {
            Object.values(viewers).forEach(viewer => {
                if (viewer && typeof viewer.updateSize === "function") {
                    viewer.updateSize();
                }
            });
        } catch (_) {}
    }

    function closePopup() {
        previewPopup?.classList.add("hidden");
    }

    function openPopup(hotspot) {
        if (!previewPopup) return;

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
        const whatsappMessage = content.whatsapp_message || "Bonjour";

        previewPopupMedia.innerHTML = imageUrl
            ? `<img src="${imageUrl}" alt="${hotspot.title || hotspot.label || "Hotspot"}">`
            : `<div class="popup-empty-media">No image</div>`;

        previewPopupTitle.textContent = hotspot.title || hotspot.label || "Hotspot";
        previewPopupDescription.textContent = hotspot.description || hotspot.tooltip_text || "";

        if (badge) {
            previewPopupBadge.textContent = badge;
            previewPopupBadge.classList.remove("hidden");
        } else {
            previewPopupBadge.classList.add("hidden");
            previewPopupBadge.textContent = "";
        }

        if (price) {
            previewPopupPrice.textContent = price;
            previewPopupPrice.classList.remove("hidden");
        } else {
            previewPopupPrice.classList.add("hidden");
            previewPopupPrice.textContent = "";
        }

        if (siteName) {
            previewPopupSite.textContent = siteName;
            previewPopupSite.classList.remove("hidden");
        } else {
            previewPopupSite.classList.add("hidden");
            previewPopupSite.textContent = "";
        }

        if (ctaUrl) {
            previewPopupAction.href = ctaUrl;
            previewPopupAction.textContent = buttonText;
            previewPopupAction.classList.remove("hidden");
        } else {
            previewPopupAction.removeAttribute("href");
            previewPopupAction.classList.add("hidden");
        }

        if (whatsappNumber) {
            const cleanNumber = String(whatsappNumber).replace(/[^\d]/g, "");
            previewPopupWhatsapp.href = `https://wa.me/${cleanNumber}?text=${encodeURIComponent(whatsappMessage)}`;
            previewPopupWhatsapp.classList.remove("hidden");
        } else {
            previewPopupWhatsapp.removeAttribute("href");
            previewPopupWhatsapp.classList.add("hidden");
        }

        if (phone) {
            previewPopupContact.href = `tel:${phone}`;
            previewPopupContact.textContent = "Call";
            previewPopupContact.classList.remove("hidden");
        } else if (email) {
            previewPopupContact.href = `mailto:${email}`;
            previewPopupContact.textContent = "Email";
            previewPopupContact.classList.remove("hidden");
        } else {
            previewPopupContact.removeAttribute("href");
            previewPopupContact.classList.add("hidden");
        }

        previewPopup.classList.remove("hidden");
    }

    function buildHotspotNode(hotspot) {
        const display = hotspot.payload?.display || {};
        const variant = display.variant || "pin";
        const size = Number(display.size || 56);
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
        img.src = resolveIcon(hotspot.selected_icon || "default");
        img.alt = hotspot.label || "Hotspot";

        if (variant === "label") {
            const span = document.createElement("span");
            span.textContent = hotspot.label || "Hotspot";
            node.appendChild(img);
            node.appendChild(span);
        } else {
            node.appendChild(img);
        }

        node.addEventListener("click", async (e) => {
            e.stopPropagation();

            if (hotspot.type === "navigate" && hotspot.target_scene) {
                await navigateToScene(hotspot.target_scene, hotspot);
                return;
            }

            openPopup(hotspot);
        });

        return node;
    }

    function ensureViewer(key) {
        const mount = getMountEl(key);
        if (!mount) return null;

        mount.innerHTML = "";
        viewers[key] = new Marzipano.Viewer(mount, {
            controls: { mouseViewMode: "drag" }
        });

        return viewers[key];
    }

    function buildSceneOnLayer(layerKey, sceneData) {
        const viewer = ensureViewer(layerKey);
        if (!viewer || !sceneData.image_360_url) return null;

        const source = Marzipano.ImageUrlSource.fromString(sceneData.image_360_url);
        const geometry = new Marzipano.EquirectGeometry([{ width: 4000 }]);
        const limiter = Marzipano.RectilinearView.limit.traditional(4096, degToRad(100));

        const yaw = degToRad(sceneData.yaw_default || 0);
        const pitch = degToRad(sceneData.pitch_default || 0);
        const fov = degToRad(sceneData.hfov_default || 100);

        views[layerKey] = new Marzipano.RectilinearView({ yaw, pitch, fov }, limiter);

        marzipanoScenes[layerKey] = viewer.createScene({
            source,
            geometry,
            view: views[layerKey],
            pinFirstLevel: true,
        });

        marzipanoScenes[layerKey].switchTo();

        (sceneData.hotspots || []).forEach(hotspot => {
            const node = buildHotspotNode(hotspot);
            marzipanoScenes[layerKey].hotspotContainer().createHotspot(node, {
                yaw: hotspot.yaw,
                pitch: hotspot.pitch,
            });
        });

        requestAnimationFrame(() => {
            updateAllViewerSizes();
        });

        return marzipanoScenes[layerKey];
    }

    function markActiveSceneCard(sceneId) {
        document.querySelectorAll(".preview-scene-card").forEach(card => {
            card.classList.toggle("active", String(card.dataset.sceneId) === String(sceneId));
        });
    }

    function renderSceneDrawer() {
        if (!previewScenesList) return;
        previewScenesList.innerHTML = "";

        scenes
            .slice()
            .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
            .forEach(scene => {
                const btn = document.createElement("button");
                btn.type = "button";
                btn.className = "preview-scene-card";
                btn.dataset.sceneId = scene.id;

                btn.innerHTML = `
                    <div class="preview-scene-thumb">
                        ${scene.thumbnail_url || scene.image_360_url
                            ? `<img src="${scene.thumbnail_url || scene.image_360_url}" alt="${scene.title}">`
                            : `<div class="thumb-placeholder">360</div>`}
                    </div>
                    <div class="preview-scene-meta">
                        <strong>${scene.title}</strong>
                        <span>Scene ${scene.order ?? ""}</span>
                    </div>
                `;

                btn.addEventListener("click", () => {
                    if (isTransitioning) return;
                    const target = findScene(scene.id);
                    if (!target) return;
                    isTransitioning = true;
                    closePopup();
                    cinematicSwitchScene(target);
                });

                previewScenesList.appendChild(btn);
            });
    }

    function setTitle(scene) {
        if (previewSceneTitle) {
            previewSceneTitle.textContent = scene?.title || "Untitled Scene";
        }
        markActiveSceneCard(scene?.id);
    }

    function cinematicSwitchScene(targetScene, fromYaw = null, fromPitch = null) {
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

        const targetYaw = fromYaw !== null ? fromYaw : degToRad(targetScene.yaw_default || 0);
        const targetPitch = fromPitch !== null ? fromPitch : degToRad(targetScene.pitch_default || 0);
        const finalFov = degToRad(targetScene.hfov_default || 100);
        const incomingStartFov = Math.max(degToRad(18), finalFov - degToRad(20));

        if (incomingView) {
            incomingView.setParameters({
                yaw: targetYaw,
                pitch: targetPitch,
                fov: incomingStartFov,
            });
        }

        outgoingEl.classList.remove("standby-layer", "layer-incoming", "layer-outgoing");
        incomingEl.classList.remove("standby-layer", "layer-incoming", "layer-outgoing");

        outgoingEl.classList.add("active-layer");
        incomingEl.classList.add("layer-incoming");
        incomingEl.style.opacity = "0";

        previewViewer.classList.add("is-cinematic-transition");

        currentSceneId = targetScene.id;
        setTitle(targetScene);

        requestAnimationFrame(() => {
            incomingEl.style.opacity = "1";
            outgoingEl.classList.add("layer-outgoing");
        });

        setTimeout(() => {
            if (incomingView) {
                incomingView.setParameters(
                    {
                        yaw: degToRad(targetScene.yaw_default || 0),
                        pitch: degToRad(targetScene.pitch_default || 0),
                        fov: finalFov,
                    },
                    { transitionDuration: 880 }
                );
            }
        }, 140);

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
        }, 1450);
    }

    async function navigateToScene(targetSceneId, hotspot) {
        if (isTransitioning) return;

        const targetScene = findScene(targetSceneId);
        const currentView = views[activeLayerKey];
        if (!targetScene || !currentView) return;

        isTransitioning = true;
        closePopup();

        const hotspotYaw = normalizeAngle(hotspot.yaw);
        const hotspotPitch = hotspot.pitch || currentView.pitch();

        const currentFov = currentView.fov();
        const lockFov = Math.max(degToRad(30), currentFov - degToRad(8));
        const punchFov = Math.max(degToRad(15), currentFov - degToRad(24));

        currentView.setParameters(
            {
                yaw: hotspotYaw,
                pitch: hotspotPitch,
                fov: lockFov,
            },
            { transitionDuration: 320 }
        );

        setTimeout(() => {
            currentView.setParameters(
                {
                    yaw: hotspotYaw,
                    pitch: hotspotPitch,
                    fov: punchFov,
                },
                { transitionDuration: 460 }
            );
        }, 180);

        setTimeout(() => {
            cinematicSwitchScene(targetScene, hotspotYaw, hotspotPitch);
        }, 680);
    }

    function setPreviewDeviceMode(mode) {
        if (!previewDeviceFrame) return;

        previewDeviceFrame.classList.remove(
            "device-desktop",
            "device-ipad-landscape",
            "device-iphone-portrait",
            "has-safe-area"
        );

        const classMap = {
            desktop: "device-desktop",
            "ipad-landscape": "device-ipad-landscape",
            "iphone-portrait": "device-iphone-portrait",
        };

        previewDeviceFrame.classList.add(classMap[mode] || "device-desktop");

        if (mode !== "desktop") {
            previewDeviceFrame.classList.add("has-safe-area");
        }

        deviceButtons.forEach(btn => {
            btn.classList.toggle("active", btn.dataset.device === mode);
        });

        setTimeout(() => {
            updateAllViewerSizes();
        }, 380);
    }

    toggleSceneDrawerBtn?.addEventListener("click", () => {
        previewScenesDrawer?.classList.toggle("collapsed");
        setTimeout(() => {
            updateAllViewerSizes();
        }, 320);
    });

    previewFullscreenBtn?.addEventListener("click", () => {
        if (previewViewer.requestFullscreen) {
            previewViewer.requestFullscreen();
        }
    });

    previewPopupClose?.addEventListener("click", (e) => {
        e.stopPropagation();
        closePopup();
    });

    previewViewer?.addEventListener("click", () => {
        closePopup();
    });

    deviceButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            setPreviewDeviceMode(btn.dataset.device);
        });
    });

    window.addEventListener("resize", () => {
        updateAllViewerSizes();
    });

    document.addEventListener("fullscreenchange", () => {
        setTimeout(() => {
            updateAllViewerSizes();
        }, 200);
    });

    if (window.innerWidth < 768) {
        previewScenesDrawer?.classList.add("collapsed");
    }

    if (scenes.length > 0) {
        scenes = scenes.slice().sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
        renderSceneDrawer();

        currentSceneId = scenes[0].id;
        buildSceneOnLayer(activeLayerKey, scenes[0]);
        setTitle(scenes[0]);
        setPreviewDeviceMode("desktop");
    }
});