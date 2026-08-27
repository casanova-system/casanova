from decimal import Decimal
import math
import os
import shutil
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User  # <-- Importação necessária para o admin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from .models import ItemVidro, Obra
from .services import calcular_precificacao_operacao, processar_excel_relatorio


def login_view(request):
    if request.method == "POST":
        usuario = request.POST.get("username")
        senha = request.POST.get("password")
        user = authenticate(request, username=usuario, password=senha)
        if user is not None:
            login(request, user)
            return redirect("menu_principal")
        else:
            return render(request, "core/login.html", {"erro": "Usuário ou senha inválidos!"})
    return render(request, "core/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required(login_url='login')
def menu_principal(request):
    return render(request, "core/menu.html")


@login_required(login_url='login')
def lista_obras(request):
    obras = Obra.objects.all().order_by("-id")
    return render(request, "core/index.html", {"obras": obras})


@login_required(login_url='login')
def upload_pdf(request):
    if request.method == "POST" and request.FILES.get("excel_file"):
        excel_file = request.FILES["excel_file"]
        try:
            obra, itens = processar_excel_relatorio(excel_file)
            
            request.session['temp_obra'] = {
                'codigo': obra.codigo,
                'nome': obra.nome,
                'cliente': obra.cliente,
                'total_pecas': obra.total_pecas,
                'm2_total': str(obra.m2_total),
                'peso_total': str(obra.peso_total),
                'distancia_km': 0.0,
                'custo_frete': '0.00',
                'custo_operacao': '0.00',
                'custo_total_deslocamento': '0.00',
            }
            request.session['temp_itens'] = [
                {
                    'codigo_item': i.codigo_item,
                    'descricao': i.descricao,
                    'quantidade': i.quantidade,
                    'm2_corte': str(i.m2_corte),
                    'peso_kg': str(i.peso_kg),
                } for i in itens
            ]
            return redirect("detalhe_obra_temp")
        except Exception as e:
            messages.error(request, str(e))
            return redirect("upload_pdf")

    return render(request, "core/upload.html")


@login_required(login_url='login')
def detalhe_obra_temp(request):
    temp_obra_data = request.session.get('temp_obra')
    temp_itens_data = request.session.get('temp_itens')

    if not temp_obra_data:
        return redirect("upload_pdf")

    if request.method == "POST" and request.POST.get("acao") == "salvar":
        try:
            disco = shutil.disk_usage("C:\\" if os.name == "nt" else "/")
            espaco_livre_mb = disco.free / (1024 * 1024)
            if espaco_livre_mb < 50:
                messages.error(request, "ERRO_ESPACO_INSUFICIENTE")
                return redirect("detalhe_obra_temp")
        except Exception:
            pass

        dist_str = request.POST.get("distancia_km", str(temp_obra_data['distancia_km']))
        try:
            dist_km = float(dist_str.replace(",", "."))
        except ValueError:
            dist_km = float(temp_obra_data['distancia_km'])

        res = calcular_precificacao_operacao(dist_km, float(temp_obra_data['m2_total']))

        obra = Obra(
            codigo=temp_obra_data['codigo'],
            nome=temp_obra_data['nome'],
            cliente=temp_obra_data['cliente'],
            total_pecas=temp_obra_data['total_pecas'],
            m2_total=Decimal(temp_obra_data['m2_total']),
            peso_total=Decimal(temp_obra_data['peso_total']),
            distancia_km=dist_km,
            custo_frete=Decimal(str(res["custo_frete"])),
            custo_operacao=Decimal(str(res["custo_operacao"])),
            custo_total_deslocamento=Decimal(str(res["custo_total_deslocamento"])),
        )
        obra.save()
        
        for i_data in temp_itens_data:
            item = ItemVidro(
                obra=obra,
                codigo_item=i_data['codigo_item'],
                descricao=i_data['descricao'],
                quantidade=i_data['quantidade'],
                m2_corte=Decimal(i_data['m2_corte']),
                peso_kg=Decimal(i_data['peso_kg']),
            )
            item.save()
        
        if 'temp_obra' in request.session:
            del request.session['temp_obra']
        if 'temp_itens' in request.session:
            del request.session['temp_itens']
            
        messages.success(request, "Obra salva com sucesso!")
        return redirect("lista_obras")

    dist_str = request.GET.get("distancia_km", str(temp_obra_data['distancia_km']))
    try:
        dist_km = float(dist_str.replace(",", "."))
    except ValueError:
        dist_km = float(temp_obra_data['distancia_km'])

    res = calcular_precificacao_operacao(dist_km, float(temp_obra_data['m2_total']))

    obra = Obra(
        codigo=temp_obra_data['codigo'],
        nome=temp_obra_data['nome'],
        cliente=temp_obra_data['cliente'],
        total_pecas=temp_obra_data['total_pecas'],
        m2_total=Decimal(temp_obra_data['m2_total']),
        peso_total=Decimal(temp_obra_data['peso_total']),
        distancia_km=dist_km,
        custo_frete=Decimal(str(res["custo_frete"])),
        custo_operacao=Decimal(str(res["custo_operacao"])),
        custo_total_deslocamento=Decimal(str(res["custo_total_deslocamento"])),
    )
    
    itens = [
        ItemVidro(
            codigo_item=i['codigo_item'],
            descricao=i['descricao'],
            quantidade=i['quantidade'],
            m2_corte=Decimal(i['m2_corte']),
            peso_kg=Decimal(i['peso_kg']),
        ) for i in temp_itens_data
    ]

    total_pecas = obra.total_pecas
    m2_corte_total = obra.m2_total
    peso_total = obra.peso_total
    custo_total_materiais = Decimal("0.00")
    custo_geral_obra = custo_total_materiais + obra.custo_total_deslocamento

    m2_real = float(m2_corte_total) if float(m2_corte_total) > 0 else 1.0
    dias_trabalho = math.ceil(m2_real / 15.0)

    parametros_calculo = {
        "media_hospedagem": 120.00,
        "media_gasolina": 5.89,
        "media_diesel": 6.19,
        "media_alimentacao": 50.00,
        "media_locomocao": 30.00,
    }

    context = {
        "obra": obra,
        "itens": itens,
        "total_pecas": total_pecas,
        "m2_corte_total": m2_corte_total,
        "peso_total": peso_total,
        "custo_total_materiais": custo_total_materiais,
        "custo_geral_obra": custo_geral_obra,
        "dias_trabalho": dias_trabalho,
        "parametros": parametros_calculo,
        "is_temp": True,
        "is_read_only": False,
        "is_edit": False,
    }
    return render(request, "core/detalhe.html", context)


@login_required(login_url='login')
def detalhe_obra(request, pk):
    obra = get_object_or_404(Obra, pk=pk)
    itens = obra.itens.all()

    total_pecas = sum(item.quantidade for item in itens)
    m2_corte_total = sum(item.m2_corte for item in itens)
    peso_total = sum(item.peso_kg for item in itens)
    custo_total_materiais = sum(item.custo_total for item in itens)

    custo_geral_obra = custo_total_materiais + obra.custo_total_deslocamento

    m2_real = float(m2_corte_total) if float(m2_corte_total) > 0 else 1.0
    dias_trabalho = math.ceil(m2_real / 15.0)

    parametros_calculo = {
        "media_hospedagem": 120.00,
        "media_gasolina": 5.89,
        "media_diesel": 6.19,
        "media_alimentacao": 50.00,
        "media_locomocao": 30.00,
    }

    context = {
        "obra": obra,
        "itens": itens,
        "total_pecas": total_pecas,
        "m2_corte_total": m2_corte_total,
        "peso_total": peso_total,
        "custo_total_materiais": custo_total_materiais,
        "custo_geral_obra": custo_geral_obra,
        "dias_trabalho": dias_trabalho,
        "parametros": parametros_calculo,
        "is_temp": False,
        "is_read_only": True,
        "is_edit": False,
    }
    return render(request, "core/detalhe.html", context)


@login_required(login_url='login')
def editar_obra(request, pk):
    obra = get_object_or_404(Obra, pk=pk)
    itens = obra.itens.all()

    total_pecas = sum(item.quantidade for item in itens)
    m2_corte_total = sum(item.m2_corte for item in itens)
    peso_total = sum(item.peso_kg for item in itens)
    custo_total_materiais = sum(item.custo_total for item in itens)

    if request.method == "POST" and request.POST.get("acao") == "salvar":
        try:
            disco = shutil.disk_usage("C:\\" if os.name == "nt" else "/")
            espaco_livre_mb = disco.free / (1024 * 1024)
            if espaco_livre_mb < 50:
                messages.error(request, "ERRO_ESPACO_INSUFICIENTE")
                return redirect("editar_obra", pk=obra.pk)
        except Exception:
            pass

        dist_str = request.POST.get("distancia_km", str(obra.distancia_km))
        try:
            dist_km = float(dist_str.replace(",", "."))
        except ValueError:
            dist_km = float(obra.distancia_km)

        res = calcular_precificacao_operacao(dist_km, float(m2_corte_total))

        obra.distancia_km = dist_km
        obra.custo_frete = Decimal(str(res["custo_frete"]))
        obra.custo_operacao = Decimal(str(res["custo_operacao"]))
        obra.custo_total_deslocamento = Decimal(str(res["custo_total_deslocamento"]))
        obra.save()

        messages.success(request, "Obra atualizada com sucesso!")
        return redirect("lista_obras")

    dist_str = request.GET.get("distancia_km", str(obra.distancia_km))
    try:
        dist_km = float(dist_str.replace(",", "."))
    except ValueError:
        dist_km = float(obra.distancia_km)

    res = calcular_precificacao_operacao(dist_km, float(m2_corte_total))

    obra.distancia_km = dist_km
    obra.custo_frete = Decimal(str(res["custo_frete"]))
    obra.custo_operacao = Decimal(str(res["custo_operacao"]))
    obra.custo_total_deslocamento = Decimal(str(res["custo_total_deslocamento"]))

    custo_geral_obra = custo_total_materiais + obra.custo_total_deslocamento

    m2_real = float(m2_corte_total) if float(m2_corte_total) > 0 else 1.0
    dias_trabalho = math.ceil(m2_real / 15.0)

    parametros_calculo = {
        "media_hospedagem": 120.00,
        "media_gasolina": 5.89,
        "media_diesel": 6.19,
        "media_alimentacao": 50.00,
        "media_locomocao": 30.00,
    }

    context = {
        "obra": obra,
        "itens": itens,
        "total_pecas": total_pecas,
        "m2_corte_total": m2_corte_total,
        "peso_total": peso_total,
        "custo_total_materiais": custo_total_materiais,
        "custo_geral_obra": custo_geral_obra,
        "dias_trabalho": dias_trabalho,
        "parametros": parametros_calculo,
        "is_temp": False,
        "is_read_only": False,
        "is_edit": True,
    }
    return render(request, "core/detalhe.html", context)


@login_required(login_url='login')
def excluir_obra(request, pk):
    obra = get_object_or_404(Obra, pk=pk)
    obra.delete()
    messages.success(request, "Registro excluído com sucesso!")
    return redirect("lista_obras")


@login_required(login_url='login')
def rotinas_view(request):
    return render(request, "core/rotinas.html")


@login_required(login_url='login')
def graficos_view(request):
    return render(request, "core/graficos.html")


@login_required(login_url='login')
def relatorios_view(request):
    return render(request, "core/relatorios.html")


# Criação automática de um admin padrão caso não exista nenhum
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('administrador', 'guilhermekauamt01@gmail.com', '@4C0f3r@')