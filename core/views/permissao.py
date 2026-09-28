from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from core.models import PerfilUsuario, Rotina
from functools import wraps

def requer_rotina(url_name):
    """Decorador para bloquear views caso o usuário não tenha a rotina permitida."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Verifica se o usuário tem perfil e se a rotina está liberada
            has_permissao = False
            if hasattr(request, 'user') and hasattr(request.user, 'perfil'):
                has_permissao = request.user.perfil.rotinas_permitidas.filter(url_name=url_name).exists()
            
            if not has_permissao:
                return redirect('menu_principal')
                
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


@login_required
def lista_permissao(request):
    """Lista todos os usuários para gerenciamento de permissões."""
    usuarios = User.objects.select_related('perfil').all()
    context = {
        'usuarios': usuarios,
    }
    return render(request, 'core/permissao_rotina/lista_permissao.html', context)


@login_required
def form_permissao(request, user_id):
    """Gerencia nível de acesso, setor e as rotinas permitidas para o usuário."""
    usuario_obj = get_object_or_404(User, id=user_id)
    perfil, created = PerfilUsuario.objects.get_or_create(user=usuario_obj)
    todas_rotinas = Rotina.objects.all()

    if request.method == 'POST':
        # Atualiza nível e setor
        perfil.nivel_acesso = request.POST.get('nivel_acesso')
        perfil.setor = request.POST.get('setor')
        perfil.save()

        # Atualiza as rotinas permitidas (checkboxes)
        rotinas_ids = request.POST.getlist('rotinas')
        perfil.rotinas_permitidas.set(rotinas_ids)

        return redirect('lista_permissao')

    context = {
        'usuario_obj': usuario_obj,
        'perfil': perfil,
        'todas_rotinas': todas_rotinas,
    }
    return render(request, 'core/permissao_rotina/form_permissao.html', context)