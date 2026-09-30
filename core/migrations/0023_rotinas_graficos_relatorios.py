# Generated manually: adiciona rotinas de gráficos/relatórios e define categorias

from django.db import migrations


ROTINAS_PADRAO = [
    ('001', 'Custo de Frete', 'lista_obras', 'ROTINA'),
    ('002', 'Cadastro de Usuário', 'lista_usuarios', 'ROTINA'),
    ('003', 'Cadastro de Veículo', 'lista_veiculos', 'ROTINA'),
    ('004', 'Cadastro de Custo', 'lista_custo', 'ROTINA'),
    ('005', 'Gerenciar Permissões', 'lista_permissao', 'ROTINA'),
    ('006', 'Gráfico de Custo de Frete', 'grafico_custo_frete', 'GRAFICO'),
    ('007', 'Relatório de Fretes do Mês', 'relatorio_fretes_mes', 'RELATORIO'),
]


def criar_rotinas(apps, schema_editor):
    Rotina = apps.get_model('core', 'Rotina')
    for codigo, nome, url_name, categoria in ROTINAS_PADRAO:
        rotina, created = Rotina.objects.get_or_create(
            codigo=codigo,
            defaults={'nome': nome, 'url_name': url_name, 'categoria': categoria},
        )
        if not created:
            rotina.nome = nome
            rotina.url_name = url_name
            rotina.categoria = categoria
            rotina.save(update_fields=['nome', 'url_name', 'categoria'])


def remover_rotinas(apps, schema_editor):
    Rotina = apps.get_model('core', 'Rotina')
    Rotina.objects.filter(codigo__in=['006', '007']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_rotina_categoria'),
    ]

    operations = [
        migrations.RunPython(criar_rotinas, remover_rotinas),
    ]
