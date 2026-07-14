import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { server } from '../test/server'
import AiProviderPanel from '../components/AiProviderPanel'

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

const config = {
  provider: 'gemini', model: 'gemini-2.5-flash-lite',
  providers: [
    { id: 'gemini', label: 'Google Gemini', default_model: 'gemini-2.5-flash-lite', free: true },
    { id: 'openai', label: 'OpenAI', default_model: 'gpt-5-nano', free: false },
  ],
  configured: { gemini: false, openai: false },
}

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('AiProviderPanel', () => {
  it('sağlayıcıları listeler ve ücretsiz rozetini gösterir', async () => {
    server.use(http.get('/api/ai/config', () => HttpResponse.json(config)))
    renderWithProviders(<AiProviderPanel />)
    await waitFor(() => expect(screen.getByText('Google Gemini')).toBeInTheDocument())
    expect(screen.getByText('OpenAI')).toBeInTheDocument()
    expect(screen.getByText('Ücretsiz')).toBeInTheDocument()  // rozet (açıklamadaki "Ücretsiz katmanlar" hariç)
    expect(screen.getByText(/Bağlantıyı test et/)).toBeInTheDocument()
  })
})
