import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Plus, FolderGit2, GitBranch } from 'lucide-react'
import { api } from '@/lib/api'
import { frameworkLabel } from '@/lib/labels'
import type { Project } from '@/types'

const frameworkColors: Record<string, string> = {
  flutter: 'bg-blue-500/20 text-blue-300',
  react_native: 'bg-cyan-500/20 text-cyan-300',
  expo: 'bg-violet-500/20 text-violet-300',
  swift: 'bg-orange-500/20 text-orange-300',
  kotlin: 'bg-green-500/20 text-green-300',
  capacitor: 'bg-sky-500/20 text-sky-300',
  ionic: 'bg-indigo-500/20 text-indigo-300',
  cordova: 'bg-teal-500/20 text-teal-300',
  pwa: 'bg-amber-500/20 text-amber-300',
  unknown: 'bg-gray-500/20 text-gray-400',
}

const statusColors: Record<string, string> = {
  pending: 'bg-gray-500/20 text-gray-400',
  analyzing: 'bg-yellow-500/20 text-yellow-300',
  ready: 'bg-green-500/20 text-green-300',
  building: 'bg-blue-500/20 text-blue-300',
  deploying: 'bg-purple-500/20 text-purple-300',
  error: 'bg-red-500/20 text-red-400',
}

export default function ProjectsPage() {
  const { data: projects = [], isLoading } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: () => api.get('/projects').then((r) => r.data.items ?? r.data),
  })

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold">Projects</h1>
          <p className="text-gray-400 text-sm mt-1">{projects.length} project(s)</p>
        </div>
        <Link
          to="/dashboard/projects/new"
          className="flex items-center gap-2 bg-primary-600 hover:bg-primary-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          <Plus size={16} />
          New Project
        </Link>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16 text-gray-500 text-sm">Loading...</div>
      ) : projects.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl flex flex-col items-center justify-center py-16 text-gray-600">
          <FolderGit2 size={40} className="mb-4 text-primary-500/60" />
          <p className="text-base font-medium text-gray-300">No projects yet</p>
          <p className="text-sm text-gray-500 mt-1 mb-4">Connect a repo and ship your first build in minutes.</p>
          <Link
            to="/dashboard/projects/new"
            className="flex items-center gap-2 bg-primary-600 hover:bg-primary-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            <Plus size={16} />
            Create your first project
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {projects.map((project) => (
            <Link key={project.id} to={`/dashboard/projects/${project.id}`} className="bg-gray-900 border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition-colors block">
              <div className="flex items-start justify-between mb-3">
                <h3 className="font-semibold truncate pr-2">{project.name}</h3>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${statusColors[project.status]}`}>
                  {project.status}
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs text-gray-500 mb-3">
                <GitBranch size={12} />
                <span className="truncate">{project.repo_url}</span>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${frameworkColors[project.framework]}`}>
                {frameworkLabel(project.framework)}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
