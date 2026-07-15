import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SAEnum, UniqueConstraint, Integer, BigInteger, Boolean, Float, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class User(Base):
    """Platform kullanıcısı — GitHub OAuth veya email/password ile kayıt."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()), comment="Kullanıcı UUID")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Görünen ad")
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, comment="E-posta adresi (unique)")
    hashed_password: Mapped[str | None] = mapped_column(String(255), comment="Bcrypt hash — OAuth kullanıcılarında null")
    github_id: Mapped[str | None] = mapped_column(String(100), comment="GitHub kullanıcı ID'si")
    github_access_token: Mapped[str | None] = mapped_column(Text, comment="Fernet ile şifrelenmiş GitHub access token")
    avatar_url: Mapped[str | None] = mapped_column(Text, comment="Profil fotoğrafı URL'si")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Platform admin yetkisi — yalnız DB'den atanır, kayıtla asla True olmaz")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="Kayıt tarihi")

    projects: Mapped[list["Project"]] = relationship("Project", back_populates="owner", cascade="all, delete-orphan")


class Project(Base):
    """Mobil uygulama projesi — GitHub repo'suna bağlı, framework otomatik tespit edilir."""
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()), comment="Proje UUID")
    owner_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="Proje sahibi kullanıcı ID")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Proje adı")
    repo_url: Mapped[str] = mapped_column(Text, nullable=False, comment="GitHub repo URL'si")
    branch: Mapped[str] = mapped_column(String(100), default="main", comment="Hedef branch: main, develop vb.")
    framework: Mapped[str] = mapped_column(String(50), default="unknown", comment="Tespit edilen framework: react-native, flutter, expo, swift, kotlin")
    status: Mapped[str] = mapped_column(String(50), default="pending", comment="Proje durumu: pending, analyzing, active, building, error")
    clone_path: Mapped[str | None] = mapped_column(Text, comment="Sunucudaki clone dizini")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="Oluşturulma tarihi")
    build_provider: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="Override build provider: github_actions, eas, codemagic, self_hosted")
    repo_visibility: Mapped[str] = mapped_column(String(20), default="private", comment="GitHub repo gorunurlugu: public, private")
    runner_type: Mapped[str] = mapped_column(String(20), default="hosted", comment="GitHub Actions runner tipi: hosted (macos-26), self_hosted")
    runner_labels: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Self-hosted için opsiyonel özel runner label CSV'i (boşsa self-hosted,macOS,ARM64)")
    org_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True, comment="Bağlı organizasyon ID (opsiyonel)")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="Son güncelleme tarihi")

    owner: Mapped["User"] = relationship("User", back_populates="projects")
    builds: Mapped[list["Build"]] = relationship("Build", back_populates="project", cascade="all, delete-orphan")


class Build(Base):
    """CI/CD build kaydı — EAS, Codemagic veya GitHub Actions üzerinde çalışır."""
    __tablename__ = "builds"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()), comment="Build UUID")
    project_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, comment="Hedef proje ID")
    platform: Mapped[str] = mapped_column(String(20), nullable=False, comment="Hedef platform: android, ios, both")
    provider: Mapped[str] = mapped_column(String(50), nullable=False, comment="CI provider: eas, codemagic, github_actions")
    status: Mapped[str] = mapped_column(String(50), default="queued", comment="Build durumu: queued, running, success, failed, cancelled")
    artifact_url: Mapped[str | None] = mapped_column(Text, comment="Build artifact (APK/IPA) URL'si")
    artifact_checksum: Mapped[str | None] = mapped_column(String(128), comment="Artifact SHA-256 hash")
    artifact_signature: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="IPA imza incelemesi: has_ipa/signed/profile_name/profile_expires")
    log_output: Mapped[str | None] = mapped_column(Text, comment="Build log çıktısı")
    external_build_id: Mapped[str | None] = mapped_column(String(255), comment="Harici provider build ID'si")
    workflow_file: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="GitHub Actions workflow dosya adı")
    idempotency_key: Mapped[str | None] = mapped_column(String(64), index=True, comment="Duplikat build önleme anahtarı")
    trigger_type: Mapped[str] = mapped_column(String(20), default="push", comment="Tetikleme tipi: push, pull_request, manual")
    pr_number: Mapped[int | None] = mapped_column(Integer, comment="PR numarası (pull_request trigger için)")
    commit_sha: Mapped[str | None] = mapped_column(String(40), comment="Commit SHA hash")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, comment="Build başlangıç zamanı")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, comment="Build bitiş zamanı")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="Oluşturulma tarihi")

    project: Mapped["Project"] = relationship("Project", back_populates="builds")
    deployments: Mapped[list["Deployment"]] = relationship("Deployment", back_populates="build", cascade="all, delete-orphan")


class Deployment(Base):
    """Store deploy kaydı — Google Play veya App Store'a yayınlama."""
    __tablename__ = "deployments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()), comment="Deployment UUID")
    build_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("builds.id", ondelete="CASCADE"), nullable=False, comment="Kaynak build ID")
    target: Mapped[str] = mapped_column(String(50), nullable=False, comment="Hedef store: google_play, app_store")
    track: Mapped[str] = mapped_column(String(50), default="internal", comment="Release track: internal, beta, production")
    status: Mapped[str] = mapped_column(String(50), default="pending", comment="Deploy durumu: pending, uploading, published, failed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="Oluşturulma tarihi")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="Son güncelleme tarihi")

    build: Mapped["Build"] = relationship("Build", back_populates="deployments")


class Credential(Base):
    """Fernet ile şifrelenmiş API key/token — provider bazlı (EAS, Codemagic, Google Play, App Store)."""
    __tablename__ = "credentials"
    __table_args__ = (
        UniqueConstraint("owner_id", "provider", "key_name", name="uq_credential_owner_provider_key"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()), comment="Credential UUID")
    owner_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="Credential sahibi")
    provider: Mapped[str] = mapped_column(String(50), nullable=False, comment="Provider: eas, codemagic, google_play, app_store")
    key_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Key adı: EAS_TOKEN, CODEMAGIC_TOKEN vb.")
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False, comment="Fernet ile şifrelenmiş değer")
    key_version: Mapped[str] = mapped_column(String(20), default="v1", comment="Şifreleme key versiyonu")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, comment="Credential son kullanma tarihi")
    rotation_due_at: Mapped[datetime | None] = mapped_column(DateTime, comment="Planlanan rotasyon tarihi")
    last_rotated_at: Mapped[datetime | None] = mapped_column(DateTime, comment="Son rotasyon tarihi")
    rotation_count: Mapped[int] = mapped_column(Integer, default=0, comment="Toplam rotasyon sayısı")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="Oluşturulma tarihi")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="Son güncelleme tarihi")

    owner: Mapped["User"] = relationship("User")


class AuditLog(Base):
    """Audit log kaydı — tüm kullanıcı ve sistem eylemlerini izler."""
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_user_created", "user_id", "created_at"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(255))
    details: Mapped[dict | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    trace_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UsageRecord(Base):
    """Kullanım kaydı — build, deploy, storage gibi metrikler period bazlı izlenir."""
    __tablename__ = "usage_records"
    __table_args__ = (
        Index("idx_usage_user_type_period", "user_id", "metric_type", "period_start"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[float] = mapped_column(Float, default=0)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserQuota(Base):
    """Kullanıcı kota limitleri — plan bazlı (free, pro, enterprise)."""
    __tablename__ = "user_quotas"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_quota"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="free")
    max_projects: Mapped[int] = mapped_column(Integer, default=3)
    max_builds_per_month: Mapped[int] = mapped_column(Integer, default=10)
    max_deploys_per_month: Mapped[int] = mapped_column(Integer, default=5)
    max_storage_mb: Mapped[int] = mapped_column(Integer, default=500)
    max_concurrent_builds: Mapped[int] = mapped_column(Integer, default=1)
    max_preview_sessions: Mapped[int] = mapped_column(Integer, default=2)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), comment="Stripe müşteri ID")
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), comment="Stripe abonelik ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship("User")


class FeatureFlag(Base):
    """Feature flag — kullanıcı bazlı veya yüzdelik açma/kapama."""
    __tablename__ = "feature_flags"
    __table_args__ = (
        UniqueConstraint("name", name="uq_feature_flag_name"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text)
    allowed_users: Mapped[dict | None] = mapped_column(JSONB)
    percentage: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WebhookNonce(Base):
    """Webhook replay attack koruması — kullanılan nonce değerleri."""
    __tablename__ = "webhook_nonces"
    __table_args__ = (
        Index("idx_nonce_source_value", "source", "nonce_value"),
        Index("idx_nonce_expires", "expires_at"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    nonce_value: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IdempotencyRecord(Base):
    """Idempotency kaydı — aynı isteğin tekrarlanmasını önler."""
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("key", "endpoint", "user_id", name="uq_idempotency_key_endpoint_user"),
        Index("idx_idempotency_expires", "expires_at"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    response_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.utcnow())


class Role(Base):
    """RBAC rolü — sistem veya kullanıcı tanımlı, izin gruplarına bağlı."""
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("name", name="uq_role_name"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    permissions: Mapped[list["RolePermission"]] = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")


class RolePermission(Base):
    """Rol-izin eşleştirmesi — resource:action çifti (ör: builds:create)."""
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "resource", "action", name="uq_role_permission"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    role_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    resource: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)

    role: Mapped["Role"] = relationship("Role", back_populates="permissions")


class UserRole(Base):
    """Kullanıcı-rol ataması — proje bazlı veya global olabilir."""
    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_user_role_project"),
        Index("idx_user_roles_project", "project_id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"))
    granted_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    role: Mapped["Role"] = relationship("Role")


class ImmutableAuditEntry(Base):
    """Değiştirilemez audit log — SHA-256 hash chain ile bütünlük garantisi."""
    __tablename__ = "immutable_audit_entries"
    __table_args__ = (
        Index("idx_immutable_audit_user", "user_id", "created_at"),
        Index("idx_immutable_audit_action", "action"),
        Index("idx_immutable_audit_chain", "sequence_number"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    sequence_number: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(255))
    details: Mapped[dict | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SecretRotationLog(Base):
    """Credential rotasyon geçmişi — kim, ne zaman, hangi versiyon."""
    __tablename__ = "secret_rotation_logs"
    __table_args__ = (
        Index("idx_secret_rotation_cred", "credential_id", "rotated_at"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    credential_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("credentials.id", ondelete="CASCADE"), nullable=False)
    old_key_version: Mapped[str | None] = mapped_column(String(50))
    new_key_version: Mapped[str | None] = mapped_column(String(50))
    rotation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    triggered_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(30), default="completed")
    rotated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DeployPolicy(Base):
    """Deploy politikası — branch kısıtlama, zaman penceresi, onay gereksinimleri."""
    __tablename__ = "deploy_policies"
    __table_args__ = (
        Index("idx_deploy_policy_project", "project_id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    policy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    rules: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DeployApproval(Base):
    """Deploy onayı — çoklu onay mekanizması, approve/reject kararı."""
    __tablename__ = "deploy_approvals"
    __table_args__ = (
        UniqueConstraint("deployment_id", "approver_id", name="uq_deploy_approval"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    deployment_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False)
    approver_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StoreMetadata(Base):
    """Store listing metadata — çoklu locale, app adı, açıklama, icon, screenshot."""
    __tablename__ = "store_metadata"
    __table_args__ = (
        UniqueConstraint("project_id", "platform", "locale", name="uq_store_meta_project_platform_locale"),
        Index("idx_store_meta_project", "project_id"),
        Index("idx_store_meta_locale", "project_id", "locale"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="en-US")
    app_name: Mapped[str | None] = mapped_column(String(255))
    short_description: Mapped[str | None] = mapped_column(String(80))
    full_description: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[str | None] = mapped_column(Text)
    privacy_url: Mapped[str | None] = mapped_column(Text)
    support_url: Mapped[str | None] = mapped_column(Text)
    marketing_url: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100))
    data_safety: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="Play Data Safety beyanı (AppTrack'te takip; Play Console'a manuel girilir)")
    bundle_id: Mapped[str | None] = mapped_column(String(255))
    version: Mapped[str | None] = mapped_column(String(50))
    icon_url: Mapped[str | None] = mapped_column(Text)
    screenshots: Mapped[dict | None] = mapped_column(JSONB)
    feature_graphic_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BackupJob(Base):
    """Veritabanı backup işi — full veya incremental, checksum ile doğrulama."""
    __tablename__ = "backup_jobs"
    __table_args__ = (
        Index("idx_backup_status", "status"),
        Index("idx_backup_type_created", "backup_type", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    backup_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    storage_path: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    checksum: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    triggered_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"))


class SupportTicket(Base):
    """Destek talebi — kullanıcı tarafından açılan bug/feature/billing talebi."""
    __tablename__ = "support_tickets"
    __table_args__ = (
        Index("idx_support_tickets_user_id", "user_id"),
        Index("idx_support_tickets_status", "status"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False, default="general")
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class Organization(Base):
    """Organizasyon — takım bazlı proje yönetimi, üye davet, rol atama."""
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    owner_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    plan: Mapped[str] = mapped_column(String(20), nullable=False, default="free")
    max_members: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class OrgMember(Base):
    """Organizasyon üyesi — role: owner, admin, member, viewer."""
    __tablename__ = "org_members"
    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_org_member"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")  # owner, admin, member, viewer
    invited_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class OTAUpdate(Base):
    """OTA güncelleme kaydı — EAS veya custom bundle, channel ve platform bazlı."""
    __tablename__ = "ota_updates"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(50), nullable=False, default="production")
    platform: Mapped[str] = mapped_column(String(10), nullable=False, default="all")
    runtime_version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    bundle_url: Mapped[str] = mapped_column(Text, nullable=False)
    bundle_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="Bundle SHA-256 hash for integrity")
    message: Mapped[str | None] = mapped_column(Text, nullable=True, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="published")  # published, rolled_back, deprecated
    created_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SSOProvider(Base):
    """SSO/OIDC provider yapılandırması — organizasyon bazlı kurumsal kimlik doğrulama."""
    __tablename__ = "sso_providers"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_type: Mapped[str] = mapped_column(String(20), nullable=False)  # oidc, saml
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="Corporate SSO")
    client_id: Mapped[str | None] = mapped_column(Text)
    encrypted_client_secret: Mapped[str | None] = mapped_column(Text)
    discovery_url: Mapped[str | None] = mapped_column(Text)  # OIDC: .well-known/openid-configuration
    metadata_url: Mapped[str | None] = mapped_column(Text)  # SAML: metadata XML URL
    allowed_domains: Mapped[str | None] = mapped_column(Text)  # Comma-separated email domains
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class Notification(Base):
    """Bildirim — build/deploy/system olayları için kullanıcı bildirimi."""
    __tablename__ = "notifications"
    __table_args__ = (
        Index("idx_notifications_user_read", "user_id", "read"),
        Index("idx_notifications_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False, comment="Bildirim tipi: build_success, build_failed, deploy_completed, quota_warning, system")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    channel: Mapped[str] = mapped_column(String(20), default="in_app", comment="Gönderim kanalı: in_app, email, slack, discord")
    resource_type: Mapped[str | None] = mapped_column(String(50), comment="İlgili kaynak tipi: build, deployment, project")
    resource_id: Mapped[str | None] = mapped_column(String(255), comment="İlgili kaynak ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NotificationPreference(Base):
    """Bildirim tercihleri — kullanıcı bazında kanal ve tip ayarları."""
    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_notification_pref_user"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    slack_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    slack_webhook_url: Mapped[str | None] = mapped_column(Text)
    discord_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    discord_webhook_url: Mapped[str | None] = mapped_column(Text)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_build_success: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_build_failed: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_deploy_completed: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_deploy_failed: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_quota_warning: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Incident(Base):
    """Status page olayı — sistem kesintileri ve bakım bildirimleri."""
    __tablename__ = "incidents"
    __table_args__ = (
        Index("idx_incidents_status", "status"),
        Index("idx_incidents_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="investigating", comment="investigating, identified, monitoring, resolved")
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="minor", comment="minor, major, critical")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    affected_components: Mapped[dict | None] = mapped_column(JSONB, comment="Etkilenen bileşenler listesi")
    created_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    updates: Mapped[list["IncidentUpdate"]] = relationship("IncidentUpdate", back_populates="incident", cascade="all, delete-orphan")


class IncidentUpdate(Base):
    """Olay güncelleme kaydı — incident için durum güncellemesi."""
    __tablename__ = "incident_updates"
    __table_args__ = (
        Index("idx_incident_updates_incident", "incident_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, comment="investigating, identified, monitoring, resolved")
    created_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    incident: Mapped["Incident"] = relationship("Incident", back_populates="updates")


class BuildCache(Base):
    """Build cache metadata — proje bazlı cache durumu ve S3/MinIO yolu."""
    __tablename__ = "build_caches"
    __table_args__ = (
        Index("idx_build_cache_project", "project_id"),
        Index("idx_build_cache_key", "cache_key"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    cache_key: Mapped[str] = mapped_column(String(128), nullable=False, comment="Cache hash key (lockfile hash)")
    s3_path: Mapped[str] = mapped_column(Text, nullable=False, comment="MinIO/S3 object path")
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    last_used: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Release(Base):
    """Release notes kaydı — build bazlı otomatik veya manuel release notes."""
    __tablename__ = "releases"
    __table_args__ = (
        Index("idx_releases_build", "build_id"),
        Index("idx_releases_project", "project_id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    build_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("builds.id", ondelete="SET NULL"))
    version: Mapped[str | None] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ApiKey(Base):
    """Programatik erişim için API anahtarı (MCP server / CLI / public API).
    Sadece SHA-256 hash saklanır; ham anahtar yalnızca oluşturma anında gösterilir."""
    __tablename__ = "api_keys"
    __table_args__ = (
        Index("idx_api_keys_user", "user_id"),
        Index("idx_api_keys_hash", "key_hash"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Kullanıcının verdiği etiket")
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False, comment="Görüntüleme için ilk karakterler (atk_xxxxxxxx)")
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, comment="Ham anahtarın SHA-256 hash'i")
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReleaseRollout(Base):
    """Staged (kademeli) yayın kaydı — bir production deploy'un rollout yaşam döngüsü.

    Android: userFraction 1%→10%→50%→100% + Play Reporting health + auto-halt.
    iOS: Apple'ın sabit phased-release programı (yalnız başlat/duraklat)."""
    __tablename__ = "release_rollouts"
    __table_args__ = (
        Index("idx_rollout_deployment", "deployment_id"),
        Index("idx_rollout_project_state", "project_id", "state"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    deployment_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, comment="google_play | app_store")
    package_name: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="Android package / iOS bundle — health & advance/halt için")
    track: Mapped[str] = mapped_column(String(50), default="production", comment="Google Play track")
    current_fraction: Mapped[float] = mapped_column(Float, default=0.01, comment="Mevcut rollout oranı (0.01/0.1/0.5/1.0); Apple'da bilgi amaçlı")
    state: Mapped[str] = mapped_column(String(20), default="in_progress", comment="in_progress | paused | halted | completed | failed")
    auto_halt_enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="Sağlık sağlayıcısı yoksa false'a düşer")
    crash_free_threshold: Mapped[float] = mapped_column(Float, default=0.99, comment="Mutlak crash-free taban eşiği")
    baseline_crash_free: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Rollout öncesi referans; >0.5pp düşüş de halt tetikler")
    min_users: Mapped[int] = mapped_column(Integer, default=1000, comment="Altında örnek değerlendirilmez (gürültü koruması)")
    halted_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Son store işlemi hatası (advance/halt başarısız)")
    release_version: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="Android versionCode / Sentry release — sürüm-filtreli sağlık için")
    external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="Apple phased release id vb.")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    deployment: Mapped["Deployment"] = relationship("Deployment")
    samples: Mapped[list["ReleaseHealthSample"]] = relationship(
        "ReleaseHealthSample", back_populates="rollout", cascade="all, delete-orphan")


class ReleaseHealthSample(Base):
    """Rollout sırasında periyodik crash-free/ANR/adoption örneği (zaman serisi)."""
    __tablename__ = "release_health_samples"
    __table_args__ = (
        Index("idx_health_sample_rollout", "rollout_id", "sampled_at"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    rollout_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("release_rollouts.id", ondelete="CASCADE"), nullable=False)
    sampled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    crash_free_rate: Mapped[float] = mapped_column(Float, nullable=False, comment="0.0–1.0")
    anr_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    distinct_users: Mapped[int] = mapped_column(Integer, default=0)
    adoption: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Sürümün kurulu taban içindeki payı, varsa")

    rollout: Mapped["ReleaseRollout"] = relationship("ReleaseRollout", back_populates="samples")
