export function Sparkline({
  dados,
  cor = 'var(--chart-1)',
}: {
  dados?: Array<number | null> | null
  cor?: string
}) {
  const nums = (dados || []).filter((v): v is number => v != null && !Number.isNaN(Number(v)))
  if (nums.length < 2) {
    return <span className="inline-block h-7 w-[88px]" aria-hidden="true" />
  }
  const w = 88
  const h = 28
  const min = Math.min(...nums)
  const max = Math.max(...nums)
  const span = max - min || 1
  const pts = nums.map((v, i) => {
    const x = (i / (nums.length - 1)) * w
    const y = h - 2 - ((v - min) / span) * (h - 4)
    return [x, y] as const
  })
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ')
  const fill = `${d} L${w} ${h} L0 ${h} Z`
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true" className="overflow-visible">
      <path d={fill} fill={cor} opacity="0.16" />
      <path d={d} fill="none" stroke={cor} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}
