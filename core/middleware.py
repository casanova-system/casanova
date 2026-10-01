"""Middleware de detecção de dispositivo.

Quando um celular (iOS/Android) acessa o sistema **voltado para PC**, ele é
redirecionado automaticamente para o app mobile em ``/app/``.

Regras:
- Só redireciona requisições GET de navegação (não afeta API, estáticos, etc.).
- Não redireciona se o usuário já está em ``/app/`` ou em rotas de API/estáticos.
- Não redireciona se o usuário pedir explicitamente o site completo
  (``?desktop=1``) — a escolha fica salva em cookie por 30 dias.
"""

import re

from django.shortcuts import redirect

# User-agents de celular/tablet (iOS, Android, Windows Phone, etc.)
_MOBILE_RE = re.compile(
    r'(android|iphone|ipod|ipad|windows phone|blackberry|opera mini|'
    r'mobile|webos|iemobile|kindle|silk)',
    re.IGNORECASE,
)

# Prefixos que NUNCA devem ser redirecionados.
_PREFIXOS_IGNORADOS = (
    '/app/',        # o próprio app mobile
    '/api/',        # API REST
    '/static/',     # arquivos estáticos
    '/media/',      # uploads
    '/admin/',      # admin do Django
    '/fotos_perfil/',
)

# Nome do cookie que guarda a preferência "usar versão desktop".
_COOKIE_DESKTOP = 'casanova_desktop'
_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 dias


class MobileRedirectMiddleware:
    """Redireciona celulares para o app mobile em ``/app/``."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Usuário pediu explicitamente a versão desktop? Salva a preferência.
        if request.GET.get('desktop') == '1':
            response = self.get_response(request)
            response.set_cookie(
                _COOKIE_DESKTOP, '1', max_age=_COOKIE_MAX_AGE, samesite='Lax'
            )
            return response

        if self._deve_redirecionar(request):
            return redirect('/app/')

        return self.get_response(request)

    def _deve_redirecionar(self, request):
        # Só GET (navegação). POST/PUT/DELETE seguem o fluxo normal.
        if request.method != 'GET':
            return False

        caminho = request.path

        # Já está em uma rota ignorada?
        if caminho.startswith(_PREFIXOS_IGNORADOS):
            return False

        # Usuário já escolheu a versão desktop (cookie)?
        if request.COOKIES.get(_COOKIE_DESKTOP) == '1':
            return False

        # É um celular?
        ua = request.META.get('HTTP_USER_AGENT', '')
        return bool(_MOBILE_RE.search(ua))

