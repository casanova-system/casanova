from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0039_restaurar_dados_movimentacao'),
    ]

    operations = [
        migrations.AddField(
            model_name='movimentacaoop',
            name='quantidade_produzida',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Qtd. Produzida'),
        ),
        migrations.AddField(
            model_name='rastreioop',
            name='quantidade_total',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Qtd. Total da OP'),
        ),
    ]
