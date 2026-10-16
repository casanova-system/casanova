from core.views import usuario as views_usuario
from core.views import permissao
from core.views.app_mobile import app_mobile
from core.views.certificado import (
    baixar_ca,
    baixar_instalador_windows,
    pagina_certificado,
)
from django.urls import path
from django.views.generic.base import RedirectView

from core.api import (
    api_escanear,
    api_login,
    api_logout,
    api_perfil,
    api_rastreio_detalhe,
    api_rastreios,
    api_setores,
)

from core.views.custo import (
    cadastrar_custo,
    detalhe_custo,
    editar_custo,
    lista_custo,
    # excluir_custo removido daqui para evitar o erro
)
from core.views.frete import (
    detalhe_obra,
    detalhe_obra_temp,
    editar_obra,
    excluir_obra,
    lista_obras,
    upload_pdf,
)
from core.views.grafico_frete import grafico_custo_frete
from core.views.ordem_producao import (
    barcode_ordem_producao,
    detalhe_obra_op,
    excluir_op,
    importar_op_excel,
    imprimir_barcode_ordem_producao,
    lista_ordem_producao,
)
from core.views.custo_producao import (
    calcular_op,
    custos_setores,
    detalhe_custo_producao,
    lista_custos,
    recalcular_todos,
)
from core.views.compra import (
    detalhe_pedido,
    detalhe_requisicao,
    lista_fornecedores,
    lista_pedidos,
    lista_requisicoes,
    nova_requisicao,
    novo_fornecedor,
)
from core.views.estoque import (
    lista_estoque,
    lista_produtos,
    movimentar,
    movimentos,
    novo_produto,
    saldo_produto,
)
from core.views.romaneio import (
    detalhe_romaneio,
    excluir_romaneio,
    imprimir_romaneio,
    lista_romaneios,
    novo_romaneio,
)
from core.views.rastreio import (
    escanear,
    producao,
    rastreio_op,
    rastreio_producao,
    registrar_movimentacao,
)
from core.views.relatorio import relatorio_fretes_mes  # <-- Importado do arquivo relatorio.py recém criado
from core.views.veiculo import (
    cadastrar_veiculo,
    detalhe_veiculo,
    editar_veiculo,
    excluir_veiculo,
    lista_veiculos,
)
from core.views.views import (
    atualizar_foto_perfil,
    graficos_view,
    login_view,
    logout_view,
    menu_principal,
    relatorios_view,
    rotinas_view,
)
from core.pontosecullum.views import (
    listar_tabelas_ponto,
    ver_tabela_ponto,
    consultar_ponto,
)

urlpatterns = [
    # LOGIN/LOGOUT
    path('', menu_principal, name='menu_principal'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    # MENU
    path('rotinas/', rotinas_view, name='rotinas'),
    path('graficos/', graficos_view, name='graficos'),
    path('relatorios/', relatorios_view, name='relatorios'),
    path(
        'relatorios/fretes-mes/',
        relatorio_fretes_mes,
        name='relatorio_fretes_mes',
    ),
    # ROTINA DE CUSTO DE FRETE
    path('frete/', lista_obras, name='lista_obras'),
    path('frete/upload/', upload_pdf, name='upload_pdf'),
    path('frete/detalhe/temp/', detalhe_obra_temp, name='detalhe_obra_temp'),
    path('frete/detalhe/<int:pk>/', detalhe_obra, name='detalhe_obra'),
    path('frete/editar/<int:pk>/', editar_obra, name='editar_obra'),
    path('frete/excluir/<int:pk>/', excluir_obra, name='excluir_obra'),
    # ROTINA CADASTRO DE USUÁRIO
    path(
        'cadastro-usuario/',
        RedirectView.as_view(pattern_name='lista_usuarios', permanent=False),
    ),
    path('usuarios/', views_usuario.lista_usuarios, name='lista_usuarios'),
    path('usuarios/novo/', views_usuario.criar_usuario, name='criar_usuario'),
    path(
        'usuarios/<int:pk>/',
        views_usuario.detalhe_usuario,
        name='detalhe_usuario',
    ),
    path(
        'usuarios/<int:pk>/editar/',
        views_usuario.editar_usuario,
        name='editar_usuario',
    ),
    path(
        'usuarios/<int:pk>/excluir/',
        views_usuario.excluir_usuario,
        name='excluir_usuario',
    ),
    # ROTINA DE PERMISSÃO DE ROTINAS
    path('permissoes/', permissao.lista_permissao, name='lista_permissao'),
    path('permissoes/<int:user_id>/editar/', permissao.form_permissao, name='form_permissao'),
    # GRAFICO
    path('graficos/custo-frete/', grafico_custo_frete, name='grafico_custo_frete'),
    # PERFIL / FOTO
    path('perfil/atualizar-foto/', atualizar_foto_perfil, name='atualizar_foto_perfil'),
    # ROTINAS DE VEÍCULOS
    path('veiculos/', lista_veiculos, name='lista_veiculos'),
    path('veiculos/cadastrar/', cadastrar_veiculo, name='cadastrar_veiculo'),
    path('veiculos/<int:pk>/', detalhe_veiculo, name='detalhe_veiculo'),
    path('veiculos/<int:pk>/editar/', editar_veiculo, name='editar_veiculo'),
    path('veiculos/<int:pk>/excluir/', excluir_veiculo, name='excluir_veiculo'),
    # ROTINA DE CUSTO (A rota de exclusão de custos foi removida daqui)
    path('custo/', lista_custo, name='lista_custo'),
    path('custo/cadastrar/', cadastrar_custo, name='cadastrar_custo'),
    path('custo/<int:pk>/', detalhe_custo, name='detalhe_custo'),
    path('custo/<int:pk>/editar/', editar_custo, name='editar_custo'),
    # ROTINA DE ORDEM DE PRODUÇÃO (INDÚSTRIA - Faktory)
    path('industria/ordem-producao/', lista_ordem_producao, name='lista_ordem_producao'),
    path('industria/ordem-producao/importar/', importar_op_excel, name='importar_op_excel'),
    path('industria/ordem-producao/obra-op/<int:obra_op_id>/', detalhe_obra_op, name='detalhe_obra_op'),
    path('industria/ordem-producao/<int:obra_op_id>/excluir/', excluir_op, name='excluir_op'),
    path('industria/ordem-producao/<int:op_id>/barcode/', barcode_ordem_producao, name='barcode_ordem_producao'),
    path('industria/ordem-producao/<int:op_id>/barcode/imprimir/', imprimir_barcode_ordem_producao, name='imprimir_barcode_ordem_producao'),
    # RASTREIO DE PRODUÇÃO (código de barras)
    path('industria/rastreio/', rastreio_producao, name='rastreio_producao'),
    path('industria/rastreio/escanear/', escanear, name='escanear'),
    path('industria/rastreio/<int:op_id>/', rastreio_op, name='rastreio_op'),
    path('industria/rastreio/<int:op_id>/registrar/', registrar_movimentacao, name='registrar_movimentacao'),
    # PRODUÇÃO (consulta rápida da OP na indústria)
    path('industria/producao/', producao, name='producao'),

    # Custo de Produção
    path('industria/custos/', lista_custos, name='lista_custos'),
    path('industria/custos/<int:custo_id>/', detalhe_custo_producao,
         name='detalhe_custo_producao'),
    path('industria/custos/op/<int:op_id>/calcular/', calcular_op, name='calcular_op'),
    path('industria/custos/setores/', custos_setores, name='custos_setores'),
    path('industria/custos/recalcular/', recalcular_todos, name='recalcular_todos'),

    # Compras
    path('industria/compras/', lista_requisicoes, name='lista_compras'),
    path('industria/compras/requisicoes/', lista_requisicoes, name='lista_requisicoes'),
    path('industria/compras/requisicoes/nova/', nova_requisicao, name='nova_requisicao'),
    path('industria/compras/requisicoes/<int:requisicao_id>/',
         detalhe_requisicao, name='detalhe_requisicao'),
    path('industria/compras/pedidos/', lista_pedidos, name='lista_pedidos'),
    path('industria/compras/pedidos/<int:pedido_id>/',
         detalhe_pedido, name='detalhe_pedido'),
    path('industria/compras/fornecedores/', lista_fornecedores, name='lista_fornecedores'),
    path('industria/compras/fornecedores/novo/', novo_fornecedor, name='novo_fornecedor'),

    # Estoque
    path('industria/estoque/', lista_estoque, name='lista_estoque'),
    path('industria/estoque/movimentar/', movimentar, name='movimentar_estoque'),
    path('industria/estoque/movimentos/', movimentos, name='movimentos_estoque'),
    path('industria/estoque/produtos/', lista_produtos, name='lista_produtos_estoque'),
    path('industria/estoque/produtos/novo/', novo_produto, name='novo_produto_estoque'),
    path('industria/estoque/produto/<int:produto_id>/', saldo_produto, name='saldo_produto'),

    # Romaneio de Carga (a Expedicao e o setor final do fluxo)
    path('industria/romaneios/', lista_romaneios, name='lista_romaneios'),
    path('industria/romaneios/novo/', novo_romaneio, name='novo_romaneio'),
    path('industria/romaneios/<int:romaneio_id>/', detalhe_romaneio,
         name='detalhe_romaneio'),
    path('industria/romaneios/<int:romaneio_id>/imprimir/', imprimir_romaneio,
         name='imprimir_romaneio'),
    path('industria/romaneios/<int:romaneio_id>/excluir/', excluir_romaneio,
         name='excluir_romaneio'),
    # ==========================================
    # API REST — App Mobile (Flutter)
    # ==========================================
    path('api/login/', api_login, name='api_login'),
    path('api/logout/', api_logout, name='api_logout'),
    path('api/perfil/', api_perfil, name='api_perfil'),
    path('api/setores/', api_setores, name='api_setores'),
    path('api/rastreios/', api_rastreios, name='api_rastreios'),
    path('api/rastreios/<int:op_id>/', api_rastreio_detalhe, name='api_rastreio_detalhe'),
    path('api/escanear/', api_escanear, name='api_escanear'),
    # ==========================================
    # APP MOBILE (Flutter Web) — acessível pelo navegador do celular
    # ==========================================
    path('app/', app_mobile, name='app_mobile'),
    # ==========================================
    # CERTIFICADO DA CA LOCAL (instalar no celular p/ camera em HTTPS)
    # ==========================================
    path('certificado/', pagina_certificado, name='pagina_certificado'),
    path('certificado/casanova-ca.crt', baixar_ca, name='baixar_ca'),
    path('certificado/instalar-certificado-windows.bat',
         baixar_instalador_windows, name='baixar_instalador_windows'),
    # ==========================================
    # PONTOSECULLUM — Visualização READ-ONLY
    # ==========================================
    path('pontosecullum/', listar_tabelas_ponto, {'banco': 'casanova'}, name='ponto_tabelas'),
    path('pontosecullum/<str:banco>/', listar_tabelas_ponto, name='ponto_tabelas'),
    path('pontosecullum/<str:banco>/tabela/<str:tabela>/', ver_tabela_ponto, name='ponto_ver_tabela'),
    path('pontosecullum/<str:banco>/consultar/', consultar_ponto, name='ponto_consultar'),
]