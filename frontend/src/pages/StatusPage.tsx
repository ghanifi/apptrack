import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Rocket, ArrowLeft, CheckCircle, AlertCircle, XCircle, Loader, Clock } from 'lucide-react'
import { api } from '@/lib/api'
import type { Incident } from '@/types'

interface HealthStatus {
  status: string
  services: Record<string, string>
  version: string
}

const STATUS_CONFIG: Record<string, { icon: React.ComponentType<any>; color: string; label: string }> = {
  healthy: { icon: CheckCircle, color: 'text-green-400', label: 'Operational' },
  degraded: { icon: AlertCircle, color: 'text-yellow-400', label: 'Degraded' },
  unhealthy: { icon: XCircle, color: 'text-red-400', label: 'Down' },
}

const SERVICE_LABELS: Record<string, string> = {
  database: 'Database (PostgreSQL)',
  rabbitmq: 'Message Queue (RabbitMQ)',
  redis: 'Cache (Redis)',
  gateway: 'API Gateway',
  build_service: 'Build Service',
  artifact_service: 'Artifact Storage',
  preview_service: 'Preview Engine',
  store_deploy: 'Store Deploy Service',
}

export default function StatusPage() {
  const { data: health, isLoading, isError } = useQuery<HealthStatus>({
    queryKey: ['health'],
    queryFn: () => api.get('/health/deep').then((r) => r.data).catch(() => ({ status: 'unhealthy', services: {}, version: 'unknown' })),
    refetchInterval: 30000,
  })

  const overallStatus = health?.status ?? 'unknown'
  const overallConfig = STATUS_CONFIG[overallStatus] ?? STATUS_CONFIG.unhealthy

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <Rocket size={20} className="text-primary-500" />
            <span className="font-bold">AppTrack</span>
          </Link>
          <Link to="/" className="text-sm text-gray-400 hover:text-white flex items-center gap-1">
            <ArrowLeft size={14} /> Back
          </Link>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-16">
        <h1 className="text-3xl font-bold mb-2">System Status</h1>
        <p className="text-gray-400 text-sm mb-8">Real-time status of AppTrack services. Updated every 30 seconds.</p>

        {isLoading ? (
          <div className="flex items-center justify-center py-20 text-gray-500">
            <Loader size={24} className="animate-spin" />
          </div>
        ) : (
          <>
            <div className={`bg-gray-900 border border-gray-800 rounded-xl p-6 mb-8 flex items-center gap-4`}>
              <overallConfig.icon size={32} className={overallConfig.color} />
              <div>
                <p className="text-lg font-semibold">{overallConfig.label}</p>
                <p className="text-sm text-gray-400">
                  {overallStatus === 'healthy'
                    ? 'All systems are running normally.'
                    : overallStatus === 'degraded'
                      ? 'Some services are experiencing issues.'
                      : 'Platform is experiencing an outage.'}
                </p>
              </div>
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-800">
                <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Services</h2>
              </div>
              <div className="divide-y divide-gray-800">
                {health?.services && Object.entries(health.services).map(([key, status]) => {
                  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.unhealthy
                  const Icon = cfg.icon
                  return (
                    <div key={key} className="flex items-center justify-between px-6 py-4">
                      <span className="text-sm text-gray-300">{SERVICE_LABELS[key] ?? key}</span>
                      <div className="flex items-center gap-2">
                        <Icon size={16} className={cfg.color} />
                        <span className={`text-sm ${cfg.color}`}>{cfg.label}</span>
                      </div>
                    </div>
                  )
                })}
                {(!health?.services || Object.keys(health.services).length === 0) && (
                  <div className="px-6 py-8 text-center text-gray-500 text-sm">
                    {isError ? 'Unable to fetch service status.' : 'No service data available.'}
                  </div>
                )}
              </div>
            </div>

            {health?.version && (
              <p className="text-xs text-gray-600 mt-4 text-right">Version: {health.version}</p>
            )}
          </>
        )}

        <IncidentHistory />
      </main>
    </div>
  )
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'text-red-400 bg-red-400/10',
  major: 'text-orange-400 bg-orange-400/10',
  minor: 'text-yellow-400 bg-yellow-400/10',
}

const STATUS_LABELS: Record<string, string> = {
  investigating: 'Investigating',
  identified: 'Identified',
  monitoring: 'Monitoring',
  resolved: 'Resolved',
}

function IncidentHistory() {
  const { data } = useQuery<{ items: Incident[] }>({
    queryKey: ['incidents'],
    queryFn: () => api.get('/status/incidents?limit=20').then((r) => r.data),
  })

  const incidents = data?.items ?? []

  return (
    <div className="mt-12 bg-gray-900 border border-gray-800 rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-4">Incident History</h2>
      {incidents.length === 0 ? (
        <div className="text-sm text-gray-500 text-center py-6">
          No incidents reported.
        </div>
      ) : (
        <div className="space-y-4">
          {incidents.map((incident) => (
            <div key={incident.id} className="border border-gray-800 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {incident.status === 'resolved' ? (
                    <CheckCircle size={16} className="text-green-400" />
                  ) : (
                    <AlertCircle size={16} className="text-yellow-400" />
                  )}
                  <h3 className="text-sm font-medium text-white">{incident.title}</h3>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${SEVERITY_COLORS[incident.severity] ?? 'text-gray-400 bg-gray-400/10'}`}>
                    {incident.severity}
                  </span>
                  <span className="text-xs text-gray-500">
                    {STATUS_LABELS[incident.status] ?? incident.status}
                  </span>
                </div>
              </div>
              <p className="text-xs text-gray-400">{incident.message}</p>
              <div className="flex items-center gap-1 mt-2 text-xs text-gray-500">
                <Clock size={12} />
                {new Date(incident.created_at).toLocaleString()}
                {incident.resolved_at && (
                  <span className="ml-2">
                    Resolved: {new Date(incident.resolved_at).toLocaleString()}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
