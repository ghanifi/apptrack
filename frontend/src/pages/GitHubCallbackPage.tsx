import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'
import LoadingSpinner from '@/components/LoadingSpinner'

export default function GitHubCallbackPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { setAuth } = useAuthStore()
  const [error, setError] = useState<string | null>(null)
  const calledRef = useRef(false)

  useEffect(() => {
    if (calledRef.current) return
    calledRef.current = true

    const code = searchParams.get('code')
    const state = searchParams.get('state')

    if (!code) {
      setError('GitHub authorization code missing.')
      return
    }

    api
      .post(`/auth/github/callback?code=${encodeURIComponent(code)}${state ? `&state=${encodeURIComponent(state)}` : ''}`)
      .then((res) => {
        const { access_token, user } = res.data
        setAuth(access_token, user)
        navigate('/dashboard', { replace: true })
      })
      .catch((err) => {
        const detail = err.response?.data?.detail || err.message || 'GitHub login failed'
        setError(detail)
      })
  }, [searchParams, navigate, setAuth])

  if (error) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 max-w-md text-center">
          <p className="text-red-400 text-sm mb-4">{error}</p>
          <button
            onClick={() => navigate('/login', { replace: true })}
            className="text-primary-400 hover:underline text-sm"
          >
            Back to Login
          </button>
        </div>
      </div>
    )
  }

  return <LoadingSpinner />
}
