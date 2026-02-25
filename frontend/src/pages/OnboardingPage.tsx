import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Github, Search, Loader, ArrowRight, ArrowLeft, Check, Rocket, Smartphone, Zap, Store } from 'lucide-react'
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
}

type Step = 'connect' | 'select' | 'detect' | 'preview' | 'build'

const STEP_META: Record<Step, { num: number; title: string; icon: React.FC<{ size?: number; className?: string }> }> = {
  connect: { num: 1, title: 'Connect GitHub', icon: Github },
  select: { num: 2, title: 'Select Repository', icon: Search },
  detect: { num: 3, title: 'Framework Detection', icon: Zap },
  preview: { num: 4, title: 'Preview', icon: Smartphone },
  build: { num: 5, title: 'Build & Deploy', icon: Store },
}

const STEPS: Step[] = ['connect', 'select', 'detect', 'preview', 'build']

export default function OnboardingPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState<Step>('connect')
  const [search, setSearch] = useState('')
  const [selectedRepo, setSelectedRepo] = useState<GithubRepo | null>(null)
  const [projectId, setProjectId] = useState<string | null>(null)
  const [framework, setFramework] = useState<string>('')

  const { data: profile } = useQuery({
    queryKey: ['github-profile'],
    queryFn: () => api.get('/github/profile').then((r) => r.data),
  })

  const { data: repos, isLoading: reposLoading } = useQuery<GithubRepo[]>({
    queryKey: ['github-repos'],
    queryFn: () => api.get('/github/repos').then((r) => r.data),
    enabled: step === 'select' && !!profile?.github_connected,
  })

  const createProject = useMutation({
    mutationFn: (data: { name: string; repo_url: string; branch: string }) => api.post('/projects', data),
    onSuccess: (res) => {
      setProjectId(res.data.id)
      setFramework(res.data.framework || 'detecting...')
      setStep('detect')
      setTimeout(() => {
        setFramework(res.data.framework || 'react-native')
        setStep('preview')
      }, 2000)
    },
  })

  const isGithubConnected = profile?.github_connected

  const filteredRepos = repos?.filter(
    (r) => r.full_name.toLowerCase().includes(search.toLowerCase())
  ) ?? []

  const currentIdx = STEPS.indexOf(step)

  return (
    <div className="min-h-screen bg-gray-950 flex">
      <aside className="w-72 bg-gray-900 border-r border-gray-800 p-8 hidden lg:block">
        <div className="flex items-center gap-2 mb-10">
          <Rocket size={22} className="text-primary-500" />
          <span className="font-bold text-lg">AppTrack</span>
        </div>
        <div className="space-y-1">
          {STEPS.map((s, i) => {
            const meta = STEP_META[s]
            const Icon = meta.icon
            const isDone = i < currentIdx
            const isCurrent = s === step
            return (
              <div
                key={s}
                className={clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors',
                  isCurrent && 'bg-primary-600/10 text-primary-400 font-medium',
                  isDone && 'text-green-400',
                  !isCurrent && !isDone && 'text-gray-600'
                )}
              >
                {isDone ? (
                  <Check size={16} className="text-green-400" />
                ) : (
                  <Icon size={16} />
                )}
                <span>{meta.title}</span>
              </div>
            )
          })}
        </div>
      </aside>

      <main className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-lg">
          <div className="flex items-center gap-2 text-xs text-gray-500 mb-6">
            Step {currentIdx + 1} of {STEPS.length}
            <div className="flex-1 h-1 bg-gray-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-primary-500 rounded-full transition-all duration-500"
                style={{ width: `${((currentIdx + 1) / STEPS.length) * 100}%` }}
              />
            </div>
          </div>

          {step === 'connect' && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 text-center">
              <Github size={48} className="mx-auto mb-4 text-gray-400" />
              <h2 className="text-2xl font-bold mb-2">Connect your GitHub</h2>
              <p className="text-gray-400 text-sm mb-8">We'll import your repositories so you can select one to build.</p>
              {isGithubConnected ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-center gap-2 text-green-400 text-sm">
                    <Check size={16} /> GitHub connected
                  </div>
                  <button
                    onClick={() => setStep('select')}
                    className="flex items-center justify-center gap-2 w-full bg-primary-600 hover:bg-primary-700 text-white py-3 rounded-xl font-medium transition-colors"
                  >
                    Continue <ArrowRight size={16} />
                  </button>
                </div>
              ) : (
                <a
                  href="/api/auth/github"
                  className="flex items-center justify-center gap-2 w-full bg-gray-800 hover:bg-gray-700 text-white py-3 rounded-xl font-medium transition-colors"
                >
                  <Github size={16} /> Connect GitHub
                </a>
              )}
            </div>
          )}

          {step === 'select' && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
              <div className="p-6 border-b border-gray-800">
                <h2 className="text-xl font-bold mb-1">Select a repository</h2>
                <p className="text-gray-400 text-sm">Choose the project you want to build and deploy.</p>
              </div>
              <div className="p-3 border-b border-gray-800 relative">
                <Search size={14} className="absolute left-6 top-1/2 -translate-y-1/2 text-gray-500" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search repos..."
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-8 pr-3 py-2 text-sm outline-none focus:border-primary-500"
                />
              </div>
              <div className="max-h-72 overflow-y-auto divide-y divide-gray-800">
                {reposLoading ? (
                  <div className="flex items-center justify-center gap-2 py-10 text-gray-500 text-sm">
                    <Loader size={16} className="animate-spin" /> Loading...
                  </div>
                ) : filteredRepos.map((repo) => (
                  <button
                    key={repo.id}
                    onClick={() => setSelectedRepo(repo)}
                    className={clsx(
                      'w-full text-left px-5 py-3 hover:bg-gray-800 transition-colors',
                      selectedRepo?.id === repo.id && 'bg-primary-600/10 border-l-2 border-primary-500'
                    )}
                  >
                    <span className="text-sm font-medium">{repo.full_name}</span>
                    {repo.description && <p className="text-xs text-gray-500 mt-0.5 truncate">{repo.description}</p>}
                  </button>
                ))}
              </div>
              {selectedRepo && (
                <div className="p-4 border-t border-gray-800 flex gap-3">
                  <button
                    onClick={() => setStep('connect')}
                    className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition-colors"
                  >
                    <ArrowLeft size={14} /> Back
                  </button>
                  <button
                    onClick={() => {
                      createProject.mutate({
                        name: selectedRepo.name,
                        repo_url: selectedRepo.clone_url,
                        branch: selectedRepo.default_branch,
                      })
                    }}
                    disabled={createProject.isPending}
                    className="flex-1 flex items-center justify-center gap-2 bg-primary-600 hover:bg-primary-700 text-white py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                  >
                    {createProject.isPending ? <><Loader size={14} className="animate-spin" /> Creating...</> : <>Import & Analyze <ArrowRight size={14} /></>}
                  </button>
                </div>
              )}
            </div>
          )}

          {step === 'detect' && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 text-center">
              <Loader size={48} className="animate-spin mx-auto mb-4 text-primary-400" />
              <h2 className="text-xl font-bold mb-2">Analyzing your project...</h2>
              <p className="text-gray-400 text-sm mb-4">Detecting framework, dependencies, and build requirements.</p>
              <div className="bg-gray-800 rounded-lg p-4 text-left text-sm font-mono text-gray-400 space-y-1">
                <p>&gt; Cloning {selectedRepo?.full_name}...</p>
                <p>&gt; Scanning project structure...</p>
                <p>&gt; Detected: <span className="text-primary-400">{framework}</span></p>
              </div>
            </div>
          )}

          {step === 'preview' && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 text-center">
              <Smartphone size={48} className="mx-auto mb-4 text-green-400" />
              <h2 className="text-xl font-bold mb-2">Project ready!</h2>
              <p className="text-gray-400 text-sm mb-6">
                Framework: <span className="text-primary-400 font-medium">{framework}</span>
              </p>
              <div className="space-y-3">
                <button
                  onClick={() => setStep('build')}
                  className="flex items-center justify-center gap-2 w-full bg-primary-600 hover:bg-primary-700 text-white py-3 rounded-xl font-medium transition-colors"
                >
                  Start First Build <Rocket size={16} />
                </button>
                <button
                  onClick={() => navigate(`/projects/${projectId}`)}
                  className="w-full text-sm text-gray-400 hover:text-white py-2 transition-colors"
                >
                  Go to project details
                </button>
              </div>
            </div>
          )}

          {step === 'build' && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 text-center">
              <Rocket size={48} className="mx-auto mb-4 text-primary-400" />
              <h2 className="text-xl font-bold mb-2">You're all set!</h2>
              <p className="text-gray-400 text-sm mb-6">
                Your project is ready. Head to the project page to trigger builds and deploy to stores.
              </p>
              <div className="space-y-3">
                <button
                  onClick={() => navigate(`/projects/${projectId}`)}
                  className="flex items-center justify-center gap-2 w-full bg-primary-600 hover:bg-primary-700 text-white py-3 rounded-xl font-medium transition-colors"
                >
                  Go to Project <ArrowRight size={16} />
                </button>
                <button
                  onClick={() => navigate('/settings')}
                  className="w-full text-sm text-gray-400 hover:text-white py-2 transition-colors"
                >
                  Configure store credentials first
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
