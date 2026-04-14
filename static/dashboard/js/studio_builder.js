document.addEventListener("DOMContentLoaded", () => {
    if (typeof Marzipano === "undefined") {
        console.error("Marzipano library is not loaded.");
        alert("Marzipano n'est pas chargé. Vérifie le script marzipano.js.");
        return;
    }

    const config = window.BUILDER_CONFIG || {};
    const scenesDataEl = document.getElementById("scenes-data");
    let scenesData = scenesDataEl ? JSON.parse(scenesDataEl.textContent) : [];

    const sceneList = document.getElementById("sceneList");
    const dropZone = document.getElementById("dropZone");
    const sceneFileInput = document.getElementById("sceneFileInput");
    const addSceneBtn = document.getElementById("addSceneBtn");

    const sceneTitleInput = document.getElementById("sceneTitle");
    const yawInput = document.getElementById("yawDefault");
    const pitchInput = document.getElementById("pitchDefault");
    const hfovInput = document.getElementById("hfovDefault");

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

    // Smart form panels
    const hotspotPanels = document.querySelectorAll(".hotspot-type-panel");
    const hotspotIconOptions = document.querySelectorAll(".hotspot-icon-option");

    // INFO
    const hotspotImageUpload = document.getElementById("hotspotImageUpload");
    const hotspotImageUrl = document.getElementById("hotspotImageUrl");

    // PRODUCT
    const hotspotProductTitle = document.getElementById("hotspotProductTitle");
    const hotspotProductDescription = document.getElementById("hotspotProductDescription");
    const hotspotImageUploadProduct = document.getElementById("hotspotImageUploadProduct");
    const hotspotImageUrlProduct = document.getElementById("hotspotImageUrlProduct");
    const hotspotPrice = document.getElementById("hotspotPrice");
    const hotspotBadge = document.getElementById("hotspotBadge");
    const hotspotButtonText = document.getElementById("hotspotButtonText");
    const hotspotCtaUrl = document.getElementById("hotspotCtaUrl");
    const hotspotSiteName = document.getElementById("hotspotSiteName");

    // WHATSAPP
    const hotspotWhatsapp = document.getElementById("hotspotWhatsapp");
    const hotspotWhatsappMessage = document.getElementById("hotspotWhatsappMessage");

    // PHONE / EMAIL
    const hotspotPhone = document.getElementById("hotspotPhone");
    const hotspotEmail = document.getElementById("hotspotEmail");

    // CTA
    const hotspotWebsiteTitle = document.getElementById("hotspotWebsiteTitle");
    const hotspotWebsiteButtonText = document.getElementById("hotspotWebsiteButtonText");
    const hotspotWebsiteUrl = document.getElementById("hotspotWebsiteUrl");

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
    let selectedHotspotId = null;
    let selectedHotspotDraft = null;
    let draggedSceneId = null;
    let tourTitleSaveTimeout = null;
    let lastSavedTourTitle = tourTitleInput?.value || "";

    const viewers = { A: null, B: null };
    const layerViews = { A: null, B: null };
    const layerScenes = { A: null, B: null };

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

    function refreshTargetSceneOptions() {
        if (!hotspotTargetScene) return;
        hotspotTargetScene.innerHTML = `<option value="">Select a scene</option>`;
        scenesData.forEach(scene => {
            const option = document.createElement("option");
            option.value = scene.id;
            option.textContent = scene.title;
            hotspotTargetScene.appendChild(option);
        });
    }

    function getHotspotDisplay(hotspot) {
        return hotspot?.payload?.display || {};
    }

    function resolveHotspotIconSrc(iconName) {
        if (config.businessIconMap && config.businessIconMap[iconName]) {
            return config.businessIconMap[iconName];
        }
        if (config.iconMap && config.iconMap[iconName]) {
            return config.iconMap[iconName];
        }
        return config.iconMap?.default || "";
    }

    function updateHotspotTypePanels(type) {
        hotspotPanels.forEach(panel => {
            panel.classList.toggle("active", panel.dataset.panel === type);
        });
    }

    function activateIconOption(iconName) {
        hotspotIconOptions.forEach(btn => {
            btn.classList.toggle("active", btn.dataset.icon === iconName);
        });
        if (hotspotSelectedIconInput) hotspotSelectedIconInput.value = iconName;
        selectedLibraryIcon = iconName;
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

        hotspotPopupMedia.innerHTML = imageUrl
            ? `<img src="${imageUrl}" alt="${hotspot.title || hotspot.label || "Hotspot"}">`
            : `<div style="color:#9fb4cf;font-size:13px;">No image</div>`;

        hotspotPopupTitle.textContent = hotspot.title || hotspot.label || "Hotspot";
        hotspotPopupDescription.textContent = hotspot.description || hotspot.tooltip_text || "";

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
        el.className = `marzipano-hotspot-marker variant-${variant} hotspot-anchor-${anchor}`;
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

    function buildLayerScene(layerKey, sceneData) {
        if (!sceneData.image_360_url) {
            console.warn("No panorama URL for scene:", sceneData);
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

        currentSceneId = scene.id;
        setActiveCard(scene.id);

        if (sceneTitleInput) sceneTitleInput.value = scene.title || "";
        if (yawInput) yawInput.value = scene.yaw_default ?? 0;
        if (pitchInput) pitchInput.value = scene.pitch_default ?? 0;
        if (hfovInput) hfovInput.value = scene.hfov_default ?? 100;

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
            currentSceneId = targetScene.id;
            setActiveCard(targetScene.id);

            if (sceneTitleInput) sceneTitleInput.value = targetScene.title || "";
            if (yawInput) yawInput.value = targetScene.yaw_default ?? 0;
            if (pitchInput) pitchInput.value = targetScene.pitch_default ?? 0;
            if (hfovInput) hfovInput.value = targetScene.hfov_default ?? 100;

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

    function renderSceneList() {
        if (!sceneList) return;

        sceneList.innerHTML = "";

        if (!scenesData.length) {
            sceneList.innerHTML = `
                <div id="emptySceneState" class="empty-state">
                    There is no panorama yet.<br>
                    Drop your panorama file here or use <strong>Add pano</strong>.
                </div>
            `;
            return;
        }

        sortScenesData();

        scenesData.forEach(scene => {
            const wrapper = document.createElement("div");
            wrapper.className = "scene-card-wrap";
            wrapper.dataset.sceneId = scene.id;
            wrapper.setAttribute("draggable", "true");

            wrapper.innerHTML = `
                <button class="scene-card ${String(scene.id) === String(currentSceneId) ? "active" : ""}"
                        data-scene-id="${scene.id}"
                        type="button">
                    <div class="scene-thumb">
                        ${scene.thumbnail_url || scene.image_360_url
                            ? `<img src="${scene.thumbnail_url || scene.image_360_url}" alt="${scene.title}">`
                            : `<div class="thumb-placeholder">360</div>`}
                    </div>
                    <div class="scene-meta">
                        <strong>${scene.title}</strong>
                        <span>Order ${scene.order}</span>
                    </div>
                </button>
                <div class="scene-drag-handle" title="Drag to reorder">⋮⋮</div>
            `;

            wrapper.querySelector(".scene-card")?.addEventListener("click", () => {
                if (isSceneTransitioning) return;
                const targetScene = findScene(scene.id);
                if (!targetScene) return;

                currentSceneId = targetScene.id;
                setActiveCard(targetScene.id);

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

        const response = await fetch(config.reorderScenesUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCSRFToken(),
            },
            body: JSON.stringify({
                scene_ids: scenesData.slice().sort((a, b) => (a.order ?? 0) - (b.order ?? 0)).map(scene => scene.id),
            }),
        });

        if (!response.ok) {
            alert("Unable to reorder scenes.");
            return false;
        }

        const data = await response.json();
        scenesData = data.scenes || [];
        sortScenesData();
        renderSceneList();
        return true;
    }

    async function uploadFiles(files) {
        if (!files || !files.length || !config.uploadScenesUrl) return;

        const formData = new FormData();
        Array.from(files).forEach(file => formData.append("panos", file));

        const response = await fetch(config.uploadScenesUrl, {
            method: "POST",
            headers: { "X-CSRFToken": getCSRFToken() },
            body: formData,
        });

        if (!response.ok) {
            alert("Upload failed.");
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
    }

    async function saveScene() {
        if (!currentSceneId) {
            alert("Select a scene first.");
            return;
        }

        const currentView = layerViews[activeLayerKey];
        if (currentView) {
            if (yawInput) yawInput.value = radiansToDegrees(currentView.yaw()).toFixed(2);
            if (pitchInput) pitchInput.value = radiansToDegrees(currentView.pitch()).toFixed(2);
            if (hfovInput) hfovInput.value = radiansToDegrees(currentView.fov()).toFixed(2);
        }

        const payload = {
            title: sceneTitleInput?.value || "",
            yaw_default: parseFloat(yawInput?.value || 0),
            pitch_default: parseFloat(pitchInput?.value || 0),
            hfov_default: parseFloat(hfovInput?.value || 100),
        };

        const response = await fetch(`${config.updateSceneBaseUrl}${currentSceneId}/update/`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCSRFToken(),
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            alert("Unable to save scene.");
            return;
        }

        const data = await response.json();
        const updatedScene = data.scene;

        scenesData = scenesData.map(scene =>
            String(scene.id) === String(updatedScene.id)
                ? { ...scene, ...updatedScene, hotspots: scene.hotspots || [] }
                : scene
        );

        renderSceneList();
        alert("Scene position saved.");
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
    }

    function openHotspotModal(position) {
        editingHotspotId = null;
        pendingHotspotPosition = position;
        if (hotspotModalTitle) hotspotModalTitle.textContent = "Create Hotspot";
        if (saveHotspotBtn) saveHotspotBtn.textContent = "Save Hotspot";
        if (deleteHotspotBtn) deleteHotspotBtn.style.display = "none";

        resetHotspotModalFields();
        hotspotModal?.classList.remove("hidden");
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
        if (saveHotspotBtn) saveHotspotBtn.textContent = "Update Hotspot";
        if (deleteHotspotBtn) deleteHotspotBtn.style.display = "inline-flex";

        if (hotspotType) hotspotType.value = type;
        if (hotspotLabel) hotspotLabel.value = hotspot.label || "";
        if (hotspotTooltip) hotspotTooltip.value = hotspot.tooltip_text || "";
        if (hotspotTitle) hotspotTitle.value = hotspot.title || "";
        if (hotspotDescription) hotspotDescription.value = hotspot.description || "";
        if (hotspotTargetScene) hotspotTargetScene.value = hotspot.target_scene || "";

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

        updateHotspotTypePanels(type);
        activateIconOption(hotspot.selected_icon || "default");

        hotspotModal?.classList.remove("hidden");
    }

    function closeHotspotModalFn() {
        hotspotModal?.classList.add("hidden");
        pendingHotspotPosition = null;
        editingHotspotId = null;
    }

    function getImageFileForType(type) {
        if (type === "info") return hotspotImageUpload?.files?.[0] || null;
        if (type === "product") return hotspotImageUploadProduct?.files?.[0] || null;
        return null;
    }

    function buildHotspotRequestPayload() {
        const type = hotspotType?.value || "navigate";

        let title = hotspotLabel?.value || "Hotspot";
        let description = "";
        let content = {};

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
            target_scene: hotspotTargetScene?.value || null,
            yaw: pendingHotspotPosition.yaw,
            pitch: pendingHotspotPosition.pitch,
            selected_icon: hotspotSelectedIconInput?.value || selectedLibraryIcon || "default",
            payload: {
                display: {
                    variant: hotspotVariant?.value || "pin",
                    size: Number(hotspotSize?.value || 56),
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
            alert("Unable to upload hotspot image.");
            return "";
        }

        const data = await response.json();
        return data?.hotspot?.ad_image_url || "";
    }

    async function createHotspotRequest() {
        if (!currentSceneId || !pendingHotspotPosition) return;

        const payload = buildHotspotRequestPayload();
        const type = payload.type;

        const response = await fetch(`${config.createHotspotBaseUrl}${currentSceneId}/create-hotspot/`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCSRFToken(),
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            alert("Unable to create hotspot.");
            return;
        }

        const data = await response.json();
        const hotspot = data.hotspot;

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
            if (String(scene.id) === String(currentSceneId)) {
                const hotspots = Array.isArray(scene.hotspots) ? scene.hotspots : [];
                return { ...scene, hotspots: [...hotspots, hotspot] };
            }
            return scene;
        });

        const activeScene = findScene(currentSceneId);
        if (activeScene) buildLayerScene(activeLayerKey, activeScene);

        closeHotspotModalFn();
    }

    async function updateHotspotRequest() {
        if (!editingHotspotId || !pendingHotspotPosition) return;

        const payload = buildHotspotRequestPayload();
        const type = payload.type;

        const response = await fetch(`${config.updateHotspotBaseUrl}${editingHotspotId}/update/`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCSRFToken(),
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            alert("Unable to update hotspot.");
            return;
        }

        const data = await response.json();
        const updatedHotspot = data.hotspot;

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
    }

    async function saveHotspotHandler() {
        if (editingHotspotId) {
            await updateHotspotRequest();
        } else {
            await createHotspotRequest();
        }
    }

    async function createHotspotAtCenter() {
        const center = getCenterViewCoordinates();
        if (!center || !currentSceneId) {
            alert("No active scene.");
            return;
        }

        openHotspotModal({
            yaw: center.yaw,
            pitch: center.pitch,
        });
    }

    async function deleteHotspot(hotspotId) {
        const response = await fetch(`${config.deleteHotspotBaseUrl}${hotspotId}/delete/`, {
            method: "POST",
            headers: { "X-CSRFToken": getCSRFToken() },
        });

        if (!response.ok) {
            alert("Unable to delete hotspot.");
            return;
        }

        scenesData = scenesData.map(scene => {
            if (String(scene.id) === String(currentSceneId)) {
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
    }

    async function deleteEditingHotspot() {
        if (!editingHotspotId) return;
        const confirmed = confirm("Delete this hotspot?");
        if (!confirmed) return;

        await deleteHotspot(editingHotspotId);
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
            alert("Unable to save tour title.");
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

    if (scenesData.length > 0) {
        sortScenesData();
        renderSceneList();
        loadInitialScene(scenesData[0].id);
    }
});