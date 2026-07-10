import { GitBranch, Layers, Hammer, Rocket, Check, X, Loader2 } from 'lucide-react'
import type { Project } from '@/types'

type StageState = 'done' | 'active' | 'failed' | 'pending'

interface Stage {
  key: string
  label: string
  hint: string
  icon: typeof GitBranch
  state: StageState
}

/** CI/CD sürecini görselleştiren pipeline haritası: Repo → Framework → Build → Deploy.
 *  Kullanıcının projesinin akışın neresinde olduğunu tek bakışta anlatır. */
export default function ProjectPipeline({
  project,
  hasDeployment,
}: {
  project: Project
  hasDeployment: boolean
}) {
  const builds = project.builds ?? []
  const frameworkDone = !!project.framework && project.framework !== 'unknown'
  const buildActive = builds.some((b) => b.status === 'queued' || b.status === 'running')
  const buildSuccess = builds.some((b) => b.status === 'success')
  const latest = builds[0]
  const buildFailed = !buildActive && !buildSuccess && latest?.status === 'failed'

  const buildState: StageState = buildActive
    ? 'active'
    : buildSuccess
      ? 'done'
      : buildFailed
        ? 'failed'
        : 'pending'

  const stages: Stage[] = [
    {
      key: 'repo',
      label: 'Repository',
      hint: 'Connected',
      icon: GitBranch,
      state: 'done',
    },
    {
      key: 'framework',
      label: 'Framework',
      hint: frameworkDone ? (project.framework ?? '') : 'Detecting…',
      icon: Layers,
      state: frameworkDone ? 'done' : project.status === 'analyzing' ? 'active' : 'pending',
    },
    {
      key: 'build',
      label: 'Build',
      hint: buildActive ? 'Running…' : buildSuccess ? 'Success' : buildFailed ? 'Failed' : 'Not built yet',
      icon: Hammer,
      state: buildState,
    },
    {
      key: 'deploy',
      label: 'Deploy',
      hint: hasDeployment ? 'Shipped' : 'Not deployed',
      icon: Rocket,
      state: hasDeployment ? 'done' : 'pending',
    },
  ]

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6 animate-fade-up">
      <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-4">Pipeline</h2>
      <div className="flex items-start">
        {stages.map((stage, i) => (
          <div key={stage.key} className="flex items-start flex-1 last:flex-none">
            <StageNode stage={stage} />
            {i < stages.length - 1 && <Connector filled={stage.state === 'done'} />}
          </div>
        ))}
      </div>
    </div>
  )
}

function StageNode({ stage }: { stage: Stage }) {
  const { icon: Icon, state, label, hint } = stage

  const circle =
    state === 'done'
      ? 'bg-primary-600 text-white'
      : state === 'active'
        ? 'bg-primary-600 text-white animate-pulse-ring'
        : state === 'failed'
          ? 'bg-red-600 text-white'
          : 'bg-gray-800 text-gray-500'

  return (
    <div className="flex flex-col items-center text-center w-[68px] shrink-0">
      <div className={`w-10 h-10 rounded-full flex items-center justify-center transition-colors ${circle}`}>
        {state === 'done' ? (
          <Check size={18} className="animate-pop-in" />
        ) : state === 'active' ? (
          <Loader2 size={18} className="animate-spin" />
        ) : state === 'failed' ? (
          <X size={18} className="animate-pop-in" />
        ) : (
          <Icon size={16} />
        )}
      </div>
      <p className={`text-xs mt-2 font-medium ${state === 'pending' ? 'text-gray-500' : 'text-gray-200'}`}>
        {label}
      </p>
      <p
        className={`text-[10px] mt-0.5 capitalize ${
          state === 'failed' ? 'text-red-400' : state === 'active' ? 'text-primary-400' : 'text-gray-500'
        }`}
      >
        {hint}
      </p>
    </div>
  )
}

function Connector({ filled }: { filled: boolean }) {
  return (
    <div className="flex-1 h-0.5 mt-5 mx-1 rounded-full bg-gray-800 overflow-hidden min-w-[16px]">
      <div
        className={`h-full bg-primary-600 rounded-full transition-all duration-700 ${
          filled ? 'w-full' : 'w-0'
        }`}
      />
    </div>
  )
}
