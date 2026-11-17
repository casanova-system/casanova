import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from core.models import ObraOPItem, ObraOP

# Busca todas as OPs
print("=== TODAS AS OPs ===")
ops = ObraOP.objects.all()
for op in ops:
    print(f"OP ID={op.pk} | {op.codigo_formatado} | esquadria={op.codigo_esquadria} | desc={op.descricao[:80]} | qtd={op.quantidade} | pausada={op.pausada_material}")
    for item in op.itens.all():
        print(f"  Item ID={item.pk} | codigo={item.codigo} | tipo={item.get_tipo_perfil_display()} | tam={item.tamanho}mm x{item.quantidade}")

print(f"\nTotal OPs: {ops.count()}")