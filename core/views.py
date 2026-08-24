from decimal import Decimal
import math
from django.shortcuts import get_object_or_404, redirect, render
from .models import Obra
from .services import calcular_precificacao_operacao, processar_excel_relatorio


def lista_obras(request):
    obras = Obra.objects.all().order_by("-id")
    return render(request, "core/index.html", {"obras": obras})


def upload_pdf(request):
    if request.method == "POST" and request.FILES.get("excel_file"):
        excel_file = request.FILES["excel_file"]

        obra, _ = processar_excel_relatorio(excel_file)
        return redirect("detalhe_obra", pk=obra.pk)

    return render(request, "core/upload.html")


def detalhe_obra(request, pk):
    obra = get_object_or_404(Obra, pk=pk)
    itens = obra.itens.all()

    total_pecas = sum(item.quantidade for item in itens)
    m2_corte_total = sum(item.m2_corte for item in itens)
    peso_total = sum(item.peso_kg for item in itens)
    custo_total_materiais = sum(item.custo_total for item in itens)

    if request.method == "POST":
        dist_str = request.POST.get("distancia_km", str(obra.distancia_km))
        try:
            dist_km = float(dist_str.replace(",", "."))
        except ValueError:
            dist_km = float(obra.distancia_km)

        res = calcular_precificacao_operacao(dist_km, float(m2_corte_total))

        obra.distancia_km = dist_km
        obra.custo_frete = Decimal(str(res["custo_frete"]))
        obra.custo_operacao = Decimal(str(res["custo_operacao"]))
        obra.custo_total_deslocamento = Decimal(
            str(res["custo_total_deslocamento"])
        )
        obra.save()

        return redirect("detalhe_obra", pk=obra.pk)

    custo_geral_obra = custo_total_materiais + obra.custo_total_deslocamento

    # Cálculo dos dias estimados de obra (15 m² por dia)
    m2_real = float(m2_corte_total) if float(m2_corte_total) > 0 else 1.0
    dias_trabalho = math.ceil(m2_real / 15.0)

    # Parâmetros de cálculo base utilizados nas variáveis operacionais
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
    }
    return render(request, "core/detalhe.html", context)