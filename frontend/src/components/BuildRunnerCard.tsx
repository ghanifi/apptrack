import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Server, Cloud, Cpu, AlertTriangle, ExternalLink, Check } from 'lucide-react'
import { api } from '@/lib/api'
import type { Project } from '@/types'

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
              Boş bırakırsan <code className="text-gray-400">self-hosted, macOS, ARM64</code> kullanılır.
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
