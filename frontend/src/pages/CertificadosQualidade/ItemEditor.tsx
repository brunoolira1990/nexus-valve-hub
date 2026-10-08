/**
 * Editor de item do Certificado de Qualidade.
 *
 * Etapa 5b-1 — subconjunto do editor do modal antigo:
 *  - Inputs basicos (ordem, codigo, descricao, qtd, un, norma, lote, ncm)
 *  - Tipo de dados tecnicos
 *  - Incluir no certificado + motivo/observacao
 *
 * Proximas sub-etapas:
 *  - 5b-2: corrida/lote + rastreabilidade por produto
 *  - 5b-3: composicao + ensaios
 *  - 5b-4: componentes de valvula
 *  - Etapa 6: corridas CF (via modal existente)
 */
import type { ItemCertificadoQualidade } from '@/types';
import {
  LABEL_OBRIGATORIO_EMITIR,
  MOTIVOS_NAO_INCLUSAO,
} from '@/lib/certificadoQualidadeConstants';
import {
  origemFisicaCqBadge,
  origemFisicaCqItem,
  rastreabilidadeCqBadge,
} from '@/lib/certificadoStatusUi';

type Props = {
  item: ItemCertificadoQualidade;
  idx: number;
  disabled?: boolean;
  onChange: (patch: Partial<ItemCertificadoQualidade>) => void;
};

export function ItemEditor({ item: it, idx, disabled, onChange }: Props) {
  const incl = it.incluir_no_certificado !== false;

  return (
    <details
      open
      className={`rounded border p-3 ${!incl ? 'border-amber-300 bg-amber-50/30 dark:border-amber-700 dark:bg-amber-900/10' : 'border-border'}`}
    >
      <summary className="cursor-pointer text-sm font-medium">
        <span className="inline-flex items-center gap-2 flex-wrap">
          <span>
            Item {it.ordem || idx + 1} - {it.codigo_produto || 'Sem codigo'} -{' '}
            {it.descricao_material || 'Sem descricao'}
          </span>
          {!incl ? (
            <span className="erp-badge-warning">Nao incluido</span>
          ) : (
            <span className="erp-badge-success">Incluido</span>
          )}
          {incl && it.rastreabilidade_status ? (
            <span
              className={`${rastreabilidadeCqBadge(it.rastreabilidade_status).className} text-[10px]`}
              title="Prontidao tecnica: dados exigidos para emissao do CQ. Nao comprova a origem fisica do material."
            >
              {it.rastreabilidade_label || rastreabilidadeCqBadge(it.rastreabilidade_status).label}
            </span>
          ) : null}
          {incl ? (
            <span
              className={`${origemFisicaCqBadge(origemFisicaCqItem(it)).className} text-[10px]`}
              title="Origem documental: vinculo com Certificado de Fornecedor e corrida/lote registrados."
            >
              {origemFisicaCqBadge(origemFisicaCqItem(it)).label}
            </span>
          ) : null}
        </span>
      </summary>

      {incl && (it.rastreabilidade_avisos?.length ?? 0) > 0 ? (
        <ul className="text-[11px] text-sky-800 dark:text-sky-300 mt-1 mb-2 list-disc pl-5">
          {it.rastreabilidade_avisos!.map((msg) => (
            <li key={msg}>{msg}</li>
          ))}
        </ul>
      ) : null}

      {incl && (it.rastreabilidade_mensagens?.length ?? 0) > 0 ? (
        <ul className="text-[11px] text-amber-800 dark:text-amber-300 mt-1 mb-2 list-disc pl-5">
          {it.rastreabilidade_mensagens!.map((msg) => (
            <li key={msg}>{msg}</li>
          ))}
        </ul>
      ) : null}

      <div className="grid grid-cols-1 md:grid-cols-6 gap-2 mt-3">
        <div>
          <label className="erp-label">Ordem</label>
          <input
            className="erp-input mt-1"
            value={it.ordem}
            disabled={disabled}
            onChange={(e) => onChange({ ordem: +e.target.value })}
          />
        </div>
        <div>
          <label className="erp-label">Codigo</label>
          <input
            className="erp-input mt-1"
            value={it.codigo_produto}
            disabled={disabled}
            onChange={(e) => onChange({ codigo_produto: e.target.value })}
          />
        </div>
        <div className="md:col-span-2">
          <label className="erp-label">Descricao{LABEL_OBRIGATORIO_EMITIR}</label>
          <input
            className="erp-input mt-1"
            value={it.descricao_material}
            disabled={disabled}
            onChange={(e) => onChange({ descricao_material: e.target.value })}
          />
        </div>
        <div>
          <label className="erp-label">Qtd</label>
          <input
            className="erp-input mt-1"
            value={it.quantidade}
            disabled={disabled}
            onChange={(e) => onChange({ quantidade: +e.target.value })}
          />
        </div>
        <div>
          <label className="erp-label">Un</label>
          <input
            className="erp-input mt-1"
            value={it.unidade}
            disabled={disabled}
            onChange={(e) => onChange({ unidade: e.target.value })}
          />
        </div>
        <div>
          <label className="erp-label">Norma{LABEL_OBRIGATORIO_EMITIR}</label>
          <input
            className="erp-input mt-1"
            value={it.norma}
            disabled={disabled}
            onChange={(e) => onChange({ norma: e.target.value })}
          />
        </div>
        <div>
          <label className="erp-label">Lote{LABEL_OBRIGATORIO_EMITIR}</label>
          <input
            className="erp-input mt-1"
            value={it.lote || ''}
            disabled={disabled}
            onChange={(e) => onChange({ lote: e.target.value })}
          />
        </div>
        <div>
          <label className="erp-label">NCM</label>
          <input
            className="erp-input mt-1"
            value={it.ncm || ''}
            disabled={disabled}
            onChange={(e) => onChange({ ncm: e.target.value })}
          />
        </div>
        <div className="md:col-span-3">
          <label className="erp-label">Tipo de dados tecnicos</label>
          <select
            className="erp-select mt-1 w-full"
            value={it.tipo_dados_tecnicos || 'PADRAO_ITEM'}
            disabled={disabled}
            onChange={(e) =>
              onChange({
                tipo_dados_tecnicos: e.target.value as 'PADRAO_ITEM' | 'VALVULA_COMPONENTES',
              })
            }
          >
            <option value="PADRAO_ITEM">Dados por item</option>
            <option value="VALVULA_COMPONENTES">Dados por componentes de valvula</option>
          </select>
        </div>
        <div className="md:col-span-6 rounded border border-border p-2">
          <label className="inline-flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={incl}
              disabled={disabled}
              onChange={(e) => onChange({ incluir_no_certificado: e.target.checked })}
            />
            Incluir no certificado
          </label>
          {!incl ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2">
              <div>
                <label className="erp-label">Motivo da nao inclusao</label>
                <select
                  className="erp-select mt-1 w-full"
                  value={it.motivo_nao_inclusao || ''}
                  disabled={disabled}
                  onChange={(e) => onChange({ motivo_nao_inclusao: e.target.value })}
                >
                  <option value="">Selecione...</option>
                  {MOTIVOS_NAO_INCLUSAO.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="erp-label">Observacao interna</label>
                <input
                  className="erp-input mt-1"
                  value={it.observacao_nao_inclusao || ''}
                  disabled={disabled}
                  onChange={(e) => onChange({ observacao_nao_inclusao: e.target.value })}
                />
              </div>
              <div className="md:col-span-2 text-xs text-amber-700 dark:text-amber-300">
                Nao incluido
                {it.motivo_nao_inclusao ? ` - Motivo: ${it.motivo_nao_inclusao}` : ''}.
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </details>
  );
}
