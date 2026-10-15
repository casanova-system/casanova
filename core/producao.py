"""Cálculo de tempo de produção considerando apenas horas úteis.

Regras:
- Segunda a sexta: 07:00-11:00 e 12:12-17:00
- Sexta-feira: 07:00-11:00 e 12:12-16:00
- Sábado e domingo: não conta
- Horários de almoço (11:00-12:12) não contam

IMPORTANTE — fuso horário:
Os horários ficam gravados em UTC no banco (USE_TZ=True) e o Django os devolve
em UTC. Como as regras acima são do relógio da FÁBRICA (America/Cuiaba, UTC-4),
toda comparação precisa converter para o fuso local antes de olhar a hora —
senão 07:00 local (11:00 UTC) é lido como "fim da manhã" e o cálculo sai
errado. Isso é feito por `_local()`.
"""
from datetime import datetime, time, timedelta

from django.utils import timezone

# Limites de horário de production
MANHA_INICIO = time(7, 0)
MANHA_FIM = time(11, 0)
TARDE_INICIO = time(12, 12)
TARDE_FIM = time(17, 0)
TARDE_FIM_SEXTA = time(16, 0)


def _local(dt: datetime) -> datetime:
    """Converte um datetime para o fuso local da fábrica.

    O banco guarda UTC; as regras de horário são do relógio local. Sem esta
    conversão o cálculo compara hora UTC contra limites locais e erra por
    todo o offset do fuso (4 horas em America/Cuiaba).

    Datetimes "naive" (sem tzinfo) já são tratados como hora local — assim a
    função continua aceitando os testes que passam datetime puro.
    """
    if dt is None:
        return None
    if timezone.is_naive(dt):
        return dt
    return timezone.localtime(dt)


def _time_para_minutos(t: time) -> int:
    """Converte time para minutos desde meia-noite."""
    return t.hour * 60 + t.minute


def _dentro_do_horario(dt: datetime) -> bool:
    """Verifica se um datetime está dentro do horário de produção."""
    dt = _local(dt)

    # Fim de semana não conta
    if dt.weekday() >= 5:  # 5=sábado, 6=domingo
        return False

    minutos = _time_para_minutos(dt.time())
    tarde_fim = TARDE_FIM_SEXTA if dt.weekday() == 4 else TARDE_FIM

    # Manhã: 7:00 - 11:00
    if _time_para_minutos(MANHA_INICIO) <= minutos <= _time_para_minutos(MANHA_FIM):
        return True

    # Tarde: 12:12 - 17:00 (ou 16:00 na sexta)
    if _time_para_minutos(TARDE_INICIO) <= minutos <= _time_para_minutos(tarde_fim):
        return True

    return False


def _proximo_horario_valido(dt: datetime) -> datetime:
    """Retorna o próximo horário de produção válido a partir de dt."""
    dt = _local(dt)

    # Se for fim de semana, pula para segunda-feira 7:00
    if dt.weekday() >= 5:
        dias_para_segunda = 7 - dt.weekday()
        dt = (dt + timedelta(days=dias_para_segunda)).replace(hour=7, minute=0, second=0, microsecond=0)
        return dt

    tarde_fim = TARDE_FIM_SEXTA if dt.weekday() == 4 else TARDE_FIM
    minutos = _time_para_minutos(dt.time())

    # Se está antes do início da manhã
    if minutos < _time_para_minutos(MANHA_INICIO):
        return dt.replace(hour=MANHA_INICIO.hour, minute=MANHA_INICIO.minute, second=0, microsecond=0)

    # Se está no intervalo do almoço (11:00 - 12:12)
    if _time_para_minutos(MANHA_FIM) < minutos < _time_para_minutos(TARDE_INICIO):
        return dt.replace(hour=TARDE_INICIO.hour, minute=TARDE_INICIO.minute, second=0, microsecond=0)

    # Se está depois do fim da tarde
    if minutos > _time_para_minutos(tarde_fim):
        # Próximo dia às 7:00
        dt = dt + timedelta(days=1)
        # Se cair no fim de semana, pula para segunda
        while dt.weekday() >= 5:
            dt = dt + timedelta(days=1)
        return dt.replace(hour=7, minute=0, second=0, microsecond=0)

    return dt


def _minutos_producao_no_dia(dt: datetime) -> tuple:
    """Retorna (inicio_manha, fim_manha, inicio_tarde, fim_tarde) em minutos para o dia de dt."""
    tarde_fim = TARDE_FIM_SEXTA if dt.weekday() == 4 else TARDE_FIM
    return (
        _time_para_minutos(MANHA_INICIO),
        _time_para_minutos(MANHA_FIM),
        _time_para_minutos(TARDE_INICIO),
        _time_para_minutos(tarde_fim),
    )


def calcular_minutos_producao(data_inicio: datetime, data_fim: datetime = None) -> float:
    """Calcula quantos minutos de produção se passaram entre data_inicio e data_fim.

    Se data_fim for None, usa o horário atual.
    Apenas horas dentro do horário de produção são contadas.

    Os dois extremos são convertidos para o fuso local da fábrica antes de
    qualquer comparação: o banco guarda UTC, e as regras (7h-11h, 12h12-17h)
    são do relógio da fábrica. Comparar hora UTC contra limite local erra por
    todo o offset do fuso.
    """
    if data_inicio is None:
        return 0.0

    if data_fim is None:
        data_fim = timezone.now()

    # Garante que data_inicio não está no futuro (ordem preservada na conversão)
    if data_inicio > data_fim:
        return 0.0

    total_minutos = 0.0
    atual = _local(data_inicio)
    limite = _local(data_fim)

    # Limite de segurança: no máximo 366 dias (1 ano) para evitar loop infinito
    max_iteracoes = 366 * 2  # 2 blocos por dia
    iteracoes = 0

    while atual < limite and iteracoes < max_iteracoes:
        iteracoes += 1

        # Fim de semana: pula para segunda-feira 7:00
        if atual.weekday() >= 5:
            dias_para_segunda = 7 - atual.weekday()
            atual = (atual + timedelta(days=dias_para_segunda)).replace(hour=7, minute=0, second=0, microsecond=0)
            continue

        ini_manha, fim_manha, ini_tarde, fim_tarde = _minutos_producao_no_dia(atual)
        minutos_atual = _time_para_minutos(atual.time())

        # Determina o fim do bloco atual
        if minutos_atual < ini_manha:
            # Antes do início: pula para o início da manhã
            atual = atual.replace(hour=MANHA_INICIO.hour, minute=MANHA_INICIO.minute, second=0, microsecond=0)
            continue
        elif minutos_atual < ini_tarde:
            # Está entre manhã e tarde (almoço ou dentro da manhã)
            if minutos_atual <= fim_manha:
                # Dentro do bloco da manhã
                fim_bloco = atual.replace(hour=MANHA_FIM.hour, minute=MANHA_FIM.minute, second=0, microsecond=0)
            else:
                # No almoço: pula para o início da tarde
                atual = atual.replace(hour=TARDE_INICIO.hour, minute=TARDE_INICIO.minute, second=0, microsecond=0)
                continue
        elif minutos_atual <= fim_tarde:
            # Dentro do bloco da tarde
            fim_bloco = atual.replace(hour=TARDE_FIM.hour if atual.weekday() != 4 else TARDE_FIM_SEXTA.hour,
                                        minute=TARDE_FIM.minute if atual.weekday() != 4 else TARDE_FIM_SEXTA.minute,
                                        second=0, microsecond=0)
        else:
            # Depois do fim da tarde: pula para o próximo dia 7:00
            atual = (atual + timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)
            continue

        # Calcula os minutos deste bloco
        fim_efetivo = min(fim_bloco, limite)
        if atual < fim_efetivo:
            delta = (fim_efetivo - atual).total_seconds() / 60
            total_minutos += delta

        # Avança para depois do fim do bloco
        atual = fim_bloco + timedelta(seconds=1)

    return total_minutos
