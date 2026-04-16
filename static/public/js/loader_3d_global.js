(function () {
    const loader = document.getElementById('globalPageLoader');
    if (!loader) return;

    const statusEl = document.getElementById('globalLoaderStatusText');
    const statuses = [
        'Loading panoramic scenes...',
        'Preparing immersive navigation...',
        'Optimizing visual experience...',
        'Almost ready...'
    ];

    let statusIndex = 0;
    let statusTimer = null;

    function startStatusRotation() {
        if (!statusEl) return;
        statusTimer = window.setInterval(() => {
            statusIndex = (statusIndex + 1) % statuses.length;
            statusEl.textContent = statuses[statusIndex];
        }, 1200);
    }

    function stopStatusRotation() {
        if (statusTimer) {
            window.clearInterval(statusTimer);
            statusTimer = null;
        }
    }

    function hideLoader() {
        loader.classList.add('is-hidden');
        stopStatusRotation();
        window.setTimeout(() => {
            loader.style.display = 'none';
        }, 650);
    }

    function showLoader() {
        loader.style.display = 'flex';
        requestAnimationFrame(() => {
            loader.classList.remove('is-hidden');
        });
        startStatusRotation();
    }

    window.VirtualTourLoader = {
        show: showLoader,
        hide: hideLoader
    };

    showLoader();

    window.addEventListener('load', function () {
        window.setTimeout(hideLoader, 700);
    });

    document.addEventListener('visibilitychange', function () {
        if (document.hidden) return;
        if (loader.style.display !== 'none' && !loader.classList.contains('is-hidden')) {
            startStatusRotation();
        }
    });
})();