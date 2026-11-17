import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from core.models import ObraOPItem

items = ObraOPItem.objects.select_related('op').all()
print(f'Total itens no banco: {items.count()}')
for i in items:
    print(f'Item ID={i.pk} | OP={i.op.codigo_formatado} | codigo={i.codigo} | tipo={i.get_tipo_perfil_display()} | tam={i.tamanho}mm x{i.quantidade}')