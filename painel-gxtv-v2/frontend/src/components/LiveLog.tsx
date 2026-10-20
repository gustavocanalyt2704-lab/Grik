import { useEffect, useRef, useState } from 'react'
import { logStreamUrl } from '@/lib/api'
import { StateBadge } from '@/components/StateBlock'

type LogLine = { t?: string | null; line: string; heartbeat?: boolean }

export function LiveLog({ initial }: { initial?: { t?: string | null; line: string }[] | null }) {
  const [lines, setLines] = useState<LogLine[]>(initial || [])
  const [status, setStatus] = useState<'connecting' | 'live' | 'unavailable' | 'error'>('connecting')
  const [message, setMessage] = useState<string | null>(null)
  const boxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (initial?.length) setLines(initial)
  }, [initial])

  useEffect(() => {
    let es: EventSource | null = null
    let closed = false
    try {
      es = new EventSource(logStreamUrl(), { withCredentials: true })
    } catch {
      setStatus('error')
      setMessage('SSE não disponível neste browser')
      return
    }

    es.onopen = () => {
      if (!closed) setStatus('live')
    }
    es.onerror = () => {
      if (!closed) {
        setStatus('error')
        setMessage('Conexão SSE interrompida — tentando reconectar…')
      }
    }
    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as {
          state?: string
          line?: string
          t?: string
          heartbeat?: boolean
          message?: string
        }
        if (data.state === 'unavailable') {
          setStatus('unavailable')
          setMessage(data.message || 'Log indisponível')
          return
        }
        if (data.state === 'error') {
          setStatus('error')
          setMessage(data.message || 'Erro no stream')
          return
        }
        setStatus('live')
        if (data.heartbeat || !data.line) return
        setLines((prev) => {
          const next = [...prev, { t: data.t, line: data.line! }]
          return next.slice(-120)
        })
      } catch {
        /* ignore malformed */
      }
    }

    return () => {
      closed = true
      es?.close()
    }
  }, [])

  useEffect(() => {
    const el = boxRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [lines])

  return (
    <div className="flex h-full flex-col">
      <div className="mb-2 flex items-center justify-between gap-2">
        <StateBadge state={status === 'live' ? 'ok' : status === 'connecting' ? 'loading' : status} />
        {message && <span className="text-[11px] text-[var(--color-mist)]">{message}</span>}
      </div>
      <div
        ref={boxRef}
        className="max-h-72 flex-1 overflow-auto rounded border border-[var(--color-line)] bg-[var(--color-ink)]/40 p-2 font-mono text-[10px] leading-relaxed text-[var(--color-mist)]"
      >
        {lines.length === 0 && (
          <div className="text-[var(--color-empty)]">Aguardando eventos do live.log…</div>
        )}
        {lines.map((row, idx) => (
          <div key={idx} className="anim-rise truncate border-b border-[var(--color-line)]/40 py-0.5">
            {row.line}
          </div>
        ))}
      </div>
    </div>
  )
}
