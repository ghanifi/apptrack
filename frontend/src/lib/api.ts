import axios from 'axios'
import { toast } from 'sonner'
import { useAuthStore } from '@/store/authStore'
import { env } from '@/lib/env'

export const api = axios.create({
  baseURL: env.API_URL,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true, // HttpOnly refresh cookie'sinin set/gönderimi için
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
    // Login/register/refresh'in kendi 401'i oturum süresi dolması değildir;
    // refresh+redirect akışına girerse sayfa yenilenir ve form hatası kaybolur.
    const isAuthEndpoint = /\/auth\/(login|register|refresh)$/.test(originalRequest?.url ?? '')
    if (err.response?.status === 401 && !isAuthEndpoint && !(originalRequest as any)._retry) {
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
    const rawDetail = err.response?.data?.detail
    const message =
      typeof rawDetail === 'string'
        ? rawDetail
        : Array.isArray(rawDetail)
          ? rawDetail.map((e: { msg?: string }) => e.msg || JSON.stringify(e)).join(', ')
          : err.message || 'An error occurred'
    if (err.response?.status !== 401) {
      toast.error(message)
    }
    return Promise.reject(err)
  }
)
