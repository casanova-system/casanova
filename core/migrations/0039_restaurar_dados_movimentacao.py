"""Migração de dados: restaurar usuario_entrada das movimentações antigas.

Quando a migração 0037 removeu o campo 'usuario' e adicionou 'usuario_entrada' e 'usuario_saida',
as movimentações antigas ficaram sem usuário. Esta migração restaura o usuário de entrada
baseado no usuário que está logado no momento (casanova).
"""

from django.db import migrations


def restaurar_usuario_entrada(apps, schema_editor):
    """Restaura o usuário_entrada das movimentações que não têm usuário."""
    MovimentacaoOP = apps.get_model('core', 'MovimentacaoOP')
    User = apps.get_model('auth', 'User')
    
    # Usuário padrão (casanova)
    user = User.objects.filter(username='casanova').first()
    if not user:
        return
    
    # Atualiza todas as movimentações sem usuario_entrada
    MovimentacaoOP.objects.filter(usuario_entrada__isnull=True).update(usuario_entrada=user)
    
    # Para movimentações com data_saida, copia usuario_entrada para usuario_saida se estiver vazio
    MovimentacaoOP.objects.filter(usuario_saida__isnull=True, data_saida__isnull=False).update(usuario_saida=user)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0037_movimentacao_entrada_saida'),
    ]

    operations = [
        migrations.RunPython(restaurar_usuario_entrada, migrations.RunPython.noop),
    ]
