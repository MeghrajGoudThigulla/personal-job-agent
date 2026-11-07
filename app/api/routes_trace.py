from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.core.models import AuditLog

router = APIRouter(prefix="/api/trace", tags=["Traceability & Audit"])

@router.get("/logs")
async def get_audit_logs(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Returns the most recent audit logs for full system traceability."""
    res = await db.execute(select(AuditLog).order_by(desc(AuditLog.timestamp)).limit(limit))
    logs = res.scalars().all()
    return [log.to_dict() for log in logs]
