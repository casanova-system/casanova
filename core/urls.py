from core.views import usuario as views_usuario
from core.views import permissao
from django.urls import path
from django.views.generic.base import RedirectView

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
    imprimir_qrcode_ordem_producao,
    lista_ordem_producao,
    qrcode_ordem_producao,
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
    path('industria/ordem-producao/<int:op_id>/qrcode/', qrcode_ordem_producao, name='qrcode_ordem_producao'),
    path('industria/ordem-producao/<int:op_id>/qrcode/imprimir/', imprimir_qrcode_ordem_producao, name='imprimir_qrcode_ordem_producao'),
]