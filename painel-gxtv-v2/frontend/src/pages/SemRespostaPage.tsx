import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { StateBlock } from '@/components/StateBlock'
import { LiveChart } from '@/components/LiveChart'

type Item = {
  sufixo: string
  instancia: string
  espera_min: number
  motivo: string
  reprocessar: boolean
  numero_teste: boolean
  prova: string
}

type Payload = {
  ok: boolean
  gerado_em?: string | null
  total: number
  causas: Record<string, number>
  itens: Item[]
  message?: string
}

export function SemRespostaPage() {
  const q = useQuery({
    queryKey: ['sem-resposta'],
    queryFn: api.semResposta,
    refetchInterval: 60_000,
  })

  if (q.isLoading) {
    return (
      <StateBlock
        title="Sem resposta"
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
          message: 'Falha ao carregar os casos sem resposta',
          timezone: 'America/Bahia',
          computed_at: '',
        }}
      />
    )
  }

  const data = q.data as Payload
  const causas = Object.entries(data.causas || {})

  return (
    <div className="space-y-6">
      <section>
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--color-accent)]">
          Atendimento
        </div>
        <h2 className="font-display text-3xl font-semibold text-[var(--color-ink)]">Sem resposta</h2>
        <p className="mt-1 max-w-2xl text-sm text-[var(--color-mist)]">
          Cliente falou e o robô não respondeu há mais de 3 minutos. Coleta local, a cada 10 minutos.
          {data.gerado_em ? ` Atualizado ${data.gerado_em}.` : ''}
        </p>
      </section>

      {data.total > 0 && (
        <LiveChart
          titulo="Por que ficou sem resposta"
          sub="Cada barra é um motivo. A lista embaixo é a pessoa, só com o final do telefone."
          tipo="bar"
          categorias={causas.map(([motivo]) => motivo)}
          series={[{ nome: 'Clientes', dados: causas.map(([, n]) => n) }]}
        />
      )}

      {data.total === 0 ? (
        <StateBlock
          envelope={{
            state: 'empty',
            value: null,
            message: data.message || 'Nenhum cliente esperando resposta agora.',
            timezone: 'America/Bahia',
            computed_at: data.gerado_em || '',
          }}
        />
      ) : (
        <>
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {causas.map(([motivo, n]) => (
              <article
                key={motivo}
                className="rounded-2xl border border-[var(--color-line)] bg-[var(--color-panel)] px-4 py-3"
              >
                <p className="text-[11px] uppercase tracking-wide text-[var(--color-mist)]">{motivo}</p>
                <p className="font-display text-3xl text-[var(--color-ink)]">{n}</p>
              </article>
            ))}
          </section>
          <div className="overflow-x-auto rounded-2xl border border-[var(--color-line)] bg-[var(--color-panel)]">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-[var(--color-line)] text-[var(--color-mist)]">
                <tr>
                  <th className="px-3 py-2 font-medium">Final</th>
                  <th className="px-3 py-2 font-medium">Número</th>
                  <th className="px-3 py-2 font-medium">Espera</th>
                  <th className="px-3 py-2 font-medium">Motivo</th>
                  <th className="px-3 py-2 font-medium">Prova</th>
                </tr>
              </thead>
              <tbody>
                {data.itens.map((item, i) => (
                  <tr key={`${item.sufixo}-${i}`} className="border-b border-[var(--color-line)] align-top">
                    <td className="px-3 py-2 font-medium">*{item.sufixo}</td>
                    <td className="px-3 py-2">{item.instancia || '—'}</td>
                    <td className="px-3 py-2">{item.espera_min} min</td>
                    <td className="px-3 py-2">
                      {item.motivo}
                      {item.numero_teste ? ' · teste, sem Sigma' : ''}
                      {item.reprocessar ? '' : ' · sem reprocesso'}
                    </td>
                    <td className="max-w-md px-3 py-2 text-[var(--color-mist)]">{item.prova}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
