'use strict';

const REFRESH_MS = 5 * 60 * 1000;
let allListings = [];
let refreshTimer = null;
let lastSeenIds = new Set();
let isFirstLoad = true;
let currentView = 'grid'; // 'grid' | 'map'

// ── Map state ─────────────────────────────────────────────────────────
let map = null;
let markers = [];
// Mariatorget centre
const MAP_CENTER = [59.3178, 18.0604];
const MAP_ZOOM   = 15;

// ── Fetch & Render ────────────────────────────────────────────────────

async function loadListings(showLoading = false) {
  if (showLoading) {
    document.getElementById('loading').classList.remove('hidden');
    document.getElementById('listings-grid').innerHTML = '';
    document.getElementById('listings-meta').classList.add('hidden');
  }

  const params = buildFilterParams();
  try {
    const res = await fetch('/api/listings?' + new URLSearchParams(params));
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    allListings = await res.json();
  } catch (e) {
    console.error('loadListings failed:', e);
    document.getElementById('loading').classList.add('hidden');
    return;
  }

  renderListings(allListings);
  updateStatus();
  scheduleNextRefresh();
}

// ── Map ───────────────────────────────────────────────────────────────

function initMap() {
  if (map) return;
  map = L.map('map', { zoomControl: true }).setView(MAP_CENTER, MAP_ZOOM);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a>',
    maxZoom: 19,
  }).addTo(map);
}

function renderMap(listings) {
  initMap();
  // Remove old markers
  markers.forEach(m => m.remove());
  markers = [];

  const valid = listings.filter(l => l.lat && l.lng && l.lat !== 0 && l.lng !== 0);

  for (const l of valid) {
    const color = l.status === 'upcoming' ? '#f59e0b' : (l.is_new ? '#22c55e' : '#3b82f6');
    const icon = L.divIcon({
      className: '',
      html: `<div class="map-pin ${l.status === 'upcoming' ? 'pin-upcoming' : ''} ${l.is_new ? 'pin-new' : ''}" style="background:${color}"></div>`,
      iconSize: [14, 14],
      iconAnchor: [7, 7],
    });

    const proxyImg = l.image_url
      ? `/api/proxy?url=${encodeURIComponent(l.image_url)}`
      : '';

    const priceStr = l.price ? formatPrice(l.price) + ' kr' : 'Pris ej angivet';
    const roomsStr = l.rooms != null ? formatRooms(l.rooms) + ' rok · ' : '';
    const sizeStr  = l.size  != null ? l.size + ' kvm' : '';

    const popup = L.popup({ maxWidth: 260, className: 'map-popup' }).setContent(`
      <div class="map-popup-inner">
        ${proxyImg ? `<a href="${l.url}" target="_blank" rel="noopener"><img src="${proxyImg}" alt="" loading="lazy" onerror="this.style.display='none'"></a>` : ''}
        <div class="map-popup-body">
          <div class="map-popup-badges">
            ${l.is_new ? '<span class="badge badge-new">NY</span>' : ''}
            ${l.status === 'upcoming' ? '<span class="badge badge-upcoming">KOMMANDE</span>' : ''}
          </div>
          <a class="map-popup-addr" href="${l.url}" target="_blank" rel="noopener">${l.address || l.title || ''}</a>
          <div class="map-popup-area">${l.area || ''}</div>
          <div class="map-popup-price">${priceStr}</div>
          <div class="map-popup-details">${roomsStr}${sizeStr}</div>
          <div class="map-popup-broker">${l.broker || ''}</div>
        </div>
      </div>
    `);

    const marker = L.marker([l.lat, l.lng], { icon }).bindPopup(popup).addTo(map);
    markers.push(marker);
  }

  // Fit map to markers if we have any
  if (valid.length > 0) {
    const group = L.featureGroup(markers);
    map.fitBounds(group.getBounds().pad(0.15), { maxZoom: 16 });
  }

  // Show count of unmapped listings
  const unmapped = listings.length - valid.length;
  document.getElementById('map-no-coords').textContent =
    unmapped > 0 ? `${unmapped} objekt saknar koordinater (geocodas efter nästa skrapning)` : '';
}

function switchView(view) {
  currentView = view;
  const grid = document.getElementById('listings-grid');
  const mapContainer = document.getElementById('map-container');
  const btnGrid = document.getElementById('btn-view-grid');
  const btnMap  = document.getElementById('btn-view-map');

  if (view === 'map') {
    grid.classList.add('hidden');
    mapContainer.classList.remove('hidden');
    btnGrid.classList.remove('active');
    btnMap.classList.add('active');
    renderMap(allListings);
    // Leaflet needs a size recalculation after becoming visible
    if (map) setTimeout(() => map.invalidateSize(), 10);
  } else {
    mapContainer.classList.add('hidden');
    grid.classList.remove('hidden');
    btnGrid.classList.add('active');
    btnMap.classList.remove('active');
  }
}

function renderListings(listings) {
  document.getElementById('loading').classList.add('hidden');
  document.getElementById('empty-state').classList.add('hidden');

  const grid = document.getElementById('listings-grid');
  const meta = document.getElementById('listings-meta');
  const newAlert = document.getElementById('new-alert');

  if (listings.length === 0) {
    grid.innerHTML = '';
    document.getElementById('empty-state').classList.remove('hidden');
    meta.classList.add('hidden');
    return;
  }

  meta.classList.remove('hidden');
  document.getElementById('result-count').textContent =
    `${listings.length} objekt`;

  // Detect new listings on subsequent loads
  const currentIds = new Set(listings.map(l => l.id));
  const brandNew = isFirstLoad ? [] :
    listings.filter(l => !lastSeenIds.has(l.id));

  if (brandNew.length > 0) {
    newAlert.classList.remove('hidden');
    document.getElementById('new-count-text').textContent =
      `${brandNew.length} ny${brandNew.length > 1 ? 'a' : 't'} sedan senast`;
  } else {
    newAlert.classList.add('hidden');
  }

  lastSeenIds = currentIds;
  isFirstLoad = false;

  const tpl = document.getElementById('card-template');
  const fragment = document.createDocumentFragment();

  for (const listing of listings) {
    const card = tpl.content.cloneNode(true).querySelector('.listing-card');
    populateCard(card, listing);
    fragment.appendChild(card);
  }

  grid.innerHTML = '';
  grid.appendChild(fragment);

  // Update map if visible
  if (currentView === 'map') renderMap(listings);
}

function populateCard(card, l) {
  card.dataset.id = l.id;
  if (l.is_new) card.classList.add('is-new');
  if (l.status === 'upcoming') card.classList.add('is-upcoming');

  // Badges
  const badgeNew = card.querySelector('.badge-new');
  const badgeUpcoming = card.querySelector('.badge-upcoming');
  if (l.is_new) badgeNew.classList.remove('hidden');
  if (l.status === 'upcoming') badgeUpcoming.classList.remove('hidden');

  // Image
  const imgLink = card.querySelector('.card-image-link');
  const img = card.querySelector('.card-image');
  const fallback = card.querySelector('.card-image-fallback');
  imgLink.href = l.url || '#';

  if (l.image_url) {
    img.src = '/api/proxy?url=' + encodeURIComponent(l.image_url);
    img.alt = l.address || l.title || '';
    img.onerror = () => {
      img.style.display = 'none';
      fallback.style.display = 'flex';
    };
  } else {
    img.style.display = 'none';
    fallback.style.display = 'flex';
  }

  // Text
  card.querySelector('.card-broker').textContent = l.broker || '';
  const addrEl = card.querySelector('.card-address');
  addrEl.textContent = l.address || l.title || 'Adress saknas';
  addrEl.href = l.url || '#';

  card.querySelector('.card-area').textContent = l.area || '';

  card.querySelector('.card-price').textContent =
    l.price ? formatPrice(l.price) + ' kr' : 'Pris ej angivet';
  card.querySelector('.card-rooms').textContent =
    l.rooms != null ? formatRooms(l.rooms) + ' rok' : '';
  card.querySelector('.card-size').textContent =
    l.size != null ? l.size + ' kvm' : '';

  const feeEl = card.querySelector('.card-fee');
  feeEl.textContent = l.monthly_fee ? 'Avgift: ' + formatPrice(l.monthly_fee) + ' kr/mån' : '';

  const floorEl = card.querySelector('.card-floor');
  floorEl.textContent = l.floor ? 'Våning: ' + l.floor : '';

  const sinceEl = card.querySelector('.card-since');
  sinceEl.textContent = l.first_seen ? 'Sedd: ' + formatDate(l.first_seen) : '';
}

// ── Filters ───────────────────────────────────────────────────────────

function buildFilterParams() {
  const params = {};
  const minPrice = document.getElementById('f-price-min').value;
  const maxPrice = document.getElementById('f-price-max').value;
  const minSize  = document.getElementById('f-size-min').value;
  const maxSize  = document.getElementById('f-size-max').value;
  const rooms    = document.getElementById('f-rooms').value;
  const status   = document.getElementById('f-status').value;
  const broker   = document.getElementById('f-broker').value;
  const sort     = document.getElementById('f-sort').value;

  if (minPrice) params.min_price = minPrice;
  if (maxPrice) params.max_price = maxPrice;
  if (minSize)  params.min_size  = minSize;
  if (maxSize)  params.max_size  = maxSize;
  if (rooms)    params.min_rooms = rooms;
  if (status)   params.status    = status;
  if (broker)   params.broker    = broker;
  if (sort)     params.sort      = sort;

  return params;
}

function resetFilters() {
  ['f-price-min','f-price-max','f-size-min','f-size-max'].forEach(id => {
    document.getElementById(id).value = '';
  });
  ['f-rooms','f-status','f-broker','f-sort'].forEach(id => {
    document.getElementById(id).selectedIndex = 0;
  });
  loadListings(true);
}

// ── Status bar ────────────────────────────────────────────────────────

async function updateStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    const badge = document.getElementById('status-count');
    badge.textContent = `${data.total} objekt`;

    if (data.last_scrape && data.last_scrape.finished_at) {
      const d = new Date(data.last_scrape.finished_at + 'Z');
      document.getElementById('last-updated').textContent =
        'Uppdaterad ' + d.toLocaleTimeString('sv-SE', { hour: '2-digit', minute: '2-digit' });
    }
  } catch (e) {
    // ignore
  }
}

// ── Scrape trigger ────────────────────────────────────────────────────

async function triggerScrape() {
  const btn = document.getElementById('btn-scrape');
  btn.disabled = true;
  btn.textContent = 'Hämtar…';

  try {
    await fetch('/api/scrape', { method: 'POST' });
    // Wait a bit for the scraper to run, then reload
    setTimeout(() => loadListings(false), 8000);
  } catch (e) {
    console.error(e);
  } finally {
    setTimeout(() => {
      btn.disabled = false;
      btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M23 4v6h-6M1 20v-6h6"/>
        <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>
      </svg> Uppdatera`;
    }, 10000);
  }
}

// ── Auto-refresh ──────────────────────────────────────────────────────

function scheduleNextRefresh() {
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(() => loadListings(false), REFRESH_MS);
}

// ── Helpers ───────────────────────────────────────────────────────────

function formatPrice(n) {
  return n.toLocaleString('sv-SE');
}
function formatRooms(n) {
  return n % 1 === 0 ? n.toString() : n.toFixed(1).replace('.', ',');
}
function formatDate(iso) {
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z');
  const now = new Date();
  const diff = now - d;
  if (diff < 3600000) return 'just nu';
  if (diff < 86400000) {
    const h = Math.floor(diff / 3600000);
    return `${h} tim sedan`;
  }
  const days = Math.floor(diff / 86400000);
  if (days === 1) return 'igår';
  if (days < 7) return `${days} dagar sedan`;
  return d.toLocaleDateString('sv-SE');
}

// ── Init ──────────────────────────────────────────────────────────────

document.getElementById('btn-filter').addEventListener('click', () => loadListings(true));
document.getElementById('btn-reset').addEventListener('click', resetFilters);
document.getElementById('btn-scrape').addEventListener('click', triggerScrape);
document.getElementById('btn-view-grid').addEventListener('click', () => switchView('grid'));
document.getElementById('btn-view-map').addEventListener('click',  () => switchView('map'));

// Also trigger on Enter in filter inputs
document.querySelectorAll('.filter-group input, .filter-group select').forEach(el => {
  el.addEventListener('keydown', e => { if (e.key === 'Enter') loadListings(true); });
});

loadListings(true);
