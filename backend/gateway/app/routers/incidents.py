import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Incident, IncidentUpdate

router = APIRouter(prefix="/api/status", tags=["incidents"])
logger = logging.getLogger(__name__)


class IncidentCreate(BaseModel):
    title: str
    message: str
    severity: str = "minor"
    affected_components: list[str] | None = None


class IncidentUpdateCreate(BaseModel):
    message: str
    status: str


@router.get("/incidents")
async def list_incidents(
    status: str | None = None,
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint — auth gerektirmez."""
    query = select(Incident).order_by(Incident.created_at.desc()).limit(limit)
    if status:
        query = query.where(Incident.status == status)

    result = await db.execute(query)
    incidents = result.scalars().all()

    return {
        "items": [
            {
                "id": i.id,
                "title": i.title,
                "status": i.status,
                "severity": i.severity,
                "message": i.message,
                "affected_components": i.affected_components,
                "resolved_at": i.resolved_at.isoformat() if i.resolved_at else None,
                "created_at": i.created_at.isoformat(),
                "updated_at": i.updated_at.isoformat(),
            }
            for i in incidents
        ]
    }


@router.get("/incidents/{incident_id}")
async def get_incident(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    updates_result = await db.execute(
        select(IncidentUpdate).where(IncidentUpdate.incident_id == incident_id)
        .order_by(IncidentUpdate.created_at.desc())
    )
    updates = updates_result.scalars().all()

    return {
        "id": incident.id,
        "title": incident.title,
        "status": incident.status,
        "severity": incident.severity,
        "message": incident.message,
        "affected_components": incident.affected_components,
        "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
        "created_at": incident.created_at.isoformat(),
        "updated_at": incident.updated_at.isoformat(),
        "updates": [
            {
                "id": u.id,
                "message": u.message,
                "status": u.status,
                "created_at": u.created_at.isoformat(),
            }
            for u in updates
        ],
    }


@router.post("/incidents")
async def create_incident(
    body: IncidentCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    incident = Incident(
        title=body.title,
        message=body.message,
        severity=body.severity,
        affected_components=body.affected_components,
        created_by=current_user["id"],
    )
    db.add(incident)
    await db.commit()
    await db.refresh(incident)

    logger.info("Incident created: %s by user %s", incident.id, current_user["id"])
    return {"id": incident.id, "status": incident.status}


@router.post("/incidents/{incident_id}/updates")
async def add_incident_update(
    incident_id: str,
    body: IncidentUpdateCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident_update = IncidentUpdate(
        incident_id=incident_id,
        message=body.message,
        status=body.status,
        created_by=current_user["id"],
    )
    db.add(incident_update)

    incident.status = body.status
    incident.updated_at = datetime.utcnow()
    if body.status == "resolved":
        incident.resolved_at = datetime.utcnow()

    await db.commit()

    logger.info("Incident %s updated to %s", incident_id, body.status)
    return {"id": incident_update.id, "incident_status": body.status}


@router.get("/summary")
async def status_summary(db: AsyncSession = Depends(get_db)):
    """Public status summary — overall system health."""
    active_result = await db.execute(
        select(Incident).where(Incident.status.in_(["investigating", "identified", "monitoring"]))
    )
    active_incidents = active_result.scalars().all()

    if not active_incidents:
        overall = "operational"
    elif any(i.severity == "critical" for i in active_incidents):
        overall = "major_outage"
    elif any(i.severity == "major" for i in active_incidents):
        overall = "partial_outage"
    else:
        overall = "degraded_performance"

    return {
        "status": overall,
        "active_incidents": len(active_incidents),
        "incidents": [
            {"id": i.id, "title": i.title, "severity": i.severity, "status": i.status}
            for i in active_incidents
        ],
    }
