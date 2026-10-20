import { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, Save } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { NexusButton } from '@/components/nexus';
import { apiErrorMessage } from '@/services/api/config';
import {
  familiaVariacoesService,
  polegadasService,
  roscasConexaoService,
  schedulesEspessuraService,
  type FamiliaPolegadaPermitidaRow,
  type FamiliaRoscaPermitidaRow,
  type FamiliaSchedulePermitidoRow,
} from '@/services/api/produtos';
import type { Polegada, RoscaConexao, ScheduleEspessura } from '@/types';

type TipoPolegadaPermitida = 'principal' | 'secundaria' | 'ambas';

const OPCOES_TIPO_POLEGADA: { value: TipoPolegadaPermitida; label: string }[] = [
  { value: 'principal', label: 'Principal' },
  { value: 'secundaria', label: 'Secundária' },
  { value: 'ambas', label: 'Ambas' },
];

const SEM_FILTRO = '';

interface FamiliaDominioCardProps {
  familiaId: number;
}

export function FamiliaDominioCard({ familiaId }: FamiliaDominioCardProps) {
  const [roscas, setRoscas] = useState<RoscaConexao[]>([]);
  const [schedules, setSchedules] = useState<ScheduleEspessura[]>([]);
  const [polegadas, setPolegadas] = useState<Polegada[]>([]);
  const [rowsRosca, setRowsRosca] = useState<FamiliaRoscaPermitidaRow[]>([]);
  const [rowsSchedule, setRowsSchedule] = useState<FamiliaSchedulePermitidoRow[]>([]);
  const [rowsPolegada, setRowsPolegada] = useState<FamiliaPolegadaPermitidaRow[]>([]);

  const [roscaIds, setRoscaIds] = useState<number[]>([]);
  const [scheduleIds, setScheduleIds] = useState<number[]>([]);
  const [polegadaTipos, setPolegadaTipos] = useState<Record<number, TipoPolegadaPermitida>>({});
  const [roscaPadrao, setRoscaPadrao] = useState<number | null>(null);
  const [schedulePadrao, setSchedulePadrao] = useState<number | null>(null);
  const [filtroPolegada, setFiltroPolegada] = useState(SEM_FILTRO);

  const [carregandoCatalogo, setCarregandoCatalogo] = useState(true);
  const [carregandoDominio, setCarregandoDominio] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let ativo = true;
    void Promise.all([
      roscasConexaoService.getAll(),
      schedulesEspessuraService.getAll(),
      polegadasService.getAll(),
    ])
      .then(([r, s, p]) => {
        if (!ativo) return;
        setRoscas(r);
        setSchedules(s);
        setPolegadas(p);
      })
      .catch(() => {
        if (ativo) setErro('Não foi possível carregar os catálogos de rosca, schedule e polegada.');
      })
      .finally(() => {
        if (ativo) setCarregandoCatalogo(false);
      });
    return () => {
      ativo = false;
    };
  }, []);

  const recarregarDominio = useCallback(async () => {
    setCarregandoDominio(true);
    try {
      const [rr, sr, pr] = await Promise.all([
        familiaVariacoesService.listRoscasPermitidas(familiaId),
        familiaVariacoesService.listSchedulesPermitidos(familiaId),
        familiaVariacoesService.listPolegadasPermitidas(familiaId),
      ]);
      setRowsRosca(rr);
      setRowsSchedule(sr);
      setRowsPolegada(pr);

      const roscasAtivas = rr.filter((x) => x.ativo);
      setRoscaIds(roscasAtivas.map((x) => x.rosca_conexao));
      setRoscaPadrao(roscasAtivas.find((x) => x.padrao_da_familia)?.rosca_conexao ?? null);

      const schedulesAtivos = sr.filter((x) => x.ativo);
      setScheduleIds(schedulesAtivos.map((x) => x.schedule));
      setSchedulePadrao(schedulesAtivos.find((x) => x.padrao_da_familia)?.schedule ?? null);

      const tipos: Record<number, TipoPolegadaPermitida> = {};
      pr.filter((x) => x.ativo).forEach((x) => {
        tipos[x.polegada] = x.tipo;
      });
      setPolegadaTipos(tipos);
    } catch (e) {
      setErro(apiErrorMessage(e, { fallback: 'Não foi possível carregar o domínio desta família.' }));
    } finally {
      setCarregandoDominio(false);
    }
  }, [familiaId]);

  useEffect(() => {
    void recarregarDominio();
  }, [recarregarDominio]);

  const toggleRosca = (id: number, marcado: boolean) => {
    setRoscaIds((prev) => (marcado ? [...new Set([...prev, id])] : prev.filter((x) => x !== id)));
    if (!marcado) setRoscaPadrao((prev) => (prev === id ? null : prev));
  };

  const toggleSchedule = (id: number, marcado: boolean) => {
    setScheduleIds((prev) => (marcado ? [...new Set([...prev, id])] : prev.filter((x) => x !== id)));
    if (!marcado) setSchedulePadrao((prev) => (prev === id ? null : prev));
  };

  const togglePolegada = (id: number, marcado: boolean) => {
    setPolegadaTipos((prev) => {
      const next = { ...prev };
      if (marcado) next[id] = 'ambas';
      else delete next[id];
      return next;
    });
  };

  const polegadasVisiveis = useMemo(() => {
    const termo = filtroPolegada.trim().toUpperCase();
    if (!termo) return polegadas;
    return polegadas.filter(
      (p) => (p.codigo || '').toUpperCase().includes(termo) || (p.descricao || '').toUpperCase().includes(termo),
    );
  }, [polegadas, filtroPolegada]);

  const salvar = async () => {
    setErro(null);
    setSalvando(true);
    try {
      // 1) Suelta o padrão antigo antes de criar/marcar outro (constraint de padrão único).
      for (const row of rowsRosca) {
        if (row.padrao_da_familia && row.rosca_conexao !== roscaPadrao) {
          await familiaVariacoesService.patchRoscaPermitida(row.id, { padrao_da_familia: false });
        }
      }
      for (const row of rowsSchedule) {
        if (row.padrao_da_familia && row.schedule !== schedulePadrao) {
          await familiaVariacoesService.patchSchedulePermitido(row.id, { padrao_da_familia: false });
        }
      }

      // 2) Remove o que deixou de ser permitido (polegada: antes de criar o novo tipo).
      const roscaDesejada = new Set(roscaIds);
      for (const row of rowsRosca) {
        if (!roscaDesejada.has(row.rosca_conexao)) await familiaVariacoesService.removeRoscaPermitida(row.id);
      }
      const scheduleDesejado = new Set(scheduleIds);
      for (const row of rowsSchedule) {
        if (!scheduleDesejado.has(row.schedule)) await familiaVariacoesService.removeSchedulePermitido(row.id);
      }
      const chavesPolegada = new Set(
        Object.entries(polegadaTipos).map(([polegadaId, tipo]) => `${polegadaId}:${tipo}`),
      );
      for (const row of rowsPolegada) {
        if (!chavesPolegada.has(`${row.polegada}:${row.tipo}`)) {
          await familiaVariacoesService.removePolegadaPermitida(row.id);
        }
      }

      // 3) Cria novas permissões.
      const roscasExistentes = new Set(rowsRosca.map((r) => r.rosca_conexao));
      for (const id of roscaIds) {
        if (roscasExistentes.has(id)) continue;
        await familiaVariacoesService.addRoscaPermitida({
          familia: familiaId,
          rosca_conexao: id,
          padrao_da_familia: id === roscaPadrao,
        });
      }
      const schedulesExistentes = new Set(rowsSchedule.map((r) => r.schedule));
      for (const id of scheduleIds) {
        if (schedulesExistentes.has(id)) continue;
        await familiaVariacoesService.addSchedulePermitido({
          familia: familiaId,
          schedule: id,
          padrao_da_familia: id === schedulePadrao,
        });
      }
      const chavesPolegadaExistentes = new Set(rowsPolegada.map((r) => `${r.polegada}:${r.tipo}`));
      for (const [polegadaId, tipo] of Object.entries(polegadaTipos)) {
        const chave = `${polegadaId}:${tipo}`;
        if (chavesPolegadaExistentes.has(chave)) continue;
        await familiaVariacoesService.addPolegadaPermitida({
          familia: familiaId,
          polegada: Number(polegadaId),
          tipo,
        });
      }

      // 4) Marca o padrão nas linhas que já existiam.
      for (const row of rowsRosca) {
        if (row.rosca_conexao === roscaPadrao && !row.padrao_da_familia) {
          await familiaVariacoesService.patchRoscaPermitida(row.id, { padrao_da_familia: true });
        }
      }
      for (const row of rowsSchedule) {
        if (row.schedule === schedulePadrao && !row.padrao_da_familia) {
          await familiaVariacoesService.patchSchedulePermitido(row.id, { padrao_da_familia: true });
        }
      }

      await recarregarDominio();
    } catch (e) {
      setErro(apiErrorMessage(e, { fallback: 'Não foi possível salvar o domínio da família.' }));
    } finally {
      setSalvando(false);
    }
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Loader2 className={`h-4 w-4 text-muted-foreground ${carregandoDominio ? 'animate-spin' : 'invisible'}`} />
          <CardTitle className="text-base">Variações Permitidas (Domínio)</CardTitle>
        </div>
        <CardDescription className="text-xs">
          Quais roscas, schedules e polegadas pertencem a esta família. Estas listas também definem o
          padrão herdado no cadastro do produto; a validação do produto contra o domínio é etapa seguinte.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {erro && (
          <div
            role="alert"
            className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          >
            {erro}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <div>
            <Label className="text-sm font-medium mb-1.5 block">Roscas / conexões</Label>
            <div className="max-h-56 overflow-y-auto rounded-md border border-border p-2 space-y-1">
              {carregandoCatalogo ? (
                <p className="text-xs text-muted-foreground px-1 py-2">Carregando roscas…</p>
              ) : roscas.length === 0 ? (
                <p className="text-xs text-muted-foreground px-1 py-2">Nenhuma rosca cadastrada.</p>
              ) : (
                roscas.map((r) => (
                  <div key={r.id} className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="rosca-padrao"
                      aria-label={`Padrão ${r.codigo || r.descricao}`}
                      className="h-3.5 w-3.5 shrink-0 disabled:opacity-40"
                      disabled={!roscaIds.includes(r.id)}
                      checked={roscaPadrao === r.id}
                      onChange={() => setRoscaPadrao(r.id)}
                    />
                    <Checkbox
                      id={`rosca-${r.id}`}
                      checked={roscaIds.includes(r.id)}
                      onCheckedChange={(v) => toggleRosca(r.id, v === true)}
                    />
                    <Label htmlFor={`rosca-${r.id}`} className="cursor-pointer font-normal text-xs flex-1 truncate">
                      {(r.codigo || '—') + ' — ' + r.descricao}
                    </Label>
                  </div>
                ))
              )}
            </div>
          </div>

          <div>
            <Label className="text-sm font-medium mb-1.5 block">Schedules / espessuras</Label>
            <div className="max-h-56 overflow-y-auto rounded-md border border-border p-2 space-y-1">
              {carregandoCatalogo ? (
                <p className="text-xs text-muted-foreground px-1 py-2">Carregando schedules…</p>
              ) : schedules.length === 0 ? (
                <p className="text-xs text-muted-foreground px-1 py-2">Nenhum schedule cadastrado.</p>
              ) : (
                schedules.map((s) => (
                  <div key={s.id} className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="schedule-padrao"
                      aria-label={`Padrão ${s.codigo_schedule}`}
                      className="h-3.5 w-3.5 shrink-0 disabled:opacity-40"
                      disabled={!scheduleIds.includes(s.id)}
                      checked={schedulePadrao === s.id}
                      onChange={() => setSchedulePadrao(s.id)}
                    />
                    <Checkbox
                      id={`schedule-${s.id}`}
                      checked={scheduleIds.includes(s.id)}
                      onCheckedChange={(v) => toggleSchedule(s.id, v === true)}
                    />
                    <Label htmlFor={`schedule-${s.id}`} className="cursor-pointer font-normal text-xs flex-1 truncate">
                      {(s.codigo || s.codigo_schedule) + ' — ' + s.descricao}
                    </Label>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <div>
          <Label className="text-sm font-medium mb-1.5 block">Polegadas / medidas</Label>
          <Input
            className="h-9 mb-2"
            value={filtroPolegada}
            onChange={(e) => setFiltroPolegada(e.target.value)}
            placeholder="Filtrar por código ou descrição…"
          />
          <div className="max-h-64 overflow-y-auto rounded-md border border-border p-2 space-y-1">
            {carregandoCatalogo ? (
              <p className="text-xs text-muted-foreground px-1 py-2">Carregando polegadas…</p>
            ) : polegadasVisiveis.length === 0 ? (
              <p className="text-xs text-muted-foreground px-1 py-2">Nenhuma polegada encontrada.</p>
            ) : (
              polegadasVisiveis.map((p) => {
                const tipo = polegadaTipos[p.id];
                return (
                  <div key={p.id} className="flex items-center gap-2">
                    <Checkbox
                      id={`polegada-${p.id}`}
                      checked={tipo !== undefined}
                      onCheckedChange={(v) => togglePolegada(p.id, v === true)}
                    />
                    <Label htmlFor={`polegada-${p.id}`} className="cursor-pointer font-normal text-xs flex-1 truncate">
                      {(p.codigo || p.codigo_oficial || '—') + ' — ' + p.descricao}
                      {p.tipo_medida ? ` (${p.tipo_medida})` : ''}
                    </Label>
                    {tipo && (
                      <Select
                        value={tipo}
                        onValueChange={(v) =>
                          setPolegadaTipos((prev) => ({ ...prev, [p.id]: v as TipoPolegadaPermitida }))
                        }
                      >
                        <SelectTrigger className="h-8 w-32 text-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {OPCOES_TIPO_POLEGADA.map((o) => (
                            <SelectItem key={o.value} value={o.value}>
                              {o.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 pt-2 border-t border-border">
          <NexusButton type="button" onClick={() => void salvar()} disabled={salvando || carregandoDominio}>
            {salvando ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
            Salvar domínio
          </NexusButton>
          <p className="text-xs text-muted-foreground">
            {roscaIds.length} rosca(s), {scheduleIds.length} schedule(s) e {Object.keys(polegadaTipos).length} medida(s)
            selecionado(s).
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
