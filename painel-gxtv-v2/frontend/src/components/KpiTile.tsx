import { MetricTooltip } from '@/components/MetricTooltip'
import { Sparkline } from '@/components/Sparkline'
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
  spark,
  delta,
  deltaHint = 'vs ontem',
  deltaGood = 'up',
  mostrarDelta = false,
}: {
  title: string
  metricId: string
  envelope: MetricEnvelope
  unit?: string | null
  subtitle?: string | null
  onDrill?: () => void
  delay?: number
  spark?: Array<number | null> | null
  delta?: number | null
  deltaHint?: string
  deltaGood?: 'up' | 'down'
  mostrarDelta?: boolean
}) {
  const clickable = Boolean(onDrill) && envelope.state !== 'loading'
  const vazio = envelope.state === 'unavailable' || envelope.state === 'empty' || envelope.state === 'error'
  const main = vazio && envelope.state !== 'error' ? 'sem dado' : envelope.state === 'error' ? '—' : formatValue(envelope.value, unit)
  const temDelta = delta != null && !Number.isNaN(Number(delta))
  const bom = temDelta && (deltaGood === 'up' ? Number(delta) > 0 : Number(delta) < 0)
  const ruim = temDelta && (deltaGood === 'up' ? Number(delta) < 0 : Number(delta) > 0)
  const sinal = temDelta && Number(delta) > 0 ? '+' : ''

  return (
    <button
      type="button"
      disabled={!clickable}
      onClick={onDrill}
      className={clsx(
        'anim-rise group relative overflow-hidden rounded-2xl border border-[var(--color-line)] bg-[var(--color-panel)] p-4 text-left shadow-[var(--shadow)] transition',
        clickable && 'hover:border-[color-mix(in_oklab,var(--color-accent)_55%,transparent)]',
        !clickable && 'cursor-default',
      )}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-16 opacity-80"
        style={{ background: 'linear-gradient(180deg, color-mix(in oklab, var(--color-accent) 10%, transparent), transparent)' }}
      />
      <div className="relative mb-3 flex items-start justify-between gap-3">
        <MetricTooltip metricId={metricId}>
          <span className="text-[12px] font-medium text-[var(--color-mist)]">{title}</span>
        </MetricTooltip>
        <Sparkline dados={spark} />
      </div>
      <div className="relative font-display text-[32px] leading-none font-semibold tracking-tight text-[var(--color-paper)]">
        {main}
        {unit && main !== '—' && main !== 'sem dado' && unit !== 'R$' && (
          <span className="ml-1 text-sm font-sans font-medium text-[var(--color-mist)]">{unit}</span>
        )}
      </div>
      <div className="relative mt-3 flex flex-wrap items-center gap-2">
        {temDelta ? (
          <span className={bom ? 'delta-up' : ruim ? 'delta-down' : 'delta-flat'}>
            {sinal}
            {Number.isInteger(Number(delta)) ? Number(delta) : Number(delta).toFixed(1)} {deltaHint}
          </span>
        ) : mostrarDelta ? (
          <span className="delta-flat">ontem · sem dado</span>
        ) : null}
        <StateBadge state={envelope.state} />
        {envelope.is_seed && <span className="delta-flat">exemplo</span>}
      </div>
      {subtitle && <p className="relative mt-2 text-[12px] leading-snug text-[var(--color-mist)]">{subtitle}</p>}
      {envelope.state === 'unavailable' && (
        <p className="relative mt-1 text-[11px] text-[var(--color-accent-2)]">
          {envelope.message || 'Indisponível'}
          {envelope.source?.last_update ? ` · ${envelope.source.last_update}` : ''}
        </p>
      )}
    </button>
  )
}
