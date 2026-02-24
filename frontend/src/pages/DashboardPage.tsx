import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { FolderGit2, Rocket, CheckCircle, Clock, ArrowRight } from 'lucide-react'
import { api } from '@/lib/api'
import type { Project } from '@/types'

export default function DashboardPage() {
  const { user } = useAuthStore()

  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: () => api.get('/projects').then((r) => r.data),
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
          <Link to="/projects" className="text-xs text-primary-400 hover:underline flex items-center gap-1">
            View all <ArrowRight size={12} />
          </Link>
        </div>
        {recentProjects.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-gray-600">
            <Rocket size={32} className="mb-3 opacity-30" />
            <p className="text-sm">No projects yet.</p>
            <Link to="/projects/new" className="mt-2 text-primary-500 hover:underline text-sm">
              Create your first project
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-gray-800">
            {recentProjects.map((project) => (
              <Link
                key={project.id}
                to={`/projects/${project.id}`}
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
    </div>
  )
}
