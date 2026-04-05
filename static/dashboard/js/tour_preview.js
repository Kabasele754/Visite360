document.addEventListener("DOMContentLoaded", () => {
    const scenes = JSON.parse(document.getElementById("preview-scenes-data").textContent || "[]");
    const previewViewerEl = document.getElementById("previewViewer");

    let viewer = null;
    let currentScene = null;

    function findScene(sceneId) {
        return scenes.find(scene => String(scene.id) === String(sceneId));
    }

    function renderScene(sceneId) {
        const scene = findScene(sceneId);
        if (!scene || !scene.image_360_url) return;

        previewViewerEl.innerHTML = "";

        if (!viewer) {
            viewer = new Marzipano.Viewer(previewViewerEl, {
                controls: { mouseViewMode: "drag" }
            });
        }

        const source = Marzipano.ImageUrlSource.fromString(scene.image_360_url);
        const geometry = new Marzipano.EquirectGeometry([{ width: 4000 }]);
        const limiter = Marzipano.RectilinearView.limit.traditional(4096, 100 * Math.PI / 180);
        const view = new Marzipano.RectilinearView(
            { yaw: 0, pitch: 0, fov: 100 * Math.PI / 180 },
            limiter
        );

        currentScene = viewer.createScene({
            source,
            geometry,
            view,
            pinFirstLevel: true
        });

        currentScene.switchTo();

        (scene.hotspots || []).forEach(hotspot => {
            const el = document.createElement("div");
            el.className = "preview-hotspot";
            el.textContent = hotspot.type === "navigate" ? "➜" : "i";
            el.title = hotspot.label || "Hotspot";

            el.addEventListener("click", () => {
                if (hotspot.type === "navigate" && hotspot.target_scene) {
                    renderScene(hotspot.target_scene);
                } else {
                    alert(hotspot.title || hotspot.description || hotspot.label || "Hotspot");
                }
            });

            currentScene.hotspotContainer().createHotspot(el, {
                yaw: hotspot.yaw,
                pitch: hotspot.pitch
            });
        });
    }

    if (scenes.length > 0) {
        renderScene(scenes[0].id);
    }

    document.getElementById("previewFullscreenBtn")?.addEventListener("click", () => {
        if (previewViewerEl.requestFullscreen) {
            previewViewerEl.requestFullscreen();
        }
    });
});