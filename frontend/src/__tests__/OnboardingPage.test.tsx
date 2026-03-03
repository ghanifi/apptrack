import { describe, it, expect, beforeAll, afterAll, afterEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from '../test/server'
import OnboardingPage from '../pages/OnboardingPage'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

// Mock the Confetti component to avoid canvas issues in test
vi.mock('../components/ui/Confetti', () => ({
  default: () => null,
}))

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
  mockNavigate.mockReset()
})
afterAll(() => server.close())

describe('OnboardingPage', () => {
  it('renders step 1 - Connect GitHub', async () => {
    renderWithProviders(<OnboardingPage />)

    expect(screen.getByText('Connect your GitHub')).toBeInTheDocument()
    expect(
      screen.getByText("We'll import your repositories so you can select one to build.")
    ).toBeInTheDocument()
    expect(screen.getByText(/Step 1 of 7/)).toBeInTheDocument()
  })

  it('shows GitHub connected state and Continue button', async () => {
    // Default handler returns github_connected: true
    renderWithProviders(<OnboardingPage />)

    await waitFor(() => {
      expect(screen.getByText('GitHub connected')).toBeInTheDocument()
    })

    expect(screen.getByText('Continue')).toBeInTheDocument()
  })

  it('shows Connect GitHub link when not connected', async () => {
    server.use(
      http.get('/api/github/profile', () => {
        return HttpResponse.json({ github_connected: false })
      })
    )

    renderWithProviders(<OnboardingPage />)

    // When GitHub is not connected, a link to /api/auth/github should be shown
    await waitFor(() => {
      const link = screen.getByRole('link', { name: /Connect GitHub/ })
      expect(link).toBeInTheDocument()
      expect(link).toHaveAttribute('href', '/api/auth/github')
    })
  })

  it('navigates to step 2 - Select Repository', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OnboardingPage />)

    await waitFor(() => {
      expect(screen.getByText('Continue')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Continue'))

    await waitFor(() => {
      expect(screen.getByText('Select a repository')).toBeInTheDocument()
    })
    expect(screen.getByText(/Step 2 of 7/)).toBeInTheDocument()
  })

  it('shows repository list on step 2', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OnboardingPage />)

    await waitFor(() => {
      expect(screen.getByText('Continue')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Continue'))

    await waitFor(() => {
      expect(screen.getByText('testuser/my-app')).toBeInTheDocument()
    })
    expect(screen.getByText('testuser/another-app')).toBeInTheDocument()
  })

  it('allows searching repos', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OnboardingPage />)

    await waitFor(() => {
      expect(screen.getByText('Continue')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Continue'))

    await waitFor(() => {
      expect(screen.getByText('testuser/my-app')).toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('Search repos...'), 'another')

    expect(screen.queryByText('testuser/my-app')).not.toBeInTheDocument()
    expect(screen.getByText('testuser/another-app')).toBeInTheDocument()
  })

  it('shows import button after selecting a repo', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OnboardingPage />)

    await waitFor(() => {
      expect(screen.getByText('Continue')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Continue'))

    await waitFor(() => {
      expect(screen.getByText('testuser/my-app')).toBeInTheDocument()
    })

    await user.click(screen.getByText('testuser/my-app'))

    expect(screen.getByText('Import & Analyze')).toBeInTheDocument()
  })

  it('shows step sidebar with all steps listed', async () => {
    renderWithProviders(<OnboardingPage />)

    // Wait for the profile to load (github_connected: true), ensuring
    // "Connect GitHub" text only appears in the sidebar (not as a link in content).
    await waitFor(() => {
      expect(screen.getByText('GitHub connected')).toBeInTheDocument()
    })

    // Sidebar step labels
    expect(screen.getByText('Connect GitHub')).toBeInTheDocument()
    expect(screen.getByText('Select Repository')).toBeInTheDocument()
    expect(screen.getByText('Framework Detection')).toBeInTheDocument()
    expect(screen.getByText('Project Ready')).toBeInTheDocument()
    expect(screen.getByText('Store Credentials')).toBeInTheDocument()
    expect(screen.getByText('Build App')).toBeInTheDocument()
    // "Deploy to Stores" appears only in sidebar on step 1
    expect(screen.getByText('Deploy to Stores')).toBeInTheDocument()
  })

  it('shows build step with platform selection', async () => {
    const user = userEvent.setup()
    // Navigate through steps: connect -> select -> detect/preview -> build
    // Use a handler that moves us through quickly
    server.use(
      http.post('/api/projects', () => {
        return HttpResponse.json({
          id: 'proj-1',
          name: 'my-app',
          framework: 'react-native',
          status: 'ready',
        })
      })
    )

    renderWithProviders(<OnboardingPage />)

    // Step 1: Continue
    await waitFor(() => {
      expect(screen.getByText('Continue')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Continue'))

    // Step 2: Select repo and import
    await waitFor(() => {
      expect(screen.getByText('testuser/my-app')).toBeInTheDocument()
    })
    await user.click(screen.getByText('testuser/my-app'))
    await user.click(screen.getByText('Import & Analyze'))

    // Step 3: Detect -> auto-advances to Step 4: Preview
    await waitFor(
      () => {
        expect(screen.getByText('Project ready!')).toBeInTheDocument()
      },
      { timeout: 5000 }
    )

    // Step 4: Preview -> skip to build
    await user.click(screen.getByText('Skip for now, just build'))

    // Step 6: Build step
    await waitFor(() => {
      expect(screen.getByText('Build your app')).toBeInTheDocument()
    })

    // Verify platform selectors are visible
    expect(screen.getByText('Android')).toBeInTheDocument()
    expect(screen.getByText('iOS')).toBeInTheDocument()
    expect(screen.getByText('Both')).toBeInTheDocument()
    expect(screen.getByText('Start Build')).toBeInTheDocument()
  })

  it('shows deploy track selector on deploy step', async () => {
    const user = userEvent.setup()
    server.use(
      http.post('/api/projects', () => {
        return HttpResponse.json({
          id: 'proj-1',
          name: 'my-app',
          framework: 'react-native',
          status: 'ready',
        })
      }),
      // Return a successful build so we can advance to deploy
      http.get('/api/builds', () => {
        return HttpResponse.json({
          items: [
            {
              id: 'build-1',
              status: 'success',
              platform: 'android',
              provider: 'eas',
            },
          ],
        })
      }),
      // Return credentials so deploy is available
      http.get('/api/credentials', () => {
        return HttpResponse.json([
          { id: 'c1', provider: 'google_play', key_name: 'GOOGLE_PLAY_KEY_JSON', updated_at: '2025-01-01T00:00:00Z' },
        ])
      })
    )

    renderWithProviders(<OnboardingPage />)

    // Navigate: connect -> select -> detect -> preview -> build
    await waitFor(() => {
      expect(screen.getByText('Continue')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Continue'))

    await waitFor(() => {
      expect(screen.getByText('testuser/my-app')).toBeInTheDocument()
    })
    await user.click(screen.getByText('testuser/my-app'))
    await user.click(screen.getByText('Import & Analyze'))

    await waitFor(
      () => {
        expect(screen.getByText('Project ready!')).toBeInTheDocument()
      },
      { timeout: 5000 }
    )

    await user.click(screen.getByText('Skip for now, just build'))

    await waitFor(() => {
      expect(screen.getByText('Build your app')).toBeInTheDocument()
    })

    // Trigger the build
    await user.click(screen.getByText('Start Build'))

    // Wait for builds to load and show the deploy button (not the sidebar label)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Deploy to Stores/ })).toBeInTheDocument()
    })

    // Click the Deploy to Stores button to advance to deploy step
    await user.click(screen.getByRole('button', { name: /Deploy to Stores/ }))

    // Now we should be on the deploy step with the track selector
    await waitFor(() => {
      expect(screen.getByText('Your app is ready to publish!')).toBeInTheDocument()
    })

    // Verify deploy track selector
    expect(screen.getByText('Deploy Track')).toBeInTheDocument()
  })
})
