import { useState, useCallback, useRef, DragEvent } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, Smartphone, Image, FileText, Save, Upload,
  Check, AlertCircle, Globe, Star, X, Plus, Eye, Shield,
  Languages, ArrowUp, ArrowDown, Clock, XCircle, CheckCircle,
  Camera, Zap, Tablet, ExternalLink, Loader2,
  MonitorSmartphone, Layout,
} from 'lucide-react'
import { api } from '@/lib/api'
import type { Project, StoreMetadata, ComplianceResult, ReviewSimulation } from '@/types'
import clsx from 'clsx'

type Platform = 'android' | 'ios'
type Tab = 'preview' | 'metadata' | 'assets' | 'compliance'

const LOCALES = [
  { code: 'en-US', label: 'English (US)', flag: 'US' },
  { code: 'tr-TR', label: 'Turkce', flag: 'TR' },
  { code: 'de-DE', label: 'Deutsch', flag: 'DE' },
  { code: 'fr-FR', label: 'Francais', flag: 'FR' },
  { code: 'es-ES', label: 'Espanol', flag: 'ES' },
  { code: 'it-IT', label: 'Italiano', flag: 'IT' },
  { code: 'pt-BR', label: 'Portugues (BR)', flag: 'BR' },
  { code: 'ja-JP', label: 'Japanese', flag: 'JP' },
  { code: 'ko-KR', label: 'Korean', flag: 'KR' },
  { code: 'zh-CN', label: 'Chinese (Simplified)', flag: 'CN' },
  { code: 'zh-TW', label: 'Chinese (Traditional)', flag: 'TW' },
  { code: 'ar-SA', label: 'Arabic', flag: 'SA' },
  { code: 'nl-NL', label: 'Dutch', flag: 'NL' },
  { code: 'ru-RU', label: 'Russian', flag: 'RU' },
  { code: 'hi-IN', label: 'Hindi', flag: 'IN' },
]

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
    <div className={clsx('relative mx-auto', isIos ? 'w-[280px]' : 'w-[270px]')}>
      <div className={clsx(
        'bg-gray-950 border-2 rounded-[2.5rem] p-2 shadow-2xl',
        isIos ? 'border-gray-600' : 'border-gray-700'
      )}>
        {isIos && (
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-28 h-6 bg-gray-950 rounded-b-2xl z-10 border-b-2 border-x-2 border-gray-600" />
        )}
        <div className={clsx('bg-white rounded-[2rem] overflow-hidden', isIos ? 'pt-8' : 'pt-6')}>
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
            <p className="text-[11px] text-gray-600 leading-relaxed line-clamp-3">{shortDesc}</p>
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

function LocaleSelector({
  locale,
  onChange,
  configuredLocales,
}: {
  locale: string
  onChange: (l: string) => void
  configuredLocales: Record<string, string[]>
}) {
  return (
    <div className="flex items-center gap-2">
      <Languages size={14} className="text-gray-500" />
      <select
        value={locale}
        onChange={e => onChange(e.target.value)}
        className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm outline-none focus:border-primary-500 transition-colors"
      >
        {LOCALES.map(l => (
          <option key={l.code} value={l.code}>
            {l.flag} {l.label} {configuredLocales[l.code] ? ' *' : ''}
          </option>
        ))}
      </select>
    </div>
  )
}

function MetadataForm({
  platform, meta, onSave, isSaving,
}: {
  platform: Platform; meta: StoreMetadata | null
  onSave: (data: Partial<StoreMetadata>) => void; isSaving: boolean
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

  return (
    <div className="space-y-5">
      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">App Name *</label>
          <input value={form.app_name} onChange={e => setForm(f => ({ ...f, app_name: e.target.value }))}
            placeholder="My Amazing App" maxLength={50}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors" />
          <p className="text-[10px] text-gray-600 mt-1">{form.app_name.length}/50</p>
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">Bundle ID / Package Name *</label>
          <input value={form.bundle_id} onChange={e => setForm(f => ({ ...f, bundle_id: e.target.value }))}
            placeholder="com.company.appname"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors" />
        </div>
      </div>
      <div>
        <label className="block text-xs text-gray-400 mb-1.5">
          {platform === 'ios' ? 'Subtitle' : 'Short Description'} *
        </label>
        <input value={form.short_description} onChange={e => setForm(f => ({ ...f, short_description: e.target.value }))}
          placeholder="A brief description of your app" maxLength={maxShort}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors" />
        <p className="text-[10px] text-gray-600 mt-1">{form.short_description.length}/{maxShort}</p>
      </div>
      <div>
        <label className="block text-xs text-gray-400 mb-1.5">Full Description *</label>
        <textarea value={form.full_description} onChange={e => setForm(f => ({ ...f, full_description: e.target.value }))}
          placeholder="Detailed description of your app features and benefits..." rows={5} maxLength={4000}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors resize-none" />
        <p className="text-[10px] text-gray-600 mt-1">{form.full_description.length}/4000</p>
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">Category</label>
          <select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors">
            <option value="">Select category</option>
            {categories.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">Version</label>
          <input value={form.version} onChange={e => setForm(f => ({ ...f, version: e.target.value }))}
            placeholder="1.0.0"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors" />
        </div>
      </div>
      {platform === 'ios' && (
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">Keywords (comma separated)</label>
          <input value={form.keywords} onChange={e => setForm(f => ({ ...f, keywords: e.target.value }))}
            placeholder="productivity, task, management, planner" maxLength={100}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors" />
          <p className="text-[10px] text-gray-600 mt-1">{form.keywords.length}/100</p>
        </div>
      )}
      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">Privacy Policy URL *</label>
          <input value={form.privacy_url} onChange={e => setForm(f => ({ ...f, privacy_url: e.target.value }))}
            placeholder="https://yoursite.com/privacy"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors" />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">Support URL</label>
          <input value={form.support_url} onChange={e => setForm(f => ({ ...f, support_url: e.target.value }))}
            placeholder="https://yoursite.com/support"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors" />
        </div>
      </div>
      <div>
        <label className="block text-xs text-gray-400 mb-1.5">Marketing URL</label>
        <input value={form.marketing_url} onChange={e => setForm(f => ({ ...f, marketing_url: e.target.value }))}
          placeholder="https://yoursite.com"
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors" />
      </div>
      <button onClick={() => onSave(form)} disabled={isSaving}
        className="flex items-center gap-2 px-5 py-2.5 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors">
        {isSaving ? <Save size={14} className="animate-spin" /> : <Save size={14} />}
        Save Metadata
      </button>
    </div>
  )
}

/* ─────────────── Screenshot Card ─────────────── */
function ScreenshotCard({
  url, index, total, isHero, onRemove, onMove, category = 'phone', platform = 'android',
}: {
  url: string; index: number; total: number; isHero: boolean
  onRemove: () => void; onMove: (dir: -1 | 1) => void
  category?: 'phone' | 'tablet'; platform?: Platform
}) {
  const [dragging, setDragging] = useState(false)
  const isTablet = category === 'tablet'
  const isIos = platform === 'ios'

  return (
    <div
      draggable
      onDragStart={e => { e.dataTransfer.setData('text/plain', String(index)); setDragging(true) }}
      onDragEnd={() => setDragging(false)}
      className={clsx(
        'relative group cursor-grab active:cursor-grabbing transition-all duration-200',
        dragging && 'opacity-40 scale-95'
      )}
    >
      {/* Device frame — platform-specific */}
      <div className="relative">
        <div className={clsx(
          'bg-zinc-900 border-2 p-[3px] shadow-lg shadow-black/20',
          isTablet ? 'w-[120px] h-[160px]' : 'w-[88px] h-[160px]',
          isIos ? 'border-zinc-600 rounded-[14px]' : 'border-zinc-700 rounded-xl'
        )}>
          {/* iOS Dynamic Island (phone) */}
          {isIos && !isTablet && (
            <div className="absolute top-[5px] left-1/2 -translate-x-1/2 w-[22px] h-[7px] bg-black rounded-full z-10 shadow-inner" />
          )}
          {/* Android punch-hole camera (phone) */}
          {!isIos && !isTablet && (
            <div className="absolute top-[6px] left-1/2 -translate-x-1/2 w-[5px] h-[5px] bg-zinc-700 rounded-full z-10 border border-zinc-600" />
          )}
          {/* iOS iPad: thin bezel, no notch */}
          {isIos && isTablet && (
            <div className="absolute top-[6px] left-1/2 -translate-x-1/2 w-[5px] h-[5px] bg-zinc-700 rounded-full z-10" />
          )}
          <div className={clsx(
            'w-full h-full overflow-hidden bg-zinc-800',
            isIos ? (isTablet ? 'rounded-[10px]' : 'rounded-[11px]') : (isTablet ? 'rounded-lg' : 'rounded-[9px]')
          )}>
            <img src={url} alt={`Screenshot ${index + 1}`} className="w-full h-full object-cover" />
          </div>
        </div>

        {/* Hero badge */}
        {isHero && (
          <div className="absolute -top-2 left-1/2 -translate-x-1/2 z-20">
            <span className="text-[9px] font-bold uppercase tracking-wider bg-amber-500 text-black px-2 py-0.5 rounded-full shadow-lg shadow-amber-500/30">
              Hero
            </span>
          </div>
        )}

        {/* Position indicator */}
        {!isHero && (
          <span className="absolute -top-1.5 -right-1.5 z-20 w-5 h-5 bg-zinc-700 border border-zinc-600 rounded-full flex items-center justify-center text-[9px] font-mono text-zinc-300">
            {index + 1}
          </span>
        )}

        {/* Hover controls */}
        <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity rounded-xl flex flex-col items-center justify-center gap-1.5">
          <div className="flex gap-1">
            {index > 0 && (
              <button onClick={() => onMove(-1)} className="w-6 h-6 bg-zinc-600 hover:bg-zinc-500 rounded-md flex items-center justify-center transition-colors">
                <ArrowUp size={11} className="text-white" />
              </button>
            )}
            {index < total - 1 && (
              <button onClick={() => onMove(1)} className="w-6 h-6 bg-zinc-600 hover:bg-zinc-500 rounded-md flex items-center justify-center transition-colors">
                <ArrowDown size={11} className="text-white" />
              </button>
            )}
          </div>
          <button onClick={onRemove} className="w-6 h-6 bg-red-500/80 hover:bg-red-500 rounded-md flex items-center justify-center transition-colors">
            <X size={11} className="text-white" />
          </button>
        </div>
      </div>
    </div>
  )
}

/* ─────────────── Auto Capture Panel ─────────────── */
function AutoCapturePanel({
  projectId, platform, onScreenshotsCaptured,
}: {
  projectId: string; platform: Platform
  onScreenshotsCaptured: (urls: string[], category: string) => void
}) {
  const [url, setUrl] = useState('')
  const [capturing, setCapturing] = useState(false)
  const [capturedShots, setCapturedShots] = useState<{ device: string; label: string; category: string; data_uri: string; selected: boolean }[]>([])
  const [error, setError] = useState('')

  const defaultDevices = platform === 'ios'
    ? ['iphone_6_7', 'iphone_6_5', 'ipad_12_9']
    : ['android_phone', 'android_tablet_7']

  const [devices, setDevices] = useState<string[]>(defaultDevices)

  const deviceOptions = platform === 'ios'
    ? [
        { id: 'iphone_6_7', label: 'iPhone 6.7"', icon: Smartphone },
        { id: 'iphone_6_5', label: 'iPhone 6.5"', icon: Smartphone },
        { id: 'iphone_5_5', label: 'iPhone 5.5"', icon: Smartphone },
        { id: 'ipad_12_9', label: 'iPad 12.9"', icon: Tablet },
      ]
    : [
        { id: 'android_phone', label: 'Phone', icon: Smartphone },
        { id: 'android_tablet_7', label: '7" Tablet', icon: Tablet },
        { id: 'android_tablet_10', label: '10" Tablet', icon: Layout },
      ]

  const toggleDevice = (id: string) => {
    setDevices(prev => prev.includes(id) ? prev.filter(d => d !== id) : [...prev, id])
  }

  const startCapture = async () => {
    if (!url.trim() || devices.length === 0) return
    setCapturing(true)
    setError('')
    setCapturedShots([])
    try {
      const res = await api.post(`/screenshots/${projectId}/auto-capture`, {
        url: url.trim(),
        devices,
        wait_seconds: 2.5,
      })
      setCapturedShots(res.data.screenshots.map((s: { device: string; label: string; category: string; data_uri: string }) => ({ ...s, selected: true })))
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Capture failed'
      setError(typeof err === 'object' && err !== null && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail || msg
        : msg)
    } finally {
      setCapturing(false)
    }
  }

  const toggleShot = (i: number) => {
    setCapturedShots(prev => prev.map((s, idx) => idx === i ? { ...s, selected: !s.selected } : s))
  }

  const saveSelected = () => {
    const phoneShots = capturedShots.filter(s => s.selected && s.category === 'phone').map(s => s.data_uri)
    const tabletShots = capturedShots.filter(s => s.selected && s.category === 'tablet').map(s => s.data_uri)
    if (phoneShots.length > 0) onScreenshotsCaptured(phoneShots, 'phone')
    if (tabletShots.length > 0) onScreenshotsCaptured(tabletShots, 'tablet')
    setCapturedShots([])
  }

  return (
    <div className="relative overflow-hidden rounded-xl border border-cyan-500/20 bg-gradient-to-br from-cyan-950/40 via-zinc-900/80 to-zinc-900/80">
      {/* Decorative glow */}
      <div className="absolute -top-20 -right-20 w-40 h-40 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-10 -left-10 w-32 h-32 bg-blue-500/5 rounded-full blur-3xl pointer-events-none" />

      <div className="relative p-5">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <Camera size={16} className="text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              Auto Capture
              <span className="text-[9px] font-bold uppercase tracking-wider bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 px-1.5 py-0.5 rounded-full">
                Free
              </span>
            </h3>
            <p className="text-[11px] text-zinc-400">Capture screenshots from your running app automatically</p>
          </div>
        </div>

        {/* URL input */}
        <div className="flex gap-2 mb-4">
          <div className="flex-1 relative">
            <ExternalLink size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input
              value={url} onChange={e => setUrl(e.target.value)}
              placeholder="https://your-app-url.com"
              className="w-full bg-zinc-800/80 border border-zinc-700 rounded-lg pl-9 pr-3 py-2.5 text-sm outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/20 transition-all placeholder:text-zinc-600"
              onKeyDown={e => e.key === 'Enter' && startCapture()}
            />
          </div>
          <button
            onClick={startCapture}
            disabled={capturing || !url.trim() || devices.length === 0}
            className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 disabled:from-zinc-700 disabled:to-zinc-700 disabled:text-zinc-500 text-white text-sm font-medium rounded-lg transition-all shadow-lg shadow-cyan-500/10 disabled:shadow-none"
          >
            {capturing ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
            {capturing ? 'Capturing...' : 'Capture'}
          </button>
        </div>

        {/* Device selector */}
        <div className="flex flex-wrap gap-2 mb-4">
          {deviceOptions.map(opt => {
            const Icon = opt.icon
            const active = devices.includes(opt.id)
            return (
              <button key={opt.id} onClick={() => toggleDevice(opt.id)}
                className={clsx(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border',
                  active
                    ? 'bg-cyan-500/15 border-cyan-500/40 text-cyan-300'
                    : 'bg-zinc-800/50 border-zinc-700/50 text-zinc-500 hover:text-zinc-300 hover:border-zinc-600'
                )}>
                <Icon size={12} />
                {opt.label}
              </button>
            )
          })}
        </div>

        {error && (
          <div className="flex items-center gap-2 px-3 py-2 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-300 mb-4">
            <AlertCircle size={12} /> {error}
          </div>
        )}

        {/* Captured screenshots preview */}
        {capturedShots.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs text-zinc-400">
                {capturedShots.filter(s => s.selected).length} of {capturedShots.length} selected
              </p>
              <button onClick={saveSelected}
                disabled={capturedShots.filter(s => s.selected).length === 0}
                className="flex items-center gap-1.5 px-4 py-1.5 bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white text-xs font-medium rounded-lg transition-colors">
                <Check size={12} /> Add Selected
              </button>
            </div>
            <div className="flex gap-3 overflow-x-auto pb-2">
              {capturedShots.map((shot, i) => (
                <button key={i} onClick={() => toggleShot(i)}
                  className={clsx(
                    'relative flex-shrink-0 rounded-lg overflow-hidden border-2 transition-all',
                    shot.selected ? 'border-cyan-500 shadow-lg shadow-cyan-500/20' : 'border-zinc-700 opacity-50'
                  )}>
                  <img src={shot.data_uri} alt={shot.label} className="w-[72px] h-[128px] object-cover" />
                  <span className="absolute bottom-0 left-0 right-0 bg-black/70 text-[8px] text-zinc-300 px-1 py-0.5 text-center truncate">
                    {shot.label}
                  </span>
                  {shot.selected && (
                    <div className="absolute top-1 right-1 w-4 h-4 bg-cyan-500 rounded-full flex items-center justify-center">
                      <Check size={10} className="text-white" />
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Info text */}
        {capturedShots.length === 0 && !capturing && (
          <p className="text-[10px] text-zinc-600 leading-relaxed">
            Enter your app's preview URL (localhost or deployed). Headless Chromium captures screenshots
            at exact store dimensions. Works best with Capacitor, Ionic, PWA apps.
            Powered by Playwright (MIT license) — completely free.
          </p>
        )}
      </div>
    </div>
  )
}

/* ─────────────── Screenshot Section ─────────────── */
function ScreenshotSection({
  title, subtitle, icon: Icon, screenshots, maxCount, category, platform = 'android', onReorder, onRemove, onAdd, onAddMultiple,
}: {
  title: string; subtitle: string; icon: typeof Smartphone
  screenshots: string[]; maxCount: number; category: 'phone' | 'tablet'
  platform?: Platform
  onReorder: (from: number, to: number) => void
  onRemove: (index: number) => void
  onAdd: (url: string) => void
  onAddMultiple?: (urls: string[]) => void
}) {
  const [input, setInput] = useState('')
  const dropRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)

  const handleFiles = (files: FileList | File[]) => {
    const remaining = maxCount - screenshots.length
    const toProcess = Array.from(files).filter(f => f.type.startsWith('image/')).slice(0, remaining)
    if (toProcess.length === 0) return
    const results: string[] = []
    let loaded = 0
    toProcess.forEach(file => {
      const reader = new FileReader()
      reader.onload = () => {
        results.push(reader.result as string)
        loaded++
        if (loaded === toProcess.length) {
          if (onAddMultiple) onAddMultiple(results)
          else results.forEach(u => onAdd(u))
        }
      }
      reader.readAsDataURL(file)
    })
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(false)
    // Check if files are being dropped (from PC)
    if (e.dataTransfer.files?.length > 0) {
      handleFiles(e.dataTransfer.files)
      return
    }
    // Otherwise handle card reorder
    const fromStr = e.dataTransfer.getData('text/plain')
    if (!fromStr) return
    const from = parseInt(fromStr, 10)
    const container = dropRef.current
    if (!container) return
    const rect = container.getBoundingClientRect()
    const x = e.clientX - rect.left
    const cardWidth = category === 'tablet' ? 132 : 100
    const to = Math.min(Math.max(Math.floor(x / cardWidth), 0), screenshots.length - 1)
    if (from !== to) onReorder(from, to)
  }

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(true)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-md bg-zinc-800 border border-zinc-700 flex items-center justify-center">
            <Icon size={13} className="text-zinc-400" />
          </div>
          <div>
            <h4 className="text-sm font-medium text-zinc-200">{title}</h4>
            <p className="text-[10px] text-zinc-500">{subtitle}</p>
          </div>
        </div>
        <span className={clsx(
          'text-xs font-mono px-2 py-0.5 rounded-md border',
          screenshots.length >= 2
            ? 'bg-green-500/10 border-green-500/20 text-green-400'
            : 'bg-amber-500/10 border-amber-500/20 text-amber-400'
        )}>
          {screenshots.length}/{maxCount}
        </span>
      </div>

      {/* Screenshot grid with drag-drop */}
      <div
        ref={dropRef}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={() => setDragOver(false)}
        className={clsx(
          'flex flex-wrap gap-3 p-3 rounded-xl border-2 border-dashed transition-all min-h-[180px]',
          dragOver ? 'border-cyan-500/40 bg-cyan-500/5' : 'border-zinc-800 bg-zinc-900/30',
          screenshots.length === 0 && 'items-center justify-center'
        )}
      >
        {screenshots.length === 0 ? (
          <div className="text-center py-4 cursor-pointer" onClick={() => fileInputRef.current?.click()}>
            <MonitorSmartphone size={32} className="text-zinc-700 mx-auto mb-2" />
            <p className="text-xs text-zinc-600">No screenshots yet</p>
            <p className="text-[10px] text-zinc-700 mt-1">Click to upload, drag files here, or paste URL below</p>
          </div>
        ) : (
          screenshots.map((url, i) => (
            <ScreenshotCard
              key={`${category}-${i}-${url.slice(-20)}`}
              url={url}
              index={i}
              total={screenshots.length}
              isHero={i === 0}
              category={category}
              platform={platform}
              onRemove={() => onRemove(i)}
              onMove={dir => onReorder(i, i + dir)}
            />
          ))
        )}
        {screenshots.length > 0 && screenshots.length < maxCount && (
          <div
            onClick={() => fileInputRef.current?.click()}
            className={clsx(
              'h-[160px] rounded-xl border-2 border-dashed border-zinc-700/50 flex flex-col items-center justify-center gap-1 text-zinc-600 hover:text-zinc-400 hover:border-zinc-600 transition-colors cursor-pointer',
              category === 'tablet' ? 'w-[120px]' : 'w-[88px]'
            )}
          >
            <Plus size={16} />
            <span className="text-[8px]">Add</span>
          </div>
        )}
      </div>
      <input ref={fileInputRef} type="file" accept="image/*" multiple className="hidden"
        onChange={e => { if (e.target.files) { handleFiles(e.target.files); e.target.value = '' } }} />

      {/* URL input + file upload button */}
      <div className="flex gap-2 mt-3">
        <input
          value={input} onChange={e => setInput(e.target.value)}
          placeholder="Paste screenshot URL or data URI..."
          className="flex-1 bg-zinc-800/60 border border-zinc-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500 transition-colors placeholder:text-zinc-600"
          onKeyDown={e => { if (e.key === 'Enter' && input.trim()) { onAdd(input.trim()); setInput('') } }}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={screenshots.length >= maxCount}
          className="flex items-center gap-1.5 px-3 py-2 bg-zinc-700 hover:bg-zinc-600 disabled:opacity-40 text-white text-sm rounded-lg transition-colors"
          title="Upload from PC"
        >
          <Upload size={13} />
        </button>
        <button
          onClick={() => { if (input.trim()) { onAdd(input.trim()); setInput('') } }}
          disabled={!input.trim() || screenshots.length >= maxCount}
          className="flex items-center gap-1.5 px-4 py-2 bg-zinc-700 hover:bg-zinc-600 disabled:opacity-40 text-white text-sm rounded-lg transition-colors"
        >
          <Plus size={12} /> Add
        </button>
      </div>
    </div>
  )
}

/* ─────────────── Asset Manager (Redesigned) ─────────────── */
function AssetManager({
  platform, meta, onIconSave, onScreenshotsSave, isSaving, projectId,
}: {
  platform: Platform; meta: StoreMetadata | null
  onIconSave: (url: string) => void
  onScreenshotsSave: (screenshots: Record<string, string[]>) => void
  isSaving: boolean; projectId: string
}) {
  const [iconInput, setIconInput] = useState(meta?.icon_url || '')
  const [iconDragOver, setIconDragOver] = useState(false)
  const iconFileRef = useRef<HTMLInputElement>(null)
  const featureFileRef = useRef<HTMLInputElement>(null)
  const screenshots = meta?.screenshots || { phone: [], tablet: [] }
  const phoneScreenshots: string[] = screenshots.phone || []
  const tabletScreenshots: string[] = screenshots.tablet || []

  const iconSpec = platform === 'ios'
    ? { w: 1024, h: 1024, note: '1024x1024px PNG — No transparency, no rounded corners' }
    : { w: 512, h: 512, note: '512x512px PNG — 32-bit with alpha channel' }

  const handleIconFile = (file: File) => {
    const reader = new FileReader()
    reader.onload = () => {
      const dataUri = reader.result as string
      setIconInput(dataUri)
      onIconSave(dataUri)
    }
    reader.readAsDataURL(file)
  }

  const handleFeatureFile = (file: File) => {
    const reader = new FileReader()
    reader.onload = () => {
      const dataUri = reader.result as string
      onScreenshotsSave({ ...screenshots, feature_graphic: [dataUri] })
    }
    reader.readAsDataURL(file)
  }

  const reorderScreenshots = (category: 'phone' | 'tablet', from: number, to: number) => {
    const list = [...(screenshots[category] || [])]
    if (to < 0 || to >= list.length) return
    const [item] = list.splice(from, 1)
    list.splice(to, 0, item)
    onScreenshotsSave({ ...screenshots, [category]: list })
  }

  const removeScreenshot = (category: 'phone' | 'tablet', index: number) => {
    const list = [...(screenshots[category] || [])]
    list.splice(index, 1)
    onScreenshotsSave({ ...screenshots, [category]: list })
  }

  const addScreenshot = (category: 'phone' | 'tablet', url: string) => {
    onScreenshotsSave({ ...screenshots, [category]: [...(screenshots[category] || []), url] })
  }

  const addScreenshots = (category: 'phone' | 'tablet', urls: string[]) => {
    onScreenshotsSave({ ...screenshots, [category]: [...(screenshots[category] || []), ...urls] })
  }

  const handleAutoCaptured = (urls: string[], category: string) => {
    const existing = screenshots[category] || []
    onScreenshotsSave({ ...screenshots, [category]: [...existing, ...urls] })
  }

  return (
    <div className="space-y-8">
      {/* ── App Icon ── */}
      <div>
        <div className="flex items-center gap-2.5 mb-4">
          <div className="w-7 h-7 rounded-md bg-zinc-800 border border-zinc-700 flex items-center justify-center">
            <Image size={13} className="text-zinc-400" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-zinc-200">App Icon</h3>
            <p className="text-[10px] text-zinc-500">{iconSpec.note}</p>
          </div>
        </div>

        <div className="flex gap-5 items-start">
          {/* Icon preview with drag-drop */}
          <div
            onClick={() => iconFileRef.current?.click()}
            onDragOver={e => { e.preventDefault(); setIconDragOver(true) }}
            onDragLeave={() => setIconDragOver(false)}
            onDrop={e => {
              e.preventDefault(); setIconDragOver(false)
              const file = e.dataTransfer.files[0]
              if (file?.type.startsWith('image/')) handleIconFile(file)
            }}
            className={clsx(
              'w-28 h-28 rounded-2xl border-2 flex items-center justify-center overflow-hidden cursor-pointer transition-all group flex-shrink-0',
              iconDragOver
                ? 'border-cyan-500 bg-cyan-500/10 scale-105'
                : iconInput
                  ? 'border-zinc-700 bg-zinc-800 hover:border-zinc-500'
                  : 'border-dashed border-zinc-700 bg-zinc-800/50 hover:border-zinc-500'
            )}
          >
            {iconInput ? (
              <img src={iconInput} alt="App icon" className="w-full h-full object-cover" />
            ) : (
              <div className="text-center">
                <Upload size={20} className="text-zinc-600 mx-auto mb-1 group-hover:text-zinc-400 transition-colors" />
                <p className="text-[9px] text-zinc-600 group-hover:text-zinc-400 transition-colors">Drop or click</p>
              </div>
            )}
          </div>
          <input ref={iconFileRef} type="file" accept="image/*" className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) handleIconFile(f) }} />

          <div className="flex-1 space-y-3">
            <div className="flex gap-2">
              <input value={iconInput} onChange={e => setIconInput(e.target.value)}
                placeholder="Or paste image URL..."
                className="flex-1 bg-zinc-800/60 border border-zinc-700 rounded-lg px-3 py-2.5 text-sm outline-none focus:border-primary-500 transition-colors placeholder:text-zinc-600" />
              <button onClick={() => onIconSave(iconInput)} disabled={isSaving || !iconInput}
                className="flex items-center gap-1.5 px-4 py-2.5 bg-primary-600 hover:bg-primary-700 disabled:opacity-40 text-white text-sm font-medium rounded-lg transition-colors">
                <Save size={13} /> Save
              </button>
            </div>
            {iconInput && !iconInput.startsWith('data:') && !iconInput.toLowerCase().endsWith('.png') && (
              <div className="flex items-center gap-2 text-xs text-amber-400/80">
                <AlertCircle size={11} /> Recommended: PNG format for store compatibility
              </div>
            )}
            <div className="grid grid-cols-2 gap-2 text-[10px] text-zinc-500">
              <div className="flex items-center gap-1.5 bg-zinc-800/40 rounded px-2 py-1.5">
                <span className="text-zinc-600">Size:</span> {iconSpec.w}x{iconSpec.h}px
              </div>
              <div className="flex items-center gap-1.5 bg-zinc-800/40 rounded px-2 py-1.5">
                <span className="text-zinc-600">Format:</span> PNG {platform === 'android' ? '(alpha OK)' : '(no alpha)'}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Divider ── */}
      <div className="border-t border-zinc-800" />

      {/* ── Auto Capture ── */}
      <AutoCapturePanel
        projectId={projectId}
        platform={platform}
        onScreenshotsCaptured={handleAutoCaptured}
      />

      {/* ── Divider ── */}
      <div className="border-t border-zinc-800" />

      {/* ── Phone Screenshots ── */}
      <ScreenshotSection
        title="Phone Screenshots"
        subtitle={platform === 'ios'
          ? 'iPhone 6.7": 1290x2796px required. Min 2, max 10.'
          : 'Phone: 1080x1920px recommended. Min 2, max 8.'}
        icon={Smartphone}
        screenshots={phoneScreenshots}
        maxCount={platform === 'ios' ? 10 : 8}
        category="phone"
        platform={platform}
        onReorder={(from, to) => reorderScreenshots('phone', from, to)}
        onRemove={(i) => removeScreenshot('phone', i)}
        onAdd={(url) => addScreenshot('phone', url)}
        onAddMultiple={(urls) => addScreenshots('phone', urls)}
      />

      {/* ── Tablet Screenshots ── */}
      <ScreenshotSection
        title="Tablet Screenshots"
        subtitle={platform === 'ios'
          ? 'iPad 12.9": 2048x2732px. Optional but recommended.'
          : '7" Tablet: 1200x1920px, 10" Tablet: 1920x1200px. Optional.'}
        icon={Tablet}
        screenshots={tabletScreenshots}
        maxCount={platform === 'ios' ? 10 : 8}
        category="tablet"
        platform={platform}
        onReorder={(from, to) => reorderScreenshots('tablet', from, to)}
        onRemove={(i) => removeScreenshot('tablet', i)}
        onAdd={(url) => addScreenshot('tablet', url)}
        onAddMultiple={(urls) => addScreenshots('tablet', urls)}
      />

      {/* ── Feature Graphic / Promotional Art ── */}
      <div>
        <div className="flex items-center gap-2.5 mb-3">
          <div className="w-7 h-7 rounded-md bg-zinc-800 border border-zinc-700 flex items-center justify-center">
            <Layout size={13} className="text-zinc-400" />
          </div>
          <div>
            <h4 className="text-sm font-medium text-zinc-200">
              {platform === 'android' ? 'Feature Graphic' : 'Promotional Art'}
            </h4>
            <p className="text-[10px] text-zinc-500">
              {platform === 'android'
                ? '1024x500px — Google Play mağaza listesinin üstünde gösterilir'
                : '1024x1024px — Apple editör ekibi uygulamayı öne çıkardığında kullanılır'}
            </p>
          </div>
        </div>
        <div
          onClick={() => featureFileRef.current?.click()}
          onDragOver={e => e.preventDefault()}
          onDrop={e => {
            e.preventDefault()
            const file = e.dataTransfer.files[0]
            if (file?.type.startsWith('image/')) handleFeatureFile(file)
          }}
          className={clsx(
            'w-full bg-zinc-800/40 border-2 border-dashed border-zinc-700 rounded-xl flex items-center justify-center overflow-hidden cursor-pointer hover:border-zinc-600 transition-colors group',
            platform === 'android' ? 'h-32' : 'h-44'
          )}
        >
          {meta?.feature_graphic_url ? (
            <img src={meta.feature_graphic_url} alt={platform === 'android' ? 'Feature graphic' : 'Promotional art'} className="w-full h-full object-cover" />
          ) : (
            <div className="text-center">
              <Upload size={20} className="text-zinc-700 mx-auto mb-1 group-hover:text-zinc-500 transition-colors" />
              <p className="text-xs text-zinc-600 group-hover:text-zinc-400 transition-colors">
                Görsel sürükleyin veya tıklayarak yükleyin
              </p>
              <p className="text-[10px] text-zinc-700 mt-0.5">
                {platform === 'android' ? '1024 x 500 piksel' : '1024 x 1024 piksel'}
              </p>
            </div>
          )}
        </div>
        <input ref={featureFileRef} type="file" accept="image/*" className="hidden"
          onChange={e => { const f = e.target.files?.[0]; if (f) handleFeatureFile(f) }} />
      </div>
    </div>
  )
}

function CompliancePanel({
  compliance, simulation, isLoadingCompliance, isLoadingSimulation, onRunCheck,
}: {
  compliance: ComplianceResult | undefined
  simulation: ReviewSimulation | undefined
  isLoadingCompliance: boolean
  isLoadingSimulation: boolean
  onRunCheck: () => void
}) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold flex items-center gap-2"><Shield size={14} /> Store Compliance Check</h3>
        <button onClick={onRunCheck}
          disabled={isLoadingCompliance || isLoadingSimulation}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white text-sm rounded-lg transition-colors">
          <Shield size={14} /> Run Check
        </button>
      </div>

      {compliance && (
        <div>
          <div className="flex items-center gap-4 mb-4">
            <div className={clsx(
              'text-4xl font-bold',
              compliance.score >= 80 ? 'text-green-400' : compliance.score >= 50 ? 'text-yellow-400' : 'text-red-400'
            )}>
              {compliance.score}
            </div>
            <div>
              <p className="text-sm font-medium">
                {compliance.ready ? 'Ready to submit' : 'Not ready — fix errors first'}
              </p>
              <p className="text-xs text-gray-500">
                {compliance.errors.length} errors, {compliance.warnings.length} warnings
              </p>
            </div>
          </div>

          {compliance.errors.length > 0 && (
            <div className="mb-4">
              <p className="text-xs font-semibold text-red-400 mb-2 uppercase tracking-wide">Errors (will cause rejection)</p>
              <div className="space-y-2">
                {compliance.errors.map((e, i) => (
                  <div key={i} className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                    <XCircle size={14} className="text-red-400 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-xs text-red-300">{e.message}</p>
                      <p className="text-[10px] text-red-500/60 mt-0.5">Field: {e.field}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {compliance.warnings.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-yellow-400 mb-2 uppercase tracking-wide">Warnings (may hurt performance)</p>
              <div className="space-y-2">
                {compliance.warnings.map((w, i) => (
                  <div key={i} className="flex items-start gap-2 bg-yellow-500/10 border border-yellow-500/20 rounded-lg px-3 py-2">
                    <AlertCircle size={14} className="text-yellow-400 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-xs text-yellow-300">{w.message}</p>
                      <p className="text-[10px] text-yellow-500/60 mt-0.5">Field: {w.field}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {simulation && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-5">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <Eye size={14} /> Simulated Review Result
          </h3>
          <div className={clsx(
            'text-center py-3 mb-4 rounded-lg font-semibold text-sm',
            simulation.verdict === 'likely_approved' ? 'bg-green-500/10 text-green-400' :
            simulation.verdict === 'needs_improvement' ? 'bg-yellow-500/10 text-yellow-400' :
            'bg-red-500/10 text-red-400'
          )}>
            {simulation.verdict === 'likely_approved' && 'Likely Approved'}
            {simulation.verdict === 'needs_improvement' && 'Needs Improvement'}
            {simulation.verdict === 'likely_rejected' && 'Likely Rejected'}
          </div>

          <div className="space-y-2 mb-4">
            {simulation.checks.map((c, i) => (
              <div key={i} className="flex items-center justify-between text-xs py-1.5 border-b border-gray-700/50">
                <span className="text-gray-300">{c.check}</span>
                <div className="flex items-center gap-2">
                  <span className="text-gray-500">{c.detail}</span>
                  {c.status === 'pass' && <CheckCircle size={12} className="text-green-400" />}
                  {c.status === 'warning' && <AlertCircle size={12} className="text-yellow-400" />}
                  {c.status === 'fail' && <XCircle size={12} className="text-red-400" />}
                </div>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between text-xs pt-2">
            <span className="text-gray-400">
              {simulation.pass_count}/{simulation.total} checks passed
            </span>
            {simulation.estimated_review_time && (
              <span className="flex items-center gap-1 text-gray-400">
                <Clock size={12} />
                Est. review: {simulation.estimated_review_time}
              </span>
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
  const [locale, setLocale] = useState('en-US')
  const [activeTab, setActiveTab] = useState<Tab>('preview')

  const { data: project } = useQuery<Project>({
    queryKey: ['projects', id],
    queryFn: () => api.get(`/projects/${id}`).then(r => r.data),
  })

  const { data: allMeta = [], isLoading } = useQuery<StoreMetadata[]>({
    queryKey: ['store-metadata', id, locale],
    queryFn: () => api.get(`/projects/${id}/store-metadata?locale=${locale}`).then(r => r.data),
  })

  const { data: localeData } = useQuery<{ configured: Record<string, string[]>; supported: string[] }>({
    queryKey: ['store-metadata-locales', id],
    queryFn: () => api.get(`/projects/${id}/store-metadata/locales`).then(r => r.data),
  })

  const meta = allMeta.find(m => m.platform === platform) || null

  const { data: compliance, isLoading: isLoadingCompliance, refetch: refetchCompliance } = useQuery<ComplianceResult>({
    queryKey: ['store-compliance', id, platform, locale],
    queryFn: () => api.get(`/projects/${id}/store-metadata/${platform}/compliance?locale=${locale}`).then(r => r.data),
    enabled: activeTab === 'compliance',
  })

  const { data: simulation, isLoading: isLoadingSimulation, refetch: refetchSimulation } = useQuery<ReviewSimulation>({
    queryKey: ['store-simulation', id, platform, locale],
    queryFn: () => api.get(`/projects/${id}/store-metadata/${platform}/simulate-review?locale=${locale}`).then(r => r.data),
    enabled: activeTab === 'compliance',
  })

  const saveMutation = useMutation({
    mutationFn: (data: Partial<StoreMetadata>) =>
      api.put(`/projects/${id}/store-metadata/${platform}?locale=${locale}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['store-metadata', id] })
      queryClient.invalidateQueries({ queryKey: ['store-metadata-locales', id] })
    },
  })

  const iconMutation = useMutation({
    mutationFn: (url: string) =>
      api.post(`/projects/${id}/store-metadata/${platform}/icon?locale=${locale}`, { icon_url: url }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['store-metadata', id] }),
  })

  const screenshotMutation = useMutation({
    mutationFn: (screenshots: Record<string, string[]>) =>
      api.post(`/projects/${id}/store-metadata/${platform}/screenshots?locale=${locale}`, { screenshots }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['store-metadata', id] }),
  })

  const runComplianceCheck = useCallback(() => {
    refetchCompliance()
    refetchSimulation()
  }, [refetchCompliance, refetchSimulation])

  const tabs: { key: Tab; label: string; icon: typeof Eye }[] = [
    { key: 'preview', label: 'Store Preview', icon: Eye },
    { key: 'metadata', label: 'Metadata', icon: FileText },
    { key: 'assets', label: 'Assets', icon: Image },
    { key: 'compliance', label: 'Compliance', icon: Shield },
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
  const configuredLocales = localeData?.configured || {}

  return (
    <div className="p-8 max-w-6xl">
      <Link to={`/dashboard/projects/${id}`}
        className="flex items-center gap-2 text-sm text-gray-400 hover:text-white mb-6 transition-colors">
        <ArrowLeft size={16} /> Back to {project?.name || 'Project'}
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
          <p className="text-sm text-gray-500 mt-1">Configure how your app appears on the stores</p>
        </div>
        <div className="flex items-center gap-3">
          <LocaleSelector locale={locale} onChange={setLocale} configuredLocales={configuredLocales} />
          <div className="flex bg-gray-800 rounded-lg p-0.5">
            {(['android', 'ios'] as Platform[]).map(p => (
              <button key={p} onClick={() => setPlatform(p)}
                className={clsx('px-4 py-2 text-sm font-medium rounded-md transition-colors',
                  platform === p
                    ? p === 'android' ? 'bg-green-600 text-white' : 'bg-gray-600 text-white'
                    : 'text-gray-400 hover:text-white')}>
                {p === 'android' ? 'Android' : 'iOS'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {Object.keys(configuredLocales).length > 1 && (
        <div className="flex items-center gap-2 mb-4 text-xs text-gray-500">
          <Languages size={12} />
          <span>Configured languages:</span>
          {Object.keys(configuredLocales).map(l => (
            <button key={l} onClick={() => setLocale(l)}
              className={clsx('px-2 py-0.5 rounded', locale === l ? 'bg-primary-600 text-white' : 'bg-gray-800 hover:bg-gray-700')}>
              {LOCALES.find(loc => loc.code === l)?.flag || l}
            </button>
          ))}
        </div>
      )}

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-6">
        <p className="text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wide">Readiness Checklist</p>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
          {Object.entries(readiness).map(([key, ok]) => (
            <div key={key} className={clsx('flex items-center gap-2 px-3 py-2 rounded-lg text-xs',
              ok ? 'bg-green-500/10 text-green-300' : 'bg-gray-800 text-gray-500')}>
              {ok ? <Check size={12} /> : <AlertCircle size={12} />}
              <span className="capitalize">{key.replace(/([A-Z])/g, ' $1').trim()}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex gap-1 mb-6 bg-gray-900 border border-gray-800 rounded-xl p-1">
        {tabs.map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => setActiveTab(key)}
            className={clsx('flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-colors flex-1 justify-center',
              activeTab === key ? 'bg-primary-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800')}>
            <Icon size={14} /> {label}
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
                  <span className="text-gray-600 ml-1">
                    ({LOCALES.find(l => l.code === locale)?.label || locale})
                  </span>
                </p>
              </div>
              <div className="grid md:grid-cols-2 gap-8 items-start">
                <PhoneMockup platform={platform} meta={meta} />
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                  <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
                    <Globe size={14} /> Store Listing Preview
                  </h3>
                  <div className="space-y-4">
                    {[
                      { label: 'App Name', value: meta?.app_name },
                      { label: 'Bundle ID', value: meta?.bundle_id, mono: true },
                      { label: 'Category', value: meta?.category },
                      { label: 'Version', value: meta?.version || '1.0.0' },
                      { label: 'Locale', value: `${locale} (${LOCALES.find(l => l.code === locale)?.label || ''})` },
                    ].map(({ label, value, mono }) => (
                      <div key={label}>
                        <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">{label}</p>
                        <p className={clsx('text-sm', mono && 'font-mono text-gray-400')}>
                          {value || <span className="text-gray-600 italic">Not set</span>}
                        </p>
                      </div>
                    ))}
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
                <span className="text-xs text-gray-500 font-normal ml-2">
                  ({LOCALES.find(l => l.code === locale)?.label || locale})
                </span>
              </h3>
              <MetadataForm
                key={`${platform}-${locale}-${meta?.id || 'new'}`}
                platform={platform}
                meta={meta}
                onSave={(data) => saveMutation.mutate(data)}
                isSaving={saveMutation.isPending}
              />
            </div>
          )}

          {activeTab === 'assets' && (
            <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-6">
              <AssetManager
                key={`${platform}-${locale}-${meta?.id || 'new'}`}
                platform={platform}
                meta={meta}
                projectId={id || ''}
                onIconSave={(url) => iconMutation.mutate(url)}
                onScreenshotsSave={(s) => screenshotMutation.mutate(s)}
                isSaving={iconMutation.isPending || screenshotMutation.isPending}
              />
            </div>
          )}

          {activeTab === 'compliance' && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
              <CompliancePanel
                compliance={compliance}
                simulation={simulation}
                isLoadingCompliance={isLoadingCompliance}
                isLoadingSimulation={isLoadingSimulation}
                onRunCheck={runComplianceCheck}
              />
            </div>
          )}
        </>
      )}
    </div>
  )
}
