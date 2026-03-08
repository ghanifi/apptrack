import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, Upload, Loader, CheckCircle, XCircle, RefreshCw,
  Radio, Clock, Undo2,
} from 'lucide-react'
import { api } from '@/lib/api'
import clsx from 'clsx'

interface OTAUpdate {
  update_id: string
  channel: string
  platform: string
  runtime_version: string
  bundle_url: string
  message: string
  status: string
  created_at: string
}

const channelColors: Record<string, string> = {
  production: 'bg-green-500/20 text-green-300',
  staging: 'bg-yellow-500/20 text-yellow-300',
  beta: 'bg-purple-500/20 text-purple-300',
}

const statusConfig: Record<string, { color: string; icon: React.FC<{ size?: number | string; className?: string }> }> = {
  published: { color: 'text-green-400', icon: CheckCircle },
  rolled_back: { color: 'text-red-400', icon: Undo2 },
  deprecated: { color: 'text-gray-500', icon: XCircle },
}

export default function OTAPage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const [channel, setChannel] = useState('production')
  const [bundleUrl, setBundleUrl] = useState('')
  const [runtimeVersion, setRuntimeVersion] = useState('1.0.0')
  const [message, setMessage] = useState('')
  const [platform, setPlatform] = useState<'all' | 'android' | 'ios'>('all')

  const { data: updates = [], isLoading } = useQuery<OTAUpdate[]>({
    queryKey: ['ota-updates', id, channel],
    queryFn: () =>
      api.get(`/ota/custom-bundle/${id}/history`).then((r) => r.data),
    enabled: !!id,
  })

  const publishMutation = useMutation({
    mutationFn: () =>
      api.post('/ota/custom-bundle', {
        project_id: id,
        channel,
        platform,
        runtime_version: runtimeVersion,
        bundle_url: bundleUrl,
        message,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ota-updates', id] })
      setBundleUrl('')
      setMessage('')
    },
  })

  const rollbackMutation = useMutation({
    mutationFn: () =>
      api.post('/ota/rollback', null, {
        params: { project_id: id, channel, platform },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ota-updates', id] })
    },
  })

  const filteredUpdates = updates.filter(
    (u) => u.channel === channel || channel === 'all'
  )

  return (
    <div className="p-8 max-w-4xl">
      <Link
        to={`/dashboard/projects/${id}`}
        className="flex items-center gap-2 text-sm text-gray-400 hover:text-white mb-6 transition-colors"
      >
        <ArrowLeft size={16} />
        Back to Project
      </Link>

      <div className="flex items-center gap-3 mb-6">
        <Radio size={22} className="text-primary-400" />
        <h1 className="text-2xl font-bold">Live Updates (OTA)</h1>
      </div>

      {/* Channel Selector */}
      <div className="flex gap-2 mb-6">
        {['production', 'staging', 'beta'].map((ch) => (
          <button
            key={ch}
            onClick={() => setChannel(ch)}
            className={clsx(
              'px-4 py-2 rounded-lg text-sm font-medium border transition-colors capitalize',
              channel === ch
                ? 'bg-primary-600 border-primary-500 text-white'
                : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600'
            )}
          >
            {ch}
          </button>
        ))}
      </div>

      {/* Publish Form */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
        <h2 className="text-sm font-semibold mb-4 flex items-center gap-2">
          <Upload size={14} />
          Publish New Update
        </h2>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Bundle URL</label>
            <input
              value={bundleUrl}
              onChange={(e) => setBundleUrl(e.target.value)}
              placeholder="https://storage.example.com/bundles/v1.2.zip"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Runtime Version</label>
            <input
              value={runtimeVersion}
              onChange={(e) => setRuntimeVersion(e.target.value)}
              placeholder="1.0.0"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Platform</label>
            <select
              value={platform}
              onChange={(e) => setPlatform(e.target.value as 'all' | 'android' | 'ios')}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
            >
              <option value="all">All Platforms</option>
              <option value="android">Android Only</option>
              <option value="ios">iOS Only</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Message (optional)</label>
            <input
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Bug fixes and performance improvements"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
            />
          </div>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => publishMutation.mutate()}
            disabled={publishMutation.isPending || !bundleUrl}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {publishMutation.isPending ? <Loader size={14} className="animate-spin" /> : <Upload size={14} />}
            Publish to {channel}
          </button>
          <button
            onClick={() => rollbackMutation.mutate()}
            disabled={rollbackMutation.isPending || filteredUpdates.length < 2}
            className="flex items-center gap-2 px-4 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-300 border border-red-500/30 rounded-lg text-sm transition-colors disabled:opacity-50"
          >
            {rollbackMutation.isPending ? <Loader size={14} className="animate-spin" /> : <Undo2 size={14} />}
            Rollback
          </button>
        </div>
        {publishMutation.isError && (
          <p className="text-red-400 text-xs mt-2">
            {(publishMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Publish failed'}
          </p>
        )}
      </div>

      {/* Update History */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <RefreshCw size={14} />
            Update History
          </h2>
          <span className="text-xs text-gray-500">{filteredUpdates.length} update(s)</span>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-10 text-gray-500">
            <Loader size={18} className="animate-spin" />
          </div>
        ) : filteredUpdates.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-gray-600">
            <Radio size={28} className="mb-2 opacity-30" />
            <p className="text-sm">No updates published yet.</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-800">
            {filteredUpdates.map((update) => {
              const StatusIcon = statusConfig[update.status]?.icon ?? Clock
              const statusColor = statusConfig[update.status]?.color ?? 'text-gray-400'
              return (
                <div key={update.update_id} className="flex items-center justify-between px-5 py-3">
                  <div className="flex items-center gap-4">
                    <StatusIcon size={16} className={statusColor} />
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">v{update.runtime_version}</span>
                        <span className={clsx('text-xs px-2 py-0.5 rounded-full font-medium', channelColors[update.channel] ?? 'bg-gray-500/20 text-gray-400')}>
                          {update.channel}
                        </span>
                        <span className="text-xs text-gray-600">{update.platform}</span>
                      </div>
                      {update.message && (
                        <p className="text-xs text-gray-500 mt-0.5">{update.message}</p>
                      )}
                      <p className="text-xs text-gray-600">
                        {update.created_at ? new Date(update.created_at).toLocaleString() : ''}
                      </p>
                    </div>
                  </div>
                  <span className={clsx('text-xs font-medium capitalize', statusColor)}>
                    {update.status}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
