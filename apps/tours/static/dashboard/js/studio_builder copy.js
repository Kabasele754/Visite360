document.addEventListener("DOMContentLoaded", () => {
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

    const saveSceneBtn = document.getElementById("saveSceneBtn");
    const toolButtons = document.querySelectorAll(".tool-btn");

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

    let currentSceneId = null;
    let currentTool = "move";
    let pendingHotspotPosition = null;

    let marzipanoViewer = null;
    let currentMarzipanoScene = null;
    let currentView = null;

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

    function ensureViewer() {
        if (!marzipanoViewer && panoramaViewer) {
            marzipanoViewer = new Marzipano.Viewer(panoramaViewer, {
                controls: { mouseViewMode: "drag" }
            });
        }
    }

    function createSceneHotspots(scene) {
        if (!scene.hotspots || !currentMarzipanoScene) return;

        scene.hotspots.forEach(hotspot => {
            const el = document.createElement("div");
            el.className = "marzipano-hotspot-marker";
            el.title = hotspot.label || "Hotspot";
            el.innerHTML = hotspot.type === "navigate" ? "➜" : "i";

            el.addEventListener("click", (e) => {
                e.stopPropagation();

                if (hotspot.type === "navigate" && hotspot.target_scene) {
                    loadScene(hotspot.target_scene);
                    return;
                }

                const remove = confirm(`Delete hotspot "${hotspot.label}" ?`);
                if (remove) {
                    deleteHotspot(hotspot.id);
                }
            });

            currentMarzipanoScene.hotspotContainer().createHotspot(el, {
                yaw: hotspot.yaw,
                pitch: hotspot.pitch
            });
        });
    }

    function loadMarzipanoScene(scene) {
    ensureViewer();
    if (!scene.image_360_url || !marzipanoViewer) return;

    const source = Marzipano.ImageUrlSource.fromString(scene.image_360_url);
    const geometry = new Marzipano.EquirectGeometry([{ width: 4000 }]);
    const limiter = Marzipano.RectilinearView.limit.traditional(4096, 100 * Math.PI / 180);

    const initialYaw = (scene.yaw_default || 0) * Math.PI / 180;
    const initialPitch = (scene.pitch_default || 0) * Math.PI / 180;
    const initialFov = (scene.hfov_default || 100) * Math.PI / 180;

    currentView = new Marzipano.RectilinearView(
        { yaw: initialYaw, pitch: initialPitch, fov: initialFov },
        limiter
    );

    currentMarzipanoScene = marzipanoViewer.createScene({
        source,
        geometry,
        view: currentView,
        pinFirstLevel: true
    });

    currentMarzipanoScene.switchTo();
    createSceneHotspots(scene);
}
    function loadScene(sceneId) {
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
        loadMarzipanoScene(scene);
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

        card.addEventListener("click", () => loadScene(scene.id));
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

        if (newScenes.length > 0) {
            loadScene(newScenes[0].id);
        }
    }

    async function saveScene() {
        if (!currentSceneId) {
            alert("Select a scene first.");
            return;
        }

        let liveYaw = parseFloat(yawInput.value || 0);
        let livePitch = parseFloat(pitchInput.value || 0);
        let liveHfov = parseFloat(hfovInput.value || 100);

        if (currentView) {
            liveYaw = currentView.yaw() * 180 / Math.PI;
            livePitch = currentView.pitch() * 180 / Math.PI;
            liveHfov = currentView.fov() * 180 / Math.PI;
        }

        const payload = {
            title: sceneTitleInput.value,
            yaw_default: liveYaw,
            pitch_default: livePitch,
            hfov_default: liveHfov,
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

        loadScene(updatedScene.id);
        alert("Scene saved.");
    }

    function openHotspotModal(position) {
        pendingHotspotPosition = position;
        hotspotLabel.value = "";
        hotspotTooltip.value = "";
        hotspotTitle.value = "";
        hotspotDescription.value = "";
        hotspotTargetScene.value = "";
        hotspotType.value = currentTool === "navigate" ? "navigate" : "info";
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

        loadScene(currentSceneId);
        closeHotspotModalFn();
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

        loadScene(currentSceneId);
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

    toolButtons.forEach(btn => {
        btn.addEventListener("click", () => setActiveTool(btn.dataset.tool));
    });

    panoramaViewer?.addEventListener("click", (e) => {
        if (!currentView) return;
        if (currentTool !== "hotspot" && currentTool !== "navigate") return;

        const rect = panoramaViewer.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const coords = currentView.screenToCoordinates({ x, y });
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
        card.addEventListener("click", () => loadScene(card.dataset.sceneId));
    });

    if (scenesData.length > 0) {
        loadScene(scenesData[0].id);
    }
});