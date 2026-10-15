"""Versionamento automático de assets estáticos.

Problema que resolve: o `<link href="casanova.css?v=1">` tem versão fixa. Quando
o CSS muda, o navegador continua servindo a cópia em cache (a URL é a mesma) e
o usuário jura que "nada mudou". Trocar o número na mão a cada deploy é
esquecimento garantido.

Solução: `{% static_v 'css/casanova.css' %}` devolve a URL com um sufixo
derivado do mtime do arquivo. Quando o arquivo muda, a URL muda e o navegador
baixa a versão nova — sem intervenção manual.
"""
import os

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def static_v(path):
    """URL do estático com ?v=<mtime>, forçando a atualização do cache.

    Em produção (DEBUG=False) o WhiteNoise já aplica hash no nome do arquivo
    via ManifestStaticFilesStorage — nesse caso `static()` devolve a URL com
    hash e não precisamos acrescentar nada.
    """
    url = static(path)

    # Se o storage já versionou (nome com hash), não mexe.
    if '?' in url:
        return url

    try:
        caminho = finders.find(path)
    except Exception:  # noqa: BLE001
        caminho = None

    if not caminho:
        raiz = getattr(settings, 'STATIC_ROOT', None) or ''
        candidato = os.path.join(raiz, path) if raiz else ''
        caminho = candidato if candidato and os.path.exists(candidato) else None

    if caminho and os.path.exists(caminho):
        try:
            versao = int(os.path.getmtime(caminho))
        except OSError:
            return url
        return f'{url}?v={versao}'

    return url
