import { type ReactNode } from 'react';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { FileText, Calculator, Percent } from 'lucide-react';
import { NcmAutocomplete, type NcmOption } from '@/components/produtos/NcmAutocomplete';
import type { ProdutoFormState } from '../types';
import type { FamiliaProduto } from '@/types';
import { ncmApiService } from '@/services/api/produtos';
import { useState, useEffect } from 'react';

/** Rótulo de campo padronizado (text-sm font-medium mb-1.5). */
function CampoLabel({ children }: { children: ReactNode }) {
  return <Label className="text-sm font-medium mb-1.5 block">{children}</Label>;
}

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
  const ncmOrigem = form.ncm
    ? 'override no produto'
    : familiaSelecionada?.ncm_padrao_id
    ? 'família / figura'
    : 'não definido';

  return (
    <div className="space-y-6">
      {/* ===== NCM efetivo ===== */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">NCM efetivo para tributação</CardTitle>
          </div>
          <CardDescription className="text-xs">
            Código utilizado em NF-e e regras fiscais. Origem: {ncmOrigem}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* NCM efetivo — read only */}
          <div className="rounded-md border border-primary/30 bg-primary/5 p-3 space-y-1">
            <p className="font-mono text-lg font-semibold">{ncmEfetivo}</p>
            {ncmEfetivoDesc && (
              <p className="text-sm text-muted-foreground">{ncmEfetivoDesc}</p>
            )}
          </div>

          {/* NCM no produto (override opcional) */}
          <div>
            <CampoLabel>NCM no produto (override opcional)</CampoLabel>
            <NcmAutocomplete
              value={ncmProdutoOption}
              onChange={(opt) => {
                setNcmProdutoOption(opt);
                handleInputChange('ncm', opt?.codigo || '');
              }}
              searchNcm={(term, limit) => ncmApiService.search(term, limit)}
              placeholder="Digite código ou descrição do NCM..."
            />
            <p className="text-xs text-muted-foreground mt-1">
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
        </CardContent>
      </Card>

      {/* ===== NCM específico e unidades ===== */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Calculator className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">NCM específico e unidades</CardTitle>
          </div>
          <CardDescription className="text-xs">
            Campos legados e unidades de controle fiscal e estoque
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {/* NCM específico (legado) */}
            <div>
              <CampoLabel>NCM específico (legado)</CampoLabel>
              <Input
                className="h-10"
                value={form.ncm_especifico || ''}
                onChange={(e) => handleInputChange('ncm_especifico', e.target.value)}
                placeholder="NCM específico legado"
              />
            </div>

            {/* Unidade específica (override) */}
            <div>
              <CampoLabel>Unidade específica (override)</CampoLabel>
              <Input
                className="h-10"
                value={form.unidade_especifica || ''}
                onChange={(e) => handleInputChange('unidade_especifica', e.target.value)}
                placeholder="Override de unidade para este produto"
              />
            </div>

            {/* Unidade fiscal */}
            <div>
              <CampoLabel>Unidade fiscal</CampoLabel>
              <Input
                className="h-10"
                value={form.unidade_fiscal || ''}
                onChange={(e) => handleInputChange('unidade_fiscal', e.target.value)}
                placeholder="Unidade para fins fiscais (NF-e)"
              />
            </div>

            {/* Unidade estoque efetiva — read only */}
            <div>
              <CampoLabel>Unidade estoque efetiva</CampoLabel>
              <Input
                className="h-10 bg-muted/40 cursor-default"
                value={form.unidade_estoque || form.unidade || '—'}
                readOnly
              />
              <p className="text-xs text-muted-foreground mt-1">
                Somente leitura. Ajuste unidades na aba Classificação industrial.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ===== Alíquotas de referência ===== */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Percent className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Alíquotas base de referência</CardTitle>
          </div>
          <CardDescription className="text-xs">
            Informativas — variam conforme operação, estado e regime tributário.
            IPI: consultar TIPI · PIS/COFINS: consultar regime · ICMS: consultar estado.
            As alíquotas efetivas são determinadas no momento da operação fiscal com base na NCM,
            CST/CSOSN, origem, destino e regime tributário da empresa.
          </CardDescription>
        </CardHeader>
      </Card>
    </div>
  );
}
