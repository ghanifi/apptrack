import React, { useState, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, Trash2, KeyRound, Github, Smartphone, Store, CreditCard, Bell, ArrowUpRight, Loader, Zap, Shield, Lock, Info, Wand2 } from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from 'sonner'
import clsx from 'clsx'
import type { CurrentPlan, PlanInfo, NotificationPreferences } from '@/types'

function InfoTooltip({ lines }: { lines: string[] }) {
  const [show, setShow] = useState(false)
  return (
    <span className="relative inline-block ml-1.5 align-middle">
      <span
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-gray-700 hover:bg-gray-600 cursor-help text-[10px] font-bold text-gray-400 hover:text-white transition-colors select-none"
      >
        i
      </span>
      {show && (
        <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-80 bg-gray-900 border border-gray-700 rounded-xl shadow-2xl p-4 text-left">
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2 rotate-45 w-2.5 h-2.5 bg-gray-900 border-r border-b border-gray-700" />
          <ol className="space-y-2">
            {lines.map((line, i) => (
              <li key={i} className="flex gap-2 text-xs text-gray-300 leading-relaxed">
                <span className="flex-shrink-0 w-5 h-5 bg-gray-800 rounded-full flex items-center justify-center text-[10px] font-bold text-gray-400 mt-0.5">
                  {i + 1}
                </span>
                <span>{line}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </span>
  )
}

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
    provider: 'github_actions',
    label: 'GitHub Actions',
    icon: Github,
    description: 'Default free build provider — uses your own GitHub Actions minutes.',
    fields: [
      {
        key_name: 'GITHUB_ACTIONS_TOKEN',
        label: 'Personal Access Token',
        placeholder: 'ghp_xxxxxxxxxxxxxxxxxxxx',
        helpText: 'GitHub > Settings > Developer settings > Personal access tokens. Needs "repo" and "workflow" scopes so AppTrack can push workflow files and dispatch builds. If you connected GitHub above, this is optional — the connection token is used as fallback.',
        helpUrl: 'https://github.com/settings/tokens',
      },
    ],
  },
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
        helpText: 'expo.dev > Account Settings > Access Tokens > Create Token. Create a "Personal Access Token" for CI/CD usage.',
        helpUrl: 'https://expo.dev/accounts/[account]/settings/access-tokens',
      },
      {
        key_name: 'EXPO_APP_ID',
        label: 'Expo App ID',
        placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
        helpText: 'expo.dev > Projects > select your project > the ID shown at the top of the page. Also found in app.json under "extra.eas.projectId".',
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
        helpText: 'Codemagic > User Settings > Integrations > Codemagic API > Show. Copy the displayed token.',
        helpUrl: 'https://codemagic.io/settings',
      },
      {
        key_name: 'CODEMAGIC_APP_ID',
        label: 'App ID',
        placeholder: '64a1b2c3d4e5f6a7b8c9d0e1',
        helpText: 'Codemagic > select your app > Settings > App ID. Also visible as the last segment in the URL.',
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
      helpText: 'Step 1: Go to Google Cloud Console > IAM & Admin > Service Accounts > Create Service Account.\nStep 2: Click the account > Keys tab > Add Key > Create new key > JSON. Download the file.\nStep 3: Go to Google Play Console > Users and Permissions > Invite User.\nStep 4: Enter the service account email (from the JSON file) and grant "Release to production" permission.\nStep 5: Paste the entire JSON file content here.',
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
        helpText: 'Step 1: Go to App Store Connect > Users and Access > Integrations > App Store Connect API.\nStep 2: Click "Generate API Key", name it (e.g. "AppTrack CI/CD"), select "Admin" or "Developer" role.\nStep 3: Copy the "Key ID" value shown in the table.',
        helpUrl: 'https://appstoreconnect.apple.com/access/integrations/api',
      },
      {
        key_name: 'APP_STORE_ISSUER_ID',
        label: 'Issuer ID',
        placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
        helpText: 'On the same page (App Store Connect > Integrations), the "Issuer ID" is shown at the top. It is the same for all keys in your account.',
        helpUrl: 'https://appstoreconnect.apple.com/access/integrations/api',
      },
      {
        key_name: 'APP_STORE_PRIVATE_KEY',
        label: 'Private Key (.p8 content)',
        placeholder: '-----BEGIN PRIVATE KEY-----\n...',
        type: 'textarea',
        helpText: 'Step 1: After generating the key, click "Download API Key" to get the .p8 file.\nStep 2: Important — it can only be downloaded ONCE! Save it securely.\nStep 3: Open the .p8 file with a text editor and paste the full content here (including the BEGIN/END lines).',
        helpUrl: 'https://developer.apple.com/documentation/appstoreconnectapi/creating-api-keys-for-app-store-connect-api',
      },
    ],
  },
  {
    provider: 'ios_signing',
    label: 'iOS Signing',
    icon: Shield,
    description: 'Code signing credentials for building signed IPA files. You can enter manually or use Auto-Generate below.',
    fields: [
      {
        key_name: 'IOS_CERT_P12_BASE64',
        label: 'Distribution Certificate (.p12, base64)',
        placeholder: 'Base64 encoded .p12 certificate',
        type: 'textarea',
        helpText: 'Tip: Use "Auto-Generate" below to create this automatically — no Mac needed. Manual: Keychain Access > My Certificates > Export (.p12). Convert: Mac: base64 -i cert.p12 | pbcopy / Windows: certutil -encode cert.p12 tmp.b64 / Linux: base64 cert.p12',
        helpUrl: 'https://developer.apple.com/help/account/certificates/certificates-overview',
      },
      {
        key_name: 'IOS_CERT_PASSWORD',
        label: 'Certificate Password',
        placeholder: 'P12 export password',
        helpText: 'Auto-generated if you use Auto-Generate. For manual: the password set when exporting .p12 from Keychain Access.',
      },
      {
        key_name: 'IOS_PROVISIONING_PROFILE_BASE64',
        label: 'Provisioning Profile (base64)',
        placeholder: 'Base64 encoded .mobileprovision',
        type: 'textarea',
        helpText: 'Auto-generated if you provide a Bundle ID during Auto-Generate. Manual: Apple Developer > Profiles > Download .mobileprovision. Convert: Mac: base64 -i file | pbcopy / Windows: certutil -encode file tmp.b64 / Linux: base64 file',
        helpUrl: 'https://developer.apple.com/account/resources/profiles/list',
      },
    ],
  },
  {
    provider: 'android_signing',
    label: 'Android Signing',
    icon: Lock,
    description: 'Keystore credentials for building signed AAB files. You can enter manually or use Auto-Generate below.',
    fields: [
      {
        key_name: 'ANDROID_KEYSTORE_BASE64',
        label: 'Keystore File (base64)',
        placeholder: 'Base64 encoded .keystore or .jks file',
        type: 'textarea',
        helpText: 'Tip: Use "Auto-Generate" below to create this automatically — no keytool needed. Manual: keytool -genkey -v -keystore release.keystore -alias my-alias -keyalg RSA -keysize 2048 -validity 10000. Convert: Mac: base64 -i file | pbcopy / Windows: certutil -encode file tmp.b64 / Linux: base64 file',
        helpUrl: 'https://developer.android.com/studio/publish/app-signing',
      },
      {
        key_name: 'ANDROID_KEYSTORE_PASSWORD',
        label: 'Keystore Password',
        placeholder: 'Keystore password',
        helpText: 'Auto-generated if you use Auto-Generate. For manual: the password set with -storepass when generating the keystore via keytool.',
      },
      {
        key_name: 'ANDROID_KEY_ALIAS',
        label: 'Key Alias',
        placeholder: 'my-key-alias',
        helpText: 'Auto-generated if you use Auto-Generate (default: "upload"). For manual: the alias set with -alias when generating the keystore.',
      },
      {
        key_name: 'ANDROID_KEY_PASSWORD',
        label: 'Key Password',
        placeholder: 'Key password',
        helpText: 'Auto-generated if you use Auto-Generate (same as keystore password). For manual: the password set with -keypass.',
      },
    ],
  },
]

/* InfoTooltip for individual fields — uses the top-level InfoTooltip with single-item list */
function FieldInfoTooltip({ text, url }: { text: string; url?: string }) {
  const [show, setShow] = useState(false)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleEnter = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    setShow(true)
  }
  const handleLeave = () => {
    timeoutRef.current = setTimeout(() => setShow(false), 150)
  }

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
    >
      <Info size={13} className="text-gray-500 hover:text-blue-400 cursor-help transition-colors" />
      {show && (
        <div
          className="absolute left-0 bottom-full mb-1 w-72 p-3 bg-gray-900 border border-gray-600 rounded-lg shadow-xl text-xs text-gray-300 whitespace-pre-line leading-relaxed"
          style={{ zIndex: 9999 }}
          onMouseEnter={handleEnter}
          onMouseLeave={handleLeave}
        >
          {text}
          {url && (
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 mt-2 text-blue-400 hover:text-blue-300 hover:underline"
            >
              <ArrowUpRight size={11} /> Open guide
            </a>
          )}
          <div className="absolute top-full left-4 w-0 h-0 border-l-[6px] border-r-[6px] border-t-[6px] border-l-transparent border-r-transparent border-t-gray-600" />
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
                  {field.helpText && <FieldInfoTooltip text={field.helpText} url={field.helpUrl} />}
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

function AutoGenerateIOS({ credentials }: { credentials: Credential[] }) {
  const queryClient = useQueryClient()
  const [bundleId, setBundleId] = useState('')
  const [expanded, setExpanded] = useState(false)

  const hasAppStoreKeys = ['APP_STORE_KEY_ID', 'APP_STORE_ISSUER_ID', 'APP_STORE_PRIVATE_KEY'].every(
    (k) => credentials.some((c) => c.provider === 'app_store' && c.key_name === k)
  )

  const hasIosSigning = ['IOS_CERT_P12_BASE64', 'IOS_CERT_PASSWORD'].every(
    (k) => credentials.some((c) => c.provider === 'ios_signing' && c.key_name === k)
  )

  const generateMutation = useMutation({
    mutationFn: (data: { bundle_id?: string }) =>
      api.post('/signing/auto-generate-ios', data).then((r) => r.data),
    onSuccess: (data) => {
      toast.success(data.message)
      queryClient.invalidateQueries({ queryKey: ['credentials'] })
      setExpanded(false)
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to generate certificates')
    },
  })

  return (
    <div className="bg-gradient-to-r from-blue-900/20 to-purple-900/20 border border-blue-800/40 rounded-xl p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-blue-600/20 rounded-lg flex items-center justify-center">
            <Wand2 size={18} className="text-blue-400" />
          </div>
          <div>
            <h3 className="font-semibold text-blue-100">
              Auto-Generate iOS Certificates
              <InfoTooltip lines={[
                'Create an App Store Connect API Key from your Apple Developer account (developer.apple.com > Users and Access > Integrations > App Store Connect API).',
                'Save the Key ID, Issuer ID and .p8 file in the "App Store Connect" section above.',
                'Click "Generate" — the server will automatically create a Distribution Certificate (.p12) and Provisioning Profile.',
                'Generated certificates are saved automatically. If you enter a Bundle ID, a Provisioning Profile will also be created.',
                'Now when you trigger an iOS build, a signed IPA will be produced and can be uploaded to App Store / TestFlight.',
              ]} />
            </h3>
            <p className="text-xs text-blue-300/70">
              {!hasAppStoreKeys
                ? 'First save your App Store Connect keys above, then generate certificates here — no Mac needed.'
                : hasIosSigning
                  ? 'Certificates already generated. You can regenerate if needed.'
                  : 'No Mac required — generates certificates automatically via Apple API.'}
            </p>
          </div>
        </div>
        <button
          onClick={() => hasAppStoreKeys ? setExpanded(!expanded) : toast.error('Save your App Store Connect Key ID, Issuer ID, and Private Key (.p8) first.')}
          className={clsx(
            'px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2',
            expanded
              ? 'bg-gray-700 hover:bg-gray-600 text-gray-300'
              : !hasAppStoreKeys
                ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-700 text-white'
          )}
        >
          <Wand2 size={14} />
          {expanded ? 'Cancel' : hasIosSigning ? 'Regenerate' : 'Generate'}
        </button>
      </div>

      {expanded && hasAppStoreKeys && (
        <div className="mt-4 pt-4 border-t border-blue-800/30 space-y-3">
          <div>
            <label className="text-xs text-blue-300/70 block mb-1">
              Bundle ID <span className="text-gray-500">(optional — for provisioning profile)</span>
            </label>
            <input
              type="text"
              value={bundleId}
              onChange={(e) => setBundleId(e.target.value)}
              placeholder="com.yourcompany.appname"
              className="w-full bg-gray-800/80 border border-blue-800/40 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500 transition-colors"
            />
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => generateMutation.mutate({ bundle_id: bundleId || undefined })}
              disabled={generateMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
            >
              {generateMutation.isPending ? (
                <><Loader size={14} className="animate-spin" /> Generating...</>
              ) : (
                <><Wand2 size={14} /> Generate Certificates</>
              )}
            </button>
            <p className="text-xs text-blue-300/50">
              Uses your App Store Connect API key to create certificates server-side.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

function AutoGenerateAndroid({ credentials }: { credentials: Credential[] }) {
  const queryClient = useQueryClient()
  const [expanded, setExpanded] = useState(false)
  const [keyAlias, setKeyAlias] = useState('upload')
  const [keystorePassword, setKeystorePassword] = useState('')
  const [organization, setOrganization] = useState('')

  const hasAndroidSigning = ['ANDROID_KEYSTORE_BASE64', 'ANDROID_KEYSTORE_PASSWORD', 'ANDROID_KEY_ALIAS'].every(
    (k) => credentials.some((c) => c.provider === 'android_signing' && c.key_name === k)
  )

  const generateMutation = useMutation({
    mutationFn: (data: { key_alias: string; keystore_password: string; organization?: string }) =>
      api.post('/signing/auto-generate-android', data).then((r) => r.data),
    onSuccess: (data) => {
      toast.success(data.message)
      queryClient.invalidateQueries({ queryKey: ['credentials'] })
      setExpanded(false)
      setKeystorePassword('')
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to generate keystore')
    },
  })

  return (
    <div className="bg-gradient-to-r from-green-900/20 to-emerald-900/20 border border-green-800/40 rounded-xl p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-green-600/20 rounded-lg flex items-center justify-center">
            <Wand2 size={18} className="text-green-400" />
          </div>
          <div>
            <h3 className="font-semibold text-green-100">
              Auto-Generate Android Keystore
              <InfoTooltip lines={[
                'Enter a Key Alias (default: "upload"). This is the identifier for the key inside the keystore.',
                'Set a Keystore Password (min 6 characters). Keep this password safe — you\'ll need it if you ever re-sign.',
                'Organization field is optional — enter your company name (appears in the certificate info).',
                'Click "Generate Keystore" — the server creates a .jks file automatically and saves it as base64.',
                'Now when you trigger an Android build, a signed AAB/APK will be produced and can be uploaded to Google Play.',
              ]} />
            </h3>
            <p className="text-xs text-green-300/70">
              {hasAndroidSigning
                ? 'Keystore already generated. You can regenerate if needed.'
                : 'No keytool or JDK needed — generates release keystore automatically on the server.'}
            </p>
          </div>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className={clsx(
            'px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2',
            expanded
              ? 'bg-gray-700 hover:bg-gray-600 text-gray-300'
              : 'bg-green-600 hover:bg-green-700 text-white'
          )}
        >
          <Wand2 size={14} />
          {expanded ? 'Cancel' : hasAndroidSigning ? 'Regenerate' : 'Generate'}
        </button>
      </div>

      {expanded && (
        <div className="mt-4 pt-4 border-t border-green-800/30 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-green-300/70 block mb-1">Key Alias</label>
              <input
                type="text"
                value={keyAlias}
                onChange={(e) => setKeyAlias(e.target.value)}
                placeholder="upload"
                className="w-full bg-gray-800/80 border border-green-800/40 rounded-lg px-3 py-2 text-sm outline-none focus:border-green-500 transition-colors"
              />
            </div>
            <div>
              <label className="text-xs text-green-300/70 block mb-1">
                Keystore Password <span className="text-gray-500">(min 6 chars)</span>
              </label>
              <input
                type="password"
                value={keystorePassword}
                onChange={(e) => setKeystorePassword(e.target.value)}
                placeholder="Enter password"
                className="w-full bg-gray-800/80 border border-green-800/40 rounded-lg px-3 py-2 text-sm outline-none focus:border-green-500 transition-colors"
              />
            </div>
          </div>
          <div>
            <label className="text-xs text-green-300/70 block mb-1">
              Organization <span className="text-gray-500">(optional)</span>
            </label>
            <input
              type="text"
              value={organization}
              onChange={(e) => setOrganization(e.target.value)}
              placeholder="Your Company Name"
              className="w-full bg-gray-800/80 border border-green-800/40 rounded-lg px-3 py-2 text-sm outline-none focus:border-green-500 transition-colors"
            />
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                if (!keystorePassword || keystorePassword.length < 6) {
                  toast.error('Keystore password must be at least 6 characters.')
                  return
                }
                generateMutation.mutate({
                  key_alias: keyAlias || 'upload',
                  keystore_password: keystorePassword,
                  ...(organization ? { organization } : {}),
                })
              }}
              disabled={generateMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
            >
              {generateMutation.isPending ? (
                <><Loader size={14} className="animate-spin" /> Generating...</>
              ) : (
                <><Wand2 size={14} /> Generate Keystore</>
              )}
            </button>
            <p className="text-xs text-green-300/50">
              Generates RSA 2048 key + self-signed certificate (25 year validity).
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

const PLAN_FEATURES: Record<string, string[]> = {
  free: ['3 Projects', '10 Builds/mo', '5 Deploys/mo', '500 MB Storage', '1 Concurrent Build'],
  pro: ['20 Projects', '100 Builds/mo', '50 Deploys/mo', '5 GB Storage', '5 Concurrent Builds'],
  enterprise: ['999 Projects', '999 Builds/mo', '999 Deploys/mo', '50 GB Storage', '20 Concurrent Builds'],
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
    onError: () => {},
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
          {plan !== 'free' && currentPlan?.stripe_configured && (
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
    <div className="p-8 max-w-3xl mx-auto">
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
              <React.Fragment key={section.provider}>
                <ProviderCard section={section} credentials={credentials} />
                {section.provider === 'ios_signing' && (
                  <AutoGenerateIOS credentials={credentials} />
                )}
                {section.provider === 'android_signing' && (
                  <AutoGenerateAndroid credentials={credentials} />
                )}
              </React.Fragment>
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
