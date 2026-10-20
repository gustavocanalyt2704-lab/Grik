import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { StateBlock } from '@/components/StateBlock'
import { MetricTooltip } from '@/components/MetricTooltip'
import { KpiTile } from '@/components/KpiTile'
import { useState } from 'react'
import { DrilldownPanel } from '@/components/DrilldownPanel'
import { useFilters } from '@/lib/filters'

export function EspelhoPage() {
  const { filters } = useFilters()
  const [drill, setDrill] = useState<string | null>(null)
  const q = useQuery({
    queryKey: ['espelho'],
    queryFn: api.espelho,
    refetchInterval: 20_000,
  })

  if (q.isLoading) {
    return (
      <StateBlock
        title="Espelho"
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
          message: 'Falha ao carregar o Espelho',
          timezone: 'America/Bahia',
          computed_at: '',
        }}
      />
    )
  }

  const data = q.data!

  return (
    <div className="space-y-6">
      <section className="anim-rise">
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--color-accent)]">Espelho</div>
        <h2 className="font-display text-3xl font-semibold text-[var(--color-ink)]">Saúde do webhook</h2>
        <p className="mt-1 max-w-2xl text-sm text-[var(--color-mist)]">
          Lag, cobertura e presença da fila — leitura local apenas. Nenhuma chamada DataCrazy de
          conversa.
          {data.is_seed ? ' · seed' : ''}
        </p>
      </section>

      <section className="grid gap-3 md:grid-cols-3">
        <KpiTile
          title="Lag"
          metricId="espelho.lag"
          envelope={data.lag}
          unit="s"
          onDrill={() => setDrill('espelho.lag')}
        />
        <KpiTile
          title="Cobertura"
          metricId="espelho.cobertura"
          envelope={
            typeof data.cobertura.value === 'number'
              ? { ...data.cobertura, value: Math.round(data.cobertura.value * 1000) / 10 }
              : data.cobertura
          }
          unit="%"
          subtitle={
            typeof data.cobertura.value === 'number'
              ? 'eventos com texto / eventos'
              : null
          }
          onDrill={() => setDrill('espelho.cobertura')}
          delay={40}
        />
        <StateBlock title="Pacote saúde" envelope={data.saude}>
          <MetricTooltip metricId="inicio.saude_espelho">meta + fila</MetricTooltip>
          {data.saude.value && (
            <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
              {Object.entries(data.saude.value).map(([chave, valor]) => (
                <div key={chave} className="rounded-xl bg-[var(--color-panel-2)] px-3 py-2">
                  <dt className="text-[11px] uppercase tracking-wide text-[var(--color-mist)]">{chave.replaceAll('_', ' ')}</dt>
                  <dd className="font-mono text-[var(--color-ink)]">{valor == null ? 'sem dado' : String(valor)}</dd>
                </div>
              ))}
            </dl>
          )}
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
