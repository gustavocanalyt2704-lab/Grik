export type MetricState = 'loading' | 'ok' | 'empty' | 'error' | 'stale' | 'unavailable'

export type MetricEnvelope<T = unknown> = {
  state: MetricState
  value: T | null
  message?: string | null
  timezone: string
  window?: string | null
  source?: {
    id: string
    label: string
    last_update?: string | null
    cache_ttl_s?: number | null
  } | null
  metric_id?: string | null
  computed_at: string
  is_seed?: boolean
}

export type MetricDef = {
  id: string
  name: string
  definition: string
  source: string
  formula: string
  timezone: string
  default_window: string
  module: string
  drilldown?: string | null
  unit?: string | null
  notes?: string | null
  last_update?: string | null
}

export type GlobalFilters = {
  periodo: string
  numero?: string | null
  atendente?: string | null
  app?: string | null
  aparelho?: string | null
}

export type InicioKpis = {
  faturamento: MetricEnvelope<number | null>
  renovacoes: MetricEnvelope<number | null>
  vencem_hoje: MetricEnvelope<{
    total: number | null
    renovaram: number | null
    pendentes: number | null
  } | null>
  atendidos: MetricEnvelope<number | null>
  esperando_15min: MetricEnvelope<{
    n: number
    minutos: number
    lista: {
      conversation_id: string
      phone_final: string
      name?: string | null
      espera_min: number
      instance?: string | null
      ultima_fala?: string | null
    }[]
  } | null>
  clientes_min: MetricEnvelope<number | null>
}

export type CampoNumero = { rotulo: string; valor: number | null; detalhe?: string | null }

export type NumeroCard = {
  id: string
  grupo?: string
  conversas: CampoNumero
  finalizadas: CampoNumero
  abertas: CampoNumero
  tempo_resposta: CampoNumero
  pix_enviados: CampoNumero
  vendas_dia: CampoNumero
}

export type GrupoNumeros = {
  id: string
  titulo: string
  cards: NumeroCard[]
}

export type ResumoLateral = {
  pediram_assinatura: CampoNumero
  pagamentos: CampoNumero
  renovacoes: CampoNumero
}

export type VendaLinha = {
  telefone_final: string
  valor: number | null
  numero: string | null
  origem: string
}

export type NumerosPayload = {
  cards: NumeroCard[]
  grupos?: GrupoNumeros[]
  resumo?: ResumoLateral
  nota?: string | null
  aviso_gestor?: string | null
  vendas?: VendaLinha[]
  vendas_sem_lista?: boolean
}

export type InicioPayload = {
  ok: boolean
  phase: string
  timezone: string
  window: { inicio: string | null; fim: string | null; label: string }
  is_seed?: boolean
  kpis: InicioKpis
  entrada_viva: MetricEnvelope<
    {
      t?: string | null
      phone_final?: string
      name?: string | null
      text?: string | null
      instance?: string | null
      conversation_id?: string
      evento?: string
    }[]
  >
  log_operacional: MetricEnvelope<{ t?: string | null; line: string }[]>
  saude_espelho: MetricEnvelope<Record<string, unknown>>
  poll?: { ocupadas?: number; aguardando?: number; line?: string } | null
  numeros?: NumerosPayload
  computed_at?: string
}

export type AtendimentoPayload = {
  ok: boolean
  phase: string
  timezone: string
  window: { inicio: string | null; fim: string | null; label: string }
  is_seed?: boolean
  funil: MetricEnvelope<{
    stages: { id: string; label: string; n: number }[]
    total: number
  } | null>
  tempos: {
    media: MetricEnvelope<number | null>
    mediana: MetricEnvelope<number | null>
    p95: MetricEnvelope<number | null>
    max: MetricEnvelope<number | null>
    resumo: Record<string, unknown>
  }
  atual_vs_historico: {
    atual: Record<string, unknown> | null
    historico_7d: Record<string, unknown> | null
  }
  computed_at?: string
}

export type EspelhoPayload = {
  ok: boolean
  phase: string
  timezone: string
  is_seed?: boolean
  saude: MetricEnvelope<Record<string, unknown>>
  lag: MetricEnvelope<number | null>
  cobertura: MetricEnvelope<number | null>
  no_datacrazy?: boolean
}

export type DrilldownPayload = {
  ok: boolean
  metric?: MetricDef
  window?: string
  page: number
  page_size: number
  total: number
  rows: unknown[]
  state: MetricEnvelope
  filters?: GlobalFilters
  motivo?: string
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init?.headers || {}),
    },
    ...init,
  })
  if (r.status === 401) {
    const err = new Error('unauthorized') as Error & { status: number }
    err.status = 401
    throw err
  }
  return r.json() as Promise<T>
}

function qs(filters: GlobalFilters): string {
  const p = new URLSearchParams()
  p.set('periodo', filters.periodo || 'hoje')
  if (filters.numero) p.set('numero', filters.numero)
  if (filters.atendente) p.set('atendente', filters.atendente)
  if (filters.app) p.set('app', filters.app)
  if (filters.aparelho) p.set('aparelho', filters.aparelho)
  return p.toString()
}

export const api = {
  health: () => req<{ ok: boolean; phase: string; timezone: string; now: string }>('/api/v2/health'),
  login: (username: string, password: string) =>
    req<{ ok: boolean; motivo?: string; username?: string }>('/api/v2/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  logout: () => req<{ ok: boolean }>('/api/v2/auth/logout', { method: 'POST' }),
  me: () => req<{ ok: boolean; user: { username: string; via: string } }>('/api/v2/auth/me'),
  registry: () => req<{ ok: boolean; metrics: MetricDef[]; timezone: string; count: number }>('/api/v2/registry'),
  filterOptions: () =>
    req<{
      ok: boolean
      options: {
        periodos: { id: string; label: string }[]
        numeros: { id: string; label: string }[]
        atendentes: { id: string; label: string }[]
        apps: { id: string; label: string }[]
        aparelhos: { id: string; label: string }[]
      }
    }>('/api/v2/filters/options'),
  shell: () => req<Record<string, unknown>>('/api/v2/meta/shell'),
  states: () => req<{ ok: boolean; examples: Record<string, MetricEnvelope> }>('/api/v2/meta/states'),
  inicio: (filters: GlobalFilters) =>
    req<InicioPayload>(`/api/v2/inicio?${qs(filters)}`),
  espelho: () => req<EspelhoPayload>('/api/v2/espelho'),
  semResposta: () => req<{
    ok: boolean
    gerado_em?: string | null
    total: number
    causas: Record<string, number>
    itens: {
      sufixo: string
      instancia: string
      espera_min: number
      motivo: string
      reprocessar: boolean
      numero_teste: boolean
      prova: string
    }[]
    message?: string
  }>('/api/v2/sem-resposta'),
  atendimento: (filters: GlobalFilters) =>
    req<AtendimentoPayload>(`/api/v2/atendimento?${qs(filters)}`),
  comercial: (filters: GlobalFilters) =>
    req<Record<string, unknown>>(`/api/v2/comercial?${qs(filters)}`),
  operacao: (filters: GlobalFilters) =>
    req<Record<string, unknown>>(`/api/v2/operacao?${qs(filters)}`),
  robo: (filters: GlobalFilters) =>
    req<Record<string, unknown>>(`/api/v2/robo?${qs(filters)}`),
  drilldown: (body: {
    metric_id: string
    page?: number
    page_size?: number
    filters?: GlobalFilters
    stage?: string | null
  }) =>
    req<DrilldownPayload>('/api/v2/drilldown', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}

export function logStreamUrl(): string {
  return '/api/v2/inicio/log/stream'
}
