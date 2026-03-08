import { describe, it, expect, beforeAll, afterAll, afterEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from '../test/server'
import OTAPage from '../pages/OTAPage'

// Mock useParams to return a project ID
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useParams: () => ({ id: 'proj-001' }) }
})

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{ui}</BrowserRouter>
    </QueryClientProvider>
  )
}

beforeAll(() => server.listen())
afterEach(() => {
  server.resetHandlers()
})
afterAll(() => server.close())

describe('OTAPage', () => {
  it('renders page header and channel selector', () => {
    server.use(
      http.get('/api/ota/custom-bundle/proj-001/history', () => {
        return HttpResponse.json([])
      })
    )
    renderWithProviders(<OTAPage />)

    expect(screen.getByText('Live Updates (OTA)')).toBeInTheDocument()
    expect(screen.getByText('production')).toBeInTheDocument()
    expect(screen.getByText('staging')).toBeInTheDocument()
    expect(screen.getByText('beta')).toBeInTheDocument()
  })

  it('renders publish form with all fields', () => {
    server.use(
      http.get('/api/ota/custom-bundle/proj-001/history', () => {
        return HttpResponse.json([])
      })
    )
    renderWithProviders(<OTAPage />)

    expect(screen.getByText('Publish New Update')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/storage\.example\.com/)).toBeInTheDocument()
    expect(screen.getByPlaceholderText('1.0.0')).toBeInTheDocument()
    expect(screen.getByText('All Platforms')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Bug fixes/)).toBeInTheDocument()
  })

  it('disables publish button when bundle URL is empty', () => {
    server.use(
      http.get('/api/ota/custom-bundle/proj-001/history', () => {
        return HttpResponse.json([])
      })
    )
    renderWithProviders(<OTAPage />)

    const publishButton = screen.getByText(/Publish to/)
    expect(publishButton).toBeDisabled()
  })

  it('switches channel on button click', async () => {
    const user = userEvent.setup()
    server.use(
      http.get('/api/ota/custom-bundle/proj-001/history', () => {
        return HttpResponse.json([])
      })
    )
    renderWithProviders(<OTAPage />)

    await user.click(screen.getByText('staging'))

    // "Publish to staging" should now be visible
    expect(screen.getByText(/Publish to staging/)).toBeInTheDocument()
  })

  it('shows empty state when no updates exist', async () => {
    server.use(
      http.get('/api/ota/custom-bundle/proj-001/history', () => {
        return HttpResponse.json([])
      })
    )
    renderWithProviders(<OTAPage />)

    await waitFor(() => {
      expect(screen.getByText('No updates published yet.')).toBeInTheDocument()
    })
  })

  it('renders update history list', async () => {
    server.use(
      http.get('/api/ota/custom-bundle/proj-001/history', () => {
        return HttpResponse.json([
          {
            update_id: 'upd-1',
            channel: 'production',
            platform: 'all',
            runtime_version: '1.2.0',
            bundle_url: 'https://example.com/v1.2.zip',
            message: 'Performance improvements',
            status: 'published',
            created_at: '2026-03-01T10:00:00Z',
          },
          {
            update_id: 'upd-2',
            channel: 'production',
            platform: 'android',
            runtime_version: '1.1.0',
            bundle_url: 'https://example.com/v1.1.zip',
            message: 'Bug fix',
            status: 'rolled_back',
            created_at: '2026-02-20T08:00:00Z',
          },
        ])
      })
    )
    renderWithProviders(<OTAPage />)

    await waitFor(() => {
      expect(screen.getByText('v1.2.0')).toBeInTheDocument()
    })
    expect(screen.getByText('Performance improvements')).toBeInTheDocument()
    expect(screen.getByText('v1.1.0')).toBeInTheDocument()
    expect(screen.getByText('Bug fix')).toBeInTheDocument()
    expect(screen.getByText('2 update(s)')).toBeInTheDocument()
  })

  it('shows back to project link', () => {
    server.use(
      http.get('/api/ota/custom-bundle/proj-001/history', () => {
        return HttpResponse.json([])
      })
    )
    renderWithProviders(<OTAPage />)

    const backLink = screen.getByText('Back to Project')
    expect(backLink).toBeInTheDocument()
    expect(backLink.closest('a')).toHaveAttribute('href', '/dashboard/projects/proj-001')
  })

  it('disables rollback button when fewer than 2 updates', async () => {
    server.use(
      http.get('/api/ota/custom-bundle/proj-001/history', () => {
        return HttpResponse.json([
          {
            update_id: 'upd-1',
            channel: 'production',
            platform: 'all',
            runtime_version: '1.0.0',
            bundle_url: 'https://example.com/v1.zip',
            message: 'First',
            status: 'published',
            created_at: '2026-03-01T10:00:00Z',
          },
        ])
      })
    )
    renderWithProviders(<OTAPage />)

    await waitFor(() => {
      expect(screen.getByText('v1.0.0')).toBeInTheDocument()
    })

    const rollbackBtn = screen.getByText('Rollback')
    expect(rollbackBtn).toBeDisabled()
  })
})
