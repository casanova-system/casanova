# Generated manually

from django.db import migrations


ROTINAS_PADRAO = [
    ('001', 'Custo de Frete', 'lista_obras'),
    ('002', 'Cadastro de Usuário', 'lista_usuarios'),
    ('003', 'Cadastro de Veículo', 'lista_veiculos'),
    ('004', 'Cadastro de Custo', 'lista_custo'),
    ('005', 'Gerenciar Permissões', 'lista_permissao'),
]


def criar_rotinas_padrao(apps, schema_editor):
    Rotina = apps.get_model('core', 'Rotina')
    for codigo, nome, url_name in ROTINAS_PADRAO:
        Rotina.objects.get_or_create(
            codigo=codigo,
            defaults={'nome': nome, 'url_name': url_name},
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_rotina_perfilusuario_rotinas_permitidas'),
    ]

    operations = [
        migrations.RunPython(criar_rotinas_padrao, noop),
    ]
