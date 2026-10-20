import ReactECharts from 'echarts-for-react'

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

const CORES = ['#0c6b58', '#0e7490', '#9a3412', '#b45309']

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
  const tem = series.some((s) => s.dados.some((v) => v != null && !Number.isNaN(Number(v))))
  return (
    <section className={`rounded-2xl border border-[var(--color-line)] bg-white p-4 ${className}`}>
      <h3 className="text-sm font-semibold text-[var(--color-ink)]">{titulo}</h3>
      {sub && <p className="mt-1 text-xs leading-relaxed text-[var(--color-mist)]">{sub}</p>}
      {!tem ? (
        <p className="mt-4 text-sm text-[var(--color-mist)]">{vazio || 'sem dado'}</p>
      ) : (
        <ReactECharts
          style={{ height: altura, width: '100%' }}
          opts={{ renderer: 'svg' }}
          option={{
            animationDuration: 400,
            grid: { left: 44, right: 12, top: 28, bottom: 28 },
            tooltip: { trigger: 'axis' },
            legend: { top: 0, textStyle: { color: '#6d675f', fontSize: 11 } },
            xAxis: {
              type: 'category',
              data: categorias,
              axisLabel: { color: '#6d675f', fontSize: 10, hideOverlap: true },
              axisLine: { lineStyle: { color: '#e4dfd4' } },
            },
            yAxis: {
              type: 'value',
              axisLabel: { color: '#6d675f', fontSize: 10 },
              splitLine: { lineStyle: { color: '#efeae2' } },
            },
            series: series.map((s, i) => ({
              name: s.nome,
              type: tipo,
              data: s.dados,
              smooth: tipo === 'line',
              showSymbol: false,
              itemStyle: { color: s.cor || CORES[i % CORES.length] },
              lineStyle: { width: 2, color: s.cor || CORES[i % CORES.length] },
              areaStyle: s.area ? { opacity: 0.15 } : undefined,
              markLine:
                marca == null
                  ? undefined
                  : {
                      symbol: 'none',
                      label: { formatter: marcaNome || `teto ${marca}`, color: '#b42318' },
                      lineStyle: { color: '#b42318', type: 'dashed' },
                      data: [{ yAxis: marca }],
                    },
            })),
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
