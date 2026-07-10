import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { server } from '../test/server'
import BuildRunnerCard from '../components/BuildRunnerCard'
import RunnerSetupWizard from '../components/RunnerSetupWizard'
import type { Project, Runner } from '../types'

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

const project: Project = {
  id: 'proj-1',
  name: 'Bitki',
  repo_url: 'https://github.com/holladevai/Bitki',
  branch: 'main',
  framework: 'flutter',
  status: 'ready',
  repo_visibility: 'private',
  runner_type: 'self_hosted',
  runner_labels: '',
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-07-01T00:00:00Z',
  owner_id: 'user-1',
  builds: [],
}

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('RunnerSetupWizard + canlı runner listesi', () => {
  it('self_hosted seçiliyken runner listesini render eder', async () => {
    const runners: Runner[] = [
      {
        id: 42,
        name: 'mac-mini-m2',
        os: 'macOS',
        status: 'online',
        busy: true,
        labels: ['self-hosted', 'macOS', 'ARM64'],
        version: '2.320.0',
      },
      {
        id: 43,
        name: 'eski-laptop',
        os: 'Linux',
        status: 'offline',
        busy: false,
        labels: ['self-hosted', 'Linux'],
        version: null,
      },
    ]
    server.use(
      http.get('/api/projects/proj-1/runners', () => HttpResponse.json(runners))
    )

    renderWithProviders(<BuildRunnerCard project={project} />)

    await waitFor(() => {
      expect(screen.getByText('mac-mini-m2')).toBeInTheDocument()
    })
    expect(screen.getByText('eski-laptop')).toBeInTheDocument()
    expect(screen.getByText('meşgul')).toBeInTheDocument()
    expect(screen.getByText('ARM64')).toBeInTheDocument()
    expect(screen.getByText('v2.320.0')).toBeInTheDocument()
    // Sihirbaz kapalı hâlde buton görünür
    expect(screen.getByText('Runner ekle')).toBeInTheDocument()
  })

  it('boş listede yönlendirme mesajı gösterir', async () => {
    server.use(
      http.get('/api/projects/proj-1/runners', () => HttpResponse.json([]))
    )

    renderWithProviders(<BuildRunnerCard project={project} />)

    await waitFor(() => {
      expect(screen.getByText('Henüz runner yok — aşağıdan ekleyin.')).toBeInTheDocument()
    })
  })

  it('403 dönerse listeyi gizler, admin uyarısı gösterir', async () => {
    server.use(
      http.get('/api/projects/proj-1/runners', () =>
        HttpResponse.json(
          { detail: 'Bu repo için admin yetkiniz yok. Runner yönetimi repo admin izni gerektirir.' },
          { status: 403 }
        )
      )
    )

    renderWithProviders(<BuildRunnerCard project={project} />)

    await waitFor(() => {
      expect(screen.getByText(/admin yetkiniz yok/)).toBeInTheDocument()
    })
    expect(screen.queryByText('Henüz runner yok — aşağıdan ekleyin.')).not.toBeInTheDocument()
  })

  it('sihirbaz aç → platform seç → script bloğu görünür', async () => {
    const user = userEvent.setup()
    server.use(
      http.post('/api/projects/proj-1/runners/setup-command', () =>
        HttpResponse.json({
          script: 'curl -sSL https://apptrack.dev/runner.sh | bash -s -- --token ABC123',
          expires_at: '2026-07-10T13:00:00Z',
          labels: 'self-hosted,macOS,ARM64',
          download_url: 'https://github.com/actions/runner/releases/download/v2.320.0/actions-runner-osx-arm64.tar.gz',
        })
      )
    )

    renderWithProviders(<RunnerSetupWizard projectId="proj-1" />)

    // Kapalı hâl: buton
    await user.click(screen.getByText('Runner ekle'))

    // Platform kartları görünür
    expect(screen.getByText('macOS ARM64')).toBeInTheDocument()
    expect(screen.getByText('Linux x64')).toBeInTheDocument()
    expect(screen.getByText('Önerilen')).toBeInTheDocument()

    // Platform seç → script gelir
    await user.click(screen.getByText('macOS ARM64'))
    await waitFor(() => {
      expect(
        screen.getByText(/curl -sSL https:\/\/apptrack\.dev\/runner\.sh/)
      ).toBeInTheDocument()
    })
    expect(screen.getByText(/kadar geçerli \(1 saat\)/)).toBeInTheDocument()
    expect(screen.getByText('Yeniden üret')).toBeInTheDocument()
  })

  it('setup-command hatasında detail mesajını gösterir', async () => {
    const user = userEvent.setup()
    server.use(
      http.post('/api/projects/proj-1/runners/setup-command', () =>
        HttpResponse.json(
          { detail: 'GitHub token runner kaydı için yetkili değil.' },
          { status: 403 }
        )
      )
    )

    renderWithProviders(<RunnerSetupWizard projectId="proj-1" />)

    await user.click(screen.getByText('Runner ekle'))
    await user.click(screen.getByText('Linux x64'))

    await waitFor(() => {
      expect(
        screen.getByText('GitHub token runner kaydı için yetkili değil.')
      ).toBeInTheDocument()
    })
  })
})
