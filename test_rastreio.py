import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from core.views.rastreio import rastreio_producao
from django.test import RequestFactory
from django.contrib.auth.models import User

factory = RequestFactory()
request = factory.get('/industria/rastreio/')
request.user = User.objects.filter(is_superuser=True).first()

try:
    response = rastreio_producao(request)
    print(f'Status: {response.status_code}')
except Exception as e:
    import traceback
    traceback.print_exc()