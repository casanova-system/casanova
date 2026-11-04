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