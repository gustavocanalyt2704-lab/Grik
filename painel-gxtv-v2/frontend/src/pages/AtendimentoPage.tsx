import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useFilters } from '@/lib/filters'
import { StateBlock } from '@/components/StateBlock'
import { MetricTooltip } from '@/components/MetricTooltip'
import { KpiTile } from '@/components/KpiTile'
import { DrilldownPanel } from '@/components/DrilldownPanel'
import { LiveChart } from '@/components/LiveChart'

function fmtSec(v: unknown): string {
  if (typeof v !== 'number' || Number.isNaN(v)) return '—'
  if (v < 60) return `${Math.round(v)}s`
  const m = Math.floor(v / 60)
  const s = Math.round(v % 60)
  return `${m}m${s.toString().padStart(2, '0')}s`
}

export function AtendimentoPage() {
  const { filters } = useFilters()
  const [drill, setDrill] = useState<string | null>(null)
  const [stage, setStage] = useState<string | null>(null)
  const q = useQuery({
    queryKey: ['atendimento', filters],
    queryFn: () => api.atendimento(filters),
    refetchInterval: 45_000,
  })

  if (q.isLoading) {
    return (
      <StateBlock
        title="Atendimento"
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
          message: 'Falha ao carregar Atendimento',
          timezone: 'America/Bahia',
          computed_at: '',
        }}
      />
    )
  }

  const data = q.data!
  const stages = data.funil.value?.stages || []
  const atual = data.atual_vs_historico.atual || {}
  const hist = data.atual_vs_historico.historico_7d || {}

  return (
    <div className="space-y-6">
      <section className="anim-rise">
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--color-accent)]">Atendimento</div>
        <h2 className="font-display text-3xl font-semibold text-[var(--color-ink)]">Funil e tempo de resposta</h2>
        <p className="mt-1 max-w-2xl text-sm text-[var(--color-mist)]">
          Estágios clicáveis com drill-down. Tempos agrupam mensagens seguidas do mesmo lado. Sem rótulo
          “abandonado”. Fonte: webhook/espelho.
          {data.is_seed ? ' · seed' : ''}
        </p>
      </section>

      <section>
        <div className="mb-2 flex items-center gap-2">
          <MetricTooltip metricId="atendimento.funil">Funil</MetricTooltip>
          <span className="text-xs text-[var(--color-mist)]">
            total {data.funil.value?.total ?? '—'} · {data.window.label}
          </span>
        </div>
        <LiveChart
          titulo="Funil do atendimento"
          sub="Do contato novo até o resolvido. Toque no estágio abaixo para ver os nomes."
          tipo="bar"
          categorias={stages.map((s) => s.label)}
          series={[{ nome: 'Conversas', dados: stages.map((s) => s.n) }]}
          vazio={data.funil.message || 'sem dado'}
        />
        <StateBlock envelope={data.funil}>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {stages.map((s, i) => (
              <button
                key={s.id}
                type="button"
                onClick={() => {
                  setStage(s.id)
                  setDrill('atendimento.funil')
                }}
                className="anim-rise rounded-2xl border border-[var(--color-line)] bg-[var(--color-panel)] px-3 py-3 text-left shadow-[var(--shadow)] hover:border-[color-mix(in_oklab,var(--color-accent)_55%,transparent)]"
                style={{ animationDelay: `${i * 40}ms` }}
              >
                <div className="text-[11px] uppercase tracking-wide text-[var(--color-mist)]">{s.label}</div>
                <div className="font-display text-3xl font-semibold">{s.n}</div>
              </button>
            ))}
          </div>
        </StateBlock>
      </section>

      <section>
        <h3 className="mb-2 font-display text-xl">Tempo de resposta</h3>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <KpiTile
            title="Média"
            metricId="atendimento.t_resposta_media"
            envelope={{
              ...data.tempos.media,
              value: data.tempos.media.value,
            }}
            subtitle={fmtSec(data.tempos.media.value)}
            onDrill={() => {
              setStage(null)
              setDrill('atendimento.t_resposta_media')
            }}
          />
          <KpiTile
            title="Mediana"
            metricId="atendimento.t_resposta_mediana"
            envelope={data.tempos.mediana}
            subtitle={fmtSec(data.tempos.mediana.value)}
            onDrill={() => {
              setStage(null)
              setDrill('atendimento.t_resposta_mediana')
            }}
            delay={40}
          />
          <KpiTile
            title="P95"
            metricId="atendimento.t_resposta_p95"
            envelope={data.tempos.p95}
            subtitle={fmtSec(data.tempos.p95.value)}
            onDrill={() => {
              setStage(null)
              setDrill('atendimento.t_resposta_p95')
            }}
            delay={80}
          />
          <KpiTile
            title="Máximo"
            metricId="atendimento.t_resposta_max"
            envelope={data.tempos.max}
            subtitle={fmtSec(data.tempos.max.value)}
            onDrill={() => {
              setStage(null)
              setDrill('atendimento.t_resposta_max')
            }}
            delay={120}
          />
        </div>
      </section>

      <section className="grid gap-3 md:grid-cols-2">
        <div className="rounded-2xl border border-[var(--color-line)] bg-[var(--color-panel)] p-4 shadow-[var(--shadow)]">
          <h3 className="mb-2 text-sm font-medium">Atual (período)</h3>
          <dl className="grid grid-cols-2 gap-2 font-mono text-xs text-[var(--color-mist)]">
            <div>média · {fmtSec(atual.media)}</div>
            <div>mediana · {fmtSec(atual.mediana)}</div>
            <div>P95 · {fmtSec(atual.p95)}</div>
            <div>máx · {fmtSec(atual.max)}</div>
            <div className="col-span-2">n gaps · {String(atual.n ?? '—')}</div>
          </dl>
        </div>
        <div className="rounded-2xl border border-[var(--color-line)] bg-[var(--color-panel)] p-4 shadow-[var(--shadow)]">
          <h3 className="mb-2 text-sm font-medium">Histórico 7 dias</h3>
          <dl className="grid grid-cols-2 gap-2 font-mono text-xs text-[var(--color-mist)]">
            <div>média · {fmtSec(hist.media)}</div>
            <div>mediana · {fmtSec(hist.mediana)}</div>
            <div>P95 · {fmtSec(hist.p95)}</div>
            <div>máx · {fmtSec(hist.max)}</div>
            <div className="col-span-2">n gaps · {String(hist.n ?? '—')}</div>
          </dl>
        </div>
      </section>

      <DrilldownPanel
        metricId={drill}
        filters={filters}
        open={!!drill}
        stage={stage}
        onClose={() => {
          setDrill(null)
          setStage(null)
        }}
      />
    </div>
  )
}
