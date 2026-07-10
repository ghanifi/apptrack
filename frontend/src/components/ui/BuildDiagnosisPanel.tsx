import { useQuery, useMutation } from '@tanstack/react-query'
import {
  AlertTriangle, ChevronRight, RefreshCw, Wrench, Shield,
  ChevronDown, ChevronUp, FileText, GitPullRequest, ExternalLink,
} from 'lucide-react'
import { api } from '@/lib/api'
import type { BuildDiagnosisResult } from '@/types'
import { useState } from 'react'
import clsx from 'clsx'

interface BuildDiagnosisPanelProps {
  buildId: string
  errorMessage?: string
  logOutput?: string
  onRetry?: () => void
}

const severityConfig = {
  critical: { color: 'text-red-400 bg-red-500/10 border-red-500/20', label: 'Critical' },
  high: { color: 'text-orange-400 bg-orange-500/10 border-orange-500/20', label: 'High' },
  medium: { color: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20', label: 'Medium' },
  low: { color: 'text-gray-400 bg-gray-500/10 border-gray-500/20', label: 'Low' },
}

export default function BuildDiagnosisPanel({ buildId, errorMessage, logOutput, onRetry }: BuildDiagnosisPanelProps) {
  const [showLogs, setShowLogs] = useState(false)

  const { data: diagnosis, isLoading, isError } = useQuery<BuildDiagnosisResult>({
    queryKey: ['build-diagnosis', buildId],
    queryFn: () => api.post(`/build-diagnosis/diagnose/${buildId}`).then(r => r.data),
    retry: false,
    staleTime: 5 * 60 * 1000,
  })

  const autofix = useMutation<{ pr_url: string; title: string; reused: boolean }, unknown>({
    mutationFn: () => api.post(`/build-diagnosis/autofix/${buildId}`).then(r => r.data),
  })

  return (
    <div className="bg-red-500/5 border border-red-500/20 rounded-xl p-5 space-y-4">
      {/* Header */}
      <div className="flex items-start gap-3">
        <AlertTriangle size={20} className="text-red-400 mt-0.5 shrink-0" />
        <div className="flex-1">
          <h3 className="text-sm font-bold text-red-400">Build Failed</h3>
          {errorMessage && (
            <p className="text-xs text-gray-400 mt-1 font-mono break-all">{errorMessage}</p>
          )}
        </div>
      </div>

      {/* AI Diagnosis */}
      {isLoading && (
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <RefreshCw size={12} className="animate-spin" />
          Analyzing build errors...
        </div>
      )}

      {isError && (
        <p className="text-xs text-gray-500">Could not load diagnosis for this build.</p>
      )}

      {diagnosis && diagnosis.diagnoses.length > 0 && (
        <div className="space-y-3">
          {/* Severity Badge */}
          <div className="flex items-center gap-2">
            <Shield size={13} className="text-gray-400" />
            <span className="text-xs font-medium text-gray-300">AI Diagnosis</span>
            <span className={clsx(
              'text-xs px-2 py-0.5 rounded-full border font-medium',
              severityConfig[diagnosis.severity]?.color ?? severityConfig.low.color,
            )}>
              {severityConfig[diagnosis.severity]?.label ?? 'Low'} · {diagnosis.diagnosis_count} issue{diagnosis.diagnosis_count > 1 ? 's' : ''}
            </span>
            {diagnosis.auto_fixable && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-green-500/10 border border-green-500/20 text-green-400 font-medium flex items-center gap-1">
                <Wrench size={10} /> Auto-fixable
              </span>
            )}
          </div>

          {/* Diagnosis Items */}
          {diagnosis.diagnoses.map((d) => (
            <div key={d.id} className="bg-gray-900/50 border border-gray-800 rounded-lg p-4 space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-xs px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 font-mono">{d.framework_group}</span>
                <span className="text-xs font-medium text-gray-200">{d.id.replace(/_/g, ' ')}</span>
                {d.auto_fix && (
                  <span className="text-xs text-green-400 flex items-center gap-0.5">
                    <Wrench size={10} /> fixable
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-300">{d.diagnosis}</p>
              <div className="bg-gray-800/50 rounded-lg p-3">
                <p className="text-xs font-medium text-gray-300 mb-1 flex items-center gap-1">
                  <ChevronRight size={11} /> How to fix:
                </p>
                <p className="text-xs text-gray-400">{d.fix}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {diagnosis && diagnosis.diagnoses.length === 0 && diagnosis.message && (
        <p className="text-xs text-gray-500">{diagnosis.message}</p>
      )}

      {/* Log Output Toggle */}
      {logOutput && (
        <div>
          <button
            onClick={() => setShowLogs(p => !p)}
            className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-200 transition-colors"
          >
            <FileText size={12} />
            {showLogs ? 'Hide' : 'Show'} Build Logs
            {showLogs ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
          {showLogs && (
            <pre className="mt-2 bg-gray-900 border border-gray-800 rounded-lg p-3 text-xs text-gray-400 font-mono overflow-x-auto max-h-64 overflow-y-auto whitespace-pre-wrap">
              {logOutput}
            </pre>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-2">
        {diagnosis?.auto_fixable && !autofix.data && (
          <button
            onClick={() => autofix.mutate()}
            disabled={autofix.isPending}
            className="flex items-center gap-1.5 px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 rounded-lg text-xs font-medium transition-colors"
          >
            <Wrench size={12} className={autofix.isPending ? 'animate-spin' : ''} />
            {autofix.isPending ? 'Opening fix PR…' : 'Auto-fix (open PR)'}
          </button>
        )}
        {onRetry && (
          <button
            onClick={onRetry}
            className="flex items-center gap-1.5 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs font-medium transition-colors"
          >
            <RefreshCw size={12} /> Retry Build
          </button>
        )}
      </div>

      {/* Auto-fix result */}
      {autofix.data && (
        <div className="flex items-center gap-2 rounded-lg border border-green-500/30 bg-green-500/5 p-3 text-xs animate-fade-up">
          <GitPullRequest size={14} className="text-green-400 shrink-0" />
          <span className="text-green-200/90">
            {autofix.data.reused ? 'Fix PR already open' : 'Fix PR opened'}: {autofix.data.title}.{' '}
            <a href={autofix.data.pr_url} target="_blank" rel="noreferrer"
               className="text-primary-400 hover:underline inline-flex items-center gap-0.5">
              Review on GitHub <ExternalLink size={9} />
            </a>
          </span>
        </div>
      )}
      {autofix.isError && (
        <p className="text-xs text-red-400">
          {(autofix.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
            ?? 'Auto-fix failed.'}
        </p>
      )}
    </div>
  )
}
