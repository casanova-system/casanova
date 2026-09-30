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
    return redirect("menu_principal")


# ADICIONADO DE VOLTA: View genérica da página de gráficos do menu
@login_required(login_url='login')
def graficos_view(request):
    return redirect("grafico_custo_frete")


@login_required(login_url='login')
def relatorios_view(request):
    return redirect("relatorio_fretes_mes")