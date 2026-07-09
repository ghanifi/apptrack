import { useMemo, useState, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, XCircle, Loader2, Circle, Radio, ExternalLink } from 'lucide-react'
import { useWebSocket } from '@/lib/useWebSocket'

interface Step {
  name: string
  status: string // queued | in_progress | completed
  conclusion: string | null // success | failure | skipped | null
  number: number
}
interface ProgressData {
  build_id: string
  run_status?: string
  html_url?: string
  elapsed_seconds?: number
  steps?: Step[]
}

function StepIcon({ step }: { step: Step }) {
  if (step.status === 'completed') {
    if (step.conclusion === 'success') return <CheckCircle2 size={16} className="text-green-400 shrink-0" />
    if (step.conclusion === 'skipped') return <Circle size={16} className="text-gray-600 shrink-0" />
    return <XCircle size={16} className="text-red-400 shrink-0" />
  }
  if (step.status === 'in_progress') return <Loader2 size={16} className="text-blue-400 shrink-0 animate-spin" />
  return <Circle size={16} className="text-gray-600 shrink-0" />
}

/** buildId verilen aktif build için canlı GitHub Actions adım ilerlemesini gösterir.
 *  WS kanalı: build.<id>.progress (gateway worker build.progress event'inden yayınlar). */
export default function LiveBuildProgress({ buildId, projectId }: { buildId: string; projectId: string }) {
  const [progress, setProgress] = useState<ProgressData | null>(null)
  const queryClient = useQueryClient()

  const channels = useMemo(() => [`build.${buildId}.progress`], [buildId])

  const onMessage = useCallback(
    (msg: { channel: string; data: Record<string, unknown> }) => {
      if (msg.channel !== `build.${buildId}.progress`) return
      const data = msg.data as unknown as ProgressData
      setProgress(data)
      // Build tamamlandıysa proje sorgusunu tazele → geçmiş/artifact güncellensin
      if (data.run_status === 'completed') {
        queryClient.invalidateQueries({ queryKey: ['projects', projectId] })
      }
    },
    [buildId, projectId, queryClient]
  )

  const { connected } = useWebSocket({ channels, onMessage })

  const steps = progress?.steps ?? []
  const elapsed = progress?.elapsed_seconds ?? 0

  return (
    <div className="bg-gray-900 border border-blue-500/30 rounded-xl mb-6">
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
        <h2 className="text-sm font-semibold flex items-center gap-2">
          <Radio size={15} className={connected ? 'text-green-400 animate-pulse' : 'text-gray-500'} />
          Live Build Progress
          <span className="text-xs font-normal text-gray-500">
            {connected ? 'connected' : 'connecting…'}
          </span>
        </h2>
        <div className="flex items-center gap-3">
          {elapsed > 0 && (
            <span className="text-xs text-gray-500">
              {Math.floor(elapsed / 60)}m {elapsed % 60}s
            </span>
          )}
          {progress?.html_url && (
            <a
              href={progress.html_url}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-primary-400 hover:underline flex items-center gap-1"
            >
              GitHub <ExternalLink size={10} />
            </a>
          )}
        </div>
      </div>
      <div className="p-5">
        {steps.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-gray-500 py-2">
            <Loader2 size={16} className="animate-spin" />
            Waiting for the runner to start…
          </div>
        ) : (
          <ul className="space-y-1.5">
            {steps.map((step) => (
              <li key={step.number} className="flex items-center gap-2.5 text-sm">
                <StepIcon step={step} />
                <span
                  className={
                    step.status === 'in_progress'
                      ? 'text-blue-300 font-medium'
                      : step.status === 'completed' && step.conclusion !== 'success' && step.conclusion !== 'skipped'
                        ? 'text-red-300'
                        : 'text-gray-300'
                  }
                >
                  {step.name}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
