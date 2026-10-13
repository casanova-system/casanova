'use strict';

// SERVICE WORKER DE LIMPEZA
// Apaga todos os caches antigos e se desregistra para forçar
// o Safari do iPhone a carregar a versão mais recente do app.

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      // 1. Apaga TODOS os caches antigos
      try {
        const cacheNames = await caches.keys();
        await Promise.all(
          cacheNames.map((name) => caches.delete(name))
        );
        console.log('[SW Limpeza] Caches apagados:', cacheNames);
      } catch (e) {
        console.warn('[SW Limpeza] Erro ao limpar caches:', e);
      }

      // 2. Desregistra este service worker
      try {
        await self.registration.unregister();
        console.log('[SW Limpeza] Service worker desregistrado');
      } catch (e) {
        console.warn('[SW Limpeza] Erro ao desregistrar:', e);
      }

      // 3. Força recarregamento de todas as abas abertas
      try {
        const clients = await self.clients.matchAll({ type: 'window' });
        clients.forEach((client) => {
          if (client.url && 'navigate' in client) {
            client.navigate(client.url);
          }
        });
      } catch (e) {
        console.warn('[SW Limpeza] Erro ao recarregar clientes:', e);
      }
    })()
  );
});
