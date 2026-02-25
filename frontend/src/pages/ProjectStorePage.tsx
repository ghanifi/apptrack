import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, Smartphone, Monitor, Image, FileText, Save, Upload,
  Check, AlertCircle, Globe, Star, X, Plus, Eye,
} from 'lucide-react'
import { api } from '@/lib/api'
import type { Project, StoreMetadata } from '@/types'
import clsx from 'clsx'

type Platform = 'android' | 'ios'
type Tab = 'preview' | 'metadata' | 'assets'

const ANDROID_CATEGORIES = [
  'Art & Design', 'Auto & Vehicles', 'Beauty', 'Books & Reference',
  'Business', 'Comics', 'Communication', 'Dating', 'Education',
  'Entertainment', 'Events', 'Finance', 'Food & Drink', 'Health & Fitness',
  'House & Home', 'Libraries & Demo', 'Lifestyle', 'Maps & Navigation',
  'Medical', 'Music & Audio', 'News & Magazines', 'Parenting',
  'Personalization', 'Photography', 'Productivity', 'Shopping', 'Social',
  'Sports', 'Tools', 'Travel & Local', 'Video Players & Editors', 'Weather',
]

const IOS_CATEGORIES = [
  'Books', 'Business', 'Developer Tools', 'Education', 'Entertainment',
  'Finance', 'Food & Drink', 'Games', 'Graphics & Design', 'Health & Fitness',
  'Lifestyle', 'Medical', 'Music', 'Navigation', 'News', 'Photo & Video',
  'Productivity', 'Reference', 'Shopping', 'Social Networking', 'Sports',
  'Travel', 'Utilities', 'Weather',
]

function PhoneMockup({ platform, meta }: { platform: Platform; meta: StoreMetadata | null }) {
  const isIos = platform === 'ios'
  const appName = meta?.app_name || 'Your App'
  const shortDesc = meta?.short_description || 'Short description will appear here'
  const iconUrl = meta?.icon_url
  const version = meta?.version || '1.0.0'
  const category = meta?.category || 'Category'
  const screenshots = meta?.screenshots?.phone || []

  return (
    <div className={clsx(
      'relative mx-auto',
      isIos ? 'w-[280px]' : 'w-[270px]'
    )}>
      <div className={clsx(
        'bg-gray-950 border-2 rounded-[2.5rem] p-2 shadow-2xl',
        isIos ? 'border-gray-600' : 'border-gray-700'
      )}>
        {isIos && (
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-28 h-6 bg-gray-950 rounded-b-2xl z-10 border-b-2 border-x-2 border-gray-600" />
        )}

        <div className={clsx(
          'bg-white rounded-[2rem] overflow-hidden',
          isIos ? 'pt-8' : 'pt-6'
        )}>
          {!isIos && (
            <div className="flex items-center justify-between px-4 py-1 bg-gray-100">
              <span className="text-[9px] text-gray-500">9:41</span>
              <div className="flex gap-1">
                <div className="w-3 h-2 bg-gray-400 rounded-sm" />
                <div className="w-2 h-2 bg-gray-400 rounded-sm" />
              </div>
            </div>
          )}

          <div className="px-4 py-3 border-b border-gray-100">
            <div className="flex items-start gap-3">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center overflow-hidden flex-shrink-0">
                {iconUrl ? (
                  <img src={iconUrl} alt="icon" className="w-full h-full object-cover" />
                ) : (
                  <Smartphone size={24} className="text-white" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-gray-900 truncate">{appName}</p>
                <p className="text-[10px] text-gray-500">{category}</p>
                <div className="flex items-center gap-1 mt-1">
                  <div className="flex">
                    {[1, 2, 3, 4, 5].map(s => (
                      <Star key={s} size={8} className="text-yellow-400 fill-yellow-400" />
                    ))}
                  </div>
                  <span className="text-[9px] text-gray-400">4.8 (127)</span>
                </div>
              </div>
              <button className="bg-blue-500 text-white text-[10px] font-semibold px-3 py-1 rounded-full flex-shrink-0">
                {isIos ? 'GET' : 'Install'}
              </button>
            </div>
          </div>

          {screenshots.length > 0 ? (
            <div className="px-4 py-3 flex gap-2 overflow-x-auto">
              {screenshots.slice(0, 3).map((url, i) => (
                <div key={i} className="w-20 h-36 bg-gray-100 rounded-lg flex-shrink-0 overflow-hidden">
                  <img src={url} alt={`screenshot ${i + 1}`} className="w-full h-full object-cover" />
                </div>
              ))}
            </div>
          ) : (
            <div className="px-4 py-3 flex gap-2">
              {[1, 2, 3].map(i => (
                <div key={i} className="w-20 h-36 bg-gray-100 rounded-lg flex-shrink-0 flex items-center justify-center">
                  <Image size={16} className="text-gray-300" />
                </div>
              ))}
            </div>
          )}

          <div className="px-4 py-3 border-t border-gray-100">
            <p className="text-[11px] text-gray-600 leading-relaxed line-clamp-3">
              {shortDesc}
            </p>
          </div>

          <div className="px-4 py-2 border-t border-gray-100 flex items-center justify-between">
            <span className="text-[9px] text-gray-400">Version {version}</span>
            <span className="text-[9px] text-gray-400">{meta?.bundle_id || 'com.example.app'}</span>
          </div>

          <div className="h-4" />
        </div>
      </div>

      <div className="text-center mt-3">
        <span className={clsx(
          'text-xs font-medium px-3 py-1 rounded-full',
          isIos ? 'bg-gray-700 text-gray-300' : 'bg-green-900/50 text-green-300'
        )}>
          {isIos ? 'App Store Preview' : 'Google Play Preview'}
        </span>
      </div>
    </div>
  )
}

function MetadataForm({
  platform,
  meta,
  onSave,
  isSaving,
}: {
  platform: Platform
  meta: StoreMetadata | null
  onSave: (data: Partial<StoreMetadata>) => void
  isSaving: boolean
}) {
  const [form, setForm] = useState({
    app_name: meta?.app_name || '',
    short_description: meta?.short_description || '',
    full_description: meta?.full_description || '',
    keywords: meta?.keywords || '',
    privacy_url: meta?.privacy_url || '',
    support_url: meta?.support_url || '',
    marketing_url: meta?.marketing_url || '',
    category: meta?.category || '',
    bundle_id: meta?.bundle_id || '',
    version: meta?.version || '',
  })

  const categories = platform === 'ios' ? IOS_CATEGORIES : ANDROID_CATEGORIES
  const maxShort = platform === 'ios' ? 30 : 80

  const handleSave = () => {
    onSave(form)
  }

  return (
    <div className="space-y-5">
      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">App Name *</label>
          <input
            value={form.app_name}
            onChange={e => setForm(f => ({ ...f, app_name: e.target.value }))}
            placeholder={platform === 'ios' ? 'My Amazing App' : 'My Amazing App'}
            maxLength={50}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors"
          />
          <p className="text-[10px] text-gray-600 mt-1">{form.app_name.length}/50</p>
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">Bundle ID / Package Name *</label>
          <input
            value={form.bundle_id}
            onChange={e => setForm(f => ({ ...f, bundle_id: e.target.value }))}
            placeholder={platform === 'ios' ? 'com.company.appname' : 'com.company.appname'}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors"
          />
        </div>
      </div>

      <div>
        <label className="block text-xs text-gray-400 mb-1.5">
          {platform === 'ios' ? 'Subtitle' : 'Short Description'} *
        </label>
        <input
          value={form.short_description}
          onChange={e => setForm(f => ({ ...f, short_description: e.target.value }))}
          placeholder="A brief description of your app"
          maxLength={maxShort}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors"
        />
        <p className="text-[10px] text-gray-600 mt-1">{form.short_description.length}/{maxShort}</p>
      </div>

      <div>
        <label className="block text-xs text-gray-400 mb-1.5">Full Description *</label>
        <textarea
          value={form.full_description}
          onChange={e => setForm(f => ({ ...f, full_description: e.target.value }))}
          placeholder="Detailed description of your app features and benefits..."
          rows={5}
          maxLength={4000}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors resize-none"
        />
        <p className="text-[10px] text-gray-600 mt-1">{form.full_description.length}/4000</p>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">Category</label>
          <select
            value={form.category}
            onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors"
          >
            <option value="">Select category</option>
            {categories.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">Version</label>
          <input
            value={form.version}
            onChange={e => setForm(f => ({ ...f, version: e.target.value }))}
            placeholder="1.0.0"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors"
          />
        </div>
      </div>

      {platform === 'ios' && (
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">Keywords (comma separated)</label>
          <input
            value={form.keywords}
            onChange={e => setForm(f => ({ ...f, keywords: e.target.value }))}
            placeholder="productivity, task, management, planner"
            maxLength={100}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors"
          />
          <p className="text-[10px] text-gray-600 mt-1">{form.keywords.length}/100</p>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">Privacy Policy URL *</label>
          <input
            value={form.privacy_url}
            onChange={e => setForm(f => ({ ...f, privacy_url: e.target.value }))}
            placeholder="https://yoursite.com/privacy"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">Support URL</label>
          <input
            value={form.support_url}
            onChange={e => setForm(f => ({ ...f, support_url: e.target.value }))}
            placeholder="https://yoursite.com/support"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors"
          />
        </div>
      </div>

      <div>
        <label className="block text-xs text-gray-400 mb-1.5">Marketing URL</label>
        <input
          value={form.marketing_url}
          onChange={e => setForm(f => ({ ...f, marketing_url: e.target.value }))}
          placeholder="https://yoursite.com"
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors"
        />
      </div>

      <button
        onClick={handleSave}
        disabled={isSaving}
        className="flex items-center gap-2 px-5 py-2.5 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
      >
        {isSaving ? <Save size={14} className="animate-spin" /> : <Save size={14} />}
        Save Metadata
      </button>
    </div>
  )
}

function AssetManager({
  platform,
  meta,
  onIconSave,
  onScreenshotsSave,
  isSaving,
}: {
  platform: Platform
  meta: StoreMetadata | null
  onIconSave: (url: string) => void
  onScreenshotsSave: (screenshots: Record<string, string[]>) => void
  isSaving: boolean
}) {
  const [iconInput, setIconInput] = useState(meta?.icon_url || '')
  const [newScreenshot, setNewScreenshot] = useState('')
  const screenshots = meta?.screenshots || { phone: [], tablet: [] }
  const phoneScreenshots = screenshots.phone || []

  const addScreenshot = (type: 'phone' | 'tablet') => {
    if (!newScreenshot.trim()) return
    const updated = {
      ...screenshots,
      [type]: [...(screenshots[type] || []), newScreenshot.trim()],
    }
    onScreenshotsSave(updated)
    setNewScreenshot('')
  }

  const removeScreenshot = (type: 'phone' | 'tablet', index: number) => {
    const list = [...(screenshots[type] || [])]
    list.splice(index, 1)
    onScreenshotsSave({ ...screenshots, [type]: list })
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Image size={14} />
          App Icon
        </h3>
        <p className="text-xs text-gray-500 mb-3">
          {platform === 'ios'
            ? '1024x1024px PNG, no alpha, no rounded corners (Apple rounds automatically)'
            : '512x512px PNG, 32-bit with alpha'}
        </p>
        <div className="flex items-end gap-3">
          <div className="w-20 h-20 rounded-2xl bg-gray-800 border border-gray-700 flex items-center justify-center overflow-hidden flex-shrink-0">
            {iconInput ? (
              <img src={iconInput} alt="icon preview" className="w-full h-full object-cover" />
            ) : (
              <Image size={24} className="text-gray-600" />
            )}
          </div>
          <div className="flex-1">
            <input
              value={iconInput}
              onChange={e => setIconInput(e.target.value)}
              placeholder="Paste icon image URL..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors"
            />
          </div>
          <button
            onClick={() => onIconSave(iconInput)}
            disabled={isSaving}
            className="px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white text-sm rounded-lg transition-colors flex-shrink-0"
          >
            <Upload size={14} />
          </button>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Monitor size={14} />
          Screenshots — Phone
        </h3>
        <p className="text-xs text-gray-500 mb-3">
          {platform === 'ios'
            ? 'iPhone 6.7": 1290x2796px (required). Min 2, max 10.'
            : 'Phone: 1080x1920px recommended. Min 2, max 8.'}
        </p>
        <div className="flex flex-wrap gap-3 mb-3">
          {phoneScreenshots.map((url, i) => (
            <div key={i} className="relative group w-20 h-36 rounded-lg overflow-hidden bg-gray-800 border border-gray-700">
              <img src={url} alt={`phone ${i + 1}`} className="w-full h-full object-cover" />
              <button
                onClick={() => removeScreenshot('phone', i)}
                className="absolute top-1 right-1 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <X size={10} className="text-white" />
              </button>
              <span className="absolute bottom-1 left-1 text-[8px] bg-black/60 text-white px-1 rounded">
                {i + 1}
              </span>
            </div>
          ))}
          {phoneScreenshots.length < 10 && (
            <div className="w-20 h-36 rounded-lg border-2 border-dashed border-gray-700 flex items-center justify-center">
              <Plus size={16} className="text-gray-600" />
            </div>
          )}
        </div>
        <div className="flex gap-2">
          <input
            value={newScreenshot}
            onChange={e => setNewScreenshot(e.target.value)}
            placeholder="Paste screenshot URL..."
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors"
            onKeyDown={e => e.key === 'Enter' && addScreenshot('phone')}
          />
          <button
            onClick={() => addScreenshot('phone')}
            disabled={!newScreenshot.trim() || isSaving}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-white text-sm rounded-lg transition-colors"
          >
            Add
          </button>
        </div>
      </div>

      {platform === 'android' && (
        <div>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Image size={14} />
            Feature Graphic
          </h3>
          <p className="text-xs text-gray-500 mb-3">
            1024x500px. Displayed at the top of your store listing on Google Play.
          </p>
          <div className="w-full h-28 bg-gray-800 border border-gray-700 rounded-lg flex items-center justify-center overflow-hidden">
            {meta?.feature_graphic_url ? (
              <img src={meta.feature_graphic_url} alt="feature graphic" className="w-full h-full object-cover" />
            ) : (
              <span className="text-xs text-gray-600">No feature graphic</span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default function ProjectStorePage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const [platform, setPlatform] = useState<Platform>('android')
  const [activeTab, setActiveTab] = useState<Tab>('preview')

  const { data: project } = useQuery<Project>({
    queryKey: ['projects', id],
    queryFn: () => api.get(`/projects/${id}`).then(r => r.data),
  })

  const { data: allMeta = [], isLoading } = useQuery<StoreMetadata[]>({
    queryKey: ['store-metadata', id],
    queryFn: () => api.get(`/projects/${id}/store-metadata`).then(r => r.data),
  })

  const meta = allMeta.find(m => m.platform === platform) || null

  const saveMutation = useMutation({
    mutationFn: (data: Partial<StoreMetadata>) =>
      api.put(`/projects/${id}/store-metadata/${platform}`, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['store-metadata', id] }),
  })

  const iconMutation = useMutation({
    mutationFn: (url: string) =>
      api.post(`/projects/${id}/store-metadata/${platform}/icon`, { icon_url: url }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['store-metadata', id] }),
  })

  const screenshotMutation = useMutation({
    mutationFn: (screenshots: Record<string, string[]>) =>
      api.post(`/projects/${id}/store-metadata/${platform}/screenshots`, { screenshots }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['store-metadata', id] }),
  })

  const tabs: { key: Tab; label: string; icon: typeof Eye }[] = [
    { key: 'preview', label: 'Store Preview', icon: Eye },
    { key: 'metadata', label: 'Metadata', icon: FileText },
    { key: 'assets', label: 'Assets', icon: Image },
  ]

  const readiness = {
    icon: !!meta?.icon_url,
    name: !!meta?.app_name,
    description: !!meta?.full_description,
    bundleId: !!meta?.bundle_id,
    privacy: !!meta?.privacy_url,
    screenshots: ((meta?.screenshots?.phone || []) as string[]).length >= 2,
  }
  const readinessCount = Object.values(readiness).filter(Boolean).length
  const readinessTotal = Object.keys(readiness).length

  return (
    <div className="p-8 max-w-6xl">
      <Link
        to={`/dashboard/projects/${id}`}
        className="flex items-center gap-2 text-sm text-gray-400 hover:text-white mb-6 transition-colors"
      >
        <ArrowLeft size={16} />
        Back to {project?.name || 'Project'}
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-3">
            Store Configuration
            {readinessCount === readinessTotal ? (
              <span className="text-xs bg-green-500/20 text-green-300 border border-green-500/30 px-2 py-0.5 rounded-full">Ready</span>
            ) : (
              <span className="text-xs bg-yellow-500/20 text-yellow-300 border border-yellow-500/30 px-2 py-0.5 rounded-full">
                {readinessCount}/{readinessTotal} complete
              </span>
            )}
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Configure how your app appears on the stores
          </p>
        </div>

        <div className="flex bg-gray-800 rounded-lg p-0.5">
          {(['android', 'ios'] as Platform[]).map(p => (
            <button
              key={p}
              onClick={() => setPlatform(p)}
              className={clsx(
                'px-4 py-2 text-sm font-medium rounded-md transition-colors',
                platform === p
                  ? p === 'android' ? 'bg-green-600 text-white' : 'bg-gray-600 text-white'
                  : 'text-gray-400 hover:text-white'
              )}
            >
              {p === 'android' ? 'Android' : 'iOS'}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-6">
        <p className="text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wide">Readiness Checklist</p>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
          {Object.entries(readiness).map(([key, ok]) => (
            <div key={key} className={clsx(
              'flex items-center gap-2 px-3 py-2 rounded-lg text-xs',
              ok ? 'bg-green-500/10 text-green-300' : 'bg-gray-800 text-gray-500'
            )}>
              {ok ? <Check size={12} /> : <AlertCircle size={12} />}
              <span className="capitalize">{key.replace(/([A-Z])/g, ' $1').trim()}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex gap-1 mb-6 bg-gray-900 border border-gray-800 rounded-xl p-1">
        {tabs.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={clsx(
              'flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-colors flex-1 justify-center',
              activeTab === key
                ? 'bg-primary-600 text-white'
                : 'text-gray-400 hover:text-white hover:bg-gray-800'
            )}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {saveMutation.isSuccess && (
        <div className="flex items-center gap-2 px-4 py-2 bg-green-500/10 border border-green-500/20 rounded-lg text-sm text-green-300 mb-4">
          <Check size={14} /> Metadata saved successfully
        </div>
      )}

      {isLoading ? (
        <div className="text-center py-12 text-gray-500 text-sm">Loading store metadata...</div>
      ) : (
        <>
          {activeTab === 'preview' && (
            <div>
              <div className="text-center mb-6">
                <p className="text-sm text-gray-400">
                  This is how your app will appear on the {platform === 'ios' ? 'App Store' : 'Google Play Store'}
                </p>
              </div>
              <div className="grid md:grid-cols-2 gap-8 items-start">
                <PhoneMockup platform={platform} meta={meta} />
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                  <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
                    <Globe size={14} />
                    Store Listing Preview
                  </h3>
                  <div className="space-y-4">
                    <div>
                      <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">App Name</p>
                      <p className="text-sm font-medium">{meta?.app_name || <span className="text-gray-600 italic">Not set</span>}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">Bundle ID</p>
                      <p className="text-sm font-mono text-gray-400">{meta?.bundle_id || <span className="text-gray-600 italic">Not set</span>}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">Category</p>
                      <p className="text-sm">{meta?.category || <span className="text-gray-600 italic">Not set</span>}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">Version</p>
                      <p className="text-sm">{meta?.version || <span className="text-gray-600 italic">1.0.0</span>}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">Description</p>
                      <p className="text-xs text-gray-400 leading-relaxed">
                        {meta?.full_description?.slice(0, 200) || <span className="text-gray-600 italic">Not set</span>}
                        {(meta?.full_description?.length || 0) > 200 && '...'}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">Screenshots</p>
                      <p className="text-sm">
                        {((meta?.screenshots?.phone || []) as string[]).length} phone
                        {meta?.screenshots?.tablet && `, ${(meta.screenshots.tablet as string[]).length} tablet`}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">Privacy URL</p>
                      {meta?.privacy_url ? (
                        <a href={meta.privacy_url} target="_blank" rel="noreferrer" className="text-xs text-primary-400 hover:underline">{meta.privacy_url}</a>
                      ) : (
                        <p className="text-sm text-gray-600 italic">Not set</p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'metadata' && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
              <h3 className="text-sm font-semibold mb-5 flex items-center gap-2">
                <FileText size={14} />
                {platform === 'ios' ? 'App Store' : 'Google Play'} Metadata
              </h3>
              <MetadataForm
                platform={platform}
                meta={meta}
                onSave={(data) => saveMutation.mutate(data)}
                isSaving={saveMutation.isPending}
              />
            </div>
          )}

          {activeTab === 'assets' && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
              <AssetManager
                platform={platform}
                meta={meta}
                onIconSave={(url) => iconMutation.mutate(url)}
                onScreenshotsSave={(s) => screenshotMutation.mutate(s)}
                isSaving={iconMutation.isPending || screenshotMutation.isPending}
              />
            </div>
          )}
        </>
      )}
    </div>
  )
}
