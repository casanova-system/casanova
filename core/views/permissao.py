from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from core.models import PerfilUsuario, Rotina, garantir_rotinas_padrao

ITENS_POR_PAGINA = 12


def requer_rotina(url_name):
    """Bloqueia a view se o usuário não tiver a rotina permitida."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            tem_acesso = False
            try:
                tem_acesso = request.user.perfil.tem_rotina(url_name)
            except (ObjectDoesNotExist, AttributeError):
                tem_acesso = False

            if not tem_acesso:
                messages.error(
                    request,
                    'Você não tem permissão para acessar esta rotina.',
                )
                return redirect('menu_principal')

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


@login_required(login_url='login')
@requer_rotina('lista_permissao')
def lista_permissao(request):
    """Lista todos os usuários para gerenciamento de permissões."""
    garantir_rotinas_padrao()
    query = request.GET.get('q', '').strip()
    ordenar = request.GET.get('ordenar', '').strip()
    acesso = request.GET.get('acesso', '').strip()
    setor_atual = request.GET.get('setor', '').strip()

    usuarios = User.objects.select_related('perfil').prefetch_related(
        'perfil__rotinas_permitidas'
    ).all()

    if query:
        usuarios = usuarios.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
            | Q(perfil__setor__icontains=query)
        )

    # Filtro de acesso: quem esta sem rotina e o que mais importa ver.
    if acesso == 'sem':
        usuarios = usuarios.filter(is_superuser=False).annotate(
            n_rotinas=Count('perfil__rotinas_permitidas')).filter(n_rotinas=0)
    elif acesso == 'com':
        usuarios = usuarios.filter(is_superuser=False).annotate(
            n_rotinas=Count('perfil__rotinas_permitidas')).filter(n_rotinas__gt=0)
    elif acesso == 'super':
        usuarios = usuarios.filter(is_superuser=True)

    if setor_atual:
        usuarios = usuarios.filter(perfil__setor=setor_atual)

    mapa_ordenacao = {
        'recentes': '-date_joined',
        'antigos': 'date_joined',
        'usuario_asc': 'username',
        'usuario_desc': '-username',
        'id_asc': 'id',
        'id_desc': '-id',
    }
    usuarios = usuarios.order_by(mapa_ordenacao.get(ordenar, 'first_name'))

    paginator = Paginator(usuarios, ITENS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))

    params = request.GET.copy()
    params.pop('page', None)
    querystring = params.urlencode()

    # KPIs sobre o conjunto INTEIRO (nao o filtrado): sao o retrato do sistema
    from core.models import PerfilUsuario as _PU
    total = User.objects.count()
    superusers = User.objects.filter(is_superuser=True).count()
    com_rotina = _PU.objects.filter(
        rotinas_permitidas__isnull=False).distinct().count()

    context = {
        'usuarios': page_obj,
        'page_obj': page_obj,
        'querystring': querystring,
        'query': query,
        'ordenacao_atual': ordenar,
        'acesso': acesso,
        'setor_atual': setor_atual,
        'setores': PerfilUsuario.SETOR_CHOICES,
        'kpi': {
            'total': total,
            'comuns': total - superusers,
            'superusers': superusers,
            'sem_rotina': total - com_rotina,
            'com_rotina': com_rotina,
            'total_rotinas': Rotina.objects.count(),
        },
    }
    return render(request, 'core/permissao_rotina/lista_permissao.html', context)


@login_required(login_url='login')
@requer_rotina('lista_usuarios')
def form_permissao(request, user_id):
    """Gerencia nível de acesso e as rotinas permitidas para o usuário.

    A rotina exigida é `lista_usuarios`: o gerenciamento de permissões é
    alcançado pelo botão de chave DENTRO da lista de usuários, não por uma
    rotina própria no menu. Exigir `lista_permissao` aqui bloquearia quem
    tem apenas a rotina de usuários — que é o fluxo normal.
    """
    garantir_rotinas_padrao()
    usuario_obj = get_object_or_404(User, id=user_id)
    perfil, _created = PerfilUsuario.objects.get_or_create(user=usuario_obj)
    todas_rotinas = Rotina.objects.all().order_by('codigo')

    if request.method == 'POST':
        perfil.nivel_acesso = request.POST.get('nivel_acesso') or perfil.nivel_acesso
        perfil.save()

        rotinas_ids = [
            int(rotina_id)
            for rotina_id in request.POST.getlist('rotinas')
            if str(rotina_id).isdigit()
        ]
        perfil.rotinas_permitidas.set(rotinas_ids)
        messages.success(
            request,
            f'Permissões de {usuario_obj.username} atualizadas com sucesso.',
        )
        return redirect('lista_usuarios')

    # Cada setor vira um bloco com cor e icone proprios. A ordem e fixa
    # (nao alfabetica) para as areas mais usadas aparecerem primeiro.
    SETORES = [
        ('INDUSTRIA', 'Indústria', 'fa-industry', '#7c3aed'),
        ('COMERCIAL', 'Comercial', 'fa-briefcase', '#0b3882'),
        ('FINANCEIRO', 'Financeiro', 'fa-coins', '#059669'),
        ('FROTAS', 'Frotas', 'fa-truck', '#d97706'),
        ('ADMINISTRADOR', 'Administrador', 'fa-user-shield', '#dc2626'),
    ]

    rotinas_por_setor = []
    for codigo, nome, icone, cor in SETORES:
        do_setor = list(todas_rotinas.filter(setor=codigo))
        if do_setor:
            rotinas_por_setor.append({
                'nome': nome,
                'icone': icone,
                'cor': cor,
                'rotinas': do_setor,
            })

    context = {
        'usuario_obj': usuario_obj,
        'perfil': perfil,
        'todas_rotinas': todas_rotinas,
        'rotinas_por_setor': rotinas_por_setor,
    }
    return render(request, 'core/permissao_rotina/form_permissao.html', context)
