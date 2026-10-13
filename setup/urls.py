from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
]

# Arquivos de mídia (fotos de perfil, uploads de usuário).
#
# Em produção o .env define DEBUG=False, então o helper static() do Django não
# registra a rota de /media/ — e o WhiteNoise só atende STATIC_ROOT (estáticos).
# Como o sistema é acessado direto pelo gunicorn na porta 8000, o nginx (porta
# 80) não intercepta /media/ e as fotos apareciam quebradas no servidor.
#
# Servimos /media/ explicitamente, valendo em qualquer modo (DEBUG True/False).
# Aplicação de rede interna (LAN), portanto o serve() do Django é adequado.
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]