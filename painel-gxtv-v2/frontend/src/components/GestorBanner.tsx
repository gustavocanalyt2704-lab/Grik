export function GestorBanner({ aviso }: { aviso?: string | null }) {
  if (!aviso) return null
  return (
    <div
      role="status"
      className="rounded-2xl border border-[#f3d19c] bg-[#fff8eb] px-4 py-3 text-sm text-[#7c2d12]"
    >
      <p className="font-semibold">Gestor</p>
      <p className="mt-1 leading-relaxed">{aviso}</p>
    </div>
  )
}
