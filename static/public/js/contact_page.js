document.addEventListener("DOMContentLoaded", () => {
    const body = document.body;

    const openMenuBtn = document.getElementById("openMenuBtn");
    const closeMenuBtn = document.getElementById("closeMenuBtn");
    const menuBackdrop = document.getElementById("menuBackdrop");
    const mobileMenuPanel = document.getElementById("mobileMenuPanel");

    const contactModal = document.getElementById("contactModal");
    const contactBackdrop = document.getElementById("contactBackdrop");
    const closeContactModalBtn = document.getElementById("closeContactModalBtn");
    const contactTopicField = document.getElementById("contactTopicField");
    const contactNameField = document.getElementById("contactNameField");

    function lockBody() {
        body.classList.add("overflow-hidden");
    }

    function unlockBody() {
        if (!mobileMenuPanel?.classList.contains("open") && !contactModal?.classList.contains("show")) {
            body.classList.remove("overflow-hidden");
        }
    }

    function setMobileMenuOpen(isOpen) {
        if (!menuBackdrop || !mobileMenuPanel) return;
        menuBackdrop.classList.toggle("show", isOpen);
        mobileMenuPanel.classList.toggle("open", isOpen);

        if (isOpen && window.innerWidth < 768) {
            lockBody();
        } else {
            unlockBody();
        }
    }

    function openContactModal(topic = "General inquiry") {
        if (!contactModal || !contactBackdrop) return;
        contactModal.classList.add("show");
        contactBackdrop.classList.add("show");
        contactModal.setAttribute("aria-hidden", "false");

        if (contactTopicField) {
            contactTopicField.value = topic;
        }

        lockBody();

        window.setTimeout(() => {
            contactNameField?.focus();
        }, 120);
    }

    function closeContactModal() {
        if (!contactModal || !contactBackdrop) return;
        contactModal.classList.remove("show");
        contactBackdrop.classList.remove("show");
        contactModal.setAttribute("aria-hidden", "true");
        unlockBody();
    }

    openMenuBtn?.addEventListener("click", () => setMobileMenuOpen(true));
    closeMenuBtn?.addEventListener("click", () => setMobileMenuOpen(false));
    menuBackdrop?.addEventListener("click", () => setMobileMenuOpen(false));

    document.querySelectorAll("[data-menu-link]").forEach((link) => {
        link.addEventListener("click", () => setMobileMenuOpen(false));
    });

    document.querySelectorAll("[data-open-contact]").forEach((button) => {
        button.addEventListener("click", () => {
            const topic = button.getAttribute("data-contact-topic") || "General inquiry";
            setMobileMenuOpen(false);
            openContactModal(topic);
        });
    });

    document.querySelectorAll("[data-close-contact]").forEach((button) => {
        button.addEventListener("click", closeContactModal);
    });

    closeContactModalBtn?.addEventListener("click", closeContactModal);
    contactBackdrop?.addEventListener("click", closeContactModal);

    window.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            if (contactModal?.classList.contains("show")) {
                closeContactModal();
            } else if (mobileMenuPanel?.classList.contains("open")) {
                setMobileMenuOpen(false);
            }
        }
    });

    window.addEventListener("resize", () => {
        if (window.innerWidth >= 768) {
            setMobileMenuOpen(false);
        }
    });
});