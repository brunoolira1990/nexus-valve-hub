export function RelatorioAvisoHistorico({ mensagem }: { mensagem?: string | null }) {
  if (!mensagem) return null;
  return (
    <p className="text-sm text-amber-800 dark:text-amber-200 mb-4 erp-card p-3 border-l-4 border-l-amber-500 bg-amber-50/80 dark:bg-amber-950/30">
      {mensagem}
    </p>
  );
}
