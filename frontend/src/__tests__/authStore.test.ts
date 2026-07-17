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

const USER = { id: '1', email: 'test@example.com', name: 'Test User' }

describe('authStore', () => {
  it('starts with null token and user (no refreshToken in store)', () => {
    const state = useAuthStore.getState()
    expect(state.token).toBeNull()
    expect(state.user).toBeNull()
    // refresh token artık store'da tutulmaz — HttpOnly cookie'de
    expect('refreshToken' in state).toBe(false)
    expect(state.isLoading).toBe(false)
  })

  it('setAuth stores token and user', () => {
    useAuthStore.getState().setAuth('my-token', USER)

    const state = useAuthStore.getState()
    expect(state.token).toBe('my-token')
    expect(state.user).toEqual(USER)
    expect(state.isLoading).toBe(false)
  })

  it('clearAuth resets token and user', () => {
    useAuthStore.getState().setAuth('my-token', USER)
    useAuthStore.getState().clearAuth()

    const state = useAuthStore.getState()
    expect(state.token).toBeNull()
    expect(state.user).toBeNull()
    expect(state.isLoading).toBe(false)
  })

  it('refreshAccessToken returns false when no user in store', async () => {
    const result = await useAuthStore.getState().refreshAccessToken()
    expect(result).toBe(false)
  })

  it('refreshAccessToken successfully refreshes access token (cookie tabanlı)', async () => {
    useAuthStore.getState().setAuth('old-token', USER)

    const result = await useAuthStore.getState().refreshAccessToken()
    expect(result).toBe(true)

    const state = useAuthStore.getState()
    expect(state.token).toBe('new-access-token')
    expect(state.user).toEqual(USER)
  })

  it('refreshAccessToken returns false on 401 (geçersiz/eksik cookie)', async () => {
    server.use(
      http.post('/api/auth/refresh', () => {
        return HttpResponse.json({ detail: 'Missing refresh token' }, { status: 401 })
      })
    )
    useAuthStore.getState().setAuth('old-token', USER)

    const result = await useAuthStore.getState().refreshAccessToken()
    expect(result).toBe(false)
  })

  it('refreshAccessToken returns false on network error', async () => {
    server.use(
      http.post('/api/auth/refresh', () => {
        return HttpResponse.error()
      })
    )
    useAuthStore.getState().setAuth('old-token', USER)

    const result = await useAuthStore.getState().refreshAccessToken()
    expect(result).toBe(false)
  })

  it('persists only token and user under apptrack-auth key (no refresh token)', () => {
    useAuthStore.getState().setAuth('persist-token', USER)

    const stored = localStorage.getItem('apptrack-auth')
    expect(stored).not.toBeNull()

    const parsed = JSON.parse(stored!)
    expect(parsed.state.token).toBe('persist-token')
    expect(parsed.state.user).toEqual(USER)
    // refresh token localStorage'a ASLA yazılmamalı (XSS koruması)
    expect(parsed.state.refreshToken).toBeUndefined()
    expect(stored).not.toContain('refresh')
  })
})
