import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from '../test/server'
import DashboardPage from '../pages/DashboardPage'
import { useAuthStore } from '../store/authStore'

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
  useAuthStore.getState().clearAuth()
})
afterAll(() => server.close())

describe('DashboardPage', () => {
  it('renders welcome message with user name', () => {
    useAuthStore.getState().setAuth('tok', 'rtok', {
      id: '1',
      email: 'test@example.com',
      name: 'John',
    })

    renderWithProviders(<DashboardPage />)

    expect(screen.getByText('Welcome back, John')).toBeInTheDocument()
    expect(screen.getByText("Here's what's happening with your apps.")).toBeInTheDocument()
  })

  it('renders welcome message with fallback when no user', () => {
    renderWithProviders(<DashboardPage />)

    expect(screen.getByText('Welcome back, there')).toBeInTheDocument()
  })

  it('shows project list after data loads', async () => {
    useAuthStore.getState().setAuth('tok', 'rtok', {
      id: '1',
      email: 'test@example.com',
      name: 'Test User',
    })

    renderWithProviders(<DashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('test-app')).toBeInTheDocument()
    })

    // Check the project details are shown
    expect(screen.getByText(/react_native/)).toBeInTheDocument()
    expect(screen.getByText(/github\.com\/test\/app/)).toBeInTheDocument()
  })

  it('shows stats cards with correct labels', async () => {
    renderWithProviders(<DashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('Total Projects')).toBeInTheDocument()
    })
    expect(screen.getByText('Ready')).toBeInTheDocument()
    expect(screen.getByText('Total Builds')).toBeInTheDocument()
    expect(screen.getByText('Pending')).toBeInTheDocument()
  })

  it('shows empty state when no projects exist', async () => {
    server.use(
      http.get('/api/projects', () => {
        return HttpResponse.json([])
      })
    )

    renderWithProviders(<DashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('No projects yet')).toBeInTheDocument()
    })
    expect(screen.getByText('Create your first project')).toBeInTheDocument()
  })

  it('displays Recent Projects section with View all link', async () => {
    renderWithProviders(<DashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('Recent Projects')).toBeInTheDocument()
    })
    expect(screen.getByText('View all')).toBeInTheDocument()
  })

  it('shows project status', async () => {
    renderWithProviders(<DashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('ready')).toBeInTheDocument()
    })
  })
})
