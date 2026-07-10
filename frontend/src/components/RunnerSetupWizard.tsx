import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Plus, Copy, Check, Loader2, RefreshCw, Apple, Terminal, Zap, Container } from 'lucide-react'
import { api } from '@/lib/api'
import type { RunnerSetupCommand, RunnerJitConfig } from '@/types'

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

type Mode = 'persistent' | 'jit'

/** Self-hosted runner kurulum sihirbazı: platform seç → tek satır kurulum script'i üret.
 *  İki mod: kalıcı runner (registration token + svc.sh) ve tek-build'lik JIT (ephemeral). */
export default function RunnerSetupWizard({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<Mode>('persistent')
  const [platform, setPlatform] = useState<PlatformOption | null>(null)
  const [copied, setCopied] = useState<string | null>(null)

  const generate = useMutation<RunnerSetupCommand, unknown, PlatformOption>({
    mutationFn: (p) =>
      api
        .post(`/projects/${projectId}/runners/setup-command`, { os: p.os, arch: p.arch })
        .then((r) => r.data),
  })

  const generateJit = useMutation<RunnerJitConfig, unknown, PlatformOption>({
    mutationFn: (p) =>
      api
        .post(`/projects/${projectId}/runners/jit-config`, { os: p.os, arch: p.arch })
        .then((r) => r.data),
  })

  const active = mode === 'persistent' ? generate : generateJit

  const selectPlatform = (p: PlatformOption) => {
    setPlatform(p)
    setCopied(null)
    if (mode === 'persistent') generate.mutate(p)
    else generateJit.mutate(p)
  }

  const switchMode = (m: Mode) => {
    setMode(m)
    setPlatform(null)
    setCopied(null)
    generate.reset()
    generateJit.reset()
  }

  const copyText = (key: string, text: string) => {
    navigator.clipboard.writeText(text)
    setCopied(key)
    setTimeout(() => setCopied(null), 2000)
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
      {/* Mod seçimi */}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => switchMode('persistent')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
            mode === 'persistent' ? 'border-primary-600 bg-primary-600/10 text-primary-400' : 'border-gray-800 text-gray-400 hover:border-gray-700'
          }`}
        >
          <Terminal size={12} />
          Kalıcı runner
        </button>
        <button
          type="button"
          onClick={() => switchMode('jit')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
            mode === 'jit' ? 'border-primary-600 bg-primary-600/10 text-primary-400' : 'border-gray-800 text-gray-400 hover:border-gray-700'
          }`}
        >
          <Zap size={12} />
          Tek build'lik (JIT)
        </button>
      </div>
      <p className="text-xs text-gray-500">
        {mode === 'persistent'
          ? 'Makineniz servise dönüşür, sürekli bağlı kalır — kendi Mac/sunucunuz için ideal.'
          : 'Runner tek job çalıştırır ve kendini siler — temiz ortam, kalıcı kayıt yok.'}
      </p>

      <p className="text-xs text-gray-400">Runner makinenizin platformunu seçin:</p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {PLATFORMS.map((p) => {
          const activeCard = platform?.id === p.id
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => selectPlatform(p)}
              className={`text-left rounded-lg border p-3 transition-colors ${
                activeCard ? 'border-primary-600 bg-primary-600/10' : 'border-gray-800 hover:border-gray-700'
              }`}
            >
              <div className="flex items-center gap-2 mb-0.5">
                <p.icon size={14} className={activeCard ? 'text-primary-400' : 'text-gray-400'} />
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

      {active.isPending && (
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <Loader2 size={12} className="animate-spin" />
          {mode === 'persistent' ? 'Kurulum komutu üretiliyor…' : 'JIT konfigürasyonu üretiliyor…'}
        </div>
      )}

      {active.isError && (
        <p className="text-xs text-red-400">
          {(active.error as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail ?? 'Komut üretilemedi.'}
        </p>
      )}

      {mode === 'persistent' && generate.data && !generate.isPending && (
        <div className="space-y-2">
          <div className="relative">
            <pre className="bg-gray-950 border border-gray-800 rounded-lg p-3 pr-12 overflow-x-auto text-xs font-mono text-gray-300">
              {generate.data.script}
            </pre>
            <button
              type="button"
              onClick={() => copyText('script', generate.data.script)}
              title="Kopyala"
              className="absolute top-2 right-2 p-1.5 rounded-md bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
            >
              {copied === 'script' ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
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

      {mode === 'jit' && generateJit.data && !generateJit.isPending && (
        <div className="space-y-2">
          <div className="relative">
            <pre className="bg-gray-950 border border-gray-800 rounded-lg p-3 pr-12 overflow-x-auto text-xs font-mono text-gray-300">
              {generateJit.data.script}
            </pre>
            <button
              type="button"
              onClick={() => copyText('jit-script', generateJit.data.script)}
              title="Kopyala"
              className="absolute top-2 right-2 p-1.5 rounded-md bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
            >
              {copied === 'jit-script' ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
            </button>
          </div>
          <div className="relative">
            <div className="flex items-center gap-1.5 text-xs text-gray-400 mb-1">
              <Container size={12} />
              Docker tek-komut alternatifi:
            </div>
            <pre className="bg-gray-950 border border-gray-800 rounded-lg p-3 pr-12 overflow-x-auto text-xs font-mono text-gray-300">
              {generateJit.data.docker_command}
            </pre>
            <button
              type="button"
              onClick={() => copyText('jit-docker', generateJit.data.docker_command)}
              title="Kopyala"
              className="absolute top-8 right-2 p-1.5 rounded-md bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
            >
              {copied === 'jit-docker' ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
            </button>
          </div>
          <p className="text-xs text-gray-500">
            ⚡ {generateJit.data.runner_name} — tek job çalıştırır, bitince GitHub'dan otomatik silinir.
            Her build için yeni konfigürasyon üretin.
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
