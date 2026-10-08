"""Dashboard operacional real — agregações por bloco (ERP 4.0.6 / 4.0.8)."""

from __future__ import annotations

from django.utils import timezone

from nexus_erp.dashboard_bi_service import MODULO_BUILDERS
from nexus_erp.dashboard_filters import parse_dashboard_filters
from nexus_erp.dashboard_permissions import permissoes_dashboard


def montar_dashboard_resumo(user=None) -> dict:
    """Compatibilidade com formato 4.0.6 — omite blocos sem permissão."""
    f = parse_dashboard_filters({})
    perms = permissoes_dashboard(user) if user else {
        k: True for k in (
            'pode_ver_comercial', 'pode_ver_fiscal', 'pode_ver_estoque',
            'pode_ver_compras', 'pode_ver_qualidade', 'pode_ver_financeiro',
            'pode_ver_consolidado',
        )
    }

    comercial = MODULO_BUILDERS['comercial'](f) if perms.get('pode_ver_comercial') else None
    fiscal = MODULO_BUILDERS['fiscal'](f) if perms.get('pode_ver_fiscal') else None
    estoque = MODULO_BUILDERS['estoque'](f) if perms.get('pode_ver_estoque') else None
    financeiro = MODULO_BUILDERS['financeiro'](f) if perms.get('pode_ver_financeiro') else None

    alertas = []
    if comercial:
        alertas.extend(comercial.get('alertas', []))
    if fiscal:
        alertas.extend(fiscal.get('alertas', []))
    if estoque:
        alertas.extend(estoque.get('alertas', []))

    def _legacy_comercial(bi):
        if not bi:
            return {
                'pedidos_abertos': 0,
                'pedidos_parcialmente_faturados': 0,
                'pedidos_faturados_mes': 0,
                'valor_aberto_faturar': '0',
                'valor_faturado_mes': '0',
                'ultimos_pedidos': [],
            }
        k = {x['id']: x for x in bi['kpis']}
        ultimos = [u for u in bi.get('ultimos', []) if u.get('tipo') == 'pedido_venda']
        return {
            'pedidos_abertos': k.get('pedidos_abertos', {}).get('valor', 0),
            'pedidos_parcialmente_faturados': k.get('pedidos_parciais', {}).get('valor', 0),
            'pedidos_faturados_mes': k.get('pedidos_faturados', {}).get('valor', 0),
            'valor_aberto_faturar': k.get('valor_aberto', {}).get('valor', '0'),
            'valor_faturado_mes': k.get('valor_faturado', {}).get('valor', '0'),
            'ultimos_pedidos': [
                {
                    'id': 0,
                    'numero': u['titulo'],
                    'cliente': u.get('subtitulo', ''),
                    'data': u.get('data', ''),
                    'valor_total': u.get('valor', '0'),
                    'status': u.get('status', ''),
                    'link': u.get('link', ''),
                }
                for u in ultimos
            ],
        }

    def _legacy_fiscal(bi):
        if not bi:
            return {
                'nfe_saida_rascunhos': 0,
                'nfe_saida_prontas_emissao': 0,
                'nfe_saida_autorizadas_homologacao': 0,
                'nfe_saida_rejeitadas_homologacao': 0,
                'nfe_saida_erro_transmissao': 0,
                'nfe_saida_canceladas': 0,
                'nfe_entrada_total': 0,
                'ultimas_nfe_saida': [],
                'ultimas_nfe_entrada': [],
                'sefaz_ultimo_status': None,
            }
        k = {x['id']: x for x in bi['kpis']}
        ult_s = [u for u in bi.get('ultimos', []) if u.get('tipo') == 'nfe_saida']
        sefaz_link = next((l for l in bi.get('links', []) if l.get('id') == 'sefaz_status'), None)
        sefaz = None
        if sefaz_link:
            parts = (sefaz_link.get('descricao') or '').split(': cStat ', 1)
            sefaz = {
                'ambiente': parts[0] if parts else '',
                'cstat': parts[1].split(' — ')[0] if len(parts) > 1 else '',
                'xmotivo': parts[1].split(' — ')[1] if len(parts) > 1 and ' — ' in parts[1] else '',
                'consultado_em': '',
                'empresa': '',
            }
        return {
            'nfe_saida_rascunhos': k.get('nfe_rascunhos', {}).get('valor', 0),
            'nfe_saida_prontas_emissao': k.get('nfe_prontas', {}).get('valor', 0),
            'nfe_saida_autorizadas_homologacao': k.get('nfe_auth_homolog', {}).get('valor', 0),
            'nfe_saida_rejeitadas_homologacao': k.get('nfe_rej_homolog', {}).get('valor', 0),
            'nfe_saida_erro_transmissao': k.get('nfe_erro_tx', {}).get('valor', 0),
            'nfe_saida_canceladas': k.get('nfe_canceladas', {}).get('valor', 0),
            'nfe_entrada_total': k.get('nfe_entrada_total', {}).get('valor', 0),
            'ultimas_nfe_saida': [
                {
                    'id': 0,
                    'titulo': u['titulo'],
                    'subtitulo': '',
                    'cliente': u.get('subtitulo', ''),
                    'status': u.get('status', ''),
                    'cstat': '',
                    'valor_total': u.get('valor', '0'),
                    'link': u.get('link', ''),
                }
                for u in ult_s
            ],
            'ultimas_nfe_entrada': [],
            'sefaz_ultimo_status': sefaz,
        }

    def _legacy_estoque(bi):
        if not bi:
            return {
                'produtos_cadastrados': 0,
                'produtos_sem_ncm': 0,
                'produtos_estoque_baixo': 0,
                'alertas_estoque': [],
            }
        k = {x['id']: x for x in bi['kpis']}
        return {
            'produtos_cadastrados': k.get('produtos_cadastrados', {}).get('valor', 0),
            'produtos_sem_ncm': k.get('produtos_sem_ncm', {}).get('valor', 0),
            'produtos_estoque_baixo': k.get('estoque_baixo', {}).get('valor', 0),
            'alertas_estoque': [],
        }

    def _legacy_financeiro(bi):
        vazio = {
            'modulo': 'operacional',
            'mensagem': '',
            'contas_receber_aberto': '0',
            'contas_receber_vencidas': '0',
            'recebido_mes': '0',
            'contas_pagar_aberto': '0',
            'contas_pagar_vencidas': '0',
            'pago_mes': '0',
            'saldo_previsto': '0',
        }
        if not bi or bi.get('em_preparacao'):
            if not bi:
                vazio['modulo'] = 'indisponivel'
                vazio['mensagem'] = 'Sem permissão para o módulo financeiro.'
            else:
                vazio['modulo'] = 'em_preparacao'
                vazio['mensagem'] = bi.get('mensagem', '')
            return vazio
        k = {x['id']: x for x in bi.get('kpis', [])}
        return {
            'modulo': 'operacional',
            'mensagem': '',
            'contas_receber_aberto': str(k.get('cr_aberto', {}).get('valor', '0')),
            'contas_receber_vencidas': str(k.get('cr_vencido', {}).get('valor', '0')),
            'recebido_mes': str(k.get('recebido_periodo', {}).get('valor', '0')),
            'contas_pagar_aberto': str(k.get('cp_aberto', {}).get('valor', '0')),
            'contas_pagar_vencidas': str(k.get('cp_vencido', {}).get('valor', '0')),
            'pago_mes': str(k.get('pago_periodo', {}).get('valor', '0')),
            'saldo_previsto': str(k.get('saldo_previsto', {}).get('valor', '0')),
        }

    com = _legacy_comercial(comercial)
    fis = _legacy_fiscal(fiscal)
    est = _legacy_estoque(estoque)
    fin = _legacy_financeiro(financeiro)

    cards = {}
    if comercial:
        cards['valor_a_faturar'] = com['valor_aberto_faturar']
        cards['pedidos_abertos'] = com['pedidos_abertos']
    if fiscal:
        cards['nfe_pendentes_rejeitadas'] = (
            fis['nfe_saida_rejeitadas_homologacao']
            + fis['nfe_saida_erro_transmissao']
            + fis['nfe_saida_rascunhos']
        )
    if estoque:
        cards['estoque_baixo'] = est['produtos_estoque_baixo']

    return {
        'comercial': com,
        'fiscal': fis,
        'financeiro': fin,
        'estoque': est,
        'alertas': [
            {
                'tipo': a.get('titulo', ''),
                'severidade': a.get('severidade', 'info'),
                'mensagem': a.get('mensagem', ''),
                'link': a.get('link', ''),
            }
            for a in alertas
        ],
        'cards_principais': cards,
        'permissoes': perms,
        'gerado_em': timezone.now().isoformat(),
    }
