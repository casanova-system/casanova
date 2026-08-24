from django.db import models

class Obra(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    nome = models.CharField(max_length=255)
    cliente = models.CharField(max_length=255, blank=True, null=True)
    tratamento_cor = models.CharField(max_length=100, blank=True, null=True)
    data_emissao = models.DateField(blank=True, null=True)
    
    # Campos de Logística e Precificação
    distancia_km = models.FloatField(default=15.0)
    custo_frete = models.DecimalField(max_length=10, decimal_places=2, max_digits=12, default=0.0)
    custo_operacao = models.DecimalField(max_length=10, decimal_places=2, max_digits=12, default=0.0)
    custo_total_deslocamento = models.DecimalField(max_length=10, decimal_places=2, max_digits=12, default=0.0)

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

class ItemVidro(models.Model):
    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name='itens')
    codigo_item = models.CharField(max_length=100, blank=True, default='')
    descricao = models.CharField(max_length=255, blank=True, default='')
    cor = models.CharField(max_length=100, blank=True, null=True, default='')
    quantidade = models.IntegerField(default=1)
    m2_corte = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    peso_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    m2_pedido = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    custo_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)