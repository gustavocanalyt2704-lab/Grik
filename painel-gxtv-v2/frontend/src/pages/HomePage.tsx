import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useFilters } from '@/lib/filters'
import { StateBlock } from '@/components/StateBlock'
import { MetricTooltip } from '@/components/MetricTooltip'
import { KpiTile } from '@/components/KpiTile'
import { LiveLog } from '@/components/LiveLog'
import { DrilldownPanel } from '@/components/DrilldownPanel'
import { GestorBanner } from '@/components/GestorBanner'
import { LiveChart, type Graficos } from '@/components/LiveChart'
import { Inbox } from 'lucide-react'
import type { CampoNumero, GrupoNumeros, NumeroCard, ResumoLateral } from '@/lib/api'

const PERIODOS = [
  { id: 'hoje', label: 'Hoje' },
  { id: 'ontem', label: 'Ontem' },
  { id: '7d', label: '7 dias' },
]

function valorCampo(cell: CampoNumero | undefined) {
  if (!cell || cell.rotulo === 'sem dado') return 'sem dado'
  return cell.rotulo
}

function NumeroLinha({ card, max }: { card: NumeroCard; max: number }) {
  const n = card.conversas.valor ?? 0
  const largura = max > 0 ? Math.max(4, Math.round((n / max) * 100)) : 0
  const vazio = (rotulo: string) => rotulo === 'sem dado'
  return (
    <article className="border-b border-[var(--color-line)] py-2.5 last:border-b-0">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="min-w-0 break-words text-sm font-semibold leading-snug text-[var(--color-ink)]">
          {card.id}
        </h3>
        <span className="shrink-0 font-mono text-sm text-[var(--color-ink)]">{valorCampo(card.conversas)}</span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-[var(--color-panel-2)]">
        <div className="h-full rounded-full bg-[var(--color-accent)]" style={{ width: `${largura}%` }} />
      </div>
      <p className="mt-1.5 text-[12px] leading-snug text-[var(--color-mist)]">
        <span className={vazio(card.finalizadas.rotulo) ? '' : 'text-[var(--color-ink-soft)]'}>
          finalizadas {valorCampo(card.finalizadas)}
        </span>
        {' · '}
        abertas {valorCampo(card.abertas)}
        {' · '}
        resposta {valorCampo(card.tempo_resposta)}
      </p>
      <p className="text-[12px] leading-snug text-[var(--color-mist)]">
        Pix {valorCampo(card.pix_enviados)}
        {' · '}
        vendas {valorCampo(card.vendas_dia)}
      </p>
    </article>
  )
}

function GrupoLista({ grupo }: { grupo: GrupoNumeros }) {
  const max = Math.max(...grupo.cards.map((c) => c.conversas.valor ?? 0), 1)
  return (
    <section className="rounded-2xl border border-[var(--color-line)] bg-[var(--color-panel)] px-3 py-2">
      <header className="flex items-baseline justify-between gap-2 border-b border-[var(--color-line)] py-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-accent)]">
          {grupo.titulo}
        </h3>
        <span className="text-[11px] text-[var(--color-mist)]">{grupo.cards.length}</span>
      </header>
      {grupo.cards.map((card) => (
        <NumeroLinha key={card.id} card={card} max={max} />
      ))}
    </section>
  )
}

function ResumoCard({ titulo, sub, cell }: { titulo: string; sub: string; cell?: CampoNumero }) {
  const vazio = !cell || cell.rotulo === 'sem dado'
  return (
    <article className="rounded-2xl border border-[var(--color-line)] bg-[var(--color-panel)] px-3 py-3">
      <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--color-mist)]">{titulo}</p>
      <p className={vazio ? 'mt-1 text-sm text-[var(--color-mist)]' : 'mt-1 font-display text-2xl text-[var(--color-ink)]'}>
        {vazio ? 'sem dado' : cell.rotulo}
      </p>
      <p className="mt-1 text-[12px] leading-snug text-[var(--color-ink-soft)]">
        {vazio ? cell?.detalhe || sub : cell.detalhe || sub}
      </p>
    </article>
  )
}

function ResumoLateralPainel({ resumo }: { resumo?: ResumoLateral }) {
  return (
    <aside className="grid gap-2 sm:grid-cols-3 lg:grid-cols-1">
      <ResumoCard titulo="Pediu preço" sub="pela conversa" cell={resumo?.pediram_assinatura} />
      <ResumoCard titulo="Pagamentos" sub="com o valor em R$" cell={resumo?.pagamentos} />
      <ResumoCard titulo="Renovações" sub="conferidas no dia" cell={resumo?.renovacoes} />
    </aside>
  )
}

export function HomePage() {
  const { filters, setFilters } = useFilters()
  const [drill, setDrill] = useState<string | null>(null)
  const inicio = useQuery({
    queryKey: ['inicio', filters],
    queryFn: () => api.inicio(filters),
    refetchInterval: 30_000,
  })

  if (inicio.isLoading) {
    return (
      <div className="grid gap-3 md:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <StateBlock
            key={i}
            title="…"
            envelope={{ state: 'loading', value: null, timezone: 'America/Bahia', computed_at: '' }}
          />
        ))}
      </div>
    )
  }

  if (inicio.isError) {
    const err = inicio.error as Error & { status?: number }
    if (err.status === 401) {
      window.location.href = '/v2/login'
      return null
    }
    return (
      <StateBlock
        envelope={{
          state: 'error',
          value: null,
          message: 'Falha ao carregar o início',
          timezone: 'America/Bahia',
          computed_at: '',
        }}
      />
    )
  }

  const data = inicio.data!
  const k = data.kpis
  const venc = k.vencem_hoje.value
  const espera = k.esperando_15min.value
  const entrada = data.entrada_viva
  const grupos = data.numeros?.grupos || []
  const graficos = (data as { graficos?: Graficos }).graficos
  const hoje = new Intl.DateTimeFormat('pt-BR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    timeZone: 'America/Bahia',
  }).format(new Date())
  const titulo =
    filters.periodo === 'ontem' ? 'Ontem' : filters.periodo === '7d' ? '7 dias' : 'Hoje'

  return (
    <div className="space-y-6">
      <section className="anim-rise">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--color-accent)]">
          {hoje}
        </p>
        <h2 className="font-display text-[28px] font-semibold text-[var(--color-ink)] md:text-[32px]">{titulo}</h2>
        <p className="mt-1 max-w-2xl text-sm leading-relaxed text-[var(--color-mist)]">
          Todos os WhatsApps que atenderam no período, do maior volume para o menor. A lista sai da
          fila do webhook, a mesma fonte do gráfico Por número de WhatsApp.
          {data.is_seed ? ' · modo seed' : ''}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {PERIODOS.map((p) => {
            const ativo = filters.periodo === p.id
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => setFilters({ periodo: p.id })}
                className={
                  ativo
                    ? 'min-h-10 rounded-full bg-[var(--color-accent)] px-4 text-sm font-medium text-[var(--color-on-accent)]'
                    : 'min-h-10 rounded-full border border-[var(--color-line)] bg-[var(--color-panel)] px-4 text-sm text-[var(--color-ink)]'
                }
              >
                {p.label}
              </button>
            )
          })}
        </div>
      </section>

      <GestorBanner aviso={data.numeros?.aviso_gestor} />

      <section className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_17rem]">
        <div className="order-2 space-y-3 lg:order-1">
          {grupos.length === 0 ? (
            <div className="flex items-start gap-3 rounded-2xl border border-dashed border-[var(--color-line)] bg-[var(--color-panel)] px-4 py-6 text-sm text-[var(--color-mist)]">
              <Inbox size={18} className="mt-0.5 shrink-0" />
              <div>
                <p className="font-medium text-[var(--color-ink)]">Nenhum WhatsApp nesta lista</p>
                <p className="mt-1 leading-relaxed">{data.numeros?.nota || 'Sem a fila do webhook, a lista fica sem dado.'}</p>
              </div>
            </div>
          ) : (
            grupos.map((grupo) => <GrupoLista key={grupo.id} grupo={grupo} />)
          )}
          {grupos.length > 0 && data.numeros?.nota && (
            <p className="text-[12px] leading-relaxed text-[var(--color-mist)]">{data.numeros.nota}</p>
          )}
        </div>
        <div className="order-1 lg:order-2 lg:sticky lg:top-20">
          <ResumoLateralPainel resumo={data.numeros?.resumo} />
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <KpiTile
          title="Faturamento"
          metricId="inicio.faturamento"
          envelope={k.faturamento}
          unit="R$"
          spark={graficos?.vendas_hora?.sem_dado ? null : graficos?.vendas_hora?.n}
          onDrill={() => setDrill('inicio.faturamento')}
          delay={0}
        />
        <KpiTile
          title="Renovações"
          metricId="inicio.renovacoes"
          envelope={k.renovacoes}
          onDrill={() => setDrill('inicio.renovacoes')}
          delay={40}
        />
        <KpiTile
          title="Vencem hoje"
          metricId="inicio.vencem_hoje"
          envelope={k.vencem_hoje}
          subtitle={
            venc
              ? `renovaram ${venc.renovaram ?? '—'} · pendentes ${venc.pendentes ?? '—'}`
              : null
          }
          onDrill={() => setDrill('inicio.vencem_hoje')}
          delay={80}
        />
        <KpiTile
          title="Atendidos"
          metricId="inicio.atendidos"
          envelope={k.atendidos}
          onDrill={() => setDrill('inicio.atendidos')}
          delay={120}
        />
        <KpiTile
          title="Esperando >15 min"
          metricId="inicio.esperando_15min"
          envelope={k.esperando_15min}
          subtitle="AGORA"
          onDrill={() => setDrill('inicio.esperando_15min')}
          delay={160}
        />
        <KpiTile
          title="Clientes / min"
          metricId="inicio.clientes_min"
          envelope={k.clientes_min}
          unit="cli/min"
          onDrill={() => setDrill('inicio.clientes_min')}
          delay={200}
        />
      </section>

      <section className="grid gap-3 lg:grid-cols-2">
        <LiveChart
          titulo="Mensagens por minuto"
          sub="Última hora, lida da fila do webhook. O detalhe por WhatsApp continua na lista acima."
          categorias={graficos?.mensagens_min?.rotulos}
          series={[
            { nome: 'Recebidas', dados: graficos?.mensagens_min?.recebidas || [], area: true },
            { nome: 'Enviadas', dados: graficos?.mensagens_min?.enviadas || [] },
          ]}
          vazio={graficos?.mensagens_min?.motivo || graficos?.motivo || 'sem dado'}
        />
        <LiveChart
          titulo="Envio do robô contra o teto"
          sub={`A linha vermelha é o teto de ${graficos?.envio?.teto || graficos?.cap_envio_min || 240} mensagens por minuto.`}
          categorias={graficos?.envio?.rotulos || []}
          series={[{ nome: 'Enviadas / min', dados: graficos?.envio?.serie || [], area: true }]}
          marca={graficos?.envio?.teto || 240}
          marcaNome="teto 240/min"
          vazio={graficos?.envio?.motivo || 'sem dado'}
        />
        <LiveChart
          titulo="Clientes ativos por painel"
          sub={graficos?.ativos?.fonte || 'P3 está desligado. P1, P2, P4, P5 e P6 entram na conta. O número oficial mora na aba Ativos reais do painel da raiz.'}
          tipo="bar"
          categorias={(graficos?.ativos?.paineis || []).map((p) => p.id)}
          series={[{ nome: 'Ativos', dados: (graficos?.ativos?.paineis || []).map((p) => p.n) }]}
          vazio="sem dado — o v2 não consulta o Sigma. Abra Ativos reais no painel da raiz."
          className="lg:col-span-2"
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <StateBlock title="Entrada ao vivo" envelope={entrada}>
            <MetricTooltip metricId="inicio.entrada_viva">Últimos 5 min</MetricTooltip>
            {Array.isArray(entrada.value) && entrada.value.length > 0 && (
              <ul className="mt-3 max-h-72 space-y-2 overflow-auto">
                {entrada.value.map((row, idx) => (
                  <li
                    key={idx}
                    className="anim-rise border-b border-[var(--color-line)]/50 pb-2 text-xs"
                    style={{ animationDelay: `${idx * 30}ms` }}
                  >
                    <div className="flex items-center justify-between gap-2 font-mono text-[10px] text-[var(--color-mist)]">
                      <span>{row.phone_final || 'final —'}</span>
                      <span>{row.instance || ''}</span>
                    </div>
                    <div className="text-[var(--color-paper)]">
                      {row.name ? `${row.name} · ` : ''}
                      {row.text || '(sem texto)'}
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <button
              type="button"
              className="mt-3 text-xs text-[var(--color-accent)] underline-offset-2 hover:underline"
              onClick={() => setDrill('inicio.entrada_viva')}
            >
              Abrir drill-down
            </button>
          </StateBlock>
        </div>

        <div className="lg:col-span-1">
          <div className="rounded-2xl border border-[var(--color-line)] bg-[var(--color-panel)] p-4 shadow-[var(--shadow)]">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-medium">
                <MetricTooltip metricId="inicio.log_operacional">Log operacional</MetricTooltip>
              </h3>
              <span className="text-[10px] uppercase tracking-wide text-[var(--color-accent)]">SSE</span>
            </div>
            <LiveLog
              initial={
                Array.isArray(data.log_operacional.value) ? data.log_operacional.value : null
              }
            />
          </div>
        </div>

        <div className="lg:col-span-1 space-y-3">
          <StateBlock title="Saúde do espelho" envelope={data.saude_espelho}>
            <MetricTooltip metricId="inicio.saude_espelho">Lag / cobertura</MetricTooltip>
            {data.saude_espelho.value && (
              <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <div>
                  <dt className="text-[var(--color-mist)]">Lag</dt>
                  <dd className="font-mono text-[var(--color-paper)]">
                    {String((data.saude_espelho.value as { lag_s?: number }).lag_s ?? '—')}s
                  </dd>
                </div>
                <div>
                  <dt className="text-[var(--color-mist)]">Cobertura</dt>
                  <dd className="font-mono text-[var(--color-paper)]">
                    {(() => {
                      const c = (data.saude_espelho.value as { cobertura?: number }).cobertura
                      return c == null ? '—' : `${Math.round(Number(c) * 100)}%`
                    })()}
                  </dd>
                </div>
              </dl>
            )}
            <button
              type="button"
              className="mt-3 text-xs text-[var(--color-accent)] underline-offset-2 hover:underline"
              onClick={() => setDrill('inicio.saude_espelho')}
            >
              Detalhe / drill-down
            </button>
          </StateBlock>

          {espera && espera.lista?.length > 0 && (
            <div className="rounded-2xl border border-[color-mix(in_oklab,var(--color-accent-2)_35%,transparent)] bg-[var(--color-panel)] p-4 shadow-[var(--shadow)]">
              <h3 className="mb-2 text-sm font-medium text-[var(--color-accent-2)]">
                Esperando agora ({espera.n})
              </h3>
              <ul className="max-h-40 space-y-1 overflow-auto text-xs">
                {espera.lista.slice(0, 8).map((row) => (
                  <li key={row.conversation_id} className="flex justify-between gap-2 font-mono">
                    <span>{row.phone_final}</span>
                    <span className="text-[var(--color-mist)]">{row.espera_min} min</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
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
