# Generated manually: define o setor de cada rotina padrão

from django.db import migrations


SETORES = {
    '001': 'COMERCIAL',
    '002': 'ADMINISTRADOR',
    '003': 'FROTAS',
    '004': 'FINANCEIRO',
    '005': 'ADMINISTRADOR',
    '006': 'COMERCIAL',
    '007': 'COMERCIAL',
}


def definir_setores(apps, schema_editor):
    Rotina = apps.get_model('core', 'Rotina')
    for codigo, setor in SETORES.items():
        Rotina.objects.filter(codigo=codigo).update(setor=setor)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_rotina_setor'),
    ]

    operations = [
        migrations.RunPython(definir_setores, noop),
    ]
