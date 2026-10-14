/* Blackline QSi Pro service worker: keeps the app itself (pages, scripts, styles, fonts, icons) so it opens with no connection.
   It NEVER stores or serves anything from the API: tender data, estimates and documents always come live from the server. */
const VERSION = "qsi-shell-v1";
const SHELL = ["/", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.pathname.startsWith("/api/") || (url.origin !== location.origin && !/fonts\.(googleapis|gstatic)\.com$/.test(url.hostname))) return;   // API and other sites: untouched
  if (req.mode === "navigate") {                         // the page itself: newest if online, else the saved copy
    e.respondWith(fetch(req).then((r) => { const c = r.clone(); caches.open(VERSION).then((x) => x.put("/", c)); return r; }).catch(() => caches.match("/")));
    return;
  }
  e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((r) => {   // built files (hashed names) and fonts: saved on first use
    if (r.ok || r.type === "opaque") { const c = r.clone(); caches.open(VERSION).then((x) => x.put(req, c)); }
    return r;
  })));
});
