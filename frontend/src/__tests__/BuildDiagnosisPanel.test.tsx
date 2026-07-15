import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import BuildDiagnosisPanel from '@/components/ui/BuildDiagnosisPanel'

const server = setupServer(
  http.post('*/build-diagnosis/diagnose/:id', () => HttpResponse.json({
    diagnoses: [{ id: 'unknown_error', framework_group: 'generic', diagnosis: 'x', fix: 'y', auto_fix: false }],
    diagnosis_count: 1, severity: 'high', auto_fixable: false, ai_available: true, message: null,
  })),
  http.post('*/build-diagnosis/autofix/:id/agentic', () => HttpResponse.json({ job_id: 'job-1' })),
  http.get('*/build-diagnosis/autofix/status/job-1', () => HttpResponse.json({
    state: 'done', steps: ['okunuyor: package.json', 'PR açılıyor'],
    pr_url: 'https://github.com/x/y/pull/1', error: null,
  })),
)
beforeEach(() => server.listen())
afterEach(() => server.resetHandlers())

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <BuildDiagnosisPanel buildId="b1" />
    </QueryClientProvider>,
  )
}

describe('BuildDiagnosisPanel agentic', () => {
  it('agentic butonu ai_available && !auto_fixable iken görünür ve akışı tamamlar', async () => {
    renderPanel()
    const btn = await screen.findByRole('button', { name: /agentic/i })
    fireEvent.click(btn)
    await waitFor(() => expect(screen.getByText(/okunuyor: package.json/)).toBeInTheDocument())
    await waitFor(() => expect(screen.getByRole('link', { name: /PR/i })).toHaveAttribute(
      'href', 'https://github.com/x/y/pull/1'))
  })
})
