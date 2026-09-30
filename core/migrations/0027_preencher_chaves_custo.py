from django.db import migrations
import unicodedata


def _normalizar(texto):
    """Remove acentos e coloca em minúsculas para comparação tolerante."""
    if not texto:
        return ''
    sem_acento = unicodedata.normalize('NFKD', texto)
    sem_acento = ''.join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.lower().strip()


# Mapeamento estável: chave do sistema -> termos que identificam o custo existente.
# A busca é feita por descrição/tipo (case-insensitive) apenas nesta migração,
# para vincular os registros já cadastrados às suas chaves fixas.
MAPA_CHAVES = {
    'carga_media': ['carga média', 'carga media'],
    'pedagio_carro': ['pedagio carro', 'pedágio carro'],
    'pedagio_caminhao': ['pedagio caminhao', 'pedágio caminhão'],
    'valor_gasolina': ['valor gasolina'],
    'valor_diesel': ['valor diesel'],
    'numero_pedagio_80km': ['numero pedagio a cada 80km', 'número pedágio a cada 80km'],
    'num_colab_supervisao': ['num colaborador supervisao tecnica', 'num colaborador supervisão técnica'],
    'num_colab_instalacao': ['num colaborador instalador'],
    'custo_diaria_hotel': ['custo diaria hotel por pessoa', 'custo diária hotel por pessoa'],
    'custo_diaria_alimentacao': ['custo diaria de alimentacao por pessoa', 'custo diária de alimentação por pessoa'],
    'auxilio_deslocamento_diario': ['auxilio deslocamento diario por pessoa', 'auxílio deslocamento diário por pessoa'],
    'num_visita_supervisao': ['num visita supervisao tecnica', 'num visita supervisão técnica'],
    'num_deslocamento_instalacao': ['num deslocamento eqp instalador'],
    'num_entrega_caminhao': ['num entrega carro furgao', 'num entrega carro furgão'],
    'num_dia_trabalhado_equipe': ['numero dia trabalhado pela equipe', 'número dia trabalhado pela equipe'],
    'taxa_espaco_veicular': ['taxa de espaco veicular', 'taxa espaço veicular', 'taxa espaco veicular'],
}


def preencher_chaves(apps, schema_editor):
    Custo = apps.get_model('core', 'Custo')
    # Carrega todos os custos sem chave uma única vez (evita N queries)
    pendentes = list(Custo.objects.filter(chave=''))

    for chave, termos in MAPA_CHAVES.items():
        termos_norm = [_normalizar(t) for t in termos]
        for custo in pendentes:
            if custo.chave:
                continue
            alvo = _normalizar(f'{custo.descricao} {custo.tipo}')
            if any(termo in alvo for termo in termos_norm):
                custo.chave = chave
                custo.fixo = True
                custo.save(update_fields=['chave', 'fixo'])
                break


def limpar_chaves(apps, schema_editor):
    Custo = apps.get_model('core', 'Custo')
    Custo.objects.update(chave='')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0026_custo_chave_sistema'),
    ]

    operations = [
        migrations.RunPython(preencher_chaves, limpar_chaves),
    ]
