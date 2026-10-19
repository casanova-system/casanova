import json
import time
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from ..models import Obra, PerfilUsuario

# Segurança do login
MAX_TENTATIVAS_LOGIN = 3
BLOQUEIO_SEGUNDOS = 300  # 5 minutos de bloqueio após exceder as tentativas


def login_view(request):
    if request.method == "POST":
        usuario = request.POST.get("username")
        senha = request.POST.get("password")

        tentativas = request.session.get("tentativas_login", 0)
        bloqueado_ate = request.session.get("login_bloqueado_ate", 0)

        # Verifica se ainda está bloqueado
        if bloqueado_ate and time.time() < bloqueado_ate:
            restante = int(bloqueado_ate - time.time())
            minutos = restante // 60
            segundos = restante % 60
            return render(
                request,
                "core/login.html",
                {
                    "erro": (
                        "Acesso temporariamente bloqueado por excesso de tentativas. "
                        f"Tente novamente em {minutos}m {segundos}s."
                    ),
                    "username": usuario,
                    "bloqueado": True,
                },
            )

        # Bloqueio expirou: zera o contador
        if bloqueado_ate and time.time() >= bloqueado_ate:
            request.session["tentativas_login"] = 0
            request.session["login_bloqueado_ate"] = 0
            tentativas = 0

        user = authenticate(request, username=usuario, password=senha)
        if user is not None:
            # Login bem-sucedido: limpa o contador
            request.session["tentativas_login"] = 0
            request.session["login_bloqueado_ate"] = 0
            login(request, user)
            return redirect("menu_principal")

        # Login falhou
        tentativas += 1
        request.session["tentativas_login"] = tentativas
        restantes = MAX_TENTATIVAS_LOGIN - tentativas

        if restantes <= 0:
            request.session["login_bloqueado_ate"] = time.time() + BLOQUEIO_SEGUNDOS
            return render(
                request,
                "core/login.html",
                {
                    "erro": (
                        "Número máximo de tentativas excedido. "
                        "Acesso bloqueado por 5 minutos."
                    ),
                    "username": usuario,
                    "bloqueado": True,
                },
            )

        return render(
            request,
            "core/login.html",
            {
                "erro": (
                    "Usuário ou senha inválidos. "
                    f"Você tem {restantes} tentativa(s) restante(s)."
                ),
                "username": usuario,
                "tentativas_restantes": restantes,
            },
        )

    return render(request, "core/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required(login_url='login')
def menu_principal(request):
    """Dashboard: atalhos para as rotinas que o usuário realmente tem.

    Monta os cards a partir do BANCO (Rotina), não de uma lista fixa no
    template. Motivo: a lista fixa apontava para rotinas que não existem
    mais (Custo de Frete, Veículos, Custos) e duplicava "Usuários" com
    "Usuários e Permissões" — dois cards para a mesma tela.

    Ordem dos grupos fixa (não alfabética): as áreas de fábrica primeiro.
    """
    from core.models import PerfilUsuario, Rotina

    # Aparencia de cada rotina: icone, cor e descricao curta.
    # Chaveado por url_name — é o que identifica a rotina no menu e no banco.
    APARENCIA = {
        'lista_ordem_producao': ('fa-industry', '#7c3aed', 'Ordens de produção do ERP'),
        'rastreio_producao':    ('fa-route', '#0891b2', 'Acompanhe a OP pelos setores'),
        'producao':             ('fa-barcode', '#0b3882', 'Bipar OP no setor'),
        'lista_estrutura':      ('fa-sitemap', '#7c3aed', 'Composição das esquadrias'),
        'lista_estruturas':     ('fa-sitemap', '#7c3aed', 'Composição das esquadrias'),
        'lista_estoque':        ('fa-boxes-stacked', '#0891b2', 'Saldo por produto e local'),
        'lista_movimentos_hist': ('fa-right-left', '#0891b2', 'Entradas e saídas do estoque'),
        'lista_compras':        ('fa-cart-flatbed', '#059669', 'Requisições e pedidos'),
        'lista_requisicoes':    ('fa-clipboard-list', '#059669', 'Solicitações de material'),
        'lista_pedidos':        ('fa-file-invoice', '#059669', 'Pedidos aos fornecedores'),
        'lista_fornecedores':   ('fa-handshake', '#059669', 'Cadastro de fornecedores'),
        'lista_romaneios':      ('fa-truck-ramp-box', '#d97706', 'Cargas e entregas'),
        'lista_custos':         ('fa-coins', '#dc2626', 'Custo por OP e por setor'),
        'custos_setores':       ('fa-money-bill-trend-up', '#dc2626', 'Custo/hora de cada posto'),
        'lista_vendas':         ('fa-file-signature', '#0b3882', 'Pedidos de venda'),
        'lista_propostas':      ('fa-file-lines', '#0b3882', 'Propostas comerciais'),
        'lista_contas_pagar':   ('fa-arrow-up-right-dots', '#059669', 'O que a fábrica deve'),
        'lista_contas_receber': ('fa-arrow-down-left-dots', '#059669', 'O que a fábrica tem a receber'),
        'lista_notas':          ('fa-receipt', '#059669', 'Histórico do que foi faturado'),
        'painel_financeiro':    ('fa-chart-pie', '#059669', 'Retrato do dinheiro da fábrica'),
        'lista_funcionarios':   ('fa-users', '#7c3aed', 'Equipe e setores'),
        'funcionarios_por_setor': ('fa-people-group', '#7c3aed', 'Equipe agrupada por setor'),
        'lista_usuarios':       ('fa-users-gear', '#475569', 'Cadastro e permissões de acesso'),
        'lista_permissao':      ('fa-key', '#475569', 'Controle de rotinas por usuário'),
    }

    # Grupos espelham EXATAMENTE o menu lateral (base.html). Se divergirem,
    # o usuario ve uma rotina no dashboard que nao esta no menu, ou o
    # contrario — foi o que aconteceu com "Custo de Frete" e "Veiculos".
    GRUPOS = [
        ('PRODUCAO', 'Produção', 'fa-industry', '#7c3aed',
         ['lista_ordem_producao', 'rastreio_producao', 'producao',
          'lista_estruturas']),
        ('ESTOQUE', 'Estoque', 'fa-boxes-stacked', '#0891b2',
         ['lista_estoque', 'lista_movimentos_hist']),
        ('COMPRAS', 'Compras', 'fa-cart-flatbed', '#059669',
         ['lista_compras', 'lista_pedidos', 'lista_fornecedores']),
        ('EXPEDICAO', 'Expedição', 'fa-truck-ramp-box', '#d97706',
         ['lista_romaneios']),
        ('CUSTOS', 'Custos', 'fa-coins', '#dc2626',
         ['lista_custos', 'custos_setores']),
        ('COMERCIAL', 'Comercial', 'fa-briefcase', '#0b3882',
         ['lista_vendas', 'lista_propostas']),
        ('FINANCEIRO', 'Financeiro', 'fa-money-bill-trend-up', '#059669',
         ['painel_financeiro', 'lista_contas_pagar', 'lista_contas_receber',
          'lista_notas']),
        ('PESSOAS', 'Pessoas', 'fa-users-gear', '#475569',
         ['lista_funcionarios', 'funcionarios_por_setor', 'lista_usuarios',
          'lista_permissao']),
    ]

    # Nome amigavel por url_name: o nome no banco e generico ("Estoque"),
    # mas no dashboard "Saldo e Movimentacao" diz mais ao usuario.
    TITULO = {
        'lista_estoque': 'Saldo e Movimentação',
        'lista_movimentos_hist': 'Movimentos (histórico)',
        'lista_compras': 'Requisições e Pedidos',
        'lista_pedidos': 'Pedidos ao Fornecedor',
        'lista_custos': 'Custo por OP',
        'custos_setores': 'Custo por Setor',
        'lista_estruturas': 'Estrutura de Produtos',
        'lista_funcionarios': 'Funcionários',
        'funcionarios_por_setor': 'Funcionários por Setor',
        'lista_permissao': 'Permissões de Acesso',
    }

    # Rotinas que o usuario pode ver (superuser ve todas)
    if request.user.is_superuser:
        permitidas = set(Rotina.objects.values_list('url_name', flat=True))
    else:
        perfil, _ = PerfilUsuario.objects.get_or_create(user=request.user)
        permitidas = set(perfil.rotinas_permitidas.values_list('url_name', flat=True))

    # Nome de cada rotina no banco, para usar quando nao houver TITULO proprio
    nome_banco = dict(Rotina.objects.values_list('url_name', 'nome'))

    grupos_menu = []
    for _cod, nome, icone, cor, urls in GRUPOS:
        itens = []
        for url_name in urls:
            if url_name not in permitidas:
                continue
            aparencia = APARENCIA.get(url_name)
            if not aparencia:
                continue
            ic, co, desc = aparencia
            itens.append({
                'titulo': TITULO.get(url_name) or nome_banco.get(url_name, url_name),
                'descricao': desc,
                'url': url_name,
                'icone': ic,
                'cor': co,
            })
        if itens:
            grupos_menu.append({
                'nome': nome, 'icone': icone, 'cor': cor, 'itens': itens,
            })

    context = {
        'grupos_menu': grupos_menu,
        'rotinas_liberadas': sum(len(g['itens']) for g in grupos_menu),
    }
    return render(request, "core/menu.html", context)


@login_required(login_url='login')
def atualizar_foto_perfil(request):
    """
    View responsável por atualizar a foto de perfil do usuário logado no banco de dados.
    """
    if request.method == 'POST' and request.FILES.get('foto'):
        try:
            # Usa get_or_create para garantir que o perfil existe em qualquer circunstância
            perfil, created = PerfilUsuario.objects.get_or_create(user=request.user)
            perfil.foto = request.FILES['foto']
            perfil.save()
            messages.success(request, "Foto de perfil atualizada com sucesso!")
        except Exception as e:
            messages.error(request, f"Erro ao atualizar foto: {e}")
            
    return redirect(request.META.get('HTTP_REFERER', 'menu_principal'))


@login_required(login_url='login')
def rotinas_view(request):
    return redirect("menu_principal")


# ADICIONADO DE VOLTA: View genérica da página de gráficos do menu
@login_required(login_url='login')
def graficos_view(request):
    return redirect("grafico_custo_frete")


@login_required(login_url='login')
def relatorios_view(request):
    return redirect("relatorio_fretes_mes")