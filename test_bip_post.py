import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from core.views.rastreio import _producao_finalizar
from django.test import RequestFactory
from django.contrib.auth.models import User

factory = RequestFactory()
request = factory.post('/industria/producao/', {
    'op_id': '648',
    'quantidade_produzida': '10',
    'observacao': '',
    'setor': '',
})
request.user = User.objects.filter(is_superuser=True).first()

try:
    response = _producao_finalizar(request)
    print(f'Status: {response.status_code}')
except Exception as e:
    import traceback
    traceback.print_exc()