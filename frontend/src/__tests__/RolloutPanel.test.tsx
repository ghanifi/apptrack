import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { server } from '../test/server'
import RolloutPanel from '../components/RolloutPanel'
import type { Rollout } from '../types'

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('RolloutPanel', () => {
  it('rollout yokken "başlat" butonunu render eder', async () => {
    server.use(
      http.get('/api/rollouts/by-project/proj-1/active', () => HttpResponse.json(null))
    )
    renderWithProviders(
      <RolloutPanel buildId="build-1" projectId="proj-1" packageName="com.example.app" />
    )

    await waitFor(() => {
      expect(screen.getByText('Kademeli yayını başlat')).toBeInTheDocument()
    })
    expect(screen.getByText('Kademeli yayın (Staged Rollout)')).toBeInTheDocument()
  })

  it('in_progress rollout için aşama çubuğu + İlerlet butonu render eder', async () => {
    const rollout: Rollout = {
      id: 'ro-1',
      deployment_id: 'dep-1',
      project_id: 'proj-1',
      platform: 'google_play',
      package_name: 'com.example.app',
      track: 'production',
      current_fraction: 0.1,
      state: 'in_progress',
      auto_halt_enabled: true,
      crash_free_threshold: 0.99,
      baseline_crash_free: 0.995,
      min_users: 1000,
      halted_reason: null,
      next_fraction: 0.5,
      samples: [
        { sampled_at: '2026-07-10T09:00:00Z', crash_free_rate: 0.998, anr_rate: 0.001, distinct_users: 4200, adoption: 0.1 },
      ],
    }
    server.use(
      http.get('/api/rollouts/by-project/proj-1/active', () => HttpResponse.json(rollout))
    )
    renderWithProviders(
      <RolloutPanel buildId="build-2" projectId="proj-1" packageName="com.example.app" />
    )

    await waitFor(() => {
      expect(screen.getByText(/İlerlet/)).toBeInTheDocument()
    })
    // Aşama çubuğu yüzdeleri
    expect(screen.getByText('1%')).toBeInTheDocument()
    expect(screen.getByText('10%')).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
    expect(screen.getByText('100%')).toBeInTheDocument()
    // İlerlet hedefi next_fraction'a göre
    expect(screen.getByText('İlerlet (→ %50)')).toBeInTheDocument()
    // Auto-halt rozeti
    expect(screen.getByText('Auto-halt açık')).toBeInTheDocument()
    // Sağlık crash-free
    expect(screen.getByText('99.80%')).toBeInTheDocument()
  })
})
