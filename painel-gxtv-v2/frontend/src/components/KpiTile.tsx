import { MetricTooltip } from '@/components/MetricTooltip'
import { StateBadge } from '@/components/StateBlock'
import type { MetricEnvelope } from '@/lib/api'
import clsx from 'clsx'

function headline(value: unknown, unit?: string | null): unknown {
  if (!value || typeof value !== 'object') return value
  const obj = value as { valor?: unknown; hoje?: unknown; n?: unknown; total?: unknown }
  if (unit === 'R$' && typeof obj.valor === 'number') return obj.valor
  if (typeof obj.hoje === 'number') return obj.hoje
  if (typeof obj.n === 'number') return obj.n
  if ('total' in obj) return obj.total
  return value
}

function formatValue(value: unknown, unit?: string | null): string {
  const shown = headline(value, unit)
  if (shown == null) return '—'
  if (typeof shown === 'number') {
    if (unit === 'R$') {
      return shown.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
    }
    return Number.isInteger(shown) ? String(shown) : shown.toFixed(2)
  }
  if (typeof shown === 'object') return 'sem dado'
  return String(shown)
}

export function KpiTile({
  title,
  metricId,
  envelope,
  unit,
  subtitle,
  onDrill,
  delay = 0,
}: {
  title: string
  metricId: string
  envelope: MetricEnvelope
  unit?: string | null
  subtitle?: string | null
  onDrill?: () => void
  delay?: number
}) {
  const clickable = Boolean(onDrill) && envelope.state !== 'loading'
  const main =
    envelope.state === 'unavailable' || envelope.state === 'empty'
      ? 'sem dado'
      : envelope.state === 'error'
        ? '—'
        : formatValue(envelope.value, unit)

  return (
    <button
      type="button"
      disabled={!clickable}
      onClick={onDrill}
      className={clsx(
        'anim-rise rounded-md border border-[var(--color-line)] bg-[var(--color-panel)]/60 p-3 text-left transition',
        clickable && 'hover:border-[var(--color-accent)] hover:bg-[var(--color-panel-2)]/70',
        !clickable && 'cursor-default',
      )}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="mb-1 flex items-start justify-between gap-2">
        <MetricTooltip metricId={metricId}>
          <span className="text-xs text-[var(--color-mist)]">{title}</span>
        </MetricTooltip>
        <StateBadge state={envelope.state} />
      </div>
      <div className="font-display text-2xl font-semibold tracking-tight text-[var(--color-paper)]">
        {main}
        {unit && main !== '—' && main !== 'sem dado' && unit !== 'R$' && (
          <span className="ml-1 text-sm font-sans font-normal text-[var(--color-mist)]">{unit}</span>
        )}
      </div>
      {subtitle && <p className="mt-1 text-[11px] text-[var(--color-mist)]">{subtitle}</p>}
      {envelope.state === 'unavailable' && (
        <p className="mt-1 text-[11px] text-[var(--color-accent-2)]">
          {envelope.message || 'Indisponível'}
          {envelope.source?.last_update ? ` · ${envelope.source.last_update}` : ''}
        </p>
      )}
      {envelope.state === 'stale' && envelope.message && (
        <p className="mt-1 text-[11px] text-[var(--color-stale)]">{envelope.message}</p>
      )}
      {envelope.is_seed && (
        <span className="mt-1 inline-block text-[10px] uppercase text-[var(--color-mist)]">seed</span>
      )}
    </button>
  )
}
