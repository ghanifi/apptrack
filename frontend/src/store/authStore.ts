import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface User {
  id: string
  email: string
  name: string
  avatar_url?: string
}

interface AuthState {
  token: string | null
  refreshToken: string | null
  user: User | null
  isLoading: boolean
  setAuth: (token: string, refreshToken: string, user: User) => void
  clearAuth: () => void
  refreshAccessToken: () => Promise<boolean>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      refreshToken: null,
      user: null,
      isLoading: false,
      setAuth: (token, refreshToken, user) => set({ token, refreshToken, user, isLoading: false }),
      clearAuth: () => set({ token: null, refreshToken: null, user: null, isLoading: false }),
      refreshAccessToken: async () => {
        const { refreshToken } = useAuthStore.getState()
        if (!refreshToken) return false
        try {
          const res = await fetch('/api/auth/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
          })
          if (!res.ok) return false
          const data = await res.json()
          useAuthStore.getState().setAuth(data.access_token, data.refresh_token ?? refreshToken, useAuthStore.getState().user!)
          return true
        } catch {
          return false
        }
      },
    }),
    { name: 'apptrack-auth' }
  )
)
