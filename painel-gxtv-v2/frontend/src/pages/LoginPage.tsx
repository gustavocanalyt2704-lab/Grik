import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'

export function LoginPage() {
  const nav = useNavigate()
  const [username, setUsername] = useState('gustavo')
  const [password, setPassword] = useState('')
  const [erro, setErro] = useState('')
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setErro('')
    try {
      const r = await api.login(username, password)
      if (!r.ok) {
        setErro(r.motivo || 'Falha no login')
        return
      }
      nav('/v2/')
    } catch {
      setErro('Não foi possível conectar ao servidor')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <form
        onSubmit={onSubmit}
        className="anim-rise w-full max-w-md rounded-3xl border border-[var(--color-line)] bg-white p-6 shadow-[0_20px_50px_rgba(28,25,23,0.08)] sm:p-8"
      >
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--color-accent)]">
          MN Tecnologia
        </p>
        <h1 className="font-display mt-2 text-4xl font-semibold text-[var(--color-ink)]">Entrar</h1>
        <p className="mt-2 text-sm leading-relaxed text-[var(--color-mist)]">
          Mesma senha do painel atual, neste login. O painel antigo continua no ar.
        </p>
        <label className="mt-6 mb-3 block text-xs font-medium uppercase tracking-wide text-[var(--color-mist)]">
          Usuário
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="mt-1 w-full rounded-xl border border-[var(--color-line)] bg-[var(--color-panel-2)] px-3 py-3 text-base text-[var(--color-paper)] outline-none focus:border-[var(--color-accent)]"
            autoComplete="username"
          />
        </label>
        <label className="mb-4 block text-xs font-medium uppercase tracking-wide text-[var(--color-mist)]">
          Senha
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-xl border border-[var(--color-line)] bg-[var(--color-panel-2)] px-3 py-3 text-base text-[var(--color-paper)] outline-none focus:border-[var(--color-accent)]"
            autoComplete="current-password"
          />
        </label>
        {erro && <p className="mb-3 text-sm text-[var(--color-danger)]">{erro}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-xl bg-[var(--color-accent)] px-4 py-3 text-sm font-semibold text-[var(--color-on-accent)] transition hover:brightness-110 disabled:opacity-60"
        >
          {loading ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
    </div>
  )
}
