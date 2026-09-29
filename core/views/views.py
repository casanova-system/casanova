import json
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from ..models import Obra, PerfilUsuario


def login_view(request):
    if request.method == "POST":
        usuario = request.POST.get("username")
        senha = request.POST.get("password")
        user = authenticate(request, username=usuario, password=senha)
        if user is not None:
            login(request, user)
            return redirect("menu_principal")
        else:
            return render(
                request,
                "core/login.html",
                {
                    "erro": "Usuário ou senha inválidos.",
                    "username": usuario,
                },
            )
    return render(request, "core/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required(login_url='login')
def menu_principal(request):
    return render(request, "core/menu.html")


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
    return render(request, "core/rotinas.html")


# ADICIONADO DE VOLTA: View genérica da página de gráficos do menu
@login_required(login_url='login')
def graficos_view(request):
    return render(request, "core/graficos.html")


@login_required(login_url='relatorio_fretes_mes')
def relatorios_view(request):
    return render(request, "core/relatorios.html")


@login_required(login_url='login')
def relatorio_fretes_mes(request):
    """
    View adicionada para atender a rota de relatório de fretes do mês,
    exibindo a página correspondente sem quebrar a estrutura existente.
    """
    return render(request, "core/relatorio_fretes_mes.html")