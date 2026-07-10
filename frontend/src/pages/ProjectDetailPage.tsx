import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, RefreshCw, Play, GitBranch, Clock, CheckCircle,
  XCircle, Loader, Package, Rocket, ExternalLink, QrCode,
  Upload, Eye, ChevronDown, ChevronUp, Store, Radio,
  Shield, AlertTriangle,
} from 'lucide-react'
import { api } from '@/lib/api'
import type { Project, Build, Deployment } from '@/types'
import BuildDiagnosisPanel from '@/components/ui/BuildDiagnosisPanel'
import LiveBuildProgress from '@/components/LiveBuildProgress'
import BuildRunnerCard from '@/components/BuildRunnerCard'
import ProjectPipeline from '@/components/ProjectPipeline'
import RolloutPanel from '@/components/RolloutPanel'
import { frameworkLabel, platformLabel, providerLabel } from '@/lib/labels'
import clsx from 'clsx'

const frameworkColors: Record<string, string> = {
  flutter: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  react_native: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  expo: 'bg-violet-500/20 text-violet-300 border-violet-500/30',
  swift: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
  kotlin: 'bg-green-500/20 text-green-300 border-green-500/30',
  capacitor: 'bg-sky-500/20 text-sky-300 border-sky-500/30',
  ionic: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
  cordova: 'bg-teal-500/20 text-teal-300 border-teal-500/30',
  pwa: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  unknown: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
}

const statusConfig: Record<string, { color: string; icon: React.FC<{ size?: number | string; className?: string }> }> = {
  pending: { color: 'text-gray-400', icon: Clock },
  analyzing: { color: 'text-yellow-400', icon: Loader },
  ready: { color: 'text-green-400', icon: CheckCircle },
  building: { color: 'text-blue-400', icon: Loader },
  deploying: { color: 'text-purple-400', icon: Rocket },
  error: { color: 'text-red-400', icon: XCircle },
}

const buildStatusColors: Record<string, string> = {
  queued: 'bg-gray-500/20 text-gray-300',
  running: 'bg-blue-500/20 text-blue-300',
  success: 'bg-green-500/20 text-green-300',
  failed: 'bg-red-500/20 text-red-400',
}

const deployStatusColors: Record<string, string> = {
  pending: 'bg-gray-500/20 text-gray-300',
  uploading: 'bg-blue-500/20 text-blue-300',
  in_review: 'bg-yellow-500/20 text-yellow-300',
  published: 'bg-green-500/20 text-green-300',
  canary: 'bg-orange-500/20 text-orange-300',
  rolled_back: 'bg-red-500/20 text-red-300',
  failed: 'bg-red-500/20 text-red-400',
}

function DeployModal({
  build,
  onClose,
}: {
  build: Build
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const { id } = useParams<{ id: string }>()
  const [target, setTarget] = useState<'google_play' | 'app_store'>('google_play')
  const [track, setTrack] = useState('internal')
  const [packageName, setPackageName] = useState('')

  const deployMutation = useMutation({
    mutationFn: () =>
      api.post(`/deployments/${build.id}/deploy`, { target, track, package_name: packageName }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects', id] })
      queryClient.invalidateQueries({ queryKey: ['deployments', id] })
      onClose()
    },
  })

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-md p-6">
        <h3 className="text-lg font-semibold mb-4">Deploy to Store</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Target Store</label>
            <div className="grid grid-cols-2 gap-2">
              {(['google_play', 'app_store'] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTarget(t)}
                  className={clsx(
                    'px-3 py-2 rounded-lg text-sm font-medium border transition-colors',
                    target === t
                      ? 'bg-primary-600 border-primary-500 text-white'
                      : 'bg-gray-800 border-gray-700 text-gray-300 hover:border-gray-600'
                  )}
                >
                  {t === 'google_play' ? 'Google Play' : 'App Store'}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Track</label>
            <select
              value={track}
              onChange={(e) => setTrack(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
            >
              <option value="internal">Internal Testing</option>
              <option value="alpha">Closed Testing (Alpha)</option>
              <option value="beta">Open Testing (Beta)</option>
              <option value="production">Production</option>
            </select>
          </div>
          {target === 'google_play' && (
            <div>
              <label className="block text-sm text-gray-400 mb-1">Package Name</label>
              <input
                value={packageName}
                onChange={(e) => setPackageName(e.target.value)}
                placeholder="com.example.app"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
              />
            </div>
          )}
          {deployMutation.isError && (
            <p className="text-red-400 text-xs">
              {(deployMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Deploy failed'}
            </p>
          )}
          <div className="flex gap-2 pt-2">
            <button
              onClick={onClose}
              className="flex-1 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-sm rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => deployMutation.mutate()}
              disabled={deployMutation.isPending}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white text-sm rounded-lg transition-colors"
            >
              {deployMutation.isPending ? <Loader size={14} className="animate-spin" /> : <Upload size={14} />}
              Deploy
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function ComplianceChecklist({ projectId }: { projectId: string }) {
  const [expanded, setExpanded] = useState(false)
  const { data, isLoading } = useQuery<{
    ready_to_publish: boolean
    summary: { total: number; passed: number; warnings: number; failed: number }
    checks: Array<{
      id: string; platform: string; category: string; title: string
      status: 'pass' | 'fail' | 'warning'; message: string; fix_url?: string
    }>
  }>({
    queryKey: ['compliance', projectId],
    queryFn: () => api.get(`/projects/${projectId}/compliance-checklist`).then(r => r.data),
    enabled: expanded,
    staleTime: 30_000,
  })

  const statusIcon = (s: string) => {
    if (s === 'pass') return <CheckCircle size={14} className="text-green-400" />
    if (s === 'fail') return <XCircle size={14} className="text-red-400" />
    return <AlertTriangle size={14} className="text-yellow-400" />
  }

  return (
    <div className="bg-gray-800/50 rounded-lg border border-gray-700/50 p-4 mb-4">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between w-full text-left"
      >
        <div className="flex items-center gap-2">
          <Shield size={16} className="text-blue-400" />
          <span className="text-sm font-semibold">2026 Store Compliance Checklist</span>
          {data && (
            <span className={clsx(
              'text-xs px-2 py-0.5 rounded-full',
              data.ready_to_publish
                ? 'bg-green-500/20 text-green-300'
                : 'bg-red-500/20 text-red-300'
            )}>
              {data.ready_to_publish ? 'Ready' : `${data.summary.failed} issue(s)`}
            </span>
          )}
        </div>
        {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>

      {expanded && (
        <div className="mt-3 space-y-2">
          {isLoading && <p className="text-xs text-gray-500">Loading checks...</p>}
          {data?.checks.map(check => (
            <div key={check.id} className="flex items-start gap-2 text-xs">
              {statusIcon(check.status)}
              <div className="flex-1">
                <span className="font-medium text-gray-200">{check.title}</span>
                <span className="text-gray-500 ml-1">({check.platform})</span>
                <p className="text-gray-400 mt-0.5">{check.message}</p>
              </div>
              {check.fix_url && check.status === 'fail' && (
                <a href={check.fix_url} className="text-blue-400 hover:underline shrink-0">Fix</a>
              )}
            </div>
          ))}
          {data && (
            <div className="pt-2 border-t border-gray-700/50 text-xs text-gray-500">
              {data.summary.passed}/{data.summary.total} passed
              {data.summary.warnings > 0 && ` | ${data.summary.warnings} warning(s)`}
              {data.summary.failed > 0 && ` | ${data.summary.failed} failed`}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function DeploymentHistory({ deployments, projectId }: { deployments: Deployment[]; projectId: string }) {
  const queryClient = useQueryClient()

  const canaryMutation = useMutation({
    mutationFn: (deploymentId: string) => api.post(`/deployments/${deploymentId}/canary`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['deployments', projectId] }),
  })

  const promoteMutation = useMutation({
    mutationFn: (deploymentId: string) => api.post(`/deployments/${deploymentId}/promote`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['deployments', projectId] }),
  })

  const rollbackMutation = useMutation({
    mutationFn: (deploymentId: string) => api.post(`/deployments/${deploymentId}/rollback`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['deployments', projectId] }),
  })

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl">
      <div className="flex items-center gap-2 px-5 py-4 border-b border-gray-800">
        <Rocket size={15} />
        <h2 className="text-sm font-semibold">Deployment History</h2>
      </div>
      <div className="divide-y divide-gray-800">
        {deployments.map((dep) => (
          <div key={dep.id} className="flex items-center justify-between px-5 py-3">
            <div className="flex items-center gap-4">
              <span className={clsx('text-xs px-2 py-0.5 rounded-full font-medium', deployStatusColors[dep.status] ?? 'bg-gray-500/20 text-gray-400')}>
                {dep.status === 'canary' ? 'Canary' : dep.status}
              </span>
              <div>
                <p className="text-sm font-medium capitalize">
                  {dep.target === 'google_play' ? 'Google Play' : 'App Store'} · {dep.track}
                </p>
                <p className="text-xs text-gray-500">{new Date(dep.created_at).toLocaleString()}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {(dep.status === 'pending' || dep.status === 'published') && (
                <button
                  onClick={() => canaryMutation.mutate(dep.id)}
                  disabled={canaryMutation.isPending}
                  className="text-xs px-2 py-1 bg-yellow-600/20 hover:bg-yellow-600/30 text-yellow-300 border border-yellow-500/30 rounded-lg transition-colors"
                >
                  Canary
                </button>
              )}
              {dep.status === 'canary' && (
                <>
                  <button
                    onClick={() => promoteMutation.mutate(dep.id)}
                    disabled={promoteMutation.isPending}
                    className="text-xs px-2 py-1 bg-green-600/20 hover:bg-green-600/30 text-green-300 border border-green-500/30 rounded-lg transition-colors"
                  >
                    Promote
                  </button>
                  <button
                    onClick={() => rollbackMutation.mutate(dep.id)}
                    disabled={rollbackMutation.isPending}
                    className="text-xs px-2 py-1 bg-red-600/20 hover:bg-red-600/30 text-red-300 border border-red-500/30 rounded-lg transition-colors"
                  >
                    Rollback
                  </button>
                </>
              )}
              {(dep.status === 'published' || dep.status === 'pending') && (
                <button
                  onClick={() => rollbackMutation.mutate(dep.id)}
                  disabled={rollbackMutation.isPending}
                  className="text-xs px-2 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg transition-colors"
                >
                  Rollback
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [deployBuild, setDeployBuild] = useState<Build | null>(null)
  const [showAllBuilds, setShowAllBuilds] = useState(false)
  const [expandedBuildId, setExpandedBuildId] = useState<string | null>(null)

  const { data: project, isLoading } = useQuery<Project & { builds: Build[] }>({
    queryKey: ['projects', id],
    queryFn: () => api.get(`/projects/${id}`).then((r) => r.data),
    refetchInterval: (query) => {
      const s = query.state.data?.status
      return s === 'analyzing' || s === 'building' || s === 'deploying' ? 3000 : false
    },
  })

  const { data: deployments = [] } = useQuery<Deployment[]>({
    queryKey: ['deployments', id],
    queryFn: () => api.get(`/deployments/project/${id}`).then((r) => r.data),
    refetchInterval: (query) => {
      const hasActive = (query.state.data as Deployment[] | undefined)?.some(
        (d) => d.status === 'pending' || d.status === 'uploading'
      )
      return hasActive ? 5000 : false
    },
  })

  const { data: preview } = useQuery({
    queryKey: ['preview', id],
    queryFn: () => api.get(`/preview/${id}`).then((r) => r.data).catch(() => null),
    enabled: project?.status === 'ready',
    retry: false,
  })

  const syncMutation = useMutation({
    mutationFn: () => api.post(`/projects/${id}/sync`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects', id] }),
  })

  const buildMutation = useMutation({
    mutationFn: (platform: string) => api.post(`/projects/${id}/build?platform=${platform}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects', id] }),
  })

  if (isLoading) {
    return (
      <div className="p-8 flex items-center gap-3 text-gray-500">
        <Loader size={18} className="animate-spin" />
        <span className="text-sm">Loading project...</span>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="p-8">
        <p className="text-gray-400">Project not found.</p>
        <Link to="/dashboard/projects" className="text-primary-500 hover:underline text-sm mt-2 inline-block">Back to Projects</Link>
      </div>
    )
  }

  const StatusIcon = statusConfig[project.status]?.icon ?? Clock
  const statusColor = statusConfig[project.status]?.color ?? 'text-gray-400'
  const isAnalyzing = project.status === 'analyzing'
  const isBuilding = project.status === 'building'
  // error: son build başarısız demektir — yeniden denemek geçerli bir eylemdir,
  // butonları gizlemek kullanıcıyı diagnosis panelindeki Retry'a mahkum ediyordu.
  const canBuild = ['ready', 'error'].includes(project.status) && project.framework !== 'unknown'
  const visibleBuilds = showAllBuilds ? (project.builds ?? []) : (project.builds ?? []).slice(0, 5)
  // En yeni devam eden build — canlı ilerleme paneli bunu izler
  const activeBuild = (project.builds ?? []).find((b) => b.status === 'queued' || b.status === 'running')
  // En yeni başarılı build — kademeli yayın (staged rollout) paneli bunu hedefler
  const latestSuccessBuild = (project.builds ?? []).find((b) => b.status === 'success')

  return (
    <div className="p-8 max-w-4xl">
      {deployBuild && <DeployModal build={deployBuild} onClose={() => setDeployBuild(null)} />}

      <button
        onClick={() => navigate('/dashboard/projects')}
        className="flex items-center gap-2 text-sm text-gray-400 hover:text-white mb-6 transition-colors"
      >
        <ArrowLeft size={16} />
        Back to Projects
      </button>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{project.name}</h1>
          <div className="flex items-center gap-2 mt-1 text-sm text-gray-500">
            <GitBranch size={14} />
            <a href={project.repo_url} target="_blank" rel="noreferrer" className="hover:text-gray-300 flex items-center gap-1">
              {project.repo_url}
              <ExternalLink size={11} />
            </a>
            <span className="text-gray-700">·</span>
            <span>{project.branch}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
        <button
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending || isAnalyzing}
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-sm transition-colors"
        >
          <RefreshCw size={14} className={syncMutation.isPending || isAnalyzing ? 'animate-spin' : ''} />
          Re-sync
        </button>
        <Link
          to={`/dashboard/projects/${id}/store`}
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-primary-600/20 hover:bg-primary-600/30 border border-primary-500/30 text-primary-300 text-sm transition-colors"
        >
          <Store size={14} />
          Store Config
        </Link>
        {['capacitor', 'ionic', 'cordova'].includes(project?.framework ?? '') && (
          <Link
            to={`/dashboard/projects/${id}/ota`}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-green-600/20 hover:bg-green-600/30 border border-green-500/30 text-green-300 text-sm transition-colors"
          >
            <Radio size={14} />
            Live Updates
          </Link>
        )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-500 mb-2">Status</p>
          <div className={clsx('flex items-center gap-2 font-medium', statusColor)}>
            <StatusIcon size={16} className={isAnalyzing || isBuilding ? 'animate-spin' : ''} />
            <span className="capitalize">{project.status}</span>
          </div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-500 mb-2">Framework</p>
          <span className={clsx('text-sm px-2 py-0.5 rounded-full border font-medium', frameworkColors[project.framework])}>
            {frameworkLabel(project.framework)}
          </span>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-500 mb-2">Builds / Deploys</p>
          <p className="text-2xl font-bold">{project.builds?.length ?? 0} <span className="text-sm text-gray-500 font-normal">/ {deployments.length}</span></p>
        </div>
      </div>

      <ProjectPipeline project={project} hasDeployment={deployments.length > 0} />

      {latestSuccessBuild && (
        <RolloutPanel
          buildId={latestSuccessBuild.id}
          projectId={project.id}
          packageName={project.package_name ?? undefined}
        />
      )}

      {preview && preview.status !== 'not_ready' && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
          <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Eye size={14} className={preview.status === 'ready' ? 'text-green-400' : 'text-yellow-400'} />
            {preview.status === 'ready' ? 'Live Preview' : 'Device Preview'}
          </h2>

          {preview.type === 'appetize' && preview.embed_url && (
            <div className="space-y-3">
              <p className="text-xs text-gray-400">{preview.instructions}</p>
              <div className="rounded-xl overflow-hidden border border-gray-700 bg-black flex justify-center">
                <iframe
                  src={preview.embed_url}
                  width="375"
                  height="667"
                  frameBorder="0"
                  scrolling="no"
                  title="Device Preview"
                  className="rounded-xl"
                />
              </div>
            </div>
          )}

          {preview.type === 'docker_android' && (
            <div className="space-y-3">
              <p className="text-xs text-gray-400">{preview.instructions}</p>
              <a
                href={preview.preview_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 bg-green-600/20 hover:bg-green-600/30 text-green-300 border border-green-500/30 rounded-lg text-sm transition-colors"
              >
                <ExternalLink size={13} />
                Open Android Emulator
              </a>
            </div>
          )}

          {preview.type === 'native_pending' || preview.status === 'pending_build' ? (
            <div className="flex items-start gap-3 text-sm text-yellow-300/80 bg-yellow-500/5 border border-yellow-500/20 rounded-lg p-3">
              <Loader size={14} className="mt-0.5 shrink-0" />
              <p className="text-xs">{preview.instructions}</p>
            </div>
          ) : null}

          {preview.type === 'download_only' && (
            <div className="space-y-2">
              <p className="text-xs text-gray-400">{preview.instructions}</p>
              {preview.preview_url && (
                <a
                  href={preview.preview_url}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm transition-colors"
                >
                  <Package size={13} />
                  Download Artifact
                </a>
              )}
            </div>
          )}

          {(preview.type === 'expo' || preview.type === 'flutter_web') && preview.status === 'ready' && (
            <div className="flex items-center gap-4">
              <a
                href={preview.preview_url}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-2 px-4 py-2 bg-green-600/20 hover:bg-green-600/30 text-green-300 border border-green-500/30 rounded-lg text-sm transition-colors"
              >
                <ExternalLink size={13} />
                Open Preview
              </a>
              {preview.qr_url && (
                <a
                  href={preview.qr_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm transition-colors"
                >
                  <QrCode size={13} />
                  QR Code
                </a>
              )}
              <p className="text-xs text-gray-500">{preview.instructions}</p>
            </div>
          )}
        </div>
      )}

      {canBuild && <BuildRunnerCard project={project} />}

      {canBuild && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
          <h2 className="text-sm font-semibold mb-3">Trigger Build</h2>
          {(project.framework === 'capacitor' || project.framework === 'ionic' || project.framework === 'cordova') && (
            <div className="flex items-center gap-2 mb-3 text-xs">
              <span className={clsx(
                'px-2 py-0.5 rounded-full font-medium border',
                project.repo_visibility === 'public'
                  ? 'bg-green-500/20 text-green-300 border-green-500/30'
                  : 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30'
              )}>
                {project.repo_visibility === 'public' ? 'GitHub Hosted — Unlimited' : 'GitHub Hosted — 200min/mo'}
              </span>
              <span className="text-gray-500">
                iOS: {project.repo_visibility === 'public' ? 'macos-latest (free, unlimited)' : 'macos-latest (free tier: ~13 builds/mo)'}
              </span>
            </div>
          )}
          <div className="flex gap-3">
            {(project.framework === 'pwa'
              ? ['android', 'web']
              : ['android', 'ios', 'both']
            ).map((platform) => (
              <button
                key={platform}
                onClick={() => buildMutation.mutate(platform)}
                disabled={buildMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
              >
                <Play size={13} />
                {platformLabel(platform)}
              </button>
            ))}
          </div>
          {buildMutation.isError && (
            <p className="text-red-400 text-xs mt-2">
              {(buildMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Build trigger failed'}
            </p>
          )}
        </div>
      )}

      {activeBuild && <LiveBuildProgress buildId={activeBuild.id} projectId={project.id} />}

      <div className="bg-gray-900 border border-gray-800 rounded-xl mb-6">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <Package size={15} />
            Build History
          </h2>
        </div>
        {!project.builds || project.builds.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-gray-600">
            <Package size={28} className="mb-2 opacity-30" />
            <p className="text-sm">No builds yet.</p>
          </div>
        ) : (
          <>
            <div className="divide-y divide-gray-800">
              {visibleBuilds.map((build) => (
                <div key={build.id}>
                  <div className="flex items-center justify-between px-5 py-3">
                    <div className="flex items-center gap-4">
                      <span className={clsx('text-xs px-2 py-0.5 rounded-full font-medium', buildStatusColors[build.status])}>
                        {build.status}
                      </span>
                      <div>
                        <p className="text-sm font-medium">
                          {platformLabel(build.platform)} · {providerLabel(build.provider)}
                          {build.trigger_type === 'pull_request' && build.pr_number && (
                            <span className="ml-2 text-xs text-purple-400 bg-purple-500/10 px-1.5 py-0.5 rounded">
                              PR #{build.pr_number}
                            </span>
                          )}
                          {build.trigger_type === 'manual' && (
                            <span className="ml-2 text-xs text-yellow-400 bg-yellow-500/10 px-1.5 py-0.5 rounded">
                              Manual
                            </span>
                          )}
                        </p>
                        <p className="text-xs text-gray-500">
                          {new Date(build.created_at).toLocaleString()}
                          {build.commit_sha && <span className="ml-2 font-mono text-gray-600">{build.commit_sha.slice(0, 7)}</span>}
                          {build.started_at && build.finished_at && (
                            <span className="ml-2">
                              {Math.round((new Date(build.finished_at).getTime() - new Date(build.started_at).getTime()) / 1000)}s
                            </span>
                          )}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {build.status === 'failed' && (
                        <button
                          onClick={() => setExpandedBuildId(expandedBuildId === build.id ? null : build.id)}
                          className="flex items-center gap-1 text-xs px-2 py-1 bg-red-600/20 hover:bg-red-600/30 text-red-300 border border-red-500/30 rounded-lg transition-colors"
                        >
                          <XCircle size={11} />
                          {expandedBuildId === build.id ? 'Hide Details' : 'Error Details'}
                        </button>
                      )}
                      {build.artifact_url && (
                        <a href={build.artifact_url} className="text-xs text-primary-400 hover:underline flex items-center gap-1">
                          Download <ExternalLink size={10} />
                        </a>
                      )}
                      {build.status === 'success' && (
                        <button
                          onClick={() => setDeployBuild(build)}
                          className="flex items-center gap-1 text-xs px-2 py-1 bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 border border-purple-500/30 rounded-lg transition-colors"
                        >
                          <Upload size={11} />
                          Deploy
                        </button>
                      )}
                    </div>
                  </div>
                  {(build.status === 'running' || build.status === 'queued') && (
                    <div className="px-5 pb-3">
                      <div className="flex items-center gap-3">
                        <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                          <div className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full animate-pulse" style={{ width: build.status === 'queued' ? '15%' : '60%' }} />
                        </div>
                        <span className="text-xs text-gray-500">
                          {build.status === 'queued' ? 'Waiting...' : 'Building on GitHub Actions...'}
                        </span>
                      </div>
                    </div>
                  )}
                  {build.status === 'failed' && expandedBuildId === build.id && (
                    <div className="px-5 pb-4">
                      <BuildDiagnosisPanel
                        buildId={build.id}
                        errorMessage={build.error_message}
                        logOutput={build.log_output}
                        onRetry={() => {
                          buildMutation.mutate(build.platform)
                          setExpandedBuildId(null)
                        }}
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
            {(project.builds?.length ?? 0) > 5 && (
              <button
                onClick={() => setShowAllBuilds((s) => !s)}
                className="w-full flex items-center justify-center gap-1 py-3 text-xs text-gray-500 hover:text-gray-300 border-t border-gray-800 transition-colors"
              >
                {showAllBuilds ? <><ChevronUp size={12} /> Show less</> : <><ChevronDown size={12} /> Show all {project.builds?.length} builds</>}
              </button>
            )}
          </>
        )}
      </div>

      <ComplianceChecklist projectId={id!} />
      {deployments.length > 0 && (
        <DeploymentHistory deployments={deployments} projectId={id!} />
      )}
    </div>
  )
}
