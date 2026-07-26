/* =====================================================================
   TWINSCOPE PREVIEW — SPATIAL RECONSTRUCTION + LOCATION V26

   Modes:
   - Tour map: a real Three.js scene graph built from scene connections.
   - Point cloud: depth-projected panorama pixels rendered as 3D points.
   - Depth mesh: depth-projected panorama surface with discontinuity filtering.
   - 360°: conventional panorama fallback.

   A single panorama cannot provide a complete metric model. The depth modes
   require a generated relative depth map. The tour map works immediately and
   uses the actual navigation graph instead of displaying the panorama again.
===================================================================== */
(function () {
    "use strict";

    const config = window.PREVIEW_CONFIG || {};
    const sceneDataElement = document.getElementById("preview-scenes-data");
    const locationDataElement = document.getElementById(
        config.mapLocationElementId || "preview-location-data"
    );

    const safeJson = (element, fallback) => {
        if (!element) return fallback;
        try {
            return JSON.parse(element.textContent || "");
        } catch (_) {
            return fallback;
        }
    };

    const scenes = safeJson(sceneDataElement, []);
    const locationData = safeJson(locationDataElement, {});

    const spatialButton = document.getElementById("previewSpatial3DBtn");
    const spatialModal = document.getElementById("previewSpatialModal");
    const spatialCanvasHost = document.getElementById("previewSpatialCanvasHost");
    const spatialLoading = document.getElementById("previewSpatialLoading");
    const spatialError = document.getElementById("previewSpatialError");
    const spatialSceneLabel = document.getElementById("previewSpatialSceneLabel");
    const spatialSceneSelect = document.getElementById("previewSpatialSceneSelect");
    const spatialMotionButton = document.getElementById("previewSpatialMotionBtn");
    const spatialStepButton = document.getElementById("previewSpatialStepBtn");
    const spatialResetButton = document.getElementById("previewSpatialResetBtn");
    const spatialModeBadge = document.getElementById("previewSpatialModeBadge");
    const spatialHint = document.getElementById("previewSpatialHint");
    const spatialModeButtons = Array.from(
        document.querySelectorAll("[data-spatial-mode]")
    );

    const locationButton = document.getElementById("previewLocation3DBtn");
    const locationModal = document.getElementById("previewLocationModal");
    const locationMapHost = document.getElementById("previewLocationMap");
    const locationState = document.getElementById("previewLocationState");
    const locationSummary = document.getElementById("previewLocationSummary");
    const locationDistance = document.getElementById("previewLocationDistance");
    const locationHint = document.getElementById("previewLocationHint");
    const locateMeButton = document.getElementById("previewLocateMeBtn");
    const mapModeButton = document.getElementById("previewMapModeBtn");
    const mapResetButton = document.getElementById("previewMapResetBtn");

    let previousFocus = null;
    let currentSceneId = null;
    let threeModulePromise = null;
    let googleMapsPromise = null;

    const MODE = Object.freeze({
        GRAPH: "graph",
        POINTS: "pointcloud",
        MESH: "mesh",
        PANORAMA: "panorama",
    });

    const spatial = {
        THREE: null,
        renderer: null,
        scene: null,
        camera: null,
        root: null,
        frameId: null,
        resizeObserver: null,
        currentScene: null,
        currentMode: MODE.GRAPH,
        requestedMode: MODE.GRAPH,
        motionEnabled: false,
        motionHandler: null,
        motionYaw: 0,
        motionPitch: 0,
        yaw: 0,
        pitch: 0,
        fov: 68,
        graphDistance: 13,
        graphTarget: null,
        pointerDown: false,
        pointerMoved: false,
        pointerStartX: 0,
        pointerStartY: 0,
        yawStart: 0,
        pitchStart: 0,
        pointerId: null,
        parallaxX: 0,
        parallaxY: 0,
        translation: null,
        keys: new Set(),
        loadToken: 0,
        raycaster: null,
        pickables: [],
        hovered: null,
        nodeObjects: [],
    };

    const mapState = {
        mode3D: Boolean(config.googleMaps3DEnabled),
        map: null,
        marker: null,
        userMarker: null,
        map3DClasses: null,
        isReady: false,
    };

    const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
    const sceneKey = (scene) => String(scene?.id ?? scene?.scene_id ?? "");

    function currentSceneFromUrl() {
        const requested = new URLSearchParams(window.location.search).get("s");
        if (requested) {
            return scenes.find((scene) =>
                String(scene.id) === String(requested) ||
                String(scene.scene_id) === String(requested)
            ) || scenes[0] || null;
        }
        return scenes[0] || null;
    }

    function findScene(sceneId) {
        return scenes.find((scene) =>
            String(scene.id) === String(sceneId) ||
            String(scene.scene_id) === String(sceneId)
        ) || null;
    }

    function sceneImageUrl(scene) {
        const assets = scene?.assets || {};
        return (
            assets.original ||
            assets.viewer_desktop ||
            scene?.image_360_url ||
            assets.viewer_mobile ||
            scene?.image_360_mobile_url ||
            assets.light ||
            scene?.image_360_preview_url ||
            ""
        );
    }

    function sceneThumbnailUrl(scene) {
        const assets = scene?.assets || {};
        return (
            assets.thumbnail ||
            scene?.thumbnail_url ||
            assets.light ||
            scene?.image_360_preview_url ||
            assets.viewer_mobile ||
            scene?.image_360_mobile_url ||
            sceneImageUrl(scene)
        );
    }

    function sceneDepthUrl(scene) {
        return scene?.spatial?.depth_map_url || "";
    }

    function setStateVisibility(element, visible) {
        if (!element) return;
        element.hidden = !visible;
    }

    function showSpatialLoading(message, detail) {
        if (spatialLoading) {
            const strong = spatialLoading.querySelector("strong");
            const small = spatialLoading.querySelector("small");
            if (strong && message) strong.textContent = message;
            if (small && detail) small.textContent = detail;
        }
        setStateVisibility(spatialLoading, true);
        setStateVisibility(spatialError, false);
    }

    function showSpatialError(message, detail) {
        if (spatialError) {
            const strong = spatialError.querySelector("strong");
            const small = spatialError.querySelector("small");
            if (strong && message) strong.textContent = message;
            if (small && detail) small.textContent = detail;
        }
        setStateVisibility(spatialLoading, false);
        setStateVisibility(spatialError, true);
    }

    function hideSpatialState() {
        setStateVisibility(spatialLoading, false);
        setStateVisibility(spatialError, false);
    }

    function setSpatialHint(title, detail) {
        if (!spatialHint) return;
        const strong = spatialHint.querySelector("strong");
        const span = spatialHint.querySelector("span");
        if (strong) strong.textContent = title || "";
        if (span) span.textContent = detail || "";
    }

    function openModal(modal, firstFocus) {
        if (!modal) return;
        closeModal(spatialModal === modal ? locationModal : spatialModal, { restoreFocus: false });
        previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
        modal.removeAttribute("inert");
        modal.setAttribute("aria-hidden", "false");
        modal.classList.add("open");
        document.body.classList.add("preview-experience-open");
        window.requestAnimationFrame(() => firstFocus?.focus?.({ preventScroll: true }));
    }

    function closeModal(modal, options = {}) {
        if (!modal || !modal.classList.contains("open")) return;
        modal.classList.remove("open");
        modal.setAttribute("aria-hidden", "true");
        modal.setAttribute("inert", "");
        if (!document.querySelector(".preview-experience-modal.open")) {
            document.body.classList.remove("preview-experience-open");
        }
        if (options.restoreFocus !== false) {
            previousFocus?.focus?.({ preventScroll: true });
        }
    }

    function populateSpatialSceneSelect() {
        if (!spatialSceneSelect) return;
        spatialSceneSelect.innerHTML = "";
        scenes.forEach((scene, index) => {
            const option = document.createElement("option");
            option.value = sceneKey(scene) || String(index);
            option.textContent = scene.title || `Scene ${index + 1}`;
            spatialSceneSelect.appendChild(option);
        });
    }

    function loadThreeModule() {
        if (!threeModulePromise) {
            const moduleUrl = String(
                config.threeModuleUrl ||
                "https://cdn.jsdelivr.net/npm/three@0.185.1/build/three.module.js"
            ).trim();
            threeModulePromise = import(moduleUrl);
        }
        return threeModulePromise;
    }

    function spatialSize() {
        const rect = spatialCanvasHost?.getBoundingClientRect();
        return {
            width: Math.max(1, Math.round(rect?.width || 1)),
            height: Math.max(1, Math.round(rect?.height || 1)),
        };
    }

    function resizeSpatialRenderer() {
        if (!spatial.renderer || !spatial.camera || !spatialCanvasHost) return;
        const { width, height } = spatialSize();
        spatial.renderer.setSize(width, height, false);
        spatial.camera.aspect = width / height;
        spatial.camera.updateProjectionMatrix();
    }

    function disposeMaterial(material) {
        if (!material) return;
        const materials = Array.isArray(material) ? material : [material];
        materials.forEach((item) => {
            ["map", "alphaMap", "normalMap", "roughnessMap", "metalnessMap"].forEach((key) => {
                item?.[key]?.dispose?.();
            });
            item?.dispose?.();
        });
    }

    function clearSpatialRoot() {
        if (!spatial.root || !spatial.scene) return;
        spatial.root.traverse((object) => {
            object.geometry?.dispose?.();
            disposeMaterial(object.material);
        });
        spatial.scene.remove(spatial.root);
        spatial.root = null;
        spatial.pickables = [];
        spatial.nodeObjects = [];
        spatial.hovered = null;
    }

    function attachSpatialPointerControls(canvas) {
        canvas.addEventListener("pointerdown", (event) => {
            spatial.pointerDown = true;
            spatial.pointerMoved = false;
            spatial.pointerId = event.pointerId;
            spatial.pointerStartX = event.clientX;
            spatial.pointerStartY = event.clientY;
            spatial.yawStart = spatial.yaw;
            spatial.pitchStart = spatial.pitch;
            canvas.setPointerCapture?.(event.pointerId);
        });

        canvas.addEventListener("pointermove", (event) => {
            const rect = canvas.getBoundingClientRect();
            spatial.parallaxX = ((event.clientX - rect.left) / Math.max(rect.width, 1) - .5) * 2;
            spatial.parallaxY = ((event.clientY - rect.top) / Math.max(rect.height, 1) - .5) * 2;

            if (spatial.currentMode === MODE.GRAPH) {
                updateGraphHover(event);
            }

            if (!spatial.pointerDown || spatial.motionEnabled) return;
            const dx = event.clientX - spatial.pointerStartX;
            const dy = event.clientY - spatial.pointerStartY;
            if (Math.abs(dx) + Math.abs(dy) > 5) spatial.pointerMoved = true;
            const sensitivity = window.matchMedia("(max-width: 760px)").matches ? .0043 : .0034;
            spatial.yaw = spatial.yawStart - dx * sensitivity;
            spatial.pitch = clamp(
                spatial.pitchStart + dy * sensitivity,
                -Math.PI / 2 + .08,
                Math.PI / 2 - .08
            );
        });

        const release = (event) => {
            const shouldPick = spatial.pointerDown && !spatial.pointerMoved && spatial.currentMode === MODE.GRAPH;
            spatial.pointerDown = false;
            if (shouldPick) pickGraphNode(event);
        };
        canvas.addEventListener("pointerup", release);
        canvas.addEventListener("pointercancel", () => { spatial.pointerDown = false; });
        canvas.addEventListener("pointerleave", () => { spatial.pointerDown = false; });

        canvas.addEventListener("wheel", (event) => {
            event.preventDefault();
            if (spatial.currentMode === MODE.GRAPH) {
                spatial.graphDistance = clamp(
                    spatial.graphDistance + (event.deltaY > 0 ? .8 : -.8),
                    5.5,
                    32
                );
            } else {
                spatial.fov = clamp(spatial.fov + (event.deltaY > 0 ? 3 : -3), 34, 94);
                if (spatial.camera) {
                    spatial.camera.fov = spatial.fov;
                    spatial.camera.updateProjectionMatrix();
                }
            }
        }, { passive: false });
    }

    async function ensureSpatialRenderer() {
        if (spatial.renderer) return;
        const THREE = await loadThreeModule();
        spatial.THREE = THREE;
        if (!spatialCanvasHost) throw new Error("Spatial canvas host is unavailable");

        const renderer = new THREE.WebGLRenderer({
            antialias: true,
            alpha: false,
            powerPreference: "high-performance",
            preserveDrawingBuffer: false,
        });
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.65));
        renderer.domElement.setAttribute("aria-label", "Interactive Three.js spatial reconstruction");
        spatialCanvasHost.replaceChildren(renderer.domElement);

        spatial.renderer = renderer;
        spatial.scene = new THREE.Scene();
        spatial.scene.background = new THREE.Color(0x01040b);
        spatial.scene.fog = new THREE.FogExp2(0x01040b, .018);
        spatial.camera = new THREE.PerspectiveCamera(spatial.fov, 1, .01, 120);
        spatial.camera.position.set(0, 0, 0);
        spatial.translation = new THREE.Vector3();
        spatial.graphTarget = new THREE.Vector3();
        spatial.raycaster = new THREE.Raycaster();

        attachSpatialPointerControls(renderer.domElement);
        resizeSpatialRenderer();
        if (window.ResizeObserver) {
            spatial.resizeObserver = new ResizeObserver(resizeSpatialRenderer);
            spatial.resizeObserver.observe(spatialCanvasHost);
        } else {
            window.addEventListener("resize", resizeSpatialRenderer);
        }
        startSpatialLoop();
    }

    function cameraDirection() {
        const THREE = spatial.THREE;
        const yaw = spatial.motionEnabled ? spatial.motionYaw : spatial.yaw;
        const pitch = spatial.motionEnabled ? spatial.motionPitch : spatial.pitch;
        return new THREE.Vector3(
            Math.sin(yaw) * Math.cos(pitch),
            Math.sin(pitch),
            Math.cos(yaw) * Math.cos(pitch)
        ).normalize();
    }

    function updateWalkFromKeys() {
        if (!spatial.translation || spatial.currentMode === MODE.GRAPH) return;
        if (!spatial.keys.size) return;
        const direction = cameraDirection();
        const right = new spatial.THREE.Vector3(direction.z, 0, -direction.x).normalize();
        const forward = new spatial.THREE.Vector3(direction.x, 0, direction.z).normalize();
        const velocity = .035;
        if (spatial.keys.has("w") || spatial.keys.has("arrowup")) spatial.translation.addScaledVector(forward, velocity);
        if (spatial.keys.has("s") || spatial.keys.has("arrowdown")) spatial.translation.addScaledVector(forward, -velocity);
        if (spatial.keys.has("a") || spatial.keys.has("arrowleft")) spatial.translation.addScaledVector(right, -velocity);
        if (spatial.keys.has("d") || spatial.keys.has("arrowright")) spatial.translation.addScaledVector(right, velocity);
        const maxMove = spatial.currentMode === MODE.PANORAMA ? .05 : 1.35;
        if (spatial.translation.length() > maxMove) spatial.translation.setLength(maxMove);
    }

    function startSpatialLoop() {
        if (spatial.frameId) return;
        const render = () => {
            spatial.frameId = window.requestAnimationFrame(render);
            if (!spatial.renderer || !spatial.scene || !spatial.camera || !spatialModal?.classList.contains("open")) {
                return;
            }

            const THREE = spatial.THREE;
            if (spatial.currentMode === MODE.GRAPH) {
                const distance = spatial.graphDistance;
                const cp = Math.cos(spatial.pitch);
                spatial.camera.position.set(
                    spatial.graphTarget.x + Math.sin(spatial.yaw) * cp * distance,
                    spatial.graphTarget.y + Math.sin(spatial.pitch) * distance,
                    spatial.graphTarget.z + Math.cos(spatial.yaw) * cp * distance
                );
                spatial.camera.lookAt(spatial.graphTarget);
                spatial.nodeObjects.forEach((object) => {
                    if (object.userData?.billboard) object.quaternion.copy(spatial.camera.quaternion);
                });
            } else {
                updateWalkFromKeys();
                const direction = cameraDirection();
                spatial.camera.position.lerp(spatial.translation, .16);
                const target = spatial.camera.position.clone().add(direction);
                spatial.camera.lookAt(target);
            }
            spatial.renderer.render(spatial.scene, spatial.camera);
        };
        spatial.frameId = window.requestAnimationFrame(render);
    }

    async function loadTexture(url, { color = true } = {}) {
        const THREE = spatial.THREE;
        const loader = new THREE.TextureLoader();
        loader.setCrossOrigin("anonymous");
        const texture = await loader.loadAsync(url);
        texture.colorSpace = color ? THREE.SRGBColorSpace : THREE.NoColorSpace;
        texture.minFilter = THREE.LinearFilter;
        texture.magFilter = THREE.LinearFilter;
        texture.generateMipmaps = false;
        return texture;
    }

    function imagePixels(image, width, height) {
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const context = canvas.getContext("2d", { willReadFrequently: true });
        if (!context) throw new Error("Canvas pixel access is unavailable");
        context.drawImage(image, 0, 0, width, height);
        return context.getImageData(0, 0, width, height).data;
    }

    function depthDistance(byteValue) {
        const raw = clamp(Number(byteValue || 0) / 255, 0, 1);
        const farFactor = config.spatialDepthInvert === false ? raw : 1 - raw;
        const shaped = Math.pow(farFactor, 1.12);
        return 2.25 + shaped * 8.2;
    }

    function pointMaterial() {
        const THREE = spatial.THREE;
        return new THREE.ShaderMaterial({
            vertexColors: true,
            transparent: true,
            depthWrite: false,
            blending: THREE.NormalBlending,
            uniforms: { pointScale: { value: window.matchMedia("(max-width: 760px)").matches ? 8.5 : 10.5 } },
            vertexShader: `
                uniform float pointScale;
                varying vec3 vColor;
                void main() {
                    vColor = color;
                    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
                    gl_PointSize = clamp(pointScale * (3.4 / max(0.5, -mvPosition.z)), 1.2, 8.0);
                    gl_Position = projectionMatrix * mvPosition;
                }
            `,
            fragmentShader: `
                varying vec3 vColor;
                void main() {
                    vec2 c = gl_PointCoord - vec2(0.5);
                    float d = dot(c, c);
                    if (d > 0.25) discard;
                    float alpha = smoothstep(0.25, 0.08, d);
                    gl_FragColor = vec4(vColor, alpha * 0.96);
                }
            `,
        });
    }

    async function buildPointCloud(scene) {
        const imageUrl = sceneImageUrl(scene);
        const depthUrl = sceneDepthUrl(scene);
        if (!imageUrl || !depthUrl) throw new Error("Depth data is unavailable");

        const [panoramaTexture, depthTexture] = await Promise.all([
            loadTexture(imageUrl, { color: true }),
            loadTexture(depthUrl, { color: false }),
        ]);
        const budget = Math.max(8000, Number(config.spatialPointBudget || 42000));
        const mobileFactor = window.matchMedia("(max-width: 760px)").matches ? .68 : 1;
        const width = Math.max(128, Math.round(Math.sqrt(budget * 2 * mobileFactor)));
        const height = Math.max(64, Math.round(width / 2));
        const colorData = imagePixels(panoramaTexture.image, width, height);
        const depthData = imagePixels(depthTexture.image, width, height);

        const positions = new Float32Array(width * height * 3);
        const colors = new Float32Array(width * height * 3);
        let cursor = 0;
        for (let y = 0; y < height; y += 1) {
            const v = (y + .5) / height;
            const latitude = (.5 - v) * Math.PI;
            const cosLat = Math.cos(latitude);
            for (let x = 0; x < width; x += 1) {
                const u = (x + .5) / width;
                const longitude = (u - .5) * Math.PI * 2;
                const pixel = (y * width + x) * 4;
                const radius = depthDistance(depthData[pixel]);
                positions[cursor] = Math.sin(longitude) * cosLat * radius;
                positions[cursor + 1] = Math.sin(latitude) * radius;
                positions[cursor + 2] = Math.cos(longitude) * cosLat * radius;
                colors[cursor] = colorData[pixel] / 255;
                colors[cursor + 1] = colorData[pixel + 1] / 255;
                colors[cursor + 2] = colorData[pixel + 2] / 255;
                cursor += 3;
            }
        }

        const geometry = new spatial.THREE.BufferGeometry();
        geometry.setAttribute("position", new spatial.THREE.BufferAttribute(positions, 3));
        geometry.setAttribute("color", new spatial.THREE.BufferAttribute(colors, 3));
        geometry.computeBoundingSphere();
        const points = new spatial.THREE.Points(geometry, pointMaterial());
        const root = new spatial.THREE.Group();
        root.add(points);

        panoramaTexture.dispose();
        depthTexture.dispose();
        return root;
    }

    async function buildDepthMesh(scene) {
        const imageUrl = sceneImageUrl(scene);
        const depthUrl = sceneDepthUrl(scene);
        if (!imageUrl || !depthUrl) throw new Error("Depth data is unavailable");

        const [panoramaTexture, depthTexture] = await Promise.all([
            loadTexture(imageUrl, { color: true }),
            loadTexture(depthUrl, { color: false }),
        ]);
        const requestedSegments = Math.max(96, Number(config.spatialMeshSegments || 220));
        const width = window.matchMedia("(max-width: 760px)").matches
            ? Math.min(160, requestedSegments)
            : Math.min(280, requestedSegments);
        const height = Math.round(width / 2);
        const depthData = imagePixels(depthTexture.image, width, height);
        const vertexWidth = width + 1;
        const positions = new Float32Array(vertexWidth * (height + 1) * 3);
        const uvs = new Float32Array(vertexWidth * (height + 1) * 2);
        const radii = new Float32Array(vertexWidth * (height + 1));

        let p = 0;
        let t = 0;
        for (let y = 0; y <= height; y += 1) {
            const v = y / height;
            const sampleY = Math.min(height - 1, y);
            const latitude = (.5 - v) * Math.PI;
            const cosLat = Math.cos(latitude);
            for (let x = 0; x <= width; x += 1) {
                const u = x / width;
                const sampleX = x === width ? 0 : x;
                const longitude = (u - .5) * Math.PI * 2;
                const pixel = (sampleY * width + sampleX) * 4;
                const radius = depthDistance(depthData[pixel]);
                const vertexIndex = y * vertexWidth + x;
                radii[vertexIndex] = radius;
                positions[p] = Math.sin(longitude) * cosLat * radius;
                positions[p + 1] = Math.sin(latitude) * radius;
                positions[p + 2] = Math.cos(longitude) * cosLat * radius;
                p += 3;
                uvs[t] = u;
                uvs[t + 1] = 1 - v;
                t += 2;
            }
        }

        const indices = [];
        const threshold = 1.6;
        for (let y = 0; y < height; y += 1) {
            for (let x = 0; x < width; x += 1) {
                const a = y * vertexWidth + x;
                const b = a + 1;
                const c = a + vertexWidth;
                const d = c + 1;
                const values = [radii[a], radii[b], radii[c], radii[d]];
                const spread = Math.max(...values) - Math.min(...values);
                if (spread > threshold) continue;
                indices.push(a, c, b, b, c, d);
            }
        }

        const geometry = new spatial.THREE.BufferGeometry();
        geometry.setAttribute("position", new spatial.THREE.BufferAttribute(positions, 3));
        geometry.setAttribute("uv", new spatial.THREE.BufferAttribute(uvs, 2));
        geometry.setIndex(indices);
        geometry.computeVertexNormals();
        const material = new spatial.THREE.MeshBasicMaterial({
            map: panoramaTexture,
            side: spatial.THREE.DoubleSide,
        });
        const mesh = new spatial.THREE.Mesh(geometry, material);
        const edgePoints = new spatial.THREE.Points(
            geometry.clone(),
            new spatial.THREE.PointsMaterial({
                size: .018,
                color: 0x67e8f9,
                transparent: true,
                opacity: .16,
                depthWrite: false,
            })
        );
        const root = new spatial.THREE.Group();
        root.add(mesh, edgePoints);
        depthTexture.dispose();
        return root;
    }

    async function buildPanorama(scene) {
        const imageUrl = sceneImageUrl(scene);
        if (!imageUrl) throw new Error("Panorama is unavailable");
        const texture = await loadTexture(imageUrl, { color: true });
        const geometry = new spatial.THREE.SphereGeometry(10, 96, 64);
        geometry.scale(-1, 1, 1);
        const material = new spatial.THREE.MeshBasicMaterial({ map: texture });
        const root = new spatial.THREE.Group();
        root.add(new spatial.THREE.Mesh(geometry, material));
        return root;
    }

    function makeTextSprite(text, options = {}) {
        const THREE = spatial.THREE;
        const canvas = document.createElement("canvas");
        canvas.width = 768;
        canvas.height = 180;
        const ctx = canvas.getContext("2d");
        const active = Boolean(options.active);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = active ? "rgba(8,145,178,.96)" : "rgba(2,6,23,.90)";
        ctx.strokeStyle = active ? "rgba(103,232,249,.95)" : "rgba(148,163,184,.45)";
        ctx.lineWidth = 5;
        const radius = 38;
        ctx.beginPath();
        ctx.roundRect(4, 4, canvas.width - 8, canvas.height - 8, radius);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = "#ffffff";
        ctx.font = "800 48px system-ui, -apple-system, sans-serif";
        ctx.textBaseline = "middle";
        const value = String(text || "Scene");
        const maxWidth = canvas.width - 86;
        let display = value;
        while (ctx.measureText(display).width > maxWidth && display.length > 8) {
            display = `${display.slice(0, -2)}…`;
        }
        ctx.fillText(display, 44, canvas.height / 2);
        const texture = new THREE.CanvasTexture(canvas);
        texture.colorSpace = THREE.SRGBColorSpace;
        const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: true });
        const sprite = new THREE.Sprite(material);
        sprite.scale.set(3.45, .81, 1);
        sprite.userData.billboard = true;
        return sprite;
    }

    function buildGraphLinks(sceneSubset) {
        const allowed = new Set(sceneSubset.map(sceneKey));
        const links = [];
        const seen = new Set();
        sceneSubset.forEach((scene) => {
            const from = sceneKey(scene);
            (scene.hotspots || []).forEach((hotspot) => {
                const target = findScene(hotspot.target_scene_id ?? hotspot.target_scene);
                const to = sceneKey(target);
                if (!from || !to || from === to || !allowed.has(to)) return;
                const pair = [from, to].sort().join("::");
                if (seen.has(pair)) return;
                seen.add(pair);
                links.push({ from, to, source: hotspot.is_ai_generated ? "ai" : "manual" });
            });
        });
        if (!links.length) {
            for (let index = 0; index < sceneSubset.length - 1; index += 1) {
                links.push({
                    from: sceneKey(sceneSubset[index]),
                    to: sceneKey(sceneSubset[index + 1]),
                    source: "sequence",
                });
            }
        }
        return links;
    }

    function graphSceneSubset() {
        const limit = Math.max(8, Number(config.spatialGraphMaxNodes || 48));
        if (scenes.length <= limit) return scenes.slice();
        const current = findScene(currentSceneId) || currentSceneFromUrl();
        const ordered = [];
        const used = new Set();
        const add = (scene) => {
            const key = sceneKey(scene);
            if (!scene || !key || used.has(key) || ordered.length >= limit) return;
            used.add(key);
            ordered.push(scene);
        };
        add(current);
        (current?.hotspots || []).forEach((hotspot) => add(findScene(hotspot.target_scene_id ?? hotspot.target_scene)));
        scenes.forEach(add);
        return ordered;
    }

    function graphLayout(sceneSubset, links) {
        const currentKey = sceneKey(findScene(currentSceneId) || sceneSubset[0]);
        const adjacency = new Map(sceneSubset.map((scene) => [sceneKey(scene), []]));
        links.forEach((link) => {
            adjacency.get(link.from)?.push(link.to);
            adjacency.get(link.to)?.push(link.from);
        });
        const levels = new Map();
        const queue = [currentKey];
        levels.set(currentKey, 0);
        while (queue.length) {
            const key = queue.shift();
            const nextLevel = (levels.get(key) || 0) + 1;
            (adjacency.get(key) || []).forEach((neighbor) => {
                if (levels.has(neighbor)) return;
                levels.set(neighbor, nextLevel);
                queue.push(neighbor);
            });
        }
        let maxKnown = Math.max(0, ...Array.from(levels.values()));
        sceneSubset.forEach((scene) => {
            const key = sceneKey(scene);
            if (!levels.has(key)) levels.set(key, ++maxKnown);
        });
        const grouped = new Map();
        levels.forEach((level, key) => {
            if (!grouped.has(level)) grouped.set(level, []);
            grouped.get(level).push(key);
        });
        const positions = new Map();
        grouped.forEach((keys, level) => {
            if (level === 0) {
                positions.set(keys[0], new spatial.THREE.Vector3(0, .35, 0));
                return;
            }
            const radius = 4.3 + (level - 1) * 3.9;
            keys.forEach((key, index) => {
                const angle = (index / Math.max(1, keys.length)) * Math.PI * 2 + level * .62;
                positions.set(key, new spatial.THREE.Vector3(
                    Math.cos(angle) * radius,
                    ((index % 3) - 1) * .72 + Math.sin(level * .8) * .3,
                    Math.sin(angle) * radius
                ));
            });
        });
        return positions;
    }

    function addGraphEnvironment(root) {
        const THREE = spatial.THREE;
        const grid = new THREE.GridHelper(34, 34, 0x0e7490, 0x123047);
        grid.position.y = -2.25;
        grid.material.transparent = true;
        grid.material.opacity = .26;
        root.add(grid);

        const count = 600;
        const positions = new Float32Array(count * 3);
        for (let index = 0; index < count; index += 1) {
            const radius = 18 + Math.random() * 26;
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);
            positions[index * 3] = Math.sin(phi) * Math.cos(theta) * radius;
            positions[index * 3 + 1] = Math.cos(phi) * radius;
            positions[index * 3 + 2] = Math.sin(phi) * Math.sin(theta) * radius;
        }
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
        const material = new THREE.PointsMaterial({
            color: 0x67e8f9,
            size: .045,
            transparent: true,
            opacity: .38,
            depthWrite: false,
        });
        root.add(new THREE.Points(geometry, material));
    }

    async function createGraphNode(scene, position, active) {
        const THREE = spatial.THREE;
        const group = new THREE.Group();
        group.position.copy(position);
        group.userData.scene = scene;
        group.userData.billboard = true;

        const backing = new THREE.Mesh(
            new THREE.PlaneGeometry(active ? 3.25 : 2.85, active ? 1.92 : 1.68),
            new THREE.MeshBasicMaterial({
                color: active ? 0x06b6d4 : 0x071524,
                transparent: true,
                opacity: active ? .96 : .88,
                side: THREE.DoubleSide,
            })
        );
        backing.position.z = -.06;
        group.add(backing);

        const url = sceneThumbnailUrl(scene);
        if (url) {
            try {
                const texture = await loadTexture(url, { color: true });
                const image = new THREE.Mesh(
                    new THREE.PlaneGeometry(active ? 3.05 : 2.65, active ? 1.70 : 1.47),
                    new THREE.MeshBasicMaterial({ map: texture, side: THREE.DoubleSide })
                );
                image.userData.scene = scene;
                image.userData.pickable = true;
                group.add(image);
                spatial.pickables.push(image);
            } catch (_) {
                backing.userData.scene = scene;
                backing.userData.pickable = true;
                spatial.pickables.push(backing);
            }
        } else {
            backing.userData.scene = scene;
            backing.userData.pickable = true;
            spatial.pickables.push(backing);
        }

        const label = makeTextSprite(scene.title || "Scene", { active });
        label.position.set(0, active ? -1.23 : -1.05, .05);
        label.userData.scene = scene;
        label.userData.pickable = true;
        group.add(label);
        spatial.pickables.push(label);
        spatial.nodeObjects.push(group, label);
        return group;
    }

    async function buildTourGraph() {
        const THREE = spatial.THREE;
        const subset = graphSceneSubset();
        const links = buildGraphLinks(subset);
        const positions = graphLayout(subset, links);
        const root = new THREE.Group();
        addGraphEnvironment(root);

        links.forEach((link) => {
            const start = positions.get(link.from);
            const end = positions.get(link.to);
            if (!start || !end) return;
            const geometry = new THREE.BufferGeometry().setFromPoints([start, end]);
            const material = new THREE.LineBasicMaterial({
                color: link.source === "manual" ? 0x67e8f9 : 0x0891b2,
                transparent: true,
                opacity: link.source === "manual" ? .78 : .48,
            });
            root.add(new THREE.Line(geometry, material));
        });

        const activeKey = sceneKey(findScene(currentSceneId) || subset[0]);
        const nodes = await Promise.all(subset.map((scene) =>
            createGraphNode(scene, positions.get(sceneKey(scene)), sceneKey(scene) === activeKey)
        ));
        nodes.forEach((node) => root.add(node));
        return root;
    }

    function pointerNdc(event) {
        const rect = spatial.renderer.domElement.getBoundingClientRect();
        return new spatial.THREE.Vector2(
            ((event.clientX - rect.left) / rect.width) * 2 - 1,
            -((event.clientY - rect.top) / rect.height) * 2 + 1
        );
    }

    function graphIntersection(event) {
        if (!spatial.raycaster || !spatial.camera || !spatial.pickables.length) return null;
        spatial.raycaster.setFromCamera(pointerNdc(event), spatial.camera);
        return spatial.raycaster.intersectObjects(spatial.pickables, true)[0] || null;
    }

    function updateGraphHover(event) {
        if (!spatial.renderer) return;
        const intersection = graphIntersection(event);
        const next = intersection?.object || null;
        if (spatial.hovered === next) return;
        if (spatial.hovered?.parent) spatial.hovered.parent.scale.setScalar(1);
        spatial.hovered = next;
        if (next?.parent) next.parent.scale.setScalar(1.06);
        spatial.renderer.domElement.style.cursor = next ? "pointer" : (spatial.pointerDown ? "grabbing" : "grab");
    }

    function pickGraphNode(event) {
        const intersection = graphIntersection(event);
        const scene = intersection?.object?.userData?.scene || intersection?.object?.parent?.userData?.scene;
        if (!scene) return;
        currentSceneId = scene.id ?? scene.scene_id;
        spatial.currentScene = scene;
        if (spatialSceneSelect) spatialSceneSelect.value = String(currentSceneId);
        if (spatialSceneLabel) spatialSceneLabel.textContent = scene.title || "360° scene";
        window.dispatchEvent(new CustomEvent("twinscopes:navigate-scene", {
            detail: { sceneId: currentSceneId, title: scene.title || "", source: "spatial-map" },
        }));
        renderSpatialMode(MODE.GRAPH, scene, { preserveView: true });
    }

    function setModeBadge(mode) {
        if (!spatialModeBadge) return;
        const labels = {
            [MODE.GRAPH]: "SPATIAL TOUR MAP",
            [MODE.POINTS]: "DEPTH POINT CLOUD",
            [MODE.MESH]: "DEPTH SURFACE",
            [MODE.PANORAMA]: "360° PANORAMA",
        };
        spatialModeBadge.textContent = labels[mode] || "SPATIAL EXPERIENCE";
    }

    function setModeHint(mode) {
        if (mode === MODE.GRAPH) {
            setSpatialHint("Drag to orbit", "Click a scene card to navigate through the tour.");
        } else if (mode === MODE.POINTS) {
            setSpatialHint("Real depth parallax", "Drag to look, use WASD or Step to move inside the point cloud.");
        } else if (mode === MODE.MESH) {
            setSpatialHint("Depth-projected surface", "Move carefully: geometry is estimated from one panorama.");
        } else {
            setSpatialHint("360° fallback", "This mode displays the original panorama without reconstructed geometry.");
        }
    }

    function syncModeButtons(scene) {
        const depthReady = Boolean(sceneDepthUrl(scene));
        spatialModeButtons.forEach((button) => {
            const mode = button.dataset.spatialMode;
            const requiresDepth = mode === MODE.POINTS || mode === MODE.MESH;
            button.disabled = requiresDepth && !depthReady;
            button.setAttribute("aria-selected", String(mode === spatial.currentMode));
            button.classList.toggle("is-active", mode === spatial.currentMode);
            if (requiresDepth && !depthReady) {
                button.title = "Generate a depth map for this scene in the AI Tour Architect dashboard";
            }
        });
        if (spatialStepButton) spatialStepButton.disabled = spatial.currentMode === MODE.GRAPH;
        if (spatialMotionButton) spatialMotionButton.disabled = spatial.currentMode === MODE.GRAPH;
    }

    function resetSpatialView() {
        const scene = spatial.currentScene || currentSceneFromUrl();
        if (spatial.currentMode === MODE.GRAPH) {
            spatial.yaw = -.58;
            spatial.pitch = .25;
            spatial.graphDistance = scenes.length > 16 ? 18 : 13;
            spatial.graphTarget.set(0, 0, 0);
        } else {
            spatial.yaw = (Number(scene?.yaw_default || 0) * Math.PI) / 180;
            spatial.pitch = (Number(scene?.pitch_default || 0) * Math.PI) / 180;
            spatial.fov = clamp(Number(scene?.hfov_default || 72), 42, 88);
            spatial.camera.fov = spatial.fov;
            spatial.camera.updateProjectionMatrix();
            spatial.translation.set(0, 0, 0);
        }
        spatial.parallaxX = 0;
        spatial.parallaxY = 0;
    }

    async function renderSpatialMode(mode, scene, options = {}) {
        if (!scene && mode !== MODE.GRAPH) {
            showSpatialError("No scene is available", "Add a published 360° scene to use the spatial view.");
            return;
        }
        await ensureSpatialRenderer();
        const token = ++spatial.loadToken;
        spatial.requestedMode = mode;
        spatial.currentScene = scene || currentSceneFromUrl();
        currentSceneId = spatial.currentScene?.id ?? spatial.currentScene?.scene_id ?? currentSceneId;
        if (spatialSceneLabel) spatialSceneLabel.textContent = spatial.currentScene?.title || "Virtual tour";
        if (spatialSceneSelect && currentSceneId != null) spatialSceneSelect.value = String(currentSceneId);

        const depthReady = Boolean(sceneDepthUrl(spatial.currentScene));
        if ((mode === MODE.POINTS || mode === MODE.MESH) && !depthReady) {
            mode = scenes.length > 1 ? MODE.GRAPH : MODE.PANORAMA;
        }

        const loadingCopy = {
            [MODE.GRAPH]: ["Building the spatial tour map", "Connecting scenes from real navigation hotspots."],
            [MODE.POINTS]: ["Building the point cloud", "Projecting panorama pixels into estimated 3D depth."],
            [MODE.MESH]: ["Building the depth surface", "Creating a spatial mesh while protecting depth edges."],
            [MODE.PANORAMA]: ["Loading the panorama", "Preparing the standard 360° fallback."],
        };
        showSpatialLoading(...loadingCopy[mode]);

        try {
            let root;
            if (mode === MODE.GRAPH) root = await buildTourGraph();
            else if (mode === MODE.POINTS) root = await buildPointCloud(spatial.currentScene);
            else if (mode === MODE.MESH) root = await buildDepthMesh(spatial.currentScene);
            else root = await buildPanorama(spatial.currentScene);

            if (token !== spatial.loadToken) {
                root.traverse((object) => {
                    object.geometry?.dispose?.();
                    disposeMaterial(object.material);
                });
                return;
            }
            clearSpatialRoot();
            spatial.root = root;
            spatial.scene.add(root);
            spatial.currentMode = mode;
            setModeBadge(mode);
            setModeHint(mode);
            syncModeButtons(spatial.currentScene);
            if (!options.preserveView) resetSpatialView();
            hideSpatialState();
        } catch (error) {
            console.warn("Spatial reconstruction unavailable", error);
            if (mode !== MODE.GRAPH && scenes.length > 1) {
                await renderSpatialMode(MODE.GRAPH, spatial.currentScene);
                return;
            }
            showSpatialError(
                "Spatial reconstruction is temporarily unavailable",
                "The standard 360° tour remains available and no tour data was changed."
            );
        }
    }

    async function requestMotionPermission() {
        const requestPermission = window.DeviceOrientationEvent?.requestPermission;
        if (typeof requestPermission === "function") {
            const result = await requestPermission.call(window.DeviceOrientationEvent);
            if (result !== "granted") throw new Error("Device motion permission was not granted");
        }
    }

    async function toggleMotion() {
        if (!spatialMotionButton || spatial.currentMode === MODE.GRAPH) return;
        if (!spatial.motionEnabled) {
            try {
                await requestMotionPermission();
                spatial.motionHandler = (event) => {
                    if (event.alpha == null || event.beta == null) return;
                    spatial.motionYaw = (Number(event.alpha) * Math.PI) / 180;
                    spatial.motionPitch = clamp(
                        ((Number(event.beta) - 90) * Math.PI) / 180,
                        -Math.PI / 2 + .05,
                        Math.PI / 2 - .05
                    );
                };
                window.addEventListener("deviceorientation", spatial.motionHandler, true);
                spatial.motionEnabled = true;
            } catch (_) {
                spatial.motionEnabled = false;
            }
        } else {
            stopMotion();
        }
        spatialMotionButton.setAttribute("aria-pressed", String(spatial.motionEnabled));
    }

    function stopMotion() {
        if (spatial.motionHandler) {
            window.removeEventListener("deviceorientation", spatial.motionHandler, true);
        }
        spatial.motionHandler = null;
        spatial.motionEnabled = false;
        spatialMotionButton?.setAttribute("aria-pressed", "false");
    }

    function stepForward() {
        if (!spatial.translation || spatial.currentMode === MODE.GRAPH) return;
        const direction = cameraDirection();
        direction.y = 0;
        if (direction.lengthSq() < .001) return;
        direction.normalize();
        spatial.translation.addScaledVector(direction, .32);
        const maxMove = spatial.currentMode === MODE.PANORAMA ? .05 : 1.35;
        if (spatial.translation.length() > maxMove) spatial.translation.setLength(maxMove);
    }

    async function openSpatial() {
        if (!spatialModal) return;
        openModal(spatialModal, spatialModal.querySelector("[data-spatial-close]"));
        populateSpatialSceneSelect();
        const scene = findScene(currentSceneId) || currentSceneFromUrl();
        const defaultMode = scenes.length > 1
            ? MODE.GRAPH
            : (sceneDepthUrl(scene) ? MODE.POINTS : MODE.PANORAMA);
        await renderSpatialMode(defaultMode, scene);
    }

    function closeSpatial() {
        stopMotion();
        spatial.keys.clear();
        closeModal(spatialModal);
    }

    /* ----------------------------- Google Maps ----------------------------- */
    function loadGoogleMaps() {
        if (window.google?.maps?.importLibrary) return Promise.resolve(window.google.maps);
        if (googleMapsPromise) return googleMapsPromise;
        const key = String(config.googleMapsBrowserKey || "").trim();
        if (!key) return Promise.reject(new Error("Google Maps browser key is not configured"));

        googleMapsPromise = new Promise((resolve, reject) => {
            const script = document.createElement("script");
            const params = new URLSearchParams({
                key,
                loading: "async",
                v: "weekly",
                libraries: "maps3d,marker",
            });
            script.src = `https://maps.googleapis.com/maps/api/js?${params.toString()}`;
            script.async = true;
            script.onerror = () => reject(new Error("Google Maps could not be loaded"));
            script.onload = () => {
                if (window.google?.maps?.importLibrary) resolve(window.google.maps);
                else reject(new Error("Google Maps did not initialize"));
            };
            document.head.appendChild(script);
        });
        return googleMapsPromise;
    }

    function tourCoordinates() {
        const lat = Number(locationData.latitude);
        const lng = Number(locationData.longitude);
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
        return { lat, lng };
    }

    function showLocationState(title, detail, visible = true) {
        if (locationState) {
            const strong = locationState.querySelector("strong");
            const small = locationState.querySelector("small");
            if (strong) strong.textContent = title;
            if (small) small.textContent = detail;
            locationState.hidden = !visible;
        }
    }

    function clearMapHost() {
        if (locationMapHost) locationMapHost.replaceChildren();
        mapState.map = null;
        mapState.marker = null;
        mapState.userMarker = null;
        mapState.isReady = false;
    }

    async function build3DMap(coords) {
        const maps = await loadGoogleMaps();
        const library = await maps.importLibrary("maps3d");
        const Map3DElement = library.Map3DElement;
        const Marker3DElement = library.Marker3DElement;
        const MapMode = library.MapMode;
        if (!Map3DElement || !Marker3DElement) throw new Error("3D Maps is unavailable");

        const options = {
            center: { ...coords, altitude: 0 },
            range: 520,
            tilt: 67.5,
            heading: 0,
            mode: MapMode?.HYBRID || "HYBRID",
        };
        if (config.googleMaps3DMapId) options.mapId = config.googleMaps3DMapId;
        const map = new Map3DElement(options);
        const marker = new Marker3DElement({
            position: { ...coords, altitude: 0 },
            label: locationData.label || "Tour location",
            extruded: true,
        });
        map.append(marker);
        locationMapHost.replaceChildren(map);
        mapState.map = map;
        mapState.marker = marker;
        mapState.map3DClasses = { Marker3DElement };
        mapState.isReady = true;
    }

    async function build2DMap(coords) {
        const maps = await loadGoogleMaps();
        const { Map } = await maps.importLibrary("maps");
        const map = new Map(locationMapHost, {
            center: coords,
            zoom: 17,
            mapId: config.googleMaps3DMapId || undefined,
            mapTypeId: "hybrid",
            tilt: 45,
            heading: 0,
            fullscreenControl: false,
            streetViewControl: true,
            mapTypeControl: false,
        });
        let marker = null;
        try {
            const { AdvancedMarkerElement } = await maps.importLibrary("marker");
            marker = new AdvancedMarkerElement({ map, position: coords, title: locationData.label || "Tour location" });
        } catch (_) {
            if (window.google?.maps?.Marker) {
                marker = new window.google.maps.Marker({ map, position: coords, title: locationData.label || "Tour location" });
            }
        }
        mapState.map = map;
        mapState.marker = marker;
        mapState.isReady = true;
    }

    async function renderMap() {
        const coords = tourCoordinates();
        clearMapHost();
        if (!coords) {
            showLocationState(
                "Location coordinates are not available",
                "Add latitude and longitude to the Tour or Place in the dashboard.",
                true
            );
            if (locationSummary && locationData.address) locationSummary.textContent = locationData.address;
            return;
        }

        showLocationState("Preparing the location", "Loading an interactive map around this tour.", true);
        try {
            if (mapState.mode3D && config.googleMaps3DEnabled) {
                try {
                    await build3DMap(coords);
                } catch (_) {
                    mapState.mode3D = false;
                    await build2DMap(coords);
                }
            } else {
                await build2DMap(coords);
            }
            showLocationState("", "", false);
            syncMapModeButton();
            if (locationDistance) locationDistance.textContent = locationData.label || "Tour location";
            if (locationHint) locationHint.textContent = locationData.address || "Explore the surrounding area.";
        } catch (error) {
            console.warn("Location map unavailable", error);
            showLocationState(
                "The interactive map is not configured yet",
                "The tour location remains available in the information panel.",
                true
            );
        }
    }

    function syncMapModeButton() {
        if (!mapModeButton) return;
        mapModeButton.setAttribute("aria-pressed", String(mapState.mode3D));
        const label = mapModeButton.querySelector("span");
        if (label) label.textContent = mapState.mode3D ? "3D map" : "Satellite";
    }

    function resetMap() {
        const coords = tourCoordinates();
        if (!coords || !mapState.map) return;
        if (mapState.mode3D) {
            mapState.map.center = { ...coords, altitude: 0 };
            mapState.map.range = 520;
            mapState.map.tilt = 67.5;
            mapState.map.heading = 0;
        } else {
            mapState.map.setCenter?.(coords);
            mapState.map.setZoom?.(17);
            mapState.map.setTilt?.(45);
            mapState.map.setHeading?.(0);
        }
    }

    function haversineKm(a, b) {
        const radians = (value) => (value * Math.PI) / 180;
        const earth = 6371;
        const dLat = radians(b.lat - a.lat);
        const dLng = radians(b.lng - a.lng);
        const lat1 = radians(a.lat);
        const lat2 = radians(b.lat);
        const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
        return 2 * earth * Math.asin(Math.sqrt(h));
    }

    function bearingLabel(a, b) {
        const radians = (value) => (value * Math.PI) / 180;
        const degrees = (value) => (value * 180) / Math.PI;
        const y = Math.sin(radians(b.lng - a.lng)) * Math.cos(radians(b.lat));
        const x = Math.cos(radians(a.lat)) * Math.sin(radians(b.lat)) -
            Math.sin(radians(a.lat)) * Math.cos(radians(b.lat)) * Math.cos(radians(b.lng - a.lng));
        const bearing = (degrees(Math.atan2(y, x)) + 360) % 360;
        const labels = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"];
        return labels[Math.round(bearing / 45) % 8];
    }

    async function addUserMarker(position) {
        const coords = { lat: position.coords.latitude, lng: position.coords.longitude };
        const target = tourCoordinates();
        if (!target || !mapState.map) return;

        if (mapState.userMarker) {
            try { mapState.userMarker.remove?.(); } catch (_) {}
            try { mapState.userMarker.setMap?.(null); } catch (_) {}
        }

        try {
            if (mapState.mode3D && mapState.map3DClasses?.Marker3DElement) {
                const marker = new mapState.map3DClasses.Marker3DElement({
                    position: { ...coords, altitude: 0 },
                    label: "Your position",
                    extruded: true,
                });
                mapState.map.append(marker);
                mapState.userMarker = marker;
                mapState.map.center = { ...coords, altitude: 0 };
                mapState.map.range = 850;
            } else {
                const maps = await loadGoogleMaps();
                try {
                    const { AdvancedMarkerElement } = await maps.importLibrary("marker");
                    mapState.userMarker = new AdvancedMarkerElement({ map: mapState.map, position: coords, title: "Your position" });
                } catch (_) {
                    if (window.google?.maps?.Marker) {
                        mapState.userMarker = new window.google.maps.Marker({ map: mapState.map, position: coords, title: "Your position" });
                    }
                }
                mapState.map.panTo?.(coords);
            }
        } catch (_) {}

        const distance = haversineKm(coords, target);
        const direction = bearingLabel(coords, target);
        if (locationDistance) {
            locationDistance.textContent = distance < 1
                ? `${Math.round(distance * 1000)} m from this tour`
                : `${distance.toFixed(distance < 10 ? 1 : 0)} km from this tour`;
        }
        if (locationHint) locationHint.textContent = `The tour is ${direction} of your current position.`;
    }

    function locateVisitor() {
        if (!navigator.geolocation) {
            if (locationHint) locationHint.textContent = "Location services are not supported by this browser.";
            return;
        }
        if (locationHint) locationHint.textContent = "Requesting your location…";
        navigator.geolocation.getCurrentPosition(
            addUserMarker,
            () => {
                if (locationHint) locationHint.textContent = "Your location was not shared. You can still explore the map.";
            },
            { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 }
        );
    }

    async function openLocation() {
        if (!locationModal) return;
        openModal(locationModal, locationModal.querySelector("[data-location-close]"));
        await renderMap();
    }

    function closeLocation() {
        closeModal(locationModal);
    }

    spatialButton?.addEventListener("click", openSpatial);
    locationButton?.addEventListener("click", openLocation);

    spatialModal?.querySelectorAll("[data-spatial-close]").forEach((element) => {
        element.addEventListener("click", closeSpatial);
    });
    locationModal?.querySelectorAll("[data-location-close]").forEach((element) => {
        element.addEventListener("click", closeLocation);
    });

    spatialModeButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const mode = button.dataset.spatialMode;
            const scene = spatial.currentScene || findScene(currentSceneId) || currentSceneFromUrl();
            renderSpatialMode(mode, scene);
        });
    });

    spatialSceneSelect?.addEventListener("change", () => {
        const scene = findScene(spatialSceneSelect.value);
        if (!scene) return;
        currentSceneId = scene.id ?? scene.scene_id;
        spatial.currentScene = scene;
        window.dispatchEvent(new CustomEvent("twinscopes:navigate-scene", {
            detail: { sceneId: currentSceneId, title: scene.title || "", source: "spatial-picker" },
        }));
        renderSpatialMode(spatial.currentMode, scene);
    });

    spatialMotionButton?.addEventListener("click", toggleMotion);
    spatialStepButton?.addEventListener("click", stepForward);
    spatialResetButton?.addEventListener("click", resetSpatialView);
    locateMeButton?.addEventListener("click", locateVisitor);
    mapResetButton?.addEventListener("click", resetMap);
    mapModeButton?.addEventListener("click", async () => {
        mapState.mode3D = !mapState.mode3D;
        syncMapModeButton();
        await renderMap();
    });

    window.addEventListener("twinscopes:scene-changed", (event) => {
        currentSceneId = event.detail?.sceneId ?? currentSceneId;
        const scene = findScene(currentSceneId);
        if (!scene) return;
        spatial.currentScene = scene;
        if (spatialSceneSelect) spatialSceneSelect.value = String(currentSceneId || "");
        if (spatialModal?.classList.contains("open")) {
            renderSpatialMode(spatial.currentMode, scene, { preserveView: spatial.currentMode === MODE.GRAPH });
        }
    });

    document.addEventListener("keydown", (event) => {
        const key = String(event.key || "").toLowerCase();
        if (spatialModal?.classList.contains("open") && ["w", "a", "s", "d", "arrowup", "arrowdown", "arrowleft", "arrowright"].includes(key)) {
            if (spatial.currentMode !== MODE.GRAPH) {
                event.preventDefault();
                spatial.keys.add(key);
            }
        }
        if (event.key !== "Escape") return;
        if (spatialModal?.classList.contains("open")) {
            event.preventDefault();
            closeSpatial();
        } else if (locationModal?.classList.contains("open")) {
            event.preventDefault();
            closeLocation();
        }
    });

    document.addEventListener("keyup", (event) => {
        spatial.keys.delete(String(event.key || "").toLowerCase());
    });

    window.addEventListener("pagehide", () => {
        stopMotion();
        spatial.keys.clear();
        spatial.resizeObserver?.disconnect?.();
        if (spatial.frameId) window.cancelAnimationFrame(spatial.frameId);
        spatial.frameId = null;
        clearSpatialRoot();
        spatial.renderer?.dispose?.();
    });

    currentSceneId = currentSceneFromUrl()?.id ?? currentSceneFromUrl()?.scene_id ?? null;
    populateSpatialSceneSelect();
    syncMapModeButton();
    syncModeButtons(currentSceneFromUrl());

    if (spatialButton && config.spatial3DEnabled === false) spatialButton.hidden = true;
})();
