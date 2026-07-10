export interface Project {
  id: string
  name: string
  repo_url: string
  branch: string
  framework: 'flutter' | 'react_native' | 'expo' | 'swift' | 'kotlin' | 'capacitor' | 'ionic' | 'cordova' | 'pwa' | 'unknown'
  status: 'pending' | 'analyzing' | 'ready' | 'building' | 'deploying' | 'error'
  repo_visibility?: 'public' | 'private'
  runner_type?: 'hosted' | 'self_hosted'
  runner_labels?: string | null
  created_at: string
  updated_at: string
  owner_id: string
  builds: Build[]
  last_build?: Build
}

export interface Build {
  id: string
  project_id: string
  platform: 'android' | 'ios' | 'both' | 'web'
  provider: 'eas' | 'codemagic' | 'github_actions' | 'self_hosted'
  status: 'queued' | 'running' | 'success' | 'failed' | 'cancelled'
  artifact_url?: string
  error_message?: string
  log_output?: string
  trigger_type?: 'push' | 'pull_request' | 'manual'
  pr_number?: number
  commit_sha?: string
  started_at?: string
  finished_at?: string
  created_at: string
}

export interface BuildDiagnosis {
  id: string
  framework_group: string
  diagnosis: string
  fix: string
  auto_fix: boolean
}

export interface BuildDiagnosisResult {
  build_id: string
  project_id: string
  platform: string
  provider: string
  framework: string | null
  status: string
  diagnoses: BuildDiagnosis[]
  diagnosis_count: number
  severity: 'critical' | 'high' | 'medium' | 'low'
  auto_fixable: boolean
  message?: string
}

export interface Deployment {
  id: string
  build_id: string
  target: 'google_play' | 'app_store' | 'web'
  track: string
  status: 'pending' | 'uploading' | 'in_review' | 'published' | 'canary' | 'rolled_back' | 'failed'
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

export interface Notification {
  id: string
  type: string
  title: string
  body: string
  read: boolean
  channel: string
  resource_type?: string
  resource_id?: string
  created_at: string
}

export interface NotificationPreferences {
  email_enabled: boolean
  slack_enabled: boolean
  slack_webhook_url?: string
  discord_enabled: boolean
  discord_webhook_url?: string
  in_app_enabled: boolean
  notify_build_success: boolean
  notify_build_failed: boolean
  notify_deploy_completed: boolean
  notify_deploy_failed: boolean
  notify_quota_warning: boolean
}

export interface Incident {
  id: string
  title: string
  status: 'investigating' | 'identified' | 'monitoring' | 'resolved'
  severity: 'minor' | 'major' | 'critical'
  message: string
  affected_components?: string[]
  resolved_at?: string
  created_at: string
  updated_at: string
  updates?: IncidentUpdate[]
}

export interface IncidentUpdate {
  id: string
  message: string
  status: string
  created_at: string
}

export interface ReleaseNotes {
  id: string
  build_id?: string
  project_id: string
  version?: string
  title: string
  notes: string
  auto_generated: boolean
  created_at: string
}

export interface PlanInfo {
  name: string
  price_usd: number
  features: {
    max_projects: number
    max_builds_per_month: number
    max_deploys_per_month: number
    max_storage_mb: number
    max_concurrent_builds: number
    max_preview_sessions: number
  }
}

export interface CurrentPlan {
  plan: string
  price_usd: number
  stripe_configured?: boolean
  quotas: {
    max_projects: number
    max_builds_per_month: number
    max_deploys_per_month: number
    max_storage_mb: number
    max_concurrent_builds: number
    max_preview_sessions: number
  }
}

export interface UsageSummary {
  plan: string
  period: string
  usage: {
    projects: { current: number; limit: number }
    builds_this_month: { current: number; limit: number }
    deploys_this_month: { current: number; limit: number }
    concurrent_builds: { current: number; limit: number }
    storage_mb: { current: number; limit: number }
    build_minutes: { current: number }
  }
}
