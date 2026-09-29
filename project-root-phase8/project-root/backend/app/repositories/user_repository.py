"""
Data access for User/Role. Role is always eagerly loaded (selectinload)
so callers never trigger a lazy-load from an async context — that
would raise MissingGreenlet, not silently work like it does in sync
SQLAlchemy code.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Role, User


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.email == email)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def get_role_by_name(db: AsyncSession, name: str) -> Role | None:
    result = await db.execute(select(Role).where(Role.name == name))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, email: str, password_hash: str, role_id: int) -> User:
    user = User(email=email, password_hash=password_hash, role_id=role_id)
    db.add(user)
    await db.flush()
    await db.refresh(user, attribute_names=["role"])
    return user
