from app.models import AuditLog
from sqlalchemy.ext.asyncio import AsyncSession


async def create_audit_log(
    db: AsyncSession,
    *,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None,
    extra_data: dict | None = None,
) -> AuditLog:
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        extra_data=extra_data,
    )
    db.add(log)
    await db.flush()
    return log
