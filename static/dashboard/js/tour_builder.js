document.addEventListener("DOMContentLoaded", () => {
    const scenesData = JSON.parse(
        document.getElementById("scenes-data")?.textContent || "[]"
    );

    const sceneCards = document.querySelectorAll(".scene-card");
    const sceneTitleInput = document.getElementById("sceneTitle");
    const yawInput = document.getElementById("yawDefault");
    const pitchInput = document.getElementById("pitchDefault");
    const hfovInput = document.getElementById("hfovDefault");
    const viewerSceneTitle = document.getElementById("viewerSceneTitle");
    const activeSceneLabel = document.getElementById("activeSceneLabel");

    let currentSceneId = null;

    function findScene(sceneId) {
        return scenesData.find(scene => String(scene.id) === String(sceneId));
    }

    function setActiveCard(sceneId) {
        document.querySelectorAll(".scene-card").forEach(card => {
            card.classList.toggle("active", String(card.dataset.sceneId) === String(sceneId));
        });
    }

    function loadScene(sceneId) {
        const scene = findScene(sceneId);
        if (!scene) return;

        currentSceneId = scene.id;
        setActiveCard(scene.id);

        sceneTitleInput.value = scene.title || "";
        yawInput.value = scene.yaw_default ?? 0;
        pitchInput.value = scene.pitch_default ?? 0;
        hfovInput.value = scene.hfov_default ?? 100;

        viewerSceneTitle.textContent = `Scene active: ${scene.title}`;
        activeSceneLabel.textContent = scene.title;

        const viewer = document.getElementById("panoramaViewer");
        if (scene.image_360_url) {
            viewer.style.backgroundImage = `linear-gradient(rgba(10,12,18,0.20), rgba(10,12,18,0.35)), url('${scene.image_360_url}')`;
            viewer.style.backgroundSize = "cover";
            viewer.style.backgroundPosition = "center";
        }
    }

    sceneCards.forEach(card => {
        card.addEventListener("click", () => {
            loadScene(card.dataset.sceneId);
        });
    });

    document.getElementById("saveSceneBtn")?.addEventListener("click", () => {
        if (!currentSceneId) {
            alert("Sélectionne une scène d'abord.");
            return;
        }

        alert(`Scene ${currentSceneId} prête à être sauvegardée via API.`);
    });

    document.getElementById("addSceneBtn")?.addEventListener("click", () => {
        alert("Ici on ouvrira un modal pour upload une nouvelle scène.");
    });

    document.getElementById("saveDraftBtn")?.addEventListener("click", () => {
        alert("Save Draft branché plus tard sur l'API.");
    });

    document.getElementById("previewBtn")?.addEventListener("click", () => {
        alert("Preview branché plus tard.");
    });

    document.getElementById("publishBtn")?.addEventListener("click", () => {
        alert("Publish branché plus tard sur l'API.");
    });

    if (scenesData.length > 0) {
        loadScene(scenesData[0].id);
    }
});