from django.db import models
from django.contrib.auth.models import User
from datetime import date

class Obra(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    nome = models.CharField(max_length=255)
    cliente = models.CharField(max_length=255, blank=True, null=True)
    tratamento_cor = models.CharField(max_length=100, blank=True, null=True)
    data_emissao = models.DateField(blank=True, null=True)
    
    total_pecas = models.IntegerField(default=0)
    m2_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    peso_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Campos de Logística e Precificação
    distancia_km = models.FloatField(default=15.0)
    custo_frete = models.DecimalField(max_length=10, decimal_places=2, max_digits=12, default=0.0)
    custo_operacao = models.DecimalField(max_length=10, decimal_places=2, max_digits=12, default=0.0)
    custo_total_deslocamento = models.DecimalField(max_length=10, decimal_places=2, max_digits=12, default=0.0)

    # NOVO CAMPO: Registra qual usuário calculou/salvou este frete (obra)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuário Responsável")

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

    def __str__(self):
        return f"{self.codigo_item} - {self.descricao}"


# ==========================================
# NOVO MODELO DE PERFIL PARA OS USUÁRIOS
# ==========================================
class PerfilUsuario(models.Model):
    NIVEIS_ACESSO = [
        ('DIRETORIA', 'Diretoria'),
        ('GERENCIA', 'Gerência'),
        ('USUARIO', 'Usuário'),
    ]

    SETOR_CHOICES = [
        ('COMERCIAL', 'Comercial'),
        ('FINANCEIRO', 'Financeiro'),
        ('OPERACAO', 'Operação'),
        ('ADMINISTRACAO', 'Administração'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    cpf = models.CharField(max_length=14, blank=True, null=True)
    data_nascimento = models.DateField(null=True, blank=True)
    cep = models.CharField(max_length=9, blank=True, null=True)
    endereco = models.CharField(max_length=255, blank=True, null=True)
    nivel_acesso = models.CharField(max_length=20, choices=NIVEIS_ACESSO, default='USUARIO')
    setor = models.CharField(max_length=50, choices=SETOR_CHOICES, default='COMERCIAL')
    
    # Campo adicionado para a foto de perfil do usuário
    foto = models.ImageField(upload_to='fotos_perfil/', blank=True, null=True)

    @property
    def idade(self):
        if not self.data_nascimento:
            return None
        hoje = date.today()
        return hoje.year - self.data_nascimento.year - ((hoje.month, hoje.day) < (self.data_nascimento.month, self.data_nascimento.day))

    def __str__(self):
        return f"{self.user.username} - {self.nivel_acesso} ({self.setor})"