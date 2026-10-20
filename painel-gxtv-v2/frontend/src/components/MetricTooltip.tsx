import { useQuery } from '@tanstack/react-query'
import { api, type MetricDef } from '@/lib/api'
import { useState } from 'react'

export function MetricTooltip({
  metricId,
  children,
}: {
  metricId: string
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(false)
  const q = useQuery({
    queryKey: ['registry'],
    queryFn: api.registry,
    staleTime: 60_000,
  })
  const metric = q.data?.metrics.find((m: MetricDef) => m.id === metricId)

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <span
        tabIndex={0}
        className="inline-flex items-center gap-1 border-b border-dotted border-[var(--color-mist)] text-left"
        aria-describedby={open ? `tip-${metricId}` : undefined}
      >
        {children}
        <span className="text-[10px] text-[var(--color-mist)]">ⓘ</span>
      </span>
      {open && (
        <div
          id={`tip-${metricId}`}
          role="tooltip"
          className="anim-rise absolute left-0 top-full z-40 mt-2 w-72 rounded-xl border border-[var(--color-line)] bg-white p-3 text-[var(--color-ink)] shadow-xl"
        >
          {!metric ? (
            <p className="text-xs text-[var(--color-mist)]">Carregando registro…</p>
          ) : (
            <div className="space-y-1.5 text-xs leading-relaxed">
              <div className="font-display text-sm text-[var(--color-paper)]">{metric.name}</div>
              <p className="text-[var(--color-mist)]">{metric.definition}</p>
              <p>
                <span className="text-[var(--color-accent)]">Fonte:</span> {metric.source}
              </p>
              <p className="font-mono text-[11px] text-[var(--color-mist)]">
                {metric.formula}
              </p>
              <p className="text-[var(--color-mist)]">
                TZ {metric.timezone} · janela {metric.default_window}
                {metric.last_update ? ` · ${metric.last_update}` : ''}
              </p>
              {metric.notes && <p className="text-[var(--color-accent-2)]">{metric.notes}</p>}
            </div>
          )}
        </div>
      )}
    </span>
  )
}
