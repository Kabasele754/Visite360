const EMPTY_DOM = (() => {
  const noop = () => {};
  const handler = {
    get(target, prop) {
      if (prop === 'querySelectorAll') return () => [];
      if (prop === 'querySelector') return () => null;
      if (prop === 'addEventListener') return noop;
      if (prop === 'removeEventListener') return noop;
      if (prop === 'appendChild') return noop;
      if (prop === 'remove') return noop;
      if (prop === 'setAttribute') return noop;
      if (prop === 'getAttribute') return () => null;
      if (prop === 'classList') return proxy;
      if (prop === 'style') return proxy;
      if (prop === 'dataset') return {};
      if (prop === 'value') return '';
      if (prop === 'checked') return false;
      if (prop === 'textContent') return '';
      if (prop === 'innerHTML') return '';
      if (prop === 'disabled') return false;
      if (prop === 'contains') return () => false;
      return noop;
    },
    set() { return true; },
    apply() { return undefined; }
  };
  const proxy = new Proxy(noop, handler);
  return proxy;
})();

const $ = (id) => document.getElementById(id) || EMPTY_DOM;
const hasEl = (id) => Boolean(document.getElementById(id));
const bindClick = (id, handler) => {
  const node = document.getElementById(id);
  if (node) node.onclick = handler;
};
const setText = (id, value) => {
  const node = document.getElementById(id);
  if (node) node.textContent = value ?? '';
};
const setHtml = (id, value) => {
  const node = document.getElementById(id);
  if (node) node.innerHTML = value ?? '';
};
const setValue = (id, value) => {
  const node = document.getElementById(id);
  if (node) node.value = value ?? '';
};
const toggleHidden = (id, hidden) => {
  const node = document.getElementById(id);
  if (node) node.classList.toggle('hidden', Boolean(hidden));
};

window.initCanonicalPublisherPage = function () {
  window.__canonicalPublisherMapReady = Boolean(window.google && google.maps);
  if (typeof boot === 'function') {
    boot().catch(e => {
      console.error(e);
      const msg = e && e.message ? e.message : 'Initialization error';
      if (typeof toast === 'function') toast(msg);
    });
  }
};
const API = '/apis/streetview/';

const state = {
  booted: false,
  uiBound: false,
  activeTab: 'prepare',
  orgs: [],
  places: [],
  tours: [],
  project: null,
  selectedOrg: null,
  selectedPlace: null,
  selectedTour: null,
  selectedScene: null,
  shareText: '',

  googlePhotos: [],
  googleSequences: [],
  googlePhotosNextToken: '',
  googlePhotoFilter: 'all',
  googlePhotoQuery: '',
  googlePhotosStats: null,
  googleLibraryLoaded: false,
  googleLibraryLoading: false,

  qualityReport: null,
  smartLinkData: null,
  activeJob: null,
  jobPollTimer: null,
  historyEvents: [],
  analyticsSummary: null,

  viewer: null,
  marziScene: null,
  view: null,
  viewerSyncFrame: null,
  viewerReadySceneId: null,

  mapsReady: false,
  editorMap: null,
  editorMapType: 'roadmap',
  streetMarkers: new Map(),
  headingLine: null,
  headingHandle: null,
  linkLines: [],
  searchAutocomplete: null,
};

function csrfToken() {
  const m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : '';
}

async function requestJSON(url, opts = {}) {
  const res = await fetch(url, {
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken(),
      ...(opts.headers || {}),
    },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw Object.assign(new Error(data.error || `Erreur HTTP ${res.status}`), { data, status: res.status });
  }
  return data;
}

function toast(msg) {
  const box = $('toastBox');
  if (!box) return;
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = msg;
  box.appendChild(el);
  setTimeout(() => el.remove(), 3600);
}

function esc(v = '') {
  return String(v).replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));
}

function num(value, fallback = null) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function normalizeHeading(value) {
  const n = num(value, 0);
  return ((n % 360) + 360) % 360;
}

function clamp(value, min, max, fallback) {
  const n = num(value, fallback);
  return Math.min(max, Math.max(min, n));
}

function degToRad(value) {
  return Number(value || 0) * Math.PI / 180;
}

function radToDeg(value) {
  return Number(value || 0) * 180 / Math.PI;
}

function fmtGps(g) {
  return g?.latitude != null && g?.longitude != null
    ? `${Number(g.latitude).toFixed(6)}, ${Number(g.longitude).toFixed(6)}`
    : 'GPS manquant';
}

function pill(label, type = '') {
  return `<span class="pill ${type}">${label}</span>`;
}

function scenes() {
  return state.project?.scenes || [];
}

function links() {
  return state.project?.navigation_links || [];
}

function currentScene() {
  return scenes().find(s => Number(s.id) === Number(state.selectedScene));
}

function titleById(id) {
  return scenes().find(s => Number(s.id) === Number(id))?.title || `Scene ${id}`;
}

function sceneIndex(id) {
  return Math.max(0, scenes().findIndex(s => Number(s.id) === Number(id)));
}

function rawSceneLatLng(scene) {
  const lat = num(scene?.gps?.latitude, null);
  const lng = num(scene?.gps?.longitude, null);
  if (lat != null && lng != null) return { lat, lng };
  const tLat = num(state.project?.tour?.latitude, null);
  const tLng = num(state.project?.tour?.longitude, null);
  if (tLat != null && tLng != null) return { lat: tLat, lng: tLng };
  return null;
}

function visualSceneLatLng(scene) {
  const base = rawSceneLatLng(scene);
  if (!base) return null;
  const same = scenes().filter(s => {
    const p = rawSceneLatLng(s);
    return p && Math.abs(p.lat - base.lat) < 0.0000005 && Math.abs(p.lng - base.lng) < 0.0000005;
  });
  if (same.length <= 1) return base;
  const index = same.findIndex(s => Number(s.id) === Number(scene.id));
  if (index <= 0) return base;
  if (window.google?.maps?.geometry?.spherical) {
    const angle = (index * 72) % 360;
    const meters = 2.4 + index * 1.2;
    const offset = google.maps.geometry.spherical.computeOffset(base, meters, angle);
    return { lat: offset.lat(), lng: offset.lng() };
  }
  return { lat: base.lat + index * 0.000015, lng: base.lng + index * 0.000015 };
}

function selectedLatLngFromInputs() {
  const lat = num($('sceneLat')?.value, null);
  const lng = num($('sceneLng')?.value, null);
  return lat != null && lng != null ? { lat, lng } : null;
}

function updateTourStats() {
  const all = scenes();
  const gps = all.filter(s => s.gps?.latitude != null && s.gps?.longitude != null).length;
  const published = all.filter(s => s.google?.is_published).length;
  const connected = all.filter(s => s.google?.is_connected).length;
  const nav = links().length;
  const box = $('tourStats');
  if (!box) return;
  box.innerHTML = [
    ['Images', all.length],
    ['GPS', `${gps}/${all.length}`],
    ['Publishedes', `${published}/${all.length}`],
    ['Connected', `${connected}/${all.length}`],
    ['Liaisons', nav],
  ].map(([k, v]) => `<span class="stat-chip">${k}: ${v}</span>`).join('');
}

async function boot() {
  if (state.booted) return;
  state.booted = true;
  state.mapsReady = Boolean(window.google && google.maps);

  // Important: l'interface doit rester cliquable même si une requête API échoue.
  bindActions();
  bindMainTabsFallback();
  setMode('auto');
  setMainTab('prepare', { silent: true });

  try {
    await loadGoogleStatus();
  } catch (e) {
    console.warn('Google status unavailable', e);
    setText('googleStatus', 'Google: check failed');
  }

  try {
    await loadOrganizations();
  } catch (e) {
    console.error(e);
    setHtml('organizationsList', `<div class="muted-box">Impossible de charger les organisations.<br>${esc(e.message || e)}</div>`);
    toast(e.message || 'Erreur chargement organisations');
  }
}

// La fonction est déclarée en haut du fichier pour éviter l'erreur Google callback
// `initCanonicalPublisherPage is not a function` lorsque Maps charge très vite.

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    if (!window.STREETVIEW_MAP_CONFIG?.apiKey) window.initCanonicalPublisherPage();
  });
} else if (!window.STREETVIEW_MAP_CONFIG?.apiKey) {
  window.initCanonicalPublisherPage();
}

async function loadGoogleStatus() {
  try {
    const data = await requestJSON(API + 'google/status/');
    const el = $('googleStatus');
    if (!el) return;
    if (data.connected) {
      el.textContent = `Google connected${data.googleEmail ? ' · ' + data.googleEmail : ''}`;
    } else {
      el.innerHTML = `Google not connected · <a href="${data.oauthStartUrl}">Connect</a>`;
    }
  } catch (e) {
    setText('googleStatus', 'Google: erreur');
  }
}

async function loadOrganizations() {
  const data = await requestJSON(API + 'source/organizations/');
  state.orgs = data.results || [];
  renderOrganizations();
}

function renderOrganizations() {
  const box = $('organizationsList');
  box.innerHTML = state.orgs.map(o => `
    <button class="item ${state.selectedOrg === o.id ? 'active' : ''}" data-org="${o.id}">
      <b>${esc(o.name)}</b><span>${esc(o.slug)} · ${esc(o.status)}</span>
    </button>
  `).join('') || '<div class="muted-box">Aucune organisation.</div>';
  box.querySelectorAll('[data-org]').forEach(b => b.onclick = () => selectOrg(Number(b.dataset.org)));
}

async function selectOrg(id) {
  state.selectedOrg = id;
  state.selectedPlace = null;
  state.selectedTour = null;
  state.project = null;
  state.selectedScene = null;
  stopViewerSync();
  renderOrganizations();
  $('placesList').innerHTML = 'Chargement...';
  $('toursList').innerHTML = '<div class="muted-box">Choisis un place.</div>';
  hideWorkspace();
  const data = await requestJSON(`${API}source/organizations/${id}/places/`);
  state.places = data.results || [];
  renderPlaces();
}

function renderPlaces() {
  const box = $('placesList');
  box.innerHTML = state.places.map(p => `
    <button class="item ${state.selectedPlace === p.id ? 'active' : ''}" data-place="${p.id}">
      <b>${esc(p.name)}</b><span>${esc(p.city || 'Ville ?')} · ${esc(p.category)} · ${p.latitude && p.longitude ? 'GPS OK' : 'GPS manquant'}</span>
    </button>
  `).join('') || '<div class="muted-box">Aucun place dans cette organisation.</div>';
  box.querySelectorAll('[data-place]').forEach(b => b.onclick = () => selectPlace(Number(b.dataset.place)));
}

async function selectPlace(id) {
  state.selectedPlace = id;
  state.selectedTour = null;
  state.project = null;
  state.selectedScene = null;
  stopViewerSync();
  renderPlaces();
  $('toursList').innerHTML = 'Chargement...';
  hideWorkspace();
  const data = await requestJSON(`${API}source/places/${id}/tours/`);
  state.tours = data.results || [];
  renderTours();
}

function renderTours() {
  const box = $('toursList');
  box.innerHTML = state.tours.map(t => {
    const sv = t.streetview;
    return `
      <button class="item ${state.selectedTour === t.id ? 'active' : ''}" data-tour="${t.id}">
        <b>${esc(t.title)}</b>
        <span>${t.scenes_count || 0} scene(s) · ${sv ? `${sv.published_scenes_count}/${sv.scenes_count} published` : 'not prepared yet'}</span>
      </button>
    `;
  }).join('') || '<div class="muted-box">Aucun tour pour ce place.</div>';
  box.querySelectorAll('[data-tour]').forEach(b => b.onclick = () => selectTour(Number(b.dataset.tour)));
}

async function selectTour(id) {
  state.selectedTour = id;
  state.selectedScene = null;
  state.activeTab = 'prepare';
  stopViewerSync();
  $('workspace').classList.remove('hidden');
  $('emptyState').classList.add('hidden');
  $('publishLogs').textContent = 'Chargement du tour...';
  const data = await requestJSON(`${API}source/tours/${id}/`);
  state.project = data;
  state.selectedScene = data.scenes?.[0]?.id || null;
  renderWorkspace();
  loadHistoryAndAnalytics();
  toast('Tour loaded. You can adjust the map and camera.');
}

function hideWorkspace() {
  $('workspace').classList.add('hidden');
  $('emptyState').classList.remove('hidden');
  clearMapOverlays();
}

function renderWorkspace() {
  const p = state.project;
  if (!p) return;
  const t = p.tour || {}, place = p.place || {}, org = p.organization || {};
  setText('breadcrumb', `${org.name || 'Organisation'} / ${place.name || 'Place'}`);
  setText('tourTitle', t.title || 'Tour');
  setText('tourMeta', `${place.address_line || t.location || ''} ${place.city || ''} ${place.country || ''}`.trim() || 'No address set');
  setText('sceneCounter', `${(p.scenes || []).length}`);
  updateTourStats();
  renderSceneList();
  renderSceneDetail();
  renderManualConnections();
  renderShareLinks();
  initOrRefreshMap();
  renderQualitySummary();
  renderSmartLinkSuggestions();
  renderAnalyticsSummary();
  renderHistoryList();
  renderGoogleVerificationSummary();
}

function renderGoogleVerificationSummary() {
  const box = $('googleVerificationSummary');
  if (!box) return;
  const all = scenes();
  const published = all.filter(s => s.google?.photo_id);
  const accepted = published.filter(s => s.google?.maps_publish_status === 'PUBLISHED');
  const rejected = published.filter(s => String(s.google?.maps_publish_status || '').includes('REJECT'));
  const connected = published.filter(s => ['synced', 'not_required'].includes(s.google?.connection_sync_status));
  const attention = published.filter(s => !['synced', 'not_required'].includes(s.google?.connection_sync_status) || s.google?.maps_publish_status !== 'PUBLISHED');
  box.classList.toggle('muted-box', !published.length);
  box.innerHTML = published.length ? `
    <div class="verify-grid">
      <div class="verify-cell"><b>${accepted.length}/${published.length}</b><span>accepted by Google</span></div>
      <div class="verify-cell"><b>${connected.length}/${published.length}</b><span>navigation verified</span></div>
      <div class="verify-cell"><b>${rejected.length}</b><span>rejected</span></div>
      <div class="verify-cell"><b>${attention.length}</b><span>need attention</span></div>
    </div>
    <div class="verify-note">Status comes from Google photo.get. Use “Audit & repair navigation” after indexing when only a few arrows appear.</div>
  ` : 'Publish at least one panorama to synchronize Google acceptance and navigation.';
}

function renderSceneList() {
  const all = scenes();
  const sceneListBox = document.getElementById('sceneList');
  if (!sceneListBox) return;
  sceneListBox.innerHTML = all.map((s, i) => {
    const active = Number(s.id) === Number(state.selectedScene);
    const gpsOk = s.gps?.latitude != null && s.gps?.longitude != null;
    const google = s.google || {};
    return `
      <article class="scene-card ${active ? 'active' : ''}" data-scene="${s.id}">
        <img src="${esc(s.preview_url || s.image_url || '')}" alt="">
        <div>
          <h4>${i + 1}. ${esc(s.title)}</h4>
          <p>${fmtGps(s.gps)} · ${esc(s.gps?.source || '')}</p>
          <div class="status-row">
            ${pill(gpsOk ? 'GPS' : 'GPS ?', gpsOk ? 'good' : 'bad')}
            ${pill(google.is_published ? 'Google' : 'Local', google.is_published ? 'good' : 'warn')}
            ${pill(google.maps_publish_status || (google.is_published ? 'PROCESSING' : 'LOCAL'), String(google.maps_publish_status || '').includes('REJECT') ? 'bad' : (google.maps_publish_status === 'PUBLISHED' ? 'good' : 'warn'))}
          </div>
          <div class="scene-google-detail">
            <small class="${String(google.maps_publish_status || '').includes('REJECT') ? 'rejected' : ''}">${esc(google.maps_publish_status || 'Not synchronized')}</small>
            <small class="${['synced','not_required'].includes(google.connection_sync_status) ? 'synced' : ''}">links: ${esc(google.connection_sync_status || 'pending')}</small>
            <small>${Number(google.view_count || 0).toLocaleString()} views</small>
          </div>
        </div>
      </article>`;
  }).join('') || '<div class="muted-box">No scene 360 dans ce tour.</div>';
  sceneListBox.querySelectorAll('[data-scene]').forEach(el => el.onclick = () => selectScene(Number(el.dataset.scene), true));
}

function selectScene(id, center = true) {
  state.selectedScene = id;
  renderSceneList();
  renderSceneDetail();
  renderManualConnections();
  updateMarkerSelectionStyles();
  focusSceneOnMap(center);
  openViewerInline();
}

function renderSceneDetail() {
  const s = currentScene();
  toggleHidden('sceneDetailEmpty', Boolean(s));
  toggleHidden('sceneDetail', !s);

  if (!s) {
    setText('sceneTitle', 'No scene selected');
    return;
  }

  setText('sceneTitle', s.title || 'Scene');
  setValue('sceneLat', s.gps?.latitude ?? '');
  setValue('sceneLng', s.gps?.longitude ?? '');
  setValue('sceneHeading', normalizeHeading(s.camera?.heading ?? 0).toFixed(2));
  setValue('scenePitch', clamp(s.camera?.pitch, -90, 90, 0).toFixed(2));
  setValue('sceneRoll', clamp(s.camera?.roll, -180, 180, 0).toFixed(2));
  setValue('sceneFov', clamp(s.camera?.initial_fov, 10, 120, 90).toFixed(2));
  setText('cameraReadout', `heading ${Number($('sceneHeading').value || 0).toFixed(1)}°`);

  const delBtn = document.getElementById('deleteGooglePhotoBtn');
  if (delBtn) {
    delBtn.disabled = !s.google?.is_published;
    delBtn.textContent = s.google?.is_published ? 'Effacer de Google' : 'Pas encore sur Google';
  }

  updateHeadingOverlay();
  openViewerInline();
}

async function initOrRefreshMap() {
  if (!state.mapsReady || !window.google?.maps) {
    setText('editorHelp', 'Google Map unavailable: check GOOGLE_MAPS_API_KEY.');
    return;
  }
  await createMapIfNeeded();
  renderSceneMarkers();
  renderConnectionLines();
  updateHeadingOverlay();
  focusSceneOnMap(false);
}

async function createMapIfNeeded() {
  if (state.editorMap) return;
  let MapClass = google.maps.Map;
  try {
    const mapsLib = await google.maps.importLibrary('maps');
    MapClass = mapsLib.Map || MapClass;
  } catch (_) {}
  const mapNode = document.getElementById('streetEditorMap');
  if (!mapNode) return;
  const first = scenes().map(rawSceneLatLng).find(Boolean) || { lat: -26.2041, lng: 28.0473 };
  state.editorMap = new MapClass(mapNode, {
    center: first,
    zoom: 18,
    mapId: window.STREETVIEW_MAP_CONFIG?.mapId || 'DEMO_MAP_ID',
    mapTypeId: state.editorMapType,
    mapTypeControl: false,
    fullscreenControl: false,
    streetViewControl: false,
    clickableIcons: false,
    gestureHandling: 'greedy',
  });
  setupPlacesSearch();
}

function clearMapOverlays() {
  state.streetMarkers.forEach(m => {
    if (m.marker) m.marker.setMap ? m.marker.setMap(null) : (m.marker.map = null);
  });
  state.streetMarkers.clear();
  state.linkLines.forEach(line => line.setMap(null));
  state.linkLines = [];
  if (state.headingLine) state.headingLine.setMap(null);
  state.headingLine = null;
  if (state.headingHandle) state.headingHandle.setMap ? state.headingHandle.setMap(null) : (state.headingHandle.map = null);
  state.headingHandle = null;
}

function markerContent(scene, i) {
  const el = document.createElement('div');
  el.className = `street-marker ${scene.google?.is_published ? 'published' : ''}`;
  el.dataset.sceneId = scene.id;
  el.innerHTML = `<span>${i + 1}</span><i class="dot"></i>`;
  return el;
}

async function renderSceneMarkers() {
  if (!state.editorMap || !window.google?.maps) return;
  const AdvancedMarkerElement = await getAdvancedMarkerElement();
  const wanted = new Set();
  scenes().forEach((scene, i) => {
    const pos = visualSceneLatLng(scene);
    if (!pos) return;
    wanted.add(String(scene.id));
    let entry = state.streetMarkers.get(String(scene.id));
    if (!entry) {
      const node = markerContent(scene, i);
      let marker;
      if (AdvancedMarkerElement) {
        marker = new AdvancedMarkerElement({ map: state.editorMap, position: pos, content: node, title: scene.title, gmpDraggable: true });
        marker.addListener('click', () => selectScene(scene.id, false));
        marker.addListener('dragend', (ev) => onMarkerDragEnd(scene.id, ev.latLng || marker.position));
      } else {
        marker = new google.maps.Marker({ map: state.editorMap, position: pos, title: scene.title, draggable: true, label: String(i + 1) });
        marker.addListener('click', () => selectScene(scene.id, false));
        marker.addListener('dragend', (ev) => onMarkerDragEnd(scene.id, ev.latLng));
      }
      entry = { marker, node };
      state.streetMarkers.set(String(scene.id), entry);
    } else {
      if (entry.marker.setPosition) entry.marker.setPosition(pos);
      else entry.marker.position = pos;
      if (entry.node) {
        entry.node.className = `street-marker ${scene.google?.is_published ? 'published' : ''}`;
        entry.node.innerHTML = `<span>${i + 1}</span><i class="dot"></i>`;
      }
    }
  });
  state.streetMarkers.forEach((entry, id) => {
    if (!wanted.has(String(id))) {
      if (entry.marker.setMap) entry.marker.setMap(null); else entry.marker.map = null;
      state.streetMarkers.delete(id);
    }
  });
  updateMarkerSelectionStyles();
}

async function getAdvancedMarkerElement() {
  if (!window.google?.maps?.importLibrary) return null;
  try {
    const lib = await google.maps.importLibrary('marker');
    return lib.AdvancedMarkerElement || null;
  } catch (_) {
    return null;
  }
}

function onMarkerDragEnd(sceneId, latLng) {
  const lat = typeof latLng.lat === 'function' ? latLng.lat() : Number(latLng.lat);
  const lng = typeof latLng.lng === 'function' ? latLng.lng() : Number(latLng.lng);
  state.selectedScene = Number(sceneId);
  renderSceneList();
  renderSceneDetail();
  $('sceneLat').value = lat.toFixed(7);
  $('sceneLng').value = lng.toFixed(7);
  updateHeadingOverlay();
  toast('Position moved. Click ✓ to save.');
}

function updateMarkerSelectionStyles() {
  state.streetMarkers.forEach((entry, id) => {
    entry.node?.classList.toggle('active', String(id) === String(state.selectedScene));
  });
}

function fitAllScenes() {
  if (!state.editorMap || !window.google?.maps) return;
  const bounds = new google.maps.LatLngBounds();
  let count = 0;
  scenes().forEach(s => {
    const p = visualSceneLatLng(s);
    if (p) { bounds.extend(p); count += 1; }
  });
  if (count) state.editorMap.fitBounds(bounds, 70);
}

function focusSceneOnMap(center = true) {
  if (!state.editorMap) return;
  const s = currentScene();
  const p = s ? visualSceneLatLng(s) : null;
  if (!p) return;
  if (center) {
    state.editorMap.panTo(p);
    state.editorMap.setZoom(Math.max(state.editorMap.getZoom() || 18, 18));
  }
  updateHeadingOverlay();
}

function renderConnectionLines() {
  if (!state.editorMap || !window.google?.maps) return;
  state.linkLines.forEach(line => line.setMap(null));
  state.linkLines = [];
  const byId = Object.fromEntries(scenes().map(s => [String(s.id), s]));
  links().forEach(link => {
    const from = byId[String(link.scene)];
    const to = byId[String(link.target_scene)];
    const p1 = rawSceneLatLng(from);
    const p2 = rawSceneLatLng(to);
    if (!p1 || !p2) return;
    const line = new google.maps.Polyline({
      map: state.editorMap,
      path: [p1, p2],
      strokeColor: '#22d3ee',
      strokeOpacity: 0.88,
      strokeWeight: 3,
      icons: [{
        icon: { path: google.maps.SymbolPath.FORWARD_CLOSED_ARROW, scale: 3, strokeColor: '#22d3ee' },
        offset: '100%',
      }],
    });
    line.addListener('click', () => {
      state.selectedScene = Number(link.scene);
      renderSceneList();
      renderSceneDetail();
      toast(`${titleById(link.scene)} → ${titleById(link.target_scene)}`);
    });
    state.linkLines.push(line);
  });
}

async function updateHeadingOverlay() {
  if (!state.editorMap || !window.google?.maps) return;
  const s = currentScene();
  if (!s) return;
  const p = selectedLatLngFromInputs() || rawSceneLatLng(s);
  if (!p) return;
  const heading = normalizeHeading($('sceneHeading')?.value ?? s.camera.heading ?? 0);
  const endpoint = google.maps.geometry?.spherical
    ? google.maps.geometry.spherical.computeOffset(p, 7, heading)
    : { lat: p.lat + Math.cos(degToRad(heading)) * 0.00004, lng: p.lng + Math.sin(degToRad(heading)) * 0.00004 };
  if (!state.headingLine) {
    state.headingLine = new google.maps.Polyline({
      map: state.editorMap,
      path: [p, endpoint],
      strokeColor: '#fbbf24',
      strokeOpacity: 1,
      strokeWeight: 4,
      icons: [{ icon: { path: google.maps.SymbolPath.FORWARD_CLOSED_ARROW, scale: 4, strokeColor: '#fbbf24' }, offset: '100%' }],
      zIndex: 40,
    });
  } else {
    state.headingLine.setPath([p, endpoint]);
  }
  await renderHeadingHandle(endpoint, p);
}

async function renderHeadingHandle(endpoint, origin) {
  const AdvancedMarkerElement = await getAdvancedMarkerElement();
  if (state.headingHandle) {
    if (state.headingHandle.setMap) state.headingHandle.setMap(null); else state.headingHandle.map = null;
    state.headingHandle = null;
  }
  if (AdvancedMarkerElement) {
    const node = document.createElement('div');
    node.className = 'heading-handle';
    const marker = new AdvancedMarkerElement({ map: state.editorMap, position: endpoint, content: node, title: 'Rotate camera', gmpDraggable: true });
    marker.addListener('dragend', ev => onHeadingHandleDrag(origin, ev.latLng || marker.position));
    state.headingHandle = marker;
  } else {
    const marker = new google.maps.Marker({ map: state.editorMap, position: endpoint, draggable: true, title: 'Rotate camera' });
    marker.addListener('dragend', ev => onHeadingHandleDrag(origin, ev.latLng));
    state.headingHandle = marker;
  }
}

function onHeadingHandleDrag(origin, latLng) {
  if (!window.google?.maps?.geometry?.spherical || !origin || !latLng) return;
  const p = typeof latLng.lat === 'function' ? { lat: latLng.lat(), lng: latLng.lng() } : { lat: Number(latLng.lat), lng: Number(latLng.lng) };
  const heading = normalizeHeading(google.maps.geometry.spherical.computeHeading(origin, p));
  $('sceneHeading').value = heading.toFixed(2);
  setViewerCameraFromInputs(false);
  updateHeadingOverlay();
  toast('Camera direction adjusted. Click ✓ to save.');
}

function setupPlacesSearch() {
  if (!state.editorMap || !window.google?.maps?.places || !google.maps.places.Autocomplete) return;
  const input = $('mapSearchInput');
  if (!input || state.searchAutocomplete) return;
  state.searchAutocomplete = new google.maps.places.Autocomplete(input, { fields: ['geometry', 'name', 'formatted_address'] });
  state.searchAutocomplete.addListener('place_changed', () => {
    const place = state.searchAutocomplete.getPlace();
    if (!place?.geometry?.location) return;
    const loc = place.geometry.location;
    state.editorMap.panTo(loc);
    state.editorMap.setZoom(19);
    $('sceneLat').value = loc.lat().toFixed(7);
    $('sceneLng').value = loc.lng().toFixed(7);
    updateSelectedMarkerPosition({ lat: loc.lat(), lng: loc.lng() });
    updateHeadingOverlay();
    toast('Address placed on the active scene. Click ✓ to save.');
  });
}

function updateSelectedMarkerPosition(pos) {
  const entry = state.streetMarkers.get(String(state.selectedScene));
  if (!entry) return;
  if (entry.marker.setPosition) entry.marker.setPosition(pos);
  else entry.marker.position = pos;
}

function openViewerInline() {
  const s = currentScene();
  if (!s || !s.image_url || typeof Marzipano === 'undefined') return;
  if (state.viewerReadySceneId === s.id && state.viewer && state.view) {
    setViewerCameraFromInputs(false);
    return;
  }
  state.viewerReadySceneId = s.id;
  const viewerEl = $('viewer');
  if (!state.viewer) state.viewer = new Marzipano.Viewer(viewerEl, { controls: { mouseViewMode: 'drag' } });
  state.viewer.updateSize();
  const source = Marzipano.ImageUrlSource.fromString(s.image_url);
  const width = 4096;
  const geometry = new Marzipano.EquirectGeometry([{ width }]);
  const limiter = Marzipano.RectilinearView.limit.traditional(width, degToRad(120));
  const view = new Marzipano.RectilinearView({
    yaw: degToRad(normalizeHeading($('sceneHeading').value || s.camera.heading || 0)),
    pitch: degToRad(clamp($('scenePitch').value || s.camera.pitch, -90, 90, 0)),
    fov: degToRad(clamp($('sceneFov').value || s.camera.initial_fov, 10, 120, 90)),
  }, limiter);
  state.view = view;
  state.marziScene = state.viewer.createScene({ source, geometry, view, pinFirstLevel: true });
  state.marziScene.switchTo({ transitionDuration: 220 });
  setTimeout(() => state.viewer?.updateSize(), 120);
  startViewerSync();
}

function startViewerSync() {
  stopViewerSync();
  const tick = () => {
    if (state.view && $('liveCameraToggle')?.checked) {
      syncInputsFromViewer(false);
    }
    state.viewerSyncFrame = requestAnimationFrame(tick);
  };
  state.viewerSyncFrame = requestAnimationFrame(tick);
}

function stopViewerSync() {
  if (state.viewerSyncFrame) cancelAnimationFrame(state.viewerSyncFrame);
  state.viewerSyncFrame = null;
}

function syncInputsFromViewer(showToast = true) {
  if (!state.view) return;
  const p = state.view.parameters();
  const heading = normalizeHeading(radToDeg(p.yaw));
  const pitch = clamp(radToDeg(p.pitch), -90, 90, 0);
  const fov = clamp(radToDeg(p.fov), 10, 120, 90);
  $('sceneHeading').value = heading.toFixed(2);
  $('scenePitch').value = pitch.toFixed(2);
  $('sceneFov').value = fov.toFixed(2);
  $('cameraReadout').textContent = `heading ${heading.toFixed(1)}° · pitch ${pitch.toFixed(1)}°`;
  updateHeadingOverlay();
  if (showToast) toast('Camera captured. Click ✓ to save.');
}

function setViewerCameraFromInputs(updateOverlay = true) {
  if (!state.view) return;
  const params = {
    yaw: degToRad(normalizeHeading($('sceneHeading').value)),
    pitch: degToRad(clamp($('scenePitch').value, -90, 90, 0)),
    fov: degToRad(clamp($('sceneFov').value, 10, 120, 90)),
  };
  try {
    state.view.setParameters(params);
  } catch (_) {}
  if (updateOverlay) updateHeadingOverlay();
}

function renderManualConnections() {
  const all = scenes();
  const nav = links();
  const from = $('manualFromScene'), to = $('manualToScene'), list = $('manualConnectionsList');
  if (!from || !to || !list) return;
  const options = all.map(s => `<option value="${s.id}">${esc(s.title)}</option>`).join('');
  from.innerHTML = options;
  to.innerHTML = options;
  if (state.selectedScene) from.value = String(state.selectedScene);
  const selected = all.find(s => Number(s.id) !== Number(from.value));
  if (selected) to.value = String(selected.id);
  if (!nav.length) {
    list.classList.add('muted-box');
    list.innerHTML = 'Aucune liaison pour ce tour.';
    return;
  }
  list.classList.remove('muted-box');
  list.innerHTML = nav.map(l => `
    <div class="connection-row">
      <span>${esc(titleById(l.scene))} → ${esc(titleById(l.target_scene))}<small>${esc(l.label || '')}</small></span>
      <button class="mini-danger" data-del-conn="${l.id}">×</button>
    </div>
  `).join('');
  list.querySelectorAll('[data-del-conn]').forEach(btn => btn.onclick = () => deleteManualConnection(Number(btn.dataset.delConn)));
}

async function addManualConnection() {
  if (!state.selectedTour) return;
  const from = Number($('manualFromScene').value);
  const to = Number($('manualToScene').value);
  if (!from || !to) return toast('Choose both scenes.');
  if (from === to) return toast('Choose two different scenes.');
  const payload = {
    from_scene_id: from,
    to_scene_id: to,
    label: $('manualConnectionLabel').value || `Vers ${titleById(to)}`,
    yaw: $('sceneHeading').value,
    pitch: $('scenePitch').value,
  };
  const data = await requestJSON(`${API}source/tours/${state.selectedTour}/connections/add/`, { method: 'POST', body: JSON.stringify(payload) });
  state.project = data;
  renderWorkspace();
  toast('Manual connection created.');
}

async function deleteManualConnection(id) {
  if (!state.selectedTour || !id) return;
  const data = await requestJSON(`${API}source/tours/${state.selectedTour}/connections/${id}/delete/`, { method: 'POST', body: JSON.stringify({}) });
  state.project = data;
  renderWorkspace();
  toast('Connection deleted.');
}

function alignToTarget() {
  const fromId = Number($('manualFromScene').value);
  const toId = Number($('manualToScene').value);
  const from = scenes().find(s => Number(s.id) === fromId);
  const to = scenes().find(s => Number(s.id) === toId);
  const p1 = rawSceneLatLng(from);
  const p2 = rawSceneLatLng(to);
  if (!p1 || !p2 || !window.google?.maps?.geometry?.spherical) return toast('GPS requis pour orienter automatiquement.');
  const heading = normalizeHeading(google.maps.geometry.spherical.computeHeading(p1, p2));
  if (Number(state.selectedScene) !== fromId) selectScene(fromId, true);
  $('sceneHeading').value = heading.toFixed(2);
  setViewerCameraFromInputs(true);
  updateHeadingOverlay();
  toast('Camera aligned to the target scene. Click ✓ to save.');
}

async function syncGoogleStatus() {
  if (!state.selectedTour) return toast('Choose a tour first.');
  const btn = $('syncGoogleStatusBtn');
  btn && (btn.disabled = true);
  try {
    const data = await requestJSON(`${API}source/tours/${state.selectedTour}/google-status-sync/`, { method: 'POST', body: JSON.stringify({}) });
    $('publishLogs').textContent = JSON.stringify(data, null, 2);
    const refreshed = await requestJSON(`${API}source/tours/${state.selectedTour}/`);
    state.project = refreshed;
    renderWorkspace();
    toast(`Google status synchronized: ${data.published || 0} published, ${data.rejected || 0} rejected.`);
  } catch (e) {
    $('publishLogs').textContent = JSON.stringify(e.data || { error: e.message }, null, 2);
    toast(e.message || 'Google status synchronization failed.');
  } finally {
    btn && (btn.disabled = false);
  }
}

async function auditAndRepairConnections() {
  if (!state.selectedTour) return toast('Choose a tour first.');
  const btn = $('auditConnectionsBtn');
  btn && (btn.disabled = true);
  $('publishLogs').textContent = 'Auditing Google navigation connections...\n';
  try {
    const data = await requestJSON(`${API}source/tours/${state.selectedTour}/connection-audit/`, {
      method: 'POST',
      body: JSON.stringify({ attempts: 5 }),
    });
    $('publishLogs').textContent = JSON.stringify(data, null, 2);
    const refreshed = await requestJSON(`${API}source/tours/${state.selectedTour}/`);
    state.project = refreshed;
    renderWorkspace();
    const repaired = data.repair?.connections_synced || 0;
    toast(data.ok ? `Navigation verified for ${repaired} panorama(s).` : 'Audit completed with connections still waiting for Google indexing.');
  } catch (e) {
    $('publishLogs').textContent = JSON.stringify(e.data || { error: e.message }, null, 2);
    toast(e.message || 'Google connection audit failed.');
  } finally {
    btn && (btn.disabled = false);
  }
}

async function retryGoogleConnections() {
  if (!state.selectedTour) return;
  $('publishLogs').textContent = 'Updating Google connections...\n';
  try {
    const data = await requestJSON(`${API}source/tours/${state.selectedTour}/retry-connections/`, { method: 'POST', body: JSON.stringify({}) });
    state.project = { publication: data.publication, tour: data.tour, organization: data.organization, place: data.place, scenes: data.scenes, navigation_links: data.navigation_links };
    $('publishLogs').textContent = JSON.stringify(data, null, 2);
    renderWorkspace();
    toast(data.ok ? 'Google connections updated.' : 'Connections sent with warnings.');
  } catch (e) {
    $('publishLogs').textContent = JSON.stringify(e.data || { error: e.message }, null, 2);
    toast(e.message);
  }
}

function renderShareLinks() {
  const published = scenes().filter(s => s.google?.photo_id).map(s => ({ title: s.title, link: s.google.share_link || '' }));
  state.shareText = published.map(x => `${x.title}: ${x.link}`).join('\n');
  const box = $('shareLinks');
  box.classList.toggle('muted-box', !published.length);
  box.innerHTML = published.length
    ? published.map(x => `<div class="share-link"><span>${esc(x.title)}</span><a href="${x.link}" target="_blank" rel="noopener">ouvrir</a></div>`).join('')
    : 'No published link yet.';
}

function setMode(mode) {
  const auto = mode === 'auto';
  $('autoModeTab')?.classList.toggle('active', auto);
  $('manualModeTab')?.classList.toggle('active', !auto);
  $('autoModePanel')?.classList.toggle('hidden', !auto);
  $('manualModePanel')?.classList.toggle('hidden', auto);
}


function setMainTab(tab, options = {}) {
  state.activeTab = tab === 'library' ? 'library' : 'prepare';

  const prepareBtn = document.getElementById('prepareTabBtn');
  const libraryBtn = document.getElementById('libraryTabBtn');
  const libraryBox = document.getElementById('googleLibraryWorkspace');
  const workspaceBox = document.getElementById('workspace');
  const emptyBox = document.getElementById('emptyState');

  prepareBtn?.classList.toggle('active', state.activeTab === 'prepare');
  libraryBtn?.classList.toggle('active', state.activeTab === 'library');

  if (libraryBox) {
    libraryBox.classList.toggle('hidden', state.activeTab !== 'library');
    libraryBox.hidden = state.activeTab !== 'library';
  }

  if (state.activeTab === 'library') {
    if (workspaceBox) { workspaceBox.classList.add('hidden'); workspaceBox.hidden = true; }
    if (emptyBox) { emptyBox.classList.add('hidden'); emptyBox.hidden = true; }

    // First opening: never keep a project/search keyword that could hide
    // Google account photos which are not linked to TwinScopes.
    if (!state.googleLibraryLoaded) {
      state.googlePhotoQuery = '';
      const search = document.getElementById('googlePhotoSearch');
      if (search) search.value = '';
    }

    if (!state.googleLibraryLoaded && !state.googleLibraryLoading && !options.silent) {
      loadGooglePhotos(true);
    } else {
      renderGoogleLibrary();
    }
    return;
  }

  if (libraryBox) { libraryBox.classList.add('hidden'); libraryBox.hidden = true; }

  if (state.project) {
    if (workspaceBox) { workspaceBox.classList.remove('hidden'); workspaceBox.hidden = false; }
    if (emptyBox) { emptyBox.classList.add('hidden'); emptyBox.hidden = true; }
    renderWorkspace();
  } else {
    if (workspaceBox) { workspaceBox.classList.add('hidden'); workspaceBox.hidden = true; }
    if (emptyBox) { emptyBox.classList.remove('hidden'); emptyBox.hidden = false; }
  }
}

function bindMainTabsFallback() {
  if (window.__streetviewMainTabsFallbackBound) return;
  window.__streetviewMainTabsFallbackBound = true;
  document.addEventListener('click', (event) => {
    const prepare = event.target.closest?.('#prepareTabBtn');
    const library = event.target.closest?.('#libraryTabBtn, #openLibraryTopBtn');
    if (prepare) {
      event.preventDefault();
      setMainTab('prepare');
    }
    if (library) {
      event.preventDefault();
      setMainTab('library');
    }
  });
}

function googleStatusLabel(status) {
  const s = String(status || 'UNKNOWN').toUpperCase();
  if (s === 'PUBLISHED' || s === 'LOCAL_INDEXED') return 'Published';
  if (s.includes('REJECTED')) return 'Rejected';
  if (s.includes('PROCESS')) return 'Processing';
  return s.replaceAll('_', ' ').toLowerCase();
}

function googleStatusClass(status) {
  const s = String(status || '').toUpperCase();
  if (s === 'PUBLISHED' || s === 'LOCAL_INDEXED') return 'good';
  if (s.includes('REJECTED')) return 'bad';
  return 'warn';
}

function googlePhotoSearchBlob(item) {
  const local = item.local || {};
  return [
    item.photo_id,
    item.maps_publish_status,
    item.upload_time,
    item.capture_time,
    local.scene_title,
    local.tour_title,
    local.organization_name,
    local.place_name,
  ].filter(Boolean).join(' ').toLowerCase();
}

function filteredGooglePhotos() {
  const q = String(state.googlePhotoQuery || '').trim().toLowerCase();
  return (state.googlePhotos || []).filter(item => {
    const matched = Boolean(item.local && item.local.matched);
    const status = String(item.maps_publish_status || '').toUpperCase();
    if (state.googlePhotoFilter === 'matched' && !matched) return false;
    if (state.googlePhotoFilter === 'unmatched' && matched) return false;
    if (state.googlePhotoFilter === 'rejected' && !status.includes('REJECTED')) return false;
    return !q || googlePhotoSearchBlob(item).includes(q);
  });
}

function updateGoogleLibraryStats(stats) {
  const photos = state.googlePhotos || [];
  const fallback = {
    total: photos.length,
    matched: photos.filter(x => x.local?.matched).length,
    unmatched: photos.filter(x => !x.local?.matched).length,
    rejected: photos.filter(x => String(x.maps_publish_status || '').toUpperCase().includes('REJECTED')).length,
  };
  const s = stats || fallback;
  setText('googleStatTotal', s.total ?? fallback.total);
  setText('googleStatMatched', s.matched ?? fallback.matched);
  setText('googleStatUnmatched', s.unmatched ?? fallback.unmatched);
  setText('googleStatRejected', s.rejected ?? fallback.rejected);
}

async function loadGooglePhotos(reset = true) {
  if (state.googleLibraryLoading) return;
  state.googleLibraryLoading = true;
  const grid = $('googlePhotoGrid');
  if (grid) {
    grid.classList.add('muted-box');
    grid.innerHTML = reset ? 'Loading Google Street View photos...' : 'Loading more...';
  }
  try {
    const token = reset ? '' : state.googlePhotosNextToken;
    const url = `${API}published/google-photos/?mode=account&include_local=1&include_sequences=1&page_size=100&max_pages=300&all=${token ? '0' : '1'}${token ? '&page_token=' + encodeURIComponent(token) : ''}`;
    const data = await requestJSON(url);
    const incoming = data.results || [];
    if (reset) state.googleSequences = data.sequences || [];
    if (reset) state.googlePhotos = incoming;
    else {
      const current = new Map(state.googlePhotos.map(item => [item.photo_id, item]));
      incoming.forEach(item => current.set(item.photo_id, item));
      state.googlePhotos = Array.from(current.values());
    }
    state.googlePhotosNextToken = data.nextPageToken || '';
    state.googlePhotosStats = data.stats || null;
    state.googleLibraryLoaded = true;
    $('loadMoreGooglePhotosBtn')?.classList.toggle('hidden', !state.googlePhotosNextToken);
    updateGoogleLibraryStats(data.stats);
    renderGoogleLibrary();
    const total = data.stats?.total ?? state.googlePhotos.length;
    const seqs = data.stats?.sequences ?? (state.googleSequences || []).length;
    const pages = data.pages_loaded ? ` · ${data.pages_loaded} page(s)` : '';
    toast(`${total} photo(s) + ${seqs} sequence(s) loaded${pages}.`);
  } catch (e) {
    if (grid) grid.innerHTML = `<b>Error</b><br>${esc(e.message)}`;
    toast(e.message);
  } finally {
    state.googleLibraryLoading = false;
  }
}

function renderGoogleSequences() {
  const sequences = state.googleSequences || [];
  if (!sequences.length) return '';
  return `
    <div class="google-sequence-section">
      <div class="sequence-title">Street View sequences / videos <span>${sequences.length}</span></div>
      ${sequences.map(seq => {
        const id = seq.sequence_id || seq.name || '';
        const status = seq.status || (seq.done ? 'DONE' : 'PROCESSING');
        const count = seq.photos_count ? `${seq.photos_count} photos` : 'sequence';
        const distance = seq.distance_meters ? `${Number(seq.distance_meters).toFixed(0)} m` : '';
        return `
          <article class="google-sequence-card">
            <div class="sequence-icon">🎞️</div>
            <div>
              <b>${esc(seq.filename || 'Street View sequence')}</b>
              <small>${esc(id)}</small>
              <div class="google-photo-meta">
                <span>${esc(status)}</span>
                <span>${esc(count)}</span>
                ${distance ? `<span>${esc(distance)}</span>` : ''}
              </div>
            </div>
          </article>`;
      }).join('')}
    </div>`;
}

function renderGoogleLibrary() {
  const grid = $('googlePhotoGrid');
  if (!grid) return;
  const items = filteredGooglePhotos();
  grid.classList.toggle('muted-box', !items.length);
  updateGoogleLibraryStats();
  if (!items.length) {
    const total = state.googlePhotos.length;
    const seqCount = (state.googleSequences || []).length;
    if (!total && !seqCount) {
      grid.innerHTML = `
        <div class="library-empty-state">
          <b>No Google Street View photos returned for this connected Google account.</b>
          <span>This calls Google directly. If your photos exist in Google Maps but do not appear here, reconnect with the exact Gmail that owns them. Some Street View Studio/video uploads may be returned as sequences, not individual photos.</span>
        </div>`;
    } else if (!total && seqCount) {
      grid.innerHTML = renderGoogleSequences();
    } else {
      grid.innerHTML = 'No photos match this filter.';
    }
    return;
  }
  const sequencesHtml = state.googlePhotoFilter === 'all' && !state.googlePhotoQuery ? renderGoogleSequences() : '';
  grid.innerHTML = sequencesHtml + items.map(item => {
    const local = item.local || {};
    const img = item.thumbnail_url || item.download_url || item.local?.preview_url || '';
    const p = item.pose || {};
    const gps = p.latitude != null && p.longitude != null ? `${Number(p.latitude).toFixed(6)}, ${Number(p.longitude).toFixed(6)}` : 'GPS ?';
    const connected = item.connections_count ? `${item.connections_count} link(s)` : '0 links';
    const useDisabled = !state.selectedScene ? 'disabled' : '';
    const localTitle = local.matched
      ? `${esc(local.tour_title || '')}<small>${esc(local.scene_title || '')}</small>`
      : '<small>Google account photo · not linked to TwinScopes</small>';
    return `
      <article class="google-photo-card" data-photo-id="${esc(item.photo_id)}">
        <div class="google-photo-thumb">
          ${img ? `<img src="${esc(img)}" alt="Street View">` : `<div class="google-photo-empty">360</div>`}
          <span class="photo-status ${googleStatusClass(item.maps_publish_status)}">${esc(googleStatusLabel(item.maps_publish_status))}</span>
        </div>
        <div class="google-photo-content">
          <div class="google-photo-title">
            <b>${local.matched ? esc(local.scene_title || 'Linked scene') : 'Google account photo'}</b>
            <code>${esc((item.photo_id || '').slice(0, 22))}${item.photo_id && item.photo_id.length > 22 ? '…' : ''}</code>
          </div>
          <p>${localTitle}</p>
          <div class="google-photo-meta">
            <span>📍 ${esc(gps)}</span>
            <span>🧭 ${Number(p.heading || 0).toFixed(1)}°</span>
            <span>🔗 ${esc(connected)}</span>
          </div>
          <div class="google-photo-actions">
            ${item.share_link ? `<a class="icon-action tiny" href="${esc(item.share_link)}" target="_blank" rel="noopener" title="Open Google Maps">↗</a>` : `<span class="icon-action tiny disabled" title="No Google Maps link">↗</span>`}
            <button class="icon-action tiny" data-copy-photo="${esc(item.photo_id)}" title="Copy Photo ID">⧉</button>
            <button class="icon-action tiny" data-link-photo="${esc(item.photo_id)}" data-share-link="${esc(item.share_link || '')}" data-thumb="${esc(item.thumbnail_url || '')}" title="Link to selected scene" ${useDisabled}>⛓</button>
            <button class="icon-action tiny danger" data-delete-photo="${esc(item.photo_id)}" title="Delete from Google">🗑</button>
          </div>
        </div>
      </article>`;
  }).join('');

  grid.querySelectorAll('[data-copy-photo]').forEach(btn => btn.onclick = async () => {
    await navigator.clipboard.writeText(btn.dataset.copyPhoto || '');
    toast('Google Photo ID copied.');
  });
  grid.querySelectorAll('[data-link-photo]').forEach(btn => btn.onclick = () => linkGooglePhotoToSelectedScene(btn.dataset));
  grid.querySelectorAll('[data-delete-photo]').forEach(btn => btn.onclick = () => deleteGooglePhotoFromLibrary(btn.dataset.deletePhoto));
}

async function linkGooglePhotoToSelectedScene(dataset) {
  if (!state.selectedScene) return toast('Select a scene in the editor first.');
  const s = currentScene();
  const ok = confirm(`Link this Google photo to the selected scene?\n\n${s?.title || ''}`);
  if (!ok) return;
  try {
    const data = await requestJSON(`${API}published/google-photos/link-scene/`, {
      method: 'POST',
      body: JSON.stringify({
        photo_id: dataset.linkPhoto,
        source_scene_id: state.selectedScene,
        share_link: dataset.shareLink || '',
        thumbnail_url: dataset.thumb || '',
      }),
    });
    state.project = { publication: data.publication, tour: data.tour, organization: data.organization, place: data.place, scenes: data.scenes, navigation_links: data.navigation_links };
    renderWorkspace();
    await loadGooglePhotos(true);
    toast('Google photo linked to the scene.');
  } catch (e) {
    toast(e.message);
  }
}

async function deleteGooglePhotoFromLibrary(photoId) {
  if (!photoId) return;
  const ok = confirm('Delete this photo from the Google Street View account?\n\nThis does not delete your local images.');
  if (!ok) return;
  try {
    await requestJSON(`${API}published/google-photos/delete/`, {
      method: 'POST',
      body: JSON.stringify({ photo_id: photoId }),
    });
    state.googlePhotos = state.googlePhotos.filter(x => x.photo_id !== photoId);
    renderGoogleLibrary();
    if (state.selectedTour) {
      const refreshed = await requestJSON(`${API}source/tours/${state.selectedTour}/`);
      state.project = refreshed;
      renderWorkspace();
    }
    toast('Photo deleted from Google.');
  } catch (e) {
    toast(e.message);
  }
}

function bindActions() {
  if (state.uiBound) return;
  state.uiBound = true;
  bindClick('runQualityTopBtn', runQualityCheck);
  bindClick('qualityBtn', runQualityCheck);
  bindClick('qualityBtnSide', runQualityCheck);
  bindClick('smartLinkBtn', loadSmartLinks);
  bindClick('smartLinkBtnSide', loadSmartLinks);
  bindClick('applySmartLinksBtn', applySmartLinks);
  bindClick('applyPlaceGpsBtn', applyPlaceGps);
  bindClick('autoLinkBtn', autoLink);
  bindClick('autoLinkBtnSide', autoLink);
  bindClick('publishBtn', publishTour);
  bindClick('publishBtnSide', publishTour);
  bindClick('quickPublishBtn', publishTour);
  bindClick('addManualConnectionBtn', addManualConnection);
  bindClick('retryConnectionsBtn', retryGoogleConnections);
  bindClick('syncGoogleStatusBtn', syncGoogleStatus);
  bindClick('auditConnectionsBtn', auditAndRepairConnections);
  bindClick('saveSceneBtn', saveScene);
  bindClick('deleteGooglePhotoBtn', deleteGooglePhoto);
  bindClick('copyAllLinksBtn', copyAllLinks);
  bindClick('captureCameraBtn', () => syncInputsFromViewer(true));
  bindClick('reloadViewerBtn', () => { state.viewerReadySceneId = null; openViewerInline(); });
  bindClick('focusMapBtn', () => focusSceneOnMap(true));
  bindClick('fitScenesBtn', fitAllScenes);
  bindClick('satelliteToggleBtn', toggleSatellite);
  bindClick('placeSearchBtn', () => $('mapSearchBox').classList.toggle('hidden'));
  bindClick('closeMapSearchBtn', () => $('mapSearchBox').classList.add('hidden'));
  bindClick('autoModeTab', () => setMode('auto'));
  bindClick('manualModeTab', () => setMode('manual'));
  bindClick('alignToTargetBtn', alignToTarget);
  bindClick('prepareTabBtn', () => setMainTab('prepare'));
  bindClick('libraryTabBtn', () => setMainTab('library'));
  bindClick('openLibraryTopBtn', () => setMainTab('library'));
  bindClick('refreshGooglePhotosBtn', () => loadGooglePhotos(true));
  bindClick('loadMoreGooglePhotosBtn', () => loadGooglePhotos(false));
  const gSearch = document.getElementById('googlePhotoSearch');
  if (gSearch) gSearch.addEventListener('input', () => { state.googlePhotoQuery = gSearch.value || ''; renderGoogleLibrary(); });
  document.querySelectorAll('[data-google-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      state.googlePhotoFilter = btn.dataset.googleFilter || 'all';
      document.querySelectorAll('[data-google-filter]').forEach(b => b.classList.toggle('active', b === btn));
      renderGoogleLibrary();
    });
  });

  ['sceneHeading', 'scenePitch', 'sceneFov', 'sceneLat', 'sceneLng'].forEach(id => {
    const node = document.getElementById(id);
    if (!node) return;
    node.addEventListener('input', () => {
      if (id === 'sceneHeading' || id === 'scenePitch' || id === 'sceneFov') setViewerCameraFromInputs(true);
      if (id === 'sceneLat' || id === 'sceneLng') {
        const p = selectedLatLngFromInputs();
        if (p) updateSelectedMarkerPosition(p);
        updateHeadingOverlay();
      }
    });
  });
}

async function applyPlaceGps() {
  if (!state.selectedTour) return;
  const data = await requestJSON(`${API}source/tours/${state.selectedTour}/apply-place-gps/`, { method: 'POST', body: JSON.stringify({ apply_to: 'missing' }) });
  state.project = data;
  renderWorkspace();
  toast('GPS applied to scenes without GPS.');
}

async function autoLink() {
  if (!state.selectedTour) return;
  const data = await requestJSON(`${API}source/tours/${state.selectedTour}/auto-link/`, { method: 'POST', body: JSON.stringify({ bidirectional: true }) });
  state.project = data;
  renderWorkspace();
  toast('Two-way navigation created.');
}

async function saveScene() {
  const s = currentScene();
  if (!s) return;
  const payload = {
    gps: { latitude: $('sceneLat').value, longitude: $('sceneLng').value },
    camera: {
      heading: normalizeHeading($('sceneHeading').value),
      pitch: clamp($('scenePitch').value, -90, 90, 0),
      roll: clamp($('sceneRoll').value, -180, 180, 0),
      initial_fov: clamp($('sceneFov').value, 10, 120, 90),
    },
  };
  const data = await requestJSON(`${API}source/scenes/${s.id}/state/`, { method: 'POST', body: JSON.stringify(payload) });
  const idx = state.project.scenes.findIndex(x => Number(x.id) === Number(s.id));
  if (idx >= 0) state.project.scenes[idx] = data.scene;
  renderWorkspace();
  toast('GPS and camera saved.');
}

async function deleteGooglePhoto() {
  const s = currentScene();
  if (!s) return;
  if (!s.google?.is_published) return toast('This image is not published on Google yet.');
  const ok = confirm(`Delete this image from Google Street View?\n\n${s.title}\n\nThe original image stays in your app.`);
  if (!ok) return;
  $('publishLogs').textContent = `Suppression Google Street View: ${s.title}\n`;
  try {
    const data = await requestJSON(`${API}source/scenes/${s.id}/delete-google-photo/`, { method: 'POST', body: JSON.stringify({ delete_from_google: true, clear_local_if_missing: true }) });
    state.project = { publication: data.publication, tour: data.tour, organization: data.organization, place: data.place, scenes: data.scenes, navigation_links: data.navigation_links };
    $('publishLogs').textContent = JSON.stringify(data, null, 2);
    renderWorkspace();
    toast(data.ok ? 'Photo deleted from Google.' : 'Deletion completed with warnings.');
  } catch (e) {
    $('publishLogs').textContent = JSON.stringify(e.data || { error: e.message }, null, 2);
    toast(e.message);
  }
}

async function publishTour() {
  if (!state.selectedTour) return toast('Choose a tour first.');
  $('publishLogs').textContent = 'Starting publish job...\n';
  try {
    const data = await requestJSON(`${API}source/tours/${state.selectedTour}/publish/background/`, {
      method: 'POST',
      body: JSON.stringify({
        skip_published: true,
        force_reupload: false,
        auto_link: false,
        run_mode: 'auto',
        local_fallback: true,
        indexing_wait_seconds: 2
      })
    });
    if (data.publication) state.project = { publication: data.publication, tour: data.tour, organization: data.organization, place: data.place, scenes: data.scenes, navigation_links: data.navigation_links };
    state.activeJob = data.job || null;
    $('publishLogs').textContent = JSON.stringify(data.job || data, null, 2);
    renderJobProgress(data.job || null);
    startJobPolling(data.job || null);
    renderWorkspace();
    const mode = data.execution_mode === 'local_thread' ? 'local background' : (data.execution_mode || 'background');
    toast(`Publish started (${mode}).`);
  } catch (e) {
    const payload = e.data || { error: e.message };
    $('publishLogs').textContent = JSON.stringify(payload, null, 2);
    if (payload.quality) {
      state.qualityReport = payload.quality;
      renderQualitySummary();
    }
    toast(e.message);
  }
}

function qualityBadgeClass(status) {
  if (status === 'ready') return 'good';
  if (status === 'blocked') return 'bad';
  return 'warn';
}

function renderQualitySummary() {
  const box = $('qualitySummary');
  const q = state.qualityReport;
  if (!q) {
    box.classList.add('muted-box');
    box.innerHTML = 'Run a check before publishing.';
    return;
  }
  const issues = q.issues || [];
  const topIssues = issues.slice(0, 6).map(i => `
    <div class="qa-issue ${esc(i.level)}">
      <b>${esc(i.level)}</b>
      <span>${esc(i.scene_title || i.code)} — ${esc(i.message)}</span>
    </div>`).join('');
  box.classList.remove('muted-box');
  box.innerHTML = `
    <div class="quality-score ${qualityBadgeClass(q.status)}">
      <strong>${Number(q.score || 0)}</strong><span>${esc(q.status || '')}</span>
    </div>
    <div class="qa-counts">
      <span>${q.counts?.blockers || 0} blockers</span>
      <span>${q.counts?.warnings || 0} warnings</span>
      <span>${q.counts?.navigation_links || 0} links</span>
    </div>
    ${topIssues || '<div class="qa-ok">Ready to publish.</div>'}
  `;
}

async function runQualityCheck() {
  if (!state.selectedTour) return toast('Choose a tour first.');
  setHtml('qualitySummary', 'Checking GPS, images, camera and links...');
  try {
    const data = await requestJSON(`${API}source/tours/${state.selectedTour}/quality-check/`);
    state.qualityReport = data.quality;
    renderQualitySummary();
    await loadHistoryAndAnalytics();
    toast(`Quality: ${data.quality.status} (${data.quality.score}/100)`);
  } catch (e) {
    toast(e.message);
  }
}

function renderSmartLinkSuggestions() {
  const box = $('smartLinkSuggestions');
  const data = state.smartLinkData;
  if (!data || !data.suggestions) {
    box.classList.add('muted-box');
    box.innerHTML = 'No suggestion yet.';
    return;
  }
  const list = data.suggestions;
  box.classList.remove('muted-box');
  box.innerHTML = list.length ? list.map(s => `
    <label class="smart-link-row ${s.already_exists ? 'exists' : ''}">
      <input type="checkbox" data-smart-id="${esc(s.id)}" ${s.recommended ? 'checked' : ''} ${s.already_exists ? 'disabled' : ''}>
      <span>
        <b>${esc(s.from_title)} → ${esc(s.to_title)}</b>
        <small>${s.distance_m == null ? 'distance unknown' : Number(s.distance_m).toFixed(1) + ' m'} · heading ${Number(s.heading || 0).toFixed(1)}° · ${esc(s.reason)}</small>
      </span>
    </label>
  `).join('') : 'No suggestion found.';
}

async function loadSmartLinks() {
  if (!state.selectedTour) return toast('Choose a tour first.');
  setHtml('smartLinkSuggestions', 'Analyzing ordered scenes and GPS distance...');
  try {
    const data = await requestJSON(`${API}source/tours/${state.selectedTour}/smart-link/?bidirectional=1&max_distance_m=250`);
    state.smartLinkData = data;
    renderSmartLinkSuggestions();
    toast(`${data.recommended_count || 0} recommended link(s).`);
  } catch (e) {
    toast(e.message);
  }
}

async function applySmartLinks() {
  if (!state.selectedTour) return toast('Choose a tour first.');
  const ids = Array.from(document.querySelectorAll('[data-smart-id]:checked')).map(x => x.dataset.smartId);
  if (!ids.length) return toast('No smart link selected.');
  try {
    const data = await requestJSON(`${API}source/tours/${state.selectedTour}/smart-link/apply/`, {
      method: 'POST',
      body: JSON.stringify({ suggestion_ids: ids, bidirectional: true, max_distance_m: 250 })
    });
    state.project = { publication: data.publication, tour: data.tour, organization: data.organization, place: data.place, scenes: data.scenes, navigation_links: data.navigation_links };
    state.smartLinkData = null;
    renderWorkspace();
    await loadHistoryAndAnalytics();
    toast(`Smart links applied: ${data.applied?.length || 0}`);
  } catch (e) {
    toast(e.message);
  }
}

function getJobStage(job) {
  const log = Array.isArray(job?.log) ? job.log : [];
  const lastWithStep = [...log].reverse().find(x => x && x.step);
  const last = lastWithStep || log[log.length - 1] || null;
  const step = String(last?.step || '').toLowerCase();
  const total = Number(job?.total_scenes || last?.total || 0);
  const current = Number(last?.current || job?.published_scenes || 0);
  const labelMap = {
    queued: 'Queued',
    preparing: 'Preparing publish job',
    uploading: `Uploading ${current || 0} / ${total || 0}`,
    creating: `Creating Google photos ${current || 0} / ${total || 0}`,
    indexing: 'Waiting for indexing',
    connections: 'Updating connections',
    done: 'Done',
    failed: 'Failed'
  };
  let label = labelMap[step] || String(job?.status || 'Job');
  if (String(job?.status || '').toLowerCase() === 'failed') label = 'Failed';
  return { label, message: last?.message || '', step, current, total };
}

function renderJobProgress(job) {
  const box = $('jobProgress');
  if (!box) return;
  if (!job) {
    box.classList.add('muted-box');
    box.innerHTML = 'No publish job yet.';
    return;
  }
  const total = Number(job.total_scenes || 0);
  const done = Number(job.published_scenes || 0);
  const pct = total ? Math.min(100, Math.round((done / total) * 100)) : 0;
  const stage = getJobStage(job);
  box.classList.remove('muted-box');
  box.innerHTML = `
    <div class="job-stage">${esc(stage.label)}</div>
    <div class="job-head"><b>${esc(job.status)}</b><span>${done}/${total}</span></div>
    <div class="job-bar"><i style="width:${pct}%"></i></div>
    ${stage.message ? `<div class="job-last">${esc(stage.message)}</div>` : ''}
    ${job.error ? `<div class="job-error">${esc(job.error)}</div>` : ''}
  `;
}

function startJobPolling(job) {
  if (!job || !job.public_id) return;
  if (state.jobPollTimer) clearInterval(state.jobPollTimer);
  const tick = async () => {
    try {
      const data = await requestJSON(`${API}source/publish-jobs/${job.public_id}/`);
      state.activeJob = data.job;
      renderJobProgress(data.job);
      $('publishLogs').textContent = JSON.stringify(data.job || data, null, 2);
      if (data.publication) {
        state.project = { publication: data.publication, tour: data.tour, organization: data.organization, place: data.place, scenes: data.scenes, navigation_links: data.navigation_links };
        renderWorkspace();
      }
      const status = String(data.job?.status || '').toLowerCase();
      if (['succeeded', 'succeeded_with_warnings', 'failed'].includes(status)) {
        clearInterval(state.jobPollTimer);
        state.jobPollTimer = null;
        await loadHistoryAndAnalytics();
        toast(status === 'failed' ? 'Publishing failed.' : 'Publishing finished.');
      }
    } catch (e) {
      console.warn(e);
    }
  };
  tick();
  state.jobPollTimer = setInterval(tick, 3500);
}

function renderAnalyticsSummary() {
  const box = $('analyticsSummary');
  const a = state.analyticsSummary;
  if (!a) {
    box.classList.add('muted-box');
    box.innerHTML = 'No analytics yet.';
    return;
  }
  const q = a.latest_quality;
  box.classList.remove('muted-box');
  box.innerHTML = `
    <div class="analytics-grid">
      <span><b>${a.scenes || 0}</b><small>Scenes</small></span>
      <span><b>${a.published || 0}</b><small>Published</small></span>
      <span><b>${a.connected || 0}</b><small>Connected</small></span>
      <span><b>${q ? q.score : '-'}</b><small>Quality</small></span>
    </div>
  `;
}

function renderHistoryList() {
  const box = $('historyList');
  const events = state.historyEvents || [];
  if (!events.length) {
    box.classList.add('muted-box');
    box.innerHTML = 'No history yet.';
    return;
  }
  box.classList.remove('muted-box');
  box.innerHTML = events.slice(0, 12).map(ev => `
    <div class="history-row">
      <b>${esc(ev.action)}</b>
      <span>${esc(ev.message || '')}</span>
      <small>${esc(new Date(ev.created_at).toLocaleString())}</small>
    </div>
  `).join('');
}

async function loadHistoryAndAnalytics() {
  if (!state.selectedTour) return;
  try {
    const [history, analytics] = await Promise.all([
      requestJSON(`${API}source/tours/${state.selectedTour}/history/?limit=60`),
      requestJSON(`${API}source/tours/${state.selectedTour}/analytics/`),
    ]);
    state.historyEvents = history.events || [];
    state.analyticsSummary = analytics.summary || null;
    renderHistoryList();
    renderAnalyticsSummary();
  } catch (e) {
    console.warn(e);
  }
}

async function copyAllLinks() {
  if (!state.shareText) return toast('No links to copy.');
  await navigator.clipboard.writeText(state.shareText);
  toast('Links copied.');
}

function toggleSatellite() {
  if (!state.editorMap) return;
  state.editorMapType = state.editorMapType === 'roadmap' ? 'satellite' : 'roadmap';
  state.editorMap.setMapTypeId(state.editorMapType);
  $('satelliteToggleBtn').textContent = state.editorMapType === 'roadmap' ? 'Satellite' : 'Plan';
}
