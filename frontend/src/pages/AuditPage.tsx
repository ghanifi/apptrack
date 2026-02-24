import { useState, useEffect } from 'react'
import { useAuthStore } from '@/store/authStore'

interface AuditEntry {
  id: string
  action: string
  resource_type: string
  resource_id: string | null
  details: Record<string, unknown> | null
  ip_address: string | null
  trace_id: string | null
  created_at: string
}

export default function AuditPage() {
  const { token } = useAuthStore()
  const [logs, setLogs] = useState<AuditEntry[]>([])
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')

  useEffect(() => {
    setLoading(true)
    const params = new URLSearchParams({ page: String(page), size: '25' })
    if (filter) params.append('action', filter)
    fetch(`/api/audit?${params}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(data => {
        setLogs(data.items || [])
        setTotalPages(data.pages || 1)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [token, page, filter])

  const actionColors: Record<string, string> = {
    'project.created': 'text-green-400',
    'build.triggered': 'text-blue-400',
    'deploy.triggered': 'text-purple-400',
    'credential.upserted': 'text-yellow-400',
    'user.login': 'text-cyan-400',
    'user.github_login': 'text-cyan-400',
  }

  return (
    <div className="p-6 max-w-5xl">
      <h1 className="text-2xl font-bold text-white mb-6">Audit Log</h1>

      <div className="flex gap-2 mb-4">
        {['', 'project.created', 'build.triggered', 'deploy.triggered', 'credential.upserted'].map(f => (
          <button
            key={f}
            onClick={() => { setFilter(f); setPage(1) }}
            className={`px-3 py-1 rounded text-sm ${filter === f ? 'bg-blue-600 text-white' : 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600'}`}
          >
            {f || 'All'}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-zinc-400">Loading...</p>
      ) : logs.length === 0 ? (
        <p className="text-zinc-500">No audit logs found.</p>
      ) : (
        <div className="bg-zinc-800/50 border border-zinc-700 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-700 text-zinc-400">
                <th className="text-left p-3">Action</th>
                <th className="text-left p-3">Resource</th>
                <th className="text-left p-3">IP</th>
                <th className="text-left p-3">Time</th>
              </tr>
            </thead>
            <tbody>
              {logs.map(log => (
                <tr key={log.id} className="border-b border-zinc-700/50 hover:bg-zinc-700/20">
                  <td className={`p-3 font-mono ${actionColors[log.action] || 'text-zinc-300'}`}>{log.action}</td>
                  <td className="p-3 text-zinc-400">{log.resource_type}{log.resource_id ? `:${log.resource_id.slice(0, 8)}` : ''}</td>
                  <td className="p-3 text-zinc-500 font-mono text-xs">{log.ip_address || '-'}</td>
                  <td className="p-3 text-zinc-500 text-xs">{new Date(log.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex justify-between items-center mt-4">
        <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} className="px-3 py-1 bg-zinc-700 text-zinc-300 rounded disabled:opacity-50">Previous</button>
        <span className="text-zinc-400 text-sm">Page {page} / {totalPages}</span>
        <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)} className="px-3 py-1 bg-zinc-700 text-zinc-300 rounded disabled:opacity-50">Next</button>
      </div>
    </div>
  )
}
