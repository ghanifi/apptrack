import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Rocket, ChevronRight, ShieldCheck, ShieldOff, Pause, Activity,
  Loader2, AlertTriangle,
} from 'lucide-react'
import { api } from '@/lib/api'
import type { Rollout } from '@/types'
import clsx from 'clsx'

interface RolloutPanelProps {
  buildId: string
  projectId: string
  packageName?: string
}

const ROLLOUT_STEPS = [0.01, 0.1, 0.5, 1.0]

const stateBadge: Record<Rollout['state'], { color: string; label: string }> = {
  in_progress: { color: 'text-blue-400 bg-blue-500/10 border-blue-500/20', label: 'Yayında' },
  paused: { color: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20', label: 'Duraklatıldı' },
  halted: { color: 'text-red-400 bg-red-500/10 border-red-500/20', label: 'Durduruldu' },
  failed: { color: 'text-red-400 bg-red-500/10 border-red-500/20', label: 'Başarısız' },
  completed: { color: 'text-green-400 bg-green-500/10 border-green-500/20', label: 'Tamamlandı' },
}

/** sampled_at → "X önce" basit göreli zaman. */
function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const s = Math.round(diff / 1000)
  if (s < 60) return `${s} sn önce`
  const m = Math.round(s / 60)
  if (m < 60) return `${m} dk önce`
  const h = Math.round(m / 60)
  if (h < 24) return `${h} sa önce`
  return `${Math.round(h / 24)} gün önce`
}

/** Kademeli yayın (staged rollout) paneli: %1 → %10 → %50 → %100, crash-free izler,
 *  regresyonda otomatik durdurur (Android). Apple sabit 7 gün programı — yalnız duraklat. */
export default function RolloutPanel({ buildId, projectId, packageName }: RolloutPanelProps) {
  const queryClient = useQueryClient()
  const [pkgInput, setPkgInput] = useState('')

  // Rollout'u proje düzeyinde ara: aktif rollout deploy edilen build'e bağlıdır ve o build,
  // "en son başarılı build" (panelin hedefi) olmayabilir — ör. iOS build'i en yeniyken
  // rollout Android build'e açılmışsa. Proje düzeyinde arayınca canlı rollout her zaman görünür.
  const { data: rollout, isLoading } = useQuery<Rollout | null>({
    queryKey: ['rollout-active', projectId],
    queryFn: () => api.get(`/rollouts/by-project/${projectId}/active`).then((r) => r.data),
    retry: false,
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['rollout-active', projectId] })

  const deploy = useMutation<Rollout, unknown>({
    mutationFn: () =>
      api.post(`/rollouts/deploy/${buildId}`, {
        target: 'google_play',
        track: 'production',
        package_name: packageName ?? pkgInput,
        start_fraction: 0.01,
        auto_halt: true,
        crash_free_threshold: 0.99,
        min_users: 1000,
      }).then((r) => r.data),
    onSuccess: invalidate,
  })

  const advance = useMutation<Rollout, unknown>({
    mutationFn: () =>
      api.post(`/rollouts/${rollout!.id}/advance`).then((r) => r.data),
    onSuccess: invalidate,
  })

  const halt = useMutation<Rollout, unknown>({
    mutationFn: () =>
      api.post(`/rollouts/${rollout!.id}/halt`).then((r) => r.data),
    onSuccess: invalidate,
  })

  if (isLoading) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6 flex items-center gap-2 text-xs text-gray-400">
        <Loader2 size={12} className="animate-spin" />
        Kademeli yayın durumu yükleniyor…
      </div>
    )
  }

  // --- Rollout yok: başlat kartı ---
  if (!rollout) {
    const needsPkg = !packageName
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6 animate-fade-up">
        <div className="flex items-start gap-3">
          <Rocket size={18} className="text-primary-400 mt-0.5 shrink-0" />
          <div className="flex-1">
            <h2 className="text-sm font-semibold">Kademeli yayın (Staged Rollout)</h2>
            <p className="text-xs text-gray-400 mt-1">
              Yayını %1 → %10 → %50 → %100 kademeli yay, crash-free izle, regresyonda otomatik durdur.
            </p>

            {needsPkg && (
              <input
                value={pkgInput}
                onChange={(e) => setPkgInput(e.target.value)}
                placeholder="com.example.app"
                className="mt-3 w-full max-w-xs bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
              />
            )}

            <button
              onClick={() => deploy.mutate()}
              disabled={deploy.isPending || (needsPkg && !pkgInput.trim())}
              className="mt-3 flex items-center gap-1.5 px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 rounded-lg text-xs font-medium transition-colors"
            >
              {deploy.isPending ? <Loader2 size={12} className="animate-spin" /> : <Rocket size={12} />}
              {deploy.isPending ? 'Başlatılıyor…' : 'Kademeli yayını başlat'}
            </button>

            {deploy.isError && (
              <p className="text-xs text-red-400 mt-2">
                {(deploy.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
                  ?? 'Kademeli yayın başlatılamadı.'}
              </p>
            )}
          </div>
        </div>
      </div>
    )
  }

  // --- Rollout var: durum paneli ---
  const badge = stateBadge[rollout.state]
  const isIOS = rollout.platform === 'app_store'
  const canAdvance =
    rollout.state === 'in_progress' && rollout.platform === 'google_play' && rollout.current_fraction < 1.0
  const canHalt = rollout.state === 'in_progress' || rollout.state === 'paused'
  const lastSample = rollout.samples && rollout.samples.length > 0
    ? rollout.samples[rollout.samples.length - 1]
    : null

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6 space-y-4 animate-fade-up">
      {/* Header + durum rozeti */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold flex items-center gap-2">
          <Rocket size={15} className="text-primary-400" />
          Kademeli yayın
          <span className="text-xs text-gray-500 font-normal">
            {isIOS ? 'App Store' : 'Google Play'} · {rollout.track}
          </span>
        </h2>
        <span className={clsx('text-xs px-2 py-0.5 rounded-full border font-medium', badge.color)}>
          {badge.label}
        </span>
      </div>

      {/* Aşama çubuğu */}
      <div className="flex items-center">
        {ROLLOUT_STEPS.map((step, i) => {
          const reached = rollout.current_fraction >= step
          const current = rollout.current_fraction === step
          return (
            <div key={step} className="flex items-center flex-1 last:flex-none">
              <div className="flex flex-col items-center shrink-0">
                <div
                  className={clsx(
                    'w-9 h-9 rounded-full flex items-center justify-center text-xs font-semibold transition-colors',
                    reached ? 'bg-primary-600 text-white' : 'bg-gray-800 text-gray-500',
                    current && 'ring-2 ring-primary-400 ring-offset-2 ring-offset-gray-900',
                  )}
                >
                  {`${step * 100}%`}
                </div>
              </div>
              {i < ROLLOUT_STEPS.length - 1 && (
                <div className="flex-1 h-0.5 mx-1 rounded-full bg-gray-800 overflow-hidden min-w-[16px]">
                  <div
                    className={clsx(
                      'h-full bg-primary-600 rounded-full transition-all duration-700',
                      rollout.current_fraction >= ROLLOUT_STEPS[i + 1] ? 'w-full' : 'w-0',
                    )}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* halted nedeni */}
      {rollout.state === 'halted' && rollout.halted_reason && (
        <div className="flex items-start gap-2 rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-xs text-red-300">
          <AlertTriangle size={13} className="mt-0.5 shrink-0" />
          <span>{rollout.halted_reason}</span>
        </div>
      )}

      {/* store işlemi hatası — DB ile store arasındaki tutarsızlık kullanıcıya görünür */}
      {rollout.last_error && (
        <div className="flex items-start gap-2 rounded-lg border border-orange-500/30 bg-orange-500/5 p-3 text-xs text-orange-300">
          <AlertTriangle size={13} className="mt-0.5 shrink-0" />
          <span>
            <strong>Son store işlemi başarısız:</strong> {rollout.last_error} — rollout store'daki
            önceki durumunda; işlemi tekrar deneyin.
          </span>
        </div>
      )}

      {/* sağlık sinyali canlılığı — auto-halt sessizce ölmesin */}
      {rollout.auto_halt_enabled && rollout.state === 'in_progress' &&
        (rollout.health_status === 'no_data' || rollout.health_status === 'stale') && (
        <div className="flex items-start gap-2 rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-3 text-xs text-yellow-200/90">
          <AlertTriangle size={13} className="mt-0.5 shrink-0" />
          <span>
            {rollout.health_status === 'no_data'
              ? 'Sağlık verisi henüz hiç alınamadı — Play Console\'da "View app information" izni ve Cloud\'da Play Developer Reporting API etkin mi kontrol edin. Auto-halt şu an sizi KORUMUYOR.'
              : 'Sağlık verisi bayat (3+ döngüdür güncellenmedi) — izleme kesintide olabilir, credential/izinleri kontrol edin.'}
          </span>
        </div>
      )}

      {/* Auto-halt rozeti */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {rollout.auto_halt_enabled ? (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-500/10 border border-green-500/20 text-green-400 font-medium">
            <ShieldCheck size={11} /> Auto-halt açık
          </span>
        ) : (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-500/10 border border-gray-500/20 text-gray-400 font-medium">
            <ShieldOff size={11} /> Auto-halt kapalı (yalnız Android)
          </span>
        )}
        {isIOS && (
          <span className="text-gray-500">Apple sabit 7 gün programı — yalnız duraklat.</span>
        )}
      </div>

      {/* Sağlık */}
      <div className="bg-gray-800/40 border border-gray-800 rounded-lg p-3">
        <div className="flex items-center gap-1.5 text-xs font-medium text-gray-300 mb-2">
          <Activity size={12} /> Sağlık
        </div>
        {!lastSample ? (
          <p className="text-xs text-gray-500">Sağlık verisi henüz yok.</p>
        ) : (
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs">
              <span className="text-gray-300">
                Crash-free:{' '}
                <span className="font-semibold text-green-400">
                  {(lastSample.crash_free_rate * 100).toFixed(2)}%
                </span>
              </span>
              <span className="text-gray-300">
                Kullanıcı: <span className="font-semibold">{lastSample.distinct_users.toLocaleString()}</span>
              </span>
              {lastSample.anr_rate !== null && (
                <span className="text-gray-300">
                  ANR: <span className="font-semibold">{(lastSample.anr_rate * 100).toFixed(2)}%</span>
                </span>
              )}
              {lastSample.sampled_at && (
                <span className="text-gray-500">son örnek: {relativeTime(lastSample.sampled_at)}</span>
              )}
            </div>
            {/* Mini crash-free sparkline (inline div bar'lar) */}
            <div className="flex items-end gap-0.5 h-10">
              {rollout.samples!.map((s, i) => (
                <div
                  key={i}
                  title={`${(s.crash_free_rate * 100).toFixed(2)}%`}
                  className={clsx(
                    'flex-1 rounded-sm min-w-[2px]',
                    s.crash_free_rate >= rollout.crash_free_threshold ? 'bg-green-500/60' : 'bg-red-500/60',
                  )}
                  style={{ height: `${Math.max(4, Math.min(100, s.crash_free_rate * 100)) * 0.4 + 4}px` }}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Aksiyonlar */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => advance.mutate()}
          disabled={!canAdvance || advance.isPending}
          className="flex items-center gap-1.5 px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-xs font-medium transition-colors"
        >
          {advance.isPending ? <Loader2 size={12} className="animate-spin" /> : <ChevronRight size={12} />}
          İlerlet (→ %{Math.round(rollout.next_fraction * 100)})
        </button>
        <button
          onClick={() => halt.mutate()}
          disabled={!canHalt || halt.isPending}
          className="flex items-center gap-1.5 px-4 py-2 bg-red-600/20 hover:bg-red-600/30 disabled:opacity-40 disabled:cursor-not-allowed text-red-300 border border-red-500/30 rounded-lg text-xs font-medium transition-colors"
        >
          {halt.isPending ? <Loader2 size={12} className="animate-spin" /> : <Pause size={12} />}
          Durdur
        </button>
      </div>

      {(advance.isError || halt.isError) && (
        <p className="text-xs text-red-400">İşlem başarısız oldu, tekrar deneyin.</p>
      )}
    </div>
  )
}
