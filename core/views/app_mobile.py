"""Serve o app Flutter (web) dentro do Django.

O build do Flutter fica em ``core/static/app/`` e é servido pelo WhiteNoise
em ``/static/app/``. Esta view apenas entrega o ``index.html`` na rota ``/app/``
para que o usuário acesse pelo navegador do celular (iPhone/Android) sem
instalar nada.
"""

import os

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse


def _index_path():
    return os.path.join(settings.BASE_DIR, 'core', 'static', 'app', 'index.html')


def app_mobile(request):
    """Entrega o index.html do app Flutter."""
    caminho = _index_path()
    if not os.path.exists(caminho):
        return HttpResponse(
            '<h1>App mobile não encontrado</h1>'
            '<p>O build do Flutter ainda não foi gerado/deployado.</p>'
            '<p>Rode: <code>flutter build web --release --base-href /static/app/</code> '
            'e copie <code>build/web</code> para <code>core/static/app/</code>.</p>',
            status=404,
        )
    return FileResponse(open(caminho, 'rb'), content_type='text/html')
