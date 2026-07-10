import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Plus, Copy, Check, Loader2, RefreshCw, Apple, Terminal } from 'lucide-react'
import { api } from '@/lib/api'
import type { RunnerSetupCommand } from '@/types'

interface PlatformOption {
  id: string
  title: string
  desc: string
  badge?: string
  os: 'osx' | 'linux'
  arch: 'arm64' | 'x64'
  icon: typeof Apple
}

const PLATFORMS: PlatformOption[] = [
  { id: 'osx-arm64', title: 'macOS ARM64', desc: 'Apple Silicon — iOS build', badge: 'Önerilen', os: 'osx', arch: 'arm64', icon: Apple },
  { id: 'osx-x64', title: 'macOS x64', desc: 'Intel Mac', os: 'osx', arch: 'x64', icon: Apple },
  { id: 'linux-x64', title: 'Linux x64', desc: 'Android build', badge: 'Android için önerilen', os: 'linux', arch: 'x64', icon: Terminal },
  { id: 'linux-arm64', title: 'Linux ARM64', desc: 'ARM sunucu / Raspberry Pi', os: 'linux', arch: 'arm64', icon: Terminal },
]

/** Self-hosted runner kurulum sihirbazı: platform seç → tek satır kurulum script'i üret. */
export default function RunnerSetupWizard({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false)
  const [platform, setPlatform] = useState<PlatformOption | null>(null)
  const [copied, setCopied] = useState(false)

  const generate = useMutation<RunnerSetupCommand, unknown, PlatformOption>({
    mutationFn: (p) =>
      api
        .post(`/projects/${projectId}/runners/setup-command`, { os: p.os, arch: p.arch })
        .then((r) => r.data),
  })

  const selectPlatform = (p: PlatformOption) => {
    setPlatform(p)
    setCopied(false)
    generate.mutate(p)
  }

  const copyScript = () => {
    if (!generate.data) return
    navigator.clipboard.writeText(generate.data.script)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-800 hover:border-gray-700 text-xs font-medium text-gray-300 transition-colors"
      >
        <Plus size={13} />
        Runner ekle
      </button>
    )
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-400">Runner makinenizin platformunu seçin:</p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {PLATFORMS.map((p) => {
          const active = platform?.id === p.id
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => selectPlatform(p)}
              className={`text-left rounded-lg border p-3 transition-colors ${
                active ? 'border-primary-600 bg-primary-600/10' : 'border-gray-800 hover:border-gray-700'
              }`}
            >
              <div className="flex items-center gap-2 mb-0.5">
                <p.icon size={14} className={active ? 'text-primary-400' : 'text-gray-400'} />
                <span className="text-sm font-medium">{p.title}</span>
                {p.badge && (
                  <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded-full bg-primary-600/15 border border-primary-600/30 text-primary-400 font-medium">
                    {p.badge}
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-500">{p.desc}</p>
            </button>
          )
        })}
      </div>

      {generate.isPending && (
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <Loader2 size={12} className="animate-spin" />
          Kurulum komutu üretiliyor…
        </div>
      )}

      {generate.isError && (
        <p className="text-xs text-red-400">
          {(generate.error as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail ?? 'Kurulum komutu üretilemedi.'}
        </p>
      )}

      {generate.data && !generate.isPending && (
        <div className="space-y-2">
          <div className="relative">
            <pre className="bg-gray-950 border border-gray-800 rounded-lg p-3 pr-12 overflow-x-auto text-xs font-mono text-gray-300">
              {generate.data.script}
            </pre>
            <button
              type="button"
              onClick={copyScript}
              title="Kopyala"
              className="absolute top-2 right-2 p-1.5 rounded-md bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
            >
              {copied ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
            </button>
          </div>
          <p className="text-xs text-gray-500">
            ⏱ Token{' '}
            {new Date(generate.data.expires_at).toLocaleTimeString('tr-TR', {
              hour: '2-digit',
              minute: '2-digit',
            })}
            'e kadar geçerli (1 saat). Süre geçerse yeniden üret.
          </p>
          <p className="text-xs text-gray-500">
            Kurulum bitince yukarıdaki liste ~30 sn içinde güncellenir.
          </p>
          <button
            type="button"
            onClick={() => platform && selectPlatform(platform)}
            className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-200 transition-colors"
          >
            <RefreshCw size={11} />
            Yeniden üret
          </button>
        </div>
      )}
    </div>
  )
}
