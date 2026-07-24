(() => {
  const form = document.querySelector("[data-home-search-launcher]");
  const input = form?.querySelector("[data-home-search-input]");
  if (!form || !input) return;

  const openSearchPage = () => {
    const url = new URL(form.action, window.location.origin);
    const query = input.value.trim();
    if (query) url.searchParams.set("q", query);
    window.location.assign(url.toString());
  };

  input.addEventListener("pointerdown", (event) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    event.preventDefault();
    openSearchPage();
  });
  input.addEventListener("focus", openSearchPage);
  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openSearchPage();
    }
  });
})();
