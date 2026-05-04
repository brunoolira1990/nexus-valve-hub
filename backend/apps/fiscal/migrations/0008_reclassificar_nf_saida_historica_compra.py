from django.db import migrations, transaction


def _norm_digits(value):
    return ''.join(c for c in str(value or '') if c.isdigit())


def _party_doc(party):
    if not isinstance(party, dict):
        return ''
    return _norm_digits(party.get('CNPJ') or party.get('CPF') or '')


def forwards(apps, schema_editor):
    Empresa = apps.get_model('cadastros', 'Empresa')
    Fornecedor = apps.get_model('cadastros', 'Fornecedor')
    NFeSaida = apps.get_model('fiscal', 'NFeSaidaHistoricaImportada')
    NFeEntrada = apps.get_model('fiscal', 'NFeEntradaHistoricaImportada')
    ItemSaida = apps.get_model('fiscal', 'ItemNFeSaidaHistoricaImportada')
    ItemEntrada = apps.get_model('fiscal', 'ItemNFeEntradaHistoricaImportada')

    empresas_por_doc = {}
    for emp in Empresa.objects.only('id', 'cnpj'):
        doc = _norm_digits(emp.cnpj)
        if len(doc) == 14:
            empresas_por_doc[doc] = emp.id

    fornecedores_por_doc = {}
    for forn in Fornecedor.objects.only('id', 'cnpj'):
        doc = _norm_digits(forn.cnpj)
        if len(doc) == 14:
            fornecedores_por_doc[doc] = forn.id

    saidas = NFeSaida.objects.all().order_by('id')
    for nf_saida in saidas.iterator(chunk_size=500):
        emit_doc = _party_doc(nf_saida.emit_json)
        dest_doc = _party_doc(nf_saida.dest_json)
        emit_empresa_id = empresas_por_doc.get(emit_doc)
        dest_empresa_id = empresas_por_doc.get(dest_doc)

        # Critério de correção: Empresa = destinatária e emitente != Empresa.
        if not dest_empresa_id or emit_empresa_id:
            continue

        with transaction.atomic():
            if NFeEntrada.objects.filter(chave_acesso=nf_saida.chave_acesso).exists():
                nf_saida.delete()
                continue

            fornecedor_id = fornecedores_por_doc.get(emit_doc)
            nf_entrada = NFeEntrada.objects.create(
                chave_acesso=nf_saida.chave_acesso,
                numero=nf_saida.numero,
                serie=nf_saida.serie,
                modelo=nf_saida.modelo,
                dh_emissao=nf_saida.dh_emissao,
                tp_amb=nf_saida.tp_amb,
                tp_nf=nf_saida.tp_nf,
                nat_op=nf_saida.nat_op,
                versao_layout=nf_saida.versao_layout,
                cstat=nf_saida.cstat,
                xmotivo=nf_saida.xmotivo,
                protocolo=nf_saida.protocolo,
                valor_produtos=nf_saida.valor_produtos,
                valor_total_nf=nf_saida.valor_total_nf,
                v_frete=nf_saida.v_frete,
                v_seg=nf_saida.v_seg,
                v_desc=nf_saida.v_desc,
                v_outro=nf_saida.v_outro,
                emit_json=nf_saida.emit_json,
                dest_json=nf_saida.dest_json,
                totais_json=nf_saida.totais_json,
                reforma_e_outros_json=nf_saida.reforma_e_outros_json,
                prot_json=nf_saida.prot_json,
                empresa_destinataria_id=dest_empresa_id,
                fornecedor_emitente_id=fornecedor_id,
                papel_empresa_no_documento='destinatario',
                importada=nf_saida.importada,
                origem_externa=nf_saida.origem_externa,
                historica=nf_saida.historica,
                nome_arquivo=nf_saida.nome_arquivo,
            )

            itens_saida = ItemSaida.objects.filter(nf_id=nf_saida.id).order_by('n_item')
            ItemEntrada.objects.bulk_create(
                [
                    ItemEntrada(
                        nf_id=nf_entrada.id,
                        n_item=item.n_item,
                        prod_json=item.prod_json,
                        imposto_json=item.imposto_json,
                    )
                    for item in itens_saida
                ]
            )
            nf_saida.delete()


def backwards(apps, schema_editor):
    # Migração corretiva sem rollback automático para evitar recolocar dados no fluxo incorreto.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('fiscal', '0007_nfe_entrada_historica_importada'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
