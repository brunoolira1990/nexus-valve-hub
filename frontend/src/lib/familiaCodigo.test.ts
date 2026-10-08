import { describe, expect, it } from 'vitest';

import {
  MENSAGEM_CODIGO_FIGURA_AUTO,
  MENSAGEM_CODIGO_FIGURA_MANUAL,
  MODO_CODIGO_FIGURA_PADRAO,
  MSG_ALERTA_OD_REPETIDO_PELO_TEMPLATE,
  MSG_CODIGO_FIGURA_MANUAL_OBRIGATORIO,
  MSG_DESCRICAO_BASE_OBRIGATORIA,
  alertaCodigoManualRepeteComplementoTemplate,
  avisoMesmaDescricaoModeloDiferente,
  classificarDuplicidadeDescricaoFamilia,
  campoCodigoFiguraVisivelNaCriacao,
  chaveDescricaoDuplicidadeFamilia,
  deveRecarregarFamiliasAposErroCodigoApi,
  erroCodigoAposAlternarModo,
  extrairDuplicidadeDescricaoModeloApi,
  familiaEmEdicao,
  montarPayloadFamiliaSalvar,
  payloadIncluiCodigoFigura,
  podeIniciarSalvarFamilia,
  templateAcrescentaOd,
  validarCodigoFiguraManualLocal,
  validarDescricaoBaseLocal,
} from '@/lib/familiaCodigo';

describe('familiaCodigo', () => {
  const eff = {
    usa_rosca_conexao: false,
    usa_schedule: false,
    usa_polegada_principal: true,
    usa_polegada_secundaria: false,
  };

  const famQuick = {
    codigo_figura: '0199',
    descricao_base: 'TESTE',
    categoria_produto: 'PRODUTO_TECNICO' as const,
    tipo_regra_codigo: 'BASE_POLEGADA' as const,
    tipo_dimensional: 'SIMPLES' as const,
    separador_base_medidas: '.',
    ativo: true,
    usa_conversao_dimensional: false,
    controla_composicao_fisica: false,
    tipo_composicao_fisica: 'BARRA_M' as const,
    tipo_fisico: 'PECA' as const,
    tipo_controle_unidade: 'PECA' as const,
    unidade_estoque_padrao: '',
    unidade_venda_padrao: '',
    unidade_compra_padrao: '',
    unidade_fiscal_padrao: '',
    unidades_venda_permitidas: [] as string[],
    unidades_compra_permitidas: [] as string[],
    comprimento_padrao_barra_m: null,
    peso_por_metro_kg: null,
    peso_por_peca_kg: null,
    peso_por_chapa_kg: null,
    densidade: null,
    observacoes_conversao: '',
    ncm_padrao: null,
  };

  it('automático selecionado por padrão, sem obrigar código', () => {
    expect(MODO_CODIGO_FIGURA_PADRAO).toBe('AUTOMATICO');
    expect(campoCodigoFiguraVisivelNaCriacao('AUTOMATICO')).toBe(false);
    expect(campoCodigoFiguraVisivelNaCriacao('MANUAL')).toBe(true);
    expect(validarCodigoFiguraManualLocal('AUTOMATICO', '')).toBeNull();
  });

  it('orientação manual é contextual (não proíbe OD genericamente)', () => {
    expect(MENSAGEM_CODIGO_FIGURA_AUTO).toMatch(/gerado automaticamente/i);
    expect(MENSAGEM_CODIGO_FIGURA_MANUAL).toMatch(/somente quando o modelo/i);
    expect(familiaEmEdicao(null)).toBe(false);
    expect(familiaEmEdicao({ id: 1 })).toBe(true);
  });

  it('alerta OD×template só quando ambos acrescentam OD', () => {
    expect(templateAcrescentaOd('BASE_OD_MM_ESPESSURA')).toBe(true);
    expect(templateAcrescentaOd('BASE_POLEGADA')).toBe(false);
    expect(
      alertaCodigoManualRepeteComplementoTemplate('MANUAL', '6119OD', 'BASE_OD_MM_ESPESSURA'),
    ).toBe(MSG_ALERTA_OD_REPETIDO_PELO_TEMPLATE);
    expect(
      alertaCodigoManualRepeteComplementoTemplate('MANUAL', '0023OD', 'BASE_POLEGADA'),
    ).toBeNull();
  });

  it('submit automático envia modo_codigo e não inclui codigo_figura', () => {
    const p = montarPayloadFamiliaSalvar(
      { ...famQuick, modo_codigo_figura: 'AUTOMATICO', codigo_figura: '' },
      null,
      eff,
    );
    expect(p.modo_codigo).toBe('AUTOMATICO');
    expect(payloadIncluiCodigoFigura(p)).toBe(false);
    expect(p).not.toHaveProperty('codigo_figura');
  });

  it('payload automático ignora codigo preenchido no form', () => {
    const p = montarPayloadFamiliaSalvar(
      { ...famQuick, modo_codigo_figura: 'AUTOMATICO', codigo_figura: '0199' },
      null,
      eff,
    );
    expect(p.modo_codigo).toBe('AUTOMATICO');
    expect(payloadIncluiCodigoFigura(p)).toBe(false);
  });

  it('manual vazio exibe erro de obrigatoriedade', () => {
    expect(validarCodigoFiguraManualLocal('MANUAL', '')).toBe(MSG_CODIGO_FIGURA_MANUAL_OBRIGATORIO);
    expect(validarCodigoFiguraManualLocal('MANUAL', '   ')).toBe(MSG_CODIGO_FIGURA_MANUAL_OBRIGATORIO);
  });

  it('manual preenchido envia codigo_figura', () => {
    const p = montarPayloadFamiliaSalvar(
      { ...famQuick, modo_codigo_figura: 'MANUAL', codigo_figura: '6119OD' },
      null,
      eff,
    );
    expect(p.modo_codigo).toBe('MANUAL');
    expect(p.codigo_figura).toBe('6119OD');
  });

  it('troca MANUAL → AUTOMATICO limpa erro de código', () => {
    expect(
      erroCodigoAposAlternarModo('MANUAL', 'AUTOMATICO', MSG_CODIGO_FIGURA_MANUAL_OBRIGATORIO),
    ).toBeNull();
  });

  it('descrição e demais campos são preservados na troca de modo no payload', () => {
    const base = {
      ...famQuick,
      descricao_base: 'DESCRICAO PRESERVADA',
      ncm_padrao: 42,
      modo_codigo_figura: 'MANUAL' as const,
      codigo_figura: '',
    };
    const auto = montarPayloadFamiliaSalvar(
      { ...base, modo_codigo_figura: 'AUTOMATICO', codigo_figura: '' },
      null,
      eff,
    );
    expect(auto.descricao_base).toBe('DESCRICAO PRESERVADA');
    expect(auto.ncm_padrao).toBe(42);
    expect(auto.tipo_regra_codigo).toBe('BASE_POLEGADA');
    expect(payloadIncluiCodigoFigura(auto)).toBe(false);
  });

  it('payload de edição inclui codigo_figura somente leitura no backend', () => {
    const p = montarPayloadFamiliaSalvar(famQuick, { ...famQuick, id: 9 }, eff);
    expect(p.codigo_figura).toBe('0199');
    expect(p).not.toHaveProperty('modo_codigo');
  });

  it('descrição vazia bloqueia submit localmente (sem POST)', () => {
    expect(validarDescricaoBaseLocal('')).toBe(MSG_DESCRICAO_BASE_OBRIGATORIA);
    expect(validarDescricaoBaseLocal('  ')).toBe(MSG_DESCRICAO_BASE_OBRIGATORIA);
    expect(validarDescricaoBaseLocal('OK')).toBeNull();
  });

  it('clique duplo / reentrada não inicia segundo save', () => {
    expect(podeIniciarSalvarFamilia(false)).toBe(true);
    expect(podeIniciarSalvarFamilia(true)).toBe(false);
  });

  it('HTTP 400 obrigatório não dispara refetch; duplicidade sim', () => {
    expect(deveRecarregarFamiliasAposErroCodigoApi('Este campo é obrigatório.')).toBe(false);
    expect(deveRecarregarFamiliasAposErroCodigoApi('Informe o código da Família/Figura.')).toBe(
      false,
    );
    expect(
      deveRecarregarFamiliasAposErroCodigoApi('Já existe uma Família/Figura com este código.'),
    ).toBe(true);
  });

  it('chave de descrição colapsa espaços e ignora caixa', () => {
    expect(chaveDescricaoDuplicidadeFamilia('  reducao   excentrica  ')).toBe('REDUCAO EXCENTRICA');
  });

  it('extrai erro estruturado de duplicidade descrição+modelo', () => {
    const parsed = extrairDuplicidadeDescricaoModeloApi({
      descricao_base: [
        'Já existe a Família/Figura 0114 — REDUCAO EXCENTRICA ACO CARBONO com o mesmo modelo de formação.',
      ],
      familia_existente_id: 33,
      familia_existente_codigo: '0114',
      familia_existente_descricao: 'REDUCAO EXCENTRICA ACO CARBONO',
    });
    expect(parsed?.existente?.codigo_figura).toBe('0114');
    expect(parsed?.existente?.id).toBe(33);
    expect(parsed?.mensagem).toMatch(/0114/);
  });

  it('aviso quando mesma descrição com modelo diferente', () => {
    const msg = avisoMesmaDescricaoModeloDiferente(
      'REDUCAO EXCENTRICA ACO CARBONO',
      'BASE_POLEGADA',
      [
        {
          id: 1,
          codigo_figura: '0114',
          descricao_base: 'REDUCAO EXCENTRICA ACO CARBONO',
          tipo_regra_codigo: 'BASE_SCHEDULE_DUAS_POLEGADAS',
        },
      ],
      null,
    );
    expect(msg).toMatch(/outro modelo/i);
  });

  const familiasReducao = [
    {
      id: 33,
      codigo_figura: '0114',
      descricao_base: 'REDUCAO EXCENTRICA ACO CARBONO',
      tipo_regra_codigo: 'BASE_SCHEDULE_DUAS_POLEGADAS',
    },
  ];

  it('descrição igual + modelo ainda não confirmado → aviso neutro (não “outro modelo”)', () => {
    const c = classificarDuplicidadeDescricaoFamilia({
      descricaoBase: 'REDUCAO EXCENTRICA ACO CARBONO',
      tipoRegraFormulario: 'BASE_POLEGADA', // default do form, ainda não confirmado
      tipoRegraSugerido: undefined,
      modeloConfirmado: false,
      familias: familiasReducao,
      editingId: null,
    });
    expect(c.tipo).toBe('descricao_sem_modelo');
    if (c.tipo === 'descricao_sem_modelo') {
      expect(c.mensagem).toMatch(/Selecione ou aplique/i);
      expect(c.mensagem).not.toMatch(/outro modelo/i);
    }
  });

  it('descrição igual + sugestão igual ao existente → provável duplicidade', () => {
    const c = classificarDuplicidadeDescricaoFamilia({
      descricaoBase: 'REDUCAO EXCENTRICA ACO CARBONO',
      tipoRegraFormulario: 'BASE_POLEGADA',
      tipoRegraSugerido: 'BASE_SCHEDULE_DUAS_POLEGADAS',
      modeloConfirmado: false,
      familias: familiasReducao,
      editingId: null,
    });
    expect(c.tipo).toBe('provavel_exata');
    if (c.tipo === 'provavel_exata') {
      expect(c.existente.codigo_figura).toBe('0114');
      expect(c.mensagem).toMatch(/sugestão automática corresponde/i);
    }
  });

  it('aplicar sugestão igual → duplicidade exata', () => {
    const c = classificarDuplicidadeDescricaoFamilia({
      descricaoBase: 'REDUCAO EXCENTRICA ACO CARBONO',
      tipoRegraFormulario: 'BASE_SCHEDULE_DUAS_POLEGADAS',
      tipoRegraSugerido: 'BASE_SCHEDULE_DUAS_POLEGADAS',
      modeloConfirmado: true,
      familias: familiasReducao,
      editingId: null,
    });
    expect(c.tipo).toBe('exata');
    if (c.tipo === 'exata') {
      expect(c.mensagem).toMatch(/mesmo modelo de formação/i);
      expect(c.existente.codigo_figura).toBe('0114');
    }
  });

  it('descrição igual + modelo diferente confirmado → aviso amarelo permitido', () => {
    const c = classificarDuplicidadeDescricaoFamilia({
      descricaoBase: 'REDUCAO EXCENTRICA ACO CARBONO',
      tipoRegraFormulario: 'BASE_POLEGADA',
      tipoRegraSugerido: 'BASE_SCHEDULE_DUAS_POLEGADAS',
      modeloConfirmado: true,
      familias: familiasReducao,
      editingId: null,
    });
    expect(c.tipo).toBe('modelo_diferente');
    if (c.tipo === 'modelo_diferente') {
      expect(c.mensagem).toMatch(/outro modelo de formação/i);
      expect(c.mensagem).toMatch(/variação técnica/i);
    }
  });

  it('trocar modelo diferente para igual → exata', () => {
    const antes = classificarDuplicidadeDescricaoFamilia({
      descricaoBase: 'REDUCAO EXCENTRICA ACO CARBONO',
      tipoRegraFormulario: 'BASE_POLEGADA',
      tipoRegraSugerido: 'BASE_SCHEDULE_DUAS_POLEGADAS',
      modeloConfirmado: true,
      familias: familiasReducao,
      editingId: null,
    });
    expect(antes.tipo).toBe('modelo_diferente');
    const depois = classificarDuplicidadeDescricaoFamilia({
      descricaoBase: 'REDUCAO EXCENTRICA ACO CARBONO',
      tipoRegraFormulario: 'BASE_SCHEDULE_DUAS_POLEGADAS',
      tipoRegraSugerido: 'BASE_SCHEDULE_DUAS_POLEGADAS',
      modeloConfirmado: true,
      familias: familiasReducao,
      editingId: null,
    });
    expect(depois.tipo).toBe('exata');
  });

  it('trocar modelo igual para diferente → modelo_diferente', () => {
    const depois = classificarDuplicidadeDescricaoFamilia({
      descricaoBase: 'REDUCAO EXCENTRICA ACO CARBONO',
      tipoRegraFormulario: 'BASE_ROSCA_POLEGADA',
      tipoRegraSugerido: 'BASE_SCHEDULE_DUAS_POLEGADAS',
      modeloConfirmado: true,
      familias: familiasReducao,
      editingId: null,
    });
    expect(depois.tipo).toBe('modelo_diferente');
  });

  it('montar payload só ocorre sob demanda (abrir/digitar/sugerir não mutam API)', () => {
    // Contrato: helpers de sugestão/modo não chamam create; payload só via montarPayloadFamiliaSalvar.
    const depoisSugestao = {
      ...famQuick,
      modo_codigo_figura: 'AUTOMATICO' as const,
      codigo_figura: '',
      descricao_base: 'VALVULA GLOBO',
    };
    const p = montarPayloadFamiliaSalvar(depoisSugestao, null, eff);
    expect(p.modo_codigo).toBe('AUTOMATICO');
    expect(p.descricao_base).toBe('VALVULA GLOBO');
    expect(payloadIncluiCodigoFigura(p)).toBe(false);
  });
});
