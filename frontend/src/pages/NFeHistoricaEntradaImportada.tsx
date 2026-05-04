import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileUp, FileCheck, Copy, AlertCircle } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { apiErrorMessage } from '@/services/api/config';
import { empresasService } from '@/services/api/empresas';
import { fornecedoresService } from '@/services/api/fornecedores';
import {
  nfeHistoricaEntradaImportadaService,
  type NFeEntradaHistoricaDetalhe,
  type NFeEntradaHistoricaImportResultado,
  type NFeEntradaHistoricaList,
} from '@/services/api/nfeHistoricaEntradaImportada';
import type { Empresa, Fornecedor } from '@/types';

const NFeHistoricaEntradaImportada = () => {
  const navigate = useNavigate();
  const [lista, setLista] = useState<NFeEntradaHistoricaList[]>([]);
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const [resultado, setResultado] = useState<NFeEntradaHistoricaImportResultado | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [detalhe, setDetalhe] = useState<NFeEntradaHistoricaDetalhe | null>(null);
  const [modal, setModal] = useState(false);
  const [empresaId, setEmpresaId] = useState('');
  const [fornecedorId, setFornecedorId] = useState('');
  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const [fornecedores, setFornecedores] = useState<Fornecedor[]>([]);

  const load = useCallback(async () => {
    const qs = new URLSearchParams();
    if (empresaId) qs.set('empresa_destinataria_id', empresaId);
    if (fornecedorId) qs.set('fornecedor_id', fornecedorId);
    setLista(await nfeHistoricaEntradaImportadaService.list(qs));
  }, [empresaId, fornecedorId]);

  useEffect(() => {
    void load().catch((e) => setErro(apiErrorMessage(e)));
  }, [load]);

  useEffect(() => {
    void (async () => {
      const [e, f] = await Promise.all([empresasService.getAll(), fornecedoresService.getAll()]);
      setEmpresas(e);
      setFornecedores(f);
    })().catch((e) => setErro(apiErrorMessage(e)));
  }, []);

  const onFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setErro(null);
    setBusy(true);
    try {
      const res = await nfeHistoricaEntradaImportadaService.importarXmls(Array.from(files));
      setResultado(res);
      await load();
    } catch (e) {
      setErro(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const filtrados = lista.filter((x) => x.chave_acesso.includes(search) || `${x.numero}/${x.serie}`.includes(search) || (x.fornecedor_nome || '').toLowerCase().includes(search.toLowerCase()));

  return (
    <div>
      <PageHeader title="NF-e entrada histórica (importação XML)" searchValue={search} onSearch={setSearch} />

      <div className="erp-card p-6 mb-6 border-dashed border-2 border-border">
        <div className="flex flex-col md:flex-row md:items-center gap-4">
          <div className="flex-1">
            <h2 className="font-semibold text-foreground flex items-center gap-2"><FileUp className="h-5 w-5" />Importar XMLs de NF-e de entrada</h2>
            <p className="text-sm text-muted-foreground mt-1">Base histórica fiscal/gerencial, sem gerar movimentação operacional.</p>
          </div>
          <label className="erp-btn-primary cursor-pointer shrink-0">
            <input type="file" accept=".xml,application/xml,text/xml" multiple className="hidden" disabled={busy} onChange={(e) => { void onFiles(e.target.files); e.target.value = ''; }} />
            {busy ? 'Importando…' : 'Selecionar XMLs'}
          </label>
        </div>
        {erro && <p className="text-sm text-destructive mt-3">{erro}</p>}
      </div>

      {resultado && (
        <div className="erp-card p-4 mb-4 grid md:grid-cols-3 gap-3">
          <div><div className="text-xs text-muted-foreground">Importadas</div><div className="text-xl font-semibold">{resultado.resumo.importadas}</div></div>
          <div><div className="text-xs text-muted-foreground">Duplicadas</div><div className="text-xl font-semibold">{resultado.resumo.duplicadas}</div></div>
          <div><div className="text-xs text-muted-foreground">Erros</div><div className="text-xl font-semibold">{resultado.resumo.erros}</div></div>
          {resultado.importadas.slice(0, 5).map((r) => <div key={r.id} className="text-xs text-muted-foreground"><FileCheck className="inline h-3 w-3 mr-1 text-success" />{r.arquivo}</div>)}
          {resultado.duplicadas.slice(0, 5).map((r) => <div key={`${r.arquivo}-${r.chave_acesso}`} className="text-xs text-muted-foreground"><Copy className="inline h-3 w-3 mr-1" />{r.arquivo}</div>)}
          {resultado.erros.slice(0, 5).map((r) => <div key={r.arquivo} className="text-xs text-destructive"><AlertCircle className="inline h-3 w-3 mr-1" />{r.arquivo}: {r.mensagem}</div>)}
        </div>
      )}

      <div className="erp-card p-3 mb-4 flex flex-wrap gap-3">
        <select className="erp-select" value={empresaId} onChange={(e) => setEmpresaId(e.target.value)}>
          <option value="">Empresa destinatária (todas)</option>
          {empresas.map((e) => <option key={e.id} value={e.id}>{e.razao_social}</option>)}
        </select>
        <select className="erp-select" value={fornecedorId} onChange={(e) => setFornecedorId(e.target.value)}>
          <option value="">Fornecedor emitente (todos)</option>
          {fornecedores.map((f) => <option key={f.id} value={f.id}>{f.razao_social}</option>)}
        </select>
        <button type="button" className="erp-btn-outline" onClick={() => void load()}>Atualizar</button>
      </div>

      <div className="erp-card overflow-x-auto">
        <table className="erp-table">
          <thead><tr><th>Emissão</th><th>NF</th><th>Fornecedor</th><th>Empresa (ERP)</th><th>Valor</th><th>Ações</th></tr></thead>
          <tbody>
            {filtrados.map((r) => (
              <tr key={r.id}>
                <td>{r.dh_emissao?.slice(0, 16).replace('T', ' ')}</td>
                <td>{r.numero}/{r.serie}</td>
                <td>{r.fornecedor_nome || '—'}</td>
                <td>{r.empresa_nome ? `${r.empresa_nome} (${r.papel_empresa || 'destinatario'})` : '—'}</td>
                <td>R$ {Number(r.valor_total_nf || 0).toFixed(2)}</td>
                <td>
                  <div className="flex gap-2">
                    <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => {
                      void nfeHistoricaEntradaImportadaService.getById(r.id).then((d) => { setDetalhe(d); setModal(true); }).catch((e) => setErro(apiErrorMessage(e)));
                    }}>Detalhes</button>
                    <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => navigate(`/nfe-entrada/${r.id}/conferencia`)}>Conferir entrada</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Modal isOpen={modal} onClose={() => setModal(false)} title="NF-e de entrada importada (histórico)" size="xl">
        {detalhe && (
          <div className="space-y-3 text-sm">
            <p><strong>Chave:</strong> {detalhe.chave_acesso}</p>
            <p><strong>Empresa (ERP):</strong> {detalhe.empresa_nome || '—'} {detalhe.papel_empresa ? `(${detalhe.papel_empresa})` : ''}</p>
            <p><strong>Fornecedor:</strong> {detalhe.fornecedor_nome || '—'}</p>
            <p><strong>Status XML:</strong> {detalhe.cstat || '—'} {detalhe.xmotivo ? `- ${detalhe.xmotivo}` : ''}</p>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default NFeHistoricaEntradaImportada;

