import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, Trash2, KeyRound, Github, Smartphone, Store, CreditCard, Bell, ArrowUpRight, Loader, Zap, Shield, Lock, Info } from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from 'sonner'
import clsx from 'clsx'
import type { CurrentPlan, PlanInfo, NotificationPreferences } from '@/types'

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
  helpText?: string
  helpUrl?: string
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
      {
        key_name: 'EAS_TOKEN',
        label: 'EAS Access Token',
        placeholder: 'eas_xxxxxxxxxxxx',
        helpText: 'expo.dev > Account Settings > Access Tokens > Create Token. CI/CD icin "Personal Access Token" olusturun.',
        helpUrl: 'https://expo.dev/accounts/[account]/settings/access-tokens',
      },
      {
        key_name: 'EXPO_APP_ID',
        label: 'Expo App ID',
        placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
        helpText: 'expo.dev > Projects > projenizi secin > sayfanin ust kismindaki ID. "app.json" dosyasindaki "extra.eas.projectId" alanidir.',
        helpUrl: 'https://expo.dev',
      },
    ],
  },
  {
    provider: 'codemagic',
    label: 'Codemagic',
    icon: Smartphone,
    description: 'Build Flutter apps via Codemagic CI/CD.',
    fields: [
      {
        key_name: 'CODEMAGIC_TOKEN',
        label: 'API Access Token',
        placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
        helpText: 'Codemagic > User Settings > Integrations > Codemagic API > Show. Token\'i kopyalayin.',
        helpUrl: 'https://codemagic.io/settings',
      },
      {
        key_name: 'CODEMAGIC_APP_ID',
        label: 'App ID',
        placeholder: '64a1b2c3d4e5f6a7b8c9d0e1',
        helpText: 'Codemagic > uygulamanizi secin > Settings > App ID. URL\'deki son segment de App ID\'dir.',
        helpUrl: 'https://codemagic.io/apps',
      },
    ],
  },
  {
    provider: 'google_play',
    label: 'Google Play',
    icon: Store,
    description: 'Deploy Android AAB to Google Play Store.',
    fields: [{
      key_name: 'GOOGLE_PLAY_KEY_JSON',
      label: 'Service Account Key (JSON)',
      placeholder: '{ "type": "service_account", ... }',
      type: 'textarea',
      helpText: '1) Google Cloud Console > IAM & Admin > Service Accounts > Create\n2) Actions > Manage Keys > Add Key > JSON\n3) Google Play Console > Users & Permissions > Invite > service account e-posta adresini ekleyin ve "Release" izni verin.',
      helpUrl: 'https://console.cloud.google.com/iam-admin/serviceaccounts',
    }],
  },
  {
    provider: 'app_store',
    label: 'App Store Connect',
    icon: Store,
    description: 'Deploy iOS IPA to App Store via App Store Connect API.',
    fields: [
      {
        key_name: 'APP_STORE_KEY_ID',
        label: 'Key ID',
        placeholder: 'XXXXXXXXXX',
        helpText: 'App Store Connect > Users and Access > Integrations > Team Keys > Generate API Key. Olusturulan key\'in "Key ID" sutunundaki deger.',
        helpUrl: 'https://appstoreconnect.apple.com/access/integrations/api',
      },
      {
        key_name: 'APP_STORE_ISSUER_ID',
        label: 'Issuer ID',
        placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
        helpText: 'App Store Connect > Users and Access > Integrations > sayfanin ust kismindaki "Issuer ID". Tum keyler icin aynidir.',
        helpUrl: 'https://appstoreconnect.apple.com/access/integrations/api',
      },
      {
        key_name: 'APP_STORE_PRIVATE_KEY',
        label: 'Private Key (.p8 content)',
        placeholder: '-----BEGIN PRIVATE KEY-----\n...',
        type: 'textarea',
        helpText: 'Key olusturduktan sonra "Download API Key" ile .p8 dosyasini indirin. Sadece 1 kez indirilebilir! Dosya icerigini buraya yapisttirin.',
        helpUrl: 'https://developer.apple.com/documentation/appstoreconnectapi/creating-api-keys-for-app-store-connect-api',
      },
    ],
  },
  {
    provider: 'ios_signing',
    label: 'iOS Signing',
    icon: Shield,
    description: 'Code signing credentials for building signed IPA files. Required for App Store submission.',
    fields: [
      {
        key_name: 'IOS_CERT_P12_BASE64',
        label: 'Distribution Certificate (.p12, base64)',
        placeholder: 'Base64 encoded .p12 certificate',
        type: 'textarea',
        helpText: 'Mac\'te Keychain Access > My Certificates > iOS Distribution sertifikasini secin > sag tik > Export (.p12). Sonra terminalde: base64 -i certificate.p12 | pbcopy',
        helpUrl: 'https://developer.apple.com/help/account/certificates/certificates-overview',
      },
      {
        key_name: 'IOS_CERT_PASSWORD',
        label: 'Certificate Password',
        placeholder: 'P12 export password',
        helpText: 'Keychain Access\'ten .p12 dosyasini disari aktarirken belirlediginiz sifre. Bos birakmadiysiniz buraya ayni sifreyi girin.',
      },
      {
        key_name: 'IOS_PROVISIONING_PROFILE_BASE64',
        label: 'Provisioning Profile (base64)',
        placeholder: 'Base64 encoded .mobileprovision',
        type: 'textarea',
        helpText: 'Apple Developer > Certificates, Identifiers & Profiles > Profiles > Distribution profilinizi secin > Download. Sonra terminalde: base64 -i profile.mobileprovision | pbcopy',
        helpUrl: 'https://developer.apple.com/account/resources/profiles/list',
      },
    ],
  },
  {
    provider: 'android_signing',
    label: 'Android Signing',
    icon: Lock,
    description: 'Keystore credentials for building signed AAB files. Required for Play Store submission.',
    fields: [
      {
        key_name: 'ANDROID_KEYSTORE_BASE64',
        label: 'Keystore File (base64)',
        placeholder: 'Base64 encoded .keystore or .jks file',
        type: 'textarea',
        helpText: 'Keystore olusturma: keytool -genkey -v -keystore release.keystore -alias my-alias -keyalg RSA -keysize 2048 -validity 10000. Sonra: base64 -i release.keystore | pbcopy (Mac) veya base64 release.keystore (Linux)',
        helpUrl: 'https://developer.android.com/studio/publish/app-signing',
      },
      {
        key_name: 'ANDROID_KEYSTORE_PASSWORD',
        label: 'Keystore Password',
        placeholder: 'Keystore password',
        helpText: 'keytool komutuyla keystore olustururken -storepass ile belirlediginiz sifre.',
      },
      {
        key_name: 'ANDROID_KEY_ALIAS',
        label: 'Key Alias',
        placeholder: 'my-key-alias',
        helpText: 'keytool komutuyla keystore olustururken -alias ile belirlediginiz isim. Varsayilan olarak "my-alias" veya "upload" kullanilir.',
      },
      {
        key_name: 'ANDROID_KEY_PASSWORD',
        label: 'Key Password',
        placeholder: 'Key password',
        helpText: 'keytool komutuyla keystore olustururken -keypass ile belirlediginiz sifre. Genellikle keystore sifresiyle aynidir.',
      },
    ],
  },
]

function InfoTooltip({ text, url }: { text: string; url?: string }) {
  const [show, setShow] = useState(false)
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <Info size={13} className="text-gray-500 hover:text-blue-400 cursor-help transition-colors" />
      {show && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 w-72 p-3 bg-gray-900 border border-gray-600 rounded-lg shadow-xl text-xs text-gray-300 whitespace-pre-line leading-relaxed">
          {text}
          {url && (
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 mt-2 text-blue-400 hover:text-blue-300 hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              <ArrowUpRight size={11} /> Ilgili sayfa
            </a>
          )}
          <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-[6px] border-r-[6px] border-t-[6px] border-l-transparent border-r-transparent border-t-gray-600" />
        </div>
      )}
    </span>
  )
}

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
                <label className="flex items-center gap-1.5 text-xs text-gray-400">
                  {field.label}
                  {field.helpText && <InfoTooltip text={field.helpText} url={field.helpUrl} />}
                </label>
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

const PLAN_FEATURES: Record<string, string[]> = {
  free: ['3 Projects', '10 Builds/mo', '5 Deploys/mo', '500 MB Storage', '1 Concurrent Build'],
  pro: ['20 Projects', '100 Builds/mo', '50 Deploys/mo', '5 GB Storage', '5 Concurrent Builds'],
  enterprise: ['Unlimited Projects', 'Unlimited Builds', 'Unlimited Deploys', '50 GB Storage', '20 Concurrent Builds'],
}

function BillingSection() {
  const { data: currentPlan, isLoading } = useQuery<CurrentPlan>({
    queryKey: ['billing-current'],
    queryFn: () => api.get('/billing/current').then((r) => r.data),
  })

  const { data: plansData } = useQuery<{ plans: PlanInfo[] }>({
    queryKey: ['billing-plans'],
    queryFn: () => api.get('/billing/plans').then((r) => r.data),
  })

  const upgradeMutation = useMutation({
    mutationFn: (plan: string) => api.post(`/billing/upgrade?plan=${plan}`).then((r) => r.data),
    onSuccess: (data) => {
      if (data.checkout_url) {
        window.location.href = data.checkout_url
      } else {
        toast.info(data.message || 'Upgrade initiated')
      }
    },
  })

  const portalMutation = useMutation({
    mutationFn: () => api.post('/billing/portal').then((r) => r.data),
    onSuccess: (data) => {
      if (data.portal_url) {
        window.open(data.portal_url, '_blank')
      }
    },
  })

  if (isLoading) return <p className="text-gray-500 text-sm">Loading billing...</p>

  const plan = currentPlan?.plan ?? 'free'
  const planOrder = ['free', 'pro', 'enterprise']
  const currentIdx = planOrder.indexOf(plan)

  return (
    <div className="space-y-4">
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider">Current Plan</p>
            <p className="text-xl font-bold mt-1 capitalize">{plan}</p>
            <p className="text-sm text-gray-400 mt-0.5">${currentPlan?.price_usd ?? 0}/month</p>
          </div>
          {plan !== 'free' && (
            <button
              onClick={() => portalMutation.mutate()}
              disabled={portalMutation.isPending}
              className="flex items-center gap-1.5 px-4 py-2 text-sm bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors"
            >
              {portalMutation.isPending ? <Loader size={14} className="animate-spin" /> : <ArrowUpRight size={14} />}
              Manage Subscription
            </button>
          )}
        </div>
      </div>

      {planOrder.filter((p) => planOrder.indexOf(p) > currentIdx).length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {planOrder
            .filter((p) => planOrder.indexOf(p) > currentIdx)
            .map((p) => {
              const planInfo = plansData?.plans.find((pl) => pl.name === p)
              const features = PLAN_FEATURES[p] ?? []
              return (
                <div key={p} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <h4 className="font-semibold capitalize">{p}</h4>
                      <p className="text-sm text-gray-400">${planInfo?.price_usd ?? 0}/month</p>
                    </div>
                    <Zap size={18} className="text-primary-400" />
                  </div>
                  <ul className="space-y-1.5 mb-4">
                    {features.map((f) => (
                      <li key={f} className="text-xs text-gray-400 flex items-center gap-1.5">
                        <Check size={11} className="text-green-400" /> {f}
                      </li>
                    ))}
                  </ul>
                  <button
                    onClick={() => upgradeMutation.mutate(p)}
                    disabled={upgradeMutation.isPending}
                    className="w-full py-2 text-sm font-medium bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors disabled:opacity-50"
                  >
                    {upgradeMutation.isPending ? 'Processing...' : `Upgrade to ${p}`}
                  </button>
                </div>
              )
            })}
        </div>
      )}
    </div>
  )
}

function NotificationSection() {
  const queryClient = useQueryClient()
  const { data: prefs, isLoading } = useQuery<NotificationPreferences>({
    queryKey: ['notification-prefs'],
    queryFn: () => api.get('/notifications/preferences').then((r) => r.data),
  })

  const updateMutation = useMutation({
    mutationFn: (updates: Partial<NotificationPreferences>) =>
      api.put('/notifications/preferences', updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notification-prefs'] })
      toast.success('Notification preferences saved')
    },
  })

  const [webhookValues, setWebhookValues] = useState<Record<string, string>>({})

  if (isLoading) return <p className="text-gray-500 text-sm">Loading preferences...</p>
  if (!prefs) return null

  const toggles: { key: keyof NotificationPreferences; label: string; group: string }[] = [
    { key: 'in_app_enabled', label: 'In-App Notifications', group: 'Channels' },
    { key: 'email_enabled', label: 'Email Notifications', group: 'Channels' },
    { key: 'slack_enabled', label: 'Slack Notifications', group: 'Channels' },
    { key: 'discord_enabled', label: 'Discord Notifications', group: 'Channels' },
    { key: 'notify_build_success', label: 'Build Success', group: 'Events' },
    { key: 'notify_build_failed', label: 'Build Failed', group: 'Events' },
    { key: 'notify_deploy_completed', label: 'Deploy Completed', group: 'Events' },
    { key: 'notify_deploy_failed', label: 'Deploy Failed', group: 'Events' },
    { key: 'notify_quota_warning', label: 'Quota Warnings', group: 'Events' },
  ]

  const groups = [...new Set(toggles.map((t) => t.group))]

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-6">
      {groups.map((group) => (
        <div key={group}>
          <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-3">{group}</h4>
          <div className="space-y-3">
            {toggles
              .filter((t) => t.group === group)
              .map((t) => (
                <label key={t.key} className="flex items-center justify-between cursor-pointer">
                  <span className="text-sm text-gray-300">{t.label}</span>
                  <button
                    onClick={() => updateMutation.mutate({ [t.key]: !prefs[t.key] })}
                    className={clsx(
                      'w-9 h-5 rounded-full transition-colors relative',
                      prefs[t.key] ? 'bg-primary-600' : 'bg-gray-700'
                    )}
                  >
                    <span
                      className={clsx(
                        'absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform',
                        prefs[t.key] ? 'translate-x-4' : 'translate-x-0.5'
                      )}
                    />
                  </button>
                </label>
              ))}
          </div>
        </div>
      ))}

      {prefs.slack_enabled && (
        <div>
          <label className="text-xs text-gray-400 block mb-1">Slack Webhook URL</label>
          <div className="flex gap-2">
            <input
              type="url"
              placeholder={prefs.slack_webhook_url || 'https://hooks.slack.com/services/...'}
              value={webhookValues.slack ?? ''}
              onChange={(e) => setWebhookValues((v) => ({ ...v, slack: e.target.value }))}
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
            />
            {webhookValues.slack && (
              <button
                onClick={() => {
                  updateMutation.mutate({ slack_webhook_url: webhookValues.slack } as any)
                  setWebhookValues((v) => ({ ...v, slack: '' }))
                }}
                className="px-3 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg text-xs font-medium"
              >
                Save
              </button>
            )}
          </div>
        </div>
      )}

      {prefs.discord_enabled && (
        <div>
          <label className="text-xs text-gray-400 block mb-1">Discord Webhook URL</label>
          <div className="flex gap-2">
            <input
              type="url"
              placeholder={prefs.discord_webhook_url || 'https://discord.com/api/webhooks/...'}
              value={webhookValues.discord ?? ''}
              onChange={(e) => setWebhookValues((v) => ({ ...v, discord: e.target.value }))}
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
            />
            {webhookValues.discord && (
              <button
                onClick={() => {
                  updateMutation.mutate({ discord_webhook_url: webhookValues.discord } as any)
                  setWebhookValues((v) => ({ ...v, discord: '' }))
                }}
                className="px-3 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg text-xs font-medium"
              >
                Save
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default function SettingsPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  useEffect(() => {
    const billing = searchParams.get('billing')
    if (billing === 'success') {
      toast.success('Plan upgraded successfully!')
      setSearchParams({}, { replace: true })
    } else if (billing === 'cancelled') {
      toast.info('Upgrade cancelled')
      setSearchParams({}, { replace: true })
    }
  }, [searchParams, setSearchParams])

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
          <CreditCard size={14} /> Billing & Plan
        </h2>
        <BillingSection />
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

      <section className="mb-8">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4 flex items-center gap-2">
          <Bell size={14} /> Notification Preferences
        </h2>
        <NotificationSection />
      </section>
    </div>
  )
}
