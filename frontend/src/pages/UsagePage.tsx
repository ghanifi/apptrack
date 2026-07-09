import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

interface UsageSummary {
  plan: string
  period: string
  usage: {
    projects: { current: number; limit: number }
    builds_this_month: { current: number; limit: number }
    deploys_this_month: { current: number; limit: number }
    concurrent_builds: { current: number; limit: number }
    storage_mb: { current: number; limit: number }
    build_minutes: { current: number }
  }
}

function formatPeriod(period: string): string {
  const [year, month] = period.split('-').map(Number)
  if (!year || !month) return period
  return new Date(year, month - 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
}

function ProgressBar({ current, limit, label }: { current: number; limit: number; label: string }) {
  const pct = limit > 0 ? Math.min((current / limit) * 100, 100) : 0
  const color = pct >= 90 ? 'bg-red-500' : pct >= 70 ? 'bg-yellow-500' : 'bg-blue-500'
  return (
    <div className="mb-4">
      <div className="flex justify-between text-sm text-gray-300 mb-1">
        <span>{label}</span>
        <span>{current} / {limit}</span>
      </div>
      <div
        role="progressbar"
        aria-valuenow={current}
        aria-valuemin={0}
        aria-valuemax={limit}
        aria-label={label}
        className="w-full h-2 bg-gray-700 rounded-full overflow-hidden"
      >
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function UsagePage() {
  const { data, isLoading, error } = useQuery<UsageSummary>({
    queryKey: ['usage-summary'],
    queryFn: () => api.get('/usage/summary').then(r => r.data),
  })

  if (isLoading) return <div className="p-6 text-gray-400">Loading usage data...</div>

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-red-400">Kullanım verileri yüklenemedi. Sayfayı yenileyin.</p>
      </div>
    )
  }

  if (!data) return <div className="p-6 text-red-400">Failed to load usage data</div>

  const planColors: Record<string, string> = {
    free: 'bg-gray-600',
    pro: 'bg-blue-600',
    enterprise: 'bg-purple-600',
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Usage & Billing</h1>
        <span className={`px-3 py-1 rounded-full text-sm font-medium text-white ${planColors[data.plan] || 'bg-gray-600'}`}>
          {data.plan.toUpperCase()} Plan
        </span>
      </div>

      <p className="text-gray-400 text-sm mb-6">Period: {formatPeriod(data.period)}</p>

      <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Resource Usage</h2>
        <ProgressBar current={data.usage.projects.current} limit={data.usage.projects.limit} label="Projects" />
        <ProgressBar current={data.usage.builds_this_month.current} limit={data.usage.builds_this_month.limit} label="Builds This Month" />
        <ProgressBar current={data.usage.deploys_this_month.current} limit={data.usage.deploys_this_month.limit} label="Deploys This Month" />
        <ProgressBar current={data.usage.concurrent_builds.current} limit={data.usage.concurrent_builds.limit} label="Concurrent Builds" />
        <ProgressBar current={data.usage.storage_mb.current} limit={data.usage.storage_mb.limit} label="Storage (MB)" />
        <div className="mt-4 text-sm text-gray-400">
          Build Minutes Used: <span className="text-white font-medium">{data.usage.build_minutes.current}</span>
        </div>
      </div>

      <div className="mt-6 bg-gray-800/50 border border-gray-700 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-white mb-3">Plan Comparison</h2>
        <div className="grid grid-cols-3 gap-4 text-sm">
          {(['free', 'pro', 'enterprise'] as const).map(plan => (
            <div key={plan} className={`p-4 rounded-lg border ${data.plan === plan ? 'border-blue-500 bg-blue-500/10' : 'border-gray-600'}`}>
              <h3 className="text-white font-bold capitalize mb-2">{plan}</h3>
              <ul className="text-gray-400 space-y-1">
                <li>{plan === 'free' ? '3' : plan === 'pro' ? '20' : '999'} projects</li>
                <li>{plan === 'free' ? '10' : plan === 'pro' ? '100' : '999'} builds/mo</li>
                <li>{plan === 'free' ? '500MB' : plan === 'pro' ? '5GB' : '50GB'} storage</li>
              </ul>
              {data.plan === plan && <span className="mt-2 inline-block text-blue-400 text-xs font-medium">Current Plan</span>}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
