import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, Trash2, KeyRound, Github, Smartphone, Store } from 'lucide-react'
import { api } from '@/lib/api'
import clsx from 'clsx'

interface Credential {
  id: string
  provider: string
  key_name: string
  updated_at: string
}

interface CredentialField {
  key_name: string
  label: string
  placeholder: string
  type?: string
}

interface ProviderSection {
  provider: string
  label: string
  icon: React.ComponentType<any>
  description: string
  fields: CredentialField[]
}

const PROVIDERS: ProviderSection[] = [
  {
    provider: 'eas',
    label: 'Expo EAS',
    icon: Smartphone,
    description: 'Build React Native & Expo apps via Expo Application Services.',
    fields: [
      { key_name: 'EAS_TOKEN', label: 'EAS Access Token', placeholder: 'eas_xxxxxxxxxxxx' },
      { key_name: 'EXPO_APP_ID', label: 'Expo App ID', placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx' },
    ],
  },
  {
    provider: 'codemagic',
    label: 'Codemagic',
    icon: Smartphone,
    description: 'Build Flutter apps via Codemagic CI/CD.',
    fields: [
      { key_name: 'CODEMAGIC_TOKEN', label: 'API Access Token', placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx' },
      { key_name: 'CODEMAGIC_APP_ID', label: 'App ID', placeholder: '64a1b2c3d4e5f6a7b8c9d0e1' },
    ],
  },
  {
    provider: 'google_play',
    label: 'Google Play',
    icon: Store,
    description: 'Deploy Android APK/AAB to Google Play Store.',
    fields: [{ key_name: 'GOOGLE_PLAY_KEY_JSON', label: 'Service Account Key (JSON)', placeholder: '{ "type": "service_account", ... }', type: 'textarea' }],
  },
  {
    provider: 'app_store',
    label: 'App Store Connect',
    icon: Store,
    description: 'Deploy iOS IPA to App Store via App Store Connect API.',
    fields: [
      { key_name: 'APP_STORE_KEY_ID', label: 'Key ID', placeholder: 'XXXXXXXXXX' },
      { key_name: 'APP_STORE_ISSUER_ID', label: 'Issuer ID', placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx' },
      { key_name: 'APP_STORE_PRIVATE_KEY', label: 'Private Key (.p8 content)', placeholder: '-----BEGIN PRIVATE KEY-----\n...', type: 'textarea' },
    ],
  },
]

function ProviderCard({ section, credentials }: { section: ProviderSection; credentials: Credential[] }) {
  const queryClient = useQueryClient()
  const [values, setValues] = useState<Record<string, string>>({})
  const [saved, setSaved] = useState<Record<string, boolean>>({})

  const saveMutation = useMutation({
    mutationFn: (vars: { key_name: string; value: string }) =>
      api.put('/credentials', { provider: section.provider, key_name: vars.key_name, value: vars.value }),
    onSuccess: (_, vars) => {
      setSaved((s) => ({ ...s, [vars.key_name]: true }))
      setTimeout(() => setSaved((s) => ({ ...s, [vars.key_name]: false })), 2000)
      setValues((v) => ({ ...v, [vars.key_name]: '' }))
      queryClient.invalidateQueries({ queryKey: ['credentials'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (key_name: string) => api.delete(`/credentials/${section.provider}/${key_name}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['credentials'] }),
  })

  const Icon = section.icon
  const connectedKeys = credentials.filter((c) => c.provider === section.provider).map((c) => c.key_name)
  const isFullyConnected = section.fields.every((f) => connectedKeys.includes(f.key_name))

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gray-800 rounded-lg flex items-center justify-center">
            <Icon size={18} className="text-gray-300" />
          </div>
          <div>
            <h3 className="font-semibold">{section.label}</h3>
            <p className="text-xs text-gray-500">{section.description}</p>
          </div>
        </div>
        {isFullyConnected && (
          <span className="flex items-center gap-1 text-xs text-green-400 bg-green-500/10 px-2 py-1 rounded-full">
            <Check size={11} /> Connected
          </span>
        )}
      </div>
      <div className="space-y-4">
        {section.fields.map((field) => {
          const isConnected = connectedKeys.includes(field.key_name)
          return (
            <div key={field.key_name}>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs text-gray-400">{field.label}</label>
                {isConnected && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-green-400">Saved</span>
                    <button
                      onClick={() => deleteMutation.mutate(field.key_name)}
                      className="text-gray-600 hover:text-red-400 transition-colors"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                )}
              </div>
              {field.type === 'textarea' ? (
                <textarea
                  value={values[field.key_name] ?? ''}
                  onChange={(e) => setValues((v) => ({ ...v, [field.key_name]: e.target.value }))}
                  placeholder={isConnected ? '•••••••••••• (saved)' : field.placeholder}
                  rows={3}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs font-mono outline-none focus:border-primary-500 transition-colors resize-none"
                />
              ) : (
                <input
                  type="password"
                  value={values[field.key_name] ?? ''}
                  onChange={(e) => setValues((v) => ({ ...v, [field.key_name]: e.target.value }))}
                  placeholder={isConnected ? '•••••••••••• (saved)' : field.placeholder}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors"
                />
              )}
              {values[field.key_name] && (
                <button
                  onClick={() => saveMutation.mutate({ key_name: field.key_name, value: values[field.key_name] })}
                  disabled={saveMutation.isPending}
                  className={clsx(
                    'mt-2 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                    saved[field.key_name]
                      ? 'bg-green-600 text-white'
                      : 'bg-primary-600 hover:bg-primary-700 text-white disabled:opacity-50'
                  )}
                >
                  {saved[field.key_name] ? <><Check size={11} /> Saved</> : 'Save'}
                </button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function SettingsPage() {
  const { data: credentials = [], isLoading } = useQuery<Credential[]>({
    queryKey: ['credentials'],
    queryFn: () => api.get('/credentials').then((r) => r.data),
  })

  const { data: profile } = useQuery({
    queryKey: ['github-profile'],
    queryFn: () => api.get('/github/profile').then((r) => r.data),
  })

  return (
    <div className="p-8 max-w-3xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-gray-400 text-sm mt-1">Manage your build provider credentials and integrations.</p>
      </div>

      <section className="mb-8">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4 flex items-center gap-2">
          <Github size={14} /> GitHub Connection
        </h2>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex items-center justify-between">
          <div>
            <p className="font-medium">GitHub</p>
            <p className="text-xs text-gray-500 mt-0.5">Connect your GitHub account to import repositories.</p>
          </div>
          {profile?.github_connected ? (
            <span className="flex items-center gap-1 text-xs text-green-400 bg-green-500/10 px-3 py-1.5 rounded-full">
              <Check size={11} /> Connected
            </span>
          ) : (
            <a
              href="/api/auth/github"
              className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-sm rounded-lg transition-colors"
            >
              <Github size={14} />
              Connect GitHub
            </a>
          )}
        </div>
      </section>

      <section className="mb-8">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4 flex items-center gap-2">
          <KeyRound size={14} /> Build Providers
        </h2>
        {isLoading ? (
          <p className="text-gray-500 text-sm">Loading credentials...</p>
        ) : (
          <div className="space-y-4">
            {PROVIDERS.map((section) => (
              <ProviderCard key={section.provider} section={section} credentials={credentials} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
