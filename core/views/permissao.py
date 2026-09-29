from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404, redirect, render

from core.models import PerfilUsuario, Rotina, garantir_rotinas_padrao


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
    usuarios = User.objects.select_related('perfil').prefetch_related(
        'perfil__rotinas_permitidas'
    ).all()
    context = {
        'usuarios': usuarios,
    }
    return render(request, 'core/permissao_rotina/lista_permissao.html', context)


@login_required(login_url='login')
@requer_rotina('lista_permissao')
def form_permissao(request, user_id):
    """Gerencia nível de acesso, setor e as rotinas permitidas para o usuário."""
    garantir_rotinas_padrao()
    usuario_obj = get_object_or_404(User, id=user_id)
    perfil, _created = PerfilUsuario.objects.get_or_create(user=usuario_obj)
    todas_rotinas = Rotina.objects.all().order_by('codigo')

    if request.method == 'POST':
        perfil.nivel_acesso = request.POST.get('nivel_acesso') or perfil.nivel_acesso
        perfil.setor = request.POST.get('setor') or perfil.setor
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

    context = {
        'usuario_obj': usuario_obj,
        'perfil': perfil,
        'todas_rotinas': todas_rotinas,
    }
    return render(request, 'core/permissao_rotina/form_permissao.html', context)
