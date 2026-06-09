"""Gera arquivos XML de debug para diagnóstico NF-e (schema / rejeição 225)."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.empresa_emitente import resolver_empresa_emitente_nfe
from apps.fiscal.nfe_emissao.envi_nfe import montar_envi_nfe_xml
from apps.fiscal.nfe_emissao.schema_validacao import validar_emissao_completa
from apps.fiscal.nfe_emissao.xml_compactacao import debug_xml_bytes, validar_xml_sem_caracteres_edicao
from apps.fiscal.nfe_emissao.xml_oficial import gerar_xml_oficial_emissao


class Command(BaseCommand):
    help = 'Gera XMLs de debug NF-e em media/debug/ (pré-assinatura, assinado, enviNFe, retorno).'

    def add_arguments(self, parser):
        parser.add_argument('--nfe-id', type=int, required=True, help='ID da NFeSaida')
        parser.add_argument(
            '--tipo',
            choices=['pre', 'assinado', 'enviNFe', 'retorno', 'todos'],
            default='todos',
            help='Tipo de XML a gerar/exibir',
        )

    def handle(self, *args, **options):
        nfe_id = options['nfe_id']
        tipo = options['tipo']

        try:
            nf = NFeSaida.objects.get(pk=nfe_id)
        except NFeSaida.DoesNotExist as exc:
            raise CommandError(f'NF-e id={nfe_id} não encontrada.') from exc

        debug_dir = Path(settings.MEDIA_ROOT) / 'debug'
        debug_dir.mkdir(parents=True, exist_ok=True)

        prefix = f'nfe_{nfe_id}'
        arquivos: dict[str, str] = {}

        if tipo in ('pre', 'todos', 'assinado', 'enviNFe'):
            try:
                xml_pre = gerar_xml_oficial_emissao(nf).decode('utf-8')
            except Exception as exc:
                raise CommandError(f'Falha ao gerar XML: {exc}') from exc
            arquivos[f'{prefix}_pre_assinatura.xml'] = xml_pre

            assinado = (nf.xml_assinado or '').strip()
            if tipo in ('assinado', 'enviNFe', 'todos'):
                try:
                    from apps.fiscal.nfe_emissao.assinatura import assinar_xml_nfe

                    empresa = resolver_empresa_emitente_nfe(nf)
                    assinado = assinar_xml_nfe(xml_pre, empresa, nfe_saida=nf).decode('utf-8')
                except Exception as exc:
                    self.stderr.write(f'Aviso: não foi possível assinar — {exc}')
                if assinado:
                    arquivos[f'{prefix}_assinada.xml'] = assinado
                    envi = montar_envi_nfe_xml(assinado, id_lote=int(nf.pk), ind_sinc=1)
                    arquivos[f'{prefix}_enviNFe.xml'] = envi
                    validacao = validar_emissao_completa(
                        assinado,
                        envi,
                        validar_assinado=True,
                        xml_pre_assinatura=xml_pre,
                    )
                    self.stdout.write(
                        self.style.WARNING(
                            f'Validação: ok={validacao.get("ok")} tipo={validacao.get("tipo")} '
                            f'compacto={validacao.get("compacto")} schema_ok={validacao.get("schema_ok")}',
                        ),
                    )
                    for err in (validacao.get('erros') or [])[:10]:
                        self.stdout.write(f'  - {err.get("contexto", "")} {err.get("mensagem")}')

        lote_salvo = (nf.xml_envio_lote or '').strip()
        if lote_salvo and tipo in ('enviNFe', 'todos'):
            arquivos[f'{prefix}_enviNFe_salvo_sefaz.xml'] = lote_salvo
            diag = debug_xml_bytes(lote_salvo)
            self.stdout.write(self.style.WARNING(f'Diagnóstico lote salvo SEFAZ: {diag}'))
            ed = validar_xml_sem_caracteres_edicao(lote_salvo)
            if not ed.get('ok'):
                self.stdout.write(self.style.ERROR(f'cStat 588 provável: {ed.get("mensagem")}'))

        if tipo in ('retorno', 'todos'):
            retorno = (nf.xml_retorno_lote or nf.xml_retorno or '').strip()
            if retorno:
                arquivos[f'{prefix}_retorno.xml'] = retorno
            else:
                self.stderr.write('Aviso: sem XML de retorno SEFAZ salvo.')

        for nome, conteudo in arquivos.items():
            path = debug_dir / nome
            path.write_text(conteudo, encoding='utf-8')
            self.stdout.write(self.style.SUCCESS(f'Gravado: {path}'))

        if tipo == 'assinado' and f'{prefix}_assinada.xml' in arquivos:
            self.stdout.write('\n--- XML assinado ---\n')
            self.stdout.write(arquivos[f'{prefix}_assinada.xml'][:4000])
