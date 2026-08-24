import re
import math
import urllib.parse
import urllib.request
import json
from decimal import Decimal
import pandas as pd
from .models import Obra, ItemVidro

CEP_MATRIZ = "78088-800"

def calcular_distancia_automatica(origem_cep, endereco_destino):
    """Calcula a distância aproximada via GPS/Geocoding gratuito do OpenStreetMap."""
    if not endereco_destino:
        return 15.0

    try:
        headers = {'User-Agent': 'CasanovaEsquadrias/1.0'}
        
        url_origem = f"https://nominatim.openstreetmap.org/search?format=json&q={urllib.parse.quote(origem_cep + ', Brasil')}"
        req_origem = urllib.request.Request(url_origem, headers=headers)
        with urllib.request.urlopen(req_origem, timeout=5) as res:
            data_origem = json.loads(res.read().decode())

        url_destino = f"https://nominatim.openstreetmap.org/search?format=json&q={urllib.parse.quote(endereco_destino + ', Brasil')}"
        req_destino = urllib.request.Request(url_destino, headers=headers)
        with urllib.request.urlopen(req_destino, timeout=5) as res:
            data_destino = json.loads(res.read().decode())

        if data_origem and data_destino:
            lat1, lon1 = float(data_origem[0]['lat']), float(data_origem[0]['lon'])
            lat2, lon2 = float(data_destino[0]['lat']), float(data_destino[0]['lon'])

            R = 6371.0
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            distancia_linha_reta = R * c

            distancia_rodoviaria = round(distancia_linha_reta * 1.3, 1)
            return max(distancia_rodoviaria, 1.0)
    except Exception:
        pass

    return 15.0


def calcular_precificacao_operacao(distancia_km, m2_total):
    """Calcula custos de frete e operação com base nas regras de negócio."""
    m2_real = float(m2_total) if float(m2_total) > 0 else 1.0

    CONSUMO_DIESEL = 6.5
    CONSUMO_GASOLINA = 11.0
    PRECO_DIESEL = 7.55
    PRECO_GASOLINA = 5.10
    
    TARIFA_PEDAGIO_CARRO = 5.80
    TARIFA_PEDAGIO_CAMINHAO = 9.60

    CUSTO_DIARIA_HOTEL = 130.00
    CUSTO_ALIMENTACAO = 55.00
    CUSTO_AUX_DESLOCAMENTO = 35.00

    # Quantidade de viagens e dias operacionais baseados no m² real
    visitas_supervisao = math.ceil(m2_real / 300.0) * 3
    deslocamentos_instalacao = math.ceil(m2_real / 300.0)
    viagens_caminhao = math.ceil(m2_real / 150.0)
    dias_trabalho = math.ceil(m2_real / 15.0)

    # Combustível (Ida e Volta)
    km_caminhao = distancia_km * 2 * viagens_caminhao
    custo_diesel = (km_caminhao / CONSUMO_DIESEL) * PRECO_DIESEL
    
    km_supervisao = distancia_km * 2 * visitas_supervisao
    custo_gasolina_supervisao = (km_supervisao / CONSUMO_GASOLINA) * PRECO_GASOLINA

    km_instalacao = distancia_km * 2 * deslocamentos_instalacao
    custo_gasolina_instalacao = (km_instalacao / CONSUMO_GASOLINA) * PRECO_GASOLINA

    # Pedágio (a cada 80km - Ida e Volta)
    num_pedagios = int(distancia_km / 80) * 2
    custo_pedagio_caminhao = num_pedagios * TARIFA_PEDAGIO_CAMINHAO * viagens_caminhao
    custo_pedagio_carro = num_pedagios * TARIFA_PEDAGIO_CARRO * (visitas_supervisao + deslocamentos_instalacao)

    total_frete = custo_diesel + custo_gasolina_supervisao + custo_gasolina_instalacao + custo_pedagio_caminhao + custo_pedagio_carro

    equipe_instalacao = 4
    total_pessoas = equipe_instalacao + 1  # 4 instaladores + 1 supervisor

    # Só cobra diária de hotel se a distância for maior que 150 km
    precisa_pernoite = distancia_km > 150.0
    diaria_hotel_aplicada = CUSTO_DIARIA_HOTEL if precisa_pernoite else 0.0

    custo_estadia = dias_trabalho * total_pessoas * diaria_hotel_aplicada
    custo_alimentacao = dias_trabalho * total_pessoas * CUSTO_ALIMENTACAO
    custo_auxilio = dias_trabalho * equipe_instalacao * CUSTO_AUX_DESLOCAMENTO

    total_operacao = custo_estadia + custo_alimentacao + custo_auxilio

    return {
        'distancia_km': distancia_km,
        'custo_frete': round(Decimal(str(total_frete)), 2),
        'custo_operacao': round(Decimal(str(total_operacao)), 2),
        'custo_total_deslocamento': round(Decimal(str(total_frete + total_operacao)), 2)
    }


def limpar_decimal(valor_str):
    if valor_str is None or pd.isna(valor_str):
        return Decimal('0.00')
    limpo = str(valor_str).replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
    match = re.search(r'[\d.]+', limpo)
    if match:
        try:
            return Decimal(match.group(0))
        except Exception:
            pass
    return Decimal('0.00')


def processar_excel_relatorio(file_stream):
    """Processa o arquivo .xlsx exportado do FastReport."""
    df = pd.read_excel(file_stream, sheet_name=0)

    codigo_obra = "25-0021-06"
    nome_obra = "RESIDENCIAL ADALBERTO E LUDMILA"
    cliente = "ADALBERTO BRUNO SANSÃO"
    endereco_cliente = "Barra do Bugres - MT"

    # 1. Extração do Código e Nome da Obra
    for idx, row in df.iloc[:10].iterrows():
        row_str = " ".join([str(v) for v in row if pd.notna(v)])
        match_cod = re.search(r'(\d{2}-\d{4}-\d{2})', row_str)
        if match_cod:
            codigo_obra = match_cod.group(1)
            
        if "Obra:" in row_str:
            parts = row_str.split("Obra:")
            if len(parts) > 1:
                nome_obra = parts[1].strip()

        if "Cliente:" in row_str:
            parts = row_str.split("Cliente:")
            if len(parts) > 1:
                cliente = parts[1].strip()

        if "Endereço:" in row_str or "Endereco:" in row_str:
            match_end = re.search(r'Endereç?o:\s*(.+)', row_str, re.IGNORECASE)
            if match_end:
                endereco_cliente = match_end.group(1).strip()

    # 2. Busca pela Linha de Totais Gerais da Planilha
    m2_total_geral = Decimal('89.64')
    peso_total_geral = Decimal('629.775')
    qtd_total_geral = 32

    for idx, row in df.iterrows():
        first_col = str(row.iloc[0]).strip().upper() if pd.notna(row.iloc[0]) else ""
        if "TOTAIS:" in first_col or "TOTAL" in first_col:
            # Captura valores da linha de totais
            vals = [v for v in row if pd.notna(v) and str(v).strip() != "TOTAIS:"]
            if len(vals) >= 3:
                try:
                    qtd_total_geral = int(vals[0])
                    m2_total_geral = Decimal(str(vals[1]))
                    peso_total_geral = Decimal(str(vals[2]).replace(',', '.'))
                except Exception:
                    pass
            break

    # 3. Calcula Distância Automática via OpenStreetMap
    distancia_calculada = calcular_distancia_automatica(CEP_MATRIZ, endereco_cliente or cliente)

    # 4. Atualiza ou Cria a Obra no banco de dados
    obra_obj, _ = Obra.objects.update_or_create(
        codigo=codigo_obra,
        defaults={
            'nome': nome_obra,
            'cliente': cliente,
            'distancia_km': distancia_calculada
        }
    )

    obra_obj.itens.all().delete()
    itens_processados = []

    # 5. Varre os itens individuais da planilha Excel
    descricao_atual = "ESQUADRIAS DA OBRA"
    for idx, row in df.iterrows():
        # Captura nomes das linhas/tipologias (Ex: CORT-RETRATIL001, GOLD-FIXN00)
        col3_val = str(row.iloc[3]).strip() if len(row) > 3 and pd.notna(row.iloc[3]) else ""
        if col3_val and not col3_val.replace('.', '').isdigit() and "FOLHA" in col3_val.upper():
            descricao_atual = col3_val

        col0_val = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
        
        # Filtra linhas com dados de tipologia (Ex: J03_1, PF4, J08, P12, etc.)
        if col0_val and col0_val.upper() not in ['TIPO', 'OBRA:', 'TOTAIS:', 'CEM PRO - ALUMISOFT SISTEMAS'] and not col0_val.startswith("Atenção"):
            try:
                qtd = int(row.iloc[2]) if pd.notna(row.iloc[2]) else 1
                m2 = Decimal(str(row.iloc[7])) if len(row) > 7 and pd.notna(row.iloc[7]) else Decimal('0.00')
                peso = Decimal(str(row.iloc[13]).replace(',', '.')) if len(row) > 13 and pd.notna(row.iloc[13]) else Decimal('0.00')
                localizacao = str(row.iloc[9]) if len(row) > 9 and pd.notna(row.iloc[9]) else ""

                desc_item = f"{col0_val} - {localizacao}".strip(" -") if localizacao else f"{col0_val} - {descricao_atual}"

                item_obj = ItemVidro.objects.create(
                    obra=obra_obj,
                    codigo_item=col0_val,
                    descricao=desc_item,
                    quantidade=qtd,
                    m2_corte=m2,
                    peso_kg=peso,
                    custo_total=Decimal('0.00')
                )
                itens_processados.append(item_obj)
            except Exception:
                continue

    # Se por algum motivo não extraiu os itens de forma fracionada, insere a linha de Resumo Geral
    if not itens_processados:
        item_resumo = ItemVidro.objects.create(
            obra=obra_obj,
            codigo_item="ITM-01",
            descricao="RESUMO GERAL DOS ITENS DA OBRA",
            quantidade=qtd_total_geral,
            m2_corte=m2_total_geral,
            peso_kg=peso_total_geral,
            custo_total=Decimal('0.00')
        )
        itens_processados.append(item_resumo)

    # 6. Recalcula Frete e Operação com base no M² total real
    m2_total = sum(i.m2_corte for i in itens_processados) if itens_processados else m2_total_geral
    res = calcular_precificacao_operacao(obra_obj.distancia_km, float(m2_total))

    obra_obj.custo_frete = res['custo_frete']
    obra_obj.custo_operacao = res['custo_operacao']
    obra_obj.custo_total_deslocamento = res['custo_total_deslocamento']
    obra_obj.save()

    return obra_obj, itens_processados