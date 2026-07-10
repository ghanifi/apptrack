import { useQuery } from '@tanstack/react-query'
import { ShieldCheck, ShieldAlert, ShieldX, HelpCircle, FileKey } from 'lucide-react'
import { api } from '@/lib/api'

interface HealthItem {
  name: string
  kind: string
  expires_at: string | null
  days_left: number | null
  status: 'ok' | 'expiring_soon' | 'expired' | 'unknown'
}
interface SigningHealth {
  configured: boolean
  overall: string
  items: HealthItem[]
}

const STATUS = {
  ok: { icon: ShieldCheck, color: 'text-green-400', label: 'Valid' },
  expiring_soon: { icon: ShieldAlert, color: 'text-yellow-400', label: 'Expiring soon' },
  expired: { icon: ShieldX, color: 'text-red-400', label: 'Expired' },
  unknown: { icon: HelpCircle, color: 'text-gray-500', label: 'Unknown' },
}

/** iOS imzalama doktoru — sertifika/profil süre bitimini proaktif gösterir. */
export default function SigningHealthPanel() {
  const { data } = useQuery<SigningHealth>({
    queryKey: ['signing-health'],
    queryFn: () => api.get('/signing/health').then((r) => r.data),
    retry: false,
  })

  if (!data) return null

  if (!data.configured) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center gap-3">
        <FileKey size={16} className="text-gray-500 shrink-0" />
        <p className="text-xs text-gray-500">
          No iOS signing credentials yet. Add or auto-generate them to monitor certificate &amp; profile expiry.
        </p>
      </div>
    )
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <p className="text-xs text-gray-500 mb-3">
        Certificate &amp; provisioning profile expiry — caught before your next build breaks.
      </p>
      <div className="space-y-2">
        {data.items.map((item) => {
          const s = STATUS[item.status] ?? STATUS.unknown
          const Icon = s.icon
          return (
            <div key={item.kind} className="flex items-center justify-between py-1.5">
              <div className="flex items-center gap-2.5 min-w-0">
                <Icon size={16} className={`${s.color} shrink-0`} />
                <div className="min-w-0">
                  <p className="text-sm truncate">{item.name}</p>
                  {item.expires_at && (
                    <p className="text-xs text-gray-500">
                      Expires {new Date(item.expires_at).toLocaleDateString()}
                      {item.days_left !== null && item.days_left >= 0 && ` · ${item.days_left} days left`}
                    </p>
                  )}
                </div>
              </div>
              <span className={`text-xs font-medium ${s.color} shrink-0`}>{s.label}</span>
            </div>
          )
        })}
      </div>
      {data.overall === 'expired' || data.overall === 'expiring_soon' ? (
        <div className="mt-3 text-xs text-yellow-200/80 border-t border-gray-800 pt-3">
          Renew via <span className="font-medium">iOS Signing → Auto-Generate</span> above to avoid failed builds.
        </div>
      ) : null}
    </div>
  )
}
