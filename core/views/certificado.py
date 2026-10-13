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

_CERT_DIR = ('core', 'static', 'certs')


def _caminho(nome):
    return os.path.join(settings.BASE_DIR, *_CERT_DIR, nome)


def pagina_certificado(request):
    """Instrucoes de instalacao + links de download."""
    return render(request, 'core/certificado.html', {
        'ca_disponivel': os.path.exists(_caminho('casanova-ca.crt')),
        'bat_disponivel': os.path.exists(_caminho('instalar-certificado-windows.bat')),
        'host': request.get_host().split(':')[0],
    })


def baixar_ca(request):
    """Entrega o certificado publico da CA para instalacao no aparelho."""
    caminho = _caminho('casanova-ca.crt')
    if not os.path.exists(caminho):
        raise Http404('Certificado nao encontrado no servidor.')

    resp = FileResponse(open(caminho, 'rb'), content_type='application/x-x509-ca-cert')
    resp['Content-Disposition'] = 'attachment; filename="casanova-ca.crt"'
    return resp


def baixar_instalador_windows(request):
    """Entrega o .bat que instala a CA no Windows com um duplo clique."""
    caminho = _caminho('instalar-certificado-windows.bat')
    if not os.path.exists(caminho):
        raise Http404('Instalador nao encontrado no servidor.')

    resp = FileResponse(open(caminho, 'rb'), content_type='application/octet-stream')
    resp['Content-Disposition'] = 'attachment; filename="instalar-certificado-windows.bat"'
    return resp
