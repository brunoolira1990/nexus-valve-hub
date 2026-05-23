import { useState } from 'react';
import { CatalogCodigoFiscalSelect } from '@/components/fiscal/CatalogCodigoFiscalSelect';
import {
  AVISO_REFORMA_TRIBUTARIA_SAIDA,
  CLASSIFICACAO_TRIBUTARIA_OPCOES,
  CST_IBS_CBS_OPCOES,
  HINT_EXCECAO_REFORMA_ESCOPO,
  REFORMA_CAMPOS_CBS,
  REFORMA_CAMPOS_IBS,
  REFORMA_TRIBUTARIA_LABELS_SAIDA,
} from '@/lib/catalogosFiscais';
import type { ReformaTributariaForm } from '@/lib/regrasFiscaisSaidaHelpers';

type Props = {
  reforma: ReformaTributariaForm;
  onChange: (reforma: ReformaTributariaForm) => void;
};

type SubAbaReforma = 'ibs' | 'cbs';

export const ReformaTributariaSaidaEditor = ({ reforma, onChange }: Props) => {
  const [subAba, setSubAba] = useState<SubAbaReforma>('ibs');

  const f = (k: keyof ReformaTributariaForm, v: string) =>
    onChange({ ...reforma, [k]: v });

  const campos = subAba === 'ibs' ? REFORMA_CAMPOS_IBS : REFORMA_CAMPOS_CBS;

  return (
    <section>
      <h3 className="font-semibold text-sm mb-2 border-b border-border pb-1">Reforma Tributária</h3>
      <p className="text-[10px] text-amber-700 dark:text-amber-400 border border-amber-500/30 bg-amber-500/10 rounded px-2 py-1 mb-3">
        {AVISO_REFORMA_TRIBUTARIA_SAIDA}
      </p>
      <p className="text-[10px] text-muted-foreground mb-3">{HINT_EXCECAO_REFORMA_ESCOPO}</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
        <CatalogCodigoFiscalSelect
          label="CST IBS/CBS"
          value={reforma.cst_ibs_cbs}
          onChange={(v) => f('cst_ibs_cbs', v)}
          opcoes={CST_IBS_CBS_OPCOES}
        />
        <CatalogCodigoFiscalSelect
          label="Classificação tributária"
          value={reforma.classificacao_tributaria}
          onChange={(v) => f('classificacao_tributaria', v)}
          opcoes={CLASSIFICACAO_TRIBUTARIA_OPCOES}
        />
      </div>
      <div className="flex flex-wrap gap-1 mb-3">
        <button
          type="button"
          className={subAba === 'ibs' ? 'erp-btn-primary erp-btn-sm' : 'erp-btn-outline erp-btn-sm'}
          onClick={() => setSubAba('ibs')}
        >
          IBS
        </button>
        <button
          type="button"
          className={subAba === 'cbs' ? 'erp-btn-primary erp-btn-sm' : 'erp-btn-outline erp-btn-sm'}
          onClick={() => setSubAba('cbs')}
        >
          CBS
        </button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
        {campos.map((key) => (
          <div key={key}>
            <label className="erp-label">{REFORMA_TRIBUTARIA_LABELS_SAIDA[key] ?? key}</label>
            <input className="erp-input mt-1" value={reforma[key]} onChange={(e) => f(key, e.target.value)} />
          </div>
        ))}
      </div>
      <div>
        <label className="erp-label">{REFORMA_TRIBUTARIA_LABELS_SAIDA.observacoes}</label>
        <textarea
          className="erp-input mt-1 min-h-[72px] w-full"
          value={reforma.observacoes}
          onChange={(e) => f('observacoes', e.target.value)}
        />
      </div>
    </section>
  );
};
