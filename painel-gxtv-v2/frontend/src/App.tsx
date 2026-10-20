import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { FiltersProvider } from '@/lib/filters'
import { Layout } from '@/components/Layout'
import { LoginPage } from '@/pages/LoginPage'
import { HomePage } from '@/pages/HomePage'
import { RegistryPage } from '@/pages/RegistryPage'
import { EspelhoPage } from '@/pages/EspelhoPage'
import { AtendimentoPage } from '@/pages/AtendimentoPage'
import { ComercialPage } from '@/pages/ComercialPage'
import { OperacaoPage } from '@/pages/OperacaoPage'
import { RoboPage } from '@/pages/RoboPage'
import { SemRespostaPage } from '@/pages/SemRespostaPage'

const qc = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <FiltersProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/v2/login" element={<LoginPage />} />
            <Route path="/v2" element={<Layout />}>
              <Route index element={<HomePage />} />
              <Route path="registro" element={<RegistryPage />} />
              <Route path="atendimento" element={<AtendimentoPage />} />
              <Route path="sem-resposta" element={<SemRespostaPage />} />
              <Route path="comercial" element={<ComercialPage />} />
              <Route path="operacao" element={<OperacaoPage />} />
              <Route path="robo" element={<RoboPage />} />
              <Route path="espelho" element={<EspelhoPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/v2/" replace />} />
          </Routes>
        </BrowserRouter>
      </FiltersProvider>
    </QueryClientProvider>
  )
}
