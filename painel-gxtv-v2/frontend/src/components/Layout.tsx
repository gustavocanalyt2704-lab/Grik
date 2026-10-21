import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { GlobalFiltersBar } from './GlobalFilters'
import { api } from '@/lib/api'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import {
  Activity,
  Bot,
  LayoutDashboard,
  LogOut,
  MessagesSquare,
  Moon,
  MoreHorizontal,
  Radio,
  ScrollText,
  Sun,
  TriangleAlert,
  Wallet,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

const NAV: { to: string; end?: boolean; label: string; short: string; icon: LucideIcon }[] = [
  { to: '/v2/', end: true, label: 'Início', short: 'Início', icon: LayoutDashboard },
  { to: '/v2/atendimento', label: 'Atendimento', short: 'Atend.', icon: MessagesSquare },
  { to: '/v2/sem-resposta', label: 'Sem resposta', short: 'Sem resp.', icon: TriangleAlert },
  { to: '/v2/comercial', label: 'Comercial', short: 'Vendas', icon: Wallet },
  { to: '/v2/operacao', label: 'Operação', short: 'Oper.', icon: Activity },
  { to: '/v2/robo', label: 'Robô', short: 'Robô', icon: Bot },
  { to: '/v2/espelho', label: 'Espelho', short: 'Espelho', icon: Radio },
  { to: '/v2/registro', label: 'Registro', short: 'Registro', icon: ScrollText },
]

const MOBILE = NAV.slice(0, 4)
const MORE = NAV.slice(4)

function aplicarTema(tema: 'escuro' | 'claro') {
  document.documentElement.dataset.tema = tema
  try { localStorage.setItem('gx_tema', tema) } catch { /* */ }
}

function Item({
  to,
  end,
  label,
  icon: Icon,
  onClick,
}: {
  to: string
  end?: boolean
  label: string
  icon: LucideIcon
  onClick?: () => void
}) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onClick}
      className={({ isActive }) =>
        clsx(
          'flex items-center gap-2.5 rounded-xl px-3 py-2 text-[13px] font-medium transition-colors',
          isActive
            ? 'bg-[color-mix(in_oklab,var(--color-accent)_18%,transparent)] text-[var(--color-ink)]'
            : 'text-[var(--color-mist)] hover:bg-[var(--color-panel-2)] hover:text-[var(--color-ink)]',
        )
      }
    >
      {({ isActive }) => (
        <>
          <Icon size={16} strokeWidth={1.75} className={isActive ? 'text-[var(--color-accent)]' : ''} />
          {label}
        </>
      )}
    </NavLink>
  )
}

export function Layout() {
  const qc = useQueryClient()
  const me = useQuery({ queryKey: ['me'], queryFn: api.me })
  const [mais, setMais] = useState(false)
  const [tema, setTema] = useState<'escuro' | 'claro'>(() =>
    document.documentElement.dataset.tema === 'claro' ? 'claro' : 'escuro',
  )
  useEffect(() => { aplicarTema(tema) }, [tema])
  const logout = useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      qc.clear()
      window.location.href = '/v2/login'
    },
  })

  return (
    <div className="min-h-screen md:grid md:grid-cols-[240px_minmax(0,1fr)]">
      <aside className="sticky top-0 hidden h-screen flex-col border-r border-[var(--color-line)] bg-[color-mix(in_oklab,var(--color-bg)_88%,black)] px-3 py-5 md:flex">
        <div className="flex items-center gap-2.5 px-2">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-[var(--color-accent)] text-sm font-semibold text-[var(--color-on-accent)]">
            MN
          </div>
          <div>
            <p className="text-[13px] font-semibold tracking-tight text-[var(--color-ink)]">MN Tecnologia</p>
            <p className="text-[11px] text-[var(--color-mist)]">Operação · Bahia</p>
          </div>
        </div>
        <nav className="mt-6 flex flex-1 flex-col gap-0.5">
          {NAV.map((item) => (
            <Item key={item.to} {...item} />
          ))}
        </nav>
        <div className="mt-4 border-t border-[var(--color-line)] pt-3">
          <button
            type="button"
            onClick={() => setTema((t) => (t === 'escuro' ? 'claro' : 'escuro'))}
            className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-[13px] text-[var(--color-mist)] hover:bg-[var(--color-panel-2)] hover:text-[var(--color-ink)]"
          >
            {tema === 'escuro' ? <Sun size={16} /> : <Moon size={16} />}
            {tema === 'escuro' ? 'Tema claro' : 'Tema escuro'}
          </button>
          <p className="mt-2 px-3 text-[12px] text-[var(--color-mist)]">{me.data?.user.username || '…'}</p>
          <button
            type="button"
            onClick={() => logout.mutate()}
            className="mt-1 flex w-full items-center gap-2 rounded-xl px-3 py-2 text-[13px] text-[var(--color-mist)] hover:bg-[var(--color-panel-2)] hover:text-[var(--color-ink)]"
          >
            <LogOut size={16} /> Sair
          </button>
        </div>
      </aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-[var(--color-line)] bg-[color-mix(in_oklab,var(--color-bg)_82%,transparent)] px-4 py-3 backdrop-blur-xl md:px-6">
          <div className="flex items-center gap-2 md:hidden">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-[var(--color-accent)] text-xs font-semibold text-[var(--color-on-accent)]">MN</div>
            <p className="text-sm font-semibold tracking-tight">Operação</p>
          </div>
          <p className="hidden items-center gap-2 text-[13px] text-[var(--color-mist)] md:flex">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[color-mix(in_oklab,var(--color-ok)_16%,transparent)] px-2 py-0.5 text-[11px] font-semibold text-[var(--color-ok)]">
              <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-ok)]" />
              ao vivo
            </span>
            America/Bahia
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setTema((t) => (t === 'escuro' ? 'claro' : 'escuro'))}
              className="grid h-9 w-9 place-items-center rounded-full border border-[var(--color-line)] bg-[var(--color-panel)] text-[var(--color-ink)] md:hidden"
              aria-label="Trocar tema"
            >
              {tema === 'escuro' ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <span className="hidden text-[13px] text-[var(--color-mist)] sm:inline">{me.data?.user.username || '…'}</span>
          </div>
        </header>

        <div className="px-4 pt-4 md:px-6">
          <GlobalFiltersBar />
        </div>

        <main className="pb-nav px-4 pt-4 md:px-6">
          <Outlet />
        </main>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-[var(--color-line)] bg-[color-mix(in_oklab,var(--color-bg)_92%,transparent)] backdrop-blur-xl md:hidden">
        <div className="grid grid-cols-5" style={{ paddingBottom: 'max(0.35rem, env(safe-area-inset-bottom))' }}>
          {MOBILE.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setMais(false)}
              className={({ isActive }) =>
                clsx(
                  'flex flex-col items-center gap-0.5 px-1 py-2 text-[10px] font-medium',
                  isActive ? 'text-[var(--color-accent)]' : 'text-[var(--color-mist)]',
                )
              }
            >
              <item.icon size={18} strokeWidth={1.75} />
              {item.short}
            </NavLink>
          ))}
          <button
            type="button"
            onClick={() => setMais((v) => !v)}
            className={clsx(
              'flex flex-col items-center gap-0.5 px-1 py-2 text-[10px] font-medium',
              mais ? 'text-[var(--color-accent)]' : 'text-[var(--color-mist)]',
            )}
          >
            <MoreHorizontal size={18} />
            Mais
          </button>
        </div>
        {mais && (
          <div className="border-t border-[var(--color-line)] bg-[var(--color-panel)] px-3 py-2">
            {MORE.map((item) => (
              <Item key={item.to} {...item} onClick={() => setMais(false)} />
            ))}
            <button
              type="button"
              onClick={() => logout.mutate()}
              className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-[13px] text-[var(--color-mist)]"
            >
              <LogOut size={16} /> Sair
            </button>
          </div>
        )}
      </nav>
    </div>
  )
}
