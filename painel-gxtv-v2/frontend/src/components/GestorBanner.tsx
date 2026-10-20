import { TriangleAlert } from 'lucide-react'

export function GestorBanner({ aviso }: { aviso?: string | null }) {
  if (!aviso) return null
  return (
    <div
      role="status"
      className="flex gap-3 rounded-2xl border border-[color-mix(in_oklab,var(--color-stale)_35%,transparent)] bg-[color-mix(in_oklab,var(--color-stale)_10%,var(--color-panel))] px-4 py-3 text-sm text-[var(--color-ink)]"
    >
      <TriangleAlert size={18} className="mt-0.5 shrink-0 text-[var(--color-stale)]" />
      <div>
        <p className="font-semibold">Gestor</p>
        <p className="mt-1 leading-relaxed text-[var(--color-ink-soft)]">{aviso}</p>
      </div>
    </div>
  )
}
