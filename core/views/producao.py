"""Relatório de Produção — métricas de rastreio, tempo por setor e eficiência.

Gera relatório completo do fluxo de produção com:
- Métricas por setor (tempo médio, total, min/max)
- Timeline de movimentações com timestamps
- Resumo executivo de produção
- Identificação de gargalos (setores com maior tempo)
- Carga horária da empresa (Seg-Sex: 7h-17h, Sexta: 7h-16h, almoço 1h12min)
"""

from datetime import date, datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.models import RastreioOP, MovimentacaoOP, SetorProducao
from core.views.permissao import requer_rotina

# === CARGA HORÁRIA DA EMPRESA ===
# Segunda a Sexta: 7:00 às 17:00 (10h brutas) - 1h12min almoço = 8h48min líquidas
# Sexta: 7:00 às 16:00 (9h brutas) - 1h12min almoço = 7h48min líquidas
CARGA_SEG_SEX = timedelta(hours=8, minutes=48)  # 8h48min
CARGA_SEXTA = timedelta(hours=7, minutes=48)    # 7h48min
ALMOCo = timedelta(hours=1, minutes=12)         # 1h12min


def _dias_uteis(data_inicio, data_fim):
    """Calcula dias úteis no período e carga horária total esperada."""
    dias_seg_sex = 0
    dias_sexta = 0
    data_atual = data_inicio
    while data_atual <= data_fim:
        # weekday(): 0=seg, 6=dom
        if data_atual.weekday() < 5:  # Seg-Sex
            dias_seg_sex += 1
        elif data_atual.weekday() == 5:  # Sexta
            dias_sexta += 1
        data_atual += timedelta(days=1)
    
    carga_total = (dias_seg_sex * CARGA_SEG_SEX) + (dias_sexta * CARGA_SEXTA)
    return {
        'dias_seg_sex': dias_seg_sex,
        'dias_sexta': dias_sexta,
        'dias_totais': dias_seg_sex + dias_sexta,
        'carga_total': carga_total,
        'carga_seg_sex': CARGA_SEG_SEX,
        'carga_sexta': CARGA_SEXTA,
        'almoco': ALMOCo,
    }


def _formatar_tempo(td):
    """Formata timedelta em 'Xh XXmin'."""
    if td is None:
        return '—'
    total_min = int(td.total_seconds() / 60)
    h = total_min // 60
    m = total_min % 60
    return f'{h}h {m:02d}min' if m else f'{h}h'


@login_required(login_url='login')
@requer_rotina('relatorio_fretes_mes')
def relatorio_producao(request):
    """Relatório de produção — métricas de rastreio, tempo por setor e eficiência."""

    # Filtros de período
    data_inicio_str = request.GET.get('data_inicio', '')
    data_fim_str = request.GET.get('data_fim', '')

    # Se não houver filtro, usa últimos 30 dias
    if not data_inicio_str or not data_fim_str:
        hoje = date.today()
        data_inicio_str = (hoje - timedelta(days=30)).strftime('%Y-%m-%d')
        data_fim_str = hoje.strftime('%Y-%m-%d')

    data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()

    # Filtra movimentações por período
    movimentacoes = MovimentacaoOP.objects.filter(
        data_entrada__date__gte=data_inicio,
        data_entrada__date__lte=data_fim,
    )
    rastreios = RastreioOP.objects.filter(
        criado_em__date__gte=data_inicio,
        criado_em__date__lte=data_fim,
    )

    # Setores do fluxo
    setores = SetorProducao.objects.filter(ativo=True).order_by('ordem')

    # === MÉTRICAS POR SETOR ===
    metricas_setores = []
    for setor in setores:
        movs = movimentacoes.filter(setor=setor.codigo)
        total_movs = movs.count()
        movs_completas = movs.filter(data_entrada__isnull=False, data_saida__isnull=False)

        tempo_total = None
        tempo_medio = None
        tempo_min = None
        tempo_max = None

        if movs_completas.exists():
            duracoes = []
            for mov in movs_completas:
                if mov.data_entrada and mov.data_saida:
                    duracao = (mov.data_saida - mov.data_entrada).total_seconds()
                    duracoes.append(duracao)
            if duracoes:
                tempo_total = sum(duracoes)
                tempo_medio = tempo_total / len(duracoes)
                tempo_min = min(duracoes)
                tempo_max = max(duracoes)

        ops_no_setor = rastreios.filter(setor_atual=setor.codigo).count()
        ops_concluidas = movs_completas.values('rastreio').distinct().count()

        metricas_setores.append({
            'setor': setor,
            'total_movimentacoes': total_movs,
            'ops_concluidas': ops_concluidas,
            'ops_no_setor': ops_no_setor,
            'tempo_total': tempo_total,
            'tempo_medio': tempo_medio,
            'tempo_min': tempo_min,
            'tempo_max': tempo_max,
        })

    # === RESUMO EXECUTIVO ===
    total_ops = rastreios.count()
    ops_concluidas_total = rastreios.filter(status='CONCLUIDA').count()
    ops_em_producao = rastreios.filter(status='EM_PRODUCAO').count()

    # Tempo total de produção
    tempo_producao_total = None
    if movimentacoes.exists():
        primeira = movimentacoes.order_by('data_entrada').first()
        ultima = movimentacoes.order_by('-data_saida').first()
        if primeira.data_entrada and ultima.data_saida:
            tempo_producao_total = (ultima.data_saida - primeira.data_entrada).total_seconds()

    # Gargalo: setor com maior tempo médio
    gargalo = None
    for m in metricas_setores:
        if m['tempo_medio'] is not None:
            if gargalo is None or m['tempo_medio'] > gargalo['tempo_medio']:
                gargalo = m

    # === CARGA HORÁRIA E EFICIÊNCIA ===
    carga_horaria = _dias_uteis(data_inicio, data_fim)
    
    # Tempo total gasto em produção (soma de todas as movimentacoes completas)
    tempo_produção_total_segundos = 0
    for m in metricas_setores:
        if m['tempo_total']:
            tempo_produção_total_segundos += m['tempo_total']
    
    # Eficiência: tempo de produção / carga horária disponível
    eficiencia = None
    if carga_horaria['carga_total'].total_seconds() > 0 and tempo_produção_total_segundos > 0:
        eficiencia = (tempo_produção_total_segundos / carga_horaria['carga_total'].total_seconds()) * 100

    # OPs por dia (média)
    ops_por_dia = None
    if carga_horaria['dias_totais'] > 0:
        ops_por_dia = ops_concluidas_total / carga_horaria['dias_totais']

    # === TIMELINE DE MOVIMENTAÇÕES (últimas 50) ===
    timeline = movimentacoes.select_related(
        'rastreio', 'usuario_entrada', 'usuario_saida'
    ).order_by('-data_entrada')[:50]

    # === MOVIMENTAÇÕES COM PROBLEMA (tempo > 2h) ===
    movimentacoes_problema = []
    for mov in movimentacoes.filter(data_entrada__isnull=False, data_saida__isnull=False):
        duracao = (mov.data_saida - mov.data_entrada).total_seconds()
        if duracao > 7200:
            movimentacoes_problema.append({
                'movimentacao': mov,
                'duracao': duracao,
            })
    movimentacoes_problema.sort(key=lambda x: x['duracao'], reverse=True)

    # === MOVIMENTAÇÕES EM ANDAMENTO ===
    movimentacoes_andamento = movimentacoes.filter(
        data_entrada__isnull=False, data_saida__isnull=True
    ).select_related('rastreio', 'usuario_entrada').order_by('-data_entrada')

    # Formata datas para exibição
    data_inicio_fmt = data_inicio.strftime('%d/%m/%Y')
    data_fim_fmt = data_fim.strftime('%d/%m/%Y')

    context = {
        'data_inicio': data_inicio_str,
        'data_fim': data_fim_str,
        'data_inicio_fmt': data_inicio_fmt,
        'data_fim_fmt': data_fim_fmt,
        'total_ops': total_ops,
        'ops_concluidas_total': ops_concluidas_total,
        'ops_em_producao': ops_em_producao,
        'tempo_producao_total': tempo_producao_total,
        'metricas_setores': metricas_setores,
        'gargalo': gargalo,
        'timeline': timeline,
        'movimentacoes_problema': movimentacoes_problema,
        'movimentacoes_andamento': movimentacoes_andamento,
        'carga_horaria': carga_horaria,
        'eficiencia': eficiencia,
        'ops_por_dia': ops_por_dia,
        'tempo_produção_total_segundos': tempo_produção_total_segundos,
        'data_geracao': datetime.now(),
        'usuario_gerador': request.user.get_full_name() or request.user.username,
        '_formatar_tempo': _formatar_tempo,
    }
    return render(request, 'core/relatorios/relatorio_producao.html', context)
