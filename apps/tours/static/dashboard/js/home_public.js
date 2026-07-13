document.addEventListener("DOMContentLoaded", () => {
    const heroPanoEl = document.getElementById("heroMarzipano");
    const heroLoader = document.getElementById("heroLoader");
    const openMenuBtn = document.getElementById("openMenuBtn");
    const closeMenuBtn = document.getElementById("closeMenuBtn");
    const menuBackdrop = document.getElementById("menuBackdrop");
    const mobileMenuPanel = document.getElementById("mobileMenuPanel");

    function setMobileMenuOpen(isOpen) {
        if (!menuBackdrop || !mobileMenuPanel) return;
        menuBackdrop.classList.toggle("show", isOpen);
        mobileMenuPanel.classList.toggle("open", isOpen);
        document.body.classList.toggle("overflow-hidden", isOpen && window.innerWidth < 768);
    }

    openMenuBtn?.addEventListener("click", () => setMobileMenuOpen(true));
    closeMenuBtn?.addEventListener("click", () => setMobileMenuOpen(false));
    menuBackdrop?.addEventListener("click", () => setMobileMenuOpen(false));

    document.querySelectorAll("[data-menu-link]").forEach(link => {
        link.addEventListener("click", () => setMobileMenuOpen(false));
    });

    window.addEventListener("resize", () => {
        if (window.innerWidth >= 768) {
            setMobileMenuOpen(false);
        }
    });

    function hideHeroLoader() {
        if (heroLoader) {
            heroLoader.classList.add("is-hidden");
        }
    }

    if (!heroPanoEl || typeof Marzipano === "undefined") {
        setTimeout(hideHeroLoader, 600);
        return;
    }

    const panoramaUrl = heroPanoEl.dataset.panoramaUrl;
    if (!panoramaUrl) {
        setTimeout(hideHeroLoader, 600);
        return;
    }

    const degToRad = (deg) => deg * Math.PI / 180;

    try {
        const viewer = new Marzipano.Viewer(heroPanoEl, {
            controls: {
                mouseViewMode: "drag"
            }
        });

        const source = Marzipano.ImageUrlSource.fromString(panoramaUrl);
        const geometry = new Marzipano.EquirectGeometry([{ width: 4000 }]);

        const limiter = Marzipano.RectilinearView.limit.traditional(
            4096,
            degToRad(120)
        );

        const view = new Marzipano.RectilinearView(
            {
                yaw: degToRad(0),
                pitch: degToRad(-2),
                fov: degToRad(108)
            },
            limiter
        );

        const scene = viewer.createScene({
            source,
            geometry,
            view,
            pinFirstLevel: true
        });

        scene.switchTo({
            transitionDuration: 900
        });

        let autoRotateSpeed = 0.0022;
        let autoRotateFrame = null;
        let isInteracting = false;

        function animate() {
            if (!isInteracting) {
                view.setYaw(view.yaw() + autoRotateSpeed);
            }
            autoRotateFrame = requestAnimationFrame(animate);
        }

        animate();
        setTimeout(hideHeroLoader, 850);

        heroPanoEl.addEventListener("mouseenter", () => {
            isInteracting = true;
        });

        heroPanoEl.addEventListener("mouseleave", () => {
            isInteracting = false;
        });

        heroPanoEl.addEventListener("touchstart", () => {
            isInteracting = true;
        }, { passive: true });

        heroPanoEl.addEventListener("touchend", () => {
            isInteracting = false;
        }, { passive: true });

        window.addEventListener("beforeunload", () => {
            if (autoRotateFrame) {
                cancelAnimationFrame(autoRotateFrame);
            }
        });
    } catch (error) {
        console.error("Unable to initialize Marzipano hero panorama:", error);
        setTimeout(hideHeroLoader, 600);
    }
});