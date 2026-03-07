"""Support ticket management router."""
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import SupportTicket
from app.limiter import limiter

router = APIRouter(prefix="/support", tags=["support"])


class SupportTicketCreate(BaseModel):
    subject: str = Field(..., min_length=5, max_length=200)
    message: str = Field(..., min_length=10, max_length=5000)
    category: Literal["bug", "feature", "billing", "general"] = "general"
    priority: Literal["low", "medium", "high"] = "medium"


class SupportTicketResponse(BaseModel):
    ticket_id: str
    subject: str
    category: str
    priority: str
    status: str
    created_at: str
    estimated_response_hours: int


@router.post("", response_model=SupportTicketResponse, status_code=201)
@limiter.limit("5/minute")
async def create_support_ticket(
    request: Request,
    req: SupportTicketCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Yeni destek talebi oluşturur.

    Konu, mesaj, kategori ve öncelik bilgileriyle destek talebi açar.
    Önceliğe göre tahmini yanıt süresi hesaplanır (high: 4s, medium: 24s, low: 72s).

    Raises:
        401: Kimlik doğrulama gerekli
        422: Geçersiz istek verisi (konu/mesaj uzunluğu, geçersiz kategori/öncelik)
        429: Rate limit aşıldı (5 istek/dakika)
    """
    ticket = SupportTicket(
        id=str(uuid.uuid4()),
        user_id=current_user["id"],
        subject=req.subject,
        message=req.message,
        category=req.category,
        priority=req.priority,
        status="open",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)

    # Önceliğe göre tahmini yanıt süresi
    response_hours = {"high": 4, "medium": 24, "low": 72}.get(req.priority, 24)

    return SupportTicketResponse(
        ticket_id=ticket.id,
        subject=ticket.subject,
        category=ticket.category,
        priority=ticket.priority,
        status=ticket.status,
        created_at=ticket.created_at.isoformat(),
        estimated_response_hours=response_hours,
    )


@router.get("")
async def list_my_tickets(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcının kendi destek taleplerini listeler.

    Mevcut kullanıcıya ait tüm destek taleplerini oluşturulma
    tarihine göre en yeniden en eskiye sıralayarak döndürür.

    Raises:
        401: Kimlik doğrulama gerekli
    """
    result = await db.execute(
        select(SupportTicket)
        .where(SupportTicket.user_id == current_user["id"])
        .order_by(SupportTicket.created_at.desc())
    )
    tickets = result.scalars().all()
    return [
        {
            "ticket_id": t.id,
            "subject": t.subject,
            "category": t.category,
            "priority": t.priority,
            "status": t.status,
            "created_at": t.created_at.isoformat(),
        }
        for t in tickets
    ]
