from django import template

register = template.Library()


@register.filter
def tempo_no_setor(rastreio, codigo_setor):
    """Retorna o tempo formatado que a OP ficou em um setor específico."""
    if not rastreio:
        return '—'
    return rastreio.tempo_no_setor_formatado(codigo_setor)


@register.filter
def status_tempo_setor_classe(rastreio, codigo_setor):
    """Retorna a classe CSS de status de tempo de um setor."""
    if not rastreio:
        return ''
    return rastreio.status_tempo_setor_classe(codigo_setor)


@register.filter
def status_tempo_setor_texto(rastreio, codigo_setor):
    """Retorna o texto de status de tempo de um setor."""
    if not rastreio:
        return ''
    status = rastreio.status_tempo_setor(codigo_setor)
    if status == 'CRITICO':
        return 'Crítico'
    if status == 'ATENCAO':
        return 'Atenção'
    return 'OK'


@register.filter
def get_mesa_mesa(movimentacoes):
    """Retorna o número da mesa da movimentação da mesa."""
    if not movimentacoes:
        return ''
    try:
        mov = movimentacoes.filter(setor='mesa', mesa__isnull=False).first()
        return mov.mesa if mov else ''
    except Exception:
        return ''
