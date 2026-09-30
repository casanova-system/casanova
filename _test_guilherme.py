"""Verifica acesso do usuario guilherme apos reinicio do servidor."""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from django.urls import reverse

u = User.objects.get(username="guilherme")
print(f"Usuario: {u.username}")
print(f"  is_superuser: {u.is_superuser}")
print(f"  rotinas: {list(u.perfil.rotinas_permitidas.values_list('codigo', 'nome', 'categoria'))}")
print(f"  tem_graficos: {u.perfil.tem_rotina.tem_graficos}")
print(f"  tem_relatorios: {u.perfil.tem_rotina.tem_relatorios}")

client = Client()
client.force_login(u)

print("\n=== Acesso as rotas ===")
for nome in ["lista_obras", "grafico_custo_frete", "relatorio_fretes_mes",
             "lista_usuarios", "lista_veiculos", "lista_custo", "lista_permissao"]:
    resp = client.get(reverse(nome))
    esperado = "200" if nome == "lista_obras" else "302"
    ok = "OK" if str(resp.status_code) == esperado else "FALHA"
    print(f"  [{ok}] {nome:25s} -> {resp.status_code} (esperado {esperado})")

# Verifica o menu
resp = client.get(reverse("menu_principal"))
html = resp.content.decode("utf-8", errors="ignore")
print("\n=== Menu lateral ===")
print(f"  link grafico presente:   {reverse('grafico_custo_frete') in html} (esperado: False)")
print(f"  link relatorio presente: {reverse('relatorio_fretes_mes') in html} (esperado: False)")
print(f"  link lista_obras presente: {reverse('lista_obras') in html} (esperado: True)")
