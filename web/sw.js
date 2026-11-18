// Goalscraper: always try the network first so you get this morning's data;
// if you're offline, show the last copy that loaded.
const CACHE = "goalscraper-v3";
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(
  caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim())));
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const key = url.origin === location.origin ? url.origin + url.pathname : req.url;  // ignore ?v= cache-busters
  e.respondWith(
    fetch(req).then(res => {
      if (res.ok || res.type === "opaque") {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put(key, copy));
      }
      return res;
    }).catch(() => caches.match(key))
  );
});
