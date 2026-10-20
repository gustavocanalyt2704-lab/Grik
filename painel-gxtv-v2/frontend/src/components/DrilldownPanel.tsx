import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type DrilldownPayload, type GlobalFilters } from '@/lib/api'
import { StateBadge } from '@/components/StateBlock'

export function DrilldownPanel({
  metricId,
  filters,
  open,
  onClose,
  stage,
}: {
  metricId: string | null
  filters: GlobalFilters
  open: boolean
  onClose: () => void
  stage?: string | null
}) {
  const [page, setPage] = useState(1)
  const q = useQuery({
    queryKey: ['drilldown', metricId, page, filters, stage],
    queryFn: () =>
      api.drilldown({
        metric_id: metricId || '',
        page,
        page_size: 25,
        filters,
        stage,
      }),
    enabled: open && !!metricId,
  })

  useEffect(() => {
    setPage(1)
  }, [metricId, stage])

  if (!open || !metricId) return null

  const data = q.data as DrilldownPayload | undefined
  const rows = data?.rows || []
  const total = data?.total || 0
  const pages = Math.max(1, Math.ceil(total / 25))

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-4 md:items-center">
      <div className="anim-rise max-h-[85vh] w-full max-w-3xl overflow-hidden rounded-lg border border-[var(--color-line)] bg-[var(--color-ink-soft)] shadow-2xl">
        <div className="flex items-center justify-between border-b border-[var(--color-line)] px-4 py-3">
          <div>
            <div className="text-[11px] uppercase tracking-wide text-[var(--color-mist)]">Drill-down</div>
            <h3 className="font-display text-xl">{data?.metric?.name || metricId}</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-[var(--color-line)] px-3 py-1 text-sm hover:border-[var(--color-accent)]"
          >
            Fechar
          </button>
        </div>
        <div className="max-h-[60vh] overflow-auto px-4 py-3">
          {q.isLoading && <div className="skeleton h-24 w-full" />}
          {q.isError && (
            <p className="text-sm text-[var(--color-danger)]">Falha ao carregar drill-down</p>
          )}
          {data?.state && (
            <div className="mb-3 flex items-center gap-2 text-xs text-[var(--color-mist)]">
              <StateBadge state={data.state.state} />
              <span>
                {total} linha{total === 1 ? '' : 's'} · {data.window}
              </span>
            </div>
          )}
          {rows.length === 0 && !q.isLoading && (
            <p className="text-sm text-[var(--color-empty)]">
              {data?.state?.message || 'Sem linhas neste filtro'}
            </p>
          )}
          <ul className="space-y-2">
            {rows.map((row, idx) => (
              <li
                key={idx}
                className="rounded border border-[var(--color-line)] bg-[var(--color-panel)]/60 px-3 py-2 font-mono text-[11px] text-[var(--color-mist)]"
              >
                <pre className="whitespace-pre-wrap break-all">{JSON.stringify(row, null, 2)}</pre>
              </li>
            ))}
          </ul>
        </div>
        <div className="flex items-center justify-between border-t border-[var(--color-line)] px-4 py-2 text-sm">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="rounded border border-[var(--color-line)] px-3 py-1 disabled:opacity-40"
          >
            Anterior
          </button>
          <span className="font-mono text-xs text-[var(--color-mist)]">
            {page}/{pages}
          </span>
          <button
            type="button"
            disabled={page >= pages}
            onClick={() => setPage((p) => p + 1)}
            className="rounded border border-[var(--color-line)] px-3 py-1 disabled:opacity-40"
          >
            Próxima
          </button>
        </div>
      </div>
    </div>
  )
}
