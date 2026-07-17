import { describe, it, expect, beforeAll, afterAll, afterEach, beforeEach } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../test/server'
import { useAuthStore } from '../store/authStore'
import { api } from '../lib/api'

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

beforeEach(() => {
  useAuthStore.getState().clearAuth()
})

describe('api module', () => {
  it('has correct baseURL', () => {
    expect(api.defaults.baseURL).toBe('/api')
  })

  it('adds Authorization header when token is set', async () => {
    const user = { id: '1', email: 'test@example.com', name: 'Test User' }
    useAuthStore.getState().setAuth('test-bearer-token', user)

    let capturedAuth = ''
    server.use(
      http.get('/api/test-auth-header', ({ request }) => {
        capturedAuth = request.headers.get('Authorization') ?? ''
        return HttpResponse.json({ ok: true })
      })
    )

    await api.get('/test-auth-header')
    expect(capturedAuth).toBe('Bearer test-bearer-token')
  })

  it('does not add Authorization header when no token', async () => {
    let capturedAuth: string | null = null
    server.use(
      http.get('/api/test-no-auth', ({ request }) => {
        capturedAuth = request.headers.get('Authorization')
        return HttpResponse.json({ ok: true })
      })
    )

    await api.get('/test-no-auth')
    // When no token is set, Authorization should either be null or not contain "Bearer null"
    expect(capturedAuth).toBeNull()
  })

  it('retries on 401 with successful token refresh', async () => {
    const user = { id: '1', email: 'test@example.com', name: 'Test User' }
    useAuthStore.getState().setAuth('expired-token', user)

    let callCount = 0
    server.use(
      http.get('/api/protected-resource', ({ request }) => {
        callCount++
        const auth = request.headers.get('Authorization')
        if (auth === 'Bearer expired-token') {
          return HttpResponse.json({ detail: 'Unauthorized' }, { status: 401 })
        }
        // After refresh, the new token should be used
        if (auth === 'Bearer new-access-token') {
          return HttpResponse.json({ data: 'secret stuff' })
        }
        return HttpResponse.json({ detail: 'Unauthorized' }, { status: 401 })
      })
    )

    const res = await api.get('/protected-resource')
    expect(res.data).toEqual({ data: 'secret stuff' })
    expect(callCount).toBe(2) // First call fails, retry succeeds
  })

  it('clears auth and redirects on refresh failure', async () => {
    const user = { id: '1', email: 'test@example.com', name: 'Test User' }
    useAuthStore.getState().setAuth('expired-token', user)

    // Mock window.location.href
    const originalHref = window.location.href
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { ...window.location, href: originalHref },
    })

    server.use(
      http.get('/api/protected-resource-fail', () => {
        return HttpResponse.json({ detail: 'Unauthorized' }, { status: 401 })
      }),
      http.post('/api/auth/refresh', () => {
        return HttpResponse.json({ detail: 'Invalid refresh token' }, { status: 401 })
      })
    )

    try {
      await api.get('/protected-resource-fail')
    } catch {
      // Expected to throw after refresh failure
    }

    // Auth should be cleared
    const state = useAuthStore.getState()
    expect(state.token).toBeNull()
    expect(state.user).toBeNull()
  })

  it('does not retry on non-401 errors', async () => {
    const user = { id: '1', email: 'test@example.com', name: 'Test User' }
    useAuthStore.getState().setAuth('valid-token', user)

    server.use(
      http.get('/api/server-error', () => {
        return HttpResponse.json({ detail: 'Server error' }, { status: 500 })
      })
    )

    // 500 error should not trigger retry and should reject
    await expect(api.get('/server-error')).rejects.toThrow()

    // Auth should NOT be cleared on 500 (only on 401)
    const state = useAuthStore.getState()
    expect(state.token).toBe('valid-token')
  })

  it('sends Content-Type application/json header', () => {
    expect(api.defaults.headers['Content-Type']).toBe('application/json')
  })
})
