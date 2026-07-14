import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ShieldCheck, ShieldAlert, ShieldX, HelpCircle, Wrench, Loader2, Stethoscope } from 'lucide-react'
import { api } from '@/lib/api'
import clsx from 'clsx'

interface Check {
  id: string; title: string; status: string; severity: string; detail: string; fixable: boolean
}
interface Doctor {
  configured: boolean; overall: string; can_auto_repair: boolean; checks: Check[]
}

const IOS_FRAMEWORKS = ['flutter', 'react_native', 'expo', 'swift', 'capacitor', 'ionic', 'cordova']

const ICON: Record<string, { icon: typeof ShieldCheck; color: string }> = {
  ok: { icon: ShieldCheck, color: 'text-green-400' },
  expiring_soon: { icon: ShieldAlert, color: 'text-yellow-400' },
  missing: { icon: ShieldAlert, color: 'text-yellow-400' },
  expired: { icon: ShieldX, color: 'text-red-400' },
  error: { icon: ShieldX, color: 'text-red-400' },
  mismatch: { icon: ShieldX, color: 'text-red-400' },
  unknown: { icon: HelpCircle, color: 'text-gray-500' },
}

interface Props { projectId: string; packageName?: string; framework: string }

/** Proje-bağlı iOS imzalama doktoru — bundle eşleşme, sertifika-profil bağı,
 *  şifre, süre teşhisi + tek-tık onarım (auto-generate-ios). */
export default function SigningDoctorPanel({ projectId, packageName, framework }: Props) {
  const queryClient = useQueryClient()
  const { data } = useQuery<Doctor>({
    queryKey: ['signing-doctor', projectId],
    queryFn: () => api.get(`/signing/doctor/${projectId}`).then((r) => r.data),
    retry: false,
    enabled: IOS_FRAMEWORKS.includes(framework),
  })

  const repair = useMutation({
    mutationFn: () =>
      api.post('/signing/auto-generate-ios', { bundle_id: packageName }).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['signing-doctor', projectId] }),
  })

  if (!IOS_FRAMEWORKS.includes(framework) || !data) return null
  if (!data.configured) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-6 flex items-center gap-3">
        <Stethoscope size={16} className="text-gray-500 shrink-0" />
        <p className="text-xs text-gray-500">
          iOS imzalama kimlik bilgisi yok. Ayarlar → iOS Signing'den üretin; doktor sertifika/profil
          sağlığını ve bundle eşleşmesini burada izler.
        </p>
      </div>
    )
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6 animate-fade-up">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold flex items-center gap-2">
          <Stethoscope size={15} className="text-primary-400" /> İmzalama doktoru
        </h2>
        {data.can_auto_repair && (
          <button
            onClick={() => repair.mutate()}
            disabled={repair.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 rounded-lg text-xs font-medium transition-colors"
          >
            {repair.isPending ? <Loader2 size={12} className="animate-spin" /> : <Wrench size={12} />}
            Sertifika + profili yeniden üret
          </button>
        )}
      </div>
      <div className="space-y-2">
        {data.checks.map((c) => {
          const ic = ICON[c.status] ?? ICON.unknown
          const Icon = ic.icon
          return (
            <div key={c.id} className="flex items-start gap-2.5 py-1">
              <Icon size={15} className={clsx('mt-0.5 shrink-0', ic.color)} />
              <div className="min-w-0">
                <p className="text-sm">{c.title}</p>
                <p className="text-xs text-gray-500">{c.detail}</p>
              </div>
            </div>
          )
        })}
      </div>
      {!data.can_auto_repair && (data.overall === 'mismatch' || data.overall === 'expired' || data.overall === 'error') && (
        <p className="mt-3 text-xs text-yellow-200/80 border-t border-gray-800 pt-3">
          Otomatik onarım için proje bundle id'si (Store Config) ve App Store Connect API kimlik
          bilgisi (Ayarlar) gerekli.
        </p>
      )}
      {repair.isError && <p className="mt-2 text-xs text-red-400">Onarım başarısız — Ayarlar'daki ASC kimlik bilgilerini doğrulayın.</p>}
    </div>
  )
}
