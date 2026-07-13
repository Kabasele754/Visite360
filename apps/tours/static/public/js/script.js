/*
  script.js
  Cartes 3D pour visite virtuelle
  - Mobile : 2 cartes par ligne
  - Flip simple au tap/click
  - Pas de double flip sur mobile
  - Tilt 3D seulement sur desktop
*/

const cardsData = [
  {
    id: "scene-entrance",
    title: "Entrance Experience",
    tag: "Entrée",
    image:
      "https://images.unsplash.com/photo-1524995997946-a1c2e315a42f?q=80&w=1600&auto=format&fit=crop",
    avatar:
      "https://images.unsplash.com/photo-1507842217343-583bb7270b66?q=80&w=400&auto=format&fit=crop",
    desc:
      "Commencez la visite virtuelle par une entrée immersive, moderne et accueillante. Une première impression claire, élégante et professionnelle.",
    features: ["Vue immersive", "Navigation fluide", "Accueil premium"],
    actionLabel: "Entrer",
    sceneUrl: "#entrance"
  },
  {
    id: "scene-reception",
    title: "Reception Area",
    tag: "Réception",
    image:
      "https://images.unsplash.com/photo-1497366754035-f200968a6e72?q=80&w=1600&auto=format&fit=crop",
    avatar:
      "https://images.unsplash.com/photo-1519389950473-47ba0277781c?q=80&w=400&auto=format&fit=crop",
    desc:
      "Découvrez un espace de réception soigné, pensé pour orienter les visiteurs et présenter les informations importantes avec élégance.",
    features: ["Infos visiteurs", "Design clair", "Accès rapide"],
    actionLabel: "Voir",
    sceneUrl: "#reception"
  },
  {
    id: "scene-reading",
    title: "Reading Space",
    tag: "Lecture",
    image:
      "https://images.unsplash.com/photo-1521587760476-6c12a4b040da?q=80&w=1600&auto=format&fit=crop",
    avatar:
      "https://images.unsplash.com/photo-1512820790803-83ca734da794?q=80&w=400&auto=format&fit=crop",
    desc:
      "Un espace calme et inspirant pour lire, apprendre et découvrir de nouvelles idées dans une atmosphère moderne et confortable.",
    features: ["Ambiance calme", "Espace moderne", "Confort visuel"],
    actionLabel: "Explorer",
    sceneUrl: "#reading"
  },
  {
    id: "scene-books",
    title: "Book Collection",
    tag: "Livres",
    image:
      "https://images.unsplash.com/photo-1513475382585-d06e58bcb0e0?q=80&w=1600&auto=format&fit=crop",
    avatar:
      "https://images.unsplash.com/photo-1481627834876-b7833e8f5570?q=80&w=400&auto=format&fit=crop",
    desc:
      "Parcourez les rayons, découvrez les livres disponibles et laissez chaque ouvrage ouvrir une nouvelle porte vers la connaissance.",
    features: ["Rayons organisés", "Découverte facile", "Culture & savoir"],
    actionLabel: "Découvrir",
    sceneUrl: "#books"
  }
];

const grid = document.getElementById("cardGrid");

const canTilt = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

function createEl(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text) el.textContent = text;
  return el;
}

function createCard(data) {
  const scene = createEl("div", "card-scene");
  scene.setAttribute("role", "button");
  scene.setAttribute("aria-label", `${data.title}. Touchez pour retourner la carte.`);
  scene.setAttribute("aria-pressed", "false");
  scene.tabIndex = 0;

  const card = createEl("div", "card");
  card.dataset.id = data.id;

  /* FRONT */
  const front = createEl("div", "face front");

  const thumb = createEl("div", "thumb");
  thumb.style.backgroundImage = `url("${data.image}")`;

  const meta = createEl("div", "meta");

  const topRow = createEl("div", "top-row");

  const tag = createEl("div", "tag", data.tag || "Visite");

  const flipDot = createEl("div", "flip-dot", "↻");
  flipDot.setAttribute("aria-hidden", "true");

  topRow.appendChild(tag);
  topRow.appendChild(flipDot);

  const title = createEl("div", "title", data.title);

  meta.appendChild(topRow);
  meta.appendChild(title);

  const info = createEl("div", "info");
  info.innerHTML = `
    <span>Touchez la carte</span>
    <span>Voir détails</span>
  `;

  front.appendChild(thumb);
  front.appendChild(meta);
  front.appendChild(info);

  /* BACK */
  const back = createEl("div", "face back");

  const backTop = createEl("div", "back-top");

  const backBadge = createEl("span", "back-badge", data.tag || "Visite");

  const closeBtn = createEl("button", "close-flip", "↩");
  closeBtn.type = "button";
  closeBtn.setAttribute("aria-label", "Retourner la carte");
  closeBtn.dataset.noFlip = "true";

  backTop.appendChild(backBadge);
  backTop.appendChild(closeBtn);

  const h3 = createEl("h3", data.title);
  const p = createEl("p", null, data.desc || "");

  const features = createEl("div", "features");
  const list = Array.isArray(data.features) ? data.features : [];

  list.slice(0, 3).forEach((item) => {
    const feature = createEl("div", "feature", item);
    features.appendChild(feature);
  });

  const details = createEl("div", "details");

  const avatar = createEl("div", "avatar");
  avatar.style.backgroundImage = `url("${data.avatar || data.image}")`;

  const btn = createEl("button", "btn", data.actionLabel || "Ouvrir");
  btn.type = "button";
  btn.dataset.noFlip = "true";

  details.appendChild(avatar);
  details.appendChild(btn);

  back.appendChild(backTop);
  back.appendChild(h3);
  back.appendChild(p);
  back.appendChild(features);
  back.appendChild(details);

  card.appendChild(front);
  card.appendChild(back);
  scene.appendChild(card);

  function isFlipped() {
    return card.classList.contains("is-flipped");
  }

  function setFlipped(value) {
    card.classList.toggle("is-flipped", value);
    scene.classList.toggle("is-active", value);
    scene.setAttribute("aria-pressed", String(value));

    if (!value) {
      resetTilt();
    }
  }

  function toggleFlip(event) {
    if (event.target.closest("[data-no-flip='true']")) return;
    setFlipped(!isFlipped());
  }

  function resetTilt() {
    card.style.setProperty("--rx", "0deg");
    card.style.setProperty("--ry", "0deg");
  }

  function applyTilt(event) {
    if (!canTilt) return;
    if (isFlipped()) return;

    const rect = scene.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;

    const maxTilt = 8;
    const ry = (x - 0.5) * maxTilt;
    const rx = (0.5 - y) * maxTilt;

    card.style.setProperty("--rx", `${rx.toFixed(2)}deg`);
    card.style.setProperty("--ry", `${ry.toFixed(2)}deg`);
  }

  scene.addEventListener("click", toggleFlip);

  scene.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setFlipped(!isFlipped());
    }

    if (event.key === "Escape") {
      setFlipped(false);
    }
  });

  scene.addEventListener("pointermove", applyTilt);

  scene.addEventListener("pointerleave", () => {
    resetTilt();
  });

  closeBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    setFlipped(false);
  });

  btn.addEventListener("click", (event) => {
    event.stopPropagation();

    if (data.sceneUrl && data.sceneUrl !== "#") {
      window.location.href = data.sceneUrl;
      return;
    }

    window.open(data.image, "_blank", "noopener,noreferrer");
  });

  return scene;
}

function renderCards() {
  if (!grid) return;

  grid.innerHTML = "";

  cardsData.forEach((cardData, index) => {
    const card = createCard(cardData);

    card.style.opacity = "0";
    card.style.transform = "translateY(18px) scale(0.98)";

    grid.appendChild(card);

    window.setTimeout(() => {
      card.style.transition =
        "opacity 520ms ease, transform 650ms cubic-bezier(.2,.9,.25,1)";
      card.style.opacity = "1";
      card.style.transform = "translateY(0) scale(1)";
    }, index * 90);
  });
}

renderCards();