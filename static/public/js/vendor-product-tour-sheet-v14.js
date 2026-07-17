(() => {
  "use strict";
  const sheet = document.getElementById("marketTourBottomSheet");
  const openButton = document.querySelector("[data-market-tour-sheet-open]");
  if (!sheet || !openButton) return;
  const closeButtons = sheet.querySelectorAll("[data-market-tour-sheet-close]");
  const flipButtons = sheet.querySelectorAll("[data-tour-flip]");
  const openSheet = () => {
    sheet.removeAttribute("inert");
    sheet.setAttribute("aria-hidden", "false");
    sheet.classList.add("is-open");
    openButton.setAttribute("aria-expanded", "true");
    document.documentElement.style.overflow = "hidden";
    setTimeout(() => sheet.querySelector(".market-tour-sheet__close")?.focus(), 120);
  };
  const closeSheet = () => {
    sheet.classList.remove("is-open");
    sheet.setAttribute("aria-hidden", "true");
    openButton.setAttribute("aria-expanded", "false");
    document.documentElement.style.overflow = "";
    setTimeout(() => { sheet.setAttribute("inert", ""); openButton.focus(); }, 340);
  };
  openButton.addEventListener("click", openSheet);
  closeButtons.forEach((button) => button.addEventListener("click", closeSheet));
  flipButtons.forEach((button) => button.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    button.closest("[data-tour-flip-card]")?.classList.toggle("is-flipped");
  }));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && sheet.classList.contains("is-open")) closeSheet();
  });
})();
