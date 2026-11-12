"""Filtros de formatação brasileira (real, quantidade, percentual).

PROBLEMA QUE RESOLVE
    O `floatformat` do Django imprime no padrão americano:
        {{ 46965576.42|floatformat:2 }}  ->  46965576.42
    O usuário lê errado. No Brasil o mesmo número é:
        46.965.576,42
    Ponto separa milhar, vírgula separa decimal. É o inverso.

    Além de ilegível, isso causa erro de leitura em valor alto: "46.965.576"
    lido como americano é quarenta e seis mil e novecentos e sessenta e cinco.

POR QUE UM FILTRO E NÃO O `USE_L10N`
    O `USE_L10N` do Django depende do locale e não formata separador de
    milhar por padrão. Um filtro explícito é previsível: sempre o mesmo
    resultado, em qualquer lugar do sistema.

USO NOS TEMPLATES
    Registrado como builtin em settings.TEMPLATES, então funciona em
    qualquer template sem `{% load %}`:

        R$ {{ valor|moeda }}         ->  R$ 46.965.576,42
        {{ qtd|quantidade }}         ->  4.825.833,032
        {{ pct|percentual }}         ->  59,4%
        {{ valor|moeda_curta }}      ->  R$ 46,97 mi
"""
from decimal import Decimal, InvalidOperation

from django import template
from django.template.defaultfilters import floatformat

register = template.Library()


def _dec(valor):
    """Converte para Decimal aceitando número, string com ponto ou vírgula."""
    if valor in (None, ''):
        return None
    if isinstance(valor, Decimal):
        return valor
    try:
        if isinstance(valor, str):
            s = valor.strip()
            # "1.234,56" (BR) -> 1234.56  |  "1234.56" (US) -> 1234.56
            if ',' in s and '.' in s:
                s = s.replace('.', '').replace(',', '.')
            elif ',' in s:
                s = s.replace(',', '.')
            return Decimal(s)
        return Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _formata(valor, casas, com_milhar=True):
    d = _dec(valor)
    if d is None:
        return ''
    s = f'{d:,.{casas}f}'          # 46,965,576.42 (US)
    if not com_milhar:
        return s.replace(',', 'X').replace('.', ',').replace('X', '.')
    # troca: vírgula (milhar) -> ponto, ponto (decimal) -> vírgula
    return s.replace(',', 'X').replace('.', ',').replace('X', '.')


@register.filter
def moeda(valor):
    """Valor em reais: 46965576.42 -> 46.965.576,42"""
    return _formata(valor, 2)


@register.filter
def moeda_simbolo(valor):
    """Valor em reais com o prefixo: R$ 46.965.576,42"""
    s = _formata(valor, 2)
    return f'R$ {s}' if s else ''


@register.filter
def moeda_4(valor):
    """Valor em reais com 4 casas — preço unitário de material.

    Perfil e vidro são comprados por quilo/metro e o preço tem mais casas.
    Arredondar para 2 aqui esconde diferença de centavo que, multiplicada
    por milhares de quilos, vira dinheiro.
    """
    return _formata(valor, 4)


@register.filter
def quantidade(valor):
    """Quantidade com 3 casas: 4825833.032 -> 4.825.833,032"""
    return _formata(valor, 3)


@register.filter
def quantidade_curta(valor):
    """Quantidade com no máximo 2 casas, sem zeros à direita: 12,5"""
    d = _dec(valor)
    if d is None:
        return ''
    if d == d.to_integral_value():
        return _formata(d, 0)
    return _formata(d, 2).rstrip('0').rstrip(',')


@register.filter
def percentual(valor):
    """Percentual com 1 casa: 59.4 -> 59,4%"""
    s = _formata(valor, 1)
    return f'{s}%' if s else ''


@register.filter
def moeda_curta(valor):
    """Valor abreviado para KPI e etiqueta: 46965576 -> R$ 46,97 mi

    Serve para cartão de indicador, onde o número completo não cabe e o
    que importa é a ordem de grandeza.
    """
    d = _dec(valor)
    if d is None:
        return ''
    n = float(d)
    sinal = '-' if n < 0 else ''
    n = abs(n)
    if n >= 1_000_000_000:
        return f'{sinal}R$ {_formata(n / 1_000_000_000, 2)} bi'
    if n >= 1_000_000:
        return f'{sinal}R$ {_formata(n / 1_000_000, 2)} mi'
    if n >= 1_000:
        return f'{sinal}R$ {_formata(n / 1_000, 1)} mil'
    return f'{sinal}R$ {_formata(n, 2)}'


@register.filter
def numero(valor):
    """Número com separador de milhar e sem casas: 25362 -> 25.362"""
    return _formata(valor, 0)


@register.filter
def casas(valor, n):
    """Formata com N casas escolhido no template: {{ x|casas:3 }}"""
    try:
        n = int(n)
    except (TypeError, ValueError):
        n = 2
    return _formata(valor, n)


@register.filter
def peso(valor):
    """Peso inteligente: kg abaixo de 1000, toneladas acima.
    
    Exemplos:
        500    -> 500,000 kg
        1500   -> 1,500 t
        25500  -> 25,500 t
        40000  -> 40,000 t
    """
    d = _dec(valor)
    if d is None:
        return ''
    kg = float(d)
    if kg < 1000:
        return _formata(kg, 3) + ' kg'
    t = kg / 1000
    return _formata(t, 3) + ' t'


@register.filter
def peso_kg(valor):
    """Peso sempre em kg com 3 casas: 25500 -> 25.500,000 kg"""
    d = _dec(valor)
    if d is None:
        return ''
    return _formata(float(d), 3) + ' kg'


@register.filter
def dictkey(dicionario, chave):
    """Acessa dicionario[chave] no template.

    O Django nao permite fazer dicionario[variavel] direto no template, e o
    filtro `dictsort` nao serve para isso. Sem este filtro, mostrar a senha
    por id exigiria uma query por linha.
    """
    if not dicionario:
        return ''
    try:
        return dicionario.get(chave, '')
    except AttributeError:
        try:
            return dicionario[chave]
        except (KeyError, IndexError, TypeError):
            return ''


@register.filter
def get_item(dicionario, chave):
    """Permite acessar dicionario[chave] no template."""
    if not dicionario:
        return ''
    try:
        return dicionario.get(chave, '')
    except AttributeError:
        try:
            return dicionario[chave]
        except (KeyError, IndexError, TypeError):
            return ''


@register.filter
def total(values):
    """Soma os valores de um iterável (dict.values(), list, etc)."""
    try:
        if hasattr(values, 'values'):
            return sum(values.values())
        return sum(values)
    except (TypeError, AttributeError):
        return 0


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

@register.filter
def div(value, divisor):
    """Divide um valor por outro (divisão)."""
    try:
        return float(value) / float(divisor)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0
