const $ = (id) => document.getElementById(id);
const API = '/apis/streetview/';
const state = { orgs: [], places: [], tours: [], project: null, selectedOrg: null, selectedPlace: null, selectedTour: null, selectedScene: null, viewer: null, marziScene: null, view: null, shareText: '' };

function csrfToken(){const m=document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);return m?decodeURIComponent(m[1]):'';}
async function requestJSON(url, opts={}){const res=await fetch(url,{credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrfToken(),...(opts.headers||{})},...opts});const data=await res.json().catch(()=>({}));if(!res.ok)throw Object.assign(new Error(data.error||`Erreur HTTP ${res.status}`),{data,status:res.status});return data;}
function toast(msg){const el=document.createElement('div');el.className='toast';el.textContent=msg;$('toastBox').appendChild(el);setTimeout(()=>el.remove(),3500);}
function esc(v=''){return String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
function fmtGps(g){return g?.latitude&&g?.longitude?`${Number(g.latitude).toFixed(6)}, ${Number(g.longitude).toFixed(6)}`:'GPS manquant';}
function pill(label,type=''){return `<span class="pill ${type}">${label}</span>`;}

async function init(){await loadGoogleStatus();await loadOrganizations();bindActions();}
async function loadGoogleStatus(){try{const data=await requestJSON(API+'google/status/');$('googleStatus').textContent=data.connected?`Google connecté${data.googleEmail?' · '+data.googleEmail:''}`:'Google non connecté';if(!data.connected){$('googleStatus').innerHTML=`Google non connecté · <a href="${data.oauthStartUrl}">Connecter</a>`;}}catch(e){$('googleStatus').textContent='Google: erreur';}}
async function loadOrganizations(){const data=await requestJSON(API+'source/organizations/');state.orgs=data.results||[];renderOrganizations();}
function renderOrganizations(){const box=$('organizationsList');box.innerHTML=state.orgs.map(o=>`<button class="item ${state.selectedOrg===o.id?'active':''}" data-org="${o.id}"><b>${esc(o.name)}</b><span>${esc(o.slug)} · ${esc(o.status)}</span></button>`).join('')||'<div class="muted-box">Aucune organisation.</div>';box.querySelectorAll('[data-org]').forEach(b=>b.onclick=()=>selectOrg(Number(b.dataset.org)));}
async function selectOrg(id){state.selectedOrg=id;state.selectedPlace=null;state.selectedTour=null;state.project=null;state.selectedScene=null;renderOrganizations();$('placesList').innerHTML='Chargement...';$('toursList').innerHTML='<div class="muted-box">Choisis un place.</div>';hideWorkspace();const data=await requestJSON(`${API}source/organizations/${id}/places/`);state.places=data.results||[];renderPlaces();}
function renderPlaces(){const box=$('placesList');box.innerHTML=state.places.map(p=>`<button class="item ${state.selectedPlace===p.id?'active':''}" data-place="${p.id}"><b>${esc(p.name)}</b><span>${esc(p.city||'Ville ?')} · ${esc(p.category)} · ${p.latitude&&p.longitude?'GPS OK':'GPS manquant'}</span></button>`).join('')||'<div class="muted-box">Aucun place dans cette organisation.</div>';box.querySelectorAll('[data-place]').forEach(b=>b.onclick=()=>selectPlace(Number(b.dataset.place)));}
async function selectPlace(id){state.selectedPlace=id;state.selectedTour=null;state.project=null;state.selectedScene=null;renderPlaces();$('toursList').innerHTML='Chargement...';hideWorkspace();const data=await requestJSON(`${API}source/places/${id}/tours/`);state.tours=data.results||[];renderTours();}
function renderTours(){const box=$('toursList');box.innerHTML=state.tours.map(t=>{const sv=t.streetview;return `<button class="item ${state.selectedTour===t.id?'active':''}" data-tour="${t.id}"><b>${esc(t.title)}</b><span>${t.scenes_count||0} scène(s) · ${sv?`${sv.published_scenes_count}/${sv.scenes_count} publiées`:'pas encore préparé'}</span></button>`}).join('')||'<div class="muted-box">Aucun tour pour ce place.</div>';box.querySelectorAll('[data-tour]').forEach(b=>b.onclick=()=>selectTour(Number(b.dataset.tour)));}
async function selectTour(id){state.selectedTour=id;state.selectedScene=null;$('workspace').classList.remove('hidden');$('emptyState').classList.add('hidden');$('publishLogs').textContent='Chargement du tour...';const data=await requestJSON(`${API}source/tours/${id}/`);state.project=data;state.selectedScene=data.scenes?.[0]?.id||null;renderWorkspace();toast('Tour chargé sans dupliquer les images.');}
function hideWorkspace(){$('workspace').classList.add('hidden');$('emptyState').classList.remove('hidden');}
function renderWorkspace(){const p=state.project;if(!p)return;const t=p.tour, place=p.place, org=p.organization;$('breadcrumb').textContent=`${org.name} / ${place.name}`;$('tourTitle').textContent=t.title;$('tourMeta').textContent=`${place.address_line||t.location||''} ${place.city||''} ${place.country||''}`.trim()||'Adresse non définie';$('sceneCounter').textContent=`${p.scenes.length} scène(s)`;renderSceneList();renderSceneDetail();renderManualConnections();renderShareLinks();}
function renderSceneList(){const scenes=state.project?.scenes||[];$('sceneList').innerHTML=scenes.map(s=>{const active=s.id===state.selectedScene;const gpsOk=s.gps.latitude&&s.gps.longitude;const google=s.google||{};return `<article class="scene-card ${active?'active':''}" data-scene="${s.id}"><img src="${s.preview_url||s.image_url||''}" alt=""><div><h4>${esc(s.title)}</h4><p>${fmtGps(s.gps)} · source ${esc(s.gps.source||'')}</p><p>${s.has_image?'image OK':'image manquante'} · ${esc(s.status)}</p></div><div class="status-col">${pill(gpsOk?'GPS':'GPS ? ',gpsOk?'good':'bad')} ${pill(google.is_published?'Google':'Local',google.is_published?'good':'warn')} ${pill(google.is_connected?'Lié':'Non lié',google.is_connected?'good':'warn')}</div></article>`}).join('')||'<div class="muted-box">Aucune scène 360 dans ce tour.</div>';$('sceneList').querySelectorAll('[data-scene]').forEach(el=>el.onclick=()=>{state.selectedScene=Number(el.dataset.scene);renderSceneList();renderSceneDetail();});}
function currentScene(){return (state.project?.scenes||[]).find(s=>s.id===state.selectedScene);}
function renderSceneDetail(){const s=currentScene();$('sceneDetailEmpty').classList.toggle('hidden',!!s);$('sceneDetail').classList.toggle('hidden',!s);if(!s){$('sceneTitle').textContent='Aucune scène sélectionnée';return;}$('sceneTitle').textContent=s.title;$('scenePreview').src=s.preview_url||s.image_url||'';$('sceneLat').value=s.gps.latitude??'';$('sceneLng').value=s.gps.longitude??'';$('sceneHeading').value=s.camera.heading??0;$('scenePitch').value=s.camera.pitch??0;$('sceneRoll').value=s.camera.roll??0;$('sceneFov').value=s.camera.initial_fov??90;const delBtn=$('deleteGooglePhotoBtn');if(delBtn){delBtn.disabled=!s.google?.is_published;delBtn.textContent=s.google?.is_published?'Effacer de Google':'Pas encore sur Google';}}

function renderManualConnections(){
  const scenes=state.project?.scenes||[];
  const links=state.project?.navigation_links||[];
  const from=$('manualFromScene'), to=$('manualToScene'), list=$('manualConnectionsList');
  if(!from||!to||!list)return;
  const options=scenes.map(s=>`<option value="${s.id}">${esc(s.title)}</option>`).join('');
  from.innerHTML=options; to.innerHTML=options;
  if(state.selectedScene)from.value=String(state.selectedScene);
  const selected=scenes.find(s=>s.id!==Number(from.value));
  if(selected)to.value=String(selected.id);
  if(!links.length){list.classList.add('muted-box');list.innerHTML='Aucune liaison manuelle pour ce tour.';return;}
  list.classList.remove('muted-box');
  const titleById=Object.fromEntries(scenes.map(s=>[s.id,s.title]));
  list.innerHTML=links.map(l=>`<div class="connection-row"><span>${esc(titleById[l.scene]||l.scene)} → ${esc(titleById[l.target_scene]||l.target_scene)}<small>${esc(l.label||'')}</small></span><button class="mini-danger" data-del-conn="${l.id}">×</button></div>`).join('');
  list.querySelectorAll('[data-del-conn]').forEach(btn=>btn.onclick=()=>deleteManualConnection(Number(btn.dataset.delConn)));
}
async function addManualConnection(){
  if(!state.selectedTour)return;
  const from=Number($('manualFromScene').value), to=Number($('manualToScene').value);
  if(!from||!to)return toast('Choisis les deux scènes.');
  if(from===to)return toast('Choisis deux scènes différentes.');
  const payload={from_scene_id:from,to_scene_id:to,label:$('manualConnectionLabel').value||''};
  const data=await requestJSON(`${API}source/tours/${state.selectedTour}/connections/add/`,{method:'POST',body:JSON.stringify(payload)});
  state.project=data;renderWorkspace();toast('Liaison manuelle créée. Clique Réessayer connexions Google.');
}
async function deleteManualConnection(id){
  if(!state.selectedTour||!id)return;
  const data=await requestJSON(`${API}source/tours/${state.selectedTour}/connections/${id}/delete/`,{method:'POST',body:JSON.stringify({})});
  state.project=data;renderWorkspace();toast('Liaison supprimée.');
}
async function retryGoogleConnections(){
  if(!state.selectedTour)return;
  $('publishLogs').textContent='Mise à jour des connexions Google...\n';
  try{
    const data=await requestJSON(`${API}source/tours/${state.selectedTour}/retry-connections/`,{method:'POST',body:JSON.stringify({})});
    state.project={publication:data.publication,tour:data.tour,organization:data.organization,place:data.place,scenes:data.scenes,navigation_links:data.navigation_links};
    $('publishLogs').textContent=JSON.stringify(data,null,2);
    renderWorkspace();toast(data.ok?'Connexions Google mises à jour.':'Connexions envoyées avec avertissements.');
  }catch(e){$('publishLogs').textContent=JSON.stringify(e.data||{error:e.message},null,2);toast(e.message);}
}

function renderShareLinks(){const scenes=state.project?.scenes||[];const links=scenes.filter(s=>s.google?.photo_id).map(s=>({title:s.title,link:s.google.share_link||''}));state.shareText=links.map(x=>`${x.title}: ${x.link}`).join('\n');const box=$('shareLinks');box.classList.toggle('muted-box',!links.length);box.innerHTML=links.length?links.map(x=>`<div class="share-link"><span>${esc(x.title)}</span><a href="${x.link}" target="_blank" rel="noopener">ouvrir</a></div>`).join(''):'Aucun lien publié pour le moment.';}
async function refreshProject(){if(!state.selectedTour)return;const data=await requestJSON(`${API}source/tours/${state.selectedTour}/`);state.project=data;renderWorkspace();}
function bindActions(){ $('applyPlaceGpsBtn').onclick=async()=>{if(!state.selectedTour)return;const data=await requestJSON(`${API}source/tours/${state.selectedTour}/apply-place-gps/`,{method:'POST',body:JSON.stringify({apply_to:'missing'})});state.project=data;renderWorkspace();toast('GPS appliqué aux scènes sans GPS.');}; $('autoLinkBtn').onclick=async()=>{if(!state.selectedTour)return;const data=await requestJSON(`${API}source/tours/${state.selectedTour}/auto-link/`,{method:'POST',body:JSON.stringify({bidirectional:true})});state.project=data;renderWorkspace();toast('Navigation aller/retour créée avec tes hotspots existants.');}; $('addManualConnectionBtn').onclick=addManualConnection; $('retryConnectionsBtn').onclick=retryGoogleConnections; $('saveSceneBtn').onclick=saveScene; if($('deleteGooglePhotoBtn'))$('deleteGooglePhotoBtn').onclick=deleteGooglePhoto; $('publishBtn').onclick=publishTour; $('openViewerBtn').onclick=openViewer; $('closeViewerBtn').onclick=closeViewer; $('captureCameraBtn').onclick=captureCamera; $('copyAllLinksBtn').onclick=async()=>{if(!state.shareText)return toast('Aucun lien à copier.');await navigator.clipboard.writeText(state.shareText);toast('Liens copiés.');};}
async function saveScene(){const s=currentScene();if(!s)return;const payload={gps:{latitude:$('sceneLat').value,longitude:$('sceneLng').value},camera:{heading:$('sceneHeading').value,pitch:$('scenePitch').value,roll:$('sceneRoll').value,initial_fov:$('sceneFov').value}};const data=await requestJSON(`${API}source/scenes/${s.id}/state/`,{method:'POST',body:JSON.stringify(payload)});const idx=state.project.scenes.findIndex(x=>x.id===s.id);if(idx>=0)state.project.scenes[idx]=data.scene;renderWorkspace();toast('Caméra/GPS sauvegardés.');}

async function deleteGooglePhoto(){
  const s=currentScene();
  if(!s)return;
  if(!s.google?.is_published)return toast('Cette image n’est pas encore publiée sur Google.');
  const ok=confirm(`Effacer cette image de Google Street View ?\n\n${s.title}\n\nL’image originale restera dans ton app. Seule la publication Google sera supprimée.`);
  if(!ok)return;
  $('publishLogs').textContent=`Suppression Google Street View: ${s.title}\n`;
  try{
    const data=await requestJSON(`${API}source/scenes/${s.id}/delete-google-photo/`,{method:'POST',body:JSON.stringify({delete_from_google:true,clear_local_if_missing:true})});
    state.project={publication:data.publication,tour:data.tour,organization:data.organization,place:data.place,scenes:data.scenes,navigation_links:data.navigation_links};
    $('publishLogs').textContent=JSON.stringify(data,null,2);
    renderWorkspace();
    toast(data.ok?'Image supprimée de Google Street View.':'Image supprimée, mais avec avertissements.');
  }catch(e){
    $('publishLogs').textContent=JSON.stringify(e.data||{error:e.message},null,2);
    toast(e.message);
  }
}

async function publishTour(){if(!state.selectedTour)return;$('publishLogs').textContent='Publication en cours...\n';try{const data=await requestJSON(`${API}source/tours/${state.selectedTour}/publish/`,{method:'POST',body:JSON.stringify({skip_published:true,auto_link:false})});state.project={publication:data.publication,tour:data.tour,organization:data.organization,place:data.place,scenes:data.scenes,navigation_links:data.navigation_links};$('publishLogs').textContent=JSON.stringify(data.job||data,null,2);renderWorkspace();toast('Publication terminée.');}catch(e){$('publishLogs').textContent=JSON.stringify(e.data||{error:e.message},null,2);toast(e.message);}}
async function openViewer(){const s=currentScene();if(!s||!s.image_url)return toast('Image indisponible.');$('viewerModal').classList.remove('hidden');$('viewerTitle').textContent=s.title;await new Promise(r=>setTimeout(r,50));if(!state.viewer)state.viewer=new Marzipano.Viewer($('viewer'),{controls:{mouseViewMode:'drag'}});state.viewer.updateSize();const source=Marzipano.ImageUrlSource.fromString(s.image_url);const width=4096;const geometry=new Marzipano.EquirectGeometry([{width}]);const limiter=Marzipano.RectilinearView.limit.traditional(width,120*Math.PI/180);const view=new Marzipano.RectilinearView({yaw:(Number(s.camera.heading)||0)*Math.PI/180,pitch:(Number(s.camera.pitch)||0)*Math.PI/180,fov:(Number(s.camera.initial_fov)||90)*Math.PI/180},limiter);state.view=view;state.marziScene=state.viewer.createScene({source,geometry,view,pinFirstLevel:true});state.marziScene.switchTo({transitionDuration:250});setTimeout(()=>state.viewer.updateSize(),100);}
function closeViewer(){$('viewerModal').classList.add('hidden');}
function captureCamera(){const s=currentScene();if(!s||!state.view)return;const p=state.view.parameters();$('sceneHeading').value=(((p.yaw*180/Math.PI)+360)%360).toFixed(2);$('scenePitch').value=(p.pitch*180/Math.PI).toFixed(2);$('sceneFov').value=(p.fov*180/Math.PI).toFixed(2);closeViewer();toast('Vue principale capturée. Clique sauvegarder.');}

init().catch(e=>{console.error(e);toast(e.message||'Erreur initialisation');});
