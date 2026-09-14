from decimal import Decimal
import json
import math
import os
import shutil
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from ..models import ItemVidro, Obra, Veiculo, Custo
from ..services import processar_excel_relatorio

def obter_parametros_custo_do_banco(request):
    tipos_desejados = {
        "media_hospedagem": ["hospedagem", "hotel", "HOSPEDAGEM", "Hospedagem", "Hotel", "HOTEL"],
        "media_gasolina": ["gasolina", "GASOLINA", "Gasolina", "gASOLINA", "gasosa", "GASOSA"],
        "media_diesel": ["diesel", "DIESEL", "Diesel", "díesel", "DÍESEL", "Díesel"],
        "media_alimentacao": ["alimentacao", "alimentação", "ALIMENTAÇÃO", "ALIMENTACAO", "Alimentação", "Alimentacao", "almoço", "ALMOÇO", "Almoço", "almoco", "ALMOCO", "Almoco", "refeicao", "REFEICAO", "Refeicao", "refeição", "REFEIÇÃO", "Refeição"],
        "media_locomocao": ["locomocao", "locomoção", "LOCOMOÇÃO", "LOCOMOCAO", "Locomocao", "Locomoção", "TRANSPORTE", "Transporte", "Uber", "UBER", "TAXI", "TÁXI", "Táxi", "Taxi", "táxi", "transporte", "uber", "taxi"],
        "tarifa_pedagio_carro": ["pedagio carro", "pedágio carro", "Tarifa Pedágio Carro"],
        "tarifa_pedagio_caminhao": ["pedagio caminhao", "pedágio caminhão", "Tarifa Pedágio Caminhão"],
        "consumo_gasolina": ["consumo gasolina", "Consumo Gasolina"],
        "num_colab_supervisao": ["número colaboradores supervisão", "numero colaboradores supervisao", "Sup. Técnica"],
        "num_colab_instalacao": ["número colaboradores instalação", "numero colaboradores instalacao", "Instalação"],
    }
    
    parametros = {}
    faltando = []

    eh_tela_de_detalhe = any(termo in request.path for termo in ["detalhe", "editar", "obra"])

    for chave, termos in tipos_desejados.items():
        custo_obj = None
        for termo in termos:
            custo_obj = Custo.objects.filter(
                Q(tipo__icontains=termo) | Q(descricao__icontains=termo)
            ).first()
            if custo_obj:
                break
        
        if custo_obj:
            parametros[chave] = float(custo_obj.valor)
        else:
            faltando.append(chave)
            parametros[chave] = 0.0

    # Definir valores padrão caso algum parâmetro opcional não seja encontrado
    parametros.setdefault("tarifa_pedagio_carro", 5.80)
    parametros.setdefault("tarifa_pedagio_caminhao", 9.60)
    parametros.setdefault("consumo_gasolina", 11.0)
    parametros.setdefault("media_diesel", 7.55)
    parametros.setdefault("media_gasolina", 5.10)
    parametros.setdefault("media_hospedagem", 130.0)
    parametros.setdefault("media_alimentacao", 55.0)
    parametros.setdefault("media_locomocao", 35.0) # Auxílio Deslocamento
    parametros.setdefault("num_colab_supervisao", 1.0)
    parametros.setdefault("num_colab_instalacao", 4.0)

    if faltando and eh_tela_de_detalhe:
        parametros["_bloqueado"] = True
        parametros["_faltando_str"] = ", ".join(faltando)
    else:
        parametros["_bloqueado"] = False
        parametros["_faltando_str"] = ""

    return parametros


def calcular_custos_detalhados(dist_km, m2_total, parametros):
    """
    Replica exatamente o cálculo da planilha de Excel:
    Frente A (Frete / Combustíveis / Pedágios)
    Frente B (Operação / Estadias / Alimentação / Auxílios)
    """
    # 1. Parâmetros base da planilha
    consumo_diesel = 6.5
    consumo_gasolina = parametros.get("consumo_gasolina", 11.0)
    
    preco_diesel = parametros.get("media_diesel", 7.55)
    preco_gasolina = parametros.get("media_gasolina", 5.10)
    
    tarifa_pedagio_caminhao = parametros.get("tarifa_pedagio_caminhao", 9.60)
    tarifa_pedagio_carro = parametros.get("tarifa_pedagio_carro", 5.80)
    
    custo_hospedagem = parametros.get("media_hospedagem", 130.0)
    custo_alimentacao = parametros.get("media_alimentacao", 55.0)
    custo_auxilio = parametros.get("media_locomocao", 35.0)
    
    colab_supervisao = int(parametros.get("num_colab_supervisao", 1))
    colab_instalacao = int(parametros.get("num_colab_instalacao", 4))
    motorista_auxiliar = 2 # Padrão caminhão (motorista + auxiliar)

    # Critérios proporcionais baseados na metragem quadrada (M2)
    # Considera-se 1 visita/deslocamento a cada 300 m² (mínimo 1)
    num_visitas_supervisao = max(1, math.ceil(m2_total / 300.0)) * 3 # 3 visitas base ou proporcional
    num_desloc_instalacao = max(1, math.ceil(m2_total / 300.0))
    num_entregas_caminhao = max(1, math.ceil(m2_total / 150.0))
    
    # Dias trabalhados (produção média diária de 15m² para equipe de 4)
    m2_real = float(m2_total) if float(m2_total) > 0 else 1.0
    dias_trabalho = max(1, math.ceil(m2_real / 15.0))

    # Distâncias totais (Ida e Volta = * 2)
    distancia_caminhao = dist_km * 2 * num_entregas_caminhao
    distancia_supervisao = dist_km * 2 * num_visitas_supervisao
    distancia_instalacao = dist_km * 2 * num_desloc_instalacao

    # Pedágios (8 praças padrão de referência ou proporcional à distância)
    pracas_pedagio = max(1, round(dist_km / 80.0)) * 2 # Ida e volta

    # --- RESULTADOS - CUSTOS (FRENTE A) ---
    combustivel_caminhao = (distancia_caminhao / consumo_diesel) * preco_diesel
    combustivel_supervisao = (distancia_supervisao / consumo_gasolina) * preco_gasolina
    combustivel_instalacao = (distancia_instalacao / consumo_gasolina) * preco_gasolina
    
    pedagio_caminhao = pracas_pedagio * tarifa_pedagio_caminhao * num_entregas_caminhao
    pedagio_supervisao = pracas_pedagio * tarifa_pedagio_carro * num_visitas_supervisao
    pedagio_instalacao = pracas_pedagio * tarifa_pedagio_carro * num_desloc_instalacao

    total_frete_a = (
        combustivel_caminhao + combustivel_supervisao + combustivel_instalacao +
        pedagio_caminhao + pedagio_supervisao + pedagio_instalacao
    )

    # --- RESULTADOS - CUSTOS (FRENTE B - OPERAÇÃO) ---
    # Regra: Estadia, alimentação e deslocamento só ocorrem se a distância for maior que 200 km
    if dist_km > 200.0:
        dias_supervisao = num_visitas_supervisao * 2

        estadia_supervisao = custo_hospedagem * colab_supervisao * dias_supervisao
        estadia_caminhao = custo_hospedagem * motorista_auxiliar * num_entregas_caminhao
        estadia_instalacao = custo_hospedagem * colab_instalacao * dias_trabalho

        alimentacao_supervisao = custo_alimentacao * colab_supervisao * dias_supervisao
        alimentacao_caminhao = custo_alimentacao * motorista_auxiliar * num_entregas_caminhao
        alimentacao_instalacao = custo_alimentacao * colab_instalacao * dias_trabalho

        auxilio_instalacao = custo_auxilio * colab_instalacao * dias_trabalho
    else:
        estadia_supervisao = 0.0
        estadia_caminhao = 0.0
        estadia_instalacao = 0.0
        alimentacao_supervisao = 0.0
        alimentacao_caminhao = 0.0
        alimentacao_instalacao = 0.0
        auxilio_instalacao = 0.0

    total_operacao_b = (
        estadia_supervisao + estadia_caminhao + estadia_instalacao +
        alimentacao_supervisao + alimentacao_caminhao + alimentacao_instalacao +
        auxilio_instalacao
    )

    # --- LOGS DETALHADOS PARA APARECER NO TERMINAL DO DJANGO ---
    print("\n" + "="*50)
    print("--- [DEBUG PRECIFICAÇÃO E CUSTOS (FRETES.PY)] ---")
    print(f"Distância informada: {dist_km} km")
    print(f"Área Total (m²): {m2_real}")
    print(f"Dias de Trabalho calculados: {dias_trabalho}")
    print(f"Viagens de Caminhão: {num_entregas_caminhao}")
    print(f"Custo Diesel: R$ {combustivel_caminhao:.2f}")
    print(f"Custo Gasolina Supervisão: R$ {combustivel_supervisao:.2f}")
    print(f"Custo Gasolina Instalação: R$ {combustivel_instalacao:.2f}")
    print(f"Custo Pedágio Caminhão: R$ {pedagio_caminhao:.2f}")
    print(f"Custo Pedágio Carro: R$ {pedagio_supervisao + pedagio_instalacao:.2f}")
    print(f"-> TOTAL FRETE: R$ {total_frete_a:.2f}")
    print("-" * 30)
    print(f"Custo Estadia (Hotel): R$ {estadia_supervisao + estadia_caminhao + estadia_instalacao:.2f}")
    print(f"Custo Alimentação: R$ {alimentacao_supervisao + alimentacao_caminhao + alimentacao_instalacao:.2f}")
    print(f"Custo Auxílio Deslocamento: R$ {auxilio_instalacao:.2f}")
    print(f"-> TOTAL OPERAÇÃO: R$ {total_operacao_b:.2f}")
    print("="*50 + "\n")
    # -----------------------------------------------------------

    return {
        "custo_frete": round(total_frete_a, 2),
        "custo_operacao": round(total_operacao_b, 2),
        "custo_total_deslocamento": round(total_frete_a + total_operacao_b, 2),
        "dias_trabalho": dias_trabalho,
    }


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

    return render(request, "core/fretes/upload_frete.html")


@login_required(login_url='login')
def detalhe_obra_temp(request):
    temp_obra_data = request.session.get('temp_obra')
    temp_itens_data = request.session.get('temp_itens')

    if not temp_obra_data:
        return redirect("upload_pdf")

    calcular_cubagem_param = request.GET.get('calcular_cubagem') or request.POST.get('calcular_cubagem')
    faz_cubagem = True if calcular_cubagem_param == 'on' else False

    veiculos_cadastrados = Veiculo.objects.all()
    veiculo_id = request.GET.get('veiculo_id') or request.POST.get('veiculo_id')
    veiculo_selecionado = Veiculo.objects.filter(pk=veiculo_id).first() if veiculo_id else None

    m2_total_temp = float(temp_obra_data['m2_total'])
    if veiculo_selecionado and faz_cubagem:
        cubagem_calc = round(m2_total_temp * 0.06, 4)
    else:
        cubagem_calc = 0.0

    viagens_calc = 1
    if veiculo_selecionado and faz_cubagem and getattr(veiculo_selecionado, 'capacidade_volumetrica', None):
        cap_v = float(veiculo_selecionado.capacidade_volumetrica)
        if cap_v > 0 and cubagem_calc > 0:
            viagens_calc = max(1, math.ceil(cubagem_calc / cap_v))

    dist_str = request.GET.get("distancia_km") or request.POST.get("distancia_km")
    if not dist_str:
        dist_str = str(temp_obra_data['distancia_km'])
    try:
        dist_km = float(dist_str.replace(",", "."))
    except ValueError:
        dist_km = float(temp_obra_data['distancia_km'])

    desconto_str = request.GET.get('percentual_desconto') or request.POST.get('percentual_desconto')
    try:
        percentual_desconto = float(str(desconto_str).replace(',', '.')) if desconto_str else 0.0
    except ValueError:
        percentual_desconto = 0.0

    parametros_calculo = obter_parametros_custo_do_banco(request)

    if parametros_calculo.get("_bloqueado"):
        f_frete = 0.0
        f_operacao = 0.0
        f_total = 0.0
        dias_trabalho = 1
    else:
        custos_calculados = calcular_custos_detalhados(dist_km, m2_total_temp, parametros_calculo)
        
        f_frete_bruto = custos_calculados["custo_frete"]
        f_operacao_bruto = custos_calculados["custo_operacao"]
        dias_trabalho = custos_calculados["dias_trabalho"]
        
        f_frete = f_frete_bruto * (1 - (percentual_desconto / 100))
        f_operacao = f_operacao_bruto * (1 - (percentual_desconto / 100))
        f_total = f_frete + f_operacao

    if request.method == "POST" and request.POST.get("acao") == "salvar":
        if parametros_calculo.get("_bloqueado"):
            messages.error(request, "Não é possível salvar a obra com custos pendentes/zerados.")
            return redirect("detalhe_obra_temp")

        try:
            disco = shutil.disk_usage("C:\\" if os.name == "nt" else "/")
            espaco_livre_mb = disco.free / (1024 * 1024)
            if espaco_livre_mb < 50:
                messages.error(request, "ERRO_ESPACO_INSUFICIENTE")
                return redirect("detalhe_obra_temp")
        except Exception:
            pass

        obra = Obra(
            codigo=temp_obra_data['codigo'],
            nome=temp_obra_data['nome'],
            cliente=temp_obra_data['cliente'],
            total_pecas=temp_obra_data['total_pecas'],
            m2_total=Decimal(str(m2_total_temp)),
            peso_total=Decimal(temp_obra_data['peso_total']),
            distancia_km=dist_km,
            custo_frete=Decimal(str(f_frete)),
            custo_operacao=Decimal(str(f_operacao)),
            custo_total_deslocamento=Decimal(str(f_total)),
            percentual_desconto=Decimal(str(percentual_desconto)),
            usuario=request.user,
            veiculo=veiculo_selecionado,
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

    obra = Obra(
        codigo=temp_obra_data['codigo'],
        nome=temp_obra_data['nome'],
        cliente=temp_obra_data['cliente'],
        total_pecas=temp_obra_data['total_pecas'],
        m2_total=Decimal(str(m2_total_temp)),
        peso_total=Decimal(temp_obra_data['peso_total']),
        distancia_km=dist_km,
        custo_frete=Decimal(str(f_frete)),
        custo_operacao=Decimal(str(f_operacao)),
        custo_total_deslocamento=Decimal(str(f_total)),
        percentual_desconto=Decimal(str(percentual_desconto)),
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

    cubagem_total = cubagem_calc
    peso_cubado = round(cubagem_total * 300, 2)
    peso_real_val = float(peso_total)
    requer_escolha_peso = bool(veiculo_selecionado) and (peso_cubado > peso_real_val)
    viagens_necessarias = viagens_calc

    valor_diaria_operacional = (
        parametros_calculo.get("media_hospedagem", 0.0) + 
        parametros_calculo.get("media_alimentacao", 0.0)
    )

    tarifa_km_veiculo = float(veiculo_selecionado.custo_km) if veiculo_selecionado and hasattr(veiculo_selecionado, 'custo_km') and veiculo_selecionado.custo_km else 2.50

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
        "tarifa_km": tarifa_km_veiculo,
        "valor_diaria_operacional": valor_diaria_operacional,
        "distancia_km": dist_km,
        "calcular_cubagem": "on" if faz_cubagem else "off",
        "cubagem_total": cubagem_total,
        "peso_cubado": peso_cubado,
        "requer_escolha_peso": requer_escolha_peso,
        "veiculos_cadastrados": veiculos_cadastrados,
        "veiculo_selecionado": veiculo_selecionado,
        "viagens_necessarias": viagens_necessarias,
        "percentual_desconto": percentual_desconto,
        "is_temp": True,
        "is_read_only": False,
        "is_edit": False,
        "erro_custos_obrigatorios": parametros_calculo.get("_faltando_str") if parametros_calculo.get("_bloqueado") else None,
    }
    return render(request, "core/fretes/detalhe_frete.html", context)


@login_required(login_url='login')
def detalhe_obra(request, pk):
    obra = get_object_or_404(Obra, pk=pk)
    itens = obra.itens.all()

    total_pecas = sum(item.quantidade for item in itens)
    m2_corte_total = sum(item.m2_corte for item in itens)
    peso_total = sum(item.peso_kg for item in itens)
    custo_total_materiais = sum(item.custo_total for item in itens)

    calcular_cubagem_param = request.GET.get('calcular_cubagem')
    faz_cubagem = True if calcular_cubagem_param == 'on' else getattr(obra, 'calcular_cubagem', False)

    veiculos_cadastrados = Veiculo.objects.all()
    veiculo_selecionado = getattr(obra, 'veiculo', None)
    
    if veiculo_selecionado and faz_cubagem:
        cubagem_total = round(float(m2_corte_total) * 0.06, 4)
    else:
        cubagem_total = 0.0

    peso_cubado = round(cubagem_total * 300, 2)
    peso_real_val = float(peso_total)
    requer_escolha_peso = bool(veiculo_selecionado) and (peso_cubado > peso_real_val)

    viagens_necessarias = 1
    if veiculo_selecionado and faz_cubagem and getattr(veiculo_selecionado, 'capacidade_volumetrica', None):
        cap = float(veiculo_selecionado.capacidade_volumetrica)
        if cap > 0 and cubagem_total > 0:
            viagens_necessarias = max(1, math.ceil(cubagem_total / cap))

    parametros_calculo = obter_parametros_custo_do_banco(request)

    if parametros_calculo.get("_bloqueado"):
        obra.custo_frete = Decimal("0.00")
        obra.custo_operacao = Decimal("0.00")
        obra.custo_total_deslocamento = Decimal("0.00")
        dias_trabalho = 1
    else:
        custos_calculados = calcular_custos_detalhados(float(obra.distancia_km), float(m2_corte_total), parametros_calculo)
        dias_trabalho = custos_calculados["dias_trabalho"]

    custo_geral_obra = custo_total_materiais + obra.custo_total_deslocamento

    valor_diaria_operacional = (
        parametros_calculo.get("media_hospedagem", 0.0) + 
        parametros_calculo.get("media_alimentacao", 0.0)
    )

    tarifa_km_veiculo = float(veiculo_selecionado.custo_km) if veiculo_selecionado and hasattr(veiculo_selecionado, 'custo_km') and veiculo_selecionado.custo_km else 2.50

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
        "tarifa_km": tarifa_km_veiculo,
        "valor_diaria_operacional": valor_diaria_operacional,
        "distancia_km": float(obra.distancia_km),
        "calcular_cubagem": "on" if faz_cubagem else "off",
        "cubagem_total": cubagem_total,
        "peso_cubado": peso_cubado,
        "requer_escolha_peso": requer_escolha_peso,
        "veiculos_cadastrados": veiculos_cadastrados,
        "veiculo_selecionado": veiculo_selecionado,
        "viagens_necessarias": viagens_necessarias,
        "percentual_desconto": float(obra.percentual_desconto) if hasattr(obra, 'percentual_desconto') else 0.0,
        "is_temp": False,
        "is_read_only": True,
        "is_edit": False,
        "erro_custos_obrigatorios": parametros_calculo.get("_faltando_str") if parametros_calculo.get("_bloqueado") else None,
    }
    return render(request, "core/fretes/detalhe_frete.html", context)


@login_required(login_url='login')
def editar_obra(request, pk):
    obra = get_object_or_404(Obra, pk=pk)
    itens = obra.itens.all()

    total_pecas = sum(item.quantidade for item in itens)
    m2_corte_total = sum(item.m2_corte for item in itens)
    peso_total = sum(item.peso_kg for item in itens)
    custo_total_materiais = sum(item.custo_total for item in itens)

    calcular_cubagem_param = request.GET.get('calcular_cubagem') or request.POST.get('calcular_cubagem')
    faz_cubagem = True if calcular_cubagem_param == 'on' else getattr(obra, 'calcular_cubagem', False)

    veiculos_cadastrados = Veiculo.objects.all()
    veiculo_id = request.GET.get('veiculo_id') or request.POST.get('veiculo_id')
    veiculo_selecionado = Veiculo.objects.filter(pk=veiculo_id).first() if veiculo_id else getattr(obra, 'veiculo', None)

    if veiculo_selecionado and faz_cubagem:
        cubagem_total_ed = round(float(m2_corte_total) * 0.06, 4)
    else:
        cubagem_total_ed = 0.0

    viagens_nec_ed = 1
    if veiculo_selecionado and faz_cubagem and getattr(veiculo_selecionado, 'capacidade_volumetrica', None):
        cap_v_ed = float(veiculo_selecionado.capacidade_volumetrica)
        if cap_v_ed > 0 and cubagem_total_ed > 0:
            viagens_nec_ed = max(1, math.ceil(cubagem_total_ed / cap_v_ed))

    dist_str = request.GET.get("distancia_km") or request.POST.get("distancia_km")
    if not dist_str:
        dist_str = str(obra.distancia_km)
    try:
        dist_km = float(dist_str.replace(",", "."))
    except ValueError:
        dist_km = float(obra.distancia_km)

    desconto_str = request.GET.get('percentual_desconto') or request.POST.get('percentual_desconto')
    try:
        percentual_desconto = float(str(desconto_str).replace(',', '.')) if desconto_str else float(obra.percentual_desconto)
    except ValueError:
        percentual_desconto = float(obra.percentual_desconto)

    parametros_calculo = obter_parametros_custo_do_banco(request)

    if parametros_calculo.get("_bloqueado"):
        f_frete = 0.0
        f_operacao = 0.0
        f_total = 0.0
        dias_trabalho = 1
    else:
        custos_calculados = calcular_custos_detalhados(dist_km, float(m2_corte_total), parametros_calculo)
        
        f_frete_bruto = custos_calculados["custo_frete"]
        f_operacao_bruto = custos_calculados["custo_operacao"]
        dias_trabalho = custos_calculados["dias_trabalho"]
        
        f_frete = f_frete_bruto * (1 - (percentual_desconto / 100))
        f_operacao = f_operacao_bruto * (1 - (percentual_desconto / 100))
        f_total = f_frete + f_operacao

    if request.method == "POST" and request.POST.get("acao") == "salvar":
        if parametros_calculo.get("_bloqueado"):
            messages.error(request, "Não é possível salvar a obra com custos pendentes/zerados.")
            return redirect("editar_obra", pk=obra.pk)

        try:
            disco = shutil.disk_usage("C:\\" if os.name == "nt" else "/")
            espaco_livre_mb = disco.free / (1024 * 1024)
            if espaco_livre_mb < 50:
                messages.error(request, "ERRO_ESPACO_INSUFICIENTE")
                return redirect("editar_obra", pk=obra.pk)
        except Exception:
            pass

        obra.distancia_km = dist_km
        obra.custo_frete = Decimal(str(f_frete))
        obra.custo_operacao = Decimal(str(f_operacao))
        obra.custo_total_deslocamento = Decimal(str(f_total))
        obra.percentual_desconto = Decimal(str(percentual_desconto))
        obra.usuario = request.user
        obra.veiculo = veiculo_selecionado if veiculo_selecionado else None
        obra.save()

        messages.success(request, "Obra atualizada com sucesso!")
        return redirect("lista_obras")

    obra.distancia_km = dist_km
    obra.custo_frete = Decimal(str(f_frete))
    obra.custo_operacao = Decimal(str(f_operacao))
    obra.custo_total_deslocamento = Decimal(str(f_total))
    obra.percentual_desconto = Decimal(str(percentual_desconto))

    custo_geral_obra = custo_total_materiais + obra.custo_total_deslocamento

    cubagem_total = cubagem_total_ed
    peso_cubado = round(cubagem_total * 300, 2)
    peso_real_val = float(peso_total)
    requer_escolha_peso = bool(veiculo_selecionado) and (peso_cubado > peso_real_val)
    viagens_necessarias = viagens_nec_ed

    valor_diaria_operacional = (
        parametros_calculo.get("media_hospedagem", 0.0) + 
        parametros_calculo.get("media_alimentacao", 0.0)
    )

    tarifa_km_veiculo = float(veiculo_selecionado.custo_km) if veiculo_selecionado and hasattr(veiculo_selecionado, 'custo_km') and veiculo_selecionado.custo_km else 2.50

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
        "tarifa_km": tarifa_km_veiculo,
        "valor_diaria_operacional": valor_diaria_operacional,
        "distancia_km": dist_km,
        "calcular_cubagem": "on" if faz_cubagem else "off",
        "cubagem_total": cubagem_total,
        "peso_cubado": peso_cubado,
        "requer_escolha_peso": requer_escolha_peso,
        "veiculos_cadastrados": veiculos_cadastrados,
        "veiculo_selecionado": veiculo_selecionado,
        "viagens_necessarias": viagens_necessarias,
        "percentual_desconto": percentual_desconto,
        "is_temp": False,
        "is_read_only": False,
        "is_edit": True,
        "erro_custos_obrigatorios": parametros_calculo.get("_faltando_str") if parametros_calculo.get("_bloqueado") else None,
    }
    return render(request, "core/fretes/detalhe_frete.html", context)


@login_required(login_url='login')
def excluir_obra(request, pk):
    obra = get_object_or_404(Obra, pk=pk)
    obra.delete()
    messages.success(request, "Registro excluído com sucesso!")
    return redirect("lista_obras")


@login_required(login_url='login')
def lista_obras(request):
    obras = Obra.objects.filter(usuario=request.user) if hasattr(Obra, 'usuario') else Obra.objects.all()
    context = {
        "obras": obras,
    }
    return render(request, "core/fretes/lista_frete.html", context)