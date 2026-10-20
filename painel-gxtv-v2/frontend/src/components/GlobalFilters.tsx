import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useFilters } from '@/lib/filters'

function Select({
  label,
  value,
  onChange,
  options,
  allLabel,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  options: { id: string; label: string }[]
  allLabel: string
}) {
  return (
    <label className="flex min-w-[140px] flex-1 flex-col gap-1 text-[11px] uppercase tracking-wide text-[var(--color-mist)]">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-[var(--color-line)] bg-[var(--color-panel-2)] px-2 py-1.5 text-sm normal-case text-[var(--color-paper)] outline-none focus:border-[var(--color-accent)]"
      >
        <option value="">{allLabel}</option>
        {options.map((o) => (
          <option key={o.id} value={o.id}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )
}

export function GlobalFiltersBar() {
  const { filters, setFilters, reset } = useFilters()
  const q = useQuery({
    queryKey: ['filter-options'],
    queryFn: api.filterOptions,
    staleTime: 60_000,
  })
  const opts = q.data?.options

  const dirty =
    filters.periodo !== 'hoje' ||
    !!filters.numero ||
    !!filters.atendente ||
    !!filters.app ||
    !!filters.aparelho

  return (
    <div className="anim-rise flex flex-wrap items-end gap-3 rounded-md border border-[var(--color-line)] bg-[var(--color-panel)]/60 p-3 backdrop-blur">
      <label className="flex min-w-[140px] flex-col gap-1 text-[11px] uppercase tracking-wide text-[var(--color-mist)]">
        Período
        <select
          value={filters.periodo}
          onChange={(e) => setFilters({ periodo: e.target.value })}
          className="rounded border border-[var(--color-line)] bg-[var(--color-panel-2)] px-2 py-1.5 text-sm normal-case text-[var(--color-paper)] outline-none focus:border-[var(--color-accent)]"
        >
          {(opts?.periodos || [{ id: 'hoje', label: 'Hoje' }]).map((o) => (
            <option key={o.id} value={o.id}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
      <Select
        label="WhatsApp"
        value={filters.numero || ''}
        onChange={(v) => setFilters({ numero: v || null })}
        options={opts?.numeros || []}
        allLabel="Todos os números"
      />
      <Select
        label="Atendente"
        value={filters.atendente || ''}
        onChange={(v) => setFilters({ atendente: v || null })}
        options={opts?.atendentes || []}
        allLabel="Todos"
      />
      <Select
        label="App"
        value={filters.app || ''}
        onChange={(v) => setFilters({ app: v || null })}
        options={opts?.apps || []}
        allLabel="Todos os apps"
      />
      <Select
        label="Aparelho"
        value={filters.aparelho || ''}
        onChange={(v) => setFilters({ aparelho: v || null })}
        options={opts?.aparelhos || []}
        allLabel="Todos"
      />
      {dirty && (
        <button
          type="button"
          onClick={reset}
          className="rounded border border-[var(--color-line)] px-3 py-1.5 text-sm text-[var(--color-mist)] hover:border-[var(--color-accent)] hover:text-[var(--color-paper)]"
        >
          Limpar filtros
        </button>
      )}
      <div className="ml-auto font-mono text-[10px] text-[var(--color-mist)]">America/Bahia</div>
    </div>
  )
}
