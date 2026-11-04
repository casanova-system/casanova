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