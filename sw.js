/* Portail Festival Mantra Joie : service worker.
   Ce qu'il fait : garder en mémoire l'enveloppe de l'interface (la page, les images, l'icône) pour s'ouvrir plus vite et rester ouvrable sans réseau.
   Ce qu'il ne fait JAMAIS :
   - toucher à une requête qui n'est pas un simple affichage (envois de formulaires, fichiers, connexion : méthode POST) ;
   - toucher à une requête vers un autre site (le script Google, les polices) : les données du portail et les réponses de l'API ne passent jamais par ici ;
   - garder une réponse d'erreur, ni une réponse qui interdit le stockage.
   La page est toujours demandée au réseau d'abord : on ne voit une copie gardée que sans réseau, donc jamais une vieille page avec un script à jour. */
const VERSION = 'v3.36-2027';
const CACHE = 'portail-mantra-' + VERSION;
const PAGE = './equipe.html';
const ENVELOPPE = [PAGE, './manifest.webmanifest', './assets/icon-192.png', './assets/icon-512.png', './assets/apple-touch-icon.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ENVELOPPE)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((cles) => Promise.all(cles.filter((c) => c.indexOf('portail-mantra-') === 0 && c !== CACHE).map((c) => caches.delete(c))))
      .then(() => self.clients.claim())
  );
});
function gardable(reponse) {
  if (!reponse || reponse.status !== 200 || reponse.type === 'opaque') return false;
  const cc = (reponse.headers && reponse.headers.get && reponse.headers.get('Cache-Control')) || '';
  return !/no-store|private/i.test(cc);
}
self.addEventListener('fetch', (event) => {
  const requete = event.request;
  if (requete.method !== 'GET') return;                                       // jamais un envoi
  const url = new URL(requete.url);
  if (url.origin !== self.location.origin) return;                            // jamais un autre site
  if (requete.mode === 'navigate') {                                          // la page : le réseau d'abord, la copie seulement hors ligne
    event.respondWith(
      fetch(requete).then((reponse) => {
        if (gardable(reponse)) { const copie = reponse.clone(); caches.open(CACHE).then((c) => c.put(PAGE, copie)); }
        return reponse;
      }).catch(() => caches.match(PAGE))
    );
    return;
  }
  if (url.pathname.indexOf('/assets/') < 0 && !/manifest\.webmanifest$/.test(url.pathname)) return;   // le reste ne nous regarde pas
  event.respondWith(                                                          // images et icônes : la copie tout de suite, mise à jour en arrière-plan
    caches.match(requete).then((gardee) => {
      const reseau = fetch(requete).then((reponse) => {
        if (gardable(reponse)) { const copie = reponse.clone(); caches.open(CACHE).then((c) => c.put(requete, copie)); }
        return reponse;
      }).catch(() => gardee);
      return gardee || reseau;
    })
  );
});
