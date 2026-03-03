import { describe, it, expect, beforeAll, afterAll, afterEach, beforeEach } from 'vitest'
import { server } from '../test/server'
import { useAuthStore } from '../store/authStore'
import { http, HttpResponse } from 'msw'

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

beforeEach(() => {
  useAuthStore.getState().clearAuth()
})

describe('authStore', () => {
  it('starts with null token, refreshToken, and user', () => {
    const state = useAuthStore.getState()
    expect(state.token).toBeNull()
    expect(state.refreshToken).toBeNull()
    expect(state.user).toBeNull()
    expect(state.isLoading).toBe(false)
  })

  it('setAuth stores token, refreshToken, and user', () => {
    const user = { id: '1', email: 'test@example.com', name: 'Test User' }
    useAuthStore.getState().setAuth('my-token', 'my-refresh-token', user)

    const state = useAuthStore.getState()
    expect(state.token).toBe('my-token')
    expect(state.refreshToken).toBe('my-refresh-token')
    expect(state.user).toEqual(user)
    expect(state.isLoading).toBe(false)
  })

  it('clearAuth resets token, refreshToken, and user', () => {
    const user = { id: '1', email: 'test@example.com', name: 'Test User' }
    useAuthStore.getState().setAuth('my-token', 'my-refresh-token', user)
    useAuthStore.getState().clearAuth()

    const state = useAuthStore.getState()
    expect(state.token).toBeNull()
    expect(state.refreshToken).toBeNull()
    expect(state.user).toBeNull()
    expect(state.isLoading).toBe(false)
  })

  it('refreshAccessToken returns false when no refresh token', async () => {
    const result = await useAuthStore.getState().refreshAccessToken()
    expect(result).toBe(false)
  })

  it('refreshAccessToken successfully refreshes token', async () => {
    const user = { id: '1', email: 'test@example.com', name: 'Test User' }
    useAuthStore.getState().setAuth('old-token', 'valid-refresh-token', user)

    const result = await useAuthStore.getState().refreshAccessToken()
    expect(result).toBe(true)

    const state = useAuthStore.getState()
    expect(state.token).toBe('new-access-token')
    expect(state.refreshToken).toBe('new-refresh-token')
    expect(state.user).toEqual(user)
  })

  it('refreshAccessToken returns false on invalid refresh token', async () => {
    const user = { id: '1', email: 'test@example.com', name: 'Test User' }
    useAuthStore.getState().setAuth('old-token', 'invalid-refresh-token', user)

    const result = await useAuthStore.getState().refreshAccessToken()
    expect(result).toBe(false)
  })

  it('refreshAccessToken returns false on network error', async () => {
    server.use(
      http.post('/api/auth/refresh', () => {
        return HttpResponse.error()
      })
    )

    const user = { id: '1', email: 'test@example.com', name: 'Test User' }
    useAuthStore.getState().setAuth('old-token', 'valid-refresh-token', user)

    const result = await useAuthStore.getState().refreshAccessToken()
    expect(result).toBe(false)
  })

  it('persists state under apptrack-auth key', () => {
    const user = { id: '1', email: 'test@example.com', name: 'Test User' }
    useAuthStore.getState().setAuth('persist-token', 'persist-refresh', user)

    // The zustand persist middleware uses localStorage with key 'apptrack-auth'
    const stored = localStorage.getItem('apptrack-auth')
    expect(stored).not.toBeNull()

    const parsed = JSON.parse(stored!)
    expect(parsed.state.token).toBe('persist-token')
    expect(parsed.state.refreshToken).toBe('persist-refresh')
    expect(parsed.state.user).toEqual(user)
  })
})
