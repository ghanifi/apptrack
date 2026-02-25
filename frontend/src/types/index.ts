export interface Project {
  id: string
  name: string
  repo_url: string
  branch: string
  framework: 'flutter' | 'react_native' | 'expo' | 'swift' | 'kotlin' | 'unknown'
  status: 'pending' | 'analyzing' | 'ready' | 'building' | 'deploying' | 'error'
  created_at: string
  updated_at: string
  owner_id: string
  builds: Build[]
  last_build?: Build
}

export interface Build {
  id: string
  project_id: string
  platform: 'android' | 'ios' | 'both'
  provider: 'eas' | 'codemagic' | 'github_actions'
  status: 'queued' | 'running' | 'success' | 'failed'
  artifact_url?: string
  started_at?: string
  finished_at?: string
  created_at: string
}

export interface Deployment {
  id: string
  build_id: string
  target: 'google_play' | 'app_store'
  track: string
  status: 'pending' | 'uploading' | 'in_review' | 'published' | 'failed'
  created_at: string
  updated_at: string
}

export interface StoreMetadata {
  id: string
  project_id: string
  platform: 'android' | 'ios'
  locale: string
  app_name: string | null
  short_description: string | null
  full_description: string | null
  keywords: string | null
  privacy_url: string | null
  support_url: string | null
  marketing_url: string | null
  category: string | null
  bundle_id: string | null
  version: string | null
  icon_url: string | null
  screenshots: Record<string, string[]> | null
  feature_graphic_url: string | null
  created_at: string
  updated_at: string
}

export interface ComplianceResult {
  ready: boolean
  score: number
  errors: { field: string; severity: string; message: string }[]
  warnings: { field: string; severity: string; message: string }[]
  platform: string
  locale: string
}

export interface ReviewSimulation {
  verdict: 'likely_approved' | 'needs_improvement' | 'likely_rejected'
  checks: { check: string; status: 'pass' | 'warning' | 'fail'; detail: string }[]
  pass_count: number
  fail_count: number
  total: number
  estimated_review_time: string | null
  platform: string
}
