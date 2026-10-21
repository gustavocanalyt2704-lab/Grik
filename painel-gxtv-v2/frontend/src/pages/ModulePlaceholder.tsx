import { StateBlock } from '@/components/StateBlock'

export function ModulePlaceholder({
  title,
  phase,
  summary,
}: {
  title: string
  phase: string
  summary: string
}) {
  return (
    <div className="space-y-4">
      <div>
        <div className="text-[11px] uppercase tracking-wide text-[var(--color-accent)]">{phase}</div>
        <h2 className="font-display text-2xl font-semibold">{title}</h2>
        <p className="mt-1 max-w-2xl text-sm text-[var(--color-mist)]">{summary}</p>
      </div>
      <StateBlock
        title="Módulo ainda não entregue"
        envelope={{
          state: 'empty',
          value: null,
          message: `A casca F1 já expõe navegação, filtros e registro. O conteúdo de ${title} sobe em ${phase}.`,
          timezone: 'America/Bahia',
          computed_at: new Date().toISOString(),
        }}
      />
    </div>
  )
}
