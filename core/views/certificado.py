"""Pagina publica de instalacao do certificado da CA local.

Serve o certificado raiz da Casanova para os aparelhos da fabrica, de modo que
a camera do celular funcione em HTTPS sem o aviso "Nao seguro".

A CA e uma autoridade local da propria empresa (nao e uma CA publica). O
certificado servido aqui e APENAS a parte publica (.crt) — a chave privada
da CA nunca sai do servidor.
"""

import os

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import render


def _caminho_ca():
    return os.path.join(settings.BASE_DIR, 'core', 'static', 'certs', 'casanova-ca.crt')


def pagina_certificado(request):
    """Instrucoes de instalacao + link de download do certificado."""
    return render(request, 'core/certificado.html', {
        'ca_disponivel': os.path.exists(_caminho_ca()),
        'host': request.get_host().split(':')[0],
    })


def baixar_ca(request):
    """Entrega o certificado publico da CA para instalacao no aparelho."""
    caminho = _caminho_ca()
    if not os.path.exists(caminho):
        raise Http404('Certificado nao encontrado no servidor.')

    resp = FileResponse(open(caminho, 'rb'), content_type='application/x-x509-ca-cert')
    resp['Content-Disposition'] = 'attachment; filename="casanova-ca.crt"'
    return resp
