import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { server } from '../test/server'
import SigningDoctorPanel from '../components/SigningDoctorPanel'

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

const mismatchPayload = {
  configured: true, overall: 'mismatch', can_auto_repair: true,
  checks: [
    { id: 'certificate', title: 'İmzalama sertifikası', status: 'ok', severity: 'info', detail: 'Sertifika geçerli.', fixable: false },
    { id: 'bundle_match', title: 'Bundle ID eşleşmesi', status: 'mismatch', severity: 'critical', detail: "Profil 'com.other' ≠ proje 'com.example'.", fixable: true },
  ],
}

describe('SigningDoctorPanel', () => {
  it('sorunlu check + onarım butonu render eder', async () => {
    server.use(http.get('/api/signing/doctor/p1', () => HttpResponse.json(mismatchPayload)))
    renderWithProviders(<SigningDoctorPanel projectId="p1" packageName="com.example" framework="flutter" />)
    await waitFor(() => expect(screen.getByText('Bundle ID eşleşmesi')).toBeInTheDocument())
    expect(screen.getByText(/yeniden üret/i)).toBeInTheDocument()
  })

  it('iOS üretmeyen framework için hiçbir şey render etmez', () => {
    const { container } = renderWithProviders(
      <SigningDoctorPanel projectId="p1" packageName="com.example" framework="pwa" />
    )
    expect(container).toBeEmptyDOMElement()
  })
})
