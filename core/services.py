from decimal import Decimal
import json
import math
import re
import urllib.parse
import urllib.request
import pdfplumber
from .models import ItemVidro, Obra

CEP_MATRIZ = "78088-800"


def calcular_distancia_automatica(origem_cep, endereco_destino):
    """Calcula a distância aproximada via GPS/Geocoding gratuito do OpenStreetMap."""
    if not endereco_destino:
        return 15.0

    try:
        headers = {"User-Agent": "CasanovaEsquadrias/1.0"}

        url_origem = f"https://nominatim.openstreetmap.org/search?format=json&q={urllib.parse.quote(origem_cep + ', Brasil')}"
        req_origem = urllib.request.Request(url_origem, headers=headers)
        with urllib.request.urlopen(req_origem, timeout=5) as res:
            data_origem = json.loads(res.read().decode())

        url_destino = f"https://nominatim.openstreetmap.org/search?format=json&q={urllib.parse.quote(endereco_destino + ', Brasil')}"
        req_destino = urllib.request.Request(url_destino, headers=headers)
        with urllib.request.urlopen(req_destino, timeout=5) as res:
            data_destino = json.loads(res.read().decode())

        if data_origem and data_destino:
            lat1, lon1 = float(data_origem[0]["lat"]), float(data_origem[0]["lon"])
            lat2, lon2 = float(data_destino[0]["lat"]), float(data_destino[0]["lon"])

            R = 6371.0
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = (
                math.sin(dlat / 2) ** 2
                + math.cos(math.radians(lat1))
                * math.cos(math.radians(lat2))
                * math.sin(dlon / 2) ** 2
            )
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

    CONSUMO_DIESEL = 8.0
    CONSUMO_GASOLINA = 11.0
    PRECO_DIESEL = 7.55 #
    PRECO_GASOLINA = 7.99#

    TARIFA_PEDAGIO_CARRO = 12.00
    TARIFA_PEDAGIO_CAMINHAO = 65.00

    CUSTO_DIARIA_HOTEL = 453.00#
    CUSTO_ALIMENTACAO = 50.00
    CUSTO_AUX_DESLOCAMENTO = 50.00

    visitas_supervisao = math.ceil(m2_real / 300.0) * 3
    deslocamentos_instalacao = math.ceil(m2_real / 300.0)
    viagens_caminhao = math.ceil(m2_real / 150.0)
    dias_trabalho = math.ceil(m2_real / 15.0)

    km_caminhao = distancia_km * 2 * viagens_caminhao
    custo_diesel = (km_caminhao / CONSUMO_DIESEL) * PRECO_DIESEL

    km_supervisao = distancia_km * 2 * visitas_supervisao
    custo_gasolina_supervisao = (
        km_supervisao / CONSUMO_GASOLINA
    ) * PRECO_GASOLINA

    km_instalacao = distancia_km * 2 * deslocamentos_instalacao
    custo_gasolina_instalacao = (
        km_instalacao / CONSUMO_GASOLINA
    ) * PRECO_GASOLINA

    num_pedagios = int(distancia_km / 80) * 2
    custo_pedagio_caminhao = (
        num_pedagios * TARIFA_PEDAGIO_CAMINHAO * viagens_caminhao
    )
    custo_pedagio_carro = (
        num_pedagios
        * TARIFA_PEDAGIO_CARRO
        * (visitas_supervisao + deslocamentos_instalacao)
    )

    total_frete = (
        custo_diesel
        + custo_gasolina_supervisao
        + custo_gasolina_instalacao
        + custo_pedagio_caminhao
        + custo_pedagio_carro
    )

    equipe_instalacao = 4
    total_pessoas = equipe_instalacao + 1  

    precisa_pernoite = distancia_km > 150.0
    diaria_hotel_aplicada = CUSTO_DIARIA_HOTEL if precisa_pernoite else 0.0

    custo_estadia = dias_trabalho * total_pessoas * diaria_hotel_aplicada
    custo_alimentacao = dias_trabalho * total_pessoas * CUSTO_ALIMENTACAO
    custo_auxilio = dias_trabalho * equipe_instalacao * CUSTO_AUX_DESLOCAMENTO

    total_operacao = custo_estadia + custo_alimentacao + custo_auxilio

    return {
        "distancia_km": distancia_km,
        "custo_frete": round(Decimal(str(total_frete)), 2),
        "custo_operacao": round(Decimal(str(total_operacao)), 2),
        "custo_total_deslocamento": round(
            Decimal(str(total_frete + total_operacao)), 2
        ),
    }


def converter_para_decimal(valor):
    if valor is None:
        return Decimal("0.00")
    if isinstance(valor, (int, float)):
        return Decimal(str(valor))

    val_str = str(valor).strip().replace("R$", "").replace(" ", "")
    if "," in val_str and "." in val_str:
        if val_str.find(".") < val_str.find(","):
            val_str = val_str.replace(".", "").replace(",", ".")
        else:
            val_str = val_str.replace(",", "")
    elif "," in val_str:
        val_str = val_str.replace(",", ".")

    try:
        return Decimal(val_str)
    except Exception:
        match = re.search(r"[\d.]+", val_str)
        if match:
            try:
                return Decimal(match.group(0))
            except:
                pass
    return Decimal("0.00")


def validar_codigo_esquadria(codigo):
    """Filtra e valida se o código extraído segue o padrão real de esquadria (ex: J03_1, PF4, OF5)."""
    if not codigo:
        return False
    
    codigo_limpo = str(codigo).strip().upper()
    
    if codigo_limpo.isdigit() or codigo_limpo in ["FIXO", "MOVEL", "TIPO", "OBRA", "TOTAIS"]:
        return False
        
    padrao = re.compile(r'^[A-Z]+\d+(_\d+)?$')
    return bool(padrao.match(codigo_limpo))


def processar_excel_relatorio(file_stream):
    """Lê o relatório em PDF e prepara o objeto e os itens em memória sem salvar imediatamente."""
    if hasattr(file_stream, 'seek'):
        file_stream.seek(0)

    linhas_texto = []
    with pdfplumber.open(file_stream) as pdf:
        for page in pdf.pages:
            texto_pagina = page.extract_text()
            if texto_pagina:
                for linha in texto_pagina.split("\n"):
                    if linha.strip():
                        linhas_texto.append(linha.strip())

    codigo_obra = "25-0021-06"
    nome_obra = "RESIDENCIA"
    cliente = ""
    endereco_cliente = ""

    for linha in linhas_texto:
        match_cod = re.search(r"(\d{2}-\d{4}-\d{2})", linha)
        if match_cod:
            codigo_obra = match_cod.group(1)

        if "Obra:" in linha:
            parts = linha.split("Obra:")
            if len(parts) > 1:
                nome_obra = parts[1].strip()

        if "Cliente:" in linha:
            parts = linha.split("Cliente:")
            if len(parts) > 1:
                cliente = parts[1].strip()

        if "Endereço:" in linha or "Endereco:" in linha:
            match_end = re.search(r"Endereç?o:\s*(.+)", linha, re.IGNORECASE)
            if match_end:
                endereco_cliente = match_end.group(1).strip()

    # BLOQUEIO DE DUPLICIDADE: Impede processar se a obra já estiver salva no banco
    if Obra.objects.filter(codigo=codigo_obra).exists():
        raise ValueError(f"A obra com o código {codigo_obra} já existe no sistema e não pode ser duplicada!")

    m2_total_geral = Decimal("0.00")
    peso_total_geral = Decimal("0.00")
    qtd_total_geral = 0

    for linha in linhas_texto:
        linha_upper = linha.upper()
        if "TOTAIS" in linha_upper or "TOTAL" in linha_upper:
            vals = re.findall(r"[\d,\.]+", linha)
            if len(vals) >= 1:
                try:
                    nums = []
                    for v in vals:
                        dec = converter_para_decimal(v)
                        if dec > 0:
                            nums.append(dec)
                    
                    if len(nums) >= 1:
                        qtd_total_geral = int(nums[0])
                    if len(nums) >= 2:
                        m2_total_geral = nums[1]
                    if len(nums) >= 3:
                        peso_total_geral = nums[2]
                    
                    if qtd_total_geral > 0:
                        break
                except Exception:
                    pass

    dist_calc = calcular_distancia_automatica(CEP_MATRIZ, endereco_cliente or cliente)

    # Cria o objeto Obra apenas em memória (sem .save() ou update_or_create)
    obra_obj = Obra(
        codigo=codigo_obra,
        nome=nome_obra,
        cliente=cliente,
        total_pecas=qtd_total_geral,
        m2_total=m2_total_geral,
        peso_total=peso_total_geral,
        distancia_km=dist_calc,
    )

    itens_processados = []
    capturando_itens = False
    for linha in linhas_texto:
        if "Tipo" in linha and "Quantidade" in linha and "Área" in linha:
            capturando_itens = True
            continue
        
        if capturando_itens:
            if "TOTAIS" in linha.upper() or not linha:
                if "TOTAIS" in linha.upper():
                    capturando_itens = False
                continue

            partes = linha.split()
            if len(partes) >= 3:
                col0_val = partes[0]
                
                if not validar_codigo_esquadria(col0_val):
                    continue

                try:
                    raw_qtd = partes[1] if len(partes) > 1 else "1"
                    qtd = int(float(raw_qtd.replace(",", ".")))

                    # CORREÇÃO DA MÊTRAGEM (Blindada com try-except individual)
                    m2 = Decimal("0.00")
                    for parte in partes[2:]:
                        try:
                            val_dec = converter_para_decimal(parte)
                            if Decimal("0.01") <= val_dec < Decimal("100.00"):
                                m2 = val_dec
                                break
                        except Exception:
                            continue

                    # Tratamento seguro para o peso
                    peso = Decimal("0.00")
                    if len(partes) > 4:
                        try:
                            peso = converter_para_decimal(partes[-1])
                        except Exception:
                            peso = Decimal("0.00")

                    # Cria o item em memória vinculado à obra (sem .create() no banco)
                    item_obj = ItemVidro(
                        obra=obra_obj,
                        codigo_item=col0_val,
                        descricao=f"{col0_val} - ESQUADRIA",
                        quantidade=qtd,
                        m2_corte=m2,
                        peso_kg=peso,
                        custo_total=Decimal("0.00"),
                    )
                    itens_processados.append(item_obj)
                except Exception:
                    continue

    if not itens_processados:
        item_resumo = ItemVidro(
            obra=obra_obj,
            codigo_item="ITM-01",
            descricao="RESUMO GERAL DOS ITENS DA OBRA",
            quantidade=qtd_total_geral if qtd_total_geral > 0 else 1,
            m2_corte=m2_total_geral,
            peso_kg=peso_total_geral,
            custo_total=Decimal("0.00"),
        )
        itens_processados.append(item_resumo)

    m2_total = (
        sum(i.m2_corte for i in itens_processados)
        if itens_processados
        else m2_total_geral
    )
    res = calcular_precificacao_operacao(obra_obj.distancia_km, float(m2_total))

    obra_obj.custo_frete = res["custo_frete"]
    obra_obj.custo_operacao = res["custo_operacao"]
    obra_obj.custo_total_deslocamento = res["custo_total_deslocamento"]
    
    # ATENÇÃO: Nenhum .save() é executado aqui! Tudo fica guardado na memória.

    return obra_obj, itens_processados