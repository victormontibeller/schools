const CACHE_NAME = "schools-shell-v3";
const SHELL = [
    "/offline/",
    "/static/css/bootstrap.min.css",
    "/static/icons/school-manager.svg"
];

self.addEventListener("install", function (event) {
    event.waitUntil(caches.open(CACHE_NAME).then(function (cache) { return cache.addAll(SHELL); }));
    self.skipWaiting();
});

self.addEventListener("activate", function (event) {
    event.waitUntil(caches.keys().then(function (keys) {
        return Promise.all(keys.filter(function (key) { return key !== CACHE_NAME; }).map(function (key) {
            return caches.delete(key);
        }));
    }));
    self.clients.claim();
});

self.addEventListener("fetch", function (event) {
    if (event.request.method !== "GET") { return; }
    const url = new URL(event.request.url);
    if (url.origin !== self.location.origin) { return; }
    if (url.pathname.startsWith("/static/")) {
        if (/\/css\/school-manager(?:\.[0-9a-f]{12})?\.css$/.test(url.pathname)) {
            event.respondWith(fetch(event.request, {cache: "no-store"}).then(function (response) {
                return caches.open(CACHE_NAME).then(function (cache) {
                    cache.put(event.request, response.clone());
                    return response;
                });
            }).catch(function () { return caches.match(event.request); }));
            return;
        }
        event.respondWith(caches.match(event.request).then(function (cached) {
            return cached || fetch(event.request);
        }));
        return;
    }
    if (event.request.mode === "navigate") {
        event.respondWith(fetch(event.request).catch(function () { return caches.match("/offline/"); }));
    }
});
