import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

client = Client()
user = User.objects.filter(is_superuser=True).first()
if user:
    client.force_login(user)
    # Test POST to producao (2nd bip - finalização)
    resp = client.post('/industria/producao/', {
        'op_id': '648',
        'quantidade_produzida': '10',
        'observacao': '',
        'setor': '',
    })
    print(f'POST /industria/producao/: {resp.status_code}')
    print(f'Content: {resp.content[:500]}')
else:
    print('No superuser found')