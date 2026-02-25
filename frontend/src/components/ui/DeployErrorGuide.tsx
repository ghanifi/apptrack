import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ExternalLink, RefreshCw, ChevronRight } from 'lucide-react'
import { api } from '@/lib/api'

interface DeployErrorGuideProps {
  errorCode: string
  onRetry?: () => void
}

interface ErrorGuide {
  title: string
  message: string
  steps: string[]
  links: Record<string, string>
  error_code: string
}

export default function DeployErrorGuide({ errorCode, onRetry }: DeployErrorGuideProps) {
  const { data: guide } = useQuery<ErrorGuide>({
    queryKey: ['deploy-error', errorCode],
    queryFn: () => api.get(`/deploy-errors/${errorCode}`).then((r) => r.data),
    enabled: !!errorCode,
  })

  if (!guide) return null

  return (
    <div className="bg-red-500/5 border border-red-500/20 rounded-xl p-5">
      <div className="flex items-start gap-3 mb-4">
        <AlertTriangle size={20} className="text-red-400 mt-0.5 shrink-0" />
        <div>
          <h3 className="text-sm font-bold text-red-400">{guide.title}</h3>
          <p className="text-xs text-gray-400 mt-1">{guide.message}</p>
        </div>
      </div>

      {guide.steps.length > 0 && (
        <div className="space-y-2 mb-4">
          <p className="text-xs font-medium text-gray-300">How to fix this:</p>
          {guide.steps.map((step, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-gray-400">
              <ChevronRight size={12} className="mt-0.5 text-gray-600 shrink-0" />
              <span>{step}</span>
            </div>
          ))}
        </div>
      )}

      {Object.keys(guide.links).length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {Object.entries(guide.links).map(([label, url]) => (
            <a
              key={label}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-xs text-primary-400 hover:text-primary-300 transition-colors"
            >
              <ExternalLink size={10} /> {label}
            </a>
          ))}
        </div>
      )}

      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs font-medium transition-colors"
        >
          <RefreshCw size={12} /> Try Again
        </button>
      )}
    </div>
  )
}
