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
