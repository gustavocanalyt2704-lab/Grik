import type { MetricEnvelope } from '@/lib/api'
import clsx from 'clsx'

const LABELS: Record<string, string> = {
  loading: 'Carregando',
  ok: 'OK',
  empty: 'Vazio',
  error: 'Erro',
  stale: 'Atrasado',
  unavailable: 'Indisponível',
}

const TONES: Record<string, string> = {
  loading: 'border-[var(--color-line)] text-[var(--color-mist)]',
  ok: 'border-[color-mix(in_oklab,var(--color-ok)_45%,transparent)] text-[var(--color-ok)]',
  empty: 'border-[var(--color-line)] text-[var(--color-empty)]',
  error: 'border-[color-mix(in_oklab,var(--color-danger)_50%,transparent)] text-[var(--color-danger)]',
  stale: 'border-[color-mix(in_oklab,var(--color-stale)_50%,transparent)] text-[var(--color-stale)]',
  unavailable: 'border-[color-mix(in_oklab,var(--color-accent-2)_45%,transparent)] text-[var(--color-accent-2)]',
}

export function StateBadge({ state }: { state: string }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide',
        TONES[state] || TONES.empty,
      )}
    >
      {state === 'loading' && <span className="anim-pulse h-1.5 w-1.5 rounded-full bg-current" />}
      {LABELS[state] || state}
    </span>
  )
}

export function StateBlock({
  envelope,
  title,
  children,
}: {
  envelope: MetricEnvelope
  title?: string
  children?: React.ReactNode
}) {
  const { state, message, source, value, is_seed } = envelope

  if (state === 'loading') {
    return (
      <div className="space-y-2 rounded-md border border-[var(--color-line)] bg-[var(--color-panel)]/70 p-4">
        {title && <div className="text-sm text-[var(--color-mist)]">{title}</div>}
        <div className="skeleton h-8 w-2/3" />
        <div className="skeleton h-4 w-1/2" />
        <StateBadge state="loading" />
      </div>
    )
  }

  if (state === 'error') {
    return (
      <div className="rounded-md border border-[color-mix(in_oklab,var(--color-danger)_40%,transparent)] bg-[var(--color-panel)]/80 p-4">
        <div className="mb-2 flex items-center justify-between gap-2">
          {title && <h3 className="text-sm font-medium">{title}</h3>}
          <StateBadge state="error" />
        </div>
        <p className="text-sm text-[var(--color-danger)]">{message || 'Erro ao carregar'}</p>
      </div>
    )
  }

  if (state === 'empty') {
    return (
      <div className="rounded-md border border-dashed border-[var(--color-line)] bg-[var(--color-panel)]/40 p-4">
        <div className="mb-2 flex items-center justify-between gap-2">
          {title && <h3 className="text-sm font-medium text-[var(--color-mist)]">{title}</h3>}
          <StateBadge state="empty" />
        </div>
        <p className="text-sm text-[var(--color-empty)]">{message || 'Sem dados neste período'}</p>
      </div>
    )
  }

  if (state === 'unavailable') {
    return (
      <div className="rounded-md border border-[color-mix(in_oklab,var(--color-accent-2)_40%,transparent)] bg-[var(--color-panel)]/80 p-4">
        <div className="mb-2 flex items-center justify-between gap-2">
          {title && <h3 className="text-sm font-medium">{title}</h3>}
          <StateBadge state="unavailable" />
        </div>
        <p className="text-sm text-[var(--color-accent-2)]">
          {message || 'Fonte indisponível'}
        </p>
        {source?.last_update && (
          <p className="mt-2 font-mono text-xs text-[var(--color-mist)]">
            Última atualização: {source.last_update}
          </p>
        )}
        {value != null && (
          <div className="mt-3 border-t border-[var(--color-line)] pt-3 text-xs text-[var(--color-mist)]">
            Cache preservado — não é zero inventado.
            {children}
          </div>
        )}
      </div>
    )
  }

  return (
    <div
      className={clsx(
        'rounded-md border bg-[var(--color-panel)]/75 p-4',
        state === 'stale'
          ? 'border-[color-mix(in_oklab,var(--color-stale)_40%,transparent)]'
          : 'border-[var(--color-line)]',
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        {title && <h3 className="text-sm font-medium">{title}</h3>}
        <div className="flex items-center gap-2">
          {is_seed && (
            <span className="rounded border border-[var(--color-line)] px-1.5 py-0.5 text-[10px] uppercase text-[var(--color-mist)]">
              seed
            </span>
          )}
          <StateBadge state={state} />
        </div>
      </div>
      {state === 'stale' && message && (
        <p className="mb-2 text-xs text-[var(--color-stale)]">{message}</p>
      )}
      {children}
      {source?.last_update && (
        <p className="mt-3 font-mono text-[10px] text-[var(--color-mist)]">
          {source.label} · {source.last_update}
        </p>
      )}
    </div>
  )
}
