from decimal import Decimal
import json
import math
import re
import urllib.parse
import urllib.request
import pandas as pd
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
    custo_gasolina_supervisao = (
        km_supervisao / CONSUMO_GASOLINA
    ) * PRECO_GASOLINA

    km_instalacao = distancia_km * 2 * deslocamentos_instalacao
    custo_gasolina_instalacao = (
        km_instalacao / CONSUMO_GASOLINA
    ) * PRECO_GASOLINA

    # Pedágio (a cada 80km - Ida e Volta)
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
    total_pessoas = equipe_instalacao + 1  # 4 instaladores + 1 supervisor

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
    if valor is None or pd.isna(valor):
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


def processar_excel_relatorio(file_stream):
    df = pd.read_excel(file_stream, sheet_name=0, header=None)

    codigo_obra = "25-0021-06"
    nome_obra = "RESIDENCIA"
    cliente = ""
    endereco_cliente = ""

    for idx, row in df.iloc[:15].iterrows():
        row_str = " ".join([str(v) for v in row if pd.notna(v)])
        match_cod = re.search(r"(\d{2}-\d{4}-\d{2})", row_str)
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
            match_end = re.search(r"Endereç?o:\s*(.+)", row_str, re.IGNORECASE)
            if match_end:
                endereco_cliente = match_end.group(1).strip()

    m2_total_geral = Decimal("0.00")
    peso_total_geral = Decimal("0.00")
    qtd_total_geral = 0

    for idx, row in df.iterrows():
        first_col = (
            str(row.iloc[0]).strip().upper() if pd.notna(row.iloc[0]) else ""
        )
        row_full_str = " ".join([str(v) for v in row if pd.notna(v)]).upper()
        if "TOTAIS:" in first_col or "TOTAIS" in row_full_str:
            vals = [
                v for v in row if pd.notna(v) and "TOTAIS" not in str(v).upper()
            ]
            if len(vals) >= 2:
                try:
                    nums = []
                    for v in vals:
                        dec_v = converter_para_decimal(v)
                        if dec_v > 0:
                            nums.append(float(dec_v))
                    if len(nums) >= 2:
                        qtd_total_geral = int(nums[0])
                        m2_total_geral = Decimal(str(nums[1]))
                        if len(nums) >= 3:
                            peso_total_geral = Decimal(str(nums[2]))
                except Exception:
                    pass
            break

    obra_obj, _ = Obra.objects.update_or_create(
        codigo=codigo_obra,
        defaults={
            "nome": nome_obra,
            "cliente": cliente,
            "distancia_km": calcular_distancia_automatica(
                CEP_MATRIZ, endereco_cliente or cliente
            ),
        },
    )

    obra_obj.itens.all().delete()
    itens_processados = []

    idx_tipo, idx_qtd, idx_area, idx_local, idx_peso = 0, 3, 8, 10, 13

    for idx, row in df.iterrows():
        headers = [str(cell).strip().lower() for cell in row.values]
        if "tipo" in headers or ("quantidade" in headers and "área" in headers):
            for i, h in enumerate(headers):
                if h in ["tipo", "código", "codigo"]:
                    idx_tipo = i
                elif h in ["quantidade", "qtd"]:
                    idx_qtd = i
                elif "área" in h or "area" in h:
                    idx_area = i
                elif "localização" in h or "localizacao" in h:
                    idx_local = i
                elif "peso" in h and "unit" not in h:
                    idx_peso = i
            break

    descricao_atual = "ESQUADRIAS DA OBRA"
    for idx, row in df.iterrows():
        for cell in row.values:
            if pd.notna(cell):
                cell_str = str(cell).strip()
                if (
                    not cell_str.replace(".", "").isdigit()
                    and "FOLHA" in cell_str.upper()
                ):
                    descricao_atual = cell_str

        col0_val = (
            str(row.iloc[idx_tipo]).strip()
            if len(row) > idx_tipo and pd.notna(row.iloc[idx_tipo])
            else ""
        )

        if (
            col0_val
            and col0_val.upper()
            not in [
                "TIPO",
                "OBRA:",
                "TOTAIS:",
                "CEM PRO - ALUMISOFT SISTEMAS",
                "ITENS DA OBRA",
            ]
            and not col0_val.startswith("Atenção")
            and not col0_val.startswith("Emitido")
        ):
            try:
                raw_qtd = (
                    row.iloc[idx_qtd]
                    if len(row) > idx_qtd and pd.notna(row.iloc[idx_qtd])
                    else 1
                )
                qtd = int(float(str(raw_qtd).replace(",", ".")))

                m2 = (
                    converter_para_decimal(row.iloc[idx_area])
                    if len(row) > idx_area
                    else Decimal("0.00")
                )
                peso = (
                    converter_para_decimal(row.iloc[idx_peso])
                    if len(row) > idx_peso
                    else Decimal("0.00")
                )

                localizacao = (
                    str(row.iloc[idx_local]).strip()
                    if len(row) > idx_local and pd.notna(row.iloc[idx_local])
                    else ""
                )
                if localizacao.lower() in ["nan", "none"]:
                    localizacao = ""

                desc_item = (
                    f"{col0_val} - {localizacao}".strip(" -")
                    if localizacao
                    else f"{col0_val} - {descricao_atual}"
                )

                item_obj = ItemVidro.objects.create(
                    obra=obra_obj,
                    codigo_item=col0_val,
                    descricao=desc_item,
                    quantidade=qtd,
                    m2_corte=m2,
                    peso_kg=peso,
                    custo_total=Decimal("0.00"),
                )
                itens_processados.append(item_obj)
            except Exception:
                continue

    if not itens_processados:
        item_resumo = ItemVidro.objects.create(
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
    obra_obj.save()

    return obra_obj, itens_processados