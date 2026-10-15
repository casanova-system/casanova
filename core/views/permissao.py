from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db.models import Q
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
    query = request.GET.get('q', '')
    ordenar = request.GET.get('ordenar', '')

    usuarios = User.objects.select_related('perfil').prefetch_related(
        'perfil__rotinas_permitidas'
    ).all()

    if query:
        usuarios = usuarios.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(perfil__setor__icontains=query)
        )

    mapa_ordenacao = {
        'recentes': '-date_joined',
        'antigos': 'date_joined',
        'usuario_asc': 'username',
        'usuario_desc': '-username',
        'id_asc': 'id',
        'id_desc': '-id',
    }
    usuarios = usuarios.order_by(mapa_ordenacao.get(ordenar, '-date_joined'))

    paginator = Paginator(usuarios, ITENS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))

    params = request.GET.copy()
    params.pop('page', None)
    querystring = params.urlencode()

    context = {
        'usuarios': page_obj,
        'page_obj': page_obj,
        'querystring': querystring,
        'query': query,
        'ordenacao_atual': ordenar,
    }
    return render(request, 'core/permissao_rotina/lista_permissao.html', context)


@login_required(login_url='login')
@requer_rotina('lista_permissao')
def form_permissao(request, user_id):
    """Gerencia nível de acesso e as rotinas permitidas para o usuário."""
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
        return redirect('lista_permissao')

    # Agrupa as rotinas por categoria e, dentro de cada uma, por setor
    def agrupar_por_setor(queryset):
        return {
            'COMERCIAL': queryset.filter(setor='COMERCIAL'),
            'FINANCEIRO': queryset.filter(setor='FINANCEIRO'),
            'FROTAS': queryset.filter(setor='FROTAS'),
            'INDUSTRIA': queryset.filter(setor='INDUSTRIA'),
            'ADMINISTRADOR': queryset.filter(setor='ADMINISTRADOR'),
        }

    rotinas_por_categoria = {
        'ROTINA': agrupar_por_setor(todas_rotinas.filter(categoria='ROTINA')),
    }

    context = {
        'usuario_obj': usuario_obj,
        'perfil': perfil,
        'todas_rotinas': todas_rotinas,
        'rotinas_por_categoria': rotinas_por_categoria,
    }
    return render(request, 'core/permissao_rotina/form_permissao.html', context)
