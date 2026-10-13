(()=>{
if (!window._flutter) {
  window._flutter = {};
}
_flutter.buildConfig = {"engineRevision":"692136cb6582dbfc5af3fb33c2515a069f2f66d0","wasmHashes":{"canvaskit.wasm":"fbed517a43e82452404446683f00f2e876d835aed84410695759e67b6bb01cd3","chromium/canvaskit.wasm":"ae8ff1d858140f7b1300ced3fa89fb8c9dce0a400a0f4f1e11f6dcfb3315fdcf","skwasm.wasm":"e540fd5e8303b7b68ec2718cb49e9c421f8ade3075b15e02a7059a62654df9a1","skwasm_heavy.wasm":"565f5cc1cca6ab120f11934b105f01fec4b58b480c82e0889dca93af8e6f8635","webparagraph/canvaskit.wasm":"0ce1b05082efdc8529550e8a01f6ff0593972d55525035010e26f5600aa9f254","wimp.wasm":"e924eaafd801d41e017d178f3fd5cf8a417f641fe35c9ed34a4e1d7582283e0c"},"builds":[{"compileTarget":"dart2js","renderer":"canvaskit","mainJsPath":"casanova_app.js"},{}]};

// Desregistra qualquer service worker antigo
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations().then(function(regs) {
    regs.forEach(function(r) { r.unregister(); });
  });
}
if (window.caches) {
  caches.keys().then(function(names) {
    names.forEach(function(name) { caches.delete(name); });
  });
}

// Carrega o app com nome NOVO (sem cache do iOS)
var script = document.createElement('script');
script.src = 'casanova_app.js?v=' + Date.now();
script.type = 'application/javascript';
document.head.appendChild(script);
})();
