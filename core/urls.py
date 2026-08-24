from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_obras, name='lista_obras'),
    path('upload/', views.upload_pdf, name='upload_pdf'),
    path('obra/<int:pk>/', views.detalhe_obra, name='detalhe_obra'),
]