import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { NcmAutocomplete, type NcmOption } from '@/components/produtos/NcmAutocomplete';
import type { ProdutoFormState } from '../types';
import type { FamiliaProduto } from '@/types';
import { ncmApiService } from '@/services/api/produtos';
import { useState, useEffect } from 'react';
import { ORIGEM_MERCADORIA_OPTIONS } from './constants';

interface ProdutoFiscalFormTabProps {
  form: ProdutoFormState;
  setForm: (updater: (prev: ProdutoFormState) => ProdutoFormState) => void;
  preview?: { ncm?: string };
  familiaSelecionada?: FamiliaProduto | null;
}

export function ProdutoFiscalFormTab({
  form,
  setForm,
  preview,
  familiaSelecionada,
}: ProdutoFiscalFormTabProps) {
  const [ncmProdutoOption, setNcmProdutoOption] = useState<NcmOption | null>(null);

  // Inicializa o autocomplete com o NCM já salvo no produto ao montar o tab
  // ou quando form.ncm mudar externamente (ex.: reset do formulário).
  useEffect(() => {
    if (!form.ncm) {
      setNcmProdutoOption(null);
      return;
    }
    // Evita re-busca se a opção já está sincronizada com o código atual
    if (ncmProdutoOption?.codigo === form.ncm) return;

    ncmApiService
      .search(form.ncm, 1)
      .then((results) => {
        const match = results.find((o) => o.codigo === form.ncm);
        setNcmProdutoOption(match ?? null);
      })
      .catch(() => setNcmProdutoOption(null));
    // ncmProdutoOption intencionalmente omitido: só re-executa quando o código muda,
    // não quando a opção interna é atualizada por este mesmo efeito.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.ncm]);

  const handleInputChange = <K extends keyof ProdutoFormState>(
    key: K,
    value: ProdutoFormState[K]
  ) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  // NCM efetivo: produto override > família > não definido
  const ncmEfetivo = form.ncm || familiaSelecionada?.ncm_padrao_info?.codigo || 'NÃO DEFINIDO';
  const ncmEfetivoDesc = familiaSelecionada?.ncm_padrao_info?.descricao || '';
  const ncmOrigem = form.ncm ? 'override no produto' : (familiaSelecionada?.ncm_padrao_id ? 'família / figura' : 'não definido');

  return (
    <div className="space-y-4">
      {/* NCM Efetivo - Read Only */}
      <div className="rounded-lg border border-primary/30 bg-primary/5 p-4 space-y-2">
        <p className="text-sm font-semibold">NCM efetivo para tributação</p>
        <p className="text-lg font-mono">{ncmEfetivo}</p>
        <p className="text-xs text-muted-foreground">
          Este é o código utilizado em NF-e e regras fiscais. Origem: {ncmOrigem}
        </p>
        {ncmEfetivoDesc && (
          <p className="text-sm text-muted-foreground">{ncmEfetivoDesc}</p>
        )}
      </div>

      {/* NCM no produto (override opcional) */}
      <div className="space-y-2">
        <Label>NCM no produto (override opcional)</Label>
        <NcmAutocomplete
          value={ncmProdutoOption}
          onChange={(opt) => {
            setNcmProdutoOption(opt);
            handleInputChange('ncm', opt?.codigo || '');
          }}
          searchNcm={(term, limit) => ncmApiService.search(term, limit)}
          placeholder="Digite código ou descrição do NCM..."
        />
        <p className="text-xs text-muted-foreground">
          Preencha para sobrescrever o NCM da família. Vazio = herda da família/figura.
        </p>
        {form.ncm && (
          <button
            type="button"
            className="erp-btn-outline erp-btn-sm mt-2 w-full sm:w-auto"
            onClick={() => {
              handleInputChange('ncm', '');
              setNcmProdutoOption(null);
            }}
          >
            Remover override e usar NCM da família
          </button>
        )}
      </div>

      {/* Campos fiscais adicionais */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Origem da mercadoria */}
        <div className="space-y-1">
          <Label>Origem da mercadoria</Label>
          <Select
            value={form.origem || '0'}
            onValueChange={(v) => handleInputChange('origem', v)}
            className="w-full"
          >
            <SelectTrigger className="erp-select">
              <SelectValue placeholder="Selecione a origem" />
            </SelectTrigger>
            <SelectContent>
              {ORIGEM_MERCADORIA_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* NCM específico (legado) */}
        <div className="space-y-1">
          <Label>NCM específico (legado)</Label>
          <Input
            className="erp-input mt-1"
            value={form.ncm_especifico || ''}
            onChange={(e) => handleInputChange('ncm_especifico', e.target.value)}
            placeholder="NCM específico legado"
          />
        </div>

        {/* Unidade específica (override) */}
        <div className="space-y-1">
          <Label>Unidade específica (override)</Label>
          <Input
            className="erp-input mt-1"
            value={form.unidade_especifica || ''}
            onChange={(e) => handleInputChange('unidade_especifica', e.target.value)}
            placeholder="Override de unidade para este produto"
          />
        </div>

        {/* Unidade fiscal */}
        <div className="space-y-1">
          <Label>Unidade fiscal</Label>
          <Input
            className="erp-input mt-1"
            value={form.unidade_fiscal || ''}
            onChange={(e) => handleInputChange('unidade_fiscal', e.target.value)}
            placeholder="Unidade para fins fiscais (NF-e)"
          />
        </div>

        {/* Unidade estoque efetiva - Read Only */}
        <div className="space-y-1">
          <Label>Unidade estoque efetiva</Label>
          <Input
            className="erp-input mt-1 bg-muted/40 cursor-default"
            value={form.unidade_estoque || form.unidade || '—'}
            readOnly
          />
          <p className="text-xs text-muted-foreground">
            Somente leitura. Ajuste unidades na aba Classificação industrial.
          </p>
        </div>
      </div>

      {/* Alíquotas base de referência (informativas) */}
      <section className="rounded-lg border border-border bg-muted/20 p-4 space-y-3">
        <p className="text-sm font-semibold text-foreground">Alíquotas base de referência (informativas)</p>
        <p className="text-xs text-muted-foreground">
          Estas alíquotas são de referência e podem variar conforme a operação, estado e regime tributário.
          Consulte a legislação vigente e seu contador para valores aplicáveis.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <div className="rounded-md border border-border bg-background p-3">
            <p className="text-xs text-muted-foreground">IPI</p>
            <p className="font-mono text-lg">—</p>
            <p className="text-[11px] text-muted-foreground">Consultar TIPI</p>
          </div>
          <div className="rounded-md border border-border bg-background p-3">
            <p className="text-xs text-muted-foreground">PIS/COFINS</p>
            <p className="font-mono text-lg">—</p>
            <p className="text-[11px] text-muted-foreground">Consultar regime</p>
          </div>
          <div className="rounded-md border border-border bg-background p-3">
            <p className="text-xs text-muted-foreground">ICMS</p>
            <p className="font-mono text-lg">—</p>
            <p className="text-[11px] text-muted-foreground">Consultar estado</p>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          <strong>Nota:</strong> As alíquotas efetivas são determinadas no momento da operação fiscal
          com base na NCM, CST/CSOSN, origem, destino e regime tributário da empresa.
        </p>
      </section>
    </div>
  );
}