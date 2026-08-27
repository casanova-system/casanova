from django.urls import path
from django.views.generic.base import RedirectView
from . import views

urlpatterns = [
    # Se acessar a raiz '', o Django manda para o login (ou para o menu se já estiver logado, controlado pelo login_required na view do menu)
    path('', views.menu_principal, name='menu_principal'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('frete/', views.lista_obras, name='lista_obras'),
    path('frete/upload/', views.upload_pdf, name='upload_pdf'),
    
    # Rota temporária para pré-visualização do PDF antes de salvar no banco
    path('frete/detalhe/temp/', views.detalhe_obra_temp, name='detalhe_obra_temp'),
    
    path('frete/detalhe/<int:pk>/', views.detalhe_obra, name='detalhe_obra'),
    
    # Nova rota para editar o frete/obra:
    path('frete/editar/<int:pk>/', views.editar_obra, name='editar_obra'),
    
    # Nova rota para excluir o frete/obra:
    path('frete/excluir/<int:pk>/', views.excluir_obra, name='excluir_obra'),

    # ==========================================
    # NOVAS ROTAS ADICIONADAS PARA O MENU
    # ==========================================
    path('rotinas/', views.rotinas_view, name='rotinas'),
    path('graficos/', views.graficos_view, name='graficos'),
    path('relatorios/', views.relatorios_view, name='relatorios'),
]