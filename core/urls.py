from django.urls import path
from django.views.generic.base import RedirectView
from core.views import usuario as views_usuario

# ADICIONE AQUI O lista_obras JUNTO COM AS VIEWS DE FRETE:
from core.views.frete import (
    lista_obras,
    upload_pdf,
    detalhe_obra_temp,
    detalhe_obra,
    editar_obra,
    excluir_obra,
)

from core.views.veiculo import (
    lista_veiculos,
    cadastrar_veiculo,
    detalhe_veiculo,
    editar_veiculo,
    excluir_veiculo,
)

from core.views.custo import (
    lista_custo,
    cadastrar_custo,
    detalhe_custo,
    editar_custo,
    excluir_custo,
)

from core.views.grafico_frete import grafico_custo_frete

# REMOVA O lista_obras DAQUI:
from core.views.views import (
    menu_principal,
    login_view,
    logout_view,
    rotinas_view,
    graficos_view,
    relatorios_view,
    relatorio_fretes_mes,
    atualizar_foto_perfil,
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
    path('relatorios/fretes-mes/', relatorio_fretes_mes, name='relatorio_fretes_mes'),    

    # ROTINA DE CUSTO DE FRETE
    path('frete/', lista_obras, name='lista_obras'),
    path('frete/upload/', upload_pdf, name='upload_pdf'),
    path('frete/detalhe/temp/', detalhe_obra_temp, name='detalhe_obra_temp'),
    path('frete/detalhe/<int:pk>/', detalhe_obra, name='detalhe_obra'),
    path('frete/editar/<int:pk>/', editar_obra, name='editar_obra'),
    path('frete/excluir/<int:pk>/', excluir_obra, name='excluir_obra'),

    # ROTINA CADASTRO DE USUÁRIO     
    path('cadastro-usuario/', RedirectView.as_view(pattern_name='lista_usuarios', permanent=False)),  
    path('usuarios/', views_usuario.lista_usuarios, name='lista_usuarios'),
    path('usuarios/novo/', views_usuario.criar_usuario, name='criar_usuario'),
    path('usuarios/<int:pk>/', views_usuario.detalhe_usuario, name='detalhe_usuario'),
    path('usuarios/<int:pk>/editar/', views_usuario.editar_usuario, name='editar_usuario'),
    path('usuarios/<int:pk>/excluir/', views_usuario.excluir_usuario, name='excluir_usuario'),

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

    # ROTINA DE CUSTO
    path('custo/', lista_custo, name='lista_custo'),
    path('custo/cadastrar/', cadastrar_custo, name='cadastrar_custo'),
    path('custo/<int:pk>/', detalhe_custo, name='detalhe_custo'),
    path('custo/<int:pk>/editar/', editar_custo, name='editar_custo'),
    path('custo/<int:pk>/excluir/', excluir_custo, name='excluir_custo'),
]