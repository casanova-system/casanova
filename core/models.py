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
    ('INDUSTRIA', 'Indústria'),
    ('ADMINISTRADOR', 'Administrador'),
]

ROTINAS_PADRAO = [
    ('008', 'Ordem de Produção (OP)', 'lista_ordem_producao', 'ROTINA', 'INDUSTRIA'),
    ('009', 'Rastreio de Produção', 'rastreio_producao', 'ROTINA', 'INDUSTRIA'),
    ('010', 'Produção', 'producao', 'ROTINA', 'INDUSTRIA'),
    ('011', 'Romaneio de Carga', 'lista_romaneios', 'ROTINA', 'INDUSTRIA'),
    ('012', 'Estoque', 'lista_estoque', 'ROTINA', 'INDUSTRIA'),
    ('013', 'Compras', 'lista_compras', 'ROTINA', 'INDUSTRIA'),
    ('014', 'Custo de Produção', 'lista_custos', 'ROTINA', 'INDUSTRIA'),
]

# Rotinas descontinuadas — removidas do menu e da tela de permissões.
# Mantidas aqui para que garantir_rotinas_padrao() possa apagá-las de bancos
# que já as tenham, sem deixar checkbox órfão no formulário de permissão.
ROTINAS_REMOVIDAS = [
    ('006', 'grafico_custo_frete'),   # Gráficos
    ('007', 'relatorio_fretes_mes'),  # Relatórios
    # Modulos anteriores ao Casanova System — sairam do menu.
    ('001', 'lista_obras'),           # Custo de Frete
    ('002', 'lista_usuarios'),        # Cadastro de Usuário
    ('003', 'lista_veiculos'),        # Cadastro de Veículo
    ('004', 'lista_custo'),           # Cadastro de Custo
    ('005', 'lista_permissao'),       # Gerenciar Permissões
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

    # Remove as rotinas descontinuadas (Gráficos / Relatórios). O M2M de
    # permissões é limpo automaticamente ao apagar a Rotina.
    Rotina.objects.filter(codigo__in=[c for c, _ in ROTINAS_REMOVIDAS]).delete()


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
    def tem_industria(self):
        return self._tem_setor('INDUSTRIA')

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

    # Setor de produção do usuário (usado no rastreio por código de barras).
    # Ex.: gerente do Estoque, da Separação, do Corte, etc.
    setor_producao = models.ForeignKey(
        'SetorProducao',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responsaveis',
        verbose_name='Setor de Produção',
        help_text='Setor que este usuário gerencia no rastreio de produção.',
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


# ==========================================
# MODELOS: Rastreio de Produção (OP)
# ==========================================
SETORES_PRODUCAO_PADRAO = [
    # (codigo, nome, ordem, requer_vidro)
    ('estoque', 'Estoque', 1, False),
    ('separacao', 'Separação', 2, False),
    ('corte', 'Corte', 3, False),
    ('usinagem', 'Usinagem', 4, False),
    ('mesa', 'Mesa', 5, False),
    ('encaixilhamento', 'Encaixilhamento', 6, True),
    ('expedicao', 'Expedição', 7, False),
]


def garantir_setores_padrao():
    """Garante que os setores do fluxo de produção existam e estejam atualizados."""
    for codigo, nome, ordem, requer_vidro in SETORES_PRODUCAO_PADRAO:
        setor, created = SetorProducao.objects.get_or_create(
            codigo=codigo,
            defaults={
                'nome': nome,
                'ordem': ordem,
                'requer_vidro': requer_vidro,
            },
        )
        if not created and (
            setor.nome != nome
            or setor.ordem != ordem
            or setor.requer_vidro != requer_vidro
        ):
            setor.nome = nome
            setor.ordem = ordem
            setor.requer_vidro = requer_vidro
            setor.save(update_fields=['nome', 'ordem', 'requer_vidro'])


class SetorProducao(models.Model):
    """Setor do fluxo produtivo pelo qual a OP passa (Separação, Usinagem...)."""

    codigo = models.CharField(max_length=30, unique=True, verbose_name='Código')
    nome = models.CharField(max_length=100, verbose_name='Nome do Setor')
    ordem = models.PositiveIntegerField(default=0, verbose_name='Ordem no Fluxo')
    requer_vidro = models.BooleanField(
        default=False,
        verbose_name='Somente se tiver vidro',
        help_text='Se marcado, este setor só entra no fluxo quando a OP tiver vidro.',
    )
    ativo = models.BooleanField(default=True, verbose_name='Ativo')

    class Meta:
        ordering = ['ordem']
        verbose_name = 'Setor de Produção'
        verbose_name_plural = 'Setores de Produção'

    def __str__(self):
        return self.nome


class ObraOP(models.Model):
    """OP/Tipologia importada do Excel - vinculada a uma Obra."""
    obra = models.ForeignKey(
        'Obra',
        on_delete=models.CASCADE,
        related_name='ops',
        verbose_name='Obra'
    )
    codigo_documento = models.CharField(max_length=20, blank=True, default='', verbose_name='Cód. Documento (ex: J01, J02)')
    codigo_esquadria = models.CharField(max_length=50, verbose_name='Cód. Esquadria/Tipologia')
    descricao = models.TextField(verbose_name='Descrição da Tipologia')
    quantidade = models.IntegerField(default=1, verbose_name='Quantidade')
    largura = models.IntegerField(verbose_name='Largura (mm)')
    altura = models.IntegerField(verbose_name='Altura (mm)')
    tratamento = models.CharField(max_length=100, blank=True, default='', verbose_name='Tratamento/Cor')
    vidro_descricao = models.CharField(max_length=255, blank=True, default='', verbose_name='Descrição do Vidro')
    vidro_localizacao = models.CharField(max_length=255, blank=True, default='', verbose_name='Localização do Vidro')
    data_importacao = models.DateTimeField(auto_now_add=True, verbose_name='Importado em')
    
    class Meta:
        ordering = ['-data_importacao']
        verbose_name = 'OP/Tipologia da Obra'
        verbose_name_plural = 'OPs/Tipologias da Obra'
        # A identidade da OP é o documento (ex.: J01) dentro da obra.
        # O código da esquadria NÃO é único: a mesma esquadria (ex.: GOLS-JCR200)
        # pode aparecer em documentos diferentes (J04, J05).
        unique_together = ['obra', 'codigo_documento']

    def __str__(self):
        return f'{self.obra.codigo} - {self.codigo_formatado} ({self.descricao[:50]})'

    @property
    def codigo_formatado(self):
        """Código da OP no formato '1-J01' (ID sequencial + documento)."""
        documento = self.codigo_documento or self.codigo_esquadria
        return f'{self.pk}-{documento}'

    @property
    def peso_total(self):
        """Peso líquido total da tipologia.

        No relatório do Alumisoft a coluna "Peso" de cada perfil já é o peso
        líquido **daquela linha** (a soma das linhas é exatamente o
        "Peso Total:" impresso pelo próprio ERP), por isso somamos direto.
        """
        return sum((item.peso or 0) for item in self.itens.all())

    @property
    def total_pecas(self):
        """Soma das quantidades dos perfis da tipologia."""
        return sum(item.quantidade or 0 for item in self.itens.all())

    @property
    def identificacao(self):
        """Rótulo curto da OP (documento quando houver, senão a esquadria)."""
        return self.codigo_documento or self.codigo_esquadria


class ObraOPItem(models.Model):
    """Itens/Perfis de uma OP/Tipologia."""
    TIPO_PERFIL_CHOICES = [
        ('CM', 'Contra Marco'),
        ('MARCO', 'Marco'),
        ('ARREMATE', 'Arremate'),
        ('FOLHA', 'Folha'),
        ('CONEXAO', 'Conexão'),
        ('CUNHA', 'Cunha'),
        ('OUTRO', 'Outro'),
    ]
    
    op = models.ForeignKey(
        'ObraOP',
        on_delete=models.CASCADE,
        related_name='itens',
        verbose_name='OP/Tipologia'
    )
    posicao = models.IntegerField(default=0, verbose_name='Posição')
    codigo = models.CharField(max_length=50, blank=True, default='', verbose_name='Código do Perfil')
    tipo_perfil = models.CharField(max_length=20, choices=TIPO_PERFIL_CHOICES, default='OUTRO', verbose_name='Tipo de Perfil')
    orientacao = models.CharField(max_length=10, blank=True, default='', verbose_name='L/H')
    corte = models.CharField(max_length=20, blank=True, default='', verbose_name='Corte (ex: 45/45)')
    tamanho = models.IntegerField(default=0, verbose_name='Tamanho (mm)')
    quantidade = models.IntegerField(default=1, verbose_name='Quantidade')
    peso = models.DecimalField(max_digits=10, decimal_places=3, default=0, verbose_name='Peso (kg)')
    observacao = models.CharField(max_length=255, blank=True, default='', verbose_name='Observação')
    
    class Meta:
        ordering = ['posicao']
        verbose_name = 'Item da OP'
        verbose_name_plural = 'Itens da OP'

    def __str__(self):
        return f'{self.op.codigo_esquadria} - {self.tipo_perfil} {self.codigo} ({self.tamanho}mm x{self.quantidade})'

    @property
    def peso_unitario(self):
        """Peso líquido de uma peça (peso da linha dividido pela quantidade)."""
        if not self.quantidade:
            return self.peso or 0
        return (self.peso or 0) / self.quantidade


class ObraOPComponente(models.Model):
    """Componentes de uma OP/Tipologia importada do Excel."""
    op = models.ForeignKey(
        'ObraOP',
        on_delete=models.CASCADE,
        related_name='componentes',
        verbose_name='OP/Tipologia'
    )
    posicao = models.IntegerField(default=0, verbose_name='Posição')
    codigo = models.CharField(max_length=50, blank=True, default='', verbose_name='Código')
    descricao = models.TextField(blank=True, default='', verbose_name='Descrição')
    aplicacao = models.CharField(max_length=50, blank=True, default='', verbose_name='Aplicação')
    quantidade = models.IntegerField(default=1, verbose_name='Quantidade')
    unidade = models.CharField(max_length=10, blank=True, default='', verbose_name='Unidade')
    observacao = models.CharField(max_length=255, blank=True, default='', verbose_name='Observação')

    class Meta:
        ordering = ['posicao']
        verbose_name = 'Componente da OP'
        verbose_name_plural = 'Componentes da OP'

    def __str__(self):
        return f'{self.op.codigo_esquadria} - {self.codigo} ({self.quantidade} {self.unidade})'


class ObraOPVidro(models.Model):
    """Vidros de uma OP/Tipologia importada do Excel."""
    op = models.ForeignKey(
        'ObraOP',
        on_delete=models.CASCADE,
        related_name='vidros',
        verbose_name='OP/Tipologia'
    )
    posicao = models.IntegerField(default=0, verbose_name='Posição')
    codigo = models.CharField(max_length=50, blank=True, default='', verbose_name='Código')
    descricao = models.CharField(max_length=255, blank=True, default='', verbose_name='Descrição')
    cor = models.CharField(max_length=100, blank=True, default='', verbose_name='Cor')
    quantidade = models.IntegerField(default=1, verbose_name='Quantidade')
    largura = models.IntegerField(default=0, verbose_name='Largura (mm)')
    altura = models.IntegerField(default=0, verbose_name='Altura (mm)')
    observacao = models.CharField(max_length=255, blank=True, default='', verbose_name='Observação')

    class Meta:
        ordering = ['posicao']
        verbose_name = 'Vidro da OP'
        verbose_name_plural = 'Vidros da OP'

    def __str__(self):
        return f'{self.op.codigo_esquadria} - {self.codigo} ({self.largura}x{self.altura}mm)'


class RastreioOP(models.Model):
    """Estado atual do rastreio de uma OP (identificada pelo ID do Faktory)."""

    STATUS_CHOICES = [
        ('EM_PRODUCAO', 'Em Produção'),
        ('CONCLUIDA', 'Concluída'),
    ]

    op_id = models.IntegerField(
        unique=True, db_index=True, verbose_name='ID da OP (Faktory)'
    )
    op_numero = models.CharField(max_length=50, blank=True, default='', verbose_name='Número da OP')
    obra = models.CharField(max_length=255, blank=True, default='', verbose_name='Obra')
    produto = models.CharField(max_length=255, blank=True, default='', verbose_name='Produto')
    variante = models.CharField(max_length=100, blank=True, default='', verbose_name='Variante')

    # None = ainda não decidido (a decisão acontece na Mesa)
    tem_vidro = models.BooleanField(null=True, blank=True, verbose_name='Tem vidro?')

    setor_atual = models.CharField(max_length=30, blank=True, default='', verbose_name='Setor Atual')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='EM_PRODUCAO', verbose_name='Status'
    )

    # True = operador bipou para sair do setor, mas o próximo setor ainda não bipou para receber
    aguardando_saida = models.BooleanField(default=False, verbose_name='Aguardando saída do setor')

    quantidade_total = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Qtd. Total da OP',
        help_text='Quantidade total de peças desta OP (vinda da ObraOP).',
    )

    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    class Meta:
        ordering = ['-atualizado_em']
        verbose_name = 'Rastreio de OP'
        verbose_name_plural = 'Rastreios de OP'

    def __str__(self):
        return f'OP {self.op_numero or self.op_id} — {self.setor_atual_nome}'

    @property
    def setor_atual_nome(self):
        if not self.setor_atual:
            return 'Aguardando início'
        setor = SetorProducao.objects.filter(codigo=self.setor_atual).first()
        return setor.nome if setor else self.setor_atual

    @property
    def concluida(self):
        return self.status == 'CONCLUIDA'

    @property
    def tempo_no_setor_atual(self):
        """Retorna o tempo (em minutos) que a OP está no setor atual.
        Considera apenas horário de produção (seg-sex 7:00-11:00, 12:12-17:00,
        sexta até 16:00, sem sáb/dom).
        """
        if not self.setor_atual or self.concluida:
            return None
        from core.producao import calcular_minutos_producao
        from django.utils import timezone
        agora = timezone.now()
        # Busca a última movimentação de entrada no setor atual
        ultima_entrada = self.movimentacoes.filter(
            setor=self.setor_atual
        ).order_by('-data_hora').first()
        if ultima_entrada:
            return calcular_minutos_producao(ultima_entrada.data_hora, agora)
        return None

    @property
    def tempo_no_setor_atual_formatado(self):
        """Retorna o tempo formatado no setor atual."""
        minutos = self.tempo_no_setor_atual
        if minutos is None:
            return '—'
        if minutos < 60:
            return f'{int(minutos)}min'
        horas = int(minutos // 60)
        mins = int(minutos % 60)
        return f'{horas}h {mins}min' if mins else f'{horas}h'

    @property
    def status_tempo(self):
        """Retorna o status de tempo: 'OK', 'ATENCAO' ou 'CRITICO'."""
        minutos = self.tempo_no_setor_atual
        if minutos is None:
            return 'OK'
        if minutos >= 240:  # 4 horas
            return 'CRITICO'
        if minutos >= 120:  # 2 horas
            return 'ATENCAO'
        return 'OK'

    @property
    def status_tempo_classe(self):
        """Retorna a classe CSS correspondente ao status de tempo."""
        status = self.status_tempo
        if status == 'CRITICO':
            return 'status-critico'
        if status == 'ATENCAO':
            return 'status-atencao'
        return 'status-ok'

    @property
    def status_tempo_texto(self):
        """Retorna o texto descritivo do status de tempo."""
        status = self.status_tempo
        if status == 'CRITICO':
            return 'Parado há muito tempo'
        if status == 'ATENCAO':
            return 'Demorando um pouco'
        return 'Sem problema'

    @property
    def quantidade_produzida_total(self):
        """Quantidade produzida da OP.

        Cada setor informa as pecas que produziu, mas sao as MESMAS pecas
        passando pelos setores: numa OP de 5 pecas, somar os 7 setores daria
        35 — um numero impossivel. Por isso o resultado e limitado ao total
        da OP.
        """
        total = 0
        for mov in self.movimentacoes.all():
            if mov.quantidade_produzida:
                total += mov.quantidade_produzida
        if total <= 0:
            return None
        if self.quantidade_total:
            return min(total, self.quantidade_total)
        return total

    def tempo_no_setor(self, codigo_setor):
        """Retorna o tempo (em minutos) que a OP ficou em um setor específico.
        Considera apenas horário de produção (seg-sex 7:00-11:00, 12:12-17:00,
        sexta até 16:00, sem sáb/dom).
        """
        from core.producao import calcular_minutos_producao
        from django.utils import timezone
        movimentacoes = self.movimentacoes.filter(setor=codigo_setor).order_by('data_hora')
        total_minutos = 0.0
        for mov in movimentacoes:
            if mov.data_entrada and mov.data_saida:
                total_minutos += calcular_minutos_producao(mov.data_entrada, mov.data_saida)
            elif mov.data_entrada and not mov.data_saida:
                # Setor atual - calcula até agora
                total_minutos += calcular_minutos_producao(mov.data_entrada)
        return total_minutos

    def tempo_no_setor_formatado(self, codigo_setor):
        """Retorna o tempo formatado em um setor específico."""
        minutos = self.tempo_no_setor(codigo_setor)
        if minutos == 0:
            return '—'
        if minutos < 60:
            return f'{int(minutos)}min'
        horas = int(minutos // 60)
        mins = int(minutos % 60)
        return f'{horas}h {mins}min' if mins else f'{horas}h'

    def status_tempo_setor(self, codigo_setor):
        """Retorna o status de tempo de um setor: 'OK', 'ATENCAO' ou 'CRITICO'."""
        minutos = self.tempo_no_setor(codigo_setor)
        if minutos == 0:
            return 'OK'
        if minutos >= 240:  # 4 horas
            return 'CRITICO'
        if minutos >= 120:  # 2 horas
            return 'ATENCAO'
        return 'OK'

    def status_tempo_setor_classe(self, codigo_setor):
        """Retorna a classe CSS correspondente ao status de tempo do setor."""
        status = self.status_tempo_setor(codigo_setor)
        if status == 'CRITICO':
            return 'status-critico'
        if status == 'ATENCAO':
            return 'status-atencao'
        return 'status-ok'


class MovimentacaoOP(models.Model):
    """Registro histórico de cada passagem da OP por um setor."""

    rastreio = models.ForeignKey(
        RastreioOP, on_delete=models.CASCADE, related_name='movimentacoes'
    )
    setor = models.CharField(max_length=30, verbose_name='Setor')
    setor_nome = models.CharField(max_length=100, blank=True, default='', verbose_name='Nome do Setor')
    usuario_entrada = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='movimentacoes_entrada', verbose_name='Usuário (Entrada)'
    )
    usuario_saida = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='movimentacoes_saida', verbose_name='Usuário (Saída)'
    )
    observacao_entrada = models.CharField(max_length=255, blank=True, default='', verbose_name='Observação (Entrada)')
    observacao_saida = models.CharField(max_length=255, blank=True, default='', verbose_name='Observação (Saída/B.O.)')
    quantidade_produzida = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Qtd. Produzida',
        help_text='Quantidade de peças produzidas neste setor (informada no 2º bip).',
    )
    data_hora = models.DateTimeField(auto_now_add=True, verbose_name='Data/Hora')
    data_entrada = models.DateTimeField(null=True, blank=True, verbose_name='Data/Hora de Entrada')
    data_saida = models.DateTimeField(null=True, blank=True, verbose_name='Data/Hora de Saída')

    class Meta:
        ordering = ['data_hora']
        verbose_name = 'Movimentação de OP'
        verbose_name_plural = 'Movimentações de OP'

    def __str__(self):
        return f'{self.setor_nome} — {self.data_hora:%d/%m/%Y %H:%M}'

    @property
    def tempo_no_setor(self):
        """Retorna o tempo gasto no setor em minutos."""
        if self.data_entrada and self.data_saida:
            return (self.data_saida - self.data_entrada).total_seconds() / 60
        return None

    @property
    def tempo_no_setor_formatado(self):
        """Retorna o tempo formatado (ex: '2h 30min', '45min')."""
        minutos = self.tempo_no_setor
        if minutos is None:
            return '—'
        if minutos < 60:
            return f'{int(minutos)}min'
        horas = int(minutos // 60)
        mins = int(minutos % 60)
        return f'{horas}h {mins}min' if mins else f'{horas}h'


# ===========================================================================
# ROMANEIO DE CARGA
# ===========================================================================
# A Expedicao e o setor final do fluxo de producao: quando a OP chega la, ela
# esta pronta para sair. O romaneio agrupa as OPs que vao juntas numa carga.
#
# Regra central: so entra OP que JA CHEGOU na Expedicao. Um romaneio montado a
# mao (planilha) costuma incluir peca que ainda esta na fabrica, e a carga sai
# incompleta. Aqui o sistema nao deixa.
# ===========================================================================

STATUS_ROMANEIO = [
    ('ABERTO', 'Aberto'),
    ('EM_CARGA', 'Em carga'),
    ('SAIU', 'Saiu para entrega'),
    ('ENTREGUE', 'Entregue'),
    ('CANCELADO', 'Cancelado'),
]


class Romaneio(models.Model):
    """Uma carga: as OPs que saem juntas, o veiculo e o destino."""

    numero = models.CharField(
        max_length=20, unique=True, blank=True, default='',
        verbose_name='Número do Romaneio',
        help_text='Gerado automaticamente no formato ROM-AAAA-NNNN.',
    )

    # --- Destino ---
    obra = models.ForeignKey(
        Obra, on_delete=models.PROTECT, related_name='romaneios',
        verbose_name='Obra / Destino',
    )
    endereco_entrega = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Endereço de Entrega',
    )

    # --- Transporte ---
    veiculo = models.ForeignKey(
        Veiculo, on_delete=models.PROTECT, related_name='romaneios',
        null=True, blank=True, verbose_name='Veículo',
    )
    motorista = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Motorista',
    )
    distancia_km = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Distância (km)',
    )

    # --- Estado ---
    status = models.CharField(
        max_length=12, choices=STATUS_ROMANEIO, default='ABERTO',
        verbose_name='Status',
    )
    data_saida = models.DateTimeField(
        null=True, blank=True, verbose_name='Saída',
    )
    data_entrega = models.DateTimeField(
        null=True, blank=True, verbose_name='Entrega',
    )
    observacao = models.TextField(
        blank=True, default='', verbose_name='Observação',
    )

    # --- Auditoria ---
    criado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='romaneios_criados', verbose_name='Criado por',
    )
    recebido_por = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='Recebido por (quem assinou)',
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Romaneio de Carga'
        verbose_name_plural = 'Romaneios de Carga'

    def __str__(self):
        return f'{self.numero} — {self.obra.codigo}'

    @property
    def status_nome(self):
        return dict(STATUS_ROMANEIO).get(self.status, self.status)

    @property
    def status_classe(self):
        """Classe CSS para o selo de status."""
        return {
            'ABERTO': 'rom-aberto',
            'EM_CARGA': 'rom-carga',
            'SAIU': 'rom-saiu',
            'ENTREGUE': 'rom-entregue',
            'CANCELADO': 'rom-cancelado',
        }.get(self.status, 'rom-aberto')

    @property
    def total_ops(self):
        return self.itens.count()

    @property
    def total_pecas(self):
        """Soma das quantidades das OPs do romaneio."""
        total = 0
        for item in self.itens.all():
            total += item.quantidade
        return total

    @property
    def peso_total(self):
        """Soma do peso dos itens (quando informado)."""
        total = 0
        for item in self.itens.all():
            if item.peso_kg:
                total += float(item.peso_kg)
        return round(total, 2)

    @property
    def pode_editar(self):
        """Depois de sair para entrega, o romaneio nao se altera mais."""
        return self.status in ('ABERTO', 'EM_CARGA')

    def gerar_numero(self):
        """Gera o proximo numero no formato ROM-AAAA-NNNN (sequencial por ano)."""
        from django.utils import timezone as tz
        ano = tz.localdate().year
        prefixo = f'ROM-{ano}-'
        ultimo = (
            Romaneio.objects
            .filter(numero__startswith=prefixo)
            .order_by('-numero')
            .values_list('numero', flat=True)
            .first()
        )
        seq = 1
        if ultimo:
            try:
                seq = int(ultimo.split('-')[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        return f'{prefixo}{seq:04d}'


class RomaneioItem(models.Model):
    """Uma OP dentro do romaneio (uma linha da carga)."""

    romaneio = models.ForeignKey(
        Romaneio, on_delete=models.CASCADE, related_name='itens',
        verbose_name='Romaneio',
    )
    obra_op = models.ForeignKey(
        ObraOP, on_delete=models.PROTECT, related_name='romaneio_itens',
        verbose_name='OP',
    )
    quantidade = models.PositiveIntegerField(default=1, verbose_name='Quantidade')
    peso_kg = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Peso (kg)',
    )
    volumes = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Volumes',
    )
    conferido = models.BooleanField(default=False, verbose_name='Conferido')
    observacao = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Observação',
    )

    class Meta:
        ordering = ['obra_op__codigo_documento']
        verbose_name = 'Item do Romaneio'
        verbose_name_plural = 'Itens do Romaneio'
        # A mesma OP nao pode estar duas vezes no mesmo romaneio.
        unique_together = ['romaneio', 'obra_op']

    def __str__(self):
        return f'{self.obra_op.codigo_formatado} ({self.quantidade})'

    @property
    def descricao(self):
        return self.obra_op.descricao or ''

    @property
    def tipologia(self):
        return self.obra_op.codigo_esquadria or ''

    @property
    def medidas(self):
        if self.obra_op.largura and self.obra_op.altura:
            return f'{self.obra_op.largura} x {self.obra_op.altura} mm'
        return '—'


# ===========================================================================
# ESTOQUE
# ===========================================================================
# A fabrica controla tres coisas que se comportam diferente:
#   PERFIL / VIDRO  -> material de linha, medido em barra/m2, tem retalho
#   COMPONENTE      -> peca pequena (parafuso, guarnicao, botao), contada em PC
#   CONSUMIVEL/EPI  -> nao entra em OP, mas some do almoxarifado
#
# Por isso o produto tem GRUPO (define como se mede) e o saldo e por LOCAL
# (almoxarifado, retalho, obra, terceiro). Sem isso o saldo mente: o perfil
# que virou retalho continua contado como barra inteira.
# ===========================================================================

TIPOS_MOVIMENTO_ESTOQUE = [
    ('ENTRADA', 'Entrada'),
    ('SAIDA', 'Saída'),
    ('AJUSTE', 'Ajuste de inventário'),
]

ORIGENS_MOVIMENTO_ESTOQUE = [
    ('COMPRA', 'Compra / Nota fiscal'),
    ('PRODUCAO', 'Consumo em produção'),
    ('DEVOLUCAO', 'Devolução'),
    ('TRANSFERENCIA', 'Transferência entre locais'),
    ('AJUSTE', 'Ajuste / inventário'),
    ('MANUAL', 'Lançamento manual'),
]


class GrupoEstoque(models.Model):
    """Grupo de material (PERFIL, VIDRO, COMPONENTE, EPI...)."""

    nome = models.CharField(max_length=80, unique=True, verbose_name='Grupo')
    unidade = models.CharField(
        max_length=6, default='PC', verbose_name='Unidade padrão',
        help_text='PC = peça, BR = barra, M2 = metro quadrado, KG = quilo, M = metro.',
    )
    descricao = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Descrição',
    )
    ativo = models.BooleanField(default=True, verbose_name='Ativo')

    class Meta:
        ordering = ['nome']
        verbose_name = 'Grupo de Estoque'
        verbose_name_plural = 'Grupos de Estoque'

    def __str__(self):
        return self.nome


class LocalEstoque(models.Model):
    """Onde o material fica.

    Inclui os casos que a planilha nao consegue representar: retalho (que
    ainda vale dinheiro), material em obra e material em terceiro.
    """

    nome = models.CharField(max_length=120, unique=True, verbose_name='Local')
    terceiro = models.BooleanField(
        default=False, verbose_name='Está em terceiro',
        help_text='Material em poder de terceiro (não conta como estoque próprio).',
    )
    ativo = models.BooleanField(default=True, verbose_name='Ativo')

    class Meta:
        ordering = ['nome']
        verbose_name = 'Local de Estoque'
        verbose_name_plural = 'Locais de Estoque'

    def __str__(self):
        return self.nome


class ProdutoEstoque(models.Model):
    """Material controlado no estoque."""

    codigo = models.CharField(
        max_length=40, unique=True, verbose_name='Código',
    )
    descricao = models.CharField(max_length=255, verbose_name='Descrição')
    grupo = models.ForeignKey(
        GrupoEstoque, on_delete=models.PROTECT, related_name='produtos',
        verbose_name='Grupo',
    )
    unidade = models.CharField(
        max_length=6, default='PC', verbose_name='Unidade',
        help_text='Vazio = usa a unidade do grupo.',
    )

    # Medidas (perfil e vidro tem, componente nao)
    largura = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Largura (mm)',
    )
    altura = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Altura (mm)',
    )
    comprimento = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Comprimento (mm)',
    )
    cor = models.CharField(
        max_length=60, blank=True, default='', verbose_name='Cor / Tratamento',
    )
    peso_unitario = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        verbose_name='Peso unitário (kg)',
    )

    # Custo (vem da ultima compra / custo medio)
    custo_medio = models.DecimalField(
        max_digits=12, decimal_places=4, default=0,
        verbose_name='Custo médio',
    )
    custo_ultima_compra = models.DecimalField(
        max_digits=12, decimal_places=4, default=0,
        verbose_name='Custo da última compra',
    )

    # Controle
    estoque_minimo = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name='Estoque mínimo',
    )
    ponto_pedido = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name='Ponto de pedido',
    )
    codigo_ean = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Código de barras',
    )
    codigo_faktory = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Código no Faktory',
        help_text='Guarda o código original do ERP para conciliar.',
    )

    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    class Meta:
        ordering = ['codigo']
        verbose_name = 'Produto do Estoque'
        verbose_name_plural = 'Produtos do Estoque'

    def __str__(self):
        return f'{self.codigo} — {self.descricao[:50]}'

    @property
    def unidade_efetiva(self):
        return self.unidade or self.grupo.unidade

    @property
    def saldo_total(self):
        total = 0
        for s in self.saldos.all():
            total += float(s.quantidade or 0)
        return round(total, 3)

    @property
    def valor_total(self):
        total = 0
        for s in self.saldos.all():
            total += float(s.valor_total or 0)
        return round(total, 2)

    @property
    def abaixo_minimo(self):
        if not self.estoque_minimo:
            return False
        return self.saldo_total < float(self.estoque_minimo)

    @property
    def medidas_texto(self):
        partes = []
        if self.comprimento:
            partes.append(f'{self.comprimento:.0f}')
        if self.largura:
            partes.append(f'{self.largura:.0f}')
        if self.altura:
            partes.append(f'{self.altura:.0f}')
        return ' x '.join(partes) if partes else '—'


class SaldoEstoque(models.Model):
    """Quanto de um produto existe em um local."""

    produto = models.ForeignKey(
        ProdutoEstoque, on_delete=models.CASCADE, related_name='saldos',
        verbose_name='Produto',
    )
    local = models.ForeignKey(
        LocalEstoque, on_delete=models.PROTECT, related_name='saldos',
        verbose_name='Local',
    )
    quantidade = models.DecimalField(
        max_digits=14, decimal_places=3, default=0, verbose_name='Quantidade',
    )
    valor = models.DecimalField(
        max_digits=18, decimal_places=5, default=0, verbose_name='Valor (R$)',
        help_text='Valor total deste saldo, como veio do ERP. '
                  'Guardar o valor (e não só a quantidade) faz o estoque '
                  'fechar exatamente com o sistema de origem: derivar o valor '
                  'de quantidade x custo unitário acumula erro de '
                  'arredondamento em milhares de linhas. A precisão de 5 '
                  'casas acompanha a do ERP para o total bater ao centavo.',
    )
    reservado = models.DecimalField(
        max_digits=14, decimal_places=3, default=0,
        help_text='Quantidade já comprometida com uma OP.',
    )
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    class Meta:
        ordering = ['produto__codigo', 'local__nome']
        verbose_name = 'Saldo de Estoque'
        verbose_name_plural = 'Saldos de Estoque'
        unique_together = ['produto', 'local']

    def __str__(self):
        return f'{self.produto.codigo} @ {self.local.nome}: {self.quantidade}'

    @property
    def disponivel(self):
        return (self.quantidade or 0) - (self.reservado or 0)

    @property
    def valor_total(self):
        if not self.produto.custo_medio:
            return 0
        return round(float(self.quantidade or 0) * float(self.produto.custo_medio), 2)


class MovimentoEstoque(models.Model):
    """Toda entrada e saída de material."""

    produto = models.ForeignKey(
        ProdutoEstoque, on_delete=models.PROTECT, related_name='movimentos',
        verbose_name='Produto',
    )
    local = models.ForeignKey(
        LocalEstoque, on_delete=models.PROTECT, related_name='movimentos',
        verbose_name='Local',
    )
    local_destino = models.ForeignKey(
        LocalEstoque, on_delete=models.PROTECT, related_name='movimentos_entrada',
        null=True, blank=True, verbose_name='Local de destino',
        help_text='Só em transferência.',
    )

    tipo = models.CharField(
        max_length=8, choices=TIPOS_MOVIMENTO_ESTOQUE, verbose_name='Tipo',
    )
    origem = models.CharField(
        max_length=14, choices=ORIGENS_MOVIMENTO_ESTOQUE, default='MANUAL',
        verbose_name='Origem',
    )
    quantidade = models.DecimalField(
        max_digits=14, decimal_places=3, verbose_name='Quantidade',
    )
    valor_unitario = models.DecimalField(
        max_digits=12, decimal_places=4, default=0, verbose_name='Valor unitário',
    )
    valor_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, verbose_name='Valor total',
    )

    # Documento de origem
    documento = models.CharField(
        max_length=60, blank=True, default='', verbose_name='Documento',
        help_text='Nota fiscal, OP, requisição...',
    )
    obra_op = models.ForeignKey(
        ObraOP, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='movimentos_estoque', verbose_name='OP',
        help_text='Quando o consumo vem da produção.',
    )

    observacao = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Observação',
    )
    usuario = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='movimentos_estoque', verbose_name='Usuário',
    )
    data = models.DateTimeField(auto_now_add=True, verbose_name='Data')

    class Meta:
        ordering = ['-data', '-id']
        verbose_name = 'Movimento de Estoque'
        verbose_name_plural = 'Movimentos de Estoque'

    def __str__(self):
        sinal = '+' if self.tipo == 'ENTRADA' else '-'
        return f'{sinal}{self.quantidade} {self.produto.codigo} ({self.get_origem_display()})'

    @property
    def tipo_nome(self):
        return dict(TIPOS_MOVIMENTO_ESTOQUE).get(self.tipo, self.tipo)

    @property
    def origem_nome(self):
        return dict(ORIGENS_MOVIMENTO_ESTOQUE).get(self.origem, self.origem)

    @property
    def tipo_classe(self):
        return {'ENTRADA': 'mov-entrada', 'SAIDA': 'mov-saida',
                'AJUSTE': 'mov-ajuste'}.get(self.tipo, 'mov-ajuste')

    def aplicar_no_saldo(self):
        """Atualiza o saldo do produto no local. Chamado ao salvar o movimento.

        O saldo guarda quantidade E valor. Manter os dois em sincronia e o que
        faz o estoque fechar com o sistema de origem: se so a quantidade
        mudasse, o valor ficaria velho e a conta nunca bateria.
        """
        saldo, _ = SaldoEstoque.objects.get_or_create(
            produto=self.produto, local=self.local,
        )
        qtd = float(self.quantidade or 0)
        valor = float(self.valor_total or 0)
        if not valor:
            valor = qtd * float(self.valor_unitario or 0)

        qtd_antes = float(saldo.quantidade or 0)
        valor_antes = float(saldo.valor or 0)
        # custo unitario do saldo ANTES da alteracao — tem que ser lido antes,
        # senao a conta usa a quantidade ja alterada
        unitario = (valor_antes / qtd_antes) if qtd_antes else 0.0

        if self.tipo == 'ENTRADA':
            saldo.quantidade = qtd_antes + qtd
            saldo.valor = valor_antes + valor
        elif self.tipo == 'SAIDA':
            saldo.quantidade = qtd_antes - qtd
            # o que sai do estoque sai pelo que custou, nao pelo preco de venda
            saida = (qtd * unitario) if qtd_antes else valor
            saldo.valor = max(0.0, valor_antes - saida)
        elif self.tipo == 'AJUSTE':
            # ajuste define o saldo (nao soma)
            saldo.quantidade = qtd
            saldo.valor = valor if valor else valor_antes
        saldo.save(update_fields=['quantidade', 'valor', 'atualizado_em'])

        # transferencia: tira de um local e poe no outro
        if self.origem == 'TRANSFERENCIA' and self.local_destino:
            destino, _ = SaldoEstoque.objects.get_or_create(
                produto=self.produto, local=self.local_destino,
            )
            sai = (qtd * unitario) if qtd_antes else valor
            destino.quantidade = float(destino.quantidade or 0) + qtd
            destino.valor = float(destino.valor or 0) + sai
            destino.save(update_fields=['quantidade', 'valor', 'atualizado_em'])


# ===========================================================================
# COMPRA
# ===========================================================================
# O ciclo que fecha o estoque com a producao:
#
#   Estoque abaixo do minimo ─┐
#   OP precisa de material  ──┼─> REQUISICAO ─> PEDIDO ─> ENTRADA no estoque
#   Pedido manual           ──┘
#
# Sem esse ciclo, o estoque baixa e ninguem sabe o que comprar. E a requisicao
# ligada a OP e o que evita comprar material que nao vai ser usado.
# ===========================================================================

STATUS_REQUISICAO = [
    ('ABERTA', 'Aberta'),
    ('APROVADA', 'Aprovada'),
    ('COTACAO', 'Em cotação'),
    ('PEDIDO', 'Virou pedido'),
    ('ATENDIDA', 'Atendida'),
    ('CANCELADA', 'Cancelada'),
]

STATUS_PEDIDO_COMPRA = [
    ('ABERTO', 'Aberto'),
    ('ENVIADO', 'Enviado ao fornecedor'),
    ('PARCIAL', 'Recebido parcial'),
    ('RECEBIDO', 'Recebido'),
    ('CANCELADO', 'Cancelado'),
]


class Fornecedor(models.Model):
    """Quem fornece o material."""

    razao_social = models.CharField(max_length=180, verbose_name='Razão social')
    nome_fantasia = models.CharField(
        max_length=180, blank=True, default='', verbose_name='Nome fantasia')
    cnpj = models.CharField(
        max_length=20, blank=True, default='', verbose_name='CNPJ')
    inscricao_estadual = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Inscrição estadual')

    contato = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Contato')
    telefone = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Telefone')
    email = models.EmailField(
        blank=True, default='', verbose_name='E-mail')

    endereco = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Endereço')
    cidade = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Cidade')
    uf = models.CharField(
        max_length=2, blank=True, default='', verbose_name='UF')

    prazo_entrega_dias = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Prazo de entrega (dias)',
        help_text='Prazo padrão deste fornecedor, usado no pedido.')
    observacao = models.TextField(
        blank=True, default='', verbose_name='Observação')

    codigo_faktory = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Código no Faktory')
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')

    class Meta:
        ordering = ['razao_social']
        verbose_name = 'Fornecedor'
        verbose_name_plural = 'Fornecedores'

    def __str__(self):
        return self.nome_fantasia or self.razao_social

    @property
    def nome_curto(self):
        return self.nome_fantasia or self.razao_social[:40]


class ProdutoFornecedor(models.Model):
    """Qual fornecedor entrega qual produto, e por quanto.

    Permite comparar preco e escolher o melhor na cotacao — sem isso a compra
    vira pesquisa manual a cada pedido.
    """

    produto = models.ForeignKey(
        ProdutoEstoque, on_delete=models.CASCADE, related_name='fornecedores',
        verbose_name='Produto',
    )
    fornecedor = models.ForeignKey(
        Fornecedor, on_delete=models.CASCADE, related_name='produtos',
        verbose_name='Fornecedor',
    )
    codigo_no_fornecedor = models.CharField(
        max_length=60, blank=True, default='',
        verbose_name='Código no fornecedor',
        help_text='Como o fornecedor identifica este produto.',
    )
    preco = models.DecimalField(
        max_digits=12, decimal_places=4, default=0, verbose_name='Preço',
    )
    prazo_entrega_dias = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Prazo (dias)')
    ultima_compra = models.DateField(
        null=True, blank=True, verbose_name='Última compra')
    preferencial = models.BooleanField(
        default=False, verbose_name='Fornecedor preferencial')

    class Meta:
        ordering = ['produto__codigo', 'preco']
        verbose_name = 'Produto do Fornecedor'
        verbose_name_plural = 'Produtos do Fornecedor'
        unique_together = ['produto', 'fornecedor']

    def __str__(self):
        return f'{self.produto.codigo} — {self.fornecedor.nome_curto}'


class RequisicaoCompra(models.Model):
    """Pedido interno de material: alguem precisa, alguem autoriza.

    Nasce de tres formas:
      1. Estoque abaixo do minimo (o sistema sugere)
      2. Consumo previsto de uma OP (a producao precisa)
      3. Manual (o encarregado pede)
    """

    numero = models.CharField(
        max_length=20, unique=True, blank=True, default='',
        verbose_name='Número',
        help_text='Gerado no formato REQ-AAAA-NNNN.',
    )
    solicitante = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='requisicoes', verbose_name='Solicitante',
    )
    obra_op = models.ForeignKey(
        ObraOP, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='requisicoes', verbose_name='OP',
        help_text='Quando o material é para uma ordem de produção.',
    )
    setor = models.CharField(
        max_length=60, blank=True, default='', verbose_name='Setor solicitante',
    )

    origem = models.CharField(
        max_length=12,
        choices=[('MINIMO', 'Estoque mínimo'), ('OP', 'Ordem de produção'),
                 ('MANUAL', 'Solicitação manual')],
        default='MANUAL', verbose_name='Origem',
    )
    prioridade = models.CharField(
        max_length=10,
        choices=[('BAIXA', 'Baixa'), ('NORMAL', 'Normal'), ('URGENTE', 'Urgente')],
        default='NORMAL', verbose_name='Prioridade',
    )
    status = models.CharField(
        max_length=10, choices=STATUS_REQUISICAO, default='ABERTA',
        verbose_name='Status',
    )

    data_necessaria = models.DateField(
        null=True, blank=True, verbose_name='Necessário até',
    )
    justificativa = models.TextField(
        blank=True, default='', verbose_name='Justificativa',
    )

    aprovado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='requisicoes_aprovadas', verbose_name='Aprovado por',
    )
    data_aprovacao = models.DateTimeField(
        null=True, blank=True, verbose_name='Aprovação',
    )

    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criada em')
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizada em')

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Requisição de Compra'
        verbose_name_plural = 'Requisições de Compra'

    def __str__(self):
        return f'{self.numero} ({self.get_status_display()})'

    @property
    def status_nome(self):
        return dict(STATUS_REQUISICAO).get(self.status, self.status)

    @property
    def status_classe(self):
        return {
            'ABERTA': 'req-aberta', 'APROVADA': 'req-aprovada',
            'COTACAO': 'req-cotacao', 'PEDIDO': 'req-pedido',
            'ATENDIDA': 'req-atendida', 'CANCELADA': 'req-cancelada',
        }.get(self.status, 'req-aberta')

    @property
    def prioridade_classe(self):
        return {'BAIXA': 'pri-baixa', 'NORMAL': 'pri-normal',
                'URGENTE': 'pri-urgente'}.get(self.prioridade, 'pri-normal')

    @property
    def total_itens(self):
        return self.itens.count()

    @property
    def valor_estimado(self):
        total = 0
        for i in self.itens.all():
            total += float(i.valor_estimado or 0)
        return round(total, 2)

    @property
    def pode_aprovar(self):
        return self.status == 'ABERTA'

    @property
    def pode_editar(self):
        return self.status in ('ABERTA', 'APROVADA')

    def gerar_numero(self):
        from django.utils import timezone as tz
        ano = tz.localdate().year
        prefixo = f'REQ-{ano}-'
        ultimo = (
            RequisicaoCompra.objects
            .filter(numero__startswith=prefixo)
            .order_by('-numero').values_list('numero', flat=True).first()
        )
        seq = 1
        if ultimo:
            try:
                seq = int(ultimo.split('-')[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        return f'{prefixo}{seq:04d}'


class RequisicaoCompraItem(models.Model):
    """Um material pedido na requisicao."""

    requisicao = models.ForeignKey(
        RequisicaoCompra, on_delete=models.CASCADE, related_name='itens',
        verbose_name='Requisição',
    )
    produto = models.ForeignKey(
        ProdutoEstoque, on_delete=models.PROTECT, related_name='requisicoes',
        verbose_name='Produto',
    )
    quantidade = models.DecimalField(
        max_digits=14, decimal_places=3, verbose_name='Quantidade',
    )
    quantidade_atendida = models.DecimalField(
        max_digits=14, decimal_places=3, default=0, verbose_name='Atendida',
    )
    preco_estimado = models.DecimalField(
        max_digits=12, decimal_places=4, default=0, verbose_name='Preço estimado',
    )
    observacao = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Observação',
    )

    class Meta:
        ordering = ['produto__codigo']
        verbose_name = 'Item da Requisição'
        verbose_name_plural = 'Itens da Requisição'

    def __str__(self):
        return f'{self.produto.codigo} x {self.quantidade}'

    @property
    def valor_estimado(self):
        return round(float(self.quantidade or 0) * float(self.preco_estimado or 0), 2)

    @property
    def pendente(self):
        return (self.quantidade or 0) - (self.quantidade_atendida or 0)


class PedidoCompra(models.Model):
    """Pedido enviado ao fornecedor."""

    numero = models.CharField(
        max_length=20, unique=True, blank=True, default='',
        verbose_name='Número',
        help_text='Gerado no formato PED-AAAA-NNNN.',
    )
    fornecedor = models.ForeignKey(
        Fornecedor, on_delete=models.PROTECT, related_name='pedidos',
        verbose_name='Fornecedor',
    )
    requisicao = models.ForeignKey(
        RequisicaoCompra, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pedidos', verbose_name='Requisição de origem',
    )

    status = models.CharField(
        max_length=10, choices=STATUS_PEDIDO_COMPRA, default='ABERTO',
        verbose_name='Status',
    )
    condicao_pagamento = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Condição de pagamento',
    )
    data_pedido = models.DateField(
        null=True, blank=True, verbose_name='Data do pedido',
    )
    previsao_entrega = models.DateField(
        null=True, blank=True, verbose_name='Previsão de entrega',
    )
    data_recebimento = models.DateField(
        null=True, blank=True, verbose_name='Recebimento',
    )
    frete = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name='Frete',
    )
    observacao = models.TextField(
        blank=True, default='', verbose_name='Observação',
    )

    comprador = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pedidos_compra', verbose_name='Comprador',
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Pedido de Compra'
        verbose_name_plural = 'Pedidos de Compra'

    def __str__(self):
        return f'{self.numero} — {self.fornecedor.nome_curto}'

    @property
    def status_nome(self):
        return dict(STATUS_PEDIDO_COMPRA).get(self.status, self.status)

    @property
    def status_classe(self):
        return {
            'ABERTO': 'ped-aberto', 'ENVIADO': 'ped-enviado',
            'PARCIAL': 'ped-parcial', 'RECEBIDO': 'ped-recebido',
            'CANCELADO': 'ped-cancelado',
        }.get(self.status, 'ped-aberto')

    @property
    def total_itens(self):
        return self.itens.count()

    @property
    def valor_produtos(self):
        total = 0
        for i in self.itens.all():
            total += float(i.valor_total or 0)
        return round(total, 2)

    @property
    def valor_total(self):
        return round(self.valor_produtos + float(self.frete or 0), 2)

    @property
    def pode_receber(self):
        return self.status in ('ENVIADO', 'PARCIAL', 'ABERTO')

    @property
    def pode_editar(self):
        return self.status in ('ABERTO', 'ENVIADO')

    def gerar_numero(self):
        from django.utils import timezone as tz
        ano = tz.localdate().year
        prefixo = f'PED-{ano}-'
        ultimo = (
            PedidoCompra.objects
            .filter(numero__startswith=prefixo)
            .order_by('-numero').values_list('numero', flat=True).first()
        )
        seq = 1
        if ultimo:
            try:
                seq = int(ultimo.split('-')[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        return f'{prefixo}{seq:04d}'


class PedidoCompraItem(models.Model):
    """Um material do pedido, com preco fechado."""

    pedido = models.ForeignKey(
        PedidoCompra, on_delete=models.CASCADE, related_name='itens',
        verbose_name='Pedido',
    )
    produto = models.ForeignKey(
        ProdutoEstoque, on_delete=models.PROTECT, related_name='pedidos_compra',
        verbose_name='Produto',
    )
    quantidade = models.DecimalField(
        max_digits=14, decimal_places=3, verbose_name='Quantidade',
    )
    quantidade_recebida = models.DecimalField(
        max_digits=14, decimal_places=3, default=0, verbose_name='Recebida',
    )
    preco_unitario = models.DecimalField(
        max_digits=12, decimal_places=4, default=0, verbose_name='Preço unitário',
    )
    desconto = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name='Desconto',
    )
    local_destino = models.ForeignKey(
        LocalEstoque, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pedidos_compra', verbose_name='Local de destino',
        help_text='Onde o material entra quando chegar.',
    )
    observacao = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Observação',
    )

    class Meta:
        ordering = ['produto__codigo']
        verbose_name = 'Item do Pedido de Compra'
        verbose_name_plural = 'Itens do Pedido de Compra'

    def __str__(self):
        return f'{self.produto.codigo} x {self.quantidade}'

    @property
    def valor_total(self):
        bruto = float(self.quantidade or 0) * float(self.preco_unitario or 0)
        return round(bruto - float(self.desconto or 0), 2)

    @property
    def pendente(self):
        return (self.quantidade or 0) - (self.quantidade_recebida or 0)

    @property
    def recebido_completo(self):
        return (self.quantidade_recebida or 0) >= (self.quantidade or 0)


# ===========================================================================
# CUSTO POR OP
# ===========================================================================
# O Faktory guardava VL_CUSTODIRETOUN (custo por hora) e o tempo apontado por
# etapa, e daí saía o custo da OP. Ao migrar, esse controle se perdeu.
#
# Aqui o custo e reconstruido de dados que JA existem neste sistema:
#
#   MATERIAL      MovimentoEstoque com origem=PRODUCAO ligado a OP
#                 -> quanto de perfil/vidro/componente a OP consumiu
#   MAO DE OBRA   MovimentacaoOP.data_entrada / data_saida por setor
#                 -> quantas horas a OP passou em cada setor
#   INDIRETO      rateio por hora (energia, aluguel, supervisao)
#
# O numero que importa no fim: CUSTO UNITARIO. Numa esquadria o que decide o
# preco e quanto custou cada peca — nao o total da OP.
# ===========================================================================

# Custo por hora de cada setor. Vem da realidade da fabrica: o que a hora de
# trabalho custa naquele posto (salario + encargos + maquina).
CUSTO_HORA_SETOR_PADRAO = {
    'separacao': 32.0,
    'corte': 48.0,
    'usinagem': 52.0,
    'mesa': 45.0,
    'encaixilhamento': 50.0,
    'expedicao': 35.0,
    'estoque': 28.0,
}


class CustoSetor(models.Model):
    """Quanto custa a hora de trabalho em cada setor.

    E o que permite transformar TEMPO em DINHEIRO. Sem isso o rastreio mede
    tempo mas nao diz quanto custou.
    """

    setor = models.CharField(
        max_length=30, unique=True, verbose_name='Setor',
        help_text='Código do setor, igual ao usado no rastreio.',
    )
    nome = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Nome',
    )
    custo_hora = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Custo por hora (R$)',
        help_text='Salário + encargos + máquina, por hora.',
    )
    custo_hora_indireto = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Custo indireto por hora (R$)',
        help_text='Rateio de energia, aluguel, supervisão por hora.',
    )
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    class Meta:
        ordering = ['setor']
        verbose_name = 'Custo por Setor'
        verbose_name_plural = 'Custos por Setor'

    def __str__(self):
        return f'{self.nome or self.setor} — R$ {self.custo_hora}/h'

    @property
    def custo_hora_total(self):
        return float(self.custo_hora or 0) + float(self.custo_hora_indireto or 0)

    @classmethod
    def custo_do_setor(cls, setor):
        """Custo/hora do setor, caindo no padrao da fabrica se nao cadastrado.

        Assim o custo funciona desde o primeiro dia, sem cadastro previo —
        e o cadastro serve para afinar o numero com o valor real.
        """
        c = cls.objects.filter(setor=setor, ativo=True).first()
        if c:
            return float(c.custo_hora or 0), float(c.custo_hora_indireto or 0)
        padrao = CUSTO_HORA_SETOR_PADRAO.get(setor, 40.0)
        return padrao, round(padrao * 0.35, 2)


class CustoOP(models.Model):
    """O custo consolidado de uma OP — o que ela custou de verdade.

    Calculado a partir do rastreio (tempo) e do estoque (material). Pode ser
    recalculado a qualquer momento: e um retrato, nao um lancamento contabil.
    """

    obra_op = models.OneToOneField(
        ObraOP, on_delete=models.CASCADE, related_name='custo',
        verbose_name='OP',
    )
    rastreio = models.ForeignKey(
        RastreioOP, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='custos', verbose_name='Rastreio',
    )

    # --- material (vem do estoque) ---
    custo_material = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Custo de material (R$)',
        help_text='Perfil, vidro e componentes consumidos, pelo custo do estoque.',
    )

    # --- mao de obra (vem do tempo no rastreio) ---
    horas_totais = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Horas totais de produção',
    )
    custo_mao_obra = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Custo de mão de obra (R$)',
    )

    # --- indireto (rateio) ---
    custo_indireto = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Custo indireto (R$)',
        help_text='Energia, aluguel e supervisão rateados pelo tempo.',
    )

    # --- resultado ---
    custo_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, verbose_name='Custo total (R$)',
    )
    quantidade = models.PositiveIntegerField(
        default=1, verbose_name='Quantidade de peças',
    )
    custo_unitario = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Custo por peça (R$)',
        help_text='O número que decide o preço de venda.',
    )

    # --- comparacao com a venda ---
    valor_venda = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Valor de venda (R$)', null=True, blank=True,
    )

    calculado_em = models.DateTimeField(
        auto_now=True, verbose_name='Calculado em',
    )
    calculado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='custos_calculados', verbose_name='Calculado por',
    )
    observacao = models.TextField(
        blank=True, default='', verbose_name='Observação',
    )

    class Meta:
        ordering = ['-calculado_em']
        verbose_name = 'Custo de OP'
        verbose_name_plural = 'Custos de OP'

    def __str__(self):
        return f'{self.obra_op.codigo_formatado} — R$ {self.custo_total}'

    # -----------------------------------------------------------------
    # Resultado
    # -----------------------------------------------------------------

    @property
    def margem(self):
        """Quanto sobra da venda depois do custo (R$)."""
        if not self.valor_venda:
            return None
        return round(float(self.valor_venda) - float(self.custo_total or 0), 2)

    @property
    def margem_percentual(self):
        """Margem sobre a venda (%). Abaixo de 20% acende o alerta."""
        if not self.valor_venda or float(self.valor_venda) == 0:
            return None
        return round((self.margem / float(self.valor_venda)) * 100, 1)

    @property
    def margem_classe(self):
        """Classe CSS conforme a margem — verde, amarelo ou vermelho."""
        m = self.margem_percentual
        if m is None:
            return 'margem-neutra'
        if m >= 35:
            return 'margem-boa'
        if m >= 20:
            return 'margem-atencao'
        return 'margem-ruim'

    @property
    def prejuizo(self):
        m = self.margem
        return m is not None and m < 0

    # -----------------------------------------------------------------
    # Composicao do custo (para o gráfico de barras)
    # -----------------------------------------------------------------

    @property
    def composicao(self):
        """As tres parcelas do custo, com o percentual de cada uma.

        Serve para responder a pergunta que mais aparece na pratica:
        "o que esta pesando mais nesta OP — material ou tempo?"
        """
        total = float(self.custo_total or 0)
        if total <= 0:
            return []
        parcelas = [
            ('Material', float(self.custo_material or 0), 'mat'),
            ('Mão de obra', float(self.custo_mao_obra or 0), 'mo'),
            ('Indireto', float(self.custo_indireto or 0), 'ind'),
        ]
        return [
            {'nome': nome, 'valor': round(v, 2), 'classe': cls,
             'percentual': round((v / total) * 100, 1)}
            for nome, v, cls in parcelas if v > 0
        ]

    @property
    def parcela_dominante(self):
        """O que pesa mais no custo desta OP."""
        c = self.composicao
        if not c:
            return None
        return max(c, key=lambda x: x['valor'])['nome']


class CustoOPSetor(models.Model):
    """Quanto tempo e quanto custo cada setor consumiu de uma OP.

    E o detalhamento que mostra ONDE o dinheiro foi gasto. Sem isso voce sabe
    que a OP custou R$ 500, mas nao sabe que R$ 300 foram na mesa.
    """

    custo_op = models.ForeignKey(
        CustoOP, on_delete=models.CASCADE, related_name='setores',
        verbose_name='Custo da OP',
    )
    setor = models.CharField(max_length=30, verbose_name='Setor')
    setor_nome = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Nome do setor',
    )
    minutos = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name='Minutos',
    )
    horas = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name='Horas',
    )
    custo_hora = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name='Custo/hora (R$)',
    )
    custo = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, verbose_name='Custo (R$)',
    )
    quantidade_produzida = models.PositiveIntegerField(
        default=0, verbose_name='Peças produzidas',
    )

    class Meta:
        ordering = ['-custo']
        verbose_name = 'Custo por Setor da OP'
        verbose_name_plural = 'Custos por Setor da OP'

    def __str__(self):
        return f'{self.setor_nome} — R$ {self.custo}'

    @property
    def tempo_formatado(self):
        m = float(self.minutos or 0)
        if m < 60:
            return f'{int(m)}min'
        h, mi = int(m // 60), int(m % 60)
        return f'{h}h {mi}min' if mi else f'{h}h'

    @property
    def percentual(self):
        """Quanto este setor representa do custo de mão de obra."""
        try:
            total = float(self.custo_op.custo_mao_obra or 0)
        except Exception:
            return 0
        if total <= 0:
            return 0
        return round((float(self.custo or 0) / total) * 100, 1)


class CustoOPMaterial(models.Model):
    """O material que a OP consumiu, item a item, com o custo de cada um."""

    custo_op = models.ForeignKey(
        CustoOP, on_delete=models.CASCADE, related_name='materiais',
        verbose_name='Custo da OP',
    )
    produto = models.ForeignKey(
        ProdutoEstoque, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='custos_op', verbose_name='Produto',
    )
    codigo = models.CharField(
        max_length=60, blank=True, default='', verbose_name='Código',
    )
    descricao = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Descrição',
    )
    quantidade = models.DecimalField(
        max_digits=14, decimal_places=3, default=0, verbose_name='Quantidade',
    )
    unidade = models.CharField(
        max_length=10, blank=True, default='UN', verbose_name='Unidade',
    )
    valor_unitario = models.DecimalField(
        max_digits=12, decimal_places=4, default=0, verbose_name='Valor unitário',
    )
    custo = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, verbose_name='Custo (R$)',
    )

    class Meta:
        ordering = ['-custo']
        verbose_name = 'Material da OP'
        verbose_name_plural = 'Materiais da OP'

    def __str__(self):
        return f'{self.codigo} x {self.quantidade} = R$ {self.custo}'

    @property
    def percentual(self):
        try:
            total = float(self.custo_op.custo_material or 0)
        except Exception:
            return 0
        if total <= 0:
            return 0
        return round((float(self.custo or 0) / total) * 100, 1)


# ===========================================================================
# VENDA
# ===========================================================================
# Importado de PEDIDOVENDA / PROPOSTA do ERP. Sao 3.808 pedidos e 2.327
# propostas — o comercial da fabrica inteiro.
#
# Por que importar venda num sistema de producao: e o que amarra o dinheiro
# a fabrica. O pedido de venda vira OP, a OP consome material e gera custo.
# Sem o pedido, o custo da OP fica solto — sabe-se quanto custou, mas nao
# quanto foi vendido.
# ===========================================================================

STATUS_VENDA = [
    ('ABERTO', 'Aberto'),
    ('PARCIAL', 'Parcial'),
    ('ATENDIDO', 'Atendido'),
    ('FATURADO', 'Faturado'),
    ('CANCELADO', 'Cancelado'),
]


class VendaPedido(models.Model):
    """Pedido de venda — o que o cliente comprou."""

    numero = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Número',
    )
    cliente_nome = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Cliente',
    )
    participante_codigo = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Cód. cliente',
    )
    data_cadastro = models.DateField(
        null=True, blank=True, verbose_name='Data',
    )
    data_finalizacao = models.DateField(
        null=True, blank=True, verbose_name='Finalização',
    )
    status = models.CharField(
        max_length=12, choices=STATUS_VENDA, default='ABERTO', verbose_name='Status',
    )
    valor_total = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, verbose_name='Valor total (R$)',
    )
    observacao = models.TextField(
        blank=True, default='', verbose_name='Observação',
    )
    obra = models.ForeignKey(
        Obra, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='vendas', verbose_name='Obra',
        help_text='Ligação com a obra quando o pedido virou produção.',
    )
    codigo_faktory = models.CharField(
        max_length=40, blank=True, default='', db_index=True,
        verbose_name='Código no Faktory',
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Importado em')

    class Meta:
        ordering = ['-data_cadastro', '-id']
        verbose_name = 'Pedido de Venda'
        verbose_name_plural = 'Pedidos de Venda'

    def __str__(self):
        return f'{self.numero} — {self.cliente_nome[:30]}'

    @property
    def status_nome(self):
        return dict(STATUS_VENDA).get(self.status, self.status)

    @property
    def status_classe(self):
        return {
            'ABERTO': 'req-aberta', 'PARCIAL': 'req-cotacao',
            'ATENDIDO': 'req-atendida', 'FATURADO': 'req-pedido',
            'CANCELADO': 'req-cancelada',
        }.get(self.status, 'req-aberta')

    @property
    def total_itens(self):
        return self.itens.count()

    @property
    def valor_calculado(self):
        """Soma dos itens — confere o valor_total importado."""
        return round(sum(float(i.valor_total or 0) for i in self.itens.all()), 2)


class VendaPedidoItem(models.Model):
    """Um item do pedido de venda."""

    pedido = models.ForeignKey(
        VendaPedido, on_delete=models.CASCADE, related_name='itens',
        verbose_name='Pedido',
    )
    produto_codigo = models.CharField(
        max_length=60, blank=True, default='', verbose_name='Código',
    )
    descricao = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Descrição',
    )
    quantidade = models.DecimalField(
        max_digits=14, decimal_places=3, default=0, verbose_name='Quantidade',
    )
    valor_unitario = models.DecimalField(
        max_digits=14, decimal_places=4, default=0, verbose_name='Valor unitário',
    )
    valor_total = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, verbose_name='Total',
    )
    data_entrega = models.DateField(
        null=True, blank=True, verbose_name='Entrega',
    )
    produto = models.ForeignKey(
        ProdutoEstoque, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='vendas', verbose_name='Produto do estoque',
    )
    codigo_faktory = models.CharField(
        max_length=40, blank=True, default='', db_index=True,
        verbose_name='Código no Faktory',
    )

    class Meta:
        ordering = ['produto_codigo']
        verbose_name = 'Item do Pedido de Venda'
        verbose_name_plural = 'Itens do Pedido de Venda'

    def __str__(self):
        return f'{self.produto_codigo} x {self.quantidade}'


class VendaProposta(models.Model):
    """Proposta comercial — o que ainda nao virou pedido."""

    numero = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Número',
    )
    cliente_nome = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Cliente',
    )
    data_cadastro = models.DateField(
        null=True, blank=True, verbose_name='Data',
    )
    valor_total = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, verbose_name='Valor total (R$)',
    )
    status = models.CharField(
        max_length=12, choices=STATUS_VENDA, default='ABERTO', verbose_name='Status',
    )
    codigo_faktory = models.CharField(
        max_length=40, blank=True, default='', db_index=True,
        verbose_name='Código no Faktory',
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Importado em')

    class Meta:
        ordering = ['-data_cadastro', '-id']
        verbose_name = 'Proposta'
        verbose_name_plural = 'Propostas'

    def __str__(self):
        return f'{self.numero} — {self.cliente_nome[:30]}'

    @property
    def status_nome(self):
        return dict(STATUS_VENDA).get(self.status, self.status)


class VendaPropostaItem(models.Model):
    """Item da proposta."""

    proposta = models.ForeignKey(
        VendaProposta, on_delete=models.CASCADE, related_name='itens',
        verbose_name='Proposta',
    )
    produto_codigo = models.CharField(
        max_length=60, blank=True, default='', verbose_name='Código',
    )
    descricao = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Descrição',
    )
    quantidade = models.DecimalField(
        max_digits=14, decimal_places=3, default=0, verbose_name='Quantidade',
    )
    valor_unitario = models.DecimalField(
        max_digits=14, decimal_places=4, default=0, verbose_name='Valor unitário',
    )
    valor_total = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, verbose_name='Total',
    )
    codigo_faktory = models.CharField(
        max_length=40, blank=True, default='', db_index=True,
        verbose_name='Código no Faktory',
    )

    class Meta:
        ordering = ['produto_codigo']
        verbose_name = 'Item da Proposta'
        verbose_name_plural = 'Itens da Proposta'

    def __str__(self):
        return f'{self.produto_codigo} x {self.quantidade}'


# ===========================================================================
# FINANCEIRO
# ===========================================================================
# CPTITULO (94.414) e CRTITULO (11.108) do ERP: contas a pagar e a receber,
# com as baixas. E o dinheiro da fabrica.
#
# O valor esta guardado em coluna propria (como no estoque) para o total
# fechar exatamente com o ERP — derivar de saldo x valor acumula erro.
# ===========================================================================

STATUS_TITULO = [
    ('ABERTO', 'Em aberto'),
    ('PARCIAL', 'Parcial'),
    ('PAGO', 'Pago'),
    ('RECEBIDO', 'Recebido'),
    ('CANCELADO', 'Cancelado'),
]


class ContaPagar(models.Model):
    """Título a pagar — o que a fabrica deve."""

    numero = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Número',
    )
    parcela = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Parcela',
    )
    fornecedor_nome = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Fornecedor',
    )
    fornecedor = models.ForeignKey(
        Fornecedor, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contas_pagar', verbose_name='Fornecedor cadastrado',
    )
    data_emissao = models.DateField(null=True, blank=True, verbose_name='Emissão')
    data_vencimento = models.DateField(
        null=True, blank=True, db_index=True, verbose_name='Vencimento',
    )
    valor = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, verbose_name='Valor (R$)',
    )
    valor_pago = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, verbose_name='Pago (R$)',
    )
    data_pagamento = models.DateField(
        null=True, blank=True, verbose_name='Pagamento',
    )
    status = models.CharField(
        max_length=12, choices=STATUS_TITULO, default='ABERTO', verbose_name='Status',
    )
    observacao = models.TextField(
        blank=True, default='', verbose_name='Observação',
    )
    pedido_compra = models.ForeignKey(
        PedidoCompra, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contas_pagar', verbose_name='Pedido de compra',
    )
    codigo_faktory = models.CharField(
        max_length=40, blank=True, default='', db_index=True,
        verbose_name='Código no Faktory',
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Importado em')

    class Meta:
        ordering = ['-data_vencimento', '-id']
        verbose_name = 'Conta a Pagar'
        verbose_name_plural = 'Contas a Pagar'

    def __str__(self):
        return f'{self.numero} — R$ {self.valor}'

    @property
    def status_nome(self):
        return dict(STATUS_TITULO).get(self.status, self.status)

    @property
    def saldo(self):
        return round(float(self.valor or 0) - float(self.valor_pago or 0), 2)

    @property
    def atrasado(self):
        from django.utils import timezone
        if self.status in ('PAGO', 'CANCELADO') or not self.data_vencimento:
            return False
        return self.data_vencimento < timezone.localdate()

    @property
    def status_classe(self):
        if self.status in ('PAGO', 'RECEBIDO'):
            return 'req-atendida'
        if self.atrasado:
            return 'req-cancelada'
        if self.status == 'PARCIAL':
            return 'req-cotacao'
        return 'req-aberta'


class ContaReceber(models.Model):
    """Título a receber — o que devem para a fabrica."""

    numero = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Número',
    )
    parcela = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Parcela',
    )
    cliente_nome = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Cliente',
    )
    data_emissao = models.DateField(null=True, blank=True, verbose_name='Emissão')
    data_vencimento = models.DateField(
        null=True, blank=True, db_index=True, verbose_name='Vencimento',
    )
    valor = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, verbose_name='Valor (R$)',
    )
    valor_recebido = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, verbose_name='Recebido (R$)',
    )
    data_recebimento = models.DateField(
        null=True, blank=True, verbose_name='Recebimento',
    )
    status = models.CharField(
        max_length=12, choices=STATUS_TITULO, default='ABERTO', verbose_name='Status',
    )
    observacao = models.TextField(
        blank=True, default='', verbose_name='Observação',
    )
    venda = models.ForeignKey(
        VendaPedido, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contas_receber', verbose_name='Pedido de venda',
    )
    codigo_faktory = models.CharField(
        max_length=40, blank=True, default='', db_index=True,
        verbose_name='Código no Faktory',
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Importado em')

    class Meta:
        ordering = ['-data_vencimento', '-id']
        verbose_name = 'Conta a Receber'
        verbose_name_plural = 'Contas a Receber'

    def __str__(self):
        return f'{self.numero} — R$ {self.valor}'

    @property
    def status_nome(self):
        return dict(STATUS_TITULO).get(self.status, self.status)

    @property
    def saldo(self):
        return round(float(self.valor or 0) - float(self.valor_recebido or 0), 2)

    @property
    def atrasado(self):
        from django.utils import timezone
        if self.status in ('RECEBIDO', 'CANCELADO') or not self.data_vencimento:
            return False
        return self.data_vencimento < timezone.localdate()

    @property
    def status_classe(self):
        if self.status == 'RECEBIDO':
            return 'req-atendida'
        if self.atrasado:
            return 'req-cancelada'
        if self.status == 'PARCIAL':
            return 'req-cotacao'
        return 'req-aberta'


# ===========================================================================
# NOTA FISCAL
# ===========================================================================
# 65.356 notas com 203.130 itens. O sistema nao emite NF-e (isso exige
# certificacao SEFAZ), mas CONSULTAR o que ja foi faturado e essencial:
# e o documento que liga venda, estoque e financeiro.
# ===========================================================================

TIPO_NOTA = [
    ('ENTRADA', 'Entrada'),
    ('SAIDA', 'Saída'),
]


class NotaFiscal(models.Model):
    """Nota fiscal — historico do que foi faturado."""

    numero = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Número',
    )
    serie = models.CharField(
        max_length=10, blank=True, default='', verbose_name='Série',
    )
    tipo = models.CharField(
        max_length=10, choices=TIPO_NOTA, default='SAIDA', verbose_name='Tipo',
    )
    participante_nome = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Cliente/Fornecedor',
    )
    data_emissao = models.DateField(
        null=True, blank=True, db_index=True, verbose_name='Emissão',
    )
    valor_produtos = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, verbose_name='Produtos (R$)',
    )
    valor_desconto = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, verbose_name='Desconto (R$)',
    )
    valor_frete = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, verbose_name='Frete (R$)',
    )
    valor_total = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, verbose_name='Total (R$)',
    )
    chave_acesso = models.CharField(
        max_length=60, blank=True, default='', verbose_name='Chave de acesso',
    )
    status = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Situação',
    )
    codigo_faktory = models.CharField(
        max_length=40, blank=True, default='', db_index=True,
        verbose_name='Código no Faktory',
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Importado em')

    class Meta:
        ordering = ['-data_emissao', '-id']
        verbose_name = 'Nota Fiscal'
        verbose_name_plural = 'Notas Fiscais'

    def __str__(self):
        return f'NF {self.numero}/{self.serie} — {self.participante_nome[:28]}'

    @property
    def total_itens(self):
        return self.itens.count()


class NotaFiscalItem(models.Model):
    """Item da nota fiscal."""

    nota = models.ForeignKey(
        NotaFiscal, on_delete=models.CASCADE, related_name='itens',
        verbose_name='Nota',
    )
    produto_codigo = models.CharField(
        max_length=60, blank=True, default='', verbose_name='Código',
    )
    descricao = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Descrição',
    )
    quantidade = models.DecimalField(
        max_digits=14, decimal_places=3, default=0, verbose_name='Quantidade',
    )
    valor_unitario = models.DecimalField(
        max_digits=14, decimal_places=4, default=0, verbose_name='Valor unitário',
    )
    valor_total = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, verbose_name='Total',
    )
    codigo_faktory = models.CharField(
        max_length=40, blank=True, default='', db_index=True,
        verbose_name='Código no Faktory',
    )

    class Meta:
        ordering = ['produto_codigo']
        verbose_name = 'Item da Nota Fiscal'
        verbose_name_plural = 'Itens da Nota Fiscal'

    def __str__(self):
        return f'{self.produto_codigo} x {self.quantidade}'


# ===========================================================================
# MOVIMENTO DE ESTOQUE HISTORICO
# ===========================================================================
# 307.932 movimentos do ERP. O nosso MovimentoEstoque e o movimento VIVO
# (que mexe no saldo). Este aqui e o HISTORICO importado: consulta e
# rastreabilidade, sem tocar no saldo atual (que ja veio correto).
# ===========================================================================

class MovimentoEstoqueHistorico(models.Model):
    """Movimento de estoque importado do ERP (histórico, não mexe no saldo)."""

    produto_codigo = models.CharField(
        max_length=60, blank=True, default='', db_index=True, verbose_name='Código',
    )
    produto_descricao = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Descrição',
    )
    local_nome = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Local',
    )
    tipo = models.CharField(
        max_length=10, blank=True, default='', verbose_name='Tipo',
    )
    origem = models.CharField(
        max_length=60, blank=True, default='', verbose_name='Origem',
    )
    data_movimento = models.DateTimeField(
        null=True, blank=True, db_index=True, verbose_name='Data',
    )
    quantidade = models.DecimalField(
        max_digits=16, decimal_places=3, default=0, verbose_name='Quantidade',
    )
    valor_unitario = models.DecimalField(
        max_digits=16, decimal_places=5, default=0, verbose_name='Valor unitário',
    )
    valor_total = models.DecimalField(
        max_digits=18, decimal_places=5, default=0, verbose_name='Valor total',
    )
    documento = models.CharField(
        max_length=60, blank=True, default='', verbose_name='Documento',
    )
    codigo_faktory = models.CharField(
        max_length=40, blank=True, default='', db_index=True,
        verbose_name='Código no Faktory',
    )

    class Meta:
        ordering = ['-data_movimento', '-id']
        verbose_name = 'Movimento de Estoque (histórico)'
        verbose_name_plural = 'Movimentos de Estoque (histórico)'

    def __str__(self):
        return f'{self.produto_codigo} {self.quantidade} ({self.data_movimento:%d/%m/%Y})'


# ===========================================================================
# ESTRUTURA DO PRODUTO
# ===========================================================================
# ESTRUTURA (13.342) + ESTRUTURACOMPONENTE (13.383): a composicao de cada
# esquadria — quais perfis, vidros e componentes ela leva.
#
# Isso e o que permite EXPLODIR a OP: sabendo a esquadria, sabe-se o material
# necessario. Sem a estrutura, o custo da OP depende de alguem lancar o
# consumo a mao.
# ===========================================================================

class EstruturaProduto(models.Model):
    """Composição de um produto: o que ele leva."""

    produto_codigo = models.CharField(
        max_length=60, blank=True, default='', db_index=True, verbose_name='Produto',
    )
    produto_descricao = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Descrição',
    )
    quantidade = models.DecimalField(
        max_digits=14, decimal_places=3, default=1, verbose_name='Quantidade base',
    )
    codigo_faktory = models.CharField(
        max_length=40, blank=True, default='', db_index=True,
        verbose_name='Código no Faktory',
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Importado em')

    class Meta:
        ordering = ['produto_codigo']
        verbose_name = 'Estrutura do Produto'
        verbose_name_plural = 'Estruturas dos Produtos'

    def __str__(self):
        return f'{self.produto_codigo}'

    @property
    def total_componentes(self):
        return self.componentes.count()


class EstruturaComponente(models.Model):
    """Um componente da estrutura: perfil, vidro ou acessório."""

    estrutura = models.ForeignKey(
        EstruturaProduto, on_delete=models.CASCADE, related_name='componentes',
        verbose_name='Estrutura',
    )
    componente_codigo = models.CharField(
        max_length=60, blank=True, default='', verbose_name='Componente',
    )
    componente_descricao = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Descrição',
    )
    quantidade = models.DecimalField(
        max_digits=14, decimal_places=5, default=0, verbose_name='Quantidade',
    )
    unidade = models.CharField(
        max_length=10, blank=True, default='', verbose_name='Unidade',
    )
    codigo_faktory = models.CharField(
        max_length=40, blank=True, default='', db_index=True,
        verbose_name='Código no Faktory',
    )

    class Meta:
        ordering = ['componente_codigo']
        verbose_name = 'Componente da Estrutura'
        verbose_name_plural = 'Componentes da Estrutura'

    def __str__(self):
        return f'{self.componente_codigo} x {self.quantidade}'


# ===========================================================================
# FUNCIONARIO
# ===========================================================================
# 414 funcionarios no ERP, 109 com VL_HORA preenchido. O valor/hora e o que
# permite calcular o custo de mao de obra por OP usando o valor REAL da
# fabrica em vez de um chute.
# ===========================================================================

class Funcionario(models.Model):
    """Funcionário da fábrica."""

    nome = models.CharField(max_length=200, verbose_name='Nome')
    cpf = models.CharField(
        max_length=20, blank=True, default='', verbose_name='CPF',
    )
    setor = models.CharField(
        max_length=80, blank=True, default='', verbose_name='Setor',
    )
    cargo = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Cargo',
    )
    data_admissao = models.DateField(
        null=True, blank=True, verbose_name='Admissão',
    )
    valor_hora = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Valor/hora (R$)',
        help_text='Custo da hora deste funcionário, como no ERP.',
    )
    telefone = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Telefone',
    )
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    usuario = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='funcionario', verbose_name='Usuário do sistema',
        help_text='Vincula o funcionário ao login do Casanova System.',
    )
    codigo_faktory = models.CharField(
        max_length=40, blank=True, default='', db_index=True,
        verbose_name='Código no Faktory',
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Importado em')

    class Meta:
        ordering = ['nome']
        verbose_name = 'Funcionário'
        verbose_name_plural = 'Funcionários'

    def __str__(self):
        return f'{self.nome} ({self.setor or "sem setor"})'

    @property
    def tem_hora(self):
        return float(self.valor_hora or 0) > 0
