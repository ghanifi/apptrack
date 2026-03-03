import axios from 'axios'
import { toast } from 'sonner'
import { useAuthStore } from '@/store/authStore'
import { env } from '@/lib/env'

export const api = axios.create({
  baseURL: env.API_URL,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const originalRequest = err.config
    if (err.response?.status === 401 && !(originalRequest as any)._retry) {
      (originalRequest as any)._retry = true
      const refreshed = await useAuthStore.getState().refreshAccessToken()
      if (refreshed) {
        // Token yenilendi, isteği tekrar dene
        const newToken = useAuthStore.getState().token
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return api(originalRequest)
      }
      // Refresh başarısız → logout
      useAuthStore.getState().clearAuth()
      window.location.href = '/login'
    }
    const message = err.response?.data?.detail || err.message || 'An error occurred'
    if (err.response?.status !== 401) {
      toast.error(message)
    }
    return Promise.reject(err)
  }
)
