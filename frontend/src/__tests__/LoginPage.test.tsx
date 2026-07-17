import { describe, it, expect, beforeAll, afterAll, afterEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from '../test/server'
import LoginPage from '../pages/LoginPage'
import { useAuthStore } from '../store/authStore'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
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
  mockNavigate.mockReset()
  useAuthStore.getState().clearAuth()
})
afterAll(() => server.close())

describe('LoginPage', () => {
  it('renders the login page with form elements', () => {
    renderWithProviders(<LoginPage />)

    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByText('AppTrack')).toBeInTheDocument()
    // Labels exist as text
    expect(screen.getByText('Email')).toBeInTheDocument()
    expect(screen.getByText('Password')).toBeInTheDocument()
    // Form inputs by type
    expect(screen.getByRole('textbox')).toBeInTheDocument() // email input with type="email" -> role textbox
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByText('Mobile App Publishing Automation Platform')).toBeInTheDocument()
  })

  it('submits valid credentials and navigates to dashboard', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(<LoginPage />)

    const emailInput = container.querySelector('input[type="email"]')!
    const passwordInput = container.querySelector('input[type="password"]')!

    await user.type(emailInput, 'test@example.com')
    await user.type(passwordInput, 'password123')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/')
    })

    // LoginPage setAuth(access_token, user) çağırır; refresh token gövdede
    // dönmez (HttpOnly cookie'de). Token + kullanıcı store'a doğru yerleşmeli.
    const state = useAuthStore.getState()
    expect(state.token).toBe('mock-access-token')
    expect(state.user).toEqual({ id: '1', email: 'test@example.com', name: 'Test User' })
  })

  it('shows loading state while submitting', async () => {
    const user = userEvent.setup()
    // Add a delay to the handler so we can observe loading state
    server.use(
      http.post('/api/auth/login', async () => {
        await new Promise((r) => setTimeout(r, 200))
        return HttpResponse.json({
          access_token: 'tok',
          refresh_token: 'rtok',
          user: { id: '1', email: 'a@b.com', name: 'A' },
        })
      })
    )

    const { container } = renderWithProviders(<LoginPage />)

    const emailInput = container.querySelector('input[type="email"]')!
    const passwordInput = container.querySelector('input[type="password"]')!

    await user.type(emailInput, 'test@example.com')
    await user.type(passwordInput, 'password123')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(screen.getByText('Signing in...')).toBeInTheDocument()

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalled()
    })
  })

  it('shows error message on invalid credentials', async () => {
    const user = userEvent.setup()
    server.use(
      http.post('/api/auth/login', () => {
        return HttpResponse.json({ detail: 'Invalid credentials' }, { status: 401 })
      })
    )

    const { container } = renderWithProviders(<LoginPage />)

    const emailInput = container.querySelector('input[type="email"]')!
    const passwordInput = container.querySelector('input[type="password"]')!

    await user.type(emailInput, 'wrong@example.com')
    await user.type(passwordInput, 'wrongpassword')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => {
      expect(screen.getByText('Invalid email or password')).toBeInTheDocument()
    })
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('shows error on network failure', async () => {
    const user = userEvent.setup()
    server.use(
      http.post('/api/auth/login', () => {
        return HttpResponse.error()
      })
    )

    const { container } = renderWithProviders(<LoginPage />)

    const emailInput = container.querySelector('input[type="email"]')!
    const passwordInput = container.querySelector('input[type="password"]')!

    await user.type(emailInput, 'test@example.com')
    await user.type(passwordInput, 'password123')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => {
      expect(screen.getByText('Invalid email or password')).toBeInTheDocument()
    })
  })
})
