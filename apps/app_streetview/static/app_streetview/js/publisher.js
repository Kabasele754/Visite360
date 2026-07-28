(() => {
  const root = document.getElementById('streetviewApp');
  const apiBase = root?.dataset.apiBase || '/apis/streetview/';
  const $ = (id) => document.getElementById(id);
  const rad = (deg) => Number(deg || 0) * Math.PI / 180;
  const deg = (r) => ((Number(r || 0) * 180 / Math.PI) + 360) % 360;

  const app = {
    config: {},
    tours: [],
    tour: null,
    scenes: [],
    links: [],
    selectedId: null,
    activeStep: 'images',
    map: null,
    mapMarkers: new Map(),
    mapAutocomplete: null,
    viewer: null,
    marziScene: null,
    currentView: null,
    shareText: '',
  };

  function csrfToken() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  async function api(path, options = {}) {
    const method = (options.method || 'GET').toUpperCase();
    const headers = options.headers || {};
    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }
    if (method !== 'GET') headers['X-CSRFToken'] = csrfToken();

    const res = await fetch(apiBase + path.replace(/^\//, ''), {
      credentials: 'same-origin',
      ...options,
      headers,
    });

    const text = await res.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch (_) { data = { raw: text }; }
    if (!res.ok) {
      const error = new Error(data.error || data.detail || `Erreur HTTP ${res.status}`);
      error.data = data;
      error.status = res.status;
      throw error;
    }
    return data;
  }

  function toast(message, type = 'ok') {
    const box = $('toastBox');
    if (!box) return;
    const el = document.createElement('div');
    el.className = `sv-toast ${type}`;
    el.textContent = `${type === 'bad' ? '⚠️' : '✅'} ${message}`;
    box.appendChild(el);
    setTimeout(() => el.remove(), 4200);
  }

  function escapeHtml(value = '') {
    return String(value).replace(/[&<>'"]/g, (ch) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    }[ch]));
  }

  function setLoading(button, loading, text) {
    if (!button) return;
    if (loading) {
      button.dataset.oldText = button.textContent;
      button.textContent = text || 'Chargement...';
      button.disabled = true;
    } else {
      button.textContent = button.dataset.oldText || button.textContent;
      button.disabled = false;
    }
  }

  function normalizeScene(item) {
    const gps = item.gps || {};
    const orientation = item.orientation || {};
    return {
      id: String(item.id),
      backendId: item.id,
      title: item.title || `Scène ${item.id}`,
      description: item.description || '',
      imageUrl: item.image_url || item.google?.thumbnail_url || '',
      width: item.image_width || 0,
      height: item.image_height || 0,
      xmpDetected: !!item.xmp_detected,
      ratioOk: !!item.is_full_360_ratio,
      order: item.order || 0,
      gps: {
        lat: gps.latitude ?? '',
        lng: gps.longitude ?? '',
        alt: gps.altitude ?? '',
      },
      camera: {
        heading: orientation.heading ?? 0,
        pitch: orientation.pitch ?? 0,
        roll: orientation.roll ?? 0,
        fov: orientation.initial_fov ?? 90,
      },
      google: {
        photoId: item.google?.photo_id || '',
        shareLink: item.google?.share_link || '',
        thumbnailUrl: item.google?.thumbnail_url || '',
        publishStatus: item.google?.publish_status || 'local',
        mapsPublishStatus: item.google?.maps_publish_status || '',
        transferStatus: item.google?.transfer_status || '',
        viewCount: Number(item.google?.view_count || 0),
        connectionStatus: item.google?.connection_sync_status || 'pending',
        connectionAudit: item.google?.connection_audit || {},
        lastError: item.google?.last_error || '',
        remoteOnly: !!item.google?.remote_only,
      },
    };
  }

  function hydrateTour(tour) {
    app.tour = tour;
    app.scenes = (tour.scenes || []).map(normalizeScene);
    app.links = (tour.connections || []).map((link) => ({
      id: String(link.id),
      from: String(link.from_scene),
      to: String(link.to_scene),
      label: link.label || 'Navigation',
      yaw: Number(link.yaw || 0),
      pitch: Number(link.pitch || 0),
      order: link.order || 0,
    }));
    if (!app.selectedId || !app.scenes.some(s => s.id === app.selectedId)) {
      app.selectedId = app.scenes[0]?.id || null;
    }
    renderAll();
    refreshMapMarkers();
  }

  function selectedScene() {
    return app.scenes.find(s => s.id === app.selectedId) || null;
  }

  function hasGps(scene) {
    return scene && scene.gps.lat !== '' && scene.gps.lat !== null && scene.gps.lng !== '' && scene.gps.lng !== null;
  }

  function isPublished(scene) {
    return !!scene?.google?.photoId;
  }

  function isConnected(scene) {
    return scene?.google?.publishStatus === 'connected';
  }

  function sceneShareLink(scene) {
    if (!scene) return '';
    return scene.google.shareLink || (scene.google.photoId ? `https://www.google.com/maps?layer=c&panoid=${encodeURIComponent(scene.google.photoId)}` : '');
  }

  function badgesForScene(scene) {
    const out = [];
    out.push(scene.ratioOk ? '<span class="sv-badge ok">360</span>' : '<span class="sv-badge warn">Ratio ?</span>');
    out.push(hasGps(scene) ? '<span class="sv-badge ok">GPS</span>' : '<span class="sv-badge bad">GPS manquant</span>');
    if (String(scene.google.mapsPublishStatus || '').includes('REJECT')) out.push('<span class="sv-badge bad">Google rejected</span>');
    else if (scene.google.mapsPublishStatus === 'PUBLISHED') out.push('<span class="sv-badge ok">Google accepted</span>');
    else if (isPublished(scene)) out.push('<span class="sv-badge blue">Google processing</span>');
    else out.push('<span class="sv-badge">Locale</span>');
    if (isPublished(scene)) out.push(`<span class="sv-badge ${['synced','not_required'].includes(scene.google.connectionStatus) ? 'ok' : 'warn'}">Links ${escapeHtml(scene.google.connectionStatus || 'pending')}</span>`);
    return out.join('');
  }

  async function loadConfig() {
    try {
      app.config = await api('config/');
      const connect = $('connectGoogle');
      if (connect) connect.href = app.config.oauthStartUrl || `${apiBase}oauth/start/`;
      renderGoogleStatus();
    } catch (err) {
      console.error(err);
      toast('Configuration Street View impossible à charger.', 'bad');
    }
  }

  function renderGoogleStatus() {
    const pill = $('googlePill');
    const connect = $('connectGoogle');
    const ok = !!app.config.googleConnected;
    if (pill) {
      pill.className = `sv-pill ${ok ? 'ok' : 'bad'}`;
      pill.textContent = ok ? `Google connecté${app.config.googleEmail ? ' · ' + app.config.googleEmail : ''}` : 'Google non connecté';
    }
    if (connect) connect.textContent = ok ? 'Reconnecter' : 'Connecter Google';
  }

  async function loadTours({ silent = false } = {}) {
    try {
      const data = await api('tours/');
      app.tours = data.results || [];
      renderTours();
      if (!app.tour && app.tours[0]) await selectTour(app.tours[0].id, { silent: true });
      if (!silent) toast('Projets chargés.');
    } catch (err) {
      console.error(err);
      toast(err.message || 'Impossible de charger les projets.', 'bad');
    }
  }

  async function selectTour(id, { silent = false } = {}) {
    try {
      const data = await api(`tours/${id}/`);
      hydrateTour(data.tour);
      if (!silent) toast('Projet ouvert.');
    } catch (err) {
      console.error(err);
      toast(err.message || 'Impossible d’ouvrir ce projet.', 'bad');
    }
  }

  async function createTour() {
    const input = $('newTourTitle');
    const title = input?.value.trim() || 'Nouvelle visite Street View';
    try {
      const data = await api('tours/create/', {
        method: 'POST',
        body: JSON.stringify({
        title,
        description: '',
        storage_policy: $('newTourStoragePolicy')?.value || 'delete_after_verified',
        auto_connect: true,
        auto_sync_status: true,
      }),
      });
      if (input) input.value = '';
      await loadTours({ silent: true });
      await selectTour(data.tour.id);
      switchStep('images');
      toast('Visite créée. Importe les images maintenant.');
    } catch (err) {
      console.error(err);
      toast(err.message || 'Création impossible.', 'bad');
    }
  }

  function renderTours() {
    const list = $('tourList');
    const empty = $('tourEmpty');
    if (!list) return;
    empty?.classList.toggle('hidden', app.tours.length > 0);
    list.innerHTML = app.tours.map(t => `
      <article class="sv-tour-card ${app.tour && String(app.tour.id) === String(t.id) ? 'active' : ''}" data-id="${t.id}">
        <h3>${escapeHtml(t.title)}</h3>
        <p>${escapeHtml(t.status || 'draft')} · #${t.id}</p>
      </article>
    `).join('');
    list.querySelectorAll('.sv-tour-card').forEach(card => {
      card.addEventListener('click', () => selectTour(card.dataset.id));
    });
  }

  function switchStep(step) {
    app.activeStep = step;
    document.querySelectorAll('.sv-step').forEach(el => el.classList.remove('active'));
    $(`step-${step}`)?.classList.add('active');
    document.querySelectorAll('.sv-step-tab').forEach(btn => btn.classList.toggle('active', btn.dataset.step === step));
    if (step === 'prepare') renderEditor();
    if (step === 'navigation') renderNavigation();
    if (step === 'publish') renderPublish();
  }

  function renderAll() {
    renderTours();
    renderHeaderStats();
    renderScenes();
    renderEditor();
    renderNavigation();
    renderPublish();
  }

  function renderHeaderStats() {
    const scenes = app.scenes.length;
    const gps = app.scenes.filter(hasGps).length;
    const published = app.scenes.filter(isPublished).length;
    const links = app.links.length;
    const tourTitle = $('activeTourTitle');
    const subtitle = $('activeTourSubtitle');
    if (tourTitle) tourTitle.textContent = app.tour ? app.tour.title : 'Aucune visite sélectionnée';
    if (subtitle) subtitle.textContent = app.tour ? `${scenes} image(s), ${gps} avec GPS, ${published} publiée(s).` : 'Crée ou ouvre un projet à gauche.';
    $('statScenes') && ($('statScenes').textContent = scenes);
    $('statGps') && ($('statGps').textContent = gps);
    $('statPublished') && ($('statPublished').textContent = published);
    $('statLinks') && ($('statLinks').textContent = links);
    $('sceneCountText') && ($('sceneCountText').textContent = `${scenes} image${scenes > 1 ? 's' : ''}`);
  }

  function renderScenes() {
    const grid = $('sceneGrid');
    const empty = $('sceneEmpty');
    if (!grid) return;
    empty?.classList.toggle('hidden', app.scenes.length > 0);
    grid.innerHTML = app.scenes.map(scene => `
      <article class="sv-scene-card ${scene.id === app.selectedId ? 'active' : ''}" data-id="${scene.id}">
        ${scene.imageUrl ? `<img src="${escapeHtml(scene.imageUrl)}" alt="${escapeHtml(scene.title)}" loading="lazy">` : `<div class="sv-scene-placeholder">GOOGLE 360</div>`}
        <div class="sv-scene-card-body">
          <h3>${escapeHtml(scene.title)}</h3>
          <p>${hasGps(scene) ? `${scene.gps.lat}, ${scene.gps.lng}` : 'GPS manquant'}</p>
          <div class="sv-badges">${badgesForScene(scene)}</div>
        </div>
      </article>
    `).join('');
    grid.querySelectorAll('.sv-scene-card').forEach(card => {
      card.addEventListener('click', () => {
        app.selectedId = card.dataset.id;
        renderAll();
        switchStep('prepare');
      });
    });
  }

  function renderEditor() {
    const scene = selectedScene();
    $('noSceneSelected')?.classList.toggle('hidden', !!scene);
    $('sceneEditor')?.classList.toggle('hidden', !scene);
    $('viewScene360Btn') && ($('viewScene360Btn').disabled = !scene);
    $('viewScene360SideBtn') && ($('viewScene360SideBtn').disabled = !scene);
    if (!scene) return;

    $('editorImage') && ($('editorImage').src = scene.imageUrl);
    $('editorStatus') && ($('editorStatus').innerHTML = badgesForScene(scene));
    $('sceneTitleInput') && ($('sceneTitleInput').value = scene.title);
    $('sceneDescriptionInput') && ($('sceneDescriptionInput').value = scene.description);
    $('sceneLatInput') && ($('sceneLatInput').value = scene.gps.lat);
    $('sceneLngInput') && ($('sceneLngInput').value = scene.gps.lng);
    $('sceneHeadingInput') && ($('sceneHeadingInput').value = scene.camera.heading);
    $('scenePitchInput') && ($('scenePitchInput').value = scene.camera.pitch);
  }

  async function saveSelectedScene({ silent = false } = {}) {
    const scene = selectedScene();
    if (!scene) return;
    const payload = {
      title: $('sceneTitleInput')?.value.trim() || scene.title,
      description: $('sceneDescriptionInput')?.value || '',
      gps: {
        latitude: $('sceneLatInput')?.value || null,
        longitude: $('sceneLngInput')?.value || null,
        altitude: scene.gps.alt || null,
      },
      orientation: {
        heading: $('sceneHeadingInput')?.value || 0,
        pitch: $('scenePitchInput')?.value || 0,
        roll: scene.camera.roll || 0,
        initial_fov: scene.camera.fov || 90,
      },
    };
    try {
      const data = await api(`scenes/${scene.backendId}/update/`, { method: 'POST', body: JSON.stringify(payload) });
      const updated = normalizeScene(data.scene);
      app.scenes = app.scenes.map(s => s.id === scene.id ? updated : s);
      app.selectedId = updated.id;
      renderAll();
      refreshMapMarkers();
      if (!silent) toast('Scène sauvegardée.');
    } catch (err) {
      console.error(err);
      toast(err.message || 'Sauvegarde scène impossible.', 'bad');
    }
  }

  async function deleteSelectedScene() {
    const scene = selectedScene();
    if (!scene) return;
    if (!confirm(`Supprimer ${scene.title} ?`)) return;
    try {
      await api(`scenes/${scene.backendId}/delete/`, { method: 'POST', body: JSON.stringify({}) });
      await reloadActiveTour();
      toast('Scène supprimée.');
    } catch (err) {
      console.error(err);
      toast(err.message || 'Suppression impossible.', 'bad');
    }
  }

  async function reloadActiveTour() {
    if (!app.tour) return;
    await selectTour(app.tour.id, { silent: true });
  }

  async function handleFiles(files) {
    if (!app.tour) return toast('Crée ou sélectionne d’abord une visite.', 'bad');
    const realFiles = [...files].filter(file => file.type.startsWith('image/'));
    if (!realFiles.length) return toast('Aucune image valide.', 'bad');
    const form = new FormData();
    realFiles.forEach(file => form.append('images', file));
    try {
      toast('Upload en cours...');
      await api(`tours/${app.tour.id}/upload-scenes/`, { method: 'POST', body: form, headers: {} });
      await reloadActiveTour();
      toast('Images importées.');
    } catch (err) {
      console.error(err);
      toast(err.message || 'Upload impossible.', 'bad');
    }
  }

  function setDirectStatus(message, type = '') {
    const box = $('directPublishStatus');
    if (!box) return;
    box.className = `sv-direct-status ${type}`.trim();
    box.textContent = message;
  }

  async function directPublishScene() {
    if (!app.tour) return toast('Create or select a Google project first.', 'bad');
    const file = $('directImageInput')?.files?.[0];
    const lat = $('directLatInput')?.value;
    const lng = $('directLngInput')?.value;
    if (!file) return setDirectStatus('Choose a 360 panorama first.', 'bad');
    if (!lat || !lng) return setDirectStatus('Latitude and longitude are required.', 'bad');
    const form = new FormData();
    form.append('image', file);
    form.append('title', $('directTitleInput')?.value.trim() || file.name.replace(/\.[^.]+$/, ''));
    form.append('latitude', lat);
    form.append('longitude', lng);
    form.append('heading', $('directHeadingInput')?.value || '0');
    form.append('pitch', '0');
    form.append('roll', '0');
    form.append('initial_fov', '90');
    const capture = $('directCaptureTimeInput')?.value;
    if (capture) form.append('capture_time', new Date(capture).toISOString());
    const btn = $('directPublishBtn');
    setLoading(btn, true, 'Uploading to Google...');
    setDirectStatus('Validating the panorama, adding Photo Sphere metadata and streaming it to Google Street View...');
    try {
      const data = await api(`tours/${app.tour.id}/direct-publish-scene/`, { method: 'POST', body: form, headers: {} });
      await reloadActiveTour();
      setDirectStatus(`Google photo created (${data.scene?.google?.photo_id || 'indexing'}). The original bytes were not stored in Twinscopes.`, 'ok');
      if ($('directImageInput')) $('directImageInput').value = '';
      toast('Panorama sent directly to Google.');
    } catch (err) {
      console.error(err);
      setDirectStatus(err.message || 'Direct Google upload failed.', 'bad');
      toast(err.message || 'Direct Google upload failed.', 'bad');
    } finally {
      setLoading(btn, false);
    }
  }

  async function syncDirectProjectStatus() {
    if (!app.tour) return toast('Select a project first.', 'bad');
    const btn = $('syncDirectStatusBtn') || $('syncProjectGoogleBtn');
    setLoading(btn, true, 'Synchronizing...');
    try {
      const data = await api(`tours/${app.tour.id}/google-status-sync/`, { method: 'POST', body: JSON.stringify({}) });
      await reloadActiveTour();
      setDirectStatus(`Google status: ${data.published || 0} published, ${data.rejected || 0} rejected, ${data.connections_synced || 0} navigation states verified.`, data.rejected ? 'bad' : 'ok');
      toast('Google acceptance status synchronized.');
    } catch (err) {
      console.error(err);
      setDirectStatus(err.message || 'Google status synchronization failed.', 'bad');
      toast(err.message || 'Google status synchronization failed.', 'bad');
    } finally {
      setLoading(btn, false);
    }
  }

  async function saveProject() {
    if (!app.tour) return;
    try {
      const payload = buildProjectPayload();
      await api(`tours/${app.tour.id}/save-project/`, { method: 'POST', body: JSON.stringify(payload) });
      toast('Projet sauvegardé.');
    } catch (err) {
      console.error(err);
      toast(err.message || 'Sauvegarde projet impossible.', 'bad');
    }
  }

  function buildProjectPayload() {
    return {
      scenes: app.scenes.map(s => ({
        id: s.backendId,
        title: s.title,
        description: s.description,
        gps: { latitude: s.gps.lat || null, longitude: s.gps.lng || null, altitude: s.gps.alt || null },
        orientation: {
          heading: s.camera.heading || 0,
          pitch: s.camera.pitch || 0,
          roll: s.camera.roll || 0,
          initial_fov: s.camera.fov || 90,
        },
      })),
      connections: app.links.map((l, index) => ({
        from_scene: Number(l.from),
        to_scene: Number(l.to),
        label: l.label || 'Navigation',
        yaw: l.yaw || 0,
        pitch: l.pitch || 0,
        order: index,
      })),
      hotspots: [],
    };
  }

  function renderNavigation() {
    renderHeaderStats();
    const list = $('routeList');
    const empty = $('routeEmpty');
    if (!list) return;
    const canRoute = app.scenes.length >= 2;
    empty?.classList.toggle('hidden', canRoute);
    if (!canRoute) {
      list.innerHTML = '';
    } else {
      const linkKeys = new Set(app.links.map(l => `${l.from}->${l.to}`));
      list.innerHTML = app.scenes.map((scene, index) => {
        const next = app.scenes[index + 1];
        if (!next) return '';
        const forward = linkKeys.has(`${scene.backendId}->${next.backendId}`);
        const backward = linkKeys.has(`${next.backendId}->${scene.backendId}`);
        return `
          <div class="sv-route-item">
            <img src="${escapeHtml(scene.imageUrl)}" alt="">
            <div><b>${escapeHtml(scene.title)}</b><p class="sv-muted">${forward ? '✅ aller créé' : '⚪ aller manquant'}</p></div>
            <div class="sv-route-arrow">⇄</div>
            <div><b>${escapeHtml(next.title)}</b><p class="sv-muted">${backward ? '✅ retour créé' : '⚪ retour manquant'}</p></div>
          </div>`;
      }).join('');
    }
    const options = app.scenes.map(s => `<option value="${s.backendId}">${escapeHtml(s.title)}</option>`).join('');
    $('manualFrom') && ($('manualFrom').innerHTML = options);
    $('manualTo') && ($('manualTo').innerHTML = options);
    if (app.scenes[1] && $('manualTo')) $('manualTo').value = app.scenes[1].backendId;
  }

  async function autoConnect() {
    if (!app.tour) return toast('Aucun projet actif.', 'bad');
    if (app.scenes.length < 2) return toast('Il faut au moins 2 images.', 'bad');
    const btn = $('autoConnectBtn');
    setLoading(btn, true, 'Création...');
    try {
      const data = await api(`tours/${app.tour.id}/auto-connect/`, {
        method: 'POST',
        body: JSON.stringify({ replace: true, bidirectional: true }),
      });
      hydrateTour(data.tour);
      switchStep('navigation');
      toast('Navigation aller/retour créée.');
    } catch (err) {
      console.error(err);
      toast(err.message || 'Auto-liaison impossible.', 'bad');
    } finally {
      setLoading(btn, false);
    }
  }

  async function addManualLink() {
    if (!app.tour) return;
    const from = $('manualFrom')?.value;
    const to = $('manualTo')?.value;
    if (!from || !to || from === to) return toast('Choisis deux scènes différentes.', 'bad');
    const links = [...app.links, { from, to, label: $('manualLabel')?.value || 'Navigation', yaw: 0, pitch: 0 }];
    try {
      const data = await api(`tours/${app.tour.id}/save-connections/`, {
        method: 'POST',
        body: JSON.stringify({ connections: links.map((l, i) => ({ from_scene: l.from, to_scene: l.to, label: l.label, order: i })) }),
      });
      await reloadActiveTour();
      $('manualLabel') && ($('manualLabel').value = '');
      toast(`${data.created || 0} lien(s) enregistré(s).`);
    } catch (err) {
      console.error(err);
      toast(err.message || 'Ajout du lien impossible.', 'bad');
    }
  }

  function readinessItems() {
    const scenes = app.scenes.length;
    return [
      { ok: !!app.tour, label: 'Projet sélectionné' },
      { ok: scenes > 0, label: 'Images importées' },
      { ok: scenes > 0 && app.scenes.every(hasGps), label: 'Toutes les images ont GPS' },
      { ok: app.config.googleConnected, label: 'Compte Google connecté' },
      { ok: scenes < 2 || app.links.length > 0, label: 'Navigation Street View créée' },
      { ok: scenes > 0 && app.scenes.every(s => s.ratioOk || s.xmpDetected), label: 'Images 360 compatibles recommandées' },
    ];
  }

  function renderPublish() {
    renderHeaderStats();
    const box = $('readinessBox');
    if (!box) return;
    box.innerHTML = readinessItems().map(item => `
      <div class="sv-ready-item ${item.ok ? 'ok' : 'bad'}">${item.ok ? '✅' : '⚠️'} ${item.label}</div>
    `).join('');
  }

  async function publishTour() {
    if (!app.tour) return toast('Aucun projet actif.', 'bad');
    if (!app.config.googleConnected) return toast('Connecte d’abord ton compte Google.', 'bad');
    const missing = app.scenes.filter(s => !hasGps(s));
    if (missing.length) return toast('Certaines images n’ont pas de GPS.', 'bad');

    const btn = $('publishBtn');
    setLoading(btn, true, 'Publication...');
    $('publishLog')?.classList.remove('hidden');
    $('publishLog').textContent = 'Sauvegarde projet...\n';
    try {
      await api(`tours/${app.tour.id}/save-project/`, { method: 'POST', body: JSON.stringify(buildProjectPayload()) });
      if (app.scenes.length >= 2 && !app.links.length) {
        $('publishLog').textContent += 'Auto-liaison des scènes...\n';
        await api(`tours/${app.tour.id}/auto-connect/`, { method: 'POST', body: JSON.stringify({ replace: false, bidirectional: true }) });
      }
      $('publishLog').textContent += 'Envoi vers Google Street View...\n';
      const data = await api(`tours/${app.tour.id}/publish/`, {
        method: 'POST',
        body: JSON.stringify({ skip_published: true, force_reupload: false, auto_connect: false, bidirectional: true }),
      });
      $('publishLog').textContent += JSON.stringify(data.job || data, null, 2);
      await reloadActiveTour();
      await loadShareLinks({ silent: true });
      toast('Publication terminée.');
    } catch (err) {
      console.error(err);
      $('publishLog').textContent += '\nERREUR:\n' + JSON.stringify(err.data || { error: err.message }, null, 2);
      toast(err.message || 'Publication impossible.', 'bad');
    } finally {
      setLoading(btn, false);
    }
  }

  async function retryConnections() {
    if (!app.tour) return;
    const btn = $('retryConnectionsBtn');
    setLoading(btn, true, 'Connexion...');
    try {
      const data = await api(`tours/${app.tour.id}/retry-connections/`, { method: 'POST', body: JSON.stringify({}) });
      if (data.tour) hydrateTour(data.tour);
      $('publishLog')?.classList.remove('hidden');
      $('publishLog').textContent = JSON.stringify(data.results || data, null, 2);
      toast(data.ok ? 'Connexions Google envoyées.' : 'Connexions envoyées avec avertissements.', data.ok ? 'ok' : 'bad');
    } catch (err) {
      console.error(err);
      toast(err.message || 'Retry connexions impossible.', 'bad');
    } finally {
      setLoading(btn, false);
    }
  }

  async function loadShareLinks({ silent = false } = {}) {
    if (!app.tour) return;
    try {
      const data = await api(`tours/${app.tour.id}/share-links/`);
      app.shareText = data.share_text || '';
      renderShareLinks(data.links || []);
      if (!silent) toast('Liens de partage chargés.');
    } catch (err) {
      console.error(err);
      toast(err.message || 'Impossible de charger les liens.', 'bad');
    }
  }

  function renderShareLinks(links) {
    const box = $('shareLinks');
    const empty = $('shareEmpty');
    if (!box) return;
    empty?.classList.toggle('hidden', links.length > 0);
    box.innerHTML = links.map(item => `
      <div class="sv-share-card">
        <b>${escapeHtml(item.title)}</b>
        <a href="${escapeHtml(item.share_link)}" target="_blank" rel="noopener">${escapeHtml(item.share_link)}</a>
        <div class="sv-share-actions">
          <a class="sv-btn sv-btn-primary" href="${escapeHtml(item.share_link)}" target="_blank" rel="noopener">Ouvrir</a>
          <button class="sv-btn sv-btn-soft copy-link" data-link="${escapeHtml(item.share_link)}">Copier</button>
        </div>
      </div>
    `).join('');
    box.querySelectorAll('.copy-link').forEach(btn => btn.addEventListener('click', async () => {
      await navigator.clipboard.writeText(btn.dataset.link || '');
      toast('Lien copié.');
    }));
  }

  async function copyAllLinks() {
    if (!app.shareText) await loadShareLinks({ silent: true });
    if (!app.shareText) return toast('Aucun lien publié.', 'bad');
    await navigator.clipboard.writeText(app.shareText);
    toast('Tous les liens copiés.');
  }

  async function markPublished() {
    const scene = selectedScene();
    if (!scene) return;
    $('markPhotoId').value = scene.google.photoId || '';
    $('markShareLink').value = sceneShareLink(scene) || '';
    openModal('markModal');
  }

  async function confirmMarkPublished() {
    const scene = selectedScene();
    if (!scene) return;
    const photoId = $('markPhotoId')?.value.trim();
    if (!photoId) return toast('Google Photo ID obligatoire.', 'bad');
    try {
      const data = await api(`scenes/${scene.backendId}/mark-published/`, {
        method: 'POST',
        body: JSON.stringify({ photo_id: photoId, share_link: $('markShareLink')?.value.trim() || '' }),
      });
      closeModal('markModal');
      const updated = normalizeScene(data.scene);
      app.scenes = app.scenes.map(s => s.id === scene.id ? updated : s);
      app.selectedId = updated.id;
      renderAll();
      toast('Scène marquée publiée.');
    } catch (err) {
      console.error(err);
      toast(err.message || 'Impossible de marquer publiée.', 'bad');
    }
  }

  async function checkGoogleStatus() {
    const scene = selectedScene();
    if (!scene || !scene.google.photoId) return toast('Cette scène n’a pas de Google Photo ID.', 'bad');
    try {
      const data = await api(`scenes/${scene.backendId}/google-status/`);
      if (data.scene) {
        const updated = normalizeScene(data.scene);
        app.scenes = app.scenes.map(s => s.id === scene.id ? updated : s);
        app.selectedId = updated.id;
        renderAll();
      }
      toast(data.ok ? 'Statut Google actualisé.' : 'Google n’a pas encore tout indexé.', data.ok ? 'ok' : 'bad');
    } catch (err) {
      console.error(err);
      toast(err.message || 'Vérification Google impossible.', 'bad');
    }
  }

  function openModal(id) { $(id)?.classList.remove('hidden'); }
  function closeModal(id) { $(id)?.classList.add('hidden'); }

  function loadGoogleMapsScript() {
    if (window.google?.maps) return Promise.resolve();
    const key = app.config.googleMapsKey || '';
    if (!key) return Promise.reject(new Error('Clé Google Maps absente dans /config/.'));
    if (window.__svMapLoading) return window.__svMapLoading;
    window.__svMapLoading = new Promise((resolve, reject) => {
      window.initStreetViewPublisherMap = () => resolve();
      const script = document.createElement('script');
      script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&libraries=places&callback=initStreetViewPublisherMap&v=weekly`;
      script.async = true;
      script.defer = true;
      script.onerror = () => reject(new Error('Google Maps n’a pas pu charger.'));
      document.head.appendChild(script);
    });
    return window.__svMapLoading;
  }

  async function openMap() {
    openModal('mapModal');
    try {
      await loadGoogleMapsScript();
      initMap();
    } catch (err) {
      console.error(err);
      toast(err.message, 'bad');
    }
  }

  function initMap() {
    if (!window.google?.maps) return;
    const centerScene = selectedScene();
    const centerGps = hasGps(centerScene) ? { lat: Number(centerScene.gps.lat), lng: Number(centerScene.gps.lng) } : firstGps() || { lat: -4.325, lng: 15.322 };
    if (!app.map) {
      app.map = new google.maps.Map($('map'), { center: centerGps, zoom: 16, streetViewControl: true, fullscreenControl: true, mapTypeId: 'roadmap' });
      app.map.addListener('click', (e) => assignGpsToSelected(e.latLng.lat(), e.latLng.lng()));
      app.mapAutocomplete = new google.maps.places.Autocomplete($('addressSearch'), { fields: ['formatted_address', 'geometry', 'name'] });
      app.mapAutocomplete.addListener('place_changed', () => {
        const place = app.mapAutocomplete.getPlace();
        if (!place.geometry?.location) return toast('Adresse non trouvée.', 'bad');
        assignGpsToSelected(place.geometry.location.lat(), place.geometry.location.lng());
        app.map.panTo(place.geometry.location);
      });
    }
    app.map.setCenter(centerGps);
    setTimeout(() => google.maps.event.trigger(app.map, 'resize'), 120);
    refreshMapMarkers();
  }

  function firstGps() {
    const s = app.scenes.find(hasGps);
    return s ? { lat: Number(s.gps.lat), lng: Number(s.gps.lng) } : null;
  }

  async function assignGpsToSelected(lat, lng) {
    const scene = selectedScene();
    if (!scene) return toast('Sélectionne d’abord une image.', 'bad');
    scene.gps.lat = Number(lat.toFixed(7));
    scene.gps.lng = Number(lng.toFixed(7));
    $('sceneLatInput') && ($('sceneLatInput').value = scene.gps.lat);
    $('sceneLngInput') && ($('sceneLngInput').value = scene.gps.lng);
    await saveSelectedScene({ silent: true });
    refreshMapMarkers();
    toast('GPS assigné.');
  }

  function refreshMapMarkers() {
    if (!app.map || !window.google?.maps) return;
    app.mapMarkers.forEach(marker => marker.setMap(null));
    app.mapMarkers.clear();
    const bounds = new google.maps.LatLngBounds();
    let hasAny = false;
    app.scenes.forEach(scene => {
      if (!hasGps(scene)) return;
      const position = { lat: Number(scene.gps.lat), lng: Number(scene.gps.lng) };
      const marker = new google.maps.Marker({ map: app.map, position, title: scene.title, draggable: true, label: scene.id === app.selectedId ? '★' : '' });
      marker.addListener('click', () => { app.selectedId = scene.id; renderAll(); app.map.panTo(position); });
      marker.addListener('dragend', (e) => { app.selectedId = scene.id; assignGpsToSelected(e.latLng.lat(), e.latLng.lng()); });
      app.mapMarkers.set(scene.id, marker);
      bounds.extend(position);
      hasAny = true;
    });
    if (hasAny && app.mapMarkers.size > 1) app.map.fitBounds(bounds);
  }

  async function openViewer() {
    const scene = selectedScene();
    if (!scene) return toast('Sélectionne une scène.', 'bad');
    openModal('viewerModal');
    $('viewerTitle') && ($('viewerTitle').textContent = scene.title);
    try {
      if (!window.Marzipano) throw new Error('Marzipano n’est pas chargé.');
      if (!app.viewer) app.viewer = new Marzipano.Viewer($('viewer'), { controls: { mouseViewMode: 'drag' } });
      $('viewer').innerHTML = '';
      app.viewer = new Marzipano.Viewer($('viewer'), { controls: { mouseViewMode: 'drag' } });
      const source = Marzipano.ImageUrlSource.fromString(scene.imageUrl);
      const width = Math.min(Math.max(scene.width || 4096, 1024), 8192);
      const geometry = new Marzipano.EquirectGeometry([{ width }]);
      const limiter = Marzipano.RectilinearView.limit.traditional(width, rad(120));
      const view = new Marzipano.RectilinearView({ yaw: rad(scene.camera.heading || 0), pitch: rad(scene.camera.pitch || 0), fov: rad(scene.camera.fov || 90) }, limiter);
      app.marziScene = app.viewer.createScene({ source, geometry, view, pinFirstLevel: true });
      app.currentView = view;
      app.marziScene.switchTo({ transitionDuration: 250 });
      setTimeout(() => app.viewer?.updateSize(), 100);
    } catch (err) {
      console.error(err);
      toast(err.message || 'Viewer impossible.', 'bad');
    }
  }

  async function captureCamera() {
    const scene = selectedScene();
    if (!scene || !app.currentView) return toast('Ouvre d’abord la scène en 360.', 'bad');
    const params = app.currentView.parameters();
    scene.camera.heading = Number(deg(params.yaw).toFixed(2));
    scene.camera.pitch = Number((params.pitch * 180 / Math.PI).toFixed(2));
    scene.camera.fov = Number((params.fov * 180 / Math.PI).toFixed(2));
    $('sceneHeadingInput') && ($('sceneHeadingInput').value = scene.camera.heading);
    $('scenePitchInput') && ($('scenePitchInput').value = scene.camera.pitch);
    await saveSelectedScene({ silent: true });
    toast('Vue principale sauvegardée.');
  }

  async function updateGoogleCamera() {
    const scene = selectedScene();
    if (!scene || !scene.google.photoId) return toast('Cette scène n’est pas encore publiée.', 'bad');
    try {
      await saveSelectedScene({ silent: true });
      const data = await api(`scenes/${scene.backendId}/update-google-camera/`, { method: 'POST', body: JSON.stringify({}) });
      toast(data.message || 'Caméra Google mise à jour.');
    } catch (err) {
      console.error(err);
      toast(err.message || 'Correction caméra impossible.', 'bad');
    }
  }

  function bindEvents() {
    document.querySelectorAll('.sv-step-tab').forEach(btn => btn.addEventListener('click', () => switchStep(btn.dataset.step)));
    document.querySelectorAll('[data-close-modal]').forEach(btn => btn.addEventListener('click', () => closeModal(btn.dataset.closeModal)));
    $('refreshToursBtn')?.addEventListener('click', () => loadTours());
    $('createTourBtn')?.addEventListener('click', createTour);
    $('newTourTitle')?.addEventListener('keydown', (e) => { if (e.key === 'Enter') createTour(); });
    $('browseBtn')?.addEventListener('click', () => $('fileInput')?.click());
    $('fileInput')?.addEventListener('change', (e) => handleFiles(e.target.files));
    $('saveProjectQuickBtn')?.addEventListener('click', saveProject);
    $('directPublishBtn')?.addEventListener('click', directPublishScene);
    $('syncDirectStatusBtn')?.addEventListener('click', syncDirectProjectStatus);
    $('syncProjectGoogleBtn')?.addEventListener('click', syncDirectProjectStatus);
    $('openMapBulkBtn')?.addEventListener('click', openMap);
    $('openMapBtn')?.addEventListener('click', openMap);
    $('saveSceneBtn')?.addEventListener('click', () => saveSelectedScene());
    $('deleteSceneBtn')?.addEventListener('click', deleteSelectedScene);
    $('viewScene360Btn')?.addEventListener('click', openViewer);
    $('viewScene360SideBtn')?.addEventListener('click', openViewer);
    $('markPublishedBtn')?.addEventListener('click', markPublished);
    $('confirmMarkPublishedBtn')?.addEventListener('click', confirmMarkPublished);
    $('checkGoogleBtn')?.addEventListener('click', checkGoogleStatus);
    $('captureCameraBtn')?.addEventListener('click', captureCamera);
    $('updateGoogleCameraBtn')?.addEventListener('click', updateGoogleCamera);
    $('autoConnectBtn')?.addEventListener('click', autoConnect);
    $('addManualLinkBtn')?.addEventListener('click', addManualLink);
    $('publishBtn')?.addEventListener('click', publishTour);
    $('retryConnectionsBtn')?.addEventListener('click', retryConnections);
    $('loadShareLinksBtn')?.addEventListener('click', () => loadShareLinks());
    $('copyAllLinksBtn')?.addEventListener('click', copyAllLinks);
    $('assignMapCenterBtn')?.addEventListener('click', () => {
      if (!app.map) return;
      const center = app.map.getCenter();
      assignGpsToSelected(center.lat(), center.lng());
    });

    const dz = $('dropZone');
    dz?.addEventListener('click', (e) => { if (e.target.id !== 'browseBtn') $('fileInput')?.click(); });
    dz?.addEventListener('dragover', (e) => { e.preventDefault(); dz.classList.add('over'); });
    dz?.addEventListener('dragleave', () => dz.classList.remove('over'));
    dz?.addEventListener('drop', (e) => { e.preventDefault(); dz.classList.remove('over'); handleFiles(e.dataTransfer.files); });

    window.addEventListener('resize', () => app.viewer?.updateSize());
  }

  async function init() {
    bindEvents();
    await loadConfig();
    await loadTours({ silent: true });
    renderAll();
  }

  init();
})();
