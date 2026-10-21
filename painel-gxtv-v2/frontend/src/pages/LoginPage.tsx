import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { Lock } from 'lucide-react'

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
        className="anim-rise w-full max-w-md rounded-3xl border border-[var(--color-line)] bg-[var(--color-panel)] p-6 shadow-[var(--shadow)] sm:p-8"
      >
        <div className="grid h-11 w-11 place-items-center rounded-2xl bg-[var(--color-accent)] text-sm font-semibold text-[var(--color-on-accent)]">
          MN
        </div>
        <p className="mt-5 text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-mist)]">
          MN Tecnologia
        </p>
        <h1 className="font-display mt-1 text-3xl font-semibold text-[var(--color-ink)]">Entrar</h1>
        <p className="mt-2 text-sm leading-relaxed text-[var(--color-mist)]">
          Mesma senha do painel da raiz. O painel antigo continua no ar.
        </p>
        <label className="mt-6 mb-3 block text-[12px] font-medium text-[var(--color-mist)]">
          Usuário
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="mt-1 w-full rounded-xl border border-[var(--color-line)] bg-[var(--color-panel-2)] px-3 py-3 text-base text-[var(--color-paper)] outline-none focus:border-[var(--color-accent)]"
            autoComplete="username"
          />
        </label>
        <label className="mb-4 block text-[12px] font-medium text-[var(--color-mist)]">
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
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--color-accent)] px-4 py-3 text-sm font-semibold text-[var(--color-on-accent)] transition hover:brightness-110 disabled:opacity-60"
        >
          <Lock size={16} />
          {loading ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
    </div>
  )
}
