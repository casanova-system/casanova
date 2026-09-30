from datetime import date
from django.contrib.auth.models import User
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver


class Obra(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    nome = models.CharField(max_length=255)
    cliente = models.CharField(max_length=255, blank=True, null=True)
    tratamento_cor = models.CharField(max_length=100, blank=True, null=True)
    data_emissao = models.DateField(blank=True, null=True)

    total_pecas = models.IntegerField(default=0)
    m2_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    peso_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    percentual_desconto = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Campos de Logística e Precificação
    distancia_km = models.FloatField(default=15.0)
    custo_frete = models.DecimalField(
        max_length=10, decimal_places=2, max_digits=12, default=0.0
    )
    custo_operacao = models.DecimalField(
        max_length=10, decimal_places=2, max_digits=12, default=0.0
    )
    custo_total_deslocamento = models.DecimalField(
        max_length=10, decimal_places=2, max_digits=12, default=0.0
    )

    veiculo = models.ForeignKey(
        'Veiculo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Veículo Selecionado',
    )

    # Registra qual usuário calculou/salvou este frete (obra)
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Usuário Responsável',
    )    

    def __str__(self):
        return f'{self.codigo} - {self.nome}'


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
        return f'{self.codigo_item} - {self.descricao}'


# ==========================================
# MODELO DE ROTINAS DO SISTEMA
# ==========================================
CATEGORIAS_ROTINA = [
    ('ROTINA', 'Rotina'),
    ('GRAFICO', 'Gráfico'),
    ('RELATORIO', 'Relatório'),
]

SETORES_ROTINA = [
    ('COMERCIAL', 'Comercial'),
    ('FINANCEIRO', 'Financeiro'),
    ('FROTAS', 'Frotas'),
    ('ADMINISTRADOR', 'Administrador'),
]

ROTINAS_PADRAO = [
    ('001', 'Custo de Frete', 'lista_obras', 'ROTINA', 'COMERCIAL'),
    ('002', 'Cadastro de Usuário', 'lista_usuarios', 'ROTINA', 'ADMINISTRADOR'),
    ('003', 'Cadastro de Veículo', 'lista_veiculos', 'ROTINA', 'FROTAS'),
    ('004', 'Cadastro de Custo', 'lista_custo', 'ROTINA', 'FINANCEIRO'),
    ('005', 'Gerenciar Permissões', 'lista_permissao', 'ROTINA', 'ADMINISTRADOR'),
    ('006', 'Gráfico de Custo de Frete', 'grafico_custo_frete', 'GRAFICO', 'COMERCIAL'),
    ('007', 'Relatório de Fretes do Mês', 'relatorio_fretes_mes', 'RELATORIO', 'COMERCIAL'),
]


def garantir_rotinas_padrao():
    """Garante que as rotinas do menu existam e estejam com os dados corretos."""
    for codigo, nome, url_name, categoria, setor in ROTINAS_PADRAO:
        rotina, created = Rotina.objects.get_or_create(
            codigo=codigo,
            defaults={
                'nome': nome,
                'url_name': url_name,
                'categoria': categoria,
                'setor': setor,
            },
        )
        if not created and (
            rotina.url_name != url_name
            or rotina.nome != nome
            or rotina.categoria != categoria
            or rotina.setor != setor
        ):
            rotina.url_name = url_name
            rotina.nome = nome
            rotina.categoria = categoria
            rotina.setor = setor
            rotina.save(update_fields=['url_name', 'nome', 'categoria', 'setor'])


class Rotina(models.Model):
    codigo = models.CharField(max_length=10, unique=True, verbose_name='Código da Rotina')
    nome = models.CharField(max_length=100, verbose_name='Nome da Rotina')
    url_name = models.CharField(max_length=100, verbose_name='URL Name')
    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIAS_ROTINA,
        default='ROTINA',
        verbose_name='Categoria',
    )
    setor = models.CharField(
        max_length=20,
        choices=SETORES_ROTINA,
        default='COMERCIAL',
        verbose_name='Setor',
    )

    def __str__(self):
        return f'{self.codigo} - {self.nome}'


class AcessoRotinas:
    """Permite {% if perfil.tem_rotina.lista_obras %} e perfil.tem_rotina('lista_obras') no Python."""

    do_not_call_in_templates = True

    def __init__(self, perfil):
        object.__setattr__(self, '_perfil', perfil)

    def _checa(self, valor):
        perfil = object.__getattribute__(self, '_perfil')
        if perfil.user.is_superuser:
            return True
        valor = str(valor)
        return perfil.rotinas_permitidas.filter(
            models.Q(url_name=valor) | models.Q(codigo=valor)
        ).exists()

    def __call__(self, valor):
        return self._checa(valor)

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        return self._checa(name)

    def __getitem__(self, key):
        # O Django tenta __getitem__ ANTES de atributos/propriedades.
        # Se a chave for uma propriedade real da classe (ex.: tem_graficos),
        # devolvemos o valor dela em vez de tratar como código de rotina.
        if isinstance(key, str) and hasattr(type(self), key):
            return getattr(self, key)
        if isinstance(key, int):
            return self._checa(f'{key:03d}') or self._checa(str(key))
        return self._checa(key)

    def _tem_categoria(self, categoria):
        perfil = object.__getattribute__(self, '_perfil')
        if perfil.user.is_superuser:
            return True
        return perfil.rotinas_permitidas.filter(categoria=categoria).exists()

    def _tem_setor(self, setor):
        perfil = object.__getattribute__(self, '_perfil')
        if perfil.user.is_superuser:
            return True
        return perfil.rotinas_permitidas.filter(setor=setor).exists()

    @property
    def tem_graficos(self):
        return self._tem_categoria('GRAFICO')

    @property
    def tem_relatorios(self):
        return self._tem_categoria('RELATORIO')

    @property
    def tem_comercial(self):
        return self._tem_setor('COMERCIAL')

    @property
    def tem_financeiro(self):
        return self._tem_setor('FINANCEIRO')

    @property
    def tem_frotas(self):
        return self._tem_setor('FROTAS')

    @property
    def tem_administrador(self):
        return self._tem_setor('ADMINISTRADOR')


# ==========================================
# MODELO DE PERFIL PARA OS USUÁRIOS
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

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='perfil'
    )
    cpf = models.CharField(max_length=14, blank=True, null=True)
    data_nascimento = models.DateField(null=True, blank=True)
    cep = models.CharField(max_length=9, blank=True, null=True)
    endereco = models.CharField(max_length=255, blank=True, null=True)
    nivel_acesso = models.CharField(
        max_length=20, choices=NIVEIS_ACESSO, default='USUARIO'
    )
    setor = models.CharField(
        max_length=50, choices=SETOR_CHOICES, default='COMERCIAL'
    )

    # Novo campo adicionado para gerenciar as rotinas permitidas
    rotinas_permitidas = models.ManyToManyField(
        Rotina, blank=True, verbose_name='Rotinas Permitidas'
    )

    foto = models.ImageField(upload_to='fotos_perfil/', blank=True, null=True)

    @property
    def tem_rotina(self):
        """Uso no template: perfil.tem_rotina.lista_obras / perfil.tem_rotina.001
        Uso no Python: perfil.tem_rotina('lista_obras')"""
        return AcessoRotinas(self)

    @property
    def idade(self):
        if not self.data_nascimento:
            return None
        hoje = date.today()
        return (
            hoje.year
            - self.data_nascimento.year
            - (
                (hoje.month, hoje.day)
                < (self.data_nascimento.month, self.data_nascimento.day)
            )
        )

    def __str__(self):
        return f'{self.user.username} - {self.nivel_acesso} ({self.setor})'


# Signals para criar e salvar o perfil automaticamente ao criar um User
@receiver(post_save, sender=User)
def criar_perfil_usuario(sender, instance, created, **kwargs):
    if created:
        PerfilUsuario.objects.create(user=instance)


@receiver(post_save, sender=User)
def salvar_perfil_usuario(sender, instance, **kwargs):
    try:
        instance.perfil.save()
    except PerfilUsuario.DoesNotExist:
        PerfilUsuario.objects.create(user=instance)


# ==========================================
# MODELO: VEÍCULOS
# ==========================================
class Veiculo(models.Model):
    placa = models.CharField(
        max_length=10, unique=True, verbose_name='Placa'
    )
    chassi = models.CharField(
        max_length=50, blank=True, null=True, verbose_name='Chassi'
    )
    marca_modelo = models.CharField(
        max_length=100, blank=True, null=True, verbose_name='Marca/Modelo'
    )
    ano_fabricacao = models.IntegerField(
        blank=True, null=True, verbose_name='Ano de Fabricação'
    )
    cor = models.CharField(
        max_length=30, blank=True, null=True, verbose_name='Cor'
    )
    tipo_combustivel = models.CharField(
        max_length=50, blank=True, null=True, verbose_name='Tipo de Combustível'
    )

    litros_tanque = models.DecimalField(
        max_digits=6, decimal_places=2, blank=True, null=True, verbose_name='Litros do Tanque'
    )
    
    comprimento_bau = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True, verbose_name='Comprimento do Baú (m)'
    )
    largura_bau = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True, verbose_name='Largura do Baú (m)'
    )
    altura_bau = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True, verbose_name='Altura do Baú (m)'
    )

    capacidade_volumetrica = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Capacidade Volumétrica (m³)'
    )
    consumo_combustivel = models.DecimalField(
        max_digits=5, decimal_places=2, verbose_name='Consumo de Combustível (km/L)'
    )

    especificacao_tecnica = models.TextField(
        blank=True, null=True, verbose_name='Especificação Técnica'
    )

    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    data_cadastro = models.DateTimeField(
        auto_now_add=True, verbose_name='Data de Cadastro'
    )
    usuario_responsavel = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Cadastrado por',
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.marca_modelo} - {self.placa}'


# ==========================================
# MODELO: Custo
# ==========================================
class Custo(models.Model):
    tipo = models.CharField(max_length=100, verbose_name='Tipo de Custo')
    descricao = models.CharField(max_length=255, verbose_name='Descrição')
    valor = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Valor (R$)')

    # Chave estável usada pelo cálculo de frete (não muda quando o nome/descrição é editado)
    chave = models.CharField(
        max_length=50,
        blank=True,
        default='',
        db_index=True,
        verbose_name='Chave do Sistema',
        help_text='Identificador fixo usado pelo cálculo de frete. Não altere.',
    )

    # Campo adicionado para proteger registros essenciais contra exclusão
    fixo = models.BooleanField(default=False, verbose_name='Custo Fixo do Sistema')

    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')    

    usuario_responsavel = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Cadastrado por',
    )

    # Propriedade para compatibilidade com a chamada {{ c.usuario }} no template
    @property
    def usuario(self):
        return self.usuario_responsavel

    def delete(self, *args, **kwargs):
        # Bloqueia a exclusão se o registro estiver marcado como fixo
        if self.fixo:
            raise ValidationError("Este custo é fixo do sistema e não pode ser excluído. Você pode apenas editá-lo.")
        super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.tipo} - {self.valor}'