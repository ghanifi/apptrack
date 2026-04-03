"""Organization management router."""
import re
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Organization, OrgMember, User, Project
from app.limiter import limiter

router = APIRouter(prefix="/organizations", tags=["organizations"])


class OrgCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")


class OrgUpdate(BaseModel):
    name: str | None = None


class InviteMember(BaseModel):
    email: str
    role: str = "member"  # admin, member, viewer


class OrgResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class OrgDetailResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    owner_id: str
    max_members: int
    member_count: int
    project_count: int
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class OrgMemberResponse(BaseModel):
    id: str
    user_id: str
    name: str
    email: str
    avatar_url: Optional[str] = None
    role: str
    joined_at: Optional[str] = None

    class Config:
        from_attributes = True


class InviteResponse(BaseModel):
    status: str
    user_id: str
    email: str
    role: str


class RemoveMemberResponse(BaseModel):
    status: str
    user_id: str


class UpdateRoleResponse(BaseModel):
    status: str
    user_id: str
    role: str


class AssignProjectResponse(BaseModel):
    status: str
    project_id: str
    org_id: str


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@router.post("", status_code=201, response_model=OrgResponse)
@limiter.limit("10/minute")
async def create_organization(
    request: Request,
    req: OrgCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Yeni organizasyon olusturur.

    Benzersiz slug ile organizasyon oluşturur ve oluşturan kişiyi
    otomatik olarak owner rolüyle üye olarak ekler.

    Raises:
        401: Kimlik doğrulama gerekli
        409: Bu slug zaten kullanımda
        429: Rate limit aşıldı (10 istek/dakika)
    """
    existing = await db.execute(
        select(Organization).where(Organization.slug == req.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Bu slug zaten kulanimda")

    org = Organization(
        id=str(uuid.uuid4()),
        name=req.name,
        slug=req.slug,
        owner_id=current_user["id"],
        plan="free",
    )
    db.add(org)
    await db.flush()

    # Owner'i otomatik member olarak ekle
    member = OrgMember(
        id=str(uuid.uuid4()),
        org_id=org.id,
        user_id=current_user["id"],
        role="owner",
    )
    db.add(member)
    await db.commit()
    await db.refresh(org)

    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "plan": org.plan,
        "created_at": org.created_at.isoformat() if org.created_at else None,
    }


@router.get("", response_model=List[OrgResponse])
async def list_my_organizations(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcının üye olduğu tüm organizasyonları listeler.

    Mevcut kullanıcının üyeliği bulunan organizasyonları
    ada göre sıralayarak döndürür.

    Raises:
        401: Kimlik doğrulama gerekli
    """
    result = await db.execute(
        select(Organization)
        .join(OrgMember, OrgMember.org_id == Organization.id)
        .where(OrgMember.user_id == current_user["id"])
        .order_by(Organization.name)
    )
    orgs = result.scalars().all()
    return [
        {
            "id": o.id,
            "name": o.name,
            "slug": o.slug,
            "plan": o.plan,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in orgs
    ]


@router.get("/{org_id}", response_model=OrgDetailResponse)
async def get_organization(
    org_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Organizasyon detaylarını getirir.

    Üye sayısı, proje sayısı, plan bilgisi ve üye limiti dahil
    organizasyonun tüm detaylarını döndürür. Üyelik zorunludur.

    Raises:
        401: Kimlik doğrulama gerekli
        403: Organizasyona erişim yetkiniz yok
        404: Organizasyon bulunamadı
    """
    membership = await db.execute(
        select(OrgMember).where(
            OrgMember.org_id == org_id,
            OrgMember.user_id == current_user["id"],
        )
    )
    if not membership.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Bu organizasyona erisim yetkiniz yok")

    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organizasyon bulunamadi")

    member_count = await db.execute(
        select(func.count()).select_from(OrgMember).where(OrgMember.org_id == org_id)
    )
    project_count = await db.execute(
        select(func.count()).select_from(Project).where(Project.org_id == org_id)
    )

    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "plan": org.plan,
        "owner_id": org.owner_id,
        "max_members": org.max_members,
        "member_count": member_count.scalar() or 0,
        "project_count": project_count.scalar() or 0,
        "created_at": org.created_at.isoformat() if org.created_at else None,
    }


@router.get("/{org_id}/members", response_model=List[OrgMemberResponse])
async def list_members(
    org_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Organizasyon üyelerini listeler.

    Her üyenin kullanıcı bilgileri, rolü ve katılma tarihini
    döndürür. Organizasyona üyelik zorunludur.

    Raises:
        401: Kimlik doğrulama gerekli
        403: Erişim yetkiniz yok
    """
    membership = await db.execute(
        select(OrgMember).where(
            OrgMember.org_id == org_id,
            OrgMember.user_id == current_user["id"],
        )
    )
    if not membership.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Erisim yetkiniz yok")

    result = await db.execute(
        select(OrgMember, User)
        .join(User, User.id == OrgMember.user_id)
        .where(OrgMember.org_id == org_id)
        .order_by(OrgMember.joined_at)
    )
    members = result.all()
    return [
        {
            "id": m.OrgMember.id,
            "user_id": m.User.id,
            "name": m.User.name,
            "email": m.User.email,
            "avatar_url": m.User.avatar_url,
            "role": m.OrgMember.role,
            "joined_at": m.OrgMember.joined_at.isoformat() if m.OrgMember.joined_at else None,
        }
        for m in members
    ]


@router.post("/{org_id}/members", response_model=InviteResponse)
@limiter.limit("20/minute")
async def invite_member(
    request: Request,
    org_id: str,
    req: InviteMember,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Organizasyona yeni üye davet eder.

    E-posta ile kullanıcıyı bulur ve belirtilen rolle organizasyona ekler.
    Admin veya owner yetkisi gereklidir. Üye limiti kontrol edilir.

    Raises:
        400: Geçersiz rol
        401: Kimlik doğrulama gerekli
        403: Davet etme yetkisi yok veya üye limiti doldu
        404: Kullanıcı bulunamadı
        409: Kullanıcı zaten üye
        429: Rate limit aşıldı (20 istek/dakika)
    """
    caller = await db.execute(
        select(OrgMember).where(
            OrgMember.org_id == org_id,
            OrgMember.user_id == current_user["id"],
        )
    )
    caller_member = caller.scalar_one_or_none()
    if not caller_member or caller_member.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Uye davet etme yetkiniz yok (owner/admin gerekli)")

    if req.role not in ("admin", "member", "viewer"):
        raise HTTPException(status_code=400, detail="Gecersiz rol. Gecerli: admin, member, viewer")

    # Kullaniciyi bul
    user_result = await db.execute(select(User).where(User.email == req.email))
    target_user = user_result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="Bu e-posta ile kayitli kullanici bulunamadi")

    # Zaten uye mi?
    existing = await db.execute(
        select(OrgMember).where(
            OrgMember.org_id == org_id,
            OrgMember.user_id == target_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Kullanici zaten bu organizasyonun uyesi")

    # Max member kontrolu
    org = await db.get(Organization, org_id)
    member_count = await db.execute(
        select(func.count()).select_from(OrgMember).where(OrgMember.org_id == org_id)
    )
    if (member_count.scalar() or 0) >= (org.max_members if org else 5):
        raise HTTPException(status_code=403, detail=f"Organizasyon uye limiti ({org.max_members}) doldu")

    member = OrgMember(
        id=str(uuid.uuid4()),
        org_id=org_id,
        user_id=target_user.id,
        role=req.role,
        invited_by=current_user["id"],
    )
    db.add(member)
    await db.commit()

    return {
        "status": "invited",
        "user_id": target_user.id,
        "email": target_user.email,
        "role": req.role,
    }


@router.delete("/{org_id}/members/{user_id}", response_model=RemoveMemberResponse)
async def remove_member(
    org_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Organizasyondan üye çıkarır.

    Belirtilen kullanıcıyı organizasyondan kaldırır. Owner/admin yetkisi
    gereklidir. Owner çıkarılamaz ve kişi kendini çıkaramaz.

    Raises:
        400: Kendinizi çıkaramazsınız
        401: Kimlik doğrulama gerekli
        403: Üye çıkarma yetkisi yok veya owner çıkarılamaz
        404: Üye bulunamadı
    """
    caller = await db.execute(
        select(OrgMember).where(
            OrgMember.org_id == org_id,
            OrgMember.user_id == current_user["id"],
        )
    )
    caller_member = caller.scalar_one_or_none()
    if not caller_member or caller_member.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Uye cikarma yetkiniz yok")

    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Kendinizi organizasyondan cikaramazsiniz")

    target = await db.execute(
        select(OrgMember).where(
            OrgMember.org_id == org_id,
            OrgMember.user_id == user_id,
        )
    )
    target_member = target.scalar_one_or_none()
    if not target_member:
        raise HTTPException(status_code=404, detail="Uye bulunamadi")

    if target_member.role == "owner":
        raise HTTPException(status_code=403, detail="Owner cikarilmaz")

    await db.delete(target_member)
    await db.commit()

    return {"status": "removed", "user_id": user_id}


@router.put("/{org_id}/members/{user_id}/role", response_model=UpdateRoleResponse)
async def update_member_role(
    org_id: str,
    user_id: str,
    role: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Üyenin rolünü değiştirir.

    Belirtilen üyenin organizasyondaki rolünü günceller.
    Yalnızca owner yetkisine sahip kullanıcılar rol değiştirebilir.

    Raises:
        400: Geçersiz rol
        401: Kimlik doğrulama gerekli
        403: Rol değiştirme yetkisi yok (owner gerekli)
        404: Üye bulunamadı
    """
    caller = await db.execute(
        select(OrgMember).where(
            OrgMember.org_id == org_id,
            OrgMember.user_id == current_user["id"],
        )
    )
    caller_member = caller.scalar_one_or_none()
    if not caller_member or caller_member.role != "owner":
        raise HTTPException(status_code=403, detail="Rol degistirme yetkiniz yok (owner gerekli)")

    if role not in ("admin", "member", "viewer"):
        raise HTTPException(status_code=400, detail="Gecersiz rol")

    target = await db.execute(
        select(OrgMember).where(
            OrgMember.org_id == org_id,
            OrgMember.user_id == user_id,
        )
    )
    target_member = target.scalar_one_or_none()
    if not target_member:
        raise HTTPException(status_code=404, detail="Uye bulunamadi")

    target_member.role = role
    await db.commit()

    return {"status": "updated", "user_id": user_id, "role": role}


@router.post("/{org_id}/projects/{project_id}", response_model=AssignProjectResponse)
async def assign_project_to_org(
    org_id: str,
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Projeyi organizasyona bağlar.

    Proje sahibi olan kullanıcı, projesini belirtilen organizasyona atar.
    Hem proje sahibi hem de organizasyonda admin/owner olması gerekir.

    Raises:
        401: Kimlik doğrulama gerekli
        403: Organizasyona proje atama yetkisi yok
        404: Proje bulunamadı veya yetkiniz yok
    """
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Proje bulunamadi veya yetkiniz yok")

    caller = await db.execute(
        select(OrgMember).where(
            OrgMember.org_id == org_id,
            OrgMember.user_id == current_user["id"],
        )
    )
    caller_member = caller.scalar_one_or_none()
    if not caller_member or caller_member.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Organizasyona proje atama yetkiniz yok")

    project.org_id = org_id
    await db.commit()

    return {"status": "assigned", "project_id": project_id, "org_id": org_id}
