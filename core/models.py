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
    ('001', 'Custo de Frete', 'lista_obras', 'ROTINA', 'COMERCIAL'),
    ('002', 'Cadastro de Usuário', 'lista_usuarios', 'ROTINA', 'ADMINISTRADOR'),
    ('003', 'Cadastro de Veículo', 'lista_veiculos', 'ROTINA', 'FROTAS'),
    ('004', 'Cadastro de Custo', 'lista_custo', 'ROTINA', 'FINANCEIRO'),
    ('005', 'Gerenciar Permissões', 'lista_permissao', 'ROTINA', 'ADMINISTRADOR'),
    ('006', 'Gráfico de Custo de Frete', 'grafico_custo_frete', 'GRAFICO', 'COMERCIAL'),
    ('007', 'Relatório de Fretes do Mês', 'relatorio_fretes_mes', 'RELATORIO', 'COMERCIAL'),
    ('008', 'Ordem de Produção (OP)', 'lista_ordem_producao', 'ROTINA', 'INDUSTRIA'),
    ('009', 'Rastreio de Produção', 'rastreio_producao', 'ROTINA', 'INDUSTRIA'),
    ('010', 'Produção', 'producao', 'ROTINA', 'INDUSTRIA'),
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
        """Retorna o tempo (em minutos) que a OP está no setor atual."""
        if not self.setor_atual or self.concluida:
            return None
        from django.utils import timezone
        agora = timezone.now()
        # Busca a última movimentação de entrada no setor atual
        ultima_entrada = self.movimentacoes.filter(
            setor=self.setor_atual
        ).order_by('-data_hora').first()
        if ultima_entrada:
            return (agora - ultima_entrada.data_hora).total_seconds() / 60
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

    def tempo_no_setor(self, codigo_setor):
        """Retorna o tempo (em minutos) que a OP ficou em um setor específico."""
        from django.utils import timezone
        movimentacoes = self.movimentacoes.filter(setor=codigo_setor).order_by('data_hora')
        total_minutos = 0
        for mov in movimentacoes:
            if mov.data_entrada and mov.data_saida:
                total_minutos += (mov.data_saida - mov.data_entrada).total_seconds() / 60
            elif mov.data_entrada and not mov.data_saida:
                # Setor atual - calcula até agora
                total_minutos += (timezone.now() - mov.data_entrada).total_seconds() / 60
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
    usuario = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Usuário'
    )
    observacao = models.CharField(max_length=255, blank=True, default='', verbose_name='Observação')
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