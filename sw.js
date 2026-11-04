// CA Money Mantra app shell. Same-origin GET only; never touches third-party data requests.
// Pages: network first (so a new deploy shows up), cached copy when offline or slow.
const CACHE = 'cmm-v1';
const SHELL = ['./', 'index.html', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png', 'icons/maskable-512.png', 'icons/apple-touch-icon.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (req.mode === 'navigate') {
    // Network first with a 4 s fallback to the cached page; the network copy still refreshes the cache.
    const net = fetch(req).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put('index.html', copy)); }
      return res;
    });
    e.respondWith(new Promise(resolve => {
      let done = false;
      const fallback = () => caches.match('index.html').then(r => { if (r && !done) { done = true; resolve(r); } });
      const timer = setTimeout(fallback, 4000);
      net.then(res => { clearTimeout(timer); if (!done) { done = true; resolve(res); } })
         .catch(() => { clearTimeout(timer); fallback().then(() => { if (!done) { done = true; resolve(Response.error()); } }); });
    }));
    return;
  }

  // Icons, manifest and other static files: cache first, then network.
  e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
    if (res.ok && SHELL.some(p => url.pathname.endsWith(p.replace('./', '/')))) {
      const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy));
    }
    return res;
  })));
});
