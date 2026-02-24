import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Github, Globe, GitBranch, Loader, Search } from 'lucide-react'
import { api } from '@/lib/api'
import clsx from 'clsx'

interface GithubRepo {
  id: number
  name: string
  full_name: string
  clone_url: string
  default_branch: string
  private: boolean
  language: string | null
  description: string | null
  updated_at: string
}

type Mode = 'picker' | 'manual'

export default function NewProjectPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<Mode>('picker')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<GithubRepo | null>(null)
  const [form, setForm] = useState({ name: '', repo_url: '', branch: 'main' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const { data: repos, isLoading: reposLoading, isError: reposError } = useQuery<GithubRepo[]>({
    queryKey: ['github-repos'],
    queryFn: () => api.get('/github/repos').then((r) => r.data),
    enabled: mode === 'picker',
    retry: false,
  })

  const filteredRepos = repos?.filter(
    (r) =>
      r.full_name.toLowerCase().includes(search.toLowerCase()) ||
      r.description?.toLowerCase().includes(search.toLowerCase())
  ) ?? []

  const handleSelectRepo = (repo: GithubRepo) => {
    setSelected(repo)
    setForm({ name: repo.name, repo_url: repo.clone_url, branch: repo.default_branch })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.repo_url) { setError('Please select or enter a repository.'); return }
    setError('')
    setLoading(true)
    try {
      await api.post('/projects', form)
      navigate('/projects')
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(message ?? 'Failed to create project')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-8 max-w-2xl">
      <button
        onClick={() => navigate('/projects')}
        className="flex items-center gap-2 text-sm text-gray-400 hover:text-white mb-6 transition-colors"
      >
        <ArrowLeft size={16} />
        Back to Projects
      </button>
      <h1 className="text-2xl font-bold mb-6">New Project</h1>

      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setMode('picker')}
          className={clsx('flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
            mode === 'picker' ? 'bg-primary-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white')}
        >
          <Github size={14} /> Import from GitHub
        </button>
        <button
          onClick={() => setMode('manual')}
          className={clsx('flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
            mode === 'manual' ? 'bg-primary-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white')}
        >
          <Globe size={14} /> Manual URL
        </button>
      </div>

      {mode === 'picker' && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl mb-4">
          {reposLoading ? (
            <div className="flex items-center justify-center gap-2 py-10 text-gray-500 text-sm">
              <Loader size={16} className="animate-spin" /> Loading repositories...
            </div>
          ) : reposError ? (
            <div className="p-6 text-center text-sm text-gray-500">
              <Github size={24} className="mx-auto mb-2 opacity-30" />
              GitHub not connected.{' '}
              <a href="/settings" className="text-primary-400 hover:underline">Connect in Settings</a>
            </div>
          ) : (
            <>
              <div className="p-3 border-b border-gray-800 relative">
                <Search size={14} className="absolute left-6 top-1/2 -translate-y-1/2 text-gray-500" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search repositories..."
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-8 pr-3 py-2 text-sm outline-none focus:border-primary-500"
                />
              </div>
              <div className="max-h-64 overflow-y-auto divide-y divide-gray-800">
                {filteredRepos.length === 0 ? (
                  <p className="text-center text-gray-500 text-sm py-6">No repositories found.</p>
                ) : filteredRepos.map((repo) => (
                  <button
                    key={repo.id}
                    onClick={() => handleSelectRepo(repo)}
                    className={clsx(
                      'w-full text-left px-5 py-3 hover:bg-gray-800 transition-colors',
                      selected?.id === repo.id && 'bg-primary-600/10 border-l-2 border-primary-500'
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">{repo.full_name}</span>
                      <div className="flex items-center gap-2 text-xs text-gray-500">
                        {repo.language && <span>{repo.language}</span>}
                        {repo.private && <span className="bg-gray-700 px-1.5 py-0.5 rounded">Private</span>}
                      </div>
                    </div>
                    {repo.description && <p className="text-xs text-gray-500 mt-0.5 truncate">{repo.description}</p>}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {(selected || mode === 'manual') && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Project Name</label>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
                placeholder="My Awesome App"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Repository URL</label>
              <input
                value={form.repo_url}
                onChange={(e) => setForm({ ...form, repo_url: e.target.value })}
                required
                readOnly={mode === 'picker' && !!selected}
                placeholder="https://github.com/username/repo"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors read-only:opacity-60"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1 flex items-center gap-1">
                <GitBranch size={12} /> Branch
              </label>
              <input
                value={form.branch}
                onChange={(e) => setForm({ ...form, branch: e.target.value })}
                required
                placeholder="main"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors"
              />
            </div>
            {error && <p className="text-red-400 text-sm">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white rounded-lg py-2 text-sm font-medium transition-colors"
            >
              {loading ? 'Creating...' : 'Create Project'}
            </button>
          </form>
        </div>
      )}
    </div>
  )
}
