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
  user: User | null
  isLoading: boolean
  setAuth: (token: string, user: User) => void
  clearAuth: () => void
  refreshAccessToken: () => Promise<boolean>
}

// Refresh token artık localStorage'da DEĞİL — sunucuda HttpOnly cookie'de tutulur
// (XSS ile çalınamaz). Burada yalnız kısa ömürlü access token + kullanıcı saklanır.
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isLoading: false,
      setAuth: (token, user) => set({ token, user, isLoading: false }),
      clearAuth: () => {
        // Sunucudaki HttpOnly refresh cookie'sini de temizle (fire-and-forget).
        // .catch(): ağ/logout hatası önemsiz — istemci durumu yine temizlenir.
        void fetch('/api/auth/logout', { method: 'POST', credentials: 'include' }).catch(() => {})
        set({ token: null, user: null, isLoading: false })
      },
      refreshAccessToken: async () => {
        try {
          const res = await fetch('/api/auth/refresh', {
            method: 'POST',
            credentials: 'include', // HttpOnly refresh cookie'sini gönder
          })
          if (!res.ok) return false
          const data = await res.json()
          const user = useAuthStore.getState().user
          if (!user) return false
          useAuthStore.getState().setAuth(data.access_token, user)
          return true
        } catch {
          return false
        }
      },
    }),
    { name: 'apptrack-auth', partialize: (s) => ({ token: s.token, user: s.user }) }
  )
)
