"""Redireciona /app/ para a rotina de Producao (versao web responsiva).

O app Flutter foi descontinuado: o celular agora usa a MESMA tela do PC
(rotina /industria/producao/), que e responsiva e ja tem leitor de QR Code
pela camera. Mantemos esta rota apenas para nao quebrar atalhos salvos nos
celulares da fabrica - quem acessar /app/ cai direto na tela de Producao.
"""

from django.shortcuts import redirect


def app_mobile(request):
    """Redireciona o antigo app Flutter para a rotina de Producao."""
    return redirect('producao')
