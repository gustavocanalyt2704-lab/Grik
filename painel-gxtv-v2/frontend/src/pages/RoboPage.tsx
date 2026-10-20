import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type MetricEnvelope } from '@/lib/api'
import { useFilters } from '@/lib/filters'
import { StateBlock } from '@/components/StateBlock'
import { MetricTooltip } from '@/components/MetricTooltip'
import { KpiTile } from '@/components/KpiTile'
import { DrilldownPanel } from '@/components/DrilldownPanel'

export function RoboPage() {
  const { filters } = useFilters()
  const [drill, setDrill] = useState<string | null>(null)
  const q = useQuery({
    queryKey: ['robo', filters],
    queryFn: () => api.robo(filters),
    refetchInterval: 20_000,
  })

  if (q.isLoading) {
    return (
      <StateBlock
        title="Robô"
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
          message: 'Falha ao carregar Robô',
          timezone: 'America/Bahia',
          computed_at: '',
        }}
      />
    )
  }

  const data = q.data as {
    is_seed?: boolean
    ocupadas: MetricEnvelope<{ n?: number; label_claro?: string }>
    envios: MetricEnvelope<{ n?: number; label_claro?: string }>
    aguardando_poll: MetricEnvelope<{ n?: number; label_claro?: string }>
    catalogo: { id: string; name: string; definition: string; formula: string; source: string }[]
  }

  return (
    <div className="space-y-6">
      <section className="anim-rise">
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--color-accent)]">Robô</div>
        <h2 className="font-display text-3xl font-semibold text-[var(--color-ink)]">O que o robô está fazendo</h2>
        <p className="mt-1 max-w-2xl text-sm text-[var(--color-mist)]">
          Sem jargão interno. Cada número tem tooltip do registro único (definição, fonte, fórmula, TZ).
          {data.is_seed ? ' · seed' : ''}
        </p>
      </section>

      <section className="grid gap-3 md:grid-cols-3">
        <KpiTile
          title={data.ocupadas.value?.label_claro || 'Conversas em atendimento pelo robô'}
          metricId="robo.ocupadas"
          envelope={data.ocupadas}
          subtitle="POLL ocupadas"
          onDrill={() => setDrill('robo.ocupadas')}
        />
        <KpiTile
          title={data.aguardando_poll.value?.label_claro || 'Fila do robô'}
          metricId="robo.ocupadas"
          envelope={data.aguardando_poll}
          subtitle="POLL aguardando"
          onDrill={() => setDrill('robo.ocupadas')}
          delay={40}
        />
        <KpiTile
          title={data.envios.value?.label_claro || 'Envios do robô'}
          metricId="robo.envios"
          envelope={data.envios}
          onDrill={() => setDrill('robo.envios')}
          delay={80}
        />
      </section>

      <section>
        <h3 className="mb-2 font-display text-xl">Catálogo (registro)</h3>
        <div className="grid gap-3 md:grid-cols-2">
          {(data.catalogo || []).map((m) => (
            <div
              key={m.id}
              className="rounded-md border border-[var(--color-line)] bg-[var(--color-panel)]/50 p-4"
            >
              <MetricTooltip metricId={m.id}>
                <span className="font-display text-lg">{m.name}</span>
              </MetricTooltip>
              <p className="mt-1 text-sm text-[var(--color-mist)]">{m.definition}</p>
              <p className="mt-2 font-mono text-[11px] text-[var(--color-mist)]">{m.formula}</p>
              <p className="mt-1 text-[11px] text-[var(--color-accent)]">Fonte: {m.source}</p>
            </div>
          ))}
        </div>
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
