import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Key, Plus, Trash2, Copy, Check, ShieldAlert } from 'lucide-react'
import { api } from '@/lib/api'

interface ApiKeyItem {
  id: string
  name: string
  key_prefix: string
  revoked: boolean
  last_used_at: string | null
  created_at: string
}

export default function ApiKeysSection() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [newKey, setNewKey] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const { data } = useQuery<{ items: ApiKeyItem[] }>({
    queryKey: ['api-keys'],
    queryFn: () => api.get('/api-keys').then((r) => r.data),
  })

  const create = useMutation({
    mutationFn: (n: string) => api.post('/api-keys', { name: n }).then((r) => r.data),
    onSuccess: (d) => {
      setNewKey(d.api_key)
      setName('')
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
    },
  })

  const revoke = useMutation({
    mutationFn: (id: string) => api.delete(`/api-keys/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['api-keys'] }),
  })

  const copy = () => {
    if (newKey) {
      navigator.clipboard?.writeText(newKey)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const keys = (data?.items ?? []).filter((k) => !k.revoked)

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
      <p className="text-xs text-gray-500 mb-4">
        Programmatic access for the MCP server, CLI and API. Connect AI agents (Claude Code, Cursor)
        to trigger builds and check status.
      </p>

      {/* Newly created key — shown ONCE */}
      {newKey && (
        <div className="mb-4 rounded-lg border border-green-500/30 bg-green-500/5 p-3 animate-fade-up">
          <div className="flex items-center gap-2 mb-2 text-xs text-green-300">
            <ShieldAlert size={14} /> Copy this key now — it won't be shown again.
          </div>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-xs font-mono text-gray-200 break-all">
              {newKey}
            </code>
            <button
              onClick={copy}
              className="shrink-0 px-3 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg text-xs font-medium flex items-center gap-1"
            >
              {copied ? <Check size={13} /> : <Copy size={13} />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
        </div>
      )}

      {/* Create */}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Key name (e.g. My Mac / Claude Code)"
          className="flex-1 bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm focus:border-primary-600 focus:outline-none"
        />
        <button
          onClick={() => name.trim() && create.mutate(name.trim())}
          disabled={!name.trim() || create.isPending}
          className="px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-40 rounded-lg text-sm font-medium flex items-center gap-1.5 shrink-0"
        >
          <Plus size={14} /> Create key
        </button>
      </div>

      {/* List */}
      {keys.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-gray-600">
          <Key size={24} className="mb-2 opacity-30" />
          <p className="text-sm">No API keys yet.</p>
        </div>
      ) : (
        <div className="divide-y divide-gray-800">
          {keys.map((k) => (
            <div key={k.id} className="flex items-center justify-between py-3">
              <div className="min-w-0">
                <p className="text-sm font-medium truncate">{k.name}</p>
                <p className="text-xs text-gray-500 font-mono">
                  {k.key_prefix}…{' '}
                  <span className="font-sans">
                    · {k.last_used_at ? `last used ${new Date(k.last_used_at).toLocaleDateString()}` : 'never used'}
                  </span>
                </p>
              </div>
              <button
                onClick={() => revoke.mutate(k.id)}
                disabled={revoke.isPending}
                className="shrink-0 flex items-center gap-1 text-xs px-2 py-1 bg-red-600/20 hover:bg-red-600/30 text-red-300 border border-red-500/30 rounded-lg transition-colors"
              >
                <Trash2 size={11} /> Revoke
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
