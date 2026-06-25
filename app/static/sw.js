// Minimal service worker — exists only to make the app installable (PWA).
// Network-only passthrough: we never cache portfolio data, so family always
// sees fresh numbers. (A fetch handler is required for Chrome's install prompt.)
self.addEventListener("install", (e) => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (e) => {
  // Pass through to the network; if offline, the browser shows its default page.
  e.respondWith(fetch(e.request));
});
