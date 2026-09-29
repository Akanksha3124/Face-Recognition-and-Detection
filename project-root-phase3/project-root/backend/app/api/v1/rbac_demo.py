"""
Phase 3 verification endpoints only — they exist to prove the
authorization dependency works per role before any real feature
routes exist. Delete or repurpose once Phase 4+ adds actual
role-gated endpoints (persons/cases/verification/admin).
"""
from fastapi import APIRouter, Depends

from app.core.deps import get_current_user, require_roles
from app.models import User

router = APIRouter()


@router.get("/any-authenticated")
async def any_authenticated(current_user: User = Depends(get_current_user)) -> dict:
    return {"message": f"Hello {current_user.email}", "role": current_user.role.name}


@router.get("/admin-only")
async def admin_only(current_user: User = Depends(require_roles("ADMIN"))) -> dict:
    return {"message": "Welcome, admin.", "role": current_user.role.name}


@router.get("/investigator-only")
async def investigator_only(current_user: User = Depends(require_roles("INVESTIGATOR"))) -> dict:
    return {"message": "Welcome, investigator.", "role": current_user.role.name}


@router.get("/disaster-responder-only")
async def disaster_responder_only(current_user: User = Depends(require_roles("DISASTER_RESPONDER"))) -> dict:
    return {"message": "Welcome, disaster responder.", "role": current_user.role.name}


@router.get("/verifier-only")
async def verifier_only(current_user: User = Depends(require_roles("VERIFIER"))) -> dict:
    return {"message": "Welcome, verifier.", "role": current_user.role.name}
