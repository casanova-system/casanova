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
    for url in ['/industria/producao/', '/industria/rastreio/', '/industria/acompanhamento-mesa/']:
        resp = client.get(url)
        print(f'{url}: {resp.status_code}')
else:
    print('No superuser found')