import { useEffect, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import * as echarts from 'echarts'

type Serie = {
  nome: string
  dados: Array<number | null>
  cor?: string
  area?: boolean
}

type Props = {
  titulo: string
  sub?: string
  categorias?: string[]
  series?: Serie[]
  marca?: number | null
  marcaNome?: string
  vazio?: string | null
  altura?: number
  tipo?: 'line' | 'bar'
  className?: string
}

const CHAVES = ['--chart-1', '--chart-2', '--chart-3', '--chart-4', '--chart-5']

function useTema() {
  const [tema, setTema] = useState(() => document.documentElement.dataset.tema || 'escuro')
  useEffect(() => {
    const obs = new MutationObserver(() => setTema(document.documentElement.dataset.tema || 'escuro'))
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-tema'] })
    return () => obs.disconnect()
  }, [])
  return tema
}

function token(nome: string, fallback: string) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(nome).trim()
  return v || fallback
}

export function LiveChart({
  titulo,
  sub,
  categorias = [],
  series = [],
  marca = null,
  marcaNome,
  vazio,
  altura = 240,
  tipo = 'line',
  className = '',
}: Props) {
  const tema = useTema()
  const tem = series.some((s) => s.dados.some((v) => v != null && !Number.isNaN(Number(v))))
  const mist = token('--color-mist', '#a1a1aa')
  const line = token('--color-line', 'rgba(255,255,255,.08)')
  const ink = token('--color-paper', '#fafafa')
  const panel = token('--color-panel', '#141418')
  const cap = token('--chart-5', '#fb7185')

  return (
    <section className={`rounded-2xl border border-[var(--color-line)] bg-[var(--color-panel)] p-4 shadow-[var(--shadow)] ${className}`}>
      <h3 className="text-[13px] font-semibold tracking-tight text-[var(--color-ink)]">{titulo}</h3>
      {sub && <p className="mt-1 text-[12px] leading-relaxed text-[var(--color-mist)]">{sub}</p>}
      {!tem ? (
        <div className="mt-4 rounded-xl border border-dashed border-[var(--color-line)] px-4 py-8 text-center">
          <p className="text-sm font-medium text-[var(--color-ink-soft)]">Sem série nesta tela</p>
          <p className="mt-1 text-xs text-[var(--color-mist)]">{vazio || 'sem dado'}</p>
        </div>
      ) : (
        <ReactECharts
          key={tema}
          style={{ height: altura, width: '100%' }}
          opts={{ renderer: 'svg' }}
          option={{
            animationDuration: 700,
            animationDurationUpdate: 500,
            animationEasing: 'cubicOut',
            grid: { left: 46, right: 16, top: 36, bottom: 28 },
            tooltip: {
              trigger: 'axis',
              backgroundColor: panel,
              borderColor: line,
              textStyle: { color: ink, fontSize: 12, fontFamily: 'Inter Variable, Inter, sans-serif' },
              extraCssText: 'border-radius:12px;box-shadow:0 12px 32px rgba(0,0,0,.28);',
            },
            legend: { top: 0, icon: 'circle', itemWidth: 8, itemHeight: 8, textStyle: { color: mist, fontSize: 11 } },
            xAxis: {
              type: 'category',
              data: categorias,
              axisLabel: { color: mist, fontSize: 10, hideOverlap: true },
              axisLine: { lineStyle: { color: line } },
              axisTick: { show: false },
            },
            yAxis: {
              type: 'value',
              axisLabel: { color: mist, fontSize: 10 },
              splitLine: { lineStyle: { color: line } },
            },
            series: series.map((s, i) => {
              const cor =
                s.cor ||
                (/erro|alerta/i.test(s.nome)
                  ? token('--chart-5', '#fb7185')
                  : token(CHAVES[i % CHAVES.length], '#8b7cf6'))
              return {
                name: s.nome,
                type: tipo,
                data: s.dados,
                smooth: tipo === 'line',
                showSymbol: false,
                barMaxWidth: 18,
                itemStyle: { color: cor, borderRadius: tipo === 'bar' ? [6, 6, 0, 0] : 0 },
                lineStyle: { width: 2, color: cor },
                areaStyle: s.area
                  ? {
                      color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: cor },
                        { offset: 1, color: 'transparent' },
                      ]),
                      opacity: 0.22,
                    }
                  : undefined,
                markLine:
                  marca == null
                    ? undefined
                    : {
                        symbol: 'none',
                        label: { formatter: marcaNome || `teto ${marca}`, color: cap, fontSize: 10 },
                        lineStyle: { color: cap, type: 'dashed', width: 1.2 },
                        data: [{ yAxis: marca }],
                      },
              }
            }),
          }}
        />
      )}
    </section>
  )
}

export type Graficos = {
  ok?: boolean
  is_seed?: boolean
  sem_dado?: boolean
  motivo?: string
  cap_envio_min?: number
  mensagens_min?: {
    sem_dado?: boolean
    motivo?: string
    rotulos?: string[]
    recebidas?: number[]
    enviadas?: number[]
  }
  envio?: {
    sem_dado?: boolean
    motivo?: string
    agora?: number | null
    teto?: number
    serie?: number[] | null
    rotulos?: string[] | null
    fonte?: string
  }
  erros_min?: { sem_dado?: boolean; motivo?: string; rotulos?: string[]; n?: number[]; fonte?: string }
  vendas_hora?: { sem_dado?: boolean; motivo?: string; rotulos?: string[]; n?: number[] }
  ativos?: { paineis?: { id: string; n: number | null; nota?: string }[]; fonte?: string }
}
