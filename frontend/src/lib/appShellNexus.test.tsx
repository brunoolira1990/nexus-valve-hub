import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import { Header } from '@/components/Header';
import { MainLayout } from '@/components/MainLayout';
import { Sidebar } from '@/components/Sidebar';
import { TopBar } from '@/components/layout/TopBar';
import {
  APP_SWITCHER_OTHER_SECTIONS,
  APP_SWITCHER_PRIMARY_SECTIONS,
  buildAppSwitcherModules,
} from '@/components/layout/AppSwitcher';
import { AppsHome } from '@/pages/Apps/AppsHome';
import { BIPageLayout } from '@/components/bi/BIPageLayout';
import { BIAccessDenied } from '@/components/bi/BIAccessDenied';
import { BIModuleCard } from '@/components/bi/BIModuleCard';
import { BIModuleNav } from '@/components/bi/BIModuleNav';
import { BIFilterBar } from '@/components/bi/BIFilterBar';
import { kpiTom } from '@/components/bi/dashboardBiConfig';
import type { BIKpi, DashboardModuloHome, DashboardPermissoes } from '@/services/api/dashboard';

vi.mock('@/hooks/useAppContexto', () => ({
  useAppContexto: () => ({
    contexto: {
      empresa: { id: 1, nome_exibicao: 'NEXUS VÁLVULAS', cnpj: '12345678000199', ambiente: 'homologacao' },
      usuario: { id: 1, nome: 'Admin', nome_exibicao: 'Admin', email: 'a@t.com', perfil_label: 'Administrador', is_admin: true },
      colaborador: null,
      ambiente: 'homologacao',
      ambiente_label: 'Homologação',
    },
    loading: false,
  }),
  clearAppContextoCache: vi.fn(),
}));

vi.mock('@/components/header/GlobalSearch', () => ({
  GlobalSearch: () => <input aria-label="Busca global" placeholder="Buscar…" />,
}));

vi.mock('@/components/layout/NotificacoesSino', () => ({
  NotificacoesSino: () => <button type="button" aria-label="Notificações" />,
}));

const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8');
const tailwind = readFileSync(resolve(process.cwd(), 'tailwind.config.ts'), 'utf8');

describe('App shell 3.8 — identidade visual Nexus', () => {
  it('index.css declara o azul e o laranja Nexus como tokens', () => {
    // triplets HSL: 209 51% 36% = #2D5D8A, 28 80% 52% = #E67E22
    expect(css).toMatch(/--nexus-blue:\s*209 51% 36%/);
    expect(css).toMatch(/--nexus-orange:\s*28 80% 52%/);
    expect(tailwind).toMatch(/nexus:/);
    expect(tailwind).toMatch(/"hsl\(var\(--nexus-orange\)\)"/);
  });

  it('a Sidebar é azul Nexus com item ativo claro e marcador laranja', () => {
    expect(css).toMatch(/--sidebar-bg:\s*var\(--nexus-blue\)/);
    expect(css).toMatch(/--sidebar-fg:\s*0 0% 100%/);
    // Odoo: o fundo ativo é branco 10%; o laranja da marca ficou na borda esquerda.
    expect(css).toMatch(/--sidebar-active:\s*0 0% 100% \/ 0\.1/);
    // o grafite antigo que virava "buraco escuro" não pode voltar
    expect(css).not.toMatch(/--sidebar-bg:\s*220 26% 14%/);
    expect(css).not.toMatch(/--sidebar-active:\s*217 91% 45%/);
  });

  it('a TopBar continua clara', () => {
    render(
      <MemoryRouter initialEntries={['/produtos']}>
        <TopBar onOpenAppSwitcher={vi.fn()} />
      </MemoryRouter>,
    );
    expect(document.querySelector('header')?.className).toMatch(/bg-card/);
  });

  it('"+ Novo" é o laranja da marca, não o primário azul', () => {
    render(
      <MemoryRouter initialEntries={['/produtos']}>
        <TopBar onOpenAppSwitcher={vi.fn()} />
      </MemoryRouter>,
    );
    const novo = screen.getByRole('button', { name: 'Criar rapidamente' });
    expect(novo.className).toMatch(/bg-nexus-orange/);
    expect(novo.className).toMatch(/hover:bg-nexus-orange-strong/);
    expect(novo.className).not.toMatch(/bg-primary/);
  });

  it('a busca fica encostada entre "+ Novo" e as notificações, sem spacer no meio', () => {
    render(
      <MemoryRouter initialEntries={['/produtos']}>
        <TopBar onOpenAppSwitcher={vi.fn()} />
      </MemoryRouter>,
    );
    const header = document.querySelector('header')!;
    const kids = Array.from(header.children);
    const searchBox = screen.getByLabelText('Busca global').parentElement!;
    const novoBox = screen.getByRole('button', { name: 'Criar rapidamente' }).parentElement!;
    const sino = screen.getByRole('button', { name: 'Notificações' });

    expect(searchBox.className).toMatch(/flex-1/);
    expect(kids.indexOf(novoBox) + 1).toBe(kids.indexOf(searchBox));
    expect(kids.indexOf(searchBox) + 1).toBe(kids.indexOf(sino));
  });
});

describe('App shell 3.8 — busca universal', () => {
  it('GlobalSearch perdeu o modo compacto que escondia o campo em mobile', () => {
    const src = readFileSync(resolve(process.cwd(), 'src/components/header/GlobalSearch.tsx'), 'utf8');
    expect(src).not.toMatch(/compact/);
    expect(src).not.toMatch(/const \[expanded/);
    expect(src).not.toMatch(/max-w-/);
    expect(src).toMatch(/className="flex items-center gap-1[^"]*w-full"/);
  });
});

describe('App shell 3.8 — hambúrguer só quando há Sidebar', () => {
  it('mostra o botão de menu por padrão', () => {
    render(
      <MemoryRouter initialEntries={['/produtos']}>
        <Header onToggleSidebar={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: 'Abrir menu' })).toBeInTheDocument();
  });

  it('esconde em rota sem Sidebar (Dashboard)', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Header onToggleSidebar={vi.fn()} showMenuButton={false} />
      </MemoryRouter>,
    );
    expect(screen.queryByRole('button', { name: 'Abrir menu' })).not.toBeInTheDocument();
  });
});

describe('App shell 3.8 — Sidebar densidade Odoo', () => {
  it('itens a 13px com py-1.5; ativo = fundo claro + marcador laranja de 3px à esquerda', () => {
    render(
      <MemoryRouter initialEntries={['/familias']}>
        <Sidebar isOpen onClose={vi.fn()} onOpenAppSwitcher={vi.fn()} />
      </MemoryRouter>,
    );
    const aside = document.querySelector('aside');
    expect(aside?.className).toMatch(/bg-sidebar-bg\s+text-sidebar-fg/);

    const ativo = screen.getByRole('link', { name: 'Famílias' });
    expect(ativo.className).toMatch(/text-\[13px\]/);
    expect(ativo.className).toMatch(/py-1\.5/);
    expect(ativo.className).toMatch(/border-l-\[3px\]/);
    expect(ativo.className).toMatch(/border-nexus-orange/);
    expect(ativo.className).toMatch(/bg-sidebar-active/);
    expect(ativo.className).toMatch(/text-sidebar-fg/);
    expect(ativo.className).not.toMatch(/rounded-l/);

    const inativo = screen.getByRole('link', { name: 'Produtos' });
    expect(inativo.className).toMatch(/border-transparent/);
    expect(inativo.className).not.toMatch(/bg-sidebar-active/);
  });

  it('o cabeçalho do módulo traz o chevron que abre o grid de módulos', () => {
    render(
      <MemoryRouter initialEntries={['/produtos']}>
        <Sidebar isOpen onClose={vi.fn()} onOpenAppSwitcher={vi.fn()} />
      </MemoryRouter>,
    );
    const trocar = screen.getByTitle('Trocar de módulo');
    // grade + chevron: é a única linha da sidebar que expande algo
    expect(trocar.querySelectorAll('svg')).toHaveLength(2);
  });

  it('subgrupos do menu são títulos de seção 10px em caixa alta, sem ícone', () => {
    render(
      <MemoryRouter initialEntries={['/central-dfe']}>
        <Sidebar isOpen onClose={vi.fn()} />
      </MemoryRouter>,
    );
    const grupo = screen.getByText('Bases / Histórico');
    expect(grupo.tagName).toBe('P');
    expect(grupo.className).toMatch(/text-\[10px\]/);
    expect(grupo.className).toMatch(/uppercase/);
    expect(grupo.querySelector('svg')).toBeNull();
  });
});

describe('App shell 3.8 — abas BI no estilo Odoo', () => {
  const permissoes: DashboardPermissoes = {
    pode_ver_comercial: true,
    pode_ver_fiscal: true,
    pode_ver_estoque: true,
    pode_ver_expedicao: true,
    pode_ver_compras: true,
    pode_ver_qualidade: true,
    pode_ver_financeiro: true,
    pode_ver_consolidado: true,
  };

  it('a aba ativa é sublinhada em azul Nexus; nenhuma pílula colorida sobra', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard/comercial']}>
        <BIModuleNav permissoes={permissoes} />
      </MemoryRouter>,
    );
    const ativa = screen.getByRole('link', { name: 'Comercial' });
    expect(ativa.className).toMatch(/border-b-2/);
    expect(ativa.className).toMatch(/border-nexus-blue/);
    expect(ativa.className).toMatch(/text-nexus-blue/);
    expect(ativa.className).not.toMatch(/rounded-full/);
    expect(ativa.className).not.toMatch(/bg-primary/);
    expect(ativa).toHaveAttribute('aria-current', 'page');

    const inativa = screen.getByRole('link', { name: 'Visão geral' });
    expect(inativa.className).toMatch(/border-transparent/);
    expect(inativa.className).toMatch(/text-muted-foreground/);
    expect(inativa).not.toHaveAttribute('aria-current');
  });
});

describe('App shell 3.8 — área de conteúdo', () => {
  it('--surface-muted é o cinza claro pedido (210 40% 98% = slate-50) e o main o usa', () => {
    expect(css).toMatch(/--surface-muted:\s*210 40% 98%/);
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route element={<MainLayout />}>
            <Route path="/dashboard" element={<div>Painel</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(document.querySelector('main')?.className).toMatch(/bg-surface-muted/);
    expect(document.querySelector('aside')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Abrir menu' })).not.toBeInTheDocument();
    expect(screen.getByText('Painel')).toBeInTheDocument();
  });

  it('em módulo real o main continua cinza e a Sidebar volta', () => {
    render(
      <MemoryRouter initialEntries={['/produtos']}>
        <Routes>
          <Route element={<MainLayout />}>
            <Route path="/produtos" element={<div>Lista</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(document.querySelector('main')?.className).toMatch(/bg-surface-muted/);
    expect(document.querySelector('aside')).not.toBeNull();
    expect(screen.getByRole('button', { name: 'Abrir menu' })).toBeInTheDocument();
  });
});

describe('App shell 3.8 — título duplicado virou h1 acessível', () => {
  it('titleVisible={false} mantém o h1, só que fora da tela', () => {
    render(
      <MemoryRouter>
        <BIPageLayout title="Dashboard" titleVisible={false} subtitle="Visão executiva dos módulos permitidos ao seu perfil">
          <div>KPIs</div>
        </BIPageLayout>
      </MemoryRouter>,
    );
    const h1 = document.querySelector('h1');
    expect(h1?.textContent).toBe('Dashboard');
    expect(h1?.className).toBe('sr-only');
    expect(screen.getByText('Visão executiva dos módulos permitidos ao seu perfil')).toBeInTheDocument();
  });

  it('com titleVisible omitido o h1 visível continua igual (demais páginas BI não mudam)', () => {
    render(
      <MemoryRouter>
        <BIPageLayout title="BI Comercial">x</BIPageLayout>
      </MemoryRouter>,
    );
    expect(document.querySelector('h1')?.className).toBe('nexus-heading-xl');
  });

  it('Dashboard e os 7 painéis BI pedem o título invisível', () => {
    const home = readFileSync(resolve(process.cwd(), 'src/pages/dashboard/DashboardHome.tsx'), 'utf8');
    const modulo = readFileSync(resolve(process.cwd(), 'src/pages/dashboard/DashboardModuloView.tsx'), 'utf8');
    expect(home).toMatch(/title="Dashboard"\s*\n\s*titleVisible=\{false\}/);
    // um call site no ramo de erro + um no ramo normal = as 8 rotas /dashboard*
    expect(modulo.match(/titleVisible=\{false\}/g)).toHaveLength(2);
    expect(modulo).toMatch(/title=\{`BI \$\{MODULO_LABELS\[modulo\]\}`\}\s*\n\s*titleVisible=\{false\}/);
  });

  it('até o estado de acesso negado tem h1 acessível', () => {
    render(
      <MemoryRouter>
        <BIAccessDenied modulo="Fiscal" />
      </MemoryRouter>,
    );
    expect(document.querySelector('h1')?.textContent).toBe('Painel Fiscal');
    expect(document.querySelector('h1')?.className).toBe('sr-only');
    expect(screen.getByRole('heading', { level: 2, name: 'Acesso restrito' })).toBeInTheDocument();
  });
});

const backendBi = readFileSync(
  resolve(process.cwd(), '../backend/nexus_erp/dashboard_bi_service.py'),
  'utf8',
);

function kpi(id: string, titulo: string, valor: string | number, formato = 'numero'): BIKpi {
  return { id, titulo, valor, formato };
}

function card(modulo: string, kpis: BIKpi[], heroKpiId: string): DashboardModuloHome {
  return {
    modulo,
    titulo: modulo.charAt(0).toUpperCase() + modulo.slice(1),
    kpis,
    alerta_principal: null,
    link_bi: `/dashboard/${modulo}`,
    hero_kpi_id: heroKpiId,
  };
}

describe('Dashboard 3.8 — CAMADA 1: card de KPI denso', () => {
  // `modulo` é o código (chave de MODULO_ICONE/MODULO_HERO_KPI); `titulo` é a label.
  const fiscal = card('fiscal', [
    kpi('nfe_auth_prod', 'Autorizadas produção', 78),
    kpi('nfe_rej_prod', 'Rejeitadas produção', 0),
    kpi('nfe_enviada_prod', 'Enviadas produção', 4),
  ], 'nfe_auth_prod');

  it('padding p-4, título text-sm e número do hero text-2xl (não 3xl)', () => {
    render(
      <MemoryRouter>
        <BIModuleCard modulo={fiscal} />
      </MemoryRouter>,
    );
    const raiz = document.querySelector('.erp-card');
    expect(raiz?.className).toMatch(/\bp-4\b/);
    expect(raiz?.className).not.toMatch(/\bp-6\b/);
    const h2 = screen.getByRole('heading', { level: 2, name: 'Fiscal' });
    expect(h2.className).toMatch(/text-sm/);
    expect(h2.className).toMatch(/font-semibold/);
    expect(h2.className).not.toMatch(/text-lg/);
    const heroi = screen.getByText('78');
    expect(heroi.className).toMatch(/text-2xl/);
    expect(heroi.className).not.toMatch(/text-3xl/);
  });

  it('título do card tem ícone Lucide 16px na cor do módulo', () => {
    render(
      <MemoryRouter>
        <BIModuleCard modulo={fiscal} />
      </MemoryRouter>,
    );
    const icone = document.querySelector('h2')?.parentElement?.querySelector('svg');
    expect(icone).not.toBeNull();
    expect(icone?.getAttribute('class')).toMatch(/h-4 w-4/);
    expect(icone?.getAttribute('class')).toMatch(/text-nexus-blue/);
  });

  it('badge do KPI secundário segue a tonalidade: âmbar para alerta, slate para zero', () => {
    render(
      <MemoryRouter>
        <BIModuleCard modulo={fiscal} />
      </MemoryRouter>,
    );
    expect(screen.getByText('0').className).toMatch(/bg-slate-100/);
    expect(screen.getByText('4').className).toMatch(/bg-amber-50/);
    expect(screen.getByText('0').className).not.toMatch(/bg-red-50/);
  });

  it('rodapé é link "Ver painel" discreto, não botão', () => {
    render(
      <MemoryRouter>
        <BIModuleCard modulo={fiscal} />
      </MemoryRouter>,
    );
    const link = screen.getByRole('link', { name: /Ver painel/ });
    expect(link.getAttribute('href')).toBe('/dashboard/fiscal');
    expect(link.className).toMatch(/text-xs/);
    expect(link.className).toMatch(/text-nexus-blue/);
    expect(link.className).toMatch(/hover:underline/);
    expect(link.className).not.toMatch(/bg-primary/);
  });

  it('números positivos do hero ficam em verde', () => {
    render(
      <MemoryRouter>
        <BIModuleCard modulo={card('comercial', [kpi('pedidos_faturados', 'Faturados', 12)], 'pedidos_faturados')} />
      </MemoryRouter>,
    );
    expect(screen.getByText('12').className).toMatch(/text-emerald-600/);
  });

  it('kpiTom: zero neutraliza o alerta e id desconhecido fica neutro', () => {
    expect(kpiTom(kpi('nfe_rej_prod', 'Rejeitadas', 0))).toBe('neutro');
    expect(kpiTom(kpi('nfe_rej_prod', 'Rejeitadas', 3))).toBe('erro');
    expect(kpiTom(kpi('pedidos_abertos', 'Pedidos abertos', 0))).toBe('neutro');
    expect(kpiTom(kpi('pedidos_abertos', 'Pedidos abertos', 1))).toBe('alerta');
    expect(kpiTom(kpi('algum_kpi_novo', 'Novo', 5))).toBe('neutro');
    expect(kpiTom({ id: 'valor_aberto', titulo: 'Valor a faturar', valor: '0.00', formato: 'moeda' })).toBe('neutro');
  });

  it('todo KPI mapeado em dashboardBiConfig existe no serviço BI do backend', () => {
    const config = readFileSync(
      resolve(process.cwd(), 'src/components/bi/dashboardBiConfig.ts'),
      'utf8',
    );
    const blocos = [
      /const KPI_POSITIVOS = new Set\(\[(.*?)\]\);/s,
      /const KPI_ALERTAS = new Set\(\[(.*?)\]\);/s,
      /const KPI_ERROS = new Set\(\[(.*?)\]\);/s,
    ];
    const ids = blocos
      .map((re) => config.match(re)?.[1] ?? '')
      .flatMap((corpo) => corpo.match(/'[a-z0-9_]+'/g) ?? [])
      .map((s) => s.replace(/'/g, ''));
    expect(ids.length).toBeGreaterThan(20);
    for (const id of ids) {
      expect(backendBi, `id '${id}' não é produzido por _kpi(...)`).toContain(`'${id}'`);
    }
  });
});

describe('Dashboard 3.8 — CAMADA 2: toolbar de filtros', () => {
  it('some o card: uma linha transparente alinhada à direita', () => {
    render(
      <BIFilterBar
        filters={{ periodo: 'mes_atual', empresa_id: '', status: '' }}
        onApply={vi.fn()}
        onClear={vi.fn()}
        showEmpresa={false}
      />,
    );
    const raiz = screen.getByText('Filtrar').parentElement;
    expect(raiz?.className).not.toMatch(/erp-card/);
    expect(raiz?.className).toMatch(/sm:h-10/);
    expect(raiz?.className).toMatch(/justify-end/);
    expect(document.querySelector('svg')?.getAttribute('class')).toMatch(/h-3\.5/);
  });

  it('Aplicar azul Nexus e Limpar slate, ambos h-9', () => {
    render(
      <BIFilterBar
        filters={{ periodo: 'mes_atual', empresa_id: '', status: '' }}
        onApply={vi.fn()}
        onClear={vi.fn()}
        showEmpresa={false}
      />,
    );
    const aplicar = screen.getByRole('button', { name: 'Aplicar' });
    expect(aplicar.className).toMatch(/bg-nexus-blue/);
    expect(aplicar.className).toMatch(/text-white/);
    expect(aplicar.className).toMatch(/h-9/);
    const limpar = screen.getByRole('button', { name: 'Limpar' });
    expect(limpar.className).toMatch(/text-slate-600/);
    expect(limpar.className).toMatch(/hover:text-slate-900/);
    expect(limpar.className).not.toMatch(/erp-btn-outline/);
  });

  it('os selects perdem os labels empilhados mas mantêm nome acessível', () => {
    render(
      <BIFilterBar
        filters={{ periodo: 'mes_atual', empresa_id: '', status: '' }}
        onApply={vi.fn()}
        onClear={vi.fn()}
        showEmpresa={false}
      />,
    );
    expect(screen.getByLabelText('Período')).toBeInTheDocument();
    expect(screen.queryByText(/^Período$/)).not.toBeInTheDocument();
  });
});

describe('Dashboard 3.8 — CAMADA 3: abas com ícone e header compacto', () => {
  const permissoes: DashboardPermissoes = {
    pode_ver_comercial: true,
    pode_ver_fiscal: true,
    pode_ver_estoque: true,
    pode_ver_expedicao: true,
    pode_ver_compras: true,
    pode_ver_qualidade: true,
    pode_ver_financeiro: true,
    pode_ver_consolidado: true,
  };

  it('cada aba tem ícone 16px antes do texto', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <BIModuleNav permissoes={permissoes} />
      </MemoryRouter>,
    );
    for (const label of ['Visão geral', 'Comercial', 'Fiscal']) {
      const aba = screen.getByRole('link', { name: label });
      expect(aba.className).toMatch(/gap-1\.5/);
      expect(aba.querySelectorAll('svg')).toHaveLength(1);
      expect(aba.querySelector('svg')?.getAttribute('class')).toMatch(/h-4 w-4/);
    }
  });

  it('header reduz para 36px e o breadcrumb vira text-xs', () => {
    render(
      <MemoryRouter initialEntries={['/produtos']}>
        <Header onToggleSidebar={vi.fn()} breadcrumbs={[{ label: 'Produtos' }]} />
      </MemoryRouter>,
    );
    const cabecalho = document.querySelector('header');
    expect(cabecalho?.className).toMatch(/min-h-9/);
    expect(cabecalho?.className).not.toMatch(/min-h-12/);
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' }).className).toMatch(/text-xs/);
  });

  it('selos saem do Header só quando a página os assume', () => {
    const { unmount } = render(
      <MemoryRouter>
        <Header onToggleSidebar={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.getByText('NEXUS VÁLVULAS')).toBeInTheDocument();
    expect(screen.getByText('Homologação')).toBeInTheDocument();
    unmount();

    render(
      <MemoryRouter>
        <Header onToggleSidebar={vi.fn()} mostraSelos={false} />
      </MemoryRouter>,
    );
    expect(screen.queryByText('NEXUS VÁLVULAS')).not.toBeInTheDocument();
    expect(screen.queryByText('Homologação')).not.toBeInTheDocument();
  });

  it('no Dashboard o selo vive no topo do conteúdo BI', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route element={<MainLayout />}>
            <Route path="/dashboard" element={<BIPageLayout title="Dashboard">KPIs</BIPageLayout>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('NEXUS VÁLVULAS')).toBeInTheDocument();
    expect(screen.getByText('Homologação')).toBeInTheDocument();
    expect(document.querySelector('h1')?.className).toBe('nexus-heading-xl');
  });

  it('em rota de módulo o Header ainda mostra o selo (94 rotas sem BI)', () => {
    render(
      <MemoryRouter initialEntries={['/nfe-saida']}>
        <Routes>
          <Route element={<MainLayout />}>
            <Route path="/nfe-saida" element={<div>Lista</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('NEXUS VÁLVULAS')).toBeInTheDocument();
  });
});

describe('Dashboard 3.8 — CAMADA 4: espaçamento', () => {
  it('grade de cards do Dashboard usa gap-4', () => {
    const home = readFileSync(resolve(process.cwd(), 'src/pages/dashboard/DashboardHome.tsx'), 'utf8');
    expect(home).toMatch(/grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-3 gap-4/);
    expect(home).not.toMatch(/gap-5 mb-8/);
  });

  it('BIPageLayout troca a seção de 1.5rem por space-y-4', () => {
    const layout = readFileSync(resolve(process.cwd(), 'src/components/bi/BIPageLayout.tsx'), 'utf8');
    expect(layout).toMatch(/className="space-y-4"/);
    expect(layout).not.toMatch(/space-y-\[var\(--section-gap\)\]/);
  });

  it('o sparkline de 7 dias não é desenhado sem série no payload', () => {
    const cardSrc = readFileSync(resolve(process.cwd(), 'src/components/bi/BIModuleCard.tsx'), 'utf8');
    expect(cardSrc).not.toMatch(/recharts|Sparkline|ResponsiveContainer/);
    expect(backendBi).not.toMatch(/'serie|'historico_dias|ultimos_7_dias_dados/);
  });
});

describe('App shell 3.8 — tela de Aplicativos é a primeira após o login', () => {
  const appSrc = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const loginSrc = readFileSync(resolve(process.cwd(), 'src/pages/Login.tsx'), 'utf8');

  it('a raiz redireciona para /apps e a rota existe com AppsHome', () => {
    expect(appSrc).toMatch(/<Route index element=\{<Navigate to="\/apps" replace \/>\} \/>/);
    expect(appSrc).toMatch(/<Route path="apps" element=\{<AppsHome \/>\} \/>/);
    expect(appSrc).not.toMatch(/<Navigate to="\/dashboard" replace \/>/);
  });

  it('o login manda para /apps, não para o Dashboard', () => {
    expect(loginSrc).toMatch(/navigate\('\/apps'\)/);
    expect(loginSrc).not.toMatch(/navigate\('\/dashboard'\)/);
  });

  it('o logo NEXUS APP leva para /apps', () => {
    render(
      <MemoryRouter initialEntries={['/produtos']}>
        <TopBar onOpenAppSwitcher={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.getByText('NEXUS APP').closest('a')).toHaveAttribute('href', '/apps');
  });

  it('em /apps a Sidebar some e só ficam TopBar + grid, como no Dashboard', () => {
    render(
      <MemoryRouter initialEntries={['/apps']}>
        <Routes>
          <Route element={<MainLayout />}>
            <Route path="/apps" element={<AppsHome />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(document.querySelector('aside')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Abrir menu' })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'Aplicativos' })).toBeInTheDocument();
    expect(screen.getByText('Bem-vindo, Admin.')).toBeInTheDocument();
  });

  it('o breadcrumb da tela é Aplicativos, nunca "Página"', () => {
    render(
      <MemoryRouter initialEntries={['/apps']}>
        <Routes>
          <Route element={<MainLayout />}>
            <Route path="/apps" element={<div>Grid</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('Aplicativos')).toBeInTheDocument();
    expect(screen.queryByText('Página')).toBeNull();
  });

  it('o grid em tela cheia usa os mesmos 8 módulos do modal, ligando à rota raiz', () => {
    render(
      <MemoryRouter initialEntries={['/apps']}>
        <AppsHome />
      </MemoryRouter>,
    );
    const main = document.querySelector('main') ?? document.body;
    const esperados = buildAppSwitcherModules(APP_SWITCHER_PRIMARY_SECTIONS);
    const outros = buildAppSwitcherModules(APP_SWITCHER_OTHER_SECTIONS);
    expect(esperados).toHaveLength(8);
    const cards = within(main).getAllByRole('link');
    // as 15 rotas da tela são exatamente as do modal, sem rota inventada: 8 módulos + 7 áreas
    expect(cards.map((card) => card.getAttribute('href'))).toEqual(
      [...esperados, ...outros].map((m) => m.path),
    );
    esperados.forEach((modulo, i) => expect(cards[i]).toHaveTextContent(modulo.label));
  });

  it('"Outras áreas" traz os 7 blocos restantes, pelos mesmos dados do modal', () => {
    render(
      <MemoryRouter initialEntries={['/apps']}>
        <AppsHome />
      </MemoryRouter>,
    );
    const outros = buildAppSwitcherModules(APP_SWITCHER_OTHER_SECTIONS);
    expect(outros).toHaveLength(7);
    const secao = screen.getByRole('heading', { name: 'Outras áreas' }).closest('section')!;
    const cards = within(secao).getAllByRole('link');
    expect(cards.map((card) => card.getAttribute('href'))).toEqual(outros.map((m) => m.path));
    outros.forEach((modulo, i) => expect(cards[i]).toHaveTextContent(modulo.label));
  });

  it('aumentou o card: mais padding e ícone maior que os do modal', () => {
    const tela = readFileSync(resolve(process.cwd(), 'src/pages/Apps/AppsHome.tsx'), 'utf8');
    const modal = readFileSync(resolve(process.cwd(), 'src/components/layout/AppSwitcher.tsx'), 'utf8');
    expect(tela).toMatch(/h-12 w-12/);
    expect(tela).toMatch(/p-5/);
    expect(modal).toMatch(/h-9 w-9/);
    expect(modal).toMatch(/gap-3 rounded-lg border p-3/);
  });
});
