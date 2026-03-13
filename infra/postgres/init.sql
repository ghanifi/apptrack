-- AppTrack initial schema

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255),
    github_id VARCHAR(100),
    github_access_token TEXT,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_github_id ON users(github_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    repo_url TEXT NOT NULL,
    branch VARCHAR(100) DEFAULT 'main',
    framework VARCHAR(50) DEFAULT 'unknown',
    status VARCHAR(50) DEFAULT 'pending',
    clone_path TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_projects_owner_id ON projects(owner_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_owner_created ON projects(owner_id, created_at DESC);

CREATE TABLE IF NOT EXISTS builds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    platform VARCHAR(20) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'queued',
    artifact_url TEXT,
    artifact_checksum VARCHAR(128),
    external_build_id VARCHAR(255),
    idempotency_key VARCHAR(64),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_builds_project_id ON builds(project_id);
CREATE INDEX IF NOT EXISTS idx_builds_status ON builds(status);
CREATE INDEX IF NOT EXISTS idx_builds_idempotency_key ON builds(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_builds_external_id ON builds(external_build_id);
CREATE INDEX IF NOT EXISTS idx_builds_project_created ON builds(project_id, created_at DESC);

-- Add log_output column if it does not exist
ALTER TABLE builds ADD COLUMN IF NOT EXISTS log_output TEXT;

-- PR build support columns
ALTER TABLE builds ADD COLUMN IF NOT EXISTS trigger_type VARCHAR(20) DEFAULT 'push';
ALTER TABLE builds ADD COLUMN IF NOT EXISTS pr_number INTEGER;
ALTER TABLE builds ADD COLUMN IF NOT EXISTS commit_sha VARCHAR(40);

-- Stripe billing columns on user_quotas
ALTER TABLE user_quotas ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255);
ALTER TABLE user_quotas ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(255);

CREATE TABLE IF NOT EXISTS deployments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    build_id UUID NOT NULL REFERENCES builds(id) ON DELETE CASCADE,
    target VARCHAR(50) NOT NULL,
    track VARCHAR(50) DEFAULT 'internal',
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_deployments_build_id ON deployments(build_id);
CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments(status);

CREATE TABLE IF NOT EXISTS credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    key_name VARCHAR(100) NOT NULL,
    encrypted_value TEXT NOT NULL,
    key_version VARCHAR(20) DEFAULT 'v1',
    expires_at TIMESTAMPTZ,
    rotation_due_at TIMESTAMPTZ,
    last_rotated_at TIMESTAMPTZ,
    rotation_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (owner_id, provider, key_name)
);

CREATE INDEX IF NOT EXISTS idx_credentials_owner ON credentials(owner_id);
CREATE INDEX IF NOT EXISTS idx_credentials_owner_provider ON credentials(owner_id, provider);

-- Audit Logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(255),
    details JSONB,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    trace_id VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_user_created ON audit_logs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_logs(resource_type, resource_id);

-- Usage Records
CREATE TABLE IF NOT EXISTS usage_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    metric_type VARCHAR(50) NOT NULL,
    value DOUBLE PRECISION DEFAULT 0,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    metadata_json JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usage_user_type_period ON usage_records(user_id, metric_type, period_start);

-- User Quotas
CREATE TABLE IF NOT EXISTS user_quotas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan VARCHAR(50) DEFAULT 'free',
    max_projects INTEGER DEFAULT 3,
    max_builds_per_month INTEGER DEFAULT 10,
    max_deploys_per_month INTEGER DEFAULT 5,
    max_storage_mb INTEGER DEFAULT 500,
    max_concurrent_builds INTEGER DEFAULT 1,
    max_preview_sessions INTEGER DEFAULT 2,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id)
);

-- Feature Flags
CREATE TABLE IF NOT EXISTS feature_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    enabled BOOLEAN DEFAULT FALSE,
    description TEXT,
    allowed_users JSONB,
    percentage INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Default feature flags
INSERT INTO feature_flags (name, enabled, description) VALUES
    ('preview_service', true, 'Enable preview service for projects'),
    ('native_simulator', false, 'Enable native simulator preview'),
    ('store_deploy', true, 'Enable store deployment'),
    ('build_codemagic', true, 'Enable Codemagic build provider'),
    ('build_eas', true, 'Enable EAS build provider')
ON CONFLICT (name) DO NOTHING;

-- Webhook Nonces
CREATE TABLE IF NOT EXISTS webhook_nonces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(50) NOT NULL,
    nonce_value VARCHAR(255) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nonce_source_value ON webhook_nonces(source, nonce_value);
CREATE INDEX IF NOT EXISTS idx_nonce_expires ON webhook_nonces(expires_at);

-- Idempotency Records
CREATE TABLE IF NOT EXISTS idempotency_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(128) NOT NULL,
    endpoint VARCHAR(100) NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    response_hash VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (key, endpoint, user_id)
);

CREATE INDEX IF NOT EXISTS idx_idempotency_expires ON idempotency_records(expires_at);

-- RBAC: Roles
CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- RBAC: Role Permissions
CREATE TABLE IF NOT EXISTS role_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    resource VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    UNIQUE (role_id, resource, action)
);

-- RBAC: User Roles
CREATE TABLE IF NOT EXISTS user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    granted_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, project_id)
);

CREATE INDEX IF NOT EXISTS idx_user_roles_project ON user_roles(project_id);

-- Default System Roles
INSERT INTO roles (name, description, is_system) VALUES
    ('owner', 'Full project access including deletion and settings', true),
    ('developer', 'Build, deploy, and manage code', true),
    ('viewer', 'Read-only access to project data', true),
    ('billing_admin', 'Manage billing and subscription settings', true)
ON CONFLICT (name) DO NOTHING;

-- Default Permissions for Owner
INSERT INTO role_permissions (role_id, resource, action)
SELECT r.id, p.resource, p.action
FROM roles r
CROSS JOIN (VALUES
    ('project', 'read'), ('project', 'write'), ('project', 'delete'), ('project', 'settings'),
    ('build', 'read'), ('build', 'trigger'), ('build', 'cancel'),
    ('deploy', 'read'), ('deploy', 'trigger'), ('deploy', 'approve'),
    ('credential', 'read'), ('credential', 'write'), ('credential', 'delete'),
    ('member', 'read'), ('member', 'invite'), ('member', 'remove'),
    ('policy', 'read'), ('policy', 'write'), ('policy', 'delete'),
    ('audit', 'read'), ('backup', 'trigger'), ('backup', 'read')
) AS p(resource, action)
WHERE r.name = 'owner'
ON CONFLICT (role_id, resource, action) DO NOTHING;

-- Default Permissions for Developer
INSERT INTO role_permissions (role_id, resource, action)
SELECT r.id, p.resource, p.action
FROM roles r
CROSS JOIN (VALUES
    ('project', 'read'), ('project', 'write'),
    ('build', 'read'), ('build', 'trigger'), ('build', 'cancel'),
    ('deploy', 'read'), ('deploy', 'trigger'),
    ('credential', 'read'),
    ('member', 'read'),
    ('policy', 'read'),
    ('audit', 'read')
) AS p(resource, action)
WHERE r.name = 'developer'
ON CONFLICT (role_id, resource, action) DO NOTHING;

-- Default Permissions for Viewer
INSERT INTO role_permissions (role_id, resource, action)
SELECT r.id, p.resource, p.action
FROM roles r
CROSS JOIN (VALUES
    ('project', 'read'),
    ('build', 'read'),
    ('deploy', 'read'),
    ('audit', 'read')
) AS p(resource, action)
WHERE r.name = 'viewer'
ON CONFLICT (role_id, resource, action) DO NOTHING;

-- Default Permissions for Billing Admin
INSERT INTO role_permissions (role_id, resource, action)
SELECT r.id, p.resource, p.action
FROM roles r
CROSS JOIN (VALUES
    ('project', 'read'),
    ('build', 'read'),
    ('deploy', 'read'),
    ('credential', 'read'), ('credential', 'write'),
    ('audit', 'read'),
    ('billing', 'read'), ('billing', 'write')
) AS p(resource, action)
WHERE r.name = 'billing_admin'
ON CONFLICT (role_id, resource, action) DO NOTHING;

-- Immutable Audit Chain
CREATE TABLE IF NOT EXISTS immutable_audit_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sequence_number BIGSERIAL UNIQUE NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(255),
    details JSONB,
    ip_address VARCHAR(45),
    previous_hash VARCHAR(64) NOT NULL,
    entry_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_immutable_audit_user ON immutable_audit_entries(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_immutable_audit_action ON immutable_audit_entries(action);
CREATE INDEX IF NOT EXISTS idx_immutable_audit_chain ON immutable_audit_entries(sequence_number);

-- Secret Rotation Logs
CREATE TABLE IF NOT EXISTS secret_rotation_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    credential_id UUID NOT NULL REFERENCES credentials(id) ON DELETE CASCADE,
    old_key_version VARCHAR(50),
    new_key_version VARCHAR(50),
    rotation_type VARCHAR(30) NOT NULL,
    triggered_by UUID REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(30) DEFAULT 'completed',
    rotated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_secret_rotation_cred ON secret_rotation_logs(credential_id, rotated_at);

-- Deploy Policies
CREATE TABLE IF NOT EXISTS deploy_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    policy_type VARCHAR(50) NOT NULL,
    rules JSONB NOT NULL,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_deploy_policy_project ON deploy_policies(project_id);

-- Deploy Approvals
CREATE TABLE IF NOT EXISTS deploy_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deployment_id UUID NOT NULL REFERENCES deployments(id) ON DELETE CASCADE,
    approver_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    decision VARCHAR(20) NOT NULL,
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (deployment_id, approver_id)
);

-- Backup Jobs
CREATE TABLE IF NOT EXISTS backup_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    backup_type VARCHAR(30) NOT NULL,
    status VARCHAR(30) DEFAULT 'pending',
    storage_path TEXT,
    size_bytes BIGINT,
    checksum VARCHAR(128),
    metadata_json JSONB,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    triggered_by UUID REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_backup_status ON backup_jobs(status);
CREATE INDEX IF NOT EXISTS idx_backup_type_created ON backup_jobs(backup_type, created_at);

-- Artifact Storage (migrated from file system)
CREATE TABLE IF NOT EXISTS artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    build_id VARCHAR(64) NOT NULL,
    owner_id VARCHAR(64) DEFAULT '',
    platform VARCHAR(20) DEFAULT '',
    filename VARCHAR(255),
    object_key TEXT NOT NULL,
    url TEXT,
    checksum VARCHAR(64),
    size_bytes BIGINT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_artifacts_build_id ON artifacts(build_id);

-- Preview States (migrated from file system)
CREATE TABLE IF NOT EXISTS preview_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(64) NOT NULL UNIQUE,
    framework VARCHAR(50) DEFAULT '',
    status VARCHAR(50) DEFAULT 'pending',
    preview_type VARCHAR(50) DEFAULT '',
    preview_url TEXT,
    embed_url TEXT,
    qr_url TEXT,
    instructions TEXT,
    extra JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_preview_states_project_id ON preview_states(project_id);

-- Support Tickets
CREATE TABLE IF NOT EXISTS support_tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    subject VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    category VARCHAR(20) NOT NULL DEFAULT 'general',
    priority VARCHAR(10) NOT NULL DEFAULT 'medium',
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_support_tickets_user_id ON support_tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status);

-- Organizations
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    owner_id UUID REFERENCES users(id) ON DELETE SET NULL,
    plan VARCHAR(20) NOT NULL DEFAULT 'free',
    max_members INTEGER NOT NULL DEFAULT 5,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug);
CREATE INDEX IF NOT EXISTS idx_organizations_owner ON organizations(owner_id);

-- Organization Members
CREATE TABLE IF NOT EXISTS org_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL DEFAULT 'member',
    invited_by UUID REFERENCES users(id),
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_org_members_org ON org_members(org_id);
CREATE INDEX IF NOT EXISTS idx_org_members_user ON org_members(user_id);

-- OTA Updates
CREATE TABLE IF NOT EXISTS ota_updates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    channel VARCHAR(50) NOT NULL DEFAULT 'production',
    platform VARCHAR(10) NOT NULL DEFAULT 'all',
    runtime_version VARCHAR(50) NOT NULL DEFAULT '1.0.0',
    bundle_url TEXT NOT NULL,
    message TEXT DEFAULT '',
    status VARCHAR(20) NOT NULL DEFAULT 'published',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE ota_updates ADD COLUMN IF NOT EXISTS bundle_hash VARCHAR(64);

CREATE INDEX IF NOT EXISTS idx_ota_updates_project ON ota_updates(project_id);
CREATE INDEX IF NOT EXISTS idx_ota_updates_channel ON ota_updates(project_id, channel);

-- Capacitor/PWA build support columns
ALTER TABLE projects ADD COLUMN IF NOT EXISTS build_provider VARCHAR(50);
ALTER TABLE projects ADD COLUMN IF NOT EXISTS repo_visibility VARCHAR(20) DEFAULT 'private';
ALTER TABLE builds ADD COLUMN IF NOT EXISTS workflow_file VARCHAR(100);

-- Add org_id to projects (nullable, for gradual migration)
ALTER TABLE projects ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_projects_org ON projects(org_id);

-- SSO Providers
CREATE TABLE IF NOT EXISTS sso_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    provider_type VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL DEFAULT 'Corporate SSO',
    client_id TEXT,
    encrypted_client_secret TEXT,
    discovery_url TEXT,
    metadata_url TEXT,
    allowed_domains TEXT,
    enabled BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sso_providers_org ON sso_providers(org_id);
CREATE INDEX IF NOT EXISTS idx_sso_providers_enabled ON sso_providers(org_id, enabled);

-- Notifications
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    read BOOLEAN DEFAULT FALSE,
    channel VARCHAR(20) DEFAULT 'in_app',
    resource_type VARCHAR(50),
    resource_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, read);
CREATE INDEX IF NOT EXISTS idx_notifications_user_created ON notifications(user_id, created_at);

-- Notification Preferences
CREATE TABLE IF NOT EXISTS notification_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email_enabled BOOLEAN DEFAULT TRUE,
    slack_enabled BOOLEAN DEFAULT FALSE,
    slack_webhook_url TEXT,
    discord_enabled BOOLEAN DEFAULT FALSE,
    discord_webhook_url TEXT,
    in_app_enabled BOOLEAN DEFAULT TRUE,
    notify_build_success BOOLEAN DEFAULT TRUE,
    notify_build_failed BOOLEAN DEFAULT TRUE,
    notify_deploy_completed BOOLEAN DEFAULT TRUE,
    notify_deploy_failed BOOLEAN DEFAULT TRUE,
    notify_quota_warning BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id)
);

-- Incidents (Status Page)
CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'investigating',
    severity VARCHAR(20) NOT NULL DEFAULT 'minor',
    message TEXT NOT NULL,
    affected_components JSONB,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_created ON incidents(created_at);

-- Incident Updates
CREATE TABLE IF NOT EXISTS incident_updates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    status VARCHAR(30) NOT NULL,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_incident_updates_incident ON incident_updates(incident_id, created_at);

-- Build Cache
CREATE TABLE IF NOT EXISTS build_caches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    cache_key VARCHAR(128) NOT NULL,
    s3_path TEXT NOT NULL,
    size_bytes BIGINT DEFAULT 0,
    last_used TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_build_cache_project ON build_caches(project_id);
CREATE INDEX IF NOT EXISTS idx_build_cache_key ON build_caches(cache_key);

-- Releases
CREATE TABLE IF NOT EXISTS releases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    build_id UUID REFERENCES builds(id) ON DELETE SET NULL,
    version VARCHAR(50),
    title VARCHAR(255) NOT NULL,
    notes TEXT NOT NULL,
    auto_generated BOOLEAN DEFAULT TRUE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_releases_build ON releases(build_id);
CREATE INDEX IF NOT EXISTS idx_releases_project ON releases(project_id);
