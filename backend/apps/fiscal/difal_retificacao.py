"""Auditoria de retificação DIFAL — NF-e de saída autorizadas com DIFAL recalculado pela tabela de UF.

Usado por `manage.py relatorio_difal_retificacao` para comparar, sem alterar nada,
o ICMS UF destino efetivamente emitido (snapshot por item) com o valor correto
(alíquota interna da UF destino na tabela − alíquota interestadual da região).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from apps.fiscal.dfe_classificacao import eh_documento_autorizado, eh_documento_producao
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_atualizar_impostos import _descricao_item, _uf_destino_nf, _uf_origem_nf
from apps.regras_fiscais.aliquotas_uf_seed import UF_FAIXA_INTERESTADUAL_12
from apps.regras_fiscais.models import AliquotaIcmsUF

DIFAL_ARREDONDAMENTO = Decimal('0.01')


def _dec(val) -> Decimal:
    if val is None or val == '':
        return Decimal('0')
    try:
        return Decimal(str(val).replace(',', '.'))
    except Exception:
        return Decimal('0')


def interestadual_regiao(uf_origem: str, uf_destino: str) -> Decimal:
    """Faixa 12% = Sul/Sudeste exceto ES. De lá: 12% dentro da faixa, 7% para fora. Demais origens: 12%."""
    if uf_origem not in UF_FAIXA_INTERESTADUAL_12:
        return Decimal('12')
    return Decimal('12') if uf_destino in UF_FAIXA_INTERESTADUAL_12 else Decimal('7')


@dataclass(frozen=True)
class LinhaDifalRetificacao:
    nf_id: int
    numero: str
    data_emissao: date
    chave_acesso: str
    uf_destino: str
    item_id: int
    descricao: str
    base_difal: Decimal
    p_emitido: Decimal
    p_correto: Decimal
    v_emitido: Decimal
    v_correto: Decimal
    diferenca: Decimal
    situacao: str
    frete_sem_base: bool = False

    @property
    def divergente(self) -> bool:
        return self.situacao != 'OK'


@dataclass
class RelatorioDifalRetificacao:
    linhas: list[LinhaDifalRetificacao] = field(default_factory=list)
    nf_avaliadas: int = 0
    nf_sem_uf_destino: int = 0
    itens_com_frete_fora_da_base: int = 0
    total_v_emitido: Decimal = Decimal('0')
    total_v_correto: Decimal = Decimal('0')
    total_diferenca: Decimal = Decimal('0')
    pendencias_tabela: list[str] = field(default_factory=list)

    @property
    def nf_divergentes(self) -> int:
        return len({linha.nf_id for linha in self.linhas if linha.divergente})


def _aliquetas_interna_map() -> dict[str, Decimal]:
    return {
        registro.uf: _dec(registro.aliquota_interna)
        for registro in AliquotaIcmsUF.objects.filter(ativo=True)
    }


def analisar_difal_retificacao(
    *,
    desde: date | None = None,
    ate: date | None = None,
    uf_exclusao_origem: str | None = None,
) -> RelatorioDifalRetificacao:
    """Varre NF-e saída autorizadas de produção e compara DIFAL emitido × correto (tabela de UF)."""
    qs = NFeSaida.objects.select_related(
        'cliente', 'pedido_venda', 'pedido_venda__empresa_emitente', 'fornecedor',
    ).prefetch_related('itens__produto').order_by('data', 'numero')
    if desde is not None:
        qs = qs.filter(data__gte=desde)
    if ate is not None:
        qs = qs.filter(data__lte=ate)

    interna_por_uf = _aliquetas_interna_map()
    rel = RelatorioDifalRetificacao()

    for nf in qs:
        if not eh_documento_producao(nf) or not eh_documento_autorizado(nf):
            continue
        ufo = _uf_origem_nf(nf)
        if uf_exclusao_origem and ufo == uf_exclusao_origem:
            continue
        rel.nf_avaliadas += 1
        ufd = _uf_destino_nf(nf)
        if len(ufd) != 2 or ufd == ufo:
            continue
        if len(ufd) != 2:
            rel.nf_sem_uf_destino += 1
            continue
        p_correto_pct = interna_por_uf.get(ufd)
        if p_correto_pct is None:
            rel.pendencias_tabela.append(f'UF {ufd} sem alíquota interna na tabela (NF {nf.numero}).')
            continue
        ali_inter = interestadual_regiao(ufo, ufd)
        difal_pct = max(p_correto_pct - ali_inter, Decimal('0'))
        frete_nf = _dec(getattr(nf, 'valor_frete', None))
        tem_frete_fora_da_base = frete_nf > 0

        for item in nf.itens.all():
            snap: dict[str, Any] = item.snapshot_fiscal or {}
            difal = snap.get('difal') or {}
            v_bc = _dec(difal.get('v_bc_uf_dest'))
            if v_bc <= 0:
                v_bc = _dec(snap.get('base_icms'))
            v_emitido = _dec(difal.get('v_icms_uf_dest'))
            p_emitido = _dec(difal.get('p_icms_uf_dest'))
            v_correto = (v_bc * difal_pct / Decimal('100')).quantize(Decimal('0.01'))
            diferenca = v_correto - v_emitido
            if not difal:
                situacao = 'NAO_CALCULADO' if abs(v_correto) >= DIFAL_ARREDONDAMENTO else 'OK'
                if situacao != 'OK':
                    diferenca = v_correto
            elif abs(diferenca) < DIFAL_ARREDONDAMENTO and v_bc > 0:
                situacao = 'OK'
            elif v_bc <= 0:
                situacao = 'SEM_BASE'
            elif diferenca > 0:
                situacao = 'A_MENOR'
            else:
                situacao = 'A_MAIOR'
            linha = LinhaDifalRetificacao(
                nf_id=nf.pk,
                numero=nf.numero,
                data_emissao=nf.data,
                chave_acesso=(nf.chave_acesso or '').strip(),
                uf_destino=ufd,
                item_id=item.pk,
                descricao=_descricao_item(item),
                base_difal=v_bc,
                p_emitido=p_emitido,
                p_correto=p_correto_pct,
                v_emitido=v_emitido,
                v_correto=v_correto,
                diferenca=diferenca,
                situacao=situacao,
                frete_sem_base=tem_frete_fora_da_base,
            )
            rel.linhas.append(linha)
            if tem_frete_fora_da_base:
                rel.itens_com_frete_fora_da_base += 1
            rel.total_v_emitido += v_emitido
            rel.total_v_correto += v_correto
            rel.total_diferenca += diferenca
    return rel


def formatar_relatorio_difal_retificacao(rel: RelatorioDifalRetificacao) -> str:
    linhas_out: list[str] = []
    divergentes = [linha for linha in rel.linhas if linha.divergente]
    cabecalho = (
        f'NF-e avaliadas (produção, autorizadas): {rel.nf_avaliadas} | '
        f'itens analisados: {len(rel.linhas)} | itens divergentes: {len(divergentes)} | '
        f'NF-e divergentes: {rel.nf_divergentes}'
    )
    linhas_out.append(cabecalho)
    linhas_out.append('')
    linhas_out.append(
        f'{"NF":>6} {"DATA":>10} {"UF":>3} {"ITEM":>5} {"BASE":>12} {"pEM":>6} {"pCOR":>6} '
        f'{"VEMIT":>12} {"VCORR":>12} {"DIF":>12} {"SIT":>13} {"FR":>2} CHAVE'
    )
    for linha in divergentes:
        linhas_out.append(
            f'{linha.numero:>6} {linha.data_emissao.isoformat():>10} {linha.uf_destino:>3} '
            f'{linha.item_id:>5} {linha.base_difal:>12.2f} {linha.p_emitido:>6.2f} {linha.p_correto:>6.2f} '
            f'{linha.v_emitido:>12.2f} {linha.v_correto:>12.2f} {linha.diferenca:>12.2f} '
            f'{linha.situacao:>13} {("F" if linha.frete_sem_base else "-"):>2} {linha.chave_acesso}'
        )
    linhas_out.append('')
    linhas_out.append(
        f'TOTAIS — DIFAL emitido R$ {rel.total_v_emitido:.2f} | '
        f'DIFAL correto R$ {rel.total_v_correto:.2f} | '
        f'diferença R$ {rel.total_diferenca:.2f}'
    )
    if rel.nf_sem_uf_destino:
        linhas_out.append(f'NF-e sem UF destino resolvida: {rel.nf_sem_uf_destino}')
    if rel.itens_com_frete_fora_da_base:
        linhas_out.append(
            f'ITENS COM FRETE FORA DA BASE (coluna FR=F): {rel.itens_com_frete_fora_da_base} — '
            'a BC do DIFAL é o valor da operação (frete, seguro, despesas acessórias); '
            'para esses itens o DIFAL correto está subestimado neste relatório.'
        )
    for pend in rel.pendencias_tabela:
        linhas_out.append(f'PENDÊNCIA: {pend}')
    if not divergentes:
        linhas_out.append('Nenhuma divergência de DIFAL identificada.')
    return '\n'.join(linhas_out)
