import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { GlobalFiltersBar } from './GlobalFilters'
import { api } from '@/lib/api'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'

const NAV = [
  { to: '/v2/', end: true, label: 'Início', short: 'Início' },
  { to: '/v2/atendimento', label: 'Atendimento', short: 'Atend.' },
  { to: '/v2/sem-resposta', label: 'Sem resposta', short: 'Sem resp.' },
  { to: '/v2/comercial', label: 'Comercial', short: 'Vendas' },
  { to: '/v2/operacao', label: 'Operação', short: 'Oper.' },
  { to: '/v2/robo', label: 'Robô', short: 'Robô' },
  { to: '/v2/espelho', label: 'Espelho', short: 'Espelho' },
  { to: '/v2/registro', label: 'Registro', short: 'Registro' },
]

const MOBILE = NAV.slice(0, 4)
const MORE = NAV.slice(4)

function Item({ to, end, label, onClick }: { to: string; end?: boolean; label: string; onClick?: () => void }) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onClick}
      className={({ isActive }) =>
        clsx(
          'block rounded-xl px-3 py-2 text-sm transition-colors',
          isActive
            ? 'bg-[var(--color-accent)] text-[var(--color-on-accent)]'
            : 'text-[var(--color-ink-soft)] hover:bg-[var(--color-panel-2)]',
        )
      }
    >
      {label}
    </NavLink>
  )
}

export function Layout() {
  const qc = useQueryClient()
  const me = useQuery({ queryKey: ['me'], queryFn: api.me })
  const [mais, setMais] = useState(false)
  const logout = useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      qc.clear()
      window.location.href = '/v2/login'
    },
  })

  return (
    <div className="min-h-screen md:grid md:grid-cols-[232px_minmax(0,1fr)]">
      <aside className="hidden border-r border-[var(--color-line)] bg-white md:flex md:flex-col md:px-4 md:py-6">
        <div className="px-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--color-accent)]">
            MN Tecnologia
          </p>
          <p className="font-display mt-1 text-2xl leading-none text-[var(--color-ink)]">Operação</p>
        </div>
        <nav className="mt-8 flex flex-1 flex-col gap-1">
          {NAV.map((item) => (
            <Item key={item.to} to={item.to} end={item.end} label={item.label} />
          ))}
        </nav>
        <div className="mt-4 border-t border-[var(--color-line)] pt-4 text-sm">
          <p className="px-2 text-[var(--color-mist)]">{me.data?.user.username || '…'}</p>
          <button
            type="button"
            onClick={() => logout.mutate()}
            className="mt-2 w-full rounded-xl border border-[var(--color-line)] px-3 py-2 text-left text-[var(--color-ink)] hover:border-[var(--color-accent)]"
          >
            Sair
          </button>
        </div>
      </aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-[var(--color-line)] bg-[#f7f4ee]/95 px-4 py-3 backdrop-blur md:px-6">
          <div className="md:hidden">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-accent)]">
              MN Tecnologia
            </p>
            <p className="font-display text-xl leading-none">Operação</p>
          </div>
          <p className="hidden text-sm text-[var(--color-mist)] md:block">Painel da operação · America/Bahia</p>
          <div className="flex items-center gap-2 text-sm">
            <span className="hidden text-[var(--color-mist)] sm:inline">{me.data?.user.username || '…'}</span>
            <button
              type="button"
              onClick={() => logout.mutate()}
              className="rounded-full border border-[var(--color-line)] bg-white px-3 py-1.5 md:hidden"
            >
              Sair
            </button>
          </div>
        </header>

        <div className="px-4 pt-4 md:px-6">
          <GlobalFiltersBar />
        </div>

        <main className="pb-nav px-4 pt-4 md:px-6">
          <Outlet />
        </main>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-[var(--color-line)] bg-white/95 backdrop-blur md:hidden">
        <div className="grid grid-cols-5 px-1 pt-1" style={{ paddingBottom: 'max(0.35rem, env(safe-area-inset-bottom))' }}>
          {MOBILE.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setMais(false)}
              className={({ isActive }) =>
                clsx(
                  'rounded-lg px-1 py-2 text-center text-[11px] font-medium',
                  isActive ? 'text-[var(--color-accent)]' : 'text-[var(--color-mist)]',
                )
              }
            >
              {item.short}
            </NavLink>
          ))}
          <button
            type="button"
            onClick={() => setMais((v) => !v)}
            className={clsx(
              'rounded-lg px-1 py-2 text-center text-[11px] font-medium',
              mais ? 'text-[var(--color-accent)]' : 'text-[var(--color-mist)]',
            )}
          >
            Mais
          </button>
        </div>
        {mais && (
          <div className="border-t border-[var(--color-line)] bg-white px-3 py-2">
            {MORE.map((item) => (
              <Item key={item.to} to={item.to} label={item.label} onClick={() => setMais(false)} />
            ))}
          </div>
        )}
      </nav>
    </div>
  )
}
