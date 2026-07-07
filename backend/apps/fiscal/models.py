from decimal import Decimal

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models

from .modelo_operacional import DestinoFisico, OrigemFisica, StatusEntradaFiscal, TipoAtendimentoItem


class EstoqueCorrida(models.Model):
    produto = models.ForeignKey('produtos.Produto', on_delete=models.CASCADE, related_name='estoques_corrida')
    corrida = models.ForeignKey('corridas.Corrida', on_delete=models.CASCADE, related_name='estoques')
    saldo = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))

    class Meta:
        unique_together = [['produto', 'corrida']]
        ordering = ['produto_id', 'corrida_id']


class NFeEntrada(models.Model):
    class TipoOrigem(models.TextChoices):
        MANUAL = 'MANUAL', 'Manual'
        ENTRADA_PROPRIA_IMPORTADA = 'ENTRADA_PROPRIA_IMPORTADA', 'Entrada própria importada'
        ENTRADA_PROPRIA_EMITIDA = 'ENTRADA_PROPRIA_EMITIDA', 'Entrada própria emitida'

    class StatusOperacional(models.TextChoices):
        RASCUNHO = 'RASCUNHO', 'Rascunho'
        EM_CONFERENCIA = 'EM_CONFERENCIA', 'Em conferência'
        PRONTA_HOMOLOGACAO = 'PRONTA_HOMOLOGACAO', 'Pronta homologação'
        AUTORIZADA_HOMOLOGACAO = 'AUTORIZADA_HOMOLOGACAO', 'Autorizada homologação'
        REJEITADA = 'REJEITADA', 'Rejeitada'
        ERRO_TRANSMISSAO = 'ERRO_TRANSMISSAO', 'Erro transmissão'
        IMPORTADA_PENDENTE_CONFERENCIA = (
            'IMPORTADA_PENDENTE_CONFERENCIA',
            'Importada — pendente conferência',
        )

    class AmbienteEmissao(models.TextChoices):
        HOMOLOGACAO = 'homologacao', 'Homologação'
        PRODUCAO = 'producao', 'Produção'

    class StatusEmissaoSefaz(models.TextChoices):
        NUMERACAO_RESERVADA = 'NUMERACAO_RESERVADA', 'Numeração reservada'
        XML_GERADO = 'XML_GERADO', 'XML oficial gerado'
        XML_ASSINADO = 'XML_ASSINADO', 'XML assinado'
        ENVIADA_HOMOLOGACAO = 'ENVIADA_HOMOLOGACAO', 'Enviada homologação'
        AUTORIZADA_HOMOLOGACAO = 'AUTORIZADA_HOMOLOGACAO', 'Autorizada homologação'
        REJEITADA_HOMOLOGACAO = 'REJEITADA_HOMOLOGACAO', 'Rejeitada homologação'
        ERRO_TRANSMISSAO = 'ERRO_TRANSMISSAO', 'Erro transmissão'

    numero = models.CharField(max_length=64)
    serie = models.CharField(max_length=4, blank=True)
    chave_acesso = models.CharField(max_length=44, blank=True, db_index=True)
    fornecedor = models.ForeignKey(
        'cadastros.Fornecedor',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='nf_entradas',
    )
    empresa_emitente = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_entradas_proprias_emitidas',
    )
    cliente_destinatario = models.ForeignKey(
        'cadastros.Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_entradas_proprias_destinatario',
    )
    data = models.DateField()
    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    tipo_origem = models.CharField(
        max_length=32,
        choices=TipoOrigem.choices,
        default=TipoOrigem.MANUAL,
    )
    status_operacional = models.CharField(
        max_length=40,
        choices=StatusOperacional.choices,
        default=StatusOperacional.RASCUNHO,
    )
    emit_json = models.JSONField(default=dict, blank=True)
    dest_json = models.JSONField(default=dict, blank=True)
    itens_json = models.JSONField(default=list, blank=True)
    xml_importado = models.TextField(blank=True)
    nome_arquivo = models.CharField(max_length=255, blank=True)
    importado_em = models.DateTimeField(null=True, blank=True)
    pedido_compra = models.ForeignKey(
        'comercial.PedidoCompra',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_entradas',
    )
    cte = models.ForeignKey(
        'fiscal.CTeEntrada',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_entradas_vinculadas',
    )

    # ERP 4.0.15.0 — emissão entrada própria (fundação; sem transmissão nesta fase)
    ambiente_emissao = models.CharField(
        max_length=16,
        choices=AmbienteEmissao.choices,
        default=AmbienteEmissao.HOMOLOGACAO,
        blank=True,
    )
    fin_nfe = models.CharField(max_length=1, blank=True)
    nat_op = models.CharField(max_length=60, blank=True)
    chave_nfe_referenciada = models.CharField(max_length=44, blank=True)
    serie_nfe = models.CharField(max_length=3, blank=True)
    numero_nfe = models.CharField(
        max_length=9,
        blank=True,
        help_text='Número fiscal (nNF) — distinto do número interno.',
    )
    codigo_numerico = models.CharField(max_length=8, blank=True)
    digito_verificador = models.CharField(max_length=1, blank=True)
    numero_reservado_em = models.DateTimeField(null=True, blank=True)
    numero_reservado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_entradas_numeracao_reservada',
    )
    status_emissao_sefaz = models.CharField(
        max_length=32,
        choices=StatusEmissaoSefaz.choices,
        blank=True,
    )
    xml_nfe_gerado = models.TextField(blank=True)
    xml_assinado = models.TextField(blank=True)
    xml_envio = models.TextField(blank=True)
    xml_retorno = models.TextField(blank=True)
    xml_autorizado = models.TextField(blank=True)
    xml_retorno_lote = models.TextField(blank=True)
    xml_protocolo = models.TextField(blank=True)
    xml_envio_lote = models.TextField(blank=True)
    protocolo_autorizacao = models.CharField(max_length=20, blank=True)
    autorizada_em = models.DateTimeField(null=True, blank=True)
    cstat_autorizacao = models.CharField(max_length=4, blank=True)
    motivo_autorizacao = models.TextField(blank=True)
    cstat_lote = models.CharField(max_length=4, blank=True)
    xmotivo_lote = models.TextField(blank=True)
    recibo_lote = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ['-data', 'numero']
        verbose_name = 'NF entrada'
        constraints = [
            models.UniqueConstraint(
                fields=['chave_acesso'],
                condition=~models.Q(chave_acesso=''),
                name='uniq_nf_entrada_chave_acesso_nao_vazia',
            ),
        ]


class ItemNFeEntrada(models.Model):
    nf = models.ForeignKey(NFeEntrada, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey('produtos.Produto', on_delete=models.PROTECT)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3)
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    corrida = models.ForeignKey(
        'corridas.Corrida',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    snapshot_produto = models.JSONField(default=dict, blank=True)
    numero_item = models.PositiveSmallIntegerField(null=True, blank=True)
    ncm = models.CharField(max_length=8, blank=True)
    cfop = models.CharField(max_length=4, blank=True)
    unidade = models.CharField(max_length=6, blank=True)
    descricao_xml = models.CharField(max_length=120, blank=True)
    impostos_json = models.JSONField(default=dict, blank=True)


class NFeSaida(models.Model):
    class ModoAtendimentoEstoque(models.TextChoices):
        IMEDIATO = 'IMEDIATO', 'Baixa física na emissão'
        ANTECIPADO = 'ANTECIPADO', 'Compromisso sem baixa física'

    numero = models.CharField(max_length=64)
    cliente = models.ForeignKey(
        'cadastros.Cliente',
        on_delete=models.PROTECT,
        related_name='nf_saidas',
    )
    data = models.DateField()
    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    modo_atendimento_estoque = models.CharField(
        max_length=16,
        choices=ModoAtendimentoEstoque.choices,
        default=ModoAtendimentoEstoque.IMEDIATO,
    )
    status = models.CharField(max_length=64, blank=True)
    condicao_pagamento_texto = models.CharField(max_length=120, blank=True)
    dias_parcelas = ArrayField(models.IntegerField(), default=list, blank=True)
    quantidade_parcelas = models.PositiveSmallIntegerField(default=0)
    vencimentos_finais = ArrayField(models.DateField(), default=list, blank=True)
    titulos_receber = models.JSONField(default=list, blank=True)
    pedido_venda = models.ForeignKey(
        'comercial.PedidoVenda',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saidas',
    )
    faturamento_pedido_venda = models.ForeignKey(
        'comercial.FaturamentoPedidoVenda',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saidas_geradas',
    )
    observacao_origem = models.TextField(
        blank=True,
        help_text='Observação da geração a partir do faturamento (rascunho).',
    )
    motivo_cancelamento = models.TextField(
        blank=True,
        help_text='Motivo do cancelamento interno (simulação pré-SEFAZ).',
    )
    cancelada_em = models.DateTimeField(null=True, blank=True)
    cancelada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saidas_canceladas',
    )
    efeitos_autorizacao_aplicados_em = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Quando os efeitos operacionais de autorização (interna) foram aplicados.',
    )
    efeitos_cancelamento_aplicados_em = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Quando os efeitos operacionais de cancelamento (interno) foram aplicados.',
    )
    efeitos_cancelamento_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saidas_cancelamento_efeitos',
    )
    transportadora = models.ForeignKey(
        'cadastros.Transportadora',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saidas',
    )
    modalidade_frete = models.CharField(
        max_length=1,
        blank=True,
        default='9',
        help_text='Modalidade do frete (9=sem frete, 0=CIF, 1=FOB, etc.).',
    )
    valor_frete = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    quantidade_volumes = models.PositiveIntegerField(default=0)
    peso_bruto = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    peso_liquido = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    observacoes_nfe = models.TextField(
        blank=True,
        help_text='Observações complementares da NF-e (editáveis em rascunho).',
    )
    informacoes_adicionais = models.TextField(
        blank=True,
        help_text='Informações adicionais de interesse do fisco/contribuinte.',
    )
    pedido_cliente_numero = models.CharField(max_length=64, blank=True)
    pedido_cliente_observacao = models.TextField(blank=True)
    informacoes_fisco = models.TextField(
        blank=True,
        help_text='Informações ao Fisco (prévia/preparatório).',
    )
    observacoes_internas = models.TextField(
        blank=True,
        help_text='Observações internas ERP — não saem no XML/DANFE.',
    )
    especie_volumes = models.CharField(max_length=64, blank=True)
    marca_volumes = models.CharField(max_length=64, blank=True)
    numeracao_volumes = models.CharField(max_length=64, blank=True)
    placa_veiculo = models.CharField(max_length=16, blank=True)
    uf_veiculo = models.CharField(max_length=2, blank=True)
    ind_final = models.CharField(
        max_length=1,
        default='1',
        help_text='Indicador consumidor final (0=Não, 1=Sim).',
    )
    ind_pres = models.CharField(
        max_length=1,
        default='1',
        help_text='Indicador de presença do comprador (tabela NF-e).',
    )
    indicadores_fiscais_confirmados = models.BooleanField(
        default=False,
        help_text='Usuário confirmou indFinal e indPres na conferência.',
    )

    class StatusConferencia(models.TextChoices):
        EM_CONFERENCIA = 'EM_CONFERENCIA', 'Em conferência'
        COM_PENDENCIAS = 'COM_PENDENCIAS', 'Com pendências'
        CONFERIDA = 'CONFERIDA', 'Conferida'
        PRONTA_PARA_EMISSAO = 'PRONTA_PARA_EMISSAO', 'Pronta para emissão'

    status_conferencia = models.CharField(
        max_length=24,
        choices=StatusConferencia.choices,
        default=StatusConferencia.EM_CONFERENCIA,
    )
    conferencia_validada_em = models.DateTimeField(null=True, blank=True)
    conferencia_validada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saidas_conferencia_validadas',
    )
    conferencia_marcada_pronta_em = models.DateTimeField(null=True, blank=True)
    conferencia_marcada_pronta_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saidas_conferencia_prontas',
    )
    conferencia_ultima_mensagem = models.TextField(blank=True)
    xml_preliminar = models.TextField(
        blank=True,
        help_text='XML NF-e 4.00 preliminar (conferência). Não é XML autorizado/assinado.',
    )
    xml_preliminar_gerado_em = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Última geração do XML preliminar.',
    )
    chave_acesso_preliminar = models.CharField(
        max_length=44,
        blank=True,
        db_index=True,
        help_text='Chave calculada do XML preliminar — sem protocolo SEFAZ.',
    )
    serie_fiscal_preliminar = models.CharField(
        max_length=3,
        blank=True,
        help_text='Série fiscal no XML preliminar (homologação).',
    )
    numero_fiscal_preliminar = models.CharField(
        max_length=9,
        blank=True,
        help_text='nNF numérico no XML preliminar (não é o número interno RASCUNHO-*).',
    )

    # NF-e 4.0.2 — emissão SEFAZ (homologação / produção)
    class AmbienteEmissao(models.TextChoices):
        HOMOLOGACAO = 'homologacao', 'Homologação'
        PRODUCAO = 'producao', 'Produção'

    class StatusEmissaoSefaz(models.TextChoices):
        NUMERACAO_RESERVADA = 'NUMERACAO_RESERVADA', 'Numeração reservada'
        XML_GERADO = 'XML_GERADO', 'XML oficial gerado'
        XML_ASSINADO = 'XML_ASSINADO', 'XML assinado'
        ENVIADA_HOMOLOGACAO = 'ENVIADA_HOMOLOGACAO', 'Enviada homologação'
        AUTORIZADA_HOMOLOGACAO = 'AUTORIZADA_HOMOLOGACAO', 'Autorizada homologação'
        REJEITADA_HOMOLOGACAO = 'REJEITADA_HOMOLOGACAO', 'Rejeitada homologação'
        ENVIADA_PRODUCAO = 'ENVIADA_PRODUCAO', 'Enviada produção'
        AUTORIZADA_PRODUCAO = 'AUTORIZADA_PRODUCAO', 'Autorizada produção'
        REJEITADA_PRODUCAO = 'REJEITADA_PRODUCAO', 'Rejeitada produção'
        ERRO_TRANSMISSAO = 'ERRO_TRANSMISSAO', 'Erro transmissão'
        LOTE_PROCESSADO_SEM_PROTOCOLO = 'LOTE_PROCESSADO_SEM_PROTOCOLO', 'Lote processado sem protocolo'
        AGUARDANDO_PROCESSAMENTO = 'AGUARDANDO_PROCESSAMENTO', 'Aguardando processamento SEFAZ'
        ERRO_RETORNO_SEFAZ = 'ERRO_RETORNO_SEFAZ', 'Erro retorno SEFAZ'

    empresa_emitente = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='nf_saidas_emitidas',
    )
    ambiente_emissao = models.CharField(
        max_length=16,
        choices=AmbienteEmissao.choices,
        blank=True,
    )
    serie_nfe = models.CharField(max_length=3, blank=True)
    numero_nfe = models.CharField(
        max_length=9,
        blank=True,
        help_text='Número fiscal (nNF) — numérico, distinto do número interno.',
    )
    codigo_numerico = models.CharField(max_length=8, blank=True)
    chave_acesso = models.CharField(max_length=44, blank=True, db_index=True)
    digito_verificador = models.CharField(max_length=1, blank=True)
    numero_reservado_em = models.DateTimeField(null=True, blank=True)
    numero_reservado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saidas_numeracao_reservada',
    )
    status_emissao_sefaz = models.CharField(
        max_length=32,
        choices=StatusEmissaoSefaz.choices,
        blank=True,
    )
    xml_assinado = models.TextField(blank=True)
    xml_envio = models.TextField(blank=True)
    xml_retorno = models.TextField(blank=True)
    xml_autorizado = models.TextField(
        blank=True,
        help_text='procNFe / XML autorizado com protocolo SEFAZ.',
    )
    protocolo_autorizacao = models.CharField(max_length=20, blank=True)
    autorizada_em = models.DateTimeField(null=True, blank=True)
    cstat_autorizacao = models.CharField(
        max_length=4,
        blank=True,
        help_text='cStat final da NF-e (infProt), não do lote.',
    )
    motivo_autorizacao = models.TextField(
        blank=True,
        help_text='xMotivo final da NF-e (infProt), não do lote.',
    )
    cstat_lote = models.CharField(max_length=4, blank=True)
    xmotivo_lote = models.TextField(blank=True)
    recibo_lote = models.CharField(max_length=20, blank=True)
    xml_retorno_lote = models.TextField(blank=True)
    xml_protocolo = models.TextField(blank=True)
    xml_nfe_gerado = models.TextField(
        blank=True,
        help_text='XML NF-e antes da assinatura (emissão oficial).',
    )
    xml_envio_lote = models.TextField(
        blank=True,
        help_text='XML enviNFe enviado à SEFAZ.',
    )

    class Meta:
        ordering = ['-data', 'numero']
        verbose_name = 'NF saída'


class NFeSaidaEvento(models.Model):
    """Trilha operacional da NF-e Saída (rascunho, efeitos internos — sem SEFAZ)."""

    class TipoEvento(models.TextChoices):
        RASCUNHO_CRIADO = 'RASCUNHO_CRIADO', 'Rascunho criado'
        VALIDADA = 'VALIDADA', 'Validada (pré-emissão)'
        AUTORIZACAO_EFEITOS_APLICADOS = 'AUTORIZACAO_EFEITOS_APLICADOS', 'Efeitos de autorização aplicados (interno)'
        CANCELAMENTO_EFEITOS_APLICADOS = 'CANCELAMENTO_EFEITOS_APLICADOS', 'Efeitos de cancelamento aplicados (interno)'
        CANCELADA = 'CANCELADA', 'Cancelada (interno)'
        ESTORNO_FATURAMENTO = 'ESTORNO_FATURAMENTO', 'Estorno de faturamento vinculado'
        ESTORNO_FATURAMENTO_PRE_AUTORIZACAO_NFE = (
            'ESTORNO_FATURAMENTO_PRE_AUTORIZACAO_NFE',
            'Estorno de faturamento antes da autorização SEFAZ',
        )
        DESCARTE_RASCUNHO_NFE = 'DESCARTE_RASCUNHO_NFE', 'Descarte interno de NF-e rascunho'
        NUMERACAO_LIBERADA_DESCARTE = 'NUMERACAO_LIBERADA_DESCARTE', 'Numeração liberada após descarte local'
        NUMERACAO_REUTILIZADA = 'NUMERACAO_REUTILIZADA', 'Numeração reutilizada de descarte local'
        NUMERACAO_RECUPERADA_LOCALMENTE = (
            'NUMERACAO_RECUPERADA_LOCALMENTE',
            'Numeração recuperada administrativamente (local)',
        )
        IMPOSTOS_ATUALIZADOS = 'IMPOSTOS_ATUALIZADOS', 'Impostos atualizados da regra atual'
        CONFERENCIA_SALVA = 'CONFERENCIA_SALVA', 'Conferência salva'
        CONFERENCIA_VALIDADA = 'CONFERENCIA_VALIDADA', 'Conferência validada'
        CONFERENCIA_COM_PENDENCIAS = 'CONFERENCIA_COM_PENDENCIAS', 'Conferência com pendências'
        PRONTA_PARA_EMISSAO = 'PRONTA_PARA_EMISSAO', 'Pronta para emissão'
        PRONTIDAO_INVALIDADA = 'PRONTIDAO_INVALIDADA', 'Prontidão invalidada'
        OBSERVACAO = 'OBSERVACAO', 'Observação'
        EMISSAO_HOMOLOGACAO_INICIADA = 'EMISSAO_HOMOLOGACAO_INICIADA', 'Emissão homologação iniciada'
        NUMERACAO_RESERVADA = 'NUMERACAO_RESERVADA', 'Numeração reservada'
        XML_OFICIAL_GERADO = 'XML_OFICIAL_GERADO', 'XML oficial gerado'
        XML_ASSINADO = 'XML_ASSINADO', 'XML assinado'
        NFE_ENVIADA_HOMOLOGACAO = 'NFE_ENVIADA_HOMOLOGACAO', 'NF-e enviada homologação'
        NFE_AUTORIZADA_HOMOLOGACAO = 'NFE_AUTORIZADA_HOMOLOGACAO', 'NF-e autorizada homologação'
        NFE_REJEITADA_HOMOLOGACAO = 'NFE_REJEITADA_HOMOLOGACAO', 'NF-e rejeitada homologação'
        EMISSAO_PRODUCAO_INICIADA = 'EMISSAO_PRODUCAO_INICIADA', 'Emissão produção iniciada'
        NFE_ENVIADA_PRODUCAO = 'NFE_ENVIADA_PRODUCAO', 'NF-e enviada produção'
        NFE_AUTORIZADA_PRODUCAO = 'NFE_AUTORIZADA_PRODUCAO', 'NF-e autorizada produção'
        NFE_REJEITADA_PRODUCAO = 'NFE_REJEITADA_PRODUCAO', 'NF-e rejeitada produção'
        ERRO_TRANSMISSAO_SEFAZ = 'ERRO_TRANSMISSAO_SEFAZ', 'Erro transmissão SEFAZ'
        CONSULTA_SITUACAO_SEFAZ = 'CONSULTA_SITUACAO_SEFAZ', 'Consulta situação SEFAZ'
        CARTA_CORRECAO_EMITIDA = 'CARTA_CORRECAO_EMITIDA', 'Carta de Correção emitida'
        CANCELAMENTO_SEFAZ_EMITIDO = 'CANCELAMENTO_SEFAZ_EMITIDO', 'Cancelamento SEFAZ emitido'
        INUTILIZACAO_SEFAZ_EMITIDA = 'INUTILIZACAO_SEFAZ_EMITIDA', 'Inutilização SEFAZ emitida'

    nfe_saida = models.ForeignKey(
        NFeSaida,
        on_delete=models.CASCADE,
        related_name='eventos',
    )
    tipo_evento = models.CharField(max_length=40, choices=TipoEvento.choices)
    pedido_venda = models.ForeignKey(
        'comercial.PedidoVenda',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_nfe_saida',
    )
    faturamento_pedido_venda = models.ForeignKey(
        'comercial.FaturamentoPedidoVenda',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_nfe_saida',
    )
    status_anterior = models.CharField(max_length=64, blank=True)
    status_novo = models.CharField(max_length=64, blank=True)
    resumo = models.JSONField(null=True, blank=True)
    observacao = models.TextField(blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_nfe_saida_criados',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        indexes = [
            models.Index(fields=['nfe_saida', '-criado_em']),
        ]


class NFeSaidaEnvioEmail(models.Model):
    """Log de envio manual de DANFE/XML autorizado por e-mail — sem efeito fiscal."""

    class StatusEnvio(models.TextChoices):
        SUCESSO = 'SUCESSO', 'Sucesso'
        ERRO = 'ERRO', 'Erro'

    nfe_saida = models.ForeignKey(
        NFeSaida,
        on_delete=models.CASCADE,
        related_name='envios_email',
    )
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saida_envios_email',
    )
    enviado_em = models.DateTimeField(auto_now_add=True)
    destinatario = models.CharField(max_length=320)
    copias = models.TextField(blank=True, help_text='Destinatários em cópia (separados por vírgula).')
    assunto = models.CharField(max_length=255)
    ambiente = models.CharField(max_length=16, blank=True)
    status_envio = models.CharField(max_length=8, choices=StatusEnvio.choices)
    mensagem_erro = models.TextField(blank=True)
    anexo_xml = models.BooleanField(default=False)
    anexo_danfe_pdf = models.BooleanField(default=False)

    class Meta:
        ordering = ['-enviado_em', '-id']
        verbose_name = 'Envio e-mail NF-e Saída'
        verbose_name_plural = 'Envios e-mail NF-e Saída'
        indexes = [
            models.Index(fields=['nfe_saida', '-enviado_em']),
            models.Index(fields=['status_envio', '-enviado_em']),
        ]

    def __str__(self) -> str:
        return f'Envio NF-e {self.nfe_saida_id} → {self.destinatario} ({self.status_envio})'


class ItemNFeSaida(models.Model):
    nf = models.ForeignKey(NFeSaida, on_delete=models.CASCADE, related_name='itens')
    item_faturamento_pedido = models.ForeignKey(
        'comercial.ItemFaturamentoPedidoVenda',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='itens_nfe_saida',
    )
    produto = models.ForeignKey('produtos.Produto', on_delete=models.PROTECT)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3)
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    corrida = models.ForeignKey(
        'corridas.Corrida',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    snapshot_produto = models.JSONField(default=dict, blank=True)
    snapshot_fiscal = models.JSONField(null=True, blank=True)
    snapshot_comercial = models.JSONField(null=True, blank=True)
    pedido_cliente_numero = models.CharField(max_length=64, blank=True)
    pedido_cliente_item = models.CharField(max_length=64, blank=True)
    observacao_item = models.TextField(blank=True)
    informacao_adicional_item = models.TextField(blank=True)

    class Meta:
        ordering = ['id']


class AtendimentoEstoque(models.Model):
    class OrigemTipo(models.TextChoices):
        NF_SAIDA = 'NF_SAIDA', 'NF de saída'

    class Status(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente'
        PARCIAL = 'PARCIAL', 'Parcial'
        ATENDIDO = 'ATENDIDO', 'Atendido'
        CANCELADO = 'CANCELADO', 'Cancelado'

    origem_tipo = models.CharField(
        max_length=16,
        choices=OrigemTipo.choices,
        default=OrigemTipo.NF_SAIDA,
    )
    item_nf_saida = models.ForeignKey(
        ItemNFeSaida,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='atendimentos_estoque',
    )
    nf_saida = models.ForeignKey(
        NFeSaida,
        on_delete=models.CASCADE,
        related_name='atendimentos_estoque',
    )
    produto = models.ForeignKey(
        'produtos.Produto',
        on_delete=models.PROTECT,
        related_name='atendimentos_estoque',
    )
    quantidade_comprometida = models.DecimalField(max_digits=14, decimal_places=3)
    quantidade_atendida = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    unidade = models.CharField(max_length=16, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDENTE,
    )
    estoque_fisico_aplicado = models.BooleanField(default=False)
    estoque_aplicado_em = models.DateTimeField(null=True, blank=True)
    observacoes = models.TextField(blank=True)
    motivo_cancelamento = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    atendido_em = models.DateTimeField(null=True, blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        indexes = [
            models.Index(fields=['produto', 'status']),
            models.Index(fields=['nf_saida', 'status']),
            models.Index(fields=['criado_em']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantidade_comprometida__gt=0),
                name='ck_atend_estoque_qtd_comprometida_pos',
            ),
            models.CheckConstraint(
                check=models.Q(quantidade_atendida__gte=0),
                name='ck_atend_estoque_qtd_atendida_nonneg',
            ),
            models.CheckConstraint(
                check=models.Q(status='CANCELADO')
                | models.Q(quantidade_atendida__lte=models.F('quantidade_comprometida')),
                name='ck_atend_estoque_qtd_atend_lte_comp',
            ),
            models.UniqueConstraint(
                fields=['item_nf_saida'],
                condition=models.Q(~models.Q(status='CANCELADO'), item_nf_saida__isnull=False),
                name='uniq_atend_estoque_item_nf_saida_ativo',
            ),
        ]

    def __str__(self) -> str:
        return f'Atendimento #{self.pk} NF {self.nf_saida_id} item {self.item_nf_saida_id}'


class AtendimentoEstoqueLinha(models.Model):
    atendimento = models.ForeignKey(
        AtendimentoEstoque,
        on_delete=models.CASCADE,
        related_name='linhas',
    )
    item_conferencia = models.ForeignKey(
        'ItemNFeEntradaConferencia',
        on_delete=models.PROTECT,
        related_name='linhas_atendimento_estoque',
    )
    conferencia = models.ForeignKey(
        'NFeEntradaConferencia',
        on_delete=models.PROTECT,
        related_name='linhas_atendimento_estoque',
    )
    quantidade = models.DecimalField(max_digits=14, decimal_places=3)
    item_certificado_fornecedor = models.ForeignKey(
        'qualidade.ItemCertificadoFornecedorEntrada',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linhas_atendimento_estoque',
    )
    corrida_texto = models.CharField(max_length=64, blank=True)
    lote = models.CharField(max_length=64, blank=True)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['criado_em', 'id']
        indexes = [
            models.Index(fields=['atendimento']),
            models.Index(fields=['item_conferencia']),
            models.Index(fields=['conferencia']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantidade__gt=0),
                name='ck_atend_estoque_linha_qtd_pos',
            ),
        ]

    def __str__(self) -> str:
        return f'Linha atend. #{self.pk} conf {self.item_conferencia_id} → atend {self.atendimento_id}'


class NFeSaidaHistoricaImportada(models.Model):
    """NF-e de saída emitida fora do ERP, importada por XML para base fiscal/gerencial."""

    chave_acesso = models.CharField(max_length=44, unique=True, db_index=True)
    numero = models.CharField(max_length=16)
    serie = models.CharField(max_length=4, blank=True)
    modelo = models.CharField(max_length=4, blank=True)
    dh_emissao = models.DateTimeField()
    tp_amb = models.CharField(max_length=1, blank=True)
    tp_nf = models.CharField(max_length=1, blank=True)
    nat_op = models.CharField(max_length=120, blank=True)
    versao_layout = models.CharField(max_length=16, blank=True)

    cstat = models.CharField(max_length=8, blank=True)
    xmotivo = models.CharField(max_length=255, blank=True)
    protocolo = models.CharField(max_length=30, blank=True)

    valor_produtos = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    valor_total_nf = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    v_frete = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    v_seg = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    v_desc = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    v_outro = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))

    emit_json = models.JSONField(default=dict, blank=True)
    dest_json = models.JSONField(default=dict, blank=True)
    totais_json = models.JSONField(default=dict, blank=True)
    reforma_e_outros_json = models.JSONField(default=dict, blank=True)
    prot_json = models.JSONField(default=dict, blank=True)
    cancelada = models.BooleanField(default=False)
    status_documento = models.CharField(max_length=32, default='autorizada')
    data_cancelamento = models.DateTimeField(null=True, blank=True)
    protocolo_evento = models.CharField(max_length=30, blank=True)
    tipo_evento = models.CharField(max_length=16, blank=True)
    evento_cancelamento_json = models.JSONField(default=dict, blank=True)
    evento_cancelamento_id = models.CharField(max_length=80, blank=True)

    empresa_emitente = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saida_historicas_importadas',
    )
    cliente = models.ForeignKey(
        'cadastros.Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saida_historicas_importadas',
    )
    papel_empresa_no_documento = models.CharField(max_length=32, blank=True)

    importada = models.BooleanField(default=True)
    origem_externa = models.BooleanField(default=True)
    historica = models.BooleanField(default=True)

    nome_arquivo = models.CharField(max_length=255, blank=True)
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-dh_emissao', '-id']
        verbose_name = 'NF-e saída importada (histórico)'
        verbose_name_plural = 'NF-e saída importadas (histórico)'

    def __str__(self):
        return f'{self.chave_acesso} — {self.numero}/{self.serie}'


class NFeEntradaHistoricaImportada(models.Model):
    """NF-e de entrada emitida fora do ERP, importada por XML para base fiscal/gerencial."""

    chave_acesso = models.CharField(max_length=44, unique=True, db_index=True)
    numero = models.CharField(max_length=16)
    serie = models.CharField(max_length=4, blank=True)
    modelo = models.CharField(max_length=4, blank=True)
    dh_emissao = models.DateTimeField()
    tp_amb = models.CharField(max_length=1, blank=True)
    tp_nf = models.CharField(max_length=1, blank=True)
    nat_op = models.CharField(max_length=120, blank=True)
    versao_layout = models.CharField(max_length=16, blank=True)

    cstat = models.CharField(max_length=8, blank=True)
    xmotivo = models.CharField(max_length=255, blank=True)
    protocolo = models.CharField(max_length=30, blank=True)

    valor_produtos = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    valor_total_nf = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    v_frete = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    v_seg = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    v_desc = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    v_outro = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))

    emit_json = models.JSONField(default=dict, blank=True)
    dest_json = models.JSONField(default=dict, blank=True)
    totais_json = models.JSONField(default=dict, blank=True)
    reforma_e_outros_json = models.JSONField(default=dict, blank=True)
    prot_json = models.JSONField(default=dict, blank=True)

    empresa_destinataria = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_entrada_historicas_importadas_como_destinataria',
    )
    fornecedor_emitente = models.ForeignKey(
        'cadastros.Fornecedor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_entrada_historicas_importadas_como_emitente',
    )
    papel_empresa_no_documento = models.CharField(max_length=32, blank=True)

    importada = models.BooleanField(default=True)
    origem_externa = models.BooleanField(default=True)
    historica = models.BooleanField(default=True)

    nome_arquivo = models.CharField(max_length=255, blank=True)
    xml_conteudo = models.TextField(blank=True)
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-dh_emissao', '-id']
        verbose_name = 'NF-e entrada importada (histórico)'
        verbose_name_plural = 'NF-e entrada importadas (histórico)'

    def __str__(self):
        return f'{self.chave_acesso} — {self.numero}/{self.serie}'


class ItemNFeEntradaHistoricaImportada(models.Model):
    nf = models.ForeignKey(
        NFeEntradaHistoricaImportada,
        on_delete=models.CASCADE,
        related_name='itens',
    )
    n_item = models.PositiveIntegerField()
    prod_json = models.JSONField(default=dict, blank=True)
    imposto_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['nf_id', 'n_item']

    def __str__(self):
        return f'Item {self.n_item} NF entrada hist. {self.nf_id}'


class NFeEntradaConferencia(models.Model):
    class Status(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente'
        CONFERIDA = 'CONFERIDA', 'Conferida'
        PREPARADA = 'PREPARADA', 'Entrada preparada'
        CANCELADA = 'CANCELADA', 'Cancelada/Revertida'

    nf_entrada_historica = models.OneToOneField(
        NFeEntradaHistoricaImportada,
        on_delete=models.CASCADE,
        related_name='conferencia',
    )
    pedido_compra = models.ForeignKey(
        'comercial.PedidoCompra',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conferencias_nf_entrada',
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDENTE)
    divergencias_aceitas = models.BooleanField(default=False)
    observacao_divergencias = models.TextField(blank=True)
    preparado_em = models.DateTimeField(null=True, blank=True)
    estoque_aplicado_em = models.DateTimeField(null=True, blank=True)
    estoque_aplicado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conferencias_estoque_aplicado',
    )
    estoque_aplicado_observacao = models.TextField(blank=True)
    pedido_baixa_aplicado_em = models.DateTimeField(null=True, blank=True)
    pedido_baixa_aplicado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conferencias_pedido_baixa_aplicado',
    )
    data_entrada = models.DateField(
        null=True,
        blank=True,
        help_text='Data operacional/fiscal de entrada informada pelo usuário na finalização.',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-atualizado_em', '-id']


class ItemNFeEntradaConferencia(models.Model):
    class Status(models.TextChoices):
        PENDENTE_PRODUTO = 'PENDENTE_PRODUTO', 'Pendente produto'
        PRODUTO_VINCULADO = 'PRODUTO_VINCULADO', 'Produto vinculado'
        CONFERIDO = 'CONFERIDO', 'Conferido'
        DIVERGENTE = 'DIVERGENTE', 'Divergente'
        IGNORADO = 'IGNORADO', 'Ignorado'

    conferencia = models.ForeignKey(
        NFeEntradaConferencia,
        on_delete=models.CASCADE,
        related_name='itens',
    )
    item_nfe_historico = models.OneToOneField(
        ItemNFeEntradaHistoricaImportada,
        on_delete=models.CASCADE,
        related_name='item_conferencia',
    )
    produto = models.ForeignKey(
        'produtos.Produto',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='itens_conferencia_nfe_entrada',
    )
    item_pedido_compra = models.ForeignKey(
        'comercial.ItemPedidoCompra',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='itens_conferencia_nfe_entrada',
    )
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDENTE_PRODUTO)
    motivo_ignorado = models.CharField(max_length=255, blank=True)
    observacao = models.TextField(blank=True)
    corrida = models.CharField(max_length=64, blank=True)
    lote = models.CharField(max_length=64, blank=True)
    rastreabilidade_observacao = models.CharField(max_length=255, blank=True)
    unidade_nf = models.CharField(max_length=16, blank=True)
    quantidade_nf = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    valor_unitario_nf = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    valor_total_nf = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    unidade_estoque_calculada = models.CharField(max_length=16, blank=True)
    quantidade_estoque_calculada = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    peso_total_kg = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    metros_total = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    barras_total = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    toneladas_total = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    divergencias = models.JSONField(default=list, blank=True)
    alertas = models.JSONField(default=list, blank=True)
    snapshot_produto = models.JSONField(default=dict, blank=True)
    snapshot_pedido = models.JSONField(default=dict, blank=True)
    estoque_aplicado_em = models.DateTimeField(null=True, blank=True)
    quantidade_estoque_aplicada = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=Decimal('0'),
    )
    corrida_estoque = models.ForeignKey(
        'corridas.Corrida',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='itens_conferencia_entrada',
    )
    estoque_corrida = models.ForeignKey(
        'EstoqueCorrida',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='itens_conferencia_entrada',
    )
    quantidade_pedido_baixada = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=Decimal('0'),
    )
    pedido_baixa_aplicada_em = models.DateTimeField(null=True, blank=True)
    conversao_estoque_auditoria = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['item_nfe_historico__n_item']


class ItemNFeEntradaConferenciaEquivalencia(models.Model):
    item_conferencia = models.ForeignKey(
        ItemNFeEntradaConferencia,
        on_delete=models.CASCADE,
        related_name='equivalencias',
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    metros = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    barras = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    peso_kg = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    peso_por_metro_utilizado = models.DecimalField(max_digits=14, decimal_places=6, null=True, blank=True)

    class Meta:
        ordering = ['ordem', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['item_conferencia', 'ordem'],
                name='uniq_item_conf_equivalencia_ordem',
            ),
        ]


class EstoqueBarra(models.Model):
    """Estoque físico rastreável por barra (metros), originado da conferência NF-e entrada."""

    class Status(models.TextChoices):
        DISPONIVEL = 'DISPONIVEL', 'Disponível'
        PARCIAL = 'PARCIAL', 'Parcial'
        CONSUMIDA = 'CONSUMIDA', 'Consumida'
        CANCELADA = 'CANCELADA', 'Cancelada'

    class Origem(models.TextChoices):
        CONFERENCIA_NFE_ENTRADA = 'CONFERENCIA_NFE_ENTRADA', 'Conferência NF-e entrada'

    produto = models.ForeignKey(
        'produtos.Produto',
        on_delete=models.CASCADE,
        related_name='estoque_barras',
    )
    item_conferencia = models.ForeignKey(
        'ItemNFeEntradaConferencia',
        on_delete=models.CASCADE,
        related_name='estoque_barras',
    )
    equivalencia_entrada = models.OneToOneField(
        'ItemNFeEntradaConferenciaEquivalencia',
        on_delete=models.PROTECT,
        related_name='estoque_barra',
    )
    nfe_entrada_historica = models.ForeignKey(
        'NFeEntradaHistoricaImportada',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='estoque_barras',
    )
    fornecedor = models.ForeignKey(
        'cadastros.Fornecedor',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='estoque_barras',
    )
    codigo_interno_barra = models.CharField(max_length=64, unique=True, db_index=True)
    comprimento_original_m = models.DecimalField(max_digits=14, decimal_places=3)
    saldo_m = models.DecimalField(max_digits=14, decimal_places=3)
    unidade_base = models.CharField(max_length=8, default='M')
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DISPONIVEL,
    )
    origem = models.CharField(
        max_length=32,
        choices=Origem.choices,
        default=Origem.CONFERENCIA_NFE_ENTRADA,
    )
    metadata = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['item_conferencia_id', 'equivalencia_entrada__ordem', 'id']
        indexes = [
            models.Index(fields=['produto', 'status']),
            models.Index(fields=['item_conferencia']),
        ]

    def __str__(self) -> str:
        return f'{self.codigo_interno_barra} ({self.saldo_m} M)'


class ItemNFeEntradaConferenciaCorridaSplit(models.Model):
    item_conferencia = models.ForeignKey(
        ItemNFeEntradaConferencia,
        on_delete=models.CASCADE,
        related_name='corridas_split',
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    corrida = models.CharField(max_length=64, blank=True)
    lote = models.CharField(max_length=64, blank=True)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3)
    corrida_estoque = models.ForeignKey(
        'corridas.Corrida',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='splits_conferencia',
    )
    estoque_corrida = models.ForeignKey(
        'EstoqueCorrida',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='splits_conferencia',
    )
    quantidade_aplicada = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ['ordem', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['item_conferencia', 'ordem'],
                name='uniq_item_conf_corrida_split_ordem',
            ),
        ]


class ItemNFeSaidaHistoricaImportada(models.Model):
    nf = models.ForeignKey(
        NFeSaidaHistoricaImportada,
        on_delete=models.CASCADE,
        related_name='itens',
    )
    n_item = models.PositiveIntegerField()
    prod_json = models.JSONField(default=dict, blank=True)
    imposto_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['nf_id', 'n_item']

    def __str__(self):
        return f'Item {self.n_item} NF hist. {self.nf_id}'


class EventoNFeSaidaHistoricaPendente(models.Model):
    """Evento de NF-e (XML) recebido antes da nota correspondente existir na base — conciliação posterior."""

    class Direcao(models.TextChoices):
        SAIDA = 'SAIDA', 'Saída'
        ENTRADA = 'ENTRADA', 'Entrada'

    class Status(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente'
        APLICADO = 'APLICADO', 'Aplicado'
        IGNORADO = 'IGNORADO', 'Ignorado'

    chave_nfe = models.CharField(max_length=44, db_index=True)
    tipo_evento = models.CharField(max_length=16, db_index=True)
    descricao_evento = models.CharField(max_length=255, blank=True)
    sequencia_evento = models.PositiveSmallIntegerField(default=0)
    data_evento = models.DateTimeField(null=True, blank=True)
    protocolo_evento = models.CharField(max_length=30, blank=True)
    id_evento = models.CharField(max_length=80, blank=True)
    justificativa = models.TextField(blank=True)
    evento_json = models.JSONField(default=dict, blank=True)
    nome_arquivo = models.CharField(max_length=255, blank=True)
    direcao = models.CharField(max_length=8, choices=Direcao.choices, default=Direcao.SAIDA)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDENTE, db_index=True)
    mensagem = models.TextField(blank=True)
    nf = models.ForeignKey(
        NFeSaidaHistoricaImportada,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='eventos_pendentes_resolvidos',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['chave_nfe', 'tipo_evento', 'protocolo_evento', 'id_evento'],
                name='uniq_evento_hist_pendente_dedup',
            )
        ]

    def __str__(self) -> str:
        return f'Evento pendente {self.tipo_evento} chave {self.chave_nfe[:8]}…'


class EventoNFeSaidaHistoricaImportada(models.Model):
    nf = models.ForeignKey(
        NFeSaidaHistoricaImportada,
        on_delete=models.CASCADE,
        related_name='eventos',
    )
    chave_acesso = models.CharField(max_length=44, db_index=True)
    tipo_evento = models.CharField(max_length=16, db_index=True)
    protocolo_evento = models.CharField(max_length=30, blank=True)
    id_evento = models.CharField(max_length=80, blank=True)
    sequencial_evento = models.PositiveSmallIntegerField(default=0)
    data_evento = models.DateTimeField(null=True, blank=True)
    evento_json = models.JSONField(default=dict, blank=True)
    nome_arquivo = models.CharField(max_length=255, blank=True)
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-importado_em', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['nf', 'tipo_evento', 'protocolo_evento', 'id_evento'],
                name='uniq_nf_hist_evento_dedup',
            )
        ]


class CTeEntrada(models.Model):
    numero = models.CharField(max_length=64, unique=True)
    transportadora = models.ForeignKey(
        'cadastros.Transportadora',
        on_delete=models.PROTECT,
        related_name='ctes',
    )
    tomador = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.PROTECT,
        related_name='ctes_como_tomador',
    )
    valor_frete = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    data = models.DateField()
    nfe_ids = ArrayField(models.IntegerField(), default=list, blank=True)

    class Meta:
        ordering = ['-data', 'numero']
        verbose_name = 'CT-e entrada'


class CTeHistoricoImportado(models.Model):
    """CT-e emitido fora do ERP, importado por XML para base fiscal/logística/gerencial."""

    chave_acesso = models.CharField(max_length=44, unique=True, db_index=True)
    numero = models.CharField(max_length=16)
    serie = models.CharField(max_length=4, blank=True)
    modelo = models.CharField(max_length=4, blank=True)
    dh_emissao = models.DateTimeField()
    tp_amb = models.CharField(max_length=1, blank=True)
    nat_op = models.CharField(max_length=120, blank=True)
    cfop = models.CharField(max_length=8, blank=True)
    versao_layout = models.CharField(max_length=16, blank=True)

    cstat = models.CharField(max_length=8, blank=True)
    xmotivo = models.CharField(max_length=255, blank=True)
    protocolo = models.CharField(max_length=30, blank=True)

    cancelado = models.BooleanField(default=False)
    status_documento = models.CharField(max_length=32, default='autorizado')
    data_cancelamento = models.DateTimeField(null=True, blank=True)
    protocolo_cancelamento = models.CharField(max_length=30, blank=True)
    motivo_cancelamento = models.CharField(max_length=255, blank=True)

    valor_total_servico = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    valor_receber = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    componentes_frete_json = models.JSONField(default=list, blank=True)

    icms_base = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    icms_aliquota = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal('0'))
    icms_valor = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))

    modal = models.CharField(max_length=16, blank=True)
    tipo_servico = models.CharField(max_length=16, blank=True)
    municipio_inicio = models.CharField(max_length=120, blank=True)
    uf_inicio = models.CharField(max_length=2, blank=True)
    municipio_fim = models.CharField(max_length=120, blank=True)
    uf_fim = models.CharField(max_length=2, blank=True)

    # Participantes (JSON fiel ao XML)
    emit_json = models.JSONField(default=dict, blank=True)
    rem_json = models.JSONField(default=dict, blank=True)
    dest_json = models.JSONField(default=dict, blank=True)
    exped_json = models.JSONField(default=dict, blank=True)
    receb_json = models.JSONField(default=dict, blank=True)
    tomador_json = models.JSONField(default=dict, blank=True)

    totais_json = models.JSONField(default=dict, blank=True)
    imposto_json = models.JSONField(default=dict, blank=True)
    prot_json = models.JSONField(default=dict, blank=True)
    reforma_e_outros_json = models.JSONField(default=dict, blank=True)

    chaves_nfe_vinculadas = models.JSONField(default=list, blank=True)

    transportadora = models.ForeignKey(
        'cadastros.Transportadora',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ctes_historicos_importados',
    )
    empresa_tomadora = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ctes_historicos_importados_como_tomadora',
    )
    empresa_destinataria = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ctes_historicos_importados_como_destinataria',
    )
    empresa_recebedora = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ctes_historicos_importados_como_recebedora',
    )
    fornecedor_remetente = models.ForeignKey(
        'cadastros.Fornecedor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ctes_historicos_importados_como_remetente',
    )
    papel_empresa_no_documento = models.CharField(max_length=32, blank=True)

    importado = models.BooleanField(default=True)
    origem_externa = models.BooleanField(default=True)
    historico = models.BooleanField(default=True)

    nome_arquivo = models.CharField(max_length=255, blank=True)
    xml_conteudo = models.TextField(blank=True)
    importado_em = models.DateTimeField(auto_now_add=True)

    class StatusConferencia(models.TextChoices):
        IMPORTADO = 'IMPORTADO', 'Importado'
        PROCESSADO = 'PROCESSADO', 'Processado'
        PREPARADO = 'PREPARADO', 'Preparado'
        CONFERIDO = 'CONFERIDO', 'Conferido'
        DIVERGENTE = 'DIVERGENTE', 'Divergente'
        IGNORADO = 'IGNORADO', 'Ignorado'
        CANCELADO = 'CANCELADO', 'Cancelado'

    status_conferencia = models.CharField(
        max_length=16,
        choices=StatusConferencia.choices,
        default=StatusConferencia.IMPORTADO,
    )
    conferido_em = models.DateTimeField(null=True, blank=True)
    conferido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ctes_historicos_conferidos',
    )
    observacao_conferencia = models.TextField(blank=True)
    divergencia_motivo = models.CharField(max_length=500, blank=True)
    apto_operacional = models.BooleanField(default=False)
    ignorado_operacionalmente = models.BooleanField(default=False)
    checklist_conferencia_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-dh_emissao', '-id']
        verbose_name = 'CT-e importado (histórico)'
        verbose_name_plural = 'CT-e importados (histórico)'

    def __str__(self):
        return f'{self.chave_acesso} — {self.numero}/{self.serie}'


class EventoCTeHistoricoImportado(models.Model):
    """
    Estrutura pronta para eventos do CT-e (cancelamento, etc).
    Nesta fase, o XML de evento pode não ser importado, mas a base já fica preparada.
    """

    cte = models.ForeignKey(
        CTeHistoricoImportado,
        on_delete=models.CASCADE,
        related_name='eventos',
    )
    chave_acesso = models.CharField(max_length=44, db_index=True)
    tipo_evento = models.CharField(max_length=16, db_index=True)
    protocolo_evento = models.CharField(max_length=30, blank=True)
    id_evento = models.CharField(max_length=80, blank=True)
    sequencial_evento = models.PositiveSmallIntegerField(default=0)
    data_evento = models.DateTimeField(null=True, blank=True)
    evento_json = models.JSONField(default=dict, blank=True)
    nome_arquivo = models.CharField(max_length=255, blank=True)
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-importado_em', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['cte', 'tipo_evento', 'protocolo_evento', 'id_evento'],
                name='uniq_cte_hist_evento_dedup',
            )
        ]


class NFeSefazStatusConsulta(models.Model):
    """NF-e 3.6 — registro de consulta status_servico SEFAZ (homologação/produção)."""

    class Ambiente(models.TextChoices):
        HOMOLOGACAO = 'homologacao', 'Homologação'
        PRODUCAO = 'producao', 'Produção'

    empresa = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.CASCADE,
        related_name='consultas_status_sefaz',
    )
    uf = models.CharField(max_length=2, default='SP')
    ambiente = models.CharField(max_length=16, choices=Ambiente.choices, default=Ambiente.HOMOLOGACAO)
    modelo = models.CharField(max_length=8, default='nfe')
    sucesso = models.BooleanField(default=False)
    c_stat = models.CharField(max_length=8, blank=True)
    x_motivo = models.TextField(blank=True)
    ver_aplic = models.CharField(max_length=64, blank=True)
    tp_amb = models.CharField(max_length=2, blank=True)
    c_uf = models.CharField(max_length=4, blank=True)
    dh_recbto = models.CharField(max_length=40, blank=True)
    t_med = models.CharField(max_length=16, blank=True)
    versao_retorno = models.CharField(max_length=8, blank=True)
    servico_operacional = models.BooleanField(default=False)
    certificado_valido = models.BooleanField(default=False)
    certificado_cnpj = models.CharField(max_length=20, blank=True)
    certificado_validade_fim = models.DateField(null=True, blank=True)
    xml_resposta = models.TextField(blank=True)
    raw_response = models.TextField(blank=True)
    erro_tecnico = models.TextField(blank=True)
    tipo_erro = models.CharField(max_length=32, blank=True)
    traceback_resumido = models.TextField(blank=True)
    mensagens = models.JSONField(default=list, blank=True)
    consultado_em = models.DateTimeField(auto_now_add=True)
    consultado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='consultas_status_sefaz_nfe',
    )

    class Meta:
        ordering = ['-consultado_em', '-id']
        verbose_name = 'Consulta status SEFAZ NF-e'
        verbose_name_plural = 'Consultas status SEFAZ NF-e'

    def __str__(self):
        return f'{self.empresa_id} {self.uf} {self.ambiente} cStat={self.c_stat or "—"}'


class NFeNumeracaoConfiguracao(models.Model):
    """Numeração fiscal NF-e modelo 55 por empresa e ambiente (homologação/produção separados)."""

    class Ambiente(models.TextChoices):
        HOMOLOGACAO = 'homologacao', 'Homologação'
        PRODUCAO = 'producao', 'Produção'

    class TipoOperacao(models.TextChoices):
        SAIDA = 'saida', 'Saída'
        ENTRADA_PROPRIA = 'entrada_propria', 'Entrada própria'

    empresa = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.CASCADE,
        related_name='numeracoes_nfe',
    )
    modelo_documento = models.CharField(max_length=2, default='55')
    ambiente = models.CharField(max_length=16, choices=Ambiente.choices)
    tipo_operacao = models.CharField(
        max_length=20,
        choices=TipoOperacao.choices,
        default=TipoOperacao.SAIDA,
    )
    serie = models.CharField(max_length=3, default='0')
    proximo_numero = models.PositiveIntegerField(default=1)
    ultimo_numero_reservado = models.PositiveIntegerField(null=True, blank=True)
    ultimo_numero_autorizado = models.PositiveIntegerField(null=True, blank=True)
    ativo = models.BooleanField(default=True)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['empresa_id', 'ambiente', 'serie']
        verbose_name = 'Configuração numeração NF-e'
        verbose_name_plural = 'Configurações numeração NF-e'
        constraints = [
            models.UniqueConstraint(
                fields=['empresa', 'modelo_documento', 'ambiente', 'tipo_operacao', 'serie'],
                condition=models.Q(ativo=True),
                name='uniq_nfe_numeracao_ativa_empresa_ambiente_tipo_serie',
            ),
        ]

    def __str__(self) -> str:
        return (
            f'{self.empresa_id} mod{self.modelo_documento} {self.ambiente} '
            f'{self.tipo_operacao} série {self.serie} próx={self.proximo_numero}'
        )


class NFeNumeracaoNumeroLiberado(models.Model):
    """Número fiscal liberado após descarte de NF-e nunca transmitida à SEFAZ (reutilização segura)."""

    configuracao = models.ForeignKey(
        NFeNumeracaoConfiguracao,
        on_delete=models.CASCADE,
        related_name='numeros_liberados',
    )
    numero = models.PositiveIntegerField()
    nfe_saida_origem = models.ForeignKey(
        'fiscal.NFeSaida',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='numeracao_liberada_origem',
    )
    liberado_em = models.DateTimeField(auto_now_add=True)
    liberado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='numeros_nfe_liberados',
    )
    motivo = models.TextField(blank=True)
    consumido_em = models.DateTimeField(null=True, blank=True)
    nfe_saida_consumo = models.ForeignKey(
        'fiscal.NFeSaida',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='numeracao_reutilizada_de',
    )

    class Meta:
        ordering = ['configuracao_id', 'numero']
        verbose_name = 'Número NF-e liberado para reutilização'
        verbose_name_plural = 'Números NF-e liberados para reutilização'
        indexes = [
            models.Index(
                fields=['configuracao', 'consumido_em', 'numero'],
                name='fiscal_nfe__configu_8a1f2d_idx',
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['configuracao', 'numero'],
                condition=models.Q(consumido_em__isnull=True),
                name='uniq_nfe_numero_liberado_disponivel',
            ),
        ]

    def __str__(self) -> str:
        estado = 'disponível' if self.consumido_em is None else 'consumido'
        return f'NF-e nº {self.numero} ({estado}) cfg#{self.configuracao_id}'


class NFeInutilizacaoSefaz(models.Model):
    """Registro de inutilização de faixa numérica transmitida à SEFAZ."""

    configuracao = models.ForeignKey(
        NFeNumeracaoConfiguracao,
        on_delete=models.PROTECT,
        related_name='inutilizacoes_sefaz',
    )
    serie = models.CharField(max_length=3)
    ambiente = models.CharField(max_length=16)
    ano = models.CharField(max_length=2, blank=True)
    numero_inicial = models.PositiveIntegerField()
    numero_final = models.PositiveIntegerField()
    justificativa = models.TextField()
    protocolo = models.CharField(max_length=32, blank=True)
    cstat = models.CharField(max_length=8, blank=True)
    xmotivo = models.TextField(blank=True)
    xml_retorno = models.TextField(blank=True)
    sefaz_ok = models.BooleanField(default=False)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nfe_inutilizacoes_criadas',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-pk']
        verbose_name = 'Inutilização NF-e SEFAZ'
        verbose_name_plural = 'Inutilizações NF-e SEFAZ'
        indexes = [
            models.Index(fields=['configuracao', 'serie', 'numero_inicial', 'numero_final']),
        ]

    def __str__(self) -> str:
        return (
            f'Inutilização série {self.serie} nº {self.numero_inicial}–{self.numero_final} '
            f'({self.ambiente})'
        )


class AlocacaoAtendimento(models.Model):
    """ERP 4.0.10 — registro de intenção de atendimento por item/quantidade.

    Distinto de AtendimentoEstoque (compromisso NF saída antecipada + vínculo conferência).
    Campos opcionais; não movimenta estoque nem gera financeiro nesta fase.
    """


    pedido_venda_item = models.ForeignKey(
        'comercial.ItemPedidoVenda',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alocacoes_atendimento',
    )
    faturamento_item = models.ForeignKey(
        'comercial.ItemFaturamentoPedidoVenda',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alocacoes_atendimento',
    )
    produto = models.ForeignKey(
        'produtos.Produto',
        on_delete=models.PROTECT,
        related_name='alocacoes_atendimento',
    )
    quantidade_necessaria = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    quantidade_atendida = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    quantidade_pendente = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    tipo_atendimento = models.CharField(
        max_length=40,
        choices=TipoAtendimentoItem.choices,
        default=TipoAtendimentoItem.NAO_DEFINIDO,
    )
    status_entrada_fiscal = models.CharField(
        max_length=20,
        choices=StatusEntradaFiscal.choices,
        default=StatusEntradaFiscal.NAO_APLICAVEL,
    )
    origem_fisica = models.CharField(
        max_length=20,
        choices=OrigemFisica.choices,
        default=OrigemFisica.NAO_DEFINIDA,
    )
    destino_fisico = models.CharField(
        max_length=20,
        choices=DestinoFisico.choices,
        default=DestinoFisico.NAO_DEFINIDO,
    )
    pedido_compra_item = models.ForeignKey(
        'comercial.ItemPedidoCompra',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alocacoes_atendimento',
    )
    nf_entrada_item = models.ForeignKey(
        'fiscal.ItemNFeEntrada',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alocacoes_atendimento',
    )
    nf_entrada_historica_item = models.ForeignKey(
        'fiscal.ItemNFeEntradaHistoricaImportada',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alocacoes_atendimento',
    )
    cte_historico_importado = models.ForeignKey(
        'fiscal.CTeHistoricoImportado',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alocacoes_atendimento',
    )
    item_nf_saida = models.ForeignKey(
        'fiscal.ItemNFeSaida',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alocacoes_atendimento',
    )
    fornecedor = models.ForeignKey(
        'cadastros.Fornecedor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alocacoes_atendimento',
    )
    observacao_operacional = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        verbose_name = 'Alocação de atendimento'
        verbose_name_plural = 'Alocações de atendimento'
        indexes = [
            models.Index(fields=['produto', 'tipo_atendimento']),
            models.Index(fields=['status_entrada_fiscal']),
            models.Index(fields=['pedido_venda_item']),
        ]

    def __str__(self) -> str:
        return f'Alocação #{self.pk} produto={self.produto_id} tipo={self.tipo_atendimento}'


class NFeEntradaAgrupamentoConferencia(models.Model):
    """Agrupamento conferencial NF-e entrada ↔ produto interno — ERP 4.0.13.7."""

    class TipoAgrupamento(models.TextChoices):
        EQUIVALENCIA_SIMPLES = 'equivalencia_simples', 'Equivalência simples'
        EQUIVALENCIA_COMPOSTA = 'equivalencia_composta', 'Equivalência composta'
        MONTAGEM_PLANEJADA = 'montagem_planejada', 'Montagem planejada'
        DIVERGENTE = 'divergente', 'Divergente'

    class Status(models.TextChoices):
        SUGERIDO = 'sugerido', 'Sugerido'
        CONFIRMADO = 'confirmado', 'Confirmado'
        REJEITADO = 'rejeitado', 'Rejeitado'
        DIVERGENTE = 'divergente', 'Divergente'

    conferencia = models.ForeignKey(
        NFeEntradaConferencia,
        on_delete=models.CASCADE,
        related_name='agrupamentos',
    )
    pedido_compra = models.ForeignKey(
        'comercial.PedidoCompra',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agrupamentos_nfe_entrada',
    )
    item_pedido_compra = models.ForeignKey(
        'comercial.ItemPedidoCompra',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agrupamentos_nfe_entrada',
    )
    produto_interno_resultante = models.ForeignKey(
        'produtos.Produto',
        on_delete=models.PROTECT,
        related_name='agrupamentos_nfe_entrada',
    )
    tipo_agrupamento = models.CharField(max_length=32, choices=TipoAgrupamento.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SUGERIDO)
    confianca = models.PositiveSmallIntegerField(default=0)
    quantidade_equivalente = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    valor_total_agrupado = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    valor_pedido_referencia = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    diferenca_valor = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    diferenca_quantidade = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    motivo_confirmacao = models.TextField(blank=True)
    regra_equivalencia_composta = models.ForeignKey(
        'produtos.FornecedorComposicaoEquivalencia',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agrupamentos_conferencia',
    )
    regra_equivalencia_simples = models.ForeignKey(
        'produtos.FornecedorProdutoEquivalencia',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agrupamentos_conferencia',
    )
    usuario_confirmacao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agrupamentos_nfe_entrada_confirmados',
    )
    data_confirmacao = models.DateTimeField(null=True, blank=True)
    salvar_regra_fornecedor = models.BooleanField(default=False)
    snapshot_rastreabilidade = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['conferencia_id', '-confianca', 'id']

    def __str__(self) -> str:
        return f'Agrupamento {self.pk} → produto {self.produto_interno_resultante_id}'


class NFeEntradaAgrupamentoItem(models.Model):
    agrupamento = models.ForeignKey(
        NFeEntradaAgrupamentoConferencia,
        on_delete=models.CASCADE,
        related_name='itens',
    )
    item_nfe_conferencia = models.ForeignKey(
        ItemNFeEntradaConferencia,
        on_delete=models.CASCADE,
        related_name='agrupamentos',
    )
    quantidade_usada = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    valor_usado = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    observacoes = models.TextField(blank=True)

    class Meta:
        ordering = ['agrupamento_id', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['item_nfe_conferencia'],
                name='uq_nfe_entrada_agrup_item_conf_unico',
            ),
        ]

    def __str__(self) -> str:
        return f'Agrup. {self.agrupamento_id} item conf {self.item_nfe_conferencia_id}'


class NFeDestinadaManifestacao(models.Model):
    """Monitor de NF-e destinada ao CNPJ da empresa — distribuição DF-e / manifestação."""

    class StatusManifestacao(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente manifestação'
        CIENTE = 'CIENTE', 'Ciência registrada'
        CONFIRMADA = 'CONFIRMADA', 'Confirmação da operação'
        DESCONHECIDA = 'DESCONHECIDA', 'Desconhecimento'
        NAO_REALIZADA = 'NAO_REALIZADA', 'Operação não realizada'
        ERRO = 'ERRO', 'Erro SEFAZ'

    class StatusXml(models.TextChoices):
        RESUMO = 'RESUMO', 'Resumo recebido'
        DISPONIVEL = 'DISPONIVEL', 'XML disponível'
        BAIXADO = 'BAIXADO', 'XML baixado'
        PENDENTE = 'PENDENTE', 'Pendente XML'
        ERRO = 'ERRO', 'Erro'

    class Ambiente(models.TextChoices):
        PRODUCAO = '1', 'Produção'
        HOMOLOGACAO = '2', 'Homologação'

    empresa = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.CASCADE,
        related_name='nfe_destinadas_manifestacao',
    )
    chave_acesso = models.CharField(max_length=44, db_index=True)
    nsu = models.CharField(max_length=20, blank=True, db_index=True)
    cnpj_destinatario = models.CharField(max_length=14, db_index=True)
    cnpj_emitente = models.CharField(max_length=14, blank=True, db_index=True)
    razao_social_emitente = models.CharField(max_length=255, blank=True)
    ie_emitente = models.CharField(max_length=20, blank=True)
    dh_emissao = models.DateTimeField(null=True, blank=True)
    valor_nf = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    status_manifestacao = models.CharField(
        max_length=24,
        choices=StatusManifestacao.choices,
        default=StatusManifestacao.PENDENTE,
        db_index=True,
    )
    status_xml = models.CharField(
        max_length=16,
        choices=StatusXml.choices,
        default=StatusXml.RESUMO,
        db_index=True,
    )
    ambiente = models.CharField(
        max_length=1,
        choices=Ambiente.choices,
        default=Ambiente.PRODUCAO,
        db_index=True,
    )
    classificacao_dfe = models.CharField(max_length=32, default='BASE_DFE_IMPORTADA', blank=True)
    ultimo_cstat = models.CharField(max_length=8, blank=True)
    ultimo_xmotivo = models.CharField(max_length=255, blank=True)
    resumo_json = models.JSONField(default=dict, blank=True)
    nf_entrada_historica = models.ForeignKey(
        'NFeEntradaHistoricaImportada',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nfe_destinadas_manifestacao',
    )
    manifestado_em = models.DateTimeField(null=True, blank=True)
    xml_baixado_em = models.DateTimeField(null=True, blank=True)
    consultado_em = models.DateTimeField(auto_now=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-dh_emissao', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['empresa', 'chave_acesso'],
                name='uq_nfe_destinada_manifestacao_empresa_chave',
            ),
        ]
        indexes = [
            models.Index(fields=['empresa', 'status_manifestacao']),
            models.Index(fields=['empresa', 'status_xml']),
            models.Index(fields=['empresa', '-dh_emissao']),
        ]
        verbose_name = 'NF-e destinada (manifestação)'
        verbose_name_plural = 'NF-e destinadas (manifestação)'

    def __str__(self) -> str:
        return f'{self.chave_acesso} — {self.razao_social_emitente or self.cnpj_emitente}'


class NFeDestinadaManifestacaoEvento(models.Model):
    """Trilha auditável de consulta, manifestação e download XML."""

    class TipoAcao(models.TextChoices):
        CONSULTA = 'CONSULTA', 'Consulta DF-e'
        MANIFESTACAO = 'MANIFESTACAO', 'Manifestação do destinatário'
        BAIXA_XML = 'BAIXA_XML', 'Download XML'

    documento = models.ForeignKey(
        NFeDestinadaManifestacao,
        on_delete=models.CASCADE,
        related_name='eventos',
        null=True,
        blank=True,
    )
    empresa = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.CASCADE,
        related_name='eventos_manifestacao_destinatario',
        null=True,
        blank=True,
    )
    tipo_acao = models.CharField(max_length=16, choices=TipoAcao.choices)
    codigo_evento = models.CharField(max_length=16, blank=True)
    descricao = models.TextField()
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_manifestacao_destinatario',
    )
    ambiente = models.CharField(max_length=1, blank=True)
    resultado_resumido = models.CharField(max_length=255, blank=True)
    cstat = models.CharField(max_length=8, blank=True)
    xmotivo = models.CharField(max_length=255, blank=True)
    dados_json = models.JSONField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        indexes = [
            models.Index(fields=['documento', '-criado_em']),
        ]
        verbose_name = 'Evento manifestação destinatário'
        verbose_name_plural = 'Eventos manifestação destinatário'

    def __str__(self) -> str:
        return f'{self.tipo_acao} doc={self.documento_id} {self.criado_em:%Y-%m-%d %H:%M}'

