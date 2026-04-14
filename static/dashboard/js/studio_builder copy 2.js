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
    const emptySceneState = document.getElementById("emptySceneState");
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
    const closeHotspotModal = document.getElementById("closeHotspotModal");
    const cancelHotspotBtn = document.getElementById("cancelHotspotBtn");
    const saveHotspotBtn = document.getElementById("saveHotspotBtn");

    const hotspotType = document.getElementById("hotspotType");
    const hotspotLabel = document.getElementById("hotspotLabel");
    const hotspotTooltip = document.getElementById("hotspotTooltip");
    const hotspotTitle = document.getElementById("hotspotTitle");
    const hotspotDescription = document.getElementById("hotspotDescription");
    const hotspotTargetScene = document.getElementById("hotspotTargetScene");
    const hotspotSelectedIconInput = document.getElementById("hotspotSelectedIcon");

    const iconChoices = document.querySelectorAll(".icon-choice");

    let currentSceneId = null;
    let currentTool = "move";
    let pendingHotspotPosition = null;
    let selectedLibraryIcon = "default";
    let isSceneTransitioning = false;

    let activeLayerKey = "A";

    const viewers = {
        A: null,
        B: null,
    };

    const layerViews = {
        A: null,
        B: null,
    };

    const layerScenes = {
        A: null,
        B: null,
    };

    function getLayerEl(key) {
        return key === "A" ? layerAEl : layerBEl;
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

        yawInput.value = radiansToDegrees(currentView.yaw()).toFixed(2);
        pitchInput.value = radiansToDegrees(currentView.pitch()).toFixed(2);
        hfovInput.value = radiansToDegrees(currentView.fov()).toFixed(2);
    }

    function getCenterViewCoordinates() {
        const currentView = layerViews[activeLayerKey];
        if (!currentView) return null;

        return {
            yaw: currentView.yaw(),
            pitch: currentView.pitch(),
            fov: currentView.fov()
        };
    }

    function refreshTargetSceneOptions() {
        if (!hotspotTargetScene) return;

        hotspotTargetScene.innerHTML = `<option value="">No target</option>`;
        scenesData.forEach(scene => {
            const option = document.createElement("option");
            option.value = scene.id;
            option.textContent = scene.title;
            hotspotTargetScene.appendChild(option);
        });
    }

    function buildHotspotElement(hotspot) {
        const el = document.createElement("div");
        el.className = "marzipano-hotspot-marker";
        el.title = hotspot.label || "Hotspot";

        const img = document.createElement("img");
        const iconName = hotspot.selected_icon || "default";
        img.src = (config.iconMap && config.iconMap[iconName]) ? config.iconMap[iconName] : config.iconMap.default;
        img.alt = hotspot.label || "Hotspot";
        img.className = "marzipano-hotspot-icon";

        el.appendChild(img);
        return el;
    }

    function ensureViewer(key) {
        const el = getLayerEl(key);
        if (!el) return null;

        el.innerHTML = "";
        viewers[key] = new Marzipano.Viewer(el, {
            controls: { mouseViewMode: "drag" }
        });

        return viewers[key];
    }

    function createSceneHotspots(scene, layerKey) {
        if (!scene.hotspots || !layerScenes[layerKey]) return;

        scene.hotspots.forEach(hotspot => {
            const el = buildHotspotElement(hotspot);

            el.addEventListener("click", async (e) => {
                e.stopPropagation();

                if (hotspot.type === "navigate" && hotspot.target_scene) {
                    if (!isSceneTransitioning) {
                        await navigateThroughHotspot(hotspot);
                    }
                    return;
                }

                const remove = confirm(`Delete hotspot "${hotspot.label}" ?`);
                if (remove) {
                    deleteHotspot(hotspot.id);
                }
            });

            layerScenes[layerKey].hotspotContainer().createHotspot(el, {
                yaw: hotspot.yaw,
                pitch: hotspot.pitch
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
    const limiter = Marzipano.RectilinearView.limit.traditional(
        4096,
        degreesToRadians(100)
    );

    const initialYaw = degreesToRadians(sceneData.yaw_default || 0);
    const initialPitch = degreesToRadians(sceneData.pitch_default || 0);
    const initialFov = degreesToRadians(sceneData.hfov_default || 100);

    layerViews[layerKey] = new Marzipano.RectilinearView(
        {
            yaw: initialYaw,
            pitch: initialPitch,
            fov: initialFov
        },
        limiter
    );

    layerScenes[layerKey] = viewer.createScene({
        source,
        geometry,
        view: layerViews[layerKey],
        pinFirstLevel: true
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

    console.log("Scene loaded:", sceneData.image_360_url);
    return layerScenes[layerKey];
}
    function markLayerClasses(outgoingKey, incomingKey) {
        const outgoingEl = getLayerEl(outgoingKey);
        const incomingEl = getLayerEl(incomingKey);

        outgoingEl.classList.remove("active-layer", "standby-layer", "layer-incoming");
        incomingEl.classList.remove("active-layer", "standby-layer", "layer-outgoing");

        outgoingEl.classList.add("layer-outgoing");
        incomingEl.classList.add("layer-incoming");
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
            {
                yaw: targetYaw,
                pitch: targetPitch,
                fov: targetFov
            },
            {
                transitionDuration: duration
            }
        );

        setTimeout(syncInputsFromView, duration + 40);
    }

    function nudgeCamera(deltaYaw = 0, deltaPitch = 0, deltaFov = 0) {
        const currentView = layerViews[activeLayerKey];
        if (!currentView) return;

        const nextYaw = currentView.yaw() + deltaYaw;
        const nextPitch = currentView.pitch() + deltaPitch;
        const nextFov = currentView.fov() + deltaFov;

        animateActiveCameraTo(nextYaw, nextPitch, nextFov, 350);
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

        sceneTitleInput.value = scene.title || "";
        yawInput.value = scene.yaw_default ?? 0;
        pitchInput.value = scene.pitch_default ?? 0;
        hfovInput.value = scene.hfov_default ?? 100;

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
            const outgoingEl = getLayerEl(outgoingKey);
            const incomingEl = getLayerEl(incomingKey);

            outgoingEl.classList.add("layer-outgoing");
            incomingEl.classList.add("layer-incoming");
        });

        setTimeout(() => {
            panoramaViewer.classList.remove("transitioning");
            finalizeLayerSwap(incomingKey, outgoingKey);
            isSceneTransitioning = false;
        }, 1020);
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
        const tighterFov = Math.max(degreesToRadians(18), currentView.fov() - degreesToRadians(28));

        animateActiveCameraTo(targetYaw, currentPitch, currentView.fov(), 260);

        setTimeout(() => {
            animateActiveCameraTo(targetYaw, currentPitch, tighterFov, 260);
        }, 180);

        setTimeout(() => {
            currentSceneId = targetScene.id;
            setActiveCard(targetScene.id);

            sceneTitleInput.value = targetScene.title || "";
            yawInput.value = targetScene.yaw_default ?? 0;
            pitchInput.value = targetScene.pitch_default ?? 0;
            hfovInput.value = targetScene.hfov_default ?? 100;

            if (viewerSceneTitle) viewerSceneTitle.textContent = targetScene.title || "Untitled Scene";
            if (activeSceneLabel) activeSceneLabel.textContent = targetScene.title || "Scene preview";

            refreshTargetSceneOptions();
            crossfadeToScene(targetScene);
        }, 380);
    }

    function appendSceneCard(scene) {
        if (emptySceneState) emptySceneState.remove();

        const card = document.createElement("button");
        card.type = "button";
        card.className = "scene-card";
        card.dataset.sceneId = scene.id;

        card.innerHTML = `
            <div class="scene-thumb">
                ${scene.thumbnail_url || scene.image_360_url
                    ? `<img src="${scene.thumbnail_url || scene.image_360_url}" alt="${scene.title}">`
                    : `<div class="thumb-placeholder">360</div>`}
            </div>
            <div class="scene-meta">
                <strong>${scene.title}</strong>
                <span>Order ${scene.order}</span>
            </div>
        `;

        card.addEventListener("click", () => {
            if (isSceneTransitioning) return;
            const targetScene = findScene(scene.id);
            if (!targetScene) return;

            currentSceneId = targetScene.id;
            setActiveCard(targetScene.id);

            sceneTitleInput.value = targetScene.title || "";
            yawInput.value = targetScene.yaw_default ?? 0;
            pitchInput.value = targetScene.pitch_default ?? 0;
            hfovInput.value = targetScene.hfov_default ?? 100;

            if (viewerSceneTitle) viewerSceneTitle.textContent = targetScene.title || "Untitled Scene";
            if (activeSceneLabel) activeSceneLabel.textContent = targetScene.title || "Scene preview";

            refreshTargetSceneOptions();
            isSceneTransitioning = true;
            crossfadeToScene(targetScene);
        });

        sceneList.appendChild(card);
    }

    async function uploadFiles(files) {
        if (!files || files.length === 0) return;

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
            scene.hotspots = [];
            scenesData.push(scene);
            appendSceneCard(scene);
        });

        if (newScenes.length > 0 && !currentSceneId) {
            loadInitialScene(newScenes[0].id);
        }
    }

    async function saveScene() {
        if (!currentSceneId) {
            alert("Select a scene first.");
            return;
        }

        syncInputsFromView();

        const payload = {
            title: sceneTitleInput.value,
            yaw_default: parseFloat(yawInput.value || 0),
            pitch_default: parseFloat(pitchInput.value || 0),
            hfov_default: parseFloat(hfovInput.value || 100),
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

        document.querySelectorAll(".scene-card").forEach(card => {
            if (String(card.dataset.sceneId) === String(updatedScene.id)) {
                const titleEl = card.querySelector(".scene-meta strong");
                if (titleEl) titleEl.textContent = updatedScene.title;

                const orderEl = card.querySelector(".scene-meta span");
                if (orderEl) orderEl.textContent = `Order ${updatedScene.order}`;
            }
        });

        alert("Scene camera saved.");
    }

    function openHotspotModal(position) {
        pendingHotspotPosition = position;
        hotspotLabel.value = "";
        hotspotTooltip.value = "";
        hotspotTitle.value = "";
        hotspotDescription.value = "";
        hotspotTargetScene.value = "";
        hotspotType.value = currentTool === "navigate" ? "navigate" : "info";

        if (hotspotSelectedIconInput) {
            hotspotSelectedIconInput.value = selectedLibraryIcon;
        }

        hotspotModal.classList.remove("hidden");
    }

    function closeHotspotModalFn() {
        hotspotModal.classList.add("hidden");
        pendingHotspotPosition = null;
    }

    async function createHotspotRequest() {
        if (!currentSceneId || !pendingHotspotPosition) return;

        const payload = {
            type: hotspotType.value,
            label: hotspotLabel.value || "Hotspot",
            tooltip_text: hotspotTooltip.value || "",
            title: hotspotTitle.value || "",
            description: hotspotDescription.value || "",
            target_scene: hotspotTargetScene.value || null,
            yaw: pendingHotspotPosition.yaw,
            pitch: pendingHotspotPosition.pitch,
            selected_icon: hotspotSelectedIconInput?.value || selectedLibraryIcon || "default",
            payload: {},
        };

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

        scenesData = scenesData.map(scene => {
            if (String(scene.id) === String(currentSceneId)) {
                const hotspots = Array.isArray(scene.hotspots) ? scene.hotspots : [];
                return { ...scene, hotspots: [...hotspots, hotspot] };
            }
            return scene;
        });

        const activeScene = findScene(currentSceneId);
        if (activeScene) {
            const refreshed = { ...activeScene, hotspots: scenesData.find(s => String(s.id) === String(currentSceneId)).hotspots };
            buildLayerScene(activeLayerKey, refreshed);
        }

        closeHotspotModalFn();
    }

    async function createHotspotAtCenter() {
        const center = getCenterViewCoordinates();
        if (!center || !currentSceneId) {
            alert("No active scene.");
            return;
        }

        openHotspotModal({
            yaw: center.yaw,
            pitch: center.pitch
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

        const activeScene = findScene(currentSceneId);
        if (activeScene) {
            buildLayerScene(activeLayerKey, activeScene);
        }
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
    setCurrentViewBtn?.addEventListener("click", saveScene);
    createCenterHotspotBtn?.addEventListener("click", createHotspotAtCenter);

    toolButtons.forEach(btn => {
        btn.addEventListener("click", () => setActiveTool(btn.dataset.tool));
    });

    iconChoices.forEach(btn => {
        btn.addEventListener("click", () => {
            selectedLibraryIcon = btn.dataset.icon;
            iconChoices.forEach(item => item.classList.remove("active"));
            btn.classList.add("active");

            if (hotspotSelectedIconInput) {
                hotspotSelectedIconInput.value = selectedLibraryIcon;
            }
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
            pitch: coords.pitch
        });
    });

    closeHotspotModal?.addEventListener("click", closeHotspotModalFn);
    cancelHotspotBtn?.addEventListener("click", closeHotspotModalFn);
    saveHotspotBtn?.addEventListener("click", createHotspotRequest);

    document.querySelectorAll(".scene-card").forEach(card => {
        card.addEventListener("click", () => {
            if (isSceneTransitioning) return;
            const targetScene = findScene(card.dataset.sceneId);
            if (!targetScene) return;

            currentSceneId = targetScene.id;
            setActiveCard(targetScene.id);

            sceneTitleInput.value = targetScene.title || "";
            yawInput.value = targetScene.yaw_default ?? 0;
            pitchInput.value = targetScene.pitch_default ?? 0;
            hfovInput.value = targetScene.hfov_default ?? 100;

            if (viewerSceneTitle) viewerSceneTitle.textContent = targetScene.title || "Untitled Scene";
            if (activeSceneLabel) activeSceneLabel.textContent = targetScene.title || "Scene preview";

            refreshTargetSceneOptions();
            isSceneTransitioning = true;
            crossfadeToScene(targetScene);
        });
    });

    if (scenesData.length > 0) {
        loadInitialScene(scenesData[0].id);
    }
});