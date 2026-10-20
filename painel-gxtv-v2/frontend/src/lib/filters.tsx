import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import type { GlobalFilters } from './api'

type Ctx = {
  filters: GlobalFilters
  setFilters: (patch: Partial<GlobalFilters>) => void
  reset: () => void
}

const defaultFilters: GlobalFilters = {
  periodo: 'hoje',
  numero: null,
  atendente: null,
  app: null,
  aparelho: null,
}

const FiltersContext = createContext<Ctx | null>(null)

export function FiltersProvider({ children }: { children: ReactNode }) {
  const [filters, setState] = useState<GlobalFilters>(defaultFilters)
  const value = useMemo<Ctx>(
    () => ({
      filters,
      setFilters: (patch) => setState((f) => ({ ...f, ...patch })),
      reset: () => setState(defaultFilters),
    }),
    [filters],
  )
  return <FiltersContext.Provider value={value}>{children}</FiltersContext.Provider>
}

export function useFilters() {
  const ctx = useContext(FiltersContext)
  if (!ctx) throw new Error('useFilters fora do FiltersProvider')
  return ctx
}
