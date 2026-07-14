import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Sparkles, Loader2, CheckCircle2, XCircle } from 'lucide-react'
import { api } from '@/lib/api'

interface ProviderOpt { id: string; label: string; default_model: string; free: boolean }
interface AiConfig {
  provider: string | null; model: string | null
  providers: ProviderOpt[]; configured: Record<string, boolean>
}
interface ModelOpt { id: string; free: boolean | null }

/** AI Sağlayıcıları (BYOK) — sağlayıcı seç, kendi anahtarını gir, bağlantıyı test et.
 *  Anahtarlar sunucuda Fernet-şifreli saklanır. Autofix LLM fallback bunu kullanır. */
export default function AiProviderPanel() {
  const qc = useQueryClient()
  const { data } = useQuery<AiConfig>({
    queryKey: ['ai-config'], queryFn: () => api.get('/ai/config').then((r) => r.data), retry: false,
  })
  const [sel, setSel] = useState<string | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [testResult, setTestResult] = useState<{ ok: boolean; error?: string | null; model?: string | null } | null>(null)

  const provider = sel ?? data?.provider ?? null
  const current = data?.providers.find((p) => p.id === provider)
  const keyConfigured = !!(provider && data?.configured[provider])

  // Sağlayıcının CANLI model listesi (2026 temmuz aktif) — anahtar kaydedilince yüklenir.
  const models = useQuery<ModelOpt[]>({
    queryKey: ['ai-models', provider],
    queryFn: () => api.get('/ai/models', { params: { provider } }).then((r) => r.data.models),
    enabled: keyConfigured,
    retry: false,
  })

  const save = useMutation({
    mutationFn: () => api.put('/ai/config', {
      provider, model: model || undefined, api_key: apiKey || undefined,
    }).then((r) => r.data),
    onSuccess: () => { setApiKey(''); qc.invalidateQueries({ queryKey: ['ai-config'] }) },
  })
  const test = useMutation({
    mutationFn: () => api.post('/ai/test').then((r) => r.data),
    onSuccess: (r) => setTestResult(r),
  })

  if (!data) return null

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-1">
        <Sparkles size={16} className="text-primary-400" />
        <h3 className="font-semibold">AI Sağlayıcıları</h3>
      </div>
      <p className="text-xs text-gray-500 mb-4">
        Kendi anahtarınızı getirin (BYOK). Build hataları için deterministik yama bulunamazsa AI bir düzeltme
        PR'ı önerir. Anahtarlar sunucuda şifreli saklanır. Ücretsiz katmanlar önerilir — maliyet size aittir.
      </p>

      <div className="grid grid-cols-2 gap-2 mb-4">
        {data.providers.map((p) => (
          <button
            key={p.id}
            onClick={() => { setSel(p.id); setModel(''); setTestResult(null) }}
            className={`text-left px-3 py-2 rounded-lg border text-sm transition-colors ${
              provider === p.id ? 'border-primary-500 bg-primary-600/10' : 'border-gray-700 hover:border-gray-600'
            }`}
          >
            <div className="flex items-center justify-between">
              <span>{p.label}</span>
              {p.free && <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/10 text-green-400">Ücretsiz</span>}
              {data.configured[p.id] && <CheckCircle2 size={13} className="text-green-400" />}
            </div>
          </button>
        ))}
      </div>

      {current && (
        <div className="space-y-3">
          <input
            type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
            placeholder={`${current.label} API anahtarı`}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
          />
          {keyConfigured && models.data && models.data.length > 0 ? (
            <div>
              <select
                value={model || data.model || current.default_model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
              >
                {!models.data.some((m) => m.id === (data.model || current.default_model)) && (
                  <option value={data.model || current.default_model}>
                    {data.model || current.default_model} (kayıtlı)
                  </option>
                )}
                {models.data.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.id}{m.free === true ? ' — ücretsiz' : m.free === false ? ' — ücretli' : ''}
                  </option>
                ))}
              </select>
              <p className="text-[11px] text-gray-500 mt-1">
                {models.data.length} model (2026 temmuz aktif). Ücretsiz ve ücretli modeller seçilebilir.
              </p>
            </div>
          ) : (
            <input
              value={model} onChange={(e) => setModel(e.target.value)}
              placeholder={keyConfigured && models.isLoading
                ? 'Modeller yükleniyor…'
                : `Model (boş = ${current.default_model}) — anahtar kaydedince liste gelir`}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
            />
          )}
          <div className="flex items-center gap-2">
            <button
              onClick={() => save.mutate()} disabled={save.isPending}
              className="px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 rounded-lg text-xs font-medium"
            >
              {save.isPending ? 'Kaydediliyor…' : 'Kaydet'}
            </button>
            <button
              onClick={() => test.mutate()} disabled={test.isPending}
              className="flex items-center gap-1.5 px-4 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 border border-gray-700 rounded-lg text-xs font-medium"
            >
              {test.isPending ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
              Bağlantıyı test et
            </button>
            {testResult && (testResult.ok
              ? <span className="flex items-center gap-1 text-xs text-green-400"><CheckCircle2 size={13} /> {testResult.model} çalışıyor</span>
              : <span className="flex items-center gap-1 text-xs text-red-400"><XCircle size={13} /> {testResult.error}</span>)}
          </div>
        </div>
      )}
    </div>
  )
}
