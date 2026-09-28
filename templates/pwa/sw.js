/* Service worker del sistema (ver core/pwa.py).
 *
 * Única función: si no hay internet al abrir o navegar a una pantalla,
 * mostrar una página amable de "sin conexión" en vez del error del
 * navegador. NO guarda en caché ninguna pantalla del sistema — todas se
 * piden siempre en vivo al servidor — así nunca se ven datos viejos.
 */
const VERSION = '{{ version|escapejs }}';
const CACHE = 'sistema-produccion-' + VERSION;
const OFFLINE_URL = '{{ offline_url|escapejs }}';
const PRECACHE = [{% for url in precache %}'{{ url|escapejs }}'{% if not forloop.last %}, {% endif %}{% endfor %}];

self.addEventListener('install', function (event) {
    event.waitUntil(
        caches.open(CACHE)
            .then(function (cache) { return cache.addAll(PRECACHE); })
            .then(function () { return self.skipWaiting(); })
    );
});

self.addEventListener('activate', function (event) {
    // Borra las cachés de versiones anteriores (de deploys viejos).
    event.waitUntil(
        caches.keys()
            .then(function (claves) {
                return Promise.all(claves
                    .filter(function (c) { return c.startsWith('sistema-produccion-') && c !== CACHE; })
                    .map(function (c) { return caches.delete(c); }));
            })
            .then(function () { return self.clients.claim(); })
    );
});

self.addEventListener('fetch', function (event) {
    const req = event.request;
    // Solo abrir pantallas (GET). Formularios (POST), descargas de
    // reportes, imágenes, el polling de la campanita, etc. pasan directo
    // al servidor sin que este archivo los toque.
    if (req.mode !== 'navigate' || req.method !== 'GET') return;

    event.respondWith(
        fetch(req).catch(function () {
            return caches.match(OFFLINE_URL).then(function (r) {
                return r || new Response('Sin conexión a internet.', {
                    status: 503, headers: { 'Content-Type': 'text/plain; charset=utf-8' },
                });
            });
        })
    );
});
