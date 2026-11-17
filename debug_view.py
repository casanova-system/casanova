import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from core.views.ordem_producao import imprimir_barcode_ordem_producao

# Cria request fake
factory = RequestFactory()
request = factory.get('/industria/ordem-producao/648/barcode/imprimir/')
request.user = User.objects.filter(is_superuser=True).first()

print("=== Testando view imprimir_barcode_ordem_producao(648) ===")
try:
    response = imprimir_barcode_ordem_producao(request, 648)
    print(f"Status: {response.status_code}")
    if hasattr(response, 'content'):
        print(f"Content length: {len(response.content)}")
except Exception as e:
    print(f"ERRO: {e}")
    import traceback
    traceback.print_exc()