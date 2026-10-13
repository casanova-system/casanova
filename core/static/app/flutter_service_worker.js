'use strict';

// Service worker de limpeza: apaga todos os caches antigos e se desregistra
// para forçar o Safari do iPhone a carregar a versão mais recente do app.

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      // Apaga todos os caches antigos
      try {
        const cacheNames = await caches.keys();
        await Promise.all(
          cacheNames.map((name) => caches.delete(name))
        );
      } catch (e) {
        console.warn('Erro ao limpar caches:', e);
      }

      // Desregistra este service worker
      try {
        await self.registration.unregister();
      } catch (e) {
        console.warn('Erro ao desregistrar service worker:', e);
      }

      // Força recarregamento de todas as abas abertas
      try {
        const clients = await self.clients.matchAll({ type: 'window' });
        clients.forEach((client) => {
          if (client.url && 'navigate' in client) {
            client.navigate(client.url);
          }
        });
      } catch (e) {
        console.warn('Erro ao recarregar clientes:', e);
      }
    })()
  );
});
