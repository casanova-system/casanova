from django.urls import path
from django.views.generic.base import RedirectView
from core.views import usuario as views_usuario
from core.views.views import (
    menu_principal,
    login_view,
    logout_view,
    lista_obras,
    upload_pdf,
    detalhe_obra_temp,
    detalhe_obra,
    editar_obra,
    excluir_obra,
    rotinas_view,
    graficos_view,
    relatorios_view,          # <--- Certifique-se de importar esta view
    relatorio_fretes_mes,
    grafico_custo_frete,
    atualizar_foto_perfil     # <--- Importação da nova view de foto de perfil
)

urlpatterns = [
    # LOGIN/LOGOUT
    path('', menu_principal, name='menu_principal'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),

    # MENU
    path('rotinas/', rotinas_view, name='rotinas'),
    path('graficos/', graficos_view, name='graficos'),
    path('relatorios/', relatorios_view, name='relatorios'),                     # <--- ADICIONE ESTA LINHA
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
]