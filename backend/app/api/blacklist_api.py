"""Blacklist API — manage user's blacklist rules."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import User, BlacklistRule
from app.api.deps import require_user

router = APIRouter(prefix="/api/blacklist", tags=["blacklist"])


class BlacklistRuleCreate(BaseModel):
    rule_line: str


class BlacklistRuleUpdate(BaseModel):
    is_active: Optional[bool] = None
    rule_line: Optional[str] = None


@router.get("")
async def list_rules(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BlacklistRule)
        .where(BlacklistRule.user_id == user.id)
        .order_by(BlacklistRule.created_at.desc())
    )
    rules = result.scalars().all()
    return {
        "rules": [
            {
                "id": r.id,
                "rule_line": r.rule_line,
                "is_active": r.is_active,
            }
            for r in rules
        ]
    }


@router.post("", status_code=201)
async def add_rule(
    body: BlacklistRuleCreate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    rule = BlacklistRule(
        user_id=user.id,
        rule_line=body.rule_line.strip(),
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return {"id": rule.id, "message": "Rule added"}


@router.put("/{rule_id}")
async def update_rule(
    rule_id: int,
    body: BlacklistRuleUpdate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BlacklistRule).where(
            BlacklistRule.id == rule_id, BlacklistRule.user_id == user.id
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if body.is_active is not None:
        rule.is_active = body.is_active
    if body.rule_line is not None:
        rule.rule_line = body.rule_line.strip()
    await db.commit()
    return {"message": "Rule updated"}


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BlacklistRule).where(
            BlacklistRule.id == rule_id, BlacklistRule.user_id == user.id
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
    return {"message": "Rule deleted"}
