// Service worker for Partisan Lillestrøm PWA
// Gjør appen installerbar og cacher kjernefiler for raskere lasting.
// CACHE_VERSION oppdateres av GitHub Actions (update_data.py) ved endringer.

const CACHE_VERSION = '2026-10-21';
const CACHE_NAME = 'partisan-' + CACHE_VERSION;
const CORE_ASSETS = [
  './',
  './index.html',
  './logo-icon.png',
  './logo-main.png',
  './header-logo.png',
  './manifest.json'
];

// Installer: cache kjernefiler, ta over umiddelbart
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(CORE_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// Aktiver: rydd opp ALLE gamle cacher, ta kontroll over klienter
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Fetch: nettverket først, fall tilbake til cache
self.addEventListener('fetch', e => {
  e.respondWith(
    fetch(e.request)
      .then(res => {
        if (e.request.method === 'GET' && res.status === 200) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(e.request, clone));
        }
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});
