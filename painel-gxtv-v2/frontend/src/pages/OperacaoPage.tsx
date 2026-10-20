import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type MetricEnvelope } from '@/lib/api'
import { useFilters } from '@/lib/filters'
import { StateBlock } from '@/components/StateBlock'
import { MetricTooltip } from '@/components/MetricTooltip'
import { KpiTile } from '@/components/KpiTile'
import { DrilldownPanel } from '@/components/DrilldownPanel'

export function OperacaoPage() {
  const { filters } = useFilters()
  const [drill, setDrill] = useState<string | null>(null)
  const q = useQuery({
    queryKey: ['operacao', filters],
    queryFn: () => api.operacao(filters),
    refetchInterval: 60_000,
  })

  if (q.isLoading) {
    return (
      <StateBlock
        title="Operação"
        envelope={{ state: 'loading', value: null, timezone: 'America/Bahia', computed_at: '' }}
      />
    )
  }
  if (q.isError) {
    const err = q.error as Error & { status?: number }
    if (err.status === 401) {
      window.location.href = '/v2/login'
      return null
    }
    return (
      <StateBlock
        envelope={{
          state: 'error',
          value: null,
          message: 'Falha ao carregar Operação',
          timezone: 'America/Bahia',
          computed_at: '',
        }}
      />
    )
  }

  const data = q.data as {
    is_seed?: boolean
    problemas: MetricEnvelope<{
      hoje: number
      ontem: number
      media_7d: number
      delta_ontem: number
      delta_media_7d: number
    }>
    correlacoes: MetricEnvelope<{
      por_app?: { app: string; n: number }[]
      por_aparelho?: { aparelho: string; n: number }[]
      por_hora?: { hora: number; n: number }[]
      cruzamentos?: { app: string; aparelho: string; hora: number; n: number }[]
    }>
    apps: MetricEnvelope
    aparelhos: MetricEnvelope
    utra_lg?: MetricEnvelope<{
      titulo?: string
      total: number
      taxa_sucesso: number | null
      taxa_xc_account: number | null
      taxa_falha: number | null
      utra_ok: number
      utra_xc_account: number
      outro_erro: number
      modelos_xc_account: { modelo: string; n: number }[]
      alerta_pendente?: boolean
      min_n?: number
      limiar_falha?: number
    }>
  }
  const p = data.problemas.value
  const corr = data.correlacoes.value
  const ul = data.utra_lg?.value
  const pct = (v: number | null | undefined) =>
    v == null ? '—' : `${Math.round(v * 100)}%`

  return (
    <div className="space-y-6">
      <section className="anim-rise">
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--color-accent)]">Operação</div>
        <h2 className="font-display text-3xl font-semibold text-[var(--color-ink)]">Problemas e correlações</h2>
        <p className="mt-1 max-w-2xl text-sm text-[var(--color-mist)]">
          Contagem vs ontem e média 7 dias. Cruzamento app × aparelho × horário (Bahia). Só webhook —
          zero GET DataCrazy.
          {data.is_seed ? ' · seed' : ''}
        </p>
      </section>

      <section className="grid gap-3 md:grid-cols-4">
        <KpiTile
          title="Problemas hoje"
          metricId="operacao.problemas"
          envelope={data.problemas}
          subtitle={p ? `Δ ontem ${p.delta_ontem >= 0 ? '+' : ''}${p.delta_ontem}` : null}
          onDrill={() => setDrill('operacao.problemas')}
        />
        <div className="rounded-md border border-[var(--color-line)] bg-[var(--color-panel)]/60 p-3">
          <div className="text-xs text-[var(--color-mist)]">Ontem</div>
          <div className="font-display text-2xl">{p?.ontem ?? '—'}</div>
        </div>
        <div className="rounded-md border border-[var(--color-line)] bg-[var(--color-panel)]/60 p-3">
          <div className="text-xs text-[var(--color-mist)]">Média 7d</div>
          <div className="font-display text-2xl">{p?.media_7d ?? '—'}</div>
        </div>
        <div className="rounded-md border border-[var(--color-line)] bg-[var(--color-panel)]/60 p-3">
          <div className="text-xs text-[var(--color-mist)]">Δ vs média</div>
          <div className="font-display text-2xl">
            {p ? `${p.delta_media_7d >= 0 ? '+' : ''}${p.delta_media_7d}` : '—'}
          </div>
        </div>
      </section>

      {data.utra_lg ? (
        <section className="anim-rise rounded-md border border-[var(--color-line)] bg-[var(--color-panel)]/60 p-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--color-accent)]">
                UTRA × LG
              </div>
              <h3 className="font-display text-2xl font-semibold text-[var(--color-ink)]">
                Taxa de sucesso do UTRA na LG
              </h3>
              <p className="mt-1 max-w-2xl text-sm text-[var(--color-mist)]">
                Só registra. Ordem UTRA→Brasil→Max não muda sozinha — se a falha passar de ~
                {Math.round((ul?.limiar_falha ?? 0.5) * 100)}% com n≥{ul?.min_n ?? 20}, alerta no Telegram
                pro Gustavo decidir.
              </p>
            </div>
            <MetricTooltip metricId="operacao.utra_lg">métrica CSV</MetricTooltip>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-4">
            <div>
              <div className="text-xs text-[var(--color-mist)]">Total LG→UTRA</div>
              <div className="font-display text-2xl">{ul?.total ?? '—'}</div>
            </div>
            <div>
              <div className="text-xs text-[var(--color-mist)]">Sucesso</div>
              <div className="font-display text-2xl">{pct(ul?.taxa_sucesso)}</div>
              <div className="text-[11px] text-[var(--color-mist)]">{ul?.utra_ok ?? 0} ok</div>
            </div>
            <div>
              <div className="text-xs text-[var(--color-mist)]">XC Account</div>
              <div className="font-display text-2xl">{pct(ul?.taxa_xc_account)}</div>
              <div className="text-[11px] text-[var(--color-mist)]">{ul?.utra_xc_account ?? 0}</div>
            </div>
            <div>
              <div className="text-xs text-[var(--color-mist)]">Falha (XC+outro)</div>
              <div className="font-display text-2xl">{pct(ul?.taxa_falha)}</div>
              <div className="text-[11px] text-[var(--color-mist)]">outro {ul?.outro_erro ?? 0}</div>
            </div>
          </div>
          <div className="mt-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--color-mist)]">
              Modelos com XC Account
            </div>
            <ul className="mt-2 max-h-40 space-y-1 overflow-auto font-mono text-xs">
              {(ul?.modelos_xc_account || []).length === 0 ? (
                <li className="text-[var(--color-mist)]">Nenhum registrado ainda</li>
              ) : (
                (ul?.modelos_xc_account || []).map((m) => (
                  <li key={m.modelo} className="flex justify-between gap-4">
                    <span>{m.modelo}</span>
                    <span>{m.n}</span>
                  </li>
                ))
              )}
            </ul>
          </div>
        </section>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-3">
        <StateBlock title="Apps" envelope={data.apps}>
          <MetricTooltip metricId="operacao.correlacoes">por app</MetricTooltip>
          <ul className="mt-2 max-h-56 space-y-1 overflow-auto text-sm">
            {(corr?.por_app || []).map((r) => (
              <li key={r.app} className="flex justify-between font-mono text-xs">
                <span>{r.app}</span>
                <span>{r.n}</span>
              </li>
            ))}
          </ul>
        </StateBlock>
        <StateBlock title="Aparelhos" envelope={data.aparelhos}>
          <ul className="mt-2 max-h-56 space-y-1 overflow-auto text-sm">
            {(corr?.por_aparelho || []).map((r) => (
              <li key={r.aparelho} className="flex justify-between font-mono text-xs">
                <span>{r.aparelho}</span>
                <span>{r.n}</span>
              </li>
            ))}
          </ul>
        </StateBlock>
        <StateBlock title="Correlações" envelope={data.correlacoes}>
          <ul className="mt-2 max-h-56 space-y-1 overflow-auto text-[11px] font-mono text-[var(--color-mist)]">
            {(corr?.cruzamentos || []).slice(0, 12).map((r, i) => (
              <li key={i}>
                {r.app} × {r.aparelho} @ {r.hora}h · {r.n}
              </li>
            ))}
          </ul>
          <button
            type="button"
            className="mt-3 text-xs text-[var(--color-accent)] underline-offset-2 hover:underline"
            onClick={() => setDrill('operacao.correlacoes')}
          >
            Drill-down
          </button>
        </StateBlock>
      </section>

      <DrilldownPanel
        metricId={drill}
        filters={filters}
        open={!!drill}
        onClose={() => setDrill(null)}
      />
    </div>
  )
}
