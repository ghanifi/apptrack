import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Github, Search, Loader, ArrowRight, ArrowLeft, Check, Rocket,
  Smartphone, Zap, Store, KeyRound, Upload, Shield, ExternalLink,
  Play, CheckCircle2, XCircle, Clock, RefreshCw
} from 'lucide-react'
import { api } from '@/lib/api'
import clsx from 'clsx'
import logoImg from '@/assets/logo.png'
import Confetti from '@/components/ui/Confetti'
import BuildDiagnosisPanel from '@/components/ui/BuildDiagnosisPanel'

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

interface Credential {
  id: string
  provider: string
  key_name: string
  updated_at: string
}

type Step = 'connect' | 'select' | 'detect' | 'preview' | 'credentials' | 'build' | 'deploy'

const STEP_META: Record<Step, { num: number; title: string; icon: React.ComponentType<any> }> = {
  connect: { num: 1, title: 'Connect GitHub', icon: Github },
  select: { num: 2, title: 'Select Repository', icon: Search },
  detect: { num: 3, title: 'Framework Detection', icon: Zap },
  preview: { num: 4, title: 'Project Ready', icon: Smartphone },
  credentials: { num: 5, title: 'Store Credentials', icon: KeyRound },
  build: { num: 6, title: 'Build App', icon: Play },
  deploy: { num: 7, title: 'Deploy to Stores', icon: Store },
}

const STEPS: Step[] = ['connect', 'select', 'detect', 'preview', 'credentials', 'build', 'deploy']

type CredentialTab = 'google_play' | 'app_store' | 'ios_signing'

const STORE_FIELDS: Record<CredentialTab, { provider: string; label: string; description: string; fields: { key_name: string; label: string; placeholder: string; help?: string; type?: string }[] }> = {
  google_play: {
    provider: 'google_play',
    label: 'Google Play',
    description: 'Upload your Android app to the Google Play Store.',
    fields: [
      {
        key_name: 'GOOGLE_PLAY_KEY_JSON',
        label: 'Service Account Key (JSON)',
        placeholder: '{ "type": "service_account", ... }',
        help: 'Go to Google Cloud Console > IAM > Service Accounts > Create Key (JSON). Grant "Service Account User" and "Android Management" roles.',
        type: 'textarea',
      },
    ],
  },
  app_store: {
    provider: 'app_store',
    label: 'App Store Connect',
    description: 'Upload your iOS app to the Apple App Store.',
    fields: [
      {
        key_name: 'APP_STORE_KEY_ID',
        label: 'Key ID',
        placeholder: 'XXXXXXXXXX',
        help: 'Found in App Store Connect > Users and Access > Keys.',
      },
      {
        key_name: 'APP_STORE_ISSUER_ID',
        label: 'Issuer ID',
        placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
        help: 'Shown at the top of the API Keys page in App Store Connect.',
      },
      {
        key_name: 'APP_STORE_PRIVATE_KEY',
        label: 'Private Key (.p8 content)',
        placeholder: '-----BEGIN PRIVATE KEY-----\n...',
        help: 'Download the .p8 file when creating the API key. Paste its full content here.',
        type: 'textarea',
      },
    ],
  },
  ios_signing: {
    provider: 'ios_signing',
    label: 'iOS Signing',
    description: 'Optional here — you can auto-generate certificates later in Settings if you have App Store Connect keys.',
    fields: [
      {
        key_name: 'IOS_CERT_P12_BASE64',
        label: 'Distribution Certificate (.p12, base64)',
        placeholder: 'MIIKYgIBAzCCCi...',
        help: 'Tip: Skip this — go to Settings after setup and use "Auto-Generate" (no Mac needed). Manual: Export .p12 from Keychain Access, then base64 encode it.',
        type: 'textarea',
      },
      {
        key_name: 'IOS_CERT_PASSWORD',
        label: 'Certificate Password',
        placeholder: 'Password used when exporting .p12',
        help: 'Auto-set if you use Auto-Generate in Settings. For manual: the password set when exporting .p12.',
      },
      {
        key_name: 'IOS_PROVISIONING_PROFILE_BASE64',
        label: 'Provisioning Profile (base64)',
        placeholder: 'MIIFfDCCBGSgA...',
        help: 'Auto-generated in Settings if you provide a Bundle ID. Manual: Download from Apple Developer Portal > Profiles, then base64 encode.',
        type: 'textarea',
      },
    ],
  },
}

interface BuildStatus {
  id: string
  status: string
  platform: string
  provider: string
  artifact_url?: string
  started_at?: string
  completed_at?: string
  error_message?: string
  log_output?: string
}

export default function OnboardingPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [step, setStep] = useState<Step>('connect')
  const [search, setSearch] = useState('')
  const [selectedRepo, setSelectedRepo] = useState<GithubRepo | null>(null)
  const [projectId, setProjectId] = useState<string | null>(null)
  const [framework, setFramework] = useState<string>('')
  const [credentialTab, setCredentialTab] = useState<CredentialTab>('google_play')
  const [credentialValues, setCredentialValues] = useState<Record<string, string>>({})
  const [savedFields, setSavedFields] = useState<Record<string, boolean>>({})
  const [buildTriggered, setBuildTriggered] = useState(false)
  const [buildPlatform, setBuildPlatform] = useState<'android' | 'ios' | 'both'>('android')
  const [deployStarted, setDeployStarted] = useState(false)
  const [deployTrack, setDeployTrack] = useState<'internal' | 'beta' | 'production'>('internal')

  const { data: profile } = useQuery({
    queryKey: ['github-profile'],
    queryFn: () => api.get('/github/profile').then((r) => r.data),
  })

  const { data: repos, isLoading: reposLoading } = useQuery<GithubRepo[]>({
    queryKey: ['github-repos'],
    queryFn: () => api.get('/github/repos').then((r) => r.data),
    enabled: step === 'select' && !!profile?.github_connected,
  })

  const { data: credentials = [] } = useQuery<Credential[]>({
    queryKey: ['credentials'],
    queryFn: () => api.get('/credentials').then((r) => r.data),
    enabled: step === 'credentials' || step === 'deploy',
  })

  const { data: buildsResp, refetch: refetchBuilds } = useQuery<{ items: BuildStatus[] }>({
    queryKey: ['project-builds', projectId],
    queryFn: () => api.get('/builds', { params: { project_id: projectId } }).then((r) => r.data),
    enabled: !!projectId && (step === 'build' || step === 'deploy'),
    refetchInterval: step === 'build' && buildTriggered ? 3000 : false,
  })
  const builds = buildsResp?.items ?? []

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

  const saveCredential = useMutation({
    mutationFn: (vars: { provider: string; key_name: string; value: string }) =>
      api.put('/credentials', vars),
    onSuccess: (_, vars) => {
      setSavedFields((s) => ({ ...s, [vars.key_name]: true }))
      setTimeout(() => setSavedFields((s) => ({ ...s, [vars.key_name]: false })), 2000)
      setCredentialValues((v) => ({ ...v, [vars.key_name]: '' }))
      queryClient.invalidateQueries({ queryKey: ['credentials'] })
    },
  })

  const triggerBuild = useMutation({
    mutationFn: (platform: string) =>
      api.post(`/projects/${projectId}/build`, null, { params: { platform } }),
    onSuccess: () => {
      setBuildTriggered(true)
      refetchBuilds()
    },
  })

  const triggerDeploy = useMutation({
    mutationFn: (buildId: string) =>
      api.post(`/deployments/${buildId}/deploy`, { target: googlePlayConnected ? 'google_play' : 'app_store', track: deployTrack }),
    onSuccess: () => {
      setDeployStarted(true)
    },
  })

  const isGithubConnected = profile?.github_connected

  const filteredRepos = repos?.filter(
    (r) => r.full_name.toLowerCase().includes(search.toLowerCase())
  ) ?? []

  const currentIdx = STEPS.indexOf(step)

  const storeSection = STORE_FIELDS[credentialTab]
  const connectedKeys = credentials.filter((c) => c.provider === storeSection.provider).map((c) => c.key_name)
  const googlePlayConnected = credentials.some((c) => c.provider === 'google_play')
  const appStoreConnected = credentials.filter((c) => c.provider === 'app_store').length >= 3
  const anyStoreConnected = googlePlayConnected || appStoreConnected

  const latestBuild = builds.length > 0 ? builds[0] : null
  const buildDone = latestBuild?.status === 'success'
  const buildFailed = latestBuild?.status === 'failed'

  useEffect(() => {
    if (buildDone && step === 'build') {
      // auto-advance not needed, user clicks
    }
  }, [buildDone, step])

  return (
    <div className="min-h-screen bg-gray-950 flex">
      <aside className="w-72 bg-gray-900 border-r border-gray-800 p-8 hidden lg:block">
        <div className="flex items-center gap-2 mb-10">
          <img src={logoImg} alt="AppTrack" className="w-7 h-7 object-contain" />
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
                  aria-label="Search repositories"
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
                    aria-label={`Select repository ${repo.full_name}`}
                    aria-pressed={selectedRepo?.id === repo.id}
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
              <p className="text-gray-400 text-sm mb-2">
                Framework: <span className="text-primary-400 font-medium">{framework}</span>
              </p>
              <p className="text-gray-500 text-xs mb-6">
                {/* Configure store credentials first to enable deploy */}
                Next, add your store credentials so we can publish your app.
              </p>
              <div className="space-y-3">
                <button
                  onClick={() => setStep('credentials')}
                  aria-label="Configure store credentials"
                  className="flex items-center justify-center gap-2 w-full bg-primary-600 hover:bg-primary-700 text-white py-3 rounded-xl font-medium transition-colors"
                >
                  Set Up Store Credentials <KeyRound size={16} />
                </button>
                <button
                  onClick={() => setStep('build')}
                  className="w-full text-sm text-gray-400 hover:text-white py-2 transition-colors"
                >
                  Skip for now, just build
                </button>
              </div>
            </div>
          )}

          {step === 'credentials' && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
              <div className="p-6 border-b border-gray-800">
                <div className="flex items-center gap-3 mb-2">
                  <Shield size={20} className="text-primary-400" />
                  <h2 className="text-xl font-bold">Store Credentials</h2>
                </div>
                <p className="text-gray-400 text-sm">
                  Add your store API keys to publish your app. All credentials are encrypted.
                </p>
              </div>

              <div className="flex border-b border-gray-800">
                {(['google_play', 'app_store', 'ios_signing'] as CredentialTab[]).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setCredentialTab(tab)}
                    className={clsx(
                      'flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2',
                      credentialTab === tab
                        ? 'border-primary-500 text-primary-400 bg-primary-600/5'
                        : 'border-transparent text-gray-500 hover:text-gray-300'
                    )}
                  >
                    {tab === 'ios_signing' ? <Shield size={14} /> : <Store size={14} />}
                    {tab === 'google_play' ? 'Google Play' : tab === 'app_store' ? 'App Store' : 'iOS Signing'}
                    {tab === 'google_play' && googlePlayConnected && <Check size={12} className="text-green-400" />}
                    {tab === 'app_store' && appStoreConnected && <Check size={12} className="text-green-400" />}
                    {tab === 'ios_signing' && credentials.some(c => c.provider === 'ios_signing') && <Check size={12} className="text-green-400" />}
                  </button>
                ))}
              </div>

              <div className="p-5 space-y-4">
                <p className="text-xs text-gray-500">{storeSection.description}</p>

                {storeSection.fields.map((field) => {
                  const isConnected = connectedKeys.includes(field.key_name)
                  return (
                    <div key={field.key_name}>
                      <div className="flex items-center justify-between mb-1.5">
                        <label className="text-xs font-medium text-gray-300">{field.label}</label>
                        {isConnected && (
                          <span className="flex items-center gap-1 text-xs text-green-400">
                            <Check size={10} /> Saved
                          </span>
                        )}
                      </div>
                      {field.help && (
                        <p className="text-xs text-gray-600 mb-2">{field.help}</p>
                      )}
                      {field.type === 'textarea' ? (
                        <textarea
                          value={credentialValues[field.key_name] ?? ''}
                          onChange={(e) => setCredentialValues((v) => ({ ...v, [field.key_name]: e.target.value }))}
                          placeholder={isConnected ? '(saved securely)' : field.placeholder}
                          rows={4}
                          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs font-mono outline-none focus:border-primary-500 transition-colors resize-none"
                        />
                      ) : (
                        <input
                          type="password"
                          value={credentialValues[field.key_name] ?? ''}
                          onChange={(e) => setCredentialValues((v) => ({ ...v, [field.key_name]: e.target.value }))}
                          placeholder={isConnected ? '(saved securely)' : field.placeholder}
                          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors"
                        />
                      )}
                      {credentialValues[field.key_name] && (
                        <button
                          onClick={() => saveCredential.mutate({
                            provider: storeSection.provider,
                            key_name: field.key_name,
                            value: credentialValues[field.key_name],
                          })}
                          disabled={saveCredential.isPending}
                          className={clsx(
                            'mt-2 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                            savedFields[field.key_name]
                              ? 'bg-green-600 text-white'
                              : 'bg-primary-600 hover:bg-primary-700 text-white disabled:opacity-50'
                          )}
                        >
                          {savedFields[field.key_name] ? <><Check size={11} /> Saved</> : <><Upload size={11} /> Save Credential</>}
                        </button>
                      )}
                    </div>
                  )
                })}

                {credentialTab === 'google_play' && (
                  <a
                    href="https://console.cloud.google.com/iam-admin/serviceaccounts"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-xs text-primary-400 hover:text-primary-300 transition-colors"
                  >
                    <ExternalLink size={11} /> Open Google Cloud Console
                  </a>
                )}
                {credentialTab === 'app_store' && (
                  <a
                    href="https://appstoreconnect.apple.com/access/api"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-xs text-primary-400 hover:text-primary-300 transition-colors"
                  >
                    <ExternalLink size={11} /> Open App Store Connect
                  </a>
                )}
                {credentialTab === 'ios_signing' && (
                  <a
                    href="https://developer.apple.com/account/resources/profiles/list"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-xs text-primary-400 hover:text-primary-300 transition-colors"
                  >
                    <ExternalLink size={11} /> Open Apple Developer Portal
                  </a>
                )}
              </div>

              <div className="p-4 border-t border-gray-800 flex gap-3">
                <button
                  onClick={() => setStep('preview')}
                  className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition-colors"
                >
                  <ArrowLeft size={14} /> Back
                </button>
                <button
                  onClick={() => setStep('build')}
                  className="flex-1 flex items-center justify-center gap-2 bg-primary-600 hover:bg-primary-700 text-white py-2.5 rounded-lg text-sm font-medium transition-colors"
                >
                  {anyStoreConnected ? (
                    <>Continue to Build <ArrowRight size={14} /></>
                  ) : (
                    <>Skip, Build Without Deploy <ArrowRight size={14} /></>
                  )}
                </button>
              </div>
            </div>
          )}

          {step === 'build' && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
              <div className="p-6 border-b border-gray-800 text-center">
                <Play size={40} className="mx-auto mb-3 text-primary-400" />
                <h2 className="text-xl font-bold mb-1">Build your app</h2>
                <p className="text-gray-400 text-sm">
                  {buildTriggered
                    ? 'Your build is in progress. This usually takes 2-5 minutes.'
                    : 'Select your target platform and start building.'}
                </p>
              </div>

              {!buildTriggered ? (
                <div className="p-6 space-y-4">
                  <div className="space-y-2">
                    <label className="text-xs font-medium text-gray-400">Target Platform</label>
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { value: 'android' as const, label: 'Android', emoji: '' },
                        { value: 'ios' as const, label: 'iOS', emoji: '' },
                        { value: 'both' as const, label: 'Both', emoji: '' },
                      ].map((opt) => (
                        <button
                          key={opt.value}
                          onClick={() => setBuildPlatform(opt.value)}
                          className={clsx(
                            'py-2.5 rounded-lg text-sm font-medium transition-colors border',
                            buildPlatform === opt.value
                              ? 'border-primary-500 bg-primary-600/10 text-primary-400'
                              : 'border-gray-700 bg-gray-800 text-gray-400 hover:border-gray-600'
                          )}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <button
                      onClick={() => setStep('credentials')}
                      className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition-colors"
                    >
                      <ArrowLeft size={14} /> Back
                    </button>
                    <button
                      onClick={() => {
                        if (buildPlatform === 'both') {
                          triggerBuild.mutate('android')
                          setTimeout(() => triggerBuild.mutate('ios'), 500)
                        } else {
                          triggerBuild.mutate(buildPlatform)
                        }
                      }}
                      disabled={triggerBuild.isPending}
                      className="flex-1 flex items-center justify-center gap-2 bg-primary-600 hover:bg-primary-700 text-white py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                    >
                      {triggerBuild.isPending ? (
                        <><Loader size={14} className="animate-spin" /> Starting...</>
                      ) : (
                        <><Rocket size={14} /> Start Build</>
                      )}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="p-6 space-y-4">
                  <div className="space-y-3">
                    {builds.length > 0 ? builds.map((build) => (
                      <div key={build.id} className="bg-gray-800 rounded-lg p-4">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium capitalize">{build.platform}</span>
                          <span className={clsx(
                            'flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full',
                            build.status === 'success' && 'bg-green-500/10 text-green-400',
                            build.status === 'failed' && 'bg-red-500/10 text-red-400',
                            build.status === 'running' && 'bg-blue-500/10 text-blue-400',
                            build.status === 'queued' && 'bg-yellow-500/10 text-yellow-400',
                          )}>
                            {build.status === 'success' && <CheckCircle2 size={11} />}
                            {build.status === 'failed' && <XCircle size={11} />}
                            {build.status === 'running' && <Loader size={11} className="animate-spin" />}
                            {build.status === 'queued' && <Clock size={11} />}
                            {build.status}
                          </span>
                        </div>
                        {build.status === 'running' && (
                          <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
                            <div className="h-full bg-primary-500 rounded-full animate-pulse" style={{ width: '60%' }} />
                          </div>
                        )}
                        {build.status === 'failed' && (
                          <div className="mt-3">
                            <BuildDiagnosisPanel
                              buildId={build.id}
                              errorMessage={build.error_message}
                              logOutput={build.log_output}
                              onRetry={() => setBuildTriggered(false)}
                            />
                          </div>
                        )}
                      </div>
                    )) : (
                      <div className="flex items-center justify-center gap-2 py-6 text-gray-500 text-sm">
                        <Loader size={14} className="animate-spin" /> Preparing build...
                      </div>
                    )}
                  </div>

                  {buildFailed && !builds.some(b => b.status === 'failed') && (
                    <button
                      onClick={() => {
                        setBuildTriggered(false)
                      }}
                      className="flex items-center justify-center gap-2 w-full bg-gray-800 hover:bg-gray-700 text-white py-2.5 rounded-lg text-sm transition-colors"
                    >
                      <RefreshCw size={14} /> Retry Build
                    </button>
                  )}

                  {buildDone && (
                    <button
                      onClick={() => setStep('deploy')}
                      className="flex items-center justify-center gap-2 w-full bg-green-600 hover:bg-green-700 text-white py-3 rounded-xl font-medium transition-colors"
                    >
                      Deploy to Stores <ArrowRight size={16} />
                    </button>
                  )}

                  {buildDone && (
                    <button
                      onClick={() => navigate(`/dashboard/projects/${projectId}`)}
                      className="w-full text-sm text-gray-400 hover:text-white py-2 transition-colors text-center"
                    >
                      Go to project details instead
                    </button>
                  )}
                </div>
              )}
            </div>
          )}

          {step === 'deploy' && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 text-center">
              {!deployStarted ? (
                <>
                  <Store size={48} className="mx-auto mb-4 text-green-400" />
                  <h2 className="text-xl font-bold mb-2">Your app is ready to publish!</h2>
                  <p className="text-gray-400 text-sm mb-6">
                    {anyStoreConnected
                      ? 'Deploy your build to the app stores with one click.'
                      : 'Add store credentials first to deploy, or go to your project.'}
                  </p>
                  <div className="space-y-3">
                    {anyStoreConnected && (
                      <div className="mt-4">
                        <label className="block text-sm text-gray-400 mb-1">Deploy Track</label>
                        <select
                          value={deployTrack}
                          onChange={e => setDeployTrack(e.target.value as 'internal' | 'beta' | 'production')}
                          aria-label="Deploy track"
                          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white"
                        >
                          <option value="internal">Internal Testing</option>
                          <option value="beta">Beta / TestFlight</option>
                          <option value="production">⚠️ Production (Canlı)</option>
                        </select>
                      </div>
                    )}
                    {anyStoreConnected && latestBuild && (
                      <button
                        onClick={() => triggerDeploy.mutate(latestBuild.id)}
                        disabled={triggerDeploy.isPending}
                        className="flex items-center justify-center gap-2 w-full bg-green-600 hover:bg-green-700 text-white py-3 rounded-xl font-medium transition-colors disabled:opacity-50"
                      >
                        {triggerDeploy.isPending ? (
                          <><Loader size={16} className="animate-spin" /> Deploying...</>
                        ) : (
                          <><Rocket size={16} /> Publish to Stores</>
                        )}
                      </button>
                    )}
                    {!anyStoreConnected && (
                      <button
                        onClick={() => setStep('credentials')}
                        className="flex items-center justify-center gap-2 w-full bg-primary-600 hover:bg-primary-700 text-white py-3 rounded-xl font-medium transition-colors"
                      >
                        <KeyRound size={16} /> Add Store Credentials
                      </button>
                    )}
                    <button
                      onClick={() => navigate(`/dashboard/projects/${projectId}`)}
                      className="w-full text-sm text-gray-400 hover:text-white py-2 transition-colors"
                    >
                      Go to project dashboard
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <Confetti duration={5000} />
                  <Rocket size={48} className="mx-auto mb-4 text-primary-400 animate-bounce" />
                  <h2 className="text-xl font-bold mb-2">Your app is on the way to the stores!</h2>
                  <p className="text-gray-400 text-sm mb-2">
                    Store review may take a few hours. We'll notify you once it's live.
                  </p>
                  <div className="bg-gray-800 rounded-lg p-4 my-6 text-left space-y-2">
                    {googlePlayConnected && (
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-300">Google Play</span>
                        <span className="flex items-center gap-1 text-yellow-400 text-xs">
                          <Clock size={11} /> In Review
                        </span>
                      </div>
                    )}
                    {appStoreConnected && (
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-300">App Store</span>
                        <span className="flex items-center gap-1 text-yellow-400 text-xs">
                          <Clock size={11} /> Processing
                        </span>
                      </div>
                    )}
                  </div>
                  <div className="space-y-3">
                    <button
                      onClick={() => navigate(`/dashboard/projects/${projectId}`)}
                      className="flex items-center justify-center gap-2 w-full bg-primary-600 hover:bg-primary-700 text-white py-3 rounded-xl font-medium transition-colors"
                    >
                      View Deployment Status <ArrowRight size={16} />
                    </button>
                    <button
                      onClick={() => navigate('/dashboard')}
                      className="w-full text-sm text-gray-400 hover:text-white py-2 transition-colors"
                    >
                      Go to Dashboard
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
