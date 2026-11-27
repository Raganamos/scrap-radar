// Scrap Radar offline helper: app shell from cache when signal drops, live data always tried first.
const V='sr-v4',SHELL=['./','index.html','manifest.json','icon-192.png','https://unpkg.com/leaflet@1.9.4/dist/leaflet.css','https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(V).then(c=>c.addAll(SHELL)).catch(()=>{}));self.skipWaiting()});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==V).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(e.request.method!=='GET')return;
  if(u.hostname.includes('ntfy.sh')||u.hostname.includes('tile.openstreetmap'))return;
  const isStatic=u.hostname==='unpkg.com'||/\.png$/.test(u.pathname);
  if(isStatic){e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request).then(n=>{const c=n.clone();caches.open(V).then(x=>x.put(e.request,c));return n})));return}
  const key=u.origin+u.pathname;   // network first; fall back to the last good copy
  e.respondWith(fetch(e.request).then(n=>{if(n.ok){const c=n.clone();caches.open(V).then(x=>x.put(key,c))}return n}).catch(()=>caches.match(key).then(r=>r||caches.match('index.html'))))});
