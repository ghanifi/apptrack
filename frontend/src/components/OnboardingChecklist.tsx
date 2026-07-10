import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useState } from 'react'
import { CheckCircle2, Circle, X, Rocket } from 'lucide-react'
import { api } from '@/lib/api'

interface OnboardingStep {
  key: string
  done: boolean
}
interface OnboardingStatus {
  steps: OnboardingStep[]
  completed: number
  total: number
  all_done: boolean
}

const STEP_META: Record<string, { title: string; desc: string; to: string; cta: string }> = {
  connect_repo: {
    title: 'Connect a repository',
    desc: 'Link a GitHub repo to start building.',
    to: '/dashboard/projects/new',
    cta: 'Connect repo',
  },
  framework_detected: {
    title: 'Framework detected',
    desc: 'We auto-detect Flutter, React Native, Expo, Capacitor and more.',
    to: '/dashboard/projects',
    cta: 'View project',
  },
  first_build: {
    title: 'Run your first build',
    desc: 'Trigger a build with your own GitHub Actions minutes.',
    to: '/dashboard/projects',
    cta: 'Start a build',
  },
  first_deploy: {
    title: 'Deploy to a store',
    desc: 'Ship to App Store or Google Play.',
    to: '/dashboard/projects',
    cta: 'Deploy',
  },
}

const DISMISS_KEY = 'apptrack.onboarding.dismissed'

export default function OnboardingChecklist() {
  const [dismissed, setDismissed] = useState(() => localStorage.getItem(DISMISS_KEY) === '1')

  const { data } = useQuery<OnboardingStatus>({
    queryKey: ['onboarding-status'],
    queryFn: () => api.get('/onboarding/status').then((r) => r.data),
  })

  if (dismissed || !data || data.all_done) return null

  const pct = Math.round((data.completed / data.total) * 100)
  // İlk tamamlanmamış adım vurgulanır (sıradaki eylem)
  const nextKey = data.steps.find((s) => !s.done)?.key

  const dismiss = () => {
    localStorage.setItem(DISMISS_KEY, '1')
    setDismissed(true)
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-8">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary-600 flex items-center justify-center shrink-0">
            <Rocket size={18} className="text-white" />
          </div>
          <div>
            <h2 className="text-base font-semibold">Get started with AppTrack</h2>
            <p className="text-sm text-gray-400">
              {data.completed} of {data.total} steps complete
            </p>
          </div>
        </div>
        <button
          onClick={dismiss}
          aria-label="Dismiss checklist"
          className="text-gray-500 hover:text-gray-300 transition-colors"
        >
          <X size={18} />
        </button>
      </div>

      <div className="h-1.5 w-full bg-gray-800 rounded-full mb-5 overflow-hidden">
        <div className="h-full bg-primary-600 rounded-full transition-all" style={{ width: `${pct}%` }} />
      </div>

      <ul className="space-y-2">
        {data.steps.map((step) => {
          const meta = STEP_META[step.key]
          if (!meta) return null
          const isNext = step.key === nextKey
          return (
            <li
              key={step.key}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 border ${
                isNext ? 'border-primary-600/60 bg-primary-600/5' : 'border-transparent'
              }`}
            >
              {step.done ? (
                <CheckCircle2 size={18} className="text-green-400 shrink-0 animate-pop-in" />
              ) : (
                <Circle size={18} className="text-gray-600 shrink-0" />
              )}
              <div className="min-w-0 flex-1">
                <p className={`text-sm ${step.done ? 'text-gray-400 line-through' : 'font-medium'}`}>
                  {meta.title}
                </p>
                {!step.done && <p className="text-xs text-gray-500">{meta.desc}</p>}
              </div>
              {isNext && (
                <Link
                  to={meta.to}
                  className="text-xs font-medium px-3 py-1.5 rounded-lg bg-primary-600 hover:bg-primary-700 text-white transition-colors shrink-0"
                >
                  {meta.cta}
                </Link>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
