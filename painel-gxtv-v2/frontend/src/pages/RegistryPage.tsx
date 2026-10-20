import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useFilters } from '@/lib/filters'
import { useState } from 'react'

export function RegistryPage() {
  const { filters } = useFilters()
  const [module, setModule] = useState('')
  const q = useQuery({ queryKey: ['registry'], queryFn: api.registry })

  if (q.isLoading) return <p className="text-[var(--color-mist)]">Carregando registro…</p>
  if (q.isError) return <p className="text-[var(--color-danger)]">Erro ao carregar registro</p>

  const metrics = (q.data?.metrics || []).filter((m) => !module || m.module === module)
  const modules = Array.from(new Set((q.data?.metrics || []).map((m) => m.module)))

  async function openDrill(metricId: string) {
    const r = await api.drilldown({ metric_id: metricId, filters, page: 1 })
    alert(
      `Drill-down ${metricId}\n` +
        `estado: ${(r.state as { state?: string })?.state || '—'}\n` +
        `${(r.state as { message?: string })?.message || 'Fase do módulo ainda não entrega linhas'}`,
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-display text-3xl font-semibold text-[var(--color-ink)]">Registro de métricas</h2>
        <p className="text-sm text-[var(--color-mist)]">
          Fonte de verdade · {q.data?.count} métricas · TZ {q.data?.timezone}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setModule('')}
          className={`rounded border px-2 py-1 text-xs ${!module ? 'border-[var(--color-accent)] text-[var(--color-accent)]' : 'border-[var(--color-line)] text-[var(--color-mist)]'}`}
        >
          Todos
        </button>
        {modules.map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setModule(m)}
            className={`rounded border px-2 py-1 text-xs ${module === m ? 'border-[var(--color-accent)] text-[var(--color-accent)]' : 'border-[var(--color-line)] text-[var(--color-mist)]'}`}
          >
            {m}
          </button>
        ))}
      </div>
      <div className="overflow-x-auto rounded-md border border-[var(--color-line)]">
        <table className="w-full min-w-[900px] border-collapse text-left text-sm">
          <thead className="bg-[var(--color-panel)] text-[11px] uppercase tracking-wide text-[var(--color-mist)]">
            <tr>
              <th className="px-3 py-2">ID</th>
              <th className="px-3 py-2">Nome</th>
              <th className="px-3 py-2">Fonte</th>
              <th className="px-3 py-2">Fórmula</th>
              <th className="px-3 py-2">Janela</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {metrics.map((m) => (
              <tr key={m.id} className="border-t border-[var(--color-line)] align-top hover:bg-[var(--color-panel)]/40">
                <td className="px-3 py-2 font-mono text-xs text-[var(--color-accent)]">{m.id}</td>
                <td className="px-3 py-2">
                  <div className="font-medium">{m.name}</div>
                  <div className="text-xs text-[var(--color-mist)]">{m.definition}</div>
                </td>
                <td className="px-3 py-2 text-xs text-[var(--color-mist)]">{m.source}</td>
                <td className="px-3 py-2 font-mono text-[11px] text-[var(--color-mist)]">{m.formula}</td>
                <td className="px-3 py-2 font-mono text-xs">{m.default_window}</td>
                <td className="px-3 py-2">
                  <button
                    type="button"
                    onClick={() => openDrill(m.id)}
                    className="rounded border border-[var(--color-line)] px-2 py-1 text-xs hover:border-[var(--color-accent)]"
                  >
                    Drill-down
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
