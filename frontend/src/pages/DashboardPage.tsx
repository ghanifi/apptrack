import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { FolderGit2, Rocket, CheckCircle, Clock, ArrowRight, BarChart3 } from 'lucide-react'
import { api } from '@/lib/api'
import type { Project, UsageSummary } from '@/types'

export default function DashboardPage() {
  const { user } = useAuthStore()

  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: () => api.get('/projects').then((r) => r.data.items ?? r.data),
  })

  const { data: usage } = useQuery<UsageSummary>({
    queryKey: ['usage-summary'],
    queryFn: () => api.get('/usage/summary').then((r) => r.data),
  })

  const totalBuilds = projects.reduce((acc, p) => acc + ((p as unknown as { builds?: unknown[] }).builds?.length ?? 0), 0)
  const readyProjects = projects.filter((p) => p.status === 'ready').length
  const pendingProjects = projects.filter((p) => p.status === 'pending' || p.status === 'analyzing').length

  const stats = [
    { label: 'Total Projects', value: projects.length.toString(), icon: FolderGit2, color: 'text-blue-400' },
    { label: 'Ready', value: readyProjects.toString(), icon: CheckCircle, color: 'text-green-400' },
    { label: 'Total Builds', value: totalBuilds.toString(), icon: Rocket, color: 'text-purple-400' },
    { label: 'Pending', value: pendingProjects.toString(), icon: Clock, color: 'text-yellow-400' },
  ]

  const recentProjects = [...projects].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  ).slice(0, 5)

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Welcome back, {user?.name ?? 'there'}</h1>
        <p className="text-gray-400 text-sm mt-1">Here's what's happening with your apps.</p>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm text-gray-400">{label}</span>
              <Icon size={18} className={color} />
            </div>
            <p className="text-3xl font-bold">{value}</p>
          </div>
        ))}
      </div>
      <div className="bg-gray-900 border border-gray-800 rounded-xl">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <h2 className="text-base font-semibold">Recent Projects</h2>
          <Link to="/dashboard/projects" className="text-xs text-primary-400 hover:underline flex items-center gap-1">
            View all <ArrowRight size={12} />
          </Link>
        </div>
        {recentProjects.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-gray-600">
            <Rocket size={32} className="mb-3 opacity-30" />
            <p className="text-sm">No projects yet.</p>
            <Link to="/dashboard/projects/new" className="mt-2 text-primary-500 hover:underline text-sm">
              Create your first project
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-gray-800">
            {recentProjects.map((project) => (
              <Link
                key={project.id}
                to={`/dashboard/projects/${project.id}`}
                className="flex items-center justify-between px-6 py-3 hover:bg-gray-800/50 transition-colors"
              >
                <div>
                  <p className="text-sm font-medium">{project.name}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{project.framework} · {project.repo_url}</p>
                </div>
                <span className="text-xs text-gray-500 capitalize">{project.status}</span>
              </Link>
            ))}
          </div>
        )}
      </div>

      {usage && (
        <div className="mt-6 bg-gray-900 border border-gray-800 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold flex items-center gap-2">
              <BarChart3 size={16} className="text-blue-400" />
              Usage This Month
            </h2>
            <Link to="/dashboard/usage" className="text-xs text-primary-400 hover:underline flex items-center gap-1">
              Details <ArrowRight size={12} />
            </Link>
          </div>
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: 'Builds', current: usage.usage.builds_this_month.current, limit: usage.usage.builds_this_month.limit },
              { label: 'Deploys', current: usage.usage.deploys_this_month.current, limit: usage.usage.deploys_this_month.limit },
              { label: 'Storage', current: usage.usage.storage_mb.current, limit: usage.usage.storage_mb.limit, suffix: 'MB' },
            ].map(({ label, current, limit, suffix }) => {
              const pct = limit > 0 ? Math.min((current / limit) * 100, 100) : 0
              const color = pct >= 90 ? 'bg-red-500' : pct >= 70 ? 'bg-yellow-500' : 'bg-blue-500'
              return (
                <div key={label}>
                  <div className="flex justify-between text-xs text-gray-400 mb-1">
                    <span>{label}</span>
                    <span>{current}{suffix ? ` ${suffix}` : ''} / {limit}{suffix ? ` ${suffix}` : ''}</span>
                  </div>
                  <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden">
                    <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
          <p className="text-xs text-gray-600 mt-3 text-right capitalize">{usage.plan} Plan · {usage.period}</p>
        </div>
      )}
    </div>
  )
}
