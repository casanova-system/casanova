import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from core.views.ordem_producao import imprimir_barcode_ordem_producao, _conteudo_barcode, _gerar_barcode_svg
from django.http import HttpRequest
from django.contrib.auth.models import User

# Testa a função diretamente
print("=== Teste _conteudo_barcode(648) ===")
try:
    conteudo = _conteudo_barcode(648)
    print(f"JSON: {conteudo}")
except Exception as e:
    print(f"ERRO _conteudo_barcode: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Teste _gerar_barcode_svg ===")
try:
    svg = _gerar_barcode_svg(conteudo)
    print(f"SVG length: {len(svg)}")
except Exception as e:
    print(f"ERRO _gerar_barcode_svg: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Teste view completa ===")
try:
    from core.models import ObraOP
    op = ObraOP.objects.filter(pk=648).first()
    print(f"OP 648: {op}")
    print(f"pausada_material: {op.pausada_material if op else 'OP NAO EXISTE'}")
    if op and op.pausada_material:
        print("OP PAUSADA - view vai redirectar")
except Exception as e:
    print(f"ERRO busca OP: {e}")
    import traceback
    traceback.print_exc()