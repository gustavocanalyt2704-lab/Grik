import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type MetricEnvelope } from '@/lib/api'
import { useFilters } from '@/lib/filters'
import { StateBlock } from '@/components/StateBlock'
import { MetricTooltip } from '@/components/MetricTooltip'
import { KpiTile } from '@/components/KpiTile'
import { DrilldownPanel } from '@/components/DrilldownPanel'
import { GestorBanner } from '@/components/GestorBanner'
import { LiveChart, type Graficos } from '@/components/LiveChart'
import type { VendaLinha } from '@/lib/api'

type EtapaFunil = { id: string; label: string; n: number }
type BlocoFunil = {
  id: string
  label: string
  etapas: EtapaFunil[]
  taxa_ate_teste: number | null
  tempo_medio_ate_teste_s: number | null
  sem_resposta_3min: number | null
}
type FunilValor = {
  por_numero?: BlocoFunil[]
  sem_resposta_3min?: number | null
  alerta?: boolean
  mensagem_alerta?: string | null
}

function FunilVendas({
  envelope,
  onDrill,
}: {
  envelope?: MetricEnvelope<FunilValor | null>
  onDrill: () => void
}) {
  const env = envelope || {
    state: 'unavailable' as const,
    value: null,
    message: 'Funil de vendas sem eventos — não publicar 0',
    timezone: 'America/Bahia',
    computed_at: '',
  }
  const blocos = env.value?.por_numero || []
  const sem = env.value?.sem_resposta_3min
  return (
    <section className="rounded-3xl border border-[var(--color-line)] bg-[var(--color-panel)] p-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <MetricTooltip metricId="comercial.funil_vendas">Funil por número de venda</MetricTooltip>
          <p className="mt-1 text-sm text-[var(--color-mist)]">
            Leads novos, aparelho, app, teste, funcionou e pago. O contador de mensagem sem resposta há mais de 3 min tem que ficar em zero.
          </p>
        </div>
        {sem == null ? (
          <div className="rounded-2xl bg-[var(--color-paper)] px-3 py-2 text-sm text-[var(--color-mist)]">
            sem resposta &gt; 3 min: sem dado ao vivo
          </div>
        ) : (
          <div
            className={
              sem > 0
                ? 'rounded-2xl bg-red-50 px-3 py-2 text-sm font-semibold text-red-700'
                : 'rounded-2xl bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-800'
            }
          >
            sem resposta &gt; 3 min: {sem}
            {sem > 0 ? ' · alerta no Telegram' : ''}
          </div>
        )}
      </div>
      <StateBlock envelope={env}>
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          {blocos.map((bloco) => {
            const taxa =
              bloco.taxa_ate_teste == null ? 'sem dado' : `${Math.round(bloco.taxa_ate_teste * 100)}% até o teste`
            const tempo =
              bloco.tempo_medio_ate_teste_s == null
                ? 'tempo até o teste: sem dado'
                : `tempo médio até o teste: ${Math.round(bloco.tempo_medio_ate_teste_s / 60)} min`
            return (
              <article key={bloco.id} className="rounded-2xl border border-[var(--color-line)] p-3">
                <h3 className="text-sm font-semibold">{bloco.label}</h3>
                <p className="mt-1 text-xs text-[var(--color-mist)]">
                  {taxa} · {tempo}
                </p>
                <ol className="mt-3 space-y-1">
                  {bloco.etapas.map((etapa) => (
                    <li key={etapa.id} className="flex items-center justify-between text-sm">
                      <span>{etapa.label}</span>
                      <span className="font-mono">{etapa.n}</span>
                    </li>
                  ))}
                </ol>
                <p className="mt-2 text-xs text-[var(--color-mist)]">
                  sem resposta &gt; 3 min: {bloco.sem_resposta_3min == null ? 'sem dado' : bloco.sem_resposta_3min}
                </p>
              </article>
            )
          })}
        </div>
        <button
          type="button"
          className="mt-3 text-xs text-[var(--color-accent)] underline-offset-2 hover:underline"
          onClick={onDrill}
        >
          Drill-down
        </button>
      </StateBlock>
    </section>
  )
}

export function ComercialPage() {
  const { filters } = useFilters()
  const [drill, setDrill] = useState<string | null>(null)
  const q = useQuery({
    queryKey: ['comercial', filters],
    queryFn: () => api.comercial(filters),
    refetchInterval: 60_000,
  })

  if (q.isLoading) {
    return (
      <StateBlock
        title="Comercial"
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
          message: 'Falha ao carregar Comercial',
          timezone: 'America/Bahia',
          computed_at: '',
        }}
      />
    )
  }

  const data = q.data as {
    is_seed?: boolean
    vendas: MetricEnvelope
    vencem_hoje: MetricEnvelope<{ total: number | null; renovaram: number | null; pendentes: number | null }>
    dist_whatsapp: MetricEnvelope<{ items?: { id: string; label: string; vendas?: number | null; renovacoes?: number | null; nota?: string }[] }>
    nota_3619_0837?: string
    aviso_gestor?: string | null
    vendas_linhas?: VendaLinha[]
    vendas_sem_lista?: boolean
    funil_vendas?: MetricEnvelope<FunilValor | null>
    window: { label: string }
  }
  const venc = data.vencem_hoje.value
  const items = data.dist_whatsapp.value?.items || []
  const vendasVal = data.vendas.value as { total?: number | null; valor?: number | null } | null
  const linhas = data.vendas_linhas || []
  const graficos = (data as { graficos?: Graficos }).graficos

  return (
    <div className="space-y-6">
      <section className="anim-rise">
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--color-accent)]">Comercial</div>
        <h2 className="font-display text-3xl font-semibold text-[var(--color-ink)]">Vendas do Gestor</h2>
        <p className="mt-1 max-w-2xl text-sm text-[var(--color-mist)]">
          A venda nasce no Gestor. Se não há conversa no espelho, a origem fica como não identificada.
          {data.is_seed ? ' · seed' : ''}
        </p>
      </section>

      <GestorBanner aviso={data.aviso_gestor} />

      <section className="grid gap-3 lg:grid-cols-2">
        <LiveChart
          titulo="Vendas ao longo do dia"
          sub={graficos?.vendas_hora?.motivo || 'Pagamentos por hora.'}
          categorias={graficos?.vendas_hora?.rotulos}
          series={[{ nome: 'Pagamentos', dados: graficos?.vendas_hora?.n || [], area: true }]}
          vazio={graficos?.vendas_hora?.motivo || 'sem dado — o Gestor não manda a venda hora a hora'}
        />
        <LiveChart
          titulo="Vendas por WhatsApp"
          sub="3619 e 0837 entram juntos. Não é uma segunda conta do faturamento."
          tipo="bar"
          categorias={items.map((i) => i.label)}
          series={[
            { nome: 'Vendas', dados: items.map((i) => i.vendas ?? null) },
            { nome: 'Renovações', dados: items.map((i) => i.renovacoes ?? null) },
          ]}
          vazio="sem dado — distribuição do Gestor indisponível"
        />
      </section>

      <section className="rounded-3xl border border-[var(--color-line)] bg-[var(--color-panel)] p-4">
        <h3 className="text-sm font-medium">Vendas do período</h3>
        {data.vendas_sem_lista ? (
          <p className="mt-3 text-sm text-[var(--color-mist)]">Lista de vendas: sem dado</p>
        ) : linhas.length === 0 ? (
          <p className="mt-3 text-sm text-[var(--color-mist)]">Nenhuma venda listada neste período.</p>
        ) : (
          <ul className="mt-3 divide-y divide-[var(--color-line)]">
            {linhas.map((linha, i) => (
              <li key={`${linha.telefone_final}-${i}`} className="flex flex-col gap-1 py-3 text-sm sm:flex-row sm:items-center sm:justify-between">
                <span className="font-mono text-[var(--color-ink)]">{linha.telefone_final}</span>
                <span className="text-[var(--color-mist)]">
                  {linha.valor == null ? 'sem dado' : linha.valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                </span>
                <span className={linha.origem === 'origem não identificada' ? 'text-[var(--color-accent-2)]' : 'text-[var(--color-ink)]'}>
                  {linha.origem}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="grid gap-3 md:grid-cols-3">
        <KpiTile
          title="Vendas / faturamento"
          metricId="comercial.vendas"
          envelope={data.vendas}
          unit="R$"
          spark={graficos?.vendas_hora?.sem_dado ? null : graficos?.vendas_hora?.n}
          subtitle={
            vendasVal?.total != null ? `${vendasVal.total} renovações/vendas contadas` : data.nota_3619_0837 || null
          }
          onDrill={() => setDrill('comercial.vendas')}
        />
        <KpiTile
          title="Vencem hoje"
          metricId="comercial.vencem_hoje"
          envelope={data.vencem_hoje}
          subtitle={
            venc
              ? `renovaram ${venc.renovaram ?? '—'} · pendentes ${venc.pendentes ?? '—'}`
              : null
          }
          onDrill={() => setDrill('comercial.vencem_hoje')}
          delay={40}
        />
        <StateBlock title="Distribuição WhatsApp" envelope={data.dist_whatsapp}>
          <MetricTooltip metricId="comercial.dist_whatsapp">3619 / 0837</MetricTooltip>
          <ul className="mt-3 space-y-2">
            {items.map((it) => (
              <li
                key={it.id}
                className="flex items-center justify-between border-b border-[var(--color-line)]/50 pb-2 text-sm"
              >
                <span>{it.label}</span>
                <span className="font-mono text-[var(--color-mist)]">
                  {it.vendas != null ? it.vendas : it.nota ? 'no total' : '—'}
                </span>
              </li>
            ))}
          </ul>
          <button
            type="button"
            className="mt-3 text-xs text-[var(--color-accent)] underline-offset-2 hover:underline"
            onClick={() => setDrill('comercial.dist_whatsapp')}
          >
            Drill-down
          </button>
        </StateBlock>
      </section>

      <FunilVendas envelope={data.funil_vendas} onDrill={() => setDrill('comercial.funil_vendas')} />

      <DrilldownPanel
        metricId={drill}
        filters={filters}
        open={!!drill}
        onClose={() => setDrill(null)}
      />
    </div>
  )
}
