import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Server, Cloud, Cpu, AlertTriangle, ExternalLink, Check, Trash2, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'
import type { Project, Runner } from '@/types'
import RunnerSetupWizard from './RunnerSetupWizard'

/** Repoya kayıtlı self-hosted runner'ların canlı listesi (30 sn'de bir yenilenir). */
function RunnerList({ projectId, enabled }: { projectId: string; enabled: boolean }) {
  const queryClient = useQueryClient()
  const [confirmingId, setConfirmingId] = useState<number | null>(null)
  const confirmTimer = useRef<ReturnType<typeof setTimeout>>()

  const { data: runners, isLoading, error } = useQuery<Runner[]>({
    queryKey: ['runners', projectId],
    queryFn: () => api.get(`/projects/${projectId}/runners`).then((r) => r.data),
    refetchInterval: 30_000,
    retry: false,
    enabled,
  })

  const remove = useMutation({
    mutationFn: (runnerId: number) =>
      api.delete(`/projects/${projectId}/runners/${runnerId}`),
    onSuccess: () => {
      setConfirmingId(null)
      queryClient.invalidateQueries({ queryKey: ['runners', projectId] })
    },
  })

  const handleRemoveClick = (runnerId: number) => {
    if (confirmingId === runnerId) {
      clearTimeout(confirmTimer.current)
      remove.mutate(runnerId)
      return
    }
    setConfirmingId(runnerId)
    clearTimeout(confirmTimer.current)
    confirmTimer.current = setTimeout(() => setConfirmingId(null), 3000)
  }

  const status403 = (error as { response?: { status?: number; data?: { detail?: string } } })
    ?.response

  if (status403?.status === 403) {
    return (
      <div className="flex items-start gap-2 rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-2.5">
        <AlertTriangle size={14} className="text-yellow-400 shrink-0 mt-0.5" />
        <p className="text-xs text-yellow-200/90">
          {status403.data?.detail ?? 'Bu repo için admin yetkiniz yok.'}{' '}
          <a
            href="https://github.com/holladevai/apptrackv2/blob/main/docs/self-hosted-runner.md"
            target="_blank"
            rel="noreferrer"
            className="text-primary-400 hover:underline inline-flex items-center gap-0.5"
          >
            Kurulum rehberi <ExternalLink size={9} />
          </a>
        </p>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-xs text-gray-400">
        <Loader2 size={12} className="animate-spin" />
        Runner'lar yükleniyor…
      </div>
    )
  }

  if (!runners || runners.length === 0) {
    return <p className="text-xs text-gray-500">Henüz runner yok — aşağıdan ekleyin.</p>
  }

  return (
    <ul className="space-y-1.5">
      {runners.map((runner) => (
        <li
          key={runner.id}
          className="flex items-center gap-2 rounded-lg border border-gray-800 bg-gray-950/50 px-3 py-2"
        >
          <span
            title={runner.status === 'online' ? 'çevrimiçi' : 'çevrimdışı'}
            className={`w-2 h-2 rounded-full shrink-0 ${
              runner.status === 'online' ? 'bg-green-500' : 'bg-gray-600'
            }`}
          />
          <span className="text-sm font-medium">{runner.name}</span>
          {runner.busy && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 font-medium">
              meşgul
            </span>
          )}
          <span className="flex flex-wrap gap-1">
            {runner.labels.map((label) => (
              <span
                key={label}
                className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-800 text-gray-400"
              >
                {label}
              </span>
            ))}
          </span>
          {runner.version && (
            <span className="text-xs text-gray-600">v{runner.version}</span>
          )}
          <button
            type="button"
            onClick={() => handleRemoveClick(runner.id)}
            disabled={remove.isPending}
            className={`ml-auto flex items-center gap-1 text-xs px-2 py-1 rounded-md transition-colors ${
              confirmingId === runner.id
                ? 'bg-red-600/20 text-red-300 border border-red-500/30'
                : 'text-gray-500 hover:text-red-400'
            }`}
          >
            <Trash2 size={12} />
            {confirmingId === runner.id ? 'Emin misin?' : 'Kaldır'}
          </button>
        </li>
      ))}
    </ul>
  )
}

/** Proje bazlı GitHub Actions runner tercihi: hosted (macos-26) veya self-hosted. */
export default function BuildRunnerCard({ project }: { project: Project }) {
  const queryClient = useQueryClient()
  const [runnerType, setRunnerType] = useState<'hosted' | 'self_hosted'>(
    project.runner_type ?? 'hosted'
  )
  const [labels, setLabels] = useState(project.runner_labels ?? '')
  const [saved, setSaved] = useState(false)

  const dirty = runnerType !== (project.runner_type ?? 'hosted') || labels !== (project.runner_labels ?? '')

  const save = useMutation({
    mutationFn: () =>
      api.patch(`/projects/${project.id}`, {
        runner_type: runnerType,
        runner_labels: runnerType === 'self_hosted' ? labels : '',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects', project.id] })
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    },
  })

  const isPublic = project.repo_visibility === 'public'

  const Option = ({
    value, icon: Icon, title, desc,
  }: { value: 'hosted' | 'self_hosted'; icon: typeof Cloud; title: string; desc: string }) => {
    const active = runnerType === value
    return (
      <button
        type="button"
        onClick={() => setRunnerType(value)}
        className={`flex-1 text-left rounded-lg border p-3 transition-colors ${
          active ? 'border-primary-600 bg-primary-600/10' : 'border-gray-800 hover:border-gray-700'
        }`}
      >
        <div className="flex items-center gap-2 mb-1">
          <Icon size={15} className={active ? 'text-primary-400' : 'text-gray-400'} />
          <span className="text-sm font-medium">{title}</span>
          {active && <Check size={13} className="text-primary-400 ml-auto" />}
        </div>
        <p className="text-xs text-gray-500">{desc}</p>
      </button>
    )
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
      <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Server size={15} />
        Build Runner
      </h2>

      <div className="flex flex-col sm:flex-row gap-3 mb-3">
        <Option
          value="hosted"
          icon={Cloud}
          title="GitHub Hosted"
          desc="macOS 26. Kolay başlangıç; public repoda sınırsız, private ~200 dk/ay."
        />
        <Option
          value="self_hosted"
          icon={Cpu}
          title="Self-hosted"
          desc="Kendi Mac'in. Sınırsız dakika, tam kontrol."
        />
      </div>

      {runnerType === 'self_hosted' && (
        <div className="space-y-3 mb-3">
          <RunnerList projectId={project.id} enabled={runnerType === 'self_hosted'} />
          <RunnerSetupWizard projectId={project.id} />

          <div>
            <label className="block text-xs text-gray-400 mb-1">Özel label (opsiyonel)</label>
            <input
              type="text"
              value={labels}
              onChange={(e) => setLabels(e.target.value)}
              placeholder="apptrack-ios"
              className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm focus:border-primary-600 focus:outline-none"
            />
            <p className="text-xs text-gray-600 mt-1">
              Boş bırakırsan platforma göre varsayılan kullanılır: iOS{' '}
              <code className="text-gray-400">self-hosted, macOS, ARM64</code> · Android{' '}
              <code className="text-gray-400">self-hosted, Linux, X64</code>. Özel label girersen
              OS varsayımı yapılmaz.
            </p>
          </div>

          <div className="flex items-start gap-2 rounded-lg border border-blue-500/30 bg-blue-500/5 p-2.5">
            <Server size={14} className="text-blue-400 shrink-0 mt-0.5" />
            <p className="text-xs text-blue-200/90">
              Önce runner'ınızı repoya kaydedin.{' '}
              <a
                href="https://github.com/holladevai/apptrackv2/blob/main/docs/self-hosted-runner.md"
                target="_blank"
                rel="noreferrer"
                className="text-primary-400 hover:underline inline-flex items-center gap-0.5"
              >
                Kurulum rehberi <ExternalLink size={9} />
              </a>
            </p>
          </div>

          {isPublic && (
            <div className="flex items-start gap-2 rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-2.5">
              <AlertTriangle size={14} className="text-yellow-400 shrink-0 mt-0.5" />
              <p className="text-xs text-yellow-200/90">
                Public repoda self-hosted runner önerilmez — fork PR'ları runner makinenizde kod
                çalıştırabilir. Private repo veya ephemeral runner + fork onayı kullanın.
              </p>
            </div>
          )}
        </div>
      )}

      <div className="flex items-center gap-3">
        <button
          onClick={() => save.mutate()}
          disabled={!dirty || save.isPending}
          className="px-4 py-1.5 bg-primary-600 hover:bg-primary-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-colors"
        >
          {save.isPending ? 'Kaydediliyor…' : 'Kaydet'}
        </button>
        {saved && (
          <span className="text-xs text-green-400 flex items-center gap-1">
            <Check size={12} /> Kaydedildi
          </span>
        )}
        {save.isError && (
          <span className="text-xs text-red-400">
            {(save.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
              'Kaydetme başarısız'}
          </span>
        )}
      </div>
    </div>
  )
}
